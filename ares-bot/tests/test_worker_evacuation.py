"""E6 农民被抄转移/协防单测 —— 不起游戏,假 ai 验证判据与操作。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_worker_evacuation -v
"""
import os
import sys
import unittest
from collections import defaultdict
from types import SimpleNamespace

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
# bot.main 依赖 ares(本地子包),与 run.py 同样手动补 sys.path
sys.path[:0] = [
    os.path.join(_ROOT, "ares-sc2", "src", "ares"),
    os.path.join(_ROOT, "ares-sc2", "src"),
    os.path.join(_ROOT, "ares-sc2"),
    _ROOT,
]

from ares.consts import UnitRole  # noqa: E402
from sc2.ids.unit_typeid import UnitTypeId as UnitID  # noqa: E402
from sc2.position import Point2  # noqa: E402

from bot.main import (  # noqa: E402
    _EVAC_ROLE,
    release_contested_miners,
    update_worker_evacuation,
)
from bot.production_plans import (  # noqa: E402
    evacuation_clear,
    pick_evacuation_base,
    should_evacuate_workers,
    worker_last_stand,
    worker_transfer_count,
)

MAIN = Point2((20.0, 20.0))
NAT = Point2((60.0, 20.0))
THIRD = Point2((100.0, 20.0))


class TestWorkerLastStand(unittest.TestCase):
    """O256-①纯判据:worker_last_stand(主基决死协防)。"""

    def test_transfer_count_hysteresis(self):
        # O266(均衡化判据):主基 16 满 / 新矿 3 → 差 13,调 min(6,缺口13,4)=4
        self.assertEqual(worker_transfer_count(16, 16, 3, 16), 4)
        # 差 <4 不调(防往返)
        self.assertEqual(worker_transfer_count(16, 16, 13, 16), 0)
        self.assertEqual(worker_transfer_count(16, 16, 14, 16), 0)
        # 差额一半与缺口取小:差 4 → 半差 2(缺口 4 不封顶)
        self.assertEqual(worker_transfer_count(16, 16, 12, 16), 2)
        # 均衡点不调
        self.assertEqual(worker_transfer_count(16, 16, 16, 16), 0)
        # 源更少不调
        self.assertEqual(worker_transfer_count(10, 16, 14, 16), 0)

    def test_triggers_only_when_overwhelmed_single_base_with_cover(self):
        # o255b game_02 现场:20 敌地面(9蟑螂+11狗)、2 塔、单基地、rush → 触发
        self.assertTrue(worker_last_stand(20, 2, 1, True))
        # 压垮线 = 6+4×塔数:2 塔压垮线 14,13 不触发
        self.assertFalse(worker_last_stand(13, 2, 1, True))
        # 无塔可依 → 不触发(纯送死,交 keep_safe/E6 语义)
        self.assertFalse(worker_last_stand(20, 0, 1, True))
        # 多基地 → 不触发(E6 撤离更稳)
        self.assertFalse(worker_last_stand(20, 2, 2, True))
        # 非急性窗 → 不触发(不扰动运营)
        self.assertFalse(worker_last_stand(20, 2, 1, False))
        # 1 塔压垮线 10
        self.assertTrue(worker_last_stand(10, 1, 1, True))
        self.assertFalse(worker_last_stand(9, 1, 1, True))


