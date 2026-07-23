"""B8 自调参骨架 —— 12PoolBot leitwerk ask/tell 思路的零依赖自实现(只用标准库)。

见 docs/selftune.md(集成方式)与 docs/community-tactics-research.md B8 条目。
与 promotion.py 的分工:promotion 是档位资格考试(离线、跨档),
本模块是档内运行时调参(on_start ask 取参、on_end tell 回传结果)。

设计要点:
- 参数声明:SelfTuneParams dataclass,默认值=代码里现行的真实阈值(出处见 PARAMS)。
- 存储:bench/selftune-params.json(bench/ 已 gitignore)。读写全容错——
  文件坏/缺字段用默认补齐,未知键原样保留(schema 演进不丢旧 checkpoint)。
- ask(context):按 enemy_race 条件化取参。记录 <MIN_RECORDS 局时只用
  默认值+静态按族覆盖表;攒够后启用简单进档/退档爬山(未验证,待跑局)。
- tell(record):追加一局记录,效率分=log1p(kill)−log1p(loss)。

本模块 deliberately 不 import ares/sc2,纯函数为主、可离线单测。
"""
from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, fields
from pathlib import Path

# bench/ 与 promotion.py 同一产出目录,已被根 .gitignore 的 ares-bot/bench/ 覆盖
DEFAULT_PATH = Path(__file__).resolve().parents[1] / "bench" / "selftune-params.json"

SCHEMA_VERSION = 1

# 学习门槛(未验证,先验值):总记录攒够 20 局才启用爬山,之前只吃默认值+静态按族覆盖
MIN_RECORDS = 20
# 爬山评估窗口:同族最近 N 局
WINDOW = 5
# 窗口胜率低于此值 → 把被怀疑参数往反方向走一步
WINRATE_FLOOR = 0.4


@dataclass
class SelfTuneParams:
    """一局用的可调参数集。默认值必须与代码现行阈值一致(出处见 PARAMS)。"""
    blink_shield_perc: float = 0.25     # 护盾低于此 → blink 后撤
    blink_when_swarmed: int = 4         # 被这么多敌围 → blink 后撤
    rally_min_army: int = 14            # 集结阈值:兵力低于它先守家攒兵
    bank_threshold: int = 400           # 矿存款超此值才追加产能
    expand_advantage_supply: int = 12   # 领先这么多 supply 时提前开矿
    attack_maxed_threshold: int = 190   # when_maxed 触发器的人口阈值
    worker_evac_threshold: int = 4      # 敌地面单位 ≥N 且无塔 → 农民撤离
    anti_air_trigger: int = 3           # 敌可见空军 ≥N 架触发对空比例


# 参数元数据:step=爬山步长(内置),lo/hi=钳位区间,source=现行阈值出处(文件:行)
PARAMS = {
    "blink_shield_perc":       {"step": 0.05, "lo": 0.0, "hi": 0.60,
                                "source": "bot/combat/stalker_offensive.py:68"},
    "blink_when_swarmed":      {"step": 1,    "lo": 2,   "hi": 8,
                                "source": "bot/combat/stalker_offensive.py:69"},
    "rally_min_army":          {"step": 2,    "lo": 0,   "hi": 30,
                                "source": "flows.yml:85(stalker 流),消费于 bot/managers/combat_manager.py:78"},
    "bank_threshold":          {"step": 100,  "lo": 0,   "hi": 1000,
                                "source": "bot/managers/production_manager.py:893(minerals > 400 追加产能)"},
    "expand_advantage_supply": {"step": 2,    "lo": 0,   "hi": 30,
                                "source": "flows.yml:113 auto_expand.advantage_supply,消费于 bot/production_plans.py:130"},
    "attack_maxed_threshold":  {"step": 5,    "lo": 150, "hi": 200,
                                "source": "bot/levers.py:114 should_hold_for_trigger(maxed_threshold=190)"},
    "worker_evac_threshold":   {"step": 1,    "lo": 2,   "hi": 10,
                                "source": "bot/production_plans.py:369 should_evacuate_workers(threshold=4)"},
    "anti_air_trigger":        {"step": 1,    "lo": 1,   "hi": 8,
                                "source": "flows.yml:67 anti_air_trigger"},
}

# 爬山轮换顺序:每次退步后轮到下一个参数,避免在单个参数上震荡(未验证)
CLIMB_ORDER = list(PARAMS)

