"""combat_manager.attack_target 的 O44/O45 推进闸单测 —— 不起游戏,假 ai 验证。

O45 实证教训(o51 game_01):O44/O45 分支里裸写类常量 `_HARD_AA`(漏 self.),
敌非建筑单位可见时每帧 NameError,游戏冻死而单测全绿 —— 本测试直接调用
attack_target 属性,专治这类"分支里名字写错"。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_push_gate -v
"""
import os
import sys
import unittest
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path[:0] = [
    os.path.join(_ROOT, "ares-sc2", "src", "ares"),
    os.path.join(_ROOT, "ares-sc2", "src"),
    os.path.join(_ROOT, "ares-sc2"),
    _ROOT,
]

from sc2.ids.unit_typeid import UnitTypeId as UnitID  # noqa: E402
from sc2.data import Race  # noqa: E402
from sc2.position import Point2  # noqa: E402

from bot.managers.combat_manager import CombatManager  # noqa: E402

MAIN = Point2((20.0, 20.0))


class _StructList(list):
    """enemy_structures 假件 —— 可迭代(sc2 Units 同接口,O372-⑤
    星港预警要遍历)且带 closest_to(默认追敌分支要调用)。"""

    def __init__(self, items=(), closest=None):
        super().__init__(items)
        self._closest = closest

    def closest_to(self, p):
        return self._closest


class _OwnStructList(list):
    """我方 structures 假件 —— 可迭代且带 .ready(主基就绪塔口径
    /O377-③ 就绪塔总数硬账要读;O377-④ 起舰队口径只算在场,
    不再遍历在产订单)。"""

    def __init__(self, items=(), ready=()):
        super().__init__(items)
        self.ready = list(ready)


def _enemy(tag, type_id, pos=None, is_flying=True):
    return SimpleNamespace(
        tag=tag, type_id=type_id, position=pos or Point2((150.0, 150.0)),
        is_structure=False, is_flying=is_flying,
    )


def _estruct(type_id, pos):
    """敌建筑假件(默认追敌分支的目标 + O372-⑤ 星港预警遍历源)。"""
    return SimpleNamespace(type_id=type_id, position=pos, is_structure=True)


