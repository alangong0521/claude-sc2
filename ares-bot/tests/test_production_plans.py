"""production_plans.py 纯逻辑单测 —— 种族无关的农民/气目标计算,不起游戏。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_production_plans -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.production_plans import (  # noqa: E402
    expansion_cannon_count,
    full_gas_bases,
    gas_gated_stargate_target,
    gas_target,
    save_up_spawn,
    should_expand_dynamic,
    upgrade_tech_buildings,
    worker_target,
)


class TestWorkerTarget(unittest.TestCase):
    def test_single_base_matches_old_behavior(self):
        self.assertEqual(worker_target(1), 22)  # 与旧 Protoss _build_probes 一致

    def test_scales_with_bases(self):
        self.assertEqual(worker_target(2), 44)
        self.assertEqual(worker_target(3), 66)

    def test_caps(self):
        self.assertEqual(worker_target(4), 70)   # 88 封顶到 70
        self.assertEqual(worker_target(10), 70)

    def test_zero_or_negative(self):
        self.assertEqual(worker_target(0), 0)
        self.assertEqual(worker_target(-1), 0)

    def test_custom_params(self):
        self.assertEqual(worker_target(2, per_base=16, cap=100), 32)


class TestGasTarget(unittest.TestCase):
    def test_opener_single_gas_before_production(self):
        # 没军事建筑 → 只开 1 个气(保起手节奏)
        self.assertEqual(gas_target(1, has_production=False), 1)
        self.assertEqual(gas_target(3, has_production=False), 1)

    def test_double_gas_per_base_after_production(self):
        self.assertEqual(gas_target(1, has_production=True), 2)
        self.assertEqual(gas_target(2, has_production=True), 4)

    def test_zero_townhalls(self):
        self.assertEqual(gas_target(0, has_production=True), 0)
        self.assertEqual(gas_target(-2, has_production=False), 0)

    def test_custom_params(self):
        self.assertEqual(gas_target(2, has_production=True, per_base=3), 6)
        self.assertEqual(gas_target(2, has_production=False, opener=2), 2)


class TestUpgradeTechBuildings(unittest.TestCase):
    """O1 修复的配套纯逻辑：升级 → 研究建筑映射（去重保序）。"""

    def test_carrier_upgrades_map_to_cybercore_and_forge(self):
        from sc2.ids.upgrade_id import UpgradeId
        from sc2.ids.unit_typeid import UnitTypeId as UnitID

        ups = [
            UpgradeId.PROTOSSAIRWEAPONSLEVEL1,
            UpgradeId.PROTOSSAIRARMORSLEVEL1,
            UpgradeId.PROTOSSSHIELDSLEVEL1,
        ]
        self.assertEqual(
            upgrade_tech_buildings(ups),
            [UnitID.CYBERNETICSCORE, UnitID.FORGE],
        )

    def test_dedupes_shared_research_building(self):
        from sc2.ids.upgrade_id import UpgradeId
        from sc2.ids.unit_typeid import UnitTypeId as UnitID

        ups = [
            UpgradeId.PROTOSSGROUNDWEAPONSLEVEL1,
            UpgradeId.PROTOSSGROUNDARMORSLEVEL1,
            UpgradeId.PROTOSSSHIELDSLEVEL1,
        ]
        self.assertEqual(upgrade_tech_buildings(ups), [UnitID.FORGE])

    def test_empty(self):
        self.assertEqual(upgrade_tech_buildings([]), [])


class TestSaveUpSpawn(unittest.TestCase):
    """O5 憋气机制:freeflow 下 p0 买不起不再 fall-through 喂饱 p1。"""

    # A=主 C(p0, 0.7), B=副 C(p1, 0.3) —— 镜像 carrier 流 CARRIER/TEMPEST
    SPAWN = {
        "A": {"proportion": 0.7, "priority": 0},
        "B": {"proportion": 0.3, "priority": 1},
    }

    def _run(self, spawn=None, **kw):
        kw.setdefault("counts", {"A": 0, "B": 0})
        kw.setdefault("affordable", {"A": False, "B": True})
        kw.setdefault("gas_gap", {"A": 250, "B": 0})
        kw.setdefault("buildable", {"A": True, "B": True})
        kw.setdefault("max_gas_gap", 250)
        return save_up_spawn(spawn or self.SPAWN, **kw)

    def test_behind_share_and_close_truncates_to_p0(self):
        # 占比落后 + 气缺口 ≤ 阈值 → 只留 p0(攒气,B 不再 fall-through 吃气)
        out = self._run(counts={"A": 1, "B": 3}, gas_gap={"A": 100, "B": 0})
        self.assertEqual(list(out), ["A"])

    def test_behind_share_and_affordable_truncates_to_p0(self):
        out = self._run(counts={"A": 1, "B": 3}, affordable={"A": True, "B": True})
        self.assertEqual(list(out), ["A"])

    def test_behind_share_but_far_from_affordable_keeps_full_dict(self):
        # 缺口还很大(>阈值) → 不截断,低优先先顶着生产
        out = self._run(counts={"A": 1, "B": 3}, max_gas_gap=50)
        self.assertEqual(set(out), {"A", "B"})

    def test_share_met_drops_p0_so_p1_fills(self):
        # 占比达标(7:3) → p0 让位,副 C 照常补位
        out = self._run(counts={"A": 7, "B": 3})
        self.assertEqual(list(out), ["B"])

    def test_share_met_but_rest_unbuildable_keeps_full_dict(self):
        # 摘掉 p0 后没有可造兵种 → 原样返回(C5a:防精确配比点停产)
        out = self._run(counts={"A": 7, "B": 3}, buildable={"A": True, "B": False})
        self.assertEqual(set(out), {"A", "B"})

    def test_single_buildable_unit_is_noop(self):
        # p0 科技未就绪(开局没舰队航标) → 不截断,p1 照常顶中期
        out = self._run(buildable={"A": False, "B": True})
        self.assertEqual(set(out), {"A", "B"})

    def test_single_unit_spawn_unchanged(self):
        out = self._run(spawn={"A": {"proportion": 1.0, "priority": 0}})
        self.assertEqual(list(out), ["A"])


class TestShouldExpandDynamic(unittest.TestCase):
    """E2 动态开矿触发矩阵(爆仓/优势/上限/pending/rush)。"""

    def _run(self, **kw):
        kw.setdefault("bases", 1)
        kw.setdefault("max_bases", 4)
        kw.setdefault("nexus_pending", 0)
        kw.setdefault("supply_workers", 0)
        kw.setdefault("workers_per_base", 22)
        kw.setdefault("own_army_supply", 0)
        kw.setdefault("enemy_army_supply", 0)
        kw.setdefault("advantage_supply", 12)
        kw.setdefault("rush_active", False)
        return should_expand_dynamic(**kw)

    def test_saturation_triggers(self):
        # 爆仓:22 农民 × 1 基地 → 开;2 基地要 44 才开
        self.assertTrue(self._run(supply_workers=22))
        self.assertFalse(self._run(bases=2, supply_workers=43))
        self.assertTrue(self._run(bases=2, supply_workers=44))

    def test_advantage_triggers(self):
        # 优势:我方 army supply ≥ 敌可见 + 12
        self.assertTrue(self._run(own_army_supply=12, enemy_army_supply=0))
        self.assertFalse(self._run(own_army_supply=11, enemy_army_supply=0))
        self.assertFalse(self._run(own_army_supply=13, enemy_army_supply=2))

    def test_caps_and_pending_block(self):
        self.assertFalse(self._run(bases=4, supply_workers=999))   # 到上限
        self.assertFalse(self._run(supply_workers=999, nexus_pending=1))  # 已有在建

    def test_rush_blocks_expansion(self):
        self.assertFalse(self._run(supply_workers=999, rush_active=True))
        self.assertFalse(self._run(own_army_supply=99, rush_active=True))

    def test_no_trigger(self):
        self.assertFalse(self._run(supply_workers=10))


class TestExpansionCannonCount(unittest.TestCase):
    """E2 分矿塔数 clamp 边界(计划 §5:0 敌兵→3、16→7、40→8)。"""

    def test_plan_boundaries(self):
        self.assertEqual(expansion_cannon_count(3, 8, 0), 3)
        self.assertEqual(expansion_cannon_count(3, 8, 16), 7)
        self.assertEqual(expansion_cannon_count(3, 8, 40), 8)

    def test_intermediate_and_clamps(self):
        self.assertEqual(expansion_cannon_count(3, 8, 3), 3)   # //4 不进位
        self.assertEqual(expansion_cannon_count(3, 8, 4), 4)
        self.assertEqual(expansion_cannon_count(3, 8, 19), 7)
        self.assertEqual(expansion_cannon_count(3, 8, 20), 8)
        self.assertEqual(expansion_cannon_count(3, 8, 999), 8)  # 封顶


class TestGasGatedStargates(unittest.TestCase):
    """E2 星门气体闸门:目标数 = min(cap, 满采气基地数 + 1)(司令口径:单矿→2、双矿→3)。"""

    def test_full_gas_bases(self):
        self.assertEqual(full_gas_bases([]), 0)
        self.assertEqual(full_gas_bases([2]), 1)
        self.assertEqual(full_gas_bases([1, 2, 3]), 2)   # <2 不算满采
        self.assertEqual(full_gas_bases([2, 2, 2]), 3)

    def test_stargate_target(self):
        self.assertEqual(gas_gated_stargate_target(6, [2]), 2)          # 单矿双气 2 星门
        self.assertEqual(gas_gated_stargate_target(6, [2, 2]), 3)       # 双矿四气 3 星门
        self.assertEqual(gas_gated_stargate_target(6, [2, 2, 2]), 4)    # 3 矿 4 星门
        self.assertEqual(gas_gated_stargate_target(6, [2, 2, 1]), 3)    # 没满采的不算
        self.assertEqual(gas_gated_stargate_target(6, [0]), 1)          # 没气也有 +1 底(存款爆兵)
        self.assertEqual(gas_gated_stargate_target(2, [2, 2, 2]), 2)    # cap 仍生效


if __name__ == "__main__":
    unittest.main(verbosity=2)
