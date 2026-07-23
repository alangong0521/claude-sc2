"""追猎(Stalker)进攻 + blink 微操 —— 纯追猎流派（BUILD=stalker）用。F3 优化版 + B1。

相对旧版的 6 项优化:
① blink 帧先开火(blink 前先 AttackTarget 一下,不浪费这一帧输出)
② "附近有敌够不着"分支改 PathUnitToTarget 追击(原 StutterUnitBack 是后撤行为,该追击时反撤是 bug)
③ 全队集火同一目标(合并所有追猎附近敌选一个全队 target,而非每只各自选)
④ 进攻型 blink(目标残血能收 / 高价值 caster,且在 blink 距离内 → blink 贴脸,而非只后撤 blink)
⑤ blink 躲技能(附近 HIGHTEMPLAR/INFESTOR 等 caster 威胁时 blink 拉开躲风暴/真菌/EMP)
⑥ 保持阵型(射程内 AttackTarget 点杀保持射程不贴脸;低护盾 blink 拉开近似拉开阵型)
门限参数化(blink_at_shield_perc / blink_when_swarmed 改 @dataclass 字段,便于实测定参)。

B1 五项(2026-07-23,来源见 docs/community-tactics-research.md):
① 后跳盾阈值 25% → 12%(Sharky/sharpy 社区两家 12.5%/5%;blink 是 10s CD 稀缺资源,盾厚时走位风筝)
② AvoidTargetedDamage(Sharky):被超出自己射程的敌人(坦克/地刺)瞄准时不看盾量直接后跳
③ blink 前查 FUNGALGROWTH buff:真菌锁 blink,点了浪费,退回走位风筝
④ 后跳落点安全性校验(sharpy find_weak_influence_ground_blink):落点 influence 必须低于当前位置
⑤ Cyclone LOCKON 特判(BuffId.LOCKON):立刻 blink 远离,不看盾量不校验落点
"""
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import (
    AttackTarget,
    PathUnitToTarget,
    StutterUnitBack,
    UseAbility,
)
from cython_extensions.combat_utils import cy_pick_enemy_target
from cython_extensions.units_utils import cy_in_attack_range
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit
from bot.levers import (
    blink_away_point,
    blink_landing_is_safer,
    outranging_threats,
    pick_focus_key,
)

if TYPE_CHECKING:
    from ares import AresBot


# 高价值 caster:进攻型 blink 切这些,也用来躲它们的技能
_HIGH_VALUE_CASTERS = frozenset({
    UnitID.HIGHTEMPLAR, UnitID.INFESTOR, UnitID.GHOST, UnitID.RAVEN,
    UnitID.MEDIVAC, UnitID.VIPER, UnitID.SENTRY,
})
# caster 威胁半径(发现就 blink 拉开躲风暴/真菌)
_CASTER_THREAT_DIST: float = 9.0
# 进攻型 blink:目标残血阈值(血+盾低于此 → blink 上去收)。
# C2 实测调优:80 → 0(关掉残血贴脸触发——坦克阵里贴脸=送;切高价值 caster 保留)
_BLINK_KILL_HP: float = 0.0
# blink 距离(追猎 blink 约 7.5;只对射程外、blink 内的残血目标贴脸)
_BLINK_MIN_DIST: float = 6.0
_BLINK_MAX_DIST: float = 7.5
# B1⑤ Cyclone LOCKON:blink 后要与锁定者拉开的最小距离(未验证:blink 一跳只有 ~8,
# 15+ 需要连跳/后撤配合,这里先保证朝远离方向跳并尽量拉开)。
_LOCKON_ESCAPE_DIST: float = 15.0


def _grid_influence(grid, pos) -> float:
    """取网格 influence 值(越大越危险)。索引沿用 oracle_harass 的 grid[pos.rounded] 约定;
    越界/异常退回 0.0(视为安全,让 find_closest_safe_spot 的结果照样生效)。"""
    try:
        return float(grid[pos.rounded])
    except Exception:
        return 0.0


def _pick_focus(enemies, focus: str | None, origin=None) -> Unit:
    """焦点:按参谋长的 focus 挑目标,认不出 / 没命中 → ares 引擎默认选法。
    选择逻辑委托 levers.pick_focus_key(单一真相源,可离线单测)。"""
    chosen = pick_focus_key(enemies, focus, origin=origin)
    if chosen is not None:
        return chosen
    return cy_pick_enemy_target(enemies)


