"""carrier_logic.py 纯逻辑单测 —— 不起游戏(O12 锚点评分 / O14 残血判定)。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_carrier_logic -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.combat.carrier_logic import (  # noqa: E402
    anchor_score,
    best_anchor,
    is_wounded,
    wounded_state,
)


def _cand(name, dist=8.0, ideal=8.0, height_diff=False, aa=0):
    return {
        "point": name,
        "dist": dist,
        "ideal": ideal,
        "height_diff": height_diff,
        "aa": aa,
    }


class TestIsWounded(unittest.TestCase):
    """O14:盾+血 <40% → 残血后撤(三态)。"""

    def test_below_threshold_wounded(self):
        self.assertTrue(is_wounded(0.39))

    def test_boundary_not_wounded(self):
        self.assertFalse(is_wounded(0.4))  # 语义是 <40%

    def test_healthy_not_wounded(self):
        self.assertFalse(is_wounded(0.99))


class TestAnchorScore(unittest.TestCase):
    """O12 锚点评分:距离贴合 / 悬崖加分 / 防空降权。"""

    def test_cliff_beats_flat(self):
        cliff = anchor_score(
            dist_to_target=8, ideal_dist=8, height_diff=True, aa_threats=0
        )
        flat = anchor_score(
            dist_to_target=8, ideal_dist=8, height_diff=False, aa_threats=0
        )
        self.assertGreater(cliff, flat)

    def test_aa_penalty(self):
        safe = anchor_score(
            dist_to_target=8, ideal_dist=8, height_diff=False, aa_threats=0
        )
        risky = anchor_score(
            dist_to_target=8, ideal_dist=8, height_diff=False, aa_threats=1
        )
        self.assertEqual(safe - risky, 4.0)

    def test_off_ideal_distance_penalized(self):
        on = anchor_score(
            dist_to_target=8, ideal_dist=8, height_diff=False, aa_threats=0
        )
        off = anchor_score(
            dist_to_target=3, ideal_dist=8, height_diff=False, aa_threats=0
        )
        self.assertGreater(on, off)


class TestBestAnchor(unittest.TestCase):
    """选址排序:悬崖 > 保守平地;防空点被避开;首位=保守退路;空表 None。"""

    def test_cliff_wins_over_aa_flat(self):
        out = best_anchor([
            _cand("flat_safe"),
            _cand("cliff", height_diff=True),
            _cand("flat_aa", aa=2),
        ])
        self.assertEqual(out["point"], "cliff")

    def test_tie_picks_first_fallback(self):
        # 全平无防空 → 同分 → 取候选首位(调用方放的保守退路)
        out = best_anchor([_cand("fallback"), _cand("other"), _cand("third")])
        self.assertEqual(out["point"], "fallback")

    def test_cliff_loses_to_safe_when_heavy_aa(self):
        # 悬崖点上蹲着 1 个防空(-4) → 不如平地安全点
        out = best_anchor([
            _cand("flat_safe"),
            _cand("cliff_risky", height_diff=True, aa=1),
        ])
        self.assertEqual(out["point"], "flat_safe")

    def test_empty_returns_none(self):
        self.assertIsNone(best_anchor([]))


class TestWoundedState(unittest.TestCase):
    """O14 残血滞回:<40% 进,≥55% 出,中间带保持(防盾回充乒乓)。"""

    def test_enter_below_threshold(self):
        self.assertTrue(wounded_state(0.39, False))

    def test_exit_at_recover(self):
        self.assertFalse(wounded_state(0.55, True))

    def test_hysteresis_band_holds_state(self):
        # 40%-55% 之间:残血的保持残血,健康的保持健康(不乒乓)
        self.assertTrue(wounded_state(0.48, True))
        self.assertFalse(wounded_state(0.48, False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
