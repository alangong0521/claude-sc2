#!/usr/bin/env python3
"""难度档位晋升 runner —— 流派打穿「全种族 × 全风格」矩阵才晋级下一档(Q1 司令定)。

见 docs/bot-self-tuning-plan.md §6。矩阵 = 3 族 × 5 风格 = 15 组合
(RandomBuild 是元风格,引入额外方差,不计入)。
组合 = best-of-N(默认 3,≥2 胜通过),**逐局打、提前锁定**(司令规约):
连胜 pass_mark 局立即跳过后续局;输到数学上不可能过也提前停。
未过组合加打一轮(再 N 局,两轮合计 ≥N 胜通过);仍不过 → 标「疑似相克」记录在案、
不拦晋级(留给司令复核);一轮矩阵失败组合 >2 个 = 整体打不穿,停在该档。

档位阶梯(python-sc2 Difficulty,无 Elite):
  Medium → MediumHard → Hard → Harder → VeryHard → CheatVision → CheatMoney → CheatInsane

断点续跑:每局一个 tag(bench/<tag>/summary.json),已打的局直接读结果不重打;
流派当前档位与晋级史存 bench/promotion.json。

用法(在 ares-bot/ 下):
  poetry run python promotion.py --flow tempest --start MediumHard
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path

_AREAS = Path(__file__).resolve().parent

LADDER = [
    "Medium", "MediumHard", "Hard", "Harder", "VeryHard",
    "CheatVision", "CheatMoney", "CheatInsane",
]
RACES = ["Terran", "Zerg", "Protoss"]
BUILDS = ["Rush", "Timing", "Power", "Macro", "Air"]  # RandomBuild 除外(元风格)
STATE_FILE = _AREAS / "bench" / "promotion.json"
# 一轮矩阵里失败(且重打仍不过)的组合超过这个数 = 整体打不穿,停档不晋级
_MAX_COUNTERS_PER_TIER = 2


def _tag(flow: str, diff: str, race: str, build: str, suffix: str = "") -> str:
    return (f"promo-{flow}-{diff.lower()}-{race.lower()}-{build.lower()}{suffix}")


def _series_result(tag: str) -> tuple[int, int] | None:
    """读 bench/<tag>/summary.json → (wins, games);没有 → None。"""
    f = _AREAS / "bench" / tag / "summary.json"
    if not f.exists():
        return None
    try:
        s = json.loads(f.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    return s["wins"], s["games"]


def _run_series(args: argparse.Namespace, diff: str, race: str, build: str,
                tag: str, n: int) -> tuple[int, int]:
    print(f"[promo] 打 {tag} ...", flush=True)
    subprocess.run(
        ["poetry", "run", "python", "bench.py",
         "--flow", args.flow, "--diff", diff, "--race", race,
         "--ai-build", build, "--map", args.map,
         "-n", str(n), "--tag", tag],
        cwd=_AREAS, check=False,
    )
    return _series_result(tag) or (0, 0)


def _purge_game_logs(tag_base: str, max_games: int) -> int:
    """删一个组合的局内原始日志(game_XX/ 快照+run.log),留 summary.json/retro.md。
    司令规约:2-0/3-0 速通组合、重打通过的组合 → 删日志省磁盘。
    返回删掉的目录数。"""
    purged = 0
    for suffix in ("", "-r2"):
        for g in range(1, max_games + 1):
            series = _AREAS / "bench" / f"{tag_base}{suffix}-g{g}"
            if not series.is_dir():
                continue
            for game_dir in series.glob("game_*"):
                if game_dir.is_dir():
                    shutil.rmtree(game_dir, ignore_errors=True)
                    purged += 1
    return purged


def _analyze_failures(flow: str, diff: str, race: str, build: str,
                      tag_base: str, max_games: int) -> Path:
    """组合失败时果断归因:聚合各局 retro 的复盘信号 + 败局关键数据,
    落 bench/<tag_base>-analysis.md 供迭代回溯(司令规约:2 负即分析再复测)。"""
    issues: Counter = Counter()
    losses: list[str] = []
    banks: list[int] = []
    for suffix in ("", "-r2"):
        for g in range(1, max_games + 1):
            series = _AREAS / "bench" / f"{tag_base}{suffix}-g{g}"
            s = _series_result(f"{tag_base}{suffix}-g{g}")
            if s is None:
                continue
            try:
                sj = json.loads((series / "summary.json").read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            for tag, n in sj.get("issue_counts", {}).items():
                if tag != "clean":
                    issues[tag] += n
            if sj.get("losses"):
                losses.append(
                    f"game {series.name}: {sj.get('avg_game_time', 0):.0f}s, "
                    f"存款峰值 {sj.get('max_bank', '?')}, "
                    f"终局兵力 {sj.get('final_army_avg', {})}"
                )
                banks.append(sj.get("max_bank", 0))
    lines = [
        f"# {flow} @ {diff} {race}/{build} 失败归因",
        "",
        "## 复盘信号频次(非 clean)",
    ]
    lines += [f"- {t} × {n}" for t, n in issues.most_common()] or ["- (无)"]
    lines += ["", "## 败局明细"] + [f"- {x}" for x in losses or ["(无)"]]
    if banks and max(banks) >= 800:
        lines += ["", f"⚠️ 存款峰值 {max(banks)} ≥800:经济没转化为兵力(司令规约 3)"]
    out = _AREAS / "bench" / f"{tag_base}-analysis.md"
    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"[promo] {race}/{build} 失败归因 → {out.name}: "
          + (" ".join(f"{t}×{n}" for t, n in issues.most_common()) or "无信号"),
          flush=True)
    return out


def _play_combo(args: argparse.Namespace, diff: str, race: str, build: str,
                tag_base: str, pass_mark: int) -> tuple[int, int]:
    """打一个组合(best-of-N,逐局):已打的局跳过;连胜 pass_mark 局提前锁定,
    输到数学上不可能过也提前停(司令:连胜跳过第3局,有输才打满)。"""
    wins = games = 0
    for g in range(1, args.n + 1):
        tag = f"{tag_base}-g{g}"
        got = _series_result(tag)
        if got is None or got[1] < 1:
            got = _run_series(args, diff, race, build, tag, n=1)
        wins += got[0]
        games += 1
        if wins >= pass_mark:
            print(f"[promo] {race}/{build} {wins}-{games - wins} 提前锁定", flush=True)
            break
        if games - wins >= (args.n - pass_mark + 1):
            print(f"[promo] {race}/{build} {wins}-{games - wins} 提前出局", flush=True)
            break
    return wins, games


def _load_state(path: Path = STATE_FILE) -> dict:
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def _save_state(state: dict, path: Path = STATE_FILE) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flow", required=True, help="flows.yml 流派名")
    ap.add_argument("--start", default="MediumHard", help="起始档位(默认 MediumHard)")
    ap.add_argument("-n", type=int, default=3, help="每组合局数(默认 3,≥2 胜通过)")
    ap.add_argument("--map", default="random", help="地图(默认 random 每局随机 1v1)")
    ap.add_argument("--state", default=str(STATE_FILE),
                    help="状态文件(默认 bench/promotion.json;多车道并行时各用各的)")
    ap.add_argument("--races", default=",".join(RACES),
                    help="逗号分隔的种族子集(默认全选,如 Terran,Zerg)")
    ap.add_argument("--builds", default=",".join(BUILDS),
                    help="逗号分隔的风格子集(默认全选,如 Rush,Macro)")
    args = ap.parse_args()

    pass_mark = args.n // 2 + 1  # 3→2 胜, 5→3 胜
    state_path = Path(args.state)
    races = [r for r in RACES if r in args.races.split(",")]
    builds = [b for b in BUILDS if b in args.builds.split(",")]
    n_combos = len(races) * len(builds)

    state = _load_state(state_path)
    flow_state = state.setdefault(args.flow, {"tier": args.start, "history": {}})
    tier = flow_state.get("tier", args.start)
    if tier not in LADDER:
        print(f"[promo] 未知档位 {tier},回退 {args.start}")
        tier = args.start

    idx = LADDER.index(tier)
    while idx < len(LADDER):
        diff = LADDER[idx]
        print(f"\n===== {args.flow} @ {diff} 矩阵({n_combos} 组合 × ≤{args.n} 局)=====",
              flush=True)
        history = flow_state["history"].setdefault(diff, {})
        failed: list[tuple[str, str]] = []

        for race in races:
            for build in builds:
                tag_base = _tag(args.flow, diff, race, build)
                wins, games = _play_combo(
                    args, diff, race, build, tag_base, pass_mark
                )
                ok = wins >= pass_mark
                history[f"{race}/{build}"] = [wins, games, "pass" if ok else "fail"]
                print(f"[promo] {diff} {race}/{build}: {wins}/{games} "
                      f"{'PASS' if ok else 'FAIL'}", flush=True)
                _save_state(state, state_path)
                if ok:
                    # 司令规约:2-0/3-0 速通 → 直接删局内日志,开下一组合
                    purged = _purge_game_logs(tag_base, args.n)
                    print(f"[promo] {race}/{build} 速通,清理 {purged} 局原始日志",
                          flush=True)
                else:
                    # 司令规约:2 负出局 → 果断分析整局日志再复测
                    _analyze_failures(args.flow, diff, race, build,
                                      tag_base, args.n)
                    failed.append((race, build))

        # 失败组合加打一轮(tag 加 -r2,两轮合计 ≥n 胜通过;仍不过记「疑似相克」)
        counters = []
        for race, build in failed:
            key = f"{race}/{build}"
            tag_base = _tag(args.flow, diff, race, build)
            tag_base2 = _tag(args.flow, diff, race, build, suffix="-r2")
            w2, g2 = _play_combo(args, diff, race, build, tag_base2, pass_mark)
            total_w = history[key][0] + w2
            total_g = history[key][1] + g2
            if total_w >= args.n:
                history[key] = [total_w, total_g, "pass-retry"]
                print(f"[promo] {key} 重打后合计 {total_w}/{total_g} PASS", flush=True)
                # 司令规约:复测通过 → 删日志
                purged = _purge_game_logs(tag_base, args.n)
                print(f"[promo] {key} 复测通过,清理 {purged} 局原始日志", flush=True)
            else:
                history[key] = [total_w, total_g, "counter?"]
                counters.append(key)
                # 仍不过:重归因(含 r2 局),原始日志保留供司令复核
                _analyze_failures(args.flow, diff, race, build,
                                  tag_base, args.n)
                print(f"[promo] {key} 重打后合计 {total_w}/{total_g} → 疑似相克",
                      flush=True)
            _save_state(state, state_path)

        if len(counters) > _MAX_COUNTERS_PER_TIER:
            # 打不过降档(司令指令 4):整档 >2 组合打不穿 → 降一档继续爬(而非退出);
            # 已在最低档才退出。打穿最高档仍按 DONE 退出。
            if idx > 0:
                print(f"\n[promo] {diff} 档 {len(counters)} 个组合打不穿(>{_MAX_COUNTERS_PER_TIER}),"
                      f"降档回 {LADDER[idx - 1]} 蓄力。相克组合: {counters}", flush=True)
                flow_state["tier"] = LADDER[idx - 1]
                _save_state(state, state_path)
                idx -= 1
                continue
            print(f"\n[promo] {diff} 档 {len(counters)} 个组合打不穿(>{_MAX_COUNTERS_PER_TIER}),"
                  f"整体未过,留在 {diff} 继续迭代。相克组合: {counters}", flush=True)
            flow_state["tier"] = diff
            _save_state(state, state_path)
            return 1

        # 晋级(失败 ≤2 个记相克,不拦)
        next_idx = idx + 1
        if counters:
            print(f"\n[promo] {diff} 档通过(相克豁免: {counters})", flush=True)
        else:
            print(f"\n[promo] {diff} 档全穿,晋级!", flush=True)
        if next_idx >= len(LADDER):
            print(f"[promo] {args.flow} 已打穿最高档 CheatInsane,通关!", flush=True)
            flow_state["tier"] = "DONE"
            _save_state(state, state_path)
            return 0
        flow_state["tier"] = LADDER[next_idx]
        _save_state(state, state_path)
        print(f"[promo] 晋级 → {LADDER[next_idx]}\n", flush=True)
        idx = next_idx

    return 0


if __name__ == "__main__":
    sys.exit(main())
