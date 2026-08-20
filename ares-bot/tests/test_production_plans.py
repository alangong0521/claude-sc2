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
    base_rebuild_active,
    base_defense_anchor,
    builder_borrow_ok,
    builder_is_waiting,
    builder_release_exempt,
    cannon_target_capped,
    cannon_safe_anchor,
    carrier_quota_active,
    carrier_quota_spawn,
    carrier_rally_against_aa,
    carrier_transition_ready,
    carrier_transition_time_box,
    cannon_hard_cap_active,
    recipe_push_exempt,
    scout_credit_fallback_ok,
    power_precheck_stalled,
    forge_rebuild_guarantee_ok,
    carrier_push_safe,
    chrono_first_zealot,
    chrono_forge_first,
    chrono_primary_id,
    defense_anchor_index,
    defense_sprint_active,
    defense_syncs_with_nexus,
    expand_holding_should_abort,
    holding_abort_keep_first_expand,
    holding_allows_cyber,
    dispatch_viable,
    early_scout_verdict,
    expansion_blocked,
    expansion_cannon_count,
    expansion_cannon_min_dynamic,
    expansion_reserve_active,
    escort_pull_cap,
    escort_worker_count,
    escort_stance,
    escort_hard_cap,
    f2_dispatch_guard_bypassed,
    fleet_recall_target,
    extra_production_mineral_gate,
    floor_exits,
    floor_army_defends_home,
    forge_first_probe_yield,
    forge_first_pylon_yield,
    full_pop_all_in,
    full_gas_bases,
    gas_gated_stargate_target,
    gas_target,
    mineral_crisis_gas_stop,
    early_gas_overflow_pull,
    expand_pin_workers_ok,
    multi_expand_threat_ok,
    fb_missing_expand_hold,
    fb_saving_window,
    forge_pin_affordable,
    gas_to_minerals_needed,
    gas_to_minerals_released,
    gas_pull_window_expired,
    townhall_skips_placement,
    fb_fund_window,
    fb_fund_probe_yield,
    fb_fund_cannon_blocked,
    fb_fund_upgrade_kept,
    cannon_global_capped,
    cannon_absolute_capped,
    mothership_economy_ok,
    mothership_window_open,
    ms_window_probe_yield,
    rescue_pylon_anchor,
    second_rescue_pylon_needed,
    cannon_stall_rescue,
    ms_window_fleet_suppressed,
    mothership_supply_ok,
    pin_reanchor,
    reanchor_bases,
    reanchor_cooldown_until,
    zt_forge_pin_gate,
    zt_cannon_pending_probe_yield,
    zt_second_cannon_pin_ok,
    event_throttle_ok,
    tempest_dump_suppressed,
    cannon_capped,
    sg2_pin_economy_ok,
    zt_fast_expand_pin,
    sg_pin_expand_ok,
    zt_zealot_yield,
    zt_vacuum_buffer_caps,
    zt_sg_pin_time_ok,
    pin_deadlock_fuse,
    new_base_defense_pins,
    new_base_cannon_fb_fund_exempt,
    nexus_fund_hold_active,
    nexus_fund_hold_blocks,
    gas_stop_leaking,
    gas_stop_release_blocked,
    carrier_hard_convert_ok,
    manual_cannon_anchor,
    gas_stop_requisition_ok,
    gas_restore_needed,
    gas_restore_done,
    nexus_deal_confirmed,
    nexus_deal_verify_failed,
    nexus_pin_yield_gate,
    cyber_core_watchdog,
    evac_return_gas_stop_remark,
    anchor_retry_ok,
    pin_repin_blocked,
    gas_pull_thresholds,
    fb_fund_ground_yield,
    fb_fund_sg2_blocked,
    fb_fund_probe_brake,
    fb_safe_anchor,
    fb_arrival_guard_active,
    tempest_gas_dump_ok,
    gas_stop_repull_action,
    f2_clamp_supply_cap,
    f2_wave_cannon_floor,
    zt_expand_reserve_exempt,
    expand_exempt_zealot_only,
    oracle_gas_yield,
    new_base_survival_cannon_ok,
    extra_stargate_minerals_ok,
    fb_fund_window_stalled,
    fb_bankrupt_needed,
    fb_bankrupt_cleared,
    fb_fund_gas_gate,
    stargate_deadlock_voidray,
    power_precheck_needed,
    fb_fund_latch_needed,
    fb_latch_stalled,
    sg_idle_reset_needed,
    sg_post_fb_fill,
    power_precheck_covered,
    reanchor_fallback_default,
    cannon_investment_freeze,
    cannon_freeze_clamp,
    fb_latch_pin_allowed,
    nexus_repin_loop_forced,
    fb_rescue_expansion_bypass,
    cyber_core_build_allowed,
    expansion_defense_guard_active,
    timing_defense_chain_active,
    push_enemy_army_gate,
    cyber_core_np_default_fallback,
    stargate_pin_retry_needed,
    sg_gap_pin_needed,
    new_base_f2_cannon_floor,
    nexus_pin_yield_clamp,
    new_base_no_cannon_alarm,
    f2_survival_floor,
    fb_rebuild_latch_needed,
    fb_latch_yields_first_cannon,
    sg_power_reserve_needed,
    fleet_rebuild_watchdog_needed,
    push_commit_aa_retreat,
    fleet_collapse_clock_reset,
    fb_latch_trigger_gated,
    fb_yield_deadlock_fuse,
    pylon_rescue_pin_ok,
    zerg_aa_exemption_capped,
    aa_peak_sticky,
    f2_target_literal,
    nexus_repin_afford_ok,
    transition_push_hold,
    wave_cannon_floor_active,
    wave_cannon_floor_trigger,
    enemy_supply_credited,
    fb_latch_pin_afford_ok,
    sg2_pre_fb_pin_needed,
    sg_prefb_voidray_fill,
    zerg_sg_pin_lane_active,
    blind_push_blocked,
    push_fleet_floor_ok,
    f2_global_cannon_cap,
    sg_rebuild_cooldown_ok,
    zerg_aa_credited,
    zerg_departure_floor_ok,
    zerg_corruptor_departure_blocked,
    force_push_corruptor_ok,
    aa_reeval_due,
    e10_sg2_pin_needed,
    pylon_ring_fallback_anchor,
    tower_sector_fallback_due,
    fleet_formed_release_rush,
    rush_economy_release,
    probe_economy_hard_floor,
    terran_false_rush_release,
    gas_hard_stop_required,
    new_base_cannon_fund_needed,
    nexus_priority_fund_active,
    nexus_fund_probe_hard_floor,
    nexus_fund_should_cut_build_runner,
    mineral_patch_worker_slots,
    healthy_mining_base_target,
    healthy_mining_expand_needed,
    terran_economic_strike_window,
    desperation_push_window,
    anchor_buildable,
    main_defense_bank_fuse,
    zt_defense_at_natural,
    forge_before_first_gateway,
    gateway_chain_after_first_zealot,
    gateway_yields_tech_slots,
    hot_base_index,
    idle_builder_alarm,
    idle_builder_fuse_exempt,
    is_combat_type,
    natural_predefense_allowed,
    nexus_rebuild_active,
    nexus_rebuild_viable,
    oracle_before_fleet_allowed,
    pick_slot_anchor,
    pick_walk_patch,
    pivot_primary_id,
    pre_fleet_cap,
    pre_fleet_spawn,
    probe_floor_cap,
    probe_floor_needed,
    critical_dispatch_exempt,
    hurt_retreat_needed,
    presumed_rush_defense,
    rally_min_for_verdict,
    redispatch_cooled_down,
    rebuild_extra_production_id,
    rebuild_window_spawn,
    resource_contested,
    rescout_verdict,
    RESCOUT_DISPATCH_AT,
    RESCOUT_HARD_DEADLINE,
    research_paused_for_rush,
    reserve_deadlock_break,    rush_deadzone_active,
    rush_hold_batteries,
    rush_needs_gateway,
    rush_cannon_bypass,
    rush_defense_past_holding,
    rush_defers_second_gateway,
    rush_blocks_reserve,
    rush_contact_arms,
    carrier_sg_bonus,
    rush_triggers_defense,
    rush_gas_stop_window,
    rush_worker_escort_needed,
    save_up_spawn,
    serialize_presumed_cannons,
    spawn_pause_reason,
    sprint_blocks_probes,
    sprint_timer_update,
    scout_early_redispatch_needed,
    scout_next_step,
    scout_verdict,
    scout_verdict_timing,
    should_expand_dynamic,
    should_push_advantage,
    should_register_autosupply,
    should_release_waiting_builder,
    stargate_gas_gate_bonus,
    stargate_double_opener,
    tech_yields_to_threat,
    tower_zone_pylon_needed,
    tech_goes_to_expansion,
    tracker_entry_stale,
    core_tech_allowed,
    fb_stall_recovery_needed,
    fleet_expand_holds,
    fleet_exit_allowed,
    fleet_expansion_reserve,
    fleet_gas_starved,
    fleet_no_recall_threshold,
    fleet_rebuild_cannon_cap,
    fleet_rebuild_window,
    fleet_stargate_reserve,
    fleet_supply_buffer_needed,
    fleet_tech_reserve,
    fleet_transition_ready,
    fleet_transition_strong_exit,
    first_zealot_sprint,
    ground_floor_gateways,
    ground_floor_unmet,
    ground_floor_active,
    rush_spawn_fleet_escape,
    tempest_primary_spawn,
    threat_ground_exemption,
    threat_response_active,
    transition_expand_blocked,
    transition_expand_after_first_wave,
    transition_expand_ready,
    transition_expand_reserve,
    transition_battery_floor,
    transition_stargate_allowed,
    transition_cannon_cap,
    transition_gateway_reserve,
    transition_gateway_allowed,
    transition_needs_cybercore,
    transition_needs_gateways,
    transition_pauses_gas,
    transition_probe_yield,
    transition_should_enter,
    transition_timing_sprint,
    transition_expand_at_210,
    cancel_presumed_forge,
    tower_yields_gateway_chain,
    transition_tech_frozen,
    unknown_zt_floor_cap,
    two_base_guard_point,
    main_defense_first,
    unknown_verdict_defense,
    zerg_timing_unknown_floor,
    zerg_timing_expand_allowed,
    zt_wave_read,
    pick_pocket_expansion,
    ring_openness,
    fb_gate_f2_exempt_zt,
    wall_disabled_after,
    wall_escort_needed,
    wall_fallback_due,
    wall_hold_point,
    pick_wall_positions,
    pocket_saving_cannons,
    pivot_stalker_cap,
    carrier_reserve_ok,
    fleet_infra_rebuild_active,
    forge_rebuild_probe_yield,
    upgrade_tech_buildings,
    worker_target,
    zt_golden_window_push,
    zt_prewave_trickle_needed,
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

    def test_o62_recipe_save_up_locks_out_carrier(self):
        # O96 实证回归锁:O62 配方(TEMPEST p0/CARRIER p1)下 save_up=250 会
        # 把 CARRIER 永久摘出 spawn —— p0(暴风)缺口恒 ≤175 < 250,占比落后
        # 就恒截断到 {p0}。这就是 flows.yml carrier 改 save_up: 0 的原因;
        # 若有人把阈值改回去,本测试提醒他先看这条。
        o62 = {
            "TEMPEST": {"proportion": 0.85, "priority": 0},
            "CARRIER": {"proportion": 0.15, "priority": 1},
        }
        out = save_up_spawn(
            o62,
            counts={"TEMPEST": 0, "CARRIER": 0},
            affordable={"TEMPEST": True, "CARRIER": True},
            resource_gap={"TEMPEST": 0, "CARRIER": 0},
            buildable={"TEMPEST": True, "CARRIER": True},
            max_gap=250,
        )
        self.assertEqual(list(out), ["TEMPEST"])  # CARRIER 被截断 = 结构锁

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
        kw.setdefault("now", 0.0)
        kw.setdefault("first_expand_at", 0.0)
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

    def test_first_expand_at_time_trigger(self):
        # O30:首扩时间触发(bases=1 + now>=first_expand_at → True,不等爆仓)
        self.assertTrue(self._run(bases=1, now=200.0, first_expand_at=200.0))
        self.assertTrue(self._run(bases=1, now=250.0, first_expand_at=200.0, supply_workers=0))
        self.assertFalse(self._run(bases=1, now=199.0, first_expand_at=200.0))  # 时间没到
        # 2 矿后(bases>=2)首扩时间不再触发(走爆仓/优势)
        self.assertFalse(self._run(bases=2, now=999.0, first_expand_at=200.0, supply_workers=0))
        # rush 仍拦首扩
        self.assertFalse(self._run(bases=1, now=999.0, first_expand_at=200.0, rush_active=True))

    def test_fleet_and_mineral_gate_blocks_late_expand(self):
        # O160:首扩之后,必须同时满足 fleet≥3 且矿物≥500 才允许继续扩张
        self.assertFalse(
            self._run(
                bases=2, supply_workers=44, minerals=300, fleet_total=0
            )
        )
        self.assertFalse(
            self._run(
                bases=3, supply_workers=66, minerals=499, fleet_total=2
            )
        )
        # O216g:有 fleet 且矿线饱和 → 矿门旁路,允许开(饱和不开=农民浪费人口)
        self.assertTrue(
            self._run(
                bases=2, supply_workers=44, minerals=300, fleet_total=3
            )
        )
        # 有 fleet 但未饱和且矿物不足 → 仍阻止
        self.assertFalse(
            self._run(
                bases=2, supply_workers=20, minerals=300, fleet_total=3
            )
        )
        # 只有矿物没有 fleet → 仍阻止(舰队门不旁路)
        self.assertFalse(
            self._run(
                bases=2, supply_workers=44, minerals=500, fleet_total=0
            )
        )
        # fleet≥3 且 minerals≥500 才放行
        self.assertTrue(
            self._run(
                bases=2, supply_workers=44, minerals=500, fleet_total=3
            )
        )
        # 首扩(bases=1)不受此门限制
        self.assertTrue(
            self._run(
                bases=1, now=200.0, first_expand_at=200.0, minerals=0, fleet_total=0
            )
        )

    def test_hard_saturation_bypasses_all_gates(self):
        # O222:硬饱和(农民 ≥ 22×bases+8)舰队门/矿门全旁路
        self.assertTrue(
            self._run(bases=2, supply_workers=52, minerals=0, fleet_total=0)
        )
        self.assertTrue(
            self._run(bases=2, supply_workers=60, minerals=100, fleet_total=1)
        )
        # 未达硬饱和仍走原门(44 = 软饱和,矿门旁路但舰队门保留)
        self.assertFalse(
            self._run(bases=2, supply_workers=44, minerals=100, fleet_total=0)
        )


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

    def test_early_release_on_big_deficit(self):
        # O139-②:钉点 >3s 且缺口 >5s 收入 → 不等 grace 提前撤回
        self.assertTrue(should_release_waiting_builder(
            False, 3.5, grace=6.0, deficit=100.0, income_5s=40.0))
        # 缺口 5s 收入补得上 → 走 grace(容忍短暂等钱)
        self.assertFalse(should_release_waiting_builder(
            False, 3.5, grace=6.0, deficit=30.0, income_5s=40.0))
        # 3s 内不提前撤(走位帧容差)
        self.assertFalse(should_release_waiting_builder(
            False, 2.0, grace=6.0, deficit=100.0, income_5s=40.0))
        # TOWNHALL:early_age=30 → 开矿预走位不被提前通道误撤(O21 语义)
        self.assertFalse(should_release_waiting_builder(
            False, 10.0, grace=30.0, deficit=300.0, income_5s=40.0,
            early_age=30.0))

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

    def test_townhall_longer_grace_o21(self):
        # O21:TOWNHALL(Nexus)用 grace=30(开矿攒 400 矿需时间);原 6s 撤会误撤开矿
        self.assertFalse(should_release_waiting_builder(False, 10.0, grace=30.0))
        self.assertFalse(should_release_waiting_builder(False, 29.0, grace=30.0))
        self.assertTrue(should_release_waiting_builder(False, 31.0, grace=30.0))

    def test_opening_short_grace_o21b(self):
        # O21b:开局普通建筑 grace=1s(等>1s 就撤回采矿,不滚雪球)
        self.assertTrue(should_release_waiting_builder(False, 1.5, grace=1.0))
        self.assertFalse(should_release_waiting_builder(False, 0.5, grace=1.0))


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


class TestBaseRebuild(unittest.TestCase):
    """base_rebuild_active:基地被打掉后的重建模式。E6b 回归实证:
    只看「当前<目标」会在开局(1<max_bases=4)误触发,造农民/出兵整局被掐死
    (bench e6b 五局 8 农民封顶、零兵营、~208s 全灭)——必须有「真的丢过基地」门。"""

    def test_opening_one_base_does_not_trigger(self):
        # 开局:当前 1 = 峰值 1 < 目标 4 → 不触发(E6b 回归判例)
        self.assertFalse(base_rebuild_active(1, 1, 4, False))
        self.assertFalse(base_rebuild_active(1, 1, 4, True))

    def test_triggers_only_after_actual_base_loss(self):
        # 开到 2 矿后被打回 1 → 峰值 2 > 当前 1 → 触发
        self.assertTrue(base_rebuild_active(1, 2, 4, True))
        # 没丢过(峰值=当前)即便 < 目标也不触发
        self.assertFalse(base_rebuild_active(2, 2, 4, True))

    def test_rush_and_no_target_gate(self):
        self.assertFalse(base_rebuild_active(1, 2, 4, True, rush_active=True))
        self.assertFalse(base_rebuild_active(1, 2, None, True))  # 无 max_bases 流派


class TestIdleBuilderCriteria(unittest.TestCase):
    """O19 干等建造判据:builder_is_waiting / idle_builder_alarm。"""

    def test_waiting_only_when_tracked_and_idle_and_not_exempt(self):
        self.assertTrue(builder_is_waiting(True, is_idle=True, exempt_role=False))
        self.assertFalse(builder_is_waiting(False, True, False))   # 无建造指派
        self.assertFalse(builder_is_waiting(True, False, False))   # 走位/建造中
        self.assertFalse(builder_is_waiting(True, True, True))     # 侦查/接管/E6

    def test_alarm_threshold(self):
        # o19fix 复验后阈值 1s→3s:1-2s 短等是常态噪声(存款贴 0 的花钱风格),
        # 3s 仍 < O11 6s 撤回线,真钉点必曝光
        self.assertFalse(idle_builder_alarm(0.5))
        self.assertFalse(idle_builder_alarm(1.5))
        self.assertFalse(idle_builder_alarm(3.0))   # 边界:>3s 才算
        self.assertTrue(idle_builder_alarm(3.5))
        self.assertTrue(idle_builder_alarm(10.0))


class TestRedispatchCooledDown(unittest.TestCase):
    """O19 二轮:O11 撤回后的重派冷却(redispatch_cooled_down)。

    o19fix 实证:收入高时 dispatch_viable 恒真,「派工→钉 6s→O11 撤回→
    下帧又派」循环(macro g05 同 tag 6 次 episode)——冷却断环。"""

    def test_no_prior_release_allows_dispatch(self):
        self.assertTrue(redispatch_cooled_down(None, now=100.0))

    def test_within_cooldown_blocks(self):
        self.assertFalse(redispatch_cooled_down(100.0, now=110.0))   # 10s < 15s
        self.assertFalse(redispatch_cooled_down(100.0, now=114.9))

    def test_after_cooldown_allows(self):
        self.assertTrue(redispatch_cooled_down(100.0, now=115.0))
        self.assertTrue(redispatch_cooled_down(100.0, now=200.0))


class TestScoutVerdictTiming(unittest.TestCase):
    """E7/O16 侦查断链:scout_verdict_timing 时机决策。

    e6c2 实证根因:探机 100s 出发路 ~40s,Rush 局敌兵 129-141s 到脸触发 O4
    撤回,4/5 局探机送达前被拉回 → verdict 落「无情报→保守rush」(结论碰巧对,
    链条是断的)。判据要区分「还没走到」(等/补派)和「尽力未送达」(才按 rush)。"""

    def test_pending_before_verdict_window(self):
        self.assertEqual(
            scout_verdict_timing(False, True, False, False, now=100.0), "pending"
        )

    def test_intel_delivered_evaluates_immediately(self):
        # 有情报:不看探机状态,直接评(即使早于硬底线)
        self.assertEqual(
            scout_verdict_timing(True, False, False, False, now=170.0), "evaluate"
        )
        self.assertEqual(
            scout_verdict_timing(True, True, False, True, now=200.0), "evaluate"
        )

    def test_no_intel_scout_en_route_waits(self):
        # 探机还在路上(慢/绕路) → 等,不急着按 rush
        self.assertEqual(
            scout_verdict_timing(False, True, False, False, now=180.0), "wait"
        )

    def test_dead_scout_redispatches_once_when_not_rush(self):
        # 探机死/被撤回 + 没补派过 + 非 rush → 补派一次
        self.assertEqual(
            scout_verdict_timing(False, False, False, False, now=170.0),
            "redispatch",
        )
        # 补派过的再断 → 不再补(防无限续命送死)→ fallback
        self.assertEqual(
            scout_verdict_timing(False, False, True, False, now=200.0), "fallback"
        )

    def test_no_redispatch_during_rush(self):
        # rush 中不补派(走进狗群=白送,且 rush 响应包已在跑) → 直接 fallback
        # (= 旧「无情报→保守rush」行为,e6c2 各局路径不变)
        self.assertEqual(
            scout_verdict_timing(False, False, False, True, now=170.0), "fallback"
        )

    def test_hard_deadline_forces_fallback(self):
        # 探机一直在路上但过了硬底线 → 尽力未送达,按 rush
        self.assertEqual(
            scout_verdict_timing(False, True, False, False, now=231.0), "fallback"
        )


class TestRallyMinForVerdict(unittest.TestCase):
    """E8/O17/O18:侦查结论驱动 C3a 集结阈值(rally_min_for_verdict)。"""

    def test_greedy_halves_rally(self):
        # O17:敌贪 → 小股提早压,stalker 14→7,dt 4→2
        self.assertEqual(rally_min_for_verdict(14, "greedy"), 7)
        self.assertEqual(rally_min_for_verdict(4, "greedy"), 2)
        self.assertEqual(rally_min_for_verdict(0, "greedy"), 0)  # 关着的保持关

    def test_rush_tightens_with_floor(self):
        # O18:敌 rush → 收紧;base 0 的 carrier 也至少有 floor 6 的纪律
        self.assertEqual(rally_min_for_verdict(14, "rush"), 28)
        self.assertEqual(rally_min_for_verdict(4, "rush"), 8)
        self.assertEqual(rally_min_for_verdict(0, "rush"), 6)

    def test_unknown_and_none_keep_base(self):
        # 保守:未评估/无情报兜底 → 维持现状
        self.assertEqual(rally_min_for_verdict(14, "unknown"), 14)
        self.assertEqual(rally_min_for_verdict(14, None), 14)
        self.assertEqual(rally_min_for_verdict(0, None), 0)


class TestDispatchViable(unittest.TestCase):
    """O19 钉点修复:dispatch_viable —— 到位可负担才派建造工人。

    e7e8 bench 实证:ares BuildStructure/ExpansionController 不查 can_afford,
    PHOTONCANNON 干等 9-21 次/局、NEXUS 2-7 次/局。缺钱时正确行为是不派
    (农民照采,建筑等下帧),不是派了再撤(E4c 前科)。"""

    def test_affordable_now_dispatches(self):
        self.assertTrue(dispatch_viable(200, 10.0, 5.0, 150))   # 现钱就够
        self.assertTrue(dispatch_viable(400, 0.0, 30.0, 400))   # 无收入但现钱够

    def test_projected_affordable_on_arrival_dispatches(self):
        # 矿 120 + 路上 5s×10/s = 170 ≥ 150 → 派(到位即开工,零钉点)
        self.assertTrue(dispatch_viable(120, 10.0, 5.0, 150))
        # Nexus 预走位(E3k 保留):矿 200 + 25s×8/s = 400 ≥ 400 → 派
        self.assertTrue(dispatch_viable(200, 8.0, 25.0, 400))

    def test_not_affordable_even_on_arrival_holds(self):
        # 矿 20 + 5s×8/s = 60 < 150 → 不派(rush 矿紧钉点根因,修的就是这个)
        self.assertFalse(dispatch_viable(20, 8.0, 5.0, 150))
        # 矿 50 + 25s×8/s = 250 < 400 → Nexus 不预走位
        self.assertFalse(dispatch_viable(50, 8.0, 25.0, 400))
        self.assertFalse(dispatch_viable(0, 0.0, 5.0, 150))


class TestCannonTargetCapped(unittest.TestCase):
    """Macro 修复(诊断 #2):憋舰队期塔重建限流(cannon_target_capped)。

    o19b-macro 实证:g03 同时 16 座塔≈2400 矿≈7 艘航母,气 2200+ 烂掉矿贴 0。
    矿 < 舰队矿价且非 rush → 压回 min;憋得起 / rush 期 → 原动态数。"""

    def test_poor_and_not_rush_caps_to_min(self):
        # 矿 100 < 350,敌兵推动态数到 8 → 压回 min 3
        self.assertEqual(cannon_target_capped(8, 3, 100, 350, False), 3)
        self.assertEqual(cannon_target_capped(8, 3, 0, 350, False), 3)

    def test_rich_keeps_dynamic(self):
        # 矿 ≥ 舰队矿价(憋得起)→ 不限流
        self.assertEqual(cannon_target_capped(8, 3, 350, 350, False), 8)
        self.assertEqual(cannon_target_capped(8, 3, 900, 350, False), 8)

    def test_rush_never_caps(self):
        # rush 期保命优先(六连动不变),矿再紧也不限
        self.assertEqual(cannon_target_capped(8, 3, 0, 350, True), 8)

    def test_dynamic_below_min_untouched(self):
        # 动态数本来 ≤ min(理论防御) → 不抬不降
        self.assertEqual(cannon_target_capped(2, 3, 100, 350, False), 2)

    def test_gas_rich_mineral_poor_fleet_small_caps_to_min(self):
        # O160: 气体富余(≥600)、矿<500、舰队<5 → 即使矿≥350 也压回 min
        self.assertEqual(
            cannon_target_capped(16, 4, 450, 350, False, vespene=700, fleet_total=4),
            4,
        )
        self.assertEqual(
            cannon_target_capped(16, 4, 499, 350, False, vespene=600, fleet_total=4),
            4,
        )

    def test_gas_rich_but_fleet_large_no_extra_cap(self):
        # 舰队已成型且矿够舰队造价 → O160 gas-rich 额外限流不触发，老逻辑也不压
        self.assertEqual(
            cannon_target_capped(16, 4, 400, 350, False, vespene=1200, fleet_total=10),
            16,
        )

    def test_mineral_floor_caps_regardless_of_fleet(self):
        # O160: 矿物跌破 250 硬地板 → 舰队再大也限流，防止塔抽干舰队矿
        self.assertEqual(
            cannon_target_capped(16, 4, 249, 350, False, vespene=1200, fleet_total=10),
            4,
        )
        self.assertEqual(
            cannon_target_capped(16, 4, 100, 350, False, vespene=0, fleet_total=10),
            4,
        )

    def test_low_base_count_no_cap(self):
        # O157 / O161: 基地压缩到 ≤2 个时若舰队已成规模(≥3)才不限流
        self.assertEqual(
            cannon_target_capped(12, 6, 100, 350, False, bases=2, fleet_total=3),
            12,
        )
        self.assertEqual(
            cannon_target_capped(12, 6, 300, 350, False, vespene=1200, fleet_total=6, bases=1),
            12,
        )
        # 基地 >2 时原逻辑不变
        self.assertEqual(
            cannon_target_capped(12, 6, 100, 350, False, bases=3),
            6,
        )

    def test_low_base_count_fleet_small_still_caps(self):
        # O161: 基地压缩但舰队未成规模(<3)时，继续限流保经济，不盲目堆塔
        self.assertEqual(
            cannon_target_capped(12, 6, 100, 350, False, bases=2, fleet_total=0),
            6,
        )
        self.assertEqual(
            cannon_target_capped(12, 6, 300, 350, False, vespene=1200, fleet_total=2, bases=1),
            6,
        )


class TestExpansionCannonMinDynamic(unittest.TestCase):
    """O161/O179: 舰队成型前降低分矿塔 baseline。"""

    def test_zero_fleet_caps_to_one(self):
        # O216:zero_fleet_cap 1→2,fleet=0 仍需 2 座保命塔配合 gateway 堵口。
        self.assertEqual(expansion_cannon_min_dynamic(6, 0, fleet_min=3, early_cap=3), 2)
        self.assertEqual(expansion_cannon_min_dynamic(3, 0, fleet_min=3, early_cap=3), 2)
        self.assertEqual(expansion_cannon_min_dynamic(1, 0, fleet_min=3, early_cap=3), 1)

    def test_fleet_small_caps_to_early_cap(self):
        self.assertEqual(expansion_cannon_min_dynamic(6, 1, fleet_min=3, early_cap=3), 3)
        self.assertEqual(expansion_cannon_min_dynamic(6, 2, fleet_min=3, early_cap=3), 3)

    def test_fleet_large_restores_min(self):
        self.assertEqual(expansion_cannon_min_dynamic(6, 3, fleet_min=3, early_cap=3), 6)
        self.assertEqual(expansion_cannon_min_dynamic(6, 5, fleet_min=3, early_cap=3), 6)

    def test_early_cap_does_not_raise_min(self):
        self.assertEqual(expansion_cannon_min_dynamic(2, 1, fleet_min=3, early_cap=3), 2)

    def test_zero_fleet_cap_respects_low_min(self):
        self.assertEqual(expansion_cannon_min_dynamic(0, 0, fleet_min=3, early_cap=3), 0)


class TestThreatResponse(unittest.TestCase):
    """E9 中局威胁响应:threat_response_active / threat_ground_exemption。

    macro-fix1 实证:敌中局一波(15-25 作战单位)到脸时 bot 无响应(继续开矿/
    憋航母/塔被限流)。判据:敌可见 supply ≥ max(10, 我方×1.5) 激活,
    < max(6, 我方×1.0) 才解除(滞回)。"""

    def test_activates_on_overwhelming_visible_supply(self):
        # 敌 20 supply vs 我 8(≈6 叉+先知) → 激活(macro-fix1 典型画面)
        self.assertTrue(threat_response_active(20, 8))
        self.assertTrue(threat_response_active(12, 8))   # 12 ≥ 8×1.5
        self.assertTrue(threat_response_active(10, 0))   # 绝对下限 10

    def test_does_not_activate_on_parry_or_small(self):
        self.assertFalse(threat_response_active(11, 8))  # 11 < 12
        self.assertFalse(threat_response_active(9, 0))   # 不到绝对下限
        self.assertFalse(threat_response_active(0, 0))

    def test_hysteresis_holds_until_clear_line(self):
        # 已激活:敌 10 掉到 8、我 8 → 8 ≥ max(6,8)=8 → 仍激活(滞回)
        self.assertTrue(threat_response_active(8, 8, currently_active=True))
        # 掉到 5 < 6 → 解除
        self.assertFalse(threat_response_active(5, 8, currently_active=True))
        # 我方涨上来:敌 10 我 12 → 10 < 12 → 解除
        self.assertFalse(threat_response_active(10, 12, currently_active=True))

    def test_ground_exemption_picks_only_ground(self):
        from sc2.ids.unit_typeid import UnitTypeId as UnitID
        spawn = {UnitID.CARRIER: {}, UnitID.TEMPEST: {}, UnitID.ZEALOT: {},
                 UnitID.STALKER: {}}
        flying = {UnitID.CARRIER, UnitID.TEMPEST}
        self.assertEqual(
            threat_ground_exemption(spawn, flying),
            {UnitID.ZEALOT, UnitID.STALKER},
        )
        self.assertEqual(threat_ground_exemption({}, flying), set())


class TestStrategyPivot(unittest.TestCase):
    """策略 pivot(侦查驱动):pivot_primary_id / tempest_primary_spawn /
    carrier_transition_ready。

    司令硬性约束:分流只读 E7 verdict(侦查结论),不读 --ai-build。
    未判定(None)/unknown/rush → 保守默认(航母主 C=现状),绝不按 Macro 打。"""

    def test_primary_selection_by_verdict(self):
        from sc2.ids.unit_typeid import UnitTypeId as UnitID
        C, T = UnitID.CARRIER, UnitID.TEMPEST
        self.assertEqual(pivot_primary_id("greedy", C, T), T)   # 判非rush → 风暴主C
        self.assertEqual(pivot_primary_id("rush", C, T), C)     # rush → 维持现状
        self.assertEqual(pivot_primary_id("unknown", C, T), C)  # 未送达 → 保守
        self.assertEqual(pivot_primary_id(None, C, T), C)       # 未判定 → 保守

    def test_tempest_primary_spawn_swaps_priority_keeps_proportion(self):
        from sc2.ids.unit_typeid import UnitTypeId as UnitID
        spawn = {
            UnitID.CARRIER: {"proportion": 0.7, "priority": 0},
            UnitID.TEMPEST: {"proportion": 0.3, "priority": 1},
        }
        out = tempest_primary_spawn(spawn, UnitID.CARRIER, UnitID.TEMPEST)
        self.assertEqual(out[UnitID.TEMPEST], {"proportion": 0.3, "priority": 0})
        self.assertEqual(out[UnitID.CARRIER], {"proportion": 0.7, "priority": 1})
        # 原 dict 不被改(纯函数)
        self.assertEqual(spawn[UnitID.CARRIER]["priority"], 0)

    def test_tempest_primary_spawn_missing_unit_is_noop(self):
        from sc2.ids.unit_typeid import UnitTypeId as UnitID
        spawn = {UnitID.TEMPEST: {"proportion": 1.0, "priority": 0}}
        self.assertEqual(
            tempest_primary_spawn(spawn, UnitID.CARRIER, UnitID.TEMPEST), spawn
        )

    def test_transition_by_time_or_fleet_count(self):
        self.assertFalse(carrier_transition_ready(400.0, 5))
        self.assertTrue(carrier_transition_ready(600.0, 3))   # 时间到(压不住→转)
        self.assertTrue(carrier_transition_ready(450.0, 10))  # 风暴海成型→转
        # 阈值走参数不硬编码
        self.assertFalse(carrier_transition_ready(450.0, 9, at_time=700, tempest_cap=12))


class TestCarrierQuota(unittest.TestCase):
    """O155: carrier 配额机制 —— 暴风海成型后强制补航母。"""

    def test_quota_only_for_carrier_flow(self):
        self.assertFalse(carrier_quota_active(
            "tempest", True, tempest_count=15, carrier_count=0
        ))
        self.assertTrue(carrier_quota_active(
            "carrier", True, tempest_count=15, carrier_count=0
        ))

    def test_quota_needs_fleet_online(self):
        self.assertFalse(carrier_quota_active(
            "carrier", False, tempest_count=15, carrier_count=0
        ))

    def test_quota_triggered_when_fleet_min_met_and_carrier_low(self):
        # fleet_min 按暴风+航母合计算
        self.assertTrue(carrier_quota_active(
            "carrier", True, tempest_count=12, carrier_count=0,
            fleet_min=12, carrier_target=4
        ))
        self.assertTrue(carrier_quota_active(
            "carrier", True, tempest_count=8, carrier_count=4,
            fleet_min=12, carrier_target=5
        ))
        # O156 fallback：fleet_min=12 未到，但 11 暴风 0 航母也必须出航母
        self.assertTrue(carrier_quota_active(
            "carrier", True, tempest_count=11, carrier_count=0,
            fleet_min=12, carrier_target=4
        ))
        self.assertFalse(carrier_quota_active(
            "carrier", True, tempest_count=8, carrier_count=4,
            fleet_min=12, carrier_target=4
        ))

    def test_o352_default_threshold_four_and_first_carrier_fallback(self):
        # O352-①: 默认阈值从 8 降到 4(o351 18 局暴风峰值 0-8,阈值 8 不可达)
        self.assertTrue(carrier_quota_active(
            "carrier", True, tempest_count=4, carrier_count=0
        ))
        # 3 暴风 0 航母 → fallback(O352-① 门槛 6→3)
        self.assertTrue(carrier_quota_active(
            "carrier", True, tempest_count=3, carrier_count=0
        ))
        # 2 暴风 0 航母 → 舰队规模还不够,不触发
        self.assertFalse(carrier_quota_active(
            "carrier", True, tempest_count=2, carrier_count=0
        ))
        # 3+ 暴风但已有 1 航母且总数 ≥4 → 主判据触发(航母配额未满)
        self.assertTrue(carrier_quota_active(
            "carrier", True, tempest_count=6, carrier_count=1
        ))
        # 总数 <4 且已有 1 航母 → fallback 不触发(等舰队成型)
        self.assertFalse(carrier_quota_active(
            "carrier", True, tempest_count=2, carrier_count=1
        ))

    def test_quota_counts_pending_fleet(self):
        # O156: 在产/在队列的舰队计入总数，避免“差一艘永远到不了阈值”。
        self.assertTrue(carrier_quota_active(
            "carrier", True, tempest_count=7, carrier_count=0,
            pending_tempest=1, pending_carrier=0,
        ))
        self.assertFalse(carrier_quota_active(
            "carrier", True, tempest_count=7, carrier_count=0,
            pending_tempest=0, pending_carrier=0,
            fleet_min=12,
        ))
        # 0 航母但已有航母在产 → fallback 不触发（等那艘航母完工）。
        # (O352-① 后默认 fleet_min=4 会被主判据抢先触发,显式 12 保持
        # 本用例语义)
        self.assertFalse(carrier_quota_active(
            "carrier", True, tempest_count=6, carrier_count=0,
            pending_tempest=0, pending_carrier=1,
            fleet_min=12,
        ))

    def test_quota_spawn_swaps_priority(self):
        from sc2.ids.unit_typeid import UnitTypeId as UnitID
        spawn = {
            UnitID.TEMPEST: {"proportion": 0.85, "priority": 0},
            UnitID.CARRIER: {"proportion": 0.15, "priority": 1},
        }
        out = carrier_quota_spawn(spawn, UnitID.CARRIER, UnitID.TEMPEST)
        self.assertEqual(out[UnitID.CARRIER]["priority"], 0)
        self.assertEqual(out[UnitID.TEMPEST]["priority"], 1)
        self.assertEqual(out[UnitID.CARRIER]["proportion"], 0.15)
        self.assertEqual(out[UnitID.TEMPEST]["proportion"], 0.85)

    def test_quota_spawn_missing_unit_is_noop(self):
        from sc2.ids.unit_typeid import UnitTypeId as UnitID
        spawn = {UnitID.TEMPEST: {"proportion": 1.0, "priority": 0}}
        self.assertEqual(
            carrier_quota_spawn(spawn, UnitID.CARRIER, UnitID.TEMPEST), spawn
        )


