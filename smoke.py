#!/usr/bin/env python3
"""
Stage-0 smoke test: can python-sc2 launch the native Mac SC2 client and play one
full game vs the built-in AI? No steering, no LLM, no ares — just the bare loop.

This answers the one yellow light: does the retail client come up under
python-sc2 control on THIS Mac (Apple Silicon / current macOS), play, and exit
cleanly. If this prints "SMOKE OK" you have a working backbone.

    .venv/bin/python smoke.py            # windowed, watchable
    MAP=Whatever .venv/bin/python smoke.py

The bot does the dumbest possible thing: mine, build workers, attack-move when it
has an army. We only care that the game runs end to end.
"""

import os
import sys

from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.data import Difficulty, Race, Result
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot, Computer

MAP = os.environ.get("MAP", "AbyssalReefLE")
REALTIME = os.environ.get("REALTIME", "1") == "1"   # 1 = real speed, watchable


class SmokeBot(BotAI):
    async def on_step(self, iteration: int):
        if iteration == 0:
            await self.chat_send("smoke bot: hello")
            print(f"[smoke] game started, map={MAP}, race={self.race}")

        # keep workers mining
        await self.distribute_workers()

        nexus = self.townhalls.ready
        if not nexus:
            return
        nexus = nexus.first

        # train probes up to a small cap
        if self.can_afford(UnitTypeId.PROBE) and self.workers.amount < 22 and nexus.is_idle:
            nexus.train(UnitTypeId.PROBE)

        # build one pylon when supply is tight
        if self.supply_left < 3 and self.already_pending(UnitTypeId.PYLON) == 0 \
                and self.can_afford(UnitTypeId.PYLON):
            pos = nexus.position.towards(self.game_info.map_center, 8)
            await self.build(UnitTypeId.PYLON, near=pos)

    async def on_end(self, result: Result):
        print(f"[smoke] game ended: {result}")


def main():
    try:
        m = maps.get(MAP)
    except KeyError:
        print(f"[smoke] map '{MAP}' not found in SC2 Maps folder.")
        print("        Put a ladder map (.SC2Map) in SC2's Maps folder, e.g.")
        print("        macOS '/Applications/StarCraft II/Maps/', "
              r"Windows 'C:\\Program Files (x86)\\StarCraft II\\Maps\\'")
        print("        and pass MAP=<name-without-extension>.")
        sys.exit(2)

    result = run_game(
        m,
        [Bot(Race.Protoss, SmokeBot()), Computer(Race.Terran, Difficulty.Easy)],
        realtime=REALTIME,
    )
    print(f"[smoke] run_game returned: {result}")
    print("SMOKE OK" if result is not None else "SMOKE FAILED")


if __name__ == "__main__":
    main()
