#!/usr/bin/env python3
"""从 steer_vocab.py 生成 SKILL.md 的「命令词表」段落 —— 消除手工双份漂移(A1)。

steer_vocab.py 是词表单一真相源;参谋 skill 的词表表格以前靠人手抄同步,加了操纵杆
就容易忘改。本脚本读 steer_vocab,渲染成 markdown 表,写进 SKILL.md 里
`<!-- BEGIN AUTOGEN vocab -->` 和 `<!-- END AUTOGEN vocab -->` 两个标记之间。

跑法(在 ares-bot/ 下):
  python3 gen_skill_vocab.py            # 写回 SKILL.md
  python3 gen_skill_vocab.py --check    # 只检查是否最新(CI 友好,不一致 exit 1)
  python3 gen_skill_vocab.py --stdout    # 打到屏幕看看

纯字符串处理,不起游戏。
"""
from __future__ import annotations

import sys
from pathlib import Path

from bot.steer_vocab import (
    BUILDABLE, BUILD_ALIASES, ENEMY_SLOTS, FIELDS, HARASS, MANEUVERS,
    STANCES, TARGETS, TRIGGERS,
)

SKILL_MD = Path(__file__).resolve().parent.parent / ".claude" / "skills" / "canmou" / "SKILL.md"
BEGIN = "<!-- BEGIN AUTOGEN vocab -->"
END = "<!-- END AUTOGEN vocab -->"


def render() -> str:
    """渲染词表 markdown(表格 + 说明)。改词表结构时只改这里。"""
    aliases = sorted(k for k in BUILD_ALIASES if k not in BUILDABLE)
    rows = [
        ("出击/压上 · 撤 · 守家 · 龟一会儿", f"`stance={' / '.join(STANCES)}`"),
        ("打哪(语义目标,bot 求解坐标)", "`target=" + " / ".join(TARGETS) + "`"),
        ("集火(焦点)", "`focus=weakest / closest / workers / <兵种名如 SIEGETANK>`"),
        ("机动", f"`maneuver={' / '.join(MANEUVERS)}`"),
        ("先知骚扰开关", f"`harass={' / '.join(HARASS)}`"),
        ("择时", f"`trigger={' / '.join(TRIGGERS)}`"),
        ("开分矿(一次性)", "`expand=yes`(= `build=nexus` 别名)"),
        ("造建筑(一次性)", "`build=" + " / ".join(BUILDABLE) + "`  别名: " + " ".join(aliases)),
        ("派农民侦查(一次性)", "`scout=on`(只派一个,看完撤回,死了不补)"),
        ("(多人)焦点敌人", f"`enemy={' / '.join(ENEMY_SLOTS)}`(默认 E1=最近)"),
        ("备注(不影响 bot)", "`note=<自由文本>`"),
    ]
    lines = [
        BEGIN,
        "",
        f"> 本段由 `gen_skill_vocab.py` 从 `bot/steer_vocab.py` 生成(字段全集: "
        f"{' '.join(FIELDS)})。**别手改**,改词表后跑 `python3 gen_skill_vocab.py` 重生成。",
        "",
        "| 司令会说 | 命令 |",
        "|---|---|",
    ]
    for say, cmd in rows:
        lines.append(f"| {say} | {cmd} |")
    lines += [
        "",
        "> **一次性 vs 粘性**:`build`/`expand`/`scout` 是**一次性锁定** —— 造到/派过即停,"
        "**重下同值是 no-op**,想再来必须先 `clear`。其余(stance/target/focus/maneuver/"
        "harass/trigger/enemy)是**粘性**,写了一直生效直到改它或 `clear`。",
        "",
        END,
    ]
    return "\n".join(lines)


def splice(md: str, block: str) -> str:
    """把 block 换进 md 的 BEGIN..END 之间;没有标记则报错(需先在 SKILL.md 埋标记)。"""
    if BEGIN not in md or END not in md:
        raise SystemExit(
            f"SKILL.md 里找不到标记 {BEGIN} / {END} —— 先在词表段落埋上这两行再跑。"
        )
    pre = md[: md.index(BEGIN)]
    post = md[md.index(END) + len(END):]
    return pre + block + post


def main() -> None:
    args = sys.argv[1:]
    block = render()
    if "--stdout" in args:
        print(block)
        return
    md = SKILL_MD.read_text(encoding="utf-8")
    new = splice(md, block)
    if "--check" in args:
        if new != md:
            print("⛔ SKILL.md 词表段落已过期,跑 `python3 gen_skill_vocab.py` 重生成。")
            sys.exit(1)
        print("✅ SKILL.md 词表段落是最新的。")
        return
    if new != md:
        SKILL_MD.write_text(new, encoding="utf-8")
        print(f"✅ 已更新 {SKILL_MD}")
    else:
        print("✅ 无变化,已是最新。")


if __name__ == "__main__":
    main()
