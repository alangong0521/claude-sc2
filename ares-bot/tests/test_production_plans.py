"""production_plans.py 纯逻辑单测 —— 种族无关的农民/气目标计算,不起游戏。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_production_plans -v
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.production_plans import (  # noqa: E402
    assimilator_attempt_stuck,
    defense_syncs_with_nexus,
    expansion_cannon_count,
    expansion_reserve_active,
    floor_army_defends_home,
    full_gas_bases,
    gas_gated_stargate_target,
    gas_target,
    nexus_rebuild_active,
    nexus_rebuild_viable,
    pre_fleet_cap,
    pre_fleet_spawn,
    research_paused_for_rush,
    rush_needs_gateway,
    rush_triggers_defense,
    save_up_spawn,
    scout_verdict,
    should_expand_dynamic,
    should_register_autosupply,
    should_release_waiting_builder,
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

    def test_required_building_gated_on_previous_tier(self):
        from sc2.ids.upgrade_id import UpgradeId
        from sc2.ids.unit_typeid import UnitTypeId as UnitID

        ups = [UpgradeId.PROTOSSSHIELDSLEVEL1, UpgradeId.PROTOSSSHIELDSLEVEL2]
        # L1 没完成:盾 L2 的前置 TWILIGHTCOUNCIL 不补(防早期抢气)
        self.assertEqual(upgrade_tech_buildings(ups), [UnitID.FORGE])
        # L1 完成后:补 TWILIGHTCOUNCIL(Forge 去重不重复)
        self.assertEqual(
            upgrade_tech_buildings(ups, done={UpgradeId.PROTOSSSHIELDSLEVEL1}),
            [UnitID.FORGE, UnitID.TWILIGHTCOUNCIL],
        )

    def test_air_l2_required_fleetbeacon(self):
        from sc2.ids.upgrade_id import UpgradeId
        from sc2.ids.unit_typeid import UnitTypeId as UnitID

        ups = [UpgradeId.PROTOSSAIRWEAPONSLEVEL1, UpgradeId.PROTOSSAIRWEAPONSLEVEL2]
        self.assertEqual(
            upgrade_tech_buildings(ups, done={UpgradeId.PROTOSSAIRWEAPONSLEVEL1}),
            [UnitID.CYBERNETICSCORE, UnitID.FLEETBEACON],
        )


class TestScoutVerdict(unittest.TestCase):
    """O9 侦查情报 → 开局决策三档。"""

    def test_no_intel_is_unknown(self):
        # 探机被杀/没找到主家 → 保守(按疑似 rush)
        self.assertEqual(scout_verdict(intel=False, military_structs=0, early_army=0),
                         "unknown")

    def test_rush_signals(self):
        # 早出兵建筑 ×2(兵营×2/血池+出兵建筑)
        self.assertEqual(scout_verdict(intel=True, military_structs=2, early_army=0),
                         "rush")
        # 早期可见兵力 ≥6(与 early_swarm 阈值同源)
        self.assertEqual(scout_verdict(intel=True, military_structs=0, early_army=6),
                         "rush")

    def test_greedy_when_macro_or_tech(self):
        # 对面开矿/科技开局(有情报、无 rush 迹象) → 维持贪打法
        self.assertEqual(scout_verdict(intel=True, military_structs=1, early_army=2),
                         "greedy")
        self.assertEqual(scout_verdict(intel=True, military_structs=0, early_army=0),
                         "greedy")


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
        kw.setdefault("resource_gap", {"A": 250, "B": 0})
        kw.setdefault("buildable", {"A": True, "B": True})
        kw.setdefault("max_gap", 250)
        return save_up_spawn(spawn or self.SPAWN, **kw)

    def test_behind_share_and_close_truncates_to_p0(self):
        # 占比落后 + 资源缺口 ≤ 阈值 → 只留 p0(攒资源,B 不再 fall-through 吃气)
        out = self._run(counts={"A": 1, "B": 3}, resource_gap={"A": 100, "B": 0})
        self.assertEqual(list(out), ["A"])

    def test_behind_share_and_affordable_truncates_to_p0(self):
        out = self._run(counts={"A": 1, "B": 3}, affordable={"A": True, "B": True})
        self.assertEqual(list(out), ["A"])

    def test_behind_share_but_far_from_affordable_keeps_full_dict(self):
        # 缺口还很大(>阈值) → 不截断,低优先先顶着生产
        out = self._run(counts={"A": 1, "B": 3}, max_gap=50)
        self.assertEqual(set(out), {"A", "B"})

    def test_mineral_bottleneck_does_not_truncate(self):
        # E3h 回归:气 2000+(气缺口=0)但矿差得远(矿缺口=300>250)
        # → resource_gap 取两者大 = 300 > 阈值 → 不截断,p1 在富矿窗口能补位
        out = self._run(counts={"A": 1, "B": 3}, resource_gap={"A": 300, "B": 0})
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

    def test_exempt_anti_air_never_truncated(self):
        # E3c 回归:反空军混编(AA=追猎)触发时,即使航母占比落后要截断,
        # 保命防空兵种也保留 —— 只截副 C(B=风暴)
        spawn = {
            "A": {"proportion": 0.7, "priority": 0},
            "B": {"proportion": 0.3, "priority": 1},
            "AA": {"proportion": 0.3, "priority": 0},
        }
        out = self._run(
            spawn=spawn,
            counts={"A": 1, "B": 2, "AA": 0},
            affordable={"A": False, "B": True, "AA": True},
            resource_gap={"A": 100, "B": 0, "AA": 0},
            buildable={"A": True, "B": True, "AA": True},
            exempt={"AA"},
        )
        self.assertEqual(set(out), {"A", "AA"})

    def test_exempt_absent_from_spawn_is_noop(self):
        out = self._run(counts={"A": 1, "B": 3}, exempt={"AA"})
        self.assertEqual(list(out), ["A"])  # exempt 不在 dict 里 → 行为同前


class TestShouldRegisterAutosupply(unittest.TestCase):
    """O6 守卫 + E3h 水晶紧急通道。"""

    def test_affordable_registers(self):
        self.assertTrue(should_register_autosupply(True, 10))

    def test_broke_but_supply_ok_skips(self):
        # 常态:买不起且人口不紧 → 不注册(O6 防工人钉点)
        self.assertFalse(should_register_autosupply(False, 8))

    def test_supply_emergency_registers_even_broke(self):
        # E3h:卡人口(≤2)时即便买不起也注册,钉一个工人换人口不断链
        self.assertTrue(should_register_autosupply(False, 2))
        self.assertTrue(should_register_autosupply(False, 0))

    def test_custom_emergency_threshold(self):
        self.assertFalse(should_register_autosupply(False, 3, emergency=2))
        self.assertTrue(should_register_autosupply(False, 3, emergency=3))


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
        # 优势:我方 army supply ≥ 敌可见 + 12(敌必须先现身)
        self.assertTrue(self._run(own_army_supply=14, enemy_army_supply=1))
        self.assertFalse(self._run(own_army_supply=11, enemy_army_supply=1))
        self.assertFalse(self._run(own_army_supply=13, enemy_army_supply=2))

    def test_advantage_blocked_when_enemy_unseen(self):
        # E4b 实证:敌可见 0 时不是优势是未知(迷雾藏兵)——禁止优势触发
        self.assertFalse(self._run(own_army_supply=99, enemy_army_supply=0))
        # 爆仓触发不依赖敌情,不受影响
        self.assertTrue(self._run(supply_workers=22, enemy_army_supply=0))

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


class TestResearchPausedForRush(unittest.TestCase):
    """E3 回归:rush 期间研究(prioritize 预留)不得抢占 rush 响应包资源。

    回归出处:e3-carrier-vh-zerg-rush game_02 —— rush 窗口 SHIELDS/AIRWEAPONS
    正在研究,响应包只出 1 叉 2 塔败北。修复后 rush_active → 不注册
    UpgradeController;rush 解除 → 恢复 O8 预留。"""

    def test_rush_active_pauses_research(self):
        self.assertTrue(research_paused_for_rush(True))

    def test_normal_times_research_prioritized(self):
        self.assertFalse(research_paused_for_rush(False))


class TestRushTriggersDefense(unittest.TestCase):
    """E3b 回归:rush 检测成立即铺塔,不再等敌兵压到 40 格。

    回归出处:e3b game_02 —— rush 130s 检测到,首塔 221s 才立,232s 基地掉。
    rush_cannons=False(E1 臂 B 纯叉子)时保持不铺。"""

    def test_rush_active_triggers_defense(self):
        self.assertTrue(rush_triggers_defense(True, True))

    def test_no_rush_no_trigger(self):
        self.assertFalse(rush_triggers_defense(False, True))

    def test_arm_b_no_cannons_even_in_rush(self):
        self.assertFalse(rush_triggers_defense(True, False))


class TestRushNeedsGateway(unittest.TestCase):
    """E3d:rush 敌兵>叉子时追加 gateway(单兵营 28s 一叉是实证瓶颈)。"""

    def _run(self, **kw):
        kw.setdefault("rush_active", True)
        kw.setdefault("rush_zealots", 4)
        kw.setdefault("enemy_army", 8)
        kw.setdefault("zealots", 1)
        kw.setdefault("gateways_have", 1)
        return rush_needs_gateway(**kw)

    def test_outnumbered_adds_gateway(self):
        self.assertTrue(self._run())

    def test_not_outnumbered_no_add(self):
        self.assertFalse(self._run(enemy_army=1, zealots=2))

    def test_cap_respected(self):
        self.assertFalse(self._run(gateways_have=2))

    def test_no_rush_or_no_zealot_response(self):
        self.assertFalse(self._run(rush_active=False))
        self.assertFalse(self._run(rush_zealots=0))  # 臂 C 纯塔不补兵营


class TestPreFleetSpawn(unittest.TestCase):
    """E3e 舰队成型前地面保底:混入/封顶/退出。"""

    SPAWN = {"A": {"proportion": 0.7, "priority": 0},
             "B": {"proportion": 0.3, "priority": 1}}

    def _run(self, **kw):
        kw.setdefault("spawn", self.SPAWN)
        kw.setdefault("floor_id", "Z")
        kw.setdefault("floor_count", 0)
        kw.setdefault("floor_cap", 6)
        kw.setdefault("fleet_online", False)
        return pre_fleet_spawn(**kw)

    def test_mixes_floor_before_fleet(self):
        out = self._run()
        self.assertIn("Z", out)                       # 保底混入
        self.assertEqual(set(out), {"A", "B", "Z"})   # 主配方保留
        self.assertGreater(out["Z"]["priority"], 1)   # 优先级压最低,舰队能产时舰队优先

    def test_cap_stops_floor(self):
        out = self._run(floor_count=6)
        self.assertNotIn("Z", out)

    def test_fleet_online_exits(self):
        out = self._run(fleet_online=True)
        self.assertNotIn("Z", out)
        self.assertEqual(out, self.SPAWN)             # 回归主配方


class TestPreFleetCap(unittest.TestCase):
    """E3f 保底上限随敌兵力伸缩:clamp(base, 敌兵×per_enemy, hard_max)。"""

    def test_scales_with_threat(self):
        # 敌 30 兵 × 0.5 = 15(E3f game_02 的第二波规模)
        self.assertEqual(pre_fleet_cap(6, 0.5, 16, 30), 15)
        self.assertEqual(pre_fleet_cap(6, 0.5, 16, 20), 10)

    def test_peace_time_floor_is_base(self):
        self.assertEqual(pre_fleet_cap(6, 0.5, 16, 0), 6)
        self.assertEqual(pre_fleet_cap(6, 0.5, 16, 10), 6)  # 低于 base 不缩

    def test_hard_max_clamps(self):
        self.assertEqual(pre_fleet_cap(6, 0.5, 16, 999), 16)

    def test_zero_max_keeps_fixed_cap(self):
        # 向后兼容 E3e:不配 max → 固定 cap
        self.assertEqual(pre_fleet_cap(6, 0.5, 0, 30), 6)


class TestFloorArmyDefendsHome(unittest.TestCase):
    """E3g trickle:舰队成型前地面保底兵默认守家。"""

    def test_pre_fleet_and_no_primary_defends(self):
        self.assertTrue(floor_army_defends_home(True, 0))

    def test_primary_online_resumes_offense(self):
        self.assertFalse(floor_army_defends_home(True, 1))

    def test_no_pre_fleet_flow_unchanged(self):
        self.assertFalse(floor_army_defends_home(False, 0))


class TestBuilderReleaseRules(unittest.TestCase):
    """O11 钉点撤回 + O13 气矿卡死判定。"""

    def test_release_after_grace_when_broke(self):
        # O11:钉点 >6s 且仍买不起 → 撤回采矿
        self.assertTrue(should_release_waiting_builder(False, 7.0))

    def test_keep_within_grace(self):
        self.assertFalse(should_release_waiting_builder(False, 3.0))

    def test_keep_when_affordable(self):
        self.assertFalse(should_release_waiting_builder(True, 99.0))

    def test_assimilator_stuck_timeout(self):
        # O13:在建气矿 >45s 没落地 → 判卡死重派
        self.assertTrue(assimilator_attempt_stuck(100.0, 50.0))
        self.assertFalse(assimilator_attempt_stuck(100.0, 80.0))

    def test_defense_syncs_with_nexus(self):
        # E3l:有 Nexus 在建或已多基地 → 分矿塔防立即启动
        self.assertTrue(defense_syncs_with_nexus(1, 1))
        self.assertTrue(defense_syncs_with_nexus(0, 2))
        self.assertFalse(defense_syncs_with_nexus(0, 1))  # 单矿无在建 → 不启动


class TestNexusRebuild(unittest.TestCase):
    """O15:基地清零重建 Nexus 的触发与可行性。"""

    def test_active_only_when_zero_bases(self):
        self.assertTrue(nexus_rebuild_active(0))
        self.assertFalse(nexus_rebuild_active(1))

    def test_viable_needs_workers_and_minerals(self):
        self.assertTrue(nexus_rebuild_viable(10, 1500, 500))   # 有工有矿有钱
        self.assertFalse(nexus_rebuild_viable(0, 1500, 500))   # 没工人
        self.assertFalse(nexus_rebuild_viable(10, 0, 500))     # 全图矿干 → Q5 判负

    def test_viable_needs_bank_for_nexus(self):
        # E4 实证:0 基地 = 零收入(采了交不了),存款 <400 是死局 → 不豁免 Q5
        self.assertFalse(nexus_rebuild_viable(10, 1500, 45))
        self.assertTrue(nexus_rebuild_viable(10, 1500, 400))


class TestExpansionReserve(unittest.TestCase):
    """E3k:开矿触发但买不起 → 攒钱预留(出兵/造农民让位)。"""

    def test_triggered_and_broke_reserves(self):
        self.assertTrue(expansion_reserve_active(True, False))

    def test_affordable_dispatches_normally(self):
        self.assertFalse(expansion_reserve_active(True, True))

    def test_not_triggered_no_reserve(self):
        self.assertFalse(expansion_reserve_active(False, False))


if __name__ == "__main__":
    unittest.main(verbosity=2)
