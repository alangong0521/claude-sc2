#!/usr/bin/env python3
"""O329 录像解析:双方基地(Hatchery/Nexus/CommandCenter)落成时间线。

用法(在 ares-bot/ 下):
  poetry run python scripts/replay_bases.py replays/xxx.SC2Replay

依赖:s2protocol(上游停更,需 `poetry run pip install s2protocol`,
脚本内置 py3.12 imp 兼容垫片)+ mpyq(已在 pyproject)。

读 tracker 事件的 UnitBorn/UnitInit,按玩家打印基地出生时刻(游戏秒)。
回答「电脑一般多少时间建出 2 矿」的对照问题。
"""
from __future__ import annotations

import importlib.util
import sys
import types

# s2protocol(上游停更)的 versions/__init__.py 还在 import imp(py3.12 已移除),
# 用 importlib 垫一个最小 imp.load_source 兼容层。
if "imp" not in sys.modules:
    _imp = types.ModuleType("imp")

    def _load_source(name: str, path: str):
        spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod

    _imp.load_source = _load_source

    def _find_module(name: str, path=None):
        # 兼容 imp.find_module:返回 (fp, pathname, description)
        import os

        search = path or sys.path
        for d in search:
            p = os.path.join(d, name + ".py")
            if os.path.exists(p):
                return (open(p, "rb"), p, (".py", "rb", 1))
        raise ImportError(name)

    _imp.find_module = _find_module

    def _load_module(name: str, fp, pathname: str, description):
        try:
            return _load_source(name, pathname)
        finally:
            if fp and not fp.closed:
                fp.close()

    _imp.load_module = _load_module
    sys.modules["imp"] = _imp

import mpyq
from s2protocol import versions

_BASE_TYPES = {
    "Hatchery", "Lair", "Hive",
    "Nexus", "CommandCenter", "OrbitalCommand", "PlanetaryFortress",
}


def main(path: str) -> None:
    archive = mpyq.MPQArchive(path)
    contents = archive.read_file("replay.details")
    details = versions.latest().decode_replay_details(contents)
    players = []
    for p in details["m_playerList"]:
        players.append(
            (
                p["m_name"].decode() if isinstance(p["m_name"], bytes) else p["m_name"],
                p["m_race"].decode() if isinstance(p["m_race"], bytes) else p["m_race"],
            )
        )
    print("玩家:", players)

    tracker = archive.read_file("replay.tracker.events")
    evts = versions.latest().decode_replay_tracker_events(tracker)
    seen = set()
    for ev in evts:
        if ev.get("_event") not in (
            "NNet.Replay.Tracker.SUnitBornEvent",
            "NNet.Replay.Tracker.SUnitInitEvent",
        ):
            continue
        utype = ev.get("m_unitTypeName")
        if isinstance(utype, bytes):
            utype = utype.decode()
        if utype not in _BASE_TYPES:
            continue
        tag = ev.get("m_unitTagIndex"), ev.get("m_unitTagRecycle")
        if tag in seen:
            continue
        seen.add(tag)
        pid = ev.get("m_controlPlayerId")
        t = ev["_gameloop"] / 16.0
        name = players[pid - 1][0] if 0 < pid <= len(players) else "?"
        race = players[pid - 1][1] if 0 < pid <= len(players) else "?"
        print(f"  {t:7.1f}s  player{pid}({name}/{race}) {utype}")


if __name__ == "__main__":
    main(sys.argv[1])
