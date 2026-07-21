#!/usr/bin/env python3
"""E1 三臂实验矩阵:carrier vs Zerg VeryHard/Rush @AbyssalReefLE,每臂 N=3。

臂定义(docs/battle-log.md E1,只动 flows.yml 的 carrier.pivot 块):
  A 组合包(现状):   rush_zealots: 4, 无 rush_cannons 行
  B 纯叉子:        rush_zealots: 4 + rush_cannons: false
  C 纯塔憋航母:    rush_zealots: 0

串行跑 bench.py ×3,结束后恢复 flows.yml 原样。结果落 bench/<tag>/summary.json。

用法(在 ares-bot/ 下):  poetry run python e1_matrix.py
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

_AREAS = Path(__file__).resolve().parent
_FLOWS = _AREAS / "flows.yml"

_ARMS = {
    "armA": {"rush_zealots": 4, "rush_cannons": None},   # None = 不写该行
    "armB": {"rush_zealots": 4, "rush_cannons": False},
    "armC": {"rush_zealots": 0, "rush_cannons": None},
}


def _patch_carrier_pivot(text: str, zealots: int, cannons: bool | None) -> str:
    """只改 carrier 块(文件最后一个 flow)的 pivot 字段,其余原样。"""
    head, sep, tail = text.rpartition("\n  carrier:")
    assert sep, "flows.yml 里找不到 carrier 块"
    tail, n = re.subn(r"rush_zealots: \d+", f"rush_zealots: {zealots}", tail)
    assert n == 1, f"carrier 块 rush_zealots 替换次数={n}"
    # 先清掉已有的 rush_cannons 行,再按需补
    tail = re.sub(r"(?m)^\s+rush_cannons: \w+\n", "", tail)
    if cannons is not None:
        tail = re.sub(
            r"(?m)^(\s+rush_zealots: \d+.*)$",
            rf"\g<1>\n      rush_cannons: {str(cannons).lower()}",
            tail,
        )
    return head + sep + tail


def main() -> int:
    original = _FLOWS.read_text(encoding="utf-8")
    results = {}
    try:
        for arm, cfg in _ARMS.items():
            tag = f"e1-carrier-vh-zerg-rush-{arm}"
            _FLOWS.write_text(
                _patch_carrier_pivot(original, cfg["rush_zealots"], cfg["rush_cannons"]),
                encoding="utf-8",
            )
            print(f"\n===== {arm} (zealots={cfg['rush_zealots']}, "
                  f"cannons={cfg['rush_cannons']}) tag={tag} =====", flush=True)
            rc = subprocess.run(
                ["poetry", "run", "python", "bench.py",
                 "--flow", "carrier", "--diff", "VeryHard", "--race", "Zerg",
                 "--map", "AbyssalReefLE", "--ai-build", "Rush",
                 "-n", "3", "--tag", tag],
                cwd=_AREAS,
            ).returncode
            sp = _AREAS / "bench" / tag / "summary.json"
            results[arm] = (
                json.loads(sp.read_text(encoding="utf-8"))
                if sp.exists() else {"error": f"bench rc={rc}, 无 summary.json"}
            )
    finally:
        _FLOWS.write_text(original, encoding="utf-8")
        print("\nflows.yml 已恢复原样", flush=True)

    print("\n===== E1 汇总 =====")
    for arm, s in results.items():
        if "error" in s:
            print(f"{arm}: {s['error']}")
        else:
            print(f"{arm}: {json.dumps(s, ensure_ascii=False)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
