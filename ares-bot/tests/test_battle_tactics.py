"""B1/B2/B3/B6 战斗微操纯逻辑单测 —— 不起游戏、不 import ares/sc2,标准库 unittest 可跑。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_battle_tactics -v

覆盖:
  B2  FOCUS_PRIORITY 静态集火优先级表 + pick_focus_key 的 "priority" 模式(sharpy 出处);
  B1  outranging_threats(AvoidTargetedDamage,Sharky)/ blink_away_point(LOCKON 特判)/
      blink_landing_is_safer(落点校验,sharpy);
  B3  sim_combatants(can_win_fight 输入过滤:去农民去建筑,ares 官方警告)。
运行时接线(stalker_offensive / combat_manager / generic_offensive)不在此测 —— 那些要起游戏。
"""
import os
import sys
import unittest
from types import SimpleNamespace

# 让 `import bot.levers` 能在直接跑此文件时生效
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.levers import (  # noqa: E402
    DEFAULT_FOCUS_PRIORITY, FOCUS_PRIORITY,
    blink_away_point, blink_landing_is_safer, outranging_threats,
    pick_focus_key, sim_combatants,
)


def _unit(name, hp=100, shield=0, pos=(0, 0), ground_range=6.0, is_structure=False):
    """最小假 Unit 桩,覆盖本文件用到的全部属性。"""
    type_id = SimpleNamespace(name=name)
    p = SimpleNamespace(x=pos[0], y=pos[1])
    return SimpleNamespace(
        type_id=type_id, health=hp, shield=shield, position=p,
        ground_range=ground_range, is_structure=is_structure,
        distance_to=lambda o: ((p.x - o.position.x) ** 2 + (p.y - o.position.y) ** 2) ** 0.5,
    )


class TestFocusPriorityTable(unittest.TestCase):
    """B2:静态优先级表逐项核对(来源:sharpy micro_stalkers high_priority)。"""

    def test_tier_10(self):
        for name in ("SIEGETANKSIEGED", "INFESTOR", "INFESTORBURROWED",
                     "HIGHTEMPLAR", "COLOSSUS", "RAVEN",
                     "WIDOWMINEBURROWED", "BROODLORD"):
            self.assertEqual(FOCUS_PRIORITY[name], 10, name)

    def test_tier_9(self):
        for name in ("LURKERMP", "LURKEREGG", "DARKTEMPLAR", "IMMORTAL"):
            self.assertEqual(FOCUS_PRIORITY[name], 9, name)

    def test_tier_8_to_6(self):
        self.assertEqual(FOCUS_PRIORITY["BATTLECRUISER"], 8)
        self.assertEqual(FOCUS_PRIORITY["SENTRY"], 8)
        self.assertEqual(FOCUS_PRIORITY["GHOST"], 7)
        self.assertEqual(FOCUS_PRIORITY["MEDIVAC"], 6)

    def test_static_defence_is_1(self):
        # 电池/炮塔只有 1 —— 不浪费输出打建筑
        self.assertEqual(FOCUS_PRIORITY["SHIELDBATTERY"], 1)
        self.assertEqual(FOCUS_PRIORITY["PHOTONCANNON"], 1)

    def test_default_tier_above_buildings(self):
        # 未上榜作战单位默认 5,必须高于建筑档(1),低于关键档(9/10)
        self.assertGreater(DEFAULT_FOCUS_PRIORITY, 1)
        self.assertLess(DEFAULT_FOCUS_PRIORITY, 9)


class TestPickFocusPriorityMode(unittest.TestCase):
    """B2:pick_focus_key 的 focus="priority" 模式。"""

    def test_high_priority_beats_weakest_low_priority(self):
        # 架起坦克(满血)必须赢过残血机枪 —— 档位优先于 weakest
        tank = _unit("SIEGETANKSIEGED", hp=175)
        marine = _unit("MARINE", hp=5)
        self.assertIs(pick_focus_key([marine, tank], "priority"), tank)

    def test_same_tier_breaks_tie_by_weakest(self):
        # 同档内沿用 weakest:残血 HT 优先于满血 HT
        ht_full = _unit("HIGHTEMPLAR", hp=40, shield=40)
        ht_weak = _unit("HIGHTEMPLAR", hp=10, shield=0)
        self.assertIs(pick_focus_key([ht_full, ht_weak], "priority"), ht_weak)

    def test_buildings_rank_below_army(self):
        # 电池(1)排在未上榜兵种(默认 5)后面
        battery = _unit("SHIELDBATTERY", hp=50, shield=50)
        zealot = _unit("ZEALOT", hp=100, shield=50)
        self.assertIs(pick_focus_key([battery, zealot], "priority"), zealot)

    def test_burrowed_variants(self):
        inf = _unit("INFESTORBURROWED")
        marine = _unit("MARINE", hp=1)
        self.assertIs(pick_focus_key([marine, inf], "priority"), inf)

    def test_existing_focus_modes_unchanged(self):
        # 回归:默认 weakest 等行为不受静态表影响(坦克不插队)
        tank = _unit("SIEGETANKSIEGED", hp=175)
        marine = _unit("MARINE", hp=5)
        self.assertIs(pick_focus_key([tank, marine], "weakest"), marine)
        self.assertIsNone(pick_focus_key([tank], None))
        self.assertIsNone(pick_focus_key([], "priority"))


