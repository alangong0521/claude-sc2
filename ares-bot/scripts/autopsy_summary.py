#!/usr/bin/env python3
"""生成单局 carrier vs VH 的尸检摘要。"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from collections import defaultdict


def main(game_dir: str) -> None:
    d = Path(game_dir)
    states = sorted(d.glob("state_*.json"), key=lambda x: float(x.stem.split("_")[1]))
    if not states:
        print("no states")
        return

    game_json = list(d.glob("game_*.json"))
    result = json.loads(game_json[0].read_text()) if game_json else {}

    print(f"=== {d.name} 摘要 ===")
    print(f"结果: {result.get('result', 'N/A')}  游戏时间: {result.get('game_time', 'N/A')}")
    print(f"终局: 基地={result.get('bases', 'N/A')} 农民={result.get('workers', 'N/A')} 军队={result.get('army', {})} supply={result.get('supply', 'N/A')}")

    # 关键曲线极值
    minerals = [json.loads(s.read_text()).get("minerals", 0) for s in states]
    gas = [json.loads(s.read_text()).get("vespene", 0) for s in states]
    workers = [json.loads(s.read_text()).get("workers", 0) for s in states]
    bases = [json.loads(s.read_text()).get("bases", 0) for s in states]
    times = [json.loads(s.read_text()).get("time", 0.0) for s in states]

    print(f"\n资源/经济曲线:")
    print(f"  时间范围: {times[0]:.1f}s - {times[-1]:.1f}s")
    print(f"  矿物: min={min(minerals)} max={max(minerals)} final={minerals[-1]}")
    print(f"  气体: min={min(gas)} max={max(gas)} final={gas[-1]}")
    print(f"  农民: min={min(workers)} max={max(workers)} final={workers[-1]}")
    print(f"  基地: max={max(bases)} final={bases[-1]}")

    # 开矿时间
    base_times = defaultdict(list)
    for s in states:
        data = json.loads(s.read_text())
        base_times[data.get("bases", 0)].append(data.get("time", 0.0))
    print(f"\n开矿时间:")
    for b in sorted(base_times.keys()):
        if b >= 1:
            print(f"  {b} 基地: 首次 {min(base_times[b]):.1f}s")

    # 关键事件去重
    seen = set()
    print(f"\n关键事件:")
    for s in states:
        data = json.loads(s.read_text())
        t = data.get("time", 0.0)
        for e in data.get("events", []):
            et = round(e.get("t", t), 1)
            msg = e.get("msg", "")
            key = (et, msg)
            if key in seen:
                continue
            seen.add(key)
            if any(k in msg for k in ["农民停滞", "基地被抄", "敌压境", "新基地建成", "F2:注册防御", "E6:敌退", "idle_builder", "O98", "E10"]):
                print(f"  {et:.1f}s  {msg}")

    # Fleet 曲线
    print(f"\n舰队/塔曲线 (每 ~60s):")
    last_t = -999
    for s in states:
        data = json.loads(s.read_text())
        t = data.get("time", 0.0)
        if t - last_t < 55:
            continue
        last_t = t
        army = data.get("army", {})
        structs = data.get("structures", {})
        fleet = army.get("CARRIER", 0) + army.get("TEMPEST", 0)
        cannons = structs.get("PHOTONCANNON", 0)
        sg = structs.get("STARGATE", 0)
        nexus = structs.get("NEXUS", 0)
        print(f"  {t:.0f}s 矿{data.get('minerals',0):>4} 气{data.get('vespene',0):>4} 农{data.get('workers',0):>2} 基{nexus} 舰队{fleet} 星门{sg} 塔{cannons}")


if __name__ == "__main__":
    main(sys.argv[1])
