"""通用进攻 combat class —— 给 army_composition 里 combat=default 的兵种用。

暴风舰有专属的 tempest_offensive(超远射程风筝);但追猎/虚空/不朽等"普通"作战单位
需要一个通用指挥:射程内有敌就打(按③焦点选目标),否则寻路压向 attack_target。
逻辑刻意保守 —— 让"加一个兵种"至少能动、能打、能压点,细节微操(集火/阵型/风筝距离)
留待跑局验证后再逐兵种调优(见 docs/roadmap-unit-support.md B 类)。

⚠️ 未经跑局验证:接口/寻路与 tempest_offensive 对齐,但具体交战手感需开游戏实测。

B6 增量(2026-07-23,来源:ares SquadManager 教程):接收 regroup_center(主力 squad 中心),
无近敌且离主力 >15 格的地面散兵改为寻路归队,不独自压 attack_target 送死。
渐进式:只加归队分支,交战细节(射程内 StutterUnitBack / 追击 AMove)不动。
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
from bot.production_plans import hurt_retreat_needed

if TYPE_CHECKING:
    from ares import AresBot


# B6 归队距离:无近敌且离主力 squad 中心超过此值 → 寻路归队,不独自压点
_REGROUP_DIST: float = 15.0


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
        focus : str | None      ③焦点(weakest/workers/closest/priority/兵种名)
        maneuver : str | None   ④机动(ambush/hold_position → 到位后不主动追近敌)
        regroup_center : Point2 | None  B6 主力 squad 中心;散兵(>15 格且无近敌)归队用
        """
        assert "attack_target" in kwargs, "attack_target is required"
        attack_target = kwargs["attack_target"]
        focus = kwargs.get("focus")
        maneuver = kwargs.get("maneuver")
        regroup_center = kwargs.get("regroup_center")
        retreat_point = kwargs.get("retreat_point")  # O148-②:防守战伤兵回撤点
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

            # O148-②(o147 系列守军战损复盘):防守战伤兵后拉 —— 盾+血 <30%
            # 的地面兵撤到电池/塔覆盖圈(电池奶回再随下波顶上;伤兵白死 =
            # 每波少 2-3 叉)。只在有回撤点(防守战)时生效,进攻不留后路语义不变
            if (
                retreat_point is not None
                and not unit.is_flying
                and hurt_retreat_needed(
                    unit.shield, unit.health, unit.shield_max, unit.health_max
                )
                # 已在回撤点附近就别发呆了 —— 回到正常交战(有奶就奶,没奶站撸)
                and unit.distance_to(retreat_point) > 6.0
            ):
                grid = self._maybe_grid(unit)
                if grid is not None:
                    maneuver_plan.add(PathUnitToTarget(unit, grid, retreat_point))
                else:
                    maneuver_plan.add(AMove(unit, retreat_point))
                self.ai.register_behavior(maneuver_plan)
                continue

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
                # B6 归队(来源:ares SquadManager 教程;渐进式:只加归队,不改交战细节):
                # 地面散兵离主力 squad 中心 >15 且无近敌 → 寻路归队,不独自压点送死。
                # 飞行单位不动(tempest 个体风筝由专属 combat class 管)。
                # 逐只 PathUnitToTarget 而非 PathGroupToTarget:与现有逐单位循环一致,散兵位置分散,
                # 群体指令要以某个 start 为中心,对散兵反而是绕路(未验证)。
                destination = attack_target
                if (
                    regroup_center is not None
                    and not unit.is_flying
                    and unit.distance_to(regroup_center) > _REGROUP_DIST
                ):
                    destination = regroup_center
                if grid is not None:
                    maneuver_plan.add(PathUnitToTarget(unit, grid, destination))
                else:
                    maneuver_plan.add(AMove(unit, destination))

            self.ai.register_behavior(maneuver_plan)

    def _maybe_grid(self, unit: Unit):
        """取寻路网格:飞行单位用空中网格,地面用地面网格。拿不到返回 None(退回 AMove)。"""
        try:
            if unit.is_flying:
                return self.mediator.get_air_grid
            return self.mediator.get_ground_grid
        except Exception:
            return None
