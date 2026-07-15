#!/usr/bin/env python3
"""参谋长 CLI —— 看战况 / 给 bot 下命令。词表复用 bot/steer_vocab.py(纯字符串,不起游戏)。

用法（在 ares-bot/ 下跑，bot 必须正在运行）：
  python steer_cli.py state                              看战况（bot 每 ~4 游戏秒刷新）
  python steer_cli.py set stance=attack target=enemy_natural note="压二矿"
  python steer_cli.py set stance=hold                    龟一会儿
  python steer_cli.py set stance=defend                  全军回防
  python steer_cli.py show                               看当前生效的命令
  python steer_cli.py clear                              清命令，回 bot 默认行为
  python steer_cli.py vocab                              可用词
  python steer_cli.py validate                           校验当前 orders.json(只读不写)
  python steer_cli.py set --dry-run stance=bogus         只校验不写盘(离线可跑,无需 bot)

命令是粘性的：写了就一直生效，直到改它或 clear。set 时会校验 key/value 合法性，
不合法直接报错不写盘(避免 LLM 下了静默失败的命令)。
"""
import json
import os
import sys
from pathlib import Path

from bot.steer_vocab import (
    BUILDABLE, BUILD_ALIASES, ENEMY_SLOTS, EXPAND, FOCUS, HARASS, MANEUVERS,
    STANCES, TARGETS, TRIGGERS, canonical_build, validate_order,
)

STEER_DIR = Path(os.environ.get("STEER_DIR", Path.home() / "agent-rts-steer"))
ORDERS_FILE = STEER_DIR / "orders.json"
STATE_FILE = STEER_DIR / "state.json"


def _load(f: Path) -> dict:
    try:
        return json.loads(f.read_text())
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def _save(order: dict) -> None:
    STEER_DIR.mkdir(parents=True, exist_ok=True)
    ORDERS_FILE.write_text(json.dumps(order, ensure_ascii=False, indent=2))


def cmd_state() -> None:
    s = _load(STATE_FILE)
    if not s:
        print("(还没有战况——bot 在跑吗？state.json 不存在)")
        return
    print(json.dumps(s, ensure_ascii=False, indent=2))


def cmd_show() -> None:
    o = _load(ORDERS_FILE)
    print(json.dumps(o, ensure_ascii=False, indent=2) if o else "(当前无命令，bot 走默认行为)")


def cmd_set(args: list, dry_run: bool = False) -> None:
    """解析 key=value 列表,校验后合并进现有 orders.json。
    dry_run=True 只校验不写盘(离线测试用)。任一非法 → 不写盘、报错退出。"""
    order = _load(ORDERS_FILE)
    pending: dict = {}
    parse_errs: list[str] = []
    for a in args:
        if a in ("--dry-run", "-n"):
            dry_run = True
            continue
        if "=" not in a:
            parse_errs.append(f"跳过 '{a}'（要 key=value 形式）")
            continue
        k, v = a.split("=", 1)
        pending[k] = v

    # 合并后再整份校验(能抓出"以前写进盘的脏值 + 新值"叠加的问题)
    merged = dict(order)
    merged.update(pending)
    errs = validate_order(merged)
    if errs:
        print("⛔ 校验失败,未写盘:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(2)
    if parse_errs:
        for e in parse_errs:
            print(f"  - {e}")

    if dry_run:
        print(f"(dry-run) 校验通过,将写入: {json.dumps(merged, ensure_ascii=False)}")
        return

    order.update(pending)
    _save(order)
    print("已下令:", json.dumps(order, ensure_ascii=False))


def cmd_clear() -> None:
    try:
        ORDERS_FILE.unlink()
    except FileNotFoundError:
        pass
    print("已清空命令，bot 回默认行为")


def cmd_validate() -> None:
    """只读校验当前 orders.json,不写盘。离线可用。"""
    o = _load(ORDERS_FILE)
    if not o:
        print("(当前无命令,无需校验)")
        return
    errs = validate_order(o)
    if errs:
        print("⛔ orders.json 有非法值:")
        for e in errs:
            print(f"  - {e}")
        sys.exit(2)
    print(f"✅ 校验通过: {json.dumps(o, ensure_ascii=False)}")


def cmd_vocab() -> None:
    print("stance   (①姿态):  ", " ".join(STANCES))
    print("target   (②目标):  ", " ".join(TARGETS))
    print("focus    (③焦点):  ", " ".join(FOCUS), "<兵种名 如 SIEGETANK>")
    print("maneuver (④机动):  ", " ".join(MANEUVERS))
    print("harass   (⑤持续):  ", " ".join(HARASS), "(oracle 骚扰开关)")
    print("trigger  (⑥择时):  ", " ".join(TRIGGERS))
    print("expand   (运营):   ", " ".join(EXPAND), "(开分矿 = build=nexus 的别名)")
    # build: 规范名 + 别名一起列,让 LLM 知道能写 gas=assimilator 这类
    aliases = [k for k in BUILD_ALIASES if k not in BUILDABLE]
    print("build    (运营):   ", " ".join(BUILDABLE))
    print("            别名:   ", " ".join(sorted(aliases)),
          "(也可写任意引擎结构名,bot 运行时判断可否建造)")
    print("scout    (侦查):   ", "on off", "(派一个农民探路，看完自己回家)")
    print("enemy    (焦点):   ", " ".join(ENEMY_SLOTS), "(多人混战选打哪家；默认 E1 最近)")
    print("note     (备注):   ", "<自由文本>", "(只给人看，不影响 bot 行为)")
    print()
    print("校验: set 时自动校验 key/value; validate 只读校验当前 orders.json;"
          "set --dry-run 只校验不写盘。")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    if cmd == "set":
        cmd_set(rest, dry_run="--dry-run" in rest or "-n" in rest)
    elif cmd == "state":
        cmd_state()
    elif cmd == "show":
        cmd_show()
    elif cmd == "clear":
        cmd_clear()
    elif cmd == "vocab":
        cmd_vocab()
    elif cmd == "validate":
        cmd_validate()
    else:
        print(__doc__)


if __name__ == "__main__":
    main()