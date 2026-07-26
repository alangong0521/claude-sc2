"""Bug2: scout=on clear 后重派单测 —— 不起游戏,验证 _scout_ts 元字段机制。

steer_cli set scout=on 时盖 _scout_ts 时间戳 → bot 读到 scout='on' 且 ts 比上次新
→ scout_should_redispatch 判 True → 重置 _scout_done 重派(绕过 clear+set 同步执行
时 bot 4s 轮询读不到 clear 的时序坑)。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_steer_meta -v
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
sys.path[:0] = [
    os.path.join(_ROOT, "ares-sc2", "src", "ares"),
    os.path.join(_ROOT, "ares-sc2", "src"),
    os.path.join(_ROOT, "ares-sc2"),
    _ROOT,
]

from bot.steer_vocab import validate_field  # noqa: E402
from bot.steer import read_order  # noqa: E402
from bot.main import player_yield_for_ability, scout_should_redispatch  # noqa: E402
import steer_cli  # noqa: E402
from steer_cli import cmd_set  # noqa: E402


class TestValidateMetaField(unittest.TestCase):
    """validate_field 对 _ 前缀元字段放行,对未知非元字段仍报错。"""

    def test_underscore_meta_field_passes(self):
        self.assertEqual(validate_field("_scout_ts", "1234.5"), [])

    def test_any_underscore_field_passes(self):
        # 比 META_FIELDS 白名单更通用:未来加 _* 元字段不用改 validate
        self.assertEqual(validate_field("_anything_new", "x"), [])

    def test_unknown_non_meta_field_still_rejected(self):
        errs = validate_field("bogus_field", "x")
        self.assertEqual(len(errs), 1)
        self.assertIn("bogus_field", errs[0])

    def test_target_empty_clears_for_mopup(self):
        # O28:target= 空值放行(清空固定目标→bot 轮巡清图);其他字段空值仍报错
        self.assertEqual(validate_field("target", ""), [])
        self.assertEqual(validate_field("target", "   "), [])
        self.assertEqual(len(validate_field("stance", "")), 1)


class TestReadOrderReturnsMeta(unittest.TestCase):
    """read_order 必须把 _scout_ts 等元字段一并返回,否则 main.py 拿不到(Bug2 核心)。"""

    def test_read_order_includes_scout_ts(self):
        from bot import steer as steer_mod
        d = tempfile.mkdtemp()
        orders = Path(d) / "orders.json"
        orders.write_text(json.dumps({"scout": "on", "_scout_ts": 1234.5}))
        old = steer_mod.ORDERS_FILE
        steer_mod.ORDERS_FILE = orders
        try:
            o = read_order()
        finally:
            steer_mod.ORDERS_FILE = old
        self.assertEqual(o.get("scout"), "on")
        self.assertEqual(o.get("_scout_ts"), 1234.5)


class TestCmdSetScoutTs(unittest.TestCase):
    """cmd_set 改 scout 时刷 _scout_ts,set 别的字段不刷(否则会误触发重派)。"""

    def _run(self, argv):
        d = tempfile.mkdtemp()
        orders = Path(d) / "orders.json"
        old = steer_cli.ORDERS_FILE
        steer_cli.ORDERS_FILE = orders
        try:
            cmd_set(argv)
            return json.loads(orders.read_text())
        finally:
            steer_cli.ORDERS_FILE = old

    def test_set_scout_writes_timestamp(self):
        o = self._run(["scout=on"])
        self.assertEqual(o.get("scout"), "on")
        self.assertIn("_scout_ts", o)
        self.assertIsInstance(o["_scout_ts"], (int, float))

    def test_set_other_field_does_not_touch_scout_ts(self):
        o = self._run(["stance=attack"])
        self.assertEqual(o.get("stance"), "attack")
        self.assertNotIn("_scout_ts", o)


class TestScoutRedispatch(unittest.TestCase):
    """scout_should_redispatch 四档 + 边界。"""

    def test_first_dispatch_when_prev_none(self):
        # 第一次下令(prev None,new 有值,done=True)→ 重派
        self.assertTrue(scout_should_redispatch(None, 100.0, True))

    def test_same_ts_no_redispatch(self):
        # 同一个 scout 持续中(ts 没变)→ 不补
        self.assertFalse(scout_should_redispatch(100.0, 100.0, True))

    def test_newer_ts_redispatch(self):
        # 又下了一次 scout(new>prev,即 clear+scout=on)→ 重派
        self.assertTrue(scout_should_redispatch(100.0, 200.0, True))

    def test_already_dispatchable_skips(self):
        # scout_done 已 False → 本来就能派,不需要这个机制
        self.assertFalse(scout_should_redispatch(100.0, 200.0, False))

    def test_no_ts_no_redispatch(self):
        # 没时间戳(老 CLI 写的 / 被清)→ 不触发,走原 scout!='on' 重置路径
        self.assertFalse(scout_should_redispatch(100.0, None, True))


class TestPlayerYieldForAbility(unittest.TestCase):
    """O27:BUILD_* 命令长倒计时(30s),其他 3s(治手动造气矿被卡)。"""

    def test_build_ability_long_yield(self):
        self.assertEqual(player_yield_for_ability("BUILD_ASSIMILATOR"), 30.0)
        self.assertEqual(player_yield_for_ability("BUILD_PYLON"), 30.0)
        self.assertEqual(player_yield_for_ability("BUILD_GATEWAY"), 30.0)

    def test_non_build_ability_short_yield(self):
        self.assertEqual(player_yield_for_ability("MOVE"), 3.0)
        self.assertEqual(player_yield_for_ability("ATTACK"), 3.0)
        self.assertEqual(player_yield_for_ability(""), 3.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
