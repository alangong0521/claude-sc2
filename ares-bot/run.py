import os
import random
import sys
from os import path
from pathlib import Path
from typing import List
from loguru import logger

from sc2 import maps
from sc2.data import AIBuild, Difficulty, Race
from sc2.main import run_game
from sc2.player import Bot, Computer

sys.path.append("ares-sc2/src/ares")
sys.path.append("ares-sc2/src")
sys.path.append("ares-sc2")

# 神族兵种流派 BUILD 必须在 `from bot.main import MyBot` 之前写进 os.environ —— 因为
# 那个 import 会传递导入 production_manager，后者在模块导入时就 os.environ.get("BUILD")。
# env 已设则不覆盖(env 赢)，其次 spike_config.BUILD，其次 "tempest"(与 _opt 语义一致)。
import spike_config as _cfg_for_build
os.environ.setdefault("BUILD", getattr(_cfg_for_build, "BUILD", "tempest") or "tempest")

# 兼容补丁：让老 burnysc2 容忍新版客户端/地图里的未知 id（否则 CactusValleyLE 等
# 4 人图会因未知单位 id 2009 在开局崩溃）。导入即打补丁，必须在起游戏前。
import bot.compat_patch  # noqa: F401

import yaml

from bot.main import MyBot
from ladder import run_ladder_game

# Default SC2 Maps folder per OS. Windows & macOS installs are in standard spots;
# Linux has no standard install path, so set MAPS_PATH there. Env always overrides.
def _default_maps_path() -> str:
    if sys.platform == "win32":
        return r"C:\Program Files (x86)\StarCraft II\Maps"
    if sys.platform == "darwin":
        return "/Applications/StarCraft II/Maps"
    # Linux / other: no standard location — user should set MAPS_PATH.
    return "/Applications/StarCraft II/Maps"


MAPS_PATH: str = os.environ.get("MAPS_PATH", _default_maps_path())
CONFIG_FILE: str = "config.yml"
MAP_FILE_EXT: str = "SC2Map"
MY_BOT_NAME: str = "MyBotName"
MY_BOT_RACE: str = "MyBotRace"

# All match settings live in spike_config.py — edit there. An env var of the same name
# still overrides for one-off tests (e.g. `REALTIME=0 DIFF=VeryHard poetry run python run.py`).
import spike_config as cfg


def _opt(name: str, default):
    """env override (string) if present, else the spike_config value."""
    v = os.environ.get(name)
    if v is None:
        return default
    if isinstance(default, bool):
        return v not in ("0", "false", "False", "")
    return v


REALTIME: bool = _opt("REALTIME", cfg.REALTIME)
DIFF: str = _opt("DIFF", cfg.DIFFICULTY)
AI_BUILD: str = _opt("AI_BUILD", cfg.AI_BUILD)
OPPONENT_RACE: str = _opt("OPPONENT_RACE", cfg.OPPONENT_RACE)
SAVE_REPLAY: bool = _opt("SAVE_REPLAY", cfg.SAVE_REPLAY)
# 对手数量：1 = 常规 1v1；>1 = 多人混战（需对应人数的地图，如 4 人图 CactusValleyLE）
OPPONENTS: int = int(_opt("OPPONENTS", getattr(cfg, "OPPONENTS", 1)))


def main():
    bot_name: str = "MyBot"
    race: Race = Race.Random

    __user_config_location__: str = path.abspath(".")
    user_config_path: str = path.join(__user_config_location__, CONFIG_FILE)
    # attempt to get race and bot name from config file if they exist
    if path.isfile(user_config_path):
        with open(user_config_path) as config_file:
            config: dict = yaml.safe_load(config_file)
            if MY_BOT_NAME in config:
                bot_name = config[MY_BOT_NAME]
            if MY_BOT_RACE in config:
                race = Race[config[MY_BOT_RACE].title()]

    # spike_config.BOT_RACE (or env) wins if set
    bot_race_override = _opt("BOT_RACE", cfg.BOT_RACE)
    if bot_race_override:
        race = Race[str(bot_race_override).title()]

    bot1 = Bot(race, MyBot(), bot_name)

    if "--LadderServer" in sys.argv:
        # Ladder game started by LadderManager
        print("Starting ladder game...")
        result, opponentid = run_ladder_game(bot1)
        print(result, " against opponent ", opponentid)
    else:
        # Local game
        map_list: List[str] = [
            p.name.replace(f".{MAP_FILE_EXT}", "")
            for p in Path(MAPS_PATH).glob(f"*.{MAP_FILE_EXT}")
            if p.is_file()
        ]
        if len(map_list) == 0:
            logger.error(f"Can't find maps, please check `MAPS_PATH` in `run.py'")
            logger.info("Trying back up option")
            logger.info(
                f"\nLooking for maps in {MAPS_PATH} but didn't find anything. \n"
                f"If this path is correct please ensure maps are present. \n"
                f"If this path is incorrect please edit the `MAPS_PATH` in `run.py` \n"
                f"Tip: On Linux (and sometimes Windows) MAPS_PATH will need updating\n"
            )

            # see if user has any recent ladder maps
            map_list: List[str] = [
                "PylonAIE_v4",
                "PersephoneAIE_v4",
                "TorchesAIE_v4",
                "IncorporealAIE_v4",
                "MagannathaAIE_v2",
                "UltraloveAIE_v2",
            ]

        chosen_map = _opt("MAP", cfg.MAP) or random.choice(map_list)
        difficulty = Difficulty[DIFF]
        opp_race = Race[str(OPPONENT_RACE).title()]
        ai_build = AIBuild[AI_BUILD]

        replay_path = None
        if SAVE_REPLAY:
            replay_dir = path.join(path.abspath("."), "replays")
            os.makedirs(replay_dir, exist_ok=True)
            # absolute path so it lands where we expect; double-click in SC2 to review
            replay_path = path.join(replay_dir, f"{chosen_map}_vs_{difficulty.name}.SC2Replay")

        # 1 = 1v1；>1 = 多人混战（1 个我方 bot + N 个内置电脑，全员互殴）
        players = [bot1] + [
            Computer(opp_race, difficulty, ai_build=ai_build) for _ in range(OPPONENTS)
        ]
        mode = "1v1" if OPPONENTS == 1 else f"{OPPONENTS + 1}人混战"
        print(f"Starting local game [{mode}]: map={chosen_map} vs {OPPONENTS}x "
              f"{opp_race.name} {difficulty.name}/{ai_build.name} "
              f"(realtime={REALTIME}, replay={replay_path})")
        if OPPONENTS > 1:
            logger.warning(
                f"多人混战需 ≥{OPPONENTS + 1} 人地图；当前 map={chosen_map}。"
                f"人数不足会 CreateGame 报错——本机 4 人图为 CactusValleyLE。"
            )
        run_game(
            maps.get(chosen_map),
            players,
            realtime=REALTIME,
            save_replay_as=replay_path,
        )


# Start game
if __name__ == "__main__":
    main()
