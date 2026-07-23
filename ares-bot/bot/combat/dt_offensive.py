"""DT(黑暗圣堂)专属 combat class —— 被反隐照到就撤 + 矿线农民骚扰(B5)。

调研来源(社区 bot,见 docs/community-tactics-research.md §2.4/§B5):
- Sharky DarkTemplarMicroController:未被发现时关闭一切规避(隐身走位是负收益),
  被发现且盾不满才后跳出敌射程;ares 有现成接口 `mediator.get_is_detected(unit)`
  (unit_memory_manager.py:558),我们此前没用 —— DT 被雷达/OB/炮台照到照样站撸,
  隐刀价值归零。
- 我们没研究 Shadow Stride(DT blink),所以撤退走 KeepUnitSafe 网格安全点,
  不做 blink 后跳;未发现时完全复用 GenericOffensive(站撸/压点逻辑不变)。

B5 骚扰升级(来源:Sharky DarkTemplarHarassTask + sharpy dt_attack):
- 目标从"基地中心"改为"矿线":ai.mineral_field 按已知敌方基地位置聚类取矿簇中心。
  attack_target 语义不变(参谋长的 stance/target 覆盖仍由 combat_manager 决定),
  DT 只是在压点时用矿线点替换基地中心;交战时 focus 强制 workers
  (优先 SCV/PROBE/DRONE/MULE),司令点名了别的焦点则以司令为准。
- 三条换矿规则(Sharky):①矿点 10 格无敌军 → 换下一个已知敌矿;
  ②矿点被反隐覆盖(ares DETECTOR_RANGES,已含安全 buffer)且自己盾不满 → 换;
  ③反隐在 DT 11 格内 → 换(立刻,不管盾)。选下一个矿的纯逻辑抽成
  pick_next_harass_target,可单测。

⚠️ 换矿规则的阈值(10/11 格)与反隐口径未跑局验证;「被侦测且盾不满→KeepUnitSafe」
的既有逻辑保持不动。

只影响 DARKTEMPLAR(army_composition.yml 里 combat=dt_offensive),
carrier/tempest 流派不产 DT,零行为变更。
"""
from dataclasses import dataclass
from typing import Optional

from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, KeepUnitSafe
from ares.dicts.enemy_detector_ranges import DETECTOR_RANGES
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.generic_offensive import GenericOffensive

# 敌方城主建筑(找"已知敌矿"用;与 combat_manager._known_enemy_townhalls 同一口径)
TOWNHALL_TYPES: set[UnitID] = {
    UnitID.NEXUS,
    UnitID.COMMANDCENTER,
    UnitID.ORBITALCOMMAND,
    UnitID.PLANETARYFORTRESS,
    UnitID.HATCHERY,
    UnitID.LAIR,
    UnitID.HIVE,
}

# DT 交战默认焦点:矿线农民(levers.pick_focus_key 的 "workers" 槽)
_WORKER_FOCUS = "workers"

# 换矿规则阈值(Sharky,未跑局验证)
_NO_ENEMY_RADIUS = 10.0   # 规则①:矿点 N 格无敌军 → 换
_DETECTOR_ON_TOP = 11.0   # 规则③:反隐在 DT N 格内 → 立刻换


def cluster_mineral_lines(base_points, mineral_points, radius: float = 10.0):
    """矿点按敌方基地位置聚类,返回每簇矿线中心点列表(没矿的基地跳过)。

    base_points/mineral_points: [(x, y), ...];返回 [(x, y), ...]。纯逻辑,可单测。
    """
    lines: list[tuple[float, float]] = []
    for bx, by in base_points:
        xs: list[float] = []
        ys: list[float] = []
        for mx, my in mineral_points:
            if (mx - bx) ** 2 + (my - by) ** 2 <= radius * radius:
                xs.append(mx)
                ys.append(my)
        if xs:
            lines.append((sum(xs) / len(xs), sum(ys) / len(ys)))
    return lines


def pick_next_harass_target(dt_pos, current, candidates, blocked, eps: float = 1.0):
    """换矿:挑离 DT 最近、没被 block、且不是 current 的矿线点;没有 → None。

    dt_pos/current/candidates 都是 (x, y);blocked 与 candidates 等长。
    current=None 表示还没选过(初次选矿)。纯逻辑,可单测。
    """
    best = None
    best_d = None
    for (cx, cy), is_blocked in zip(candidates, blocked):
        if is_blocked:
            continue
        if (
            current is not None
            and abs(cx - current[0]) < eps
            and abs(cy - current[1]) < eps
        ):
            continue  # 换矿不能换回原地
        d = (cx - dt_pos[0]) ** 2 + (cy - dt_pos[1]) ** 2
        if best_d is None or d < best_d:
            best, best_d = (cx, cy), d
    return best


