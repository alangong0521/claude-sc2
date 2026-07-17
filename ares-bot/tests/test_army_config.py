"""army_config.py 纯逻辑单测 —— 不起游戏、不需 sc2(from_dict 路径)。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_army_config -v

覆盖:从 dict 构造、combat 校验、proportion 校验、去重、by_combat/by_role/unit_ids 过滤。
spawn_dict() 需 sc2 枚举,离线跳过(它在 bot 运行时才被调用)。
"""
import os
import sys
import unittest
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.army_config import (  # noqa: E402
    ArmyComposition, UnitSpec, _select_block, bot_race_name,
)


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


_PER_RACE = {
    "protoss": {"units": [
        {"id": "tempest", "proportion": 1.0, "combat": "tempest_offensive"},
    ]},
    "terran": {"units": [
        {"id": "marine", "proportion": 0.6, "combat": "default"},
        {"id": "siegetank", "proportion": 0.4, "combat": "default"},
    ]},
    "zerg": {"units": [
        {"id": "roach", "proportion": 1.0, "combat": "default"},
    ]},
}


class TestSelectBlock(unittest.TestCase):
    def test_pick_by_race(self):
        self.assertEqual(_select_block(_PER_RACE, "Terran")["units"][0]["id"], "marine")
        self.assertEqual(_select_block(_PER_RACE, "zerg")["units"][0]["id"], "roach")

    def test_case_insensitive(self):
        self.assertEqual(_select_block(_PER_RACE, "PROTOSS")["units"][0]["id"], "tempest")

    def test_none_falls_back_to_protoss(self):
        self.assertEqual(_select_block(_PER_RACE, None)["units"][0]["id"], "tempest")

    def test_unknown_race_falls_back_to_protoss(self):
        self.assertEqual(_select_block(_PER_RACE, "Random")["units"][0]["id"], "tempest")

    def test_flat_backcompat(self):
        # 旧扁平结构(顶层直接 units:) → 原样返回,忽略 race
        flat = {"units": [{"id": "tempest", "proportion": 1.0,
                           "combat": "tempest_offensive"}]}
        self.assertIs(_select_block(flat, "terran"), flat)

    def test_no_protoss_falls_back_first(self):
        d = {"zerg": {"units": [{"id": "roach"}]}}
        self.assertEqual(_select_block(d, "Terran")["units"][0]["id"], "roach")

    def test_garbage_returns_empty(self):
        self.assertEqual(_select_block(None, "x"), {})
        self.assertEqual(_select_block({}, "x"), {})


class TestBotRaceName(unittest.TestCase):
    def test_extracts_name(self):
        ai = SimpleNamespace(race=SimpleNamespace(name="Terran"))
        self.assertEqual(bot_race_name(ai), "Terran")

    def test_missing_race_none(self):
        self.assertIsNone(bot_race_name(SimpleNamespace()))
        self.assertIsNone(bot_race_name(SimpleNamespace(race=None)))


