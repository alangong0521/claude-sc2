"""策略 pivot 接线单测 —— _pivot_tempest_mode 的 True/False 分支。

P0 背景:E10 bench 唯一 verdict=greedy 的局(macro g03)因
`carrier_transition_ready` 漏 import 在 pivot 判定第一帧 NameError 崩溃——
纯函数层测试测的是函数本身,挡不住接线层遗漏。本测试直接构造 manager
走一遍接线分支(含 import 完整性)。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_strategy_pivot -v
"""
import os
import sys
import unittest
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
# bot 依赖 ares(本地子包),与 run.py 同样手动补 sys.path
sys.path[:0] = [
    os.path.join(_ROOT, "ares-sc2", "src", "ares"),
    os.path.join(_ROOT, "ares-sc2", "src"),
    os.path.join(_ROOT, "ares-sc2"),
    _ROOT,
]

from bot.managers.production_manager import ProductionManager  # noqa: E402


def _pm(verdict, flow_name="carrier", time=200.0, tempest_count=0,
        transitioned=False):
    """不走 ares Manager.__init__,直接构造最小可用实例。"""
    pm = ProductionManager.__new__(ProductionManager)
    pm._flow = SimpleNamespace(name=flow_name)
    pm._pivot_transitioned = transitioned
    pm._verdict = verdict
    pm.manager_mediator = SimpleNamespace(
        get_own_unit_count=lambda unit_type_id: tempest_count
    )
    pm.ai = SimpleNamespace(time=time, _events=[])
    return pm


class TestPivotTempestModeWiring(unittest.TestCase):
    """_pivot_tempest_mode:verdict 四态 + 转型 latch + carrier 门。"""

    def test_greedy_enters_tempest_mode(self):
        pm = _pm("greedy")
        self.assertTrue(pm._pivot_tempest_mode())
        self.assertFalse(pm._pivot_transitioned)

    def test_rush_unknown_none_stay_out(self):
        for verdict in ("rush", "unknown", None):
            self.assertFalse(_pm(verdict)._pivot_tempest_mode(), verdict)

    def test_non_carrier_flow_never_pivots(self):
        self.assertFalse(_pm("greedy", flow_name="stalker")._pivot_tempest_mode())

    def test_transition_latches_and_logs_event(self):
        # 时间到转型点(600s) → 返回 False、latch 置位、记事件,且之后恒 False
        pm = _pm("greedy", time=650.0)
        self.assertFalse(pm._pivot_tempest_mode())
        self.assertTrue(pm._pivot_transitioned)
        self.assertTrue(any("E10" in e["msg"] for e in pm.ai._events))
        self.assertFalse(pm._pivot_tempest_mode())  # 数量回落也不横跳

    def test_transition_by_fleet_count(self):
        pm = _pm("greedy", time=450.0, tempest_count=10)
        self.assertFalse(pm._pivot_tempest_mode())
        self.assertTrue(pm._pivot_transitioned)


if __name__ == "__main__":
    unittest.main(verbosity=2)
