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

    def test_stalker_frozen(self):
        _yaml_or_skip(self)
        fc = FlowConfig.load("stalker")
        self.assertEqual(fc.spawn, {
            "STALKER": {"proportion": 0.7, "priority": 0},
            "ZEALOT": {"proportion": 0.3, "priority": 1},
        })
        self.assertEqual(fc.core_structures,
                         ["GATEWAY", "CYBERNETICSCORE", "TWILIGHTCOUNCIL"])
        self.assertEqual(fc.upgrades, [
            "WARPGATERESEARCH", "BLINKTECH", "PROTOSSGROUNDWEAPONSLEVEL1",
            "PROTOSSGROUNDARMORSLEVEL1", "PROTOSSSHIELDSLEVEL1",
        ])
        self.assertEqual(fc.extra_production.id_name, "GATEWAY")
        self.assertEqual((fc.extra_production.cap, fc.extra_production.base), (8, 2))
        self.assertEqual(fc.chrono.targets, ("GATEWAY", "TWILIGHTCOUNCIL"))
        self.assertEqual(fc.chrono.when, "always")
        self.assertEqual(fc.one_off, [])

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
