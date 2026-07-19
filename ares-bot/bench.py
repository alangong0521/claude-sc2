#!/usr/bin/env python3
"""自调优验证台 runner —— 串行打 N 局 + 聚合 W/L 与军力曲线。

见 docs/bot-self-tuning-plan.md Phase A。每局 = 子进程 `poetry run python run.py`
(env 注入 BUILD/MAP/DIFF/OPPONENT_RACE/AI_BUILD/REALTIME/STEER_RECORD/BENCH_DIR;
**剥掉全部代理 env** —— 本机代理会让 SC2 本地 websocket 连不上,见 README 平台说明)。
结果信号来自 bot on_end 写的 game_*.json;没有结果文件 = 崩溃/超时 → 重试一次,
仍失败记 error(不计入胜率,单独报数)。曲线来自 STEER_RECORD 的 state_*.json 快照。

串行 + 重试是刻意的:CLAUDE.md 记录本环境 headless 不稳(websocket 超时),不并行。

用法(在 ares-bot/ 下):
  poetry run python bench.py --flow tempest --diff Hard --race Terran \
      --map AbyssalReefLE -n 10 --tag tempest-hard-terran
  # 冒烟 1 局: poetry run python bench.py -n 1 --diff Medium --tag smoke
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

_AREAS = Path(__file__).resolve().parent  # ares-bot/

# 本机 .zshrc 导出的代理会毒化 SC2 本地连接,子进程环境必须全剥(大小写都剥)
_PROXY_KEYS = (
    "HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY",
    "http_proxy", "https_proxy", "all_proxy",
)

# 随机 1v1 地图池(--map random):从 SC2 Maps 目录取,排除已知的 >2 人图
_MAPS_DIR = Path("/Applications/StarCraft II/Maps")
_MAP_EXCLUDE = {"CactusValleyLE"}  # 4 人图

# SC2 画质文件(SC2 退出时会重写它,必须每局开局前重设才不回退,Q5)
_VARS_TXT = (
    Path.home()
    / "Library/Application Support/Blizzard/StarCraft II/Variables.txt"
)


def _apply_graphics_settings() -> None:
    """每局开局前重写 SC2 画质(720P 窗口 + 全低)。文件不存在/写不动就静默跳过。"""
    import re
    try:
        text = (
            _VARS_TXT.read_text(encoding="utf-8", errors="ignore")
            if _VARS_TXT.exists() else ""
        )
        text = re.sub(r"(?m)^width=.*$", "width=1280", text)
        if re.search(r"(?m)^height=", text):
            text = re.sub(r"(?m)^height=.*$", "height=720", text)
        else:
            text += "\nheight=720\n"
        text = re.sub(r"(?m)^(GraphicsOption[A-Za-z]+)=[2-5]", r"\g<1>=1", text)
        _VARS_TXT.write_text(text, encoding="utf-8")
    except OSError:
        pass


def _hide_sc2_windows() -> None:
    """把所有 SC2 进程窗口强制退出全屏并隐藏(并行多实例)。
    macOS 会记住 App 上次的全屏状态并在下次启动时恢复——所以每局都要显式
    AXFullScreen=false,不能只"不设 true"(Q:窗口模式)。隐藏后后台对局不弹窗;
    司令想看时点 Dock 图标即可,只看不动不污染对局。"""
    subprocess.run(
        ["osascript", "-e",
         'tell application "System Events" to repeat with p in '
         '(processes whose name contains "SC2")\n'
         'try\n'
         'set value of attribute "AXFullScreen" of window 1 of p to false\n'
         'end try\n'
         'set visible of p to false\n'
         'end repeat'],
        check=False, capture_output=True,
    )


def _pick_map(requested: str) -> str:
    """--map random → 每局从 1v1 图池随机一张;否则原样返回。"""
    if requested.lower() != "random":
        return requested
    import random
    pool = [
        p.stem for p in _MAPS_DIR.glob("*.SC2Map")
        if p.stem not in _MAP_EXCLUDE
    ]
    return random.choice(pool) if pool else "AbyssalReefLE"


def _game_env(args: argparse.Namespace, game_dir: Path, map_name: str) -> dict:
    env = dict(os.environ)
    for k in _PROXY_KEYS:
        env.pop(k, None)
    env["NO_PROXY"] = "127.0.0.1,localhost"
    env["no_proxy"] = "127.0.0.1,localhost"
    env.update({
        "BUILD": args.flow,
        "MAP": map_name,
        "DIFF": args.diff,
        "OPPONENT_RACE": args.race,
        "AI_BUILD": args.ai_build,
        "OPPONENTS": "1",
        "REALTIME": "1" if args.realtime else "0",
        "STEER_RECORD": str(game_dir),   # 军力曲线(state_<time>.json)
        "BENCH_DIR": str(game_dir),      # on_end 结果 JSON(game_<uuid>.json)
        "SAVE_REPLAY": "1" if args.replay else "0",  # 每局存回放(双击可看全战况)
    })
    return env


def _read_result(game_dir: Path) -> dict | None:
    """读 bot on_end 写的最新一个结果 JSON;没有 → None(崩溃/超时)。"""
    results = list(game_dir.glob("game_*.json"))
    if not results:
        return None
    latest = max(results, key=lambda p: p.stat().st_mtime)
    try:
        return json.loads(latest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def _play_one(i: int, args: argparse.Namespace, series_dir: Path) -> dict | None:
    """打第 i 局,返回结果 dict;无结果 → None。--map random 时每局重抽图。
    开局 ~75s 后把 SC2 窗口激活一次(macOS 后台拉起的窗口默认不聚焦,
    司令点小地图前不用再手动点窗口,Q1)。"""
    game_dir = series_dir / f"game_{i:02d}"
    game_dir.mkdir(parents=True, exist_ok=True)
    map_name = _pick_map(args.map)
    (game_dir / "map.txt").write_text(map_name, encoding="utf-8")
    log_path = game_dir / "run.log"
    with log_path.open("w", encoding="utf-8") as logf:
        _apply_graphics_settings()  # Q5:开局前重设 720P+全低(SC2 退出会回写)
        proc = subprocess.Popen(
            ["poetry", "run", "python", "run.py"],
            cwd=_AREAS,
            env=_game_env(args, game_dir, map_name),
            stdout=logf,
            stderr=subprocess.STDOUT,
        )
        # SC2 窗口一出现就藏(闪屏压到 ~2s);藏过一次就停手——
        # 之后司令若点 Dock 主动观察,不再替他藏(Q3)
        t0 = time.time()
        hidden = False
        while proc.poll() is None:
            if not hidden and subprocess.run(
                ["pgrep", "-x", "SC2"], capture_output=True
            ).returncode == 0:
                _hide_sc2_windows()
                hidden = True
            if time.time() - t0 > args.timeout:
                proc.kill()
                raise subprocess.TimeoutExpired(proc.args, args.timeout)
            time.sleep(2)
    if args.replay:
        # run.py 把回放写到 ares-bot/replays/(固定文件名,每局覆盖) → 挪进本局目录
        replays = sorted(
            (_AREAS / "replays").glob("*.SC2Replay"),
            key=lambda p: p.stat().st_mtime,
        )
        if replays:
            replays[-1].replace(game_dir / f"replay_{i:02d}.SC2Replay")
    return _read_result(game_dir)


def _curve_stats(game_dir: Path) -> dict:
    """从 STEER_RECORD 快照抽曲线指标:存款峰值 + 各兵种首次出现时间。"""
    max_minerals = 0
    first_seen: dict[str, float] = {}
    for sp in sorted(game_dir.glob("state_*.json")):
        try:
            s = json.loads(sp.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        max_minerals = max(max_minerals, s.get("minerals", 0))
        t = s.get("time", 0)
        for unit, cnt in (s.get("army") or {}).items():
            if cnt and unit not in first_seen:
                first_seen[unit] = t
    return {"max_minerals": max_minerals, "unit_first_seen": first_seen}


def _postmortem(game_dir: Path, res: dict) -> list[str]:
    """单局自动复盘:从快照找「这局哪里做得不好」的启发式信号(供迭代回溯)。
    每条 = 问题标签 + 关键数据;不求全,专抓迭代里真踩过的坑(停产/花不出去/
    碎兵/卡人口/单矿/被碾压)。"""
    snaps = []
    for sp in sorted(game_dir.glob("state_*.json")):
        try:
            snaps.append(json.loads(sp.read_text(encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            continue
    if not snaps:
        return ["no_snapshots(无曲线可复盘)"]
    issues: list[str] = []

    # 停产:army=0 且存款≥800 持续 ≥60s(C1/B2 根因的探测器)
    stall_t = sum(
        b["time"] - a["time"] for a, b in zip(snaps, snaps[1:])
        if sum(a["army"].values()) == 0 and a["minerals"] >= 800
    )
    if stall_t >= 60:
        issues.append(f"stall(停产 {stall_t:.0f}s)")

    # 花不出去:存款峰值 ≥2000
    max_min = max(s["minerals"] for s in snaps)
    if max_min >= 2000:
        issues.append(f"bank(存款峰值 {max_min})")

    # 碎兵:相邻快照兵力跌 ≥5 出现 ≥3 次(分批送死)
    drops = sum(
        1 for a, b in zip(snaps, snaps[1:])
        if sum(a["army"].values()) - sum(b["army"].values()) >= 5
    )
    if drops >= 3:
        issues.append(f"trickle(兵力反复崩落 {drops} 次)")

    # 卡人口:used>=cap 持续 ≥60s
    def _blocked(s) -> bool:
        try:
            used, cap = s["supply"].split("/")
            return int(used) >= int(cap) > 0
        except (ValueError, AttributeError):
            return False
    block_t = sum(
        b["time"] - a["time"] for a, b in zip(snaps, snaps[1:]) if _blocked(a)
    )
    if block_t >= 60:
        issues.append(f"supply_block(卡人口 {block_t:.0f}s)")

    # 单矿过久(地面流重点;天空流可忽略)
    t300 = [s for s in snaps if s["time"] >= 300]
    if t300 and t300[0]["bases"] == 1:
        issues.append("one_base(300s 仍单矿)")

    # 被碾压:败局且终局敌可见兵力 ≫ 我方
    if res.get("result") == "Defeat":
        last = snaps[-1]
        enemy = sum(last["enemies"][0]["visible"]["army"].values())
        own = sum(last["army"].values())
        if enemy >= max(2 * own, own + 10):
            issues.append(f"overrun(终局兵力悬殊 敌{enemy} vs 我{own})")
    return issues or ["clean(未检出明显问题)"]


def _aggregate(games: list[dict], series_dir: Path, args: argparse.Namespace) -> dict:
    played = [g for g in games if g.get("result")]
    wins = sum(1 for g in played if g["result"] == "Victory")
    losses = sum(1 for g in played if g["result"] == "Defeat")
    ties = sum(1 for g in played if g["result"] == "Tie")
    errors = len(games) - len(played)
    times = sorted(g["game_time"] for g in played if g.get("game_time"))

    curves = [
        _curve_stats(series_dir / f"game_{i:02d}")
        for i in range(1, len(games) + 1)
    ]
    max_bank = max((c["max_minerals"] for c in curves), default=0)
    # 兵种首次出现:只统计出现过的局,取均值
    first_seen_avg: dict[str, float] = {}
    seen_units = {u for c in curves for u in c["unit_first_seen"]}
    for u in seen_units:
        ts = [c["unit_first_seen"][u] for c in curves if u in c["unit_first_seen"]]
        first_seen_avg[u] = round(sum(ts) / len(ts), 1)
    final_army_avg: dict[str, float] = {}
    for g in played:
        for u, cnt in (g.get("army") or {}).items():
            final_army_avg.setdefault(u, []).append(cnt)
    final_army_avg = {
        u: round(sum(v) / len(v), 1) for u, v in final_army_avg.items()
    }

    return {
        "tag": args.tag,
        "config": {
            "flow": args.flow, "map": args.map, "diff": args.diff,
            "race": args.race, "ai_build": args.ai_build,
            "realtime": bool(args.realtime),
        },
        "games": len(games), "wins": wins, "losses": losses,
        "ties": ties, "errors": errors,
        "winrate": round(wins / len(played), 3) if played else None,
        "avg_game_time": round(sum(times) / len(times), 1) if times else None,
        "median_game_time": times[len(times) // 2] if times else None,
        "max_bank": max_bank,
        "unit_first_seen_avg": first_seen_avg,
        "final_army_avg": final_army_avg,
    }


def _print_table(s: dict) -> None:
    c = s["config"]
    print("\n========== series 汇总 ==========")
    print(f"tag={s['tag']}  {c['flow']} vs {c['race']} {c['diff']}/{c['ai_build']} @ {c['map']}")
    print(f"战绩: {s['wins']}胜 {s['losses']}负 {s['ties']}平 {s['errors']}异常 "
          f"→ 胜率 {s['winrate']}")
    print(f"时长: 平均 {s['avg_game_time']}s 中位 {s['median_game_time']}s "
          f"存款峰值 {s['max_bank']}")
    if s["unit_first_seen_avg"]:
        fs = " ".join(f"{u}@{t}s" for u, t in
                      sorted(s["unit_first_seen_avg"].items(), key=lambda kv: kv[1]))
        print(f"主力成型(首次出现均值): {fs}")
    if s["final_army_avg"]:
        fa = " ".join(f"{u}x{n}" for u, n in s["final_army_avg"].items())
        print(f"终局编成(均值): {fa}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--flow", default="tempest", help="flows.yml 流派名")
    ap.add_argument("--diff", default="Hard", help="Difficulty 名(如 Hard)")
    ap.add_argument("--race", default="Terran", help="对手种族(Terran/Zerg/Protoss)")
    ap.add_argument("--map", default="AbyssalReefLE", help="地图名(不带 .SC2Map)")
    ap.add_argument("--ai-build", default="Macro", help="AI_BUILD(RandomBuild/Rush/...)")
    ap.add_argument("-n", type=int, default=10, help="局数")
    ap.add_argument("--tag", required=True, help="系列名(bench/<tag>/ 目录)")
    ap.add_argument("--realtime", action="store_true",
                    help="REALTIME=True 跑(慢,可观战/排查 headless 不稳时用)")
    ap.add_argument("--replay", action="store_true",
                    help="每局存回放(SAVE_REPLAY,双击 .SC2Replay 看完整战况)")
    ap.add_argument("--timeout", type=int, default=1800, help="单局超时秒数")
    args = ap.parse_args()

    series_dir = _AREAS / "bench" / args.tag
    series_dir.mkdir(parents=True, exist_ok=True)

    games: list[dict] = []
    for i in range(1, args.n + 1):
        t0 = time.time()
        try:
            res = _play_one(i, args, series_dir)
        except subprocess.TimeoutExpired:
            res = None
        if res is None:
            print(f"[bench] 第 {i} 局无结果(崩溃/超时),重试一次", flush=True)
            try:
                res = _play_one(i, args, series_dir)
            except subprocess.TimeoutExpired:
                res = None
        if res is None:
            res = {"result": None, "error": "no result json after retry"}
        games.append(res)
        print(f"[bench] 第 {i}/{args.n} 局: {res.get('result') or 'ERROR'} "
              f"({time.time() - t0:.0f}s)", flush=True)

    summary = _aggregate(games, series_dir, args)

    # 单局自动复盘(Q2/Q4:每局找「做得不好的地方」,落 retro.md 供回溯)
    from collections import Counter
    issue_counts: Counter = Counter()
    retro = [f"# {args.tag} 复盘\n"]
    for i, res in enumerate(games, 1):
        result = res.get("result") or "ERROR"
        issues = [] if res.get("result") is None else _postmortem(
            series_dir / f"game_{i:02d}", res
        )
        retro.append(f"- game_{i:02d} {result}: "
                     + ("; ".join(issues) if issues else "-"))
        for tag in issues:
            issue_counts[tag.split("(")[0]] += 1
    retro.append("\n## 问题频次\n")
    for tag, n in issue_counts.most_common():
        retro.append(f"- {tag} × {n}")
    (series_dir / "retro.md").write_text(
        "\n".join(retro) + "\n", encoding="utf-8"
    )
    summary["issue_counts"] = dict(issue_counts)

    (series_dir / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _print_table(summary)
    if issue_counts:
        print("复盘问题: " + " ".join(
            f"{t}×{n}" for t, n in issue_counts.most_common()))
    # 有异常局返回 1(便于外部脚本感知),否则 0;胜负不影响返回码
    return 1 if summary["errors"] else 0


if __name__ == "__main__":
    sys.exit(main())
