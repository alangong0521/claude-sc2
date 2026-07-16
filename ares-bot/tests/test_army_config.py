"""army_config.py 纯逻辑单测 —— 不起游戏、不需 sc2(from_dict 路径)。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_army_config -v

覆盖:从 dict 构造、combat 校验、proportion 校验、去重、by_combat/by_role/unit_ids 过滤。
spawn_dict() 需 sc2 枚举,离线跳过(它在 bot 运行时才被调用)。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.army_config import ArmyComposition, UnitSpec  # noqa: E402


_TWO_UNITS = {
    "units": [
        {"id": "tempest", "proportion": 1.0, "priority": 0,
         "role": "ATTACKING", "combat": "tempest_offensive", "notes": "主力"},
        {"id": "oracle", "proportion": 0.0, "priority": 9,
         "role": "HARASSING", "combat": "oracle_harass"},
    ]
}


class TestFromDict(unittest.TestCase):
    def test_basic_parse(self):
        ac = ArmyComposition.from_dict(_TWO_UNITS)
        self.assertEqual(len(ac.units), 2)
        t = ac.units[0]
        self.assertIsInstance(t, UnitSpec)
        self.assertEqual(t.id_name, "TEMPEST")  # 大写归一
        self.assertEqual(t.proportion, 1.0)
        self.assertEqual(t.priority, 0)
        self.assertEqual(t.role, "ATTACKING")
        self.assertEqual(t.combat, "tempest_offensive")

    def test_defaults(self):
        ac = ArmyComposition.from_dict({"units": [{"id": "stalker"}]})
        s = ac.units[0]
        self.assertEqual(s.proportion, 0.0)
        self.assertEqual(s.priority, 5)
        self.assertEqual(s.role, "ATTACKING")
        self.assertEqual(s.combat, "default")

    def test_empty(self):
        ac = ArmyComposition.from_dict({})
        self.assertEqual(ac.units, [])


class TestValidation(unittest.TestCase):
    def test_bad_combat(self):
        with self.assertRaises(ValueError):
            ArmyComposition.from_dict(
                {"units": [{"id": "x", "combat": "bogus_kind"}]}
            )

    def test_negative_proportion(self):
        with self.assertRaises(ValueError):
            ArmyComposition.from_dict(
                {"units": [{"id": "x", "proportion": -0.1}]}
            )

    def test_duplicate_id(self):
        with self.assertRaises(ValueError):
            ArmyComposition.from_dict(
                {"units": [{"id": "tempest"}, {"id": "TEMPEST"}]}
            )

    def test_proportion_sum_over_one(self):
        with self.assertRaises(ValueError):
            ArmyComposition.from_dict({"units": [
                {"id": "a", "proportion": 0.7, "combat": "default"},
                {"id": "b", "proportion": 0.7, "combat": "default"},
            ]})

    def test_proportion_sum_ok_with_zero_harasser(self):
        # 主力 1.0 + oracle 0.0 = 1.0,合法
        ac = ArmyComposition.from_dict(_TWO_UNITS)
        self.assertEqual(len(ac.units), 2)


class TestFilters(unittest.TestCase):
    def setUp(self):
        self.ac = ArmyComposition.from_dict({"units": [
            {"id": "tempest", "proportion": 0.6, "priority": 0,
             "role": "ATTACKING", "combat": "tempest_offensive"},
            {"id": "stalker", "proportion": 0.4, "priority": 1,
             "role": "ATTACKING", "combat": "default"},
            {"id": "oracle", "proportion": 0.0, "priority": 9,
             "role": "HARASSING", "combat": "oracle_harass"},
        ]})

    def test_by_combat(self):
        self.assertEqual(
            [u.id_name for u in self.ac.by_combat("tempest_offensive")], ["TEMPEST"]
        )
        self.assertEqual(
            [u.id_name for u in self.ac.by_combat("default")], ["STALKER"]
        )

    def test_by_role(self):
        self.assertEqual(
            [u.id_name for u in self.ac.by_role("ATTACKING")], ["TEMPEST", "STALKER"]
        )
        self.assertEqual(
            [u.id_name for u in self.ac.by_role("harassing")], ["ORACLE"]  # 大小写不敏感
        )

    def test_unit_ids(self):
        self.assertEqual(self.ac.unit_ids(), ["TEMPEST", "STALKER", "ORACLE"])
        self.assertEqual(self.ac.unit_ids(combat="default"), ["STALKER"])


class TestDefaultConfigLoads(unittest.TestCase):
    """确认仓库里真实的 army_composition.yml 能加载且合法(需 pyyaml)。"""
    def test_load_shipped_config(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("pyyaml 未安装")
        ac = ArmyComposition.load()
        self.assertTrue(any(u.id_name == "TEMPEST" for u in ac.units))
        # 主力应是 tempest_offensive 指挥
        self.assertTrue(ac.by_combat("tempest_offensive"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