@dataclass
class StalkerOffensive(BaseUnit):
    """F3 优化版追猎微操。Called from CombatManager。"""

    ai: "AresBot"
    config: dict
    mediator: ManagerMediator
    # 门限参数化(便于离线/实测定参)
    # B1①:25% → 12%(社区两家 12.5%/5%;blink 10s CD 稀缺,盾厚时用走位风筝)
    blink_at_shield_perc: float = 0.12   # 护盾低于此 → blink 后撤求生
    blink_when_swarmed: int = 4           # 被这么多敌围 → blink 后撤

    def execute(self, units: Units, **kwargs) -> None:
        """Actually execute stalker attack with blink (F3 优化版)。

        Parameters
        ----------
        units : Units
            The stalkers we want to control (ATTACKING role 的追猎).
        **kwargs :
            attack_target, focus, maneuver。
        """
        assert "attack_target" in kwargs, "No attack_target passed into kwargs."
        attack_target = kwargs["attack_target"]
        focus = kwargs.get("focus") or "weakest"   # F3: 默认集火残血
        maneuver = kwargs.get("maneuver")
        ambush = maneuver in ("ambush", "hold_position")

        ground_grid = self.mediator.get_ground_grid

        everything_near_stalkers: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=15,
            query_tree=UnitTreeQueryType.AllEnemy,
            return_as_dict=True,
        )

        # ③ 全队集火:合并所有追猎附近敌(按 tag 去重),选一个全队共用 target。
        seen: set[int] = set()
        all_enemies_near: list[Unit] = []
        for u in units:
            for e in everything_near_stalkers[u.tag]:
                if not e.is_memory and e.tag not in seen:
                    seen.add(e.tag)
                    all_enemies_near.append(e)
        team_target: Unit | None = (
            _pick_focus(all_enemies_near, focus) if all_enemies_near else None
        )

        for unit in units:
            offensive_maneuver: CombatManeuver = CombatManeuver()

            enemy_near = everything_near_stalkers[unit.tag].filter(
                lambda u: not u.is_memory
            )
            in_attack_range: list[Unit] = cy_in_attack_range(unit, enemy_near)
            swarmed = len(enemy_near) >= self.blink_when_swarmed
            low_shield = unit.shield_percentage <= self.blink_at_shield_perc
            blink_ready = AbilityId.EFFECT_BLINK_STALKER in unit.abilities
            # B1③:真菌(FUNGALGROWTH)锁 blink —— 点了也跳不动,不浪费操作,退回走位风筝
            fungal_locked = BuffId.FUNGALGROWTH in unit.buffs
            # B1⑤:Cyclone LOCKON —— 被锁定立刻 blink 远离,不看盾量(未验证:待跑局确认)
            lockon = BuffId.LOCKON in unit.buffs
            # B1② AvoidTargetedDamage(Sharky):被超射程敌人(架起坦克/地刺)瞄准,
            # 站桩对撸稳亏 → 不看盾量直接后跳出其射程
            targeted_by_outranger = bool(outranging_threats(unit, enemy_near))

            # 这只追猎的目标:优先全队 target;否则射程内选一个
            my_target: Unit | None = team_target
            if my_target is None and in_attack_range:
                my_target = _pick_focus(in_attack_range, focus, origin=unit)

            # ⑤ 躲技能:附近高价值 caster 威胁(风暴/真菌/EMP)
            caster_threat = any(
                e.type_id in _HIGH_VALUE_CASTERS
                and e.distance_to(unit) < _CASTER_THREAT_DIST
                for e in enemy_near
            )

            did_blink = False

            # 优先级 1:躲技能 / 防守 blink —— 后撤到安全点
            defensive_trigger = (
                lockon or caster_threat or low_shield or swarmed or targeted_by_outranger
            )
            if blink_ready and not fungal_locked and defensive_trigger:
                # ① blink 帧先开火:blink 前先点一下目标,不浪费这一帧输出
                if my_target is not None:
                    offensive_maneuver.add(AttackTarget(unit=unit, target=my_target))
                if lockon:
                    # B1⑤ LOCKON 特判(Sharky):立刻朝远离 Cyclone 的方向 blink,
                    # 不看盾量、不校验落点 —— 锁定期吃满导弹就是死,先拉开再说(未验证)
                    escape = self._lockon_escape_point(unit, enemy_near, ground_grid)
                    if escape is not None:
                        offensive_maneuver.add(
                            UseAbility(AbilityId.EFFECT_BLINK_STALKER, unit, escape)
                        )
                        did_blink = True
                else:
                    safe_point = self.mediator.find_closest_safe_spot(
                        from_pos=unit.position, grid=ground_grid, radius=8.0
                    )
                    # B1④ 落点安全性校验(sharpy):落点 influence 必须严格低于当前位置,
                    # 否则白交 10s CD 跳进更危险的地方 → 不跳,退回走位风筝
                    if blink_landing_is_safer(
                        _grid_influence(ground_grid, unit.position),
                        _grid_influence(ground_grid, safe_point),
                    ):
                        offensive_maneuver.add(
                            UseAbility(AbilityId.EFFECT_BLINK_STALKER, unit, safe_point)
                        )
                        did_blink = True
                    else:
                        did_blink = self._kite_fallback(
                            offensive_maneuver, unit, my_target, enemy_near, ground_grid
                        )
            elif fungal_locked and defensive_trigger and enemy_near:
                # B1③:被真菌定住 blink 不可用 → 退回走位风筝(站撸换血也是死)
                did_blink = self._kite_fallback(
                    offensive_maneuver, unit, my_target, enemy_near, ground_grid
                )

            # 优先级 2:进攻型 blink —— 目标残血能收 / 是高价值 caster,且在 blink 距离内 → 贴脸
            # B1③:真菌锁定时同样不浪费进攻 blink
            elif blink_ready and not fungal_locked and my_target is not None:
                target_hp = my_target.health + my_target.shield
                dist = unit.distance_to(my_target)
                if (
                    (target_hp < _BLINK_KILL_HP or my_target.type_id in _HIGH_VALUE_CASTERS)
                    and _BLINK_MIN_DIST < dist <= _BLINK_MAX_DIST
                ):
                    if in_attack_range:
                        offensive_maneuver.add(AttackTarget(unit=unit, target=my_target))
                    offensive_maneuver.add(
                        UseAbility(
                            AbilityId.EFFECT_BLINK_STALKER, unit, my_target.position
                        )
                    )
                    did_blink = True

            # 没 blink → 常规输出
            if not did_blink:
                if in_attack_range:
                    # ②⑥ 射程内有敌:点杀(全队 target 在射程就用它集火,否则射程内选),保持射程不贴脸
                    if my_target is not None and any(
                        t.tag == my_target.tag for t in in_attack_range
                    ):
                        tgt = my_target
                    else:
                        tgt = _pick_focus(in_attack_range, focus, origin=unit)
                    offensive_maneuver.add(AttackTarget(unit=unit, target=tgt))
                elif enemy_near and not ambush:
                    # ③ 附近有敌但够不着 → 追击(原 StutterUnitBack 后撤是 bug,改 PathUnitToTarget)
                    offensive_maneuver.add(
                        PathUnitToTarget(
                            unit,
                            ground_grid,
                            my_target.position if my_target is not None else attack_target,
                        )
                    )
                else:
                    # ④ 无近敌 → 推进语义目标
                    offensive_maneuver.add(
                        PathUnitToTarget(unit, ground_grid, attack_target)
                    )

            self.ai.register_behavior(offensive_maneuver)

    def _lockon_escape_point(self, unit: Unit, enemy_near: Units, ground_grid):
        """B1⑤ LOCKON 逃点:朝"远离最近 Cyclone"方向 blink 到满射程;
        找不到 Cyclone(在射程外锁的)→ 退回通用安全点(未验证)。"""
        cyclones = [e for e in enemy_near if e.type_id == UnitID.CYCLONE]
        if cyclones:
            nearest = min(cyclones, key=lambda e: e.distance_to(unit))
            away = blink_away_point(unit.position, nearest.position, _BLINK_MAX_DIST)
            if away is not None:
                return Point2(away)
        return self.mediator.find_closest_safe_spot(
            from_pos=unit.position, grid=ground_grid, radius=8.0
        )

    def _kite_fallback(
        self, maneuver: CombatManeuver, unit: Unit, my_target, enemy_near: Units, ground_grid
    ) -> bool:
        """走位风筝兜底:不该/不能 blink 时 StutterUnitBack 拉开距离(打一下就退)。
        成功加入行为返回 True(= 本帧已处理,不再走常规输出分支)。"""
        kite_target = my_target
        if kite_target is None and enemy_near:
            kite_target = cy_pick_enemy_target(enemy_near)
        if kite_target is None:
            return False
        maneuver.add(StutterUnitBack(unit, kite_target, True, ground_grid))
        return True
