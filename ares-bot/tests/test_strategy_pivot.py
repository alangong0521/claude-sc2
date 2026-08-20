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
        transitioned=False, opp_race="", fb_completed_at=None):
    """不走 ares Manager.__init__,直接构造最小可用实例。"""
    pm = ProductionManager.__new__(ProductionManager)
    pm._flow = SimpleNamespace(name=flow_name)
    pm._pivot_transitioned = transitioned
    pm._verdict = verdict
    # O374-④a:坦克首现 latch(__init__ 初始化的实例属性,fake 同补)
    pm._o374_tank_seen = False
    # O377-②:E10 时间盒输入(__init__ 初始化的实例属性,fake 同补)
    pm._opp_race = opp_race
    pm._fb_completed_at = fb_completed_at
    pm.manager_mediator = SimpleNamespace(
        get_own_unit_count=lambda unit_type_id: tempest_count
    )
    pm.ai = SimpleNamespace(
        time=time,
        _events=[],
        enemy_race=None,
        enemy_units=[],
        calculate_supply_cost=lambda type_id: 2.0,
    )
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

    def test_terran_time_box_hard_transition(self):
        # O377-②(o376a 三局 0/3 尸检):vs Terran 480s 硬转 —— 无坦克
        # 首现、敌情 0、未到 600s 也转(等坦克 = 首航母 498-671 vs
        # 配方 454 实证);latch 置位记事件
        pm = _pm("greedy", time=480.0, opp_race="terran")
        self.assertFalse(pm._pivot_tempest_mode())
        self.assertTrue(pm._pivot_transitioned)
        self.assertTrue(any("E10" in e["msg"] for e in pm.ai._events))

    def test_terran_time_box_fb_delay(self):
        # O377-②:FB 落成 +150s 先到先转(300+150=450 <480 硬顶)
        pm = _pm("greedy", time=450.0, opp_race="terran", fb_completed_at=300.0)
        self.assertFalse(pm._pivot_tempest_mode())
        self.assertTrue(pm._pivot_transitioned)
        # FB+150 未到且 <480 → 不转(时间盒三态之「留」)
        pm2 = _pm("greedy", time=449.9, opp_race="terran", fb_completed_at=300.0)
        self.assertTrue(pm2._pivot_tempest_mode())
        self.assertFalse(pm2._pivot_transitioned)

    def test_time_box_never_fires_off_terran(self):
        # O377-②:zerg/空 race 一行不动 —— 480s 不硬转(等 600s 原判据)
        for race in ("zerg", "protoss", ""):
            pm = _pm("greedy", time=480.0, opp_race=race)
            self.assertTrue(pm._pivot_tempest_mode(), race)
            self.assertFalse(pm._pivot_transitioned, race)


if __name__ == "__main__":
    unittest.main(verbosity=2)
