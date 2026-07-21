"""bot/main.py 人机共驾辅助逻辑单测 —— 不起游戏,用假 mediator 验证记账操作。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_worker_control -v
"""
import os
import sys
import unittest
from collections import defaultdict
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
# bot.main 依赖 ares(本地子包),与 run.py 同样手动补 sys.path
sys.path[:0] = [
    os.path.join(_ROOT, "ares-sc2", "src", "ares"),
    os.path.join(_ROOT, "ares-sc2", "src"),
    os.path.join(_ROOT, "ares-sc2"),
    _ROOT,
]

from ares.consts import ID as TRACKER_ID  # noqa: E402
from ares.consts import UnitRole  # noqa: E402
from sc2.ids.unit_typeid import UnitTypeId as UnitID  # noqa: E402

from bot.main import recall_scouting_workers, release_from_build_tracker  # noqa: E402


def _fake_mediator(tracker: dict, counter) -> SimpleNamespace:
    # ares 的 get_building_tracker_dict / get_building_counter 是 property,
    # 返回 BuildingManager 的 live 字典;SimpleNamespace 属性即等价物
    return SimpleNamespace(
        get_building_tracker_dict=tracker,
        get_building_counter=counter,
    )


class TestReleaseFromBuildTracker(unittest.TestCase):
    """O2 修复:司令接管的工人必须从 ares building_tracker 摘除,否则
    BuildingManager 每帧无视 role 继续给它下 move/build 命令。"""

    def test_tracked_worker_is_released_and_counter_decremented(self):
        tracker = {123: {TRACKER_ID: UnitID.FORGE, "target": None}}
        counter = defaultdict(int, {UnitID.FORGE: 1})
        med = _fake_mediator(tracker, counter)

        self.assertTrue(release_from_build_tracker(med, 123))
        self.assertNotIn(123, tracker)
        self.assertEqual(counter[UnitID.FORGE], 0)

    def test_untracked_worker_is_noop(self):
        tracker = {123: {TRACKER_ID: UnitID.FORGE, "target": None}}
        counter = defaultdict(int, {UnitID.FORGE: 1})
        med = _fake_mediator(tracker, counter)

        self.assertFalse(release_from_build_tracker(med, 999))
        self.assertIn(123, tracker)  # 别人的建造任务不受影响
        self.assertEqual(counter[UnitID.FORGE], 1)

    def test_empty_tracker_is_noop(self):
        med = _fake_mediator({}, defaultdict(int))
        self.assertFalse(release_from_build_tracker(med, 123))


class TestRecallScoutingWorkers(unittest.TestCase):
    """O4 修复:rush 确认后 SCOUTING role 的农民立刻归 GATHERING 并回矿。"""

    @staticmethod
    def _fake_ai(scouts, with_minerals=True):
        assigned: list[tuple[int, object]] = []
        gathered: list[int] = []
        mineral = SimpleNamespace(closest_to=lambda u: f"mf@{u.tag}")
        mediator = SimpleNamespace(
            get_units_from_role=lambda role: scouts,
            assign_role=lambda tag, role: assigned.append((tag, role)),
        )
        for s in scouts:
            s.gather = lambda target, _tag=s.tag: gathered.append(_tag)
        return (
            SimpleNamespace(
                mediator=mediator,
                mineral_field=mineral if with_minerals else None,
            ),
            assigned,
            gathered,
        )

    def test_scouts_recalled_to_gathering(self):
        scouts = [SimpleNamespace(tag=11), SimpleNamespace(tag=22)]
        ai, assigned, gathered = self._fake_ai(scouts)

        self.assertEqual(recall_scouting_workers(ai), 2)
        self.assertEqual(
            assigned, [(11, UnitRole.GATHERING), (22, UnitRole.GATHERING)]
        )
        self.assertEqual(gathered, [11, 22])  # 都拿到了回矿命令

    def test_no_scouts_returns_zero_and_noop(self):
        ai, assigned, gathered = self._fake_ai([])
        self.assertEqual(recall_scouting_workers(ai), 0)
        self.assertEqual(assigned, [])
        self.assertEqual(gathered, [])

    def test_no_minerals_still_reassigns_role(self):
        scouts = [SimpleNamespace(tag=33)]
        ai, assigned, gathered = self._fake_ai(scouts, with_minerals=False)
        self.assertEqual(recall_scouting_workers(ai), 1)
        self.assertEqual(assigned, [(33, UnitRole.GATHERING)])
        self.assertEqual(gathered, [])  # 没矿可回也不崩


if __name__ == "__main__":
    unittest.main(verbosity=2)