# 静态按族覆盖表(未验证,手工先验;学习启用后 learned overrides 覆盖这里的值)
RACE_OVERRIDES = {
    "zerg":    {"rally_min_army": 16},        # 虫族爆兵/换家快,集结阈值略升
    "terran":  {"blink_shield_perc": 0.20},   # 坦克溅射下更早 blink 后撤
    "protoss": {},
}

# int 类型字段(步进后要 round 回 int;从 dataclass 声明推,不手写清单)
_INT_FIELDS = {f.name for f in fields(SelfTuneParams) if f.type == "int"}

# tell 记录字段及默认值(缺字段时按此补齐)
_RECORD_DEFAULTS = {
    "flow": "", "difficulty": "", "race": "", "build": "",
    "result": "", "game_time": 0.0, "kill_value": 0, "loss_value": 0,
}


@dataclass
class TellRecord:
    """一局结局记录。tell() 的输入,也直接落盘进 state["records"]。"""
    flow: str = ""
    difficulty: str = ""
    race: str = ""
    build: str = ""
    result: str = ""          # "win"/"loss"/"tie"(victory/defeat 也认,见 _is_win)
    game_time: float = 0.0    # 游戏秒
    kill_value: float = 0.0   # 击杀价值(sc2 score.kill_value 合计)
    loss_value: float = 0.0   # 损失价值


def efficiency(kill_value: float, loss_value: float) -> float:
    """交换比效率分 = log1p(kill) − log1p(loss)。log1p 压量纲,0/0 → 0。"""
    return math.log1p(max(0.0, kill_value)) - math.log1p(max(0.0, loss_value))


def _is_win(result: str) -> bool | None:
    """result 归一:True=胜 False=负 None=平局/不认识(不计入胜率)。"""
    r = str(result).strip().lower()
    if r in ("win", "victory"):
        return True
    if r in ("loss", "defeat"):
        return False
    return None


def _norm_race(race) -> str:
    """种族键归一(敌族可能以 'Zerg'/'zerg'/Race 枚举名进来)。"""
    return str(race or "").strip().lower()


def default_state() -> dict:
    """空 checkpoint。schema 字段用于将来迁移;records/overrides/climb 三分区。"""
    return {"schema": SCHEMA_VERSION, "records": [], "overrides": {}, "climb": {}}


def _normalize_record(rec) -> dict | None:
    """单条记录容错:非 dict 丢弃;缺字段补默认;补算 efficiency。"""
    if not isinstance(rec, dict):
        return None
    out = {k: rec.get(k, v) for k, v in _RECORD_DEFAULTS.items()}
    out["efficiency"] = rec.get(
        "efficiency", efficiency(out["kill_value"], out["loss_value"]))
    return out


def load_state(path: Path | str = DEFAULT_PATH) -> dict:
    """读 checkpoint,全容错:文件不存在/坏 JSON/顶层非 dict → 默认;
    缺分区补默认;未知顶层键原样保留(schema 变更不丢旧 checkpoint)。"""
    path = Path(path)
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeDecodeError):
        return default_state()
    if not isinstance(raw, dict):
        return default_state()
    state = dict(raw)  # 保留未知键
    state["schema"] = raw.get("schema", SCHEMA_VERSION)
    records = raw.get("records")
    state["records"] = [r for r in
                        (_normalize_record(x) for x in records)
                        if r is not None] if isinstance(records, list) else []
    for key in ("overrides", "climb"):
        if not isinstance(raw.get(key), dict):
            state[key] = {}
    return state


def save_state(state: dict, path: Path | str = DEFAULT_PATH) -> bool:
    """写 checkpoint(临时文件+replace,避免半截文件)。失败不炸 bot,返回 False。"""
    path = Path(path)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                       encoding="utf-8")
        os.replace(tmp, path)
        return True
    except OSError:
        return False


def _base_value(state: dict, race: str, name: str) -> float:
    """参数当前生效值:默认 ← 静态按族覆盖 ← learned overrides(逐级覆盖)。"""
    learned = state.get("overrides", {}).get(race, {})
    static = RACE_OVERRIDES.get(race, {})
    if name in learned:
        return learned[name]
    if name in static:
        return static[name]
    return getattr(SelfTuneParams(), name)


def _cast(name: str, value: float):
    """按 dataclass 声明类型收口:int 字段 round 回 int。"""
    if name in _INT_FIELDS:
        return int(round(value))
    return float(value)


