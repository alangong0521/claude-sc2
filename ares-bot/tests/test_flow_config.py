"""flow_config.py 纯逻辑单测 —— 不起游戏、不需 sc2(from_dict 路径)。

跑法(在 ares-bot/ 下):
  python3 -m unittest tests.test_flow_config -v

覆盖:三个内置流派加载、未知名回退、spawn 比例校验、chrono.when 校验、
shipped 冻结(tempest/stalker 与已验证行为逐位一致,防手滑改坏)。
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from bot.flow_config import (  # noqa: E402
    DEFAULT_FLOW, FlowConfig, _HAS_SC2,
)


def _yaml_or_skip(case):
    try:
        import yaml  # noqa: F401
    except ImportError:
        case.skipTest("pyyaml 未安装")


class TestLoadBuiltinFlows(unittest.TestCase):
    """load() 从真实 flows.yml 读(需 pyyaml)。"""

    def test_default_and_none(self):
        _yaml_or_skip(self)
        self.assertEqual(FlowConfig.load(None).name, DEFAULT_FLOW)
        self.assertEqual(FlowConfig.load("").name, DEFAULT_FLOW)
        self.assertEqual(FlowConfig.load("Tempest").name, "tempest")  # 大小写不敏感

    def test_unknown_falls_back(self):
        _yaml_or_skip(self)
        self.assertEqual(FlowConfig.load("bogus").name, DEFAULT_FLOW)

    def test_all_builtin_load(self):
        _yaml_or_skip(self)
        for name in ("tempest", "stalker", "carrier"):
            fc = FlowConfig.load(name)
            self.assertEqual(fc.name, name)
            self.assertTrue(fc.spawn, f"{name} spawn 为空")
            self.assertTrue(fc.core_structures, f"{name} 科技链为空")


class TestValidation(unittest.TestCase):
    """from_dict 校验(纯逻辑,不读文件)。"""

    def test_spawn_sum_over_one(self):
        with self.assertRaises(ValueError):
            FlowConfig.from_dict("x", {"spawn": {
                "A": {"proportion": 0.7}, "B": {"proportion": 0.5},
            }})

    def test_negative_proportion(self):
        with self.assertRaises(ValueError):
            FlowConfig.from_dict("x", {"spawn": {"A": {"proportion": -0.1}}})

    def test_chrono_when_invalid(self):
        with self.assertRaises(ValueError):
            FlowConfig.from_dict("x", {"spawn": {}, "chrono": {"when": "sometimes"}})

    def test_normalization(self):
        fc = FlowConfig.from_dict("x", {
            "spawn": {"tempest ": {"proportion": 1.0}},
            "core_structures": [" gateway ", "STARGATE"],
            "upgrades": ["blinktech", " BLINKTECH ", ""],   # 归一大写 + 去空 + 去重
            "extra_production": {"id": " stargate"},
            "one_off": [" oracle "],
        })
        self.assertIn("TEMPEST", fc.spawn)
        self.assertEqual(fc.core_structures, ["GATEWAY", "STARGATE"])
        self.assertEqual(fc.upgrades, ["BLINKTECH"])
        self.assertEqual(fc.extra_production.id_name, "STARGATE")
        self.assertEqual(fc.chrono.when, "primary_pending")  # 缺省
        self.assertEqual(fc.one_off, ["ORACLE"])


class TestShippedFlowsUnchanged(unittest.TestCase):
    """冻结 tempest/stalker 配置值(与已验证行为逐位一致),防后续手滑。"""

    def test_tempest_frozen(self):
        _yaml_or_skip(self)
        fc = FlowConfig.load("tempest")
        self.assertEqual(fc.spawn, {"TEMPEST": {"proportion": 1.0, "priority": 0}})
        self.assertEqual(fc.core_structures,
                         ["GATEWAY", "CYBERNETICSCORE", "STARGATE", "FLEETBEACON"])
        self.assertEqual(fc.upgrades, [
            "TEMPESTGROUNDATTACKUPGRADE",
            "PROTOSSAIRARMORSLEVEL1",
            "PROTOSSAIRARMORSLEVEL2",
        ])
        self.assertEqual(fc.extra_production.id_name, "STARGATE")
        self.assertEqual((fc.extra_production.cap, fc.extra_production.base), (6, 1))
        self.assertEqual(fc.chrono.targets, ("STARGATE",))
        self.assertEqual(fc.chrono.when, "primary_pending")
        self.assertEqual(fc.one_off, ["ORACLE"])
        self.assertEqual(fc.rally_min_army, 0)  # 默认关,已验证行为不动

    def test_stalker_loads(self):
        """stalker 流正在迭代调参(非冻结),只验结构完整 + 配比和 ≈ 1.0。"""
        _yaml_or_skip(self)
        fc = FlowConfig.load("stalker")
        self.assertTrue(fc.spawn)
        total = sum(v["proportion"] for v in fc.spawn.values())
        self.assertAlmostEqual(total, 1.0, places=6)
        self.assertTrue(fc.core_structures)
        self.assertEqual(fc.chrono.when, "always")

    def test_carrier_flow(self):
        _yaml_or_skip(self)
        fc = FlowConfig.load("carrier")
        # O60(Harder Zerg AA 墙实证):暴风主 C(射程 10 压腐化 6),航母转副 C;
        # O62(VeryHard Power 实证):再压航母配比(250 气吃暴风产能),先堆暴风临界质量
        self.assertEqual(fc.spawn, {
            "TEMPEST": {"proportion": 0.85, "priority": 0},
            "CARRIER": {"proportion": 0.15, "priority": 1},
        })
        # 与暴风舰同科技链;暴风优先(priority 0 → chrono/primary 判断指向它)
        self.assertEqual(fc.core_structures,
                         ["GATEWAY", "CYBERNETICSCORE", "STARGATE", "FLEETBEACON"])

    def test_runtime_enums_resolve(self):
        """运行时(有 sc2):三个流的枚举都能解析出来,名字没拼错。"""
        if not _HAS_SC2:
            self.skipTest("sc2 未安装")
        _yaml_or_skip(self)
        for name in ("tempest", "stalker", "carrier"):
            fc = FlowConfig.load(name)
            self.assertTrue(fc.spawn_dict(), f"{name} spawn_dict 为空")
            self.assertTrue(fc.core_structure_ids(), f"{name} 科技链枚举为空")
            self.assertEqual(len(fc.upgrade_ids()), len(fc.upgrades),
                             f"{name} 有升级名解析不出")


class TestPivotRushCannons(unittest.TestCase):
    """E1 实验开关:pivot.rush_cannons(臂 B 纯叉子不铺塔)的配置解析。"""

    def test_default_true_keeps_arm_a(self):
        fc = FlowConfig.from_dict("x", {"spawn": {}, "pivot": {"rush_zealots": 4}})
        self.assertTrue(fc.pivot.rush_cannons)  # 缺省 = 现状臂 A(4叉+铺塔)

    def test_explicit_false_arm_b(self):
        fc = FlowConfig.from_dict("x", {"spawn": {}, "pivot": {
            "rush_zealots": 4, "rush_cannons": False,
        }})
        self.assertEqual(fc.pivot.rush_zealots, 4)
        self.assertFalse(fc.pivot.rush_cannons)  # 臂 B:出叉子但不铺塔

    def test_zero_zealots_arm_c(self):
        fc = FlowConfig.from_dict("x", {"spawn": {}, "pivot": {"rush_zealots": 0}})
        self.assertEqual(fc.pivot.rush_zealots, 0)
        self.assertTrue(fc.pivot.rush_cannons)  # 臂 C:只铺塔憋航母

    def test_no_pivot_block(self):
        fc = FlowConfig.from_dict("x", {"spawn": {}})
        self.assertIsNone(fc.pivot)

    def test_save_up_default_off_and_parse(self):
        # O5:save_up 缺省 0=关;carrier 块显式 250
        self.assertEqual(FlowConfig.from_dict("x", {"spawn": {}}).save_up, 0)
        fc = FlowConfig.from_dict("x", {"spawn": {}, "save_up": 250})
        self.assertEqual(fc.save_up, 250)

    def test_auto_expand_dynamic_fields(self):
        # E2:动态字段缺省 0(旧式 at/to 用法兼容),配了 max_bases 走动态
        old = FlowConfig.from_dict("x", {"spawn": {}, "auto_expand": {
            "at": 150, "to": 2, "when_workers": 18,
        }})
        self.assertEqual((old.auto_expand.at, old.auto_expand.to), (150.0, 2))
        self.assertEqual(old.auto_expand.max_bases, 0)
        self.assertEqual(old.auto_expand.advantage_supply, 0)
        dyn = FlowConfig.from_dict("x", {"spawn": {}, "auto_expand": {
            "max_bases": 4, "when_workers": 22, "advantage_supply": 12,
        }})
        self.assertEqual(
            (dyn.auto_expand.max_bases, dyn.auto_expand.when_workers,
             dyn.auto_expand.advantage_supply),
            (4, 22, 12),
        )

    def test_expansion_cannons_parse(self):
        self.assertIsNone(FlowConfig.from_dict("x", {"spawn": {}}).expansion_cannons)
        fc = FlowConfig.from_dict("x", {"spawn": {}, "expansion_cannons": {
            "min": 3, "max": 8,
        }})
        self.assertEqual((fc.expansion_cannons.min, fc.expansion_cannons.max), (3, 8))

    def test_carrier_e2_shipped(self):
        _yaml_or_skip(self)
        fc = FlowConfig.load("carrier")
        self.assertEqual(
            (fc.auto_expand.max_bases, fc.auto_expand.when_workers,
             fc.auto_expand.advantage_supply),
            (6, 16, 12),  # O30:when_workers 22→16(早开 2 矿);O158:max_bases 4→3(防御集中);O216g(司令观察):饱和要主动开 3-6 矿,max_bases 3→6(Zerg Rush 仍代码层锁 2)
        )
        self.assertEqual(fc.auto_expand.first_expand_at, 150.0)  # O198:o197 三局全单矿到死，first_expand_at 210 被 rush/threat 永久冻结；提前到 150s 让二矿资金窗更早出现。
        self.assertEqual(
            (fc.expansion_cannons.min, fc.expansion_cannons.max), (2, 4)
        )  # O211:o210-vh-zerg-rush 全 lane idle_builder 实证 min=4 时经济紧张期派工 4 塔/基地，大量塔工等钱，舰队成型资金被抽干。降到 min=2 保留动态扩容(max=4，敌兵≥8 时仍回到 4)，quiet 期少铺塔、多采矿。
        # O10:升级链补全到 L3,盾 L2/L3 垫底(防队列截断)
        self.assertEqual(fc.upgrades, [
            "PROTOSSAIRWEAPONSLEVEL1", "PROTOSSAIRARMORSLEVEL1",
            "PROTOSSSHIELDSLEVEL1",
            "PROTOSSAIRWEAPONSLEVEL2", "PROTOSSAIRARMORSLEVEL2",
            "PROTOSSAIRWEAPONSLEVEL3", "PROTOSSAIRARMORSLEVEL3",
            "PROTOSSSHIELDSLEVEL2", "PROTOSSSHIELDSLEVEL3",
        ])
        # E3e/E3f:舰队成型前地面保底;O47:vs Harder 波次加厚(O33 的 3/0.3/8 太薄);
        # O216e:exit_ground 8→6,首舰出生后更快退出地面 floor,省矿给舰队产能
        # O134-①(o133 局2 实证):cap 4→5 + 第二保底追猎×2(吃烂在银行的气)
        # O197(o196-vh-zerg-rush game_01):pre_fleet.max 12→8,transition 期地面已够,
        # 避免 15 叉把 FB/二矿资金吃光。
        self.assertEqual(
            (fc.pre_fleet.id_name, fc.pre_fleet.cap,
             fc.pre_fleet.per_enemy, fc.pre_fleet.max, fc.pre_fleet.exit_ground),
            ("ZEALOT", 5, 0.5, 8, 6),
        )
        self.assertEqual((fc.pre_fleet.id2, fc.pre_fleet.cap2), ("STALKER", 2))
        # O213:carrier 加 rally_min_army 抑制 trickle
        self.assertEqual(fc.rally_min_army, 16)
        # stalker 旧式 auto_expand 不受影响(冻结块)
        sk = FlowConfig.load("stalker")
        self.assertEqual((sk.auto_expand.to, sk.auto_expand.max_bases), (2, 0))

    def test_pre_fleet_default_none(self):
        self.assertIsNone(FlowConfig.from_dict("x", {"spawn": {}}).pre_fleet)
        fc = FlowConfig.from_dict("x", {"spawn": {}, "pre_fleet": {
            "id": "zealot", "cap": 4,
        }})
        self.assertEqual((fc.pre_fleet.id_name, fc.pre_fleet.cap), ("ZEALOT", 4))
        # O134-①:第二保底缺省关闭,旧配置行为不变;配了才生效
        self.assertEqual((fc.pre_fleet.id2, fc.pre_fleet.cap2), ("", 0))
        fc2 = FlowConfig.from_dict("x", {"spawn": {}, "pre_fleet": {
            "id": "zealot", "cap": 5, "id2": "stalker", "cap2": 2,
        }})
        self.assertEqual((fc2.pre_fleet.id2, fc2.pre_fleet.cap2), ("STALKER", 2))

    def test_carrier_save_up_shipped(self):
        _yaml_or_skip(self)
        # O96(o95 局3/局4 实证):O62 配方(TEMPEST p0)下 save_up 250 把 CARRIER
        # 永久截断出 spawn(FB 就绪后 160s 零航母)—— carrier 憋气必须关
        self.assertEqual(FlowConfig.load("carrier").save_up, 0)
        # tempest 单兵种不需要憋气,保持关
        self.assertEqual(FlowConfig.load("tempest").save_up, 0)

    def test_shipped_flows_pivot_default_true(self):
        """已发货流派(tempest/carrier 带 pivot 块)缺省 rush_cannons=True,行为不变。"""
        _yaml_or_skip(self)
        for name in ("tempest", "carrier"):
            fc = FlowConfig.load(name)
            self.assertIsNotNone(fc.pivot)
            self.assertTrue(fc.pivot.rush_cannons, f"{name} rush_cannons 缺省应为 True")


    def test_dt_loads(self):
        """dt(隐刀 rush,2026-07-21 落地):块可加载、配比和=1.0、科技链含 DARKSHRINE。"""
        _yaml_or_skip(self)
        fc = FlowConfig.load("dt")
        self.assertEqual(fc.name, "dt")
        total = sum(v["proportion"] for v in fc.spawn.values())
        self.assertAlmostEqual(total, 1.0, places=6)
        self.assertIn("DARKTEMPLAR", fc.spawn)
        self.assertIn("DARKSHRINE", fc.core_structures)
        self.assertIn("TWILIGHTCOUNCIL", fc.core_structures)
        self.assertEqual(fc.rally_min_army, 4)
        self.assertIsNotNone(fc.pivot)

    def test_dt_enums_resolve(self):
        """dt 的兵种/结构/升级枚举运行时全部可解析(防拼写静默失效)。"""
        _yaml_or_skip(self)
        fc = FlowConfig.load("dt")
        self.assertTrue(fc.spawn_dict(), "dt spawn_dict 为空")
        self.assertTrue(fc.core_structure_ids(), "dt 科技链枚举为空")
        self.assertEqual(len(fc.upgrade_ids()), len(fc.upgrades),
                         "dt 有升级名解析不出")


class TestTransitionConfig(unittest.TestCase):
    """O92 过渡形态配置解析(carrier 专属;tempest/stalker/dt 不加,行为冻结)。"""

    def test_default_none(self):
        self.assertIsNone(FlowConfig.from_dict("x", {"spawn": {}}).transition)

    def test_parse_and_defaults(self):
        fc = FlowConfig.from_dict("x", {"spawn": {}, "transition": {
            "ground_spawn": {"stalker ": {"proportion": 0.4, "priority": 0},
                             "ZEALOT": {"proportion": 0.6, "priority": 1}},
        }})
        tr = fc.transition
        self.assertIsNotNone(tr)
        self.assertEqual(tr.ground_spawn, {
            "STALKER": {"proportion": 0.4, "priority": 0},
            "ZEALOT": {"proportion": 0.6, "priority": 1},
        })
        self.assertEqual(tr.gateway_cap, 3)      # 缺省
        self.assertEqual(tr.fleet_at, 700.0)     # 缺省

    def test_explicit_values(self):
        fc = FlowConfig.from_dict("x", {"spawn": {}, "transition": {
            "ground_spawn": {"ZEALOT": {"proportion": 1.0, "priority": 0}},
            "gateway_cap": 4, "fleet_at": 650,
        }})
        self.assertEqual(fc.transition.gateway_cap, 4)
        self.assertEqual(fc.transition.fleet_at, 650.0)

    def test_ground_spawn_sum_over_one_raises(self):
        with self.assertRaises(ValueError):
            FlowConfig.from_dict("x", {"spawn": {}, "transition": {
                "ground_spawn": {"A": {"proportion": 0.7},
                                 "B": {"proportion": 0.5}},
            }})

    def test_ground_spawn_negative_proportion_raises(self):
        with self.assertRaises(ValueError):
            FlowConfig.from_dict("x", {"spawn": {}, "transition": {
                "ground_spawn": {"A": {"proportion": -0.1}},
            }})

    def test_carrier_shipped_transition(self):
        _yaml_or_skip(self)
        tr = FlowConfig.load("carrier").transition
        self.assertIsNotNone(tr)
        # O205:transition 地面彻底去气,把气全部让给舰队;纯 ZEALOT 做肉盾。
        self.assertEqual(tr.ground_spawn, {
            "ZEALOT": {"proportion": 1.0, "priority": 0},
        })
        # O204:gateway_cap 2→1,再少一座兵营=150 矿给 FB/二矿。
        self.assertEqual(tr.gateway_cap, 1)
        self.assertEqual(tr.fleet_at, 280.0)     # O177:400→320;O216:320→280,与 production_manager 中 Zerg Timing 的 _timing_fb_gate 对齐,加速舰队转型

    def test_other_flows_have_no_transition(self):
        """冻结:tempest/stalker/dt 不配 transition(行为零变化)。"""
        _yaml_or_skip(self)
        for name in ("tempest", "stalker", "dt"):
            self.assertIsNone(FlowConfig.load(name).transition, name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