class TestIsCombatType(unittest.TestCase):
    """P1 作战单位口径:is_combat_type —— 排除侦查/运输,QUEEN 保留。

    E10 bench 诊断:旧口径「非工人即算兵」把 OVERLORD 算进作战单位,
    Zerg Macro 常规运营在 ~170s 必 ≥6 → scout_verdict/early_swarm 误判 rush。"""

    def test_workers_and_scouts_excluded(self):
        from sc2.ids.unit_typeid import UnitTypeId as UnitID
        for uid in (UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE,
                    UnitID.OVERLORD, UnitID.OVERSEER, UnitID.OVERLORDTRANSPORT):
            self.assertFalse(is_combat_type(uid), uid.name)

    def test_combat_units_kept(self):
        from sc2.ids.unit_typeid import UnitTypeId as UnitID
        for uid in (UnitID.QUEEN, UnitID.ZERGLING, UnitID.ROACH,
                    UnitID.HYDRALISK, UnitID.MARINE, UnitID.ZEALOT):
            self.assertTrue(is_combat_type(uid), uid.name)

    def test_zerg_macro_opener_not_misjudged_as_rush(self):
        # 实测场景(E10-macro):pool×1 + HATCHERY + overlord×6 + queen×2 + ling×2
        # → 军事建筑 1、作战单位 4(queen×2+ling×2,overlord 不计)→ 判 greedy
        from sc2.ids.unit_typeid import UnitTypeId as UnitID
        seen = (
            [UnitID.OVERLORD] * 6 + [UnitID.QUEEN] * 2 + [UnitID.ZERGLING] * 2
            + [UnitID.DRONE] * 15
        )
        early_army = sum(1 for t in seen if is_combat_type(t))
        self.assertEqual(early_army, 4)
        self.assertEqual(
            scout_verdict(intel=True, military_structs=1, early_army=early_army),
            "greedy",
        )
        # 对照:overlord 若计入(旧口径)early_army=10 → 必误判 rush
        self.assertEqual(
            scout_verdict(intel=True, military_structs=1, early_army=10), "rush"
        )


class TestP2StargateLiberation(unittest.TestCase):
    """P2 pivot 星门产能解放:extra_production_mineral_gate /
    stargate_gas_gate_bonus(+gas_gated_stargate_target bonus) / chrono_primary_id。
    pivot 开/关两分支都测——非 pivot 行为必须零变化。"""

    def test_mineral_gate(self):
        self.assertEqual(extra_production_mineral_gate(False), 400.0)  # 非 pivot 原样
        self.assertEqual(
            extra_production_mineral_gate(
                False, fleet_beacon_ready=True, first_tempest_seen=True
            ),
            400.0,
        )  # 非 pivot 全条件满足也原样
        # pivot+FB就绪 但首艘 TEMPEST 未出 → 守 400(E10d:追加星门抢首艘生产窗)
        self.assertEqual(
            extra_production_mineral_gate(True, fleet_beacon_ready=True), 400.0
        )
        # pivot+FB就绪+首艘已出/在产 → 豁免为 0(放手追加)
        self.assertEqual(
            extra_production_mineral_gate(
                True, fleet_beacon_ready=True, first_tempest_seen=True
            ),
            0.0,
        )
        # pivot 但 FB 未就绪 → 保 400(先保前置科技,E10c)
        self.assertEqual(
            extra_production_mineral_gate(
                True, fleet_beacon_ready=False, first_tempest_seen=True
            ),
            400.0,
        )

    def test_gas_rich_mineral_poor_raises_gate(self):
        # O157: 气体烂银行且矿物紧缺、舰队未成规模时，追加产能矿门抬高到 600
        self.assertEqual(
            extra_production_mineral_gate(
                False,
                vespene=1500,
                minerals=300,
                fleet_total=6,
            ),
            600.0,
        )
        # 舰队已成型或气体不够时原样
        self.assertEqual(
            extra_production_mineral_gate(
                False,
                vespene=1500,
                minerals=300,
                fleet_total=10,
            ),
            400.0,
        )
        self.assertEqual(
            extra_production_mineral_gate(
                False,
                vespene=500,
                minerals=300,
                fleet_total=6,
            ),
            400.0,
        )

    def test_oracle_before_fleet_gate(self):
        # A2:非 pivot 随时可造(零变化);pivot 必须等首艘 TEMPEST
        self.assertTrue(oracle_before_fleet_allowed(False, False))
        self.assertTrue(oracle_before_fleet_allowed(False, True))
        self.assertFalse(oracle_before_fleet_allowed(True, False))
        self.assertTrue(oracle_before_fleet_allowed(True, True))

    def test_oracle_after_fleet_transition_gate(self):
        # O96(o95 局3/局4):转舰队后非 pivot 也等首舰(先知别抢首舰生产窗);
        # 第三参缺省 False → 旧签名行为不变
        self.assertFalse(oracle_before_fleet_allowed(False, False, True))
        self.assertTrue(oracle_before_fleet_allowed(False, True, True))
        self.assertFalse(oracle_before_fleet_allowed(True, False, True))

    def test_gas_gate_bonus(self):
        self.assertEqual(stargate_gas_gate_bonus(False), 1)
        self.assertEqual(stargate_gas_gate_bonus(True), 2)   # 单矿 2→3,不一步到 4
        # 端到端:单矿满采 2 气 → 常规 2 星门 / pivot 3 星门
        self.assertEqual(gas_gated_stargate_target(6, [2]), 2)
        self.assertEqual(gas_gated_stargate_target(6, [2], bonus=2), 3)
        self.assertEqual(gas_gated_stargate_target(6, [2, 2], bonus=2), 4)

    def test_chrono_primary(self):
        from sc2.ids.unit_typeid import UnitTypeId as UnitID
        self.assertEqual(
            chrono_primary_id(False, UnitID.CARRIER, UnitID.TEMPEST), UnitID.CARRIER
        )
        self.assertEqual(
            chrono_primary_id(True, UnitID.CARRIER, UnitID.TEMPEST), UnitID.TEMPEST
        )


class TestExpansionBlocked(unittest.TestCase):
    """B1(E9 停开矿 Macro 适配):expansion_blocked 四因子分支。
    rush 恒停;非 pivot 按 threat;pivot 改「敌压家 40 格」才停。"""

    def test_rush_always_blocks(self):
        for pivot in (False, True):
            for threat in (False, True):
                self.assertTrue(
                    expansion_blocked(True, threat, pivot, False),
                    (pivot, threat),
                )

    def test_non_pivot_follows_enemy_near_home(self):
        # O29:非 pivot 也走 enemy_near_home(扩散 pivot 修复——threat 常驻不再锁死)
        # bases>=2:敌压家停,threat 不停(原非 pivot threat 停已废)
        self.assertTrue(expansion_blocked(False, True, False, True, bases=3))    # 压家停
        self.assertFalse(expansion_blocked(False, True, False, False, bases=3))  # threat 不停

    def test_first_expand_release_o29(self):
        # O29:首扩(bases<=1)放行,不管 threat/near_home(carrier 早开 2 矿)
        self.assertFalse(expansion_blocked(False, True, False, True, bases=1))
        self.assertFalse(expansion_blocked(False, True, True, True, bases=1))
        # 2 矿后(bases>=2)按 enemy_near_home
        self.assertTrue(expansion_blocked(False, True, False, True, bases=2))

    def test_pivot_ignores_threat_unless_enemy_at_home(self):
        # pivot:threat 常驻也不停开(Macro 修复核心)
        self.assertFalse(expansion_blocked(False, True, True, False))
        # 敌作战单位压到家 40 格 → 停(rush 同款语义),与 threat 无关
        self.assertTrue(expansion_blocked(False, True, True, True))
        self.assertTrue(expansion_blocked(False, False, True, True))
        self.assertFalse(expansion_blocked(False, False, True, False))


class TestFloorExits(unittest.TestCase):
    """C1:floor 退出判据 —— 主 C 上线 且 地面 ≥4 才退;打穿继续补叉。"""

    def test_no_primary_never_exits(self):
        self.assertFalse(floor_exits(0, 10))

    def test_primary_online_with_ground_exits(self):
        # 旧行为:主 C>0 且地面够 → 退出(零变化面)
        self.assertTrue(floor_exits(1, 8))
        self.assertTrue(floor_exits(1, 4))

    def test_ground_wiped_stays_active(self):
        # C1 核心:舰队在线但地面被打穿 → 不退,继续补叉(trickle 根因)
        self.assertFalse(floor_exits(1, 3))
        self.assertFalse(floor_exits(2, 0))


class TestExpansionReserve(unittest.TestCase):
    """E3k:开矿触发但买不起 → 攒钱预留(出兵/造农民让位)。"""

    def test_triggered_and_broke_reserves(self):
        self.assertTrue(expansion_reserve_active(True, False))

    def test_affordable_dispatches_normally(self):
        self.assertFalse(expansion_reserve_active(True, True))

    def test_not_triggered_no_reserve(self):
        self.assertFalse(expansion_reserve_active(False, False))


class TestCarrierRallyAgainstAA(unittest.TestCase):
    """O23:航母流且敌有对空威胁时,航母数<gate → 守家攒兵(1-2 航母撞雷神/维京=送)。"""

    def test_non_carrier_flow_never_holds(self):
        # 非 carrier 流(tempest/stalker/dt)恒 False,基线零变化
        for flow in ("tempest", "stalker", "dt"):
            self.assertFalse(carrier_rally_against_aa(flow, 0, 10))
            self.assertFalse(carrier_rally_against_aa(flow, 2, 5))

    def test_no_enemy_aa_never_holds(self):
        # carrier 但敌无对空威胁 → 不守(没威胁不必攒)
        self.assertFalse(carrier_rally_against_aa("carrier", 1, 0))
        self.assertFalse(carrier_rally_against_aa("carrier", 2, 0))

    def test_carrier_below_gate_with_aa_holds(self):
        # carrier + 敌有防空 + 航母<3 → 守家攒兵
        self.assertTrue(carrier_rally_against_aa("carrier", 0, 4))
        self.assertTrue(carrier_rally_against_aa("carrier", 1, 2))
        self.assertTrue(carrier_rally_against_aa("carrier", 2, 10))  # 2 < 3

    def test_carrier_at_or_above_gate_advances(self):
        # 航母攒够(≥gate)→ 出击
        self.assertFalse(carrier_rally_against_aa("carrier", 3, 10))
        self.assertFalse(carrier_rally_against_aa("carrier", 5, 20))

    def test_gate_param_overridable(self):
        # gate 参数化(默认 3,可调)
        self.assertTrue(carrier_rally_against_aa("carrier", 3, 5, gate=5))
        self.assertFalse(carrier_rally_against_aa("carrier", 5, 5, gate=5))


class TestBaseDefenseAnchor(unittest.TestCase):
    """O38(司令观察·建筑学):分矿塔/电池落「朝敌正面」,主基走 ramp 口。"""

    def test_main_uses_ramp_rally(self):
        self.assertEqual(
            base_defense_anchor(True, (10, 10), (90, 90), main_rally_xy=(20, 20)),
            (20, 20),
        )

    def test_main_without_rally_no_override(self):
        self.assertIsNone(
            base_defense_anchor(True, (10, 10), (90, 90), main_rally_xy=None)
        )

    def test_expansion_anchor_toward_enemy(self):
        # 敌在正东 100 格 → 锚点 = 基地正东 forward 格
        self.assertEqual(
            base_defense_anchor(False, (10, 10), (110, 10), forward=6.0), (16.0, 10.0)
        )

    def test_expansion_anchor_diagonal(self):
        # 敌在东北对角 → 锚点在 (1,1) 方向 forward 格
        x, y = base_defense_anchor(False, (0, 0), (100, 100), forward=6.0)
        self.assertAlmostEqual(x, 6.0 / 2**0.5, places=5)
        self.assertAlmostEqual(y, 6.0 / 2**0.5, places=5)

    def test_enemy_on_top_of_base_returns_none(self):
        self.assertIsNone(base_defense_anchor(False, (10, 10), (10, 10)))


class TestDefenseAnchorIndex(unittest.TestCase):
    """O37(司令观察):主基塔够 → 防守兵蹲塔最少的分矿,不扎堆主基。"""

    def test_single_base_always_main(self):
        self.assertEqual(defense_anchor_index([3]), 0)
        self.assertEqual(defense_anchor_index([0]), 0)

    def test_main_well_defended_picks_weakest_expansion(self):
        self.assertEqual(defense_anchor_index([2, 0]), 1)   # 二矿裸奔 → 蹲二矿
        self.assertEqual(defense_anchor_index([3, 1, 0]), 2)  # 三矿最裸 → 蹲三矿
        self.assertEqual(defense_anchor_index([2, 0, 1]), 1)  # 二矿最裸 → 蹲二矿

    def test_main_under_defended_stays_main(self):
        self.assertEqual(defense_anchor_index([1, 0]), 0)  # 主基塔不够,先保本
        self.assertEqual(defense_anchor_index([0, 0, 0]), 0)

    def test_tie_picks_earlier_expansion(self):
        self.assertEqual(defense_anchor_index([2, 1, 1]), 1)  # 并列取近的分矿

    def test_empty_is_main(self):
        self.assertEqual(defense_anchor_index([]), 0)


class TestHotBaseIndex(unittest.TestCase):
    """O63:中局动态防守锚点 —— 敌计数 ≥6 的最高压基地,无热点回 None。"""

    def test_no_threat_returns_none(self):
        self.assertIsNone(hot_base_index([0, 0, 0]))
        self.assertIsNone(hot_base_index([]))

    def test_below_threshold_returns_none(self):
        self.assertIsNone(hot_base_index([0, 5, 2]))  # 5 < 6 挠痒级,不拉舰队

    def test_hot_base_picked(self):
        self.assertEqual(hot_base_index([0, 10, 3]), 1)   # 二矿被围攻 → 回防二矿
        self.assertEqual(hot_base_index([18, 0, 6]), 0)   # 主基最高压 → 回防主基

    def test_tie_picks_earlier_base(self):
        self.assertEqual(hot_base_index([0, 8, 8]), 1)  # 并列取近(> 不取 =)

    def test_threshold_boundary(self):
        self.assertEqual(hot_base_index([0, 6]), 1)  # 恰好 6 算热点


class TestRushHoldBatteries(unittest.TestCase):
    """O73:接触式 rush 电池让位;O71 持有期(t=330+,cyber 已就)双电池。"""

    def test_contact_rush_no_batteries(self):
        self.assertEqual(rush_hold_batteries(True, False), 0)  # E3d 原行为

    def test_rush_hold_gets_batteries(self):
        self.assertEqual(rush_hold_batteries(True, True), 2)   # O71 持有期

    def test_no_rush_normal(self):
        self.assertEqual(rush_hold_batteries(False, False), 2)
        self.assertEqual(rush_hold_batteries(False, True), 2)


class TestRescoutVerdict(unittest.TestCase):
    """O71(二次侦查):单基地暴兵/爆狗判 rush,开矿判 greedy,科技开局不动。"""

    def test_expo_is_greedy(self):
        self.assertEqual(rescout_verdict(True, 3, 12), "greedy")  # 开矿一切免谈
        self.assertEqual(rescout_verdict(True, 0, 0), "greedy")

    def test_single_base_production_allin_is_rush(self):
        self.assertEqual(rescout_verdict(False, 4, 0), "rush")  # o71 实证:4BB 0 兵
        self.assertEqual(rescout_verdict(False, 3, 2), "rush")  # 3BB 兵未入镜

    def test_single_base_military_swarm_is_rush(self):
        self.assertEqual(rescout_verdict(False, 3, 8), "rush")   # Terran 3BB+8 枪兵
        self.assertEqual(rescout_verdict(False, 2, 6), "rush")   # Protoss 2BG+6 叉

    def test_single_base_big_army_is_rush(self):
        self.assertEqual(rescout_verdict(False, 1, 12), "rush")  # Zerg 单 pool 爆狗

    def test_tech_opening_is_unknown(self):
        self.assertEqual(rescout_verdict(False, 1, 3), "unknown")  # 单兵营慢打
        self.assertEqual(rescout_verdict(False, 0, 0), "unknown")  # 没探到东西
        self.assertEqual(rescout_verdict(False, 2, 5), "unknown")  # 兵营 2 但兵少


class TestFullPopAllIn(unittest.TestCase):
    """O70(司令观察):接近满人口+存款充足 → 全力进攻。"""

    def test_full_pop_with_bank_triggers(self):
        self.assertTrue(full_pop_all_in(199, 200, 5000))
        self.assertTrue(full_pop_all_in(190, 200, 1500))  # 恰好双阈值

    def test_below_pop_frac_no_trigger(self):
        self.assertFalse(full_pop_all_in(180, 200, 5000))  # 180 < 190

    def test_below_bank_no_trigger(self):
        self.assertFalse(full_pop_all_in(199, 200, 1200))  # 存款不够换血

    def test_zero_cap_safe(self):
        self.assertFalse(full_pop_all_in(199, 0, 5000))


class TestTechYieldsToThreat(unittest.TestCase):
    """O67:E9 威胁期追加产能/舰队航标让位塔链;rush 期不重复(走 rush 分支)。"""

    def test_threat_active_yields(self):
        self.assertTrue(tech_yields_to_threat(True, False))

    def test_no_threat_no_yield(self):
        self.assertFalse(tech_yields_to_threat(False, False))

    def test_rush_not_double_counted(self):
        self.assertFalse(tech_yields_to_threat(True, True))  # rush 期走 rush 全停
        self.assertFalse(tech_yields_to_threat(False, True))


class TestFleetGasStarved(unittest.TestCase):
    """O83:舰队饥饿豁免 —— 气银行≥600 + 无 FB + 有就绪星门时 FB 豁免冻结。"""

    def test_starved(self):
        self.assertTrue(fleet_gas_starved(2500, False, 3, True))
        self.assertTrue(fleet_gas_starved(600, False, 1, True))

    def test_low_gas_no_rescue(self):
        self.assertFalse(fleet_gas_starved(599, False, 3, True))

    def test_fb_present_no_rescue(self):
        self.assertFalse(fleet_gas_starved(2500, True, 3, True))

    def test_no_ready_stargate_no_rescue(self):
        self.assertFalse(fleet_gas_starved(2500, False, 0, True))

    def test_fb_not_in_core_no_rescue(self):
        self.assertFalse(fleet_gas_starved(2500, False, 3, False))


class TestRushSpawnFleetEscape(unittest.TestCase):
    """O89/O99:rush 纯叉配方逃生门 —— 基建齐+气≥400 时混编(O99 从 800 降到 400),急性早期不开。"""

    def test_escape_opens(self):
        self.assertTrue(rush_spawn_fleet_escape(2344, 4, True))
        self.assertTrue(rush_spawn_fleet_escape(800, 1, True))
        self.assertTrue(rush_spawn_fleet_escape(400, 1, True))

    def test_low_gas_closed(self):
        self.assertFalse(rush_spawn_fleet_escape(399, 4, True))

    def test_no_stargate_closed(self):
        self.assertFalse(rush_spawn_fleet_escape(2344, 0, True))

    def test_no_fb_closed(self):
        self.assertFalse(rush_spawn_fleet_escape(2344, 4, False))


class TestResourceContested(unittest.TestCase):
    """O39:资源点盘踞判据(与 E6 回采滞回线 <2 同源)。"""

    def test_threshold(self):
        self.assertFalse(resource_contested(0))
        self.assertFalse(resource_contested(1))
        self.assertTrue(resource_contested(2))
        self.assertTrue(resource_contested(9))

    def test_min_threats_param(self):
        self.assertFalse(resource_contested(3, min_threats=4))
        self.assertTrue(resource_contested(4, min_threats=4))


class TestShouldPushAdvantage(unittest.TestCase):
    """O44:carrier 默认推进要决定性优势(治推-撤 yo-yo 磨舰队)。"""

    def test_enemy_drained_pushes(self):
        self.assertTrue(should_push_advantage(50, 0))   # 敌被榨干 → 收割

    def test_decisive_advantage_pushes(self):
        self.assertTrue(should_push_advantage(100, 85))   # 100 ≥ 85+15
        self.assertTrue(should_push_advantage(60, 40))

    def test_even_or_behind_holds(self):
        self.assertFalse(should_push_advantage(53, 85))   # o43 实测场景
        self.assertFalse(should_push_advantage(50, 40))   # 50 < 40+15
        self.assertFalse(should_push_advantage(0, 1))

    def test_margin_param(self):
        self.assertTrue(should_push_advantage(55, 40, margin=10))
        self.assertFalse(should_push_advantage(55, 40, margin=20))


class TestCarrierPushSafe(unittest.TestCase):
    """O45:航母推进的硬对空安全线(14 航母撞腐化+飞蛇 = 团灭)。"""

    def test_safe_below_line(self):
        self.assertTrue(carrier_push_safe(14, 20))   # 20 < 14×1.5=21
        self.assertTrue(carrier_push_safe(4, 5))

    def test_unsafe_at_or_above_line(self):
        self.assertFalse(carrier_push_safe(14, 21))  # 撞线即不推
        self.assertFalse(carrier_push_safe(2, 10))

    def test_no_carriers_never_safe(self):
        self.assertFalse(carrier_push_safe(0, 0))    # 0 < 0 为假,无舰队不推

    def test_per_carrier_param(self):
        self.assertTrue(carrier_push_safe(10, 19, per_carrier=2.0))
        self.assertFalse(carrier_push_safe(10, 20, per_carrier=2.0))


class TestO92Transition(unittest.TestCase):
    """O92 过渡形态判据(快攻四墙 build order 级修复)。"""

    def test_enter_on_rush_verdict(self):
        self.assertTrue(transition_should_enter("rush", False))

    def test_enter_on_rush_confirmed(self):
        self.assertTrue(transition_should_enter(None, True))
        # O154-①:greedy 一票否决接触进过渡(小股骚扰 E9 威胁包管,
        # 冻舰队链 = 自残,o153 局1 实锤)—— O92 的「接触证实优先于
        # 首判」语义被 O154 推翻(限 greedy;unknown 接触仍进)
        self.assertFalse(transition_should_enter("greedy", True))
        self.assertTrue(transition_should_enter("unknown", True))

    def test_no_enter_greedy_or_unknown_without_contact(self):
        # 规格约束:verdict=greedy/unknown 且从未接触 → 现状完全不变
        self.assertFalse(transition_should_enter("greedy", False))
        self.assertFalse(transition_should_enter("unknown", False))
        self.assertFalse(transition_should_enter(None, False))

    def test_o150_one_way_and_contact_limit(self):
        # O150-①:转过舰队后永不重进(任何 verdict/接触)
        self.assertFalse(transition_should_enter("rush", True, fleet_transitioned=True))
        self.assertFalse(transition_should_enter(
            None, True, fleet_transitioned=True, rush_confirmed_at=100.0))
        # O150-②:接触确认只认早期 —— ≤360 进,>360 的接触是推进波不是 rush
        self.assertTrue(transition_should_enter(None, True, rush_confirmed_at=300.0))
        self.assertFalse(transition_should_enter(None, True, rush_confirmed_at=400.0))
        # verdict=rush 的情报确认不受时点限;缺省(None)保持旧行为
        self.assertTrue(transition_should_enter("rush", False, rush_confirmed_at=999.0))
        self.assertTrue(transition_should_enter(None, True))

    def test_cancel_presumed_forge(self):
        # O150-③:greedy 且 t≤110 → 取消在建 forge 退保;晚到/非 greedy 不动
        self.assertTrue(cancel_presumed_forge("greedy", 100.0))
        self.assertFalse(cancel_presumed_forge("greedy", 120.0))
        self.assertFalse(cancel_presumed_forge("rush", 80.0))
        self.assertFalse(cancel_presumed_forge(None, 80.0))

    def test_o154_greedy_veto(self):
        # O154-①:greedy 后接触永不进过渡(含 360 时限内);
        # rescout/新情报改判 rush → 照进(verdict 路径不受否决)
        self.assertFalse(transition_should_enter(
            "greedy", True, rush_confirmed_at=237.0))
        self.assertTrue(transition_should_enter(
            "rush", True, rush_confirmed_at=237.0))

    def test_rush_contact_arms(self):
        # O154-②:greedy 判决后接触不置 rush latch;其余判决照常
        self.assertFalse(rush_contact_arms("greedy"))
        self.assertTrue(rush_contact_arms("rush"))
        self.assertTrue(rush_contact_arms("unknown"))
        self.assertTrue(rush_contact_arms(None))

    def test_tech_frozen_only_stargate_fleetbeacon(self):
        self.assertTrue(transition_tech_frozen(True, "STARGATE"))
        self.assertTrue(transition_tech_frozen(True, "FLEETBEACON"))
        # CYBERNETICSCORE 保留(追猎要它);兵营本就不冻
        self.assertFalse(transition_tech_frozen(True, "CYBERNETICSCORE"))
        self.assertFalse(transition_tech_frozen(True, "GATEWAY"))

    def test_tech_frozen_inactive_freezes_nothing(self):
        self.assertFalse(transition_tech_frozen(False, "STARGATE"))
        self.assertFalse(transition_tech_frozen(False, "FLEETBEACON"))

    def test_fleet_ready_requires_time_and_clear(self):
        # 到点 + 家 40 格无敌持续 30s → 转舰队
        self.assertTrue(fleet_transition_ready(730.0, 700.0, 0, 700.0))
        # 没到点 → 不转
        self.assertFalse(fleet_transition_ready(699.0, 700.0, 0, 600.0))
        # 到点但威胁刚清(计时未起) → 不转
        self.assertFalse(fleet_transition_ready(730.0, 700.0, 0, None))
        # 到点但清除未满 30s → 不转
        self.assertFalse(fleet_transition_ready(725.0, 700.0, 0, 700.0))
        # 到点但家附近还有敌(调用方应已清零 clear_since,这里兜底) → 不转
        self.assertFalse(fleet_transition_ready(760.0, 700.0, 2, 700.0))

    def test_fleet_ready_waits_out_threat(self):
        # fleet_at 到了但威胁未清 → 保持过渡,直到清满 30s 才转
        self.assertFalse(fleet_transition_ready(900.0, 700.0, 5, None))
        self.assertTrue(fleet_transition_ready(931.0, 700.0, 0, 901.0))


class TestO93FleetDeadlock(unittest.TestCase):
    """O93 转舰队死锁三修复(o92-vh-zerg-rush 局2/局3 实证)。"""

    def test_core_tech_allowed_baseline(self):
        # 未转舰队:O43/O51 原语义 —— 持有期冻结科技链
        self.assertFalse(core_tech_allowed(True, False))
        self.assertTrue(core_tech_allowed(False, False))

    def test_core_tech_allowed_after_transition(self):
        # O93-B1(局3):转舰队后持有期不再冻结科技链(否则持有永不解除=死锁)
        self.assertTrue(core_tech_allowed(True, True))
        self.assertTrue(core_tech_allowed(False, True))

    def test_fleet_expand_holds_baseline(self):
        # 未转舰队:扩张不受本判据影响(O57 门照旧,不进这里)
        self.assertFalse(fleet_expand_holds(False, False))
        self.assertFalse(fleet_expand_holds(False, True))

    def test_fleet_expand_holds_until_first_fleet(self):
        # O93-B2/O96(o95 局3/局4):转舰队后等首舰(已出/在产)才开矿 ——
        # 等「FB 实体」不够:FB 落地后二矿+先知仍会把首舰的钱吃光
        self.assertTrue(fleet_expand_holds(True, False))
        self.assertFalse(fleet_expand_holds(True, True))

    def test_fb_stall_recovery(self):
        # 科技链有 FB + 有就绪星门 + 无 FB 实体 + 买得起停滞 >45s → 自救
        self.assertTrue(fb_stall_recovery_needed(True, 1, False, 46.0))
        self.assertFalse(fb_stall_recovery_needed(True, 1, False, 44.0))
        # FB 实体已在(含在建) → 不停滞
        self.assertFalse(fb_stall_recovery_needed(True, 1, True, 100.0))
        # 无就绪星门 / FB 不在科技链 → 不归本自救管
        self.assertFalse(fb_stall_recovery_needed(True, 0, False, 100.0))
        self.assertFalse(fb_stall_recovery_needed(False, 1, False, 100.0))

    def test_fb_stall_timeout_param(self):
        self.assertTrue(fb_stall_recovery_needed(True, 1, False, 21.0, timeout=20.0))


class TestO94FirstWaveDefense(unittest.TestCase):
    """O94 首波速败级联修复(o92/o93-vh-zerg-rush 四局实证)。"""

    def test_defense_past_holding(self):
        # rush 确认 + transition 流派 → F2 无视持有期(修 t≈190-200 黑窗)
        self.assertTrue(rush_defense_past_holding(True, True))
        # 未确认 rush / 无 transition 流派(tempest/stalker/dt) → 原语义
        self.assertFalse(rush_defense_past_holding(False, True))
        self.assertFalse(rush_defense_past_holding(True, False))
        self.assertFalse(rush_defense_past_holding(False, False))

    def test_defers_second_gateway(self):
        # rush 确认 + forge 无实体 → 缓建追加兵营(150 矿先给炮塔链)
        self.assertTrue(rush_defers_second_gateway(True, True, False))
        # forge 实体落地(含在建) → 追加恢复
        self.assertFalse(rush_defers_second_gateway(True, True, True))
        # 未确认 rush / 非 transition 流派 → 原 E3d 行为
        self.assertFalse(rush_defers_second_gateway(False, True, False))
        self.assertFalse(rush_defers_second_gateway(True, False, False))

    def test_cannon_bypass(self):
        # rush 确认且主基无就绪炮塔 → 通用槽绕过实例
        self.assertTrue(rush_cannon_bypass(True, True, 0))
        # 首座就绪 → 退出绕过,回归 PSD 槽池
        self.assertFalse(rush_cannon_bypass(True, True, 1))
        self.assertFalse(rush_cannon_bypass(False, True, 0))
        self.assertFalse(rush_cannon_bypass(True, False, 0))

    def test_worker_escort(self):
        # 敌地面进主基 + 塔/叉都不够 → 协防
        self.assertTrue(rush_worker_escort_needed(3, 0, 0))
        self.assertTrue(rush_worker_escort_needed(12, 0, 1))
        # O104-①:1 塔不放人(转塔下作战);O123-③:叉接管线 2→4(叉海接管,
        # 农民不再参战)—— 2 塔或 4 叉才归队
        self.assertTrue(rush_worker_escort_needed(12, 1, 0))
        self.assertTrue(rush_worker_escort_needed(12, 0, 2))
        self.assertFalse(rush_worker_escort_needed(12, 2, 0))
        self.assertFalse(rush_worker_escort_needed(12, 0, 4))
        self.assertFalse(rush_worker_escort_needed(2, 0, 0))

    def test_worker_escort_params(self):
        self.assertTrue(rush_worker_escort_needed(5, 0, 0, min_enemy=5))
        self.assertFalse(rush_worker_escort_needed(4, 0, 0, min_enemy=5))
        # O299-②:ZT 首波窗 min_enemy=2 —— 1-2 狗进矿线即协防
        self.assertTrue(rush_worker_escort_needed(2, 0, 0, min_enemy=2))
        self.assertFalse(rush_worker_escort_needed(1, 0, 0, min_enemy=2))

    def test_worker_escort_hopeless(self):
        # O309-②(o308a game_03/04 实证):白送上界 —— 敌地面超 14+6×塔
        # 不拉(×6 添油四轮、骤减 4-11/波的纯放血),留矿保命
        self.assertFalse(rush_worker_escort_needed(27, 0, 0, hopeless=True))
        # 未超线照拉(顶 10-20s 空窗的本职不变)
        self.assertTrue(rush_worker_escort_needed(12, 0, 0, hopeless=False))
        # 缺省 hopeless=False → 旧行为不变
        self.assertTrue(rush_worker_escort_needed(27, 0, 0))

    def test_zt_prewave_trickle(self):
        # O292(D1):GW 就绪 + 地面 <cap + 舰队基建未活 → 预备产兵
        self.assertTrue(zt_prewave_trickle_needed(False, True, 0))
        self.assertTrue(zt_prewave_trickle_needed(False, True, 5))
        # 够数自校正回舰队配方
        self.assertFalse(zt_prewave_trickle_needed(False, True, 6))
        # GW 未就绪不开闸(开局 BO 不抢钱)
        self.assertFalse(zt_prewave_trickle_needed(False, False, 0))
        # 舰队基建活(SG 就绪+FB 在场/在建)→ 舰队上量优先,关闸
        self.assertFalse(zt_prewave_trickle_needed(True, True, 0))
        # 自定义 cap
        self.assertTrue(zt_prewave_trickle_needed(False, True, 3, cap=4))
        self.assertFalse(zt_prewave_trickle_needed(False, True, 4, cap=4))
        # O293-①:口袋激活期 cap 6→3(让钱给 Nexus 资金窗)
        self.assertTrue(zt_prewave_trickle_needed(False, True, 2, cap=3))
        self.assertFalse(zt_prewave_trickle_needed(False, True, 3, cap=3))

    def test_pocket_saving_cannons(self):
        # O293-②:激活期塔目标收到 ≤3(首波存活地板),不再归 0
        self.assertEqual(pocket_saving_cannons(0), 0)
        self.assertEqual(pocket_saving_cannons(2), 2)
        self.assertEqual(pocket_saving_cannons(3), 3)
        # O290 本意保留:3→10 塔链仍被拦
        self.assertEqual(pocket_saving_cannons(10), 3)
        # 自定义 cap
        self.assertEqual(pocket_saving_cannons(5, cap=4), 4)

    def test_forge_rebuild_probe_yield(self):
        # O294-①:无就绪 forge + 急性 + 矿不够 → 探机让位
        self.assertTrue(forge_rebuild_probe_yield(False, True, 100.0))
        # 矿够 forge → 照产(自校正)
        self.assertFalse(forge_rebuild_probe_yield(False, True, 150.0))
        # forge 就绪 → 照产
        self.assertFalse(forge_rebuild_probe_yield(True, True, 0.0))
        # 非急性期 → 照产
        self.assertFalse(forge_rebuild_probe_yield(False, False, 100.0))
        # 自定义 forge 价
        self.assertTrue(forge_rebuild_probe_yield(False, True, 100.0, forge_price=120.0))

    def test_carrier_reserve_ok(self):
        # O294-②:有就绪 SG + 非急性 → 预留成立
        self.assertTrue(carrier_reserve_ok(True, False))
        # SG 毁了 → 攒航母产不出,不预留
        self.assertFalse(carrier_reserve_ok(False, False))
        # 急性威胁期 → 停产=自杀,不预留
        self.assertFalse(carrier_reserve_ok(True, True))
        # O295-②:敌可见 supply > 我方 → 产线永不停(threat 滞后兜底)
        self.assertFalse(carrier_reserve_ok(True, False, enemy_supply=76.0, own_supply=48.0))
        self.assertTrue(carrier_reserve_ok(True, False, enemy_supply=30.0, own_supply=48.0))
        # O296-①:严格闸 —— 敌我相等(含地面0+敌不可见的 0v0)不停产
        self.assertFalse(carrier_reserve_ok(True, False, enemy_supply=48.0, own_supply=48.0))
        self.assertFalse(carrier_reserve_ok(True, False, enemy_supply=0.0, own_supply=0.0))
        self.assertTrue(carrier_reserve_ok(True, False, enemy_supply=0.0, own_supply=5.0))
        # 默认参数(无敌情)维持 O294-② 语义
        self.assertTrue(carrier_reserve_ok(True, False))

    def test_fleet_infra_rebuild_active(self):
        # O294-③:舰队曾成型 + t≥300 → 重建链开闸
        self.assertTrue(fleet_infra_rebuild_active(True, 642.9))
        self.assertTrue(fleet_infra_rebuild_active(True, 300.0))
        # 开局未成型 → 不误触发
        self.assertFalse(fleet_infra_rebuild_active(False, 500.0))
        # 太早 → 不开闸
        self.assertFalse(fleet_infra_rebuild_active(True, 299.9))

    def test_zt_golden_window_push(self):
        # O302:t≥650 + 舰队 ≥3 + 追猎 ≥8 → 黄金窗推进(O303-② 参数)
        # O325-①:追猎阈 8→6(o324b game_04:暴风6+追6@800s=胜局编成被挡)
        self.assertTrue(zt_golden_window_push(650.0, 3, 6))
        self.assertTrue(zt_golden_window_push(650.0, 3, 8))
        self.assertTrue(zt_golden_window_push(750.0, 3, 12))   # o302b-g01 场景
        # 窗口前不推
        self.assertFalse(zt_golden_window_push(649.9, 6, 20))
        # 舰队/追猎不足不推(腐化在时 t<750 追猎阈仍为 6;O356-③ 起
        # 腐化 0 真窗追猎门降 0,追猎闸用例须显式带腐化)
        self.assertFalse(zt_golden_window_push(749.9, 2, 20))
        self.assertFalse(zt_golden_window_push(700.0, 3, 5, corruptors=2))
        # 自定义阈值(带腐化,追猎阈不被 O356-③ 零腐化软化归零)
        self.assertTrue(zt_golden_window_push(600.0, 3, 8, min_t=600.0, min_fleet=3, min_stalkers=8, corruptors=1))
        self.assertFalse(zt_golden_window_push(600.0, 3, 7, min_t=600.0, min_fleet=3, min_stalkers=8, corruptors=1))
        # O354-③(o353 五局尸检):腐化上限 2→4 —— 腐化 3-4 放行(舰队
        # 6-7 艘+敌腐化 0-4 正是被永久 near-miss 饿死的最佳窗口)
        self.assertTrue(zt_golden_window_push(700.0, 6, 12, corruptors=3))
        self.assertTrue(zt_golden_window_push(700.0, 6, 12, corruptors=4))
        self.assertFalse(zt_golden_window_push(700.0, 6, 12, corruptors=5))
        self.assertTrue(zt_golden_window_push(700.0, 6, 12, corruptors=2))
        self.assertTrue(zt_golden_window_push(700.0, 6, 12, corruptors=0))
        # O354-③:时间衰减 —— t≥750 追猎阈 6→4;t=800 追猎 4 放行,
        # t=700 追猎 4 仍卡(腐化在时;O356-③ 起腐化 0 门降 0)
        self.assertTrue(zt_golden_window_push(800.0, 3, 4, corruptors=1))
        self.assertTrue(zt_golden_window_push(750.0, 3, 4, corruptors=1))
        self.assertFalse(zt_golden_window_push(749.9, 3, 4, corruptors=1))
        self.assertFalse(zt_golden_window_push(700.0, 3, 4, corruptors=1))
        # O356-③(o355a g2 实证):零腐化真窗追猎闸软化 —— 140s 零腐化
        # 真窗因追猎 5<6/2<4 被否 9 次 near-miss;暴风零腐化时射程
        # 白嫖纯地面,不需要追猎护航(腐化 0+舰队 3+追猎 0 → 推)
        self.assertTrue(zt_golden_window_push(679.0, 3, 0, corruptors=0))
        self.assertTrue(zt_golden_window_push(700.0, 3, 5, corruptors=0))
        self.assertTrue(zt_golden_window_push(700.0, 3, 2, corruptors=0))
        # 腐化 3+追猎 5(t<750)→ 仍不推(现有阈不动)
        self.assertFalse(zt_golden_window_push(700.0, 3, 5, corruptors=3))
        # 零腐化但舰队/时间不足 → 不推(舰队门/时间门不动)
        self.assertFalse(zt_golden_window_push(700.0, 2, 20, corruptors=0))
        self.assertFalse(zt_golden_window_push(649.9, 3, 0, corruptors=0))
        # O326-③:尖塔可见 = 腐化 30-60s 内必到,整局否决(o325a game_04:
        # 推时腐化 ≤2 过闸,28s 后 4-6,暴风喂转型)
        self.assertFalse(zt_golden_window_push(750.0, 6, 12, corruptors=0, spire_seen=True))
        self.assertTrue(zt_golden_window_push(750.0, 6, 12, corruptors=0, spire_seen=False))

    def test_pivot_stalker_cap(self):
        # O303-③:腐化 0-8 → cap 12(防追猎洪水)
        self.assertEqual(pivot_stalker_cap(0), 12)
        self.assertEqual(pivot_stalker_cap(8), 12)
        # 腐化 ≥9 → 1.5× 放量(腐化海时追猎是唯一能还手的)
        self.assertEqual(pivot_stalker_cap(9), 14)
        self.assertEqual(pivot_stalker_cap(19), 28)   # o302b-g04 腐化海场景
        # 自定义 base
        self.assertEqual(pivot_stalker_cap(0, base=8), 8)
        self.assertEqual(pivot_stalker_cap(20, base=8), 30)


