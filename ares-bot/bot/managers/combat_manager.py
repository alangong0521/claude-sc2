from itertools import cycle
from typing import TYPE_CHECKING

from ares import ManagerMediator
from ares.consts import UnitRole
from ares.managers.manager import Manager
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.units import Units

from bot.combat.base_unit import BaseUnit
from bot.combat.generic_offensive import GenericOffensive
from bot.combat.ghost_offensive import GhostOffensive
from bot.combat.infestor_caster import InfestorCaster
from bot.combat.medivac_support import MedivacSupport
from bot.combat.medivac_transport import MedivacTransport
from bot.combat.queen_support import QueenSupport
from bot.combat.raven_support import RavenSupport
from bot.combat.reaper_harass import ReaperHarass
from bot.combat.siege_offensive import SiegeOffensive
from bot.combat.stalker_offensive import StalkerOffensive
from bot.combat.templar_caster import TemplarCaster
from bot.combat.tempest_offensive import TempestOffensive
from bot.production_plans import floor_army_defends_home

if TYPE_CHECKING:
    from ares import AresBot


class CombatManager(Manager):
    def __init__(
        self,
        ai: "AresBot",
        config: dict,
        mediator: ManagerMediator,
    ) -> None:
        """Handle all main combat logic.

        This manager is incharge of all the main offensive units.
        Combat classes should be called as needed to execute unit control.

        Parameters
        ----------
        ai :
            Bot object that will be running the game
        config :
            Dictionary with the data from the configuration file
        mediator :
            ManagerMediator used for getting information from other managers.
        """
        super().__init__(ai, config, mediator)
        self.expansions_generator = None
        self.current_base_target: Point2 = self.ai.focused_enemy_start()
        self.tempest_offensive: BaseUnit = TempestOffensive(ai, config, mediator)
        self.stalker_offensive: BaseUnit = StalkerOffensive(ai, config, mediator)
        self.generic_offensive: BaseUnit = GenericOffensive(ai, config, mediator)
        self.siege_offensive: BaseUnit = SiegeOffensive(ai, config, mediator)
        self.medivac_support: BaseUnit = MedivacSupport(ai, config, mediator)
        self.medivac_transport: BaseUnit = MedivacTransport(ai, config, mediator)
        self.templar_caster: BaseUnit = TemplarCaster(ai, config, mediator)
        self.ghost_offensive: BaseUnit = GhostOffensive(ai, config, mediator)
        self.raven_support: BaseUnit = RavenSupport(ai, config, mediator)
        self.queen_support: BaseUnit = QueenSupport(ai, config, mediator)
        self.reaper_harass: BaseUnit = ReaperHarass(ai, config, mediator)
        self.infestor_caster: BaseUnit = InfestorCaster(ai, config, mediator)
        # 兵种组成从 army_composition.yml 读(单一真相源,按 bot 种族选块),决定指挥哪些兵种、
        # 用哪个 combat class。不再写死只指挥 TEMPEST —— 加兵种只改 yaml。
        from bot.army_config import ArmyComposition, bot_race_name
        self._army = ArmyComposition.load(race=bot_race_name(ai))
        # C3a 集结阈值(flows.yml rally_min_army,缺省 0=关):低于阈值且司令没下 stance 时守家攒兵
        import os
        from bot.flow_config import FlowConfig
        self._flow: FlowConfig = FlowConfig.load(os.environ.get("BUILD"))
        self._rally_min: int = self._flow.rally_min_army
        # combat kind → combat class 分派表(oracle_harass 由 OracleManager 单独管,这里不收)
        self._combat_dispatch: dict[str, BaseUnit] = {
            "tempest_offensive": self.tempest_offensive,
            "stalker_offensive": self.stalker_offensive,   # 纯追猎 blink 流(BUILD=stalker)
            "default": self.generic_offensive,
            "siege_offensive": self.siege_offensive,        # M4:攻城坦克
            "medivac_support": self.medivac_support,        # M4:医疗船治疗
            "medivac_transport": self.medivac_transport,    # M4:医疗船空投
            "templar_caster": self.templar_caster,          # M4:高模风暴
            "ghost_offensive": self.ghost_offensive,        # 幽灵狙杀
            "raven_support": self.raven_support,            # 渡鸦机炮台
            "queen_support": self.queen_support,            # 女王输血
            "reaper_harass": self.reaper_harass,            # 死神手雷
            "infestor_caster": self.infestor_caster,        # 感染虫真菌
        }

    def _enemy_near_their_base(self) -> bool:
        """敌主力是否还在自己家附近（⑥择时 when_enemy_away：在家就等他出门再打）。
        多人：看的是**焦点敌人**的家。"""
        home = self.ai.focused_enemy_start()
        return any(
            u.position.distance_to(home) < 25
            for u in self.ai.enemy_units
            if not u.is_structure
        )

    def _backdoor(self) -> Point2:
        """④机动·绕后：离敌军重心最远的敌方分矿（偷家）。无敌军可见 → 敌最远分矿。
        多人：绕后点相对**焦点敌人**的家算。"""
        ai = self.ai
        focus = ai.focused_enemy_start()
        enemy_exps = sorted(
            ai.expansion_locations_list,
            key=lambda p: p.distance_to(focus),
        )[:5]
        ground = [u for u in ai.enemy_units if not u.is_flying]
        if not ground:
            return enemy_exps[-1] if enemy_exps else focus
        cx = sum(u.position.x for u in ground) / len(ground)
        cy = sum(u.position.y for u in ground) / len(ground)
        center = Point2((cx, cy))
        return max(enemy_exps, key=lambda p: p.distance_to(center))

    def _known_enemy_townhalls(self) -> Units:
        """Known enemy bases near the focused enemy, sorted from main outward.

        Do not blindly target theoretical expansion points for enemy_natural/third.
        On some maps the geometric "second closest expansion to enemy start" is not
        where the AI actually expanded, which can park the army at an empty base.
        """
        townhall_types: set[UnitID] = {
            UnitID.NEXUS,
            UnitID.COMMANDCENTER,
            UnitID.ORBITALCOMMAND,
            UnitID.PLANETARYFORTRESS,
            UnitID.HATCHERY,
            UnitID.LAIR,
            UnitID.HIVE,
        }
        focus = self.ai.focused_enemy_start()
        candidates = self.ai.enemy_structures.filter(
            lambda s: s.type_id in townhall_types and s.position.distance_to(focus) < 80
        )
        return candidates.sorted(lambda s: s.position.distance_to(focus))

    def _resolve_steer_target(self, key: str) -> Point2 | None:
        """参谋长的语义目标 → Point2（不让司令点坐标）。认不出则 None。
        enemy_* 都相对**焦点敌人**（enemy=E2 切；默认最近 E1；1v1 就是唯一敌人）。"""
        ai = self.ai
        focus = ai.focused_enemy_start()
        if key == "home":
            return ai.start_location
        if key == "map_center":
            return ai.game_info.map_center
        if key == "enemy_main":
            return focus
        if key == "enemy_backdoor":
            return self._backdoor()
        # enemy_natural/third/fourth:纯选择抽到 levers.pick_known_base,这里只取候选
        from bot.levers import pick_known_base
        known = self._known_enemy_townhalls()
        idx = pick_known_base(key, range(known.amount))
        if idx is not None:
            return known[idx].position
        # 没探到那么多矿 → None(回退默认追敌,不硬冲空地)
        return None

    @property
    def attack_target(self) -> Point2:
        """进攻点。参谋长下了命令就听命令（覆盖默认）：
        defend/retreat → 回家集结；attack + 语义目标 → 求解该点；否则走默认追敌逻辑。
        pivot:rush 响应期间(_rush_active)全军守家(优先级仅次于司令命令)。"""
        order = getattr(self.ai, "steer_order", None) or {}
        stance = order.get("stance")
        if stance in ("defend", "retreat"):
            return self.ai.start_location
        if getattr(self.ai.production_manager, "_rush_active", False):
            return self.ai.start_location  # pivot:rush 响应中,先守家
        if tgt := order.get("target"):
            if (pt := self._resolve_steer_target(tgt)) is not None:
                return pt

        # E3g:舰队成型前(pre_fleet 保底阶段)地面兵默认守家 —— 无令时默认追敌会把
        # 保底叉子拉过全图送进蟑螂群(trickle,e3g game_01 实证:6 叉在敌波到脸前消失)。
        # stance/rush/司令 target 都在上面已 return,不受影响;主 C 上线恢复默认进攻。
        if floor_army_defends_home(
            has_pre_fleet=self._flow.pre_fleet is not None,
            primary_count=self.manager_mediator.get_own_unit_count(
                unit_type_id=self.ai.production_manager._primary_unit_id()
            ),
        ):
            return self.ai.start_location

        # —— 默认逻辑（无命令时）：最近敌建筑 → 轮巡分矿 ——
        if self.ai.enemy_structures:
            return self.ai.enemy_structures.closest_to(self.ai.start_location).position
        else:
            # cycle through base locations
            if self.ai.is_visible(self.current_base_target):
                if not self.expansions_generator:
                    base_locations: list[Point2] = [
                        i for i in self.ai.expansion_locations_list
                    ]
                    self.expansions_generator = cycle(base_locations)

                self.current_base_target = next(self.expansions_generator)

            return self.current_base_target

    async def update(self, iteration: int) -> None:
        """This is only currently required to execute tempest micro.

        Parameters
        ----------
        iteration
        """
        # 参谋长喊"龟"(hold)：原地不动，不推进
        order = getattr(self.ai, "steer_order", None) or {}
        if order.get("stance") == "hold":
            return

        # ⑥择时：条件没到先按兵不动（now/None=立即；when_maxed=攒满再打；when_enemy_away=等敌出门）
        from bot.levers import should_hold_for_trigger
        if should_hold_for_trigger(
            order.get("trigger"),
            supply_used=self.ai.supply_used,
            enemy_near_base=self._enemy_near_their_base(),
        ):
            return

        # 按 army_composition 逐兵种指挥:取该兵种的 ATTACKING 单位,交给它配置的 combat class。
        # 同一 combat class 的多兵种会各自 execute 一次(tempest/追猎各打各的),攻击点/焦点/机动共享。
        # C3a 集结纪律:兵力低于 rally_min_army 且司令没下 stance 时,先守家攒兵(治分批送死);
        # 司令下了 stance(attack/defend/...)以司令为准,集结让位。
        if order.get("stance") is None and 0 < self._own_army_count() < self._rally_min:
            attack_target = self.ai.start_location
        else:
            attack_target = self.attack_target
        for spec in self._army.by_role("ATTACKING"):
            combat = self._combat_dispatch.get(spec.combat)
            if combat is None:
                continue  # oracle_harass 等不由本 manager 指挥
            unit_id = getattr(UnitID, spec.id_name, None)
            if unit_id is None:
                continue
            if units := self.manager_mediator.get_units_from_role(
                role=UnitRole.ATTACKING, unit_type=unit_id
            ):
                combat.execute(
                    units,
                    attack_target=attack_target,
                    focus=order.get("focus"),        # ③焦点
                    maneuver=order.get("maneuver"),  # ④机动意图
                )

    def _own_army_count(self) -> int:
        """当前 ATTACKING 编制内的兵力数(按 army_composition 登记兵种数)。"""
        count = 0
        for spec in self._army.by_role("ATTACKING"):
            uid = getattr(UnitID, spec.id_name, None)
            if uid is not None:
                count += self.manager_mediator.get_own_unit_count(unit_type_id=uid)
        return count
