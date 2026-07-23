"""B4 防守三角 / B7 运营队列 纯逻辑单测(2026-07,来源:sharpy/QueenBot/12PoolBot)。

覆盖 production_plans.py 新增判据:防守集结点/被攻击基地选择/停气/取消建筑白名单/
存款补产能/扩张 max_pending;外加 B7① 花钱优先级固化测试(AutoSupply 严格第一)。
跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_b4_b7_plans -v
"""
import os
import re
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.production_plans import (  # noqa: E402
    RUSH_CANCELLABLE_TECH,
    bank_production_target,
    defensive_rally_point,
    expansion_max_pending,
    rush_cancellable_structure,
    rush_defend_base,
    rush_stops_gas,
)


class TestDefensiveRallyPoint(unittest.TestCase):
    """B4①(sharpy PlanHeatDefender):防守集结点 = 坡口顶端朝坡底反方向 4 格。"""

    def test_vertical_ramp(self):
        # 坡底在坡顶正下方 → 集结点 = 坡顶正上方 4 格(坡后高地)
        self.assertEqual(
            defensive_rally_point((10.0, 10.0), (10.0, 0.0)), (10.0, 14.0)
        )

    def test_horizontal_ramp(self):
        self.assertEqual(
            defensive_rally_point((10.0, 10.0), (0.0, 10.0)), (14.0, 10.0)
        )

    def test_diagonal_ramp(self):
        x, y = defensive_rally_point((3.0, 4.0), (0.0, 0.0))
        self.assertAlmostEqual(x, 3.0 + 3.0 / 5.0 * 4.0)
        self.assertAlmostEqual(y, 4.0 + 4.0 / 5.0 * 4.0)

    def test_custom_offset(self):
        self.assertEqual(
            defensive_rally_point((10.0, 10.0), (10.0, 0.0), offset=6.0),
            (10.0, 16.0),
        )

    def test_degenerate_same_point(self):
        # top==bottom(退化)→ 原样返回 top,不除零
        self.assertEqual(defensive_rally_point((5.0, 5.0), (5.0, 5.0)), (5.0, 5.0))


class TestRushDefendBase(unittest.TestCase):
    """B4②(sharpy 防御性折跃):被攻击基地 = 敌地面单位最多的分矿;主基/无威胁 → None。"""

    MAIN = (10.0, 10.0)

    def test_expansion_threatened(self):
        threats = [(10.0, 10.0, 1), (50.0, 50.0, 5)]  # 分矿 5 敌 > 主基 1 敌
        self.assertEqual(rush_defend_base(threats, self.MAIN), (50.0, 50.0))

    def test_main_threatened_returns_none(self):
        threats = [(10.0, 10.0, 8), (50.0, 50.0, 2)]
        self.assertIsNone(rush_defend_base(threats, self.MAIN))

    def test_no_threat_returns_none(self):
        threats = [(10.0, 10.0, 0), (50.0, 50.0, 0)]
        self.assertIsNone(rush_defend_base(threats, self.MAIN))

    def test_tie_prefers_main(self):
        # 计数并列 → 主基优先(None,走坡口集结点)
        threats = [(10.0, 10.0, 3), (50.0, 50.0, 3)]
        self.assertIsNone(rush_defend_base(threats, self.MAIN))

    def test_empty(self):
        self.assertIsNone(rush_defend_base([], self.MAIN))


class TestRushStopsGas(unittest.TestCase):
    """B4③-a(QueenBot 应激清单):rush_active 时停气。"""

    def test_rush_on(self):
        self.assertTrue(rush_stops_gas(True))

    def test_rush_off(self):
        self.assertFalse(rush_stops_gas(False))