class TestO96EscortAndTransitionExpand(unittest.TestCase):
    """O96 首波协防修正(o95 局2/局5)+ 过渡期开矿纪律(o95 局1)。"""

    def test_escort_count_scales_with_threat(self):
        # 挠痒级(3-5 敌) → 下限 5;敌 ≥6 → 敌数+2;cap 10 封顶
        self.assertEqual(escort_worker_count(3), 5)
        self.assertEqual(escort_worker_count(5), 7)
        self.assertEqual(escort_worker_count(8), 10)
        self.assertEqual(escort_worker_count(20), 10)

    def test_transition_expand_blocked_until_gateway_cap(self):
        # 过渡期兵营未满 cap → 不开矿(局1:二矿抢钱,单兵营 7 叉迎 30-supply 波)
        self.assertTrue(transition_expand_blocked(True, 1, 3))
        self.assertTrue(transition_expand_blocked(True, 2, 3))
        self.assertFalse(transition_expand_blocked(True, 3, 3))
        # 非过渡期 → 不拦(原行为)
        self.assertFalse(transition_expand_blocked(False, 1, 3))


class TestO97RushCascade(unittest.TestCase):
    """O97(o96-vh-zerg-rush 0-5 尸检):早侦查评估/首舰后扩张重启/过渡产能。"""

    def test_early_verdict_rush_single_base_with_pool(self):
        # 敌单基地 + 出兵建筑(pool/兵营/gateway ≥1) → rush(局2 场景:t=144
        # 看到 SPAWNINGPOOL 无二矿)
        self.assertEqual(early_scout_verdict(True, 1, 0, 1), "rush")
        self.assertEqual(early_scout_verdict(True, 2, 0, 1), "rush")
        self.assertEqual(early_scout_verdict(True, 0, 6, 1), "rush")  # 兵≥6 同老判据

    def test_early_verdict_greedy_needs_expo(self):
        # 已开二矿 → greedy(证据标准不降:看到二矿才算贪)
        self.assertEqual(early_scout_verdict(True, 1, 0, 2), "greedy")
        self.assertEqual(early_scout_verdict(True, 0, 0, 2), "greedy")

    def test_early_verdict_fallbacks(self):
        # 无情报 → unknown;单基地无兵营无兵 → 回落 scout_verdict(greedy)
        self.assertEqual(early_scout_verdict(False, 0, 0, 1), "unknown")
        self.assertEqual(early_scout_verdict(True, 0, 0, 1), "greedy")

    def test_fleet_expansion_reserve(self):
        base = dict(
            fleet_transitioned=True, first_fleet_seen=True, bases=1,
            want_expand=True, can_afford_nexus=False,
            threat_active=False, rush_active=False,
        )
        self.assertTrue(fleet_expansion_reserve(**base))  # 局5 场景:单矿攒钱开二矿
        self.assertFalse(fleet_expansion_reserve(
            **{**base, "fleet_transitioned": False}))      # 未转舰队 → O56 原语义
        self.assertFalse(fleet_expansion_reserve(
            **{**base, "first_fleet_seen": False}))        # 首舰未出 → 舰队优先
        # O145-②:首舰未出但评分 ≥25(防御站稳)→ 允许为首舰前二矿攒钱
        # (o144 局3:死等首舰 = SG/FB 把 Nexus 的 400 吃光,bases=1 到死)
        self.assertTrue(fleet_expansion_reserve(
            **{**base, "first_fleet_seen": False, "defense_score": 27.0}))
        self.assertFalse(fleet_expansion_reserve(
            **{**base, "first_fleet_seen": False, "defense_score": 20.0}))
        self.assertFalse(fleet_expansion_reserve(
            **{**base, "can_afford_nexus": True}))         # 买得起即解除
        self.assertFalse(fleet_expansion_reserve(
            **{**base, "threat_active": True}))            # 威胁期不停产
        self.assertFalse(fleet_expansion_reserve(
            **{**base, "rush_active": True}))              # rush 期不停产
        self.assertFalse(fleet_expansion_reserve(
            **{**base, "bases": 2}))                       # 双矿不需要预留

    def test_transition_probe_yield(self):
        # 过渡期农民够保底且地面未到目标 → 让位(局1:农民29/叉7;局3:116s零叉)
        self.assertTrue(transition_probe_yield(True, 14, 7))
        self.assertFalse(transition_probe_yield(True, 13, 7))   # 农民不够 → 照造
        self.assertFalse(transition_probe_yield(True, 20, 12))  # 地面达标 → 照造
        self.assertFalse(transition_probe_yield(False, 20, 7))  # 非过渡期 → 原行为


class TestO98ScoutAndSecondWave(unittest.TestCase):
    """O98(o97-vh-zerg-rush 0-5 尸检):探机早补派/断链兜底/二波强度。"""

    def test_early_redispatch(self):
        # 探机失联 + 无情报 + 未补派 + t≥95(O106-③:105→95) → 立即补派
        self.assertTrue(scout_early_redispatch_needed(True, False, True, False, 110))
        self.assertFalse(scout_early_redispatch_needed(True, False, True, False, 90))
        self.assertFalse(scout_early_redispatch_needed(True, True, True, False, 110))
        self.assertFalse(scout_early_redispatch_needed(True, False, False, False, 110))
        self.assertFalse(scout_early_redispatch_needed(True, False, True, True, 110))
        # 非 transition 流派 → 老路径
        self.assertFalse(scout_early_redispatch_needed(False, False, True, False, 110))

    def test_presumed_rush_defense(self):
        # vs Zerg + transition + 无 verdict 无接触 → 节制版防御链;
        # O113-③:at 78→65(首塔 ~150-165 vs 波次 ~150-165,再提前掰硬币)
        self.assertTrue(presumed_rush_defense(True, True, False, False, 125))
        self.assertTrue(presumed_rush_defense(True, True, False, False, 68))
        self.assertTrue(presumed_rush_defense(True, True, False, False, 60))  # O141:at→55
        self.assertFalse(presumed_rush_defense(True, True, False, False, 54))
        # verdict 落地(含 greedy)/接触确认 → 翻假交还
        self.assertFalse(presumed_rush_defense(True, True, True, False, 125))
        self.assertFalse(presumed_rush_defense(True, True, False, True, 125))
        # 非 Zerg / 非 transition → 不启动
        self.assertFalse(presumed_rush_defense(False, True, False, False, 125))
        self.assertFalse(presumed_rush_defense(True, False, False, False, 125))

    def test_transition_needs_gateways(self):
        # 过渡期兵营直补到 cap,不看敌兵对比(局2:首波后敌可见=0,GW2 拖到 301)
        self.assertTrue(transition_needs_gateways(True, 1, 3))
        self.assertTrue(transition_needs_gateways(True, 2, 3))
        self.assertFalse(transition_needs_gateways(True, 3, 3))
        self.assertFalse(transition_needs_gateways(False, 1, 3))

    def test_transition_needs_cybercore(self):
        # 过渡期 cyber 豁免 rush 全停(追猎=气出口+对重甲 DPS);有了就不补
        self.assertTrue(transition_needs_cybercore(True, False))
        self.assertFalse(transition_needs_cybercore(True, True))
        self.assertFalse(transition_needs_cybercore(False, False))


class TestO99TowerFundingOrder(unittest.TestCase):
    """O99(o98 0-5 尸检):塔链资金顺序修复 + 探机失联三态。"""

    def test_gateway_after_cannons(self):
        # O102-①:GW1 不受塔闸(与 forge 并行双开);GW2/GW3 等首 2 塔
        self.assertTrue(transition_gateway_allowed(0, 0))
        self.assertTrue(transition_gateway_allowed(0, 1))
        self.assertFalse(transition_gateway_allowed(1, 0))
        self.assertFalse(transition_gateway_allowed(2, 1))
        self.assertTrue(transition_gateway_allowed(1, 2))
        self.assertTrue(transition_gateway_allowed(2, 5))

    def test_early_redispatch_scout_lost_semantics(self):
        # O98 判据签名不变(scout_dead→scout_lost),三态失联由调用方计算;
        # 这里锁判据本身的行为:失联+无情报+未补派+到点 → 补派
        self.assertTrue(scout_early_redispatch_needed(True, False, True, False, 110))
        self.assertFalse(scout_early_redispatch_needed(True, False, False, False, 110))
        self.assertFalse(scout_early_redispatch_needed(True, False, True, True, 110))


class TestO100TransitionSurvival(unittest.TestCase):
    """O100(o99-vh-zerg-rush 0-5 尸检):站稳开矿/退出门放宽/zerg误判/失联即presumed。"""

    def test_transition_expand_ready(self):
        # 站稳三重门(O102 降阈后默认 塔≥2+地面≥5+清净≥12s);
        # 边界用显式参数锁逻辑,默认值由 O103 测试锁
        self.assertTrue(transition_expand_ready(True, 2, 8, 15.0))
        self.assertFalse(transition_expand_ready(True, 1, 8, 15.0))
        self.assertFalse(transition_expand_ready(True, 2, 7, 15.0, min_ground=8))
        self.assertFalse(transition_expand_ready(True, 2, 8, 14.0, clear_needed=15.0))
        self.assertFalse(transition_expand_ready(False, 3, 10, 60.0))

    def test_fleet_transition_strong_exit(self):
        # 局1 站稳期实测 ≈8-10叉+4-5塔 ≈ 28-35 分;波间隙敌可见 ≤14 → 放行
        # O110-②:加清净深度门(clear_for ≥30)—— 波前 40s 的退出不再放行
        self.assertTrue(fleet_transition_strong_exit(30.0, 14.0, 30.0))
        self.assertTrue(fleet_transition_strong_exit(25.0, 0.0, 35.0))
        # 清净不够 → 不放行(o108 局2/局4:score 一够就放 = 波前退出撞波)
        self.assertFalse(fleet_transition_strong_exit(30.0, 14.0, 12.0))
        self.assertFalse(fleet_transition_strong_exit(30.0, 0.0, 0.0))
        # 防御不达标 → 不放行
        self.assertFalse(fleet_transition_strong_exit(24.0, 0.0, 60.0))
        # 敌波到脸(28-45 supply) → 不放行(防带波转舰队)
        self.assertFalse(fleet_transition_strong_exit(30.0, 28.0, 60.0))
        self.assertFalse(fleet_transition_strong_exit(35.0, 30.0, 60.0))

    def test_zerg_pool_never_greedy(self):
        # O100-③/O104-③:vs Zerg 早评永不给 greedy —— 有二矿也不行
        # (hatch-first+pool 是真实 rush;pool 没看到 ≠ 没 rush)
        self.assertEqual(early_scout_verdict(True, 1, 0, 2, True), "unknown")
        self.assertEqual(early_scout_verdict(True, 0, 0, 2, True), "unknown")
        # 非 zerg 有/无兵营+二矿 → greedy 照旧;旧签名(无第五参)行为不变
        self.assertEqual(early_scout_verdict(True, 1, 0, 2, False), "greedy")
        self.assertEqual(early_scout_verdict(True, 1, 0, 2), "greedy")

    def test_presumed_on_scout_lost(self):
        # O100-④:失联 + t≥95(O106-③) → 立即 presumed;
        # O111-①:未失联 t≥78 也无条件启动 —— 「未失联仍等 120」的旧语义已废
        self.assertTrue(presumed_rush_defense(True, True, False, False, 96, scout_lost=True))
        self.assertTrue(presumed_rush_defense(True, True, False, False, 68))
        # O141:at 65→55 —— 60 已启动;更早(<55)不启动
        self.assertFalse(presumed_rush_defense(True, True, False, False, 54, scout_lost=True))


class TestO101RebuildWindow(unittest.TestCase):
    """O101(o100-vh-zerg-rush 0-5 尸检):舰队重建窗(Y:星门空转/Z:地面保底)。"""

    def test_rebuild_window(self):
        # 转舰队且首舰未出 → 窗内(农民让位/兵营保持)
        self.assertTrue(fleet_rebuild_window(True, False))
        # 首舰出场 → 关窗;未转舰队 → 无窗
        self.assertFalse(fleet_rebuild_window(True, True))
        self.assertFalse(fleet_rebuild_window(False, False))
        self.assertFalse(fleet_rebuild_window(False, True))


class TestO102WaveTwo(unittest.TestCase):
    """O102(o101-vh-zerg-rush 0-5 尸检):GW1 并行/塔 4 封顶/退出门口径。"""

    def test_defer_only_second_gateway_onwards(self):
        # GW1(have=0)不被 forge 让位拦 —— 与 forge 并行双开,首叉进守窗
        self.assertFalse(rush_defers_second_gateway(True, True, False, 0))
        # GW2/GW3 仍让位 forge(旧语义)
        self.assertTrue(rush_defers_second_gateway(True, True, False, 1))
        self.assertTrue(rush_defers_second_gateway(True, True, False, 2))
        # forge 落地 → 全放开;旧三参签名行为不变
        self.assertFalse(rush_defers_second_gateway(True, True, True, 1))
        self.assertTrue(rush_defers_second_gateway(True, True, False))

    def test_transition_cannon_cap(self):
        # O132-②:cap 2→3(2 塔 timing 波稳定穿防,o131 实证);
        # 峰值 latch(O132-③)兜兵营链,第 3 塔不挤产能;非过渡期不动
        self.assertEqual(transition_cannon_cap(6, True), 3)
        self.assertEqual(transition_cannon_cap(1, True), 1)
        self.assertEqual(transition_cannon_cap(6, False), 6)


class TestO103FirstWaveProduction(unittest.TestCase):
    """O103(o102-vh-zerg-rush 0-5 尸检):守窗零叉根因修复/开矿降阈/forge 优先。"""

    def test_research_paused_during_transition(self):
        # 过渡期研究全程让位(UC prioritize 截断 = 守窗零叉根因)
        self.assertTrue(research_paused_for_rush(False, True))
        self.assertTrue(research_paused_for_rush(True, False))
        self.assertFalse(research_paused_for_rush(False, False))
        # 旧单参签名行为不变
        self.assertTrue(research_paused_for_rush(True))
        self.assertFalse(research_paused_for_rush(False))

    def test_cyber_waits_for_two_zealots(self):
        # 0-1 叉时 cyber 不抢 150 矿(局3/5:首叉 156→183 的另一根因)
        self.assertFalse(transition_needs_cybercore(True, False, 0))
        self.assertFalse(transition_needs_cybercore(True, False, 1))
        self.assertTrue(transition_needs_cybercore(True, False, 2))
        self.assertFalse(transition_needs_cybercore(True, True, 5))
        # 旧双参签名行为不变(缺省 ground_army=2)
        self.assertTrue(transition_needs_cybercore(True, False))

    def test_expand_ready_lowered_thresholds(self):
        # O103:8→5/15→12;O119-②:再降 5→4/12→8(波间隙实测 8-12s)
        self.assertTrue(transition_expand_ready(True, 2, 5, 12.0))
        self.assertFalse(transition_expand_ready(True, 2, 3, 12.0))
        self.assertFalse(transition_expand_ready(True, 2, 5, 7.0))

    def test_forge_first_pylon_yield(self):
        # forge 未落地 → 水晶让位(含人口紧急 —— O141:农民已冻在 11,
        # 卡人口什么都不堵,应急水晶是纯浪费);forge 落地/非紧急态 → 照建
        self.assertTrue(forge_first_pylon_yield(True, False, 15.0))
        self.assertTrue(forge_first_pylon_yield(True, False, 3.0))  # O141:紧急也让位
        self.assertFalse(forge_first_pylon_yield(True, True, 15.0))
        self.assertFalse(forge_first_pylon_yield(False, False, 15.0))

    def test_chrono_forge_first(self):
        # O141-②:防御紧急 + forge 在 warp + 首塔未出 → chrono forge;
        # 首塔出现(含在建)/非紧急/无 forge 在 warp → 不抢能量
        self.assertTrue(chrono_forge_first(True, True, False))
        self.assertFalse(chrono_forge_first(True, True, True))
        self.assertFalse(chrono_forge_first(True, False, False))
        self.assertFalse(chrono_forge_first(False, True, False))


class TestO104EscortStance(unittest.TestCase):
    """O104(o103 0-5 尸检):协防双姿态(塔下作战/穿矿拖延)。"""

    def test_escort_stance(self):
        # 无就绪塔 → 穿矿拖延(不接敌);有塔 → 塔下作战
        self.assertEqual(escort_stance(0), "mineral_walk")
        self.assertEqual(escort_stance(1), "tower")
        self.assertEqual(escort_stance(3), "tower")
        # O127-③:有塔在建 → 塔下守建造点(建造窗=死亡窗)
        self.assertEqual(escort_stance(0, cannon_pending=True), "tower")


class TestO105ExpansionAndRebuildWindow(unittest.TestCase):
    """O105(o104-vh-zerg-rush 0-5 尸检):扩张门接力/攒钱预留/SG双开/塔cap6。"""

    def test_transition_expand_reserve(self):
        base = dict(
            transition_active=True, expand_ready=True, can_afford_nexus=False,
            threat_active=False, rush_active=False,
        )
        self.assertTrue(transition_expand_reserve(**base))  # 局2 场景:站稳攒钱开矿
        self.assertFalse(transition_expand_reserve(
            **{**base, "can_afford_nexus": True}))   # 买得起即解除
        self.assertFalse(transition_expand_reserve(
            **{**base, "expand_ready": False}))      # 站不稳不预留
        self.assertFalse(transition_expand_reserve(
            **{**base, "threat_active": True}))
        self.assertFalse(transition_expand_reserve(
            **{**base, "rush_active": True}))
        self.assertFalse(transition_expand_reserve(
            **{**base, "transition_active": False}))

    def test_fleet_expand_holds_defense_exemption(self):
        # 防御未达标 → 首舰门照旧拦;评分 ≥25 → 豁免(o104 局2 接力死锁修复)
        self.assertTrue(fleet_expand_holds(True, False, 20.0))
        self.assertFalse(fleet_expand_holds(True, False, 25.0))
        # 旧双参签名行为不变(缺省评分 0 → 拦)
        self.assertTrue(fleet_expand_holds(True, False))
        self.assertFalse(fleet_expand_holds(True, True))
        self.assertFalse(fleet_expand_holds(False, False))

    def test_stargate_double_opener(self):
        # 重建窗 + 恰好 1 座(已有+在建) + 钱够 → 双开
        # O115-①:门 300/200 → 200/150(o114 局3:300 档在矿振荡下零触发)
        self.assertTrue(stargate_double_opener(True, False, 1, 200, 150))
        self.assertFalse(stargate_double_opener(True, False, 1, 199, 150))
        self.assertFalse(stargate_double_opener(True, False, 1, 200, 149))
        self.assertFalse(stargate_double_opener(True, False, 0, 500, 300))
        self.assertFalse(stargate_double_opener(True, False, 2, 500, 300))
        self.assertFalse(stargate_double_opener(True, True, 1, 500, 300))
        self.assertFalse(stargate_double_opener(False, False, 1, 500, 300))

    def test_fleet_rebuild_cannon_cap(self):
        # O106-②:重建窗塔 cap 回 4(O105 的 6 把 SG 钱吃光,o105 局3 实证);
        # 窗外不动(过渡期 cap 4 由 transition_cannon_cap 管)
        self.assertEqual(fleet_rebuild_cannon_cap(10, True), 4)
        self.assertEqual(fleet_rebuild_cannon_cap(3, True), 3)
        self.assertEqual(fleet_rebuild_cannon_cap(10, False), 10)


class TestO106TechReserve(unittest.TestCase):
    """O106(o105 0-5 尸检):重建窗科技攒钱预留 + 失联/presumed 提前到 95。"""

    def test_fleet_tech_reserve(self):
        base = dict(
            fleet_transitioned=True, first_fleet_seen=False,
            next_tech_missing=True, next_tech_affordable=False,
            threat_active=False, rush_active=False,
        )
        self.assertTrue(fleet_tech_reserve(**base))  # 局3 场景:攒钱等 SG
        self.assertFalse(fleet_tech_reserve(**{**base, "next_tech_affordable": True}))
        self.assertFalse(fleet_tech_reserve(**{**base, "next_tech_missing": False}))
        self.assertFalse(fleet_tech_reserve(**{**base, "first_fleet_seen": True}))
        self.assertFalse(fleet_tech_reserve(**{**base, "threat_active": True}))
        self.assertFalse(fleet_tech_reserve(**{**base, "rush_active": True}))
        self.assertFalse(fleet_tech_reserve(**{**base, "fleet_transitioned": False}))

    def test_early_windows_at_95(self):
        # O106-③:失联补派/presumed 启动提前 105→95(速狗局接触 t≈123,差 20s)
        self.assertTrue(scout_early_redispatch_needed(True, False, True, False, 96))
        self.assertFalse(scout_early_redispatch_needed(True, False, True, False, 94))
        self.assertTrue(presumed_rush_defense(True, True, False, False, 96, scout_lost=True))
        self.assertFalse(presumed_rush_defense(True, True, False, False, 54, scout_lost=True))  # O141:at→55


class TestO107ZergVerdict(unittest.TestCase):
    """O107(o106-vh-zerg-rush 0-5 尸检):vs Zerg 早评删除一切 greedy 出口。"""

    def test_zerg_fallback_never_greedy(self):
        # o106 局3/4/5 回潮路径:补派只看到主基地 HATCHERY(单基地、无 pool、
        # 无兵)→ 旧回落 scout_verdict 给 greedy;现一律 unknown
        self.assertEqual(early_scout_verdict(True, 0, 0, 1, True), "unknown")
        # O169:Zerg 单基地+pool 无兵不再直接判 rush(Power/Timing 运营先池后矿),
        # 回落 unknown;有早期兵(≥6)或 ≥2 军事建筑才判 rush。
        self.assertEqual(early_scout_verdict(True, 1, 0, 1, True), "unknown")
        self.assertEqual(early_scout_verdict(True, 1, 6, 1, True), "rush")
        self.assertEqual(early_scout_verdict(True, 2, 0, 1, True), "rush")
        self.assertEqual(early_scout_verdict(True, 0, 0, 2, True), "unknown")
        self.assertEqual(early_scout_verdict(True, 1, 0, 2, True), "unknown")
        # 非 zerg 回落行为不变(scout_verdict 老三档)
        self.assertEqual(early_scout_verdict(True, 0, 0, 1, False), "greedy")
        self.assertEqual(early_scout_verdict(True, 1, 0, 1, False), "rush")


class TestO109FleetScaling(unittest.TestCase):
    """O109(o108-vh-zerg-rush 0-5 尸检):舰队期人口 buffer + SG 爬坡预留。"""

    def test_supply_buffer(self):
        # 舰队相关阶段 supply_left ≤8 → bot 侧提前补水晶(暴风 6 人口/艘)
        self.assertTrue(fleet_supply_buffer_needed(True, 8.0))
        self.assertTrue(fleet_supply_buffer_needed(True, 2.0))
        self.assertFalse(fleet_supply_buffer_needed(True, 9.0))
        # 非舰队阶段(门控在调用方) → 不补
        self.assertFalse(fleet_supply_buffer_needed(False, 2.0))

    def test_stargate_reserve(self):
        # 首舰后 SG 未达气体闸目标且买不起 → 停产攒钱(产能复利)
        self.assertTrue(fleet_stargate_reserve(True, 2, 3, False))
        self.assertFalse(fleet_stargate_reserve(True, 2, 3, True))   # 买得起即解除
        self.assertFalse(fleet_stargate_reserve(True, 3, 3, False))  # 达标不停产
        self.assertFalse(fleet_stargate_reserve(False, 2, 3, False)) # 首舰未出不管


class TestO111FirstTowerRace(unittest.TestCase):
    """O111(o110-vh-zerg-rush 0-4+1ERROR 尸检):presumed 提前 + forge 前农民让位。"""

    def test_forge_first_probe_yield(self):
        # 防御紧急 + forge 未落地 + 农民 ≥12 → 停训(forge 早 ~10s)
        self.assertTrue(forge_first_probe_yield(True, False, 13))
        self.assertFalse(forge_first_probe_yield(True, False, 10))  # 保底采矿(O125:下限 12→11)
        self.assertFalse(forge_first_probe_yield(True, True, 13))   # forge 落地即恢复
        self.assertFalse(forge_first_probe_yield(False, False, 13)) # 非紧急不动


class TestO112TechSlots(unittest.TestCase):
    """O112(o110-vh-zerg-rush 0-4+1ERROR 尸检):科技槽预留/科技落分矿。"""

    def test_gateway_yields_tech_slots(self):
        # GW3+ 在主基 3x3 余量 <2 时让位;GW1/GW2 不让;余量够不让
        self.assertTrue(gateway_yields_tech_slots(2, 1))
        self.assertTrue(gateway_yields_tech_slots(2, 0))
        self.assertFalse(gateway_yields_tech_slots(2, 2))
        self.assertFalse(gateway_yields_tech_slots(1, 0))
        self.assertFalse(gateway_yields_tech_slots(0, 0))

    def test_tech_goes_to_expansion(self):
        # 舰队期 + 有其他就绪基地 → 科技落分矿;单矿 → 主基硬挤
        self.assertTrue(tech_goes_to_expansion(True, 1))
        self.assertFalse(tech_goes_to_expansion(True, 0))
        self.assertFalse(tech_goes_to_expansion(False, 2))


class TestO113SlotAnchorAndRecall(unittest.TestCase):
    """O113(o112-vh-zerg-rush 1-4 尸检):贴槽落水晶 + 舰队召回阈值。"""

    def test_pick_slot_anchor(self):
        # 选离基地最近的空闲槽(贴它建水晶 = 槽位通电);无空闲 → None
        slots = [(10.0, 10.0, True), (30.0, 30.0, True), (12.0, 10.0, False)]
        self.assertEqual(pick_slot_anchor(slots, (0.0, 0.0)), (10.0, 10.0))
        self.assertEqual(pick_slot_anchor([(30.0, 30.0, False)], (0.0, 0.0)), None)
        self.assertEqual(pick_slot_anchor([], (0.0, 0.0)), None)

    def test_fleet_no_recall_threshold(self):
        # 舰队 ≥12 → 召回阈值 25(波次喂食不回家);<12 → 原 14
        self.assertEqual(fleet_no_recall_threshold(12), 25)
        self.assertEqual(fleet_no_recall_threshold(29), 25)
        self.assertEqual(fleet_no_recall_threshold(11), 14)
        self.assertEqual(fleet_no_recall_threshold(0), 14)


class TestO114PoweredSlots(unittest.TestCase):
    """O114(o113-vh-zerg-rush 0-5 尸检):带电口径 + F2 资金守卫豁免。"""

    def test_f2_dispatch_guard_bypassed(self):
        # 防御紧急 + 0 塔 → 跳过资金预估守卫(局3:守卫把 F2 拦了 45s)
        self.assertTrue(f2_dispatch_guard_bypassed(True, 0))
        # 有塔后恢复守卫(防钉点循环);非紧急不动
        self.assertFalse(f2_dispatch_guard_bypassed(True, 1))
        self.assertFalse(f2_dispatch_guard_bypassed(False, 0))


class TestO115FleetRamp(unittest.TestCase):
    """O115(o114-vh-zerg-rush 0-5 尸检):SG 爬坡/重建窗追加选择/预留停滞解除。"""

    def test_rebuild_extra_production_id(self):
        # 重建窗 + FB 已拍 + SG<3 → 星门爬坡;过渡期/FB 未拍/SG 够 → 兵营
        self.assertEqual(rebuild_extra_production_id(True, True, 1), "STARGATE")
        self.assertEqual(rebuild_extra_production_id(True, True, 2), "STARGATE")
        self.assertEqual(rebuild_extra_production_id(True, True, 3), "GATEWAY")
        self.assertEqual(rebuild_extra_production_id(True, False, 1), "GATEWAY")
        self.assertEqual(rebuild_extra_production_id(False, True, 1), "GATEWAY")

    def test_tech_reserve_releases_on_stall(self):
        # O115-③:落位停滞确认 → 预留解除(地面回填优先)
        base = dict(
            fleet_transitioned=True, first_fleet_seen=False,
            next_tech_missing=True, next_tech_affordable=False,
            threat_active=False, rush_active=False,
        )
        self.assertTrue(fleet_tech_reserve(**base))
        self.assertFalse(fleet_tech_reserve(**{**base, "tech_stalled": True}))


class TestO116DispatchForensics(unittest.TestCase):
    """O116(o115-vh-zerg-rush 0-5 尸检):派工取证 + 建造工借用。"""

    def test_builder_borrow_ok(self):
        # GATHERING 抽干 + 停气池有人 → 借;池有人/停气池空 → 不借
        self.assertTrue(builder_borrow_ok(True, 3))
        self.assertFalse(builder_borrow_ok(False, 3))
        self.assertFalse(builder_borrow_ok(True, 0))


class TestO117GasStopWindow(unittest.TestCase):
    """O117(o116 取证系列 0-5 尸检):停气时间窗 + O11 撤回豁免扩展。"""

    def test_gas_stop_window(self):
        # rush 前 45s 停气;窗后自动回气(慢性波次防棘轮);rush 解除立即回气
        self.assertTrue(rush_gas_stop_window(True, 10.0))
        self.assertFalse(rush_gas_stop_window(True, 46.0))
        self.assertFalse(rush_gas_stop_window(False, 10.0))
        # 非 transition 流派调用方传 inf → 恒旧语义
        self.assertTrue(rush_gas_stop_window(True, 9999.0, float("inf")))

    def test_builder_release_exempt(self):
        # rush 或防御紧急 → 豁免 O11 撤回;两者皆无 → 不豁免
        self.assertTrue(builder_release_exempt(True, False))
        self.assertTrue(builder_release_exempt(False, True))
        self.assertFalse(builder_release_exempt(False, False))


class TestO157MineralCrisisGasStop(unittest.TestCase):
    """O157/O160: 气体相对矿物过剩、矿物枯竭时停气转矿。"""

    def test_triggers_when_gas_rich_mineral_poor(self):
        # O160: 不再硬绑 fleet<5，气体≥600 且矿物≤300 即触发
        self.assertTrue(mineral_crisis_gas_stop(900, 300, 4))
        self.assertTrue(mineral_crisis_gas_stop(2000, 100, 10))
        self.assertTrue(mineral_crisis_gas_stop(600, 300, 10))

    def test_not_triggered_when_minerals_ok(self):
        self.assertFalse(mineral_crisis_gas_stop(1500, 350, 4))
        self.assertFalse(mineral_crisis_gas_stop(1500, 500, 4))

    def test_not_triggered_when_gas_low(self):
        self.assertFalse(mineral_crisis_gas_stop(500, 300, 4))

    def test_low_base_count_uses_higher_mineral_threshold(self):
        # O160: 基地 ≤2 个时阈值放宽到 400
        self.assertTrue(mineral_crisis_gas_stop(1500, 400, 10, bases=2))
        self.assertTrue(mineral_crisis_gas_stop(1500, 350, 10, bases=1))
        # 基地 >2 时阈值 300
        self.assertFalse(mineral_crisis_gas_stop(1500, 350, 4, bases=3))
        self.assertTrue(mineral_crisis_gas_stop(1500, 300, 4, bases=3))


class TestO358GasToMinerals(unittest.TestCase):
    """O358-②(o357 尸检):矿气倒挂停气转矿触发判据;
    O359-②(o358 尸检):阈值 800/300 → 500/200(实测倒挂带 712-1118/5-250)。"""

    def test_gas_to_minerals_needed(self):
        # 触发象限:气 >500 且矿 <200(o358b g2 实测倒挂带:
        # 气 712-1118 而矿 5-250,1076-1201s 持续 124s)
        self.assertTrue(gas_to_minerals_needed(1184.0, 100.0))
        self.assertTrue(gas_to_minerals_needed(712.0, 195.0))
        self.assertTrue(gas_to_minerals_needed(501.0, 199.9))
        # 气够但矿也够 → 不倒挂,不动气农
        self.assertFalse(gas_to_minerals_needed(1200.0, 200.0))
        self.assertFalse(gas_to_minerals_needed(1200.0, 450.0))
        # 矿紧但气未烂(≤500)→ 不触发(留给 O157 的 600 判据;
        # 与滞回解除线 350 拉开 150 缓冲防抖动)
        self.assertFalse(gas_to_minerals_needed(500.0, 100.0))
        self.assertFalse(gas_to_minerals_needed(350.0, 50.0))


class TestO118FirstCannonRace(unittest.TestCase):
    """O118(o117-vh-zerg-rush 1-4 尸检):taken 快回收 + 首塔安全锚点。"""

    def test_tracker_entry_stale(self):
        # 工人死了 → 立即清(不等年龄);活着闲置 >10s → 清;走位中 → 留
        self.assertTrue(tracker_entry_stale(False, False, 1.0))
        self.assertTrue(tracker_entry_stale(True, True, 11.0))
        self.assertFalse(tracker_entry_stale(True, False, 30.0))
        self.assertFalse(tracker_entry_stale(True, True, 5.0))

    def test_cannon_safe_anchor(self):
        # 矿线质心朝远离坡口再退 2.5 格
        out = cannon_safe_anchor((10.0, 0.0), (0.0, 0.0))
        self.assertAlmostEqual(out[0], 12.5)
        self.assertAlmostEqual(out[1], 0.0)
        # 退化(质心=坡口) → 原样
        self.assertEqual(cannon_safe_anchor((5.0, 5.0), (5.0, 5.0)), (5.0, 5.0))


class TestO118DefenseChainOrder(unittest.TestCase):
    """O118(o117-vh-zerg-rush 1-4 尸检):forge 优先于首兵营 + 穿矿目标修正。"""

    def test_pick_walk_patch(self):
        # 选离威胁最远的矿簇(背狗侧),不是离自己最远
        patches = [(0.0, 0.0), (10.0, 0.0), (5.0, 8.0)]
        self.assertEqual(pick_walk_patch(patches, (1.0, 0.0)), (10.0, 0.0))
        self.assertEqual(pick_walk_patch(patches, (9.0, 0.0)), (0.0, 0.0))
        self.assertIsNone(pick_walk_patch([], (0.0, 0.0)))


class TestO119ExitGateEconomy(unittest.TestCase):
    """O119/O132/O143(o118/o131/o142 尸检):退出闸评分优先 + 扩张降阈。"""

    def test_fleet_exit_allowed(self):
        # O143:评分 ≥25(strong-exit 阈值)直接放行 —— 叠加门不再卡
        # (o129 局5:评分 41 清净 60s+ 单矿无 SG 不退,590 波清零)
        self.assertTrue(fleet_exit_allowed(1, 10.0, 400, defense_score=27.0,
                                           sg_present_or_pending=False))
        self.assertTrue(fleet_exit_allowed(1, 16.0, 400, defense_score=25.0))
        # 评分 <25 走原三门:bases≥2 / 地面≥20 + SG + 地面≥14
        self.assertTrue(fleet_exit_allowed(2, 16.0, 400, defense_score=20.0))
        self.assertTrue(fleet_exit_allowed(1, 22.0, 400, defense_score=20.0))
        self.assertFalse(fleet_exit_allowed(1, 16.0, 400, defense_score=20.0))
        self.assertFalse(fleet_exit_allowed(1, 16.0, 400))
        # 死线 t>540:地面 ≥14 或评分 ≥25 放行(再等也是死)
        self.assertTrue(fleet_exit_allowed(1, 16.0, 550))
        self.assertTrue(fleet_exit_allowed(1, 10.0, 550, defense_score=27.0))
        self.assertFalse(fleet_exit_allowed(1, 10.0, 550, defense_score=10.0))
        self.assertFalse(fleet_exit_allowed(1, 16.0, 530))
        # 地面不足 + 低评分 → 拦;t>540 也不放(两门都不达)
        self.assertFalse(fleet_exit_allowed(2, 12.0, 400, defense_score=20.0))
        self.assertFalse(fleet_exit_allowed(1, 12.0, 550, defense_score=10.0))

    def test_expand_ready_o119_thresholds(self):
        # O119-②:地面≥4+塔≥2+清净≥8(局5 实测波间隙 8-12s)
        self.assertTrue(transition_expand_ready(True, 2, 4, 8.0))
        self.assertFalse(transition_expand_ready(True, 2, 3, 8.0))
        self.assertFalse(transition_expand_ready(True, 2, 4, 7.0))


class TestO120GatewayReserveBattery(unittest.TestCase):
    """O120(o119-vh-zerg-rush 0-5 尸检):兵营攒钱预留/电池保底/超载。"""

    def test_gateway_reserve(self):
        base = dict(
            transition_active=True, gateways_have=1, cannons_ready=2,
            gateway_cap=3, can_afford_gw=False,
            threat_active=False, rush_active=False,
        )
        self.assertTrue(transition_gateway_reserve(**base))   # 局2 场景
        self.assertFalse(transition_gateway_reserve(**{**base, "can_afford_gw": True}))
        self.assertFalse(transition_gateway_reserve(**{**base, "gateways_have": 3}))
        # O123-①:cannons_ready 不再参与判定(常态预留)
        self.assertTrue(transition_gateway_reserve(**{**base, "cannons_ready": 1}))
        self.assertFalse(transition_gateway_reserve(**{**base, "threat_active": True}))
        self.assertFalse(transition_gateway_reserve(**{**base, "rush_active": True}))
        self.assertFalse(transition_gateway_reserve(**{**base, "transition_active": False}))

    def test_battery_floor(self):
        # 过渡期 + cyber 在链 → 保底 2;cyber 没有/非过渡期 → 原样
        self.assertEqual(transition_battery_floor(True, True, 0), 2)
        self.assertEqual(transition_battery_floor(True, True, 2), 2)
        self.assertEqual(transition_battery_floor(True, False, 0), 0)
        self.assertEqual(transition_battery_floor(False, True, 0), 0)

