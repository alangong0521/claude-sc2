"""production_plans.py 纯逻辑单测 —— 种族无关的农民/气目标计算,不起游戏。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_production_plans -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.production_plans import gas_target, worker_target  # noqa: E402


class TestWorkerTarget(unittest.TestCase):
    def test_single_base_matches_old_behavior(self):
        self.assertEqual(worker_target(1), 22)  # 与旧 Protoss _build_probes 一致

    def test_scales_with_bases(self):
        self.assertEqual(worker_target(2), 44)
        self.assertEqual(worker_target(3), 66)

    def test_caps(self):
        self.assertEqual(worker_target(4), 70)   # 88 封顶到 70
        self.assertEqual(worker_target(10), 70)

    def test_zero_or_negative(self):
        self.assertEqual(worker_target(0), 0)
        self.assertEqual(worker_target(-1), 0)

    def test_custom_params(self):
        self.assertEqual(worker_target(2, per_base=16, cap=100), 32)


class TestGasTarget(unittest.TestCase):
    def test_opener_single_gas_before_production(self):
        # 没军事建筑 → 只开 1 个气(保起手节奏)
        self.assertEqual(gas_target(1, has_production=False), 1)
        self.assertEqual(gas_target(3, has_production=False), 1)

    def test_double_gas_per_base_after_production(self):
        self.assertEqual(gas_target(1, has_production=True), 2)
        self.assertEqual(gas_target(2, has_production=True), 4)

    def test_zero_townhalls(self):
        self.assertEqual(gas_target(0, has_production=True), 0)
        self.assertEqual(gas_target(-2, has_production=False), 0)

    def test_custom_params(self):
        self.assertEqual(gas_target(2, has_production=True, per_base=3), 6)
        self.assertEqual(gas_target(2, has_production=False, opener=2), 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
