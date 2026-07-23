"""Warp Prism(折跃棱镜)专属 combat class —— 相位折跃 + 接残血,不做人机搬运(B9)。

调研来源(社区 bot,见 docs/community-tactics-research.md §B9):
- Sharky WarpPrismMicroController:满盾 + 附近无敌 + 有折跃门快转好才变相位模式,
  给前线供折跃能量场;盾被打掉或能量场没用了就变回运输模式。
- sharpy micro_warp_prism:接残血打分 `score = 射程×(1.1−血量%)×战力−1`,
  只接盾已空且武器在冷却的单位;zealot 有敌在其射程内不接(叉子就是抗线的,
  契合我们 zealot 抗线、prism 只救后排的混编)。

注意:python-sc2 的技能枚举名是 MORPH_WARPPRISMPHASINGMODE(不是任务书里的
PHALANX),已按 sc2 AbilityId 实测核对。折跃门冷却在观测里拿不到字段,靠自己记账
近似(见 _track_warpgates,未验证)。站位借用 mediator.get_air_grid 的 influence
找弱威胁空域悬停(与 oracle_harass 用同一网格口径)。

⚠️ 全部行为未跑局验证(B9 排期在 B1~B5 稳定之后),阈值均照搬社区实现。
"""
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional

from ares import ManagerMediator, UnitTreeQueryType
from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import (
    AMove,
    DropCargo,
    KeepUnitSafe,
    PathUnitToTarget,
    PickUpCargo,
    UseAbility,
)
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.base_unit import BaseUnit

if TYPE_CHECKING:
    from ares import AresBot

# 相位模式阈值(Sharky,未跑局验证)
_SUPPLY_CAP = 198                    # 接近满人口就不必铺能量场了
_PHASE_EXIT_SHIELD = 0.75            # 盾低于这个比例且有敌人 → 变回运输模式跑路
_THREAT_RANGE = 8.0                  # 相位条件:附近 8 格无敌军战斗单位/防御建筑

# 折跃门冷却近似(观测里拿不到,自己记账;21.4s 是常见地面兵折跃冷却,未验证)
_WARPGATE_COOLDOWN_FRAMES = int(21.4 * 22.4)
_SOON_FRAMES = int(2.0 * 22.4)       # "冷却<2s"换算成帧

# 接残血(sharpy,未跑局验证)
_RESCUE_RANGE = 12.0                 # 只接 12 格内的残血
_RESCUE_WEAPON_COOLDOWN = 2          # 武器冷却 > 2(帧)才接:还在输出的不接

# 站位:跟随的高价值陆军 + 威胁判定口径
_HIGH_VALUE_NAMES = ("IMMORTAL", "COLOSSUS", "ARCHON", "HIGHTEMPLAR")
_DEFENSE_NAMES = (
    "PHOTONCANNON", "MISSILETURRET", "SPORECRAWLER",
    "SPINECRAWLER", "BUNKER", "PLANETARYFORTRESS",
)
_WORKER_NAMES = ("SCV", "PROBE", "DRONE", "MULE")


def rescue_score(hp_pct: float, weapon_range: float, power: float) -> float:
    """sharpy 接残血打分:score = 射程×(1.1−血量%)×战力−1。纯逻辑,可单测。"""
    return weapon_range * (1.1 - hp_pct) * power - 1


def is_rescue_candidate(
    shield: float,
    weapon_cooldown: float,
    distance: float,
    type_name: str = "",
    enemy_in_range: bool = False,
) -> bool:
    """接残血资格:盾已空、武器冷却>2、距离≤12;zealot 有敌在其射程内不接。纯逻辑。"""
    if shield > 0 or weapon_cooldown <= _RESCUE_WEAPON_COOLDOWN or distance > _RESCUE_RANGE:
        return False
    if type_name == "ZEALOT" and enemy_in_range:
        return False  # 叉子抗线是本职,被打时不接(盾>0 已被上面拦掉)
    return True


def should_phase_morph(
    shield_full: bool,
    threat_near: bool,
    warpgate_soon: bool,
    field_nearby: bool,
    supply_used: float,
    supply_cap: int = _SUPPLY_CAP,
) -> bool:
    """相位模式条件(Sharky):满盾、附近无敌、有门快转好、附近无能量场、人口<198。纯逻辑。"""
    return (
        shield_full
        and not threat_near
        and warpgate_soon
        and not field_nearby
        and supply_used < supply_cap
    )


