#!/usr/bin/env python3
"""Quick autopsy: print key curves from state_*.json snapshots."""
from __future__ import annotations

import json
import sys
from pathlib import Path


def main(game_dir: str) -> None:
    d = Path(game_dir)
    states = sorted(d.glob("state_*.json"), key=lambda p: float(p.stem.split("_")[1]))
    print(f"time\tmin\tgas\twrk\tbases\tsupply\tarmy_supply\tcannons\tpylons\tstargates\tnexuses\tfleet\tupg")
    for s in states:
        data = json.loads(s.read_text())
        t = data.get("time", 0.0)
        minerals = data.get("minerals", 0)
        gas = data.get("vespene", 0)
        workers = data.get("workers", 0)
        bases = data.get("bases", 0)
        supply_str = data.get("supply", "0/0")
        try:
            used, total = supply_str.split("/")
            used, total = int(used), int(total)
        except Exception:
            used, total = 0, 0
        army = data.get("army", {})
        structures = data.get("structures", {})
        army_supply = sum(army.values())
        cannons = structures.get("PHOTONCANNON", 0)
        pylons = structures.get("PYLON", 0)
        stargates = structures.get("STARGATE", 0)
        nexuses = structures.get("NEXUS", 0)
        fleet = army.get("CARRIER", 0) + army.get("TEMPEST", 0)
        upg = len(data.get("upgrades", []))
        print(f"{t:.1f}\t{minerals}\t{gas}\t{workers}\t{bases}\t{used}/{total}\t{army_supply}\t{cannons}\t{pylons}\t{stargates}\t{nexuses}\t{fleet}\t{upg}")


if __name__ == "__main__":
    main(sys.argv[1])
