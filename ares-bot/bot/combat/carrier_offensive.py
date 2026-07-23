from dataclasses import dataclass, field
from math import cos, pi, sin
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AttackTarget, PathUnitToTarget
from cython_extensions.combat_utils import cy_pick_enemy_target
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit
from bot.combat.carrier_logic import LAUNCH_RANGE, best_anchor, wounded_state
from bot.levers import pick_focus_key

if TYPE_CHECKING:
    from ares import AresBot

# 锚点候选环的方向数
_DIRECTIONS: int = 12
# 敌对空射程数据缺失时的兜底对空威胁半径(刺蛇 6/防空塔 7 量级)
_AA_FALLBACK_RANGE: float = 7.0
# 对空威胁圈缓冲(射程 + 缓冲 = 避让圈)
_AA_BUFFER: float = 2.0
# 放机判定余量(拦截机机动半径之外的缓冲)
_ENGAGE_BUFFER: float = 1.5


@dataclass
class CarrierOffensive(BaseUnit):
    """O12/O14 航母专属微操（CombatManager 按 army_composition.yml 分派）。

    原则（E4d 二分判决后重写）：**微操是增强不是替代** ——
    射程内有敌就放机（AttackTarget 直发,绝不走 StutterUnitBack:
    它按 cy_attack_ready 判武器冷却,航母没有常规武器 → 永远走逃跑分支,
    E4d 拦截机 100+s 不放的真凶）;锚点只是「打的时候站哪」的优化,
    任何让航母停止输出的锚点都是 bug。
    O12 站位锚点:绕参考点 12 方向候选环,评分 = 距 ideal 扣分 + 地形高差加分
    + 对空威胁圈(敌实际对空射程+2 缓冲)降权;本舰当前位置恒为候选首位
    (滞回,防锚点每帧变点打转)。
    O14 残血后撤:盾+血 <40% 进 / ≥55% 出(滞回,防盾回充乒乓),
    锚点收向最近满血航母/风暴(没有则主基方向 5 格),拦截机照常放飞。
    攻(压目标)守(守家)共用选址;纯逻辑在 bot/combat/carrier_logic.py。
    """

    ai: "AresBot"
    config: dict
    mediator: ManagerMediator
    # O14 滞回状态:处于残血后撤中的单位 tag
    _wounded_tags: set = field(default_factory=set)

    def execute(self, units: Units, **kwargs) -> None:
        assert "attack_target" in kwargs, "No attack_target passed into kwargs."
        attack_target: Point2 = kwargs["attack_target"]
        focus = kwargs.get("focus")

        everything_near: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=14,
            query_tree=UnitTreeQueryType.AllEnemy,
            return_as_dict=True,
        )
        # O14 滞回:刷新残血集合
        for u in units:
            if wounded_state(
                u.shield_health_percentage, u.tag in self._wounded_tags
            ):
                self._wounded_tags.add(u.tag)
            else:
                self._wounded_tags.discard(u.tag)
        healthy: list[Unit] = [
            u for u in units if u.tag not in self._wounded_tags
        ]

        for unit in units:
            maneuver: CombatManeuver = CombatManeuver()
            near: Units = everything_near[unit.tag].filter(lambda u: not u.is_memory)

            engage: list[Unit] = [
                e for e in near
                if unit.distance_to(e) <= LAUNCH_RANGE + _ENGAGE_BUFFER
            ]
            if engage:
                # 放机第一:射程内有敌就打(对齐 GenericOffensive),锚点不插手
                target = pick_focus_key(engage, focus, origin=unit) or (
                    cy_pick_enemy_target(Units(engage, self.ai))
                )
                maneuver.add(AttackTarget(unit=unit, target=target))
            else:
                # 不在放机射程:去锚点(带对空避让/地形/滞回的站位优化)
                if unit.tag in self._wounded_tags:
                    ref, ideal = self._retreat_ref(unit, healthy)
                else:
                    ref, ideal = attack_target, LAUNCH_RANGE
                anchor: Point2 = self._anchor(unit, ref, ideal, near)
                if anchor.distance_to(unit.position) > 1.0:
                    maneuver.add(
                        PathUnitToTarget(unit, self.mediator.get_air_grid, anchor)
                    )
            self.ai.register_behavior(maneuver)

    def _retreat_ref(self, unit: Unit, healthy: list[Unit]) -> tuple[Point2, float]:
        """O14:残血航母的锚点参考点与环半径 —— 最近满血航母/风暴站位(贴它身后);
        没有健康编队则主基方向 5 格。"""
        if healthy:
            return min(healthy, key=lambda u: u.distance_to(unit)).position, 2.0
        return unit.position.towards(self.ai.start_location, 5.0), 0.0

    def _anchor(
        self, unit: Unit, ref: Point2, ideal: float, enemies: Units
    ) -> Point2:
        """O12:绕 ref 的 12 方向候选环 + carrier_logic.best_anchor 评分选址。
        本舰当前位置恒为候选首位(滞回):无更优点时原地不动,防每帧变点打转。
        防空降权只算「对空威胁圈」(敌实际对空射程+缓冲,缺省 7+2)。"""
        try:
            h_ref = self.ai.get_terrain_height(ref)
        except (IndexError, AttributeError):
            return unit.position

        def _aa_threats(p: Point2) -> int:
            return sum(
                1 for e in enemies
                if e.can_attack_air
                and e.distance_to(p)
                < (e.air_range or _AA_FALLBACK_RANGE) + _AA_BUFFER
            )

        candidates: list[dict] = [
            {  # 首位 = 当前位置(滞回锚点)
                "point": unit.position,
                "dist": unit.position.distance_to(ref),
                "ideal": ideal,
                "height_diff": False,  # 不知道确切高度差场景下保持中性
                "aa": _aa_threats(unit.position),
            }
        ]
        try:
            h_unit = self.ai.get_terrain_height(unit.position)
            candidates[0]["height_diff"] = h_unit != h_ref
        except (IndexError, AttributeError):
            pass
        for i in range(_DIRECTIONS):
            ang = 2 * pi * i / _DIRECTIONS
            p = Point2((ref.x + ideal * cos(ang), ref.y + ideal * sin(ang)))
            try:
                h_p = self.ai.get_terrain_height(p)
            except (IndexError, AttributeError):
                continue  # 图外候选丢弃
            candidates.append({
                "point": p,
                "dist": p.distance_to(ref),
                "ideal": ideal,
                "height_diff": h_p != h_ref,
                "aa": _aa_threats(p),
            })
        best = best_anchor(candidates)
        return best["point"] if best else unit.position
