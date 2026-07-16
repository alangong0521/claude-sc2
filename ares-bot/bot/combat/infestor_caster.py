"""感染虫专属施法 (M4+, combat=infestor_caster)。

借 ares `UseAOEAbility` 放真菌爆发(Fungal Growth):敌扎堆(≥min)且能量够(≥75)就 A 一发定身;
否则跟大部队/自保。真菌能穿过友军,不用避己方。
⚠️ 未跑局验证:落点/能量/神经寄生未做。FUNGALGROWTH ability 用 getattr 兜底(离线核不了枚举)。
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

_FUNGAL = getattr(AbilityId, "FUNGALGROWTH_FUNGALGROWTH", None)
_ENERGY = 75
_MIN_TARGETS = 3


@dataclass
class InfestorCaster(BaseUnit):
    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        assert "attack_target" in kwargs, "attack_target is required"
        target = kwargs["attack_target"]
        near: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units, distances=10,
            query_tree=UnitTreeQueryType.AllEnemy, return_as_dict=True,
        )
        for unit in units:
            enemies: list[Unit] = [u for u in near[unit.tag] if not u.is_memory]
            plan: CombatManeuver = CombatManeuver()
            can_cast = (
                _FUNGAL is not None
                and unit.energy >= _ENERGY
                and len(enemies) >= _MIN_TARGETS
            )
            if can_cast:
                plan.add(UseAOEAbility(
                    unit, _FUNGAL, targets=enemies, min_targets=_MIN_TARGETS,
                ))
            elif enemies:
                plan.add(KeepUnitSafe(unit, self.mediator.get_ground_grid))
            else:
                plan.add(AMove(unit, target))
            self.ai.register_behavior(plan)