@dataclass
class DtOffensive(GenericOffensive):
    """DT 指挥:未被侦测 → 矿线骚扰;被侦测且盾不满 → 撤到网格安全点。

    「盾不满」条件照抄 Sharky:满盾 DT 即使被照到也值得换输出(盾就是拿来扛的),
    盾掉了隐身又没有,继续站撸就是白送。
    """

    # 当前骚扰的矿线点(三条换矿规则维护;None = 回退 attack_target)
    _harass_target: Optional[Point2] = None

    def execute(self, units: Units, **kwargs) -> None:
        attack_target = kwargs["attack_target"]
        focus = kwargs.get("focus")
        maneuver = kwargs.get("maneuver")

        retreat: list[Unit] = []
        fight: list[Unit] = []
        for unit in units:
            try:
                detected = self.mediator.get_is_detected(unit)
            except Exception:
                detected = False  # 接口拿不到就不当被发现(保持通用逻辑)
            if detected and unit.shield_percentage < 1.0:
                retreat.append(unit)
            else:
                fight.append(unit)

        for unit in retreat:
            maneuver_plan: CombatManeuver = CombatManeuver()
            grid = self._maybe_grid(unit)
            if grid is not None:
                maneuver_plan.add(KeepUnitSafe(unit, grid))
            else:
                maneuver_plan.add(AMove(unit, self.ai.start_location))
            self.ai.register_behavior(maneuver_plan)

        if fight:
            self._update_harass_target(fight)
            target: Point2 = (
                self._harass_target if self._harass_target is not None else attack_target
            )
            super().execute(
                Units(fight, self.ai),
                attack_target=target,
                # 交战优先杀矿线农民;司令点名了焦点则以司令为准
                focus=focus or _WORKER_FOCUS,
                maneuver=maneuver,
            )

    def _update_harass_target(self, fight: list[Unit]) -> None:
        """三条换矿规则维护 self._harass_target(Sharky DarkTemplarHarassTask)。

        ⚠️ 未跑局验证:无敌军/反隐的距离阈值照搬 Sharky,实战手感待调。
        """
        ai = self.ai
        townhalls = [s for s in ai.enemy_structures if s.type_id in TOWNHALL_TYPES]
        if not townhalls:
            self._harass_target = None  # 不知道敌基地在哪,回退 attack_target
            return
        base_points = [(s.position.x, s.position.y) for s in townhalls]
        mineral_points = [(m.position.x, m.position.y) for m in ai.mineral_field]
        candidates = cluster_mineral_lines(base_points, mineral_points)
        if not candidates:
            self._harass_target = None
            return

        # 规则①:矿点 10 格无敌军(农民跑光/矿被打空)→ 该矿没得打,block
        # 规则②:矿点被反隐覆盖且有 DT 盾不满 → block(满盾还敢硬换输出)
        wounded: bool = any(u.shield_percentage < 1.0 for u in fight)
        detectors = getattr(ai, "enemy_detectors", []) or []
        blocked: list[bool] = []
        for cx, cy in candidates:
            c = Point2((cx, cy))
            no_enemy = not any(
                e.position.distance_to(c) < _NO_ENEMY_RADIUS for e in ai.enemy_units
            )
            covered = wounded and any(
                d.position.distance_to(c) < DETECTOR_RANGES.get(d.type_id, 11.0)
                for d in detectors
            )
            blocked.append(no_enemy or covered)

        current = (
            None
            if self._harass_target is None
            else (self._harass_target.x, self._harass_target.y)
        )
        need_new: bool = current is None
        if current is not None:
            idx = next(
                (
                    i
                    for i, (cx, cy) in enumerate(candidates)
                    if abs(cx - current[0]) < 1.0 and abs(cy - current[1]) < 1.0
                ),
                None,
            )
            if idx is None:
                need_new = True  # 当前矿的基地被打掉了,重选
                current = None
            else:
                # 规则③:反隐在任一 DT 11 格内 → 立刻离开这个矿(不管盾)
                detector_on_top: bool = any(
                    d.position.distance_to(u.position) < _DETECTOR_ON_TOP
                    for d in detectors
                    for u in fight
                )
                if blocked[idx] or detector_on_top:
                    need_new = True
                    blocked[idx] = True  # 排除当前矿,逼 pick_next 换一个

        if need_new:
            anchor = fight[0].position  # 用排头 DT 的位置挑最近的矿
            nxt = pick_next_harass_target((anchor.x, anchor.y), current, candidates, blocked)
            # 全都没得打 → None,DT 回退 attack_target 听大部队指挥
            self._harass_target = Point2(nxt) if nxt is not None else None