class TestO121VoidrayFill(unittest.TestCase):
    """O121(o120-vh-zerg-rush 0-5 尸检):虚空填窗/SG 提前解冻/退出星门前提。"""

    def test_rebuild_window_spawn(self):
        base = {"TEMPEST": {"proportion": 0.85, "priority": 0}}
        # 重建窗 → 混入 VOIDRAY p0;窗外 → 原样
        out = rebuild_window_spawn(base, True, "VOIDRAY")
        self.assertIn("VOIDRAY", out)
        self.assertEqual(out["VOIDRAY"]["priority"], 0)
        self.assertNotIn("VOIDRAY", rebuild_window_spawn(base, False, "VOIDRAY"))
        self.assertIn("TEMPEST", out)  # 原配方保留(TEMPEST 就绪后自然挤占)

    def test_rebuild_window_spawn_voidray_cap(self):
        # O379-②(o378b g1 实证):zerg lane 虚空总量帽 2(场上含在产
        # 口径)—— 场上 2 虚空不注入、1 虚空注入;terran lane 不传帽
        # (None)原语义不动(无帽注入)
        base = {"TEMPEST": {"proportion": 0.85, "priority": 0}}
        capped = rebuild_window_spawn(
            base, True, "VOIDRAY", voidray_field=2, voidray_cap=2
        )
        self.assertNotIn("VOIDRAY", capped)
        under = rebuild_window_spawn(
            base, True, "VOIDRAY", voidray_field=1, voidray_cap=2
        )
        self.assertIn("VOIDRAY", under)
        uncapped = rebuild_window_spawn(
            base, True, "VOIDRAY", voidray_field=9, voidray_cap=None
        )
        self.assertIn("VOIDRAY", uncapped)
        # 帽只在重建窗内有意义:窗外恒不注入
        self.assertNotIn(
            "VOIDRAY",
            rebuild_window_spawn(base, False, "VOIDRAY", voidray_field=0, voidray_cap=2),
        )

    def test_transition_stargate_allowed(self):
        # 过渡期防御评分 ≥25 → SG 解冻;否则冻结照旧
        self.assertTrue(transition_stargate_allowed(True, 25.0))
        self.assertFalse(transition_stargate_allowed(True, 24.0))
        self.assertFalse(transition_stargate_allowed(False, 30.0))

    def test_exit_gate_stargate_precondition(self):
        # 低评分时 SG 未拍/未在建 → 不退出(空窗必死);已拍 → 按经济/地面门走
        self.assertFalse(fleet_exit_allowed(2, 16.0, 400, sg_present_or_pending=False))
        self.assertTrue(fleet_exit_allowed(2, 16.0, 400, sg_present_or_pending=True))
        # O143:评分 ≥25 豁免 SG 前提(O140 的 35 档被吸收 —— 叠加门=死锁,
        # o139 局2/o129 局5 实证);评分 <25 且无 SG 且经济不达 → 仍拦
        self.assertTrue(fleet_exit_allowed(
            1, 16.0, 400, defense_score=36.0, sg_present_or_pending=False))
        self.assertTrue(fleet_exit_allowed(
            1, 16.0, 400, defense_score=27.0, sg_present_or_pending=False))
        self.assertFalse(fleet_exit_allowed(
            1, 16.0, 400, defense_score=20.0, sg_present_or_pending=False))
        # t>540 死线放行不受 SG 门;缺省 True(评分门可达)行为不变
        self.assertTrue(fleet_exit_allowed(1, 16.0, 550, sg_present_or_pending=False))
        self.assertTrue(fleet_exit_allowed(2, 16.0, 400))


class TestO122WavePhaseExpand(unittest.TestCase):
    """O122(o121b-vh-zerg-rush 0-5 尸检):首波后扩张/虚空优先/超载目标。"""

    def test_expand_after_first_wave(self):
        # 见过一波且已清 + 塔2地面4 → 开(不看清净秒数)
        self.assertTrue(transition_expand_after_first_wave(True, True, 2, 4))
        self.assertFalse(transition_expand_after_first_wave(True, False, 2, 4))
        self.assertFalse(transition_expand_after_first_wave(True, True, 1, 4))
        self.assertFalse(transition_expand_after_first_wave(True, True, 2, 3))
        self.assertFalse(transition_expand_after_first_wave(False, True, 3, 8))

    def test_tech_reserve_yields_to_voidray_fill(self):
        base = dict(
            fleet_transitioned=True, first_fleet_seen=False,
            next_tech_missing=True, next_tech_affordable=False,
            threat_active=False, rush_active=False,
        )
        # 虚空未出/未在产 → 不预留(先产虚空顶窗);虚空在产后 → 攒 FB
        self.assertFalse(fleet_tech_reserve(**base, voidray_pending_or_seen=False))
        self.assertTrue(fleet_tech_reserve(**base, voidray_pending_or_seen=True))
        # 旧签名(缺省 True)行为不变
        self.assertTrue(fleet_tech_reserve(**base))


    def test_should_overcharge(self):
        # 敌地面压到电池旁 + 能量 ≥45 → 超载;否则不烧
        from bot.shield_battery import should_overcharge
        self.assertTrue(should_overcharge(2, 45.0))
        self.assertFalse(should_overcharge(2, 44.0))
        self.assertFalse(should_overcharge(1, 80.0))

    def test_overcharge_struct_whitelist(self):
        # O123-②:超载只挂塔/主基地 —— PYLON 白烧(o122 局3 实证)不再发生
        from bot.shield_battery import overcharge_struct_allowed
        self.assertTrue(overcharge_struct_allowed("PHOTONCANNON"))
        self.assertTrue(overcharge_struct_allowed("NEXUS"))
        self.assertFalse(overcharge_struct_allowed("PYLON"))
        self.assertFalse(overcharge_struct_allowed("GATEWAY"))


class TestO124FirstZealotSprint(unittest.TestCase):
    """O124(o123-vh-zerg-rush 0-5 尸检):预留不饿现役/过渡缓气/首叉冲刺。"""

    def test_reserve_yields_to_producible_zealot(self):
        base = dict(
            transition_active=True, gateways_have=1, cannons_ready=2,
            gateway_cap=3, can_afford_gw=False,
            threat_active=False, rush_active=False,
        )
        # 有空闲兵营且矿够出叉 → 不预留(o123 局1:GW1 空转 76s 的根因修复)
        self.assertFalse(transition_gateway_reserve(
            **base, zealot_producible=True))
        # 无空闲兵营/矿不够 → 预留照旧;缺省参数旧行为不变
        self.assertTrue(transition_gateway_reserve(**base))
        self.assertTrue(transition_gateway_reserve(
            **base, zealot_producible=False))

    def test_transition_pauses_gas(self):
        self.assertTrue(transition_pauses_gas(True))
        self.assertFalse(transition_pauses_gas(False))

    def test_first_zealot_sprint(self):
        # rush确认+兵营就绪+首叉未出+矿<100 → 冲刺(停水晶/农民)
        self.assertTrue(first_zealot_sprint(True, True, False, 50.0))
        self.assertFalse(first_zealot_sprint(True, True, False, 100.0))
        self.assertFalse(first_zealot_sprint(True, True, True, 50.0))
        self.assertFalse(first_zealot_sprint(True, False, False, 50.0))
        self.assertFalse(first_zealot_sprint(False, True, False, 50.0))


class TestO125FirstZealotRace(unittest.TestCase):
    """O125(o124-vh-zerg-rush 0-5 尸检):叉海策略的首叉竞速。"""

    def test_forge_before_first_gateway(self):
        # O127-①(数据终裁,恢复 O118):防御紧急 + forge 未拍 → GW1 让位;
        # forge 已拍(含在建) → GW1 紧随;非紧急不动
        self.assertTrue(forge_before_first_gateway(True, False))
        self.assertFalse(forge_before_first_gateway(True, True))
        self.assertFalse(forge_before_first_gateway(False, False))
        # O308-①(o307a game_02/03 实证):Zerg Timing 豁免 —— ZT 首波
        # ~240s(非 o126b 的 ~154s 狗波),GW1 先拍首叉 ~180s 上岗
        self.assertFalse(forge_before_first_gateway(True, False, True))
        # Zerg Rush 保持 O127 数据终裁(forge 先)
        self.assertTrue(forge_before_first_gateway(True, False, False))

    def test_serialize_presumed_cannons(self):
        # O308-③:首塔就绪前炮塔串行化(目标压 1,资金集中)
        self.assertTrue(serialize_presumed_cannons(0))
        # 首塔就绪即解除
        self.assertFalse(serialize_presumed_cannons(1))
        self.assertFalse(serialize_presumed_cannons(3))

    def test_chrono_first_zealot(self):
        # rush/过渡 + 首叉未出 → chrono 给兵营;首叉出场/非紧急 → 不抢
        self.assertTrue(chrono_first_zealot(True, False))
        self.assertFalse(chrono_first_zealot(True, True))
        self.assertFalse(chrono_first_zealot(False, False))

    def test_probe_yield_floor_11(self):
        # O125-①:rush 窗农民硬刹车 12→11(第 12 个农民 = GW 提前 ~15s)
        self.assertTrue(forge_first_probe_yield(True, False, 11))
        self.assertFalse(forge_first_probe_yield(True, False, 10))


class TestO126SpawnArbiter(unittest.TestCase):
    """O126/O135/O216c:产出暂停仲裁 + GW 链等首叉。"""

    def test_reserves_do_not_pause_spawn_except_zerg_timing_expand(self):
        # O135:暂停型预留体系证伪 —— 除 O216c Zerg Timing 二矿基金保护外,
        # 任何预留组合都不再暂停产兵。
        self.assertIsNone(spawn_pause_reason(rebuild_nexus=False))
        # Nexus 已开工或存款够时不暂停
        self.assertIsNone(
            spawn_pause_reason(
                rebuild_nexus=False,
                expand_holding=True,
                is_zerg_timing=True,
                nexus_unstarted=1,
                minerals=400.0,
            )
        )
        self.assertIsNone(
            spawn_pause_reason(
                rebuild_nexus=False,
                expand_holding=True,
                is_zerg_timing=True,
                nexus_unstarted=0,
                minerals=200.0,
            )
        )

    def test_zerg_timing_expand_reserve_pauses_spawn(self):
        # O216c:Nexus 已派工未开工、存款 <400 时暂停产兵,优先二矿基金
        self.assertEqual(
            spawn_pause_reason(
                rebuild_nexus=False,
                expand_holding=True,
                is_zerg_timing=True,
                nexus_unstarted=1,
                minerals=350.0,
            ),
            "zerg_timing_expand_reserve",
        )

    def test_zerg_timing_expand_reserve_enemy_gate(self):
        # O298-②:敌可见 supply ≥ 我方时 expand_reserve 不停产(波间隙特权)
        _kw = dict(
            rebuild_nexus=False,
            expand_holding=True,
            is_zerg_timing=True,
            nexus_unstarted=1,
            minerals=350.0,
        )
        self.assertIsNone(
            spawn_pause_reason(enemy_supply=45.0, own_supply=29.0, **_kw)
        )
        # 敌我相等也不停(严格闸)
        self.assertIsNone(
            spawn_pause_reason(enemy_supply=29.0, own_supply=29.0, **_kw)
        )
        # 敌 < 我 → 维持暂停
        self.assertEqual(
            spawn_pause_reason(enemy_supply=10.0, own_supply=29.0, **_kw),
            "zerg_timing_expand_reserve",
        )

    def test_zerg_timing_expand_reserve_ground_floor(self):
        # O307-②(o306c game_03/05 实证):地面低于保底(12 supply)时停产
        # 攒 Nexus = 裸奔 —— 侦查断链期 enemy_supply=0,敌情闸失效,
        # 地面保底是盲期最后防线。
        _kw = dict(
            rebuild_nexus=False,
            expand_holding=True,
            is_zerg_timing=True,
            nexus_unstarted=1,
            minerals=350.0,
            enemy_supply=0.0,
            own_supply=23.0,
        )
        # 地面 2 兵(4 supply)< 12 → 不停产(game_03 死法)
        self.assertIsNone(spawn_pause_reason(ground_supply=4.0, **_kw))
        # 地面 5 兵(10 supply)< 12 → 不停产(game_05 死法)
        self.assertIsNone(spawn_pause_reason(ground_supply=10.0, **_kw))
        # 地面达标(≥12 supply)→ 维持暂停
        self.assertEqual(
            spawn_pause_reason(ground_supply=12.0, **_kw),
            "zerg_timing_expand_reserve",
        )

    def test_expand_holding_should_abort(self):
        # O307-③(o306c game_05 实证):Nexus 未开工持有 326s 冻死科技链
        # O309-③:超时 90→60(重试周期 135s→90s,二矿时点提前)
        # 未超时 → 不放弃(正常攒钱窗)
        self.assertFalse(expand_holding_should_abort(45.0, 1, False))
        # 超时但已开工(在建不算死锁)
        self.assertFalse(expand_holding_should_abort(120.0, 0, False))
        # 超时但买得起(下一帧就开工,不是死锁)
        self.assertFalse(expand_holding_should_abort(120.0, 1, True))
        # 超时 + 未开工 + 买不起 → 撤销派工解锁科技链
        self.assertTrue(expand_holding_should_abort(75.0, 1, False))

    def test_holding_allows_cyber(self):
        # O307-①:holding 期放行 CYBERNETICSCORE(仅 Zerg Timing + 兵营就绪)
        self.assertTrue(holding_allows_cyber(True, True))
        # 非 ZT 不放行(其它对阵零变化)
        self.assertFalse(holding_allows_cyber(False, True))
        # 兵营未就绪不放行(链序不乱)
        self.assertFalse(holding_allows_cyber(True, False))

    def test_zerg_timing_tech_reserve_pauses_spawn(self):
        # O224:Zerg Timing 防御已立且 SG/FB 缺失买不起时,暂停地面产兵攒钱
        self.assertEqual(
            spawn_pause_reason(
                rebuild_nexus=False,
                is_zerg_timing=True,
                tech_saving=True,
                minerals=100.0,
                tech_price=150.0,
            ),
            "zerg_timing_tech_reserve",
        )
        # 买得起即恢复(自校正)
        self.assertIsNone(
            spawn_pause_reason(
                rebuild_nexus=False,
                is_zerg_timing=True,
                tech_saving=True,
                minerals=150.0,
                tech_price=150.0,
            )
        )
        # 非 zerg timing / 非攒钱期不受影响
        self.assertIsNone(
            spawn_pause_reason(
                rebuild_nexus=False,
                is_zerg_timing=False,
                tech_saving=True,
                minerals=0.0,
            )
        )

    def test_rebuild_nexus_still_pauses(self):
        # 基地清零应急(没经济一切免谈)仍可暂停 —— 不是预留型,保留
        self.assertEqual(
            spawn_pause_reason(rebuild_nexus=True), "rebuild_nexus"
        )

    def test_gateway_chain_after_first_zealot(self):
        # GW2+ 等首叉在产/出场;GW1 不等;首叉出来后恢复
        self.assertTrue(gateway_chain_after_first_zealot(1, False))
        self.assertFalse(gateway_chain_after_first_zealot(0, False))
        self.assertFalse(gateway_chain_after_first_zealot(1, True))


class TestO128TowerZonePower(unittest.TestCase):
    """O128(o127-vh-zerg-rush 0-5 尸检):塔位供电水晶前置。"""

    def test_tower_zone_pylon_needed(self):
        # 首塔未就绪未在建 + 塔位无电 → 派供电水晶;任一条件翻假即止
        self.assertTrue(tower_zone_pylon_needed(0, 0, 0))
        self.assertFalse(tower_zone_pylon_needed(1, 0, 0))
        self.assertFalse(tower_zone_pylon_needed(0, 1, 0))
        self.assertFalse(tower_zone_pylon_needed(0, 0, 1))


class TestO129DefenseSprint(unittest.TestCase):
    """O129(o128b-vh-zerg-rush 尸检):首波防御冲刺总闸。"""

    def _s(self, **kw):
        base = dict(
            has_transition=True, defense_urgent=True, forge_ready=False,
            first_cannon_ready=False, first_zealot_seen=False, enemy_home=0,
        )
        base.update(kw)
        return defense_sprint_active(**base)

    def test_sprint_until_chain_complete(self):
        # 链未完成 → 冲刺;全齐(forge就绪+首塔+首叉在产) → 解除
        self.assertTrue(self._s())
        self.assertTrue(self._s(forge_ready=True, first_cannon_ready=True))
        self.assertFalse(self._s(
            forge_ready=True, first_cannon_ready=True, first_zealot_seen=True,
        ))

    def test_contact_exits_sprint(self):
        # 敌进家 ≥2 → 退出(急性窗交还 F2/响应包)
        self.assertFalse(self._s(enemy_home=2))

    def test_gates(self):
        self.assertFalse(self._s(has_transition=False))
        self.assertFalse(self._s(defense_urgent=False))


    def test_gates(self):
        self.assertFalse(self._s(has_transition=False))
        self.assertFalse(self._s(defense_urgent=False))

    def test_escape_valve(self):
        # O130-①:冲刺 >120s 强制退出(链断不拖死全局);120s 内照冲
        self.assertTrue(self._s(sprint_age=60.0))
        self.assertFalse(self._s(sprint_age=121.0))


class TestO130EscapeValve(unittest.TestCase):
    """O130(o129-vh-zerg-rush 1-4 尸检):逃逸阀/探针豁免/协防底线。"""

    def test_sprint_blocks_probes(self):
        # 农民 <8 → 冲刺不拦探针(经济活命);≥8 照拦
        self.assertTrue(sprint_blocks_probes(12))
        self.assertTrue(sprint_blocks_probes(8))
        self.assertFalse(sprint_blocks_probes(7))

    def test_escort_pull_cap(self):
        # 拉人数 = min(威胁需求, 农民-6) —— 保留采矿底线(旧默认)
        self.assertEqual(escort_pull_cap(8, 14, keep_mining=6, cap=10), 8)
        self.assertEqual(escort_pull_cap(3, 14, keep_mining=6, cap=10), 5)
        self.assertEqual(escort_pull_cap(12, 8, keep_mining=6, cap=10), 2)
        self.assertEqual(escort_pull_cap(12, 5, keep_mining=6, cap=10), 0)

    def test_escort_pull_cap_o166_dynamic(self):
        # O166: 调用方传 keep_mining=max(4, workers//2), cap=6
        self.assertEqual(
            escort_pull_cap(20, 20, keep_mining=10, cap=6), 6
        )  # 需求封顶 6
        self.assertEqual(
            escort_pull_cap(8, 12, keep_mining=6, cap=6), 6
        )  # 需求 10→cap 6
        self.assertEqual(
            escort_pull_cap(8, 10, keep_mining=5, cap=6), 5
        )  # 留 5 采,最多拉 5
        self.assertEqual(
            escort_pull_cap(12, 7, keep_mining=4, cap=6), 3
        )  # 留 4 采,拉 3
        self.assertEqual(
            escort_pull_cap(12, 4, keep_mining=4, cap=6), 0
        )  # 不到保留底线不拉


class TestO131QueueNotPause(unittest.TestCase):
    """O131(o130-vh-zerg-rush 0-5 尸检):排队型兵营链 + 预留死锁保险丝。"""

    def test_tower_yields_gateway_chain(self):
        # 过渡期 + 2 塔 + GW<cap → 塔让位(排队型;叉子照产)
        self.assertTrue(tower_yields_gateway_chain(True, 1, 3, 2))
        self.assertTrue(tower_yields_gateway_chain(True, 2, 3, 4))
        self.assertFalse(tower_yields_gateway_chain(True, 3, 3, 2))
        self.assertFalse(tower_yields_gateway_chain(True, 1, 3, 1))
        self.assertFalse(tower_yields_gateway_chain(False, 1, 3, 5))

    def test_reserve_deadlock_break(self):
        # 连续激活 >60s 且矿 <150 → 熔断;否则不干预
        self.assertTrue(reserve_deadlock_break(100.0, 161.0, 100.0))
        self.assertFalse(reserve_deadlock_break(100.0, 159.0, 100.0))
        self.assertFalse(reserve_deadlock_break(100.0, 200.0, 200.0))
        self.assertFalse(reserve_deadlock_break(None, 200.0, 0.0))


class TestO133TimingDefense(unittest.TestCase):
    """O133(o132-vh-zerg-timing 1-4 尸检):二次侦查提前/250-300 防御冲刺
    /unknown 保守防御。四败同指纹:timing 波 273-289 到脸,323-384 死。"""

    def test_rescout_window_advanced(self):
        # O133-①:195 派出/260 硬截止 —— 在 timing 波 ~250 成型前读完;
        # 旧 250/330 看到兵时波已出门(273-289 到脸)
        self.assertEqual(RESCOUT_DISPATCH_AT, 195.0)
        self.assertEqual(RESCOUT_HARD_DEADLINE, 260.0)
        self.assertLess(RESCOUT_DISPATCH_AT, RESCOUT_HARD_DEADLINE)
        self.assertLess(RESCOUT_HARD_DEADLINE, 273.0)  # 波到脸前必须有结论

    def test_transition_timing_sprint(self):
        # O144-②:缺省关断(无差别冲刺在非 rush 局白吃矿)
        self.assertFalse(transition_timing_sprint(True, "rush", 240))
        self.assertFalse(transition_timing_sprint(True, "unknown", 300))
        # enabled=True 恢复 O133 语义:过渡 active + verdict≠greedy + t≥240
        self.assertTrue(transition_timing_sprint(True, "rush", 240, enabled=True))
        self.assertTrue(transition_timing_sprint(True, "unknown", 300, enabled=True))
        self.assertTrue(transition_timing_sprint(True, None, 250, enabled=True))
        self.assertFalse(transition_timing_sprint(True, "greedy", 300, enabled=True))
        self.assertFalse(transition_timing_sprint(True, "rush", 239, enabled=True))
        self.assertFalse(transition_timing_sprint(False, "rush", 300, enabled=True))

    def test_unknown_verdict_defense(self):
        # O144-①:缺省关断(unknown 不再拉 presumed 级防御)
        self.assertFalse(unknown_verdict_defense(True, True, "unknown", False, False, 200))
        # enabled=True 恢复 O133 语义
        self.assertTrue(unknown_verdict_defense(
            True, True, "unknown", False, False, 200, enabled=True))
        self.assertFalse(unknown_verdict_defense(
            True, True, "unknown", False, True, 250, enabled=True))
        self.assertFalse(unknown_verdict_defense(
            True, True, "unknown", True, False, 250, enabled=True))
        self.assertFalse(unknown_verdict_defense(
            True, True, "greedy", False, False, 250, enabled=True))
        self.assertFalse(unknown_verdict_defense(
            True, True, None, False, False, 250, enabled=True))
        self.assertFalse(unknown_verdict_defense(
            True, True, "unknown", False, False, 199, enabled=True))
        self.assertFalse(unknown_verdict_defense(
            False, True, "unknown", False, False, 250, enabled=True))
        self.assertFalse(unknown_verdict_defense(
            True, False, "unknown", False, False, 250, enabled=True))

    def test_ground_floor_active(self):
        # O144-③:rush 确认 或 敌可见地面 ≥4 → floor 激活;纯运营局不产地面
        self.assertTrue(ground_floor_active(True, 0))
        self.assertTrue(ground_floor_active(False, 4))
        self.assertFalse(ground_floor_active(False, 3))
        self.assertFalse(ground_floor_active(False, 0))

    def test_unknown_zt_floor_cap(self):
        # O314-③(o313b game_02/03 实证):波窗(t≥240)敌可见 ≥4 → cap 8
        self.assertEqual(unknown_zt_floor_cap(300.0, 20, False), 8)
        self.assertEqual(unknown_zt_floor_cap(240.0, 4, False), 8)
        # O316-①(o315b game_01:银行 485 叉仅 2,cap 是枷):常态 3→5
        self.assertEqual(unknown_zt_floor_cap(300.0, 3, False), 5)
        self.assertEqual(unknown_zt_floor_cap(200.0, 20, False), 5)
        # wave_incoming 同样 5(O279)
        self.assertEqual(unknown_zt_floor_cap(200.0, 0, True), 5)

    def test_zerg_timing_unknown_floor(self):
        # O255-③:Zerg Timing + unknown + t≥220 + 舰队未出 → 死窗叉子 floor
        self.assertTrue(zerg_timing_unknown_floor(True, "unknown", 220, False))
        self.assertTrue(zerg_timing_unknown_floor(True, "unknown", 300, False))
        # 舰队已出 / 判决落地 / 时点未到 / 非 Timing → 不激活
        self.assertFalse(zerg_timing_unknown_floor(True, "unknown", 300, True))
        self.assertFalse(zerg_timing_unknown_floor(True, "greedy", 300, False))
        self.assertFalse(zerg_timing_unknown_floor(True, "rush", 300, False))
        self.assertFalse(zerg_timing_unknown_floor(True, None, 300, False))
        self.assertFalse(zerg_timing_unknown_floor(True, "unknown", 219, False))
        self.assertFalse(zerg_timing_unknown_floor(False, "unknown", 300, False))

    def test_fb_gate_f2_exempt_zt(self):
        # O255-①:Zerg Timing 且 SG 未就绪 → F2 豁免 FB 让位闸;SG 就绪恢复
        self.assertTrue(fb_gate_f2_exempt_zt(True, False))
        self.assertFalse(fb_gate_f2_exempt_zt(True, True))
        self.assertFalse(fb_gate_f2_exempt_zt(False, False))

    def test_zt_wave_read(self):
        # O320-①:warren 先行 + 敌单基地(t≥150)→ fast(快波武装)
        self.assertEqual(zt_wave_read(True, 1, 200.0), "fast")
        # 敌已开二矿 + 未见 warren(t≥200)→ slow(退保+早开矿)
        self.assertEqual(zt_wave_read(False, 2, 240.0), "slow")
        # 情报不足不押注
        self.assertIsNone(zt_wave_read(False, 1, 300.0))
        # 时点闸:warren 早见但 t<150 不判;敌二矿 t<200 不判
        self.assertIsNone(zt_wave_read(True, 1, 140.0))
        self.assertIsNone(zt_wave_read(False, 2, 190.0))
        # warren + 敌多基地(蟑螂巢是后补的)→ 不判 fast
        self.assertIsNone(zt_wave_read(True, 2, 300.0))

    def test_zerg_timing_expand_allowed(self):
        # O278-②:t<280 或首塔未就绪 → 不开;t≥280 + 首塔 + 家无敌 +
        # 分矿点无敌 → 放行;首舰已出/t≥620 硬门原样(不看塔)
        self.assertFalse(zerg_timing_expand_allowed(True, False, 250, 0, 0, 1))
        self.assertFalse(zerg_timing_expand_allowed(True, False, 280, 0, 0, 0))
        self.assertTrue(zerg_timing_expand_allowed(True, False, 280, 0, 0, 1))
        self.assertFalse(zerg_timing_expand_allowed(True, False, 400, 2, 0, 1))
        self.assertFalse(zerg_timing_expand_allowed(True, False, 400, 0, 1, 1))
        self.assertTrue(zerg_timing_expand_allowed(True, True, 400, 2, 1, 0))
        self.assertTrue(zerg_timing_expand_allowed(True, False, 620, 0, 0, 0))
        # 非 ZT 不受影响
        self.assertTrue(zerg_timing_expand_allowed(False, False, 100, 0, 0, 0))

    def test_zerg_timing_expand_allowed_o312(self):
        # O312(A 案 GM 式):窗 200 + GW1 就绪可作防御前提
        # 200s + 0 塔 + GW1 就绪 + 家/分矿点无敌 → 放行
        self.assertTrue(
            zerg_timing_expand_allowed(
                True, False, 200, 0, 0, 0, at=200.0, gw_ready=True
            )
        )
        # 200s + 0 塔 + 无 GW1 → 仍不开(防御前提不空)
        self.assertFalse(
            zerg_timing_expand_allowed(
                True, False, 200, 0, 0, 0, at=200.0, gw_ready=False
            )
        )
        # 窗不到(199s)有 GW1 也不开
        self.assertFalse(
            zerg_timing_expand_allowed(
                True, False, 199, 0, 0, 0, at=200.0, gw_ready=True
            )
        )
        # 家 40 格有敌 / 分矿点有敌仍不开(波中不拍)
        self.assertFalse(
            zerg_timing_expand_allowed(
                True, False, 200, 1, 0, 0, at=200.0, gw_ready=True
            )
        )
        self.assertFalse(
            zerg_timing_expand_allowed(
                True, False, 200, 0, 1, 0, at=200.0, gw_ready=True
            )
        )

    def test_pick_pocket_expansion(self):
        # O281:口袋矿 = 离敌出生点最远的空闲扩张点;空入参 → None
        class _P:
            def __init__(self, x, y):
                self.x, self.y = x, y

            def distance_to(self, o):
                return ((self.x - o.x) ** 2 + (self.y - o.y) ** 2) ** 0.5

        enemy = _P(0, 0)
        near, mid, far = _P(10, 0), _P(20, 0), _P(30, 0)
        self.assertIs(pick_pocket_expansion([near, mid, far], enemy), far)
        self.assertIs(pick_pocket_expansion([far, near, mid], enemy), far)
        self.assertIs(pick_pocket_expansion([near], enemy), near)
        self.assertIsNone(pick_pocket_expansion([], enemy))
        self.assertIsNone(pick_pocket_expansion([near], None))
        # O291:背靠图缘加分 —— 同等离敌距离下贴缘点胜出;纯距离点
        # 优势 >0.5×贴缘差时仍选纯距离点
        rect = (0, 0, 100, 100)
        edge_pt = _P(45, 2)   # 离敌 45.04,贴缘(edge=2)
        open_pt = _P(45, 40)  # 离敌 60.2? 不,用同距离对照:离敌 45,edge=40
        open_pt = _P(32, 32)  # 离敌 45.25(≈同距),edge=32
        # edge_pt score=45.04-1=44.04;open_pt score=45.25-16=29.25 → 贴缘胜
        self.assertIs(pick_pocket_expansion([open_pt, edge_pt], enemy, rect), edge_pt)
        # 纯距离优势明显(60 vs 45.04,差 15>0.5×(40-2)=19? 差14.96<19) → 贴缘仍胜
        far_open = _P(60, 0)  # 离敌 60,edge=40(图缘 x 右缘 100-60=40,y 缘 0) → edge=0!
        far_open = _P(55, 50)  # 离敌 74.3,edge=min(55,45,50,50)=45 → score 51.8 胜
        self.assertIs(pick_pocket_expansion([edge_pt, far_open], enemy, rect), far_open)
        # rect=None → 纯距离(向后兼容)
        self.assertIs(pick_pocket_expansion([open_pt, edge_pt], enemy, None), open_pt)

    def test_pick_pocket_expansion_openness(self):
        # O328(司令观察+探针实测):AbyssalReefLE 主基右下 (161.5,21.5),
        # 旧分选北侧 (157.5,50.5)(open14=14/24 敞开),司令指定西侧
        # (129.5,26.5)(open14=10/24,背靠墙体只封 1-2 口)。
        class _P:
            def __init__(self, x, y):
                self.x, self.y = x, y

            def distance_to(self, o):
                return ((self.x - o.x) ** 2 + (self.y - o.y) ** 2) ** 0.5

        enemy = _P(38.5, 122.5)
        main = _P(161.5, 21.5)
        rect = (24, 4, 152, 136)
        west = _P(129.5, 26.5)   # open14=10/24,d_enemy=132.3
        north = _P(157.5, 50.5)  # open14=14/24,d_enemy=139.1
        _open = {id(west): 10, id(north): 14}
        openness = lambda el: _open[id(el)]
        # 旧行为(无 openness):北侧凭 d_enemy 胜出(o326 现状,司令判定错)
        self.assertIs(pick_pocket_expansion([west, north], enemy, rect), north)
        # O328:开阔度+距主基入分 → 西侧口袋矿胜出
        self.assertIs(
            pick_pocket_expansion(
                [west, north], enemy, rect, main=main, openness=openness
            ),
            west,
        )
        # 只传 main 不传 openness:距主基项单独生效(西侧 32.4 vs 北侧 29.3,
        # 0.5 权重差 1.55 < 旧分差 8.8 → 仍北侧,不意外翻转)
        self.assertIs(
            pick_pocket_expansion([west, north], enemy, rect, main=main), north
        )

    def test_ring_openness(self):
        class _Grid:
            def __init__(self, pred):
                self._pred = pred

            def is_set(self, p):
                return self._pred(p)

        class _P:
            def __init__(self, x, y):
                self.x, self.y = x, y

        pos = _P(100.0, 100.0)
        # 全可通行 → 24/24;全不可通行 → 0/24
        self.assertEqual(ring_openness(_Grid(lambda p: True), pos), 24)
        self.assertEqual(ring_openness(_Grid(lambda p: False), pos), 0)
        # 半平面(x<100 可通行)→ 约一半
        half = ring_openness(_Grid(lambda p: p[0] < 100), pos)
        self.assertTrue(8 <= half <= 16, half)
        # is_set 抛异常(出界)→ 按不可通行计,不炸
        self.assertEqual(
            ring_openness(_Grid(lambda p: 1 / 0), pos), 0
        )

    def test_rush_blocks_reserve(self):
        # O151-①:rush 但家 40 格无敌(波间隙)→ 不挡攒钱预留;
        # 敌在家(急性)或不 rush → 维持原语义
        self.assertTrue(rush_blocks_reserve(True, 2))
        self.assertFalse(rush_blocks_reserve(True, 0))
        self.assertFalse(rush_blocks_reserve(False, 5))

    def test_carrier_sg_bonus(self):
        # O152-③:carrier(transition 流)SG 气体闸 +1;基线流 0(逐位不变)
        self.assertEqual(carrier_sg_bonus(True), 1)
        self.assertEqual(carrier_sg_bonus(False), 0)


class TestO134GroundFloor(unittest.TestCase):
    """O134(o133-vh-zerg-timing 0-5 尸检):非过渡局地面保底兵力。

    局2 铁证:carrier 标准路径 t=542 仅 1 叉+2 兵营(39 农民 2 矿经济
    很好)—— GW1 拖到 ~350、UC prioritize 截断产兵,525 波(25+ supply)
    到脸 1 叉应战。"""

    def test_ground_floor_gateways(self):
        # pre_fleet 流派( carrier)非过渡 + GW<2 → 保底补 GW
        self.assertTrue(ground_floor_gateways(True, False, 0))
        self.assertTrue(ground_floor_gateways(True, False, 1))
        # 达标/过渡期(过渡 gateway_cap 接管,不双管)/无 pre_fleet → 不补
        self.assertFalse(ground_floor_gateways(True, False, 2))
        self.assertFalse(ground_floor_gateways(True, True, 0))
        self.assertFalse(ground_floor_gateways(False, False, 0))

    def test_ground_floor_unmet(self):
        # 地面 < floor 目标(5叉+2追猎=7)→ 未达(研究不得截断产兵)
        self.assertTrue(ground_floor_unmet(True, False, 1, 7))
        self.assertTrue(ground_floor_unmet(True, False, 6, 7))
        # 达标/过渡期/无 pre_fleet → 不干预(UC prioritize 照旧)
        self.assertFalse(ground_floor_unmet(True, False, 7, 7))
        self.assertFalse(ground_floor_unmet(True, True, 0, 7))
        self.assertFalse(ground_floor_unmet(False, False, 0, 7))


class TestO136RampWall(unittest.TestCase):
    """O136(vs Zerg 速骰:波 154-160,叉/塔竞速到极限):坡口墙。"""

    def test_pick_wall_positions(self):
        # frozenset 序不定 → 按离主基距离排序取前 n,逐局一致
        slots = [(30.0, 30.0), (10.0, 10.0), (20.0, 20.0)]
        self.assertEqual(
            pick_wall_positions(slots, (0.0, 0.0)), [(10.0, 10.0), (20.0, 20.0)]
        )
        # 乱序输入结果相同(确定性);None/空 → []
        self.assertEqual(
            pick_wall_positions(list(reversed(slots)), (0.0, 0.0)),
            [(10.0, 10.0), (20.0, 20.0)],
        )
        self.assertEqual(pick_wall_positions(None, (0.0, 0.0)), [])
        self.assertEqual(pick_wall_positions([], (0.0, 0.0)), [])
        # n=1 只取最近槽
        self.assertEqual(pick_wall_positions(slots, (0.0, 0.0), n=1), [(10.0, 10.0)])

    def test_wall_hold_point(self):
        # 缝(10,0) 基地(0,0) → 内侧回退 1.5 → (8.5, 0)
        x, y = wall_hold_point((10.0, 0.0), (0.0, 0.0))
        self.assertAlmostEqual(x, 8.5)
        self.assertAlmostEqual(y, 0.0)
        # 缝与基地重合 → 返回缝点(不除零)
        self.assertEqual(wall_hold_point((5.0, 5.0), (5.0, 5.0)), (5.0, 5.0))

    def test_wall_escort_needed(self):
        # 墙模式 + 未封口 + 敌 ≥2 → 堵缝;封口/敌退/无墙 → 不拉
        self.assertTrue(wall_escort_needed(True, False, 2))
        self.assertFalse(wall_escort_needed(True, True, 6))
        self.assertFalse(wall_escort_needed(True, False, 1))
        self.assertFalse(wall_escort_needed(False, False, 6))

    def test_wall_fallback_due(self):
        # O137-①:失败持续 >30s → 回落普通槽;未失败/30s 内(含等电窗)不回落
        self.assertFalse(wall_fallback_due(None, 100.0))
        self.assertFalse(wall_fallback_due(100.0, 129.0))
        self.assertTrue(wall_fallback_due(100.0, 131.0))

    def test_wall_disabled_after(self):
        # O137-②:2 击 latch 关墙(墙不能比命重要);1 击继续尝试
        self.assertFalse(wall_disabled_after(0))
        self.assertFalse(wall_disabled_after(1))
        self.assertTrue(wall_disabled_after(2))
        self.assertTrue(wall_disabled_after(3))


