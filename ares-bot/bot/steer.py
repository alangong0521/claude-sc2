"""参谋长指挥接缝 —— Aristaeus 版精简 steer。

参谋长（LLM / steer_cli）侧：写 `~/agent-rts-steer/orders.json`，读 `state.json`。
bot 侧：每隔 N 游戏秒 `publish_state(...)` 发布战况，`read_order()` 取最新命令。

Aristaeus 主力是 tempest 一支大军，第一刀不分队 —— 全军一个命令。
命令模型（orders.json，粘性：写了才变）：字段全集见 bot/steer_vocab.py 的 FIELDS
    —— stance/target/focus/maneuver/harass/trigger/expand/build/scout/enemy/note。
read_order() 会把这 11 个字段一次读回。语义目标(target)由 bot 侧 combat_manager
求解成 Point2（参谋长不点坐标）。
"""
from __future__ import annotations

import json
import os
from pathlib import Path

# 词表(单一真相源,见 bot/steer_vocab.py)。re-export 供旧调用方 `from bot import steer` 用。
from bot.steer_vocab import (  # noqa: F401  (re-exported for callers of this module)
    BUILDABLE,
    ENEMY_SLOTS,
    EXPAND,
    FIELDS as _FIELDS,
    FOCUS,
    HARASS,
    MANEUVERS,
    META_FIELDS as _META_FIELDS,
    STANCES,
    TARGETS,
    TRIGGERS,
    enemy_slot_index,
)

# 与参谋长交换文件的目录（默认 ~/agent-rts-steer，可用 STEER_DIR 覆盖）
STEER_DIR = Path(os.environ.get("STEER_DIR", Path.home() / "agent-rts-steer"))
ORDERS_FILE = STEER_DIR / "orders.json"
STATE_FILE = STEER_DIR / "state.json"

# C1·fixture 录制:设 STEER_RECORD=<目录> 时,每次 publish_state 除写 state.json 外,
# 再把该快照按 time 存一份到该目录(state_<time>.json),供离线回放测试参谋逻辑(L4),
# 不必每改一次 skill 都开游戏。不设则零开销。
_RECORD_DIR = os.environ.get("STEER_RECORD")


def read_order() -> dict:
    """读参谋长写的 orders.json，返回 FIELDS 里全部字段的 dict（缺省值 None）。
    读不到 / 格式坏 → 返回空 dict（bot 走默认行为）。"""
    try:
        raw = json.loads(ORDERS_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {k: raw.get(k) for k in (*_FIELDS, *_META_FIELDS)}


def publish_state(state: dict) -> None:
    """原子发布 state.json（先写 .tmp 再 replace，避免参谋长读到半截）。

    STEER_RECORD 设了目录时,额外把快照按 time 存一份(fixture 录制,见 _RECORD_DIR)。
    """
    STEER_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(state, ensure_ascii=False, indent=2)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(payload)
    tmp.replace(STATE_FILE)
    if _RECORD_DIR:
        _record_snapshot(state, payload)


def _record_snapshot(state: dict, payload: str) -> None:
    """把一帧 state 存进 STEER_RECORD 目录(state_<time>.json)。录制失败不影响 bot。"""
    try:
        rec = Path(_RECORD_DIR)
        rec.mkdir(parents=True, exist_ok=True)
        t = state.get("time", 0)
        (rec / f"state_{float(t):08.1f}.json").write_text(payload)
    except Exception:
        pass  # 录制是旁路,坏了也别拖垮 bot


def reset() -> None:
    """开局清掉上一局残留的命令 / 战况。"""
    for f in (ORDERS_FILE, STATE_FILE):
        try:
            f.unlink()
        except FileNotFoundError:
            pass
