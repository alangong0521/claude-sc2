"""通用进攻 combat class —— 给 army_composition 里 combat=default 的兵种用。

暴风舰有专属的 tempest_offensive(超远射程风筝);但追猎/虚空/不朽等"普通"作战单位
需要一个通用指挥:射程内有敌就打(按③焦点选目标),否则寻路压向 attack_target。
逻辑刻意保守 —— 让"加一个兵种"至少能动、能打、能压点,细节微操(集火/阵型/风筝距离)
留待跑局验证后再逐兵种调优(见 docs/roadmap-unit-support.md B 类)。

⚠️ 未经跑局验证:接口/寻路与 tempest_offensive 对齐,但具体交战手感需开游戏实测。
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, PathUnitToTarget, StutterUnitBack
from cython_extensions.combat_utils import cy_pick_enemy_target
from cython_extensions.units_utils import cy_in_attack_range
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit
from bot.levers import pick_focus_key

if TYPE_CHECKING:
    from ares import AresBot


def _pick_focus(enemies, focus, origin=None) -> Unit:
    """③焦点选目标:委托 levers.pick_focus_key(单一真相源),命不中退回引擎默认。"""
    chosen = pick_focus_key(enemies, focus, origin=origin)
    if chosen is not None:
        return chosen
    return cy_pick_enemy_target(enemies)


@dataclass
class GenericOffensive(BaseUnit):
    """通用地面/对空作战单位指挥(combat=default)。

    Parameters
    ----------
    ai : AresBot
    config : dict
    mediator : ManagerMediator
    """

    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        """射程内有敌 → StutterUnitBack 打(按焦点);否则寻路压向 attack_target。

        Keyword Arguments
        -----------------
        attack_target : Point2  部队要去的点
        focus : str | None      ③焦点(weakest/workers/closest/兵种名)
        maneuver : str | None   ④机动(ambush/hold_position → 到位后不主动追近敌)
        """
        assert "attack_target" in kwargs, "attack_target is required"
        attack_target = kwargs["attack_target"]
        focus = kwargs.get("focus")
        maneuver = kwargs.get("maneuver")
        ambush = maneuver in ("ambush", "hold_position")

        near: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=15,
            query_tree=UnitTreeQueryType.AllEnemy,
            return_as_dict=True,
        )

        for unit in units:
            maneuver_plan: CombatManeuver = CombatManeuver()
            enemy_near: Units = near[unit.tag].filter(lambda u: not u.is_memory)
            in_range: list[Unit] = cy_in_attack_range(unit, enemy_near)

            if len(in_range) > 0:
                target: Unit = _pick_focus(in_range, focus, origin=unit)
                # 有地面网格就用它风筝;拿不到就退回站撸(A 到目标身上)
                grid = self._maybe_grid(unit)
                if grid is not None:
                    maneuver_plan.add(StutterUnitBack(unit, target, True, grid))
                else:
                    maneuver_plan.add(AMove(unit, target.position))
            elif enemy_near and not ambush:
                target: Unit = _pick_focus(enemy_near, focus, origin=unit)
                maneuver_plan.add(AMove(unit, target.position))
            else:
                grid = self._maybe_grid(unit)
                if grid is not None:
                    maneuver_plan.add(PathUnitToTarget(unit, grid, attack_target))
                else:
                    maneuver_plan.add(AMove(unit, attack_target))

            self.ai.register_behavior(maneuver_plan)

    def _maybe_grid(self, unit: Unit):
        """取寻路网格:飞行单位用空中网格,地面用地面网格。拿不到返回 None(退回 AMove)。"""
        try:
            if unit.is_flying:
                return self.mediator.get_air_grid
            return self.mediator.get_ground_grid
        except Exception:
            return None
