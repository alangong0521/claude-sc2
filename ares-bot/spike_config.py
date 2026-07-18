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
# None = 用 config.yml 的 MyBotRace；或强制 Protoss | Terran | Zerg | Random
BOT_RACE = "Protoss"

# --- build flow（神族走哪个兵种流派）---
# tempest = 暴风舰天空体 + 先知骚扰（默认，零回归风险）
# stalker = 纯追猎 blink 流：SpawnController 只造追猎、bot 自动建 twilight+研究 blink、
#           combat 侧 StalkerOffensive 做集火/风筝/低血 blink 后撤。
# 切流派：BUILD=stalker poetry run python run.py（env 同名覆盖此项，与其它设置一致）
BUILD = "tempest"

# --- replays ---
# Off by default. Flip to True to save each game under ./replays/ for full-UI review
# (double-click the .SC2Replay in SC2: free camera, both sides, health bars, graphs).
SAVE_REPLAY = False
