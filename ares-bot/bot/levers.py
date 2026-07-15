"""操纵杆纯逻辑 —— 不依赖 ares/sc2 运行时,可离线单测。

把原本散在 combat_manager / production_manager / tempest_offensive 里的"语义→坐标/枚举"
纯计算抽到这里,方便:
  - 离线单测(不用起游戏);
  - CLI 校验复用同一份逻辑;
  - 以后扩词表/兵种只改这里。

运行时 manager 仍需 ares 对象(查 enemy_structures / expansion_locations 等),所以这里
只抽"给定输入算输出"的部分;需要运行时上下文的解析(如 _resolve_steer_target 里查已知
敌方城镇厅)保留在 manager 里,但拆成"取候选 + 纯选择"两步 —— 后者放这里。
"""
from __future__ import annotations

from typing import Sequence

from bot.steer_vocab import (
    BUILD_ALIASES, BUILDABLE, canonical_build, enemy_slot_index,
)


# ── ① 焦点敌人槽位 ──────────────────────────────────────────────────────
def resolve_enemy_slot(sel: str | None, n_enemies: int) -> int:
    """焦点敌人选择 → 0 基索引,边界安全。认不出/越界 → 0(最近,默认 E1)。

    n_enemies=敌方起始点数(1v1 时为 1)。纯逻辑,可单测。
    """
    idx = enemy_slot_index(sel)
    if idx is None or idx < 0 or idx >= n_enemies:
        return 0
    return idx


# ── ② 语义目标 → 坐标候选 ───────────────────────────────────────────────
# enemy_natural/third/fourth 需要运行时查"已知敌方城镇厅",manager 负责取候选列表,
# 这里只做"从候选里挑第 idx 个,没有就返回 None"的纯选择。
def pick_known_base(
    key: str, known_bases: Sequence,  # 已按"离焦点敌人由近及远"排好序
) -> int | None:
    """enemy_natural/third/fourth → 在已知敌方基地列表里的索引;查不到 → None。

    返回 None 让 manager 回退到默认追敌,不硬冲空地。key 不认得也返回 None。
    纯逻辑,可单测(传任意有序序列)。
    """
    idx = {"enemy_natural": 1, "enemy_third": 2, "enemy_fourth": 3}.get(key)
    if idx is None:
        return None
    if idx < len(known_bases):
        return idx
    return None  # 还没探到那么多矿,别硬冲


# ── ③ 焦点(focus)选择 ──────────────────────────────────────────────────
def pick_focus_key(enemies, focus: str | None, origin=None):
    """从敌人里按 focus 挑目标。纯逻辑版(不 import ares 的 cy_pick_enemy_target)。

    与 tempest_offensive._pick_focus 一致,但"默认/认不出"时返回 None(交回调用方走
    引擎默认选法),这样本函数完全无 ares 依赖、可单测。

    enemies: 任意可迭代,元素需有 .health/.shield/.type_id/.distance_to(视 focus 而定)。
    origin:  发起单位,用于 closest 按距离挑;None 时 closest 退回 None(=引擎默认)。
    """
    if not focus or not enemies:
        return None
    if focus == "weakest":
        return min(enemies, key=lambda u: u.health + u.shield)
    if focus == "workers":
        ws = [u for u in enemies if getattr(u.type_id, "name", "") in _WORKER_NAMES
              or _is_worker(u)]
        return ws[0] if ws else None
    if focus == "closest":
        if origin is not None:
            return min(enemies, key=lambda u: origin.distance_to(u))
        return None
    # 兵种名
    typed = [u for u in enemies if getattr(u.type_id, "name", "") == focus]
    return typed[0] if typed else None


# 测试用:避免 import ares.consts.WORKER_TYPES(会拉起 ares)。运行时 manager 仍用 ares 的。
_WORKER_NAMES = {"PROBE", "SCV", "DRONE", "MULE"}


def _is_worker(u) -> bool:
    """不依赖 ares 的 worker 判断(测试桩可能是假对象)。"""
    name = getattr(getattr(u, "type_id", None), "name", "")
    return name in _WORKER_NAMES


# ── ④ build 别名 → 引擎结构名 ────────────────────────────────────────────
def resolve_build_name(name: str) -> str | None:
    """build=<名> → 引擎枚举名(大写字符串),认不出 → None。

    先走 canonical_build(steer_vocab 别名表)归一,再用本模块 BUILD_ALIASES 复核。
    返回的是"给 getattr(UnitID, name) 用的枚举名",不是 UnitID 本身(避免 import sc2)。
    纯逻辑,可单测。
    """
    if not name:
        return None
    canon = canonical_build(name)
    # canonical_build 已把 gas→assimilator 等归一;再确认是规范名或别名键
    if canon in BUILDABLE or canon in BUILD_ALIASES:
        # 映射到引擎枚举名:BUILD_ALIASES 的值就是规范名(小写),转大写即枚举名
        return canon.upper()
    # 不在规范表 → 原样大写交回(可能是 PYLON/DARKSHRINE 等)
    return name.strip().upper() or None


# ── ⑤ 择时触发器 ────────────────────────────────────────────────────────
def should_hold_for_trigger(
    trigger: str | None,
    supply_used: int,
    enemy_near_base: bool,
    maxed_threshold: int = 190,
) -> bool:
    """⑥择时:条件没到 → 返回 True(按兵不动)。纯逻辑,可单测。

    - now/None → 立即打(False)
    - when_maxed → supply_used < maxed_threshold 时等(True)
    - when_enemy_away → 敌主力在家(enemy_near_base=True)时等(True)
    认不出的 trigger 当作 now(不阻塞)。
    """
    if trigger == "when_maxed":
        return supply_used < maxed_threshold
    if trigger == "when_enemy_away":
        return enemy_near_base
    return False


# ── ⑥ 一次性 vs 粘性判定 ────────────────────────────────────────────────
# build/expand/scout 是"一次性锁定"命令:造到/派过即停,想再来先 clear。
# stance/target/focus/maneuver/harass/trigger/enemy 是粘性的。
ONE_SHOT_FIELDS = ("build", "expand", "scout")
STICKY_FIELDS = ("stance", "target", "focus", "maneuver", "harass", "trigger", "enemy")


def is_one_shot(field: str) -> bool:
    """该操纵杆是否为"一次性锁定"型(造到即停,重下同值是 no-op)。"""
    return field in ONE_SHOT_FIELDS