class TestO146ProbeFloor(unittest.TestCase):
    """O146(o133 以来 14 连零胜元诊断):农民下限 16 + 刹车家族窗口化。

    赢局时代退出时 13-15 叉+4 塔+15-20 农;现局 7-8 叉+3 塔+12 农 ——
    每个刹车省 50 矿换几秒防御时点,叠加 = 400s 收入腰斩。"""

    def test_probe_floor_needed(self):
        # t≤350 + 非急性窗 + 农民 <16 → 必产(绕过一切 yield/brake)
        self.assertTrue(probe_floor_needed(300.0, 12, False))
        self.assertTrue(probe_floor_needed(100.0, 11, False))
        # 急性窗(敌进家/threat 25s 内)→ 不强制(急性窗语义全保留)
        self.assertFalse(probe_floor_needed(300.0, 12, True))
        # 达标/超时 → 不强制
        self.assertFalse(probe_floor_needed(300.0, 16, False))
        self.assertFalse(probe_floor_needed(400.0, 12, False))

    def test_transition_probe_yield_windowed(self):
        # O146-②:非急性窗(慢性过渡态)不让位;急性窗保持 O97-C 语义
        self.assertFalse(transition_probe_yield(True, 14, 7, acute=False))
        self.assertTrue(transition_probe_yield(True, 14, 7, acute=True))
        self.assertTrue(transition_probe_yield(True, 14, 7))  # 缺省=旧行为
        self.assertFalse(transition_probe_yield(True, 13, 7, acute=True))
        self.assertFalse(transition_probe_yield(False, 20, 7, acute=True))

    def test_forge_first_probe_yield_windowed(self):
        # O146-②:竞速窗(≤200s)内保持 O111-③ 语义;窗后 latch 不得压农民
        self.assertTrue(forge_first_probe_yield(True, False, 11, now=150.0))
        self.assertFalse(forge_first_probe_yield(True, False, 11, now=250.0))
        self.assertTrue(forge_first_probe_yield(True, False, 11))  # 缺省 now=0 旧行为
        self.assertFalse(forge_first_probe_yield(True, True, 11, now=150.0))

    def test_critical_dispatch_exempt(self):
        # O147-①:首个 forge/塔/GW 豁免钉点守卫;第二座起/其余建筑不豁免
        self.assertTrue(critical_dispatch_exempt("FORGE", 0))
        self.assertTrue(critical_dispatch_exempt("PHOTONCANNON", 0))
        self.assertTrue(critical_dispatch_exempt("GATEWAY", 0))
        self.assertFalse(critical_dispatch_exempt("FORGE", 1))
        self.assertFalse(critical_dispatch_exempt("PHOTONCANNON", 2))
        self.assertFalse(critical_dispatch_exempt("PYLON", 0))
        self.assertFalse(critical_dispatch_exempt("STARGATE", 0))

    def test_hurt_retreat_needed(self):
        # O148-②:盾+血 <30% → 后拉;≥30% 不撤;满血不撤;0 上限防护除零
        self.assertTrue(hurt_retreat_needed(0.0, 40.0, 100.0, 100.0))
        self.assertFalse(hurt_retreat_needed(30.0, 30.0, 100.0, 100.0))
        self.assertFalse(hurt_retreat_needed(100.0, 100.0, 100.0, 100.0))
        self.assertFalse(hurt_retreat_needed(0.0, 0.0, 0.0, 0.0))


class TestO149ExpansionPush(unittest.TestCase):
    """O149(o133-o148 元诊断):二矿存活率=胜率 —— 定时强开/塔先落/双矿机动位。"""

    def test_transition_expand_at_210(self):
        # 过渡 + 见过波 + 家清 + t≥210 → 强开(不等清净窗/评分/优势)
        self.assertTrue(transition_expand_at_210(True, True, 0, 210.0))
        self.assertTrue(transition_expand_at_210(True, True, 0, 300.0))
        # 窗未到/未见波/敌在家/非过渡 → 不开
        self.assertFalse(transition_expand_at_210(True, True, 0, 209.0))
        self.assertFalse(transition_expand_at_210(True, False, 0, 300.0))
        self.assertFalse(transition_expand_at_210(True, True, 2, 300.0))
        self.assertFalse(transition_expand_at_210(False, True, 0, 300.0))

    def test_two_base_guard_point(self):
        # 双矿机动位 = 主基卡位点与分矿连线中点
        self.assertEqual(two_base_guard_point((10.0, 20.0), (30.0, 40.0)), (20.0, 30.0))
        self.assertEqual(two_base_guard_point((0.0, 0.0), (10.0, 10.0)), (5.0, 5.0))

    def test_main_defense_first(self):
        # O153-③修正:主基遇袭 ≥3 → 不接应分矿(先保主基);<3 才接应
        self.assertTrue(main_defense_first(3))
        self.assertTrue(main_defense_first(8))
        self.assertFalse(main_defense_first(2))
        self.assertFalse(main_defense_first(0))


class TestScoutNextStep(unittest.TestCase):
    """O36(司令观察,4人图 CactusValley 实证):多出生点逐点排查决策。"""

    def test_en_route_keeps_walking(self):
        self.assertEqual(
            scout_next_step(["A", "B"], arrived=False, intel_found=False), "stay"
        )

    def test_empty_waypoint_advances_to_next(self):
        self.assertEqual(
            scout_next_step(["A", "B", "C"], arrived=True, intel_found=False), "next"
        )

    def test_last_waypoint_empty_goes_home(self):
        self.assertEqual(
            scout_next_step(["C"], arrived=True, intel_found=False), "home"
        )

    def test_intel_found_goes_home_immediately(self):
        # 敌建筑入眼=敌人已定位,不必走到点位正中心
        self.assertEqual(
            scout_next_step(["A", "B"], arrived=False, intel_found=True), "home"
        )

    def test_empty_route_goes_home(self):
        self.assertEqual(scout_next_step([], arrived=False, intel_found=False), "home")


class TestNaturalPredefenseAllowed(unittest.TestCase):
    """O205:分矿 Nexus 落成前是否允许预铺 2 炮+1 电池。"""

    def test_started_always_allowed(self):
        self.assertTrue(natural_predefense_allowed(True, 0, 400))

    def test_not_started_requires_minerals(self):
        # 矿刚好够 Nexus + 350 + 25 → 允许
        self.assertTrue(natural_predefense_allowed(False, 775, 400))
        # 差 1 矿 → 不允许
        self.assertFalse(natural_predefense_allowed(False, 774, 400))

    def test_default_cost_and_buffer(self):
        self.assertTrue(natural_predefense_allowed(False, 400 + 350 + 25, 400))
        self.assertFalse(natural_predefense_allowed(False, 400 + 350 + 25 - 1, 400))

    def test_custom_defense_cost_and_buffer(self):
        self.assertTrue(
            natural_predefense_allowed(
                False, 400 + 200 + 50, 400, defense_cost=200, buffer=50
            )
        )
        self.assertFalse(
            natural_predefense_allowed(
                False, 400 + 200 + 50 - 1, 400, defense_cost=200, buffer=50
            )
        )


class TestFleetRecallTarget(unittest.TestCase):
    """O205:空军回防目标 —— 任一基地 radius 格内敌地面 ≥ min_threat。"""

    def test_no_threat(self):
        bases = [(10.0, 10.0)]
        enemies = [(50.0, 50.0)]
        self.assertIsNone(fleet_recall_target(bases, enemies))

    def test_threat_meets_threshold(self):
        # 6 个敌人在基地 15 格内 → 返回该基地
        bases = [(0.0, 0.0)]
        enemies = [(10.0, 0.0)] * 6
        self.assertEqual(fleet_recall_target(bases, enemies), (0.0, 0.0))

    def test_threshold_not_met(self):
        bases = [(0.0, 0.0)]
        enemies = [(10.0, 0.0)] * 5
        self.assertIsNone(fleet_recall_target(bases, enemies))

    def test_radius_boundary(self):
        bases = [(0.0, 0.0)]
        # 刚好在 radius=15 圆周上 (9,12) → 9^2+12^2=225=15^2
        enemies = [(9.0, 12.0)] * 6
        self.assertEqual(fleet_recall_target(bases, enemies), (0.0, 0.0))
        # 多出一点
        enemies = [(9.1, 12.0)] * 6
        self.assertIsNone(fleet_recall_target(bases, enemies))

    def test_returns_primary_base_first(self):
        # 主基受威胁、分矿也受威胁,返回第一个(主基)
        bases = [(0.0, 0.0), (100.0, 0.0)]
        enemies_main = [(10.0, 0.0)] * 6
        enemies_natural = [(110.0, 0.0)] * 6
        self.assertEqual(
            fleet_recall_target(bases, enemies_main + enemies_natural), (0.0, 0.0)
        )

    def test_natural_only(self):
        bases = [(0.0, 0.0), (100.0, 0.0)]
        enemies = [(110.0, 0.0)] * 6
        self.assertEqual(fleet_recall_target(bases, enemies), (100.0, 0.0))

    def test_custom_min_threat(self):
        bases = [(0.0, 0.0)]
        enemies = [(5.0, 0.0)] * 3
        self.assertEqual(fleet_recall_target(bases, enemies, min_threat=3), (0.0, 0.0))
        self.assertIsNone(fleet_recall_target(bases, enemies, min_threat=4))

    def test_custom_radius(self):
        bases = [(0.0, 0.0)]
        enemies = [(20.0, 0.0)] * 6
        self.assertIsNone(fleet_recall_target(bases, enemies, radius=15.0))
        self.assertEqual(
            fleet_recall_target(bases, enemies, radius=25.0), (0.0, 0.0)
        )


class TestRushDeadzoneActive(unittest.TestCase):
    """O205:舰队成型后硬解 rush_active 后 60s 死区。"""

    def test_no_hard_clear(self):
        self.assertFalse(rush_deadzone_active(None, 100.0))

    def test_inside_deadzone(self):
        self.assertTrue(rush_deadzone_active(100.0, 100.0))
        self.assertTrue(rush_deadzone_active(100.0, 159.9))

    def test_at_boundary(self):
        # <60s 死区;>=60s 失效
        self.assertTrue(rush_deadzone_active(100.0, 159.9999))
        self.assertFalse(rush_deadzone_active(100.0, 160.0))

    def test_after_deadzone(self):
        self.assertFalse(rush_deadzone_active(100.0, 160.1))
        self.assertFalse(rush_deadzone_active(100.0, 200.0))

    def test_custom_deadzone(self):
        self.assertTrue(rush_deadzone_active(0.0, 30.0, deadzone=60.0))
        self.assertFalse(rush_deadzone_active(0.0, 60.1, deadzone=60.0))


class TestIdleBuilderFuseExempt(unittest.TestCase):
    """O205:idle_builder 5s 熔断豁免名单。"""

    def test_critical_ids_exempt(self):
        for sid in ("FORGE", "PHOTONCANNON", "GATEWAY", "NEXUS", "FLEETBEACON"):
            self.assertTrue(idle_builder_fuse_exempt(sid), sid)

    def test_non_critical_not_exempt(self):
        for sid in ("PYLON", "STARGATE", "ASSIMILATOR", "CYBERNETICSCORE", "ROBOTICSFACILITY"):
            self.assertFalse(idle_builder_fuse_exempt(sid), sid)

    def test_custom_critical_ids(self):
        self.assertTrue(
            idle_builder_fuse_exempt("PYLON", critical_ids={"PYLON"})
        )
        self.assertFalse(
            idle_builder_fuse_exempt("FORGE", critical_ids={"PYLON"})
        )


class TestO327Economy(unittest.TestCase):
    """O327(o326 双 lane 尸检 + 司令观察):经济专项四判据。

    o326 败局链:二矿 518-647s(胜线 ≤310s)、三矿永不开(农民峰值
    22-28 等不到 40 门槛)、早窗气烂 472-876 而矿 <200、母舰 811s
    300/300 压垮 2 基地经济、SG2 与 Nexus 同资金窗互挤。"""

    def test_early_gas_overflow_pull(self):
        # 窗内 + FB 未就绪 + 气 ≥400 且矿 ≤250 → 抽矿(o326a 225-338s 常态)
        self.assertTrue(early_gas_overflow_pull(280.0, 700.0, 115.0, False))
        # FB 就绪(舰队开始吃气)→ 不抽
        self.assertFalse(early_gas_overflow_pull(280.0, 700.0, 115.0, True))
        # 出窗(太早/太晚)→ 不抽
        self.assertFalse(early_gas_overflow_pull(100.0, 700.0, 115.0, False))
        self.assertFalse(early_gas_overflow_pull(500.0, 700.0, 115.0, False))
        # 气/矿阈值边界
        self.assertFalse(early_gas_overflow_pull(280.0, 399.0, 115.0, False))
        self.assertFalse(early_gas_overflow_pull(280.0, 700.0, 251.0, False))
        self.assertTrue(early_gas_overflow_pull(150.0, 400.0, 250.0, False))
        self.assertTrue(early_gas_overflow_pull(420.0, 400.0, 250.0, False))

    def test_expand_pin_workers_ok(self):
        # 旧门槛:16×基地+8 仍放行(1 基 24 / 2 基 40,行为不变)
        self.assertTrue(expand_pin_workers_ok(24, 1, 300.0))
        self.assertTrue(expand_pin_workers_ok(40, 2, 300.0))
        # 1 基地不到 24 → 拦(O311-③ 证伪区不复试)
        self.assertFalse(expand_pin_workers_ok(23, 1, 700.0))
        # O327-②:2+ 基地放宽 —— ≥26 农即钉;t≥600 时间兜底
        self.assertTrue(expand_pin_workers_ok(26, 2, 300.0))
        self.assertFalse(expand_pin_workers_ok(25, 2, 300.0))
        self.assertTrue(expand_pin_workers_ok(20, 2, 600.0))
        self.assertFalse(expand_pin_workers_ok(20, 2, 599.0))
        # 3 基地同样适用放宽
        self.assertTrue(expand_pin_workers_ok(26, 3, 300.0))

    def test_mothership_economy_ok(self):
        # 3 基地运转 → 放行
        self.assertTrue(mothership_economy_ok(3, 20))
        # 2 基地需 ≥36 农(o326a:22-28 农出母舰 = 净负)
        self.assertFalse(mothership_economy_ok(2, 35))
        self.assertTrue(mothership_economy_ok(2, 36))
        # 单基地未达到 36 农 → 拦
        self.assertFalse(mothership_economy_ok(1, 30))

    def test_sg2_pin_economy_ok(self):
        # 2 基地运转(含在建)→ 放行(黄金窗收益不变)
        self.assertTrue(sg2_pin_economy_ok(2, 100.0))
        # O333-④:单基地一律拦 —— 矿 ≥550 替代项已去掉(等钱期矿过
        # 550 是常态,SG2 在 346s 插队抢等钱中的 Nexus,o332b game_04)
        self.assertFalse(sg2_pin_economy_ok(1, 600.0))
        self.assertFalse(sg2_pin_economy_ok(1, 100.0))


class TestO359WaveDefense(unittest.TestCase):
    """O359-③/⑤(o358 六局尸检):波前 ≥2 塔 + 塔等钱期 150 矿预算保护。

    o358 实证:305-309s 致死波单塔守不住(o358b g1 塔 257s 落成照样穿);
    O358-⑤ 的 550 门只在钉点帧生效,o358a g1 塔链 234s 派工→342s 落成
    (探机/水晶抽干等钱窗)。"""

    def test_zt_second_cannon_pin_ok(self):
        # 首波窗(t<330)+ 首塔落成(就绪 ≥1)+ 总数 <2 → 钉第二塔
        self.assertTrue(zt_second_cannon_pin_ok(250.0, 1, 1))
        self.assertTrue(zt_second_cannon_pin_ok(299.9, 1, 1))
        # 首塔未落成 → 不钉(塔链时序:首塔先行)
        self.assertFalse(zt_second_cannon_pin_ok(250.0, 0, 1))
        self.assertFalse(zt_second_cannon_pin_ok(250.0, 0, 0))
        # 总数(实体+在途)≥2 → 自停(o358a g3 二塔 189s 局不重复钉)
        self.assertFalse(zt_second_cannon_pin_ok(250.0, 1, 2))
        self.assertFalse(zt_second_cannon_pin_ok(250.0, 2, 2))
        # 出窗(t≥330,首波已到)→ 不钉(塔链命运已定,资金回正链)
        self.assertFalse(zt_second_cannon_pin_ok(330.0, 1, 1))
        self.assertFalse(zt_second_cannon_pin_ok(400.0, 1, 1))

    def test_zt_cannon_pending_probe_yield(self):
        # 首波窗内有塔在 tracker 等钱 + 农民 ≥20 → 探机让位
        self.assertTrue(zt_cannon_pending_probe_yield(250.0, 1, 27))
        self.assertTrue(zt_cannon_pending_probe_yield(329.9, 2, 20))
        # 无塔等钱 → 不让位(自校正:塔放置 pending 归零即恢复)
        self.assertFalse(zt_cannon_pending_probe_yield(250.0, 0, 27))
        # 出窗 → 不让位(探机恢复,经济回血)
        self.assertFalse(zt_cannon_pending_probe_yield(330.0, 1, 27))
        # 农民 <20 → 不让位(O360-⑤:16 线冻死扩张期经济,o359a g1 实证)
        self.assertFalse(zt_cannon_pending_probe_yield(250.0, 1, 19))
        self.assertFalse(zt_cannon_pending_probe_yield(250.0, 1, 16))
        # O360-⑤:Nexus 在途/开工中 → 豁免(扩张期经济优先于塔的 150 短窗)
        self.assertFalse(zt_cannon_pending_probe_yield(250.0, 1, 27, nexus_in_flight=1))
        self.assertTrue(zt_cannon_pending_probe_yield(250.0, 1, 27, nexus_in_flight=0))


class TestO329FastExpand(unittest.TestCase):
    """O329(司令 2026-08-18 拍板):速二矿钉点 + 防御重心迁 2 矿。

    电脑 Zerg 二矿 119-150s(录像实测),我方 377-500s 是经济差起点;
    防御塔+电池聚在一起才有效,主基分散铺塔 = 2 矿裸奔被一波推。"""

    def test_zt_fast_expand_pin(self):
        # t≥100 + 矿≥475(造价400+走位窗buffer75,O343-①)+ 单基地
        # + 无在途 + 非 rush → 钉
        self.assertTrue(zt_fast_expand_pin(120.0, 475.0, 1, 0, False))
        # 时间/矿门槛(350 门已证伪:走位窗 opener 流水 ~800,到位必穷)
        self.assertFalse(zt_fast_expand_pin(99.0, 475.0, 1, 0, False))
        self.assertFalse(zt_fast_expand_pin(120.0, 474.0, 1, 0, False))
        self.assertFalse(zt_fast_expand_pin(120.0, 350.0, 1, 0, False))
        # rush 确认 = fuse 弃权(走旧防御先行路径)
        self.assertFalse(zt_fast_expand_pin(120.0, 500.0, 1, 0, True))
        # 已有在途/已多基地不重拍
        self.assertFalse(zt_fast_expand_pin(120.0, 500.0, 1, 1, False))
        self.assertFalse(zt_fast_expand_pin(120.0, 500.0, 2, 0, False))
        # O358-⑤(o357 尸检):首塔未落成且 t<330 → 矿门抬到 550
        # (400 Nexus + 给首塔留 150;o357 首塔 281-365s 被 233-237s
        # 二矿挤占实证)
        self.assertFalse(
            zt_fast_expand_pin(200.0, 475.0, 1, 0, False, first_cannon_ready=False)
        )
        self.assertFalse(
            zt_fast_expand_pin(200.0, 549.9, 1, 0, False, first_cannon_ready=False)
        )
        self.assertTrue(
            zt_fast_expand_pin(200.0, 550.0, 1, 0, False, first_cannon_ready=False)
        )
        # 首塔已落成 → 原 475 门(塔链资金已有着落,不拖二矿)
        self.assertTrue(
            zt_fast_expand_pin(200.0, 475.0, 1, 0, False, first_cannon_ready=True)
        )
        # 出窗(t≥330,首波已到) → 原 475 门(塔链命运已定,不再压二矿)
        self.assertTrue(
            zt_fast_expand_pin(330.0, 475.0, 1, 0, False, first_cannon_ready=False)
        )

    def test_sg_pin_expand_ok(self):
        # O363-③:t≥240 后连环门豁免(SG 与扩张并行预算)
        self.assertTrue(sg_pin_expand_ok(2, 0, 300.0))
        self.assertTrue(sg_pin_expand_ok(1, 1, 300.0))
        self.assertTrue(sg_pin_expand_ok(1, 0, 342.0))
        self.assertTrue(sg_pin_expand_ok(1, 0, 360.0))
        # t=250 单基地放行(o362a g3:SG 钉点 401s 等 Nexus 同 tick 才过)
        self.assertTrue(sg_pin_expand_ok(1, 0, 250.0))
        self.assertTrue(sg_pin_expand_ok(1, 0, 240.0))
        # t=200 仍守旧闸:单基地无在途 → 拦(360 硬时限未到)
        self.assertFalse(sg_pin_expand_ok(1, 0, 200.0))
        self.assertFalse(sg_pin_expand_ok(1, 1, 200.0))
        # t<240 时 2 基地(含在建)放行不变
        self.assertTrue(sg_pin_expand_ok(2, 0, 200.0))

    def test_zt_zealot_yield(self):
        # 二矿开工前(单基地)+非 rush +非威胁 → 零兵种(司令 doctrine)
        self.assertTrue(zt_zealot_yield(1, False))
        self.assertTrue(zt_zealot_yield(1, False, False))
        # Nexus 开工(含在建,townhalls≥2)→ 恢复产叉
        self.assertFalse(zt_zealot_yield(2, False))
        # rush 确认 → 恢复(rush 响应包要叉)
        self.assertFalse(zt_zealot_yield(1, True))
        # O333-③:threat 激活豁免 —— 钉点晚局波到脸零叉零塔 = 359s 速败
        self.assertFalse(zt_zealot_yield(1, False, True))
        # O339-②:波预警豁免 —— threat 触发时敌已到门口(296s 敌11 vs
        # 我2),才产叉 330s 接战晚 30s;预警(40-60s 提前量)即恢复
        self.assertFalse(zt_zealot_yield(1, False, False, True))
        # 无预警无威胁且二矿未开工 → 仍零兵种
        self.assertTrue(zt_zealot_yield(1, False, False, False))
        # 无预警无威胁但 t<240 → 仍零兵种
        self.assertTrue(zt_zealot_yield(1, False, False, False, now=200.0))
        # O340-②:t≥240 时间硬线 —— 侦查早死局预警不 latch,
        # threat 接触(275s 敌12 vs 我1)才产叉 = 裸接;波必来是规律
        self.assertFalse(zt_zealot_yield(1, False, False, False, now=240.0))

    def test_main_defense_bank_fuse(self):
        # 矿 ≥600 且 Nexus 未开工 → 熔断开(主基塔放行,o333a game_03
        # 银行 1315 主基零塔实证)
        self.assertTrue(main_defense_bank_fuse(600.0, False, False))
        # 滞回:熔断开后矿降到 450 仍开,<400 复位
        self.assertTrue(main_defense_bank_fuse(450.0, False, True))
        self.assertFalse(main_defense_bank_fuse(399.0, False, True))
        # Nexus 一开工立即复位(回 doctrine)
        self.assertFalse(main_defense_bank_fuse(800.0, True, True))
        # 未达阈值且未开过 → 关
        self.assertFalse(main_defense_bank_fuse(500.0, False, False))

    def test_holding_abort_keep_first_expand(self):
        # ZT 首扩(townhalls==1)→ 只解锁不撤销(o335a game_02:
        # 281/457s 二连撤销 → 落成 578s vs 胜局 212-233s)
        self.assertTrue(holding_abort_keep_first_expand(True, 1))
        # ZT 3 矿+(townhalls≥2)→ 原语义(撤销)
        self.assertFalse(holding_abort_keep_first_expand(True, 2))
        # 非 ZT → 原语义
        self.assertFalse(holding_abort_keep_first_expand(False, 1))

    def test_zt_defense_at_natural(self):
        # Nexus 在途或分矿存在 → 防御重心在 2 矿(主基塔归零)
        self.assertTrue(zt_defense_at_natural(1, False, False))
        self.assertTrue(zt_defense_at_natural(0, True, False))
        # 分矿全丢(无在途无落成)→ 回退主基防御
        self.assertFalse(zt_defense_at_natural(0, False, False))
        # rush 激活一律回退(O81 rush 教义:主基先保)
        self.assertFalse(zt_defense_at_natural(1, True, True))


class TestO352Unlocks(unittest.TestCase):
    """O352(o351 18 局尸检):航母产出解锁 / 三矿解锁 / forge 钉点近可负担门。"""

    def test_multi_expand_threat_ok(self):
        # O344-② 原语义:rush∧threat 同真 → 锁三矿(t<600 且敌强)
        self.assertFalse(multi_expand_threat_ok(
            True, True, 2, 300.0,
            visible_enemy_army_supply=30.0, own_army_supply=10.0,
        ))
        # O352-② 旁路(a):时间兜底,同参数翻 True(O353-④ 从 t≥600 降到 t≥480)
        self.assertTrue(multi_expand_threat_ok(
            True, True, 2, 481.0,
            visible_enemy_army_supply=30.0, own_army_supply=10.0,
        ))
        self.assertTrue(multi_expand_threat_ok(
            True, True, 3, 480.0,
            visible_enemy_army_supply=30.0, own_army_supply=10.0,
        ))
        # O353-④ 边界:479s 仍锁
        self.assertFalse(multi_expand_threat_ok(
            True, True, 2, 479.0,
            visible_enemy_army_supply=30.0, own_army_supply=10.0,
        ))
        # O352-② 旁路(b):闸内放宽解除口径 max(8, 我方×1.25)
        # 敌可见 9 < max(8, 8×1.25=10) → 视为威胁已退,放行
        self.assertTrue(multi_expand_threat_ok(
            True, True, 2, 300.0,
            visible_enemy_army_supply=9.0, own_army_supply=8.0,
        ))
        # 敌可见 11 ≥ 10 → 仍锁
        self.assertFalse(multi_expand_threat_ok(
            True, True, 2, 300.0,
            visible_enemy_army_supply=11.0, own_army_supply=8.0,
        ))
        # 绝对下限 8:我方 0 时敌可见 7 放行、9 锁
        self.assertTrue(multi_expand_threat_ok(
            True, True, 2, 300.0,
            visible_enemy_army_supply=7.0, own_army_supply=0.0,
        ))
        self.assertFalse(multi_expand_threat_ok(
            True, True, 2, 300.0,
            visible_enemy_army_supply=9.0, own_army_supply=0.0,
        ))
        # 原语义保留:非 rush 或非 threat → 放行;首扩恒放行
        self.assertTrue(multi_expand_threat_ok(
            False, True, 2, 300.0,
            visible_enemy_army_supply=30.0, own_army_supply=10.0,
        ))
        self.assertTrue(multi_expand_threat_ok(
            True, False, 2, 300.0,
            visible_enemy_army_supply=30.0, own_army_supply=10.0,
        ))
        self.assertTrue(multi_expand_threat_ok(
            True, True, 1, 300.0,
            visible_enemy_army_supply=30.0, own_army_supply=10.0,
        ))

    def test_fb_missing_expand_hold(self):
        # 原语义:townhalls≥2 且 FB 真缺失 → 锁
        self.assertTrue(fb_missing_expand_hold(2, True, 20, 300.0))
        # O353-④ 豁免:农 ≥28 不锁(原 O352-② 的 40 不可达)
        self.assertFalse(fb_missing_expand_hold(2, True, 28, 300.0))
        self.assertFalse(fb_missing_expand_hold(3, True, 30, 300.0))
        # O353-④ 豁免:t≥480 不锁(原 O352-② 的 600 触发时局已崩)
        self.assertFalse(fb_missing_expand_hold(2, True, 20, 480.0))
        self.assertFalse(fb_missing_expand_hold(2, True, 20, 481.0))
        # 边界:27 农 + 479s 仍锁
        self.assertTrue(fb_missing_expand_hold(2, True, 27, 479.0))
        # FB 在场/单基地 → 不锁(原语义不变)
        self.assertFalse(fb_missing_expand_hold(2, False, 30, 300.0))
        self.assertFalse(fb_missing_expand_hold(1, True, 30, 300.0))

    def test_forge_pin_affordable(self):
        # O352-③:矿 <门 不派工/不驻点/不设 tracker;≥门 才钉
        # O354-⑤(o353b game_01 实证):非威胁期门 150→100(矿 50-95 窗
        # 150 门恒关,forge 拖到 361.6s)
        self.assertFalse(forge_pin_affordable(50.0))
        self.assertFalse(forge_pin_affordable(99.0))
        self.assertTrue(forge_pin_affordable(100.0))
        self.assertTrue(forge_pin_affordable(150.0))
        self.assertTrue(forge_pin_affordable(300.0))
        # 自定义造价口径
        self.assertFalse(forge_pin_affordable(100.0, price=120.0))
        self.assertTrue(forge_pin_affordable(120.0, price=120.0))

    def test_forge_pin_affordable_threat_exempt(self):
        # O353-①:威胁期(threat/rush 激活)免门 —— 矿 <门 也钉(救命建筑,
        # 驻点等钱是对的);非威胁期保持矿门(O354-⑤:150→100)
        self.assertTrue(forge_pin_affordable(100.0, threat_active=True))
        self.assertTrue(forge_pin_affordable(0.0, threat_active=True))
        self.assertFalse(forge_pin_affordable(99.0, threat_active=False))
        self.assertTrue(forge_pin_affordable(100.0, threat_active=False))


class TestO353SprintFloorFb(unittest.TestCase):
    """O353(o352 六局尸检):sprint 累计制 / 两矿农民 floor / FB 攒钱窗。"""

    def test_sprint_timer_jitter_keeps_age(self):
        # O353-②:单帧抖动不清零 —— 冲刺中断 <10s,age 照累计(起点不动)
        since, fs = sprint_timer_update(True, None, None, 200.0)
        self.assertEqual(since, 200.0)
        self.assertIsNone(fs)
        # 抖动 3 帧(各 1s)不满足 → 计时保留,false_since 从首次中断起算
        since, fs = sprint_timer_update(False, since, fs, 210.0)
        self.assertEqual(since, 200.0)
        self.assertEqual(fs, 210.0)
        since, fs = sprint_timer_update(True, since, fs, 211.0)
        self.assertEqual(since, 200.0)  # 恢复冲刺,false_since 清零
        self.assertIsNone(fs)
        since, fs = sprint_timer_update(False, since, fs, 212.0)
        self.assertEqual(since, 200.0)

    def test_sprint_timer_grace_exit(self):
        # O353-②:连续 exit_grace(10s)不满足才清零(真退出);清零后可重新冲刺
        since, fs = sprint_timer_update(True, None, None, 200.0)
        since, fs = sprint_timer_update(False, since, fs, 250.0)
        since, fs = sprint_timer_update(False, since, fs, 259.9)
        self.assertEqual(since, 200.0)  # 未满 10s,仍保留
        since, fs = sprint_timer_update(False, since, fs, 260.0)
        self.assertIsNone(since)  # 满 10s → 清零
        self.assertIsNone(fs)
        since, fs = sprint_timer_update(True, since, fs, 300.0)
        self.assertEqual(since, 300.0)  # 清零后重新冲刺从 300 起计

    def test_sprint_escape_valve_60s(self):
        # O353-②:ZT max_age=60s —— 累计 age>60 强制退出(农民恢复生产)
        base = dict(
            has_transition=True, defense_urgent=True, forge_ready=False,
            first_cannon_ready=False, first_zealot_seen=False, enemy_home=0,
            max_age=60.0,
        )
        self.assertTrue(defense_sprint_active(**base, sprint_age=59.0))
        self.assertFalse(defense_sprint_active(**base, sprint_age=61.0))

    def test_probe_floor_cap(self):
        # O353-②:ZT 两矿 floor=28;一矿保持 16;非 ZT 恒 16
        self.assertEqual(probe_floor_cap(True, 2), 28)
        self.assertEqual(probe_floor_cap(True, 3), 28)
        self.assertEqual(probe_floor_cap(True, 1), 16)
        self.assertEqual(probe_floor_cap(False, 2), 16)

    def test_fb_saving_window(self):
        # O353-③:SG 就绪 + FB 无实体未派工 → 攒钱窗(虚空兜底禁用);
        # FB 已派工/在场或无就绪 SG → 不在窗
        self.assertTrue(fb_saving_window(True, False))
        self.assertFalse(fb_saving_window(True, True))
        self.assertFalse(fb_saving_window(False, False))
        self.assertFalse(fb_saving_window(False, True))


class TestO354CarrierMothershipWindow(unittest.TestCase):
    """O354(o353 五局尸检):航母破零优先 / 母舰资金窗 / 静态防御封顶。"""

    def test_tempest_dump_suppressed(self):
        # O354-①:FB 就绪 + 气 ≥500 + 航母(含在产)<2 + 暴风 <4 → 抑制
        self.assertTrue(tempest_dump_suppressed(0, 2, True, 500.0))
        self.assertTrue(tempest_dump_suppressed(1, 3, True, 886.0))
        # 航母 ≥2 → 恢复
        self.assertFalse(tempest_dump_suppressed(2, 0, True, 886.0))
        # 暴风 ≥4 → 恢复
        self.assertFalse(tempest_dump_suppressed(0, 4, True, 886.0))
        # FB 未就绪 / 气不够 → 不抑制(本就不在 O260 门内)
        self.assertFalse(tempest_dump_suppressed(0, 0, False, 886.0))
        self.assertFalse(tempest_dump_suppressed(0, 0, True, 499.0))

    def test_mothership_window_open(self):
        # O354-②:除 can_afford 外全满足 + 矿 <400 → 开窗
        # O358-③:开窗还要矿 ≥300(窗=「攒够了才开」的 300-400
        # 冲刺窗;<300 空窗压塔实证 o357a g3)
        base = dict(
            fb_ready=True, now=800.0, fleet_count=3, vespene=700.0,
            bases=3, workers=40, motherships=0,
        )
        self.assertTrue(mothership_window_open(**base, minerals=399.0))
        self.assertTrue(mothership_window_open(**base, minerals=300.0))
        # O358-③ 矿边界:299.9 不开(空窗不抑制防御链),300 开
        self.assertFalse(mothership_window_open(**base, minerals=299.9))
        self.assertFalse(mothership_window_open(**base, minerals=100.0))
        # 矿 ≥400 → 关窗(can_afford 达成,母舰直接点)
        self.assertFalse(mothership_window_open(**base, minerals=400.0))
        # 已有母舰(含在产)→ 关窗
        self.assertFalse(
            mothership_window_open(
                **{**base, "motherships": 1}, minerals=350.0
            )
        )
        # 各门槛缺一不开窗
        self.assertFalse(
            mothership_window_open(**{**base, "fb_ready": False}, minerals=350.0)
        )
        self.assertFalse(
            mothership_window_open(**{**base, "now": 699.9}, minerals=350.0)
        )
        self.assertFalse(
            mothership_window_open(**{**base, "fleet_count": 2}, minerals=350.0)
        )
        # O355-①:气门 600→400(与 O260 的 500 泄气闸死锁,o354 母舰 0/9)
        self.assertFalse(
            mothership_window_open(**{**base, "vespene": 399.0}, minerals=350.0)
        )
        self.assertTrue(
            mothership_window_open(**{**base, "vespene": 400.0}, minerals=350.0)
        )
        # 经济门(3 基地或 ≥36 农):2 基地 30 农不开,2 基地 36 农开
        self.assertFalse(
            mothership_window_open(
                **{**base, "bases": 2, "workers": 30}, minerals=350.0
            )
        )
        self.assertTrue(
            mothership_window_open(
                **{**base, "bases": 2, "workers": 36}, minerals=350.0
            )
        )
        # O359-④(o358 尸检):奢侈品档传 min_minerals=0(无矿底)——
        # 矿 <300 也开窗(O260/O239/探机抑制本身就是攒钱手段;
        # o358b g2 矿峰值 250 恒 <300,300 矿底 = 窗永不开死锁);
        # 防御档保持默认 300 矿底不变(上面 299.9/300 边界即防御档)
        self.assertTrue(
            mothership_window_open(**base, minerals=100.0, min_minerals=0.0)
        )
        self.assertTrue(
            mothership_window_open(**base, minerals=0.0, min_minerals=0.0)
        )
        # 无矿底档仍守其余门槛 + 矿 ≥400 关窗
        self.assertFalse(
            mothership_window_open(**base, minerals=400.0, min_minerals=0.0)
        )
        self.assertFalse(
            mothership_window_open(
                **{**base, "vespene": 399.0}, minerals=100.0, min_minerals=0.0
            )
        )

    def test_cannon_capped(self):
        # O354-④ 四象限:t≥600 且舰队 ≥4 且塔 ≥8 才封顶;威胁豁免
        self.assertTrue(cannon_capped(700.0, 4, 8, False))
        self.assertTrue(cannon_capped(700.0, 6, 13, False))
        # 塔 <8 → 不封
        self.assertFalse(cannon_capped(700.0, 4, 7, False))
        # 舰队 <4 → 不封
        self.assertFalse(cannon_capped(700.0, 3, 8, False))
        # t <600 → 不封
        self.assertFalse(cannon_capped(599.9, 4, 8, False))
        # rush/threat 激活 → 豁免(被骑脸该补还得补)
        self.assertFalse(cannon_capped(700.0, 4, 8, True))


class TestO355MothershipWindowForgeRescue(unittest.TestCase):
    """O355(o354 六局尸检):母舰气阈对齐+窗内探机让位 / forge 自救水晶锚点升级。"""

    def test_ms_window_probe_yield(self):
        # O355-①:窗开且农民 ≥28 → 探机让位(与 O225 同口径)
        self.assertTrue(ms_window_probe_yield(True, 28))
        self.assertTrue(ms_window_probe_yield(True, 44))
        # 农民 <28 → 照产(经济不能掐尖)
        self.assertFalse(ms_window_probe_yield(True, 27))
        self.assertFalse(ms_window_probe_yield(True, 18))
        # 窗关(矿 ≥400/条件失效)→ 照产
        self.assertFalse(ms_window_probe_yield(False, 40))

    def test_rescue_pylon_anchor(self):
        # O356-①a(o355 尸检):min_fails 2→1 首发即自救 —— 首次
        # no_placement 立刻对准空闲槽(等第二次失败 = 92-112s 救援
        # 延迟 vs 274s 致死波,死刑);fails=0 仍 None(未失败不触发)
        slots = [(10.0, 10.0), (20.0, 20.0), (30.0, 10.0)]
        self.assertIsNone(rescue_pylon_anchor(slots, (0.0, 0.0), 0))
        # 第 1 次起 → 离基地最近的空闲 3x3 槽
        self.assertEqual(
            rescue_pylon_anchor(slots, (0.0, 0.0), 1), (10.0, 10.0)
        )
        self.assertEqual(
            rescue_pylon_anchor(slots, (0.0, 0.0), 2), (10.0, 10.0)
        )
        self.assertEqual(
            rescue_pylon_anchor(slots, (25.0, 25.0), 3), (20.0, 20.0)
        )
        # 显式 min_fails=2 保留旧边界语义
        self.assertIsNone(rescue_pylon_anchor(slots, (0.0, 0.0), 1, min_fails=2))
        # 无空闲槽 → None(调用方保持原锚点)
        self.assertIsNone(rescue_pylon_anchor([], (0.0, 0.0), 5))


