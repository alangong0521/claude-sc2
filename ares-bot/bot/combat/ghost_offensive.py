"""幽灵专属作战 (M4+, combat=ghost_offensive)。

借 ares `GhostSnipe`:对附近敌人狙杀(高价值目标);没目标就跟大部队推进。
⚠️ 未跑局验证:狙杀选目标/能量/EMP 未做,需实测。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, GhostSnipe
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit

if TYPE_CHECKING:
    from ares import AresBot


@dataclass
class GhostOffensive(BaseUnit):
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
                plan.add(GhostSnipe(unit, close_enemy=enemies))
            else:
                plan.add(AMove(unit, target))
            self.ai.register_behavior(plan)
