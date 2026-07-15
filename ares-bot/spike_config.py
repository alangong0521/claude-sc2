"""
Spike run settings — the one place to tweak how a local game launches.

Edit a value here, then just `poetry run python run.py`. (Each setting can still be
overridden ad-hoc with an env var of the same name, which wins if set — handy for
one-off tests without editing the file.)

This is about HOW we launch a match (opponent, speed, replays). The bot's own ares
config lives separately in `config.yml`.
"""

# --- watchability ---
# True  = normal speed, you can watch the SC2 window live
# False = uncapped speed, finishes a game in ~1-2 min (good for quick win/loss checks)
REALTIME = True

# --- opponent (built-in AI) ---
# DIFFICULTY ladder, weak -> strong:
#   VeryEasy, Easy, Medium, MediumHard, Hard, Harder, VeryHard,
#   CheatVision, CheatMoney, CheatInsane   (VeryHard = strongest non-cheating)
DIFFICULTY = "Hard"
# AI_BUILD: RandomBuild | Rush | Timing | Power | Macro | Air
AI_BUILD = "Macro"
# OPPONENT_RACE: Protoss | Terran | Zerg | Random
OPPONENT_RACE = "Random"
# 对手数量：1 = 常规 1v1；>1 = 多人混战（1 个我方 bot + N 个电脑，全员互殴）。
# 注意 >1 需对应人数的地图，本机 4 人图 = CactusValleyLE（把上面 MAP 设成它）。
OPPONENTS = 1

# --- map ---
# None  = pick a random installed map; or pin one, e.g. "AbyssalReefLE"
MAP = None

# --- our bot ---
# None = use MyBotRace from config.yml; or force Protoss | Terran | Zerg | Random
# 流派按种族自动随机（config.yml 的 Playstyle 留空时）：
#   Zerg  → ravager_pressure
#   Terran→ bio_mmm / mech_tank 随机
# 想固定某流派：在 config.yml 写 Playstyle: bio_mmm（见 styles.resolve_style）。
BOT_RACE = "Protoss"

# --- replays ---
# Off by default. Flip to True to save each game under ./replays/ for full-UI review
# (double-click the .SC2Replay in SC2: free camera, both sides, health bars, graphs).
SAVE_REPLAY = False