class TestO356MothershipWindowCannonRescue(unittest.TestCase):
    """O356(o355 尸检):首塔钉点第二根自救水晶 / 死等自救 / 母舰资金窗收口。"""

    def test_second_rescue_pylon_needed(self):
        # O356-①b:无首塔钉点 / 钉点已带电 → 不补
        self.assertFalse(second_rescue_pylon_needed(None, False, (10.0, 10.0)))
        self.assertFalse(second_rescue_pylon_needed((30.0, 10.0), True, (10.0, 10.0)))
        # 钉点不带电 + 无自救锚点 → 补
        self.assertTrue(second_rescue_pylon_needed((30.0, 10.0), False, None))
        # 钉点不带电 + 自救锚点在电力半径内(落地即覆盖)→ 不补
        self.assertFalse(second_rescue_pylon_needed((30.0, 10.0), False, (32.0, 12.0)))
        # 钉点不带电 + 自救锚点在电力半径外(o355b g3:锚的 3x3 槽
        # 没覆盖首塔 2x2 钉点)→ 补第二根
        self.assertTrue(second_rescue_pylon_needed((30.0, 10.0), False, (10.0, 10.0)))
        # 边界:距离恰 = power_radius → 不补(<= 视为可覆盖)
        self.assertFalse(
            second_rescue_pylon_needed((16.0, 10.0), False, (10.0, 10.0))
        )
        self.assertTrue(
            second_rescue_pylon_needed((16.1, 10.0), False, (10.0, 10.0))
        )

    def test_cannon_stall_rescue(self):
        # O356-①c:forge 就绪 + 连续失败 ≥30s → 无视在途门补钉
        self.assertTrue(cannon_stall_rescue(30.0, True))
        self.assertTrue(cannon_stall_rescue(61.5, True))
        # 失败时长不足 → 不补(等 O296-③ 常规自救)
        self.assertFalse(cannon_stall_rescue(29.9, True))
        # forge 未就绪 → 不补(首塔 tech_not_ready 是正常等待)
        self.assertFalse(cannon_stall_rescue(90.0, False))

    def test_ms_window_fleet_suppressed(self):
        # O356-②b:窗开 + 舰队(含在产)≥6 → 星门新单让位
        self.assertTrue(ms_window_fleet_suppressed(True, 6))
        self.assertTrue(ms_window_fleet_suppressed(True, 13))
        # 舰队 <6 → 不动(窗内舰队太弱还得造)
        self.assertFalse(ms_window_fleet_suppressed(True, 5))
        self.assertFalse(ms_window_fleet_suppressed(True, 0))
        # 窗关 → 产线照跑(自校正无 latch)
        self.assertFalse(ms_window_fleet_suppressed(False, 13))

    def test_mothership_supply_ok(self):
        # O356-②d:母舰 8 人口 + 2 余量 = 10;o355b g1 终局 199/200
        # (supply_left=1)卡死场景
        self.assertTrue(mothership_supply_ok(10.0))
        self.assertTrue(mothership_supply_ok(14.0))
        self.assertFalse(mothership_supply_ok(9.9))
        self.assertFalse(mothership_supply_ok(1.0))
        self.assertFalse(mothership_supply_ok(0.0))


class TestO357ReanchorForgeFirstObservability(unittest.TestCase):
    """O357(o356 尸检):死槽拉黑换锚 / 母舰块前移 / ZT forge-first 门 / 事件节流。"""

    def test_pin_reanchor(self):
        # O357-①:带电优先 —— 带电槽再远也先于不带电槽(o356 右下
        # 死槽 (0,23,25):空闲 23 但带电 0,只挑空闲会重现死槽)
        slots = [(5.0, 0.0, True, False), (50.0, 0.0, True, True)]
        self.assertEqual(pin_reanchor(slots, (0.0, 0.0), []), (50.0, 0.0))
        # 同带电性 → 离致死波入口(斜坡口)更近优先
        slots2 = [(30.0, 0.0, True, True), (10.0, 0.0, True, True)]
        self.assertEqual(pin_reanchor(slots2, (0.0, 0.0), []), (10.0, 0.0))
        # 拉黑(取整坐标)后换下一锚 —— 再失败不回头重试死点
        self.assertEqual(
            pin_reanchor(slots2, (0.0, 0.0), [(10, 0)]), (30.0, 0.0)
        )
        # 占用槽不参与;全占/全黑/无槽 → None(调用方保持原锚点)
        self.assertIsNone(pin_reanchor([(10.0, 0.0, False, True)], (0.0, 0.0), []))
        self.assertIsNone(pin_reanchor(slots2, (0.0, 0.0), [(10, 0), (30, 0)]))
        self.assertIsNone(pin_reanchor([], (0.0, 0.0), []))

    def test_reanchor_bases(self):
        # O358-④a:锚池含分基 —— 主基恒在首位,分基/副基槽表入池
        bases = reanchor_bases((30.0, 116.0), [(120.0, 40.0), (80.0, 90.0)])
        self.assertEqual(bases[0], (30.0, 116.0))
        self.assertIn((120.0, 40.0), bases)
        self.assertIn((80.0, 90.0), bases)
        self.assertEqual(len(bases), 3)
        # 主基 Nexus 与 start_location 取整同点 → 去重不重复入池
        self.assertEqual(
            reanchor_bases((30.0, 116.0), [(30.4, 116.2)]),
            [(30.0, 116.0)],
        )
        # 无分基 → 只回主基(单矿局逐位同旧行为)
        self.assertEqual(reanchor_bases((30.0, 116.0), []), [(30.0, 116.0)])

    def test_reanchor_cooldown_until(self):
        # O358-④b:冷却闸 —— 拉黑 <3 不冷却(照常住换锚)
        self.assertIsNone(reanchor_cooldown_until(0, 330.0))
        self.assertIsNone(reanchor_cooldown_until(2, 330.0))
        # 拉黑 ≥3 仍 no_placement → 冷却 60s(o357a g1 黑1→黑5
        # 仍 no_placement、每 30s 空转刷屏实证)
        self.assertEqual(reanchor_cooldown_until(3, 330.0), 390.0)
        self.assertEqual(reanchor_cooldown_until(5, 958.6), 1018.6)

    def test_mothership_block_before_carrier(self):
        # O357-②:O264 母舰块必须在 O239 航母块之前执行(o356b g2
        # 两次同帧截胡实证);源码顺序回归锁,防后续改动悄悄挪回。
        path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "bot", "managers", "production_manager.py",
        )
        with open(path, encoding="utf-8") as f:
            src = f.read()
        ms_pos = src.index("_ms_order_ready = (")
        carrier_pos = src.index('"msg": f"O239:气烂银行点航母')
        self.assertLess(
            ms_pos, carrier_pos, "O264 母舰块必须在 O239 航母块之前"
        )
        # 全文件只此一处母舰下单判据(移动而非复制)
        self.assertEqual(src.count("_ms_order_ready = ("), 1)

    def test_zt_forge_pin_gate(self):
        # O358-①(o357 尸检)+ O359-①(o358 尸检):四象限 —— 判据
        #「GATEWAY 已放置(实体含在建)or (t≥75 且矿≥200)」;
        # pending(派工未放置)不算(o358b g2:70.7s 干等派工已出,
        # 放置拖到 124.6s,forge 63.4s 抢 150 实锤)。
        # ① GATEWAY 已放置 → 任意时刻放行(forge-first 不抢 opener)
        self.assertTrue(zt_forge_pin_gate(True, 30.0, 0.0))
        self.assertTrue(zt_forge_pin_gate(True, 60.0, 150.0))
        # ② GATEWAY 未放置且 t<75 → 不钉(GATEWAY ≤75s 基线恢复;
        # o357/o358 实证早放行把 GATEWAY 右移到 104.5-132.6s)
        self.assertFalse(zt_forge_pin_gate(False, 60.0, 500.0))
        self.assertFalse(zt_forge_pin_gate(False, 74.9, 500.0))
        # ③ GATEWAY 未放置、t≥75 且矿 ≥200 → 兜底放行(forge ≤150s)
        self.assertTrue(zt_forge_pin_gate(False, 75.0, 200.0))
        self.assertTrue(zt_forge_pin_gate(False, 104.5, 300.0))
        # ④ GATEWAY 未放置、t≥75 但矿 <200 → 不钉(opener 流水
        # 高峰矿恒 <200,150 矿 forge 不插队)
        self.assertFalse(zt_forge_pin_gate(False, 75.0, 199.9))
        self.assertFalse(zt_forge_pin_gate(False, 120.0, 100.0))

    def test_event_throttle_ok(self):
        # O357-④:O340 同规约 30s 节流 —— 只节流言不节流行为
        self.assertTrue(event_throttle_ok(530.0, 0.0))
        self.assertTrue(event_throttle_ok(560.0, 530.0))
        self.assertFalse(event_throttle_ok(559.9, 530.0))
        # 显式 interval
        self.assertTrue(event_throttle_ok(100.0, 50.0, interval=10.0))
        self.assertFalse(event_throttle_ok(55.0, 50.0, interval=10.0))


class TestO360MidGameEconomy(unittest.TestCase):
    """O360(o359a/o359b 尸检):中盘经济/放置层五修复 ——
    ① 城镇厅绕过 5x5 落位簿记;② FB 专项基金窗;③ 静态防御全局
    软顶;④ 停气转矿解除双向化+60s 保险丝;⑤ 探机让位 min_workers
    20+Nexus 豁免(⑤ 用例在 test_zt_cannon_pending_probe_yield)。"""

    def test_townhall_skips_placement(self):
        # 5x5 城镇厅 → 绕过簿记(o359b g1 256 条 FIVE_BY_FIVE 警告根因)
        self.assertTrue(townhall_skips_placement("NEXUS"))
        self.assertTrue(townhall_skips_placement("COMMANDCENTER"))
        self.assertTrue(townhall_skips_placement("HATCHERY"))
        # 2x2/3x3 结构 → 簿记照常
        self.assertFalse(townhall_skips_placement("FLEETBEACON"))
        self.assertFalse(townhall_skips_placement("PHOTONCANNON"))
        self.assertFalse(townhall_skips_placement("STARGATE"))
        self.assertFalse(townhall_skips_placement("PYLON"))

    def test_fb_fund_window(self):
        # SG 就绪 + FB 无实体 + 在 core 链 + 无威胁 + 未超时 + 矿够
        # (O368-①a:开窗矿判据 150→300,对齐 FB 造价)→ 开窗
        self.assertTrue(fb_fund_window(True, 0, True, False, False, minerals=300.0))
        # SG 未就绪 → 不开(FB 链还未到)
        self.assertFalse(fb_fund_window(False, 0, True, False, False, minerals=300.0))
        # FB 实体已落(含在建)→ 关窗(攒钱目的达成)
        self.assertFalse(fb_fund_window(True, 1, True, False, False, minerals=300.0))
        # FB 不在 core 链 → 不开(非舰队流派)
        self.assertFalse(fb_fund_window(True, 0, False, False, False, minerals=300.0))
        # threat/rush 豁免 → 被骑脸时塔链优先,关窗
        self.assertFalse(fb_fund_window(True, 0, True, True, False, minerals=300.0))
        # 90s 超时 → 关窗(O106 死锁教训:不钉死)
        self.assertFalse(fb_fund_window(True, 0, True, False, True, minerals=300.0))

    def test_fb_fund_probe_yield(self):
        # 窗内 + 农 ≥28 → 探机让位
        self.assertTrue(fb_fund_probe_yield(True, 28))
        self.assertTrue(fb_fund_probe_yield(True, 40))
        # 窗内 + 农 <28 → 不让位(不掐经济火种)
        self.assertFalse(fb_fund_probe_yield(True, 27))
        # 窗外 → 不让位
        self.assertFalse(fb_fund_probe_yield(False, 40))

    def test_fb_fund_cannon_blocked(self):
        # 窗内 + 塔 ≥2 → 第 3+ 座塔被拦
        self.assertTrue(fb_fund_cannon_blocked(True, 2))
        self.assertTrue(fb_fund_cannon_blocked(True, 8))
        # 窗内 + 塔 <2 → 保命塔照钉
        self.assertFalse(fb_fund_cannon_blocked(True, 0))
        self.assertFalse(fb_fund_cannon_blocked(True, 1))
        # 窗外(threat 豁免在上游)→ 不拦
        self.assertFalse(fb_fund_cannon_blocked(False, 8))

    def test_fb_fund_upgrade_kept(self):
        # 窗内 ≥200 矿升级 → 让位(2 攻/2 防级一笔顶大半座 FB)
        self.assertFalse(fb_fund_upgrade_kept(True, 200.0))
        self.assertFalse(fb_fund_upgrade_kept(True, 250.0))
        # 窗内 <200 矿升级 → 照常
        self.assertTrue(fb_fund_upgrade_kept(True, 100.0))
        self.assertTrue(fb_fund_upgrade_kept(True, 175.0))
        # 窗外一切升级照常
        self.assertTrue(fb_fund_upgrade_kept(False, 250.0))

    def test_cannon_global_capped(self):
        # 四象限:塔 ≥12 且非 threat → 封顶;threat 豁免;<12 不封
        self.assertTrue(cannon_global_capped(12, False))
        self.assertTrue(cannon_global_capped(19, False))  # o359b g2 实证档
        self.assertFalse(cannon_global_capped(12, True))
        self.assertFalse(cannon_global_capped(19, True))
        self.assertFalse(cannon_global_capped(11, False))
        self.assertFalse(cannon_global_capped(0, False))

    def test_cannon_absolute_capped(self):
        self.assertFalse(cannon_absolute_capped(17))
        self.assertTrue(cannon_absolute_capped(18))
        self.assertTrue(cannon_absolute_capped(25))

    def test_gas_to_minerals_released(self):
        # O363-④b:纯气压滞回 —— 气 <250 才复采
        self.assertTrue(gas_to_minerals_released(249.9, 100.0))
        self.assertTrue(gas_to_minerals_released(0.0, 0.0))
        # 矿 >400 不再解除(o362a g3:矿一缓就放回气矿,气照涨 +220)
        self.assertFalse(gas_to_minerals_released(694.0, 400.1))
        self.assertFalse(gas_to_minerals_released(616.0, 250.0))
        self.assertFalse(gas_to_minerals_released(250.0, 400.0))
        # 与 ZT 早窗触发档(气>300)的滞回带:250-300 之间按住
        self.assertFalse(gas_to_minerals_released(280.0, 50.0))

    def test_gas_pull_window_expired(self):
        # 未在停气(None)→ 不炸
        self.assertFalse(gas_pull_window_expired(None, 100.0))
        # 窗内 → 不炸
        self.assertFalse(gas_pull_window_expired(100.0, 159.9))
        # 连续停气 ≥60s → 棘轮保险丝(o359a 解除永不到达档)
        self.assertTrue(gas_pull_window_expired(100.0, 160.0))
        self.assertTrue(gas_pull_window_expired(100.0, 300.0))


class TestO362TimingVacuumWindow(unittest.TestCase):
    """O362(o361b Harder Timing 0/3 尸检):200-330s 真空窗专修族。"""

    def test_zt_vacuum_buffer_caps(self):
        # 闸关两态:GATEWAY 未就绪 / t<120 → (0,0)(零兵种闸原样)
        self.assertEqual(zt_vacuum_buffer_caps(False, False, 200.0), (0, 0))
        self.assertEqual(zt_vacuum_buffer_caps(True, True, 119.9), (0, 0))
        # 闸开:GATEWAY 就绪 + t≥120 → 叉 floor 3;core 未就绪追猎 0
        self.assertEqual(zt_vacuum_buffer_caps(True, False, 120.0), (3, 0))
        self.assertEqual(zt_vacuum_buffer_caps(True, False, 200.0), (3, 0))
        # core 就绪后 → 追猎 floor 1(吃烂气)
        self.assertEqual(zt_vacuum_buffer_caps(True, True, 200.0), (3, 1))

    def test_pin_deadlock_fuse(self):
        # 农 <10 时全场最多 1 钉点:第 2 钉点(active_pins 含本钉=2)被拒
        self.assertTrue(pin_deadlock_fuse(9, 2, 0.0))
        self.assertTrue(pin_deadlock_fuse(3, 3, 10.0))
        # 农 <10 且仅 1 钉点且未超时 → 不跳闸
        self.assertFalse(pin_deadlock_fuse(9, 1, 30.0))
        # 农 ≥10 不受上限闸
        self.assertFalse(pin_deadlock_fuse(10, 2, 30.0))
        self.assertFalse(pin_deadlock_fuse(20, 5, 59.9))
        # 任一钉点等钱 >60s → 强制释放(61s 档,o361b g2 僵尸局实证)
        self.assertTrue(pin_deadlock_fuse(9, 1, 61.0))
        self.assertTrue(pin_deadlock_fuse(20, 1, 320.0))
        # 边界:恰好 60s 不释放
        self.assertFalse(pin_deadlock_fuse(9, 1, 60.0))

    def test_new_base_defense_pins(self):
        # 新矿裸奔(forge+cyber 就绪,0 塔 0 电池)→ 塔+电池同钉
        # (o362b g3 四矿 522s target=0 被连抄三次实证档)
        self.assertEqual(new_base_defense_pins(True, True, 0, 0, 0, 0), (True, True))
        # forge 未就绪 → 不钉塔(tech 闸),电池照钉
        self.assertEqual(new_base_defense_pins(False, True, 0, 0, 0, 0), (False, True))
        # cyber 未就绪 → 不钉电池,塔照钉
        self.assertEqual(new_base_defense_pins(True, False, 0, 0, 0, 0), (True, False))
        # 就绪+在途合并计数:1 就绪+1 在途 = 满 2 塔目标,不再重钉
        self.assertEqual(new_base_defense_pins(True, True, 1, 1, 0, 0), (False, True))
        # 1 塔在途(落成交接棒已在飞)→ 仍补第 2 塔
        self.assertEqual(new_base_defense_pins(True, True, 1, 0, 0, 0), (True, True))
        # 电池在途即不重钉
        self.assertEqual(new_base_defense_pins(True, True, 2, 0, 0, 1), (False, False))
        # 塔阵+电池齐 → 全停
        self.assertEqual(new_base_defense_pins(True, True, 2, 0, 1, 0), (False, False))

    def test_pin_repin_blocked(self):
        # 封锁期内 → 禁重钉(o362b g2:30s 冷却一过被同一钉点夺回×4)
        self.assertTrue(pin_repin_blocked(255.0, 315.0))
        self.assertTrue(pin_repin_blocked(314.9, 315.0))
        # 封锁到期 → 放行
        self.assertFalse(pin_repin_blocked(315.0, 315.0))
        self.assertFalse(pin_repin_blocked(400.0, 315.0))
        # 无封锁(None)→ 放行
        self.assertFalse(pin_repin_blocked(100.0, None))

    def test_zt_sg_pin_time_ok(self):
        # t=250 放行(o361b g1 的 643s 星门档要覆盖)
        self.assertTrue(zt_sg_pin_time_ok(250.0))
        self.assertTrue(zt_sg_pin_time_ok(240.0))
        # t=230 拦(240 以下不动 opener 资金排序)
        self.assertFalse(zt_sg_pin_time_ok(230.0))
        self.assertFalse(zt_sg_pin_time_ok(0.0))

    def test_fb_fund_window_o362(self):
        # 资源路径:气 <400 → 不开(FB 气耗未就绪,开窗白压经济)
        self.assertFalse(
            fb_fund_window(True, 0, True, False, False, vespene=399.9)
        )
        # O368-①a:气 ≥400 + 矿 ≥300(对齐 FB 造价)→ 开
        self.assertTrue(
            fb_fund_window(
                True, 0, True, False, False, vespene=400.0, minerals=300.0
            )
        )
        # O368-①a:矿 150-299 且窗未开 → 不开(o367b g1 四窗两关空转
        # 档:矿 150 开窗 FB 仍买不起,纯压经济)
        self.assertFalse(
            fb_fund_window(
                True, 0, True, False, False, vespene=1500.0, minerals=299.9
            )
        )
        # 矿 <300 但窗已开 → 滞回保持(抑制攒矿正是窗的职责)
        self.assertTrue(
            fb_fund_window(
                True, 0, True, False, False,
                vespene=1500.0, minerals=47.0, window_open=True,
            )
        )

    def test_fb_fund_ground_yield(self):
        # 窗内 → trickle(floor 之上的兵营单位)让位
        self.assertTrue(fb_fund_ground_yield(True))
        # 窗外 → 不让
        self.assertFalse(fb_fund_ground_yield(False))

    def test_fb_fund_sg2_blocked(self):
        # 窗内 + 星门 ≥1 → 第 2+ 星门被拦(150矿+150气 同台竞争 FB)
        self.assertTrue(fb_fund_sg2_blocked(True, 1))
        self.assertTrue(fb_fund_sg2_blocked(True, 3))
        # 窗内 + 首座 SG 未落 → 不拦(首座是 FB 前置)
        self.assertFalse(fb_fund_sg2_blocked(True, 0))
        # 窗外 → 不拦
        self.assertFalse(fb_fund_sg2_blocked(False, 2))

    def test_fb_fund_probe_brake(self):
        # 窗开 >45s 且矿 <300 且农 ≥20 → 强制停探机一轮
        self.assertTrue(fb_fund_probe_brake(45.0, 200.0, 20))
        self.assertTrue(fb_fund_probe_brake(80.0, 47.0, 30))
        # 窗开不足 45s → 不刹(给既有抑制面机会)
        self.assertFalse(fb_fund_probe_brake(44.9, 200.0, 30))
        # 未开窗(None)→ 不刹
        self.assertFalse(fb_fund_probe_brake(None, 200.0, 30))
        # 矿已够 300 → 不刹(马上成交)
        self.assertFalse(fb_fund_probe_brake(60.0, 300.0, 30))
        # 农 <20 → 不刹(小农局探机是收入本身)
        self.assertFalse(fb_fund_probe_brake(60.0, 200.0, 19))

    def test_gas_pull_thresholds(self):
        # ZT 且 t<360 → 早窗档 (250, +inf)—— O366-②a:气档 300→250
        # (o365 六局矿 <200/气溢出 300-1700、星门 257-269s 闲置实证,
        # 250-300 这段死钱正是矿枯窗);矿档 +inf 不变(O363-④c)
        self.assertEqual(gas_pull_thresholds(True, 359.9), (250.0, float("inf")))
        self.assertEqual(gas_pull_thresholds(True, 100.0), (250.0, float("inf")))
        # ZT 且 t≥360 → 保持 500/200(舰队链开始吃气)
        self.assertEqual(gas_pull_thresholds(True, 360.0), (500.0, 200.0))
        # 非 ZT 全程 500/200
        self.assertEqual(gas_pull_thresholds(False, 100.0), (500.0, 200.0))
        # 早窗触发:气 >250 不论矿高低
        self.assertTrue(
            gas_to_minerals_needed(
                251.0, 400.0,
                vespene_threshold=250.0, mineral_threshold=float("inf"),
            )
        )
        self.assertFalse(
            gas_to_minerals_needed(
                300.0, 149.9,
                vespene_threshold=300.0, mineral_threshold=float("inf"),
            )
        )

    def test_nexus_fund_hold_active(self):
        # O364-①:窗内 + Nexus 钉点在簿记(等钱)→ hold
        self.assertTrue(nexus_fund_hold_active(100.0, 145.0, 1, False))
        # 成交放行:pending=0(Nexus 开工,tracker 无条目)→ 不 hold
        self.assertFalse(nexus_fund_hold_active(100.0, 145.0, 0, False))
        # 45s 超时放行(防死锁)
        self.assertFalse(nexus_fund_hold_active(145.0, 145.0, 1, False))
        self.assertFalse(nexus_fund_hold_active(200.0, 145.0, 1, False))
        # threat 豁免(被骑脸时塔/兵钱不能锁)
        self.assertFalse(nexus_fund_hold_active(100.0, 145.0, 1, True))
        # 未武装(hold_until=0)→ 不 hold
        self.assertFalse(nexus_fund_hold_active(100.0, 0.0, 1, False))

    def test_nexus_fund_hold_blocks(self):
        # O364-① hold 清单:SG 第 2+ 座/FB/Robo/Twilight
        self.assertTrue(nexus_fund_hold_blocks("STARGATE", 1))
        self.assertTrue(nexus_fund_hold_blocks("STARGATE", 3))
        self.assertTrue(nexus_fund_hold_blocks("FLEETBEACON", 0))
        self.assertTrue(nexus_fund_hold_blocks("ROBOTICSFACILITY", 0))
        self.assertTrue(nexus_fund_hold_blocks("TWILIGHTCOUNCIL", 0))
        # 首座 SG 豁免(舰队链起点)
        self.assertFalse(nexus_fund_hold_blocks("STARGATE", 0))
        # 保命/经济件不在清单(塔/电池/水晶/Nexus 本身/锻造炉)
        for name in ("PHOTONCANNON", "SHIELDBATTERY", "PYLON", "NEXUS", "FORGE"):
            self.assertFalse(nexus_fund_hold_blocks(name, 2))

    def test_new_base_cannon_fb_fund_exempt(self):
        # O364-②:在建 Nexus + 0 塔(含在途)→ 首塔豁免 FB 基金窗
        self.assertTrue(new_base_cannon_fb_fund_exempt(False, 0, 0))
        # 已落成 → 回归基金窗纪律
        self.assertFalse(new_base_cannon_fb_fund_exempt(True, 0, 0))
        # 已有 ≥1 塔(就绪或在途)→ 不豁免
        self.assertFalse(new_base_cannon_fb_fund_exempt(False, 1, 0))
        self.assertFalse(new_base_cannon_fb_fund_exempt(False, 0, 1))

    def test_gas_stop_leaking(self):
        # O364-③b:10s 增速 >15 → 泄漏(被拽回)
        self.assertTrue(gas_stop_leaking(4.0, 2.0))    # 折 20/10s
        self.assertTrue(gas_stop_leaking(80.0, 10.0))  # o363 实测斜率 ~+8/s
        # ≤15/10s → 正常(载货返回/尾账抖动)
        self.assertFalse(gas_stop_leaking(3.0, 2.0))   # 折 15/10s
        self.assertFalse(gas_stop_leaking(-50.0, 10.0))  # 花钱降气
        # 首帧建档(seconds≤0)不判
        self.assertFalse(gas_stop_leaking(100.0, 0.0))

    def test_gas_stop_release_blocked(self):
        # O364-③c:气 >400 且舰队 <6 → 棘轮不解除(o363b g2 +354 漏回)
        self.assertTrue(gas_stop_release_blocked(500.0, 3))
        self.assertTrue(gas_stop_release_blocked(401.0, 0))
        # 舰队成型(≥6)→ 放行
        self.assertFalse(gas_stop_release_blocked(500.0, 6))
        # 气压已下去(≤400)→ 放行
        self.assertFalse(gas_stop_release_blocked(400.0, 3))

    def test_carrier_hard_convert_ok(self):
        # O364-④ 三象限:FB 就绪 + 矿 >600 + 航母(含在产)<2 + 买得起 → 触发
        self.assertTrue(carrier_hard_convert_ok(True, 955.0, 1, True))
        self.assertTrue(carrier_hard_convert_ok(True, 600.0, 0, True))
        # 矿不烂(<600)→ 不触发(留给 O239 气烂通道)
        self.assertFalse(carrier_hard_convert_ok(True, 599.9, 1, True))
        # 航母已 ≥2 → 不触发(转化完成,回比例分配)
        self.assertFalse(carrier_hard_convert_ok(True, 955.0, 2, True))
        # FB 未就绪 / 买不起 → 不触发
        self.assertFalse(carrier_hard_convert_ok(False, 955.0, 1, True))
        self.assertFalse(carrier_hard_convert_ok(True, 955.0, 1, False))

    def test_manual_cannon_anchor(self):
        # O364-⑤a:锚在 Nexus→矿线方向上 base_offset 格
        ax, ay = manual_cannon_anchor((100.0, 100.0), (110.0, 100.0), 0)
        self.assertAlmostEqual(ax, 106.0)
        self.assertAlmostEqual(ay, 100.0)
        # O366-③c:attempt 低 3 位选方向(45° 步进扇形)—— attempt 3
        # = 矿线方向 +90°(同圈不外扩)
        ax2, ay2 = manual_cannon_anchor((100.0, 100.0), (110.0, 100.0), 3)
        self.assertAlmostEqual(ax2, 100.0)
        self.assertAlmostEqual(ay2, 106.0)
        # 高位选圈:attempt 8 = 转满一圈回到矿线方向,外扩 1 格
        ax2b, ay2b = manual_cannon_anchor((100.0, 100.0), (110.0, 100.0), 8)
        self.assertAlmostEqual(ax2b, 107.0)
        self.assertAlmostEqual(ay2b, 100.0)
        # 对角矿线 → 单位方向
        ax3, ay3 = manual_cannon_anchor((0.0, 0.0), (3.0, 4.0), 0)
        self.assertAlmostEqual(ax3, 3.6)   # 6 * 3/5
        self.assertAlmostEqual(ay3, 4.8)   # 6 * 4/5
        # 矿线取不到 → 退化方向 + 扇形旋转(不崩);attempt 1 = +45°
        ax4, ay4 = manual_cannon_anchor((50.0, 60.0), None, 1)
        _s = 0.7071067811865476
        self.assertAlmostEqual(ax4, 50.0 + 6.0 * _s)
        self.assertAlmostEqual(ay4, 60.0 - 6.0 * _s)
        # 矿线质心与 Nexus 重合(零向量)→ 退化方向,不除零
        ax5, ay5 = manual_cannon_anchor((50.0, 60.0), (50.0, 60.0), 0)
        self.assertAlmostEqual(ax5, 50.0)
        self.assertAlmostEqual(ay5, 54.0)

    def test_escort_hard_cap(self):
        # O364-⑤b:协防硬限量 ≤3(o363a g2 协防 6 农送死实证)
        self.assertEqual(escort_hard_cap(8, 14, keep_mining=6), 3)
        self.assertEqual(escort_hard_cap(20, 30, keep_mining=6), 3)
        self.assertEqual(escort_hard_cap(3, 14, keep_mining=6), 3)
        # 采矿底线不变:农民太少时少于 3
        self.assertEqual(escort_hard_cap(12, 8, keep_mining=6), 2)
        self.assertEqual(escort_hard_cap(12, 5, keep_mining=6), 0)


