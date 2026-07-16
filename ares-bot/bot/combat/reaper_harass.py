"""死神专属骚扰 (M4+, combat=reaper_harass)。

借 ares `ReaperGrenade`:向敌群丢 KD8 手雷 + 预判走位;没敌就推进。撤退点=自家。
⚠️ 未跑局验证:跳崖骚扰农民/风筝距离需实测。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, ReaperGrenade
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit

if TYPE_CHECKING:
    from ares import AresBot


@dataclass
class ReaperHarass(BaseUnit):
    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        assert "attack_target" in kwargs, "attack_target is required"
        target = kwargs["attack_target"]
        grid = self._ground_grid()
        near: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units, distances=12,
            query_tree=UnitTreeQueryType.AllEnemy, return_as_dict=True,
        )
        for unit in units:
            enemies: list[Unit] = [u for u in near[unit.tag] if not u.is_memory]
            plan: CombatManeuver = CombatManeuver()
            if enemies and grid is not None:
                plan.add(ReaperGrenade(
                    unit, enemy_units=enemies,
                    retreat_target=self.ai.start_location, grid=grid,
                ))
            else:
                plan.add(AMove(unit, target))
            self.ai.register_behavior(plan)

    def _ground_grid(self):
        try:
            return self.mediator.get_ground_grid
        except Exception:
            return None
