from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, PathUnitToTarget, StutterUnitBack
from cython_extensions.combat_utils import cy_pick_enemy_target
from cython_extensions.units_utils import cy_in_attack_range
from sc2.unit import Unit
from sc2.units import Units


from bot.levers import pick_focus_key, prefer_void_rays
from sc2.ids.unit_typeid import UnitTypeId as UnitID

# O272-①:制空避战触发单位(实证:o270b-g03 暴风 9→2 被 腐化8-13+飞蛇 磨光)。
_AA_COUNTER = {UnitID.CORRUPTOR, UnitID.VIPER}


def _pick_focus(enemies, focus: str | None, origin=None) -> Unit:
    """③焦点：从敌人里按参谋长的 focus 挑目标。认不出 / 没命中 → 默认选法。

    纯选择逻辑委托给 levers.pick_focus_key(单一真相源,可离线单测);它返回 None 时
    先走 O88 虚空优先(prefer_void_rays:棱镜烧装甲暴风是最快战损来源,暴风
    射程 10>6,优先点杀=虚空死在爬进 beam 射程的路上),再退回 ares 的
    cy_pick_enemy_target(引擎默认选法)。origin=发起攻击的单位,
    用于 closest 按"离它最近"挑(tempest 风筝时传 unit)。"""
    chosen = pick_focus_key(enemies, focus, origin=origin)
    if chosen is not None:
        return chosen
    void = prefer_void_rays(enemies, origin=origin)
    if void is not None:
        return void
    return cy_pick_enemy_target(enemies)

from bot.combat.base_unit import BaseUnit

if TYPE_CHECKING:
    from ares import AresBot


