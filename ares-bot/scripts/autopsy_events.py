#!/usr/bin/env python3
"""去重打印 game 目录中的事件日志。"""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(game_dir: str) -> None:
    d = Path(game_dir)
    states = sorted(d.glob("state_*.json"), key=lambda x: float(x.stem.split("_")[1]))
    seen = set()
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
            print(f"{et:.1f}\t{msg}")


if __name__ == "__main__":
    main(sys.argv[1])
