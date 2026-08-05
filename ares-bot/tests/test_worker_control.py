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

from bot.main import (  # noqa: E402
    recall_pivot_scout_after_intel,
    recall_scouting_workers,
    release_from_build_tracker,
)


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


class TestRecallPivotScoutAfterIntel(unittest.TestCase):
    """O35 修复(司令观察):tempest/stalker 的 pivot 早侦查探机看到敌建筑
    (情报送达)后立刻撤回,不再留在敌家等小狗孵化白送。carrier 走 O9,不动。"""

    @staticmethod
    def _fake_ai(flow="tempest", scout_tag=42, intel=True, scout_role=UnitRole.SCOUTING):
        assigned: list[tuple[int, object]] = []
        moved: list[object] = []
        scout = SimpleNamespace(tag=scout_tag) if scout_role is not None else None
        if scout is not None:
            scout.move = lambda target: moved.append(target)
        pm = SimpleNamespace(
            _flow=SimpleNamespace(name=flow),
            _pivot_scout_tag=scout_tag,
        )
        roles = {scout_tag: scout_role}
        ai = SimpleNamespace(
            production_manager=pm,
            enemy_structures=["SPAWNINGPOOL"] if intel else [],
            units=SimpleNamespace(find_by_tag=lambda tag: scout),
            mediator=SimpleNamespace(
                assign_role=lambda tag, role: assigned.append((tag, role))
            ),
            _current_role=lambda tag: roles.get(tag),
            ready_townhalls=None,  # home_mineral 返回 None → 回退 move(start_location)
            mineral_field=None,
            start_location="home",
        )
        return ai, pm, assigned, moved

    def test_tempest_scout_recalled_after_intel(self):
        ai, pm, assigned, moved = self._fake_ai()
        self.assertTrue(recall_pivot_scout_after_intel(ai))
        self.assertEqual(assigned, [(42, UnitRole.GATHERING)])
        self.assertEqual(moved, ["home"])  # 回家,不是留在敌家
        self.assertIsNone(pm._pivot_scout_tag)

    def test_no_intel_yet_is_noop(self):
        ai, pm, assigned, moved = self._fake_ai(intel=False)
        self.assertFalse(recall_pivot_scout_after_intel(ai))
        self.assertEqual(assigned, [])
        self.assertEqual(pm._pivot_scout_tag, 42)  # tag 保留,继续探

    def test_carrier_flow_untouched(self):
        # carrier 走 O9 评估撤回(已验证基线),O35 不插手
        ai, pm, assigned, moved = self._fake_ai(flow="carrier")
        self.assertFalse(recall_pivot_scout_after_intel(ai))
        self.assertEqual(assigned, [])
        self.assertEqual(pm._pivot_scout_tag, 42)

    def test_dead_scout_clears_tag_without_crash(self):
        ai, pm, assigned, moved = self._fake_ai(scout_role=None)
        self.assertFalse(recall_pivot_scout_after_intel(ai))
        self.assertEqual(assigned, [])
        self.assertIsNone(pm._pivot_scout_tag)

    def test_already_recalled_by_o4_not_double_ordered(self):
        # O4 rush 撤回先把 role 归了 GATHERING → 只清 tag,不重复下令
        ai, pm, assigned, moved = self._fake_ai(scout_role=UnitRole.GATHERING)
        self.assertFalse(recall_pivot_scout_after_intel(ai))
        self.assertEqual(assigned, [])
        self.assertEqual(moved, [])
        self.assertIsNone(pm._pivot_scout_tag)


if __name__ == "__main__":
    unittest.main(verbosity=2)
