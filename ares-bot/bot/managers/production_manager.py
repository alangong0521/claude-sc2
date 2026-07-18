import os
from typing import TYPE_CHECKING

from sc2.unit import Unit

from ares.behaviors.macro import (
    AutoSupply,
    BuildStructure,
    BuildWorkers,
    ExpansionController,
    GasBuildingController,
    ProductionController,
    ProtossStaticDefence,
    SpawnController,
    TechUp,
    UpgradeCCs,
    UpgradeController,
)
from ares.behaviors.macro.macro_plan import MacroPlan
from ares.consts import UnitRole
from cython_extensions.general_utils import cy_unit_pending
from cython_extensions.units_utils import cy_closest_to
from ares.managers.manager import Manager
from ares.managers.manager_mediator import ManagerMediator
from sc2.data import Race
from sc2.dicts.upgrade_researched_from import UPGRADE_RESEARCHED_FROM
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.units import Units

from bot.production_plans import gas_target, worker_target

if TYPE_CHECKING:
    from ares import AresBot

# 神族兵种流派（run.py 在导入本模块前已把 BUILD 写进 os.environ）：
#   tempest = 暴风舰天空体 + 先知骚扰（默认，与已验证行为逐位一致）
#   stalker = 纯追猎 blink 流（弃星门/舰队航标/先知，加议会研究 blink）
BUILD_FLOW: str = os.environ.get("BUILD", "tempest")
is_stalker_flow: bool = BUILD_FLOW == "stalker"

# 核心科技链：暴风舰流 = gateway+cyber+星门；追猎流 = gateway+cyber（星门是浪费，省 150/150）。
CORE_STRUCTURES: list[UnitID] = (
    [UnitID.GATEWAY, UnitID.CYBERNETICSCORE]
    if is_stalker_flow
    else [UnitID.GATEWAY, UnitID.CYBERNETICSCORE, UnitID.STARGATE]
)

# 升级列表：交 ares UpgradeController（自动 TechUp 建 FORGE/TWILIGHTCOUNCIL + 研究 + 打日志）。
#   追猎流：折跃门(warpgate) + blink + 地面武器/装甲/护盾 L1（L2/L3 后续追加）
#   暴风舰流：tempest 对地 + 空军装甲 L1/L2 + 护盾 L1
DESIRED_UPGRADES: list[UpgradeId] = (
    [
        UpgradeId.WARPGATERESEARCH,
        UpgradeId.BLINKTECH,
        UpgradeId.PROTOSSGROUNDWEAPONSLEVEL1,
        UpgradeId.PROTOSSGROUNDARMORSLEVEL1,
        UpgradeId.PROTOSSSHIELDSLEVEL1,
    ]
    if is_stalker_flow
    else [
        UpgradeId.TEMPESTGROUNDATTACKUPGRADE,
        UpgradeId.PROTOSSAIRARMORSLEVEL1,
        UpgradeId.PROTOSSAIRARMORSLEVEL2,
        UpgradeId.PROTOSSSHIELDSLEVEL1,
    ]
)

# 追猎流额外建 twilight council（blink 科技来源）；暴风舰流不需要，留空。
EXTRA_CORE_STRUCTURES: list[UnitID] = (
    [UnitID.TWILIGHTCOUNCIL] if is_stalker_flow else []
)

# 追猎流 SpawnController 配方（纯追猎）。暴风舰流走 self._army.spawn_dict()（army_composition.yml）。
# 追猎流 SpawnController 配方：追猎为主 + 狂热者混编（rush 杀伤力更高）。
# 暴风舰流走 self._army.spawn_dict()（army_composition.yml）。比例和须 = 1.0。
_STALKER_SPAWN: dict = {
    UnitID.STALKER: {"proportion": 0.7, "priority": 0},
    UnitID.ZEALOT: {"proportion": 0.3, "priority": 1},
}

