"""高阶圣堂武士(高模)专属作战 (M4, combat=templar_caster)。

借 ares `UseAOEAbility` 放灵能风暴(Psi Storm):附近敌人扎堆(≥min_targets)且能量够(≥75)
就 A 一发风暴;否则跟大部队推进/自保。风暴避免落在自己地面单位上(avoid_own_ground)。

⚠️ 未跑局验证(M4):落点预判/能量管理/合体成执政官都没做,需实测(见 status-and-roadmap M4)。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, KeepUnitSafe, UseAOEAbility
from sc2.ids.ability_id import AbilityId
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit

if TYPE_CHECKING:
    from ares import AresBot

# 灵能风暴 ability(离线无法核对 sc2 枚举,getattr 兜底:名字对不上就不放风暴,不崩)
_PSI_STORM = getattr(AbilityId, "PSISTORM_PSISTORM", None)
_STORM_ENERGY = 75
_MIN_TARGETS = 3


@dataclass
class TemplarCaster(BaseUnit):
    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        """逐个高模:能量够+敌扎堆 → 放风暴;否则跟队/自保。

        Keyword Arguments
        -----------------
        attack_target : Point2  大部队推进点
        """
        assert "attack_target" in kwargs, "attack_target is required"
        target = kwargs["attack_target"]

        near: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=11,   # 风暴范围内的敌人
            query_tree=UnitTreeQueryType.AllEnemy,
            return_as_dict=True,
        )
        for unit in units:
            enemies: list[Unit] = [
                u for u in near[unit.tag] if not u.is_memory and not u.is_flying
            ]
            plan: CombatManeuver = CombatManeuver()
            can_storm = (
                _PSI_STORM is not None
                and unit.energy >= _STORM_ENERGY
                and len(enemies) >= _MIN_TARGETS
            )
            if can_storm:
                plan.add(UseAOEAbility(
                    unit, _PSI_STORM, targets=enemies,
                    min_targets=_MIN_TARGETS, avoid_own_ground=True,
                ))
            elif enemies:
                # 敌近但不放风暴(能量不够)→ 别送,自保
                plan.add(KeepUnitSafe(unit, self.mediator.get_ground_grid))
            else:
                plan.add(AMove(unit, target))  # 跟大部队
            self.ai.register_behavior(plan)
