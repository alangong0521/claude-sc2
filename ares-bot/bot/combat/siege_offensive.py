"""攻城坦克专属作战 (M4, combat=siege_offensive)。

借 ares `SiegeTankDecision`(自动决定架起/撤退):附近有敌就架起开火,没敌就撤下推进。
比 generic_offensive 的\"平A\"强在会用坦克的核心机制。移动交给 AMove(没敌可打时推向目标点)。

⚠️ 未跑局验证(M4):架起时机/与枪兵拉扯的配合/攻城范围站位需实测(见 status-and-roadmap M4)。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, SiegeTankDecision
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit

if TYPE_CHECKING:
    from ares import AresBot


@dataclass
class SiegeOffensive(BaseUnit):
    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        """按坦克逐个决定架/撤 + 推进。

        Keyword Arguments
        -----------------
        attack_target : Point2  推进目标点
        """
        assert "attack_target" in kwargs, "attack_target is required"
        target = kwargs["attack_target"]

        near: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=15,
            query_tree=UnitTreeQueryType.AllEnemy,
            return_as_dict=True,
        )
        for unit in units:
            close: list[Unit] = [
                u for u in near[unit.tag] if not u.is_memory
            ]
            plan: CombatManeuver = CombatManeuver()
            # 架/撤决策(有敌→架起开火;无敌→撤下)
            plan.add(SiegeTankDecision(unit, close_enemy=close, target=target))
            # 没敌可打时推进(架起状态下 AMove 被引擎忽略,无害)
            if not close:
                plan.add(AMove(unit, target))
            self.ai.register_behavior(plan)
