"""selftune.py 纯逻辑单测 —— 不起游戏、不 import ares/sc2,标准库即可跑。

跑法(在 ares-bot/ 下):
  poetry run python -m pytest tests/test_selftune.py -q
或:
  python3 -m unittest tests.test_selftune -v

覆盖:load/save 容错(坏文件/缺字段/未知键保留)、ask 的按族覆盖
(静态表 + learned override 优先)、tell 的追加与效率分、爬山步进逻辑
(门槛/窗口胜率/反向步进/钳位/int 收口)。
"""
import json
import math
import os
import sys
import tempfile
import unittest
from pathlib import Path

# 让 `import bot.selftune` 能在直接跑此文件时生效
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.selftune import (  # noqa: E402
    CLIMB_ORDER, MIN_RECORDS, PARAMS, RACE_OVERRIDES, WINDOW,
    SelfTuneParams, SelfTuner, TellRecord,
    append_record, default_state, efficiency, load_state, maybe_climb,
    params_for, recent_winrate, save_state,
)


def _rec(race="Zerg", result="win", **kw):
    """造一条最小记录 dict。"""
    base = {"flow": "stalker", "difficulty": "Hard", "race": race,
            "build": "Rush", "result": result, "game_time": 600.0,
            "kill_value": 3000, "loss_value": 1500}
    base.update(kw)
    return base


def _state_with(records, **kw):
    """造一个带记录的 state。"""
    s = default_state()
    s["records"] = [_r for _r in (append_record({"records": []}, r)["records"][0]
                                  for r in records)]
    s.update(kw)
    return s


class TestEfficiency(unittest.TestCase):
    def test_log_ratio(self):
        self.assertAlmostEqual(efficiency(3000, 1500),
                               math.log1p(3000) - math.log1p(1500))

    def test_zero_and_negative(self):
        self.assertEqual(efficiency(0, 0), 0.0)
        # 负值按 0 处理,不炸
        self.assertEqual(efficiency(-5, -5), 0.0)
        self.assertGreater(efficiency(10, -1), 0.0)


