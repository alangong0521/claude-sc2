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
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.units import Units

from bot.production_plans import gas_target, worker_target

if TYPE_CHECKING:
    from ares import AresBot

# 神族流派(造兵配方/科技链/升级/chrono/追加产能/一次性建造)全部进 flows.yml,
# 按 BUILD env 选块(run.py 在起游戏前已把 BUILD 写进 os.environ 并归一)。
# 本文件不再有 per-流派硬编码常量 —— 加流派改 flows.yml,不动这里。
from bot.flow_config import FlowConfig


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
        # 流派配置(flows.yml,神族生产侧单一真相源);Terran/Zerg 路径不走它。
        self._flow: FlowConfig = FlowConfig.load(os.environ.get("BUILD"))
        # 兵种组成注册表(army_composition.yml):Terran/Zerg 路径的 spawn/升级从这里读,
        # 神族路径的造兵已改走 self._flow。
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
        # 兵种配方从 flows.yml 当前流派读(spawn_dict 只含 proportion>0 的兵种)。
        # freeflow_mode 按流派配置:多兵种流派必开(true=配比只当优先序不当上限),
        # 否则兵力在精确配比点永久死锁(C3c 诊断出的 stalker 停产第二根因)。
        macro_plan.add(
            SpawnController(
                army_composition_dict=self._flow.spawn_dict(),
                spawn_target=self._front_point(),  # F1: 折跃向前线(非主基地),配合前线水晶塔远程投送
                freeflow_mode=self._flow.freeflow,
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
        await self._build_flow_structures(building_counter, structures_dict)
        self._morph_gateways()
        self._auto_expand(macro_plan)
        # 按流派配置扩产能(矿富余追加产兵建筑,治"矿堆花不出去")
        self._build_extra_production(structures_dict)
        self._build_forward_pylon()  # F1: 前线水晶塔(投送),各流派共用
        self._chrono_structures()
        # 升级交 ares UpgradeController（自动建 FORGE/TWILIGHTCOUNCIL 等前置 + 研究 + 打日志）。
        _upgrades = self._flow.upgrade_ids()
        if _upgrades:
            self.ai.register_behavior(
                UpgradeController(_upgrades, base_location=self.ai.start_location)
            )

        # one off task to build an oracle（流派配置里 one_off 含 ORACLE 才造；
        # 需舰队航标 + 有空闲就绪星门）
        if not self._built_single_oracle and UnitID.ORACLE in self._flow.one_off_ids():
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

    def _auto_expand(self, macro_plan: MacroPlan) -> None:
        """C3b 自动开矿(flows.yml auto_expand,缺省关):到 at 秒把基地扩到 to 个。
        地面消耗流的命脉(B2/C1 实证 stalker 全程单矿打不起消耗战);天空流不开。
        与司令 expand=yes 杠杆不冲突:到数后 ExpansionController 自然不再动作。"""
        ae = self._flow.auto_expand
        if ae is None or self.ai.time < ae.at:
            return
        if self.ai.townhalls.amount >= ae.to:
            return
        macro_plan.add(ExpansionController(to_count=ae.to, max_pending=1))

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

    async def _build_flow_structures(
        self,
        building_counter: dict[UnitID, int],
        structures_dict: dict[UnitID, list[Unit]],
    ) -> None:
        """按当前流派的 core_structures 爬科技链(flows.yml 配置驱动)。

        building_counter : Dict[UnitTypeId, int]
            What is currently pending in the building tracker
        structures_dict : Dict[UnitTypeId, Units]
            Data structure of current buildings.
        """
        # 气随基地数放大：每个已建好的基地采满 2 个气矿（吃气大户流派的命脉）。
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

        for structure_id in self._flow.core_structure_ids():
            if structure_id == UnitID.FLEETBEACON:
                # 特例:tech_requirement_progress 对舰队航标不准,需有就绪星门才建
                if (
                    not self._structure_present_or_pending(UnitID.FLEETBEACON)
                    and [s for s in structures_dict[UnitID.STARGATE] if s.is_ready]
                ):
                    await self._build_core_structure(UnitID.FLEETBEACON)
            else:
                await self._build_core_structure(structure_id)

    def _morph_gateways(self) -> None:
        """WARPGATERESEARCH 完成后,把就绪空闲的 gateway 变形为 warpgate。

        关键背景(B2 baseline 0-10 的根因):ares `SpawnController.execute` 在 warpgate
        研究完成后,只要还有就绪空闲的 gateway 就 `return False` —— 主动停产等变形;
        而 vendored ares 全框架**没有**现成的变形行为,不下 MORPH_WARPGATE 的话,
        生产从研究完成那一刻起永久停摆。没研究(默认流派不含该升级)时 no-op。"""
        if UpgradeId.WARPGATERESEARCH not in self.ai.state.upgrades:
            return
        for gateway in self.manager_mediator.get_own_structures_dict[UnitID.GATEWAY]:
            if gateway.is_ready and gateway.is_idle:
                gateway(AbilityId.MORPH_WARPGATE)

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

    def _build_extra_production(self, structures_dict: dict[UnitID, list[Unit]]) -> None:
        """矿有富余时按流派配置追加产兵建筑（治"矿堆花不出去"）。
        得先有第一个同类建筑（核心科技就位）才追加。GATEWAY 特例:升级成 WARPGATE
        后类型变了,两者都算产能。"""
        ep = self._flow.extra_production
        if ep is None:
            return
        sid = getattr(UnitID, ep.id_name, None)
        if sid is None:
            return
        have_structures: list[Unit] = list(structures_dict[sid])
        if sid == UnitID.GATEWAY:
            have_structures += structures_dict[UnitID.WARPGATE]
        if not have_structures:
            return
        desired = min(ep.cap, ep.base + self.ai.townhalls.ready.amount)
        have = len(have_structures) + self.manager_mediator.get_building_counter[sid]
        if (
            have < desired
            and self.ai.minerals > 400  # 只在矿有富余时追加，别抢科技/造兵的钱
            and self.ai.can_afford(sid)
        ):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, sid)
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
        """当前流派 spawn 里优先级最高(proportion>0 且 priority 最小)的兵种枚举。
        chrono 判断"主力是否在造"用它;换流派自动跟随 flows.yml 配置。"""
        candidates = [
            (name, cfg) for name, cfg in self._flow.spawn.items()
            if cfg["proportion"] > 0
        ]
        if not candidates:
            return UnitID.TEMPEST  # 兜底
        name = min(candidates, key=lambda kv: kv[1]["priority"])[0]
        return getattr(UnitID, name, UnitID.TEMPEST)

    def _chrono_structures(self):
        """按流派 chrono 配置加速:targets 顺序取第一个有建筑的;
        when=always 见忙就加速,primary_pending 等主力在产(或一次性 oracle 的首次加速)。"""
        targets: list[Unit] = []
        for name in self._flow.chrono.targets:
            sid = getattr(UnitID, name, None)
            if sid is None:
                continue
            targets = self.manager_mediator.get_own_structures_dict[sid]
            if targets:
                break
        if not targets:
            return
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
            if self._flow.chrono.when == "always" or cy_unit_pending(self.ai, primary):
                nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, non_idle[0])
                return
            if not self._oracle_chrono:
                nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, non_idle[0])
                self._oracle_chrono = True
