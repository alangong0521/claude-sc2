"""女王专属支援 (M4+, combat=queen_support)。

借 ares `UseTransfuse`:给受伤友军(含自己)输血;没伤员就跟大部队。
注:注卵(inject)在生产层管(见 production_manager._build_zerg_queens 的 M2 剩余),这里只管战斗输血。
⚠️ 未跑局验证。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, UseTransfuse
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit

if TYPE_CHECKING:
    from ares import AresBot


@dataclass
class QueenSupport(BaseUnit):
    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        assert "attack_target" in kwargs, "attack_target is required"
        target = kwargs["attack_target"]
        near: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units, distances=10,
            query_tree=UnitTreeQueryType.AllOwn, return_as_dict=True,
        )
        for unit in units:
            allied: list[Unit] = [
                u for u in near[unit.tag]
                if not u.is_structure and (u.health_percentage < 1.0)
            ]
            plan: CombatManeuver = CombatManeuver()
            if allied:
                plan.add(UseTransfuse(unit, targets=allied))
            else:
                plan.add(AMove(unit, target))
            self.ai.register_behavior(plan)