class TestO365Fixes(unittest.TestCase):
    """O365 五项修复的纯逻辑单测(o364a Timing 0/3 + o364b Rush 1/3 尸检)。"""

    def test_gas_stop_requisition_ok(self):
        # O365-①:塔/电池/补电 select_worker 失败即放行停气池,
        # 不再要求采集池簿记归零(o364b g3 采集池=1虚/停气池=63 实证)
        self.assertTrue(gas_stop_requisition_ok("PHOTONCANNON", False, 63))
        self.assertTrue(gas_stop_requisition_ok("SHIELDBATTERY", False, 6))
        self.assertTrue(gas_stop_requisition_ok("PYLON", False, 6))
        # 采集池真空 → 任意结构保持旧闸(O116-② 行为不变)
        self.assertTrue(gas_stop_requisition_ok("FLEETBEACON", True, 3))
        # 非防御链结构且采集池非空 → 不强征(防停气池被奢侈品抽干)
        self.assertFalse(gas_stop_requisition_ok("FLEETBEACON", False, 3))
        self.assertFalse(gas_stop_requisition_ok("ROBOTICSFACILITY", False, 3))
        # 停气池空 → 无人可征
        self.assertFalse(gas_stop_requisition_ok("PHOTONCANNON", False, 0))

    def test_gas_restore_needed(self):
        # O365-②:矿>600 且气<125 且航母<2 且 FB 就绪 → 强制复气
        self.assertTrue(gas_restore_needed(955.0, 7.0, 1, True))
        self.assertTrue(gas_restore_needed(600.0, 124.9, 0, True))
        self.assertFalse(gas_restore_needed(599.9, 7.0, 1, True))   # 矿不够
        self.assertFalse(gas_restore_needed(955.0, 125.0, 1, True))  # 气未枯
        self.assertFalse(gas_restore_needed(955.0, 7.0, 2, True))   # 航母够
        self.assertFalse(gas_restore_needed(955.0, 7.0, 1, False))  # FB 未就绪

    def test_gas_restore_done(self):
        # O365-②:气 ≥300 复气完成(300 > 航母 250 气价)
        self.assertTrue(gas_restore_done(300.0))
        self.assertFalse(gas_restore_done(299.9))

    def test_nexus_deal_confirmed(self):
        # O365-③c:成交 = tracker 真空 + Nexus 实体(含在建)双条件
        self.assertTrue(nexus_deal_confirmed(0, 2))
        # 保险丝 pop/静默回收(条目消失但无实体)→ 不判成交(假成交防回)
        self.assertFalse(nexus_deal_confirmed(0, 1))
        # 条目还在 → 未成交
        self.assertFalse(nexus_deal_confirmed(1, 2))

    def test_nexus_deal_verify_failed(self):
        # O365-③b:报成交后 T+15s 仍无 Nexus 实体 → 假成交回滚
        self.assertTrue(nexus_deal_verify_failed(415.0, 415.0, 1))
        self.assertTrue(nexus_deal_verify_failed(430.1, 415.0, 1))
        self.assertFalse(nexus_deal_verify_failed(414.9, 415.0, 1))  # 未到点
        self.assertFalse(nexus_deal_verify_failed(415.0, 415.0, 2))  # 实体在
        self.assertFalse(nexus_deal_verify_failed(415.0, 0.0, 1))    # 无待校验

    def test_nexus_pin_yield_gate(self):
        # O365-④ 让位闸三象限:矿≥400 且二矿未钉 且主基≥2塔
        self.assertTrue(nexus_pin_yield_gate(400.0, False, 2))
        self.assertFalse(nexus_pin_yield_gate(399.9, False, 2))  # 矿不够
        self.assertFalse(nexus_pin_yield_gate(500.0, True, 2))   # 二矿已钉
        self.assertFalse(nexus_pin_yield_gate(500.0, False, 1))  # 保命塔未齐

    def test_cyber_core_watchdog(self):
        # O365-⑤a + O370-④a(180→150,o369a Timing BY 156.7/192.9/
        # 245.1 全超标实证):t>150s 且无 BY 实体无在途 → watchdog 开火
        self.assertTrue(cyber_core_watchdog(150.0, False))
        self.assertFalse(cyber_core_watchdog(149.9, False))  # 太早
        self.assertFalse(cyber_core_watchdog(300.0, True))   # BY 已在/在途

    def test_cyber_core_build_allowed(self):
        # O370-④b:双 BY 防重(o369b g2/g3 白扔 100+ 矿档)
        # 无实体无在途+runner 无 core 步 → 允许钉
        self.assertTrue(cyber_core_build_allowed(False, False))
        # 已有 BY 实体/在途 → 跳过
        self.assertFalse(cyber_core_build_allowed(True, False))
        # runner 后续步排着 core(runner 会自己建)→ 跳过
        self.assertFalse(cyber_core_build_allowed(False, True))

    def test_evac_return_gas_stop_remark(self):
        # O365-⑤b:停气台账在册者归队即重标,不在册者归 GATHERING
        self.assertTrue(evac_return_gas_stop_remark(42, {42, 43}))
        self.assertFalse(evac_return_gas_stop_remark(44, {42, 43}))
        self.assertFalse(evac_return_gas_stop_remark(42, set()))

    def test_anchor_retry_ok(self):
        # O365-⑤c:连续 no_placement ≥30s 首开,此后每 30s 持续重试
        self.assertFalse(anchor_retry_ok(920.0, 900.0, -9999.0))  # 连续窗未满
        self.assertTrue(anchor_retry_ok(930.0, 900.0, -9999.0))   # 首开
        self.assertFalse(anchor_retry_ok(950.0, 900.0, 930.0))    # 重试冷却中
        self.assertTrue(anchor_retry_ok(960.0, 900.0, 930.0))     # 持续重试

    def test_fb_fund_window_sg_started(self):
        # O367-①:①a 回退 —— sg_started 不再开窗(o366b g1 钱序倒错
        # 实证:SG(329)→FB(406)→Nexus(430,被挤晚 133s),恢复
        # SG 就绪才开窗;sg_started 参数保留签名但不入判据
        self.assertFalse(
            fb_fund_window(False, 0, True, False, False, sg_started=True)
        )
        # SG 就绪 → 照常开窗(O368-①a:矿判据 300,显式传矿)
        self.assertTrue(
            fb_fund_window(
                True, 0, True, False, False, sg_started=True, minerals=300.0
            )
        )
        # 默认参数(不传 sg_started)维持旧口径:SG 就绪才开
        self.assertFalse(fb_fund_window(False, 0, True, False, False))
        self.assertTrue(fb_fund_window(True, 0, True, False, False, minerals=300.0))

    def test_fb_fund_window_stalled(self):
        # O367-①:窗开 10s+ 矿净积累 ≤0 → 关窗放行(o366a g2 三窗
        # 零成交纯压经济实证)
        self.assertTrue(fb_fund_window_stalled(0.0, 10.0))    # 零增长
        self.assertTrue(fb_fund_window_stalled(-30.0, 12.0))  # 负增长
        # 矿在涨 → 健康,不关
        self.assertFalse(fb_fund_window_stalled(50.0, 10.0))
        # 滑窗未满 10s 不判
        self.assertFalse(fb_fund_window_stalled(-30.0, 9.9))

    def test_fb_bankrupt_needed(self):
        # O368-①b:O110 FB no_money 自救连续 ≥3 次 → 破产分支触发
        self.assertFalse(fb_bankrupt_needed(0))
        self.assertFalse(fb_bankrupt_needed(2))
        self.assertTrue(fb_bankrupt_needed(3))
        self.assertTrue(fb_bankrupt_needed(8))  # o367a g1/g3 各 6-8 次档

    def test_fb_bankrupt_cleared(self):
        # O368-①b:FB 实体出现(钉下去了)→ 解除
        self.assertTrue(fb_bankrupt_cleared(1, False))
        # threat/rush 激活 → 解除(被骑脸时防御链恢复优先)
        self.assertTrue(fb_bankrupt_cleared(0, True))
        # FB 未落且无威胁 → 维持暂停
        self.assertFalse(fb_bankrupt_cleared(0, False))

    def test_fb_fund_gas_gate(self):
        # O368-①c:窗外恒放行
        self.assertTrue(fb_fund_gas_gate(False, 150.0, 150.0))
        # 窗内 气 ≥ 200(FB 预留)+150(虚空气耗) → 放行
        self.assertTrue(fb_fund_gas_gate(True, 350.0, 150.0))
        # 窗内气不够保 FB 预留 → 拦(o367b g3 虚空 514s 产于窗内档)
        self.assertFalse(fb_fund_gas_gate(True, 349.9, 150.0))
        self.assertFalse(fb_fund_gas_gate(True, 200.0, 150.0))

    def test_stargate_deadlock_voidray(self):
        # O368-②:就绪 SG 全闲 ≥60s 且 FB 未落成 → 解绑转产虚空
        self.assertTrue(stargate_deadlock_voidray(100.0, 160.0, 0))
        # 空转 <60s → 不触发
        self.assertFalse(stargate_deadlock_voidray(100.0, 159.9, 0))
        # FB 已落成 → 不触发(正常产线接管)
        self.assertFalse(stargate_deadlock_voidray(100.0, 600.0, 1))
        # 无计时(有 SG 在产/无就绪 SG)→ 不触发
        self.assertFalse(stargate_deadlock_voidray(None, 600.0, 0))

    def test_power_precheck_needed(self):
        # O368-③:带电余=0 且空闲余>0 → 预检补电((162,22) 实证档)
        self.assertTrue(power_precheck_needed(0, 12))
        # 有带电空闲槽 → 不需要
        self.assertFalse(power_precheck_needed(1, 12))
        # 空闲余=0 → 几何死槽,归 O357 换锚管,本预检不触发
        self.assertFalse(power_precheck_needed(0, 0))
        # 簿记拿不到槽(99,99,-1)→ 不挡任何闸
        self.assertFalse(power_precheck_needed(99, 99))

    def test_fb_fund_latch_needed(self):
        # O369-①a:latch 常态生效 —— SG 就绪+FB 无实体+非 threat+
        # 矿 <300 → 触发(o368a g2 矿 5-756 被抢实证档)
        self.assertTrue(fb_fund_latch_needed(True, 0, False, 5.0, 400.0))
        self.assertTrue(fb_fund_latch_needed(True, 0, False, 299.9, 200.0))
        # 气 <200(FB 气耗未就绪)→ 同样 latch(攒够 300+200 才钉)
        self.assertTrue(fb_fund_latch_needed(True, 0, False, 500.0, 150.0))
        # 解除三态:矿 ≥300 且气 ≥200(攒够即钉,判据自灭)
        self.assertFalse(fb_fund_latch_needed(True, 0, False, 300.0, 200.0))
        # threat 激活 → 临时解除(防御链恢复优先)
        self.assertFalse(fb_fund_latch_needed(True, 0, True, 5.0, 400.0))
        # FB 实体出现(钉下去了)→ 解除
        self.assertFalse(fb_fund_latch_needed(True, 1, False, 5.0, 400.0))
        # SG 未就绪 → 不 latch(FB 前置未齐,opener 期不误触)
        self.assertFalse(fb_fund_latch_needed(False, 0, False, 5.0, 400.0))

    def test_fb_bankrupt_needed_o369(self):
        # O369-①b:no_money 累计 ≥3(不再要求连续)→ 触发
        self.assertTrue(fb_bankrupt_needed(3))
        # FB 缺失 >120s(调用方只传 SG 就绪+truly_missing 口径)→ 触发
        self.assertTrue(fb_bankrupt_needed(0, fb_missing_s=120.0))
        self.assertTrue(fb_bankrupt_needed(1, fb_missing_s=200.0))
        # 缺失 <120s 且累计 <3 → 不触发
        self.assertFalse(fb_bankrupt_needed(2, fb_missing_s=119.9))
        # 缺失时刻未知(None)→ 不触发
        self.assertFalse(fb_bankrupt_needed(0, fb_missing_s=None))

    def test_fb_latch_stalled(self):
        # O369-①c:零积累持续 ≥30s → 临时解除(防死锁)
        self.assertTrue(fb_latch_stalled(100.0, 130.0))
        # 不足 30s → 维持
        self.assertFalse(fb_latch_stalled(100.0, 129.9))
        # 上一采样矿在涨(None)→ 健康,不解除
        self.assertFalse(fb_latch_stalled(None, 600.0))

    def test_fb_latch_pin_allowed(self):
        # O370-②a:互斥仲裁(o369b g3 latch 钉压过 Nexus 窗档)
        # 二矿未成交 → latch 钉 FB 排队(Nexus 优先)
        self.assertFalse(fb_latch_pin_allowed(False, False))
        self.assertFalse(fb_latch_pin_allowed(False, True))
        # 二矿成交但 Nexus 资金窗独占期 → 仍排队
        self.assertFalse(fb_latch_pin_allowed(True, True))
        # 二矿成交且窗放行 → latch 钉点先行
        self.assertTrue(fb_latch_pin_allowed(True, False))

    def test_nexus_repin_loop_forced(self):
        # O371-③(o370a g3 实证):默认阈 3→1 —— 第 2 轮消失即强制
        # 直钉(旧阈第 4 轮才强制,4 轮死循环 130s 超验收 ≤60s)
        self.assertFalse(nexus_repin_loop_forced(0))
        self.assertFalse(nexus_repin_loop_forced(1))
        self.assertTrue(nexus_repin_loop_forced(2))
        self.assertTrue(nexus_repin_loop_forced(8))
        # 显式 max_rounds=3 保留 O370-②b 原语义(o369a g3 档)
        self.assertFalse(nexus_repin_loop_forced(3, max_rounds=3))
        self.assertTrue(nexus_repin_loop_forced(4, max_rounds=3))

    def test_fb_rescue_expansion_bypass(self):
        # O370-③a:FB 禁用「分矿试建」旁路(o369a g2 无塔分矿
        # 被拆档),SG 保留旁路
        self.assertFalse(fb_rescue_expansion_bypass("FLEETBEACON"))
        self.assertTrue(fb_rescue_expansion_bypass("STARGATE"))

    def test_sg_idle_reset_needed(self):
        # O369-②a:起点口径 —— 无就绪 SG → 销账
        self.assertTrue(sg_idle_reset_needed(0, False))
        # 有 SG 在产舰队单位(TEMPEST/CARRIER)→ 销账(产线复活)
        self.assertTrue(sg_idle_reset_needed(2, True))
        # 在产仅填线(虚空/先知)→ 保留计时(g2 223s 被打断修复档)
        self.assertFalse(sg_idle_reset_needed(1, False))
        self.assertFalse(sg_idle_reset_needed(3, False))

    def test_sg_post_fb_fill(self):
        # O369-②b:FB 已落+空转 ≥60s+矿 <300 → 允许产虚空填线
        # (o368a g3:FB 481s→风暴 590s 空转档)
        self.assertTrue(sg_post_fb_fill(481.0, 541.0, 1, 200.0))
        # 矿够 300(买得起风暴)→ 正常产线接管,不填线
        self.assertFalse(sg_post_fb_fill(481.0, 541.0, 1, 300.0))
        # FB 未落成 → 归 O368-② 死锁自救管,本分支不触发
        self.assertFalse(sg_post_fb_fill(481.0, 541.0, 0, 200.0))
        # 空转 <60s → 不触发
        self.assertFalse(sg_post_fb_fill(481.0, 540.9, 1, 200.0))
        # 有舰队在产(计时已销)→ 不触发
        self.assertFalse(sg_post_fb_fill(None, 600.0, 1, 200.0))

    def test_power_precheck_covered(self):
        # O369-③:覆盖清单 —— SG/FB 之外推广到 needs_power 防御建筑
        self.assertTrue(power_precheck_covered("STARGATE", True))
        self.assertTrue(power_precheck_covered("FLEETBEACON", True))
        self.assertTrue(power_precheck_covered("PHOTONCANNON", True))
        self.assertTrue(power_precheck_covered("SHIELDBATTERY", True))
        # needs_power=False(水晶/无电建筑)→ 不入清单
        self.assertFalse(power_precheck_covered("PHOTONCANNON", False))
        self.assertFalse(power_precheck_covered("PYLON", False))
        # 无电建筑(Nexus/气矿)→ 不入清单
        self.assertFalse(power_precheck_covered("NEXUS", True))

    def test_reanchor_fallback_default(self):
        # O369-④ + O370-④a(阈值 ≥2→≥1,o369a g3 黑名单仅 1 就把
        # BY 拖到 245s 实证):首次换锚失败(黑名单 ≥1)即回退默认槽
        self.assertTrue(reanchor_fallback_default("CYBERNETICSCORE", 1))
        self.assertTrue(reanchor_fallback_default("CYBERNETICSCORE", 2))
        self.assertTrue(reanchor_fallback_default("GATEWAY", 3))
        # 黑名单 <1 → 照常换锚
        self.assertFalse(reanchor_fallback_default("CYBERNETICSCORE", 0))
        # forge(O351 主基锚)/机械台(非 opener 链)→ 维持原冷却
        self.assertFalse(reanchor_fallback_default("FORGE", 5))
        self.assertFalse(reanchor_fallback_default("ROBOTICSFACILITY", 5))

    def test_cannon_investment_freeze(self):
        # O370-①a(o369 尸检):触发只认实际可见腐化 ≥4
        # 腐化 ≥4 → 冻结(o368b g2 腐化波档)
        self.assertTrue(cannon_investment_freeze(4, False))
        self.assertTrue(cannon_investment_freeze(9, False))
        # 敌 0 腐化 → 不冻结(o369 6/6 局误触发档:旧判据舰队<8
        # 在 t>600 常开,腐化首见前 270-360s 就开火)
        self.assertFalse(cannon_investment_freeze(0, False))
        # 腐化 <4 → 不冻结
        self.assertFalse(cannon_investment_freeze(3, False))
        # 35+ 波(wave_active)→ 豁免(wave floor 照补,生死窗不管)
        self.assertFalse(cannon_investment_freeze(4, True))

    def test_cannon_freeze_clamp(self):
        # O370-①b:断向下棘轮 —— 钳 max(现有, 快照)而非「钳现有」
        # 快照 8、塔被拆到 5 → 目标仍可按快照 8 补回(o369a g1 的
        # 8→5→4→2 棘轮档)
        self.assertEqual(cannon_freeze_clamp(9, 5, 8), 8)
        # 现有高于快照(冻结期补回中)→ 钳到现有不再增
        self.assertEqual(cannon_freeze_clamp(9, 8, 8), 8)
        # 快照外不新增投资(钱让给舰队)
        self.assertEqual(cannon_freeze_clamp(12, 8, 8), 8)
        # 快照为 0(冻结启动时无注册 target)→ 退化为「钳现有」
        self.assertEqual(cannon_freeze_clamp(9, 5, 0), 5)
        # O370-①c:新矿首批豁免 —— 全局 0 塔 + 1 个新矿名额 →
        # 新矿 F2 target 保底 1(o369b g1 三矿 target=0 裸奔档)
        self.assertEqual(cannon_freeze_clamp(2, 0, 0, new_base_exempt=1), 1)
        self.assertEqual(
            cannon_freeze_clamp(5, 0, 0, new_base_exempt=2), 2
        )

    def test_sg_gap_pin_needed(self):
        # O369-⑥:FB 已落+就绪 SG 全忙+舰队 <8+SG <3+矿 ≥150 → 硬钉
        # (o368b g2:O218 等气烂银行 794s 才动档)
        self.assertTrue(sg_gap_pin_needed(1, 2, True, 6, 2, 200.0))
        # 舰队 ≥8 → 不钉(数量够了)
        self.assertFalse(sg_gap_pin_needed(1, 2, True, 8, 2, 200.0))
        # SG 总数 ≥3 → 不钉(后续追加归 O218 气烂银行管)
        self.assertFalse(sg_gap_pin_needed(1, 3, True, 6, 3, 200.0))
        # 就绪 SG 有空闲 → 不钉(产能没满载,加了也空转)
        self.assertFalse(sg_gap_pin_needed(1, 2, False, 6, 2, 200.0))
        # FB 未落成 → 不钉(latch 期 SG2 让位 FB,O369-①)
        self.assertFalse(sg_gap_pin_needed(0, 2, True, 6, 2, 200.0))
        # 矿 <150 → 不钉(O367-⑤b 矿门:穷局钉点 no_money 空转)
        self.assertFalse(sg_gap_pin_needed(1, 2, True, 6, 2, 149.9))
        # 无就绪 SG → 不钉
        self.assertFalse(sg_gap_pin_needed(1, 0, True, 6, 2, 200.0))

    def test_sg_gap_pin_needed_o370(self):
        # O370-⑤a:单 SG 空转+气烂银行出口(o369b g3 气烂 579 档)
        # SG<2+舰队<8+气 ≥300 → 硬钉(不要求全忙)
        self.assertTrue(sg_gap_pin_needed(1, 1, False, 6, 1, 200.0, 579.0))
        self.assertTrue(sg_gap_pin_needed(1, 0, False, 6, 1, 200.0, 300.0))
        # 气 <300 → 不钉
        self.assertFalse(sg_gap_pin_needed(1, 1, False, 6, 1, 200.0, 299.9))
        # SG ≥2 且有空闲 → 不钉(空转出口只管单 SG)
        self.assertFalse(sg_gap_pin_needed(1, 2, False, 6, 2, 200.0, 579.0))
        # 舰队 ≥8 → 不钉(数量够了)
        self.assertFalse(sg_gap_pin_needed(1, 1, False, 8, 1, 200.0, 579.0))
        # FB 未落成 → 不钉
        self.assertFalse(sg_gap_pin_needed(0, 1, False, 6, 1, 200.0, 579.0))
        # 全忙路径不受气门影响(气 0 照钉,原语义不动)
        self.assertTrue(sg_gap_pin_needed(1, 2, True, 6, 2, 200.0, 0.0))

    def test_stargate_pin_retry_needed(self):
        # O370-⑤b:钉点 30s 未落成 → 重钉
        self.assertTrue(stargate_pin_retry_needed(794.0, 824.0, False))
        # 30s 内 → 不重钉
        self.assertFalse(stargate_pin_retry_needed(794.0, 823.9, False))
        # 已有实体/在途 → 销账不重钉
        self.assertFalse(stargate_pin_retry_needed(794.0, 900.0, True))
        # 无在途钉点簿记(pin_at=0)→ 不动
        self.assertFalse(stargate_pin_retry_needed(0.0, 900.0, False))

    def test_new_base_f2_cannon_floor(self):
        # O368-④a:新基地(落成 <120s)target 下限 1
        self.assertEqual(new_base_f2_cannon_floor(59.9, 0), 1)
        self.assertEqual(new_base_f2_cannon_floor(0.0, 0), 1)
        # target 已 ≥1 → 原值
        self.assertEqual(new_base_f2_cannon_floor(30.0, 3), 3)
        # 老基地(≥120s)→ 不动(o367b g3 稳态 target=0 外的常态)
        self.assertEqual(new_base_f2_cannon_floor(120.0, 0), 0)
        # 落成时刻未知 → 不动
        self.assertEqual(new_base_f2_cannon_floor(None, 0), 0)

    def test_nexus_pin_yield_clamp(self):
        # O368-④b:让位钳 max(1, target-1) —— 让位只减 1 座
        self.assertEqual(nexus_pin_yield_clamp(3), 2)
        self.assertEqual(nexus_pin_yield_clamp(5), 4)
        # 保底 1 座保命塔豁免于让位
        self.assertEqual(nexus_pin_yield_clamp(1), 1)
        self.assertEqual(nexus_pin_yield_clamp(0), 1)

    def test_new_base_no_cannon_alarm(self):
        # O368-④c:落成 ≥60s 零塔(就绪+在途皆 0)→ 告警
        self.assertTrue(new_base_no_cannon_alarm(60.0, 0, 0))
        self.assertTrue(new_base_no_cannon_alarm(450.0, 0, 0))  # o367b g2 档
        # 落成 <60s → 不告警(建造窗内)
        self.assertFalse(new_base_no_cannon_alarm(59.9, 0, 0))
        # 有就绪塔/在途塔 → 不告警
        self.assertFalse(new_base_no_cannon_alarm(60.0, 1, 0))
        self.assertFalse(new_base_no_cannon_alarm(60.0, 0, 1))
        # 落成时刻未知 → 不告警
        self.assertFalse(new_base_no_cannon_alarm(None, 0, 0))

    def test_fb_safe_anchor(self):
        # O366-①b:离斜坡口最远的带电空闲槽
        slots = [
            (10.0, 10.0, True, True),    # 带电空闲,离坡口近
            (40.0, 40.0, True, True),    # 带电空闲,离坡口最远
            (30.0, 30.0, True, False),   # 不带电 → 不选
            (50.0, 50.0, False, True),   # 被占 → 不选
        ]
        self.assertEqual(fb_safe_anchor(slots, (0.0, 0.0)), (40.0, 40.0))
        # 无带电空闲槽 → None(调用方退回默认落位)
        self.assertIsNone(
            fb_safe_anchor([(10.0, 10.0, True, False)], (0.0, 0.0))
        )
        self.assertIsNone(fb_safe_anchor([], (0.0, 0.0)))
        # O371-④(o370a g3 FB 整局悬空实证):occupied_fallback 降级
        # —— 无带电空闲槽时选带电非空闲槽(离坡口最远)
        occupied = [
            (10.0, 10.0, False, True),   # 带电被占,离坡口近
            (45.0, 45.0, False, True),   # 带电被占,离坡口最远
            (60.0, 60.0, True, False),   # 空闲不带电 → 不选
        ]
        self.assertEqual(
            fb_safe_anchor(occupied, (0.0, 0.0), occupied_fallback=True),
            (45.0, 45.0),
        )
        # 有带电空闲槽时 fallback 不改变原优选
        self.assertEqual(
            fb_safe_anchor(slots, (0.0, 0.0), occupied_fallback=True),
            (40.0, 40.0),
        )
        # 全开 fallback 仍无带电槽 → None
        self.assertIsNone(
            fb_safe_anchor(
                [(10.0, 10.0, True, False)], (0.0, 0.0),
                occupied_fallback=True,
            )
        )

    def test_expansion_defense_guard_active(self):
        # O371-①a(o370b 三局裸奔实证):分矿防御守卫去 zerg 门
        # zerg timing/rush 与原门完全一致(行为不变)
        self.assertTrue(expansion_defense_guard_active("zerg", "timing"))
        self.assertTrue(expansion_defense_guard_active("zerg", "rush"))
        self.assertFalse(expansion_defense_guard_active("zerg", "power"))
        # terran 全 build 生效(o370b 死因 = 本门)
        self.assertTrue(expansion_defense_guard_active("terran", "power"))
        self.assertTrue(expansion_defense_guard_active("terran", "timing"))
        # protoss/未知无证据,不放宽
        self.assertFalse(expansion_defense_guard_active("protoss", "timing"))
        self.assertFalse(expansion_defense_guard_active("", ""))

    def test_timing_defense_chain_active(self):
        # O371-①b/c:O329 预置塔链/O333 forge/O349 看门狗/O338 GW2 的门
        # zerg timing 与原门一致;zerg rush 不放宽(原门本就不含)
        self.assertTrue(timing_defense_chain_active("zerg", "timing"))
        self.assertFalse(timing_defense_chain_active("zerg", "rush"))
        # terran 全 build 生效(forge 168-217s/GW2 静默是 o370b 共犯)
        self.assertTrue(timing_defense_chain_active("terran", "power"))
        self.assertTrue(timing_defense_chain_active("terran", "timing"))
        self.assertFalse(timing_defense_chain_active("protoss", "timing"))

    def test_push_enemy_army_gate(self):
        # O371-② + O373-⑥:敌可见 supply ≤ 我方 ×1.0(O373-⑥ 由
        # ×1.5 收紧,兼任 O302 出发闸)且 敌硬对空 <4 才推
        # o370b g3 档:fleet=4(army ~20)撞敌 47 supply → 否决
        self.assertFalse(push_enemy_army_gate(20.0, 47.0, 0))
        # O373-⑥(o372a g1 档):own 40 撞敌 47 —— ×1.5 旧闸放行
        # (47≤60)顶波出击,×1.0 新闸否决(47>40)
        self.assertFalse(push_enemy_army_gate(40.0, 47.0, 3))
        # 量级达标(敌 ≤ 我)+ 对空稀薄 → 放行
        self.assertTrue(push_enemy_army_gate(47.0, 47.0, 3))
        # o370b g2 档:敌 11 维京 vs 我 5 风暴 → 对空闸否决
        self.assertFalse(push_enemy_army_gate(40.0, 30.0, 11))
        self.assertFalse(push_enemy_army_gate(40.0, 30.0, 4))
        # 敌可见 0(被榨干/迷雾收割)→ 自然过闸
        self.assertTrue(push_enemy_army_gate(10.0, 0.0, 0))

    def test_cyber_core_np_default_fallback(self):
        # O371-⑤:首次 no_placement 先换锚(不回退),连续 ≥2 次才
        # 走 O369-④ 默认 placement 回退(o370a g3 不换锚死等档)
        self.assertFalse(cyber_core_np_default_fallback(0))
        self.assertFalse(cyber_core_np_default_fallback(1))
        self.assertTrue(cyber_core_np_default_fallback(2))
        self.assertTrue(cyber_core_np_default_fallback(5))
        # 自定义阈
        self.assertTrue(cyber_core_np_default_fallback(1, threshold=1))

    def test_f2_survival_floor(self):
        # O372-①a:注册下限+主基兜底 —— 零塔(就绪+在途皆 0)且
        # target=0 → 下限 1(o371a g1 主基整局 0 塔/o371b g3 三矿
        # target=0 两度被拆档)
        self.assertEqual(f2_survival_floor(0, 0, 0), 1)
        # 有就绪塔 → 不动(回归常规纪律)
        self.assertEqual(f2_survival_floor(0, 1, 0), 0)
        # 有在途塔 → 不动(首塔已在路上,不重复征用);O373-②a
        # 收窄合同:第三参必须是「距本基 <15 格且派工工人存活」
        # 口径(_in_flight_near),全图在途/死亡工人残留条目不算
        self.assertEqual(f2_survival_floor(0, 0, 1), 0)
        # O373-②b:在途塔黄了(调用方清 tracker 后 in_flight=0)
        # → 当帧抬 1 补注册(o372 三局 7 次注册 target=0 档)
        self.assertEqual(f2_survival_floor(0, 0, 0), 1)
        # target >0 → 原值不动(常态/让位语义不变)
        self.assertEqual(f2_survival_floor(3, 0, 0), 3)
        self.assertEqual(f2_survival_floor(2, 2, 0), 2)

    def test_fb_latch_yields_first_cannon(self):
        # O372-①b:latch 互斥 —— 新矿首塔未立(任一落成新矿零塔)
        # → latch 让位(o371b g1 latch 431.5s 抽 500 压掉首塔窗档)
        self.assertTrue(fb_latch_yields_first_cannon(True))
        # 首塔已立(含在途)→ 不让位,latch 恢复常态
        self.assertFalse(fb_latch_yields_first_cannon(False))
        # O373-①b:资金冗余门 —— 矿 ≥400(塔100+FB300)时不让位,
        # 二者并行(o372a g3 矿300气522充足仍让位空转档)
        self.assertFalse(fb_latch_yields_first_cannon(True, 400.0))
        self.assertFalse(fb_latch_yields_first_cannon(True, 522.0))
        # 矿 <400 → 让位维持(首塔专款优先原语义)
        self.assertTrue(fb_latch_yields_first_cannon(True, 399.9))
        self.assertTrue(fb_latch_yields_first_cannon(True, 95.0))

    def test_fb_yield_deadlock_fuse(self):
        # O373-①a:熔断触发一 —— 让位持续 ≥60s(o372a g3 让位
        # 302.7/353.3/383.3s 循环空转、首塔 362s 立不起档)
        self.assertTrue(fb_yield_deadlock_fuse(300.0, 360.0, 0))
        # <60s → 不熔断(正常让位窗)
        self.assertFalse(fb_yield_deadlock_fuse(300.0, 359.9, 0))
        # 未在让位(None)→ 不熔断
        self.assertFalse(fb_yield_deadlock_fuse(None, 999.0, 0))
        # 熔断触发二 —— 首塔 survival 派工连续 no_placement ≥3
        # (g3「带电余=0→贴槽水晶」+「O337=no_placement」循环档)
        self.assertTrue(fb_yield_deadlock_fuse(None, 100.0, 3))
        self.assertTrue(fb_yield_deadlock_fuse(300.0, 310.0, 5))
        # 连击 <3 且让位 <60s → 不熔断
        self.assertFalse(fb_yield_deadlock_fuse(300.0, 310.0, 2))

    def test_pylon_rescue_pin_ok(self):
        # O373-①c:水晶自救冷却 —— 同基地 60s 内不重复钉(o372a g3
        # 水晶 8→30 根 ≈烧 2000 矿档)
        self.assertFalse(pylon_rescue_pin_ok(100.0, 159.9, 1000.0))
        self.assertTrue(pylon_rescue_pin_ok(100.0, 160.0, 1000.0))
        # 从未钉过(-9999)→ 放行(矿够时)
        self.assertTrue(pylon_rescue_pin_ok(-9999.0, 50.0, 500.0))
        # 矿专款下限:钉后矿 <300(即矿 <400)→ 不钉
        self.assertFalse(pylon_rescue_pin_ok(-9999.0, 50.0, 399.9))
        self.assertTrue(pylon_rescue_pin_ok(-9999.0, 50.0, 400.0))

    def test_fb_rebuild_latch_needed(self):
        # O372-②:重建触发 —— FB 曾落成+实体归零(被拆)+SG 就绪
        # → 直接 latch(o371b g2 重建 O110×3 no_money 空转 170s 档)
        self.assertTrue(fb_rebuild_latch_needed(True, 0, True))
        # 未落成过(首建)→ 走常态判据(fb_fund_latch_needed),不触发
        self.assertFalse(fb_rebuild_latch_needed(False, 0, True))
        # FB 实体在(含重建落成)→ 不触发;解除沿用
        # fb_bankrupt_cleared(实体>0 → True,既有判据)
        self.assertFalse(fb_rebuild_latch_needed(True, 1, True))
        self.assertTrue(fb_bankrupt_cleared(1, False))
        # SG 未就绪(FB 前置不齐)→ 不触发
        self.assertFalse(fb_rebuild_latch_needed(True, 0, False))

    def test_sg_power_reserve_needed(self):
        # O372-③:预立判定 —— 带电余=0 且有空闲槽 → 预立贴槽水晶
        # (o371b g2 SG 446s 带电余=0 卡到 490s/g3 429.9s 档)
        self.assertTrue(sg_power_reserve_needed(0, 12))
        self.assertTrue(sg_power_reserve_needed(0, 1))
        # 有带电槽 → 不预立(正常落位)
        self.assertFalse(sg_power_reserve_needed(1, 12))
        # 几何死槽(空闲余=0)→ 不预立(归 O357 换锚管)
        self.assertFalse(sg_power_reserve_needed(0, 0))
        # 簿记拿不到槽(99,99,-1)→ 不触发
        self.assertFalse(sg_power_reserve_needed(99, 99))

    def test_fb_latch_trigger_gated(self):
        # O373-③a:触发门 —— 单矿局(townhalls 含在建 <2)不触发
        # latch(o372b g3 387.3s latch 抽走 475 矿、二矿拖到 526.3s
        # 档);Nexus 开工(≥2)恢复常态
        self.assertFalse(fb_latch_trigger_gated(1))
        self.assertTrue(fb_latch_trigger_gated(2))
        self.assertTrue(fb_latch_trigger_gated(3))

    def test_fleet_collapse_clock_reset(self):
        # O373-④a:累计制清零 —— 回到 ≥2 持续 ≥15s 才清零(o372b
        # g1 短暂回到 2 艘重置 collapsed_since、70s 零补产档)
        self.assertTrue(fleet_collapse_clock_reset(100.0, 115.0))
        # 恢复 <15s(假恢复)→ 不清零,断档计时原样累计
        self.assertFalse(fleet_collapse_clock_reset(100.0, 114.9))
        # 未在恢复观察(None,仍 <2)→ 不清零
        self.assertFalse(fleet_collapse_clock_reset(None, 999.0))

    def test_zerg_aa_exemption_capped(self):
        # O373-⑤:zerg 豁免上限 —— commit 期可见腐化+大龙 ≥8
        # 即便 zerg 也撤蹲(o372b g1 撞 20 腐化+4 大龙团灭档)
        self.assertTrue(zerg_aa_exemption_capped(24))
        self.assertTrue(zerg_aa_exemption_capped(8))
        # <8 → 豁免维持(O302 黄金窗打法不变)
        self.assertFalse(zerg_aa_exemption_capped(7))
        self.assertFalse(zerg_aa_exemption_capped(0))

    def test_aa_peak_sticky(self):
        # O374-①:新峰值吸收并刷新时刻(o373b g2 峰 22@1129 档)
        self.assertEqual(aa_peak_sticky(1129.0, 22, 8, 1068.8), (22, 1129.0))
        # 峰值期内可见回落 → 粘滞不归零(13s 视野洞仍认 22)
        self.assertEqual(aa_peak_sticky(1142.0, 0, 22, 1129.0), (22, 1129.0))
        # 期内等于峰值 → 刷新时刻(持续见于视野)
        self.assertEqual(aa_peak_sticky(1150.0, 22, 22, 1129.0), (22, 1150.0))
        # 超 60s 未刷新 → 回落当帧值(粘滞衰减)
        self.assertEqual(aa_peak_sticky(1190.0, 3, 22, 1129.0), (3, 1190.0))
        # 超窗且当帧 0 → 归零
        self.assertEqual(aa_peak_sticky(1200.0, 0, 22, 1129.0), (0, 1200.0))

    def test_zerg_aa_credited(self):
        # O374-①:信用计入 —— 当帧 0 但粘滞峰 17 → 仍计 17
        # (o373b g2 腐化 1098.7s 离视野档)
        self.assertEqual(zerg_aa_credited(0, 17, False), 17)
        # 当帧更大 → 取当帧
        self.assertEqual(zerg_aa_credited(20, 17, False), 20)
        # 尖塔曾见 +2(与星港 +2 同教义)
        self.assertEqual(zerg_aa_credited(0, 17, True), 19)
        self.assertEqual(zerg_aa_credited(6, 4, True), 8)
        # 全无 → 0(豁免帽/撤蹲不误触发)
        self.assertEqual(zerg_aa_credited(0, 0, False), 0)

    def test_zerg_departure_floor_ok(self):
        # O374-②:zerg 宽下限 —— 敌可见 supply ≥ 我方 ×1.5 → 拦
        # (o373b g2 顶波出击档:我方 20 敌 46 → 不放行)
        self.assertFalse(zerg_departure_floor_ok(20.0, 46.0))
        self.assertFalse(zerg_departure_floor_ok(20.0, 30.0))
        # <1.5× → 放行(zerg 原豁免区间;黄金窗走 _force_push
        # 通道不过本闸,豁免天然保留)
        self.assertTrue(zerg_departure_floor_ok(20.0, 29.9))
        # 敌可见 0(被榨干/迷雾收割)→ 放行
        self.assertTrue(zerg_departure_floor_ok(20.0, 0.0))

    def test_transition_push_hold(self):
        # O375-①:三条件各态 —— ①threat 闸:无波不锁(o374a「留守
        # 保家」证伪:舰队全在家波照样穿)
        self.assertFalse(transition_push_hold(True, 0, 0, False))
        # ②FB 落成+有波+舰队 <5+主基塔 <2 → 守家不跟压
        # (o373a g1/g2 出击与抄家窗口重叠档)
        self.assertTrue(transition_push_hold(True, 4, 1, True))
        self.assertTrue(transition_push_hold(True, 0, 0, True))
        # 主基塔 ≥2 → 放行(新矿 0 塔不再全局锁死,o374a 锁死档)
        self.assertFalse(transition_push_hold(True, 4, 2, True))
        # ③fleet 释放线 5(对齐胜局配方 528.5s fleet=5 起推 ×29)
        self.assertFalse(transition_push_hold(True, 5, 0, True))
        # FB 未落成(真空前半段)→ 原闸不动
        self.assertFalse(transition_push_hold(False, 3, 0, True))

    def test_nexus_repin_afford_ok(self):
        # O374-③a:矿量门 —— 矿 <400 不派工(o373b g3 银行
        # 20-445 振荡、381.7s 唯一够 400 被吃掉档)
        self.assertFalse(nexus_repin_afford_ok(210.0))
        self.assertFalse(nexus_repin_afford_ok(399.0))
        # 够 400 → 派工(钉即开工,循环失去燃料)
        self.assertTrue(nexus_repin_afford_ok(400.0))
        self.assertTrue(nexus_repin_afford_ok(445.0))
        # O375-⑤a:forced(循环 ≥2 轮)免矿量门 —— no_money 封顶,
        # 驻点等钱成交不再原地空转(o374b g3 三轮 336→424s 档)
        self.assertTrue(nexus_repin_afford_ok(210.0, forced=True))
        self.assertTrue(nexus_repin_afford_ok(0.0, forced=True))
        # 非 forced 原口径不变
        self.assertFalse(nexus_repin_afford_ok(399.0, forced=False))

    def test_wave_cannon_floor_trigger(self):
        # O375-②:预警触发三态 —— ①信用 supply(含 60s remembered
        # 峰值)≥30 即触发,波进门前立塔(o374a 地板全在波进门后
        # 才抬档;当帧 0 但峰值 42 → 仍触发)
        self.assertTrue(wave_cannon_floor_trigger(42.0, "terran", 300.0))
        self.assertTrue(wave_cannon_floor_trigger(30.0, "zerg", 300.0))
        # ②terran t≥480 定时兜底(信用 0 也触发,o374a MM 波全部
        # 527s+ 到门档)
        self.assertTrue(wave_cannon_floor_trigger(0.0, "terran", 480.0))
        self.assertTrue(wave_cannon_floor_trigger(10.0, "terran", 812.6))
        # ③信用 <30 且(非 terran 或 t<480)→ 不触发(zerg 无定时
        # 档;terran 早窗不误抬)
        self.assertFalse(wave_cannon_floor_trigger(29.9, "zerg", 600.0))
        self.assertFalse(wave_cannon_floor_trigger(0.0, "terran", 479.9))

    def test_enemy_supply_credited(self):
        # O375-④:信用口径 —— 当帧 0 但 60s 粘滞峰 51 → 仍计 51
        # (o374b g2 commit 后 3-10s 敌 51-79 supply 显形档)
        self.assertEqual(enemy_supply_credited(0.0, 51.0), 51.0)
        # 当帧更大 → 取当帧
        self.assertEqual(enemy_supply_credited(79.0, 51.0), 79.0)
        # 全无 → 0(出发闸不误拦)
        self.assertEqual(enemy_supply_credited(0.0, 0.0), 0.0)

    def test_fb_latch_pin_afford_ok(self):
        # O375-③a:SG2 预扣 —— sg2_reserve=True 时攒矿口径改
        # 「存款 ≥FB+SG2 全款」(300+150/200+150),SG2 钉走后 latch
        # 仍能攒回 FB 全款,FB 不被饿死(o374b SG2 饿死档)
        self.assertFalse(fb_latch_pin_afford_ok(300.0, 200.0, True))
        self.assertFalse(fb_latch_pin_afford_ok(449.9, 350.0, True))
        self.assertTrue(fb_latch_pin_afford_ok(450.0, 350.0, True))
        self.assertTrue(fb_latch_pin_afford_ok(500.0, 400.0, True))
        # SG2 在途/落成 → 预扣自灭,恢复 300/200 原口径
        self.assertTrue(fb_latch_pin_afford_ok(300.0, 200.0, False))
        self.assertFalse(fb_latch_pin_afford_ok(299.9, 200.0, False))

    def test_sg2_pre_fb_pin_needed(self):
        # O375-③a:SG1 落成即钉 SG2(o373b 胜局 SG2@413.8s 配方)
        self.assertTrue(sg2_pre_fb_pin_needed(True, 1, 0))
        # SG 总数(含在途)≥2 → 不重复钉
        self.assertFalse(sg2_pre_fb_pin_needed(True, 2, 0))
        # FB 已落成 → 判据自灭,回归 O326-②/O369-⑥ 常态通道
        self.assertFalse(sg2_pre_fb_pin_needed(True, 1, 1))
        # SG1 未就绪 → 不钉
        self.assertFalse(sg2_pre_fb_pin_needed(False, 0, 0))

    def test_sg_prefb_voidray_fill(self):
        # O375-③b:pre-FB 闲置填充三态 —— ①就绪 SG 存在+FB 未落成
        # +虚空 <8 → 填充(o373b 胜局 12 虚空配方;60s 死锁门槛
        # 砍掉填充窗的 o374b 虚空峰 2/4/1 档)
        self.assertTrue(sg_prefb_voidray_fill(1, 0, 0))
        self.assertTrue(sg_prefb_voidray_fill(2, 0, 7))
        # ②cap 满(≥8)→ 停(留气给舰队接力)
        self.assertFalse(sg_prefb_voidray_fill(1, 0, 8))
        # ③FB 已落成/无就绪 SG → 自灭(正常产线接管)
        self.assertFalse(sg_prefb_voidray_fill(1, 1, 0))
        self.assertFalse(sg_prefb_voidray_fill(0, 0, 0))

    def test_fb_fund_second_base_gate(self):
        # O375-⑤b:FB/二矿硬序门 —— 二矿未开工(townhalls 含在建
        # <2)不开 FB 基金窗(o374a g1 FB 285s 抢在二矿 321s 前档;
        # 胜局钱序 221 二矿→309 FB);与 O373-③a latch 触发门同判据
        self.assertFalse(fb_latch_trigger_gated(1))
        self.assertTrue(fb_latch_trigger_gated(2))

    def test_wave_cannon_floor_active(self):
        # O374-④c:terran 全 build 开门(o373a 三局 35+ 窗口
        # 地板零触发档);zerg 原口径逐项等价
        self.assertTrue(wave_cannon_floor_active("terran", "power"))
        self.assertTrue(wave_cannon_floor_active("terran", ""))
        self.assertTrue(wave_cannon_floor_active("zerg", "timing"))
        self.assertTrue(wave_cannon_floor_active("zerg", "rush"))
        # zerg 非 timing/rush、protoss → 不开(无尸检证据)
        self.assertFalse(wave_cannon_floor_active("zerg", "macro"))
        self.assertFalse(wave_cannon_floor_active("protoss", "timing"))

    def test_f2_target_literal(self):
        # O374-⑤:字面收口 —— 在途豁免帧(就绪 0+在途 ≥1+
        # target=0)→ 字面抬 1 报在途(o373b 4 次 target=0 档)
        self.assertEqual(f2_target_literal(0, 0, 1), 1)
        # 已有塔 target=0 → 同样抬 1(零 target=0 成字面硬口径)
        self.assertEqual(f2_target_literal(0, 2, 0), 1)
        # 零塔基地 target=0 → 不动(归 f2_survival_floor 抬 1)
        self.assertEqual(f2_target_literal(0, 0, 0), 0)
        # target >0 → 原值不动
        self.assertEqual(f2_target_literal(3, 0, 1), 3)

    def test_carrier_transition_ready_enemy_triggered(self):
        # O374-④a:敌情挂钩 —— 敌地面 supply ≥35 提前转
        # (o373a 550-700s 舰队 2-6 艘对 MM 27-56 supply 档)
        self.assertTrue(
            carrier_transition_ready(520.0, 4, enemy_ground_supply=35.0)
        )
        # 坦克首现即转(调用方 latch)
        self.assertTrue(carrier_transition_ready(480.0, 3, tank_seen=True))
        # 敌情不足且未到点/到量 → 不转(旧判据逐项等价)
        self.assertFalse(
            carrier_transition_ready(520.0, 4, enemy_ground_supply=34.9)
        )
        self.assertFalse(carrier_transition_ready(520.0, 4))
        # 旧通道不受影响(到点/到量仍转)
        self.assertTrue(carrier_transition_ready(600.0, 3))
        self.assertTrue(carrier_transition_ready(450.0, 10))

    def test_fleet_rebuild_watchdog_needed(self):
        # O372-④:断档判定 —— 曾 ≥3 掉到 <2 持续 >60s+FB 就绪+
        # 空闲 SG → 强制补产(o371a g2 航母死后 200s 零补充档)
        self.assertTrue(
            fleet_rebuild_watchdog_needed(5, 1, 800.0, 861.0, True, 2)
        )
        # 断档 <60s → 不触发(正常战损补充期)
        self.assertFalse(
            fleet_rebuild_watchdog_needed(5, 1, 800.0, 859.9, True, 2)
        )
        # 未塌缩起点(None)→ 不触发
        self.assertFalse(
            fleet_rebuild_watchdog_needed(5, 1, None, 900.0, True, 2)
        )
        # 舰队 ≥2(重建中/未塌)→ 不触发
        self.assertFalse(
            fleet_rebuild_watchdog_needed(5, 2, 800.0, 900.0, True, 2)
        )
        # 峰值 <3(未成过型)→ 不触发(首舰前归既有产线管)
        self.assertFalse(
            fleet_rebuild_watchdog_needed(2, 0, 800.0, 900.0, True, 2)
        )
        # FB 未就绪(产线前置断)→ 不触发(FB 链优先,O372-②)
        self.assertFalse(
            fleet_rebuild_watchdog_needed(5, 0, 800.0, 900.0, False, 2)
        )
        # 无空闲就绪 SG → 不触发(产能在产即非断档)
        self.assertFalse(
            fleet_rebuild_watchdog_needed(5, 0, 800.0, 900.0, True, 0)
        )

    def test_push_commit_aa_retreat(self):
        # O372-⑤:重评触发 —— 可见硬对空 ≥4 → 撤蹲(o371a g2 维京
        # 20 架仍 commit 团灭档)
        self.assertTrue(push_commit_aa_retreat(4, False))
        self.assertTrue(push_commit_aa_retreat(20, False))
        # 3 架可见 → 不撤(carrier_push_safe 常态闸管)
        self.assertFalse(push_commit_aa_retreat(3, False))
        # remembered 星港预警 +2:2 架可见+星港曾见 → 越线撤蹲
        self.assertTrue(push_commit_aa_retreat(2, True))
        # 单星港(0 架可见)→ 预警不够撤蹲线,推进继续
        self.assertFalse(push_commit_aa_retreat(0, True))
        # 1 架可见+星港 → 3 < 4,不撤
        self.assertFalse(push_commit_aa_retreat(1, True))

    def test_fb_arrival_guard_active(self):
        # O366-①c:FB 在建 + 敌地面 >8 → 增防
        self.assertTrue(fb_arrival_guard_active(640.0, True, None, 9))
        # 敌地面 ≤8 → 不增防
        self.assertFalse(fb_arrival_guard_active(640.0, True, None, 8))
        # 落成后 60s 窗内 → 增防
        self.assertTrue(fb_arrival_guard_active(700.0, False, 642.9, 10))
        # 出窗 → 不增防
        self.assertFalse(fb_arrival_guard_active(703.0, False, 642.9, 10))
        # 无 FB 实体 → 不增防
        self.assertFalse(fb_arrival_guard_active(700.0, False, None, 20))

    def test_tempest_gas_dump_ok(self):
        # O366-②b + O367-③ 门槛三象限(舰队≥8 / SG≥2 / 航母≥1):
        # SG≥2 → 允许折现
        self.assertTrue(tempest_gas_dump_ok(400.0, 0, stargates=2, carriers=0))
        # 已有 ≥1 航母(单星门)→ 允许
        self.assertTrue(tempest_gas_dump_ok(600.0, 7, stargates=1, carriers=1))
        # 穷局(舰队<8、单星门、零航母)→ 不折现,保航母气和产能
        self.assertFalse(tempest_gas_dump_ok(1000.0, 0, stargates=1, carriers=0))
        self.assertFalse(tempest_gas_dump_ok(800.0, 3, stargates=1, carriers=0))
        # 气不够 → 不折现
        self.assertFalse(tempest_gas_dump_ok(399.9, 0, stargates=3, carriers=2))
        # 舰队达标(≥8)停止折现(数量够了,气留给航母接力)
        self.assertFalse(tempest_gas_dump_ok(1000.0, 8, stargates=3, carriers=2))

    def test_gas_stop_repull_action(self):
        # O366-②c:复拽动作映射 —— 载气卸货/未载气 smart/不在簿记不动
        self.assertEqual(gas_stop_repull_action(True, True), "return_resource")
        self.assertEqual(gas_stop_repull_action(True, False), "smart_mineral")
        self.assertEqual(gas_stop_repull_action(False, True), "none")
        self.assertEqual(gas_stop_repull_action(False, False), "none")

    def test_f2_clamp_supply_cap(self):
        # O366-③a:敌可见 supply >35 → 钳位上限 4;≤35 保持 2
        self.assertEqual(f2_clamp_supply_cap(42.0), 4)
        self.assertEqual(f2_clamp_supply_cap(35.1), 4)
        self.assertEqual(f2_clamp_supply_cap(35.0), 2)
        self.assertEqual(f2_clamp_supply_cap(0.0), 2)

    def test_zt_expand_reserve_exempt(self):
        # O366-④a:敌 supply >30 触发豁免,滞回 <20 恢复
        self.assertFalse(zt_expand_reserve_exempt(29.0, 300.0, False))
        self.assertTrue(zt_expand_reserve_exempt(31.0, 300.0, False))
        # 滞回:豁免后 supply 25(20-30 之间)仍豁免
        self.assertTrue(zt_expand_reserve_exempt(25.0, 300.0, True))
        # 降到 <20 恢复预留
        self.assertFalse(zt_expand_reserve_exempt(19.0, 300.0, True))
        # t>500 时间档恒豁免(599s 兵力={} 实证)
        self.assertTrue(zt_expand_reserve_exempt(0.0, 500.0, False))

    def test_spawn_pause_expand_reserve_exempt(self):
        # O366-④a:豁免期 expand_reserve 分支跳过(产线不停)
        _kw = dict(
            rebuild_nexus=False,
            expand_holding=True,
            is_zerg_timing=True,
            nexus_unstarted=1,
            minerals=100.0,
            nexus_price=400.0,
            enemy_supply=10.0,
            own_supply=29.0,
            ground_supply=20.0,
        )
        self.assertEqual(
            spawn_pause_reason(**_kw), "zerg_timing_expand_reserve"
        )
        self.assertIsNone(
            spawn_pause_reason(expand_reserve_exempt=True, **_kw)
        )

    def test_fleet_formed_release_rush(self):
        # O366-④b:实际舰队(TEMPEST+CARRIER)≥3 且评分达标才解除
        # (o365b g2 舰队=0 虚报 5 次实证)
        self.assertFalse(fleet_formed_release_rush(0, 20.0))   # 舰队=0 虚报
        self.assertFalse(fleet_formed_release_rush(2, 20.0))   # 舰队不足
        self.assertFalse(fleet_formed_release_rush(3, 14.9))   # 评分不足
        self.assertTrue(fleet_formed_release_rush(3, 15.0))

    def test_o380_rush_economy_release(self):
        self.assertTrue(rush_economy_release(15.0, 31, 260.0, 100.0))
        self.assertFalse(rush_economy_release(14.9, 31, 279.9, 100.0))
        self.assertTrue(rush_economy_release(14.9, 31, 280.0, 100.0))
        self.assertFalse(rush_economy_release(14.9, 40, 400.0, 100.0))
        self.assertFalse(rush_economy_release(14.9, 31, 400.0, None))

    def test_o380_probe_economy_hard_floor(self):
        self.assertTrue(probe_economy_hard_floor(21, 1))
        self.assertFalse(probe_economy_hard_floor(22, 1))
        self.assertTrue(probe_economy_hard_floor(39, 2))
        self.assertFalse(probe_economy_hard_floor(40, 2))

    def test_o380_terran_false_rush_release(self):
        self.assertTrue(
            terran_false_rush_release("terran", "unknown", 1, 0, 260.0)
        )
        self.assertFalse(
            terran_false_rush_release("terran", "unknown", 2, 0, 260.0)
        )
        self.assertFalse(
            terran_false_rush_release("terran", "rush", 1, 0, 260.0)
        )
        self.assertFalse(
            terran_false_rush_release("zerg", "unknown", 1, 0, 260.0)
        )

    def test_o380_gas_hard_stop_required(self):
        self.assertTrue(gas_hard_stop_required(True, False, False, False, False))
        self.assertTrue(gas_hard_stop_required(False, False, False, True, False))
        self.assertFalse(gas_hard_stop_required(True, True, True, True, True))
        self.assertFalse(gas_hard_stop_required(False, False, False, False, False))

    def test_o380_new_base_cannon_fund_needed(self):
        self.assertTrue(new_base_cannon_fund_needed(True, 0, 0))
        self.assertFalse(new_base_cannon_fund_needed(True, 0, 1))
        self.assertFalse(new_base_cannon_fund_needed(False, 0, 0))

    def test_o380_desperation_push_window(self):
        self.assertTrue(desperation_push_window(900.0, 2, 15.0))
        self.assertTrue(desperation_push_window(1200.0, 4, 20.0))
        self.assertFalse(desperation_push_window(899.9, 4, 20.0))
        self.assertFalse(desperation_push_window(900.0, 1, 20.0))
        self.assertFalse(desperation_push_window(900.0, 5, 20.0))
        self.assertFalse(desperation_push_window(900.0, 4, 14.9))

    def test_anchor_buildable(self):
        # O366-③c:2x2 足迹全可建 + 避让矿簇/气矿才放行
        import numpy as np

        grid = np.ones((10, 10), dtype=int)
        self.assertTrue(anchor_buildable(grid, 5.0, 5.0))
        # 足迹含不可建格 → 拒
        grid[4, 4] = 0
        self.assertFalse(anchor_buildable(grid, 5.0, 5.0))
        grid[4, 4] = 1
        # 越界 → 拒
        self.assertFalse(anchor_buildable(grid, 0.0, 0.0))
        self.assertFalse(anchor_buildable(grid, 10.0, 10.0))
        # 压矿簇(<2.5 格)→ 拒;拉开距离 → 放行
        self.assertFalse(anchor_buildable(grid, 5.0, 5.0, [(6.0, 5.0)]))
        self.assertTrue(anchor_buildable(grid, 5.0, 5.0, [(8.0, 5.0)]))

    def test_anchor_buildable_orientation(self):
        # O367-②:朝向锁定 —— sc2/ares 惯例 data_numpy[y, x](sc2
        # PixelMap reshape(size.y, size.x)、__getitem__[pos[1],pos[0]],
        # ares cy_can_place_structure placement_grid[y, x])。用非
        # 对称 mock grid:只在 [y=2, x=7] 置 0,锚 (7,2) 必拒、
        # 转置误读会看的 (2,7) 必须放行 —— 两个断言同真才证明
        # 索引方向与 sc2/ares 一致。
        import numpy as np

        grid = np.ones((10, 10), dtype=int)
        grid[2, 7] = 0  # [y, x]:点 (7,2) 的 2x2 足迹含 (7,2) 格
        self.assertFalse(anchor_buildable(grid, 7.5, 2.5))
        self.assertTrue(anchor_buildable(grid, 2.5, 7.5))

    def test_expand_exempt_zealot_only(self):
        # O367-④a:豁免激活 且 expand_holding 且 Nexus 钉点未开工
        # → 限叉(禁追猎等气耗单位,o366b g1 追猎抢航母气实证)
        self.assertTrue(expand_exempt_zealot_only(True, True, 1))
        # 未豁免 / 非持有期 / Nexus 已开工 → 常态产线不变
        self.assertFalse(expand_exempt_zealot_only(False, True, 1))
        self.assertFalse(expand_exempt_zealot_only(True, False, 1))
        self.assertFalse(expand_exempt_zealot_only(True, True, 0))

    def test_oracle_gas_yield(self):
        # O367-④b:航母<2 或气<300 → 先知让位(o366 三局各白吃
        # 150/150+37-43s 星门产能实证)
        self.assertTrue(oracle_gas_yield(0, 1000.0))   # 零航母
        self.assertTrue(oracle_gas_yield(1, 400.0))    # 航母<2
        self.assertTrue(oracle_gas_yield(3, 250.0))    # 气<300
        # 航母≥2 且气≥300 → 放行
        self.assertFalse(oracle_gas_yield(2, 300.0))

    def test_new_base_survival_cannon_ok(self):
        # O367-⑤a:落成新矿零塔(实体+在途)→ 首座保命塔豁免
        self.assertTrue(new_base_survival_cannon_ok(True, 0, 0))
        # 已有塔(含在途)→ 回归常规纪律
        self.assertFalse(new_base_survival_cannon_ok(True, 1, 0))
        self.assertFalse(new_base_survival_cannon_ok(True, 0, 1))
        # 在建 Nexus 走 O364-② 的 fb_fund 豁免,不走本闸
        self.assertFalse(new_base_survival_cannon_ok(False, 0, 0))

    def test_extra_stargate_minerals_ok(self):
        # O367-⑤b:矿 ≥150(SG 造价)才派工(o366b 矿<150 钉点
        # no_money 事件空转三次实证)
        self.assertTrue(extra_stargate_minerals_ok(150.0))
        self.assertFalse(extra_stargate_minerals_ok(149.9))

    def test_f2_wave_cannon_floor(self):
        # O367-⑤c:敌可见 supply >35 → F2 塔目标强制 ≥3(动态档
        # 作用窗错位六局零触发,改接到威胁窗)
        self.assertEqual(f2_wave_cannon_floor(42.0, 0), 3)
        self.assertEqual(f2_wave_cannon_floor(35.1, 1), 3)
        # 目标已高于地板 → 不压低
        self.assertEqual(f2_wave_cannon_floor(60.0, 5), 5)
        # ≤35 → 零变化
        self.assertEqual(f2_wave_cannon_floor(35.0, 0), 0)
        self.assertEqual(f2_wave_cannon_floor(0.0, 2), 2)


