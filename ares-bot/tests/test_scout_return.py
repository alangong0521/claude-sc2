"""Bug1: scout 探机撤回后回家单测 —— 不起游戏,假 ai 验证 home_mineral 选矿
+ _handle_scout 撤回分支显式下回家命令(不再只 assign_role 让 idle 清扫派去敌矿)。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_scout_return -v
"""
import os
import sys
import unittest
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

from bot.main import MyBot, home_mineral  # noqa: E402

MAIN = Point2((20.0, 20.0))
ENEMY_MAIN = Point2((150.0, 150.0))


def _townhall(tag, pos, ready=True):
    return SimpleNamespace(tag=tag, position=pos, is_ready=ready)


class TestHomeMineral(unittest.TestCase):
    """home_mineral 纯函数:撤回必须用离主基最近的矿,不能用 closest_to(worker)
    (后者含敌方矿 → 探机在敌家被派去采对面矿送死,Bug1:t=128 被 marine)。"""

    def test_picks_mineral_nearest_to_main_townhall(self):
        # 主基 townhall 在 MAIN;选矿应以 MAIN 为准(反模式回归点:不是 worker 位置)
        captured = []
        mfs = SimpleNamespace(closest_to=lambda p: captured.append(p) or "main_mf")
        ai = SimpleNamespace(
            ready_townhalls=[_townhall(1, MAIN)],
            mineral_field=mfs,
            start_location=MAIN,
        )
        self.assertEqual(home_mineral(ai), "main_mf")
        # closest_to 传入的必须是主基 townhall(用其 position),不是别的(敌矿/worker 位)
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].position, MAIN)

    def test_picks_nearest_to_start_location_among_many_townhalls(self):
        main_th = _townhall(1, MAIN)
        far_th = _townhall(2, Point2((200.0, 200.0)))
        captured = []
        mfs = SimpleNamespace(closest_to=lambda p: captured.append(p) or "mf")
        ai = SimpleNamespace(
            ready_townhalls=[far_th, main_th],  # 顺序无关
            mineral_field=mfs,
            start_location=MAIN,
        )
        home_mineral(ai)
        # 选离 start_location(MAIN)最近的 townhall = main_th,用它定位矿
        self.assertEqual(len(captured), 1)
        self.assertEqual(captured[0].position, MAIN)

    def test_none_when_no_ready_townhall(self):
        ai = SimpleNamespace(ready_townhalls=[], mineral_field=["mf"], start_location=MAIN)
        self.assertIsNone(home_mineral(ai))

    def test_none_when_no_mineral_field(self):
        ai = SimpleNamespace(
            ready_townhalls=[_townhall(1, MAIN)], mineral_field=[], start_location=MAIN
        )
        self.assertIsNone(home_mineral(ai))


class TestScoutReturnHome(unittest.TestCase):
    """_handle_scout 撤回分支:scout 摸到 enemy_main<12 → 显式下回家命令(Bug1)。"""

    def _fake_bot(self, scout, home_mineral_ret="main_mf", enemy_units=()):
        assigned: list[tuple[int, object]] = []
        moved, gathered = [], []
        scout.move = lambda t: moved.append(t)
        scout.gather = lambda t: gathered.append(t)

        def _find_by_tag(tag):
            return scout if tag == scout.tag else None

        mfs = SimpleNamespace(closest_to=lambda p: home_mineral_ret)
        bot = SimpleNamespace(
            steer_order={"scout": "on"},
            _scout_done=True,
            _scout_tag=scout.tag,
            _last_scout_ts=None,  # Bug2: _handle_scout 现在会读它
            enemy_units=list(enemy_units),
            units=SimpleNamespace(find_by_tag=_find_by_tag),
            mediator=SimpleNamespace(
                assign_role=lambda tag, role: assigned.append((tag, role))
            ),
            focused_enemy_start=lambda: ENEMY_MAIN,
            start_location=MAIN,
            ready_townhalls=[_townhall(1, MAIN)],
            mineral_field=mfs,
        )
        return bot, assigned, moved, gathered

    def test_reached_enemy_issues_home_command_and_clears_tag(self):
        # scout 摸进 enemy_main 12 格内 → 撤回
        scout = SimpleNamespace(
            tag=999, position=ENEMY_MAIN, is_idle=False,
            distance_to=lambda p: 5.0,
        )
        bot, assigned, moved, gathered = self._fake_bot(scout)

        MyBot._handle_scout(bot)

        # 收到回家命令(主基矿) —— Bug1 核心:不再只 assign_role 让 idle 清扫
        # 把它派去"离探机最近的矿"=敌方矿线
        self.assertTrue(gathered or moved, "撤回必须显式下回家命令,不能只切 role")
        target = gathered[0] if gathered else moved[0]
        self.assertEqual(target, "main_mf")  # home_mineral 选的主基矿
        self.assertIsNone(bot._scout_tag)    # 清 tag(不再管这个探机)
        self.assertIn((999, UnitRole.GATHERING), assigned)  # role 切 GATHERING

    def test_not_reached_idle_keeps_pushing_to_enemy(self):
        # scout 还没到 12 内(人族兵营常在外围 13-20 格) → 不撤回,idle 继续往敌家推
        scout = SimpleNamespace(
            tag=999, position=Point2((140.0, 140.0)), is_idle=True,
            distance_to=lambda p: 20.0,
        )
        bot, assigned, moved, gathered = self._fake_bot(scout)

        MyBot._handle_scout(bot)

        self.assertEqual(gathered, [])       # 没下回家命令
        self.assertEqual(moved, [ENEMY_MAIN])  # idle → 继续往敌家推(侦查中)
        self.assertEqual(bot._scout_tag, 999)  # tag 没清(还在管它)
        self.assertEqual(assigned, [])         # role 没切

    def test_scout_flees_when_enemy_ground_nearby(self):
        # O22: 途中遇敌地面作战单位(<8 格) → 立即逃跑 gather home,不傻傻走到敌家
        marine = SimpleNamespace(
            tag=500, type_id=UnitID.MARINE, is_flying=False, is_structure=False
        )
        scout = SimpleNamespace(
            tag=999, position=Point2((100.0, 100.0)), is_idle=True,
            distance_to=lambda p: 6.0 if p is marine else 20.0,  # marine 6 格(<8 触发), enemy_main 20
        )
        bot, assigned, moved, gathered = self._fake_bot(scout, enemy_units=[marine])

        MyBot._handle_scout(bot)

        # 逃跑:收到回家命令(主基矿),不 move enemy_main
        self.assertTrue(gathered or moved, "遇敌必须逃跑下回家命令")
        target = gathered[0] if gathered else moved[0]
        self.assertEqual(target, "main_mf")  # home_mineral
        self.assertIsNone(bot._scout_tag)    # 清 tag
        self.assertIn((999, UnitRole.GATHERING), assigned)
        self.assertNotIn(ENEMY_MAIN, moved)  # 没往敌家推


if __name__ == "__main__":
    unittest.main(verbosity=2)