class TestEvacuationCriteria(unittest.TestCase):
    """纯判据:should_evacuate_workers / evacuation_clear / pick_evacuation_base。"""

    def test_evacuate_only_when_no_cover_and_enemy_ge_threshold(self):
        self.assertTrue(should_evacuate_workers(4, cannon_cover=False))
        self.assertTrue(should_evacuate_workers(9, cannon_cover=False))
        self.assertFalse(should_evacuate_workers(4, cannon_cover=True, cannons_near=1))
        self.assertFalse(should_evacuate_workers(3, cannon_cover=False))  # 数量不够
        self.assertFalse(should_evacuate_workers(0, cannon_cover=False))

    def test_cannon_cover_overwhelmed_by_large_wave(self):
        # E6 bench 实证:塔覆盖≠安全——22 狗+9 蟑螂波 ~20s 拆光塔再屠农。
        # 覆盖上限 = 6 + 4×塔数:1 塔罩到 9,4 塔罩到 21
        self.assertFalse(should_evacuate_workers(9, True, cannons_near=1))   # 小股,塔罩得住
        self.assertTrue(should_evacuate_workers(10, True, cannons_near=1))   # 压垮 1 塔
        self.assertFalse(should_evacuate_workers(21, True, cannons_near=4))  # 4 塔罩得住
        self.assertTrue(should_evacuate_workers(22, True, cannons_near=4))   # 压垮 4 塔

    def test_clear_threshold_has_hysteresis(self):
        # 撤离阈值 4,回采判据 <2:3 个敌兵 = 不触发新撤离,也不放人回采
        self.assertTrue(evacuation_clear(1))
        self.assertTrue(evacuation_clear(0))
        self.assertFalse(evacuation_clear(2))
        self.assertFalse(evacuation_clear(3))

    def test_pick_target_prefers_cannon_covered_base(self):
        # 主基最近但无塔,三矿远但有塔 → 选三矿
        candidates = [(MAIN.x, MAIN.y, False), (THIRD.x, THIRD.y, True)]
        self.assertEqual(
            pick_evacuation_base((NAT.x, NAT.y), candidates),
            (THIRD.x, THIRD.y),
        )

    def test_pick_target_falls_back_to_nearest_when_no_cover(self):
        candidates = [(MAIN.x, MAIN.y, False), (THIRD.x, THIRD.y, False)]
        self.assertEqual(
            pick_evacuation_base((NAT.x, NAT.y), candidates),
            (MAIN.x, MAIN.y),
        )

    def test_pick_target_none_when_no_candidates(self):
        self.assertIsNone(pick_evacuation_base((NAT.x, NAT.y), []))


def _unit(tag, pos, type_id=UnitID.ZERGLING, structure=False, flying=False):
    return SimpleNamespace(
        tag=tag, position=pos, type_id=type_id,
        is_structure=structure, is_flying=flying,
    )


def _worker(tag, pos, idle=False):
    w = SimpleNamespace(tag=tag, position=pos, is_idle=idle, orders=[])
    w.move = lambda target, _w=w: _w.orders.append(("move", target))
    w.gather = lambda target, _w=w: _w.orders.append(("gather", target))
    return w


def _townhall(tag, pos, ready=True):
    return SimpleNamespace(tag=tag, position=pos, is_ready=ready)


def _fake_ai(
    townhalls,
    workers,
    enemies=(),
    structures=(),
    army=(),
    th_of_worker=None,
    rush=False,
):
    assigned: list[tuple[int, object]] = []
    role_dict = defaultdict(list)
    role_dict[UnitRole.GATHERING] = [w.tag for w in workers]

    def _assign(tag, role):
        assigned.append((tag, role))
        for tags in role_dict.values():
            if tag in tags:
                tags.remove(tag)
        role_dict[role].append(tag)

    mediator = SimpleNamespace(
        get_building_tracker_dict={},
        get_worker_tag_to_townhall_tag=th_of_worker or {},
        get_unit_role_dict=role_dict,
        assign_role=_assign,
    )
    ai = SimpleNamespace(
        townhalls=townhalls,
        workers=workers,
        units=list(army),
        enemy_units=list(enemies),
        structures=list(structures),
        mineral_field=SimpleNamespace(closest_to=lambda x: f"mf@{x.tag}"),
        mediator=mediator,
        production_manager=SimpleNamespace(rush_active=rush),
        _events=[],
        _player_ctrl={},
        _evac_bases={},
        time=500.0,
        start_location=MAIN,
    )
    return ai, assigned


