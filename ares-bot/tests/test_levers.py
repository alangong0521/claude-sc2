"""levers.py 纯逻辑单测 —— 不起游戏、不 import ares/sc2,用标准库 unittest 即可跑。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_levers -v
或:
  python3 tests/test_levers.py

这些测试覆盖抽到 levers.py 的纯函数:焦点敌人槽位、语义目标选择、focus 选择、
build 别名归一、择时触发器、一次性/粘性判定。所有运行时上下文(enemy_structures 等)
都用测试桩对象模拟,不触碰 ares。
"""
import os
import sys
import unittest
from types import SimpleNamespace

# 让 `import bot.levers` 能在直接跑此文件时生效
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.levers import (  # noqa: E402
    is_one_shot, pick_focus_key, pick_known_base,
    resolve_build_name, resolve_enemy_slot, should_hold_for_trigger,
)
from bot.steer_vocab import (  # noqa: E402
    BUILDABLE, canonical_build, enemy_slot_index, validate_field, validate_order,
)


def _unit(name, hp=100, shield=0, pos=(0, 0)):
    """造一个最小的假 Unit 桩,满足 pick_focus_key 访问的属性。"""
    type_id = SimpleNamespace(name=name)
    p = SimpleNamespace(x=pos[0], y=pos[1])
    return SimpleNamespace(
        type_id=type_id, health=hp, shield=shield, position=p,
        distance_to=lambda o: ((p.x - o.position.x) ** 2 + (p.y - o.position.y) ** 2) ** 0.5,
    )


class TestEnemySlot(unittest.TestCase):
    def test_basic_index(self):
        self.assertEqual(enemy_slot_index("E1"), 0)
        self.assertEqual(enemy_slot_index("E2"), 1)
        self.assertEqual(enemy_slot_index("e3"), 2)

    def test_invalid(self):
        self.assertIsNone(enemy_slot_index(None))
        self.assertIsNone(enemy_slot_index(""))
        self.assertIsNone(enemy_slot_index("E0"))
        self.assertIsNone(enemy_slot_index("EX"))
        self.assertIsNone(enemy_slot_index("enemy"))

    def test_resolve_bounds_safe(self):
        # 越界 → 回退 0
        self.assertEqual(resolve_enemy_slot("E5", n_enemies=2), 0)
        self.assertEqual(resolve_enemy_slot("E2", n_enemies=1), 0)
        self.assertEqual(resolve_enemy_slot("E2", n_enemies=3), 1)
        self.assertEqual(resolve_enemy_slot(None, n_enemies=3), 0)


class TestPickKnownBase(unittest.TestCase):
    def test_natural_third_fourth(self):
        bases = ["main", "nat", "third", "fourth"]
        self.assertEqual(pick_known_base("enemy_natural", bases), 1)
        self.assertEqual(pick_known_base("enemy_third", bases), 2)
        self.assertEqual(pick_known_base("enemy_fourth", bases), 3)

    def test_not_yet_scouted(self):
        # 只探到 2 个矿,要打 third → None(别硬冲空地)
        self.assertIsNone(pick_known_base("enemy_third", ["main", "nat"]))
        self.assertIsNone(pick_known_base("enemy_fourth", ["main"]))

    def test_unknown_key(self):
        self.assertIsNone(pick_known_base("enemy_main", ["a"]))  # main 不走这条
        self.assertIsNone(pick_known_base("home", ["a"]))
        self.assertIsNone(pick_known_base("bogus", ["a"]))


class TestPickFocus(unittest.TestCase):
    def test_weakest(self):
        es = [_unit("MARINE", hp=50), _unit("MARINE", hp=10), _unit("MARINE", hp=80)]
        self.assertEqual(pick_focus_key(es, "weakest").health, 10)

    def test_workers(self):
        es = [_unit("MARINE"), _unit("SCV"), _unit("MARINE")]
        self.assertEqual(pick_focus_key(es, "workers").type_id.name, "SCV")
        # 没工人 → None(交回引擎默认)
        self.assertIsNone(pick_focus_key([_unit("MARINE")], "workers"))

    def test_closest_with_origin(self):
        origin = _unit("TEMPEST", pos=(0, 0))
        es = [_unit("MARINE", pos=(10, 0)), _unit("MARINE", pos=(1, 0)),
              _unit("MARINE", pos=(5, 0))]
        chosen = pick_focus_key(es, "closest", origin=origin)
        self.assertEqual((chosen.position.x, chosen.position.y), (1, 0))

    def test_closest_no_origin(self):
        # 没 origin → None(引擎默认选法),不再退回"等于默认"的歧义
        self.assertIsNone(pick_focus_key([_unit("MARINE")], "closest"))

    def test_unit_type_name(self):
        es = [_unit("MARINE"), _unit("SIEGETANK"), _unit("MARINE")]
        self.assertEqual(pick_focus_key(es, "SIEGETANK").type_id.name, "SIEGETANK")
        # 没这种兵 → None
        self.assertIsNone(pick_focus_key(es, "MEDIVAC"))

    def test_empty_or_no_focus(self):
        self.assertIsNone(pick_focus_key([], "weakest"))
        self.assertIsNone(pick_focus_key([_unit("MARINE")], None))