def recent_winrate(records: list, race: str, n: int = WINDOW) -> float | None:
    """同族最近 n 局胜率(平局/不认识不计)。样本不足 n → None(不动参数)。"""
    race = _norm_race(race)
    own = [r for r in records if _norm_race(r.get("race")) == race]
    if len(own) < n:
        return None
    window = own[-n:]
    judged = [_is_win(r.get("result")) for r in window]
    judged = [j for j in judged if j is not None]
    if not judged:
        return None
    return sum(1 for j in judged if j) / len(judged)


def maybe_climb(state: dict, race: str) -> tuple | None:
    """进档/退档爬山(未验证,待跑局标定)。原地改 state,返回 (参数, 旧值, 新值) 或 None。

    规则:总记录 ≥MIN_RECORDS 且同族最近 WINDOW 局胜率 <WINRATE_FLOOR →
    把 CLIMB_ORDER 轮到的「被怀疑参数」往上一步的反方向走一步(步长内置
    在 PARAMS),并钳位在 lo/hi。走完轮换到下一个参数。
    """
    race = _norm_race(race)
    if not race or len(state.get("records", [])) < MIN_RECORDS:
        return None
    wr = recent_winrate(state["records"], race)
    if wr is None or wr >= WINRATE_FLOOR:
        return None
    climb = state.setdefault("climb", {})
    c = climb.get(race) or {"idx": 0, "direction": 1}
    name = CLIMB_ORDER[c["idx"] % len(CLIMB_ORDER)]
    meta = PARAMS[name]
    direction = -int(c.get("direction", 1))  # 反方向
    old = _base_value(state, race, name)
    new = _cast(name, min(meta["hi"], max(meta["lo"], old + direction * meta["step"])))
    if new == old:  # 顶到边界,这步白走,只换参数不换方向
        climb[race] = {"idx": c["idx"] + 1, "direction": -direction}
        return None
    state.setdefault("overrides", {}).setdefault(race, {})[name] = new
    climb[race] = {"idx": c["idx"] + 1, "direction": direction}
    return (name, old, new)


def params_for(state: dict, enemy_race=None) -> SelfTuneParams:
    """ask 的核心纯函数:默认值 ← 静态按族覆盖 ← learned overrides。
    未知参数名/未知种族一律忽略,坏值落回默认。"""
    race = _norm_race(enemy_race)
    values = asdict(SelfTuneParams())
    for source in (RACE_OVERRIDES.get(race, {}),
                   state.get("overrides", {}).get(race, {})):
        for name, v in source.items():
            if name in values and isinstance(v, (int, float)):
                values[name] = _cast(name, v)
    return SelfTuneParams(**values)


def append_record(state: dict, record: TellRecord | dict) -> dict:
    """tell 的核心纯函数:归一化并追加一条记录,原地改 state 并返回之。"""
    rec = record if isinstance(record, dict) else asdict(record)
    norm = _normalize_record(rec)
    state.setdefault("records", []).append(norm)
    return state


class SelfTuner:
    """薄壳:持有 checkpoint 路径,ask/tell 各一行(纯逻辑都在上面的函数里)。

    集成(主 agent 统一加钩子,本骨架不动 main.py):
      on_start: self._tuner = SelfTuner(); self._params = self._tuner.ask(
                    {"enemy_race": self.enemy_race})
      on_end:   self._tuner.tell(TellRecord(flow=..., difficulty=..., race=...,
                    build=..., result=str(game_result), game_time=self.time,
                    kill_value=..., loss_value=...))
    """

    def __init__(self, path: Path | str = DEFAULT_PATH):
        self.path = Path(path)

    def ask(self, context: dict | None = None) -> SelfTuneParams:
        """开局取参。先按近况走一步爬山(攒够 MIN_RECORDS 局才启用),
        落盘后返回本局参数。context 目前只认 enemy_race。"""
        state = load_state(self.path)
        race = (context or {}).get("enemy_race")
        if maybe_climb(state, race) is not None:
            save_state(state, self.path)  # 学习到的 override 立刻持久化,崩局不丢
        return params_for(state, race)

    def tell(self, record: TellRecord | dict) -> bool:
        """终局回传:追加记录并落盘。返回是否写盘成功(失败不炸 bot)。"""
        state = load_state(self.path)
        append_record(state, record)
        return save_state(state, self.path)
