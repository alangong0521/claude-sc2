"""bench.py retro(_postmortem)单测 —— 离线假快照验证 idle_builder 标签
与 one_base 的 flow 感知阈值(O19/E6c2 误报修复)。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_bench_retro -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bench import _postmortem  # noqa: E402


def _snap(t, bases=1, events=(), minerals=100, army=None, supply="10/20"):
    return {
        "time": t,
        "minerals": minerals,
        "vespene": 0,
        "supply": supply,
        "workers": 16,
        "bases": bases,
        "army": army or {},
        "structures": {},
        "upgrades": [],
        "enemies": [{"visible": {"army": {}}, "remembered": {"structures": {}}}],
        "events": [{"t": t, "msg": m} for t, m in events],
        "order": {},
    }


def _write_game(dir_path: Path, snaps: list[dict]) -> None:
    dir_path.mkdir(parents=True, exist_ok=True)
    for s in snaps:
        (dir_path / f"state_{s['time']:010.1f}.json").write_text(
            json.dumps(s, ensure_ascii=False), encoding="utf-8"
        )


class TestIdleBuilderLabel(unittest.TestCase):
    """idle_builder 标签:快照 events 里出现即打标并计数,(t,msg) 去重。"""

    def test_label_counts_unique_episodes(self):
        with tempfile.TemporaryDirectory() as td:
            gd = Path(td)
            ev = [(100.0, "idle_builder: 农民123@45,67 干等2s(等钱造FORGE)")]
            # 同一事件在连续两个快照的滚动窗口里重复出现 → 只计 1 次
            _write_game(gd, [
                _snap(100.0, events=ev),
                _snap(104.0, events=ev),
                _snap(108.0, events=ev + [(108.0, "idle_builder: 农民124@45,67 干等3s(未开工造GATEWAY)")]),
            ])
            issues = _postmortem(gd, {"result": "Victory"})
            self.assertIn("idle_builder(农民干等建造 ×2)", issues)

    def test_no_label_without_idle_builder_events(self):
        with tempfile.TemporaryDirectory() as td:
            gd = Path(td)
            _write_game(gd, [
                _snap(100.0, events=[(100.0, "新基地建成：共 2")]),
                _snap(104.0, bases=2),
            ])
            issues = _postmortem(gd, {"result": "Victory"})
            self.assertFalse(any("idle_builder" in i for i in issues))


class TestOneBaseFlowAwareThreshold(unittest.TestCase):
    """one_base 阈值 flow 感知:carrier 420s(O21 设计如此,E6c2 五连误报修复),
    其他流派保持 300s。"""

    def _one_base_issues(self, flow, snaps):
        with tempfile.TemporaryDirectory() as td:
            gd = Path(td)
            _write_game(gd, snaps)
            return _postmortem(gd, {"result": "Victory"}, flow=flow)

    def test_carrier_two_base_at_390_not_flagged(self):
        # E6c2 典型:357-390s 开出二矿 → carrier 下不再误报
        issues = self._one_base_issues("carrier", [
            _snap(300.0), _snap(390.0, bases=2), _snap(500.0, bases=2),
        ])
        self.assertFalse(any("one_base" in i for i in issues))

    def test_tempest_still_flagged_at_300(self):
        issues = self._one_base_issues("tempest", [
            _snap(300.0), _snap(390.0, bases=2),
        ])
        self.assertIn("one_base(300s 仍单矿)", issues)

    def test_carrier_still_single_at_420_flagged(self):
        issues = self._one_base_issues("carrier", [
            _snap(300.0), _snap(430.0), _snap(500.0),
        ])
        self.assertIn("one_base(420s 仍单矿)", issues)


if __name__ == "__main__":
    unittest.main(verbosity=2)
