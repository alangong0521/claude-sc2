#!/usr/bin/env python3
"""自调优验证台 runner —— 串行打 N 局 + 聚合 W/L 与军力曲线。

见 docs/bot-self-tuning-plan.md Phase A。每局 = 子进程 `poetry run python run.py`
(env 注入 BUILD/MAP/DIFF/OPPONENT_RACE/AI_BUILD/REALTIME/STEER_RECORD/BENCH_DIR;
**剥掉全部代理 env** —— 本机代理会让 SC2 本地 websocket 连不上,见 README 平台说明)。
结果信号来自 bot on_end 写的 game_*.json;没有结果文件 = 崩溃/超时 → 重试一次,
仍失败记 error(不计入胜率,单独报数)。曲线来自 STEER_RECORD 的 state_*.json 快照。

本 runner 同时支持单车道串行与多实例并行；当前正式验证按 CLAUDE.md 走
headless(REALTIME=False) + 双车道 SC2 并行。串行/重试仅作为双车道临时故障、
headless 不稳或观战排查时的降级，不是默认模式。

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
# 和让 ares PlacementManager 开局即崩的图(HonorgroundsLE:主矿路口摆点 IndexError)
_MAPS_DIR = Path("/Applications/StarCraft II/Maps")
_MAP_EXCLUDE = {"CactusValleyLE", "HonorgroundsLE"}  # 4 人图 / ares 摆点崩溃图

# SC2 画质文件(SC2 退出时会重写它,必须每局开局前重设才不回退,Q5)
_VARS_TXT = (
    Path.home()
    / "Library/Application Support/Blizzard/StarCraft II/Variables.txt"
)


def _cleanup_stale_sc2(max_age_seconds: float = 180.0) -> None:
    """O206:bench 启动前清理卡死/残留的 SC2 进程。

    并行车道场景下不能无差别杀所有 SC2(会误伤刚启动的另一条 lane),所以只杀
    「存活时间 > max_age_seconds」的 SC2。这些通常是之前 bench 中断/卡死后
    没清理干净的残留;正常对局的 SC2 才启动几秒,不会误杀。
    同时清理没有 run.py/python 父进程的孤儿 SC2(崩溃/断链后残留)。
    """
    try:
        out = subprocess.run(
            ["ps", "-axo", "pid,ppid,etime,comm"], capture_output=True, text=True
        ).stdout
    except Exception:
        return
    parents: dict[str, str] = {}
    lines = out.splitlines()[1:]
    for line in lines:
        parts = line.split(None, 3)
        if len(parts) == 4:
            parents[parts[0]] = parts[1]

    def _has_runner_parent(pid: str) -> bool:
        seen = set()
        p = pid
        while p in parents and p not in seen:
            seen.add(p)
            ppid = parents[p]
            try:
                ppid_int = int(ppid)
            except ValueError:
                return False
            if ppid_int <= 1:
                return False
            # 父进程是 run.py 或 python/poetry = 正常有主
            try:
                comm = subprocess.run(
                    ["ps", "-p", ppid, "-o", "comm="],
                    capture_output=True, text=True,
                ).stdout.strip()
            except Exception:
                comm = ""
            if comm in ("python3", "python", "SC2") or "run.py" in comm:
                return True
            p = ppid
        return False

    for line in lines:
        parts = line.split(None, 3)
        if len(parts) != 4:
            continue
        pid, ppid, etime, comm = parts
        if comm != "SC2":
            continue
        # etime 格式: [[dd-]hh:]mm:ss, 先转成总秒数(近似)
        total_sec = 0
        try:
            if "-" in etime:
                days, rest = etime.split("-", 1)
                total_sec += int(days) * 86400
                etime = rest
            chunks = etime.split(":")
            if len(chunks) == 3:
                total_sec += int(chunks[0]) * 3600 + int(chunks[1]) * 60 + int(chunks[2])
            elif len(chunks) == 2:
                total_sec += int(chunks[0]) * 60 + int(chunks[1])
            elif len(chunks) == 1:
                total_sec += int(chunks[0])
        except ValueError:
            continue
        orphan = not _has_runner_parent(pid)
        if total_sec > max_age_seconds or orphan:
            reason = "orphan" if orphan else f"stale {total_sec}s"
            print(f"[bench] cleanup {reason} SC2 pid={pid}", flush=True)
            try:
                os.kill(int(pid), 9)
            except Exception:
                pass


def _kill_orphan_sc2() -> None:
    """O195:单局崩溃/超时后,run.py 已死但 SC2 可能变成孤儿进程(init 为父)。

    双车道场景下不能无差别杀所有 SC2,所以只杀 PPID=1 的孤儿,
    避免残留实例占端口/资源,导致下局启动失败或互相干扰。
    """
    try:
        out = subprocess.run(
            ["ps", "-axo", "pid,ppid,comm"], capture_output=True, text=True
        ).stdout
    except Exception:
        return
    for line in out.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        pid, ppid, comm = parts
        if comm != "SC2" or ppid != "1":
            continue
        try:
            os.kill(int(pid), 9)
        except Exception:
            pass


def _cleanup_blizzard_error(max_age_seconds: float = 60.0) -> None:
    """O196:清理 SC2 崩溃后残留的 Blizzard Error 报告进程。

    该进程(路径含 `Blizzard Error.app`)通常 PPID=1,不占用游戏端口但会
    堆积;bench 启动时杀掉存活超过 max_age_seconds 的,避免崩溃报告器越积越多。
    """
    try:
        out = subprocess.run(
            ["ps", "-axo", "pid,etime,comm"], capture_output=True, text=True
        ).stdout
    except Exception:
        return
    for line in out.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) != 3:
            continue
        pid, etime, comm = parts
        if "Blizzard Error" not in comm:
            continue
        total_sec = 0
        try:
            if "-" in etime:
                days, rest = etime.split("-", 1)
                total_sec += int(days) * 86400
                etime = rest
            chunks = etime.split(":")
            if len(chunks) == 3:
                total_sec += int(chunks[0]) * 3600 + int(chunks[1]) * 60 + int(chunks[2])
            elif len(chunks) == 2:
                total_sec += int(chunks[0]) * 60 + int(chunks[1])
            elif len(chunks) == 1:
                total_sec += int(chunks[0])
        except ValueError:
            continue
        if total_sec > max_age_seconds:
            try:
                os.kill(int(pid), 9)
            except Exception:
                pass


def _reset_game_dir(game_dir: Path) -> None:
    """O195:重试同一局前清理旧快照/结果,避免崩溃/超时局的状态污染 retro。

    保留旧 run.log 为 run.log.1 供排错,删除 state_*.json / game_*.json。
    """
    for p in game_dir.glob("state_*.json"):
        try:
            p.unlink()
        except OSError:
            pass
    for p in game_dir.glob("game_*.json"):
        try:
            p.unlink()
        except OSError:
            pass
    log_path = game_dir / "run.log"
    if log_path.exists():
        try:
            log_path.replace(game_dir / "run.log.1")
        except OSError:
            pass


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
    """把**最新启动的**那个 SC2 进程强制退出全屏并隐藏。
    只藏新开局的一个——别误藏司令正在观察的另一局(并行车道场景)。
    macOS 会记住 App 上次的全屏状态并恢复,所以每局都要显式 AXFullScreen=false。"""
    newest = subprocess.run(
        ["pgrep", "-n", "-x", "SC2"], capture_output=True, text=True
    ).stdout.strip()
    if not newest:
        return
    pid = newest.splitlines()[0]
    subprocess.run(
        ["osascript", "-e",
         f'tell application "System Events"\n'
         f'set p to first process whose unix id is {pid}\n'
         f'try\n'
         f'set value of attribute "AXFullScreen" of window 1 of p to false\n'
         f'end try\n'
         f'set visible of p to false\n'
         f'end tell'],
        check=False, capture_output=True,
    )


def _surrender_detected(game_dir: Path) -> bool:
    """最新快照的 events 里有「敌方打出gg」→ True(bot 侧 gg 检测,main.py)。"""
    snaps = sorted(game_dir.glob("state_*.json"), key=os.path.getmtime)
    if not snaps:
        return False
    try:
        s = json.loads(snaps[-1].read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return any("投降" in e.get("msg", "") for e in s.get("events", []))


def _sc2_pid_for(proc_pid: int) -> str | None:
    """O180:找本局 run.py 进程树下的 SC2 进程(并行车道时别点错窗口)。

    双车道下不能简单 `pgrep -x SC2`——那会拿到另一条 lane 的 SC2,
    导致「对方 SC2 活着 = 我以为自己 SC2 活着」的误判。
    """
    out = subprocess.run(["ps", "-axo", "pid,ppid,comm"],
                         capture_output=True, text=True).stdout
    parent: dict[str, tuple[str, str]] = {}
    for line in out.splitlines()[1:]:
        parts = line.split(None, 2)
        if len(parts) == 3:
            parent[parts[0]] = (parts[1], parts[2])
    for pid, (ppid, comm) in parent.items():
        if not comm.endswith("SC2"):
            continue
        p = ppid
        while p in parent:
            if p == str(proc_pid):
                return pid
            p = parent[p][0]
    return None


def _accept_surrender(sc2_pid: str) -> None:
    """敌打出 gg(=弹了投降确认框):显窗置顶 → 合成点击 Yes(窗口右上 0.745,0.175 处)
    → 再藏回。提前终局,司令要求(Q:gg 后直接判我方胜)。
    注意:必须先显窗——bench 开局会把窗口藏起来,不显示的话点击落在桌面/终端上。"""
    geom = subprocess.run(
        ["osascript", "-e",
         f'tell application "System Events" to tell (first process whose unix id '
         f'is {sc2_pid})\n'
         f'set visible of it to true\n'
         f'set frontmost of it to true\n'
         f'delay 0.3\n'
         f'get {{position, size}} of window 1'],
        capture_output=True, text=True,
    ).stdout
    nums = [float(x) for x in geom.replace("\n", "").split(",") if x.strip()]
    if len(nums) != 4:
        return
    x, y, w, h = nums
    yes = (x + w * 0.745, y + h * 0.175)
    subprocess.run(
        ["osascript", "-e",
         f'tell application "System Events" to click at '
         f'{{{yes[0]:.0f}, {yes[1]:.0f}}}'],
        check=False, capture_output=True,
    )
    subprocess.run(
        ["osascript", "-e",
         f'tell application "System Events" to set visible of '
         f'(first process whose unix id is {sc2_pid}) to false'],
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
    if args.carrier_combat:  # E4 双通道对照:覆盖 CARRIER 的 combat 类
        env["CARRIER_COMBAT"] = args.carrier_combat
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
        # 之后司令若点 Dock 主动观察,不再替他藏(Q3)。
        # 同时每 ~10s 监视敌投降:AI 打出 gg → 帮点"接受投降"提前终局(Q:gg 即判胜)
        t0 = time.time()
        hidden = False
        last_gg_check = 0.0
        last_heartbeat = 0.0
        # O180:SC2 启动/健康检查
        sc2_pid: str | None = None
        startup_deadline = t0 + 60.0
        while proc.poll() is None and sc2_pid is None:
            sc2_pid = _sc2_pid_for(proc.pid)
            if sc2_pid is None:
                if time.time() > startup_deadline:
                    print(f"[bench] game {i:02d} SC2 未在 60s 内启动", flush=True)
                    proc.kill()
                    return None
                time.sleep(0.5)
        if proc.poll() is not None:
            return None
        # 状态快照停滞检测:90s 无新 snapshot → SC2 卡死/websocket 断链
        last_state_count = len(list(game_dir.glob("state_*.json")))
        last_state_time = time.time()
        # O206c:SC2 CPU 冻结检测已禁用,见下方 while 循环注释。
        # O206:游戏内时间冻结检测(snapshot 在写但游戏没推进)
        last_game_time = 0.0
        last_game_time_ts = time.time()
        while proc.poll() is None:
            now = time.time()
            if now - last_heartbeat > 20:
                print(f"[bench] game {i:02d} alive {now - t0:.0f}s", flush=True)
                last_heartbeat = now
            # O180:SC2 进程异常退出(崩溃) → 不再空等 timeout
            if sc2_pid is not None:
                try:
                    os.kill(int(sc2_pid), 0)
                except OSError:
                    print(f"[bench] game {i:02d} SC2 进程异常退出", flush=True)
                    proc.kill()
                    _kill_orphan_sc2()
                    _cleanup_blizzard_error(0)
                    return None
            # O180:状态快照停滞检测
            states = list(game_dir.glob("state_*.json"))
            if len(states) != last_state_count:
                last_state_count = len(states)
                last_state_time = now
            # O206b(o206-vh-zerg-timing 实证):双车道 headless 开局状态写入偶发
            # 抖动,90s 阈值把正常启动局误杀;放宽到 180s,真卡死仍会触发。
            elif now - last_state_time > 180:
                print(
                    f"[bench] game {i:02d} 状态快照停滞 {now - last_state_time:.0f}s,"
                    "判定卡死", flush=True
                )
                proc.kill()
                if sc2_pid is not None:
                    try:
                        os.kill(int(sc2_pid), 9)
                    except OSError:
                        pass
                _kill_orphan_sc2()
                _cleanup_blizzard_error(0)
                return None
            # O206:游戏时间推进检测(读最新 snapshot 的 time 字段)
            latest_snap = max(states, key=os.path.getmtime) if states else None
            if latest_snap is not None:
                try:
                    snap_time = json.loads(
                        latest_snap.read_text(encoding="utf-8")
                    ).get("time", 0.0)
                except (OSError, json.JSONDecodeError):
                    snap_time = last_game_time
                if snap_time > last_game_time + 0.5:
                    last_game_time = snap_time
                    last_game_time_ts = now
                # O206b:同快照停滞,放宽到 150s,避免双车道启动期误判。
                elif now - last_game_time_ts > 150:
                    print(
                        f"[bench] game {i:02d} 游戏时间停滞 {now - last_game_time_ts:.0f}s"
                        f"(time={last_game_time:.1f}),判定卡死", flush=True
                    )
                    proc.kill()
                    if sc2_pid is not None:
                        try:
                            os.kill(int(sc2_pid), 9)
                        except OSError:
                            pass
                    _kill_orphan_sc2()
                    _cleanup_blizzard_error(0)
                    return None
            # O206c:SC2 CPU 冻结检测已禁用。双车道 headless 下 SC2 开局加载期
            # CPU 占用天然抖动,基于 `ps cputime` 的采样连续误杀正常对局。
            # 真卡死由「状态快照停滞 180s」和「游戏时间停滞 150s」兜底捕获。
            if not hidden and subprocess.run(
                ["pgrep", "-x", "SC2"], capture_output=True
            ).returncode == 0:
                _hide_sc2_windows()
                hidden = True
            if now - last_gg_check > 10 and _surrender_detected(game_dir):
                last_gg_check = time.time()
                sc2_pid = _sc2_pid_for(proc.pid) or sc2_pid
                if sc2_pid:
                    print(f"[bench] 敌方打出 gg,帮点接受投降(game {i:02d})", flush=True)
                    _accept_surrender(sc2_pid)
            if now - t0 > args.timeout:
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


def _postmortem(game_dir: Path, res: dict, flow: str = "") -> list[str]:
    """单局自动复盘:从快照找「这局哪里做得不好」的启发式信号(供迭代回溯)。
    每条 = 问题标签 + 关键数据;不求全,专抓迭代里真踩过的坑(停产/花不出去/
    碎兵/卡人口/单矿/被碾压/农民干等建造)。
    flow 用于 flow 感知阈值(one_base:carrier 6 分钟开矿是设计,放宽到 420s)。"""
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

    # 单矿过久(地面流重点;天空流可忽略)。O19:flow 感知阈值 —— carrier
    # 6 分钟开矿是设计(O21),300s 阈值五连误报(E6c2 实证) → carrier 放宽到 420s。
    one_base_thr = 420 if flow == "carrier" else 300
    t_thr = [s for s in snaps if s["time"] >= one_base_thr]
    if t_thr and t_thr[0]["bases"] == 1:
        issues.append(f"one_base({one_base_thr}s 仍单矿)")

    # 农民干等建造(O19 司令章程:>1s 不干活干等建造要曝光)——bot 局中发
    # idle_builder 事件(main._detect_idle_builders),这里按 (t,msg) 去重计数
    idle_builders = {
        (e.get("t"), e.get("msg", ""))
        for s in snaps
        for e in s.get("events", [])
        if "idle_builder" in e.get("msg", "")
    }
    if idle_builders:
        issues.append(f"idle_builder(农民干等建造 ×{len(idle_builders)})")

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
            "carrier_combat": args.carrier_combat or "yml",
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
    # O159/O175: 旧结论认为本机 SC2 客户端不支持多开,用文件锁强制串行。
    # 2026-08-04 实证推翻:两个 bench.py 实例各带独立 SC2 进程可并行 100s+ 无互踢
    # (互踢只发生在同一 install 直启二进制抢默认端口;bench 走独立端口分配)。
    # 因此移除文件锁,允许司令要求的双车道后台验证。

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
    ap.add_argument("--carrier-combat", default=None,
                    choices=["default", "carrier_offensive"],
                    help="覆盖 CARRIER 的 combat 类(E4 双通道对照);不设用 yml 原值")
    ap.add_argument("--retro-only", action="store_true",
                    help="不打局:只对 bench/<tag>/ 已有快照重跑 retro/汇总"
                    "(O19:离线复验检测器/阈值改动,不重开 bench)")
    args = ap.parse_args()

    series_dir = _AREAS / "bench" / args.tag
    series_dir.mkdir(parents=True, exist_ok=True)

    # O180:bench 启动时清理残留 SC2,避免之前中断/卡死的进程占端口/资源,
    # 导致新实例启动崩溃(Blizzard Error Report)。
    _cleanup_stale_sc2()
    # O196/O208:顺手清理 SC2 崩溃留下的 Blizzard Error 报告孤儿进程。
    # 启动时立即杀掉全部(含刚弹出的),避免双车道启动时第二个 SC2 实例的
    # 崩溃报告器占用许可/资源导致连锁失败。
    _cleanup_blizzard_error(0)

    if args.retro_only:
        game_dirs = sorted(p for p in series_dir.glob("game_*") if p.is_dir())
        games: list[dict] = [
            _read_result(d) or {"result": None, "error": "no result json"}
            for d in game_dirs
        ]
        print(f"[bench] retro-only: 复用 {len(games)} 局已有快照,不重开游戏")
    else:
        games = []
        for i in range(1, args.n + 1):
            # O207:每局开始前清掉上一局残留的 Blizzard Error 报告进程，
            # 避免崩溃报告器堆积/占资源/挡输入。
            _cleanup_blizzard_error(0)
            t0 = time.time()
            try:
                res = _play_one(i, args, series_dir)
            except subprocess.TimeoutExpired:
                res = None
            if res is None:
                print(f"[bench] 第 {i} 局无结果(崩溃/超时),重试一次", flush=True)
                _kill_orphan_sc2()
                _cleanup_blizzard_error(0)
                _reset_game_dir(series_dir / f"game_{i:02d}")
                try:
                    res = _play_one(i, args, series_dir)
                except subprocess.TimeoutExpired:
                    _kill_orphan_sc2()
                    _cleanup_blizzard_error(0)
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
            series_dir / f"game_{i:02d}", res, args.flow
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