class TestLoadSave(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.path = Path(self._tmp.name) / "sub" / "params.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_missing_file_gives_defaults(self):
        state = load_state(self.path)
        self.assertEqual(state["schema"], 1)
        self.assertEqual(state["records"], [])
        self.assertEqual(state["overrides"], {})

    def test_corrupt_json_gives_defaults(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{not json!!", encoding="utf-8")
        self.assertEqual(load_state(self.path), default_state())

    def test_non_dict_json_gives_defaults(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("[1, 2, 3]", encoding="utf-8")
        self.assertEqual(load_state(self.path), default_state())

    def test_record_missing_fields_filled(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps(
            {"records": [{"race": "Zerg", "result": "win"}]}), encoding="utf-8")
        rec = load_state(self.path)["records"][0]
        self.assertEqual(rec["race"], "Zerg")
        self.assertEqual(rec["flow"], "")           # 缺字段补默认
        self.assertEqual(rec["kill_value"], 0)
        # 缺 efficiency → 按 kill/loss 补算
        self.assertEqual(rec["efficiency"], efficiency(0, 0))

    def test_garbage_records_dropped(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text(json.dumps(
            {"records": [{"race": "Zerg", "result": "win"}, 42, "x", None]}),
            encoding="utf-8")
        self.assertEqual(len(load_state(self.path)["records"]), 1)

    def test_unknown_top_level_keys_survive_roundtrip(self):
        """schema 演进不丢旧 checkpoint:未知键 load 后 save 还在。"""
        state = default_state()
        state["future_field"] = {"keep": "me"}
        state["records"] = [_rec()]
        self.assertTrue(save_state(state, self.path))
        loaded = load_state(self.path)
        self.assertEqual(loaded["future_field"], {"keep": "me"})
        self.assertTrue(save_state(loaded, self.path))
        self.assertEqual(json.loads(self.path.read_text())["future_field"],
                         {"keep": "me"})

    def test_roundtrip_and_mkdir(self):
        """save 自动建父目录;记录原样回来。"""
        state = default_state()
        append_record(state, _rec(kill_value=100, loss_value=50))
        self.assertTrue(save_state(state, self.path))
        loaded = load_state(self.path)
        self.assertEqual(len(loaded["records"]), 1)
        self.assertEqual(loaded["records"][0]["kill_value"], 100)


class TestAskRaceOverride(unittest.TestCase):
    def test_defaults_without_context(self):
        p = params_for(default_state())
        self.assertEqual(p, SelfTuneParams())

    def test_static_race_override(self):
        """静态按族覆盖表:Zerg 的 rally_min_army 抬高,Protoss 用默认。"""
        pz = params_for(default_state(), "Zerg")
        self.assertEqual(pz.rally_min_army,
                         RACE_OVERRIDES["zerg"]["rally_min_army"])
        self.assertEqual(params_for(default_state(), "Protoss").rally_min_army,
                         SelfTuneParams().rally_min_army)
        # 大小写/枚举名风格都认
        self.assertEqual(params_for(default_state(), "zerg").rally_min_army,
                         pz.rally_min_army)
        # 未覆盖的字段不受按族表影响
        self.assertEqual(pz.bank_threshold, SelfTuneParams().bank_threshold)

    def test_learned_override_beats_static(self):
        state = default_state()
        state["overrides"] = {"zerg": {"rally_min_army": 20}}
        self.assertEqual(params_for(state, "Zerg").rally_min_army, 20)

    def test_unknown_param_and_bad_value_ignored(self):
        state = default_state()
        state["overrides"] = {"zerg": {"no_such_param": 1,
                                       "rally_min_army": "oops"}}
        p = params_for(state, "Zerg")
        self.assertFalse(hasattr(p, "no_such_param"))
        self.assertEqual(p.rally_min_army,  # 坏值 → 静态表
                         RACE_OVERRIDES["zerg"]["rally_min_army"])

    def test_int_fields_stay_int(self):
        state = default_state()
        state["overrides"] = {"zerg": {"rally_min_army": 17.6}}
        p = params_for(state, "Zerg")
        self.assertIsInstance(p.rally_min_army, int)
        self.assertEqual(p.rally_min_army, 18)


class TestTell(unittest.TestCase):
    def test_append_record_computes_efficiency(self):
        state = default_state()
        append_record(state, _rec(kill_value=3000, loss_value=1500))
        rec = state["records"][0]
        self.assertAlmostEqual(rec["efficiency"],
                               math.log1p(3000) - math.log1p(1500))

    def test_tell_record_dataclass(self):
        state = default_state()
        append_record(state, TellRecord(flow="carrier", race="Terran",
                                        result="victory", kill_value=10))
        rec = state["records"][0]
        self.assertEqual(rec["flow"], "carrier")
        self.assertEqual(rec["difficulty"], "")  # dataclass 默认值也过归一
        self.assertGreater(rec["efficiency"], 0)

    def test_tuner_ask_tell_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            tuner = SelfTuner(Path(d) / "p.json")
            p = tuner.ask({"enemy_race": "Zerg"})
            self.assertIsInstance(p, SelfTuneParams)
            self.assertTrue(tuner.tell(_rec(race="Zerg", result="loss")))
            self.assertEqual(len(load_state(tuner.path)["records"]), 1)


class TestHillClimb(unittest.TestCase):
    def _losing_state(self, race="Zerg", wins=0, total=MIN_RECORDS):
        """total 局记录,其中最近 WINDOW 局同族 wins 胜。"""
        records = ([_rec(race="Terran", result="win")]
                   * (total - WINDOW)
                   + [_rec(race=race, result="win")] * wins
                   + [_rec(race=race, result="loss")] * (WINDOW - wins))
        return _state_with(records)

    def test_below_min_records_no_climb(self):
        state = _state_with([_rec(result="loss")] * (MIN_RECORDS - 1))
        self.assertIsNone(maybe_climb(state, "Zerg"))
        self.assertEqual(state["overrides"], {})

    def test_no_race_no_climb(self):
        state = self._losing_state()
        self.assertIsNone(maybe_climb(state, None))

    def test_good_winrate_no_climb(self):
        state = self._losing_state(wins=3)  # 3/5 = 60% ≥ 40%
        self.assertIsNone(maybe_climb(state, "Zerg"))

    def test_recent_winrate_window(self):
        records = ([_rec(race="Zerg", result="win")] * 10
                   + [_rec(race="Zerg", result="loss")] * WINDOW)
        self.assertEqual(recent_winrate(records, "Zerg"), 0.0)
        # 只看同族:别的族连负插在前面,不拖本族最近窗口的胜率
        mixed = ([_rec(race="Terran", result="loss")] * WINDOW
                 + [_rec(race="Zerg", result="win")] * WINDOW)
        self.assertEqual(recent_winrate(mixed, "Zerg"), 1.0)
        # 样本不足 → None
        self.assertIsNone(recent_winrate(records[:3], "Zerg"))

    def test_bad_winrate_steps_opposite(self):
        """0/5 全负 → 被怀疑参数(轮换第一个)往默认方向(+1)的反向走一步。"""
        state = self._losing_state(wins=0)
        name = CLIMB_ORDER[0]
        meta = PARAMS[name]
        before = params_for(state, "Zerg")
        old = getattr(before, name)
        step = maybe_climb(state, "Zerg")
        self.assertIsNotNone(step)
        self.assertEqual(step[0], name)
        self.assertEqual(step[2], old - meta["step"])  # direction 初值+1 → 反向=-1
        # override 落进 state,params_for 可见
        self.assertEqual(getattr(params_for(state, "Zerg"), name),
                         old - meta["step"])

    def test_climb_rotates_param(self):
        """连续退步轮换到下一个参数,不在单个参数上震荡。"""
        state = self._losing_state(wins=0)
        first = maybe_climb(state, "Zerg")[0]
        # 再喂 5 局全负,触发第二次
        for _ in range(WINDOW):
            append_record(state, _rec(race="Zerg", result="loss"))
        second = maybe_climb(state, "Zerg")[0]
        self.assertEqual(first, CLIMB_ORDER[0])
        self.assertEqual(second, CLIMB_ORDER[1])

    def test_climb_clamps_at_bounds(self):
        """步进顶到 lo/hi 边界就钳住(等于没走 → 只轮换不报步)。"""
        state = self._losing_state(wins=0)
        name = CLIMB_ORDER[0]
        meta = PARAMS[name]
        state["overrides"] = {"zerg": {name: meta["lo"]}}
        # 反向(-1)已经贴着 lo → 步进被钳 → None,但轮换指针前进
        self.assertIsNone(maybe_climb(state, "Zerg"))
        self.assertEqual(state["overrides"]["zerg"][name], meta["lo"])
        self.assertEqual(state["climb"]["zerg"]["idx"], 1)

    def test_direction_flips_back(self):
        """第二次退步沿用上次方向的反向 = 退回原方向(进档/退档往复)。"""
        state = self._losing_state(wins=0)
        maybe_climb(state, "Zerg")  # direction: +1 → -1
        self.assertEqual(state["climb"]["zerg"]["direction"], -1)
        for _ in range(WINDOW):
            append_record(state, _rec(race="Zerg", result="loss"))
        step = maybe_climb(state, "Zerg")
        # 第二参数,方向 = -(-1) = +1
        self.assertEqual(state["climb"]["zerg"]["direction"], 1)
        name = CLIMB_ORDER[1]
        old_static = getattr(SelfTuneParams(), name)
        self.assertEqual(step[2], old_static + PARAMS[name]["step"])

    def test_int_param_step_stays_int(self):
        """int 参数步进后仍是 int(blink_when_swarmed 在 CLIMB_ORDER 里)。"""
        idx = CLIMB_ORDER.index("blink_when_swarmed")
        state = self._losing_state(wins=0)
        state["climb"] = {"zerg": {"idx": idx, "direction": 1}}
        step = maybe_climb(state, "Zerg")
        self.assertIsInstance(step[2], int)


if __name__ == "__main__":
    unittest.main()
