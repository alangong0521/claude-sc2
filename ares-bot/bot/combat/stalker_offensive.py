"""追猎(Stalker)进攻 + blink 微操 —— 纯追猎流派（BUILD=stalker）用。

与 tempest_offensive.py 同构，差别在：
- 走地面 grid（get_ground_grid），不是空中 grid；
- 多一条 blink 后撤求生：护盾低 / 被围时用 EFFECT_BLINK_STALKER 瞬移到最近安全点。
追猎的语义目标(target)/焦点(focus)/机动(maneuver)杠杆与暴风舰共用同一份词表，
不增字段，全部从 steer_order 透传，由 CombatManager 解析后传到这里。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import (
    PathUnitToTarget,
    StutterUnitBack,
    UseAbility,
)
from cython_extensions.combat_utils import cy_pick_enemy_target
from cython_extensions.units_utils import cy_in_attack_range
from sc2.ids.ability_id import AbilityId
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit
from bot.levers import pick_focus_key

if TYPE_CHECKING:
    from ares import AresBot


# blink 判据门限：护盾低于此或被这么多敌围攻 → blink 后撤求生
_BLINK_AT_SHIELD_PERC: float = 0.25
_BLINK_WHEN_SWARMED: int = 4


def _pick_focus(enemies, focus: str | None, origin=None) -> Unit:
    """③焦点：从敌人里按参谋长的 focus 挑目标。认不出 / 没命中 → 默认选法。

    纯选择逻辑委托给 levers.pick_focus_key(单一真相源,可离线单测);它返回 None 时
    退回 ares 的 cy_pick_enemy_target(引擎默认选法)。origin=发起攻击的单位,
    用于 closest 按"离它最近"挑。与 TempestOffensive._pick_focus 完全一致语义。"""
    chosen = pick_focus_key(enemies, focus, origin=origin)
    if chosen is not None:
        return chosen
    return cy_pick_enemy_target(enemies)


@dataclass
class StalkerOffensive(BaseUnit):
    """Execute behavior for Stalker offensive + blink.

    Called from `CombatManager`. 与 TempestOffensive 同构：四分支
    ① blink 后撤求生（护盾低/被围 + blink 冷却好）
    ② 射程内有敌 → 风筝后撤点杀（StutterUnitBack，按 focus 选目标）
    ③ 附近有敌但没进射程 → 风筝靠近（非 ambush 时）；ambush/hold_position 不追
    ④ 无近敌 → PathUnitToTarget 推进 attack_target
    """

    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        """Actually execute stalker attack with blink.

        Parameters
        ----------
        units : Units
            The stalkers we want to control (ATTACKING role 的追猎).
        **kwargs :
            attack_target, focus, maneuver（与 TempestOffensive 同名 kwargs）。
        """
        assert "attack_target" in kwargs, "No attack_target passed into kwargs."
        attack_target = kwargs["attack_target"]
        focus = kwargs.get("focus")
        maneuver = kwargs.get("maneuver")
        ambush = maneuver in ("ambush", "hold_position")

        ground_grid = self.mediator.get_ground_grid

        everything_near_stalkers: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=15,
            query_tree=UnitTreeQueryType.AllEnemy,
            return_as_dict=True,
        )

        for unit in units:
            offensive_maneuver: CombatManeuver = CombatManeuver()

            enemy_near = everything_near_stalkers[unit.tag].filter(
                lambda u: not u.is_memory
            )
            in_attack_range: list[Unit] = cy_in_attack_range(unit, enemy_near)
            swarmed = len(enemy_near) >= _BLINK_WHEN_SWARMED
            low_shield = unit.shield_percentage <= _BLINK_AT_SHIELD_PERC

            # ① blink 后撤求生：护盾低 / 被围，且 blink 冷却好了（ability 在 abilities 里）。
            if (low_shield or swarmed) and AbilityId.EFFECT_BLINK_STALKER in unit.abilities:
                safe_point = self.mediator.find_closest_safe_spot(
                    from_pos=unit.position, grid=ground_grid, radius=8.0
                )
                offensive_maneuver.add(
                    UseAbility(AbilityId.EFFECT_BLINK_STALKER, unit, safe_point)
                )

            elif len(in_attack_range) > 0:
                # ② 射程内有敌：按③焦点选目标点杀（埋伏时也照打进了范围的）
                target: Unit = _pick_focus(in_attack_range, focus, origin=unit)
                offensive_maneuver.add(
                    StutterUnitBack(unit, target, True, ground_grid)
                )

            elif enemy_near and not ambush:
                # ③ 附近有敌但没进射程：默认主动风筝追击；埋伏/占位时不追
                target = _pick_focus(enemy_near, focus, origin=unit)
                offensive_maneuver.add(
                    StutterUnitBack(unit, target, True, ground_grid)
                )
            else:
                # ④ 无近敌 → 推进语义目标（ambush 时也走这里蹲向目标点，不主动追近敌）
                offensive_maneuver.add(
                    PathUnitToTarget(unit, ground_grid, attack_target)
                )

            self.ai.register_behavior(offensive_maneuver)
