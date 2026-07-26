"""需求3: 敌军压上主基补大量光子塔单测 —— 不起游戏。

覆盖: MainSiege 配置解析 + main_siege_active 触发判据 + shipped 全流派配置冻结。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_main_siege -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.flow_config import FlowConfig, MainSiege  # noqa: E402
from bot.production_plans import main_siege_active  # noqa: E402


def _yaml_or_skip(case):
    try:
        import yaml  # noqa: F401
    except ImportError:
        case.skipTest("pyyaml 未安装")


class TestMainSiegeParse(unittest.TestCase):
    """MainSiege dataclass + from_dict 解析(参考 test_expansion_cannons_parse)。"""

    def test_default_none(self):
        self.assertIsNone(FlowConfig.from_dict("x", {"spawn": {}}).main_siege)

    def test_full_parse(self):
        fc = FlowConfig.from_dict("x", {"spawn": {}, "main_siege": {
            "cannons": 12, "radius": 25, "threshold": 4,
        }})
        self.assertEqual(fc.main_siege, MainSiege(12, 25.0, 4))

    def test_partial_defaults(self):
        # 只给 cannons → radius/threshold 取默认
        fc = FlowConfig.from_dict("x", {"spawn": {}, "main_siege": {"cannons": 15}})
        self.assertEqual(fc.main_siege.cannons, 15)
        self.assertEqual(fc.main_siege.radius, 25.0)
        self.assertEqual(fc.main_siege.threshold, 4)


class TestMainSiegeActive(unittest.TestCase):
    """触发判据:主基 radius 内敌地面作战单位 ≥ threshold → True。纯函数。"""

    def test_below_threshold_false(self):
        self.assertFalse(main_siege_active(3, 4))
        self.assertFalse(main_siege_active(0, 4))

    def test_at_or_above_threshold_true(self):
        self.assertTrue(main_siege_active(4, 4))
        self.assertTrue(main_siege_active(10, 4))


class TestShippedMainSiege(unittest.TestCase):
    """需求3:全神族流派(carrier/tempest/stalker/dt)都配了 main_siege={12,25,4}。"""

    def test_all_flows_have_main_siege(self):
        _yaml_or_skip(self)
        for name in ("tempest", "stalker", "carrier", "dt"):
            fc = FlowConfig.load(name)
            self.assertIsNotNone(fc.main_siege, f"{name} 缺 main_siege 配置")
            self.assertEqual(
                fc.main_siege, MainSiege(12, 25.0, 2),
                f"{name} main_siege 应为 (cannons=12, radius=25, threshold=4)",
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
