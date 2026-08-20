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


def _enemy(tag, type_id, pos=None):
    return SimpleNamespace(
        tag=tag, type_id=type_id, position=pos or Point2((150.0, 150.0)),
        is_structure=False, is_flying=True,
    )


def _estruct(type_id, pos):
    """敌建筑假件(默认追敌分支的目标 + O372-⑤ 星港预警遍历源)。"""
    return SimpleNamespace(type_id=type_id, position=pos, is_structure=True)


class TestCarrierPushGate(unittest.TestCase):
    """O44/O45:attack_target 推进闸 —— 优势+对空安全 → 推进;否则蹲锚点。"""

    def _fake(self, own_carriers, enemies, enemy_supply):
        th = SimpleNamespace(position=MAIN, tag=1)
        ai = SimpleNamespace(
            steer_order={},
            start_location=MAIN,
            townhalls=[th],
            ready_townhalls=[th],
            structures=SimpleNamespace(ready=[]),
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
            ),
        )
        counts = {UnitID.CARRIER: own_carriers}
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
            manager_mediator=SimpleNamespace(
                get_own_unit_count=lambda unit_type_id: counts.get(unit_type_id, 0)
            ),
        )
        return mgr

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
