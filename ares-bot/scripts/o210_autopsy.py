#!/usr/bin/env python3
"""O210 bench autopsy: extract timelines / idle_builder / bases / army / final state."""
import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LANES = {
    "abyssal": ROOT / "bench" / "o210-vh-zerg-rush-abyssal-headless",
    "paladino": ROOT / "bench" / "o210-vh-zerg-rush-paladino-headless",
}


def parse_state(path: Path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def summarize_game(lane_dir: Path, game_dir: Path):
    states = sorted(game_dir.glob("state_*.json"), key=lambda p: p.name)
    if not states:
        return None
    first = parse_state(states[0])
    last = parse_state(states[-1])
    # timeline snapshots every ~60s
    timeline = []
    for s in states:
        st = parse_state(s)
        if st["time"] % 60 < 4.5:
            timeline.append({
                "t": st["time"],
                "minerals": st["minerals"],
                "vespene": st["vespene"],
                "workers": st["workers"],
                "bases": st["bases"],
                "supply": st["supply"],
                "army": dict(st.get("army", {})),
            })
    # idle_builder events
    idle_events = []
    base_lost_events = []
    reserve_fuse_events = []
    worker_drop_events = []
    for s in states:
        st = parse_state(s)
        for ev in st.get("events", []):
            msg = ev.get("msg", "")
            if "idle_builder" in msg or "农民干等" in msg:
                idle_events.append((st["time"], msg))
            elif "丢失基地" in msg:
                base_lost_events.append((st["time"], msg))
            elif "预留死锁保险丝熔断" in msg:
                reserve_fuse_events.append((st["time"], msg))
            elif "农民骤减" in msg:
                worker_drop_events.append((st["time"], msg))

    # final enemy army
    enemy_army = {}
    for e in last.get("enemies", []):
        enemy_army.update(e.get("visible", {}).get("army", {}))

    # first carrier/tempest/voidray seen in states
    first_seen = {}
    for s in states:
        st = parse_state(s)
        for unit in ["CARRIER", "TEMPEST", "VOIDRAY", "STALKER", "ZEALOT", "ORACLE"]:
            if unit in st.get("army", {}) and unit not in first_seen:
                first_seen[unit] = st["time"]

    # first 2 bases timing
    base2_time = None
    for s in states:
        st = parse_state(s)
        if st["bases"] >= 2:
            base2_time = st["time"]
            break

    # max minerals banked
    max_bank = max((parse_state(s)["minerals"] for s in states), default=0)

    return {
        "game": game_dir.name,
        "result": (game_dir / "run.log").read_text().splitlines()[-1] if (game_dir / "run.log").exists() else "?",
        "duration": last["time"],
        "final": {
            "minerals": last["minerals"],
            "vespene": last["vespene"],
            "workers": last["workers"],
            "bases": last["bases"],
            "army": dict(last.get("army", {})),
        },
        "enemy_final": enemy_army,
        "first_seen": first_seen,
        "base2_time": base2_time,
        "max_bank": max_bank,
        "idle_count": len(idle_events),
        "idle_events": idle_events[:8],
        "base_lost": base_lost_events,
        "reserve_fuse": reserve_fuse_events,
        "worker_drops": worker_drop_events[-5:],
        "timeline": timeline,
    }


def main():
    for lane_name, lane_dir in LANES.items():
        print(f"\n=== LANE {lane_name} ===")
        summary = json.loads((lane_dir / "summary.json").read_text())
        print(f"wins={summary['wins']} losses={summary['losses']} "
              f"issue_counts={summary['issue_counts']}")
        games = sorted(p for p in lane_dir.iterdir() if p.is_dir() and p.name.startswith("game_"))
        for gd in games:
            r = summarize_game(lane_dir, gd)
            if r is None:
                continue
            print(f"\n-- {lane_name}/{r['game']} --")
            print(f"  result={r['result']}  duration={r['duration']:.0f}s")
            print(f"  final: workers={r['final']['workers']} bases={r['final']['bases']} "
                  f"minerals={r['final']['minerals']} vespene={r['final']['vespene']}")
            print(f"  final army: {r['final']['army']}")
            print(f"  final enemy visible: {r['enemy_final']}")
            print(f"  first_seen: {r['first_seen']}")
            print(f"  base2_time: {r['base2_time']}")
            print(f"  max_bank: {r['max_bank']}")
            print(f"  idle_builder events: {r['idle_count']} (showing up to 8)")
            for t, msg in r["idle_events"]:
                print(f"    t={t:6.1f}: {msg}")
            if r["reserve_fuse"]:
                print(f"  reserve fuse events:")
                for t, msg in r["reserve_fuse"]:
                    print(f"    t={t:6.1f}: {msg}")
            if r["base_lost"]:
                print(f"  base lost events:")
                for t, msg in r["base_lost"]:
                    print(f"    t={t:6.1f}: {msg}")
            if r["worker_drops"]:
                print(f"  last worker drops:")
                for t, msg in r["worker_drops"]:
                    print(f"    t={t:6.1f}: {msg}")
            # aggregate timeline
            print("  timeline(t/minerals/workers/bases/army):")
            for snap in r["timeline"]:
                print(f"    {snap['t']:5.0f} 矿{snap['minerals']:4d} 农{snap['workers']:2d} "
                      f"基{snap['bases']} 供给{snap['supply']} 军{snap['army']}")


if __name__ == "__main__":
    main()