class TestO376Plans(unittest.TestCase):
    """O376(o375 双 lane 0/3 尸检)六项落地的纯函数单测。"""

    def test_zerg_sg_pin_lane_active(self):
        # O376-①a:SG/FB 钉点家族种族门 —— o375b 的「== "timing"
        # 单值门把 rush lane 关门外 290s」死代码修复;口径与
        # wave_cannon_floor_active 对齐(zerg timing/rush 开门)
        self.assertTrue(zerg_sg_pin_lane_active("zerg", "timing"))
        self.assertTrue(zerg_sg_pin_lane_active("zerg", "rush"))
        # zerg power/terran/protoss 无尸检证据 → 不开
        self.assertFalse(zerg_sg_pin_lane_active("zerg", "power"))
        self.assertFalse(zerg_sg_pin_lane_active("zerg", "macro"))
        self.assertFalse(zerg_sg_pin_lane_active("terran", "power"))
        self.assertFalse(zerg_sg_pin_lane_active("protoss", "timing"))
        self.assertFalse(zerg_sg_pin_lane_active("", ""))

    def test_protocol_matrix_reachability(self):
        # O376-①c 防再犯:bench 协议矩阵(zerg lane=timing/rush/
        # power、terran lane=power)× 关键闸可达性 —— 门 + 判据
        # 联合求值,断言协议内 lane 不被单值门关门外(O364-①/
        # O375-③ 同款前科)。
        matrix = [
            ("zerg", "timing"),
            ("zerg", "rush"),
            ("zerg", "power"),
            ("terran", "power"),
        ]
        # SG/FB 钉点家族:zerg timing/rush 可达,power/terran 不可达
        sg_gates = [
            lambda: sg2_pre_fb_pin_needed(True, 1, 0),
            lambda: sg_prefb_voidray_fill(1, 0, 0),
            lambda: sg_post_fb_fill(481.0, 541.0, 1, 200.0),
            lambda: sg_gap_pin_needed(1, 1, True, 4, 2, 200.0),
            lambda: stargate_pin_retry_needed(100.0, 131.0, False),
        ]
        for race, build in matrix:
            for gate in sg_gates:
                reachable = zerg_sg_pin_lane_active(race, build) and gate()
                if race == "zerg" and build in ("timing", "rush"):
                    self.assertTrue(reachable, f"{race}/{build} 应可达")
                else:
                    self.assertFalse(reachable, f"{race}/{build} 不应可达")
        # 波次塔地板:zerg timing/rush + terran 全 build 可达,
        # zerg power 不可达(无尸检证据)
        for race, build in matrix:
            floor_reachable = wave_cannon_floor_active(
                race, build
            ) and wave_cannon_floor_trigger(30.0, race, 500.0)
            if (race == "zerg" and build in ("timing", "rush")) or (
                race == "terran"
            ):
                self.assertTrue(floor_reachable, f"{race}/{build} 应可达")
            else:
                self.assertFalse(floor_reachable, f"{race}/{build} 不应可达")
        # 转型真空留守闸(terran lane 用):判据域内可达
        self.assertTrue(transition_push_hold(True, 4, 1, True))
        self.assertFalse(transition_push_hold(True, 5, 1, True))

    def test_blind_push_blocked(self):
        # O376-②:信用 supply=0(当帧可见+remembered 峰值全空)
        # → 盲推不推(o375a g1 撞 57→85 supply、o375b g2 commit
        # 后 0.3s 敌 37 supply 显形档);>0 → 放行(有情报才出击)
        self.assertTrue(blind_push_blocked(0.0))
        self.assertFalse(blind_push_blocked(0.1))
        self.assertFalse(blind_push_blocked(37.0))

    def test_supply_sticky_window_120(self):
        # O376-③:supply 峰值粘滞窗 60s→120s(对齐 Zerg Rush
        # 90-120s 波次节奏)—— 窗内(119.9s)峰值保持,超窗
        # (120.1s)回落当帧;AA 窗默认 60s 不动(已验证)
        peak, peak_at = aa_peak_sticky(100.0, 40, 0, -9999.0)
        self.assertEqual((peak, peak_at), (40, 100.0))
        # 120s 窗:119.9s 仍粘滞
        peak, peak_at = aa_peak_sticky(
            219.9, 0, peak, peak_at, window=120.0
        )
        self.assertEqual((peak, peak_at), (40, 100.0))
        # 120s 窗:120.1s 超窗回落当帧
        peak, peak_at = aa_peak_sticky(
            220.1, 0, peak, peak_at, window=120.0
        )
        self.assertEqual((peak, peak_at), (0, 220.1))
        # AA 默认窗 60s 不变:60.1s 即回落
        peak, peak_at = aa_peak_sticky(100.0, 20, 0, -9999.0)
        peak, peak_at = aa_peak_sticky(160.1, 0, peak, peak_at)
        self.assertEqual((peak, peak_at), (0, 160.1))

    def test_f2_global_cannon_cap(self):
        # O376-④:FB 落成后全局帽 min(总塔 ≤14, 每基地 ≤4)
        # (o375b g2 塔峰 23 ≈3450 矿档)
        # FB 未落成 → 不钳(前期塔链原样)
        self.assertEqual(f2_global_cannon_cap(5, 5, 3, False, False), (5, 5))
        # threat/rush → 豁免(生死窗塔不设顶,O375-② 地板优先)
        self.assertEqual(f2_global_cannon_cap(5, 5, 3, True, True), (5, 5))
        # FB 落成+非威胁:3 基地主 5/分 5 → 主 4,余额 10 均摊 5
        # 取小 4 → (4,4),总 4+4×2=12 ≤14
        self.assertEqual(f2_global_cannon_cap(5, 5, 3, True, False), (4, 4))
        # 4 基地:主 4,余额 10//3=3 → (4,3),总 4+3×3=13 ≤14
        self.assertEqual(f2_global_cannon_cap(5, 5, 4, True, False), (4, 3))
        # O375-② 地板 3 存活:帽不压低地板(3 基地 (3,3) 原样)
        self.assertEqual(f2_global_cannon_cap(3, 3, 3, True, False), (3, 3))
        # 单基地:无分矿,只钳主基 per_base
        self.assertEqual(f2_global_cannon_cap(6, 0, 1, True, False), (4, 0))
        # 目标低于帽 → 不抬
        self.assertEqual(f2_global_cannon_cap(2, 1, 3, True, False), (2, 1))

    def test_push_fleet_floor_ok(self):
        # O376-⑤:出击舰队下限 4→6(o375b g2 两次 fleet=4 无果+撞波档)
        # O377-①a:下限 6→5 —— floor 6 封杀 o373a 胜局配方首推
        # (528.5s fleet=5 起推 ×29),o376a 首推推迟到 708-776s 实证;
        # O377-④ 起入参为在场口径(在产/队列虚高剔除,g3 报 6 实 3 档)
        self.assertFalse(push_fleet_floor_ok(4))
        self.assertTrue(push_fleet_floor_ok(5))
        self.assertTrue(push_fleet_floor_ok(6))
        self.assertTrue(push_fleet_floor_ok(8))
        # 显式 floor 参数不受默认值调整影响(黄金窗/其它调用方)
        self.assertFalse(push_fleet_floor_ok(5, floor=6))
        self.assertTrue(push_fleet_floor_ok(6, floor=6))

    def test_recipe_push_exempt(self):
        # O377-①b(o376a 三局 0/3 尸检):配方推豁免 —— t∈[500,570]
        # 且在场舰队 ≥5 且主基就绪塔 ≥2 的 terran 局豁免盲推闸
        # (o373a 胜局配方 528.5s fleet=5 首推档)
        self.assertTrue(recipe_push_exempt(528.5, 5, 2, "terran"))
        # 窗口边界:500/570 含端点,499.9/570.1 不豁免
        self.assertTrue(recipe_push_exempt(500.0, 5, 2, "terran"))
        self.assertTrue(recipe_push_exempt(570.0, 5, 2, "terran"))
        self.assertFalse(recipe_push_exempt(499.9, 5, 2, "terran"))
        self.assertFalse(recipe_push_exempt(570.1, 5, 2, "terran"))
        # 舰队不足/主基塔不足 → 不豁免(盲推闸照常闭)
        self.assertFalse(recipe_push_exempt(528.5, 4, 2, "terran"))
        self.assertFalse(recipe_push_exempt(528.5, 5, 1, "terran"))
        # zerg lane 恒不豁免(信用不断链,zerg 行为一行不变)
        self.assertFalse(recipe_push_exempt(528.5, 5, 2, "zerg"))
        self.assertFalse(recipe_push_exempt(528.5, 5, 2, "protoss"))

    def test_scout_credit_fallback_ok(self):
        # O377-①c(o376a 尸检):terran t≥480 且信用 supply=0 → 侦查
        # 前出刷信用;信用 >0/未到点/非 terran 不触发
        self.assertTrue(scout_credit_fallback_ok(480.0, 0.0, "terran"))
        self.assertTrue(scout_credit_fallback_ok(546.0, 0.0, "terran"))
        self.assertFalse(scout_credit_fallback_ok(479.9, 0.0, "terran"))
        self.assertFalse(scout_credit_fallback_ok(480.0, 0.1, "terran"))
        self.assertFalse(scout_credit_fallback_ok(480.0, 37.0, "terran"))
        self.assertFalse(scout_credit_fallback_ok(480.0, 0.0, "zerg"))

    def test_carrier_transition_time_box(self):
        # O377-②(o376a 三局 0/3 尸检):vs Terran 时间盒 —— FB 落成
        # +150s 转(对齐胜局配方 FB~300s+150≈454s 首航母)、480s 硬顶
        # 兜底、坦克扳机不再是必要条件;非 terran 恒不转
        # FB 落成 300s:+149.9 不转,+150 转
        self.assertFalse(carrier_transition_time_box(449.9, 300.0, "terran"))
        self.assertTrue(carrier_transition_time_box(450.0, 300.0, "terran"))
        # FB 迟落(626s):480s 硬顶先触发,不等 FB+150
        self.assertTrue(carrier_transition_time_box(480.0, 626.0, "terran"))
        self.assertFalse(carrier_transition_time_box(479.9, 626.0, "terran"))
        # FB 未落成:480s 硬顶照转(坦克首现不再必要)
        self.assertTrue(carrier_transition_time_box(480.0, None, "terran"))
        self.assertFalse(carrier_transition_time_box(479.9, None, "terran"))
        # zerg/protoss 一行不动(原判据不管时间盒)
        self.assertFalse(carrier_transition_time_box(600.0, 300.0, "zerg"))
        self.assertFalse(carrier_transition_time_box(600.0, 300.0, "protoss"))

    def test_cannon_hard_cap_active(self):
        # O377-③(o376b 尸检):就绪塔总数全通道硬顶 18 —— 17 在顶内
        # (o376b 胜局配方不动),18/21 超顶(21 实证档被钳)
        self.assertFalse(cannon_hard_cap_active(0))
        self.assertFalse(cannon_hard_cap_active(17))
        self.assertTrue(cannon_hard_cap_active(18))
        self.assertTrue(cannon_hard_cap_active(21))

    def test_power_precheck_stalled(self):
        # O377-⑤(o376a 尸检):供电预检滞留 ≥30s → 并入 no_placement
        # 重试链(钉水晶后塔落点必须重试);None(未预检)不触发
        self.assertFalse(power_precheck_stalled(100.0, None))
        self.assertFalse(power_precheck_stalled(129.9, 100.0))
        self.assertTrue(power_precheck_stalled(130.0, 100.0))
        self.assertTrue(power_precheck_stalled(400.0, 100.0))

    def test_forge_rebuild_guarantee_ok(self):
        # O377-⑥(o376b g1 尸检):forge 缺失且塔链 tech_not_ready
        # 空转 ≥60s → critical 资金通道保底钉 FORGE(292s 空转档);
        # forge 在途/就绪、空转 <60s、无空转(None)不触发
        self.assertTrue(forge_rebuild_guarantee_ok(60.0, False))
        self.assertTrue(forge_rebuild_guarantee_ok(292.0, False))
        self.assertFalse(forge_rebuild_guarantee_ok(59.9, False))
        self.assertFalse(forge_rebuild_guarantee_ok(None, False))
        self.assertFalse(forge_rebuild_guarantee_ok(292.0, True))
        self.assertFalse(forge_rebuild_guarantee_ok(None, True))

    def test_sg_rebuild_cooldown_ok(self):
        # O376-⑥:O182 紧急重建星门 30s 冷却(o375a g2 一秒连发
        # 15 条档)—— 冷却期内不重注册,超期放行
        self.assertFalse(sg_rebuild_cooldown_ok(1260.0, 1259.0))
        self.assertFalse(sg_rebuild_cooldown_ok(1260.0, 1230.1))
        self.assertTrue(sg_rebuild_cooldown_ok(1260.0, 1230.0))
        self.assertTrue(sg_rebuild_cooldown_ok(1260.0, 0.0))


class TestO378Plans(unittest.TestCase):
    """O378(o377a Terran 1/3 + o377b Zerg Rush 0/3 尸检)六项修复的
    纯函数判据。"""

    def test_e10_sg2_pin_needed(self):
        # O378-②(o377a 三局尸检):E10 转型 latch 置位且 SG 总数 <2
        # → 钉点;SG≥2 判据自灭;latch 未置位(未转型)不钉
        self.assertTrue(e10_sg2_pin_needed(True, 0))
        self.assertTrue(e10_sg2_pin_needed(True, 1))
        self.assertFalse(e10_sg2_pin_needed(True, 2))
        self.assertFalse(e10_sg2_pin_needed(True, 3))
        self.assertFalse(e10_sg2_pin_needed(False, 1))

    def test_sg_prefb_voidray_fill_o378_cap(self):
        # O378-④(o377b g2 实证):zerg lane 调用方 cap=2 —— 1 艘还
        # 可填,2 艘即封顶(g2 填线 9 虚空 1350 气全灭档);默认
        # cap=8 的函数本体不动(O375-③b 旧断言不受影响)
        self.assertTrue(sg_prefb_voidray_fill(1, 0, 1, cap=2))
        self.assertFalse(sg_prefb_voidray_fill(1, 0, 2, cap=2))
        self.assertFalse(sg_prefb_voidray_fill(2, 0, 9, cap=2))

    def test_sg_post_fb_fill_voidray_cap(self):
        # O378-④:post-FB 填线虚空帽入判据 —— voidrays 0/1 可填,
        # 2 艘封顶(默认 voidray_cap=2);显式 cap 参数可调
        self.assertTrue(sg_post_fb_fill(481.0, 541.0, 1, 200.0, voidrays=0))
        self.assertTrue(sg_post_fb_fill(481.0, 541.0, 1, 200.0, voidrays=1))
        self.assertFalse(sg_post_fb_fill(481.0, 541.0, 1, 200.0, voidrays=2))
        self.assertTrue(
            sg_post_fb_fill(481.0, 541.0, 1, 200.0, voidrays=3, voidray_cap=4)
        )

    def test_departure_gate_credited_caliber(self):
        # O378-③(o377b g1 @870 实证):出击闸统一信用口径回归 —
        # — zerg_departure_floor_ok 吃 credited supply(当帧可见 ∪
        # 120s 粘滞峰值,enemy_supply_credited),与盲推闸/E9 同
        # 口径:当帧 10 但粘滞峰 76 → 信用 76,我方 40 supply 按
        # 当帧会放行(10<60),按信用拦(76≥60)
        credited = enemy_supply_credited(10.0, 76.0)
        self.assertEqual(credited, 76.0)
        self.assertTrue(zerg_departure_floor_ok(40.0, 10.0))   # 旧当帧口径会放行
        self.assertFalse(zerg_departure_floor_ok(40.0, credited))  # 信用口径拦

    def test_zerg_corruptor_departure_blocked(self):
        # O378-⑥a(o377b g1 实证):信用腐化 ≥4 → O302 不出击
        # (g1「塔冻结腐化≥4 舰队却出门」档);3 及以下原闸不动
        self.assertTrue(zerg_corruptor_departure_blocked(4))
        self.assertTrue(zerg_corruptor_departure_blocked(16))
        self.assertFalse(zerg_corruptor_departure_blocked(3))
        self.assertFalse(zerg_corruptor_departure_blocked(0))

    def test_force_push_corruptor_ok(self):
        # O379-①(o378b g1 尸检):_force_push 通道信用腐化闸 —
        # — fleet ≥ 信用腐化 ×1.5 才放行
        # g1 实证档:1770s 信用 18 vs fleet 13 → 拦(13 < 27)
        self.assertFalse(force_push_corruptor_ok(13, 18))
        # 信用 4 vs fleet 12 → 放(12 ≥ 6)
        self.assertTrue(force_push_corruptor_ok(12, 4))
        # 信用 0 = 无腐化情报 → 恒放行(旧语义不动)
        self.assertTrue(force_push_corruptor_ok(8, 0))
        # 边界:fleet 恰等于 信用×1.5 → 放
        self.assertTrue(force_push_corruptor_ok(9, 6))
        self.assertFalse(force_push_corruptor_ok(8, 6))
        # 黄金窗不受影响 = 调用方豁免(_golden_push 不过本闸,
        # zt_golden_window_push 自带腐化 ≤4 闸一行不动),本函数
        # 无黄金窗入参,语义上不接收该通道

    def test_aa_reeval_due(self):
        # O378-⑥b(o377b 三局团灭实证):30s 定期 + 新增腐化显形
        # ≥4 立即重评(28s 内舰队死在两次重评之间档)
        # ① 定期:距上次 ≥30s 即重评(原语义不动)
        self.assertTrue(aa_reeval_due(480.0, 449.9, 0, 0))
        self.assertFalse(aa_reeval_due(480.0, 470.0, 0, 0))
        # ② 立即:信用计数 ≥4 且较上次上升 → 不等 30s
        self.assertTrue(aa_reeval_due(480.0, 479.0, 4, 0))
        self.assertTrue(aa_reeval_due(480.0, 479.0, 9, 4))
        # 持平/下降/低于阈值不立即重评(粘滞不反复收放)
        self.assertFalse(aa_reeval_due(480.0, 479.0, 4, 4))
        self.assertFalse(aa_reeval_due(480.0, 479.0, 3, 4))
        self.assertFalse(aa_reeval_due(480.0, 479.0, 3, 0))

    def test_pylon_ring_fallback_anchor(self):
        # O378-⑤(o377b (130,26)/(130,50) 扇形全失败实证):扇形
        # 连败降级 —— 水晶旁扫描第一个可建 2x2;资源避让与全图
        # 不可建(→None)语义
        import numpy as np

        grid = np.ones((20, 20), dtype="uint8")
        # 水晶 (10,10) 旁最近可建点 = 水晶本体偏移 (0,0)
        ax, ay = pylon_ring_fallback_anchor(grid, [(10.0, 10.0)])
        self.assertEqual((ax, ay), (10.0, 10.0))
        # 水晶本体不可建(压资源)→ 跳到环带次近点
        ax2, ay2 = pylon_ring_fallback_anchor(
            grid, [(10.0, 10.0)], resource_xys=[(10.0, 10.0)]
        )
        self.assertIsNotNone((ax2, ay2))
        self.assertGreater(abs(ax2 - 10.0) + abs(ay2 - 10.0), 0)
        # 多水晶:近水晶 2x2 足迹不可建 → 退到次近可建点/下一根
        grid2 = np.ones((20, 20), dtype="uint8")
        grid2[9, 9] = 0
        grid2[10, 10] = 0
        grid2[9, 10] = 0
        grid2[10, 9] = 0
        ax3, ay3 = pylon_ring_fallback_anchor(grid2, [(10.0, 10.0), (4.0, 4.0)])
        self.assertIsNotNone((ax3, ay3))
        # 全图不可建 → None(调用方维持重试簿记)
        self.assertIsNone(
            pylon_ring_fallback_anchor(np.zeros((20, 20), dtype="uint8"), [(10.0, 10.0)])
        )

    def test_tower_sector_fallback_due(self):
        # O379-③(o378b g2/g3 尸检):重试计数降级 —— 重试 2 次走
        # 扇形、3 次跳扇形走水晶旁 2x2 扫描(g2/g3 第 5/6 次仍扇形
        # 打转档)
        self.assertFalse(tower_sector_fallback_due(0))
        self.assertFalse(tower_sector_fallback_due(2))
        self.assertTrue(tower_sector_fallback_due(3))
        self.assertTrue(tower_sector_fallback_due(6))
        # 自定义阈
        self.assertFalse(tower_sector_fallback_due(4, threshold=5))
        self.assertTrue(tower_sector_fallback_due(5, threshold=5))


class TestO381Plans(unittest.TestCase):
    """O381:首扩硬基金、分矿恢复基金、健康矿区驱动扩张。"""

    def test_nexus_priority_fund_first_expand_deadline(self):
        self.assertIsNone(nexus_priority_fund_active(219.9, 1, 1, 6))
        self.assertEqual(
            nexus_priority_fund_active(220.0, 1, 1, 6), "first_expand"
        )
        # Nexus 实体出现（含在建）后 current_bases=2，基金成交自灭。
        self.assertIsNone(nexus_priority_fund_active(280.0, 2, 2, 6))
        # 未配置动态扩张/目标仅一矿不介入。
        self.assertIsNone(nexus_priority_fund_active(999.0, 1, 1, None))
        self.assertIsNone(nexus_priority_fund_active(999.0, 1, 1, 1))

    def test_nexus_priority_fund_lost_base(self):
        self.assertEqual(
            nexus_priority_fund_active(500.0, 2, 3, 6), "lost_base"
        )
        self.assertEqual(
            nexus_priority_fund_active(500.0, 1, 3, 6), "lost_base"
        )
        self.assertIsNone(nexus_priority_fund_active(500.0, 3, 3, 6))
        # 0 基地交 Q4 数学可行性重建路径，避免双通道。
        self.assertIsNone(nexus_priority_fund_active(500.0, 0, 3, 6))

    def test_nexus_fund_probe_hard_floor(self):
        # 首扩基金不再追 22 农；先用 16 农把 Nexus 的 400 矿攒出来。
        self.assertTrue(nexus_fund_probe_hard_floor(15, "first_expand"))
        self.assertFalse(nexus_fund_probe_hard_floor(16, "first_expand"))
        self.assertFalse(nexus_fund_probe_hard_floor(21, "first_expand"))
        # 分矿损失后更严格：31/39 农都不能继续追 40，只有濒死经济补火种。
        self.assertTrue(nexus_fund_probe_hard_floor(11, "lost_base"))
        self.assertFalse(nexus_fund_probe_hard_floor(12, "lost_base"))
        self.assertFalse(nexus_fund_probe_hard_floor(39, "lost_base"))
        self.assertFalse(nexus_fund_probe_hard_floor(0, None))

    def test_nexus_fund_should_cut_build_runner(self):
        self.assertTrue(nexus_fund_should_cut_build_runner(True, False))
        self.assertFalse(nexus_fund_should_cut_build_runner(True, True))
        self.assertFalse(nexus_fund_should_cut_build_runner(False, False))

    def test_healthy_mining_base_target(self):
        self.assertEqual(healthy_mining_base_target(44), 2)
        self.assertEqual(healthy_mining_base_target(45), 3)
        self.assertEqual(healthy_mining_base_target(70), 3)

    def test_mineral_patch_worker_slots(self):
        self.assertEqual(mineral_patch_worker_slots(8), 16)
        self.assertEqual(mineral_patch_worker_slots(7), 14)
        self.assertEqual(mineral_patch_worker_slots(0), 0)
        self.assertEqual(mineral_patch_worker_slots(-2), 0)

    def test_healthy_mining_expand_needed(self):
        base = dict(
            bases=3,
            max_bases=6,
            nexus_pending=0,
            workers=60,
        )
        # 3 矿名义经济但只有 1/2 片健康矿区 → 提前四矿。
        self.assertTrue(
            healthy_mining_expand_needed(healthy_ready_bases=1, **base)
        )
        self.assertTrue(
            healthy_mining_expand_needed(healthy_ready_bases=2, **base)
        )
        self.assertFalse(
            healthy_mining_expand_needed(healthy_ready_bases=3, **base)
        )
        # 在建基地不能叠加；到 max_bases 停；一矿由首扩基金负责。
        self.assertFalse(
            healthy_mining_expand_needed(
                healthy_ready_bases=1, nexus_pending=1,
                bases=3, max_bases=6, workers=60,
            )
        )
        self.assertFalse(
            healthy_mining_expand_needed(
                healthy_ready_bases=0, nexus_pending=0,
                bases=6, max_bases=6, workers=70,
            )
        )
        self.assertFalse(
            healthy_mining_expand_needed(
                healthy_ready_bases=0, nexus_pending=0,
                bases=1, max_bases=6, workers=22,
            )
        )

    def test_terran_economic_strike_window(self):
        base = dict(
            opp_race="terran",
            now=900.0,
            fleet_count=12,
            visible_enemy_air_combat=0,
            visible_hard_aa=0,
            known_enemy_bases=3,
        )
        self.assertTrue(terran_economic_strike_window(**base))
        self.assertFalse(
            terran_economic_strike_window(
                **{**base, "visible_enemy_air_combat": 1}
            )
        )
        self.assertFalse(
            terran_economic_strike_window(**{**base, "visible_hard_aa": 1})
        )
        self.assertFalse(
            terran_economic_strike_window(**{**base, "known_enemy_bases": 1})
        )
        self.assertFalse(
            terran_economic_strike_window(**{**base, "fleet_count": 7})
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
