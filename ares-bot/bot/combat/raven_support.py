"""渡鸦专属支援 (M4+, combat=raven_support)。

借 ares `RavenAutoTurret`:附近有敌就投放自动机炮台;否则跟大部队。
⚠️ 未跑局验证:干扰矩阵/反装甲导弹等主动技能未做,需实测。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, RavenAutoTurret
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit

if TYPE_CHECKING:
    from ares import AresBot


@dataclass
class RavenSupport(BaseUnit):
    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        assert "attack_target" in kwargs, "attack_target is required"
        target = kwargs["attack_target"]
        near: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units, distances=12,
            query_tree=UnitTreeQueryType.AllEnemy, return_as_dict=True,
        )
        for unit in units:
            enemies: list[Unit] = [u for u in near[unit.tag] if not u.is_memory]
            plan: CombatManeuver = CombatManeuver()
            if enemies:
                plan.add(RavenAutoTurret(unit, all_close_enemy=enemies))
            else:
                plan.add(AMove(unit, target))
            self.ai.register_behavior(plan)