class TestLoadPerRace(unittest.TestCase):
    """load(race=...) 从真实 yaml 选块(需 pyyaml)。"""
    def _yaml_or_skip(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("pyyaml 未安装")

    def test_default_protoss(self):
        self._yaml_or_skip()
        ac = ArmyComposition.load()  # race=None → protoss
        self.assertTrue(any(u.id_name == "TEMPEST" for u in ac.units))
        self.assertTrue(ac.by_combat("tempest_offensive"))

    def test_terran_block(self):
        self._yaml_or_skip()
        ac = ArmyComposition.load(race="Terran")
        ids = [u.id_name for u in ac.units]
        self.assertIn("MARINE", ids)
        self.assertNotIn("TEMPEST", ids)

    def test_zerg_block(self):
        self._yaml_or_skip()
        ac = ArmyComposition.load(race="Zerg")
        self.assertIn("ROACH", [u.id_name for u in ac.units])

    def test_all_race_blocks_valid(self):
        # 三块都能过 _validate(proportion 和 ≤1.0、combat 合法、id 唯一)
        self._yaml_or_skip()
        for r in ("Protoss", "Terran", "Zerg"):
            ac = ArmyComposition.load(race=r)
            self.assertTrue(ac.units, f"{r} 块为空")


class TestUpgrades(unittest.TestCase):
    """M3:升级列表解析(纯逻辑,不需 sc2)。"""
    def test_parse_and_normalize(self):
        ac = ArmyComposition.from_dict({"units": [], "upgrades": [
            "stimpack", " CombatShield ", "STIMPACK",  # 归一大写 + 去空 + 去重
        ]})
        self.assertEqual(ac.upgrade_names(), ["STIMPACK", "COMBATSHIELD"])

    def test_default_empty(self):
        ac = ArmyComposition.from_dict({"units": []})
        self.assertEqual(ac.upgrade_names(), [])
        # __post_init__ 保证 upgrades 是 list 不是 None
        self.assertIsInstance(ac.upgrades, list)

    def test_none_upgrades_key(self):
        ac = ArmyComposition.from_dict({"units": [], "upgrades": None})
        self.assertEqual(ac.upgrade_names(), [])

    def test_shipped_protoss_upgrades_unchanged(self):
        try:
            import yaml  # noqa: F401
        except ImportError:
            self.skipTest("pyyaml 未安装")
        # Protoss 块必须仍是原 3 项(保证 M3 不改已验证行为)
        ac = ArmyComposition.load(race="Protoss")
        self.assertEqual(ac.upgrade_names(), [
            "TEMPESTGROUNDATTACKUPGRADE",
            "PROTOSSAIRARMORSLEVEL1",
            "PROTOSSAIRARMORSLEVEL2",
        ])


class TestNewCombatKinds(unittest.TestCase):
    """M4:新增 combat kinds 被接受。"""
    def test_siege_and_medivac_accepted(self):
        ac = ArmyComposition.from_dict({"units": [
            {"id": "siegetank", "proportion": 0.5, "combat": "siege_offensive"},
            {"id": "medivac", "proportion": 0.5, "combat": "medivac_support"},
        ]})
        self.assertEqual([u.combat for u in ac.units],
                         ["siege_offensive", "medivac_support"])

    def test_m4_remaining_kinds_accepted(self):
        # M4 剩余:高模风暴 + 医疗船空投
        ac = ArmyComposition.from_dict({"units": [
            {"id": "hightemplar", "proportion": 0.5, "combat": "templar_caster"},
            {"id": "medivac", "proportion": 0.5, "combat": "medivac_transport"},
        ]})
        self.assertEqual([u.combat for u in ac.units],
                         ["templar_caster", "medivac_transport"])

    def test_specialist_kinds_accepted(self):
        # 补充兵种:幽灵/渡鸦/女王/死神/感染虫
        ac = ArmyComposition.from_dict({"units": [
            {"id": "ghost", "proportion": 0.2, "combat": "ghost_offensive"},
            {"id": "raven", "proportion": 0.2, "combat": "raven_support"},
            {"id": "queen", "proportion": 0.2, "combat": "queen_support"},
            {"id": "reaper", "proportion": 0.2, "combat": "reaper_harass"},
            {"id": "infestor", "proportion": 0.2, "combat": "infestor_caster"},
        ]})
        self.assertEqual(
            [u.combat for u in ac.units],
            ["ghost_offensive", "raven_support", "queen_support",
             "reaper_harass", "infestor_caster"],
        )

    def test_combat_kinds_count(self):
        # COMBAT_KINDS 冻结在 12 个,防止误删/漏加
        from bot.army_config import COMBAT_KINDS
        self.assertEqual(len(COMBAT_KINDS), 12)
        self.assertEqual(len(set(COMBAT_KINDS)), 12)  # 无重复

    def test_unknown_combat_still_rejected(self):
        with self.assertRaises(ValueError):
            ArmyComposition.from_dict(
                {"units": [{"id": "x", "combat": "laser_offensive"}]}
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