class TestOutrangingThreats(unittest.TestCase):
    """B1② AvoidTargetedDamage(Sharky):超射程瞄准判定。"""

    def test_sieged_tank_is_threat(self):
        stalker = _unit("STALKER", pos=(0, 0), ground_range=6.0)
        tank = _unit("SIEGETANKSIEGED", pos=(10, 0), ground_range=13.0)
        self.assertEqual(outranging_threats(stalker, [tank]), [tank])

    def test_marine_not_threat(self):
        # 机枪射程 5 < 追猎 6:不算超射程
        stalker = _unit("STALKER", pos=(0, 0), ground_range=6.0)
        marine = _unit("MARINE", pos=(5, 0), ground_range=5.0)
        self.assertEqual(outranging_threats(stalker, [marine]), [])

    def test_out_of_enemy_range_not_threat(self):
        # 坦克射程 13 但距离 20:够不着我,不算
        stalker = _unit("STALKER", pos=(0, 0), ground_range=6.0)
        tank = _unit("SIEGETANKSIEGED", pos=(20, 0), ground_range=13.0)
        self.assertEqual(outranging_threats(stalker, [tank]), [])

    def test_range_buffer(self):
        # 射程只差 0.5(在 buffer 内)不算"明显超射程"
        stalker = _unit("STALKER", pos=(0, 0), ground_range=6.0)
        other = _unit("STALKER", pos=(6, 0), ground_range=6.5)
        self.assertEqual(outranging_threats(stalker, [other]), [])


class TestBlinkAwayPoint(unittest.TestCase):
    """B1⑤ LOCKON 逃点几何。"""

    def test_direction_and_distance(self):
        src = SimpleNamespace(x=10.0, y=0.0)
        threat = SimpleNamespace(x=0.0, y=0.0)
        x, y = blink_away_point(src, threat, 7.5)
        self.assertAlmostEqual(x, 17.5)
        self.assertAlmostEqual(y, 0.0)

    def test_diagonal(self):
        src = SimpleNamespace(x=3.0, y=4.0)   # 距原点 5
        threat = SimpleNamespace(x=0.0, y=0.0)
        x, y = blink_away_point(src, threat, 10.0)
        self.assertAlmostEqual((x ** 2 + y ** 2) ** 0.5, 15.0)  # 5 + 10
        self.assertAlmostEqual(x / 3.0, y / 4.0)                # 同方向

    def test_coincident_returns_none(self):
        p = SimpleNamespace(x=1.0, y=1.0)
        self.assertIsNone(blink_away_point(p, p, 7.5))


class TestBlinkLandingSafety(unittest.TestCase):
    """B1④ 落点 influence 校验(sharpy):严格更低才跳。"""

    def test_safer_true(self):
        self.assertTrue(blink_landing_is_safer(10.0, 3.0))

    def test_equal_or_worse_false(self):
        self.assertFalse(blink_landing_is_safer(3.0, 3.0))
        self.assertFalse(blink_landing_is_safer(3.0, 10.0))


class TestSimCombatants(unittest.TestCase):
    """B3:can_win_fight 输入过滤 —— 农民和建筑不进模拟器。"""

    def test_filters_workers_and_structures(self):
        army = _unit("STALKER")
        probe = _unit("PROBE")
        nexus = _unit("NEXUS", is_structure=True)
        cannon = _unit("PHOTONCANNON", is_structure=True)
        out = sim_combatants([army, probe, nexus, cannon])
        self.assertEqual(out, [army])

    def test_empty(self):
        self.assertEqual(sim_combatants([]), [])

    def test_missing_attrs_treated_as_combatant(self):
        # 没有 is_structure 属性的桩对象按战斗单位保留(宽松过滤)
        u = SimpleNamespace(type_id=SimpleNamespace(name="STALKER"))
        self.assertEqual(sim_combatants([u]), [u])


if __name__ == "__main__":
    unittest.main(verbosity=2)
