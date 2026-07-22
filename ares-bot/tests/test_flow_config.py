"""flow_config.py 纯逻辑单测 —— 不起游戏、不需 sc2(from_dict 路径)。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_flow_config -v

覆盖:三个内置流派加载、未知名回退、spawn 比例校验、chrono.when 校验、
shipped 冻结(tempest/stalker 与已验证行为逐位一致,防手滑改坏)。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.flow_config import (  # noqa: E402
    DEFAULT_FLOW, FlowConfig, _HAS_SC2,
)


def _yaml_or_skip(case):
    try:
        import yaml  # noqa: F401
    except ImportError:
        case.skipTest("pyyaml 未安装")


class TestLoadBuiltinFlows(unittest.TestCase):
    """load() 从真实 flows.yml 读(需 pyyaml)。"""

    def test_default_and_none(self):
        _yaml_or_skip(self)
        self.assertEqual(FlowConfig.load(None).name, DEFAULT_FLOW)
        self.assertEqual(FlowConfig.load("").name, DEFAULT_FLOW)
        self.assertEqual(FlowConfig.load("Tempest").name, "tempest")  # 大小写不敏感

    def test_unknown_falls_back(self):
        _yaml_or_skip(self)
        self.assertEqual(FlowConfig.load("bogus").name, DEFAULT_FLOW)

    def test_all_builtin_load(self):
        _yaml_or_skip(self)
        for name in ("tempest", "stalker", "carrier"):
            fc = FlowConfig.load(name)
            self.assertEqual(fc.name, name)
            self.assertTrue(fc.spawn, f"{name} spawn 为空")
            self.assertTrue(fc.core_structures, f"{name} 科技链为空")


class TestValidation(unittest.TestCase):
    """from_dict 校验(纯逻辑,不读文件)。"""

    def test_spawn_sum_over_one(self):
        with self.assertRaises(ValueError):
            FlowConfig.from_dict("x", {"spawn": {
                "A": {"proportion": 0.7}, "B": {"proportion": 0.5},
            }})

    def test_negative_proportion(self):
        with self.assertRaises(ValueError):
            FlowConfig.from_dict("x", {"spawn": {"A": {"proportion": -0.1}}})

    def test_chrono_when_invalid(self):
        with self.assertRaises(ValueError):
            FlowConfig.from_dict("x", {"spawn": {}, "chrono": {"when": "sometimes"}})

    def test_normalization(self):
        fc = FlowConfig.from_dict("x", {
            "spawn": {"tempest ": {"proportion": 1.0}},
            "core_structures": [" gateway ", "STARGATE"],
            "upgrades": ["blinktech", " BLINKTECH ", ""],   # 归一大写 + 去空 + 去重
            "extra_production": {"id": " stargate"},
            "one_off": [" oracle "],
        })
        self.assertIn("TEMPEST", fc.spawn)
        self.assertEqual(fc.core_structures, ["GATEWAY", "STARGATE"])
        self.assertEqual(fc.upgrades, ["BLINKTECH"])
        self.assertEqual(fc.extra_production.id_name, "STARGATE")
        self.assertEqual(fc.chrono.when, "primary_pending")  # 缺省
        self.assertEqual(fc.one_off, ["ORACLE"])


class TestShippedFlowsUnchanged(unittest.TestCase):
    """冻结 tempest/stalker 配置值(与已验证行为逐位一致),防后续手滑。"""

    def test_tempest_frozen(self):
        _yaml_or_skip(self)
        fc = FlowConfig.load("tempest")
        self.assertEqual(fc.spawn, {"TEMPEST": {"proportion": 1.0, "priority": 0}})
        self.assertEqual(fc.core_structures,
                         ["GATEWAY", "CYBERNETICSCORE", "STARGATE", "FLEETBEACON"])
        self.assertEqual(fc.upgrades, [
            "TEMPESTGROUNDATTACKUPGRADE",
            "PROTOSSAIRARMORSLEVEL1",
            "PROTOSSAIRARMORSLEVEL2",
        ])
        self.assertEqual(fc.extra_production.id_name, "STARGATE")
        self.assertEqual((fc.extra_production.cap, fc.extra_production.base), (6, 1))
        self.assertEqual(fc.chrono.targets, ("STARGATE",))
        self.assertEqual(fc.chrono.when, "primary_pending")
        self.assertEqual(fc.one_off, ["ORACLE"])
        self.assertEqual(fc.rally_min_army, 0)  # 默认关,已验证行为不动

    def test_stalker_loads(self):
        """stalker 流正在迭代调参(非冻结),只验结构完整 + 配比和 ≈ 1.0。"""
        _yaml_or_skip(self)
        fc = FlowConfig.load("stalker")
        self.assertTrue(fc.spawn)
        total = sum(v["proportion"] for v in fc.spawn.values())
        self.assertAlmostEqual(total, 1.0, places=6)
        self.assertTrue(fc.core_structures)
        self.assertEqual(fc.chrono.when, "always")

    def test_carrier_flow(self):
        _yaml_or_skip(self)
        fc = FlowConfig.load("carrier")
        self.assertEqual(fc.spawn, {
            "CARRIER": {"proportion": 0.7, "priority": 0},
            "TEMPEST": {"proportion": 0.3, "priority": 1},
        })
        # 与暴风舰同科技链;航母优先(priority 0 → chrono/primary 判断指向它)
        self.assertEqual(fc.core_structures,
                         ["GATEWAY", "CYBERNETICSCORE", "STARGATE", "FLEETBEACON"])

    def test_runtime_enums_resolve(self):
        """运行时(有 sc2):三个流的枚举都能解析出来,名字没拼错。"""
        if not _HAS_SC2:
            self.skipTest("sc2 未安装")
        _yaml_or_skip(self)
        for name in ("tempest", "stalker", "carrier"):
            fc = FlowConfig.load(name)
            self.assertTrue(fc.spawn_dict(), f"{name} spawn_dict 为空")
            self.assertTrue(fc.core_structure_ids(), f"{name} 科技链枚举为空")
            self.assertEqual(len(fc.upgrade_ids()), len(fc.upgrades),
                             f"{name} 有升级名解析不出")


class TestPivotRushCannons(unittest.TestCase):
    """E1 实验开关:pivot.rush_cannons(臂 B 纯叉子不铺塔)的配置解析。"""

    def test_default_true_keeps_arm_a(self):
        fc = FlowConfig.from_dict("x", {"spawn": {}, "pivot": {"rush_zealots": 4}})
        self.assertTrue(fc.pivot.rush_cannons)  # 缺省 = 现状臂 A(4叉+铺塔)

    def test_explicit_false_arm_b(self):
        fc = FlowConfig.from_dict("x", {"spawn": {}, "pivot": {
            "rush_zealots": 4, "rush_cannons": False,
        }})
        self.assertEqual(fc.pivot.rush_zealots, 4)
        self.assertFalse(fc.pivot.rush_cannons)  # 臂 B:出叉子但不铺塔

    def test_zero_zealots_arm_c(self):
        fc = FlowConfig.from_dict("x", {"spawn": {}, "pivot": {"rush_zealots": 0}})
        self.assertEqual(fc.pivot.rush_zealots, 0)
        self.assertTrue(fc.pivot.rush_cannons)  # 臂 C:只铺塔憋航母

    def test_no_pivot_block(self):
        fc = FlowConfig.from_dict("x", {"spawn": {}})
        self.assertIsNone(fc.pivot)

    def test_save_up_default_off_and_parse(self):
        # O5:save_up 缺省 0=关;carrier 块显式 250
        self.assertEqual(FlowConfig.from_dict("x", {"spawn": {}}).save_up, 0)
        fc = FlowConfig.from_dict("x", {"spawn": {}, "save_up": 250})
        self.assertEqual(fc.save_up, 250)

    def test_auto_expand_dynamic_fields(self):
        # E2:动态字段缺省 0(旧式 at/to 用法兼容),配了 max_bases 走动态
        old = FlowConfig.from_dict("x", {"spawn": {}, "auto_expand": {
            "at": 150, "to": 2, "when_workers": 18,
        }})
        self.assertEqual((old.auto_expand.at, old.auto_expand.to), (150.0, 2))
        self.assertEqual(old.auto_expand.max_bases, 0)
        self.assertEqual(old.auto_expand.advantage_supply, 0)
        dyn = FlowConfig.from_dict("x", {"spawn": {}, "auto_expand": {
            "max_bases": 4, "when_workers": 22, "advantage_supply": 12,
        }})
        self.assertEqual(
            (dyn.auto_expand.max_bases, dyn.auto_expand.when_workers,
             dyn.auto_expand.advantage_supply),
            (4, 22, 12),
        )

    def test_expansion_cannons_parse(self):
        self.assertIsNone(FlowConfig.from_dict("x", {"spawn": {}}).expansion_cannons)
        fc = FlowConfig.from_dict("x", {"spawn": {}, "expansion_cannons": {
            "min": 3, "max": 8,
        }})
        self.assertEqual((fc.expansion_cannons.min, fc.expansion_cannons.max), (3, 8))

    def test_carrier_e2_shipped(self):
        _yaml_or_skip(self)
        fc = FlowConfig.load("carrier")
        self.assertEqual(
            (fc.auto_expand.max_bases, fc.auto_expand.when_workers,
             fc.auto_expand.advantage_supply),
            (4, 22, 12),
        )
        self.assertEqual(
            (fc.expansion_cannons.min, fc.expansion_cannons.max), (3, 8)
        )
        # O10:升级链补全到 L3,盾 L2/L3 垫底(防队列截断)
        self.assertEqual(fc.upgrades, [
            "PROTOSSAIRWEAPONSLEVEL1", "PROTOSSAIRARMORSLEVEL1",
            "PROTOSSSHIELDSLEVEL1",
            "PROTOSSAIRWEAPONSLEVEL2", "PROTOSSAIRARMORSLEVEL2",
            "PROTOSSAIRWEAPONSLEVEL3", "PROTOSSAIRARMORSLEVEL3",
            "PROTOSSSHIELDSLEVEL2", "PROTOSSSHIELDSLEVEL3",
        ])
        # stalker 旧式 auto_expand 不受影响(冻结块)
        sk = FlowConfig.load("stalker")
        self.assertEqual((sk.auto_expand.to, sk.auto_expand.max_bases), (2, 0))

    def test_carrier_save_up_shipped(self):
        _yaml_or_skip(self)
        self.assertEqual(FlowConfig.load("carrier").save_up, 250)
        # tempest 单兵种不需要憋气,保持关
        self.assertEqual(FlowConfig.load("tempest").save_up, 0)

    def test_shipped_flows_pivot_default_true(self):
        """已发货流派(tempest/carrier 带 pivot 块)缺省 rush_cannons=True,行为不变。"""
        _yaml_or_skip(self)
        for name in ("tempest", "carrier"):
            fc = FlowConfig.load(name)
            self.assertIsNotNone(fc.pivot)
            self.assertTrue(fc.pivot.rush_cannons, f"{name} rush_cannons 缺省应为 True")


    def test_dt_loads(self):
        """dt(隐刀 rush,2026-07-21 落地):块可加载、配比和=1.0、科技链含 DARKSHRINE。"""
        _yaml_or_skip(self)
        fc = FlowConfig.load("dt")
        self.assertEqual(fc.name, "dt")
        total = sum(v["proportion"] for v in fc.spawn.values())
        self.assertAlmostEqual(total, 1.0, places=6)
        self.assertIn("DARKTEMPLAR", fc.spawn)
        self.assertIn("DARKSHRINE", fc.core_structures)
        self.assertIn("TWILIGHTCOUNCIL", fc.core_structures)
        self.assertEqual(fc.rally_min_army, 4)
        self.assertIsNotNone(fc.pivot)

    def test_dt_enums_resolve(self):
        """dt 的兵种/结构/升级枚举运行时全部可解析(防拼写静默失效)。"""
        _yaml_or_skip(self)
        fc = FlowConfig.load("dt")
        self.assertTrue(fc.spawn_dict(), "dt spawn_dict 为空")
        self.assertTrue(fc.core_structure_ids(), "dt 科技链枚举为空")
        self.assertEqual(len(fc.upgrade_ids()), len(fc.upgrades),
                         "dt 有升级名解析不出")


if __name__ == "__main__":
    unittest.main(verbosity=2)
