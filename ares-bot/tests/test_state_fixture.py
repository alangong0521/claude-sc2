"""C1·state fixture 离线回放 —— 证明不开游戏也能拿 state.json 喂给参谋逻辑测试。

真实 fixture 靠 `STEER_RECORD=<dir> ... run.py` 跑一局录制;在没有游戏时,仓库里
先放一份手写的代表性快照(state_mid_1v1.json,中局 1v1,对面转凤凰),让 L4 的
state 解析/简报逻辑现在就能离线单测。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_state_fixture -v
"""
import json
import os
import unittest
from pathlib import Path

FIXTURES = Path(__file__).resolve().parent / "fixtures"


def load_fixture(name: str) -> dict:
    """读一份 state fixture(离线回放入口)。参谋侧离线测试都走它拿快照。"""
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


def summarize_threats(state: dict) -> list[str]:
    """从 state 抽\"威胁要点\"—— 参谋简报的可离线测试的骨架示例。

    这是纯逻辑:给定 state dict 输出人类可读威胁行,不碰游戏。真正的参谋简报比这丰富,
    但把\"从 enemies[]/events[] 提取要点\"抽成纯函数后,就能对着 fixture 断言,不必开游戏。
    """
    out: list[str] = []
    for e in state.get("enemies", []):
        vis = e.get("visible", {})
        army = vis.get("army", {})
        structs = vis.get("structures", {})
        # 转空军预警(暴风舰死穴=凤凰)
        if "PHOENIX" in army or "STARGATE" in structs:
            out.append(f"{e['id']} 有星门/凤凰迹象 → 预警转空军(克暴风舰)")
        if army:
            out.append(f"{e['id']} 可见部队: " +
                       ", ".join(f"{k}x{v}" for k, v in army.items()))
    return out


class TestFixtureLoads(unittest.TestCase):
    def test_shape(self):
        s = load_fixture("state_mid_1v1.json")
        for key in ("time", "minerals", "supply", "workers", "bases",
                    "army", "enemies", "events", "order"):
            self.assertIn(key, s)
        self.assertEqual(len(s["enemies"]), 1)  # 1v1

    def test_threat_summary_pure_logic(self):
        s = load_fixture("state_mid_1v1.json")
        threats = summarize_threats(s)
        # 对面有 STARGATE + PHOENIX → 必须给出转空军预警
        self.assertTrue(any("转空军" in t for t in threats),
                        f"应预警转空军,得到: {threats}")

    def test_visible_vs_remembered_split(self):
        # 参谋须分清\"实时可见 vs 记忆\";fixture 两者都有,断言结构在
        e = load_fixture("state_mid_1v1.json")["enemies"][0]
        self.assertIn("STARGATE", e["visible"]["structures"])   # 此刻看得到
        self.assertIn("GATEWAY", e["remembered"]["structures"])  # 迷雾里的记忆


class TestRecordedDirReplay(unittest.TestCase):
    """若设了 STEER_REPLAY_DIR(真实录制目录),逐帧回放 summarize_threats 不崩。"""
    def test_replay_recorded_if_present(self):
        d = os.environ.get("STEER_REPLAY_DIR")
        if not d or not Path(d).is_dir():
            self.skipTest("未提供 STEER_REPLAY_DIR 录制目录")
        frames = sorted(Path(d).glob("state_*.json"))
        self.assertTrue(frames, "录制目录里没有 state_*.json")
        for f in frames:
            state = json.loads(f.read_text(encoding="utf-8"))
            summarize_threats(state)  # 不抛异常即通过


if __name__ == "__main__":
    unittest.main(verbosity=2)