@dataclass
class TempestOffensive(BaseUnit):
    """Execute behavior for Tempest offensive attack.

    Called from `CombatManager`

    Parameters
    ----------
    ai : AresBot
        Bot object that will be running the game
    config : Dict[Any, Any]
        Dictionary with the data from the configuration file
    mediator : ManagerMediator
        Used for getting information from managers in Ares.
    """

    ai: "AresBot"
    config: dict
    mediator: ManagerMediator

    def execute(self, units: Units, **kwargs) -> None:
        """Actually execute tempest attack.

        Parameters
        ----------
        units : list[Unit]
            The units we want OracleHarass to control.
        **kwargs :
            See below.

        Keyword Arguments
        -----------------
        attack_target : Point2
            Point on the map Tempest should head towards.
        """

        assert (
            "attack_target" in kwargs
        ), "No value for scout_target was passed into kwargs."
        attack_target = kwargs["attack_target"]
        focus = kwargs.get("focus")          # ③焦点
        maneuver = kwargs.get("maneuver")    # ④机动意图
        # O65(o64 game_01 实证):推进承诺(闸全开)→ 行军模式 —— 不追 15 格内的
        # 过路敌(只打进了射程的),主力压向 attack_target。否则 Power 的小队骚扰
        # 在行为层把每艘暴风永久钩在原地风筝(敌退缩→追不上→敌回头→再风筝),
        # attack_target 给得再对,舰队也永远走不出去(满人口 260+s 寸功未立)。
        commit_push = kwargs.get("commit_push", False)
        # 埋伏/占位：到位后蹲点等敌进入射程，不主动追近敌（只打进了射程的）
        ambush = maneuver in ("ambush", "hold_position")
        everything_near_tempests: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=15,
            query_tree=UnitTreeQueryType.AllEnemy,
            return_as_dict=True,
        )
        # O272-①:撤避掩体点(最近就绪塔/电池,无则主基) —— 腐化/飞蛇成群逼近时
        # 暴风不风筝硬拼(腐化对装甲加成+速度碾压,风筝=慢速送死,实证:o270b-g03
        # 暴风 9→2 全灭),撤回地面火力圈上空,让塔/追猎接手制空。
        _cover_points = [
            s.position
            for s in self.ai.structures.ready
            if s.type_id in (UnitID.PHOTONCANNON, UnitID.SHIELDBATTERY)
        ]

        for unit in units:
            offensive_maneuver: CombatManeuver = CombatManeuver()

            enemy_near_tempest: Units = everything_near_tempests[unit.tag].filter(
                lambda u: not u.is_memory
            )

            # O272-①:制空避战 —— 腐化 ≥3 或飞蛇 ≥1(寄生弹)进入 15 格圈,
            # 直接脱离战场回掩体上空(不 commit_push 时;承诺推进照打)。
            _aa_close = [
                u
                for u in enemy_near_tempest
                if not u.is_structure and u.type_id in _AA_COUNTER
            ]
            if (
                not commit_push
                and (
                    sum(1 for u in _aa_close if u.type_id == UnitID.CORRUPTOR) >= 3
                    or any(u.type_id == UnitID.VIPER for u in _aa_close)
                )
            ):
                _fallback = (
                    min(_cover_points, key=lambda p: p.distance_to(unit.position))
                    if _cover_points
                    else self.ai.start_location
                )
                offensive_maneuver.add(
                    PathUnitToTarget(unit, self.mediator.get_air_grid, _fallback)
                )
                self.ai.register_behavior(offensive_maneuver)
                continue

            in_attack_range: list[Unit] = cy_in_attack_range(unit, enemy_near_tempest)

            if len(in_attack_range) > 0 and commit_push:
                # O68(o67-vh-protoss-power game_01 实证):攻城纪律 —— 满人口收尾期
                # 暴风被「射程内有敌就风筝」钩在敌残基地门口:叉子/追猎轮流折跃
                # 进来当诱饵,暴风全程 StutterUnitBack 放风筝,300+s 拆不掉
                # 2 塔+电池护着的 Nexus,对面从容重建(5→16 建筑)。
                # 有对空单位(追猎/凤凰/维京等)照风筝;否则建筑优先站定集火
                # (23 暴风一轮一座塔,电池奶不回来);只有非对空单位就直接行军,
                # 叉子/农民够不着空军,不配当诱饵。
                aa_threats = [
                    u for u in in_attack_range
                    if not u.is_structure and getattr(u, "can_attack_air", False)
                ]
                structs = [u for u in in_attack_range if u.is_structure]
                if aa_threats:
                    target = _pick_focus(aa_threats, focus, origin=unit)
                    offensive_maneuver.add(
                        StutterUnitBack(unit, target, True, self.mediator.get_air_grid)
                    )
                elif structs:
                    closest = min(
                        structs, key=lambda s: s.position.distance_to(unit.position)
                    )
                    offensive_maneuver.add(
                        AMove(unit, closest.position)
                    )
                else:
                    offensive_maneuver.add(
                        PathUnitToTarget(unit, self.mediator.get_air_grid, attack_target)
                    )
            elif len(in_attack_range) > 0:
                # 射程内有敌：按③焦点选目标点杀（埋伏时也照打进了范围的）
                target: Unit = _pick_focus(in_attack_range, focus, origin=unit)
                offensive_maneuver.add(
                    StutterUnitBack(unit, target, True, self.mediator.get_air_grid)
                )

            elif enemy_near_tempest and not ambush and not commit_push:
                # 附近有敌但没进射程：默认主动风筝追击；埋伏/占位时不追，继续蹲向目标点
                # O65:行军模式(commit_push)下也不追 —— 过路敌交给射程纪律,
                # 舰队保持压向 attack_target,不被小队钩回跑步机
                target: Unit = _pick_focus(enemy_near_tempest, focus, origin=unit)
                offensive_maneuver.add(
                    StutterUnitBack(unit, target, True, self.mediator.get_air_grid)
                )
            else:
                offensive_maneuver.add(
                    PathUnitToTarget(unit, self.mediator.get_air_grid, attack_target)
                )

            self.ai.register_behavior(offensive_maneuver)