class TestRushCancellableStructure(unittest.TestCase):
    """B4③-b(QueenBot 应激清单):极保守白名单 —— 只取消 rush 中未完工的非关键科技。"""

    def test_whitelisted_unfinished_during_rush(self):
        for name in (
            "TWILIGHTCOUNCIL", "ROBOTICSFACILITY", "ROBOTICSBAY",
            "FLEETBEACON", "TEMPLARARCHIVE", "DARKSHRINE",
        ):
            self.assertTrue(rush_cancellable_structure(True, name, False), name)

    def test_defense_chain_never_cancelled(self):
        # 兵营/电池/水晶/炮塔/基地/气矿/FORGE(炮塔前置)/核心链 永远不动
        for name in (
            "GATEWAY", "WARPGATE", "SHIELDBATTERY", "PYLON", "PHOTONCANNON",
            "NEXUS", "ASSIMILATOR", "FORGE", "STARGATE", "CYBERNETICSCORE",
        ):
            self.assertFalse(rush_cancellable_structure(True, name, False), name)
            self.assertNotIn(name, RUSH_CANCELLABLE_TECH)

    def test_ready_building_not_cancelled(self):
        self.assertFalse(rush_cancellable_structure(True, "FLEETBEACON", True))

    def test_no_rush_no_cancel(self):
        self.assertFalse(rush_cancellable_structure(False, "FLEETBEACON", False))


class TestBankProductionTarget(unittest.TestCase):
    """B7②(12PoolBot add_production_at_bank=(400,400)):存款自动补产能。"""

    def test_below_bank_returns_none(self):
        self.assertIsNone(bank_production_target(400, 500, base=1, ready_bases=1))
        self.assertIsNone(bank_production_target(500, 400, base=1, ready_bases=1))
        self.assertIsNone(bank_production_target(100, 100, base=1, ready_bases=1))

    def test_bank_met_scales_with_minerals(self):
        # base+ready=2;矿 500→+0, 900→+1, 1700→+2
        self.assertEqual(bank_production_target(500, 500, base=1, ready_bases=1), 2)
        self.assertEqual(bank_production_target(900, 500, base=1, ready_bases=1), 3)
        self.assertEqual(bank_production_target(1700, 500, base=1, ready_bases=1), 4)

    def test_cap_12(self):
        self.assertEqual(
            bank_production_target(99999, 99999, base=2, ready_bases=4), 12
        )

    def test_custom_bank(self):
        self.assertIsNone(
            bank_production_target(500, 500, base=1, ready_bases=1, bank=(600, 600))
        )


class TestExpansionMaxPending(unittest.TestCase):
    """B7③(QueenBot 扩张动态 max_pending):矿>1250 且有富余 → 多矿同建,否则 1。"""

    def test_normal_is_one(self):
        self.assertEqual(expansion_max_pending(800, headroom=3), 1)
        self.assertEqual(expansion_max_pending(1250, headroom=3), 1)  # 严格大于才触发

    def test_rich_allows_more(self):
        self.assertEqual(expansion_max_pending(1300, headroom=3), 3)

    def test_headroom_clamps(self):
        self.assertEqual(expansion_max_pending(1300, headroom=2), 2)
        self.assertEqual(expansion_max_pending(1300, headroom=1), 1)


class TestMacroPlanPriorityOrder(unittest.TestCase):
    """B7①(QueenBot MacroPlan):AutoSupply(人口)严格第一优先 —— 固化现有顺序。

    现有 production_manager.update 的 MacroPlan 注册顺序已满足(AutoSupply 在最前,
    E3k 把 ExpansionController 排在 UpgradeController 前是实证修复,不重排),
    这里只锁死「第一个 macro_plan.add 必须是 AutoSupply」,防后续改动悄悄把人口
    挤到后面(supply_block 是 bench 头号卡死源之一)。
    """

    def test_autosupply_is_first_plan_entry(self):
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bot", "managers", "production_manager.py",
        )
        with open(path, encoding="utf-8") as f:
            src = f.read()
        # 只看 Protoss update 方法体(到 Terran 分派方法为止)
        body = src[src.index("async def update("):src.index("def _update_terran")]
        adds = re.findall(r"macro_plan\.add\(\s*(\w+)", body)
        self.assertTrue(adds, "update 里应至少有一个 macro_plan.add")
        self.assertEqual(adds[0], "AutoSupply", "AutoSupply 必须是 MacroPlan 第一项")
        # SpawnController(造兵)在 plan 里存在(补人口/产能/升级之外还有兵)
        self.assertIn("SpawnController", adds)


if __name__ == "__main__":
    unittest.main()
