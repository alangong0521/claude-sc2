"""医疗船专属支援 (M4, combat=medivac_support)。

借 ares `MedivacHeal`:给附近友军补血,并 keep_safe 自动躲危险。没友军在身边时跟向
attack_target(黏着大部队)。运兵(pick_up/drop_cargo)是后续增强,这里先只做治疗+跟队。

⚠️ 未跑局验证(M4):跟队距离/躲技能/运兵留待实测(见 status-and-roadmap M4)。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, MedivacHeal
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit

if TYPE_CHECKING:
    from ares import AresBot


@dataclass
class MedivacSupport(BaseUnit):
    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        """逐个医疗船:附近有友军就治疗,否则跟向 attack_target。

        Keyword Arguments
        -----------------
        attack_target : Point2  大部队的推进点(没友军可治时跟过去)
        """
        assert "attack_target" in kwargs, "attack_target is required"
        target = kwargs["attack_target"]
        grid = self._air_grid()

        near: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=15,
            query_tree=UnitTreeQueryType.AllOwn,
            return_as_dict=True,
        )
        for unit in units:
            allied: list[Unit] = [
                u for u in near[unit.tag] if u.tag != unit.tag and not u.is_structure
            ]
            plan: CombatManeuver = CombatManeuver()
            if allied and grid is not None:
                plan.add(MedivacHeal(unit, close_allied=allied, grid=grid))
            else:
                plan.add(AMove(unit, target))  # 附近没友军 → 跟大部队
            self.ai.register_behavior(plan)

    def _air_grid(self):
        """医疗船是飞行单位,用空中网格给 MedivacHeal 的 keep_safe 寻路。取不到 → None。"""
        try:
            return self.mediator.get_air_grid
        except Exception:
            return None