def should_phase_exit(shield_pct: float, enemy_near: bool, field_needed: bool) -> bool:
    """离开相位:盾<75% 且有敌人,或折跃门不再需要能量场 → 变回运输模式。纯逻辑。"""
    return (shield_pct < _PHASE_EXIT_SHIELD and enemy_near) or not field_needed


def pick_hover_point(anchor, candidates, values):
    """站位:在候选悬停点里挑 influence 最低的;全不可读 → 锚点头顶。纯逻辑,可单测。"""
    best = None
    best_v = None
    for c, v in zip(candidates, values):
        if v is None:
            continue  # 出界/不可读的点不参与
        if best_v is None or v < best_v:
            best, best_v = c, v
    return best if best is not None else anchor


@dataclass
class WarpPrismOffensive(BaseUnit):
    """折跃棱镜指挥:相位折跃供能量场 + 打分式接残血 + 跟高价值陆军站位。"""

    ai: "AresBot"
    config: dict
    mediator: ManagerMediator
    # 折跃门冷却记账:tag → 冷却转好的 game_loop(近似,见 _track_warpgates)
    _warpgate_ready: dict = field(default_factory=dict)

    def execute(self, units: Units, **kwargs) -> None:
        """逐个棱镜:相位中 → 看要不要变回;运输中 → 逃命/接残血/变相位/站位。

        Keyword Arguments
        -----------------
        attack_target : Point2  找不到跟随锚点时的兜底集结点
        """
        assert "attack_target" in kwargs, "attack_target is required"
        attack_target = kwargs["attack_target"]
        self._track_warpgates()

        near: dict[int, Units] = self.mediator.get_units_in_range(
            start_points=units,
            distances=15,
            query_tree=UnitTreeQueryType.AllEnemy,
            return_as_dict=True,
        )
        for unit in units:
            enemies: Units = near[unit.tag].filter(lambda u: not u.is_memory)
            if unit.type_id == UnitID.WARPPRISMPHASING:
                self._handle_phasing(unit, enemies)
            else:
                self._handle_transport(unit, enemies, attack_target)

    # ── 相位模式 ──────────────────────────────────────────────────────
    def _handle_phasing(self, unit: Unit, enemies: Units) -> None:
        """相位中:能量场没用了或被打疼了 → 变回运输模式;否则原地待着供场。"""
        if should_phase_exit(
            shield_pct=unit.shield_percentage,
            enemy_near=len(enemies) > 0,
            field_needed=self._any_warpgate_soon(),
        ):
            plan: CombatManeuver = CombatManeuver()
            plan.add(UseAbility(AbilityId.MORPH_WARPPRISMTRANSPORTMODE, unit, None))
            self.ai.register_behavior(plan)

    # ── 运输模式 ──────────────────────────────────────────────────────
    def _handle_transport(self, unit: Unit, enemies: Units, attack_target) -> None:
        plan: CombatManeuver = CombatManeuver()
        grid = self._air_grid()
        threats: list[Unit] = [e for e in enemies if _is_threat(e)]

        # ①被打疼了先跑(盾阈值与相位退出条件同口径)
        if unit.shield_percentage < _PHASE_EXIT_SHIELD and threats:
            if grid is not None:
                plan.add(KeepUnitSafe(unit, grid))
            else:
                plan.add(AMove(unit, self.ai.start_location))
            self.ai.register_behavior(plan)
            return

        # ②背着货:脱离威胁就把残血放下来(放回原战场由它自己打)
        if unit.has_cargo:
            if not threats:
                plan.add(DropCargo(unit, unit.position))
            elif grid is not None:
                plan.add(KeepUnitSafe(unit, grid))
            else:
                plan.add(AMove(unit, self.ai.start_location))
            self.ai.register_behavior(plan)
            return

        # ③接残血(sharpy 打分式,只救盾空+武器冷却中的后排)
        best = self._pick_rescue(unit, enemies)
        if best is not None and grid is not None:
            plan.add(PickUpCargo(unit, grid, [best]))
            self.ai.register_behavior(plan)
            return

        # ④相位折跃:条件齐了就地变能量场(复用 Sharky 五条)
        threat_close: bool = any(
            e.position.distance_to(unit.position) < _THREAT_RANGE for e in threats
        )
        if should_phase_morph(
            shield_full=unit.shield_percentage >= 1.0,
            threat_near=threat_close,
            warpgate_soon=self._any_warpgate_soon(),
            field_nearby=self._field_covers(unit.position),
            supply_used=self.ai.supply_used,
        ):
            plan.add(UseAbility(AbilityId.MORPH_WARPPRISMPHASINGMODE, unit, None))
            self.ai.register_behavior(plan)
            return

        # ⑤站位:跟高价值陆军头顶,挑空中 influence 最弱的点悬停
        anchor = self._high_value_anchor(unit)
        if anchor is not None and grid is not None:
            hover: Point2 = self._weak_air_point(anchor, grid)
            plan.add(PathUnitToTarget(unit, grid, hover, success_at_distance=1.5))
        else:
            plan.add(AMove(unit, attack_target))
        self.ai.register_behavior(plan)

    # ── 内部工具 ──────────────────────────────────────────────────────
    def _track_warpgates(self) -> None:
        """折跃门冷却观测里拿不到,自己记账:看到折跃中的门就记 ready 帧(近似,未验证)。"""
        now: int = self.ai.state.game_loop
        for wg in self.ai.structures(UnitID.WARPGATE):
            if wg.is_ready and wg.orders:
                self._warpgate_ready.setdefault(wg.tag, now + _WARPGATE_COOLDOWN_FRAMES)

    def _any_warpgate_soon(self) -> bool:
        """是否有 completed 折跃门冷却<2s(含已转好的)。一个门都没有 → False(场没意义)。"""
        gates = self.ai.structures(UnitID.WARPGATE).ready
        if not gates:
            return False
        soon: int = self.ai.state.game_loop + _SOON_FRAMES
        return any(self._warpgate_ready.get(wg.tag, 0) <= soon for wg in gates)

    def _field_covers(self, pos) -> bool:
        """该点是否已有能量场(水晶塔/别的相位棱镜)。未验证:power_sources 含相位棱镜。"""
        try:
            return self.ai.state.psionic_matrix.covers(pos)
        except Exception:
            return False  # 拿不到就不当覆盖(别卡死相位条件)

    def _pick_rescue(self, prism: Unit, enemies: Units) -> Optional[Unit]:
        """附近 12 格内打分最高的可接单位;没有 → None。"""
        best: Optional[Unit] = None
        best_score: float = 0.0  # score<=0 不接(sharpy 打分式自带 −1 门槛)
        for u in self.ai.units:
            if u.is_structure or u.is_flying or u.tag == prism.tag:
                continue
            d: float = u.distance_to(prism)
            enemy_in_range: bool = False
            if u.type_id.name == "ZEALOT":
                # zealot 射程≈近战,"有敌在其射程内不接"(+1 容差,未验证)
                enemy_in_range = any(
                    e.distance_to(u) <= u.ground_range + e.radius + 1.0 for e in enemies
                )
            if not is_rescue_candidate(
                u.shield, u.weapon_cooldown, d, u.type_id.name, enemy_in_range
            ):
                continue
            s: float = rescue_score(
                u.health_percentage, u.ground_range, max(u.ground_dps, 1.0)
            )
            if s > best_score:
                best, best_score = u, s
        return best

    def _high_value_anchor(self, prism: Unit) -> Optional[Unit]:
        """最近的高价值陆军(不朽/巨像/白球/高阶圣堂)当跟随锚点;没有 → None。"""
        anchor: Optional[Unit] = None
        best_d = None
        for u in self.ai.units:
            if u.type_id.name in _HIGH_VALUE_NAMES:
                d: float = u.distance_to(prism)
                if best_d is None or d < best_d:
                    anchor, best_d = u, d
        return anchor

    def _weak_air_point(self, anchor: Unit, grid) -> Point2:
        """锚点周围采 9 个点,挑空中 influence 最低的悬停(未验证:采样密度待跑局调)。"""
        ax, ay = anchor.position.x, anchor.position.y
        offsets = [
            (0, 0), (4, 0), (-4, 0), (0, 4), (0, -4),
            (4, 4), (-4, -4), (4, -4), (-4, 4),
        ]
        candidates = [(ax + dx, ay + dy) for dx, dy in offsets]
        values = []
        for cx, cy in candidates:
            try:
                values.append(float(grid[int(round(cx)), int(round(cy))]))
            except Exception:
                values.append(None)
        hx, hy = pick_hover_point((ax, ay), candidates, values)
        return Point2((hx, hy))

    def _air_grid(self):
        """取空中网格(站位/逃命用);拿不到返回 None(各分支退回 AMove)。"""
        try:
            return self.mediator.get_air_grid
        except Exception:
            return None


def _is_threat(e: Unit) -> bool:
    """威胁 = 战斗单位或防御建筑(农民和普通建筑不算,相位条件/逃命同一口径)。"""
    name: str = e.type_id.name
    if name in _WORKER_NAMES:
        return False
    if e.is_structure:
        return name in _DEFENSE_NAMES
    return e.can_attack