class TestCarrierPushGate(unittest.TestCase):
    """O44/O45:attack_target 推进闸 —— 优势+对空安全 → 推进;否则蹲锚点。"""

    def _fake(self, own_carriers, enemies, enemy_supply, pending_carriers=0):
        th = SimpleNamespace(position=MAIN, tag=1)
        ai = SimpleNamespace(
            steer_order={},
            start_location=MAIN,
            townhalls=[th],
            ready_townhalls=[th],
            structures=_OwnStructList(),
            race=Race.Protoss,
            enemy_units=list(enemies),
            enemy_structures=_StructList(),
            enemy_race=SimpleNamespace(name="Zerg"),
            supply_used=120.0,
            supply_workers=60.0,
            supply_cap=200,
            time=480.0,  # 默认 8 分钟 → O164 强制推进不触发(旧断言不受影响)
            minerals=0,  # 默认无存款 → O70 全攻不触发(旧断言不受影响)
            production_manager=SimpleNamespace(
                _rush_active=False,
                _primary_unit_id=lambda: UnitID.CARRIER,
                _visible_enemy_army_supply=lambda: enemy_supply,
                # O375-④:出发闸改信用口径(max(当帧可见, 60s 粘滞
                # 峰值));夹具无迷雾,信用值=当帧可见
                _enemy_army_supply_credited=lambda: enemy_supply,
                _defense_score=lambda: 20.0,
            ),
        )
        counts = {UnitID.CARRIER: own_carriers}
        # O378-①:在产/队列挂独立口径 —— include_pending=True(默认)
        # 才加算;False(出击口径)只数在场
        pending = {UnitID.CARRIER: pending_carriers}
        mgr = SimpleNamespace(
            ai=ai,
            _flow=SimpleNamespace(name="carrier", pre_fleet=None),
            _defend_anchor=lambda: MAIN,
            _hot_base_anchor=lambda min_threat=6: None,  # O63:单基地默认无热点
            _HARD_AA=CombatManager._HARD_AA,
            # O372-⑤:commit 期 AA 重评簿记(30s 重评时刻+撤蹲旗标)
            _o372_aa_eval_at=0.0,
            _o372_aa_retreat=False,
            # O374-①:zerg AA 信用记忆簿记(60s 粘滞峰值)
            _o374_aa_peak=0,
            _o374_aa_peak_at=-9999.0,
            # O378-⑥b:AA 重评信用计数快照(显形即重评的比较基准)
            _o378_aa_last_credited=0,
            _o380_desperation_used=False,
            _o380_desperation_until=0.0,
            _o382_economic_strike_active=False,
            manager_mediator=SimpleNamespace(
                get_own_unit_count=lambda unit_type_id, include_pending=True: (
                    counts.get(unit_type_id, 0)
                    + (pending.get(unit_type_id, 0) if include_pending else 0)
                )
            ),
        )
        return mgr

    def test_o380_desperation_push_window(self):
        # t>=900、家防达标、仅 2-4 艘舰队时开一次 60s 豁命推进窗。
        mgr = self._fake(3, [], 150.0)
        mgr.ai.time = 900.0
        enemy_base = SimpleNamespace(position=Point2((150.0, 150.0)))
        mgr.ai.enemy_structures = _StructList(
            [_estruct(UnitID.HATCHERY, enemy_base.position)], closest=enemy_base
        )
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, enemy_base.position)
        self.assertTrue(mgr._push_committed)
        self.assertTrue(mgr._o380_desperation_used)
        self.assertEqual(mgr._o380_desperation_until, 960.0)

        # 窗结束后不续杯第二次。
        mgr.ai.time = 961.0
        target2 = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target2, MAIN)
        self.assertFalse(mgr._push_committed)

    def test_advantage_and_safe_pushes(self):
        # 60 army supply vs 敌可见 20(优势),2 腐化 < 14×1.5(安全) → 推进(走到默认追敌)
        mgr = self._fake(14, [_enemy(1, UnitID.CORRUPTOR)], 20.0)
        enemy_base = SimpleNamespace(position=Point2((150.0, 150.0)))
        mgr.ai.enemy_structures = _StructList(
            [_estruct(UnitID.HATCHERY, enemy_base.position)], closest=enemy_base
        )
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, enemy_base.position)  # 推进到敌建筑
        self.assertTrue(mgr._push_committed)  # O65:闸全开 → 推进承诺(行军模式)

    def test_terran_air_cleared_targets_outer_economy(self):
        # O382-④:维京/空中作战单位已清零，只剩坦克时，
        # 成型舰队跳过近处兵营，直接打最外围已知分矿断经济。
        tank = _enemy(10, UnitID.SIEGETANKSIEGED, is_flying=False)
        mgr = self._fake(12, [tank], 120.0)
        mgr.ai.time = 900.0
        mgr.ai.production_manager._opp_race = "terran"
        nearest = _estruct(UnitID.BARRACKS, Point2((80.0, 80.0)))
        mgr.ai.enemy_structures = _StructList([nearest], closest=nearest)
        known = [
            _estruct(UnitID.ORBITALCOMMAND, Point2((150.0, 150.0))),
            _estruct(UnitID.COMMANDCENTER, Point2((135.0, 125.0))),
            _estruct(UnitID.COMMANDCENTER, Point2((118.0, 105.0))),
        ]
        mgr._known_enemy_townhalls = lambda: known

        target = CombatManager.attack_target.fget(mgr)

        self.assertEqual(target, known[-1].position)
        self.assertTrue(mgr._push_committed)
        self.assertTrue(mgr._o382_economic_strike_active)

    def test_terran_visible_air_keeps_normal_targeting(self):
        mgr = self._fake(12, [_enemy(11, UnitID.LIBERATOR)], 20.0)
        mgr.ai.time = 900.0
        mgr.ai.production_manager._opp_race = "terran"
        nearest = _estruct(UnitID.BARRACKS, Point2((80.0, 80.0)))
        mgr.ai.enemy_structures = _StructList([nearest], closest=nearest)
        mgr._known_enemy_townhalls = lambda: [
            _estruct(UnitID.ORBITALCOMMAND, Point2((150.0, 150.0))),
            _estruct(UnitID.COMMANDCENTER, Point2((118.0, 105.0))),
        ]

        target = CombatManager.attack_target.fget(mgr)

        self.assertEqual(target, nearest.position)
        self.assertFalse(mgr._o382_economic_strike_active)

    def test_hard_aa_holds_fleet(self):
        # 30 腐化 ≥ 14×1.5 → 蹲锚点(主基,即便 supply 优势)
        enemies = [_enemy(100 + i, UnitID.CORRUPTOR) for i in range(30)]
        mgr = self._fake(14, enemies, 20.0)
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, MAIN)
        self.assertFalse(mgr._push_committed)

    def test_no_advantage_holds(self):
        # 敌可见 80 > 我方 60-15 → 蹲锚点
        mgr = self._fake(14, [], 80.0)
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, MAIN)
        self.assertFalse(mgr._push_committed)

    def test_hold_branch_recalls_with_low_threshold(self):
        # O64:蹲守分支(无优势)回防用默认阈值 6 —— 小队也要回防止血
        mgr = self._fake(14, [], 80.0)
        hot_pos = Point2((80.0, 80.0))
        calls = []
        mgr._hot_base_anchor = lambda min_threat=6: calls.append(min_threat) or hot_pos
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, hot_pos)
        self.assertEqual(calls, [6])

    def test_push_branch_recalls_only_on_main_force(self):
        # O64:推进分支(优势+安全)回防用高阈值 14 —— 小队骚扰不打断推进
        # (O113:舰队 <12 时阈值仍是 14)
        mgr = self._fake(10, [], 20.0)
        hot_pos = Point2((80.0, 80.0))
        calls = []
        mgr._hot_base_anchor = lambda min_threat=6: calls.append(min_threat) or hot_pos
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, hot_pos)  # 主力压境 → 召回
        self.assertEqual(calls, [14])
        self.assertFalse(mgr._push_committed)  # O65:召回 ≠ 推进承诺

    def test_push_branch_recall_threshold_raises_at_critical_mass(self):
        # O113-②(o112 局4 实证):舰队 ≥12(临界质量)→ 召回阈值 25,
        # 波次喂食(15-20/波)不打断推进,换家比回防快
        mgr = self._fake(27, [], 20.0)
        hot_pos = Point2((80.0, 80.0))
        calls = []
        mgr._hot_base_anchor = lambda min_threat=6: calls.append(min_threat) or hot_pos
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, hot_pos)
        self.assertEqual(calls, [25])

    def test_full_pop_all_in_pushes_despite_enemy_lead(self):
        # O70(司令观察):199/200+5000 存款 → 敌 supply 接近(130 vs
        # 我方 139,fleet=7 <8 时 advantage margin 15 不够)也推,
        # 跳过 supply 优势检查(full_pop 是唯一放行理由)。
        mgr = self._fake(7, [], 130.0)
        mgr.ai.supply_used = 199.0
        mgr.ai.minerals = 5000
        enemy_base = SimpleNamespace(position=Point2((150.0, 150.0)))
        mgr.ai.enemy_structures = _StructList(
            [_estruct(UnitID.HATCHERY, enemy_base.position)], closest=enemy_base
        )
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, enemy_base.position)
        self.assertTrue(mgr._push_committed)
        # O373-⑥(o372a g1 顶波出击实证):敌 150 > 我方 139 → 即便
        # 满人口全攻档也不出发(出发闸与 advantage/full_pop 合并
        # 单判,原 150 用例改判蹲守)
        mgr2 = self._fake(7, [], 150.0)
        mgr2.ai.supply_used = 199.0
        mgr2.ai.minerals = 5000
        target2 = CombatManager.attack_target.fget(mgr2)
        self.assertEqual(target2, MAIN)
        self.assertFalse(mgr2._push_committed)

    def test_full_pop_without_bank_still_holds(self):
        # O70:满人口但存款 <1500 → 不触发全攻(换不起血,维持优势判据)
        mgr = self._fake(20, [], 150.0)
        mgr.ai.supply_used = 199.0
        mgr.ai.minerals = 800
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, MAIN)
        self.assertFalse(mgr._push_committed)

    def test_full_pop_all_in_still_respects_hard_aa(self):
        # O70:全攻不豁免硬对空安全线 —— 30 腐化 ≥ 20×1.5 → 仍蹲
        enemies = [_enemy(100 + i, UnitID.CORRUPTOR) for i in range(30)]
        mgr = self._fake(20, enemies, 150.0)
        mgr.ai.supply_used = 199.0
        mgr.ai.minerals = 5000
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, MAIN)
        self.assertFalse(mgr._push_committed)

    def test_force_push_after_ten_minutes(self):
        # O164(o163c game_01 实证):10 暴风 + 2 航母,14:30 仍蹲家 timeout →
        # 舰队 ≥10 且时间 >10 分钟应强制推进,跳过 supply 优势检查。
        mgr = self._fake(12, [], 150.0)  # 敌 150 supply 大幅领先
        mgr.ai.supply_used = 157.0
        mgr.ai.supply_workers = 60.0
        mgr.ai.time = 870.0  # 14:30
        enemy_base = SimpleNamespace(position=Point2((150.0, 150.0)))
        mgr.ai.enemy_structures = _StructList(
            [_estruct(UnitID.HATCHERY, enemy_base.position)], closest=enemy_base
        )
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, enemy_base.position)
        self.assertTrue(mgr._push_committed)

    def test_force_push_before_ten_minutes_holds(self):
        # O164:舰队 ≥10 但时间未到 10 分钟 → 仍按原优势判据(无优势则蹲)
        mgr = self._fake(12, [], 150.0)
        mgr.ai.supply_used = 157.0
        mgr.ai.supply_workers = 60.0
        mgr.ai.time = 540.0  # 9 分钟
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, MAIN)
        self.assertFalse(mgr._push_committed)

    def test_force_push_respects_hard_aa(self):
        # O164:强制推进不豁免硬对空安全线 —— 30 腐化 ≥ 12×1.5 → 仍蹲
        enemies = [_enemy(100 + i, UnitID.CORRUPTOR) for i in range(30)]
        mgr = self._fake(12, enemies, 150.0)
        mgr.ai.supply_used = 157.0
        mgr.ai.supply_workers = 60.0
        mgr.ai.time = 870.0
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, MAIN)
        self.assertFalse(mgr._push_committed)

    def test_o372_commit_aa_reeval_retreats(self):
        # O372-⑤(o371a g2 维京 20 架仍 commit 团灭档):commit 期重评
        # 可见硬对空 ≥4 → 撤蹲(回蹲守锚点),即便 supply 优势+安全线
        # 内(6 架 < 14×1.5 过了 O45,但 ≥4 过不了重评)
        enemies = [_enemy(100 + i, UnitID.VIKINGFIGHTER) for i in range(6)]
        mgr = self._fake(14, enemies, 20.0)
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, MAIN)  # 撤蹲锚点(单基地=主基)
        self.assertFalse(mgr._push_committed)
        self.assertTrue(mgr._o372_aa_retreat)

    def test_o372_starport_warning_counts_toward_retreat(self):
        # O372-⑤:remembered 星港预警 +2 —— 2 架可见维京(未越线)
        # + 星港曾见 → 越线撤蹲;单星港(0 架可见)不撤
        sp = _estruct(UnitID.STARPORT, Point2((150.0, 150.0)))
        enemies = [_enemy(100 + i, UnitID.VIKINGFIGHTER) for i in range(2)]
        mgr = self._fake(14, enemies, 20.0)
        mgr.ai.enemy_structures = _StructList([sp])
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, MAIN)
        self.assertTrue(mgr._o372_aa_retreat)
        # 单星港无可见对空 → 预警不够撤蹲线,推进照常(优势局追敌)
        mgr2 = self._fake(14, [], 20.0)
        enemy_base = SimpleNamespace(position=Point2((150.0, 150.0)))
        mgr2.ai.enemy_structures = _StructList([sp], closest=enemy_base)
        target2 = CombatManager.attack_target.fget(mgr2)
        self.assertEqual(target2, enemy_base.position)
        self.assertFalse(mgr2._o372_aa_retreat)

    def test_o378_corruptor_hard_gate_blocks_departure(self):
        # O378-⑥a(o377b g1「塔冻结腐化≥4 舰队却出门」实证):zerg
        # lane 信用腐化(当帧 ∪ 粘滞)≥4 → O302 不出击,即便
        # supply 优势+安全线内(4 < 14×1.5 过 O45、20<60×1.5 过
        # 出发宽下限);3 腐化不触发,原闸不动
        pm_zerg = lambda mgr: setattr(  # noqa: E731
            mgr.ai.production_manager, "_opp_race", "zerg"
        )
        enemy_base = SimpleNamespace(position=Point2((150.0, 150.0)))
        # 4 腐化可见 → 硬闸拦(无本闸时上面各闸全放行 = 推进)
        mgr = self._fake(
            14, [_enemy(100 + i, UnitID.CORRUPTOR) for i in range(4)], 20.0
        )
        pm_zerg(mgr)
        mgr.ai.enemy_structures = _StructList(
            [_estruct(UnitID.HATCHERY, enemy_base.position)], closest=enemy_base
        )
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, MAIN)
        self.assertFalse(mgr._push_committed)
        # 3 腐化 → 不触发,推进照常
        mgr2 = self._fake(
            14, [_enemy(100 + i, UnitID.CORRUPTOR) for i in range(3)], 20.0
        )
        pm_zerg(mgr2)
        mgr2.ai.enemy_structures = _StructList(
            [_estruct(UnitID.HATCHERY, enemy_base.position)], closest=enemy_base
        )
        target2 = CombatManager.attack_target.fget(mgr2)
        self.assertEqual(target2, enemy_base.position)
        self.assertTrue(mgr2._push_committed)

    def test_o378_corruptor_hard_gate_uses_sticky_peak(self):
        # O378-⑥a:腐化离视野但 60s 粘滞峰仍 ≥4 → 同样拦(o377b
        # 「波在途中闸是瞎子」同谱系,信用口径与 O374-① 台账同源)
        mgr = self._fake(14, [], 20.0)
        mgr.ai.production_manager._opp_race = "zerg"
        mgr._o374_aa_peak = 5           # 5 腐化刚离视野
        mgr._o374_aa_peak_at = 480.0    # 峰值时刻=当帧(粘滞期内)
        enemy_base = SimpleNamespace(position=Point2((150.0, 150.0)))
        mgr.ai.enemy_structures = _StructList(
            [_estruct(UnitID.HATCHERY, enemy_base.position)], closest=enemy_base
        )
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, MAIN)
        self.assertFalse(mgr._push_committed)

    def test_o378_new_corruptors_trigger_immediate_reeval(self):
        # O378-⑥b(o377b「28s 内舰队死在两次重评之间」实证):新增
        # 腐化/硬对空显形 ≥4 → 不等 30s 立即重评撤蹲;计数未上升
        # 且 30s 未到 → 不重评(旗标粘滞不反复收放)
        enemies = [_enemy(100 + i, UnitID.VIKINGFIGHTER) for i in range(6)]
        # 距上次重评仅 0s(30s 定期未到)但 6 维京新显形 → 立即重评
        mgr = self._fake(14, enemies, 20.0)
        mgr._o372_aa_eval_at = 480.0
        mgr._o378_aa_last_credited = 0
        target = CombatManager.attack_target.fget(mgr)
        self.assertEqual(target, MAIN)
        self.assertTrue(mgr._o372_aa_retreat)
        self.assertEqual(mgr._o378_aa_last_credited, 6)  # 重评已快照
        # 对照:计数未上升(上次已 6)且 30s 未到 → 不重评不撤蹲
        mgr2 = self._fake(14, enemies, 20.0)
        mgr2._o372_aa_eval_at = 480.0
        mgr2._o378_aa_last_credited = 6
        CombatManager.attack_target.fget(mgr2)
        self.assertFalse(mgr2._o372_aa_retreat)
        self.assertEqual(mgr2._o372_aa_eval_at, 480.0)  # 重评未发生


