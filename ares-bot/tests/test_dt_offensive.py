"""dt_offensive.py 纯逻辑单测(B5 矿线聚类 / 换矿选点)—— 不起游戏。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_dt_offensive -v

只覆盖抽出来的纯函数(cluster_mineral_lines / pick_next_harass_target);
三条换矿规则的距离判定在 execute 里,未跑局验证,不在本测试范围。
模块本身 import ares,所以要把 vendor 的 ares-sc2 加进 sys.path。
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "ares-sc2"))
sys.path.insert(0, os.path.join(_ROOT, "ares-sc2", "src"))

import bot.compat_patch  # noqa: F401, E402  与运行时一致的枚举兼容补丁

from bot.combat.dt_offensive import (  # noqa: E402
    cluster_mineral_lines,
    pick_next_harass_target,
)


class TestClusterMineralLines(unittest.TestCase):
    def test_single_base_centroid(self):
        # 基地 (0,0),两个矿点 (-1, 0)/(1, 0) → 矿线中心 (0, 0)
        lines = cluster_mineral_lines([(0, 0)], [(-1, 0), (1, 0)])
        self.assertEqual(len(lines), 1)
        self.assertAlmostEqual(lines[0][0], 0.0)
        self.assertAlmostEqual(lines[0][1], 0.0)

    def test_two_bases_split(self):
        # 两个基地各自的矿点各归各簇,互不串味
        minerals = [(-9, 0), (-8, 0), (8, 0), (9, 0)]
        lines = cluster_mineral_lines([(-10, 0), (10, 0)], minerals)
        self.assertEqual(len(lines), 2)
        self.assertAlmostEqual(lines[0][0], -8.5)
        self.assertAlmostEqual(lines[1][0], 8.5)

    def test_base_without_minerals_skipped(self):
        # 被打掉的基地(10 格内没矿)不进候选
        lines = cluster_mineral_lines([(0, 0), (100, 100)], [(1, 1)])
        self.assertEqual(len(lines), 1)

    def test_mineral_out_of_radius_ignored(self):
        # 11 格外的矿不算这个基地的
        lines = cluster_mineral_lines([(0, 0)], [(11, 0)])
        self.assertEqual(lines, [])


class TestPickNextHarassTarget(unittest.TestCase):
    def test_first_pick_nearest(self):
        # 初次选矿(current=None):挑离 DT 最近、没被 block 的
        nxt = pick_next_harass_target(
            (0, 0), None, [(5, 0), (1, 0), (9, 0)], [False, False, False]
        )
        self.assertEqual(nxt, (1, 0))

    def test_blocked_skipped(self):
        nxt = pick_next_harass_target((0, 0), None, [(1, 0), (5, 0)], [True, False])
        self.assertEqual(nxt, (5, 0))

    def test_never_repick_current(self):
        # 换矿不能换回原地:最近的没 block 点就是 current → 换次近的
        nxt = pick_next_harass_target(
            (0, 0), (1, 0), [(1, 0), (4, 0)], [False, False]
        )
        self.assertEqual(nxt, (4, 0))

    def test_all_blocked_returns_none(self):
        nxt = pick_next_harass_target((0, 0), None, [(1, 0)], [True])
        self.assertIsNone(nxt)

    def test_only_current_available_returns_none(self):
        # 唯一的矿就是当前矿(被 block 了)→ None,回退 attack_target
        nxt = pick_next_harass_target((0, 0), (1, 0), [(1, 0)], [True])
        self.assertIsNone(nxt)


if __name__ == "__main__":
    unittest.main()
