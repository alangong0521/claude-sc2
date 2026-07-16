from typing import TYPE_CHECKING

from sc2.unit import Unit

from ares.behaviors.macro import (
    AutoSupply,
    BuildStructure,
    BuildWorkers,
    ExpansionController,
    GasBuildingController,
    ProductionController,
    SpawnController,
    UpgradeCCs,
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
from sc2.units import Units

from bot.production_plans import gas_target, worker_target

if TYPE_CHECKING:
    from ares import AresBot

# we always want one of each
CORE_STRUCTURES: list[UnitID] = [
    UnitID.GATEWAY,
    UnitID.CYBERNETICSCORE,
    UnitID.STARGATE,
]

DESIRED_UPGRADES: list[UpgradeId] = [
    UpgradeId.TEMPESTGROUNDATTACKUPGRADE,
    UpgradeId.PROTOSSAIRARMORSLEVEL1,
    UpgradeId.PROTOSSAIRARMORSLEVEL2,
]

# 通用建筑杠杆 build=<名> 的别名 → UnitID。认不出的名字再退回 UnitID[名.upper()]。
# 注意:steer_vocab.BUILD_ALIASES 是"别名→规范名词表"给 CLI 校验用;本表是"别名→引擎枚举"
# 给 bot 造建筑用。两套别名键应保持一致 —— 改一处记得改另一处(或用 canonical_build 归一)。
BUILD_ALIASES: dict[str, UnitID] = {
    "nexus": UnitID.NEXUS, "base": UnitID.NEXUS, "expand": UnitID.NEXUS,
    "gas": UnitID.ASSIMILATOR, "assimilator": UnitID.ASSIMILATOR, "geyser": UnitID.ASSIMILATOR,
    "stargate": UnitID.STARGATE, "gateway": UnitID.GATEWAY,
    "cyber": UnitID.CYBERNETICSCORE, "cyberneticscore": UnitID.CYBERNETICSCORE,
    "forge": UnitID.FORGE, "robo": UnitID.ROBOTICSFACILITY,
    "roboticsfacility": UnitID.ROBOTICSFACILITY, "fleetbeacon": UnitID.FLEETBEACON,
    "twilight": UnitID.TWILIGHTCOUNCIL, "pylon": UnitID.PYLON,
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
            self._update_zerg_stub()
            return

        if not self._built_extra_production_pylon:
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, UnitID.PYLON)
            )
            self._built_extra_production_pylon = True

        # use ares-sc2 macro behaviors for building pylons and units
        macro_plan: MacroPlan = MacroPlan()
        macro_plan.add(AutoSupply(base_location=self.ai.start_location))
        # 兵种组成来自 army_composition.yml(可配置多兵种),不再写死只造 TEMPEST。
        macro_plan.add(
            SpawnController(army_composition_dict=self._army.spawn_dict())
        )
        # 运营指挥·通用建筑杠杆 build=<结构>（expand=yes = build=nexus 别名）
        _order = getattr(self.ai, "steer_order", None) or {}
        self._handle_manual_build(_order, macro_plan)
        self.ai.register_behavior(macro_plan)

        # custom behavior for all other production, using ares-sc2 to help
        building_counter: dict[UnitID, int] = self.manager_mediator.get_building_counter
        structures_dict: dict[
            UnitID, list[Unit]
        ] = self.manager_mediator.get_own_structures_dict

        self._build_probes(self.ai.ready_townhalls)
        await self._build_tempest_rush_structures(building_counter, structures_dict)
        self._build_extra_stargates(structures_dict)
        self._chrono_structures()
        self._research_upgrades()

        # one off task to build an oracle
        if not self._built_single_oracle:
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

    def _update_zerg_stub(self) -> None:
        """虫族生产尚未实现(M2:ProductionController 不支持 Zerg,需 build order+morph)。
        先只维持农民 + 补给,避免开局崩;真正出兵靠 zerg_builds.yml 的 build runner/后续自定义。"""
        ai = self.ai
        ai.register_behavior(BuildWorkers(to_count=worker_target(ai.townhalls.amount)))
        plan: MacroPlan = MacroPlan()
        plan.add(AutoSupply(base_location=ai.start_location))
        if spawn := self._army.spawn_dict():
            plan.add(SpawnController(army_composition_dict=spawn))
        ai.register_behavior(plan)

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
        if not self._structure_present_or_pending(UnitID.FLEETBEACON) and [
            s for s in structures_dict[UnitID.STARGATE] if s.is_ready
        ]:
            await self._build_core_structure(UnitID.FLEETBEACON)

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
        """Decide what to chrono."""
        stargates: list[Unit] = self.manager_mediator.get_own_structures_dict[
            UnitID.STARGATE
        ]
        primary = self._primary_unit_id()
        for nexus in self.ai.townhalls:
            if nexus.energy >= 50:
                non_idle_stargates = [
                    s
                    for s in stargates
                    if not s.is_idle
                    and not s.has_buff(BuffId.CHRONOBOOSTENERGYCOST)
                    and s.type_id == UnitID.STARGATE
                ]
                if len(non_idle_stargates) > 0:
                    if cy_unit_pending(self.ai, primary):
                        nexus(
                            AbilityId.EFFECT_CHRONOBOOSTENERGYCOST,
                            non_idle_stargates[0],
                        )
                        return
                    if not self._oracle_chrono:
                        nexus(
                            AbilityId.EFFECT_CHRONOBOOSTENERGYCOST,
                            non_idle_stargates[0],
                        )
                        self._oracle_chrono = True

    def _research_upgrades(self):
        """Decide what to research."""
        # only get upgrades if stargate is already building a tempest
        if cy_unit_pending(self.ai, UnitID.TEMPEST) == 0:
            return

        structure_dict: dict[
            UnitID, list[Unit]
        ] = self.manager_mediator.get_own_structures_dict
        for upgrade_id in DESIRED_UPGRADES:
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