class TestRecipePushGate(unittest.TestCase):
    """O377-①a/①b/④(o376a 三局 0/3 尸检):首推窗解锁的闸级线束 —
    — 在场口径舰队下限 5 + terran 配方推盲推闸豁免。"""

    def _fake_terran(self, own_carriers, main_cannons, t=528.5, pending_carriers=0):
        th = SimpleNamespace(position=MAIN, tag=1)
        cannons = [
            SimpleNamespace(
                type_id=UnitID.PHOTONCANNON,
                position=MAIN,
                is_ready=True,
            )
            for _ in range(main_cannons)
        ]
        ai = SimpleNamespace(
            steer_order={},
            start_location=MAIN,
            townhalls=[th],
            ready_townhalls=[th],
            structures=_OwnStructList(ready=cannons),
            race=Race.Protoss,
            enemy_units=[],
            enemy_structures=_StructList(),
            enemy_race=SimpleNamespace(name="Terran"),
            supply_used=120.0,
            supply_workers=60.0,
            supply_cap=200,
            time=t,
            minerals=0,
            production_manager=SimpleNamespace(
                _rush_active=False,
                _primary_unit_id=lambda: UnitID.CARRIER,
                _visible_enemy_army_supply=lambda: 0.0,
                # o376a 实证:terran lane 侦查断链,信用 supply 恒 0
                _enemy_army_supply_credited=lambda: 0.0,
                _opp_race="terran",
                _ai_build="power",
                _fb_completed_at=None,
                _threat_active=False,
            ),
        )
        counts = {UnitID.CARRIER: own_carriers}
        # O378-①:在产/队列挂独立口径(在场/含在产两种读法)
        pending = {UnitID.CARRIER: pending_carriers}
        return SimpleNamespace(
            ai=ai,
            _flow=SimpleNamespace(name="carrier", pre_fleet=None),
            _defend_anchor=lambda: MAIN,
            _hot_base_anchor=lambda min_threat=6: None,
            _HARD_AA=CombatManager._HARD_AA,
            _o372_aa_eval_at=0.0,
            _o372_aa_retreat=False,
            _o374_aa_peak=0,
            _o374_aa_peak_at=-9999.0,
            _o378_aa_last_credited=0,
            manager_mediator=SimpleNamespace(
                get_own_unit_count=lambda unit_type_id, include_pending=True: (
                    counts.get(unit_type_id, 0)
                    + (pending.get(unit_type_id, 0) if include_pending else 0)
                )
            ),
        )

    def _push_target(self, mgr):
        enemy_base = SimpleNamespace(position=Point2((150.0, 150.0)))
        mgr.ai.enemy_structures = _StructList(
            [_estruct(UnitID.COMMANDCENTER, enemy_base.position)],
            closest=enemy_base,
        )
        return CombatManager.attack_target.fget(mgr), enemy_base.position

    def test_recipe_push_exempts_blind_gate(self):
        # O377-①b:o373a 胜局配方首推档(528.5s 在场 fleet=5、主基
        # 2 就绪塔、信用 0)→ 豁免盲推闸,配方推放行
        mgr = self._fake_terran(5, 2)
        target, enemy_pos = self._push_target(mgr)
        self.assertEqual(target, enemy_pos)
        self.assertTrue(mgr._push_committed)

    def test_recipe_push_needs_main_cannons(self):
        # O377-①b:主基就绪塔 <2(裸推)→ 不豁免,盲推闸照常闭
        mgr = self._fake_terran(5, 1)
        target, _ = self._push_target(mgr)
        self.assertEqual(target, MAIN)
        self.assertFalse(mgr._push_committed)

    def test_recipe_push_needs_fleet_onfield(self):
        # O377-①a/④:在场舰队 4 < 下限 5(在产虚高不计)→ 不推;
        # 出窗(708s,o376a 被推迟的首推档)同样不豁免
        mgr = self._fake_terran(4, 2)
        target, _ = self._push_target(mgr)
        self.assertEqual(target, MAIN)
        self.assertFalse(mgr._push_committed)
        mgr2 = self._fake_terran(5, 2, t=708.0)
        target2, _ = self._push_target(mgr2)
        self.assertEqual(target2, MAIN)
        self.assertFalse(mgr2._push_committed)

    def test_o378_pending_not_counted_in_departure_caliber(self):
        # O378-①(o377b g2 @890 报 5 实 2 实证):O377-④ 假修复真
        #  bug —— get_own_unit_count 默认 include_pending=True,在
        # 产/队列虚高计入出击口径。在场 3+在产 2:含在产口径会报
        # 5(过下限豁免盲推闸 = 纸面舰队出门),修后按在场 3 拦;
        # 在场 5+在产 2 仍放行(不是一刀切欠数)
        mgr = self._fake_terran(3, 2, pending_carriers=2)
        target, _ = self._push_target(mgr)
        self.assertEqual(target, MAIN)
        self.assertFalse(mgr._push_committed)
        mgr2 = self._fake_terran(5, 2, pending_carriers=2)
        target2, enemy_pos = self._push_target(mgr2)
        self.assertEqual(target2, enemy_pos)
        self.assertTrue(mgr2._push_committed)


class TestHotBaseAnchor(unittest.TestCase):
    """O63:_hot_base_anchor —— 分矿被 ≥6 敌围攻 → 返回该分矿;否则 None。"""

    def _fake(self, threats_near_exp):
        exp = Point2((80.0, 80.0))
        ths = [SimpleNamespace(position=MAIN), SimpleNamespace(position=exp)]
        enemies = [
            _enemy(200 + i, UnitID.ROACH, pos=exp) for i in range(threats_near_exp)
        ]
        mgr = SimpleNamespace(
            ai=SimpleNamespace(
                start_location=MAIN,
                ready_townhalls=ths,
                enemy_units=enemies,
            ),
        )
        return mgr, exp

    def test_hot_expansion_returns_its_position(self):
        mgr, exp = self._fake(10)
        self.assertEqual(CombatManager._hot_base_anchor(mgr), exp)

    def test_below_threshold_returns_none(self):
        mgr, _ = self._fake(4)
        self.assertIsNone(CombatManager._hot_base_anchor(mgr))


if __name__ == "__main__":
    unittest.main(verbosity=2)