class TestWorkerEvacuation(unittest.TestCase):
    """运行时 handler:撤离 → 途中维护 → 敌退回采 全链路。"""

    def _two_base_setup(self, enemies, structures=(), rush=False):
        ths = [_townhall(1, MAIN), _townhall(2, NAT)]
        workers = [_worker(101, NAT), _worker(102, NAT), _worker(103, MAIN)]
        th_of_worker = {101: 2, 102: 2, 103: 1}  # 101/102 采二矿,103 采主矿
        ai, assigned = _fake_ai(
            ths, workers, enemies, structures,
            th_of_worker=th_of_worker, rush=rush,
        )
        return ai, assigned, workers

    def test_raided_base_without_cannon_evacuates(self):
        enemies = [_unit(900 + i, NAT) for i in range(5)]
        ai, assigned, workers = self._two_base_setup(enemies)

        update_worker_evacuation(ai)

        # 二矿两个农民被撤离,主矿农民不动
        self.assertIn((101, _EVAC_ROLE), assigned)
        self.assertIn((102, _EVAC_ROLE), assigned)
        self.assertNotIn(103, [t for t, _ in assigned])
        # 撤离目标 = 主基(唯一候选),两个农民都拿到 move
        self.assertEqual(workers[0].orders, [("move", Point2((MAIN.x, MAIN.y)))])
        self.assertEqual(workers[1].orders, [("move", Point2((MAIN.x, MAIN.y)))])
        self.assertEqual(workers[2].orders, [])
        # 台账 + 事件
        self.assertIn(2, ai._evac_bases)
        self.assertEqual(ai._evac_bases[2]["workers"], {101, 102})
        self.assertTrue(any("撤离2农民" in e["msg"] for e in ai._events))

    def test_cannon_covered_base_keeps_mining(self):
        enemies = [_unit(900 + i, NAT) for i in range(6)]
        cannon = SimpleNamespace(
            tag=50, type_id=UnitID.PHOTONCANNON, is_ready=True,
            position=NAT.towards(MAIN, 6),
        )
        ai, assigned, workers = self._two_base_setup(enemies, structures=[cannon])

        update_worker_evacuation(ai)

        self.assertEqual(assigned, [])
        self.assertEqual(ai._evac_bases, {})
        for w in workers:
            self.assertEqual(w.orders, [])

    def test_cannon_overwhelmed_still_evacuates(self):
        # 有塔但敌兵规模压垮塔(11 > 6+4×1) → 照撤,不留农民陪塔送死
        enemies = [_unit(900 + i, NAT) for i in range(11)]
        cannon = SimpleNamespace(
            tag=50, type_id=UnitID.PHOTONCANNON, is_ready=True,
            position=NAT.towards(MAIN, 6),
        )
        ai, assigned, _ = self._two_base_setup(enemies, structures=[cannon])

        update_worker_evacuation(ai)

        self.assertIn((101, _EVAC_ROLE), assigned)
        self.assertIn(2, ai._evac_bases)
        self.assertTrue(any("塔1座压不住" in e["msg"] for e in ai._events))

    def test_below_threshold_does_not_evacuate(self):
        enemies = [_unit(900 + i, NAT) for i in range(3)]
        ai, assigned, _ = self._two_base_setup(enemies)

        update_worker_evacuation(ai)

        self.assertEqual(assigned, [])
        self.assertEqual(ai._evac_bases, {})

    def test_rush_blocks_main_base_evacuation(self):
        # rush 期主基不新增撤离(六连动全权接管主基防守,行为不变)
        ths = [_townhall(1, MAIN), _townhall(2, NAT)]
        workers = [_worker(101, MAIN), _worker(102, MAIN)]
        enemies = [_unit(900 + i, MAIN) for i in range(8)]
        ai, assigned = _fake_ai(
            ths, workers, enemies, th_of_worker={101: 1, 102: 1}, rush=True
        )

        update_worker_evacuation(ai)

        self.assertEqual(assigned, [])
        self.assertEqual(ai._evac_bases, {})

    def test_rush_does_not_block_expansion_evacuation(self):
        # E6 bench 实证:VeryHard/Rush 的 rush_active 从首接敌续过中段波,
        # 全局 rush 门让 E6 在目标场景(分矿被抄)永不触发 → 分矿不受 rush 门
        enemies = [_unit(900 + i, NAT) for i in range(5)]
        ai, assigned, workers = self._two_base_setup(enemies, rush=True)

        update_worker_evacuation(ai)

        self.assertIn((101, _EVAC_ROLE), assigned)
        self.assertIn((102, _EVAC_ROLE), assigned)
        self.assertIn(2, ai._evac_bases)

    def test_workers_return_after_enemy_leaves(self):
        enemies = [_unit(900 + i, NAT) for i in range(5)]
        ai, assigned, workers = self._two_base_setup(enemies)
        update_worker_evacuation(ai)
        self.assertIn(2, ai._evac_bases)

        # 敌退(只剩 1 个 <2) → 回采
        ai.enemy_units = [_unit(900, NAT)]
        update_worker_evacuation(ai)

        self.assertIn((101, UnitRole.GATHERING), assigned)
        self.assertIn((102, UnitRole.GATHERING), assigned)
        self.assertEqual(workers[0].orders[-1], ("gather", "mf@2"))
        self.assertNotIn(2, ai._evac_bases)
        self.assertTrue(any("回采" in e["msg"] for e in ai._events))

    def test_hysteresis_holds_evacuation_at_boundary(self):
        enemies = [_unit(900 + i, NAT) for i in range(5)]
        ai, assigned, workers = self._two_base_setup(enemies)
        update_worker_evacuation(ai)
        assigned.clear()

        # 敌兵 5→3:低于撤离阈值 4 但高于回采线 2 → 滞留撤离态,不往返
        ai.enemy_units = [_unit(900 + i, NAT) for i in range(3)]
        update_worker_evacuation(ai)

        self.assertIn(2, ai._evac_bases)
        self.assertNotIn((101, UnitRole.GATHERING), assigned)
        # 途中闲置的撤离农民会补 move(维护逻辑还在管他们)
        idle_worker = _worker(105, NAT.towards(MAIN, 10), idle=True)
        ai.workers.append(idle_worker)
        ai._evac_bases[2]["workers"].add(105)
        update_worker_evacuation(ai)
        self.assertEqual(
            idle_worker.orders, [("move", Point2((MAIN.x, MAIN.y)))]
        )

    def test_single_base_no_cannon_stays_put(self):
        # 单基地无塔无处可撤 → 不动(交 ares Mining keep_safe 个体避险)
        ths = [_townhall(1, MAIN)]
        workers = [_worker(101, MAIN), _worker(102, MAIN)]
        enemies = [_unit(900 + i, MAIN) for i in range(7)]
        ai, assigned = _fake_ai(
            ths, workers, enemies, th_of_worker={101: 1, 102: 1}
        )

        update_worker_evacuation(ai)

        self.assertEqual(assigned, [])
        self.assertEqual(ai._evac_bases, {})


    def test_lost_base_stays_evacuated_while_enemy_camps(self):
        # O39(司令观察):二矿被推平、敌军仍盘踞 → 撤离不解除,不放农民回死矿送死
        enemies = [_unit(900 + i, NAT) for i in range(5)]
        ai, assigned, workers = self._two_base_setup(enemies)
        update_worker_evacuation(ai)
        self.assertIn(2, ai._evac_bases)
        assigned.clear()

        # 二矿 Nexus 被推平(th 消失),敌军还在 → 维持撤离
        ai.townhalls = [t for t in ai.townhalls if t.tag != 2]
        update_worker_evacuation(ai)
        self.assertIn(2, ai._evac_bases)
        self.assertNotIn((101, UnitRole.GATHERING), assigned)
        self.assertNotIn((102, UnitRole.GATHERING), assigned)

        # 敌军真撤了 → 回采(死矿矿脉安全后照常采)
        ai.enemy_units = []
        update_worker_evacuation(ai)
        self.assertIn((101, UnitRole.GATHERING), assigned)
        self.assertNotIn(2, ai._evac_bases)