class ProductionManager(Manager):
    def __init__(
        self,
        ai: "AresBot",
        config: dict,
        mediator: ManagerMediator,
    ) -> None:
        """Set up the manager.

        Parameters
        ----------
        ai :
            Bot object that will be running the game
        config :
            Dictionary with the data from the configuration file
        mediator :
            ManagerMediator used for getting information from other managers.

        Returns
        -------

        """
        super().__init__(ai, config, mediator)

        self._built_single_oracle: bool = False
        self._built_extra_production_pylon: bool = False
        self._forward_pylon_built: bool = False  # F1: 前线水晶塔(一次性,给折跃门提供前线电源)
        # can use a single chrono for the oracle
        self._oracle_chrono: bool = False
        # 通用建筑杠杆 build=<结构>（expand=yes 是 build=nexus 的别名）。
        # 一次性锁定：记下"目标数量"，造到就停；想再造先 clear 再下（同 scout 手感）。
        self._build_key: str | None = None
        self._build_target: int | None = None
        # 兵种组成从 army_composition.yml 读(单一真相源,按 bot 种族选块),不再硬编码 TEMPEST。
        from bot.army_config import ArmyComposition, bot_race_name
        self._army = ArmyComposition.load(race=bot_race_name(ai))

    async def update(self, iteration: int) -> None:
        """Handle production.

        TODO: Add `AutoSupply` when that feature is ready in ares

        Parameters
        ----------
        iteration :
            The game iteration.
        """
        # 种族分派:Terran 走 M1 生产层(ares ProductionController + SpawnController);
        # Zerg 尚未实现(见 status-and-roadmap M2)——先 no-op 造农民保命,不崩。
        if self.ai.race == Race.Terran:
            self._update_terran()
            return
        if self.ai.race == Race.Zerg:
            self._update_zerg()
            return

        # can_afford 守卫：钱够才派农民去造 pylon，否则农民走过去干等不采矿（idle bug 根因）。
        if not self._built_extra_production_pylon and self.ai.can_afford(UnitID.PYLON):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, UnitID.PYLON)
            )
            self._built_extra_production_pylon = True

        # use ares-sc2 macro behaviors for building pylons and units
        macro_plan: MacroPlan = MacroPlan()
        macro_plan.add(AutoSupply(base_location=self.ai.start_location))
        # 兵种组成：追猎流写死纯追猎(_STALKER_SPAWN)；暴风舰流走 army_composition.yml。
        macro_plan.add(
            SpawnController(
                army_composition_dict=_STALKER_SPAWN if is_stalker_flow else self._army.spawn_dict(),
                spawn_target=self._front_point(),  # F1: 折跃向前线(非主基地),配合前线水晶塔远程投送
            )
        )
        # 运营指挥·通用建筑杠杆 build=<结构>（expand=yes = build=nexus 别名）
        _order = getattr(self.ai, "steer_order", None) or {}
        self._handle_manual_build(_order, macro_plan)
        self.ai.register_behavior(macro_plan)

        # F2: 按局势铺防御塔(B+F+Cannon)——框架自动建 forge + 光子炮 + 护盾电池并补前置科技。
        if self._should_build_defense(_order):
            self.ai.register_behavior(
                ProtossStaticDefence(
                    photon_cannons_per_base=2,
                    shield_batteries_per_base=1,
                )
            )

        # custom behavior for all other production, using ares-sc2 to help
        building_counter: dict[UnitID, int] = self.manager_mediator.get_building_counter
        structures_dict: dict[
            UnitID, list[Unit]
        ] = self.manager_mediator.get_own_structures_dict

        self._build_probes(self.ai.ready_townhalls)
        await self._build_tempest_rush_structures(building_counter, structures_dict)
        # 按流派扩产能：追猎流补 gateway（主力产能来源），暴风舰流补星门。治"矿堆花不出去"。
        if is_stalker_flow:
            self._build_extra_gateways(structures_dict)
        else:
            self._build_extra_stargates(structures_dict)
        self._build_forward_pylon()  # F1: 前线水晶塔(投送),两流派共用
        self._chrono_structures()
        # 升级交 ares UpgradeController（自动建 FORGE/TWILIGHTCOUNCIL + 研究 + 打日志），
        # 替代手写 _research_upgrades（气体门槛过严要 310 气 / 不建 FORGE / 无日志 三 bug）。
        _upgrades = (
            DESIRED_UPGRADES
            if is_stalker_flow
            else (self._army.upgrade_ids() or DESIRED_UPGRADES)
        )
        if _upgrades:
            self.ai.register_behavior(
                UpgradeController(_upgrades, base_location=self.ai.start_location)
            )

        # one off task to build an oracle（仅暴风舰流；追猎流无星门无舰队航标，跳过）
        if not is_stalker_flow and not self._built_single_oracle:
            if (
                self.ai.can_afford(UnitID.ORACLE)
                and len(structures_dict[UnitID.FLEETBEACON]) > 0
                and self.ai.structures.filter(
                    lambda u: u.type_id == UnitID.STARGATE and u.is_ready and u.is_idle
                )
            ):
                self.ai.train(UnitID.ORACLE)
                self._built_single_oracle = True

    # ────────────────────────────── Terran 生产层 (M1) ──────────────────────────────
    def _update_terran(self) -> None:
        """人族生产:全部借 ares 种族无关/人族支持的宏行为,不手写建造顺序。

        组成: AutoSupply(补给站) + BuildWorkers(SCV) + GasBuildingController(炼油厂)
             + ProductionController(按 army_comp 自动补 rax/factory/starport,人族支持)
             + SpawnController(按 army_comp 出兵) + UpgradeCCs(升轨道指挥) + build 杠杆。
        ⚠️ 未跑局验证(M1):建造时机/addon(techlab/reactor)管理/架坦克等细节留待实测调
           (见 docs/status-and-roadmap.md M1/M4)。开局序列可由 terran_builds.yml 的 build runner 接管。
        """
        ai = self.ai
        base = ai.start_location
        spawn = self._army.spawn_dict()

        # 农民 + 轨道指挥(种族无关的 SCV/CC 升级)
        ai.register_behavior(BuildWorkers(to_count=worker_target(ai.townhalls.amount)))
        ai.register_behavior(UpgradeCCs(to=UnitID.ORBITALCOMMAND))

        # M3:升级配置化 —— army_composition.yml 的 terran.upgrades 交 ares UpgradeController
        # (种族无关,自动 tech-up)。列表空则不注册。
        if upgrades := self._army.upgrade_ids():
            ai.register_behavior(UpgradeController(upgrades, base_location=base))

        # 气:有军事生产建筑后每矿双气,开局先单气
        has_prod = any(
            self._structure_present_or_pending(s)
            for s in (UnitID.BARRACKS, UnitID.FACTORY, UnitID.STARPORT)
        )
        ai.register_behavior(GasBuildingController(
            to_count=gas_target(ai.townhalls.ready.amount, has_prod),
            closest_to=base,
        ))

        # 供给 / 造兵 / 自动补生产建筑(ProductionController 人族/神族支持)
        plan: MacroPlan = MacroPlan()
        plan.add(AutoSupply(base_location=base))
        if spawn:
            plan.add(SpawnController(army_composition_dict=spawn))
            plan.add(ProductionController(spawn, base_location=base))
        # 运营杠杆(build=barracks / expand=yes 等)复用同一套(expand 走 ExpansionController,种族无关)
        _order = getattr(ai, "steer_order", None) or {}
        self._handle_manual_build(_order, plan)
        ai.register_behavior(plan)

    def _update_zerg(self) -> None:
        """虫族生产 (M2):无 ProductionController(不支持 Zerg),改用 ares 种族无关积木自建。

        组成: BuildWorkers(drone) + AutoSupply(overlord,种族无关) + SpawnController(larva/morph 出兵)
             + TechUp(每个组成兵种自动补科技建筑,如 ROACH→RoachWarren,种族无关)
             + 女王(每巢一只) + UpgradeController(M3) + build/expand 杠杆(expand→hatchery)。
        ⚠️ 未跑局验证(M2):larva 注卵(inject)/铺菌毯/兵种节奏都没做 —— Zerg 宏离不开注卵,
           这块是 M2 剩余大头,必须跑局调(见 status-and-roadmap M2)。开局序可交 zerg_builds.yml。
        """
        ai = self.ai
        base = ai.start_location
        spawn = self._army.spawn_dict()

        ai.register_behavior(BuildWorkers(to_count=worker_target(ai.townhalls.amount)))

        plan: MacroPlan = MacroPlan()
        plan.add(AutoSupply(base_location=base))  # 种族无关:Zerg 下自动造 overlord
        if spawn:
            plan.add(SpawnController(army_composition_dict=spawn))
        # 每个在产兵种自动补所需科技建筑(TechUp 种族无关:ROACH→RoachWarren 等)
        for spec in self._army.units:
            if spec.proportion <= 0:
                continue
            uid = getattr(UnitID, spec.id_name, None)
            if uid is not None:
                plan.add(TechUp(desired_tech=uid, base_location=base))
        if upgrades := self._army.upgrade_ids():
            plan.add(UpgradeController(upgrades, base_location=base))
        _order = getattr(ai, "steer_order", None) or {}
        self._handle_manual_build(_order, plan)
        ai.register_behavior(plan)

        self._build_zerg_queens()

    def _build_zerg_queens(self) -> None:
        """每个巢穴配一只女王(需孵化池;由 TechUp/ZERGLING 或 build 杠杆先造出)。
        ⚠️ 只造女王,**没做注卵(inject larva)** —— 注卵是 Zerg 爆兵核心,列 M2 剩余,需跑局。"""
        ai = self.ai
        queen = getattr(UnitID, "QUEEN", None)
        pool = getattr(UnitID, "SPAWNINGPOOL", None)
        if queen is None or pool is None:
            return
        if not self._structure_present_or_pending(pool):
            return  # 没孵化池造不了女王
        have = ai.units(queen).amount + self.manager_mediator.get_building_counter[queen]
        if have >= ai.townhalls.amount:
            return
        for th in ai.townhalls.ready.idle:
            if ai.can_afford(queen):
                th.train(queen)
                break

    def _structure_present_or_pending(self, structure_type: UnitID) -> bool:
        return (
            len(self.manager_mediator.get_own_structures_dict[structure_type]) > 0
            or self.manager_mediator.get_building_counter[structure_type] > 0
        )

    async def _build_core_structure(self, structure_id: UnitID) -> None:
        """Here to prevent repeated logic building core structures.

        Parameters
        ----------
        structure_id : UnitTypeId
            What we want to build
        """
        if (
            not self._structure_present_or_pending(structure_id)
            and self.ai.tech_requirement_progress(structure_id) >= 1.0
            and self.ai.can_afford(structure_id)
        ):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, structure_id)
            )

    def _build_probes(self, ready_townhalls: Units) -> None:
        """Add probes.

        Parameters
        ----------
        ready_townhalls : Units
            Current ready nexuses we can train from.
        """
        # 农民上限随基地数放大：每矿 ~22（16 矿 + 6 气），封顶 70 给军队留供给。
        # 单矿时 22*1=22 与旧行为一致；开二矿后目标自动抬到 44，接着补农民采矿采气。
        if (
            self.ai.supply_workers < min(70, 22 * self.ai.townhalls.amount)
            and self.ai.can_afford(UnitID.PROBE)
            and self.ai.supply_left > 0
        ):
            if idle_ths := ready_townhalls.idle:
                for nexus in idle_ths:
                    nexus.train(UnitID.PROBE)

    async def _build_tempest_rush_structures(
        self,
        building_counter: dict[UnitID, int],
        structures_dict: dict[UnitID, list[Unit]],
    ) -> None:
        """Build everything we need towards Tempest tech.

        building_counter : Dict[UnitTypeId, int]
            What is currently pending in the building tracker
        structures_dict : Dict[UnitTypeId, Units]
            Data structure of current buildings.
        """
        # 气随基地数放大：每个已建好的基地采满 2 个气矿（暴风舰吃气大户，之前写死 2 会气荒）。
        # 前期没兵营时先只开 1 个气（保持原起手节奏）。
        max_gas_buildings = (
            2 * self.ai.townhalls.ready.amount
            if UnitID.GATEWAY in structures_dict
            else 1
        )
        if self.ai.gas_buildings.amount < max_gas_buildings:
            self._build_gas()

        ready_pylons: list[Unit] = [
            p for p in structures_dict[UnitID.PYLON] if p.is_ready
        ]
        if not ready_pylons:
            return

        for core_structure_id in CORE_STRUCTURES:
            await self._build_core_structure(core_structure_id)

        # add fleetbeacon separate, since `tech_requirement_progress` doesn't work
        # 仅暴风舰流需要舰队航标（造暴风舰/先知前置）；追猎流不需要，跳过省气。
        if (
            not is_stalker_flow
            and not self._structure_present_or_pending(UnitID.FLEETBEACON)
            and [s for s in structures_dict[UnitID.STARGATE] if s.is_ready]
        ):
            await self._build_core_structure(UnitID.FLEETBEACON)

        # 追猎流额外建 twilight council（blink 科技来源）。cybernetics core 已在
        # CORE_STRUCTURES 里造，twilight 只依赖它，core 就绪即可建。
        if EXTRA_CORE_STRUCTURES:
            for extra_id in EXTRA_CORE_STRUCTURES:
                await self._build_core_structure(extra_id)

    def _build_gas(self) -> None:
        """在离某个基地最近的空气矿上建一个气矿厂（自动选农民）。含分矿的气矿。"""
        if (
            self.manager_mediator.get_building_counter[UnitID.ASSIMILATOR] != 0
            or not self.ai.can_afford(UnitID.ASSIMILATOR)
            or not self.ai.townhalls
        ):
            return
        # 只挑"离某个基地够近(<12)且还没被占"的气矿 → 分矿的气也能采上
        geysers: Units = self.ai.vespene_geyser.filter(
            lambda vg: not self.ai.gas_buildings.closer_than(2, vg)
            and self.ai.townhalls.closest_distance_to(vg) < 12
        )
        if not geysers:
            return
        if worker := self.ai.mediator.select_worker(
            target_position=self.ai.start_location
        ):
            self.ai.mediator.build_with_specific_worker(
                worker=worker,
                structure_type=UnitID.ASSIMILATOR,
                pos=cy_closest_to(self.ai.start_location, geysers),
            )
            self.ai.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)

    def _build_extra_stargates(self, structures_dict: dict[UnitID, list[Unit]]) -> None:
        """矿有富余时自动追加星门，把积压的矿变成暴风舰产能（治"5880 矿花不出去"）。
        得先有第一个星门（核心科技就位）才追加；每多一个基地多一个，封顶 6。"""
        stargates = structures_dict[UnitID.STARGATE]
        if not stargates:
            return
        desired = min(6, 1 + self.ai.townhalls.ready.amount)
        have = len(stargates) + self.manager_mediator.get_building_counter[UnitID.STARGATE]
        if (
            have < desired
            and self.ai.minerals > 400  # 只在矿有富余时追加，别抢科技/暴风舰的钱
            and self.ai.can_afford(UnitID.STARGATE)
        ):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, UnitID.STARGATE)
            )

    def _build_extra_gateways(self, structures_dict: dict[UnitID, list[Unit]]) -> None:
        """矿有富余时自动追加 gateway/warpgate，把积压的矿变成追猎产能（治"3000+ 矿花不出去"）。
        得先有第一个 gateway（核心科技就位）才追加；随基地数放大，封顶 8。stalker 流主力产能来源。"""
        # gateway morph 成 warpgate 后类型变 WARPGATE，两者都算产能建筑。
        gateways = structures_dict[UnitID.GATEWAY] + structures_dict[UnitID.WARPGATE]
        if not gateways:
            return
        desired = min(8, 2 + self.ai.townhalls.ready.amount)
        have = len(gateways) + self.manager_mediator.get_building_counter[UnitID.GATEWAY]
        if (
            have < desired
            and self.ai.minerals > 400  # 只在矿有富余时追加，别抢科技/造兵的钱
            and self.ai.can_afford(UnitID.GATEWAY)
        ):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, UnitID.GATEWAY)
            )

    def _front_point(self) -> Point2:
        """F1: 前线折跃点 —— 敌我之间偏敌 60%。让 WarpInManager 优先把兵折跃到前线
        水晶塔（而非主基地），配合 _build_forward_pylon 实现远程投送。"""
        return self.ai.start_location.towards(self.ai.focused_enemy_start(), 0.6)

    def _build_forward_pylon(self) -> None:
        """F1: 在前线造水晶塔，给折跃门提供前线电源（兵秒投前线，不全程走）。
        条件：warpgate 已研究（能折跃）+ 矿富余 + 还没造过（一次性）。
        ⚠️ 前线塔易被打，是最小方案的固有风险（完整方案会用折跃棱镜）。"""
        if self._forward_pylon_built:
            return
        # warpgate 研究好才值得造前线塔（否则 gateway train 用不上前线电源）
        if UpgradeId.WARPGATERESEARCH not in self.ai.state.upgrades:
            return
        if self.ai.minerals > 300 and self.ai.can_afford(UnitID.PYLON):
            self.ai.register_behavior(
                BuildStructure(self._front_point(), UnitID.PYLON)
            )
            self._forward_pylon_built = True

    def _should_build_defense(self, order: dict) -> bool:
        """F2: 是否铺防御塔(B+F+Cannon)。判据: 司令下令 defend=yes / 中后期(>6分钟)自动铺。"""
        if order.get("defend") == "yes":
            return True
        if self.ai.time > 360:  # 6 分钟后自动铺防御
            return True
        return False

    def _resolve_buildable(self, name: str) -> UnitID | None:
        """build=<名> → UnitID。先走 levers.resolve_build_name 归一(复用 CLI 同一份逻辑),
        再 getattr(UnitID, ...)。认不出 → None。"""
        from bot.levers import resolve_build_name
        enum_name = resolve_build_name(name)
        if enum_name is None:
            return None
        return getattr(UnitID, enum_name, None)

    def _count_structure(self, sid: UnitID) -> int:
        """已有 + 在建 的数量（nexus 用 townhalls 计）。"""
        if sid == UnitID.NEXUS:
            return self.ai.townhalls.amount
        return (
            len(self.manager_mediator.get_own_structures_dict[sid])
            + self.manager_mediator.get_building_counter[sid]
        )

    def _handle_manual_build(self, order: dict, macro_plan: MacroPlan) -> None:
        """通用建筑杠杆 build=<结构>：参谋长只说造什么，选农民/选位置全归 bot（ares 原语）。
        一次性锁定："当前数量+1"为目标，造到就停；想再造先 clear 再下（同 scout/expand）。
        expand=yes 收编为 build=nexus 的别名。"""
        want = (order.get("build") or "").strip().lower()
        if not want and order.get("expand") == "yes":
            want = "nexus"
        if not want:
            self._build_key = None
            self._build_target = None
            return

        sid = self._resolve_buildable(want)
        if sid is None:
            return  # 认不出的结构名，忽略

        # 新的 build 请求 → 锁定目标数量
        if self._build_key != want:
            self._build_key = want
            self._build_target = self._count_structure(sid) + 1

        if self._count_structure(sid) >= self._build_target:
            return  # 已达目标，停（等 clear 重置）

        if sid == UnitID.NEXUS:
            macro_plan.add(
                ExpansionController(to_count=self._build_target, max_pending=1)
            )
        elif sid == UnitID.ASSIMILATOR:
            self._build_gas()
        elif (
            self.manager_mediator.get_building_counter[sid] == 0
            and self.ai.can_afford(sid)
        ):
            self.ai.register_behavior(BuildStructure(self.ai.start_location, sid))

    def _primary_unit_id(self) -> UnitID:
        """army_composition 里优先级最高(proportion>0 且 priority 最小)的兵种枚举。
        用于 chrono/升级判断"主力是否在造"。换 build 时自动跟随配置。"""
        candidates = [u for u in self._army.units if u.proportion > 0]
        if not candidates:
            return UnitID.TEMPEST  # 兜底
        primary = min(candidates, key=lambda u: u.priority)
        return getattr(UnitID, primary.id_name, UnitID.TEMPEST)

    def _chrono_structures(self):
        """Decide what to chrono. 暴风舰流加速星门(造暴风舰);追猎流加速 gateway(出追猎),
        没 gateway 时退 twilight council(抢 blink 科技)。"""
        if is_stalker_flow:
            targets: list[Unit] = self.manager_mediator.get_own_structures_dict[UnitID.GATEWAY]
            if not targets:  # 还没 gateway(或已全升 warpgate)→ 退 twilight 抢 blink
                targets = self.manager_mediator.get_own_structures_dict[UnitID.TWILIGHTCOUNCIL]
        else:
            targets = self.manager_mediator.get_own_structures_dict[UnitID.STARGATE]
        primary = self._primary_unit_id()
        for nexus in self.ai.townhalls:
            if nexus.energy < 50:
                continue
            non_idle = [
                s for s in targets
                if not s.is_idle
                and not s.has_buff(BuffId.CHRONOBOOSTENERGYCOST)
            ]
            if not non_idle:
                continue
            if is_stalker_flow or cy_unit_pending(self.ai, primary):
                nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, non_idle[0])
                return
            if not self._oracle_chrono:
                nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, non_idle[0])
                self._oracle_chrono = True

    def _research_upgrades(self):
        """Decide what to research."""
        # 升级只在主力兵种已在产时开始:暴风舰流看 TEMPEST 在造,追猎流看 STALKER 在造。
        pending_main = (
            cy_unit_pending(self.ai, UnitID.STALKER)
            if is_stalker_flow
            else cy_unit_pending(self.ai, UnitID.TEMPEST)
        )
        if pending_main == 0:
            return

        structure_dict: dict[
            UnitID, list[Unit]
        ] = self.manager_mediator.get_own_structures_dict
        # 升级列表:追猎流用硬编码 DESIRED_UPGRADES(blink+地面装甲;不读 yaml —— yaml 仍是
        # 暴风舰升级,test_shipped_protoss_upgrades_unchanged 要它不动);
        # 暴风舰流走 army_composition.yml,空则回退 DESIRED_UPGRADES(向后兼容)。
        desired = DESIRED_UPGRADES if is_stalker_flow else (self._army.upgrade_ids() or DESIRED_UPGRADES)
        for upgrade_id in desired:
            researched_from: UnitID = UPGRADE_RESEARCHED_FROM[upgrade_id]
            cost = self.ai.calculate_cost(upgrade_id)
            # ensure there is always nearly enough for a tempest
            # before spending all the banked vespene
            if self.ai.vespene - cost.vespene < 160:
                continue
            if (
                self.ai.can_afford(upgrade_id)
                and len([s for s in structure_dict[researched_from] if s.is_idle]) > 0
            ):
                if self.ai.research(upgrade_id):
                    return
