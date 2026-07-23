"""warp_prism_offensive.py 纯逻辑单测(B9 接残血打分 / 相位条件 / 悬停选点)—— 不起游戏。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_warp_prism_offensive -v

只覆盖抽出来的纯函数(rescue_score / is_rescue_candidate / should_phase_morph /
should_phase_exit / pick_hover_point);折跃门冷却记账、网格采样等运行时逻辑
未跑局验证,不在本测试范围。模块本身 import ares,先把 vendor 的 ares-sc2 加进 sys.path。
"""
import os
import sys
import unittest

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)
sys.path.insert(0, os.path.join(_ROOT, "ares-sc2"))
sys.path.insert(0, os.path.join(_ROOT, "ares-sc2", "src"))

import bot.compat_patch  # noqa: F401, E402  与运行时一致的枚举兼容补丁

from bot.combat.warp_prism_offensive import (  # noqa: E402
    is_rescue_candidate,
    pick_hover_point,
    rescue_score,
    should_phase_exit,
    should_phase_morph,
)


class TestRescueScore(unittest.TestCase):
    def test_formula(self):
        # score = 射程×(1.1−血量%)×战力−1
        self.assertAlmostEqual(rescue_score(0.5, 6.0, 10.0), 6.0 * 0.6 * 10.0 - 1)

    def test_full_hp_negative(self):
        # 满血:1.1−1.0=0.1,低战力直接负分 → 不接
        self.assertLess(rescue_score(1.0, 3.0, 1.0), 0)

    def test_lower_hp_scores_higher(self):
        # 同射程同战力,血越少分越高(优先救更残的)
        self.assertGreater(
            rescue_score(0.2, 6.0, 10.0), rescue_score(0.8, 6.0, 10.0)
        )


class TestIsRescueCandidate(unittest.TestCase):
    def test_basic_ok(self):
        # 盾空 + 武器冷却中 + 12 格内 → 接
        self.assertTrue(is_rescue_candidate(0, 5, 10.0, "STALKER"))

    def test_shield_up_rejected(self):
        self.assertFalse(is_rescue_candidate(1, 5, 10.0, "STALKER"))

    def test_weapon_ready_rejected(self):
        # 武器冷却 ≤2(还在输出)不接
        self.assertFalse(is_rescue_candidate(0, 2, 10.0, "STALKER"))
        self.assertFalse(is_rescue_candidate(0, 0, 10.0, "STALKER"))

    def test_too_far_rejected(self):
        self.assertFalse(is_rescue_candidate(0, 5, 12.5, "STALKER"))

    def test_zealot_enemy_in_range_rejected(self):
        # 叉子有敌在射程内 → 不接(抗线是本职)
        self.assertFalse(is_rescue_candidate(0, 5, 10.0, "ZEALOT", enemy_in_range=True))
        # 没敌贴着 → 可以接
        self.assertTrue(is_rescue_candidate(0, 5, 10.0, "ZEALOT", enemy_in_range=False))


class TestShouldPhaseMorph(unittest.TestCase):
    def test_all_conditions_met(self):
        self.assertTrue(
            should_phase_morph(True, False, True, False, 100)
        )

    def test_each_condition_vetoed(self):
        base = dict(
            shield_full=True, threat_near=False, warpgate_soon=True,
            field_nearby=False, supply_used=100,
        )
        for key, val in [
            ("shield_full", False),   # 盾不满
            ("threat_near", True),    # 附近有敌
            ("warpgate_soon", False), # 没门快转好
            ("field_nearby", True),   # 已有能量场
            ("supply_used", 198),     # 人口满
        ]:
            kw = dict(base, **{key: val})
            self.assertFalse(should_phase_morph(**kw), msg=key)


class TestShouldPhaseExit(unittest.TestCase):
    def test_low_shield_with_enemy(self):
        self.assertTrue(should_phase_exit(0.5, True, True))

    def test_low_shield_no_enemy_stays(self):
        # 盾低但没敌人 → 不撤(没人打得到相位棱镜)
        self.assertFalse(should_phase_exit(0.5, False, True))

    def test_field_not_needed(self):
        self.assertTrue(should_phase_exit(1.0, False, False))

    def test_full_shield_enemy_field_needed_stays(self):
        self.assertFalse(should_phase_exit(1.0, True, True))


class TestPickHoverPoint(unittest.TestCase):
    def test_picks_min_influence(self):
        candidates = [(0, 0), (4, 0), (-4, 0)]
        values = [10.0, 2.0, 5.0]
        self.assertEqual(pick_hover_point((0, 0), candidates, values), (4, 0))

    def test_unreadable_skipped(self):
        candidates = [(0, 0), (4, 0)]
        values = [None, 5.0]
        self.assertEqual(pick_hover_point((0, 0), candidates, values), (4, 0))

    def test_all_unreadable_falls_back_to_anchor(self):
        self.assertEqual(pick_hover_point((1, 1), [(0, 0)], [None]), (1, 1))


if __name__ == "__main__":
    unittest.main()