class TestResolveBuildName(unittest.TestCase):
    def test_canonical_names(self):
        self.assertEqual(resolve_build_name("stargate"), "STARGATE")
        self.assertEqual(resolve_build_name("nexus"), "NEXUS")
        self.assertEqual(resolve_build_name("cyberneticscore"), "CYBERNETICSCORE")

    def test_aliases(self):
        self.assertEqual(resolve_build_name("gas"), "ASSIMILATOR")
        self.assertEqual(resolve_build_name("geyser"), "ASSIMILATOR")
        self.assertEqual(resolve_build_name("base"), "NEXUS")
        self.assertEqual(resolve_build_name("cyber"), "CYBERNETICSCORE")
        self.assertEqual(resolve_build_name("robo"), "ROBOTICSFACILITY")
        self.assertEqual(resolve_build_name("roboticsfacility"), "ROBOTICSFACILITY")
        # 回归:词表词 twilight 必须映射到真枚举名 TWILIGHTCOUNCIL
        # (曾解析成不存在的 TWILIGHT,build=twilight 被静默忽略)
        self.assertEqual(resolve_build_name("twilight"), "TWILIGHTCOUNCIL")
        self.assertEqual(resolve_build_name("twilightcouncil"), "TWILIGHTCOUNCIL")

    def test_passthrough_unknown(self):
        # 不在规范表 → 原样大写交回(引擎可能能造,如 PYLON/DARKSHRINE)
        self.assertEqual(resolve_build_name("pylon"), "PYLON")
        self.assertEqual(resolve_build_name("darkshrine"), "DARKSHRINE")
        self.assertEqual(resolve_build_name("DARKSHRINE"), "DARKSHRINE")

    def test_empty(self):
        self.assertIsNone(resolve_build_name(""))
        self.assertIsNone(resolve_build_name("   "))


class TestTrigger(unittest.TestCase):
    def test_now(self):
        self.assertFalse(should_hold_for_trigger("now", 50, False))
        self.assertFalse(should_hold_for_trigger(None, 50, True))

    def test_when_maxed(self):
        self.assertTrue(should_hold_for_trigger("when_maxed", 100, False))
        self.assertFalse(should_hold_for_trigger("when_maxed", 195, False))
        self.assertFalse(should_hold_for_trigger("when_maxed", 190, False))  # = 阈值即打

    def test_when_enemy_away(self):
        self.assertTrue(should_hold_for_trigger("when_enemy_away", 100, True))
        self.assertFalse(should_hold_for_trigger("when_enemy_away", 100, False))

    def test_unknown_trigger(self):
        # 认不出 → 当 now(不阻塞)
        self.assertFalse(should_hold_for_trigger("bogus", 50, True))


class TestOneShot(unittest.TestCase):
    def test_one_shot_fields(self):
        self.assertTrue(is_one_shot("build"))
        self.assertTrue(is_one_shot("expand"))
        self.assertTrue(is_one_shot("scout"))

    def test_sticky_fields(self):
        self.assertFalse(is_one_shot("stance"))
        self.assertFalse(is_one_shot("target"))
        self.assertFalse(is_one_shot("focus"))
        self.assertFalse(is_one_shot("harass"))


class TestValidate(unittest.TestCase):
    def test_valid_enum(self):
        self.assertEqual(validate_field("stance", "attack"), [])
        self.assertEqual(validate_field("target", "enemy_natural"), [])
        self.assertEqual(validate_field("harass", "off"), [])
        self.assertEqual(validate_field("enemy", "E2"), [])

    def test_invalid_enum(self):
        self.assertTrue(validate_field("stance", "bogus"))
        self.assertTrue(validate_field("target", "enemy_fifth"))  # 不在 TARGETS
        self.assertTrue(validate_field("harass", "maybe"))

    def test_unknown_field(self):
        self.assertTrue(validate_field("bogus", "x"))

    def test_focus_free_form(self):
        # 兵种名(全大写)放行
        self.assertEqual(validate_field("focus", "SIEGETANK"), [])
        self.assertEqual(validate_field("focus", "weakest"), [])
        # 半大写不像兵种名 → 提示
        self.assertTrue(validate_field("focus", "siegetank"))

    def test_build_free_form(self):
        self.assertEqual(validate_field("build", "stargate"), [])
        self.assertEqual(validate_field("build", "gas"), [])  # 别名
        self.assertEqual(validate_field("build", "pylon"), [])  # 引擎能造但不在 BUILDABLE

    def test_order_merge(self):
        # 合并校验:旧脏值 + 新值
        errs = validate_order({"stance": "attack", "harass": "bogus"})
        self.assertTrue(any("harass" in e for e in errs))
        self.assertEqual(validate_order({"stance": "attack", "target": "home"}), [])


if __name__ == "__main__":
    unittest.main(verbosity=2)