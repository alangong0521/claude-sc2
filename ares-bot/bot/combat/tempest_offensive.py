from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import PathUnitToTarget, StutterUnitBack
from cython_extensions.combat_utils import cy_pick_enemy_target
from cython_extensions.units_utils import cy_in_attack_range
from sc2.unit import Unit
from sc2.units import Units


from bot.levers import pick_focus_key


def _pick_focus(enemies, focus: str | None, origin=None) -> Unit:
    """③焦点：从敌人里按参谋长的 focus 挑目标。认不出 / 没命中 → 默认选法。

    纯选择逻辑委托给 levers.pick_focus_key(单一真相源,可离线单测);它返回 None 时
    退回 ares 的 cy_pick_enemy_target(引擎默认选法)。origin=发起攻击的单位,
    用于 closest 按"离它最近"挑(tempest 风筝时传 unit)。"""
    chosen = pick_focus_key(enemies, focus, origin=origin)
    if chosen is not None:
        return chosen
    return cy_pick_enemy_target(enemies)

from bot.combat.base_unit import BaseUnit

if TYPE_CHECKING:
    from ares import AresBot


@dataclass
class TempestOffensive(BaseUnit):
    """Execute behavior for Tempest offensive attack.

    Called from `CombatManager`

    Parameters
    ----------
    ai : AresBot
        Bot object that will be running the game
    config : Dict[Any, Any]
        Dictionary with the data from the configuration file
    mediator : ManagerMediator
        Used for getting information from managers in Ares.
    """

    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        """Actually execute tempest attack.

        Parameters
        ----------
        units : list[Unit]
            The units we want OracleHarass to control.
        **kwargs :
            See below.

        Keyword Arguments
        -----------------
        attack_target : Point2
            Point on the map Tempest should head towards.
        """

        assert (
            "attack_target" in kwargs
        ), "No value for scout_target was passed into kwargs."
        attack_target = kwargs["attack_target"]
        focus = kwargs.get("focus")          # ③焦点
        maneuver = kwargs.get("maneuver")    # ④机动意图
        # 埋伏/占位：到位后蹲点等敌进入射程，不主动追近敌（只打进了射程的）
        ambush = maneuver in ("ambush", "hold_position")
        everything_near_tempests: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=15,
            query_tree=UnitTreeQueryType.AllEnemy,
            return_as_dict=True,
        )

        for unit in units:
            offensive_maneuver: CombatManeuver = CombatManeuver()

            enemy_near_tempest: Units = everything_near_tempests[unit.tag].filter(
                lambda u: not u.is_memory
            )

            in_attack_range: list[Unit] = cy_in_attack_range(unit, enemy_near_tempest)

            if len(in_attack_range) > 0:
                # 射程内有敌：按③焦点选目标点杀（埋伏时也照打进了范围的）
                target: Unit = _pick_focus(in_attack_range, focus, origin=unit)
                offensive_maneuver.add(
                    StutterUnitBack(unit, target, True, self.mediator.get_air_grid)
                )

            elif enemy_near_tempest and not ambush:
                # 附近有敌但没进射程：默认主动风筝追击；埋伏/占位时不追，继续蹲向目标点
                target: Unit = _pick_focus(enemy_near_tempest, focus, origin=unit)
                offensive_maneuver.add(
                    StutterUnitBack(unit, target, True, self.mediator.get_air_grid)
                )
            else:
                offensive_maneuver.add(
                    PathUnitToTarget(unit, self.mediator.get_air_grid, attack_target)
                )

            self.ai.register_behavior(offensive_maneuver)
