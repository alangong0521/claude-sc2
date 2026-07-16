"""医疗船运兵(空投)专属作战 (M4, combat=medivac_transport)。

借 ares `PickUpAndDropCargo`(=PickUpCargo+DropCargo 组合):把附近的己方地面兵装进医疗船,
运到 attack_target 再放下(空投骚扰/绕后)。与 medivac_support(纯治疗)是两种用法,按配置二选一。

⚠️ 未跑局验证(M4):装载对象筛选/空投点/时机都需实测(见 status-and-roadmap M4)。
默认 army_composition 里医疗船仍用 medivac_support(治疗);想空投把 combat 改成本 kind。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, PickUpAndDropCargo
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit

if TYPE_CHECKING:
    from ares import AresBot


@dataclass
class MedivacTransport(BaseUnit):
    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        """逐个医疗船:附近有可装的己方地面兵 → 装载空投到目标点;否则跟过去。

        Keyword Arguments
        -----------------
        attack_target : Point2  空投落点
        """
        assert "attack_target" in kwargs, "attack_target is required"
        target = kwargs["attack_target"]
        grid = self._air_grid()

        near: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=8,
            query_tree=UnitTreeQueryType.AllOwn,
            return_as_dict=True,
        )
        for unit in units:
            # 可装载对象:附近己方非建筑、非飞行的地面兵(不含农民由调用方 role 过滤)
            pickup: list[Unit] = [
                u for u in near[unit.tag]
                if u.tag != unit.tag and not u.is_structure and not u.is_flying
            ]
            plan: CombatManeuver = CombatManeuver()
            if pickup and grid is not None:
                plan.add(PickUpAndDropCargo(
                    unit, grid=grid, pickup_targets=pickup, target=target,
                ))
            else:
                plan.add(AMove(unit, target))
            self.ai.register_behavior(plan)

    def _air_grid(self):
        try:
            return self.mediator.get_air_grid
        except Exception:
            return None
