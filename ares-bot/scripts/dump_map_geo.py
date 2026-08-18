#!/usr/bin/env python3
"""O328 地图几何探针:开局打印扩张点布局 + 开阔度,立刻退游戏。

用法(在 ares-bot/ 下):
  poetry run python scripts/dump_map_geo.py [MapName]

开阔度 = 扩张点半径 10/14 环上可通行采样点计数(背靠墙体的防守矿
环上不可通行点多 = 口少;敞开矿几乎全可通行)。供 pick_pocket_expansion
的选址权重取证,不改任何 bot 逻辑。
"""
from __future__ import annotations

import math
import os
import sys

sys.path.append("ares-sc2/src")

from sc2 import maps
from sc2.data import AIBuild, Difficulty, Race
from sc2.main import run_game
from sc2.player import Bot, Computer
from sc2.bot_ai import BotAI

for k in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
    os.environ.pop(k, None)


class GeoProbe(BotAI):
    async def on_start(self):
        pass

    async def on_step(self, iteration: int):
        pa = self.game_info.playable_area
        print(f"PLAYABLE x={pa.x} y={pa.y} w={pa.width} h={pa.height}")
        print(f"MAIN {self.start_location}")
        for es in self.enemy_start_locations:
            print(f"ENEMY {es}")
        grid = self.game_info.pathing_grid
        for el in self.expansion_locations_list:
            if self.townhalls.closer_than(5.0, el):
                continue
            d_enemy = min(
                (el.distance_to(es) for es in self.enemy_start_locations),
                default=0.0,
            )
            d_main = el.distance_to(self.start_location)
            edges = sorted(
                [el.x - pa.x, pa.x + pa.width - el.x, el.y - pa.y, pa.y + pa.height - el.y]
            )
            open10 = open14 = tot = 0
            for i in range(24):
                a = i * math.tau / 24
                for r, acc in ((10.0, "o10"), (14.0, "o14")):
                    x, y = el.x + r * math.cos(a), el.y + r * math.sin(a)
                    tot += 1
                    try:
                        ok = bool(grid.is_set((int(round(x)), int(round(y)))))
                    except Exception:
                        ok = False
                    if ok:
                        if acc == "o10":
                            open10 += 1
                        else:
                            open14 += 1
            print(
                f"EXP ({el.x:.1f},{el.y:.1f}) d_enemy={d_enemy:.1f} "
                f"d_main={d_main:.1f} edge1={edges[0]:.1f} edge2={edges[1]:.1f} "
                f"open10={open10}/24 open14={open14}/24"
            )
        await self.client.leave()


if __name__ == "__main__":
    map_name = sys.argv[1] if len(sys.argv) > 1 else "AbyssalReefLE"
    run_game(
        maps.get(map_name),
        [
            Bot(Race.Protoss, GeoProbe()),
            Computer(Race.Zerg, Difficulty.VeryEasy, AIBuild.RandomBuild),
        ],
        realtime=False,
    )
