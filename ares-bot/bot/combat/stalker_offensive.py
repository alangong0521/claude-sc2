"""追猎(Stalker)进攻 + blink 微操 —— 纯追猎流派（BUILD=stalker）用。F3 优化版。

相对旧版的 6 项优化:
① blink 帧先开火(blink 前先 AttackTarget 一下,不浪费这一帧输出)
② "附近有敌够不着"分支改 PathUnitToTarget 追击(原 StutterUnitBack 是后撤行为,该追击时反撤是 bug)
③ 全队集火同一目标(合并所有追猎附近敌选一个全队 target,而非每只各自选)
④ 进攻型 blink(目标残血能收 / 高价值 caster,且在 blink 距离内 → blink 贴脸,而非只后撤 blink)
⑤ blink 躲技能(附近 HIGHTEMPLAR/INFESTOR 等 caster 威胁时 blink 拉开躲风暴/真菌/EMP)
⑥ 保持阵型(射程内 AttackTarget 点杀保持射程不贴脸;低护盾 blink 拉开近似拉开阵型)
门限参数化(blink_at_shield_perc / blink_when_swarmed 改 @dataclass 字段,便于实测定参)。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import (
    AttackTarget,
    PathUnitToTarget,
    UseAbility,
)
from cython_extensions.combat_utils import cy_pick_enemy_target
from cython_extensions.units_utils import cy_in_attack_range
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit
from bot.levers import pick_focus_key

if TYPE_CHECKING:
    from ares import AresBot


# 高价值 caster:进攻型 blink 切这些,也用来躲它们的技能
_HIGH_VALUE_CASTERS = frozenset({
    UnitID.HIGHTEMPLAR, UnitID.INFESTOR, UnitID.GHOST, UnitID.RAVEN,
    UnitID.MEDIVAC, UnitID.VIPER, UnitID.SENTRY,
})
# caster 威胁半径(发现就 blink 拉开躲风暴/真菌)
_CASTER_THREAT_DIST: float = 9.0
# 进攻型 blink:目标残血阈值(血+盾低于此 → blink 上去收)
_BLINK_KILL_HP: float = 80.0
# blink 距离(追猎 blink 约 7.5;只对射程外、blink 内的残血目标贴脸)
_BLINK_MIN_DIST: float = 6.0
_BLINK_MAX_DIST: float = 7.5


def _pick_focus(enemies, focus: str | None, origin=None) -> Unit:
    """焦点:按参谋长的 focus 挑目标,认不出 / 没命中 → ares 引擎默认选法。
    选择逻辑委托 levers.pick_focus_key(单一真相源,可离线单测)。"""
    chosen = pick_focus_key(enemies, focus, origin=origin)
    if chosen is not None:
        return chosen
    return cy_pick_enemy_target(enemies)


@dataclass
class StalkerOffensive(BaseUnit):
    """F3 优化版追猎微操。Called from CombatManager。"""

    ai: "AresBot"
    config: dict
    mediator: ManagerMediator
    # 门限参数化(便于离线/实测定参)
    blink_at_shield_perc: float = 0.25   # 护盾低于此 → blink 后撤求生
    blink_when_swarmed: int = 4           # 被这么多敌围 → blink 后撤

    def execute(self, units: Units, **kwargs) -> None:
        """Actually execute stalker attack with blink (F3 优化版)。

        Parameters
        ----------
        units : Units
            The stalkers we want to control (ATTACKING role 的追猎).
        **kwargs :
            attack_target, focus, maneuver。
        """
        assert "attack_target" in kwargs, "No attack_target passed into kwargs."
        attack_target = kwargs["attack_target"]
        focus = kwargs.get("focus") or "weakest"   # F3: 默认集火残血
        maneuver = kwargs.get("maneuver")
        ambush = maneuver in ("ambush", "hold_position")

        ground_grid = self.mediator.get_ground_grid

        everything_near_stalkers: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=15,
            query_tree=UnitTreeQueryType.AllEnemy,
            return_as_dict=True,
        )

        # ③ 全队集火:合并所有追猎附近敌(按 tag 去重),选一个全队共用 target。
        seen: set[int] = set()
        all_enemies_near: list[Unit] = []
        for u in units:
            for e in everything_near_stalkers[u.tag]:
                if not e.is_memory and e.tag not in seen:
                    seen.add(e.tag)
                    all_enemies_near.append(e)
        team_target: Unit | None = (
            _pick_focus(all_enemies_near, focus) if all_enemies_near else None
        )

        for unit in units:
            offensive_maneuver: CombatManeuver = CombatManeuver()

            enemy_near = everything_near_stalkers[unit.tag].filter(
                lambda u: not u.is_memory
            )
            in_attack_range: list[Unit] = cy_in_attack_range(unit, enemy_near)
            swarmed = len(enemy_near) >= self.blink_when_swarmed
            low_shield = unit.shield_percentage <= self.blink_at_shield_perc
            blink_ready = AbilityId.EFFECT_BLINK_STALKER in unit.abilities

            # 这只追猎的目标:优先全队 target;否则射程内选一个
            my_target: Unit | None = team_target
            if my_target is None and in_attack_range:
                my_target = _pick_focus(in_attack_range, focus, origin=unit)

            # ⑤ 躲技能:附近高价值 caster 威胁(风暴/真菌/EMP)
            caster_threat = any(
                e.type_id in _HIGH_VALUE_CASTERS
                and e.distance_to(unit) < _CASTER_THREAT_DIST
                for e in enemy_near
            )

            did_blink = False

            # 优先级 1:躲技能 / 防守 blink —— 后撤到安全点
            if blink_ready and (caster_threat or low_shield or swarmed):
                safe_point = self.mediator.find_closest_safe_spot(
                    from_pos=unit.position, grid=ground_grid, radius=8.0
                )
                # ① blink 帧先开火:blink 前先点一下目标,不浪费这一帧输出
                if my_target is not None:
                    offensive_maneuver.add(AttackTarget(unit=unit, target=my_target))
                offensive_maneuver.add(
                    UseAbility(AbilityId.EFFECT_BLINK_STALKER, unit, safe_point)
                )
                did_blink = True

            # 优先级 2:进攻型 blink —— 目标残血能收 / 是高价值 caster,且在 blink 距离内 → 贴脸
            elif blink_ready and my_target is not None:
                target_hp = my_target.health + my_target.shield
                dist = unit.distance_to(my_target)
                if (
                    (target_hp < _BLINK_KILL_HP or my_target.type_id in _HIGH_VALUE_CASTERS)
                    and _BLINK_MIN_DIST < dist <= _BLINK_MAX_DIST
                ):
                    if in_attack_range:
                        offensive_maneuver.add(AttackTarget(unit=unit, target=my_target))
                    offensive_maneuver.add(
                        UseAbility(
                            AbilityId.EFFECT_BLINK_STALKER, unit, my_target.position
                        )
                    )
                    did_blink = True

            # 没 blink → 常规输出
            if not did_blink:
                if in_attack_range:
                    # ②⑥ 射程内有敌:点杀(全队 target 在射程就用它集火,否则射程内选),保持射程不贴脸
                    if my_target is not None and any(
                        t.tag == my_target.tag for t in in_attack_range
                    ):
                        tgt = my_target
                    else:
                        tgt = _pick_focus(in_attack_range, focus, origin=unit)
                    offensive_maneuver.add(AttackTarget(unit=unit, target=tgt))
                elif enemy_near and not ambush:
                    # ③ 附近有敌但够不着 → 追击(原 StutterUnitBack 后撤是 bug,改 PathUnitToTarget)
                    offensive_maneuver.add(
                        PathUnitToTarget(
                            unit,
                            ground_grid,
                            my_target.position if my_target is not None else attack_target,
                        )
                    )
                else:
                    # ④ 无近敌 → 推进语义目标
                    offensive_maneuver.add(
                        PathUnitToTarget(unit, ground_grid, attack_target)
                    )

            self.ai.register_behavior(offensive_maneuver)