class TestReleaseContestedMiners(unittest.TestCase):
    """O39:敌主力盘踞的矿/气,摘掉农民资源指派(治基地推平后回流送死)。"""

    def _fake_ai(self, enemies):
        removed_minerals: list[int] = []
        removed_gas: list[int] = []
        mf_nat = SimpleNamespace(tag=501, position=NAT)
        mf_main = SimpleNamespace(tag=502, position=MAIN)
        gas_nat = SimpleNamespace(tag=601, position=NAT)
        mediator = SimpleNamespace(
            get_worker_to_mineral_patch_dict={101: 501, 102: 502},
            get_worker_to_vespene_dict={103: 601},
            remove_mineral_field=lambda mineral_field_tag: removed_minerals.append(
                mineral_field_tag
            ),
            remove_gas_building=lambda gas_building_tag: removed_gas.append(
                gas_building_tag
            ),
        )
        ai = SimpleNamespace(
            enemy_units=list(enemies),
            unit_tag_dict={501: mf_nat, 502: mf_main, 601: gas_nat},
            mediator=mediator,
        )
        return ai, removed_minerals, removed_gas

    def test_contested_patches_released_safe_kept(self):
        # 3 狗盘踞二矿 → 二矿的矿+气指派被摘,主矿的保留
        enemies = [_unit(900 + i, NAT) for i in range(3)]
        ai, rm, rg = self._fake_ai(enemies)

        self.assertEqual(release_contested_miners(ai), 2)
        self.assertEqual(rm, [501])
        self.assertEqual(rg, [601])

    def test_no_threats_is_noop(self):
        ai, rm, rg = self._fake_ai([])
        self.assertEqual(release_contested_miners(ai), 0)
        self.assertEqual(rm, [])
        self.assertEqual(rg, [])

    def test_single_enemy_below_threshold_keeps_assignment(self):
        # 1 个敌兵 < 滞回线 2 → 不摘(与 E6 回采判据同源)
        ai, rm, rg = self._fake_ai([_unit(900, NAT)])
        self.assertEqual(release_contested_miners(ai), 0)
        self.assertEqual(rm, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
