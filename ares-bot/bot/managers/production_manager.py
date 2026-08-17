import os
from typing import TYPE_CHECKING

from sc2.unit import Unit

from ares.behaviors.macro import (
    AutoSupply,
    BuildStructure,
    BuildWorkers,
    ExpansionController,
    GasBuildingController,
    ProductionController,
    ProtossStaticDefence,
    SpawnController,
    TechUp,
    UpgradeCCs,
    UpgradeController,
)
from ares.behaviors.macro.macro_plan import MacroPlan
from ares.consts import (
    ID as TRACKER_ID,
    TARGET,
    TIME_ORDER_COMMENCED,
    BuildingSize,
    UnitRole,
)
from cython_extensions.general_utils import cy_unit_pending
from cython_extensions.units_utils import cy_closest_to
from cython_extensions import cy_pylon_matrix_covers
from ares.managers.manager import Manager
from ares.managers.manager_mediator import ManagerMediator
from sc2.data import Race
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.ids.upgrade_id import UpgradeId
from sc2.position import Point2
from sc2.units import Units

from bot.production_plans import (
    assimilator_attempt_stuck,
    bank_production_target,
    base_defense_anchor,
    base_rebuild_active,
    builder_borrow_ok,
    cannon_target_capped,
    cannon_safe_anchor,
    carrier_quota_active,
    carrier_quota_spawn,
    carrier_transition_ready,
    chrono_first_zealot,
    chrono_forge_first,
    critical_dispatch_exempt,
    chrono_primary_id,
    core_tech_allowed,
    defense_sprint_active,
    defense_syncs_with_nexus,
    defensive_rally_point,
    dispatch_viable,
    early_scout_verdict,
    escort_worker_count,
    escort_pull_cap,
    escort_stance,
    expand_holding_should_abort,
    holding_allows_cyber,
    serialize_presumed_cannons,
    worker_last_stand_hopeless,
    expansion_cannon_count,
    expansion_cannon_min_dynamic,
    expansion_max_pending,
    expansion_blocked,
    f2_dispatch_guard_bypassed,
    extra_production_mineral_gate,
    fb_stall_recovery_needed,
    fleet_expand_holds,
    fleet_exit_allowed,
    fleet_expansion_reserve,
    fleet_rebuild_cannon_cap,
    fleet_rebuild_window,
    fleet_stargate_reserve,
    fleet_supply_buffer_needed,
    fleet_tech_reserve,
    fleet_transition_ready,
    fleet_transition_strong_exit,
    first_zealot_sprint,
    forced_expand_during_transition,
    floor_exits,
    forge_first_probe_yield,
    forge_first_pylon_yield,
    gas_gated_stargate_target,
    gas_target,
    forge_before_first_gateway,
    gateway_chain_after_first_zealot,
    gateway_yields_tech_slots,
    ground_floor_gateways,
    ground_floor_unmet,
    ground_floor_active,
    fb_gate_f2_exempt_zt,
    is_combat_type,
    main_siege_active,
    mineral_crisis_gas_stop,
    natural_predefense_allowed,
    nexus_rebuild_active,
    nexus_rebuild_viable,
    oracle_before_fleet_allowed,
    pick_slot_anchor,
    pick_walk_patch,
    pick_wall_positions,
    pocket_saving_cannons,
    pivot_stalker_cap,
    carrier_reserve_ok,
    fleet_infra_rebuild_active,
    forge_rebuild_probe_yield,
    zt_prewave_trickle_needed,
    pivot_primary_id,
    pre_fleet_cap,
    pre_fleet_spawn,
    probe_floor_needed,
    redispatch_cooled_down,
    _pylon_redispatch_ok,
    rebuild_extra_production_id,
    rebuild_window_spawn,
    rescout_verdict,
    RESCOUT_DISPATCH_AT,
    RESCOUT_HARD_DEADLINE,
    research_paused_for_rush,
    reserve_deadlock_break,
    rush_cancellable_structure,
    rush_cannon_bypass,
    rush_defense_past_holding,
    rush_defers_second_gateway,
    rush_blocks_reserve,
    rush_contact_arms,
    rush_deadzone_active,
    rush_defend_base,
    rush_hold_batteries,
    rush_needs_gateway,
    rush_stops_gas,
    rush_triggers_defense,
    rush_gas_stop_window,
    rush_worker_escort_needed,
    save_up_spawn,
    scout_early_redispatch_needed,
    scout_next_step,
    scout_verdict,
    scout_verdict_timing,
    presumed_rush_defense,
    cancel_presumed_forge,
    carrier_sg_bonus,
    should_expand_dynamic,
    should_pivot_tempest,
    should_register_autosupply,
    spawn_pause_reason,
    sprint_blocks_probes,
    stargate_double_opener,
    stargate_gas_gate_bonus,
    tempest_primary_spawn,
    tech_yields_to_threat,
    tech_goes_to_expansion,
    tracker_entry_stale,
    fleet_gas_starved,
    rush_spawn_fleet_escape,
    threat_ground_exemption,
    threat_response_active,
    transition_expand_blocked,
    transition_expand_after_first_wave,
    transition_expand_ready,
    transition_expand_reserve,
    transition_battery_floor,
    transition_cannon_cap,
    transition_gateway_allowed,
    transition_gateway_reserve,
    transition_needs_cybercore,
    transition_needs_gateways,
    transition_pauses_gas,
    transition_probe_yield,
    transition_should_enter,
    transition_timing_sprint,
    transition_expand_at_210,
    tower_yields_gateway_chain,    transition_stargate_allowed,
    transition_tech_frozen,
    tower_zone_pylon_needed,
    unknown_verdict_defense,
    zerg_timing_unknown_floor,
    zerg_timing_expand_allowed,
    pick_pocket_expansion,
    upgrade_tech_buildings,
    wall_disabled_after,
    wall_escort_needed,
    wall_fallback_due,
    wall_hold_point,
    worker_target,
)

if TYPE_CHECKING:
    from ares import AresBot

# O19:防御塔派工的走位时间估算(基地内,秒)——dispatch_viable 用,见 F2 注册点
_DEFENCE_WALK_TIME: float = 5.0
# O19 二轮:O11 撤回塔工后的重派冷却(秒)——redispatch_cooled_down 用
# O139-②:15→10,且手动派工链(_dispatch_structure)同读此冷却
_DEFENCE_REDISPATCH_CD: float = 10.0
# E9:threat 地面豁免用的神族空军类型表(sc2 Attribute 无 flying 判定,
# 神族流派出兵表内可能出现的空军兵种全列;地面 = spawn 里不在此表的)
_FLYING_UNITS = {
    UnitID.CARRIER,
    UnitID.TEMPEST,
    UnitID.ORACLE,
    UnitID.PHOENIX,
    UnitID.VOIDRAY,
    UnitID.MOTHERSHIP,
    UnitID.MOTHERSHIPCORE,
    UnitID.WARPPRISM,
    UnitID.OBSERVER,
}
# O19:探机/农民移动速度(格/游戏秒),扩张走位时间估算用
_WORKER_SPEED: float = 3.94

# 神族流派(造兵配方/科技链/升级/chrono/追加产能/一次性建造)全部进 flows.yml,
# 按 BUILD env 选块(run.py 在起游戏前已把 BUILD 写进 os.environ 并归一)。
# 本文件不再有 per-流派硬编码常量 —— 加流派改 flows.yml,不动这里。
from bot.flow_config import FlowConfig


class ProductionManager(Manager):
    def __init__(
        self,
        ai: "AresBot",
        config: dict,
        mediator: ManagerMediator,
    ) -> None:
        """Set up the manager.

        Parameters
        ----------
        ai :
            Bot object that will be running the game
        config :
            Dictionary with the data from the configuration file
        mediator :
            ManagerMediator used for getting information from other managers.

        Returns
        -------

        """
        super().__init__(ai, config, mediator)

        self._built_single_oracle: bool = False
        self._built_extra_production_pylon: bool = False
        self._forward_pylon_built: bool = False  # F1: 前线水晶塔(一次性,给折跃门提供前线电源)
        # can use a single chrono for the oracle
        self._oracle_chrono: bool = False
        # 通用建筑杠杆 build=<结构>（expand=yes 是 build=nexus 的别名）。
        # 一次性锁定：记下"目标数量"，造到就停；想再造先 clear 再下（同 scout 手感）。
        self._build_key: str | None = None
        self._build_target: int | None = None
        # pivot 自适应状态(反rush/反空军)
        self._early_scout_done: bool = False
        self._scout_verdict_done: bool = False  # O9:侦查情报→开局决策,一局评一次
        # E8:O9/E7 侦查结论(greedy/rush/unknown),combat 集结纪律读;未评估=None
        self._verdict: str | None = None
        # E7/O16 侦查断链:pivot 探机 tag(判"还在路上"用)+ 补派只一次(防送死)
        self._pivot_scout_tag: int | None = None
        self._pivot_redispatched: bool = False
        # O36: pivot 探机待排查出生点(近→远),_update_early_scout_route 逐点推进
        self._pivot_scout_route: list = []
        # O71: 二次侦查(首判后 t=250 复核开局,rush 确认偏晚修复)
        self._rescout_done: bool = False
        # O279:首波预警 latch(二判敌兵 ≥6 → 扩张暂停+叉增产;接触即解除)
        self._wave_incoming: bool = False
        self._rescout_tag: int | None = None
        self._rescout_verdict_done: bool = False
        # O72: O71 情报确认的 rush 预警持有到接触(上限时刻;None=不持有)
        self._rush_hold_until: float | None = None
        # E10 策略 pivot:风暴压制 → 航母终结的一次性转型 latch
        self._pivot_transitioned: bool = False
        self._rush_active: bool = False
        # O204:舰队成型后硬解 rush_active 只执行一次的 latch,避免中后期
        # rush 再触发后经济被永久锁死。
        self._rush_hard_cleared: bool = False
        # O205:硬解触发时刻,60s 内不因敌兵重新进入 full rush-lock,
        # 但 threat_response_active 仍可激活塔/兵响应。
        self._rush_hard_cleared_at: float | None = None
        # E9 中局威胁响应(carrier):敌可见作战 supply 大幅压过我方 → True(滞回)
        self._threat_active: bool = False
        self._rush_clear_since: float | None = None
        # O92 过渡形态(carrier 配了 transition 才生效):rush 确认 → 地面过渡,
        # 威胁清除后转舰队。active/转舰队两个 latch 各走一次,不回头。
        self._transition_active: bool = False
        self._fleet_transitioned: bool = False
        self._transition_clear_since: float | None = None
        # O92:rush 已被证实(接触式检测 / O71 二次侦查确认)的 latch ——
        # 过渡形态进入判据用它而非裸 _rush_active(unknown  verdict 的 60s
        # 保守响应包不该触发冻星门的大承诺)。
        self._rush_confirmed: bool = False
        # O110-①:舰队科技(SG/FB)停滞自救计时(每 sid 一条;O93 的单一
        # _fb_stall_since 升级而来,判据 fb_stall_recovery_needed 复用)
        # ⚠️ 命名勿用 _tech_stall_since —— 那是 O55 的 float 时间戳
        # (o110 局5 实证:撞名崩溃 'float' has no 'setdefault')
        self._fleet_stall_since: dict = {}
        # O173:FleetBeacon 实体缺失连续计时——pending 抖动导致「无实体」信号
        # 每帧翻板,o172/o173 守卫被绕过。用时间积分稳定:FB 实体为 0 时累计,
        # 一旦实体出现立即清零。
        self._fb_missing_since: float | None = None
        # O175:稳定信号挂到实例前先给默认值,避免 update 首帧前被 _want_dynamic_expand
        # /_spend_bank 读取时 AttributeError(尽管当前流程不会,防御性初始化)。
        self._fb_truly_missing: bool = False
        # O183:Zerg Timing/Rush 动态调首扩时间，优先保家再开二矿。
        self._opp_race: str = os.environ.get("OPPONENT_RACE", "").lower()
        self._ai_build: str = os.environ.get("AI_BUILD", "").lower()
        # O176:FB 已派工但买不起的让位信号,防御性初始化。
        self._fb_waiting: bool = False
        # O115-③:watchdog 开火记录(停滞确认的科技)——科技攒钱预留在
        # 落位停滞局必须解除,否则地面回填被连坐(o114 局3:FB 被杀+
        # 落位失败 → 预留永开 → army 清零后 100s 零补员)
        self._fleet_stall_fired: set = set()
        # O117-①:停气窗口计时( None=未在停气窗;transition 流派 45s 窗)
        self._gas_stop_since: float | None = None
        # O157:矿物危机停气状态(vespene 烂银行、minerals 枯竭且舰队未成规模)
        self._mineral_crisis_gas_stop: bool = False
        # O117-②:防御紧急旗标(rush确认/过渡/presumed 合成,每帧更新)——
        # main.py 的 O11 钉点撤回豁免读它(presumed 期塔工不再被撤回循环)
        self._defense_urgent: bool = False
        # O210:Zerg Rush/Timing 单矿太久时 O189 强制开二矿,本帧强制预走位。
        self._o189_forced_expand: bool = False
        # O216g:O189 事件只记一次(原每帧 append,日志刷屏)。
        self._o189_logged: bool = False
        # O129:冲刺总闸旗标(每帧在 update 头部重算;_rush_gateway_boost 读)
        self._sprint_active: bool = False
        # O130-①:冲刺起始时刻(逃逸阀计时;None=不在冲刺)
        self._sprint_since: float | None = None
        # O133-②:过渡期 timing 防御冲刺旗标(update 头部每帧重算;
        # F2 注册闸/塔目标/_rush_gateway_boost/_build_extra_production 读)
        # O144-②:判据缺省关断(无差别冲刺在非 rush 局白吃矿)→ 恒 False
        self._timing_sprint: bool = False
        # O144-③:地面 floor 激活闸(rush 确认或敌可见地面 ≥4;每帧重算,
        # _apply_floor/_build_extra_production/UC prioritize 闸读)
        self._floor_active: bool = False
        # O255-③:Zerg Timing unknown 死窗叉子 floor 旗标(每帧重算;
        # 激活时 _apply_floor 把追猎 cap 压 0、叉 cap 压 3)
        self._floor_unknown_zt: bool = False
        # O146-①:threat 末次激活时刻(急性窗 25s 延展用;None=本局未威胁)
        self._threat_last_active: float | None = None
        # O150-②:rush 证实时刻(接触/情报谁先谁记;过渡进入的接触时限用,
        # >360s 的接触是正常推进波不是 rush)
        self._rush_confirmed_at: float | None = None
        # O150-③:greedy 退保只执行一次
        self._presumed_forge_cancelled: bool = False
        # O136:坡口墙 —— 墙位簿记(首帧懒算;None=无墙位图/非 transition 流)
        # _wall_hold_point/_wall_gap_point 供 combat _rush_defend_anchor 与
        # 协防堵缝读;_wall_sealed 供协防归队判据读
        self._wall_info: tuple | None = None
        self._wall_info_done: bool = False
        self._wall_hold_point = None
        self._wall_gap_point = None
        self._wall_sealed: bool = False
        self._wall_logged: bool = False
        # O137-①②:墙派工失败台账 —— fail_since(sid 首败时刻)/strikes(失败
        # 计数,≥2 latch 关墙)/fallback(已回落普通槽的 sid)/last_result(取证节流)
        self._wall_fail_since: dict = {}
        self._wall_last_result: dict = {}
        self._wall_fallback: set = set()
        self._wall_strikes: int = 0
        self._wall_disabled: bool = False
        # O131-③:预留连续激活起始(None=无预留;死锁保险丝计时)
        self._reserve_since: float | None = None
        # O132-③(o131 timing 局1 实证):炮塔峰值 latch —— 塔被 wave 拆掉后
        # 「cannons≥2」前提反锁兵营链 ~250s(t=253 塔 3→1,GW 链恒 1-3,
        # 415-425 矿 1100-1400 也拍不下 GW3)。兵营闸改吃峰值,塔损不再关门。
        # 两个口径:peak=已有(含在建实体)+building_counter(transition_gateway_allowed
        # 用);ready_peak=就绪口径(tower_yields_gateway_chain 用)。
        self._cannons_peak: int = 0
        self._cannons_ready_peak: int = 0
        # O94:首波农民协防台账(在岗农民 tag;判据翻假自动归队,无 latch)
        self._escort_tags: set[int] = set()
        self._escort_active: bool = False
        # O104-①:mineral-walk 走位目标簿记(tag → 当前矿簇目标点)
        self._escort_targets: dict = {}
        # O122-②:首波见闻 latch(敌进家 40 格 ≥3 见过即 True)——
        # 「首波清除即扩张」判据用(o121b:清净秒数窗被波次切碎,改用波次相位)
        self._saw_wave: bool = False
        # O105-①b:过渡期「站稳」判定台账(_want_dynamic_expand 每帧重算,
        # update 头部的扩张攒钱预留读它)
        self._tr_expand_ready: bool = False
        # O108-③:presumed 启动簿记只发一次(诊断断链兜底到底哪秒启动)
        self._presumed_logged: bool = False
        # O114-③b:首塔停滞簿记计时(forge 就绪却 0 塔的持续起点)
        self._cannon_stall_since: float | None = None
        # 基地数峰值(重建模式的"真的丢过基地"门,E6b 回归修复:开局 1<max_bases 不算丢)
        self._peak_townhalls: int = 0
        # B4③ 停气台账:rush 期间被拉下气矿的农民 tag(role 归 _GAS_STOP_ROLE),
        # rush 解除后统一归 GATHERING 回气(ares 记账不动,见 _rush_gas_stop)。
        self._gas_stopped_tags: set[int] = set()
        # 流派配置(flows.yml,神族生产侧单一真相源);Terran/Zerg 路径不走它。
        self._flow: FlowConfig = FlowConfig.load(os.environ.get("BUILD"))
        # O184/O190/O208:Zerg Rush/Timing 直接强制进 transition，用 ground_spawn
        # 守窗后再转舰队；O207 让 Timing 走非 transition，结果 FleetBeacon 在
        # 578-650s 才落成、二矿被锁 2 基地、中期地面海缺失，被 Roach/Ravager/Hydra
        # 波次滚平。Timing 用比 Rush 晚的 fleet_at(380) 和更大 gateway_cap(2)，
        # 其余流忽略。
        # O248(o246b 双 lane 0-10 实证):O207 年代的基建链已被 O224-O229/O218
        # 全部重写 —— transition 把舰队起点推迟到 exit(330-450)+130s,
        # 首舰 550-620 恒晚于 500-700 波次窗;Zerg Timing 不再强制 transition
        # (Rush 保留),直爬 cyber→SG→FB,首舰目标 ≤450s,塔+追猎核守窗。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "rush"
            and self._flow.transition is not None
        ):
            self._transition_active = True
        # 兵种组成注册表(army_composition.yml):Terran/Zerg 路径的 spawn/升级从这里读,
        # 神族路径的造兵已改走 self._flow。
        from bot.army_config import ArmyComposition, bot_race_name
        self._army = ArmyComposition.load(race=bot_race_name(ai))

    async def update(self, iteration: int) -> None:
        """Handle production.

        TODO: Add `AutoSupply` when that feature is ready in ares

        Parameters
        ----------
        iteration :
            The game iteration.
        """
        # 种族分派:Terran 走 M1 生产层(ares ProductionController + SpawnController);
        # Zerg 尚未实现(见 status-and-roadmap M2)——先 no-op 造农民保命,不崩。
        if self.ai.race == Race.Terran:
            self._update_terran()
            return
        if self.ai.race == Race.Zerg:
            self._update_zerg()
            return

        # O210:O189 强制开矿旗标每帧由 _want_dynamic_expand 重算,
        # update 头部先清零,避免 _rebuild_nexus 分支跳过导致旧值残留。
        self._o189_forced_expand = False

        # O132-③:炮塔峰值 latch(每帧)——兵营链各闸吃峰值不吃实时值,
        # 塔被 wave 拆掉不再反锁 GW 链(见 __init__ 台账注释)
        self._cannons_peak = max(
            self._cannons_peak,
            len(self.manager_mediator.get_own_structures_dict[UnitID.PHOTONCANNON])
            + self.manager_mediator.get_building_counter[UnitID.PHOTONCANNON],
        )
        self._cannons_ready_peak = max(
            self._cannons_ready_peak,
            sum(
                1 for s in self.ai.structures.ready
                if s.type_id == UnitID.PHOTONCANNON
            ),
        )

        # O166/O167/O168: 8 农民开局 carrier 前期资源极紧，避免水晶/塔/追加产能/
        # 二气把 CYBERNETICCORE/STARGATE/FLEETBEACON/NEXUS 的钱吃光。
        # 只在「非 rush 证实、无威胁、单矿早期」生效；unknown verdict 的保守
        # rush_active 不应关闭本闸，否则 Forge 仍会拖慢科技链。
        # O182(o181c-vh-zerg-timing game_01 实证):把 FleetBeacon 移出 early_core
        # 清单。原清单要求 cyber/stargate/FB 全部 pending 才让开矿，导致二矿被
        # 拖到 FleetBeacon 开始建(≈290s)才能启动，game_01 二矿 361s 才落、经济
        # 被中局波次碾平。只守 cyber+stargate 可让二矿在 first_expand_at(210s)
        # 正常启动，FB 资金仍由 _expand_holding + _fb_truly_missing/_fb_waiting 保护。
        _early_core_missing = (
            self._flow.name == "carrier"
            and self.ai.time < 300.0
            and self.ai.townhalls.amount < 2
            and not self._rush_confirmed
            and not self._threat_active
            and any(
                _sid in self._flow.core_structure_ids()
                and not self._structure_present_or_pending(_sid)
                for _sid in (UnitID.CYBERNETICSCORE, UnitID.STARGATE)
            )
        )
        # O166: 有农民已派去造 Nexus 但钱不够 → 把余钱锁给 Nexus，别让其他建筑插队。
        _nexus_waiting = False
        if self.ai.minerals < self.ai.calculate_cost(UnitID.NEXUS).minerals:
            for _info in self.manager_mediator.get_building_tracker_dict.values():
                if _info.get(TRACKER_ID) == UnitID.NEXUS:
                    _nexus_waiting = True
                    break
        self._early_core_missing = _early_core_missing
        self._nexus_waiting = _nexus_waiting

        # can_afford 守卫：钱够才派农民去造 pylon，否则农民走过去干等不采矿（idle bug 根因）。
        # O166: 前期核心科技/二矿未落时，这根额外水晶会让 CYBERNETICCORE/NEXUS 资金窗被挤掉，先忍一忍。
        if (
            not self._built_extra_production_pylon
            and self.ai.can_afford(UnitID.PYLON)
            and not _early_core_missing
            and not _nexus_waiting
        ):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, UnitID.PYLON)
            )
            self._built_extra_production_pylon = True

        # use ares-sc2 macro behaviors for building pylons and units
        macro_plan: MacroPlan = MacroPlan()
        # O15:基地清零 → 一切开销让位重建 Nexus(没经济一切免谈)。截断 = 不注册
        # 研究/出兵,只留 AutoSupply;命保防御(ProtossStaticDefence,无基地时自然 no-op)。
        # O156-③(o155-vh-zerg-power game_01 实证):基地清零后存款 30、5 工人、
        # 矿脉虽在但无收入口，重建 Nexus 数学死局;O126 仍暂停出兵 250s 空转。
        # 加可行性门：存款 <400 且 0 基地时不再停产攒钱，把余钱/人口变成最后抵抗。
        _rebuild_nexus = nexus_rebuild_active(self.ai.townhalls.amount) and nexus_rebuild_viable(
            workers=self.ai.workers.amount,
            minerals_left=self.ai.mineral_field.amount,
            bank=self.ai.minerals,
        )
        # E3k:动态开矿触发判定(算一次,EC 注册/攒钱预留共用);rush 内建门,重建优先。
        _want_expand = (
            self._want_dynamic_expand() if not _rebuild_nexus else False
        )
        # O51(o49/o50 连败实证):预走位等钱的 Nexus(building_tracker 里 pending)
        # 让 should_expand_dynamic 因 nexus_pending 翻 false → 预留/停塔/停科技闸
        # 全开,银行在 250-400 振荡被塔/科技/兵吃干,等钱的 Nexus 永远开不了工。
        # O54(o53 game_01 实证):闸门带「买不起」条款也会翻板 —— 银行一跨 400
        # 持有期翻 false,塔(150)抢在 pending Nexus 付款前吃银行,科技链在反复
        # 翻板中饿死(t=273 无控制核心)。持有期 = 想开矿 或 Nexus 在建(含未付款),
        # 不问银行;期间塔(O50 闸)/科技链(O43)/追加产能/研究/出兵全部让位。
        # (取代 E3k 的 _expansion_reserve —— 它只看「想开矿且买不起」,漏了 pending 窗口)
        # O156-②(o155-vh-zerg-power game_02 实证):预走位但还没开工的 Nexus
        # 也未被计入 holding，塔链持续注册、Nexus 工人在目标点干等 800s+。
        _expand_holding = (
            _want_expand
            or self.manager_mediator.get_building_counter[UnitID.NEXUS] > 0
            or self.ai.not_started_but_in_building_tracker(UnitID.NEXUS) > 0
        )
        # O307-③(o306c game_05 实证):holding 死锁自愈 —— Nexus 预走位等钱
        # 90s+ 未开工(game_05 持了 326s),科技链/塔/研究全冻结,气烂 1300
        # 两波滚死。超时且仍买不起 → 撤销预走位派工(镜像 assimilator 反卡死),
        # 解锁 45s 让科技链/产线恢复,冷却后动态开矿自然重评。
        if _expand_holding:
            self._expand_holding_since = self._expand_holding_since or self.ai.time
        else:
            self._expand_holding_since = None
        if expand_holding_should_abort(
            self.ai.time - (self._expand_holding_since or self.ai.time),
            self.ai.not_started_but_in_building_tracker(UnitID.NEXUS),
            self.ai.can_afford(UnitID.NEXUS),
        ):
            _tracker = self.manager_mediator.get_building_tracker_dict
            for _tag, _info in list(_tracker.items()):
                if _info[TRACKER_ID] == UnitID.NEXUS:
                    self.manager_mediator.get_building_counter[UnitID.NEXUS] -= 1
                    _tracker.pop(_tag)
            self._expand_holding_since = None
            self._expand_abort_until = self.ai.time + 30.0  # O309-③:45→30
            _expand_holding = False
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": "O307:开矿持有>60s未开工,撤销派工解锁科技链(冷却30s)",
            })
        elif self.ai.time < getattr(self, "_expand_abort_until", 0.0):
            _expand_holding = False
        # O166: 这些闸在 update 尾部的方法(_spend_bank/_build_extra_production/
        # _build_forward_pylon)里也要读，挂到实例上避免 NameError。
        self._expand_holding = _expand_holding
        # 基地被打掉重建：真的丢过基地(峰值>当前)且 < 目标基地数时进入重建模式。
        # E6b 回归实证:只看"当前<目标"会在开局(1<max_bases)就误触发,
        # 造农民/出兵整局被掐死 —— 必须带峰值门(见 production_plans.base_rebuild_active)。
        # O84(n5m-zerg-power game_02 实证):重建模式不再冻结 SpawnController ——
        # 原设计(_base_rebuild 时不注册出兵)在 Zerg Power 的基地拉锯下=永久停产:
        # 3 星门+FB 就绪、矿 1000+/气 2500+/人口空闲,暴风恒 1 艘 265s 零增长;
        # 而重建 Nexus 的钱已由 _expand_holding 门(塔/科技/研究/追加产能全让位)保护,
        # 不需要再冻出兵 —— O56 同构:舰队 > 下一矿,舰队本来就是赢的方式。
        self._peak_townhalls = max(self._peak_townhalls, self.ai.townhalls.amount)
        _target_bases = self._flow.auto_expand.max_bases if (
            self._flow.auto_expand and self._flow.auto_expand.max_bases
        ) else None
        _base_rebuild = base_rebuild_active(
            self.ai.townhalls.amount,
            self._peak_townhalls,
            _target_bases,
            self.ai.can_afford(UnitID.NEXUS),
            self._rush_active,
        )
        # O97-B(o96 局5 实证):首舰已出+单矿+想开矿且买不起 → SpawnController
        # 暂停攒钱(局5:矿恒 50-250 被舰队/塔吃光,Nexus 400 攒不出,单矿
        # 20 农民打到死)。买得起/威胁/rush 自解除;农民照造(=收入来源)。
        # 状态读的是上帧值(_update_*_state 在后段才跑),一帧滞后无妨。
        # O151-①:预留的 rush 否决改急性口径(家 40 格有敌才算急性)——
        # 波间隙的 rush latch 不再压扩张攒钱(o150 局2:235 接触的 latch
        # 压住预留,塔照吃,Nexus 拖到 546)
        _rush_blocks = rush_blocks_reserve(
            self._rush_active,
            sum(
                1 for u in self.ai.enemy_units
                if not u.is_structure and is_combat_type(u.type_id)
                and u.position.distance_to(self.ai.start_location) < 40
            ),
        )
        _fleet_reserve = fleet_expansion_reserve(
            fleet_transitioned=self._fleet_transitioned,
            first_fleet_seen=(
                self._first_fleet_seen() if self._fleet_transitioned else False
            ),
            bases=self.ai.townhalls.amount,
            want_expand=_want_expand,
            can_afford_nexus=self.ai.can_afford(UnitID.NEXUS),
            threat_active=self._threat_active,
            rush_active=_rush_blocks,
            # O145-②:评分 ≥25 豁免首舰前提(首舰前科技链会把 Nexus 的 400
            # 吃光 —— o144 局3:SG 570/FB 616,bases=1 到死)
            defense_score=self._defense_score(),
        )
        # O105-①b(o104 局2 实证):过渡期站稳想开矿但买不起 → 出兵暂停攒钱
        # (局2:站稳但矿恒 0-170,Nexus 400 攒不出,扩张门形同虚设)。
        # rush/threat 不预留;买得起即解除。
        _transition_reserve = transition_expand_reserve(
            self._transition_active,
            self._tr_expand_ready,
            self.ai.can_afford(UnitID.NEXUS),
            self._threat_active,
            rush_active=_rush_blocks,
        )
        # O106-②(o105 局3 实证):重建窗科技链(cyber→SG→FB)攒钱预留 ——
        # 局3 窗内矿被电池×2+塔重建+叉/追猎吃光,SG 的 150 矿 110s 凑不出;
        # 下一件科技缺失且买不起 → 停产攒钱,威胁/rush 不预留,买得起即解除。
        _next_tech = None
        if self._fleet_transitioned:
            _core = set(self._flow.core_structure_ids())
            for _sid in (UnitID.CYBERNETICSCORE, UnitID.STARGATE, UnitID.FLEETBEACON):
                if _sid in _core and not self._structure_present_or_pending(_sid):
                    _next_tech = _sid
                    break
        _tech_reserve = fleet_tech_reserve(
            fleet_transitioned=self._fleet_transitioned,
            first_fleet_seen=(
                self._first_fleet_seen() if self._fleet_transitioned else False
            ),
            next_tech_missing=_next_tech is not None,
            next_tech_affordable=(
                self.ai.can_afford(_next_tech) if _next_tech is not None else True
            ),
            threat_active=self._threat_active,
            rush_active=self._rush_active,
            # O115-③:落位停滞确认(watchdog 已开火) → 预留解除,
            # 地面回填优先(o114 局3:预留永开 → army 清零后零补员)
            tech_stalled=bool(self._fleet_stall_fired),
            # O122-①(o121b 局1):先有一艘虚空能打的,再攒 FB ——
            # 预留不得挡虚空填窗(局1:为 FB 攒资把虚空也掐死,波到脸两头空)
            voidray_pending_or_seen=(
                cy_unit_pending(self.ai, UnitID.VOIDRAY)
                or self.manager_mediator.get_own_unit_count(
                    unit_type_id=UnitID.VOIDRAY
                )
                > 0
            ),
        )
        # O131-②(o130 局2/局5 实证):暂停型 gw_reserve 废除(死锁发生器:
        # 暂停产兵攒钱,塔照建照吃,永远攒不到),改排队型 —— 2 塔后 GW<cap
        # 时塔/水晶让位,SpawnController 永不停,GW 钱到就拍
        _gw_priority = tower_yields_gateway_chain(
            self._transition_active,
            gateways_have=(
                len(self.manager_mediator.get_own_structures_dict[UnitID.GATEWAY])
                + len(self.manager_mediator.get_own_structures_dict[UnitID.WARPGATE])
                + self.manager_mediator.get_building_counter[UnitID.GATEWAY]
            ),
            gateway_cap=(
                # O208:Zerg Timing 混编地面需要 2 兵营，塔链让位目标同步。
                2
                if (
                    self._flow.transition
                    and self._opp_race == "zerg"
                    and self._ai_build == "timing"
                )
                else (self._flow.transition.gateway_cap if self._flow.transition else 0)
            ),
            # O132-③:cannons 吃就绪峰值 latch —— 塔损不反锁兵营链
            cannons_ready=self._cannons_ready_peak,
        )
        # O109-②(o108 局3 实证):首舰后 SG 爬坡预留 —— 局3 SG 恒 2 座 600s+,
        # 暴风即产即吃矿,追加门槛 250 恒不触发;停产一艘攒 SG3 = 产能复利。
        # O152-③(o151 尸检:胜局 SG 3-9/暴风 27-29,败局 SG 1-3):FB 在链
        # 即启动爬坡(不等首舰 —— 首舰要等 SG→FB→43s 产出一整链,SG 爬坡
        # 与首舰并行才对);气体闸计在途气矿;carrier 流 bonus+1
        _sg_reserve = False
        if (
            self._flow.transition is not None
            and self._fleet_transitioned
            and self._structure_present_or_pending(UnitID.FLEETBEACON)
            and self._flow.extra_production is not None
            # O176:FB 已派工但买不起时,追加星门会抽干 FB 资金窗,先让位。
            and not self._fb_waiting
        ):
            _gas_per_base = [
                # O152-③:在途气矿也算(21s 后就是产能;SG 建造 43s,无 stale 风险)
                self.ai.gas_buildings.closer_than(12, th).amount
                for th in self.ai.townhalls.ready
            ]
            _sg_reserve = fleet_stargate_reserve(
                True,
                sg_have=(
                    len(self.manager_mediator.get_own_structures_dict[UnitID.STARGATE])
                    + self.manager_mediator.get_building_counter[UnitID.STARGATE]
                ),
                sg_target=gas_gated_stargate_target(
                    self._flow.extra_production.cap,
                    _gas_per_base,
                    bonus=stargate_gas_gate_bonus(False)
                    + carrier_sg_bonus(self._flow.transition is not None),
                ),
                can_afford_sg=self.ai.can_afford(UnitID.STARGATE),
            )
        # O131-③(o130 局2/局5 实证):预留死锁保险丝 —— 任何预留连续
        # >60s 且矿 <150(目标价一半)→ 强制全部解除(簿记)。
        # O135 后预留只闸建筑注册(产兵永动,建筑用余钱),保险丝防的是
        # 「余钱永远不够 → 建筑永久冻结」的镜像死锁
        _any_reserve = (
            _fleet_reserve or _transition_reserve or _tech_reserve or _sg_reserve
        )
        if _any_reserve and self._reserve_since is None:
            self._reserve_since = self.ai.time
        elif not _any_reserve:
            self._reserve_since = None
        # O214:Zerg Timing 的二矿资金窗常被 O131 保险丝在 60s 内打断,
        # 导致防御把 Nexus 400 矿抽干、单矿经济崩盘。扩张预留期间延长
        # 到 120s/400minerals(打断线 200),给 Nexus 更长的攒钱窗口。
        _expand_reserve = _transition_reserve or self._expand_holding
        _fuse_timeout = 120.0 if (
            _expand_reserve
            and self._opp_race == "zerg"
            and self._ai_build == "timing"
        ) else 60.0
        _fuse_min_price = 400.0 if (
            _expand_reserve
            and self._opp_race == "zerg"
            and self._ai_build == "timing"
        ) else 300.0
        if reserve_deadlock_break(
            self._reserve_since,
            self.ai.time,
            self.ai.minerals,
            timeout=_fuse_timeout,
            min_price=_fuse_min_price,
        ):
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": (
                    f"O131:预留死锁保险丝熔断(矿{self.ai.minerals:.0f},"
                    f"fleet={_fleet_reserve},expand={_transition_reserve},"
                    f"tech={_tech_reserve},sg={_sg_reserve})"
                ),
            })
            _fleet_reserve = _transition_reserve = False
            _tech_reserve = _sg_reserve = False
            self._reserve_since = None
        # O6: ares AutoSupply 同样不查 can_afford(auto_supply.py:52-55 直接调
        # BuildStructure),钱不够农民就钉在 pylon 建造点干等 —— 只在买得起时注册,
        # supply 缺口的判定仍归 ares 内部。
        # E3g:return_true_if_supply_required=False 必须显式给 —— 默认 True 时
        # supply 紧张期它每帧返回 True 截断 MacroPlan,后面的 UpgradeController/
        # SpawnController 整段饿死(e3g game_01:120s 零航母零研究,gas 囤 2000+)。
        # E3h:水晶紧急通道 —— supply_left ≤ 2 时即便买不起也注册(卡人口 68-100s
        # 的代价比钉一个工人大,见 should_register_autosupply)。
        # O103-③(o102 局3/局5 实证):forge 未落地前水晶让位 —— supply_left 15
        # 时水晶 #3(t≈108-116,100 矿)抢 forge 资金窗,forge 125-129 才落地,
        # 首塔 190-225 vs 波次 155-237。defense_urgent = rush 确认/过渡/疑似;
        # 人口紧急(≤4)照建(E3h 语义优先)。_presumed_rush 提前到这里算,
        # F2 段复用(状态均为一帧滞后,无妨)。
        _presumed_rush = presumed_rush_defense(
            getattr(getattr(self.ai, "enemy_race", None), "name", None) == "Zerg",
            self._flow.transition is not None,
            self._scout_verdict_done,
            self._rush_confirmed,
            self.ai.time,
            scout_lost=self._scout_lost(),
        )
        # O300-②:_build_flow_structures 的停气闸也读 presumed(局部变量
        # 不出 update 作用域),存属性供跨方法读。
        self._presumed_rush = _presumed_rush
        # O133-③(o132 timing 局1/2/5 实证):vs Zerg 二判仍 unknown 且 t≥200
        # → 按 presumed 同等级拉防御(F2 target 2 塔)——unknown ≠ 等到接触
        # O207:Zerg Timing 局若首判/二判仍是 unknown，t≥200 起按 presumed
        # 同等级拉 2 塔防御，不能等到接触再拍 forge。
        _unknown_defense = unknown_verdict_defense(
            getattr(getattr(self.ai, "enemy_race", None), "name", None) == "Zerg",
            self._flow.transition is not None,
            self._verdict,
            self._rush_confirmed,
            self._transition_active,
            self.ai.time,
            enabled=(self._ai_build == "timing"),
        )
        # O117-②:防御紧急旗标每帧更新(main.py O11 撤回豁免读)
        self._defense_urgent = (
            self._rush_confirmed
            or self._transition_active
            or _presumed_rush
            or _unknown_defense
        )
        # O150-③(o149 zerg-power 实证):greedy 早判(t≤110)退保 ——
        # presumed 在 verdict 落地时自动关(塔不再拍),在建 forge 是最后
        # 一笔:取消退 75%,不为不存在的 rush 付 250 矿保险;盾升级要
        # forge 时由 upgrade_tech_buildings 补建(运营局负担得起)
        if (
            not self._presumed_forge_cancelled
            and cancel_presumed_forge(self._verdict, self.ai.time)
        ):
            for s in self.manager_mediator.get_own_structures_dict[UnitID.FORGE]:
                if not s.is_ready:
                    s(AbilityId.CANCEL)
                    self._presumed_forge_cancelled = True
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": "O150:greedy早判退保,取消在建 forge(退75%)",
                    })
        _enemy_home_now = sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and is_combat_type(u.type_id)
            and u.position.distance_to(self.ai.start_location) < 40
        )
        _cannons_ready_home = sum(
            1 for s in self.ai.structures.ready
            if s.type_id == UnitID.PHOTONCANNON
            and s.position.distance_to(self.ai.start_location) < 25
        )
        # O129:冲刺总闸 —— presumed/rush 确认起,到「forge 就绪+首塔落地+
        # 首叉在产」全链路完成前,一切非链开销(农民/水晶/GW2+/气矿/研究)
        # 统一掐死;接触(敌进家 ≥2)即退出交还 F2;链完成自解除。
        # O168:8 农民 carrier 核心科技缺失期不 sprint，避免 120s 冻结把
        # Cybercore/Stargate/气矿全部拖后；真实 rush 局 _early_core_missing=False
        # → sprint 正常触发，Forge/首塔/首叉链不受影响。
        # O216f:Zerg Timing 不是 Rush,不需要 120s 全链冲刺;把 max_age 压到
        # 60s,让 F2 防御和科技链更快并行,避免 sprint 把经济锁死在 forge/首塔。
        _sprint_max_age = (
            60.0
            if (self._opp_race == "zerg" and self._ai_build == "timing")
            else 120.0
        )
        _sprint = (
            defense_sprint_active(
                has_transition=self._flow.transition is not None,
                defense_urgent=self._defense_urgent,
                forge_ready=any(
                    s.is_ready
                    for s in self.manager_mediator.get_own_structures_dict[UnitID.FORGE]
                ),
                first_cannon_ready=_cannons_ready_home > 0,
                first_zealot_seen=(
                    self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.ZEALOT)
                    > 0
                    or cy_unit_pending(self.ai, UnitID.ZEALOT)
                ),
                enemy_home=_enemy_home_now,
                sprint_age=(
                    self.ai.time - self._sprint_since
                    if self._sprint_since is not None
                    else 0.0
                ),
                max_age=_sprint_max_age,
            )
            # O207:Zerg Rush/Timing 的早期防御链优先于核心科技排队;
            # 核心科技缺失期仍允许冲刺，避免首塔被 cybercore 资金窗卡死。
            and (not _early_core_missing or self._is_zerg_rush_timing())
        )
        # O130-①:逃逸阀计时(冲刺 >120s 强制退出,链断不拖死全局)
        if _sprint and self._sprint_since is None:
            self._sprint_since = self.ai.time
        elif not _sprint:
            self._sprint_since = None
        self._sprint_active = _sprint  # 供 _rush_gateway_boost 等闸外方法读
        # O133-②:过渡期 250-300 防御冲刺旗标(t≥240+过渡 active+verdict≠greedy)
        # —— 塔补到 3/GW 让位闸旁路,不管清净/威胁(timing 波必来);
        # 供 F2 注册闸/塔目标/_rush_gateway_boost/_build_extra_production 读
        # O207:Zerg Timing 局波次 273-289 到脸，启用 t≥240 的防御冲刺，
        # 临时把塔补到 3 并旁路 GW 让位闸，避免波到脸时只有 1-2 塔。
        self._timing_sprint = transition_timing_sprint(
            self._transition_active,
            self._verdict,
            self.ai.time,
            enabled=(self._ai_build == "timing"),
        )
        # O144-③:地面 floor 激活闸(rush 确认 / 敌可见地面 ≥4;纯运营局
        # 不产地面,矿全进舰队科技链 —— O134 无差别 floor 挤科技钱实证)
        # O253 已回滚(o253 双 lane 0-7 全速败实证):t≥240 floor 常开把
        # SG/FB/塔的钱吃成叉/追猎,舰队更晚、早期更脆,比 bank 闲置更糟。
        self._floor_active = ground_floor_active(
            self._rush_confirmed,
            sum(
                1 for u in self.ai.enemy_units
                if not u.is_structure and not u.is_flying
                and is_combat_type(u.type_id)
            ),
        )
        # O255-③(o254 双 lane 0-10 尸检):Zerg Timing + verdict=unknown +
        # t≥220 + 舰队未出 → 死窗叉子 floor(仅叉 cap 3,追猎 cap 0 ——
        # 与 O253 的区别:不碰气、上限极小、舰队一出即退)。波 280-310 到脸时
        # 不再 0 地面裸接;o252/o254 长局与速败的分野就是这波硬币。
        self._floor_unknown_zt = zerg_timing_unknown_floor(
            self._opp_race == "zerg" and self._ai_build == "timing",
            self._verdict,
            self.ai.time,
            self._first_fleet_seen(),
        )
        if self._floor_unknown_zt:
            self._floor_active = True
        # O279:预警 latch 接触即解除(威胁响应包接管,预警使命完成)
        if self._wave_incoming and (self._threat_active or self._rush_active):
            self._wave_incoming = False
        # O146-①:急性窗标记(敌进家 40 格 / threat 激活或 25s 内)——
        # 农民下限与刹车家族都读它;慢性状态(rush latch/sprint/过渡态
        # 本身)一律不得压农民
        if self._threat_active:
            self._threat_last_active = self.ai.time
        _acute = (
            _enemy_home_now >= 1
            or self._threat_active
            or _sprint
            # O147 实证(smoke-o147):sprint(防链未成)必须算急性窗 ——
            # 否则农民下限(<16 必产)在 forge 竞速窗与关键三件抢矿,
            # forge 驻车 50s(99.6 钉点,152.7 才落地)。O146 的口径本意
            # 是压慢性状态,sprint 是 O129 的急性防链窗
            or (
                self._threat_last_active is not None
                and self.ai.time - self._threat_last_active <= 25.0
            )
        )
        # O136:坡口墙状态每帧刷新(rush 确认/presumed 时武装)——
        # combat _rush_defend_anchor 读 _wall_hold_point(叉子墙后站位),
        # 协防读 _wall_gap_point/_wall_sealed(封口前农民肉身堵缝)
        # O255-②(o254 尸检):unknown 保守防御(t≥200)同样武装 —— presumed
        # 在 verdict=unknown 落地(~80s)即解除,Timing 波 280-310 到脸时墙后
        # 站位/堵缝全黑,狗群直穿矿线屠农(o254a game_03/04:25→6)。
        # O258-②:ZT unknown 窗 force 重开墙槽(O138 关断只针对 rush 早期窗),
        # 武装/封口判定/建造链才能拿到槽位数据。
        _wall = self._wall_slots(
            force=(
                self._opp_race == "zerg"
                and self._ai_build == "timing"
                and _unknown_defense
            )
        )
        if _wall is not None and (
            self._rush_confirmed or _presumed_rush or _unknown_defense
        ):
            _gap = _wall[2]
            _hp = wall_hold_point(
                (_gap.x, _gap.y),
                (self.ai.start_location.x, self.ai.start_location.y),
            )
            self._wall_hold_point = Point2(_hp)
            self._wall_gap_point = _gap
            self._wall_sealed = all(
                any(
                    s.is_ready and s.position.distance_to(slot) < 2.0
                    for s in self.ai.structures
                )
                for slot in _wall[1]
            )
            if not self._wall_logged:
                self._wall_logged = True
                self.ai._events.append({
                    "t": round(self.ai.time, 1),
                    "msg": (
                        f"O136:坡口墙武装(缝=({_gap.x:.0f},{_gap.y:.0f}),"
                        f"槽={','.join(f'({s.x:.0f},{s.y:.0f})' for s in _wall[1])})"
                    ),
                })
        else:
            self._wall_hold_point = None
            self._wall_gap_point = None
            self._wall_sealed = False
        if _presumed_rush and not self._presumed_logged:
            # O108-③(o107 局1):presumed 到底哪秒启动直接决定 forge/首塔时点,
            # 簿记一次(速骰局尸检要这个数)
            self._presumed_logged = True
            self.ai._events.append(
                {"t": round(self.ai.time, 1), "msg": "O98:presumed兜底启动(forge+首塔)"}
            )
        # O124-③(o123 系列实证):首叉冲刺 —— rush 确认/过渡 + 有就绪兵营
        # + 首叉未出未在产 + 矿 <100 → 水晶/农民全停,直到首叉在产
        _zealot_sprint = first_zealot_sprint(
            defense_urgent=(
                self._rush_confirmed or self._transition_active or _presumed_rush
            ),
            gateway_ready=any(
                g.is_ready
                for g in self.manager_mediator.get_own_structures_dict[
                    UnitID.GATEWAY
                ]
            ),
            zealot_seen_or_pending=(
                cy_unit_pending(self.ai, UnitID.ZEALOT)
                or self.manager_mediator.get_own_unit_count(
                    unit_type_id=UnitID.ZEALOT
                )
                > 0
            ),
            minerals=self.ai.minerals,
        )
        # O168:8 农民 carrier 前期矿极紧，核心科技缺失期间 AutoSupply 不因
        # can_afford 就注册水晶，只在 supply_left<=2 紧急通道放行。
        if should_register_autosupply(
            self.ai.can_afford(UnitID.PYLON) and not _early_core_missing,
            self.ai.supply_left,
        ) and not forge_first_pylon_yield(
            defense_urgent=(
                self._rush_confirmed or self._transition_active or _presumed_rush
            ),
            forge_present=bool(
                self.manager_mediator.get_own_structures_dict[UnitID.FORGE]
            ),
            supply_left=self.ai.supply_left,
        ) and not (
            # O119-①:科技攒钱预留期水晶也让位(人口紧急 ≤2 照建,E3h 兜底)
            _tech_reserve and self.ai.supply_left > 2
        ) and not _zealot_sprint and not (
            # O124-③:首叉冲刺期水晶停;O129:冲刺总闸(supply ≤1 应急放行)
            _sprint and self.ai.supply_left > 1
        ) and (
            # O156-②:AutoSupply 被 O11 撤回后 10s 内不重复注册(非紧急人口)。
            # 原行为：水晶工被撤后 AutoSupply 每帧重派新工，造成 idle_builder
            # 刷屏且水晶抢 forge/Nexus 资金窗(o155 game_01/02 实证)。
            # O192-①(o191-vh-zerg-timing game_01 实证):开局前 60s 即使 supply_left<=2,
            # 也强制 2s 冷却,让被撤 PYLON 农民先采矿,避免同一农民反复钉点 30s+
            # 空转;60s 后恢复紧急通道立即补人口。
            _pylon_redispatch_ok(
                self.ai.time,
                self.ai.supply_left,
                getattr(self.ai, "_o11_released_at", {}).get(UnitID.PYLON),
                cooldown=_DEFENCE_REDISPATCH_CD,
                can_afford=self.ai.can_afford(UnitID.PYLON),
            )
        ):
            macro_plan.add(
                AutoSupply(
                    base_location=self.ai.start_location,
                    return_true_if_supply_required=False,
                )
            )
        # O109-①(o108 局3 实证):舰队期人口 buffer —— 暴风 6 人口/艘,
        # AutoSupply 默认阈值太紧(supply_block×3:89/90、86/82 反超停产);
        # supply_left ≤8 且买得起就直接补,BuildStructure 自带 max_on_route 去重
        # O166: 单矿早期先保科技和 Nexus，buffer 水晶不急。
        if (
            fleet_supply_buffer_needed(
                self._flow.transition is not None
                and (self._transition_active or self._fleet_transitioned),
                self.ai.supply_left,
            )
            and self.ai.can_afford(UnitID.PYLON)
            and not _early_core_missing
            and not _nexus_waiting
            # O198:buffer 水晶直接走 BuildStructure,钱在派工后被抽干会触发 idle_builder;
            # 加收入守卫:到位时矿+走位收入能覆盖 100 矿才派,农民不钉点等钱。
            and dispatch_viable(
                self.ai.minerals, self._mineral_income_per_sec(), 3.0, 100.0, buffer=15.0
            )
            # O198:FleetBeacon 已可建却买不起时,100 矿 buffer 水晶也让位,
            # 优先把 300/200 FB 资金窗攒出来,否则舰队转型永远完不成。
            and not self._fb_ready_to_build()
        ):
            # O119-②b(o118b 局1/局5 实证):入侵期 buffer 水晶落矿线深处 ——
            # 落前线/生产区会被狗顺路点杀(水晶一死,带电槽归零,塔/科技
            # 全成 no_placement);矿线深处与首塔同遮蔽位
            _pa = None
            _ramp = getattr(self.ai, "main_base_ramp", None)
            _mh = self.ai.mineral_field.closer_than(10, self.ai.start_location)
            if self._defense_urgent and _mh and _ramp is not None and getattr(_ramp, "top_center", None):
                _cx = sum(m.position.x for m in _mh) / len(_mh)
                _cy = sum(m.position.y for m in _mh) / len(_mh)
                _pa = Point2(cannon_safe_anchor(
                    (_cx, _cy), (_ramp.top_center.x, _ramp.top_center.y)
                ))
            self.ai.register_behavior(
                BuildStructure(
                    self.ai.start_location, UnitID.PYLON,
                    max_on_route=1, closest_to=_pa,
                )
            )
        # E3k-fix:开矿排在研究/出兵之前 —— UpgradeController(prioritize) 会把
        # plan 尾部的 ExpansionController 饿死(e3k game_03 实证)。
        # prioritize=True = 欠费也先派工人走位(钉在扩张点等 400 是正常开矿打法,
        # O11 watchdog 已对基地建筑豁免,见 main.py)。
        # O19:预走位收窄 —— 「预计到达时可负担」才允许欠费派工(dispatch_viable);
        # 到位还等不起的不派(农民照采,Nexus 起建时间不变),不再钉点干等
        # (e7e8 bench:NEXUS 干等 2-7 次/局,终局 1144s 仍有)。
        # 基地重建也需要开矿
        if _want_expand or _base_rebuild:
            # B7③(QueenBot 扩张动态 max_pending):矿>1250 且离 max_bases 有富余时
            # 允许多片矿同建(治 bank+扩张慢);rush 否决在判据层(should_expand_dynamic)。
            # _pending=1 时与旧行为完全一致(to_count=+1, max_pending=1)。⚠️ 未验证
            _headroom = (
                _target_bases - self.ai.townhalls.amount if _target_bases else 1
            )
            _pending = expansion_max_pending(
                self.ai.minerals, headroom=max(1, _headroom)
            )
            _preposition = dispatch_viable(
                self.ai.minerals,
                self._mineral_income_per_sec(),
                self._expansion_walk_time(),
                self.ai.calculate_cost(UnitID.NEXUS).minerals,
                # O181:留 25 矿 buffer，避免 Nexus 工位刚出发就被塔/兵抽干；
                # 50 矿在部分图会把二矿拖慢 30s+，导致前期防御/舰队整体后移。
                # O206(o205-vh-zerg-power 败局):Nexus 工人被钉 3.5min+ 不采矿,
                # 采矿损失远超二矿晚 10-20s。buffer 提到 75 矿,让工人接近
                # 凑够 400 矿再出发,减少工地空转。
                buffer=75.0,
            )
            # O210:O189 强制开二矿时立即预走位,不等 dispatch_viable 凑够
            # 475 矿(原 buffer=75 导致 150 矿触发后仍不派工,二矿永远落不了地)。
            # O281:ZT 首扩定点口袋矿(避 305-320s 死窗波路径,o280 基线 0-9
            # 实证 natural 拍进波路径);定点时 max_pending 钳 1,防同点双派。
            _exp_loc = self._zt_pocket_expand_target()
            if _exp_loc is not None:
                _pending = 1
            macro_plan.add(
                ExpansionController(
                    to_count=self.ai.townhalls.amount + _pending,
                    max_pending=_pending,
                    prioritize=_preposition or self._o189_forced_expand,
                    location=_exp_loc,
                )
            )
        # 升级(O1/O8/O10):研究交 UpgradeController 并进 MacroPlan 且 prioritize=True ——
        # 研究就绪但买不起时返回 True 截断 plan,SpawnController 暂停花钱 → 资源攒给
        # 研究(O8 长研究预留,Forge/科技建筑一好就点);建筑缺失/前置未就绪时返回 False
        # 不阻塞 plan(不会存款死锁)。前置科技建筑不走它的 auto tech-up(ares TechUp
        # 不查 can_afford,O1 实证),由带守卫的 _build_core_structure 补建(见 update 尾部)。
        # ⚠️ E3 回归:rush_active 期间研究整体让位(不注册)——预留会把 rush 响应包
        # (叉子/塔都在 plan 后续)饿死;rush 解除后自动恢复预留。
        # E3k:开矿攒钱预留期间研究同样让位(Nexus > 研究 > 出兵)。O51:含 pending 等待期。
        # O134-②(o133 局2 实证):地面保底未达 → 研究不得截断产兵 —— 局2
        # cyber 就绪(~400)后 UC prioritize=True 为空军升级攒钱、每帧截断
        # plan,SpawnController 拿不到帧也拿不到矿(矿恒 0-50,气 2900 烂着),
        # 叉卡 1 直到 525 波;floor 未达时 prioritize 翻假(研究买得起才点)
        _pf0 = self._flow.pre_fleet
        _floor_unmet = (
            # O144-③:floor 未激活(纯运营局)→ 不干预 UC 优先级
            self._floor_active
            and ground_floor_unmet(
                _pf0 is not None,
                self._transition_active,
                self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.ZEALOT)
                + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.STALKER),
                (_pf0.cap + _pf0.cap2) if _pf0 else 0,
            )
        )
        _upgrades = self._flow.upgrade_ids()
        if (
            _upgrades
            # O103-①:过渡期全程停研究(接触式 rush_active 60s 解除后 UC 恢复
            # 预留会把守窗叉子饿死 —— o102 局3/局5 兵营空转 26s 根因)
            and not research_paused_for_rush(self._rush_active, self._transition_active)
            and not _rebuild_nexus
            and not _expand_holding
            and not _sprint  # O129:冲刺期研究停(链外开销)
        ):
            macro_plan.add(
                UpgradeController(
                    _upgrades,
                    base_location=self.ai.start_location,
                    auto_tech_up_enabled=False,
                    prioritize=not _floor_unmet,  # O134-②:见上
                )
            )
        # 兵种配方从 flows.yml 当前流派读(spawn_dict 只含 proportion>0 的兵种)。
        # freeflow_mode 按流派配置:多兵种流派必开(true=配比只当优先序不当上限),
        # 否则兵力在精确配比点永久死锁(C3c 诊断出的 stalker 停产第二根因)。
        # E3b: rush_active 期间 spawn_target 从前线切回防守 —— 前线折跃点=敌群方向,
        # 响应兵种一落地就进狗群分批送死(trickle);平时才用 F1 前线投送。
        # B4 防守三角:防守落点不再是基地中心 —— 分矿承压折跃被攻击的分矿
        # (② sharpy 防御性折跃),主基承压折跃坡口顶端下 4 格集结点
        # (① sharpy PlanHeatDefender),见 _rush_spawn_target。⚠️ 未验证
        # O56(o55b game_01 实证):持有期不再冻出兵 —— 饱和农民(≥16/矿)让 want_expand
        # 在中局常驻,SpawnController 被 _expand_holding 冻结:3200 气烂在银行、
        # 4 星门闲置、只有 1 航母,波次一波波磨死我们。矿的敌人是建筑(塔/科技,
        # 已被 O43/O50 冻),不是部队 —— 航母本来就是赢的方式,舰队 > 下一矿。
        # E3k 原意(Nexus 不排在叉后)由 rush 门保留(rush 期 SpawnController 照停)。
        # O126-②:六道闸统一仲裁(优先级:首叉冲刺>叉子保底>GW链>forge/塔>
        # 科技>扩张);O126-①:叉子保底(空闲GW+矿≥100+需要地面)凌驾一切
        # 预留 —— o125 局1:GW1 完工撞上 forge+GW2 抢矿,首叉拖 15s
        # O135(o134 系列 0-5 尸检):暂停型预留体系整体证伪 —— 预留不再
        # 暂停产兵(攒钱期间建筑照吃 = 兵营空转死锁,o134 局1:42 农 2 GW
        # 就绪 t=542 仅 3 叉)。SpawnController 永动,攒钱只暂停建筑注册
        # (F2/水晶侧闸门保留);仅剩基地清零应急(rebuild_nexus)停产
        _ground_army_now = (
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.ZEALOT)
            + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.STALKER)
        )
        _spawn_pause = spawn_pause_reason(
            rebuild_nexus=_rebuild_nexus,
            expand_holding=self._expand_holding,
            is_zerg_timing=(
                self._opp_race == "zerg" and self._ai_build == "timing"
            ),
            nexus_unstarted=self.ai.not_started_but_in_building_tracker(
                UnitID.NEXUS
            ),
            minerals=self.ai.minerals,
            nexus_price=self.ai.calculate_cost(UnitID.NEXUS).minerals,
            # O298-②:expand_reserve 敌情闸(与 O296-① carrier 闸同口径)
            enemy_supply=sum(
                self.ai.calculate_supply_cost(u.type_id)
                for u in self.ai.enemy_units
                if not u.is_structure and is_combat_type(u.type_id)
            ),
            own_supply=float(self.ai.supply_army),
            # O307-②:地面保底闸 —— 低于 12 supply(≈6 兵)不停产攒 Nexus。
            ground_supply=2.0 * _ground_army_now,
            # O224:transition 期 zealot 吃光 SG/FB 资金窗(SG ~500s/首舰 620+)。
            # 防御已立(t≥240+塔≥2)且 SG/FB 缺失 → 停产攒钱,买得起即恢复。
            # O226(o222-lane2 game_04 实证):塔≥2 门太严(本局塔 1 拖到 281s,
            # O110 SG 自救 no_money),降到 塔≥1 提前开攒,等 O216i 门开就有钱。
            tech_saving=(
                self._opp_race == "zerg"
                and self._ai_build == "timing"
                and self._transition_active
                and self.ai.time >= 240.0
                and self._cannons_ready_peak >= 1
                and (
                    not self._structure_present_or_pending(UnitID.STARGATE)
                    or not self._structure_present_or_pending(UnitID.FLEETBEACON)
                )
            ),
            tech_price=(
                150.0
                if not self._structure_present_or_pending(UnitID.STARGATE)
                else 300.0
            ),
            # O240:气烂 ≥800 且航母配比落后(航母 < 暴风/6)时攒 350 矿点航母;
            # 航母在产/配比达标即恢复产线(自校正)。
            # O294-②(o293a game_04 实证):主基决死窗(敌 28-31 地面、地面兵 3、
            # SG 已毁)停产攒航母=自杀 —— 预留要有就绪 SG(产得出)+ 非急性
            # 威胁期(停得起)才成立。
            carrier_saving=(
                self._opp_race == "zerg"
                and self._ai_build == "timing"
                and not self._transition_active
                and self.ai.vespene >= 800.0
                and self._fb_entities_now > 0
                and carrier_reserve_ok(
                    sg_ready=any(
                        s.is_ready
                        for s in self.manager_mediator.get_own_structures_dict[
                            UnitID.STARGATE
                        ]
                    ),
                    threat_active=self._threat_active,
                    # O295-②(o294a game_02 实证):threat 侦测滞后,E9 翻旗前
                    # 76-supply 波已在途仍停产 —— 敌可见 supply > 我方军队
                    # supply 时产线永不停(攒钱是波间隙特权)。
                    enemy_supply=sum(
                        self.ai.calculate_supply_cost(u.type_id)
                        for u in self.ai.enemy_units
                        if not u.is_structure and is_combat_type(u.type_id)
                    ),
                    own_supply=float(self.ai.supply_army),
                )
                and (
                    self.manager_mediator.get_own_unit_count(
                        unit_type_id=UnitID.CARRIER
                    )
                    + cy_unit_pending(self.ai, UnitID.CARRIER)
                )
                < max(
                    1,
                    self.manager_mediator.get_own_unit_count(
                        unit_type_id=UnitID.TEMPEST
                    )
                    // 6,
                )
            ),
            # O245e 的 immortal_reserve 已废弃(O245e-lane1 game_02 实证:
            # 停产期间塔/探机照抽,275 永远攒不出、地面 0 败亡);
            # 不朽者改用 spawn dict 首位优先序(_effective_spawn O245 块)。
            immortal_saving=False,
        )
        if _spawn_pause is None:
            macro_plan.add(
                SpawnController(
                    army_composition_dict=self._effective_spawn(),
                    spawn_target=(
                        # O210:transition/timing 冲刺期地面兵也走防守集结点,
                        # 避免小股折跃到前线被虫群分批吃掉(trickle)。
                        self._rush_spawn_target() if (
                            self._rush_active
                            or self._transition_active
                            or self._timing_sprint
                        ) else self._front_point()  # F1: 折跃向前线(非主基地),配合前线水晶塔远程投送
                    ),
                    freeflow_mode=self._flow.freeflow,
                )
            )
        elif self.ai.time - getattr(self, "_spawn_pause_logged_at", 0.0) > 30.0:
            # O126-①:暂停簿记 —— 哪道闸停的,30s 节流,下轮尸检直接读
            self._spawn_pause_logged_at = self.ai.time
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": f"O126:产兵暂停={_spawn_pause}(矿{self.ai.minerals:.0f},地面{_ground_army_now})",
            })
        # 运营指挥·通用建筑杠杆 build=<结构>（expand=yes = build=nexus 别名）
        _order = getattr(self.ai, "steer_order", None) or {}
        self._handle_manual_build(_order, macro_plan)
        self.ai.register_behavior(macro_plan)

        # O83-O87 舰队饥饿信号(全帧算一次,三处共用:F2 塔目标 O87 / 追加产能
        # O86 / FB 豁免 O83+O85):气银行 ≥600 + 无 FB + 有星门 + 科技链含 FB。
        # 容量口径(已有+在建星门)拦花钱 —— 星门群会在首座就绪前一起排队
        # (n5m-terran-power game_04),只数就绪的拦不住;就绪口径救 FB(FB 需
        # 就绪星门)。
        # O167:就绪口径阈值 600→400,8 农民开局气收入低但星门就绪后仍要尽快
        # 把气转成 FleetBeacon,避免气烂银行、星门空转。
        _sg_all = self.manager_mediator.get_own_structures_dict[UnitID.STARGATE]
        _fb_pending = self._structure_present_or_pending(UnitID.FLEETBEACON)
        _fb_in_core = UnitID.FLEETBEACON in self._flow.core_structure_ids()
        # O172/O173:用「无 FB 实体」(不含 pending)判断舰队饥饿——o172 game_01
        # 实证 FB 工人被 O11 反复释放,pending 为真但实体永远落不了地,导致原
        # present_or_pending 门被绕过,三矿/过量电池照样建。
        # O175:building_counter 含 pending,不能直接当「实体」;pending-but-stuck
        # 时 still 无实体,必须用真正落成/在建中的建筑计数。
        _fb_entities_now = len(
            self.manager_mediator.get_own_structures_dict[UnitID.FLEETBEACON]
        )
        _fb_structures_now = (
            _fb_entities_now
            + self.manager_mediator.get_building_counter[UnitID.FLEETBEACON]
        )
        # O216d:把实体计数挂到实例,供追加产能/塔帽读取,避免 FB pending 期间被星门抽干。
        self._fb_entities_now = _fb_entities_now
        self._fb_structures_now = _fb_structures_now
        if _fb_entities_now == 0:
            if self._fb_missing_since is None:
                self._fb_missing_since = self.ai.time
        else:
            self._fb_missing_since = None
        # O173/O175:pending 抖动让「当前无实体」每秒翻板;要求连续 5s 无真正
        # 实体才视为缺失,避免一帧 pending 就打开三矿/电池开关。
        _fb_truly_missing = (
            _fb_in_core
            and _fb_entities_now == 0
            and self._fb_missing_since is not None
            and self.ai.time - self._fb_missing_since >= 5.0
        )
        # O175:稳定信号挂到实例,供 _want_dynamic_expand / _spend_bank 读取,
        # 避免三矿门/滚雪球门再用含 pending 的本地计算。
        self._fb_truly_missing = _fb_truly_missing
        # O176(o175-vh-zerg-power game_01 实证):FB 已派工但钱被 F2/追加星门
        # 抽干,工人干等 160s+。无真正实体且买不起时强制让位,比 truly_missing
        # 更早生效,也不影响正常 43s 建造(有钱即不触发);FB 被摧毁后同样生效。
        self._fb_waiting = (
            _fb_in_core
            and _fb_entities_now == 0
            and not self.ai.can_afford(UnitID.FLEETBEACON)
        )
        _fleet_starved_capacity = (
            fleet_gas_starved(
                vespene=self.ai.vespene,
                fb_present_or_pending=_fb_pending,
                stargates=len(_sg_all),
                fb_in_core=_fb_in_core,
            )
            # O168e:FB 是 fleet 产出的硬性前置，FB 未建时一律视为舰队饥饿，
            # 阻止追加星门/塔把 300/300 的资金窗吃掉。
            or (_fb_in_core and not _fb_pending)
        )
        _fleet_starved = fleet_gas_starved(
            vespene=self.ai.vespene,
            fb_present_or_pending=_fb_pending,
            stargates=len([s for s in _sg_all if s.is_ready]),
            fb_in_core=_fb_in_core,
            min_vespene=400.0,
        )

        # F2: 按局势铺防御塔(B+F+Cannon)——框架自动建 forge + 光子炮 + 护盾电池并补前置科技。
        # E2: 配了 expansion_cannons 的流派塔数动态化(min + 敌可见作战单位//4,封顶 max),
        # 每帧重算重注册,ProtossStaticDefence 参数本就支持每帧变。
        # O19:到位可负担才注册 —— ares ProtossStaticDefence→BuildStructure 全程不查
        # can_afford,钱不够也派农民钉在塔点等钱(e7e8 bench idle_builder 最大头:
        # PHOTONCANNON 9-21 次/局)。守卫后不派而非派了再撤(农民照采,塔起建时间不变,
        # E4c 撤回循环前科不存在这个问题)。
        # O19 二轮(o19fix 复验):守卫只挡注册瞬间,收入高时恒真——派工后钱被
        # warp-in/航母抽干 → 钉 6s → O11 撤回 → 下帧守卫又过 → 再派(循环,
        # 同 tag 反复 episode)。加撤回冷却:15s 内被 O11 撤过塔工 → 不注册。
        # O41(game_01 实证):开矿攒钱预留期间 F2 铺塔也让位 —— 预留期存款高,
        # dispatch_viable 恒真,塔持续抽干 Nexus 基金(二矿等钱 5 次、拖到 t=550 才落地,
        # 落地 45s 被 10 分钟波推平)。E3k 注释本意「Nexus 不排在塔后」,
        # 但 F2 注册在 MacroPlan 之外从没接预留闸 —— 这里补上(威胁响应 E9 不受限:
        # 敌压境时塔优先级仍高于开矿)。
        # O50(o49 game_01 实证):闸门从「预留中(买不起)」放宽到「想要开矿中」 ——
        # 银行到 400 的瞬间 can_afford=true → 预留翻 false → 塔抢在 Nexus 开工前
        # 吃掉银行(8 塔 vs 200s 开不出的二矿,振荡泄漏)。开矿意图期间(到 Nexus
        # 开工为止)一律不铺新塔,威胁仍例外。
        # O74(n5c 两连崩实证):例外补上 rush/持有期 —— O71 判 rush 后恰是持续
        # 开矿窗(t=330-550 三矿),每帧都被 _expand_holding 拦下,塔链全程不注册
        # (持有 3.9 分钟,接触时自然只有 1 塔,18 枪兵直接穿)。
        # O98-②(o97 局1/3/4/5 实证):vs Zerg 侦查断链兜底 —— 探机被截杀时
        # t≥120 仍无 verdict 且无接触确认 → 按疑似 rush 先启动节制版防御链
        # (F2 target=1:forge+首塔);verdict 落地或接触确认即翻假交还。
        # O100-④:失联即 presumed(不等 120)。计算已前移到 AutoSupply 闸处(O103-③)。
        # O118-①/O127-①:presumed 防御链手动版(forge 直补+手动首塔),
        # 绕开 PSD 的 per-base 水晶(200 矿买在 forge 前面,o117 局1/局3 实证);
        # 接触/威胁后回落 F2 正常链(满编塔阵)。
        # O128-①(o127 局2 实证):手动链窗口从「presumed 且非 rush」扩到
        # 「防御紧急且 forge 未就绪且未接触」—— 局2:早评 rush(t=81)置
        # rush_active 后手动链即退出,PSD 接管先拍它的水晶(200 矿),
        # forge 拖到 137;forge 就绪/首塔落地即交还 F2(只赛首波)。
        _presumed_manual = (
            (
                _presumed_rush
                or (
                    self._defense_urgent
                    and not any(
                        s.is_ready
                        for s in self.manager_mediator.get_own_structures_dict[
                            UnitID.FORGE
                        ]
                    )
                )
            )
            and _sprint
            and not self._threat_active
            # O202:CarrierOpenerZergRush 早期由 build order 自己铺 forge+双塔,
            # 手动链不抢资源,避免把二塔拖到 5 分钟后。
            and not self._carrier_rush_opener_early()
        )
        if _presumed_manual:
            await self._presumed_defense_chain()
        # O257-①(o256 双 lane 0-10 尸检):ZT unknown 窗(verdict=unknown,
        # t≥200)坡口墙造到封口为止 —— presumed 在 ~80s 解除后墙链停摆,
        # 死窗波(9蟑螂+11狗,~30 supply,305-320s 到脸)无墙可挡,塔/叉/追猎
        # 全组合实测守不住(o252-o256 累计 0-38)。物理封口 + 塔/电池墙后
        # 输出是 rush 局已验证的解;波到脸(threat)即停工转防守。
        # O257-① 墙链曾于 O261-② 关断(o258/o260 双系列实证:墙 400 矿在
        # 261-330s 资金窗挤死塔3与 SG)。
        # O289(2026-08-16 司令拍板 A 案重开)再证伪:o289 双 lane 0-10,
        # 墙 GW 261-369s 反复「派→等→撤→再派」 churn(o289b-g01),
        # one_base×2 —— 墙在资金窗抢钱、二矿开不出,o258 旧证据成立,
        # 重新关断(缝位堵件 combat wall_hold 分支不花钱,保留)。
        if False and (  # noqa: SIM115 — 关断备查,勿删(o289 尸检证据)
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and _unknown_defense
            and not _presumed_manual
            and not self._threat_active
            and self._structure_present_or_pending(UnitID.STARGATE)
            and self._wall_slots(force=True) is not None
            and not self._wall_sealed
        ):
            self._wall_build_chain(self.ai.start_location, force=True)
        # O179/O181:舰队总规模(就绪+在建)在 F2 注册判断与塔目标分支都要读,
        # 提到 if 链之前,避免 UnboundLocalError 并减少重复计算。
        _fleet_total_now = (
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST)
            + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER)
            + cy_unit_pending(self.ai, UnitID.TEMPEST)
            + cy_unit_pending(self.ai, UnitID.CARRIER)
        )
        # O220(o217-lane2 game_02 实证):任一就绪基地 0 就绪塔 = 无防基地,
        # dispatch_viable 资金守卫在矿 20-70 振荡期永远不过 → 新矿落成 100s
        # 零塔被 4 地面抄家。无防基地 F2 必须注册(钉点几秒 > 裸奔 100s)。
        _defenseless_base = any(
            sum(
                1 for s in self.ai.structures.ready
                if s.type_id == UnitID.PHOTONCANNON
                and s.position.distance_to(th.position) < 12
            ) == 0
            for th in self.ai.ready_townhalls
        )
        if (
            (
                self._should_build_defense(_order)
                or (_presumed_rush and not _presumed_manual)
                # O133-③:unknown 判决保守防御(presumed 同级,F2 target 2 塔)
                or _unknown_defense
                # O133-②:timing 冲刺期 F2 强制注册(不管清净/威胁,波必来)
                or self._timing_sprint
                # O220:无防基地强制注册(豁免下方 dispatch_viable 守卫)
                or _defenseless_base
            )
            # O119-①(o118b 局3/4/5 实证):科技攒钱预留激活 → F2 塔重建/电池
            # 整段让位 —— 局3/4/5 SG 停滞 100-300s,watchdog 报 no_money:
            # 钱被 F2 重建持续吃掉。预留激活 ⟹ 非威胁非 rush(判据内含),
            # 地面防御是存量,塔钱 = SG/FB 的钱
            # O133-②:timing 冲刺期不让位(timing 波 273-289 到脸,塔>SG)
            and (not _tech_reserve or self._timing_sprint)
            # O216h(o216g-lane2 game_01 实证):强开二矿的 Nexus 工人已钉点未开工时,
            # 威胁期炮塔持续注册把银行抽干 → 工人钉 15s+ 进「派→等→撤→再派」循环,
            # 二矿永远落不了地。≥2 塔保底后塔链整段让位,银行 ~12s 攒到 400;
            # rush_active 期保命塔除外(六连动不变)。
            and not (
                self.ai.not_started_but_in_building_tracker(UnitID.NEXUS) > 0
                and self._cannons_ready_peak >= 2
                and not self._rush_active
            )
            # O94-A:rush 确认(latch)过的局,F2 不再被持有期拦 —— rush_active
            # 60s 自动解除(t≈190)到首波再接触(t≈195-200)的黑窗恰是锻造炉
            # 就绪窗口,炮塔派工容错被砍光(o93 局1/局2、o92 局1 实证速败)。
            and not (
                _expand_holding
                and not self._threat_active
                and not self._rush_active
                and not rush_defense_past_holding(
                    self._rush_confirmed, self._flow.transition is not None
                )
                # O99-②(o98 局5 实证):presumed 兜底也不能被持有期拦 —— 局5
                # 农民 t≈120 到 16 触发 first_due,持有期把 presumed 的 F2
                # 整段挡死,直到 187 接触才注册第一座塔
                and not _presumed_rush
                # O133-②③:unknown 保守防御/timing 冲刺同样不被持有期拦
                and not _unknown_defense
                and not self._timing_sprint
            )
            # O168:8 农民 carrier 核心科技(CYBERNETICCORE/STARGATE/FLEETBEACON)缺失期，
            # F2 整段让位，避免 PSD 自动拍 Forge/水晶把科技链资金吃掉。
            # 真实 rush/威胁局 _early_core_missing 为假 → F2 正常注册。
            # O207:vs Zerg Rush/Timing 时 forge/首塔必须先于 cybercore 启动,
            # 核心科技缺失期仍注册 F2(节制版/presumed 链并行)，防止 timing 波裸接。
            and (not _early_core_missing or self._is_zerg_rush_timing())
            and redispatch_cooled_down(
                getattr(self.ai, "_o11_released_at", {}).get(UnitID.PHOTONCANNON),
                self.ai.time,
                _DEFENCE_REDISPATCH_CD,
            )
            and (
                dispatch_viable(
                    self.ai.minerals,
                    self._mineral_income_per_sec(),
                    _DEFENCE_WALK_TIME,
                    self.ai.calculate_cost(UnitID.PHOTONCANNON).minerals,
                    # O181:仅 Nexus 在途且舰队未成规模时留 30 矿 buffer，避免炮塔
                    # 把 Nexus/首舰资金抽干；常规威胁窗口不挡 F2 注册。
                    # O204:前期(time<120)建筑资金窗口极紧，把 buffer 提到 75，
                    # 避免 forge/塔/水晶并行派工时农民等钱 idle_builder。
                    buffer=(
                        75.0 if self.ai.time < 120.0
                        # O215:Zerg Timing 二矿/FB 资金窗期间,把 buffer 提到 250,
                        # 确保 Nexus(400矿)/FB(300矿) 优先落袋,避免炮塔重建把
                        # 关键资金窗吃光。常规局保持 75(Rush 等仍走 rush/threat
                        # 分支,buffer 不影响保命塔)。
                        else (
                            250.0 if (
                                _expand_holding and _fleet_total_now < 4
                                and self._opp_race == "zerg"
                                and self._ai_build == "timing"
                            )
                            else (75.0 if _expand_holding and _fleet_total_now < 4 else 0.0)
                        )
                    ),
                )
                # O114-③(o113 局3/局4 实证):防御紧急且 0 塔时跳过资金预估
                # 守卫 —— presumed 65 启动却被守卫拦到 t=110 才注册,forge
                # 133、首塔 185 vs 波次 160,45s 全丢在这
                # O206(o205-vh-zerg-power 败局):plain _presumed_rush 不再 bypass,
                # 避免 Power/Macro 局里 PSD 提前注册把农民钉在工地。
                or f2_dispatch_guard_bypassed(
                    self._rush_confirmed or self._transition_active,
                    sum(
                        1 for s in self.ai.structures.ready
                        if s.type_id == UnitID.PHOTONCANNON
                        and s.position.distance_to(self.ai.start_location) < 25
                    ),
                )
                # O220:无防基地(任一就绪基地 0 就绪塔)同样豁免资金守卫 ——
                # 新矿落成后矿振荡期守卫永假 = 基地裸奔被抄(o217-lane2 game_02)
                or _defenseless_base
            )
            and not _gw_priority  # O131-②:排队型让位(2 塔后 GW 链优先)
            # O131-①/O135:扩张/舰队预留激活 → F2 同步暂停 —— O135 语义反转后
            # 预留只闸建筑侧(产兵永动,钱先喂产线,塔/水晶用余钱);
            # O133-②:timing 冲刺期不让位(波必来,塔优先于扩张/舰队攒钱)
            # O221:无防基地同样不让位(新矿裸奔时被预留拦 52s,敌到脸才注册)
            and (not _transition_reserve or self._timing_sprint or _defenseless_base)
            and (not _fleet_reserve or self._timing_sprint or _defenseless_base)
            # O170/O172:o169/o172 game_01 实证,FleetBeacon 工人被反复释放,
            # pending 为真但实体不落,F2 持续派工造 PhotonCannon/Pylon/电池把
            # 300 矿 FB 资金窗抽干。用「无 FB 实体」判断,非 rush/威胁/timing 时
            # F2 整段让位,优先把 FB 拍出来,否则塔再多也没有舰队输出。
            # O176:再补「FB 已派工但买不起」闸,避免 truly_missing 偶尔未翻板时
            # 塔/追加星门继续抽干资金。
            # O221(o220-lane1 game_01 实证):无防基地豁免 —— 新二矿落成后
            # FB 等待闸把 F2 拦了 52s(385→442),敌 4 地面到脸时水晶/塔刚开工。
            # O255-①(o254 双 lane 0-10 尸检):Zerg Timing 直爬路线 SG 未就绪时
            # FB 资金窗根本不存在(FB 需就绪 SG),F2 给「还不存在的窗」让位 =
            # 200-350s 防御建设整段冻结(game_02:1 塔 0 电池接 300s 波,银行
            # 躺 1900;O216i 的 2 塔条件同步死锁,SG 被推到 305s)。SG 就绪前
            # 豁免,SG 就绪后(FB 窗真实存在)恢复原语义。
            and (
                (not _fb_truly_missing and not self._fb_waiting)
                or self._threat_active
                or self._rush_active
                or self._timing_sprint
                or _defenseless_base
                or fb_gate_f2_exempt_zt(
                    self._opp_race == "zerg" and self._ai_build == "timing",
                    any(
                        s.is_ready
                        for s in self.manager_mediator.get_own_structures_dict[
                            UnitID.STARGATE
                        ]
                    ),
                )
            )
            and not _sprint  # O129:冲刺期 F2 整块让位(手动链管 forge+首塔)
        ):
            ec = self._flow.expansion_cannons
            _rush_hold = (
                self._rush_hold_until is not None
                and self.ai.time < self._rush_hold_until
            )
            # O181:威胁分支与 else 分支都要用 _ec_min,提前计算避免重复。
            # O198:ec 为 None 时给 1 的兜底,供下方 FB 资金帽使用。
            _ec_min = expansion_cannon_min_dynamic(
                ec.min if ec is not None else 1, _fleet_total_now, fleet_min=3, early_cap=3
            )
            # O268-②(o267 尸检,司令观察):ZT 塔底线 2→3 —— 败局分矿 0-1 塔
            # 被 10+ 地面白拆(o267a-g03:分矿 541s 塔1 被抄、战损后 90s 裸奔
            # 再被抄、811s 丢矿);胜/败局塔量差仅 1 座/基地,就是这条命。
            if (
                self._opp_race == "zerg"
                and self._ai_build == "timing"
            ):
                _ec_min = max(_ec_min, 3)
            # O209:Zerg Timing 炮塔目标封顶 3/基地。O208 出现 20+ 炮塔局，
            # 把舰队成型资金吃光；3 基地 9 塔足够配合地面/舰队守家。
            # O231 曾降 3→2,但 O231b/O233 把追猎核后置到舰队≥3 后,中期
            # (500-700s)基地只剩 2 塔+零追猎,二矿连丢(o232 双 lane 0-8)——
            # 回滚到 3/基地,追猎核是增量不是替代。
            _ec_max = ec.max if ec is not None else 2
            if (
                self._opp_race == "zerg"
                and self._ai_build == "timing"
            ):
                _ec_max = min(_ec_max, 3)
            if ec is None:
                cannons = 2
            elif _rush_hold:
                # O73(n5b 两连崩实证):O71 情报确认的 rush 持有期塔目标拉满 ——
                # 敌 18 枪兵在对面家里(可见=0),按可见数目标停 min=4,摊到
                # 2-3 基地每处 2-3 塔接触即穿;兵力已被侦查证实,不需「看见」。
                cannons = _ec_max
            elif (
                self._threat_active and not self._rush_active
                and not _fleet_starved_capacity  # O87:见下行注释
                # O179(o178-vh-zerg-timing game_01-03 实证):0 舰队时拉满 max 会把
                # Nexus/首舰资金吃光,退回到动态式(min+敌兵//4),先保出一艘舰队。
                # O191(o190-vh-zerg-timing game_01 实证):1-2 艘舰队拉满 max 同样把
                # 矿吃光(23 炮 vs 7 艘 fleet),fleet 无法成型;改≥3 艘才拉满。
                and _fleet_total_now >= 3
                and (
                    not _expand_holding
                    or self._visible_enemy_army_supply() >= 25  # O49
                )
            ):
                # E9:敌压境 → 塔目标拉满 _ec.max(覆盖 cannon_target_capped 限流,
                # 修正限流在中局一波时防御变弱的副作用);rush 期按 rush 走不叠加
                # O46(Harder game_02 实证):开矿预留期威胁不拉满 —— Harder 的 E9
                # 高频触发(14-21 supply 挠痒波),每次威胁 ec.max=8 塔把 Nexus 基金
                # 吸干(6 塔+2 星门+FB,二矿 t>460 开不出)。预留期威胁走动态式
                # (min+敌//4),塔够用即可,Nexus 优先。
                # O49(Harder 三连败实证):O46 一刀切错了另一边 —— 真波(≥25 supply)
                # 来了还在省塔钱开矿 = 塔不够被一波穿。按威胁规模分流:
                # 挠痒(<25 supply)走动态式保 Nexus,真波(≥25)照旧拉满 ec.max。
                # O87(n5m-protoss-rush game_02 / n5m-zerg-timing game_02 实证):
                # 舰队饥饿期威胁不拉满 —— 慢性威胁下 12-13 座塔把 FB(300矿)的
                # 钱吃光,塔照样守不住(基地连丢),舰队才是翻盘点;饥饿期走动态式。
                cannons = _ec_max
                # O181:即使真波，Nexus 在途且舰队<3 时仍按动态式，避免 Nexus/首舰
                # 资金被大量塔吃光（game_02 二矿 361s 才落，威胁期 8+ 塔把 Nexus
                # 基金反复抽干，idle_builder 等钱造 Nexus 3 次）。
                # O191:前置条件已要求 fleet≥3,本特例基本不会触发,保留兜底。
                if _expand_holding and _fleet_total_now < 3:
                    cannons = expansion_cannon_count(
                        _ec_min, _ec_max, self._visible_enemy_army_count()
                    )
            elif _unknown_defense:
                # O133-③:unknown 判决保守防御 —— presumed 同级但 target 2 塔
                # (200s 的 unknown ≠ 65s 的 unknown,timing 波 273 必来)
                # O256-②(o255b game_02 实证):2 塔接不住 9 蟑螂+11 狗 ——
                # 塔3/塔4 在波到脸后(329-333s)才拍下,建造期被拆;ZT unknown
                # 窗目标 2→3,第三座塔在 ~280s 就绪,波到脸是 3 座成型塔。
                # O260-③:第三座塔同样让 SG 先派工(舰队科技优先,o259b-g01
                # 防御超支饿死 SG 实证);SG 在途/就绪后补。
                cannons = (
                    3
                    if (
                        self._opp_race == "zerg"
                        and self._ai_build == "timing"
                        and self._structure_present_or_pending(UnitID.STARGATE)
                    )
                    else 2
                )
            elif _presumed_rush:
                # O98-②:疑似 rush 节制版 —— forge+1 塔先立(PSD 自动补 forge),
                # 不多铺(贪心局只亏 1 塔钱);rush/threat 分支优先于本分支。
                cannons = 1
            else:
                # O161/O179: 舰队成型前压低 expansion_cannons baseline，避免二矿刚落
                # 就铺 6 塔把舰队科技/产能憋死。fleet=0 时进一步压到 1(见函数内 zero_fleet_cap)。
                cannons = cannon_target_capped(
                    # Macro 局塔重建限流(诊断 #2,o19b-macro 实证):憋舰队期
                    # (矿 < 舰队矿价 且非 rush)塔目标压回 min —— 16 座塔≈7 艘
                    # 航母的矿不该在气 2200 烂掉时继续出血;rush 期不限(保命)。
                    # O157: 气体富余但矿物紧缺、舰队未成规模时同样限流;
                    # O161: 基地被压缩且舰队未成规模时仍限流,优先让舰队成型。
                    expansion_cannon_count(
                        _ec_min, _ec_max, self._visible_enemy_army_count()
                    ),
                    _ec_min,
                    self.ai.minerals,
                    self.ai.calculate_cost(self._primary_unit_id()).minerals,
                    self._rush_active,
                    vespene=self.ai.vespene,
                    fleet_total=_fleet_total_now,
                    bases=self.ai.townhalls.amount,
                )
            # O198(o197-vh-zerg-rush game_01 实证):FB 已可建但买不起时,
            # rush/threat/timing 例外会把 300 矿 FB 资金窗抽干,舰队转型永远完不成。
            # 此处硬帽:FB 资金缺口期间塔目标最多 _ec_min,保命底线塔外全部让位给 FB。
            if self._fb_waiting:
                cannons = min(cannons, _ec_min)
            # O201(o200-vh-zerg-rush 3-7 实证):开矿持有期 Nexus 资金常被 F2 塔链
            # 持续抽干,二矿永远开不出;把塔目标压到 ec.min(1-2 座保命塔)。
            if self._expand_holding:
                cannons = min(cannons, _ec_min)
            # O290(B 案,司令 2026-08-16 拍板;o283dbg/o288 实证):口袋激活期
            # 非急性塔/电池/siege 全封顶 —— threat/rush 例外条款让塔链在
            # active=True 期间照长(塔 3→10、电池 1→6),银行振荡 25-315
            # 永远攒不到 400,Nexus 拖 375-614s。激活且非急性 → 塔/电池
            # 目标归 0(存量防御硬顶 20-40s 攒钱窗);急性(threat)不冻,
            # 保命塔照拍。Nexus 派出后 active 翻假(O54 条款接管),链恢复。
            # 与 o284 的 F2 整段冻结不同:不拦防御注册/电池奶/堵件,
            # 且激活只覆盖首扩(townhalls==1),窗短,无裸奔链式扩张问题。
            _pocket_saving = (
                self._zt_pocket_expand_active() and not self._threat_active
            )
            if _pocket_saving:
                # O293-②(o292a game_01 实证):0 封 → 3 座地板 —— 首波正落
                # 攒钱窗,threat 翻真再补塔来不及;胜局波前 3 塔是存活地板。
                cannons = pocket_saving_cannons(cannons)
            # O308-③(o307a game_03/o306c game_05 实证):ZT presumed/unknown 窗
            # 首塔未就绪时目标压 1 串行化 —— 3 塔同排(450 矿窗口)把资金摊薄,
            # 首塔拖到 200-225s 才就绪,波 ~240s 到脸;集中资金首塔 ~60s 提前。
            if (
                cannons > 1
                and self._opp_race == "zerg"
                and self._ai_build == "timing"
                and (_presumed_rush or _unknown_defense)
                and serialize_presumed_cannons(
                    sum(
                        1 for s in self.ai.structures.ready
                        if s.type_id == UnitID.PHOTONCANNON
                        and s.position.distance_to(self.ai.start_location) < 25
                    )
                )
            ):
                cannons = 1
            # O216d(O216c 败局):FB 实体落成前,动态塔目标扩到 3-4 座/基地会反复
            # 抽干 300 矿 FB 资金窗,舰队继续空转。压回 ec.min(1-2 座保命塔),
            # 让 FB 优先落地。过渡期地面防御不动。
            if (
                self._fb_entities_now == 0
                and _fleet_total_now < 3
                and not self._transition_active
            ):
                cannons = min(cannons, _ec_min)
            # E3d:rush 期电池让位(要 CYBERNETICSCORE,_tech_required 阻塞塔链,
            # game_01 零炮塔败北);E3f:max_on_route=2 允许 2 座同建(塔目标随敌兵
            # 爬升,单线 ~29s 追不上两段式 rush)。两实例共用。
            # O52(Harder 连败实证):电池 1→2 —— 波峰时塔被集火,双电池互充+奶塔
            # 显著延长塔存活,给舰队回援争取时间(新经济体养得起)。
            # O73(n5b-b 实证 0 电池):O71 持有期(t=330+,cyber 早成)恢复双电池 ——
            # 接触式 rush 的让位理由是「电池阻塞塔链」,持有期塔链早已建成,适用相反。
            # O98-②:presumed 节制版电池让位 —— 电池要 CYBERNETICSCORE,PSD 的
            # tech 链会为它先补 cyber(150 矿),阻塞 forge+首塔(E3d 同构教训)
            batt = 0 if _presumed_rush else rush_hold_batteries(self._rush_active, _rush_hold)
            # O120-③(o119 局2 实证):过渡期电池保底 2(cyber 在链上才抬,
            # 防 E3d 电池压塔链)—— 塔群无电池续航 = 一次性防御
            batt = transition_battery_floor(
                self._transition_active,
                self._structure_present_or_pending(UnitID.CYBERNETICSCORE),
                batt,
            )
            # O290(B 案):激活期电池同封顶(transition 流电池走手动派工,
            # batt=0 即不派,见下方 O140-②)。
            if _pocket_saving:
                batt = 0
            # O140-②(o139 terran-rush 局2 实证):transition 流的电池从 PSD
            # 剥离 —— PSD/BuildStructure 无 can_afford 守卫,穷局电池工
            # 「驻车↔O11撤回」死循环(局2:batt=2 自 258 注册,280s 零落地)。
            # 改 _dispatch_structure 手动派工(自带 dispatch_viable+撤回冷却,
            # 钱到位才派);PSD 侧电池数置 0 防双建。非 transition 流不变。
            _batt_psd = 0 if self._flow.transition is not None else batt
            # O172:o171/o172 game_01 实证,FB 工人被反复释放导致 pending 为真但
            # 实体不落,PSD 仍按 threat 分支铺出 7 电池/主基,把 FB 的 300 矿吸干。
            # 用 update 头部已计算的「无 FB 实体」判断,非 rush/timing 时电池目标压到 1/基地。
            if (
                _fb_truly_missing
                and not self._rush_active
                and not self._timing_sprint
            ):
                batt = min(batt, 1)
                _batt_psd = 0 if self._flow.transition is not None else batt
                # O175:FB 饥饿期电池帽临时诊断——只在状态变化时输出,
                # 避免每 10s 刷屏挤掉关键事件。
                _prev = getattr(self, "_fb_diag_prev", False)
                if _fb_truly_missing != _prev:
                    self._fb_diag_prev = _fb_truly_missing
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": (
                            f"FB_DIAG:truly_missing={_fb_truly_missing},"
                            f"entities_now={_fb_entities_now},"
                            f"structures_now={_fb_structures_now},"
                            f"missing_since={self._fb_missing_since:.1f},"
                            f"batt={batt},rush={self._rush_active},"
                            f"timing={self._timing_sprint},fb_in_core={_fb_in_core},"
                            f"fb_pending={_fb_pending}"
                        ),
                    })
            # O179(o178-vh-zerg-timing game_01-03 实证):FB 已就绪但一艘舰队都没下
            # 时,2 电池/基地仍把 Nexus/首舰资金抽干,压到 1。rush/timing 冲刺期保命
            # 优先,不受此帽限制。
            if (
                _fleet_total_now == 0
                and not self._rush_active
                and not self._timing_sprint
            ):
                batt = min(batt, 1)
                _batt_psd = 0 if self._flow.transition is not None else batt
            # O256-③(o255b game_02 实证):ZT unknown 防御窗电池 1→2 —— 9 蟑螂
            # 集火 6s 一座塔,单电池奶不住;双电池互充+奶塔把塔存活拉长 ~3 倍,
            # 给决死协防的农民/叉子换输出时间。100 矿出自死窗期 1300+ 银行。
            # O260-③:第二块电池同样让 SG 先派工(舰队科技优先)。
            if (
                _unknown_defense
                and self._opp_race == "zerg"
                and self._ai_build == "timing"
                and self._structure_present_or_pending(UnitID.STARGATE)
            ):
                batt = max(batt, 2)
            # O102-②/O132-②:过渡期塔封顶(cap=3)—— 第 4+ 座塔的钱
            # 换叉;cap=2 时 timing 波稳定穿防(o131 实证)
            cannons = transition_cannon_cap(cannons, self._transition_active)
            # O133-②:timing 冲刺期塔补到 3(不管清净/威胁 —— 波 273-289
            # 必到脸,守军从 6-8 叉+1-2 塔抬到 10-12 叉+3 塔)
            if self._timing_sprint:
                cannons = max(cannons, 3)
            # O105-③b(o104 局2/局5 实证):舰队重建窗放宽到 6 —— 首舰前必须
            # 顶住 1-2 波,局2 有 13叉4塔 仍被 723 波清零;窗关恢复原逻辑
            cannons = fleet_rebuild_cannon_cap(
                cannons,
                self._flow.transition is not None
                and fleet_rebuild_window(
                    self._fleet_transitioned, self._first_fleet_seen()
                ),
            )
            # O210:非紧急状态下钱不够光子炮就不请求新塔,杜绝 dispatch_viable
            # 预测可用、途中被兵/升级抽干导致的 idle_builder 驻点等钱。
            # rush/威胁/timing 冲刺/rush 持有期保命优先,保持原逻辑。
            _cannon_emergency = (
                self._rush_active
                or self._threat_active
                or self._timing_sprint
                or _rush_hold
                or _presumed_rush
            )
            if (
                not _cannon_emergency
                and cannons > 0
                and not self.ai.can_afford(UnitID.PHOTONCANNON)
            ):
                cannons = 0
            # O216j(o216h-lane2 game_04 实证):O210 的「买不起即归零」让新分矿
            # 落成后 88s 塔目标恒 0,敌 4 地面抄家时无塔丢矿(12 农民+基地)。
            # 分矿保底塔不走归零 —— 外层 dispatch_viable 守卫已管钉点,
            # 工人到位等几秒 > 分矿整段裸奔;主基 PSD 路径保持 O210 不变。
            _cannons_expansion = cannons if cannons > 0 else min(_ec_min, 2)
            # O274-②(司令观察):防御集中到分矿 —— 塔/电池分铺主分矿 =
            # 两处都薄(o267a-g03:主 1 塔/分 1 塔,波到分矿即穿)。ZT 且
            # 二矿已落成:分矿塔目标抬到 ≥3(+电池,迎敌侧锚点已有 O38),
            # 主基降到 1(坡口墙/叉子已在,塔是补漏);死窗期(单基地)
            # 主基目标不动。
            _zt_fortify_natural = (
                self._opp_race == "zerg"
                and self._ai_build == "timing"
                and self.ai.townhalls.ready.amount >= 2
            )
            if _zt_fortify_natural:
                # O277-①(司令观察):分矿口塔 3→4 —— 3 塔+电池仍被 10+ 蟑螂
                # 突进(o274 败局实证),分矿口是主防区,按主防区配塔。
                # O278(司令观察+36 局塔损顺序检索):分矿先拔 16/21(76%)
                # —— 分矿是事实主战场。落成后主基塔只留 1 座补漏(威胁/
                # rush 期不动),塔钱全给分矿:5 塔 + 2 电池 + 双兵营墙。
                _cannons_expansion = max(_cannons_expansion, 5)
                # O306-②(o256-③ 双电池奶塔存活×3 实证外推):中局 44-82
                # supply 波集火下双电池奶量见底(塔 8→0 序列),分矿电池
                # 2→3(塔存活≈波战损的直接杠杆;100 矿出自防御窗银行)。
                batt = max(batt, 3)
                # 主基降到 ≤1(坡口墙/叉子在,塔是补漏);威胁/rush 期不动
                # 主基目标(波打主基时塔照拉满)。
                if cannons > 0 and not self._threat_active and not self._rush_active:
                    cannons = min(cannons, 1)
            # O79b:持有期建造槽翻倍 —— max_on_route 是全图共享计数,主分矿
            # 并发抢 2 槽时主基(先注册/离工人近)恒赢;4 槽让分矿也起得了塔。
            # O207:非紧急状态下把 mor 压到 1，避免 PSD 一次派多个工人等钱
            # (dispatch_viable 只按单塔估算，多工人同时派 = idle_builder)。
            # rush/威胁/timing 冲刺期才允许多槽并行。
            if _rush_hold:
                mor = 4
            elif self._rush_active or self._threat_active or self._timing_sprint:
                mor = 2
            else:
                mor = 1
            # O268-③(o267a-g03 实证):裸矿(有基地 0 就绪塔)战损补塔串行
            # 太慢 —— 分矿 2 塔被拆后 ~90s 才补回 1 座,次波到脸仍裸奔丢矿。
            # 裸矿时建造槽保底 2(双塔并行,补防速度翻倍;急性期本来就 ≥2)。
            # O277-③:裸矿槽 2→3 —— o274 局补回 3 塔仍要 ~90s(600→694s),
            # 三槽并行把「补满前线塔阵」压进波间隙(~60s)。
            if _defenseless_base:
                mor = max(mor, 3)
            # O207:Nexus/FB 资金窗期间，塔串行建造，避免多工人同时抽干
            # 让位资金。rush/威胁/timing 冲刺期已走多槽，不覆盖。
            # O268-③:裸矿补塔豁免串行(补防速度优先于资金窗整洁)。
            if (_expand_holding or self._fb_waiting) and mor <= 2 and not _defenseless_base:
                mor = 1
            # O31:主基堵口塔跟 ramp 口(集中火力,不散基地周边)。ramp.top 朝基地 -4 格
            # (= defensive_rally_point 同款 sharpy PlanHeatDefender)。没 ramp → None 不 override。
            rally = None
            _ramp = getattr(self.ai, "main_base_ramp", None)
            if _ramp is not None and getattr(_ramp, "top_center", None) and getattr(_ramp, "bottom_center", None):
                try:
                    rally = _ramp.top_center.towards(_ramp.bottom_center, -4)
                except Exception:
                    rally = None
            ms = self._flow.main_siege
            siege = self._main_under_siege() if ms else False
            # O223(o220-lane1 game_03 实证):FB 未落成且舰队未成规模时,主基 siege
            # 6 塔(900 矿)把 FB/首舰资金吃光 —— 塔 9 座、舰队 0 败亡。siege 加强
            # 只在「FB 已出 或 舰队 ≥3 或 rush 保命」时开火;其余走原 cannons 目标。
            if (
                siege
                and self._fb_entities_now == 0
                and _fleet_total_now < 3
                and not self._rush_active
            ):
                siege = False
            # O290(B 案):激活期 siege 12 塔链同封顶(o283dbg 塔 6→10 主嫌)。
            if _pocket_saving:
                siege = False
            if siege and ms is not None:
                # 需求3:敌大军压上分矿(前线)→ 双实例(exclude 互补:只前线加强,
                # 不叠加超造 —— to_count_per_base 是 per-base_loc)。造塔~29s,radius
                # 放大(默认 25)给塔成型留提前量(敌压脸上再建来不及)。
                base_locs = list(self.manager_mediator.get_placements_dict.keys())
                if base_locs:
                    main_loc = min(
                        base_locs,
                        key=lambda bl: bl.distance_to(self.ai.focused_enemy_start()),
                    )
                    others = set(base_locs) - {main_loc}
                    self.ai.register_behavior(   # A:只前线分矿,高 cannons
                        ProtossStaticDefence(
                            photon_cannons_per_base=ms.cannons,
                            shield_batteries_per_base=_batt_psd,
                            max_on_route=mor,
                            exclude_base_locations=others,
                        )
                    )
                    self.ai.register_behavior(   # B:其余基地,原 cannons(排除主基)
                        ProtossStaticDefence(
                            photon_cannons_per_base=cannons,
                            shield_batteries_per_base=_batt_psd,
                            max_on_route=mor,
                            exclude_base_locations={main_loc},
                        )
                    )
                else:
                    self.ai.register_behavior(   # 兜底:拿不到 placements → 全局
                        ProtossStaticDefence(
                            photon_cannons_per_base=ms.cannons,
                            shield_batteries_per_base=_batt_psd, max_on_route=mor,
                        )
                    )
            else:
                # O38(司令观察·建筑学):每基地独立锚点 —— 塔/电池落在「基地朝敌
                # 一侧」(敌来犯路径与矿区之间),不再矿区背后扎堆;电池同锚点 →
                # 自然贴着塔(电池射程 6,离塔远了就是废铁)。锚点纯函数
                # production_plans.base_defense_anchor:主基沿用 O31 ramp 口,
                # 分矿 = 朝焦点敌方向 6 格(敌未定位时=最近候选出生点)。
                base_locs = list(self.manager_mediator.get_placements_dict.keys())
                focus = self.ai.focused_enemy_start()
                registered = False
                # O76b 诊断(n5/o76 分矿恒 1 塔悬案):每基地首次注册 + 每 30s 每基地
                # 塔数上报事件,定位「没注册 / 注册不建 / 建了被拆」哪一环。
                # O77(诊断一层):按离敌距离升序注册 —— 最暴露的基地(分矿)先抢
                # 建造槽。BuildStructure 的 max_on_route 是**全图共享**计数,
                # 主基实例每帧先执行先占满 2 槽,分矿实例恒抢不到槽(o76b 实证:
                # 分矿 t=267 已注册 target=4,70s 后仍 0 塔,主基同窗 4 塔)。
                # O78(o77 实证):排序键改「塔数升序,再按离敌」—— 敌打的是
                # **最弱**的基地不是最近的(o77 局:6 塔分矿闲置,1 塔主基被绕开
                # 打穿)。先补最少的,自然均衡,新落成的矿自动排最前(O37 同源)。
                _cannons_near = {
                    th.tag: sum(
                        1 for s in self.ai.structures.ready
                        if s.type_id == UnitID.PHOTONCANNON
                        and s.position.distance_to(th.position) < 12
                    )
                    for th in self.ai.townhalls
                }
                for th in sorted(
                    self.ai.townhalls,
                    # O81(n5h 实证):主基永远先抢建造槽 —— O78 的「塔数最少
                    # 优先」把 t=213-371 的槽全喂给注定弃守的分矿,主基坡口
                    # 到接触只有 2-3 塔(o67 胜局同期 5-8 塔)。rush 教义的
                    # 正确读法:主基是先保的那个,槽就该先给主基。
                    key=lambda t: (
                        t.position.distance_to(self.ai.start_location) > 5.0,
                        _cannons_near.get(t.tag, 0),
                        t.position.distance_to(focus),
                    ),
                ):
                    if not base_locs:
                        break
                    bloc = min(base_locs, key=lambda bl: bl.distance_to(th.position))
                    if bloc.distance_to(th.position) > 5.5:  # NEXUS_BASE_DISTANCE 同款口径
                        continue
                    is_main = th.position.distance_to(self.ai.start_location) < 5.0
                    # O80b(n5 系实证):rush/持有期防御只堆主基坡口 —— 分矿在
                    # ~160s 预警窗内建不起 4-6 塔(实测恒 1-2 塔被穿),
                    # 建造槽全给主基(坡口塔阵 = 六局实跑唯一稳定守住的点),
                    # 分矿放弃,农民已由 O80 提前撤回主矿。
                    if not is_main and (self._rush_active or _rush_hold):
                        continue
                    _reg_key = (round(th.position.x), round(th.position.y))
                    if _reg_key not in getattr(self, "_f2_reg_logged", set()):
                        if not hasattr(self, "_f2_reg_logged"):
                            self._f2_reg_logged = set()
                        self._f2_reg_logged.add(_reg_key)
                        self.ai._events.append({
                            "t": round(self.ai.time, 1),
                            "msg": (
                                f"F2:注册防御 base={_reg_key},target={cannons},"
                                f"batt={batt},fb_missing={_fb_truly_missing},"
                                f"fb_pending={_fb_pending}"
                            ),
                        })
                    if not is_main:
                        # O78c(o78b 实证):分矿防御绕过 ProtossStaticDefence —— 其
                        # static_defence=True 的槽位检索在分矿静默返回 None
                        # (分矿恒 0 塔:注册在、优先级在、就是不放塔)。
                        # 直接 BuildStructure 普通落位(找任意有电可建点,电池同)。
                        # O78d:先补分矿 pylon —— 分矿无电时 within_psionic_matrix
                        # 让所有塔/电池落位返回 None(悬案的最后一层)。
                        self.ai.register_behavior(
                            BuildStructure(
                                bloc, UnitID.PYLON,
                                max_on_route=1,
                                to_count_per_base=2,
                                find_alternative=True,
                                production=False,
                            )
                        )
                        self.ai.register_behavior(
                            BuildStructure(
                                bloc, UnitID.PHOTONCANNON,
                                max_on_route=mor,
                                static_defence=False,
                                to_count_per_base=_cannons_expansion,  # O216j:分矿保底塔不走 O210 归零
                                # O79c:塔贴着分矿 pylon 建(必有电) ——
                                # 裸 base_loc 落位会落到无电/矿区死角(o78 系实证)。
                                closest_to=(
                                    _pyl.position if (_pyl := next(
                                        (s for s in self.ai.structures.ready
                                         if s.type_id == UnitID.PYLON
                                         and s.position.distance_to(th.position) < 12),
                                        None,
                                    )) else None
                                ),
                                find_alternative=True,
                            )
                        )
                        if _batt_psd:
                            self.ai.register_behavior(
                                BuildStructure(
                                    bloc, UnitID.SHIELDBATTERY,
                                    max_on_route=1,
                                    static_defence=False,
                                    to_count_per_base=batt,
                                    closest_to=(
                                        _pyl2.position if (_pyl2 := next(
                                            (s for s in self.ai.structures.ready
                                             if s.type_id == UnitID.PYLON
                                             and s.position.distance_to(th.position) < 12),
                                            None,
                                        )) else None
                                    ),  # O79c:电池同塔,贴 pylon 必有电
                                    find_alternative=True,
                                )
                            )
                        registered = True
                        continue
                    # O78b(o78 实证):分矿放弃 O38 朝敌锚点,回落 ares 默认落位
                    # (基地附近**有电**的位置)。锚点概念(塔朝敌 6 格)对分矿是
                    # 连环失败源:锚点无电/不可建 → 塔单静默失败(分矿恒 0-1 塔,
                    # 主基坡口锚点无恙故主基保留)—— 矿线侧的塔 > 锚点空气。
                    anchor_xy = base_defense_anchor(
                        is_main,
                        (th.position.x, th.position.y),
                        (focus.x, focus.y),
                        main_rally_xy=(rally.x, rally.y) if rally is not None else None,
                    ) if is_main else None
                    self.ai.register_behavior(
                        ProtossStaticDefence(
                            photon_cannons_per_base=cannons,
                            shield_batteries_per_base=_batt_psd,
                            max_on_route=mor,
                            exclude_base_locations=set(base_locs) - {bloc},
                            closest_to_override=(
                                Point2(anchor_xy) if anchor_xy is not None else None
                            ),
                        )
                    )
                    registered = True
                if not registered:
                    self.ai.register_behavior(  # 兜底:拿不到 placements → 原全局单实例
                        ProtossStaticDefence(
                            photon_cannons_per_base=cannons,
                            shield_batteries_per_base=_batt_psd, max_on_route=mor,
                            closest_to_override=rally,  # O31:塔跟主基 ramp 堵口
                        )
                    )
                # O140-②:transition 流电池手动派工(从 PSD 剥离,见上)——
                # 锚点 = 最近就绪塔(电池贴塔奶);钱到位才派(不驻车)
                # O277-②(司令观察):锚点从「任意最近塔」(恒落主基)改
                # 「最暴露基地(离敌焦点最近)附近的塔」—— 电池跟着前线
                # 塔阵走,分矿堵口阵才有奶;无塔可贴时落最暴露基地锚点。
                if self._flow.transition is not None and batt > 0:
                    _batt_have = (
                        len(
                            self.manager_mediator.get_own_structures_dict[
                                UnitID.SHIELDBATTERY
                            ]
                        )
                        + self.manager_mediator.get_building_counter[
                            UnitID.SHIELDBATTERY
                        ]
                    )
                    if _batt_have < batt:
                        _focus = self.ai.focused_enemy_start()
                        _front_th = min(
                            self.ai.townhalls.ready,
                            key=lambda t: t.position.distance_to(_focus),
                            default=None,
                        )
                        _batt_anchor = next(
                            (
                                s.position
                                for s in self.ai.structures.ready
                                if s.type_id == UnitID.PHOTONCANNON
                                and (
                                    _front_th is None
                                    or s.position.distance_to(_front_th.position)
                                    < 15
                                )
                            ),
                            _front_th.position if _front_th is not None else rally,
                        )
                        self._dispatch_structure(
                            UnitID.SHIELDBATTERY,
                            self.ai.start_location,
                            closest_to=_batt_anchor,
                        )
                # O76b 诊断:每 30s 上报每基地塔数(与 E6 同 12 格口径)
                # O78c 追加每基地 pylon 数 —— 排查「分矿无电 → within_psionic_matrix
                # 下所有塔落位返回 None」这一层(o78b/o78c 分矿恒 0 塔)。
                if self.ai.time - getattr(self, "_f2_count_ts", 0.0) > 30.0:
                    self._f2_count_ts = self.ai.time
                    _per_base = [
                        (
                            round(th.position.x), round(th.position.y),
                            sum(
                                1 for s in self.ai.structures.ready
                                if s.type_id == UnitID.PHOTONCANNON
                                and s.position.distance_to(th.position) < 12
                            ),
                            sum(
                                1 for s in self.ai.structures.ready
                                if s.type_id == UnitID.PYLON
                                and s.position.distance_to(th.position) < 12
                            ),
                        )
                        for th in self.ai.townhalls
                    ]
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": f"F2:每基地(塔,晶)={_per_base}",
                    })

        # O149-②/O151-②:Nexus 在途 → 分矿 2 塔+1 电池预派 —— 移出 F2 闸:
        # F2 整体被 _expand_holding 按住(Nexus 在途即 holding,E3l 的注册
        # 也被同一闸否决),挂在 F2 里 = 在唯一需要它的窗口里是死代码
        # (o150 局2:546 裸开,16s 被 37-supply 波秒)。挂 carrier 门
        # (transition 配置),tempest/stalker 基线不变
        if (
            self._flow.transition is not None
            and self.manager_mediator.get_building_counter[UnitID.NEXUS] > 0
        ):
            self._expansion_predefense()
        # O278:分矿口防御先于 Nexus(塔 250s 起铺,二矿窗 280s 跟进)——
        # 波路径穿分矿,后建塔永远晚于波;与 Nexus 在途预派互补。
        if self._flow.transition is not None:
            self._natural_forward_defense()

        # O94-D(o93 局1 实证):rush 确认且主基无就绪炮塔 → 通用 2x2 槽的炮塔
        # 绕过实例。PSD 的 static_defence 槽(坡口锚点+要电)会静默返回 None
        # (局1:forge t≈185 就绪、矿 435、F2 注册正常,炮塔零派出败亡)——
        # O78c 在分矿绕过同类失败的同思路:槽池大、有电即可,锚点优先。
        # BuildStructure 自带 tech 闸(forge 未就绪不派工),首座就绪后退出。
        # O286:在途驻点条目计入去重(与 presumed 链同口径),
        # 防「派→等→撤→再派」多工人钉点。
        if (
            rush_cannon_bypass(
                self._rush_confirmed,
                self._flow.transition is not None,
                sum(
                    1 for s in self.ai.structures.ready
                    if s.type_id == UnitID.PHOTONCANNON
                    and s.position.distance_to(self.ai.start_location) < 25
                ),
            )
            and self.ai.not_started_but_in_building_tracker(UnitID.PHOTONCANNON) == 0
        ):
            _ramp = getattr(self.ai, "main_base_ramp", None)
            _anchor = None
            # O101-X:协防塔锚点 = 矿线质心(狗绕坡口直进矿线,塔要在矿线);
            # O118-③(o117 局1/2/4 实证):再朝远离坡口退 2.5 格 —— 首塔
            # 建造期 25-29s 被狗两口咬掉三局实证;矿线深处建造期不吃狗,
            # 成型后射程 7 照样覆盖矿线。坡口迎敌位留给 F2 主链的后续塔
            _mh = self.ai.mineral_field.closer_than(10, self.ai.start_location)
            if _mh and _ramp is not None and getattr(_ramp, "top_center", None):
                _cx = sum(m.position.x for m in _mh) / len(_mh)
                _cy = sum(m.position.y for m in _mh) / len(_mh)
                _anchor = Point2(cannon_safe_anchor(
                    (_cx, _cy), (_ramp.top_center.x, _ramp.top_center.y)
                ))
            elif _mh:
                _anchor = Point2((
                    sum(m.position.x for m in _mh) / len(_mh),
                    sum(m.position.y for m in _mh) / len(_mh),
                ))
            elif _ramp is not None and getattr(_ramp, "top_center", None) and getattr(_ramp, "bottom_center", None):
                _anchor = Point2(defensive_rally_point(
                    (_ramp.top_center.x, _ramp.top_center.y),
                    (_ramp.bottom_center.x, _ramp.bottom_center.y),
                ))
            # O116-①:首塔走手动取证派工 —— 失败环节写进事件
            # (no_placement/no_worker/tech_not_ready/taken 四分类);
            # O119-②a:入侵期选工锚点=基地中心(家里方向挑人,
            # 不走坡口入侵路径)
            _dispatch = self._dispatch_structure(
                UnitID.PHOTONCANNON, self.ai.start_location, closest_to=_anchor,
                worker_origin=(
                    self.ai.start_location if self._defense_urgent else None
                ),
            )
            # O296-③(o295a game_02/o292b 多局实证):首塔 no_placement 多为
            # 主基带电 2x2 槽归零(带电余=0 反复出现)——塔链无电自救,
            # 防御窗干等死。no_placement 且带电槽 0 → 钉点补电(O55/O295-①
            # 同构;critical 钉点等钱=钱到即开工,can_afford 守卫防穷局钉死)。
            if (
                _dispatch == "no_placement"
                and self._slot_counts_at(
                    self.ai.start_location, BuildingSize.TWO_BY_TWO
                )[0] == 0
                and self.ai.can_afford(UnitID.PYLON)
            ):
                self._dispatch_structure(
                    UnitID.PYLON, self.ai.start_location, critical=True
                )
            # O118-①:防御紧急窗内派工即时簿记(结果变化或 5s 节流)——
            # forge 就绪 → 首塔落地的静默段逐帧可见,不等 15s 停滞
            if self._defense_urgent and (
                _dispatch != getattr(self, "_last_cannon_dispatch", None)
                or self.ai.time - getattr(self, "_last_cannon_dispatch_ts", 0.0) > 5.0
            ):
                self._last_cannon_dispatch = _dispatch
                self._last_cannon_dispatch_ts = self.ai.time
                self.ai._events.append({
                    "t": round(self.ai.time, 1),
                    "msg": f"O118:首塔派工={_dispatch}",
                })
            # O114-③b/O116-①:首塔停滞簿记 —— forge 就绪 >15s 仍 0 塔,
            # 报失败环节 + 主基 2x2 槽带电三值 + GATHERING 池余量
            _forge_ready = any(
                s.is_ready
                for s in self.manager_mediator.get_own_structures_dict[UnitID.FORGE]
            )
            if _forge_ready:
                if self._cannon_stall_since is None:
                    self._cannon_stall_since = self.ai.time
                elif self.ai.time - self._cannon_stall_since > 15.0:
                    self._cannon_stall_since = self.ai.time
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": (
                            f"O116:首塔派工={ _dispatch },"
                            f"主基2x2槽(带电余,空闲余,总)="
                            f"{self._slot_counts_at(self.ai.start_location, BuildingSize.TWO_BY_TWO)},"
                            f"采集池={len(self.manager_mediator.get_unit_role_dict.get(UnitRole.GATHERING, set()))},"
                            f"停气池={len(self._gas_stopped_tags)},协防={len(self._escort_tags)}"
                        ),
                    })
            else:
                self._cannon_stall_since = None

        # custom behavior for all other production, using ares-sc2 to help
        building_counter: dict[UnitID, int] = self.manager_mediator.get_building_counter
        structures_dict: dict[
            UnitID, list[Unit]
        ] = self.manager_mediator.get_own_structures_dict

        # E3d: rush 期间连造农民也让位(50 矿/个是防御链的最大竞争项)
        # O42(o39-carrier-hard-zerg-macro 0-3 实证):开矿攒钱预留**不再掐农民** ——
        # first_expand_at:150 让预留从 t=150 起常驻 ~400s,期间农民从 14 爬到 20,
        # 收入锁死单矿 700/min,Nexus 基金反而攒更慢(恶性循环,retro one_base×3)。
        # E3k 短预留(rush 收尾矿紧)的让位语义已由 rush 门覆盖;预留期让位的仍是
        # 出兵/研究/塔(O41),农民 = 攒 Nexus 的收入来源,掐农民 = 掐开矿本身。
        # O75(n5d 四连败实证):O71 预警持有期不掐农民 —— E3d 的掐农民是给
        # 「接触式 rush 急性防御窗」(几十秒)设计的;O72 把 rush_active 拉长到
        # t=330-600,农民冻 270s → 接触时只有 23-34 农民、银行烂 3000-5900,
        # 塔再满也付不起恢复战。持有期农民 = 防御链的收入来源,照造不误。
        _rush_hold = (
            self._rush_hold_until is not None
            and self.ai.time < self._rush_hold_until
        )
        # O97-C(o96 局1/局3 实证):过渡期农民够保底且地面未到目标 → 农民让位
        # 地面产能(局1:农民 17→29 吃 600 矿,叉子 7 个迎 30-supply 波;
        # 局3:农民每次吃掉 50,叉子 100 永远攒不出,116s 零叉)。自校正无 latch。
        _probe_yield = transition_probe_yield(
            self._transition_active,
            self.ai.supply_workers,
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.ZEALOT)
            + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.STALKER),
            acute=_acute,  # O146-②:非急性窗(慢性过渡)不让位
        ) or (
            # O101-Y(o100 局4 实证):舰队重建窗内农民 ≥14 也停训 —— 局4 转舰队
            # 后农民 13→20(350 矿)+电池(100)把 SG 挤到 t=605 才落地;
            # 重建窗内一切非舰队开销都是凶手,首舰出场即解除
            # O194-②(o193-vh-zerg-rush game_01 实证):阈值 14 过低,2 基地局 27 农仍被掐,
            # 108s 重建窗内零农民增长→经济断气。改为按当前基地饱和数:1 基地 22 农,
            # 2 基地 44 农,未饱和时继续造农民回血。
            fleet_rebuild_window(
                self._fleet_transitioned, self._first_fleet_seen()
            )
            and self.ai.supply_workers >= 22 * max(1, self.ai.townhalls.amount)
        ) or forge_first_probe_yield(
            # O111-③(o110 局1/局2 实证):forge 未落地前 2-3 个农民(各 50)
            # 排在 forge(150)前面 —— 防御紧急时农民 ≥12 即让位,首塔目标 ≤150
            defense_urgent=(
                self._rush_confirmed or self._transition_active or _presumed_rush
            ),
            forge_present=bool(
                self.manager_mediator.get_own_structures_dict[UnitID.FORGE]
            ),
            workers=self.ai.supply_workers,
            now=self.ai.time,  # O146-②:竞速窗截止 200s(防 latch 压农民到终局)
        ) or _zealot_sprint  # O124-③:首叉冲刺期农民也停(矿全留给首叉)
        # O146-①(元诊断:赢局退出时 15-20 农,现局被刹车家族压在 12):
        # t≤350 且非急性窗且农民 <16 → 必产,一切 yield/brake 不得压
        _probe_floor = probe_floor_needed(
            self.ai.time, self.ai.supply_workers, _acute
        )
        # O203:经济崩溃底线——农民掉到临界值以下时,无论 rush/transition/
        # 重建窗,优先补农民。没有农民就没有矿物,没有矿物舰队/塔都造不出。
        _econ_floor = self.ai.supply_workers < min(
            16, 22 * max(1, self.ai.townhalls.amount)
        )
        if _probe_floor or _econ_floor or (
            (not self._rush_active or _rush_hold)
            and not _probe_yield
            # O130-①:农民 <8 豁免冲刺闸(经济活命优先于链纯洁)
            and not (_sprint and sprint_blocks_probes(self.ai.supply_workers))
        ):
            self._build_probes(self.ai.ready_townhalls)
        # O145-①(o144 局3 实证):农民 402-643 恒 12-13(240s 零增长,矿 280
        # 躺着)—— 各闸静态读都假,取证事件直接读(30s 节流,有农民在产/
        # 无基地/开局序列期不报)
        if (
            self.ai.time > 200
            and self.ai.supply_workers
            < min(70, 22 * max(1, self.ai.townhalls.amount))
            and self.ai.ready_townhalls
            and not cy_unit_pending(self.ai, UnitID.PROBE)
            and self.ai.time - getattr(self, "_probe_block_logged_at", 0.0) > 30.0
        ):
            self._probe_block_logged_at = self.ai.time
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": (
                    f"O145:农民停滞 wrk={self.ai.supply_workers}"
                    f"(rush={self._rush_active},hold={_rush_hold},"
                    f"yield={_probe_yield},sprint={_sprint},急性={_acute},"
                    f"矿{self.ai.minerals:.0f},左{self.ai.supply_left:.0f},"
                    f"闲置基地{len(self.ai.ready_townhalls.idle)},"
                    f"过渡={self._transition_active},转舰队={self._fleet_transitioned})"
                ),
            })
        self._ensure_townhall()  # Q4:保底主基地(被打爆到 0 且有矿区价值时重建)
        self._early_scout()      # pivot:2分钟自动派一个探机看对面开局
        self._update_early_scout_route()  # O36:多出生点逐点推进(4人图不赌单点)
        self._evaluate_scout_intel()  # O9:侦查情报→开局决策(t≈170s,一局一次)
        self._rescout()  # O71:二次侦查(t=250 派出,敌兵出门前复核开局)
        self._update_rush_state()  # pivot:rush 检测/解除(响应包=叉子+塔+守家)
        self._update_threat_state()  # E9:中局威胁检测/解除(carrier,塔满+地面豁免+停开矿)
        self._update_transition_state()  # O92:过渡形态状态机(carrier,rush确认→地面过渡→转舰队)
        # B4③(QueenBot rush 应激清单)经济侧联动:停气+取消在建非关键科技。
        # 放 rush 检测之后:本帧最新状态;role 改动先于 _after_step 的 Mining 执行生效。
        self._rush_economy_response()
        # O94-C:首波农民协防(炮塔/叉子就绪前的物理空窗,农民坡口顶 10-20s)
        self._rush_worker_escort()
        # E3d: rush 期间资源全部让位防御链(叉子/塔) —— 暂停科技链(cybercore/星门/
        # 第二气)、造农民、追加产能、滚雪球、前线塔;rush 解除后各自恢复。
        # 保底:_rush_gateway_boost 保证兵营产能,升级循环保留 FORGE(炮塔前置,见下)。
        # O80c(n5 系实证):O71 持有期**不停科技链** —— 持有窗 t=330-600 全停 =
        # 舰队晚 ~4 分钟,恢复战(t=750+ 二波)撞上零舰队;E3d 的暂停是给
        # 「接触式 rush 急性窗」设计的,持有期农民(O75)+塔+科技并行养得起。
        _rush_hold_tech = (
            self._rush_hold_until is not None
            and self.ai.time < self._rush_hold_until
        )
        # O83/O85/O86/O87 舰队饥饿信号已在上方(macro_plan 注册后)算好:
        # _fleet_starved(就绪口径,救 FB)/ _fleet_starved_capacity(容量口径,
        # 拦塔/拦追加产能)。
        # O216f(o216e-vh-zerg-timing game_01 双车道实证):Zerg Timing 的 sprint
        # 把科技链(CYBERNETICCORE→STARGATE→FLEETBEACON)冻结 200s+,星门 450s
        # 才出现、首舰 731s 才出,transition 退出后无舰队可转。Timing 不是 Rush,
        # 波次晚,允许 sprint 期间并行建核心科技,把舰队科技窗口提前。
        _sprint_freeze_tech = _sprint and not (
            self._opp_race == "zerg" and self._ai_build == "timing"
        )
        if (
            (not self._rush_active or _rush_hold_tech)
            and not _rebuild_nexus
            and not _sprint_freeze_tech
        ):
            # O43(o42 bench 实证):开矿攒钱预留期间科技链(星门/舰队航标 ~450 矿)
            # 也让位 Nexus —— 预留只剩农民/气矿/pylon 花费,Nexus 从 t=490 提前到
            # ~430,分矿塔链才能在 10 分钟波(t≈560)前落地(塔链=水晶25s+塔29s,
            # 晚一秒都是"无塔"丢矿)。气矿照采(航母的气不能断)。
            # O216f:Zerg Timing sprint 期间强开 core_allowed,确保 cybercore/stargate/FB
            # 都能排队,不被持有期/预留卡住。
            _zerg_timing_sprint_core = (
                _sprint
                and self._opp_race == "zerg"
                and self._ai_build == "timing"
            )
            await self._build_flow_structures(
                building_counter, structures_dict,
                # O51:含 pending 等待期;O93-B1:转舰队后科技链不再让位持有期
                # (o92 局3:持有期恒 True → 解冻后星门/FB 仍零建,死锁)
                # O145-②:但扩张攒钱预留(_fleet_reserve,评分≥25 豁免首舰
                # 前提后)期间让位 —— 否则 SG/FB 把 Nexus 的 400 吃光,
                # bases=1 到死(o144 局3 实证:SG 570/FB 616,二矿从未开)
                # O166: 单矿早期核心科技(CYBERNETICCORE/STARGATE)缺失时，即便想开二矿
                # 也不冻结科技链 —— 否则 Nexus 工人在目标点干等钱、科技又建不了，两头空。
                core_allowed=(
                    core_tech_allowed(_expand_holding, self._fleet_transitioned)
                    or _early_core_missing
                    or _zerg_timing_sprint_core
                ) and not _fleet_reserve,
            )
            # O13:每个就绪基地双气满采,优先级高于一切矿物开销(气矿买上再谈产能/滚雪球)
            # O124-②:过渡期缓气(叉海不吃气),退出后恢复满采
            if not transition_pauses_gas(self._transition_active):
                self._ensure_expansion_gas()
            # O79:每个就绪基地保底 2 pylon(电力跟 Nexus 走,不等防御激活)
            # O127-①:防御紧急且 forge 未拍 → 保底水晶让位(o126b 局1:O79
            # 路径 90/110 各 100 矿偷 forge 资金窗,上轮漏网)
            if not forge_first_pylon_yield(
                self._defense_urgent,
                bool(self.manager_mediator.get_own_structures_dict[UnitID.FORGE]),
                self.ai.supply_left,
            ):
                self._ensure_expansion_pylon()
                self._ensure_expansion_wall_gateway()
            # 按流派配置扩产能(矿富余追加产兵建筑,治"矿堆花不出去")
            # O43:预留期间不追加(第二星门 150 矿同样抢 Nexus 基金)
            # O67(Terran Rush game_01 实证):E9 威胁期也不追加 —— 敌压境时
            # 追加星门抢光塔钱(「等钱造PHOTONCANNON」干等,0 塔基地被推平)。
            # O86(n5m-terran-power game_02 / terran-timing game_03 实证):舰队饥饿
            # 期更不追加 —— 3-4 座星门(450-600 矿气)先于 FB 落地 = 无科技可用的
            # 死钱,FB(300矿)被挤得 200s 落不了地,中局波(t≈500-540)到脸时
            # 舰队零产出。产能 > 科技是本末倒置,先 FB 后星门。
            # O182:星门被拆光且有余钱时紧急重建产能，避免 late-game 气体烂银行
            # 却造不出舰队。前置：FB 还在科技链上、非 rush/timing 冲刺保命期、
            # 至少还有一个基地能落建筑。
            _sg_ready_and_pending = (
                len(self.manager_mediator.get_own_structures_dict[UnitID.STARGATE])
                + self.manager_mediator.get_building_counter[UnitID.STARGATE]
            )
            if (
                _sg_ready_and_pending == 0
                and self.ai.townhalls.amount >= 1
                and self._structure_present_or_pending(UnitID.FLEETBEACON)
                and not self._rush_active
                and not self._timing_sprint
                and self.ai.can_afford(UnitID.STARGATE)
            ):
                self.ai.register_behavior(
                    BuildStructure(self.ai.start_location, UnitID.STARGATE)
                )
                self.ai._events.append({
                    "t": round(self.ai.time, 1),
                    "msg": "O182:紧急重建星门(0 SG,有余钱)",
                })
            if (
                not _expand_holding
                and not _fleet_starved_capacity
                and not tech_yields_to_threat(
                    self._threat_active, self._rush_active
                )
            ):
                self._build_extra_production(structures_dict)
            self._spend_bank()  # Q3:存款淤积时换成开矿/追加产能,经济优势→战场优势
            self._build_forward_pylon()  # F1: 前线水晶塔(投送),各流派共用
        # O98-③c(o97 局2 实证):过渡期 CYBERNETICSCORE 豁免 E3d rush 全停 ——
        # 追猎是气出口 + 对蟑螂/刺蛇波的关键 DPS(局2:气烂 2000,二波
        # 30 supply 穿 8 叉)。星门/FB 仍冻结;can_afford 守卫让急性窗
        # 自然让位塔/叉(矿 <150 时本就不建)。
        if transition_needs_cybercore(
            self._transition_active,
            self._structure_present_or_pending(UnitID.CYBERNETICSCORE),
            # O103-①:先有两个叉站岗再谈追猎科技(局3/5:cyber 抢 150 矿,
            # 首叉 156→183)
            ground_army=(
                self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.ZEALOT)
                + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.STALKER)
            ),
        ) and not _rebuild_nexus:
            await self._build_core_structure(UnitID.CYBERNETICSCORE)
        # O108-②(o107 局4 实证):重建窗内 SG/FB 同样豁免 E3d rush 全停 ——
        # 局4:420 转舰队(评分36),425 波次接触 → rush_active 恒真 → 刚解冻
        # 的科技链被 E3d 重新冻结,SG 到死(t=476)没拍。豁免只挂重建窗
        # (首舰出场即恢复 rush 停产语义);can_afford 守卫让急性窗资金仍
        # 优先塔/叉。FB 沿用「需就绪星门」特判。
        if (
            self._flow.transition is not None
            and fleet_rebuild_window(
                self._fleet_transitioned, self._first_fleet_seen()
            )
            and not _rebuild_nexus
        ):
            # O112-②(o110 局1/3/4 实证):有二矿 → SG/FB 优先落分矿
            # (主基 3x3 槽被塔/兵营占满,分矿槽位全新)
            _others = [
                th for th in self.ai.townhalls.ready
                if th.position.distance_to(self.ai.start_location) > 5.0
            ]
            _tech_base = (
                _others[0].position
                if tech_goes_to_expansion(True, len(_others))
                else None
            )
            if not self._structure_present_or_pending(UnitID.STARGATE):
                await self._build_core_structure(UnitID.STARGATE, base=_tech_base)
            elif (
                not self._structure_present_or_pending(UnitID.FLEETBEACON)
                and [s for s in structures_dict[UnitID.STARGATE] if s.is_ready]
            ):
                # O228(o224-lane1 game_02 实证):FB 走 can_afford 派工,矿到 300 同帧
                # 被 zealot/探机/塔抢走,O110 自救 95 次全 no_money,FB 到死未落。
                # Zerg Timing 改关键件钉点派工(同 O147 forge:驻点等钱=钱到立刻
                # 开工),让 FB 排进资金第一顺位;其余流派维持 can_afford 守卫。
                if self._opp_race == "zerg" and self._ai_build == "timing":
                    self._dispatch_structure(
                        UnitID.FLEETBEACON,
                        _tech_base or self.ai.start_location,
                        critical=True,
                    )
                else:
                    await self._build_core_structure(
                        UnitID.FLEETBEACON, base=_tech_base
                    )
        # O109-③(o108 局3 实证):分矿供电豁免 rush 全停(仅 transition 流派)——
        # 局3 分矿晶落后 Nexus ~80-100s(波次接触期上面整块被跳),分矿塔
        # 恒 0-1、两掉两分矿。与块内调用幂等(在建计数 + max_on_route 去重)。
        if self._flow.transition is not None and not _rebuild_nexus:
            # O127-①:防御紧急且 forge 未拍 → 保底水晶让位(o126b 局1:O79
            # 路径 90/110 各 100 矿偷 forge 资金窗,上轮漏网)
            if not forge_first_pylon_yield(
                self._defense_urgent,
                bool(self.manager_mediator.get_own_structures_dict[UnitID.FORGE]),
                self.ai.supply_left,
            ):
                self._ensure_expansion_pylon()
                self._ensure_expansion_wall_gateway()
        # O105-③a(o104 局2/局5 实证):重建窗星门双开 —— 串行 SG1→SG2 亏一整个
        # 建造周期(~45s),首舰 ~640→~680 撞 650-720 大波;钱够两座就同时拍
        # O216d:FB 实体落成前不双开,否则第二座星门直接吃掉 FB 的 300 矿。
        if (
            stargate_double_opener(
                self._fleet_transitioned,
                self._first_fleet_seen(),
                len(structures_dict[UnitID.STARGATE])
                + self.manager_mediator.get_building_counter[UnitID.STARGATE],
                self.ai.minerals,
                self.ai.vespene,
            )
            and self._fb_entities_now > 0
        ):
            await self._build_core_structure(UnitID.STARGATE)
        # O218(o217 lane1/lane2 game_01 双实证):转舰队后星门恒 1 ——
        # extra_production 被 threat/_fleet_starved_capacity/_expand_holding
        # 常年闸住,气烂 400-736 而舰队 300s 只涨 1-4 艘,被 60+ supply 波滚平。
        # FB 实体在 + 首舰已出 + 气 ≥400(留 250 产舰) + SG 数 < min(8, 1+就绪基地)
        # → 直接补一座星门(can_afford 守卫,不抢塔/Nexus 保命钱)。
        _sg_total_o218 = (
            len(structures_dict[UnitID.STARGATE])
            + self.manager_mediator.get_building_counter[UnitID.STARGATE]
        )
        if (
            # O249(o248-lane1 game_01 实证):O248 不再强制 transition 后
            # _fleet_transitioned 永假,O218 追加 SG 整局不触发(星门恒 1);
            # 改为转舰队 或 首舰已出 皆可(Timing 直爬路线同样生效)。
            (self._fleet_transitioned or self._first_fleet_seen())
            and self._fb_entities_now > 0
            and self._first_fleet_seen()
            and _sg_total_o218 < min(8, 1 + self.ai.townhalls.ready.amount)
            and self.ai.vespene >= 400.0
            # O301-③(o300b game_03 实证):can_afford 门挡在钉点之外 —— 矿
            # 振荡 0-175 时闸不开,钉点永远不成立,SG1 整局、气 1060 烂。
            # ZT 走 critical 钉点(驻点等钱=钱到即开工,O229),不需要帧判
            # 钱够;非 ZT 路径 _build_core_structure 内部自带 can_afford
            # 守卫(5823),本门移除两侧都安全。
            # O233(o232-lane1 game_01 实证):rush latch 长期化把追加 SG 闸死,
            # 舰队 280s 卡 1 艘;放宽为「急性 rush(家 40 格敌 ≥4)」才闸,
            # 波间隙 latch 不挡产能。
            and not (
                self._rush_active
                and sum(
                    1 for u in self.ai.enemy_units
                    if not u.is_structure and is_combat_type(u.type_id)
                    and u.position.distance_to(self.ai.start_location) < 40
                ) >= 4
            )
        ):
            # O229(o227-lane2 game_01 实证):O218 事件连发 58+ 次但 SG2 至死
            # 未落成 —— can_afford 帧判后矿被 zealot/探机/塔同帧抢走,与 FB
            # 同型。Zerg Timing 追加星门同样改关键件钉点派工(驻点等钱)。
            # O295-①(o294a game_02 实证):钉点仍不落地 —— 主基带电 3x3 槽
            # 归零(no_placement),事件每帧无条件刷屏 100+ 次掩盖真因。
            # 改:就绪基地逐个试落位(主基满了落分矿);全部 no_placement →
            # 钉点补电(O55 同构自救);事件只在结果变化时记(节流治刷屏)。
            if self._opp_race == "zerg" and self._ai_build == "timing":
                _rc = None
                _blocs = [th.position for th in self.ai.townhalls.ready]
                for _bloc in (_blocs or [self.ai.start_location]):
                    _rc = self._dispatch_structure(
                        UnitID.STARGATE, _bloc, critical=True
                    )
                    if _rc == "dispatched":
                        break
                if _rc == "no_placement":
                    self._dispatch_structure(
                        UnitID.PYLON, self.ai.start_location, critical=True
                    )
                if _rc != getattr(self, "_o218_last_rc", None):
                    self._o218_last_rc = _rc
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": (
                            f"O218:气烂银行追加星门(SG={_sg_total_o218},"
                            f"气={self.ai.vespene:.0f},派工={_rc})"
                        ),
                    })
            else:
                await self._build_core_structure(UnitID.STARGATE)
                self.ai._events.append({
                    "t": round(self.ai.time, 1),
                    "msg": (
                        f"O218:气烂银行追加星门(SG={_sg_total_o218},"
                        f"气={self.ai.vespene:.0f})"
                    ),
                })
        # O83(n5m-zerg-rush game_03 实证):舰队饥饿豁免 —— 慢性威胁/持续抄家时
        # rush 分支(上)与 E9 让位(tech_yields_to_threat)把舰队航标永久冻结:
        # 3 就绪星门 250s 零产出、气烂 2500+ 败亡(流派出兵全是耗气的暴风/航母)。
        # 气银行 ≥600 + 无 FB + 有就绪星门 = 管线明确停转,防御已饱和后
        # FB(300矿/200气)豁免一切冻结单独补建。急性 rush 窗(O67)气攒不到
        # 600,语义不受影响。
        # O85(n5m-terran-timing game_01 实证):豁免不能再让 _expand_holding ——
        # 拉锯局 Nexus pending/重建几乎常驻,holding 把豁免一并跳过,FB 照旧死锁
        # (SG 就绪 300s、气 2400、无 FB)。舰队饥饿时 FB > 下一矿(O56/O57 同构:
        # 舰队成型前不开三矿,同理舰队饥饿时先 FB 后 Nexus)。
        # O92:过渡形态期冻结 FB 豁免 —— 豁免的本意是救舰队管线,过渡期舰队
        # 是故意推迟的(气攒着无害,追猎也在吃),转舰队后豁免自然恢复。
        if _fleet_starved and not self._transition_active:
            # O235(o234-lane1 game_01 实证):中后局 FB 被拆后重建走 can_afford
            # 同帧抢单老路,气烂 2400/5 星门/舰队停产 300s+ 僵死。Zerg Timing
            # FB 重建同走 O228 关键件钉点派工。
            if self._opp_race == "zerg" and self._ai_build == "timing":
                self._dispatch_structure(
                    UnitID.FLEETBEACON, self.ai.start_location, critical=True
                )
            else:
                await self._build_core_structure(UnitID.FLEETBEACON)
        # O93-B3:FB 建造停滞自救(买得起+有就绪星门却始终无 FB 实体 →
        # 落位静默失败/tracker 泄漏,见方法注释)。_fleet_starved 豁免只管注册,
        # 不管"注册了但永远建不出来"。
        self._fleet_stall_watchdog(structures_dict)
        # O239(o237 多局尸检):气烂 ≥700 而矿恒 <100 的局,暴风(250 矿)产不动,
        # 舰队 6-9 艘打不赢 60-90 supply 地面波。航母拦截机吸火+本体远程,
        # vs 无对空地面是质变(胜局均有 3-4 航母混编)。气烂且 FB 在时,
        # 空闲就绪星门直接点航母(每帧最多 1 座,can_afford 含 350 矿判)。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and self.ai.vespene >= 700.0
            and self._fb_entities_now > 0
            and self.ai.can_afford(UnitID.CARRIER)
        ):
            for _sg in self.manager_mediator.get_own_structures_dict[
                UnitID.STARGATE
            ]:
                if _sg.is_ready and _sg.is_idle:
                    _sg.train(UnitID.CARRIER)
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": f"O239:气烂银行点航母(气={self.ai.vespene:.0f})",
                    })
                    break
        # O260-②(o259b-g02 实证):航母买不起(矿恒 <350)但暴风买得起且气
        # ≥500 → 空闲星门先点暴风。save_up 截断(航母占比落后只留航母)把
        # 星门押给永远凑不齐的 350 矿,气 1000+ 烂 300s 只产 1 暴风 1 航母;
        # 舰队数量 > 完美配比,暴风落地即战力。
        # O301-②(o300b game_03 实证):气门 500 太高 —— 气 365-507 窗星门
        # 全闲(G1 整局),暴风 175/125 本可负担却一艘不点,追猎洪水抢矿。
        # 300 以上即点(暴风气耗 125,留 175 余量给 FB/航母接力)。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and self.ai.vespene >= 300.0
            and self._fb_entities_now > 0
            and not self.ai.can_afford(UnitID.CARRIER)
            and self.ai.can_afford(UnitID.TEMPEST)
        ):
            for _sg in self.manager_mediator.get_own_structures_dict[
                UnitID.STARGATE
            ]:
                if _sg.is_ready and _sg.is_idle:
                    _sg.train(UnitID.TEMPEST)
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": f"O260:气烂点暴风兜底(气={self.ai.vespene:.0f})",
                    })
                    break
        # O264-②(司令观察③):舰队 ≥3 艘后补母舰 —— 隐身场(Cloaking Field)
        # 覆盖航母/暴风/地面混编,Zerg Timing AI 反隐靠眼虫、推进通常不带,
        # 隐身期舰队存活显著拉长;母舰本体还有光束输出。只吃烂气窗口
        # (气 ≥600 且买得起才点,400/400 不抢舰队产能资金窗);全局 1 艘。
        # O266b(o266 双 lane 实证):Nexus 全程在产农 → idle 永不成立,
        # 母舰整轮零出场;改为允许排队(跟在 1 个农民后 +12s,可接受)。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and self._fb_entities_now > 0
            and self.ai.vespene >= 600.0
            and (
                self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST)
                + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER)
            ) >= 3
            and (
                self.manager_mediator.get_own_unit_count(
                    unit_type_id=UnitID.MOTHERSHIP
                )
                + cy_unit_pending(self.ai, UnitID.MOTHERSHIP)
            )
            == 0
            and self.ai.can_afford(UnitID.MOTHERSHIP)
        ):
            for _th in self.ai.townhalls.ready:
                if _th.orders and len(_th.orders) >= 2:
                    continue  # 队列里已有 2 条(农民+母舰在途)就别再压
                _th.train(UnitID.MOTHERSHIP)
                self.ai._events.append({
                    "t": round(self.ai.time, 1),
                    "msg": "O264:母舰开造(隐身场保舰队)",
                })
                break
        # O261-①(o224 胜局编配实证 + o254-o260 累计 0-58 死窗尸检):ZT 直爬
        # SG 就绪(261-281s)→FB 就绪(~385s)之间星门空转 100s+,而死窗波
        # (9蟑螂+11狗)零对空 —— 虚空(仅需 SG)是死窗唯一的真实战力:
        # 2 艘虚空 ~20dps 无战损点杀蟑螂,o224 首胜编配里就有 3 虚空。
        # FB 就绪即停(舰队科技接管星门),最多 2 艘(300/200,不抢 FB 窗)。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and self._fb_entities_now == 0
            and not self._structure_present_or_pending(UnitID.FLEETBEACON)
            and (
                self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.VOIDRAY)
                + cy_unit_pending(self.ai, UnitID.VOIDRAY)
            ) < 2
            and self.ai.can_afford(UnitID.VOIDRAY)
        ):
            for _sg in self.manager_mediator.get_own_structures_dict[
                UnitID.STARGATE
            ]:
                if _sg.is_ready and _sg.is_idle:
                    _sg.train(UnitID.VOIDRAY)
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": "O261:死窗虚空(FB 前星门不空转)",
                    })
                    break
        # Nexus 因矿恒 <475(dispatch_viable buffer)永远排不出,2 基地 44 农封顶
        # 被慢性磨死。硬饱和时对最近空闲扩张点钉点派 Nexus(驻点等钱,与
        # SG/FB/robo 同款),三矿真正把饱和农民变成收入。
        # O262-②(o261 双 lane 0-10 尸检,复盘 one_base×5):钉点开矿从三矿
        # 起(2<=bases)扩到首扩(1<=bases)——单矿硬饱和(≥24 农)时同样钉点,
        # 治「主闸已放行但 Nexus 排不出/被波次打断」。
        # O262-③:钉点派工加近可负担门(矿 ≥350)——驻点等钱从 100s+ 压到
        # <10s,暴露窗与 idle_builder 等钱同步收敛(o261a-g01 两次钉点
        # 各等 100s+ 被波次打断)。
        # O263-②:首扩钉点叠加「320s 窗 + 分矿点无敌」——O262-② 的无窗首扩
        # 钉点会把 Nexus 拍进首波行进路线(o262a-g02 白捐 400 实证);
        # 多矿钉点(o251 原场景)行为不变。
        # O265 已证伪回退(220s 实验双 lane 1-4/1-2,速败回升):窗保持 320s。
        # O274-①(司令观察):首扩钉点去 rush 闸 —— 波 60-90s 一波,
        # rush latch 近半时间激活,钉点被无限推迟(二矿 422-482s 甚至不开,
        # 司令实证)。波在主基被塔/墙接住时正是分矿空窗,保留
        # 320s 窗 + 分矿点无敌 + 矿 ≥350 三重保护,不再等 rush 解除。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and 1 <= self.ai.townhalls.amount < 5
            and self.ai.supply_workers >= 16 * self.ai.townhalls.amount + 8
            and self.ai.not_started_but_in_building_tracker(UnitID.NEXUS) == 0
            and (
                not self._rush_active or self.ai.townhalls.amount == 1
            )
            and self.ai.minerals >= 350.0
            # O279:首波预警期暂停扩张钉点 —— 波出门后往分矿点派工人/拍
            # Nexus = 往波路径上送 400 矿(o262 白捐实证);预警解除(接触)
            # 后波打主基,分矿空窗再开。
            and not self._wave_incoming
            and (
                self.ai.townhalls.amount >= 2
                or (
                    # O278-②:首扩窗 320→280,与分矿口预置塔(t≥250)联动
                    # O281:踩点检查对着首扩目标点(口袋矿),不是 natural
                    self.ai.time >= 280.0
                    and self._cannons_ready_peak >= 1
                    and self._zt_enemy_near_expand_target() == 0
                )
            )
        ):
            _free_exp = [
                el
                for el in self.ai.expansion_locations_list
                if not self.ai.townhalls.closer_than(5.0, el)
            ]
            if _free_exp:
                # O281:ZT 首扩(townhalls==1)钉点目标 = 口袋矿(离敌最远);
                # 多矿钉点(o251 原场景)仍取最近,行为不变。
                _exp_target = self._zt_pocket_expand_target() or min(
                    _free_exp,
                    key=lambda el: min(el.distance_to(th) for th in self.ai.townhalls),
                )
                self._dispatch_structure(
                    UnitID.NEXUS, _exp_target, critical=True, needs_power=False
                )
                if not getattr(self, "_o251_logged", False):
                    self._o251_logged = True
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": "O251:硬饱和钉点开矿(Nexus 驻点等钱)",
                    })
        # O245(Zerg Timing 攻坚,vs roach/hydra 地面海的正确答案):转舰队后
        # 敌可见地面 ≥6 且无机械台 → 钉点派工建 ROBOTICSFACILITY(与 SG/FB
        # 同优先级,驻点等钱),不朽者混编见 _effective_spawn O245 块。
        # O245b(o245 双 lane game_01 实证):first_fleet_seen 前置太晚(robo
        # 600s+ 才排,基地 500-700s 已丢),去掉;落位优先分矿(主基被围/
        # 槽位满/工人被杀是 game_01 robo 派工 8 次零落成的直接原因)。
        # O245d(o245-lane2 game_03 实证):波次连续时 transition 常驻不退出,
        # _fleet_transitioned 永假 → robo 整局不排(本局 1354s robo=0)。
        # 加时间旁路:转舰队 或 t≥360 且敌地面 ≥6 即排。
        # O257-②(o256 尸检):360s 太晚 —— 波 305-315s 已可见(敌地面 ≥6),
        # 360 才排 → 首不朽 ~450s,波 2-6(350-660s 连续)已把经济磨穿;
        # 降到 280(敌地面 ≥6 前提不变,无形早排风险)。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and (self._fleet_transitioned or self.ai.time >= 280.0)
            and self._visible_enemy_army_count() >= 6
            and not self._structure_present_or_pending(UnitID.ROBOTICSFACILITY)
        ):
            _robo_others = [
                th
                for th in self.ai.townhalls.ready
                if th.position.distance_to(self.ai.start_location) > 5.0
            ]
            _robo_base = (
                _robo_others[0].position if _robo_others else self.ai.start_location
            )
            _robo_result = self._dispatch_structure(
                UnitID.ROBOTICSFACILITY, _robo_base, critical=True
            )
            # O245f(o245e 双 lane game_01 实证):建台派工反复尝试零落成,
            # 失败环节(no_worker/no_placement/taken/tech_not_ready)取证,
            # 30s 节流;dispatched 时记落成跟踪。
            if _robo_result != "dispatched" and (
                self.ai.time - getattr(self, "_o245_fail_logged_at", 0.0) > 30.0
            ):
                self._o245_fail_logged_at = self.ai.time
                self.ai._events.append({
                    "t": round(self.ai.time, 1),
                    "msg": f"O245:建台派工失败={_robo_result}",
                })
            if not getattr(self, "_o245_logged", False):
                self._o245_logged = True
                self.ai._events.append({
                    "t": round(self.ai.time, 1),
                    "msg": "O245:敌地面重型,钉点建机械台(不朽者混编)",
                })
        # O245e(o245-lane1 game_04 实证):SpawnController 优先级竞争中不朽者
        # 每帧让位暴风,零产出。机械台就绪且敌地面 ≥6 且不朽 <4 且买得起
        # → 空闲机械台直接点不朽(与 O239 航母同机制,绕过配比竞争);
        # 买不起时由 spawn_pause_reason 的 immortal_reserve 攒钱。
        # O297-②(o296b game_02 实证):舰队基建已活后不朽 275 矿/个与暴风
        # 抢矿(2 不朽 ≈ 3 暴风的矿,94 人口杂牌军被 82 波碾)——让位舰队。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and self._visible_enemy_army_count() >= 6
            and not self._zt_fleet_infra_live()
            and self.ai.can_afford(UnitID.IMMORTAL)
            and (
                self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.IMMORTAL)
                + cy_unit_pending(self.ai, UnitID.IMMORTAL)
            ) < 4
        ):
            for _robo in self.manager_mediator.get_own_structures_dict[
                UnitID.ROBOTICSFACILITY
            ]:
                if _robo.is_ready and _robo.is_idle:
                    _robo.train(UnitID.IMMORTAL)
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": "O245e:机械台直产不朽",
                    })
                    break
        self._rush_gateway_boost()  # E3d: rush 敌兵>叉子时追加 gateway(单兵营是瓶颈)
        self._morph_gateways()
        if not _rebuild_nexus:
            self._auto_expand(macro_plan)
            self._chrono_structures()
        # 升级前置科技建筑补建(O1/O10):core_structures 没覆盖的(如 FORGE,
        # 以及盾 L2/L3 需要的 TWILIGHTCOUNCIL)由带 can_afford 守卫的
        # _build_core_structure 补建;已覆盖的走 _build_flow_structures(保留
        # FLEETBEACON 需就绪星门的特判)。研究本身在上方 MacroPlan 里(O8)。
        if _upgrades and not _rebuild_nexus:
            _covered = set(self._flow.core_structure_ids())
            for _tech_building in upgrade_tech_buildings(
                _upgrades, done=self.ai.state.upgrades
            ):
                if _tech_building not in _covered:
                    # E3d: rush 期间只保炮塔前置 FORGE,其余科技建筑(暮光等)让位
                    if self._rush_active and _tech_building != UnitID.FORGE:
                        continue
                    # O168:8 农民 carrier 核心科技缺失期间，升级的 Forge 前置也让位，
                    # 避免空军攻 L1 把 Cybercore/Stargate 的 150 矿吃掉。
                    if (
                        _early_core_missing
                        and _tech_building == UnitID.FORGE
                    ):
                        continue
                    await self._build_core_structure(_tech_building)

        # one off task to build an oracle（流派配置里 one_off 含 ORACLE 才造；
        # 需舰队航标 + 有空闲就绪星门）
        # A2:pivot 模式下先知推迟到首艘 TEMPEST 之后(先知 150/150 插队星门
        # 是首艘风暴晚 50-70s 的另一半原因);非 pivot 行为零变化
        # O96:转舰队后(fleet_transitioned)同闸 —— o95 局3/局4 先知在舰队
        # 零产出窗口抢 150/150,首暴风拖到 t=791
        if not self._built_single_oracle and UnitID.ORACLE in self._flow.one_off_ids():
            if (
                self.ai.can_afford(UnitID.ORACLE)
                and oracle_before_fleet_allowed(
                    self._pivot_tempest_mode(),
                    self._first_fleet_seen(),
                    self._fleet_transitioned,
                )
                and len(structures_dict[UnitID.FLEETBEACON]) > 0
                and self.ai.structures.filter(
                    lambda u: u.type_id == UnitID.STARGATE and u.is_ready and u.is_idle
                )
            ):
                self.ai.train(UnitID.ORACLE)
                self._built_single_oracle = True

    # ────────────────────────────── Terran 生产层 (M1) ──────────────────────────────
    def _update_terran(self) -> None:
        """人族生产:全部借 ares 种族无关/人族支持的宏行为,不手写建造顺序。

        组成: AutoSupply(补给站) + BuildWorkers(SCV) + GasBuildingController(炼油厂)
             + ProductionController(按 army_comp 自动补 rax/factory/starport,人族支持)
             + SpawnController(按 army_comp 出兵) + UpgradeCCs(升轨道指挥) + build 杠杆。
        ⚠️ 未跑局验证(M1):建造时机/addon(techlab/reactor)管理/架坦克等细节留待实测调
           (见 docs/status-and-roadmap.md M1/M4)。开局序列可由 terran_builds.yml 的 build runner 接管。
        """
        ai = self.ai
        base = ai.start_location
        spawn = self._army.spawn_dict()

        # 农民 + 轨道指挥(种族无关的 SCV/CC 升级)
        ai.register_behavior(BuildWorkers(to_count=worker_target(ai.townhalls.amount)))
        ai.register_behavior(UpgradeCCs(to=UnitID.ORBITALCOMMAND))

        # M3:升级配置化 —— army_composition.yml 的 terran.upgrades 交 ares UpgradeController
        # (种族无关,自动 tech-up)。列表空则不注册。
        if upgrades := self._army.upgrade_ids():
            ai.register_behavior(UpgradeController(upgrades, base_location=base))

        # 气:有军事生产建筑后每矿双气,开局先单气
        has_prod = any(
            self._structure_present_or_pending(s)
            for s in (UnitID.BARRACKS, UnitID.FACTORY, UnitID.STARPORT)
        )
        ai.register_behavior(GasBuildingController(
            to_count=gas_target(ai.townhalls.ready.amount, has_prod),
            closest_to=base,
        ))

        # 供给 / 造兵 / 自动补生产建筑(ProductionController 人族/神族支持)
        plan: MacroPlan = MacroPlan()
        plan.add(AutoSupply(base_location=base))
        if spawn:
            plan.add(SpawnController(army_composition_dict=spawn))
            plan.add(ProductionController(spawn, base_location=base))
        # 运营杠杆(build=barracks / expand=yes 等)复用同一套(expand 走 ExpansionController,种族无关)
        _order = getattr(ai, "steer_order", None) or {}
        self._handle_manual_build(_order, plan)
        ai.register_behavior(plan)

    def _update_zerg(self) -> None:
        """虫族生产 (M2):无 ProductionController(不支持 Zerg),改用 ares 种族无关积木自建。

        组成: BuildWorkers(drone) + AutoSupply(overlord,种族无关) + SpawnController(larva/morph 出兵)
             + TechUp(每个组成兵种自动补科技建筑,如 ROACH→RoachWarren,种族无关)
             + 女王(每巢一只) + UpgradeController(M3) + build/expand 杠杆(expand→hatchery)。
        ⚠️ 未跑局验证(M2):larva 注卵(inject)/铺菌毯/兵种节奏都没做 —— Zerg 宏离不开注卵,
           这块是 M2 剩余大头,必须跑局调(见 status-and-roadmap M2)。开局序可交 zerg_builds.yml。
        """
        ai = self.ai
        base = ai.start_location
        spawn = self._army.spawn_dict()

        ai.register_behavior(BuildWorkers(to_count=worker_target(ai.townhalls.amount)))

        plan: MacroPlan = MacroPlan()
        plan.add(AutoSupply(base_location=base))  # 种族无关:Zerg 下自动造 overlord
        if spawn:
            plan.add(SpawnController(army_composition_dict=spawn))
        # 每个在产兵种自动补所需科技建筑(TechUp 种族无关:ROACH→RoachWarren 等)
        for spec in self._army.units:
            if spec.proportion <= 0:
                continue
            uid = getattr(UnitID, spec.id_name, None)
            if uid is not None:
                plan.add(TechUp(desired_tech=uid, base_location=base))
        if upgrades := self._army.upgrade_ids():
            plan.add(UpgradeController(upgrades, base_location=base))
        _order = getattr(ai, "steer_order", None) or {}
        self._handle_manual_build(_order, plan)
        ai.register_behavior(plan)

        self._build_zerg_queens()

    # ────────────────────── pivot 自适应(反rush/反空军,2026-07) ──────────────────────
    def _early_scout(self) -> None:
        """pivot·早侦查:t≈100s 自动派一个探机看对面开局(看有没有 rush 迹象),到点撤回。
        O36(司令观察,4人图实证):多出生点地图近→远逐点排查,不是只赌最近一个点
        (推进由 _update_early_scout_route 负责)。"""
        if self._early_scout_done or self.ai.time < (
            # O97:transition 流派探机 t≈55 出发(事件驱动早评,防链前移 ~40s);
            # O98(o97 局1/3/4/5 实证):再提前到 40 —— 55 出发 t≈95-105 才到
            # 敌家,撞上出门狗群(~95-105)被截杀,4/5 局从未送达;40 出发
            # t≈75-85 到,早于最早狗群孵化。其余流派保持 100 不变
            40 if self._flow.transition is not None else 100
        ):
            return
        self._early_scout_done = True
        self._pivot_scout_route = list(self.ai.enemy_starts_ranked())
        if not self._pivot_scout_route:
            return
        if w := self.ai.mediator.select_worker(
            target_position=self._pivot_scout_route[0]
        ):
            self.ai.mediator.assign_role(tag=w.tag, role=UnitRole.SCOUTING)
            w.move(self._pivot_scout_route[0])
            self._pivot_scout_tag = w.tag  # E7:记下tag,断链判"还在路上"用
            if self._flow.transition is not None:
                # O99-② 簿记:出发一条(抵达=O97 早评事件,失联=O99 补派事件)
                self.ai._events.append(
                    {
                        "t": round(self.ai.time, 1),
                        "msg": f"O99:早侦查探机出发(目标{self._pivot_scout_route[0]})",
                    }
                )

    def _update_early_scout_route(self) -> None:
        """O36(司令观察,4人图 CactusValley 实证):pivot 早侦查探机逐点推进出生点。
        摸到空点(无建筑)→ 去下一点;情报到手 → 停推进,撤回交给 O35(tempest/stalker)
        /O9(carrier);全部摸完仍无情报 → 直接回家采矿(对面主基必占其一,纯兜底)。
        判据纯函数 production_plans.scout_next_step。"""
        tag = self._pivot_scout_tag
        if tag is None or not self._pivot_scout_route:
            return
        scout = self.ai.units.find_by_tag(tag)
        if scout is None:
            self._pivot_scout_route = []
            return
        step = scout_next_step(
            self._pivot_scout_route,
            arrived=scout.distance_to(self._pivot_scout_route[0]) < 12,
            intel_found=bool(self.ai.enemy_structures),
        )
        if step == "next":
            self._pivot_scout_route.pop(0)
            scout.move(self._pivot_scout_route[0])
        elif step == "home":
            self._pivot_scout_route = []
            if not self.ai.enemy_structures:
                self.ai.mediator.assign_role(tag=scout.tag, role=UnitRole.GATHERING)
                scout.move(self.ai.start_location)
                self._pivot_scout_tag = None
        elif scout.is_idle:
            scout.move(self._pivot_scout_route[0])

    # O9: 侦查情报→开局决策的评估时点(探机 100s 出发,留 70s 赶路/送死窗口)
    _SCOUT_VERDICT_AT: float = 170.0
    # E7:无情报时的宽限/补派硬底线(之后按「侦查已尽力未送达」保守 rush)
    _SCOUT_HARD_DEADLINE: float = 230.0
    # O9: rush 征兆的"早出兵建筑"(看到 ≥2 个即判 rush;与判据早期多兵互补)
    _MILITARY_STRUCTS = {
        UnitID.BARRACKS, UnitID.GATEWAY, UnitID.SPAWNINGPOOL, UnitID.ROACHWARREN,
    }
    # O97:早评/O71 共用的敌基地口径(开二矿 = 运营开局证据)
    _ENEMY_TOWNHALL_IDS = {
        UnitID.NEXUS, UnitID.COMMANDCENTER, UnitID.HATCHERY,
        UnitID.ORBITALCOMMAND, UnitID.PLANETARYFORTRESS,
        UnitID.LAIR, UnitID.HIVE,
    }

    # O138(o136b/o137 0-10 实证):坡口墙默认关断 —— _wall_slots() 入口闸,
    # 墙链/墙后站位/农民堵缝全由此取 None 回退 o135 行为;重开实验翻 True
    _WALL_ENABLED: bool = False

    def _wall_slots(self, force: bool = False) -> tuple | None:
        """O136-①:主坡墙位簿记 = (墙位水晶点, [3x3 墙槽×2], 墙缝点)。

        读 burnysc2 Ramp 的 protoss_wall_pylon/protoss_wall_buildings/
        protoss_wall_warpin(ares placement 已按同组数据预计算 wall 槽,
        BuildStructure/request_building_placement 传 wall=True 即取)。
        只挂 transition 流派(carrier);非主图结构(槽 <2/ramp 数据异常)
        → None,调用方回退原防链。一局算一次(位置静态)。
        O137-②:派工失败 ≥2 次 latch 关闭(_wall_disabled)→ 恒 None。
        O138(o136b/o137 两系列 0-10,avg 231-233 远差于 o135 基线 570-640):
        坡口墙实验整体证伪 —— 墙派工(水晶→GW→forge 串行+等电窗)拖累
        防链,两轮修复没救回。默认关断(代码保留备查,重开= _WALL_ENABLED
        翻 True);protoss_builds.yml 的 '12 gateway' 开局独立有效,不受影响。
        force(O258-②):O138 关断针对的是 rush 早期窗(55-150s 墙派工抢
        forge/首塔钱);ZT unknown 窗(t≥200,银行 1300+,threat 即停工)是
        不同的经济上下文,调用方传 force=True 局部重开,_WALL_ENABLED
        保持 False 不动 O138 语义。"""
        if not (self._WALL_ENABLED or force):
            return None
        if self._wall_disabled:
            return None
        if self._wall_info_done:
            return self._wall_info
        self._wall_info_done = True
        if self._flow.transition is None:
            return None
        ramp = getattr(self.ai, "main_base_ramp", None)
        if ramp is None:
            return None
        try:
            buildings = list(ramp.protoss_wall_buildings)
            pylon = ramp.protoss_wall_pylon
            gap = ramp.protoss_wall_warpin
        except Exception:  # 槽数不对的图 burnysc2 直接 raise —— 当无墙位处理
            return None
        if pylon is None or gap is None:
            return None
        home = self.ai.start_location
        slots = pick_wall_positions(
            [(p.x, p.y) for p in buildings], (home.x, home.y)
        )
        if len(slots) < 2:
            return None
        self._wall_info = (
            Point2(pylon),
            [Point2(s) for s in slots],
            Point2(gap),
        )
        return self._wall_info

    def _pending_near(self, sid, pos, radius: float = 3.0) -> int:
        """O136:tracker 里目标点在 pos 半径内的在途建筑数(墙槽占用口径,
        补 structures 只看已落地的盲区)。"""
        n = 0
        for info in self.manager_mediator.get_building_tracker_dict.values():
            if info[TRACKER_ID] != sid or not info.get(TARGET):
                continue
            if Point2(info[TARGET]).distance_to(pos) < radius:
                n += 1
        return n

    def _on_wall(self, slots, sid) -> bool:
        """O136:墙槽上是否已有(落地或在途)该型建筑。"""
        for slot in slots:
            if any(
                s.type_id == sid and s.position.distance_to(slot) < 2.0
                for s in self.ai.structures
            ) or self._pending_near(sid, slot, 2.0):
                return True
        return False

    def _wall_strike(self, sid, reason: str) -> None:
        """O137-②:墙派工失败记一击 + 簿记;≥2 击 latch 关墙(回退 o135)。"""
        self._wall_strikes += 1
        self.ai._events.append({
            "t": round(self.ai.time, 1),
            "msg": f"O137:墙派工失败×{self._wall_strikes}({sid.name},{reason})",
        })
        if wall_disabled_after(self._wall_strikes):
            self._wall_disabled = True
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": "O137:墙逻辑本局关闭(latch),防链回退普通槽",
            })

    def _wall_track(self, sid, result: str) -> bool:
        """O137-①:墙派工四分类取证(O116 同型:taken/no_placement/no_worker/
        dispatched,结果变化时簿记)+ 失败计时;超 30s → 回落普通槽+记一击。
        返回 True = 已回落(调用方本帧起落回原链)。"""
        if result != self._wall_last_result.get(sid):
            self._wall_last_result[sid] = result
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": f"O137:墙派工{sid.name}={result}",
            })
        if result == "dispatched":
            self._wall_fail_since.pop(sid, None)
            return False
        if result in ("not_viable", "cooldown"):
            # O139:缺钱/撤回冷却是全局资源态,不是墙槽的问题 —— 不计失败
            # 时钟/击数(否则穷局墙被误判死刑,富局墙也没机会)
            return False
        since = self._wall_fail_since.setdefault(sid, self.ai.time)
        if wall_fallback_due(since, self.ai.time):
            self._wall_fallback.add(sid)
            self._wall_fail_since.pop(sid, None)
            self._wall_strike(sid, result)
            return True
        return False

    def _wall_release_stalled(self, sid, slots) -> bool:
        """O137-①:墙槽在途 sid 超 30s 未开工(驻车干等)→ 清 tracker 放人
        回采 + 记一击 + 回落普通槽。o136b 局1:无 can_afford 守卫的墙派工
        让 2/11 工人在墙槽干等 90s+,钱全被水晶吃光。返回 True=本帧有释放。"""
        tracker = self.manager_mediator.get_building_tracker_dict
        for tag, info in list(tracker.items()):
            if info[TRACKER_ID] != sid or not info.get(TARGET):
                continue
            tgt = Point2(info[TARGET])
            if not any(tgt.distance_to(slot) < 2.0 for slot in slots):
                continue  # 普通槽的在途同型不归墙管
            if any(
                s.type_id == sid and s.position.distance_to(tgt) < 2.0
                for s in self.ai.structures
            ):
                continue  # 已开工
            if not wall_fallback_due(info[TIME_ORDER_COMMENCED], self.ai.time):
                continue
            self.manager_mediator.get_building_counter[sid] -= 1
            tracker.pop(tag)
            w = self.ai.workers.find_by_tag(tag)
            if w is not None:
                self.manager_mediator.assign_role(tag=tag, role=UnitRole.GATHERING)
                if self.ai.mineral_field:
                    w.gather(self.ai.mineral_field.closest_to(w))
            self._wall_fallback.add(sid)
            self._wall_strike(sid, "stalled")
            return True
        return False

    def _wall_build_chain(self, home, force: bool = False) -> bool:
        """O136-①/O257 抽取:坡口墙建造链(墙位水晶 → GW 上墙 → forge 上墙)。

        True = 墙工在途/等钱(调用方串行返回,一次只推进一步);
        False = 无墙槽 或 三件已在墙(调用方继续后续链)。
        物理封口后狗群进不来,叉/塔竞速(差 1-2s 的硬币)整个家族被消灭。
        runner 的 '12 gateway' 若抢先落普通槽不冲突 —— rush 局 GW2 本来
        就要(③b cap 3),max_on_route=2 不被它在途占住。
        force(O258-②):透传 _wall_slots 的局部重开(ZT unknown 窗)。
        """
        wall = self._wall_slots(force=force)
        if wall is None:
            return False
        _pylon_pos, _slots, _gap = wall
        # O137-①:墙槽在途超 30s 未开工(驻车干等)→ 放人回落普通槽
        for _wsid in (UnitID.PYLON, UnitID.GATEWAY, UnitID.FORGE):
            self._wall_release_stalled(_wsid, [_pylon_pos] if _wsid == UnitID.PYLON else _slots)
        # ① 墙位供电水晶(墙两件没电起不来;水晶自身即电源 needs_power=False)
        # O137-①②:can_afford 守卫(无钱不派工不驻车)+ 失败取证/30s 回落
        if UnitID.PYLON not in self._wall_fallback and (
            sum(
                1 for s in self.ai.structures
                if s.type_id == UnitID.PYLON
                and s.position.distance_to(_pylon_pos) < 3.0
            )
            + self._pending_near(UnitID.PYLON, _pylon_pos)
        ) == 0:
            if not self.ai.can_afford(UnitID.PYLON):
                return True  # 无钱:等下帧(原链各步自带守卫,同样无米下锅)
            self._wall_track(
                UnitID.PYLON,
                self._dispatch_structure(
                    UnitID.PYLON, home,
                    closest_to=_pylon_pos, needs_power=False, wall=True,
                ),
            )
            return True
        # ② GW 上墙(血厚墙件;在普通槽的 runner GW 不算数)
        if UnitID.GATEWAY not in self._wall_fallback and not self._on_wall(
            _slots, UnitID.GATEWAY
        ):
            if not self.ai.can_afford(UnitID.GATEWAY):
                return True
            self._wall_track(
                UnitID.GATEWAY,
                self._dispatch_structure(
                    UnitID.GATEWAY, home, wall=True, max_on_route=2
                ),
            )
            return True
        # ③ forge 上墙(第二墙件;墙两件+缝 = 物理封口,只漏 1 格单位缝)
        if UnitID.FORGE not in self._wall_fallback and not self._on_wall(
            _slots, UnitID.FORGE
        ):
            if not self.ai.can_afford(UnitID.FORGE):
                return True
            self._wall_track(
                UnitID.FORGE,
                self._dispatch_structure(UnitID.FORGE, home, wall=True),
            )
            return True
        # O288-②(司令观察「彻底堵口+折射出门」):缝不用建筑封 —— 农民
        # 开矿/调拨必须步行出缝,建筑封死=自囚(口袋矿经济链断)。
        # 缝的防守交给 O136 武装的站位/堵件逻辑(_wall_gap_point 消费方),
        # 这里补墙外折射水晶:地面部队出门靠折射到低地水晶能量场
        # (缝朝坡底 5 格),同时给墙后塔阵供电。
        _ramp = getattr(self.ai, "main_base_ramp", None)
        if _ramp is not None and getattr(_ramp, "bottom_center", None) is not None:
            _out = Point2(_gap).towards(Point2(_ramp.bottom_center), 5.0)
            if (
                sum(
                    1 for s in self.ai.structures
                    if s.type_id == UnitID.PYLON
                    and s.position.distance_to(_out) < 4.0
                )
                + self._pending_near(UnitID.PYLON, _out, 4.0)
            ) == 0:
                if not self.ai.can_afford(UnitID.PYLON):
                    return True
                self._wall_track(
                    UnitID.PYLON,
                    self._dispatch_structure(
                        UnitID.PYLON, home, closest_to=_out, needs_power=False,
                    ),
                )
                return True
        return False

    async def _presumed_defense_chain(self) -> None:
        """O118-①/O127-①/O129:presumed/冲刺窗防御链手动版,不走 PSD。

        PSD 的 per-base 水晶先吃 200 矿(o117 实证);O129 链序硬编码:
        forge(150) → 塔位供电水晶+首塔(150) → GW1(150) → 首叉(100),
        前一步「已拍或在建」才放行下一步。波次接触(threat/敌进家)即
        交还 F2 正常防御链(调用方条件保证)。
        """
        home = self.ai.start_location
        # O136-①:坡口墙链(O257 起抽为 _wall_build_chain, presumed 链与
        # ZT unknown 窗共用);True=墙工在途/等钱,调用方串行返回
        if self._wall_build_chain(home):
            return
        # O168:8 农民开局 carrier 核心科技(CYBERNETICCORE/STARGATE/FLEETBEACON)
        # 缺失期间，presumed 链连 forge 一起跳过，把 150 矿留给科技链。
        # 真实 rush 局 _rush_active 为真 → _early_core_missing 为假 → 链正常走。
        # O207:vs Zerg Rush/Timing 不能等 cybercore 排队再铺 forge——timing 波
        # 273-289s 到脸，cybercore 90s 才排，等 cybercore 再 forge 首塔赶不上。
        if self._early_core_missing and not self._is_zerg_rush_timing():
            return
        # ① forge(未拍才补;present_or_pending 守卫在上)
        # O147-①:forge 走关键件豁免派工(钉点驻点等钱 = 钱到立刻开工,
        # O118 时代 forge 95-110 靠它;_build_core_structure 的 can_afford
        # 守卫 + O139 禁钉把 forge 治回 125-155,o146b 局1 实证 153)
        # O206(o205-vh-zerg-power 败局实证):Power/Macro 局里 _presumed_rush
        # 长期触发,关键件豁免把农民钉在 FORGE 3.5min+ 不采矿。仅在地
        # rush_confirmed(情报/接触证实)时才豁免;plain presumed 走资金守卫。
        if not self._structure_present_or_pending(UnitID.FORGE):
            self._dispatch_structure(
                UnitID.FORGE, home,
                critical=(
                    self._rush_confirmed
                    and critical_dispatch_exempt(
                        "FORGE",
                        len(self.manager_mediator.get_own_structures_dict[UnitID.FORGE]),
                    )
                ),
            )
            return
        _forge_ready = any(
            s.is_ready
            for s in self.manager_mediator.get_own_structures_dict[UnitID.FORGE]
        )
        _cannons_pp = (
            sum(
                1 for s in self.ai.structures
                if s.type_id == UnitID.PHOTONCANNON
                and s.position.distance_to(home) < 25
            )
            + self.manager_mediator.get_building_counter[UnitID.PHOTONCANNON]
            # O286(o285b-g03 实证):驻点等钱的在途条目必须计入 —— 原口径漏
            # not_started tracker,派工下帧即「0 塔」再派,126s 三农民钉点
            # 干等(派→等→撤→再派循环),forge/首塔资金被钉穿,首波 236s
            # 到脸 0 塔。计入后单一驻点,O212 熔断正常收尾。
            + self.ai.not_started_but_in_building_tracker(UnitID.PHOTONCANNON)
        )
        # O168:核心科技缺失期间 presumed 链已在上游跳过 forge；这里再拦一次
        # 首塔/首叉，确保非 rush 运营局不把矿投进防御链。
        if self._early_core_missing:
            return
        # ② 首塔(forge 就绪才可拍;塔位供电水晶先行 —— 矿线无电是四局累犯)
        if not _cannons_pp:
            if not _forge_ready:
                return
            _anchor = None
            _mh = self.ai.mineral_field.closer_than(10, home)
            if _mh:
                _anchor = Point2((
                    sum(m.position.x for m in _mh) / len(_mh),
                    sum(m.position.y for m in _mh) / len(_mh),
                ))
            _pyl_near = (
                sum(
                    1 for s in self.ai.structures
                    if s.type_id == UnitID.PYLON and _anchor is not None
                    and s.position.distance_to(_anchor) < 9
                )
                + self.manager_mediator.get_building_counter[UnitID.PYLON]
            )
            if _anchor is not None and tower_zone_pylon_needed(0, 0, _pyl_near):
                # O147-①:首塔的供电水晶同豁免(它是首塔链路的一段)
                # O206:同 FORGE,仅 rush_confirmed 真触发时豁免。
                self._dispatch_structure(
                    UnitID.PYLON, home, closest_to=_anchor, needs_power=False,
                    critical=self._rush_confirmed,
                )
            # O147-①②:首塔豁免 —— forge 就绪同帧即派(驻点等钱),
            # 消灭 forge→首塔 43s 空档(o146b 局1:153→196)
            # O206:同 FORGE,仅 rush_confirmed 真触发时豁免。
            self._dispatch_structure(
                UnitID.PHOTONCANNON, home, closest_to=_anchor,
                critical=(
                    self._rush_confirmed
                    and critical_dispatch_exempt("PHOTONCANNON", _cannons_pp)
                ),
            )
            return
        # ③ GW1(首塔已拍才放行)
        if (
            not self.manager_mediator.get_own_structures_dict[UnitID.GATEWAY]
            and self.manager_mediator.get_building_counter[UnitID.GATEWAY] == 0
        ):
            # O147-①:GW1 豁免(首叉竞速链路的最后一段)
            # O206:同 FORGE,仅 rush_confirmed 真触发时豁免。
            self._dispatch_structure(
                UnitID.GATEWAY, home,
                critical=(
                    self._rush_confirmed
                    and critical_dispatch_exempt("GATEWAY", 0)
                ),
            )

    def _scout_lost(self) -> bool:
        """O99-②:早侦查探机是否失联 —— 三态:派发失败(tag=None)/ 单位死了 /
        活着但被摘了 SCOUTING role(idle 清扫扫回采矿)。O100-④ 起供
        _evaluate_scout_intel 早补派与 presumed 兜底两处共用。"""
        if not self._early_scout_done:
            return False
        if self._pivot_scout_tag is None:
            return True
        scout = self.ai.units.find_by_tag(self._pivot_scout_tag)
        return scout is None or scout.tag not in (
            self.manager_mediator.get_unit_role_dict[UnitRole.SCOUTING]
        )

    def _evaluate_scout_intel(self) -> None:
        """O9+E7 侦查情报 → 开局决策闭环(carrier 流,一局一次,t≈170s)。

        O9 三档(判据纯函数 production_plans.scout_verdict):
        (a) rush 征兆(早出兵建筑×2 / 早期多兵) → 提前置 _rush_active,
            复用现有响应包(出叉+铺塔+守家),比"敌兵压到 40 格"提前 ~1 分钟;
        (b) 对面开矿/科技开局 → 维持贪打法(什么都不做);
        (c) 没探到 → 保守按疑似 rush。
        E7(O16 侦查断链修复,时机判据纯函数 production_plans.scout_verdict_timing):
        verdict 不再只看「情报有无」一锤定音 —— 区分「还没走到」和「尽力未送达」:
        探机还在路上 → 宽限到 230s;探机死/被 O4 提前撤回且非 rush → 补派一次
        (仅一次,防无限续命送死;rush 中不补派——走进狗群是白送,且 rush 响应包
        已在跑);硬底线仍无情报 → 才按「尽力未送达」保守 rush(=旧 unknown 行为)。
        评估完把 SCOUTING 农民撤回采矿(情报已用,别留在敌家白送,同 O4 精神)。
        只挂 carrier:tempest/stalker 是已验证基线,行为一行不动。"""
        if self._scout_verdict_done or self._flow.name != "carrier":
            return
        if self._flow.pivot is None:
            return
        intel = bool(self.ai.enemy_structures)
        scout = (
            self.ai.units.find_by_tag(self._pivot_scout_tag)
            if self._pivot_scout_tag is not None
            else None
        )
        en_route = scout is not None and scout.tag in (
            self.manager_mediator.get_unit_role_dict[UnitRole.SCOUTING]
        )
        # O97(o96 局1/2/4 实证):事件驱动早评 —— 情报到手且探机已抵敌家附近
        # 即评估,不等 170 定时(局2 探机 t=144.6 已看到 SPAWNINGPOOL,干等
        # 170 纯浪费 25s+;首波 155-195 到脸,这 25-40s 是防链的全部差距)。
        # 只挂 transition 流派;无情报/未抵达 → 走 170/230 老路径,语义不变。
        _early_eval = (
            self._flow.transition is not None
            and intel
            and scout is not None
            and scout.distance_to(self.ai.focused_enemy_start()) < 15
        )
        if _early_eval:
            action = "evaluate"
        else:
            action = scout_verdict_timing(
                intel=intel,
                scout_en_route=en_route,
                redispatched=self._pivot_redispatched,
                rush_active=self._rush_active,
                now=self.ai.time,
                verdict_at=self._SCOUT_VERDICT_AT,
                hard_deadline=self._SCOUT_HARD_DEADLINE,
            )
        # O98-①/O99-②:探机失联(死/被摘 role/派发失败)时,不等 170 定时 ——
        # t≈105 无情报且探机失联 → 立即补派一次(只一次)。
        # O99-②(o98 局5 实证):O98 的「单位没了才算死」漏两种失联 ——
        # 派发失败(tag=None)与探机活着但被 idle 清扫摘了 SCOUTING role。
        if action == "pending" and scout_early_redispatch_needed(
            has_transition=self._flow.transition is not None,
            intel=intel,
            scout_lost=self._scout_lost(),  # O99-②:三态失联(死/被摘role/派发失败)
            redispatched=self._pivot_redispatched,
            now=self.ai.time,
        ):
            action = "redispatch"
            self.ai._events.append(
                {
                    "t": round(self.ai.time, 1),
                    "msg": "O99:探机失联(死亡/被扫回/派发失败),不等170补派一次",
                }
            )
        if action in ("pending", "wait"):
            return
        if action == "redispatch":
            enemy_main = self.ai.focused_enemy_start()
            if w := self.ai.mediator.select_worker(target_position=enemy_main):
                self.ai.mediator.assign_role(tag=w.tag, role=UnitRole.SCOUTING)
                w.move(enemy_main)
                self._pivot_scout_tag = w.tag
                self._pivot_scout_route = []  # O36:补派走单点老逻辑,不带路线
                self.ai._events.append(
                    {
                        "t": round(self.ai.time, 1),
                        "msg": "E7:侦查断链(未送达),补派探机一次(O16)",
                    }
                )
            self._pivot_redispatched = True  # 没可选农民也只试这一次
            return
        if action == "fallback":
            self.ai._events.append(
                {
                    "t": round(self.ai.time, 1),
                    "msg": "E7:侦查未送达(尽力),按保守rush(O16)",
                }
            )
        # evaluate / fallback → 一局一次 latch,按 O9 三档评估
        self._scout_verdict_done = True
        military = sum(
            1 for s in self.ai.enemy_structures if s.type_id in self._MILITARY_STRUCTS
        )
        # P1:作战单位口径(is_combat_type)——排除 OVERLORD/OVERSEER 等侦查/运输,
        # 否则 Zerg Macro 常规运营(pool+overlord 铺开)在 ~170s 必 ≥6 误判 rush
        army = sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and is_combat_type(u.type_id)
        )
        if _early_eval:
            # O97:早评用带基地数的判据 —— 敌单基地+出兵建筑(pool/兵营/gateway
            # ≥1)即 rush;敌已开二矿才 greedy(证据标准不降);回落老三档。
            verdict = early_scout_verdict(
                intel=intel,
                military_structs=military,
                early_army=army,
                enemy_townhalls=sum(
                    1 for s in self.ai.enemy_structures
                    if s.type_id in self._ENEMY_TOWNHALL_IDS
                ),
                # O100-③(o99 局2):hatch-first+pool 不开 greedy 绿灯
                enemy_is_zerg=(
                    getattr(getattr(self.ai, "enemy_race", None), "name", None)
                    == "Zerg"
                ),
            )
            self.ai._events.append(
                {
                    "t": round(self.ai.time, 1),
                    "msg": f"O97:情报到手即评(t<{self._SCOUT_VERDICT_AT:.0f}前),结论={verdict}",
                }
            )
        else:
            verdict = scout_verdict(
                intel=intel,
                military_structs=military,
                early_army=army,
            )
        self._verdict = verdict  # E8:存结论,combat 集结纪律(O17/O18)读它
        # E10:侦查判非 rush(greedy) → 策略 pivot 风暴主 C 压制(spawn 层分流,
        # 见 _pivot_tempest_mode);rush/unknown 不 pivot,维持现状逻辑
        if verdict == "greedy" and self._flow.name == "carrier":
            self.ai._events.append(
                {
                    "t": round(self.ai.time, 1),
                    "msg": "E10:侦查判非rush,风暴主C压制(成型后转航母)",
                }
            )
        if verdict != "greedy":
            self._rush_active = True
            self._rush_clear_since = None
        if verdict == "rush":
            # O107(o106 局1 实证):情报确认的 rush 也算「证实」—— 此前
            # _rush_confirmed 只在接触/rescout 设置,早评 rush 局(t≈81)里
            # O94-D 炮塔绕过/rush_defense_past_holding/O94-B 等全部
            # rush_confirmed 门要到接触(t≈154)才武装,白丢 70s 防链窗口
            self._rush_confirmed = True
            self._rush_confirmed_at = self.ai.time  # O150-②:接触时限台账
        for s in self.manager_mediator.get_units_from_role(role=UnitRole.SCOUTING):
            self.manager_mediator.assign_role(tag=s.tag, role=UnitRole.GATHERING)
            if self.ai.mineral_field:
                s.gather(self.ai.mineral_field.closest_to(s))

    # O71: 二次侦查时点(首判 t≈170 后,rush 兵营刚成型、敌兵未出门的窗口)
    # O133-①(o132 timing 1-4 尸检):250/330 看到兵时 timing 波已出门
    # (273-289 到脸)——提前到 195/260,波出门前读真实开局
    _RESCOUT_DISPATCH_AT: float = RESCOUT_DISPATCH_AT
    _RESCOUT_HARD_DEADLINE: float = RESCOUT_HARD_DEADLINE

    def _rescout(self) -> None:
        """O71(二次侦查):首判(t≈170)后 t=195 再派一个探机复核对面开局。

        首判时点 rush 兵营还没成型(3BB/3BG t=210-240 才完工,只能判 greedy),
        之后 6 分钟零情报 —— Terran Rush 两局实败(3→2→1→0 连锁、t=845 早夭)
        都是敌兵 t=500+ 到脸上才确认。二次侦查在敌兵出门前(O133-①:Zerg
        timing 波 ~250 成型、273-289 到脸,195 派出/260 硬截止)读
        真实开局:单基地+兵营类≥2+兵≥6(或兵≥10) → rush,提前启动
        防御包(叉+塔+守家,塔链=水晶25s+塔29s,早一秒都是命);对面开矿 → 维持贪。
        rush 旗标与 O9 同路(_update_rush_state 60s 无接触自动解除 —— 预警
        窗口本身就是价值:塔先落位,接触后响应包重新激活);rush_confirmed
        latch 置位后 _update_transition_state 下帧即进过渡形态(O133-①:
        防御链提前 60-80s 启动,不等接触)。
        判据纯函数 production_plans.rescout_verdict。只挂 carrier,一局一次。
        """
        if self._flow.name != "carrier" or self._flow.pivot is None:
            return
        if not self._scout_verdict_done:
            return  # 首判还没落地,不抢跑
        if self._rush_active:
            self._rescout_done = True  # rush 已确认,响应包在跑,不必复核
            return
        if not self._rescout_done:
            if self.ai.time < self._RESCOUT_DISPATCH_AT:
                return
            self._rescout_done = True
            enemy_main = self.ai.focused_enemy_start()
            if w := self.ai.mediator.select_worker(target_position=enemy_main):
                self.ai.mediator.assign_role(tag=w.tag, role=UnitRole.SCOUTING)
                w.move(enemy_main)
                self._rescout_tag = w.tag
                self.ai._events.append(
                    {"t": round(self.ai.time, 1), "msg": "O71:二次侦查派出(t=195,首判后复核)"}
                )
            return
        if self._rescout_verdict_done:
            return
        # 等探机到位(情报才是新鲜的);走不到/死了 → 硬底线按现有情报兜底
        scout = (
            self.ai.units.find_by_tag(self._rescout_tag)
            if self._rescout_tag is not None
            else None
        )
        arrived = (
            scout is not None
            and scout.distance_to(self.ai.focused_enemy_start()) < 15
        )
        if not arrived and self.ai.time < self._RESCOUT_HARD_DEADLINE:
            return
        self._rescout_verdict_done = True
        has_expo = (
            sum(
                1 for s in self.ai.enemy_structures
                if s.type_id in self._ENEMY_TOWNHALL_IDS
            )
            >= 2
        )
        military = sum(
            1 for s in self.ai.enemy_structures if s.type_id in self._MILITARY_STRUCTS
        )
        army = sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and is_combat_type(u.type_id)
        )
        verdict = rescout_verdict(has_expo, military, army)
        self.ai._events.append(
            {
                "t": round(self.ai.time, 1),
                "msg": f"O71:二次侦查结论={verdict}"
                f"(开矿={has_expo},兵营={military},兵={army})",
            }
        )
        # O279(A 方向):首波预警 —— 二判读到敌兵 ≥6(蟑螂群成型)且非 greedy
        # → 置 _wave_incoming:扩张钉点暂停(不往波路径送 Nexus 工人),
        # 死窗叉 cap 3→5(墙缝多两条命)。E9 接触(只剩 ~25s)不再等于
        # 首次知情 —— 预警把防御反应提前 40-60s。接触即解除(交还威胁响应)。
        if army >= 6 and verdict != "greedy" and not self._wave_incoming:
            self._wave_incoming = True
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": f"O279:首波预警(敌兵{army}成型中,扩张暂停+叉增产)",
            })
        if verdict == "rush":
            self._rush_active = True
            self._rush_clear_since = None
            self._rush_confirmed = True  # O92:O71 情报确认的 rush 也算证实(过渡形态进入用)
            self._rush_confirmed_at = self.ai.time  # O150-②
            # O133-①:rush_confirmed latch → _update_transition_state 下帧
            # 进过渡形态(防御链提前 60-80s,不等 273-289 接触)
            # O82(n5i 0-5 实证回滚):不再持有 rush 预警 —— O72 的 600s 持有
            # 让 rush_active 贯穿 t=330-600 整段舰队管线窗,科技/经济全方位
            # 扭曲(后续 O75/O80c/O81 打补丁也救不回):n5i 五局全灭,
            # 对照无持有的第一轮 2-3(o67/o70b/o71 胜局全是 60s 自动解除、
            # 快速恢复正常运营,t=750-900 舰队 8-12 艘到位)。回到接触式
            # 检测的 60s 自动解除(预警的价值=提前 60s 的塔/叉,不是锁运营)。
            # O80(n5 系实证):分矿不可守,早撤离保农民 —— rush 波到达窗口
            # (~160s) < 分矿从零建防所需 (~200s+:2 晶+4 塔的建造+走位),
            # 塔永远少 2-3 座。判 rush 即刻把分矿农民拉回主矿(主基坡口塔阵
            # 是六局实跑唯一稳定守住的点),农民不死在半路 = 恢复的本钱。
            main_pos = self.ai.start_location
            if self.ai.mineral_field:
                main_min = self.ai.mineral_field.closest_to(main_pos)
                for w in self.ai.workers:
                    if w.position.distance_to(main_pos) > 30:
                        w.gather(main_min)
        elif verdict != "unknown":
            self._verdict = verdict  # 新鲜情报覆盖首判的 unknown(E8 集结纪律读)
        # 撤回侦查农民(情报已用,别留在敌家白送,同 O9/O4 精神)
        for s in self.manager_mediator.get_units_from_role(role=UnitRole.SCOUTING):
            self.manager_mediator.assign_role(tag=s.tag, role=UnitRole.GATHERING)
            if self.ai.mineral_field:
                s.gather(self.ai.mineral_field.closest_to(s))

    @property
    def verdict(self) -> str | None:
        """O9/E7 侦查结论(greedy/rush/unknown;未评估=None)。
        E8:combat_manager 的 C3a 集结纪律按它调阈值(rally_min_for_verdict)。
        非 carrier 流恒 None(不评估)→ 集结行为不变。"""
        return self._verdict

    @property
    def rush_active(self) -> bool:
        """rush 检测是否成立。combat 守家、O4 侦查农民撤回都读它。"""
        return self._rush_active

    def _fleet_stall_watchdog(self, structures_dict: dict[UnitID, list[Unit]]) -> None:
        """O93-B3 + O110-①(o109 局2/局4 实证):舰队科技(SG/FB)建造停滞自救。

        O93 原版(o92 局2):FB 注册后建不出来没人管(落位静默 None / 工人
        死在路上 tracker 泄漏)。O110-① 修两个失效点(局4 实证:FB 买得起
        却 450s 没拍,watchdog 一次没火):
        a) 计时条件摘掉 can_afford —— 矿在造价上下振荡时计时器反复归零,
           「连续 45s 买得起」永不成立;停滞与否不该问银行(重试仍由
           can_afford 守,事件照发);
        b) 监视面扩到 SG(重建窗内)—— 局2 SG 落位停滞整局,O55 补电救
           不回(缺的不是电,是空闲 3x3 槽)。
        自救动作:① 清超龄 tracker 条目(O13 同构);② 主基换落位池
        (production=False,通用 3x3 槽)重试;③ 有其他就绪基地 → 那边
        也试一座(分矿槽位全新);④ 发事件(尸检可读)。45s 一轮,直到
        实体出现。过渡期 FB 故意冻结、非重建窗 SG 未到点 → 都不监视。
        """
        fb = UnitID.FLEETBEACON
        sg = UnitID.STARGATE
        fb_in_core = fb in self._flow.core_structure_ids()
        sg_ready = len([s for s in structures_dict[sg] if s.is_ready])
        _rebuild = self._flow.transition is not None and fleet_rebuild_window(
            self._fleet_transitioned, self._first_fleet_seen()
        )
        watch: list = []
        if fb_in_core and sg_ready and not self._transition_active:
            watch.append(fb)  # 过渡期 FB 是故意冻结,不算停滞
        if _rebuild and self._structure_present_or_pending(
            UnitID.CYBERNETICSCORE
        ):
            watch.append(sg)  # 重建窗内 SG 该在建/已有
        for sid in watch:
            if len(structures_dict[sid]) > 0:
                self._fleet_stall_since.pop(sid, None)
                continue
            since = self._fleet_stall_since.setdefault(sid, self.ai.time)
            stall_age = self.ai.time - since
            if not fb_stall_recovery_needed(True, 1, False, stall_age):
                continue
            self._fleet_stall_since[sid] = self.ai.time  # 每 45s 一轮
            self._fleet_stall_fired.add(sid)  # O115-③:停滞确认,科技预留解除
            # ① 清超龄 tracker 条目(O13 反卡死同构)
            purged = 0
            tracker = self.manager_mediator.get_building_tracker_dict
            for tag, info in list(tracker.items()):
                if info[TRACKER_ID] == sid and assimilator_attempt_stuck(
                    self.ai.time, info[TIME_ORDER_COMMENCED]
                ):
                    self.manager_mediator.get_building_counter[sid] -= 1
                    tracker.pop(tag)
                    purged += 1
            # ② 主基换落位池手动取证派工 + 贴槽水晶;③ 有其他就绪基地 → 分矿也试
            _retry = "no_money"
            if self.ai.can_afford(sid):
                _retry = self._dispatch_structure(
                    sid, self.ai.start_location, needs_power=True
                )
                if self.ai.can_afford(UnitID.PYLON):
                    # O113-①(o112 局2/局5 实证):贴最近的空闲 3x3 槽落水晶
                    # —— 簿记实锤「余20/总25,槽没占满,是带电槽为零」;
                    # 泛泛补水晶落点不覆盖空闲槽,自救空转两轮
                    _anchor = pick_slot_anchor(
                        self._free_3x3_slots_at(self.ai.start_location),
                        (self.ai.start_location.x, self.ai.start_location.y),
                    )
                    self.ai.register_behavior(
                        BuildStructure(
                            self.ai.start_location,
                            UnitID.PYLON,
                            closest_to=Point2(_anchor) if _anchor else None,
                        )
                    )
                for th in self.ai.townhalls.ready:
                    if th.position.distance_to(self.ai.start_location) > 5.0:
                        self.ai.register_behavior(
                            BuildStructure(th.position, sid, production=False)
                        )
                        break
            # O112-③/O114-①:细粒度簿记 —— 各基地 3x3 槽(带电空闲/空闲/总),
            # 下轮尸检据此区分「槽物理占满」vs「电力不覆盖」vs「预约泄漏」
            _slot_report = []
            for th in self.ai.townhalls.ready:
                _pw, _fr, _tot = self._slot_counts_at(
                    th.position, BuildingSize.THREE_BY_THREE
                )
                _slot_report.append(
                    (round(th.position.x), round(th.position.y), _pw, _fr, _tot)
                )
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": (
                    f"O110:{sid.name}建造停滞>45s,自救"
                    f"(清tracker×{purged}+主基派工={_retry}+贴槽水晶+分矿试建)"
                    f" 槽位(基x,y,带电余,空闲余,总)={_slot_report}"
                ),
            })

    def _expansion_predefense(self) -> None:
        """O149-②/O151-②:Nexus 在途分矿防御预派 —— 塔 29s vs Nexus 71s,
        Nexus 落地瞬间已有 2 塔(+1 电池)。

        断点 1(O149):F2 per-base 循环只迭代「已落地」townhalls,分矿从
        Nexus 落地到塔链就绪裸奔 30-60s。
        断点 2(O151,o150 局2 实证):调用点挂在 F2 闸内,而 F2 整体被
        _expand_holding 按住(Nexus 在途即 holding)→ 唯一需要它的窗口里
        是死代码;已移出 F2(carrier 门)。Nexus 未开工(在途/等钱)不预派
        —— 400 还是 Nexus 基金;开工(71s)后再派,塔 29s 照样先完工。
        实现:tracker 在途 Nexus 目标点 → 先供电水晶 → 2 塔 → 1 电池
        (cyber 未就绪时 tech 闸自然等待)。在途计数含本帧新派,天然防重派。
        """
        tracker = self.manager_mediator.get_building_tracker_dict
        for info in list(tracker.values()):
            if info[TRACKER_ID] != UnitID.NEXUS or not info.get(TARGET):
                continue
            pos = Point2(info[TARGET])
            if pos.distance_to(self.ai.start_location) < 5.0:
                continue  # 主基重建不是扩张
            # O205:Nexus 落成前即预铺 2 炮+1 电池,但 Nexus 基金优先:
            # 仅当 Nexus 已开工,或矿足够同时付 Nexus+防御(含 buffer)才预派。
            # 避免塔先动导致 Nexus 永远开不了工。
            _nexus_started = any(
                s.type_id == UnitID.NEXUS and s.position.distance_to(pos) < 3.0
                for s in self.ai.structures
            )
            if not natural_predefense_allowed(
                _nexus_started,
                self.ai.minerals,
                self.ai.calculate_cost(UnitID.NEXUS).minerals,
            ):
                continue
            _pyl = (
                sum(
                    1 for s in self.ai.structures
                    if s.type_id == UnitID.PYLON
                    and s.position.distance_to(pos) < 9
                )
                + self._pending_near(UnitID.PYLON, pos, 9.0)
            )
            if _pyl == 0:
                self._dispatch_structure(
                    UnitID.PYLON, pos, closest_to=pos, needs_power=False
                )
                continue
            _can = (
                sum(
                    1 for s in self.ai.structures
                    if s.type_id == UnitID.PHOTONCANNON
                    and s.position.distance_to(pos) < 12
                )
                + self._pending_near(UnitID.PHOTONCANNON, pos, 12.0)
            )
            if _can < 2:
                # O288-①:塔贴电池(电池幸存/塔战损重建时塔阵不散)
                _canchor = self._cannon_anchor_near_battery(pos, pos)
                self._dispatch_structure(
                    UnitID.PHOTONCANNON, pos, closest_to=_canchor
                )
                continue
            _bat = (
                sum(
                    1 for s in self.ai.structures
                    if s.type_id == UnitID.SHIELDBATTERY
                    and s.position.distance_to(pos) < 12
                )
                + self._pending_near(UnitID.SHIELDBATTERY, pos, 12.0)
            )
            if _bat < 1:
                self._dispatch_structure(
                    UnitID.SHIELDBATTERY, pos, closest_to=pos
                )

    def _cannon_anchor_near_battery(self, base_pos, fallback):
        """O288-①(司令观察):塔贴着电池建 —— 电池奶射程(6)内的塔阵才是
        完整防线,塔散在电池奶不到的地方是废铁。基地 15 格内有就绪电池
        且其 6 格内尚无就绪塔 → 下一座塔锚到电池位;否则回落原锚点。"""
        for s in self.ai.structures.ready:
            if s.type_id != UnitID.SHIELDBATTERY:
                continue
            if s.position.distance_to(base_pos) > 15.0:
                continue
            if any(
                c.type_id == UnitID.PHOTONCANNON
                and c.position.distance_to(s.position) < 6.0
                for c in self.ai.structures.ready
            ):
                continue
            return s.position
        return fallback

    def _natural_forward_defense(self) -> None:
        """O278(司令观察②):分矿口防御先于 Nexus —— 波(305-320s)路径穿分矿,
        后建的塔永远晚于波(o262 裸 Nexus 被白拆;36 局检索分矿先拔 76%)。
        ZT + t≥250 + 主基就绪塔 ≥2 + 分矿点 35 格无敌 + 尚无分矿基地
        → 提前在分矿口锚点铺 水晶→2 塔→电池;配合二矿窗 280s(O278-②),
        二矿落在已设防的口子上,波到脸撞上的是塔阵不是建筑期 Nexus。
        与 _expansion_predefense(Nexus 在途才预派)互补:本函数管 Nexus 之前。"""
        if self._opp_race != "zerg" or self._ai_build != "timing":
            return
        if not self.ai.townhalls:
            return  # 基地全灭后 min() 空序列(o278a-g03 实证崩溃)
        if self.ai.time < 250.0 or self._cannons_ready_peak < 2:
            return
        if any(
            th.position.distance_to(self.ai.start_location) > 5.0
            for th in self.ai.townhalls
        ):
            return  # 已有分矿(含在建已落) → 交 F2/_expansion_predefense
        if self._zt_enemy_near_natural() > 0:
            return  # 波在踩点,不送建筑材料
        free = [
            el
            for el in self.ai.expansion_locations_list
            if not self.ai.townhalls.closer_than(5.0, el)
        ]
        if not free:
            return
        nat = min(
            free, key=lambda el: min(el.distance_to(th) for th in self.ai.townhalls)
        )
        _enemy = self.ai.focused_enemy_start()
        _anchor = base_defense_anchor(
            False, (nat.x, nat.y), (_enemy.x, _enemy.y), forward=4.0
        )
        _at = Point2(_anchor) if _anchor is not None else nat
        if (
            sum(
                1
                for s in self.ai.structures
                if s.type_id == UnitID.PYLON and s.position.distance_to(nat) < 9
            )
            + self._pending_near(UnitID.PYLON, nat, 9.0)
        ) == 0:
            self._dispatch_structure(
                UnitID.PYLON, nat, closest_to=_at, needs_power=False
            )
            return
        if (
            sum(
                1
                for s in self.ai.structures
                if s.type_id == UnitID.PHOTONCANNON
                and s.position.distance_to(_at) < 12
            )
            + self._pending_near(UnitID.PHOTONCANNON, _at, 12.0)
        ) < 2:
            # O288-①:塔贴电池(电池奶射程内的塔阵才是完整防线)
            _cat = self._cannon_anchor_near_battery(nat, _at)
            self._dispatch_structure(UnitID.PHOTONCANNON, nat, closest_to=_cat)
            return
        if (
            sum(
                1
                for s in self.ai.structures
                if s.type_id == UnitID.SHIELDBATTERY
                and s.position.distance_to(_at) < 12
            )
            + self._pending_near(UnitID.SHIELDBATTERY, _at, 12.0)
        ) < 1:
            self._dispatch_structure(UnitID.SHIELDBATTERY, nat, closest_to=_at)

    # O94-C 农民协防 role(E6 撤离=CONTROL_GROUP_ONE、B4 停气=TWO,均无框架消费者)
    _ESCORT_ROLE = UnitRole.CONTROL_GROUP_THREE
    # O101-X(o100 局1/3/5 实证):协防触发半径 25→40 —— 3-6 狗绕坡口塔直进
    # 矿线,25 格触发时狗已在咬农民(农民 12→5-6);40 格 ≈ 与 rush 接触
    # 检测同圈,协防在狗进矿线前 5-8s 就位
    _ESCORT_TRIGGER_RADIUS: float = 40.0

    def _rush_worker_escort(self) -> None:
        """O94-C(o93 局1/局2、o92 局1 首波速败实证):炮塔/叉子就绪前的物理空窗
        拉农民协防。

        物理账:rush 确认(t≈130)时狗已过半场,炮塔链(forge 33s+塔 29s+派工)
        最快 t≈205 出首座,首波 t≈195-201 到脸 —— 差 10-20s 只能用人顶。
        判据纯函数 rush_worker_escort_needed:敌地面进主基 25 格 ≥3 且主基
        无就绪炮塔且叉子 <2 → 在岗;炮塔就绪/叉子够/敌退 → 自动归队
        (自校正,无 latch)。只挂配了 transition 的流派(carrier)。
        实现同 E6/B4 停气:role 一切换脱离 Mining;建造中/司令接管的农民不动;
        在岗农民每帧补 attack 保持不闲置(_handle_idle_workers 不豁免本 role)。
        O96(o95 局2/局5 实证)修正:数量随威胁伸缩(escort_worker_count)。
        O104-①(o103 局1/3/4/5 实证):「攻击最近敌」证伪,改双姿态 ——
        有就绪塔 → 塔下作战(attack 塔位);无塔 → mineral-walk 穿矿拖延
        (不接敌,甩包围;其余农民照采不接管)。归队门槛 1 塔→2 塔
        (1 塔就放人回矿线 = 狗继续咬采矿农民)。"""
        if self._flow.transition is None:
            return
        home = self.ai.start_location
        enemies_near = [
            u for u in self.ai.enemy_units
            if not u.is_structure and not u.is_flying and is_combat_type(u.type_id)
            and u.position.distance_to(home) < self._ESCORT_TRIGGER_RADIUS
        ]
        enemy_near = len(enemies_near)
        cannons_ready = sum(
            1 for s in self.ai.structures.ready
            if s.type_id == UnitID.PHOTONCANNON
            and s.position.distance_to(home) < 25
        )
        zealots = self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.ZEALOT)
        # O299-②(o298b game_03 实证):164s 1-2 狗进矿线时 min_enemy=3 不触发,
        # 无人应答 → 狗群 234s 滚到 4+ 才协防,249s 农民 24→7 崩盘。
        # ZT 首波窗触发收到 2(协防池 O130 采矿底线不变,过度拉人自有 cap)。
        need = rush_worker_escort_needed(
            enemy_near, cannons_ready, zealots,
            min_enemy=(
                2
                if (self._opp_race == "zerg" and self._ai_build == "timing")
                else 3
            ),
            # O309-②:白送上界(同 O306-③口径),超线不拉,留经济火种
            hopeless=worker_last_stand_hopeless(enemy_near, cannons_ready),
        )
        # O136-③:坡口墙模式未封口 + 敌地面近家 ≥2 → 协防去墙缝肉身填缝
        # (墙建筑完工前的空窗 = 速骰局死刑窗;封口/敌退自动归队)
        _wall_plug = wall_escort_needed(
            self._wall_gap_point is not None, self._wall_sealed, enemy_near
        )
        if not need and not _wall_plug:
            if self._escort_tags:
                alive = {w.tag: w for w in self.ai.workers}
                for tag in list(self._escort_tags):
                    self.manager_mediator.assign_role(tag=tag, role=UnitRole.GATHERING)
                    w = alive.get(tag)
                    if w is not None and self.ai.mineral_field:
                        w.gather(self.ai.mineral_field.closest_to(w))
                    self._escort_tags.discard(tag)
                self._escort_targets.clear()  # O104-①:mineral-walk 簿记随归队清
                if self._escort_active:
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": "O94:炮塔/叉子就位或敌退,协防农民回采",
                    })
                self._escort_active = False
            return
        # 需要在岗:补足 escort_worker_count(只拉 GATHERING;建造链/司令接管的不动)
        # O130-③/O166: 保留采矿底线动态 = max(4, 农民//2)，cap 压到 6。
        # 避免 Power 中后期反复扰家时把经济拉崩(局1 从 21 农崩到 8 农)。
        _keep_mining = max(4, len(self.ai.workers) // 2)
        want = escort_pull_cap(
            enemy_near, len(self.ai.workers),
            keep_mining=_keep_mining, cap=6,
        )
        alive = {w.tag for w in self.ai.workers}
        self._escort_tags &= alive
        gathering = self.manager_mediator.get_unit_role_dict.get(
            UnitRole.GATHERING, set()
        )
        # O105-②(o104 局3 实证):rush 期停气(B4③-a,6 个气矿农民摘出
        # GATHERING)+建造链+侦查把候选池抽干 → 协防只拉出 1 人(敌12地面
        # 进主基)。停气农民本就已离矿,是天然协防候选;归队回 GATHERING 后
        # Mining 按原记账自动派回气矿,台账无冲突。
        gathering = gathering | self.manager_mediator.get_unit_role_dict.get(
            self._GAS_STOP_ROLE, set()
        )
        player_ctrl = getattr(self.ai, "_player_ctrl", {})
        tracker = self.manager_mediator.get_building_tracker_dict
        for w in self.ai.workers:
            if len(self._escort_tags) >= want:
                break
            if (
                w.tag in gathering
                and w.tag not in player_ctrl
                and w.tag not in tracker
            ):
                self.manager_mediator.assign_role(tag=w.tag, role=self._ESCORT_ROLE)
                self._escort_tags.add(w.tag)
        if not self._escort_tags:
            return
        # O136-③:堵缝优先于塔下/穿矿 —— 墙未封口时协防 attack 到缝点,
        # 肉身物理封堵(接触即战;封口后判据翻假,下帧归队回采)
        if _wall_plug and self._wall_gap_point is not None:
            for w in self.ai.workers:
                if w.tag in self._escort_tags:
                    w.attack(self._wall_gap_point)
            return
        # O104-①(o103 局1/3/4/5 实证):「攻击最近敌」范式证伪 —— 协防 ×5
        # 主动 charge,赢战斗也输经济(农民 13→4)。改双姿态:
        # 有就绪塔 → 塔下作战(attack 塔位,敌进塔程被塔+农民双打);
        # 无塔 → mineral-walk(穿矿往返甩包围,不接敌,纯拖时间等塔/叉)。
        stance = escort_stance(
            cannons_ready,
            # O127-③:有塔在建 → 协防回撤守建造点(29s 建造窗=新的死亡窗)
            cannon_pending=bool(
                [
                    s
                    for s in self.ai.structures
                    if s.type_id == UnitID.PHOTONCANNON and not s.is_ready
                ]
            ),
        )
        if stance == "tower":
            self._escort_targets.clear()
            _cannon = min(
                (
                    s for s in self.ai.structures  # O127-③:含在建(守建造点)
                    if s.type_id == UnitID.PHOTONCANNON
                ),
                key=lambda s: s.position.distance_to(home),
                default=None,
            )
            if _cannon is not None:
                point = _cannon.position
            elif enemies_near:
                point = min(
                    enemies_near, key=lambda u: u.position.distance_to(home)
                ).position
            else:
                ramp = self.ai.main_base_ramp
                point = Point2(defensive_rally_point(
                    (ramp.top_center.x, ramp.top_center.y),
                    (ramp.bottom_center.x, ramp.bottom_center.y),
                ))
            for w in self.ai.workers:
                if w.tag in self._escort_tags:
                    w.attack(point)
        else:
            patches = self.ai.mineral_field.closer_than(11, home)
            for w in self.ai.workers:
                if w.tag not in self._escort_tags:
                    continue
                if not patches:
                    # 矿线取不到 → 回退坡口蹲点(不动比送强)
                    ramp = self.ai.main_base_ramp
                    w.move(Point2(defensive_rally_point(
                        (ramp.top_center.x, ramp.top_center.y),
                        (ramp.bottom_center.x, ramp.bottom_center.y),
                    )))
                    continue
                tgt = self._escort_targets.get(w.tag)
                if tgt is None or w.distance_to(tgt) < 2.5:
                    # O118-③(o117 局1 实证):目标 = 离最近威胁最远的矿簇
                    # (穿矿背狗侧走位);旧版「离自己最远」会径直穿狗群,
                    # 协防 30s 死 10
                    _threat = min(
                        enemies_near,
                        key=lambda u: u.position.distance_to(w.position),
                    )
                    _p = pick_walk_patch(
                        [(m.position.x, m.position.y) for m in patches],
                        (_threat.position.x, _threat.position.y),
                    )
                    if _p is None:
                        continue
                    tgt = Point2(_p)
                    self._escort_targets[w.tag] = tgt
                    w.move(tgt)
        if not self._escort_active:
            self._escort_active = True
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": (
                    f"O94:首波农民协防×{len(self._escort_tags)}"
                    f"(炮塔未就绪,顶窗口;敌{enemy_near}地面进主基)"
                ),
            })

    def _rush_gateway_boost(self) -> None:
        """E3d: rush 期间敌可见兵力超过在场叉子数时追加 gateway(封顶 2)。
        单 gateway ~28s 一叉是实证瓶颈——叉子永远分批到场被围殴(在场恒 1)。"""
        pv = self._flow.pivot
        # P1:作战单位口径(is_combat_type),排除侦查/运输(见 _evaluate_scout_intel)
        enemy_army = sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and is_combat_type(u.type_id)
        )
        have = (
            len(self.manager_mediator.get_own_structures_dict[UnitID.GATEWAY])
            + len(self.manager_mediator.get_own_structures_dict[UnitID.WARPGATE])
            + self.manager_mediator.get_building_counter[UnitID.GATEWAY]
        )
        # O94-B:forge 实体落地前缓建追加兵营 —— 第二兵营的叉子 t≈215 才出场,
        # 赶不上首波(t≈200);炮塔链(forge 33s+塔 29s)是唯一能赶上的防线,
        # 兵营的 150 矿先给 forge(o93 局1:兵营抢钱,forge 拖 30s,0 炮塔速败)。
        # O102-①(o101 局3/4/5 实证):只拦 GW2/GW3 —— GW1 与 forge 并行双开
        # (各 150,t≈110 前),GW1 t≈110 完工 → 首叉 ~140-155 正好进首波守窗;
        # 塔先排序管 GW1 的局(o101)首叉 195+,完美错过
        if rush_defers_second_gateway(
            self._rush_confirmed,
            self._flow.transition is not None,
            bool(self.manager_mediator.get_own_structures_dict[UnitID.FORGE]),
            have,
        ):
            return
        # O98-③b(o97 局2 实证):过渡期兵营直补到 cap —— 不等敌兵对比(首波后
        # 敌可见=0 判据停)、不等 rush 解除(extra_production 被 rush 分支挡)。
        # 局2 GW2 拖到 t=301,二波(30 supply)只有 8 叉;产能=过渡形态命根。
        # O99-①(o98 局3/4 实证):但必须先有 2 塔(已有+在建)——③b 的直补把
        # 塔链饿死(局3:兵营×3 吃光矿,300s 零塔)。资金顺序:塔 2 → 兵营 cap。
        # O126-①(o125 局1 实证):GW2+ 必须等首叉在产/出场 —— 局1 GW2 在
        # GW1 完工前 10s 抢走 150,首叉 163→178
        tr = self._flow.transition
        # O208:Zerg Timing 混编地面需要 2 兵营产能；Rush 保持 flows.yml 的 1。
        _timing_gateway_cap = tr.gateway_cap
        if (
            self._transition_active
            and self._opp_race == "zerg"
            and self._ai_build == "timing"
        ):
            _timing_gateway_cap = 2
        if (
            tr is not None
            and not self._sprint_active  # O129:冲刺期兵营链由手动防链独管
            and transition_needs_gateways(
                self._transition_active, have, _timing_gateway_cap
            )
            and not gateway_chain_after_first_zealot(
                have,
                self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.ZEALOT)
                > 0
                or cy_unit_pending(self.ai, UnitID.ZEALOT),
            )
            # O128-①(数据终裁顺序):forge 未拍 → GW1 也让位(③b 不过
            # forge 顺序闸,o127 局2:GW1 在 t=122 抢走 forge 的 150)
            and not forge_before_first_gateway(
                self._defense_urgent,
                self._structure_present_or_pending(UnitID.FORGE),
                # O308-①:Zerg Timing 豁免(GW1 先拍,首叉 ~180s)
                self._opp_race == "zerg" and self._ai_build == "timing",
            )
            # O112-①:GW3+ 在主基 3x3 余量 <2 时让位科技槽(给 cyber/SG/FB
            # 留位)—— rush 局主基铺满塔是必然,不能等舰队期才发现没地方放
            # O133-②:timing 冲刺期不让位(GW3 的叉 > 科技槽,波 273-289 到脸)
            and not (
                gateway_yields_tech_slots(have, self._main_free_3x3())
                and not self._timing_sprint
            )
            and transition_gateway_allowed(
                have,
                # O132-③:峰值口径 —— 塔被拆不再反锁 GW2+(o131 timing 局1)
                self._cannons_peak,
            )
            and self.ai.can_afford(UnitID.GATEWAY)
            # O197:星门已就绪但 FleetBeacon 还没影时,不再追加兵营,
            # 把 150 矿留给 FB(300/200),避免 transition 期兵营链把舰队转型资金永远吃光。
            and not self._fb_ready_to_build()
        ):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, UnitID.GATEWAY)
            )
            return
        # O197:同 transition 块,FB 已可建时优先保 FB 资金,不再应急追加 gateway。
        _rush_gw_needed = (
            rush_needs_gateway(
                rush_active=self._rush_active,
                rush_zealots=pv.rush_zealots if pv else 0,
                enemy_army=enemy_army,
                zealots=self.manager_mediator.get_own_unit_count(
                    unit_type_id=UnitID.ZEALOT
                ),
                gateways_have=have,
            )
            and self.ai.can_afford(UnitID.GATEWAY)
            and not self._fb_ready_to_build()
        )
        if _rush_gw_needed:
            # O107(o106 局1 实证):E3d 老路在过渡期也走塔先闸 —— 局1 GW1
            # 就绪瞬间此路不过闸抢建 GW2(150),首叉 156→182;③b 直补块
            # 有闸、此路没有,补同一只(transition_gateway_allowed 对
            # GW1 天然放行,非过渡期此判据不生效)
            if self._transition_active and not transition_gateway_allowed(
                have,
                # O132-③:峰值口径(同 ③b)
                self._cannons_peak,
            ):
                return
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, UnitID.GATEWAY)
            )

    def _update_rush_state(self) -> None:
        """pivot·rush 检测与解除。判据(2026-07 初版):
        ≥2 敌作战单位压到家 40 格内(沿用 F2) 或 4 分钟前敌可见兵力 ≥6(兵力异常=快攻)。
        成立后:连出叉子顶(见 _effective_spawn) + F2 铺塔 + 全军守家(combat 读 _rush_active)
        + B4 防守三角(折跃落点 _rush_spawn_target、应激经济 _rush_economy_response);
        40 格内无敌 60 秒后自动解除,恢复正常生产/进攻。"""
        if self._flow.pivot is None:
            return
        home = self.ai.start_location
        # P1:作战单位口径(is_combat_type)——排除 OVERLORD/OVERSEER 侦查/运输;
        # 旧口径「非工人即算兵」让 Zerg Macro 的 overlord 铺开每局误触发
        # early_swarm(E10-macro 五局 169s 全误中,O4 误撤侦查农民)。
        # O207:Zerg Timing 是中局波次而非 all-in，降低 rush latch 敏感度并
        # 缩短自动解除时间，避免波间隙被 60s 锁死导致开不出二矿。
        _near_threshold = 2
        _clear_timeout = 60.0
        if self._opp_race == "zerg" and self._ai_build == "timing":
            _near_threshold = 3
            _clear_timeout = 25.0
        near = sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and is_combat_type(u.type_id)
            and u.position.distance_to(home) < 40
        )
        early_swarm = (
            self.ai.time < 240
            and sum(1 for u in self.ai.enemy_units
                    if not u.is_structure and is_combat_type(u.type_id)) >= 6
        )
        # O154-②:greedy 判决(侦查确认运营)后接触不置 rush latch ——
        # 小股骚扰/中期推进波由 E9 威胁包处理(塔+守家,不动科技链);
        # greedy 局置 latch = 过渡误入 + 农民/科技被接触语义反复掐(o153 局1)
        if (near >= _near_threshold or early_swarm) and rush_contact_arms(self._verdict):
            # O205:硬解 rush 后 60s 死区 —— 期间不因敌兵重新进入 full rush-lock,
            # 让经济/扩张/FB 不再被反复掐死;E9 threat 仍正常响应塔/兵。
            if rush_deadzone_active(
                self._rush_hard_cleared_at, self.ai.time, deadzone=60.0
            ):
                return
            self._rush_active = True
            self._rush_clear_since = None
            self._rush_hold_until = None  # O72:接触了,预警持有使命完成,走正常解除
            self._rush_confirmed = True  # O92:接触/早群证实 rush(过渡形态进入判据用)
            if self._rush_confirmed_at is None:
                self._rush_confirmed_at = self.ai.time  # O150-②:首次证实时刻
            return
        if self._rush_active:
            # O203:舰队已转型成功且防御达标 → 强制解除 rush 经济锁,
            # 恢复 probe 生产、扩张、fleet spawn。若敌后续压家,_update_rush_state
            # 下帧会重新置位,不影响守家响应。
            if self._fleet_transitioned and self._defense_score() >= 15.0:
                self._rush_active = False
                self._rush_clear_since = None
                self.ai._events.append({
                    "t": round(self.ai.time, 1),
                    "msg": (
                        "O203:舰队成型且防御评分达标,解除rush恢复经济"
                        f"(评分{self._defense_score():.0f})"
                    ),
                })
                return
            # O204:舰队成型后再触发 rush 往往解不开,经济二次锁死。
            # 硬解冻:time>480s、已转舰队、SG+FB 就绪 → 强制解除,只执行一次。
            # 若敌真压家,上面接触检测会下帧重新置位,不影响守家。
            if (
                not self._rush_hard_cleared
                and self._fleet_transitioned
                and self.ai.time > 480.0
                and self._structure_present_or_pending(UnitID.STARGATE)
                and self._structure_present_or_pending(UnitID.FLEETBEACON)
            ):
                self._rush_active = False
                self._rush_clear_since = None
                self._rush_hard_cleared = True
                self._rush_hard_cleared_at = self.ai.time
                self.ai._events.append({
                    "t": round(self.ai.time, 1),
                    "msg": "O204:舰队成型后硬解rush锁,恢复运营",
                })
                return
            # O72(n5 三连败实证):O71 情报确认的 rush 预警,敌未出门前
            # (持有上限内)不做 60s 自动解除 —— 否则 t=330 判 rush、t≈390
            # 旗标过期,防御包只建一半(接触时 2-3 塔被 15-18 枪兵淹没)。
            if (
                self._rush_hold_until is not None
                and self.ai.time < self._rush_hold_until
            ):
                return
            if self._rush_clear_since is None:
                self._rush_clear_since = self.ai.time
            elif self.ai.time - self._rush_clear_since > _clear_timeout:
                self._rush_active = False
                self._rush_clear_since = None

    def _update_threat_state(self) -> None:
        """E9 中局威胁检测与解除(只挂 carrier,判据纯函数
        production_plans.threat_response_active)。

        macro-fix1 五局实证:威胁响应原来只覆盖早期 rush,Macro AI 的中局一波
        (t≈520-560 敌 15-25 作战单位到脸)bot 毫无反应——继续开矿/憋航母/
        塔被限流压着,常备军 ≈6 叉对敌 20+,基地连丢。激活效果(update 各处):
        塔目标=ec.max(覆盖 cannon_target_capped 限流)、save_up 不截地面防御
        兵种、暂停开新矿。rush 六连动优先级更高(threat 与 rush 同时激活时
        各效果按 rush 走,不叠加)。状态每帧更新,激活/解除各记一次事件。"""
        if self._flow.name != "carrier":
            return
        own = self.ai.supply_used - self.ai.supply_workers
        enemy = self._visible_enemy_army_supply()
        was = self._threat_active
        self._threat_active = threat_response_active(enemy, own, was)
        if self._threat_active == was:
            return
        msg = (
            f"E9:敌压境威胁响应(敌可见{enemy:.0f}supply vs 我{own:.0f})"
            if self._threat_active
            else "E9:威胁解除,恢复运营"
        )
        self.ai._events.append({"t": round(self.ai.time, 1), "msg": msg})

    def _update_transition_state(self) -> None:
        """O92 过渡形态状态机(只挂配了 transition 的流派,现仅 carrier)。

        进入(latch 一次):transition_should_enter —— verdict == "rush"(O9 首判
        情报确认)或 rush 已证实(_rush_confirmed:接触式检测/O71 二次侦查)。
        unknown(侦查尽力未送达)不进入 —— 它的 60s 响应包照跑,但冻星门的大
        承诺不押未确认情报;greedy/未接触 → 永远不进(Macro/Air 对阵零变化)。
        激活期间(update 各处接入):spawn 换 ground_spawn(_effective_spawn)、
        科技链冻结 STARGATE/FLEETBEACON(_build_flow_structures)、追加产能改
        GATEWAY ≤gateway_cap(_build_extra_production/_spend_bank)、save_up/
        pre_fleet 随配方早退自然挂起。塔防/开矿/rush 六连动/E6/E9 不动。
        退出(latch 不回头):fleet_transition_ready —— time ≥ fleet_at 且家
        (start_location)40 格内无敌作战单位持续 30s;到点威胁未清 → 保持过渡
        直到清(防"转舰队瞬间被波次打死")。退出后科技链/配比/憋气自动恢复
        (所有接入点都吃 _transition_active,旗标一落全恢复)。"""
        tr = self._flow.transition
        if tr is None or self._fleet_transitioned:
            return
        if not self._transition_active:
            # O150-①②:单程化(fleet_transitioned 判据层硬关断)+ 接触时限
            # (>360s 的接触是推进波不是 rush,verdict=rush 情报确认不受限)
            # O249b(o249-lane game_01 实证):O248 只去掉开局强制,接触/verdict
            # 仍会在 ~300s 触发 transition → 直爬舰队路线被 ground_spawn 截胡;
            # Zerg Timing 禁止进入 transition(Rush 保留)。
            if self._opp_race == "zerg" and self._ai_build == "timing":
                return
            if transition_should_enter(
                self._verdict,
                self._rush_confirmed,
                fleet_transitioned=self._fleet_transitioned,
                rush_confirmed_at=self._rush_confirmed_at,
            ):
                self._transition_active = True
                self._transition_clear_since = None
                self.ai._events.append({
                    "t": round(self.ai.time, 1),
                    "msg": (
                        f"O92:过渡形态(叉/追猎),推迟星门"
                        f"(verdict={self._verdict},接触证实={self._rush_confirmed})"
                    ),
                })
            return
        home = self.ai.start_location
        enemy_near = sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and is_combat_type(u.type_id)
            and u.position.distance_to(home) < 40
        )
        if enemy_near:
            self._transition_clear_since = None
            if enemy_near >= 3:
                self._saw_wave = True  # O122-②:首波见闻(扩张相位判据用)
        elif self._transition_clear_since is None:
            self._transition_clear_since = self.ai.time
        # O185:Zerg Rush 把舰队退出点从 320 提到 500,让地面多守/多推。
        # O192-②(o191-vh-zerg-timing game_01 实证):Timing 局拖到 500 才转舰队,
        # 舰队成型过晚被滚雪球;仅 Rush 保持 500,Timing 走 flow.fleet_at(320)。
        # O193-③(o192-vh-zerg-rush game_01 实证):500 仍太晚,单矿地面被滚雪球,
        # 提前到 450 给舰队更多成型窗口,strong_exit 评分门兜底防早退。
        # O201(o200-vh-zerg-rush 3-7 实证):450 仍太晚,Lane1 失败局 transition 期
        # 纯地面硬顶 7-8 分钟,单矿经济被滚雪球;再降到 360,让 fleet 更早成型。
        # O204(o203-vh-zerg-rush 1-9 实证):360 仍导致 Carrier 首次出现 972-1146s,
        # 再降到 280,并同步放宽 strong_exit/exit_allowed 门,让 fleet 在 6-7 分钟成型。
        # O208/O209:Zerg Timing 强制进 transition。O208 用 380s 偏保守，
        # Paladino 多局 FleetBeacon 拖到 550s+ 甚至不建，舰队成型过晚被滚雪球。
        # O209 把 timing fleet_at 降到 340s（更接近 flows.yml 的 320），并同步
        # 放宽退出阈值，让 transition 在 6 分钟左右退出、FleetBeacon 尽早落成。
        # O216:flows.yml fleet_at 已降到 280,Timing 同步降到 280,避免 ground_spawn
        # 把资源永远锁在地面部队里,加速舰队转型。
        _is_zerg_rush = self._opp_race == "zerg" and self._ai_build == "rush"
        _is_zerg_timing = self._opp_race == "zerg" and self._ai_build == "timing"
        _fleet_at = tr.fleet_at
        if _is_zerg_rush or _is_zerg_timing:
            _fleet_at = max(_fleet_at, 280.0)
        # O100-②(o99 局1/局5 实证):完全清净 30s 对持续骚扰局永假 —— 加
        # 放宽通道:t≥fleet_at 且防御达标(地面×2+就绪塔×3+就绪电池×2 ≥25)
        # 且领先敌可见 supply 10+ → 也退;敌波到脸(28-45 supply)不放行,
        # 防「带波转舰队瞬间被打死」。时间闸保留(不到 fleet_at 两路都不退)。
        # O209:Timing 阈值进一步放宽，匹配 340s fleet_at。
        if _is_zerg_rush:
            _min_defense, _clear_needed = 20.0, 20.0
        elif _is_zerg_timing:
            _min_defense, _clear_needed = 18.0, 20.0
        else:
            _min_defense, _clear_needed = 25.0, 30.0
        _defense_score = self._defense_score()
        _strong_exit = (
            self.ai.time >= _fleet_at
            and fleet_transition_strong_exit(
                _defense_score,
                # O102-③:敌情口径从全图可见 supply 改家 40 格(is_combat_type
                # 口径,顺带排除 overlord —— _visible_enemy_army_supply 把
                # 王虫也算 supply,远图残兵/王虫不该挡退出门)
                sum(
                    self.ai.calculate_supply_cost(u.type_id)
                    for u in self.ai.enemy_units
                    if not u.is_structure and is_combat_type(u.type_id)
                    and u.position.distance_to(home) < 40
                ),
                # O110-②:清净深度 ≥30s —— strong 通道只落在波间隙深位
                # (o108 局2/局4:score 一够就放 = 波前 40s 退出,撞上 440 波)
                # O204:Zerg Rush 骚扰密度高,30s 太奢侈,降到 20s。
                clear_for=(
                    self.ai.time - self._transition_clear_since
                    if self._transition_clear_since is not None
                    else 0.0
                ),
                min_defense=_min_defense,
                clear_needed=_clear_needed,
            )
        )
        # O119-①③(o118 局5 实证):退出加经济+地面前提 —— 单矿 12-14 农
        # 退出 = 死亡判决(440+ 波次前产出物理不够)
        # O132-①(o131 系列尸检):经济门三选一(bases≥2 / 地面≥20 / 防御
        # 评分≥35),死线 600→540 —— bases≥2 门上线后 0 胜(单矿局永远
        # 等不到二矿);地面 ≥14 supply(≈7 叉)与 SG 前提不变
        # O143(o142 双系列 0-10):评分 ≥25 直接放行 —— 叠加门在评分门上
        # 是死锁放大器(o129 局5 评分 41 清净 60s+ 不退被一波清零)
        # O201(o200-vh-zerg-rush 3-7 实证):Rush 局地面门槛 14 supply 太高,
        # 单矿经济养不起,舰队永远解不了冻;降到 10 supply,deadline 延到 480s。
        # O204(o203 实证):Rush 局地面门槛 10 仍太高,评分门 25 偏严;
        # 降到 6 supply,评分门降到 20,让 transition 更早退出转舰队。
        # O209:Timing 阈值进一步放宽，匹配 340s fleet_at，避免 ground_spawn
        # 把资源永远锁在地面部队里。
        if _is_zerg_rush:
            _exit_min_ground, _exit_deadline, _exit_strong_score = 6.0, 480.0, 20.0
        elif _is_zerg_timing:
            _exit_min_ground, _exit_deadline, _exit_strong_score = 8.0, 480.0, 18.0
        else:
            _exit_min_ground, _exit_deadline, _exit_strong_score = 14.0, 540.0, 25.0
        _exit_allowed = fleet_exit_allowed(
            bases=self.ai.townhalls.amount,
            ground_supply=2.0
            * (
                self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.ZEALOT)
                + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.STALKER)
            ),
            now=self.ai.time,
            defense_score=_defense_score,
            # O121-③:SG 未拍就退出 = 空窗 +60s(配套过渡期达标解冻)
            # O140-①:评分 ≥35 豁免 SG 前提 —— o139 局2 死锁:SG 解冻
            # (评分≥25)虽已亮但单矿矿恒 25-75,SG 150 永攒不出;「SG 已拍
            # 才准退、SG 要退了才有钱拍」循环,543 波穿防死 575
            sg_present_or_pending=self._structure_present_or_pending(
                UnitID.STARGATE
            ),
            min_ground=_exit_min_ground,
            deadline=_exit_deadline,
            strong_exit_score=_exit_strong_score,
        )
        if _exit_allowed and (
            fleet_transition_ready(
                self.ai.time, _fleet_at, enemy_near, self._transition_clear_since
            )
            or _strong_exit
        ):
            self._transition_active = False
            self._fleet_transitioned = True
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": (
                    "O92:威胁清除,转舰队(解冻星门/舰队航标)"
                    if not _strong_exit
                    else f"O100:防御达标转舰队(评分{_defense_score:.0f},解冻星门/舰队航标)"
                ),
            })

    # ────────────────────── B4 防守三角(2026-07,来源:sharpy/QueenBot) ──────────────────────
    def _rush_spawn_target(self) -> Point2:
        """B4 rush 折跃落点(取代 E3b 的"切回主基中心")。⚠️ 未验证(未跑局)。

        ②(sharpy 防御性折跃):威胁位置取各基地 25 格内敌地面单位计数(与
        _update_rush_state 的威胁口径同源),最多的分矿 = 被攻击的基地,折跃过去;
        ①(sharpy PlanHeatDefender):主基承压/无明确威胁 → 主坡口顶端下 4 格的
        防守集结点(而非基地中心) —— 集结在坡后高地,响应兵落地即占坡口。
        主坡口取 ai.main_base_ramp(ares/python-sc2 现成属性,无需 mediator)。"""
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        threats = []
        for th in self.ai.townhalls:
            n = sum(
                1 for u in self.ai.enemy_units
                if not u.is_structure and u.type_id not in workers
                and u.position.distance_to(th) < 25
            )
            threats.append((th.position.x, th.position.y, n))
        main = self.ai.start_location
        base = rush_defend_base(threats, (main.x, main.y))
        if base is not None:
            return Point2(base)  # ② 分矿承压 → 折跃被攻击的分矿
        ramp = self.ai.main_base_ramp  # ① 主基 → 坡口顶端下 4 格
        return Point2(defensive_rally_point(
            (ramp.top_center.x, ramp.top_center.y),
            (ramp.bottom_center.x, ramp.bottom_center.y),
        ))

    # B4③-a 停气用的兜底 role(同 E6 的 CONTROL_GROUP_ONE 套路:vendored ares 无
    # 消费者,Mining 只指挥 GATHERING,role 一切换自然脱离气矿指派)。
    _GAS_STOP_ROLE = UnitRole.CONTROL_GROUP_TWO

    def _rush_economy_response(self) -> None:
        """B4③(QueenBot rush 应激清单)经济侧联动:
        a) 停气(见 _rush_gas_stop):rush 期间气矿农民拉去采矿;
        b) 取消在建非关键科技建筑换现金(极保守白名单,见 rush_cancellable_structure)。
        扩张暂停走判据层(should_expand_dynamic / _auto_expand 的 rush 否决,B7③)。
        rush 未激活时停气台账自动清(农民归 GATHERING 回气),取消建筑自然不触发。"""
        self._rush_gas_stop()
        if not self._rush_active:
            return
        for s in self.ai.structures:
            if rush_cancellable_structure(True, s.type_id.name, s.is_ready):
                # ⚠️ 未验证:取消指令(AbilityId.CANCEL)与返款比例未跑局确认
                s(AbilityId.CANCEL)

    def _rush_gas_stop(self) -> None:
        """B4③-a(QueenBot 停气):rush 期间把气矿农民拉去采矿(气换矿 —— 叉子/塔全矿耗)。
        ⚠️ 未验证(未跑局)。

        实现说明:不能直接 mediator.set_workers_per_gas(0) —— main.py 的 Mining 行为
        每帧末尾重置回 3(mining.py:240,本任务不改 main.py);故学 E6 撤离改 role
        脱离 Mining,ares ResourceManager 的记账(worker_to_geyser)不动,rush 解除
        归 GATHERING 后 Mining 按原记账自动派回气矿。被司令接管的农民不动(人机共驾)。
        已停农民闲置时补采集命令(main.py 的 _handle_idle_workers 不豁免本 role,
        靠"不闲置"避免被扫走;同帧本方法在其后重停,单帧抖动无害)。
        O117-①(o116 局3/局1 实证):停气加时间窗(45s,仅 transition 流派)——
        慢性波次下 rush_active 长期 latch,停气单向棘轮把全局农民摘进台账
        (局3:停气池 38/40,采集池=0,经济停摆);窗后自动回气。"""
        # O117-①:窗口感知(非 transition 流派 window=inf = 旧行为)
        if self._rush_active and self._gas_stop_since is None:
            self._gas_stop_since = self.ai.time
        if not self._rush_active:
            self._gas_stop_since = None
        _stop_age = (
            self.ai.time - self._gas_stop_since
            if self._gas_stop_since is not None
            else 0.0
        )
        # O157:气体烂银行、矿物枯竭、舰队未成规模 → 停气转矿。
        _fleet_total = (
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST)
            + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER)
            + cy_unit_pending(self.ai, UnitID.TEMPEST)
            + cy_unit_pending(self.ai, UnitID.CARRIER)
        )
        _crisis_now = mineral_crisis_gas_stop(
            self.ai.vespene,
            self.ai.minerals,
            _fleet_total,
            bases=self.ai.townhalls.amount,
        )
        if _crisis_now:
            self._mineral_crisis_gas_stop = True
        # O160: 恢复阈值下调并与触发阈值拉开滞回(触发 vespene≥600/minerals≤300,
        # 恢复 vespene<300 或 minerals>500),避免每帧抖动。
        elif self._mineral_crisis_gas_stop and (
            self.ai.vespene < 300 or self.ai.minerals > 500
        ):
            self._mineral_crisis_gas_stop = False
        if rush_gas_stop_window(
            self._rush_active,
            _stop_age,
            window=45.0 if self._flow.transition is not None else float("inf"),
        ) or self._mineral_crisis_gas_stop:
            gas_workers = self.manager_mediator.get_worker_to_vespene_dict
            gathering = self.manager_mediator.get_unit_role_dict.get(
                UnitRole.GATHERING, set()
            )
            player_ctrl = getattr(self.ai, "_player_ctrl", {})
            for w in self.ai.workers:
                if w.tag in player_ctrl:
                    continue
                if w.tag in gas_workers and w.tag in gathering:
                    self.manager_mediator.assign_role(
                        tag=w.tag, role=self._GAS_STOP_ROLE
                    )
                    self._gas_stopped_tags.add(w.tag)
                    if w.is_carrying_vespene:
                        w.return_resource()
                    elif self.ai.mineral_field:
                        w.gather(self.ai.mineral_field.closest_to(w))
                elif w.tag in self._gas_stopped_tags and w.is_idle:
                    if self.ai.mineral_field:
                        w.gather(self.ai.mineral_field.closest_to(w))
        elif self._gas_stopped_tags:
            alive = {w.tag for w in self.ai.workers}
            for tag in list(self._gas_stopped_tags):
                if tag in alive:
                    self.manager_mediator.assign_role(tag=tag, role=UnitRole.GATHERING)
                self._gas_stopped_tags.discard(tag)

    def _effective_spawn(self) -> dict:
        """当前实际 spawn 配方 = 流派配方 + pivot 动态修正:
        rush 中 → 只出叉子顶到 rush_zealots 个;对面爆空军 → 混入 anti_air_units;
        侦查判 greedy → E10 风暴主 C 压制(成型/中后期转回航母)。"""
        pv = self._flow.pivot
        if pv is None:
            return self._flow.spawn_dict()
        # O92:过渡形态激活 → ground_spawn 就是主配方(不是临时补丁):
        # rush 纯叉覆盖/O89 逃生门/E10 pivot/反空军混编/pre_fleet/save_up 全部
        # 让位 —— 星门已冻(舰队分支无意义),追猎自带对空(反空军多余),
        # 地面配方不吃气(憋气无意义),叉/追猎本身就是主 C(不需要保底)。
        # O208:Zerg Timing 的 timing 压力比 Rush 晚，Roach/Ravager 混合波次
        # 对纯 Zealot 不利，改用 Stalker/Zealot 混编(追猎吃气先行、叉子矿耗补位)。
        if self._transition_active and self._flow.transition is not None:
            if self._opp_race == "zerg" and self._ai_build == "timing":
                return {
                    UnitID.STALKER: {"proportion": 0.4, "priority": 0},
                    UnitID.ZEALOT: {"proportion": 0.6, "priority": 1},
                }
            return self._flow.transition.ground_spawn_dict()
        # rush 响应:叉子还没顶够数,全力补叉
        # O203:舰队已转型成功 → 不再走 rush_zealots 分支,避免 zealot 持续吞矿、
        # gas 烂银行。fleet 成型后的赢法是舰队规模,不是填叉子。
        # O297-①(o296b game_02 实证):ZT 的 _fleet_transitioned 永假 → rush
        # 纯叉分支整局有效,舰队基建已活仍波后叉子回填(5×100 矿/波 ≈ 2.5
        # 暴风的矿);与 O203 同语义,舰队基建活即退出本分支。
        if (
            self._rush_active
            and pv.rush_zealots
            and not self._fleet_transitioned
            and not self._zt_fleet_infra_live()
        ):
            zealots = self.manager_mediator.get_own_unit_count(
                unit_type_id=UnitID.ZEALOT
            )
            if zealots < pv.rush_zealots:
                # O89(n5m-terran-air game_05 实证):舰队逃生门 —— 慢性接触下
                # 叉子即出即死、永远填不满 cap,纯叉配方把星门永久饿死
                # (4 SG+FB 就绪、气 2344、124s+ 零舰队败亡)。基建齐 + 气 ≥800
                # → 混编:叉子续防吃矿,舰队吃叉子用不上的气;配比减半、
                # 优先级后移,叉子保持第一优先。急性 rush 早期基建未齐,门不开。
                if rush_spawn_fleet_escape(
                    vespene=self.ai.vespene,
                    ready_stargates=len(
                        [
                            s
                            for s in self.manager_mediator.get_own_structures_dict[
                                UnitID.STARGATE
                            ]
                            if s.is_ready
                        ]
                    ),
                    fb_present_or_pending=self._structure_present_or_pending(
                        UnitID.FLEETBEACON
                    ),
                ):
                    # O200(o199b-vh-zerg-rush game_04 910s 仅 2 虚空):mixed 模式 Zealot
                    # 比例过高,持续吞 mineral 窗,舰队成型不足。降到 0.3,舰队占 0.7,
                    # 让 FB/星门就绪后舰队更快上量。
                    mixed = {UnitID.ZEALOT: {"proportion": 0.3, "priority": 0}}
                    for uid, conf in self._flow.spawn_dict().items():
                        mixed[uid] = {
                            "proportion": conf["proportion"] * 0.7,
                            "priority": conf["priority"] + 1,
                        }
                    return mixed
                return {UnitID.ZEALOT: {"proportion": 1.0, "priority": 0}}
        # O292(D1,o291a game_01 实证):ZT 首波预备产兵 —— rush 确认=波到脸
        # 才开闸,GW1 156s 就绪后空转 93s,首叉 249s,波 278s 到脸只 1 叉
        # +2 塔,矿 415/气 552 烂银行。GW 就绪即开闸:追猎/叉子混编(气全
        # 烂银行,追猎=白捡的对重甲 DPS),cap 6 自校正 —— 够数即回舰队配方。
        # 与 O208 证伪的 transition 不同:不冻星门/FB 科技链,只动用闲置 GW
        # 产能;rush 确认后上方 rush 分支接管(纯叉顶数),本分支自然让位。
        # fleet_infra_live 即关闸:舰队上量第一优先,trickle 不压舰队(败局层②)。
        # O293-①(o292a game_01 实证):口袋 Nexus 激活期 cap 6→3 —— 保留
        # 首波核心 3 地面兵,余下 ~300 矿让进 Nexus 400 资金窗(O290 塔链
        # 已封顶,trickle 不让位 = Nexus 永远攒不出);Nexus 派出 active 翻假,
        # cap 自动回 6。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and zt_prewave_trickle_needed(
                fleet_infra_live=self._zt_fleet_infra_live(),
                gateway_ready=any(
                    g.is_ready
                    for g in self.manager_mediator.get_own_structures_dict[
                        UnitID.GATEWAY
                    ]
                ),
                ground_count=(
                    self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.ZEALOT)
                    + self.manager_mediator.get_own_unit_count(
                        unit_type_id=UnitID.STALKER
                    )
                ),
                cap=(
                    3
                    if (
                        self._zt_pocket_expand_active()
                        and self.ai.townhalls.amount < 2
                    )
                    else 6
                ),
            )
        ):
            return {
                UnitID.STALKER: {"proportion": 0.4, "priority": 0},
                UnitID.ZEALOT: {"proportion": 0.6, "priority": 1},
            }
        spawn = self._flow.spawn_dict()
        # E10 策略 pivot(只挂 carrier × 侦查 verdict=greedy):舰队成型前
        # 风暴主 C 压制(9c2f89d 认证赢法),成型/中后期转回航母主 C 终结。
        # rush/unknown/未判定 → 不 pivot(保守默认,绝不按 Macro 打)。
        if self._pivot_tempest_mode():
            spawn = tempest_primary_spawn(spawn, UnitID.CARRIER, UnitID.TEMPEST)
        # 反空军 pivot:敌可见空军主力 ≥ trigger → 混入对空兵种
        air_threat = sum(
            1 for u in self.ai.enemy_units
            if u.is_flying and not u.is_structure
            and u.type_id not in (UnitID.OBSERVER, UnitID.WARPPRISM,
                                  UnitID.MEDIVAC, UnitID.OVERSEER)
        )
        # O301-①(o300a game_01 实证):pivot 追猎 p0/0.3 在 freeflow 下无上限
        # —— 兵营快(30s/125 矿)对星门(43s/175 矿+125 气)速度碾压,追猎
        # 洪水 28 只(3500 矿+1400 气)把暴风挤到 4 艘(胜局配方 14-17)。
        # 追猎混入加上限:现有 <12 才混(防空保险够用的量,矿留给暴风)。
        # O303-③(o302b game_04 实证):腐化海(19-20 条)时 cap 12 = 缴械
        # —— 暴风被 massive 加成克死,追猎是唯一能还手的;cap 动态化
        # (pivot_stalker_cap:腐化 ≥9 按 1.5× 放量)。
        if air_threat >= pv.anti_air_trigger and pv.anti_air_units:
            _corruptors = sum(
                1 for u in self.ai.enemy_units
                if u.type_id == UnitID.CORRUPTOR
            )
            _stalker_cap = pivot_stalker_cap(_corruptors)
            for name in pv.anti_air_units:
                uid = getattr(UnitID, name, None)
                if uid is not None:
                    if (
                        uid == UnitID.STALKER
                        and self.manager_mediator.get_own_unit_count(
                            unit_type_id=UnitID.STALKER
                        )
                        >= _stalker_cap
                    ):
                        continue
                    spawn[uid] = {
                        "proportion": pv.anti_air_proportion, "priority": 0,
                    }
        # O245(Zerg Timing 攻坚):敌地面重型(roach/hydra 波)时 pivot 不触发、
        # 追猎/叉子被滚平——混编不朽者(蟑螂重甲被不朽加成攻击克制,刚毅护盾
        # 站线)。机械台就绪 + 敌可见地面 ≥6 + 不朽 <4 → **dict 首位**混入
        # (p0/proportion 1.0):275 矿可付时优先于暴风,250-274 时暴风照产
        # (O245e 的 reserve 停产实证:其他开销照抽,275 永远攒不出,地面 0
        # 败亡——用优先序而不是停产解决)。
        # O297-②:舰队基建已活 → 不朽让位(矿集中灌暴风,对齐胜局配方)。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and not self._zt_fleet_infra_live()
            and any(
                s.is_ready
                for s in self.manager_mediator.get_own_structures_dict[
                    UnitID.ROBOTICSFACILITY
                ]
            )
            and self._visible_enemy_army_count() >= 6
            and self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.IMMORTAL)
            < 4
        ):
            spawn = {
                **{UnitID.IMMORTAL: {"proportion": 1.0, "priority": 0}},
                **spawn,
            }
        # O121-①(o120 局2/3/4 实证):重建窗(FB 未就绪)星门填 VOIDRAY ——
        # 退出即产,exit+60s 有 1-2 虚空顶空窗;TEMPEST 随 FB 就绪入队后
        # 同档 p0、dict 序在前自然挤占,窗关配方复原
        spawn = rebuild_window_spawn(
            spawn,
            self._flow.transition is not None
            and fleet_rebuild_window(
                self._fleet_transitioned, self._first_fleet_seen()
            ),
            UnitID.VOIDRAY,
        )
        # O155/O156: carrier 流暴风海成型后强制补航母配额。
        # 当前 TEMPEST p0/CARRIER p1 + save_up=0 导致航母被永久截断、永不出场
        # (O154 终局编成 28 暴风 0 航母实证)。触发配额时把 CARRIER 提为 p0
        # 并开动态 save_up，憋出航母后再恢复暴风主 C。
        # O156: 计入在产/在队列的舰队，避免 11 艘差一点永远到不了阈值。
        force_gap = self._flow.save_up
        if carrier_quota_active(
            self._flow.name,
            self._first_fleet_seen(),
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST),
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER),
            pending_tempest=cy_unit_pending(self.ai, UnitID.TEMPEST),
            pending_carrier=cy_unit_pending(self.ai, UnitID.CARRIER),
        ):
            spawn = carrier_quota_spawn(spawn, UnitID.CARRIER, UnitID.TEMPEST)
            force_gap = max(force_gap, 250)
        return self._apply_save_up(self._apply_floor(spawn), force_gap=force_gap)

    def _first_tempest_seen(self) -> bool:
        """A1/A2:首艘 TEMPEST 是否已出或在产(在产也算——生产窗已被主 C 占上,
        追加星门此时不再抢窗)。"""
        return (
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST)
            > 0
            or cy_unit_pending(self.ai, UnitID.TEMPEST)
        )

    def _first_fleet_seen(self) -> bool:
        """O96:首艘舰队单位(TEMPEST/CARRIER)是否已出或在产 —— 首舰闸
        (fleet_expand_holds/oracle_before_fleet_allowed)的放行信号。"""
        return (
            self._first_tempest_seen()
            or self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER)
            > 0
            or cy_unit_pending(self.ai, UnitID.CARRIER)
        )

    def _pivot_tempest_mode(self) -> bool:
        """E10:当前是否处于「风暴主 C 压制」模式(只挂 carrier × 侦查 greedy)。

        进入条件:verdict == greedy(E7 侦查判非 rush)且未到转型点;
        退出(一次性 latch):carrier_transition_ready 到点/到量 → 记事件,
        之后恒回航母主 C(不随风暴数量回落反复横跳)。
        O32:vs Zerg 不 pivot(Zerg Macro 双矿爆兵,风暴压不死;航母主 C 龟缩憋航母+早2矿)。"""
        if self._pivot_transitioned:
            return False
        _er = getattr(getattr(self.ai, "enemy_race", None), "name", None)
        if not should_pivot_tempest(self._verdict, self._flow.name, _er):
            return False
        if carrier_transition_ready(
            self.ai.time,
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST),
        ):
            self._pivot_transitioned = True
            self.ai._events.append(
                {
                    "t": round(self.ai.time, 1),
                    "msg": "E10:风暴压制转航母终结(转型点)",
                }
            )
            return False
        return True

    def _apply_floor(self, spawn: dict) -> dict:
        """E3e 舰队成型前地面保底:舰队主 C 出生前混入保底兵种(默认叉子,矿耗
        不吃气),达 cap 或主 C 上线自动退出。rush 响应的叉子覆盖优先(不进这里);
        保底兵种在 save_up 里走 exempt(保命不截断,见 _apply_save_up)。
        O134-①(o133 局2 实证):第二保底(id2/cap2,追猎)—— 非过渡局 525 波
        (25+ supply)到脸仅 1 叉;追猎吃烂在银行的气(局2 气 2900),priority
        先于叉子(气耗兵种先行的过渡配方同原则:叉子恒可负担,先放叉追猎出不来)。
        O144-③(o133 以来 10+ 系列零胜尸检):floor 收窄 —— 仅 rush 确认或
        敌可见地面 ≥4 时激活(_floor_active);纯运营局不产地面,矿全进
        舰队科技链(无差别 floor 挤 SG/FB 的钱,非 rush 局全慢半拍)。"""
        pf = self._flow.pre_fleet
        if pf is None or not self._floor_active:
            return spawn
        # O298-③(o297a game_03 实证):重建二矿钉点期(707-791s)叉子 floor
        # 回填(100 矿/个,波后 3→7 只)把 400 矿 Nexus 资金窗磨穿,
        # expand_reserve 三连停仍开不出 —— 叉子 floor 与追猎 cap2(O236)
        # 同口径:bases<2 且 Nexus 钉点未开工 → floor 全停;解除自动恢复。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and self.ai.townhalls.amount < 2
            and self.ai.not_started_but_in_building_tracker(UnitID.NEXUS) > 0
        ):
            return spawn
        uid = getattr(UnitID, pf.id_name, None)
        if uid is None:
            return spawn
        # C1:floor 退出判据收紧 —— 主 C 上线 且 地面作战单位 ≥4 才退;
        # 地面被打穿(<4)即便舰队在线也继续补叉(E10d 实证:叉子一波战死后
        # floor 已退、地面零补员 = trickle 根因)。pre_fleet 只有 carrier 配,
        # stalker/tempest/dt 无此配置,floor 语义天然不变。
        fleet_online = floor_exits(
            self.manager_mediator.get_own_unit_count(
                unit_type_id=self._primary_unit_id()
            ),
            self._ground_combat_count(),
            ground_min=pf.exit_ground,  # O48:carrier vs Harder 波次要 8(默认 4)
        )
        # O134-①:追猎先行(p5,气耗),叉子补位(p6,矿耗)
        if pf.id2 and pf.cap2 > 0:
            uid2 = getattr(UnitID, pf.id2, None)
            if uid2 is not None:
                # O230(o224 胜局 vs o229-lane1 game_01 败局对照):胜局靠 pivot
                # 反空军混出 25 追猎(吃烂气、对空对地双用)才守住;败局敌纯地面
                # 时追猎 cap2=2,基地被 27 地面滚平。Zerg Timing cap2 2→8,
                # 用烂在银行的气(常态 1000+)养追猎防守核,不抢舰队矿。
                # O231b(o230-lane2 game_01 实证):8 追猎(125 矿/只)在 FB 资金窗
                # 同样抢矿,FB 钉点派工 21 次 no_money;cap2=8 推迟到首舰出场后
                # (胜局的追猎海本来就是舰队成型后经 pivot 混出来的)。
                # O233(o232-lane1 game_01 实证):首舰刚出(舰队 1-2)时 8 追猎
                # 与暴风抢矿,舰队 280s 卡 1 艘;cap2=8 再后置到舰队 ≥3。
                _cap2 = pf.cap2
                # O255-③:unknown 死窗 floor 不产追猎 —— 追猎吃气(125/50)
                # 直接抢 SG/FB 资金窗(O253 实证 0-7);死窗只要矿耗叉子。
                if self._floor_unknown_zt:
                    _cap2 = 0
                # O236:Nexus 钉点期间追猎 floor 归零(125 矿/只),与探机暂停
                # 一起把 400 矿资金窗让给二矿;pinning 解除自动恢复。
                # O238:只限首扩钉点(bases<2);三矿以上钉点追猎核照产(防守优先)。
                elif (
                    self._opp_race == "zerg"
                    and self._ai_build == "timing"
                    and self.ai.townhalls.amount < 2
                    and self.ai.not_started_but_in_building_tracker(UnitID.NEXUS)
                    > 0
                ):
                    _cap2 = 0
                elif self._opp_race == "zerg" and self._ai_build == "timing":
                    # O241(0-30 回归排查):O230 原版(无条件 cap2=8)是两场胜局的
                    # 代码状态;O231b/O233 的舰队≥3/敌≥8 前置让中期追猎零产,
                    # 恰是 0-30 的起点。回滚为无条件 cap2=8(吃烂气防守核)。
                    # O246(o245e 系列 0-10 实证):500-700s 窗口 8 追猎仍被
                    # 10-27 地面波滚平(不朽者 650s+ 才到,补不上窗);胜局的
                    # 21-25 追猎海才是守窗答案。舰队 <8(未成型)时 cap2 8→12,
                    # 吃烂气(常态 1000+),舰队成型后回 8 让气给航母/暴风。
                    _fleet_now_o246 = (
                        self.manager_mediator.get_own_unit_count(
                            unit_type_id=UnitID.TEMPEST
                        )
                        + self.manager_mediator.get_own_unit_count(
                            unit_type_id=UnitID.CARRIER
                        )
                    )
                    _cap2 = max(_cap2, 12 if _fleet_now_o246 < 8 else 8)
                    # O260-①(o259b-g02 实证):气烂 ≥600 说明瓶颈是矿不是气,
                    # 12 追猎(1500 矿)波灭即重建,把航母(350 矿)的资金窗
                    # 磨没(舰队 750-1050s 卡 2-3,气 1000+ 恒在)。气烂时
                    # 追猎核收到 4,矿让给舰队。
                    if self.ai.vespene >= 600.0:
                        _cap2 = min(_cap2, 4)
                    # O272-②(o270b-g03 实证):敌制空成群(腐化/飞蛇/大龙)时
                    # 追猎是暴风唯一的存活保障(对装甲加成,射程外点杀腐化),
                    # 节流让位 —— cap 拉回 12,舰队被腐化磨光比矿窗更要命。
                    _enemy_aa = sum(
                        1
                        for u in self.ai.enemy_units
                        if u.is_flying
                        and u.type_id
                        in (
                            UnitID.CORRUPTOR,
                            UnitID.VIPER,
                            UnitID.MUTALISK,
                            UnitID.BROODLORD,
                        )
                    )
                    if _enemy_aa >= 4:
                        _cap2 = max(_cap2, 12)
                    # O273-①(o272b-g01 实证):敌制空转型是预见性的(700s 后
                    # 必来),等看见腐化再产追猎 = 30s+ 产能空窗,舰队 8s 内
                    # 先死(4→0)。t≥700 追猎 cap 预置 8(防空保险),
                    # 舰队成型(≥8)后回 4 让矿给航母。
                    # O304-③(o303a game_05 实证):快尖塔局腐化 723s 出场时
                    # 我方追猎仅 2 只 —— 预置窗提前到 650s,腐化一到即有
                    # 追猎核可战。
                    if self.ai.time >= 650.0 and _fleet_now_o246 < 8:
                        _cap2 = max(_cap2, 8)
                spawn = pre_fleet_spawn(
                    spawn,
                    floor_id=uid2,
                    floor_count=self.manager_mediator.get_own_unit_count(
                        unit_type_id=uid2
                    ),
                    floor_cap=_cap2,
                    fleet_online=fleet_online,
                    priority=5,
                )
        return pre_fleet_spawn(
            spawn,
            floor_id=uid,
            floor_count=self.manager_mediator.get_own_unit_count(unit_type_id=uid),
            # O255-③:unknown 死窗 floor 叉子上限压 3(300 矿,从常态 1300+
            # 银行出);常规 floor 通道(rush 确认/敌可见 ≥4)不受影响。
            # O279:首波预警期(敌兵成型情报到手)叉 cap 3→5 —— 墙缝/塔阵
            # 多两条命,波 40-60s 后到脸正好折跃完。
            floor_cap=(
                min(
                    pre_fleet_cap(
                        pf.cap, pf.per_enemy, pf.max,
                        self._visible_enemy_army_count(),
                    ),
                    5 if self._wave_incoming else 3,
                )
                if self._floor_unknown_zt
                else pre_fleet_cap(
                    pf.cap, pf.per_enemy, pf.max, self._visible_enemy_army_count()
                )
            ),
            fleet_online=fleet_online,
            priority=6,
        )

    def _ground_combat_count(self) -> int:
        """C1:我方地面作战单位数(ATTACKING 编制内非空军非建筑)。"""
        return sum(
            1
            for u in self.manager_mediator.get_units_from_role(
                role=UnitRole.ATTACKING
            )
            if not u.is_flying and not u.is_structure
        )

    def _apply_save_up(self, spawn: dict, force_gap: int | None = None) -> dict:
        """O5 憋气机制(方案 b):spawn dict 喂 SpawnController 前过 save_up_spawn。
        freeflow 下 p0(航母)买不起就会被 p1(风暴)fall-through 吃掉每一滴气,
        永远攒不出 250 气 —— 这里按占比/气缺口动态截断低优先兵种。
        阈值 = flows.yml 的 save_up(气缺口,0=关);单兵种配方无需处理直接返回。
        E3c:pivot 反空军混编兵种(STALKER)走 exempt 永不截断 —— 它是保命的防空,
        不是副 C(敌 6 腐化时被截断 = 零对空团灭)。
        O155: force_gap 覆盖 flow.save_up，用于 carrier 配额窗口强制憋气。
        """
        gap = force_gap if force_gap is not None else self._flow.save_up
        if not gap or len(spawn) < 2:
            return spawn
        pv = self._flow.pivot
        exempt = {
            uid
            for name in (pv.anti_air_units if pv else ())
            if (uid := getattr(UnitID, name, None)) is not None and uid in spawn
        }
        # E3e:保底兵种同样 exempt(保命不截断,与反空军同原则)
        pf = self._flow.pre_fleet
        if pf is not None:
            floor_uid = getattr(UnitID, pf.id_name, None)
            if floor_uid in spawn:
                exempt.add(floor_uid)
            # O134-①:第二保底兵种(追猎)同例 exempt
            if pf.id2:
                floor_uid2 = getattr(UnitID, pf.id2, None)
                if floor_uid2 in spawn:
                    exempt.add(floor_uid2)
        # E9:threat 激活(且非 rush) → 地面防御兵种全部 exempt —— 敌大部队
        # 压境还憋舰队截地面就是裸奔(macro-fix1 实证:敌 20+ 到脸我方 6 叉)。
        # rush 期六连动已全权接管,不叠加。
        if self._threat_active and not self._rush_active:
            exempt |= threat_ground_exemption(spawn, _FLYING_UNITS)
        return save_up_spawn(
            spawn,
            counts={
                uid: self.manager_mediator.get_own_unit_count(unit_type_id=uid)
                for uid in spawn
            },
            affordable={uid: self.ai.can_afford(uid) for uid in spawn},
            resource_gap={
                # E3h:缺口看矿+气两者取大 —— 只看气会在矿瓶颈局把 p1 锁死
                uid: max(
                    0,
                    self.ai.calculate_cost(uid).vespene - self.ai.vespene,
                    self.ai.calculate_cost(uid).minerals - self.ai.minerals,
                )
                for uid in spawn
            },
            buildable={uid: self.ai.tech_ready_for_unit(uid) for uid in spawn},
            max_gap=gap,
            exempt=exempt,
        )

    def _defense_score(self) -> float:
        """O100-② 防御评分口径:地面(叉/追猎)×2 + 就绪塔×3 + 就绪电池×2。
        strong-exit(O100)/扩张门豁免(O105-①)共用。"""
        return (
            2 * (
                self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.ZEALOT)
                + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.STALKER)
            )
            + 3 * sum(
                1 for s in self.ai.structures.ready
                if s.type_id == UnitID.PHOTONCANNON
            )
            + 2 * sum(
                1 for s in self.ai.structures.ready
                if s.type_id == UnitID.SHIELDBATTERY
            )
        )

    def _zt_enemy_near_natural(self) -> int:
        """O263-①:最近的空闲扩张点 35 格内敌作战单位数(波次路径踩点检查)。

        无空闲扩张点 → 0(不挡开矿闸,反正也开不了)。
        O263b(o263a 两局 ERROR 实证):基地死光后 townhalls 为空,
        min() 空序列炸 ValueError 整局崩 —— 空列表守卫。"""
        if not self.ai.townhalls:
            return 0
        free = [
            el
            for el in self.ai.expansion_locations_list
            if not self.ai.townhalls.closer_than(5.0, el)
        ]
        if not free:
            return 0
        nat = min(
            free,
            key=lambda el: min(el.distance_to(th) for th in self.ai.townhalls),
        )
        return sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and is_combat_type(u.type_id)
            and u.position.distance_to(nat) < 35
        )

    def _zt_pocket_expand_target(self):
        """O281(o280 基线复测 0-9 裁决打法上限):ZT 口袋矿选址。

        natural 在 305-320s 死窗波行进路径上,Nexus 建筑期被首波打断/白捐
        (o280 复盘 one_base×2:420s 仍单矿)。首扩(townhalls==1)目标改取
        离敌出生点最远的空闲扩张点;非 ZT / bases>=2 / 敌点未知 / 无空闲点
        → None(调用方退回原 natural 逻辑)。空集合守卫同 O263b。
        O283 推广到 1..max_bases-1 已证伪回退(o283/o284/o285 三个 0-10:
        首扩行为不变、三矿早落但新矿裸奔被小股轮抄,胜场反消失)。"""
        if not (self._opp_race == "zerg" and self._ai_build == "timing"):
            return None
        if self.ai.townhalls.amount != 1:
            return None
        if not self.ai.enemy_start_locations:
            return None
        free = [
            el
            for el in self.ai.expansion_locations_list
            if not self.ai.townhalls.closer_than(5.0, el)
        ]
        # O291(司令观察):传 playable 区域 → 选址加地形分(背靠图缘的
        # 矿点背后墙体天然封口,只需封正面 1-2 个口)。
        _pa = getattr(self.ai.game_info, "playable_area", None)
        _rect = (_pa.x, _pa.y, _pa.width, _pa.height) if _pa is not None else None
        return pick_pocket_expansion(
            free, self.ai.enemy_start_locations[0], _rect
        )

    def _zt_enemy_near_expand_target(self) -> int:
        """O281:扩张目标点(口袋矿)35 格内敌作战单位数。

        波压在 natural(波路径)上时口袋矿仍安全,开矿闸应看目标点而不是
        natural —— 否则波一到 natural 开矿永被锁死(o280 one_base 死法)。
        非 ZT 场景退回 _zt_enemy_near_natural(行为不变)。
        O296-②(o295a game_02 实证):35 格半径把主基交战圈也罩进来
        (口袋-主基仅 ~28 格)——敌一波主基,口袋开矿就被锁,激活拖到
        600s 错过 ≤413s 配方窗。收到 20 格:只看口袋矿线/逼近路口的敌,
        主基交战(塔阵接敌)不再锁口袋(O282「敌压主基正是口袋空窗」本意)。"""
        target = self._zt_pocket_expand_target()
        if target is None:
            return self._zt_enemy_near_natural()
        return sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and is_combat_type(u.type_id)
            and u.position.distance_to(target) < 20
        )

    def _zt_fleet_infra_live(self) -> bool:
        """O297:ZT 舰队基建是否已活(SG 就绪 + FB 在场/在建)。

        ZT 的 _fleet_transitioned 永假(transition 禁入,O249b),凡以
        「已转型」为闸的逻辑(O203 rush 纯叉退出/O292 trickle 关闸)对 ZT
        都失效 —— 本方法提供统一的 ZT 实况口径。"""
        return (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and any(
                s.is_ready
                for s in self.manager_mediator.get_own_structures_dict[
                    UnitID.STARGATE
                ]
            )
            and self._structure_present_or_pending(UnitID.FLEETBEACON)
        )

    def _zt_pocket_expand_active(self) -> bool:
        """O282(o281 双 lane 0-9 尸检):口袋矿首扩激活判据。

        o281 实证:口袋矿机制成立(死窗波不再收割,存活 697-949s)但扩张
        拖到 442-671s —— enemy_home/rush 闸在波 305-660s 常闭,holding 随闸
        翻板,矿被塔/地面吃干,窗开放后永远攒不到 400。口袋矿远离主基前线,
        敌压主基正是口袋空窗(塔阵接敌):激活期(窗开放+首塔就绪+口袋点
        无敌+无 Nexus 在途)直接想开,holding 锁死攒钱,目标落成 ≤400s
        (O236 胜负线)。Nexus 一旦在途,holding 由 O54 的 counter/tracker
        条款接管,本判据退出。"""
        if self._zt_pocket_expand_target() is None:
            return False
        # O287(跨 60 局胜/败局支出结构对照):激活窗 280→200 —— 唯一胜局
        # (o282a-g02)的赢面轨迹是 ~180s 起零新增建筑、硬攒到 790 银行,
        # 窗开即拍 Nexus(309s);败局共同点是 190-280s 零星支出(水晶 5-6/
        # 二 forge/塔 2-3)把银行滴干,窗开时 m=20-90。早激活 = 早 holding =
        # 非威胁开销全让位;威胁/rush 例外不变,真波来仍放塔。
        if self.ai.time < 200.0 or self._cannons_ready_peak < 1:
            return False
        if self._zt_enemy_near_expand_target() > 0:
            return False
        if self.manager_mediator.get_building_counter[UnitID.NEXUS] > 0:
            return False
        if self.ai.not_started_but_in_building_tracker(UnitID.NEXUS) > 0:
            return False
        return True

    def _zt_pocket_expand_debug(self) -> None:
        """O283d(o283 双 lane 0-10 排查):口袋激活判据逐子条件节流记账。

        o283 实证:激活旁路整局未触发(二矿走 O251 硬饱和钉点 584s),
        静态读码定位不到哪个子条件为假 —— 运行时记账,10s 一条。"""
        if not (self._opp_race == "zerg" and self._ai_build == "timing"):
            return
        if not (1 <= self.ai.townhalls.amount <= 2):
            return
        if not (270.0 < self.ai.time < 700.0):
            return
        _last = getattr(self, "_o283_dbg_ts", 0.0)
        if self.ai.time - _last < 10.0:
            return
        self._o283_dbg_ts = self.ai.time
        _near_main = sum(
            1 for s in self.ai.structures.ready
            if s.type_id == UnitID.PHOTONCANNON
            and s.position.distance_to(self.ai.start_location) < 25
        )
        self.ai._events.append({
            "t": round(self.ai.time, 1),
            "msg": (
                f"O283d: target={self._zt_pocket_expand_target() is not None}"
                f" cannons_peak={self._cannons_ready_peak}"
                f" near={self._zt_enemy_near_expand_target()}"
                f" counter={self.manager_mediator.get_building_counter[UnitID.NEXUS]}"
                f" tracker={self.ai.not_started_but_in_building_tracker(UnitID.NEXUS)}"
                f" active={self._zt_pocket_expand_active()}"
                f" cn_main={_near_main}"
                f" rush={self._rush_active}/{self._rush_confirmed}"
                f" threat={self._threat_active}"
                f" m={round(self.ai.minerals)}"
            ),
        })

    def _want_dynamic_expand(self) -> bool:
        """动态开矿是否已触发(配了 max_bases 的流派,rush 内建门)。
        E3k:update 头部算一次,ExpansionController 注册与攒钱预留共用。"""
        self._zt_pocket_expand_debug()  # O283d:激活判据节流记账(排查期)
        # O168:8 农民 carrier 核心科技缺失期间禁扩张，避免 Nexus 把
        # CYBERNETICCORE/STARGATE/FLEETBEACON 的资金窗吸干。
        # O216:Zerg Timing 下二矿是生存前提,150s 触发不能被 early_core_missing
        # 阻塞到 300s;Rush/Power/Macro 仍保持原保护。
        if (
            getattr(self, "_early_core_missing", False)
            and not (
                self._opp_race == "zerg" and self._ai_build == "timing"
            )
        ):
            return False
        # O216i(o216h-lane2 game_01 实证):Zerg Timing 首塔未就绪不开矿 ——
        # 196s 派 Nexus 时 0 塔,银行被塔链/科技抽干,Nexus 工人钉点后撤,
        # 306s 波到脸 0 塔被推平(O216a 150s 无防强开教训复现)。防御先行。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and self._cannons_ready_peak < 1
        ):
            return False
        # O282(o281 双 lane 0-9 尸检):口袋矿首扩激活 → 不看主基前线
        # (enemy_home/rush/transition 闸在波 305-660s 常闭,holding 翻板,
        # 矿被塔/地面吃干,Nexus 拖 442-671s 全在 O236 负侧)。口袋矿远离
        # 前线,敌压主基正是口袋空窗,塔阵接敌与开矿并行。
        if self._zt_pocket_expand_active():
            return True
        # O247(o246 系列 0-15 实证):二矿 400-500s 落成即被 10-27 地面波轮抄,
        # 经济永远起不来;改舰队先行 —— 首舰(Tempest)出场前不开二矿,
        # 舰队掩护下再扩(600s 前后),单矿期矿全给塔/地面/舰队科技。
        # 本门在 O189 强开上游,首舰前 O189 同步不触发(语义一致)。
        # O258-①(o257 双 lane 0-10 尸检):O255-O257 后死窗/波 2-6 可守,
        # 闸改防御驱动(zerg_timing_expand_allowed):t≥340 且非急性窗即放行,
        # 不等首舰 —— O236 对照「二矿 ≤400s=胜、≥500s=负」,原闸把落成压到
        # 518-671s 全在负侧(单矿 22-24 农养不起航母海,舰队 2-3 封顶被磨死)。
        # O262-①(o261 双 lane 0-10 尸检):threat 首波后几乎常驻,闸整局不开
        # (o261a-g01 单矿到 900s);窗提前到 260s 且去 threat 条件(波打主基
        # 正是分矿空窗),家 40 格有敌仍不开。
        if not zerg_timing_expand_allowed(
            self._opp_race == "zerg" and self._ai_build == "timing",
            self._first_fleet_seen(),
            self.ai.time,
            sum(
                1 for u in self.ai.enemy_units
                if not u.is_structure and is_combat_type(u.type_id)
                and u.position.distance_to(self.ai.start_location) < 40
            ),
            self._zt_enemy_near_expand_target(),  # O281:对着首扩目标点(口袋矿)
            self._cannons_ready_peak,
        ):
            return False
        ae = self._flow.auto_expand
        if ae is None or not ae.max_bases:
            return False
        # O183:Zerg Timing/Rush 不能按 210s 抢二矿，先把 400 矿投入防御；
        # Power/Macro 等已验证组合保持原 first_expand_at。
        # O207:Timing 压力比 Rush 晚/轻，允许 240s 启动二矿(仍晚于首波 160-200)，
        # 避免 Paladino 系列 one_base×4 被滚雪球；Rush 保持 300s 先站稳。
        # O215:Timing 二矿仍太晚(430-470s)，降到 180s——首波 160-200s 前 forge+
        # 1-2 塔已就位，180s 开始攒 Nexus 能在 240-280s 落成，比当前 430s+ 早一
        # 个波次周期；Rush 维持 300s 先站稳。
        _first_expand_at = ae.first_expand_at
        if self._opp_race == "zerg" and self._ai_build == "rush":
            _first_expand_at = max(_first_expand_at, 300.0)
        elif self._opp_race == "zerg" and self._ai_build == "timing":
            # O216(o215-vh-zerg-timing 0-9 实证):Timing 二矿仍太晚(373-630s),
            # 降到 180s 让 Nexus 资金窗在首波间隙出现;二矿存活率=胜率。
            # 150s 实证(O216a game_01):forge/首塔尚未就绪,无防御强开被滚雪球,
            # 回调到 180s 等基础防御落位。
            _first_expand_at = max(_first_expand_at, 180.0)
        # O96(o95 局1 实证):过渡期兵营未到 cap 不开矿 —— 局1 二矿 t≈290
        # 抢走 400 矿,兵营#2 拖到 t≈280,单兵营 7 叉迎 30-supply 波。
        # 「已有+在建」口径与 _build_extra_production 同源。
        tr = self._flow.transition
        if tr is not None:
            _gw = (
                len(self.manager_mediator.get_own_structures_dict[UnitID.GATEWAY])
                + len(self.manager_mediator.get_own_structures_dict[UnitID.WARPGATE])
                + self.manager_mediator.get_building_counter[UnitID.GATEWAY]
            )
            # O191(o190-vh-zerg-rush game_01 实证):Rush transition 中 gateway_cap=3
            # 卡住二矿——单矿要同时造 3 个兵营+塔+气矿+科技,400 矿永远攒不出来;
            # 降到 2 让二矿在站稳后能启动,双矿经济支撑地面阶段/舰队转型。
            _expand_gateway_cap = tr.gateway_cap
            # O208:Zerg Timing 混编地面需要更多兵营产能，cap 提到 2；
            # Rush 保持上限 2 避免兵营吞二矿资金。
            if (
                self._transition_active
                and self._opp_race == "zerg"
                and self._ai_build in ("rush", "timing")
            ):
                _expand_gateway_cap = max(min(_expand_gateway_cap, 2), 2)
            # O216:Zerg Timing 下二矿优先于兵营 cap 凑齐——等 2 兵营+2 塔再开矿,
            # 在 timing 局永远凑不齐(首波 160-200s 后到脸,地面/塔钱持续被抽)。
            # Rush 仍保持阻塞,先站稳。
            if (
                transition_expand_blocked(
                    self._transition_active, _gw, _expand_gateway_cap
                )
                and not (
                    self._opp_race == "zerg" and self._ai_build == "timing"
                )
            ):
                return False
            # O100-①(o99 局1/局5 实证):过渡期防御站稳(塔≥2+地面≥8+家 40 格
            # 清净 15s)→ 允许开二矿,不等转舰队 —— 波次 60-90s 一波的局清净
            # 退出门永假,单矿 12-15 农民缓慢必死;双矿地面产能翻倍,要么地面
            # 打死对面,要么攒出退出门。rush 否决旁路(站稳三重门已含敌情)。
            if self._transition_active:
                _clear = (
                    self.ai.time - self._transition_clear_since
                    if self._transition_clear_since is not None
                    else 0.0
                )
                # O105-①b:站稳判定记账(update 头部的扩张攒钱预留读)
                _cannons_ready = sum(
                    1 for s in self.ai.structures.ready
                    if s.type_id == UnitID.PHOTONCANNON
                )
                _ground = (
                    self.manager_mediator.get_own_unit_count(
                        unit_type_id=UnitID.ZEALOT
                    )
                    + self.manager_mediator.get_own_unit_count(
                        unit_type_id=UnitID.STALKER
                    )
                )
                _enemy_home = sum(
                    1 for u in self.ai.enemy_units
                    if not u.is_structure and is_combat_type(u.type_id)
                    and u.position.distance_to(self.ai.start_location) < 40
                )
                # O204:Zerg Rush 二矿门槛进一步降低:地面 4→2,清净 8s→5s。
                _tr_min_ground = 2 if (
                    self._opp_race == "zerg" and self._ai_build == "rush"
                ) else 4
                _tr_clear_needed = 5.0 if (
                    self._opp_race == "zerg" and self._ai_build == "rush"
                ) else 8.0
                self._tr_expand_ready = transition_expand_ready(
                    True,
                    cannons_ready=_cannons_ready,
                    ground_army=_ground,
                    clear_for=_clear,
                    min_ground=_tr_min_ground,
                    clear_needed=_tr_clear_needed,
                ) or transition_expand_after_first_wave(
                    # O122-②(o121b 实证):清净秒数窗被波次切碎(全系列 0 触发)
                    # —— 见过一波且当前已清 + 塔/地面达标即开,不等秒数
                    True,
                    self._saw_wave and _enemy_home == 0,
                    cannons_ready=_cannons_ready,
                    ground_army=_ground,
                )
                # O149-①(o133-o148 元诊断:二矿存活率=胜率):定时强开 ——
                # t≥210 且首波已清 → 直接开,不等站稳三重门/兵力优势
                # (timing 局清净窗永远不够,触发率≈0 的判据等于没有)
                # O216:Zerg Timing 强开线降到 150s,且放宽到「首波已清 或 时间到
                # 180s」,避免 timing 波连续到脸导致 saw_wave 后 enemy_home 不空、
                # 二矿永远开不出。
                _tr_expand_at = 180.0 if (
                    self._opp_race == "zerg" and self._ai_build == "timing"
                ) else 210.0
                if transition_expand_at_210(
                    self._transition_active,
                    self._saw_wave or (
                        self._opp_race == "zerg"
                        and self._ai_build == "timing"
                        and self.ai.time >= 200.0
                    ),
                    _enemy_home,
                    self.ai.time,
                    at=_tr_expand_at,
                ):
                    self._tr_expand_ready = True
                    return True
                if not self._tr_expand_ready:
                    # O189:Zerg Timing/Rush 在 transition 中常因波次不断、 mineral
                    # 被防御吸干而永远开不出二矿，单矿经济撑不到 fleet 成型。
                    # 兜底：t≥210、仅 1 基地、无 Nexus 在造、矿≥150 时强制开二矿。
                    # O201(o200-vh-zerg-rush 3-7 实证):Lane1 5/5 one_base,240/200
                    # 仍太高;降到 210/150,让二矿资金窗更早出现。
                    # O214:Timing 压力比 Rush 更早更重,再降到 180/100,让二矿
                    # 在首波 160-200s 到来前开始攒/拍,避免单矿被滚雪球。
                    # O216:Timing 降到 180/100,二矿资金窗必须让出来;
                    # 150s 实证 forge/首塔未就绪,回调到 180 等基础防御。
                    # O216g(o216f 尸检:idle_builder NEXUS 42-166 次/局):
                    # 事件只记一次,不再每帧刷屏。
                    # O216h(o216g-lane2 game_01 实证):矿门 300 回调到 150 ——
                    # 威胁期塔链持续抽干银行,300 矿门整局不触发=二矿永远不开;
                    # 配合 F2「Nexus 钉点期间塔链让位」闸,银行 ~12s 攒到 400,
                    # 钉点有界且二矿真正落地。
                    _o189_at = 210.0
                    _o189_minerals = 150.0
                    if self._opp_race == "zerg" and self._ai_build == "timing":
                        _o189_at = 180.0
                        _o189_minerals = 150.0
                    if (
                        self._opp_race == "zerg"
                        and self._ai_build in ("rush", "timing")
                        and self.ai.time >= _o189_at
                        and self.ai.townhalls.amount == 1
                        and self.manager_mediator.get_building_counter[UnitID.NEXUS] == 0
                        and self.ai.minerals >= _o189_minerals
                    ):
                        self._o189_forced_expand = True
                        if not self._o189_logged:
                            self._o189_logged = True
                            self.ai._events.append({
                                "t": round(self.ai.time, 1),
                                "msg": "O189:Zerg rush/timing 单矿太久,强制开二矿",
                            })
                        return True
                    # O204:transition 期强制二矿触发器(与 rush_active 解耦):
                    # 180s 后只要 2 塔就绪、家附近无敌、矿够 450 就强开。
                    if forced_expand_during_transition(
                        True,
                        self.ai.time,
                        _cannons_ready,
                        _enemy_home,
                        self.ai.minerals,
                        self.manager_mediator.get_building_counter[UnitID.NEXUS],
                        self.ai.calculate_cost(UnitID.NEXUS).minerals,
                    ):
                        self.ai._events.append({
                            "t": round(self.ai.time, 1),
                            "msg": "O204:transition 防御站稳,强制开二矿",
                        })
                        return True
                    return False
                _fleet_total = (
                    self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST)
                    + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER)
                    + cy_unit_pending(self.ai, UnitID.TEMPEST)
                    + cy_unit_pending(self.ai, UnitID.CARRIER)
                )
                # O186:Zerg Rush 的 transition 延长到 500s,若 max_bases 仍
                # 用 3,bot 会铺 3-4 基地把舰队资金吃光;封顶 2 基地,让资源优先变
                # 成地面防御/兵营/舰队科技。
                # O208:Zerg Timing 需要 3 基地经济支撑 carrier 后期舰队规模，
                # 仅 Rush 锁 2 基地，Timing 保持 flows.yml 的 max_bases(3)。
                _max_bases = ae.max_bases
                if self._opp_race == "zerg" and self._ai_build == "rush":
                    _max_bases = min(_max_bases, 2)
                return should_expand_dynamic(
                    bases=self.ai.townhalls.amount,
                    max_bases=_max_bases,
                    nexus_pending=self.manager_mediator.get_building_counter[
                        UnitID.NEXUS
                    ],
                    supply_workers=self.ai.supply_workers,
                    workers_per_base=ae.when_workers,
                    own_army_supply=self.ai.supply_used - self.ai.supply_workers,
                    enemy_army_supply=self._visible_enemy_army_supply(),
                    advantage_supply=ae.advantage_supply,
                    now=self.ai.time,
                    first_expand_at=_first_expand_at,
                    rush_active=False,  # O100-①:站稳窗内 rush 不否决
                    minerals=self.ai.minerals,
                    fleet_total=_fleet_total,
                )
            self._tr_expand_ready = False
        # O93-B2/O96/O105-①:转舰队后首舰(已出/在产)前不开矿;O105 起防御
        # 评分达标(≥25,strong-exit 同口径)豁免 —— o104 局2:首舰门与
        # strong-exit 接力把扩张连挡 ~260s,单矿被 723 波磨死。
        # 未转舰队 → 走原 O57 门,行为不变。
        if fleet_expand_holds(
            self._fleet_transitioned,
            self._first_fleet_seen(),
            self._defense_score(),
        ):
            return False
        # O57/o172/o175:o172 game_01 实证,FleetBeacon 工人被反复释放导致 pending
        # 为真但实体永远落不了地,原「present_or_pending」门被绕过,三矿照样开。
        # O175 改用 update 头部稳定信号:连续 5s 无真正实体才视为缺失,避免
        # pending 抖动一帧破防。
        if (
            self.ai.townhalls.amount >= 2
            and getattr(self, "_fb_truly_missing", False)
        ):
            return False
        _fleet_total = (
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST)
            + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER)
            + cy_unit_pending(self.ai, UnitID.TEMPEST)
            + cy_unit_pending(self.ai, UnitID.CARRIER)
        )
        return should_expand_dynamic(
            bases=self.ai.townhalls.amount,
            max_bases=ae.max_bases,
            nexus_pending=self.manager_mediator.get_building_counter[UnitID.NEXUS],
            supply_workers=self.ai.supply_workers,
            workers_per_base=ae.when_workers,
            own_army_supply=self.ai.supply_used - self.ai.supply_workers,
            enemy_army_supply=self._visible_enemy_army_supply(),
            advantage_supply=ae.advantage_supply,
            now=self.ai.time,
            first_expand_at=_first_expand_at,
            # B1(E9 停开矿的 Macro 适配):rush 恒停开;非 pivot 按 E9 threat 停;
            # pivot 模式 threat 不再停开,改「敌作战单位压到家 40 格 ≥2」才停
            # (rush 同款语义)——threat 在 Macro 局常驻,两轮 bench 二矿 700s+
            # 或开不出(one_base×5,单矿经济是天花板)。E9 塔拉满/地面混编不变。
            rush_active=expansion_blocked(
                rush_active=self._rush_active,
                threat_active=self._threat_active,
                pivot_active=self._pivot_tempest_mode(),
                enemy_near_home=sum(
                    1
                    for u in self.ai.enemy_units
                    if not u.is_structure
                    and is_combat_type(u.type_id)
                    and u.position.distance_to(self.ai.start_location) < 40
                )
                >= 2,
                bases=self.ai.townhalls.amount,  # O29:首扩(bases<=1)放行
            ),
            minerals=self.ai.minerals,
            fleet_total=_fleet_total,
        )

    def _auto_expand(self, macro_plan: MacroPlan) -> None:
        """自动开矿(flows.yml auto_expand,缺省关)。两种模式:
        旧式(stalker,没配 max_bases):到 at 秒 或 农民 ≥ when_workers 触发,一次扩到 to 个;
        动态(carrier,配了 max_bases):爆仓(农民 ≥ when_workers×当前基地数)或
        前线优势(我方 army supply ≥ 敌可见 army supply + advantage_supply)时逐矿 +1,
        rush_active 期间不开(E2,司令:有能力开到 4 矿,不设死 2 矿)。
        与司令 expand=yes 杠杆不冲突:到数后自然停。
        E3k:动态路径已上移到 plan 构建处(EC 排 UC 前+prioritize,见 update),
        这里只剩旧式。"""
        ae = self._flow.auto_expand
        if ae is None or ae.max_bases:
            return
        # B7③:rush_active 时禁扩张(动态路径的否决在 should_expand_dynamic,
        # 这里补旧式;stalker 没配 pivot → _rush_active 恒 False,基线行为不变)
        if self._rush_active:
            return
        if self.ai.townhalls.amount >= ae.to:
            return
        triggered = self.ai.time >= ae.at or (
            ae.when_workers and self.ai.supply_workers >= ae.when_workers
        )
        if not triggered:
            return
        macro_plan.add(ExpansionController(to_count=ae.to, max_pending=1))

    def _visible_enemy_army_supply(self) -> float:
        """敌可见作战单位的 supply 合计(E2 优势判据;排除农民/建筑,与 rush 判据同源)。"""
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        return sum(
            self.ai.calculate_supply_cost(u.type_id)
            for u in self.ai.enemy_units
            if not u.is_structure and u.type_id not in workers
        )

    def _visible_enemy_army_count(self) -> int:
        """敌可见作战单位数(E2 分矿塔数估算;口径同 _visible_enemy_army_supply)。"""
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        return sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and u.type_id not in workers
        )

    def _ensure_townhall(self) -> None:
        """保底主基地(Q4,全流派):基地被打爆到 0 时,出生点矿区还有价值(有矿)且脚下
        没敌军 → 立刻重建。没基地=没农民=慢性死亡;在建/已有/矿干/被压则 no-op。"""
        if self.ai.townhalls.amount > 0:
            return
        if self.manager_mediator.get_building_counter[UnitID.NEXUS] > 0:
            return
        if not self.ai.can_afford(UnitID.NEXUS):
            return
        minerals_left = sum(
            mf.mineral_contents
            for mf in self.ai.mineral_field.closer_than(10, self.ai.start_location)
        ) if self.ai.mineral_field else 0
        if minerals_left <= 0:
            # O15:主矿已干 → 不在原地重建,交 ExpansionController 找新矿点
            self.ai.register_behavior(
                ExpansionController(to_count=1, max_pending=1)
            )
            return
        if any(
            not u.is_structure
            and u.position.distance_to(self.ai.start_location) < 15
            for u in self.ai.enemy_units
        ):
            return  # 出生点被压着,重建白送
        # O93(o92 局1 实证):神族落位簿记只有 3x3/2x2 两种尺寸(protobuf 求解器
        # 不为 5x5 基地生成槽位)—— BuildStructure(NEXUS) 的落位请求恒返回
        # None(warning 刷屏 76 条,重建静默零进展)。走 ExpansionController
        # (自己的扩张选址逻辑,含安全/占位检查),与矿干分支同一路径。
        self.ai.register_behavior(
            ExpansionController(to_count=1, max_pending=1)
        )

    def _build_zerg_queens(self) -> None:
        """每个巢穴配一只女王(需孵化池;由 TechUp/ZERGLING 或 build 杠杆先造出)。
        ⚠️ 只造女王,**没做注卵(inject larva)** —— 注卵是 Zerg 爆兵核心,列 M2 剩余,需跑局。"""
        ai = self.ai
        queen = getattr(UnitID, "QUEEN", None)
        pool = getattr(UnitID, "SPAWNINGPOOL", None)
        if queen is None or pool is None:
            return
        if not self._structure_present_or_pending(pool):
            return  # 没孵化池造不了女王
        have = ai.units(queen).amount + self.manager_mediator.get_building_counter[queen]
        if have >= ai.townhalls.amount:
            return
        for th in ai.townhalls.ready.idle:
            if ai.can_afford(queen):
                th.train(queen)
                break

    def _structure_present_or_pending(self, structure_type: UnitID) -> bool:
        return (
            len(self.manager_mediator.get_own_structures_dict[structure_type]) > 0
            or self.manager_mediator.get_building_counter[structure_type] > 0
        )

    def _fb_ready_to_build(self) -> bool:
        """O197:判断 FleetBeacon 是否已到「该建却还没建」的节点。

        条件：FB 在 core 链上、至少一座星门已就绪、当前没有任何 FB 实体/pending。
        此时再追加 Gateway/塔会抢走 FB 的 300/200 资金窗,导致舰队转型失败。
        """
        if UnitID.FLEETBEACON not in self._flow.core_structure_ids():
            return False
        if self._structure_present_or_pending(UnitID.FLEETBEACON):
            return False
        stargates = self.manager_mediator.get_own_structures_dict[UnitID.STARGATE]
        return any(s.is_ready for s in stargates)

    def _dispatch_structure(
        self,
        sid,
        base_location,
        closest_to=None,
        max_on_route: int = 1,
        needs_power: bool = True,
        allow_borrow: bool = True,
        worker_origin=None,
        wall: bool = False,
        critical: bool = False,
    ) -> str:
        """O116-①(o115 局3/局5 实证):BuildStructure 的手动取证版 ——
        落位→选工→下单三段拆开,返回失败环节字符串;成功返回 "dispatched"。

        背景:「钱够槽够电够就是不建」三局实证,BuildStructure 静默返回
        False 无区分度。四类失败:taken(同型已在途)/ tech_not_ready /
        no_placement(落位请求 None)/ no_worker(GATHERING 池被协防+停气
        +建造抽干,select_worker 恒 None —— 局3 首塔 218→266 的主嫌)。
        no_worker 且 allow_borrow → 从停气池借(builder_borrow_ok;
        借出即从 _gas_stopped_tags 摘除,防 rush 解除的回气循环把建造工
        从建造点拽走)。失败环节由调用方写事件(下轮尸检直接读)。
        """
        if self.ai.not_started_but_in_building_tracker(sid) >= max_on_route:
            # O118-②(o117 局1/2/4 实证):taken 快回收 —— 条目工人已死立即清
            # (45s 周期对 190s 死局是 eternity);活着但闲置超 10s(被拽走/
            # 卡死)也清;活着走位中保留。防御窗的塔/科技等不起
            tracker = self.manager_mediator.get_building_tracker_dict
            for tag, info in list(tracker.items()):
                if info[TRACKER_ID] != sid:
                    continue
                w = self.ai.workers.find_by_tag(tag)
                if tracker_entry_stale(
                    w is not None,
                    w.is_idle if w is not None else False,
                    self.ai.time - info[TIME_ORDER_COMMENCED],
                ):
                    self.manager_mediator.get_building_counter[sid] -= 1
                    tracker.pop(tag)
            if self.ai.not_started_but_in_building_tracker(sid) >= max_on_route:
                return "taken"
        if self.ai.tech_requirement_progress(sid) < 0.85:
            return "tech_not_ready"
        # O139-②:O11 撤回冷却接入手动链(此前只 F2 读)—— 撤回后 10s 内
        # 不重派同型,防「派→钉→撤→下帧又派」循环
        # O147-①:关键三件(forge/首塔/GW1)豁免 —— 驻点等钱=钱到立刻开工,
        # 是 forge 准点的关键机制(O118 forge 95-110 靠钉点;O139 禁钉后
        # forge 漂回 125-155、forge→首塔 43s 空档,o146b 局1 实证)
        if not critical and not redispatch_cooled_down(
            getattr(self.ai, "_o11_released_at", {}).get(sid),
            self.ai.time,
            _DEFENCE_REDISPATCH_CD,
        ):
            return "cooldown"
        # O139-①(o137 两 lane 干等事件实证):手动派工链接入收入守卫(与 F2
        # 同判据 dispatch_viable)—— 到位时钱不够就不派(农民继续采矿);
        # O147-①:关键三件豁免(同上)
        if not critical and not dispatch_viable(
            self.ai.minerals,
            self._mineral_income_per_sec(),
            _DEFENCE_WALK_TIME,
            self.ai.calculate_cost(sid).minerals,
        ):
            return "not_viable"
        placement = self.manager_mediator.request_building_placement(
            base_location=base_location,
            structure_type=sid,
            within_psionic_matrix=needs_power,
            production=False,
            closest_to=closest_to,
            find_alternative=True,
            wall=wall,  # O136-①:坡口墙槽(主坡 3x3/墙位水晶)
        )
        if placement is None:
            return "no_placement"
        worker = self.ai.mediator.select_worker(
            # O119-②a(o118b 局1/局5 实证):入侵期从家里方向(基地中心)
            # 挑建造工,不从坡口入侵路径方向送死;None=落点就近(原行为)
            target_position=worker_origin if worker_origin is not None else placement,
            force_close=True,
        )
        if worker is None and allow_borrow and builder_borrow_ok(
            not self.manager_mediator.get_unit_role_dict.get(
                UnitRole.GATHERING, set()
            ),
            len(self._gas_stopped_tags),
        ):
            # O116-②:GATHERING 抽干 → 停气池借最近的建造工
            alive = {w.tag: w for w in self.ai.workers}
            candidates = [
                alive[t] for t in self._gas_stopped_tags if t in alive
            ]
            if candidates:
                worker = min(
                    candidates, key=lambda w: w.position.distance_to(placement)
                )
                self._gas_stopped_tags.discard(worker.tag)
        if worker is None:
            return "no_worker"
        self.ai.mediator.build_with_specific_worker(
            worker=worker, structure_type=sid, pos=placement
        )
        return "dispatched"

    def _slot_counts_at(self, base_location, size) -> tuple[int, int, int]:
        """O114-①(o113 局1 实证):(空闲且带电, 空闲, 总数) 槽口径 ——
        读 placement 簿记 + psionic matrix 过滤。簿记的 available 不含电力
        (局1:余 21/25 全不带电,SG 停滞 6 轮自救空转),下游门(槽让位/
        自救决策)必须读带电口径。簿记拿不到 → (99, 99, -1)(不挡任何闸)。"""
        placements = self.manager_mediator.get_placements_dict
        if not placements:
            return (99, 99, -1)
        bloc = min(
            placements.keys(), key=lambda k: k.distance_to(base_location)
        )
        slots = placements[bloc].get(size, {})
        free = [
            pos
            for pos, v in slots.items()
            if v.get("available") and not v.get("worker_on_route")
        ]
        pylons = self.manager_mediator.get_own_structures_dict[UnitID.PYLON]
        heights = self.ai.game_info.terrain_height.data_numpy
        powered = sum(
            1 for pos in free if cy_pylon_matrix_covers(pos, pylons, heights)
        )
        return (powered, len(free), len(slots))

    def _free_3x3_at(self, base_location) -> int:
        """O112:某基地空闲 3x3 槽数;O114-① 起为**带电**口径(空闲且通电)。"""
        return self._slot_counts_at(base_location, BuildingSize.THREE_BY_THREE)[0]

    def _total_3x3_at(self, base_location) -> int:
        """O112 尸检用:某基地 3x3 槽总数。"""
        placements = self.manager_mediator.get_placements_dict
        if not placements:
            return -1
        bloc = min(
            placements.keys(), key=lambda k: k.distance_to(base_location)
        )
        return len(placements[bloc].get(BuildingSize.THREE_BY_THREE, {}))

    def _main_free_3x3(self) -> int:
        """O112-①:主基空闲 3x3 槽数(_free_3x3_at 的主基便捷口径)。"""
        return self._free_3x3_at(self.ai.start_location)

    def _free_3x3_slots_at(self, base_location) -> list:
        """O113-①:某基地 3x3 槽 [(x, y, free), ...] —— 贴槽落水晶的锚点源。"""
        placements = self.manager_mediator.get_placements_dict
        if not placements:
            return []
        bloc = min(
            placements.keys(), key=lambda k: k.distance_to(base_location)
        )
        return [
            (pos.x, pos.y, v.get("available") and not v.get("worker_on_route"))
            for pos, v in placements[bloc].get(
                BuildingSize.THREE_BY_THREE, {}
            ).items()
        ]

    async def _build_core_structure(
        self, structure_id: UnitID, base: Point2 | None = None
    ) -> None:
        """Here to prevent repeated logic building core structures.
        O112-②:base 可选指定落位基地(科技落分矿),None=主基(原行为)。

        Parameters
        ----------
        structure_id : UnitTypeId
            What we want to build
        """
        # O216i(o216h-lane2 game_01 实证):Zerg Timing 前期(300s 前)主基 2 塔
        # 未就绪时 STARGATE/FLEETBEACON 让位塔链 —— SG 在 0 塔窗口抢走 150 矿,
        # 306s 波到脸时 0 塔被推平;舰队科技晚 ~60s 不影响成型窗。
        if (
            structure_id in (UnitID.STARGATE, UnitID.FLEETBEACON)
            and self._opp_race == "zerg"
            and self._ai_build == "timing"
            and self.ai.time < 300.0
            and self._cannons_ready_peak < 2
            and not self._fleet_transitioned
        ):
            return
        if (
            not self._structure_present_or_pending(structure_id)
            and self.ai.tech_requirement_progress(structure_id) >= 1.0
            and self.ai.can_afford(structure_id)
        ):
            self.ai.register_behavior(
                BuildStructure(base or self.ai.start_location, structure_id)
            )

    def _build_probes(self, ready_townhalls: Units) -> None:
        """Add probes.

        Parameters
        ----------
        ready_townhalls : Units
            Current ready nexuses we can train from.
        """
        # O236(o229 胜局 vs o234 败局对照):二矿时点 ≤400s=胜、≥500s=负。
        # Nexus 钉点期间探机(50 矿/个)是最大抽血源之一,暂停探机把 400 矿
        # 资金窗让给 Nexus;18+ 农民已够当前矿线, pinning 解除自动恢复。
        # O238(o237-lane1 game_01 实证):钉点反复发生(二矿/三矿/四矿),每次都
        # 停探机 = 累计农民缺口(峰值 44 vs 胜局 63-71)。只限首扩钉点(bases<2),
        # 三矿以上钉点照产探机,经济不再被掐尖。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and self.ai.townhalls.amount < 2
            and self.ai.not_started_but_in_building_tracker(UnitID.NEXUS) > 0
            and self.ai.workers.amount >= 18
        ):
            return
        # O240:航母攒钱期探机(50 矿/个)同样让位,与产线暂停同口径。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and not self._transition_active
            and self.ai.vespene >= 800.0
            and getattr(self, "_fb_entities_now", 0) > 0
            and (
                self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER)
                + cy_unit_pending(self.ai, UnitID.CARRIER)
            )
            < max(
                1,
                self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST)
                // 6,
            )
        ):
            return
        # O225(o222-lane2 game_03 实证):FB 停滞自救 60 次全 no_money ——
        # 探机 35→42 连续训练(50 矿/个)把 FB 的 300 矿资金窗吃光,
        # fleet 0 到 800s 败亡。SG 就绪 + FB 无实体 + 舰队 0 + 农民 ≥28
        # → 暂停探机,矿全部让给 FB(农民 28+ 已超双矿饱和线的 87%)。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and getattr(self, "_fb_entities_now", 1) == 0
            and not self._first_fleet_seen()
            and self.ai.workers.amount >= 28
            and any(
                s.is_ready
                for s in self.manager_mediator.get_own_structures_dict[
                    UnitID.STARGATE
                ]
            )
        ):
            return
        # O294-①(o293a game_04 实证):forge 随分矿阵亡后,150 矿重建资金窗
        # 被探机+叉子吃干,塔链 tech_not_ready 80s+、塔 8→0 连锁丢基。
        # 无就绪 forge + 急性防御 + 矿不够 forge → 探机让位资金窗(自校正)。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and forge_rebuild_probe_yield(
                forge_ready=any(
                    s.is_ready
                    for s in self.manager_mediator.get_own_structures_dict[
                        UnitID.FORGE
                    ]
                ),
                defense_acute=(self._threat_active or self._rush_active),
                minerals=self.ai.minerals,
                forge_price=self.ai.calculate_cost(UnitID.FORGE).minerals,
            )
        ):
            return
        # O295-③(o294a game_02 实证):O218 追加星门钉点 100+ 帧不落地 ——
        # 钉点无资金预留,150 矿窗被探机(50/个)帧级抢走(与 O236 Nexus
        # 钉点同型)。SG 钉点未开工 + 矿不够 SG → 探机让位资金窗(自校正:
        # SG 开工/矿够即恢复)。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and self.ai.not_started_but_in_building_tracker(UnitID.STARGATE) > 0
            and self.ai.minerals
            < self.ai.calculate_cost(UnitID.STARGATE).minerals
        ):
            return
        # 农民上限随基地数放大：每矿 ~22（16 矿 + 6 气），封顶 70 给军队留供给。
        # 单矿时 22*1=22 与旧行为一致；开二矿后目标自动抬到 44，接着补农民采矿采气。
        if (
            self.ai.supply_workers < min(70, 22 * self.ai.townhalls.amount)
            and self.ai.can_afford(UnitID.PROBE)
            and self.ai.supply_left > 0
        ):
            if idle_ths := ready_townhalls.idle:
                for nexus in idle_ths:
                    nexus.train(UnitID.PROBE)

    async def _build_flow_structures(
        self,
        building_counter: dict[UnitID, int],
        structures_dict: dict[UnitID, list[Unit]],
        core_allowed: bool = True,
    ) -> None:
        """按当前流派的 core_structures 爬科技链(flows.yml 配置驱动)。
        core_allowed=False(O43 开矿预留)→ 只补气和 pylon 前置,核心科技让位 Nexus。

        building_counter : Dict[UnitTypeId, int]
            What is currently pending in the building tracker
        structures_dict : Dict[UnitTypeId, Units]
            Data structure of current buildings.
        """
        # 气随基地数放大：每个已建好的基地采满 2 个气矿（吃气大户流派的命脉）。
        # 前期没兵营时先只开 1 个气（保持原起手节奏）。
        # O165:本机 SC2 环境 Protoss 开局只有 8 农民,过早下气矿(24s)会拖慢
        # pylon/gate/cyber 节奏;农民<12 且兵营未好前不开气,把矿留给建筑和农民。
        # ⚠️ structures_dict 是 defaultdict,只要被访问过 key 就会存在,
        # 所以不能用 `UnitID.GATEWAY in structures_dict`,要用 len>0 判断。
        _have_gateway = len(structures_dict.get(UnitID.GATEWAY, [])) > 0
        if _have_gateway:
            max_gas_buildings = 2 * self.ai.townhalls.ready.amount
        else:
            # O167b:8 农民开局矿极紧，兵营落地前连 1 气都别开，
            # 把 75 矿留给 Pylon/Gateway/Cybercore 科技链。
            max_gas_buildings = 0
        # O17x:核心科技缺失期 further 收紧气矿——Cybercore 未排队前完全不下气矿，
        # 把 75 矿和农民彻底留给 Pylon/Gateway/Cybercore;Cybercore 排队/就绪后
        # 才允许 1 气，为 Stargate 蓄气但不抢科技链资金。
        if self._early_core_missing:
            if self._structure_present_or_pending(UnitID.CYBERNETICSCORE):
                max_gas_buildings = min(max_gas_buildings, 1)
            else:
                max_gas_buildings = 0
        # O124-②(o123 局1 实证):过渡期不建新气矿 —— 叉海不吃气,
        # 每个气矿 75-150 矿是 forge/GW/叉的钱;退出后自动恢复
        # O187:Zerg Timing/Rush 例外 —— 舰队科技(Stargate/FleetBeacon)需要气,
        # 若 transition 全程锁气,星门永远落不了地,transition 退出后 100-200s
        # 无舰队。允许下气矿但保留 max_gas_buildings 上限,不抢前期防御资金。
        _gas_paused = transition_pauses_gas(self._transition_active) and not (
            self._opp_race == "zerg" and self._ai_build in ("rush", "timing")
        )
        # O299-③(o298b game_03 实证):rush 确认后 forge/首塔资金窗仍被新
        # 气矿(75 矿/个)抢 —— forge 220s 等钱、首塔 249s 才落成,249s
        # 农民 24→7 崩盘。ZT rush 确认且 forge 未就绪 → 暂停新气矿
        # (75 矿=半个塔/半个 forge),forge 就绪自动恢复。
        # O300-②(o299a game_01 实证):接触确认(~290s)太晚 —— 首塔 203.6s
        # 等钱时双气已在跑(气 444+),确认前资金窗早被吃。扩到 presumed
        # (55s 起):forge 准点(95-110s)时气矿窗本来就在 100s+,误伤极小;
        # forge 晚点时新气矿让位正是本意。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and (self._rush_confirmed or getattr(self, "_presumed_rush", False))
            and not any(
                s.is_ready
                for s in self.manager_mediator.get_own_structures_dict[UnitID.FORGE]
            )
        ):
            _gas_paused = True
        if (
            self.ai.gas_buildings.amount < max_gas_buildings
            and not _gas_paused
        ):
            self._build_gas()

        ready_pylons: list[Unit] = [
            p for p in structures_dict[UnitID.PYLON] if p.is_ready
        ]
        if not ready_pylons:
            return

        # O55(o53/o54 连败实证):核心科技「想建建不了」自救 —— TechUp 与
        # _build_core_structure 双双尝试无进展 = 生产区无电(3x3 不在水晶覆盖内,
        # 水晶被 O38 锚去了坡口/矿区)。首个缺失且买得起的科技连续 >20s 无进展
        # → 在科技点补一根水晶恢复供电,之后科技自然能落位。
        # O55b:必须放在 core_allowed 早退之前 —— 开矿持有期(_expand_holding)
        # 冻科技链时也冻了自救,而停滞恰恰常发生在持有期(三矿 pending 期间
        # gateway/CC 双双卡壳,195-394 实证)。
        missing_sid = next(
            (
                sid for sid in self._flow.core_structure_ids()
                # O92:冻结中的建筑不算"缺失"(故意不建,不是停滞)
                if not transition_tech_frozen(self._transition_active, sid.name)
                and not self._structure_present_or_pending(sid)
            ),
            None,
        )
        if (
            missing_sid is not None
            and self.ai.can_afford(missing_sid)
            and missing_sid == getattr(self, "_tech_stall_id", None)
            and self.ai.time - getattr(self, "_tech_stall_since", 0.0) > 20.0
        ):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, UnitID.PYLON)
            )
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": f"O55:科技{missing_sid.name}停滞>20s,补供电水晶",
            })
            self._tech_stall_since = self.ai.time  # 一根一根来,过 20s 再评
        else:
            self._tech_stall_id = missing_sid
            self._tech_stall_since = self.ai.time

        # O294-③(o293a game_04 实证):舰队基建(SG 642s/FB 679s 随分矿阵亡)
        # 被拆后到判负 100s+ 零重建 —— 开矿持有冻核心链(core_allowed=False
        # 早退)、FB 重建闸要就绪 SG、威胁让位闸三层堵死,878 气烂银行。
        # ZT 且舰队曾成型(first_fleet_seen=基建曾存在,开局不误触发)→
        # cyber→SG→FB 链式钉点补建,放在 core_allowed 早退之前(同 O55b
        # 理由:冻结期恰恰是最需要自救的窗口)。critical 钉点等钱=钱到即开工;
        # _dispatch_structure 自带 taken/tech 闸,重复调用安全。
        if (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            and fleet_infra_rebuild_active(self._first_fleet_seen(), self.ai.time)
        ):
            _rebuild_sid = None
            if not self._structure_present_or_pending(UnitID.CYBERNETICSCORE):
                _rebuild_sid = UnitID.CYBERNETICSCORE
            elif not self._structure_present_or_pending(UnitID.STARGATE):
                _rebuild_sid = UnitID.STARGATE
            elif (
                not self._structure_present_or_pending(UnitID.FLEETBEACON)
                and any(s.is_ready for s in structures_dict[UnitID.STARGATE])
            ):
                _rebuild_sid = UnitID.FLEETBEACON
            if _rebuild_sid is not None:
                _rc = self._dispatch_structure(
                    _rebuild_sid, self.ai.start_location, critical=True
                )
                if _rc == "dispatched":
                    self.ai._events.append({
                        "t": round(self.ai.time, 1),
                        "msg": f"O294:舰队基建重建钉点={_rebuild_sid.name}",
                    })

        if not core_allowed:
            # O163(o162-vh-zerg-power game_01 实证):经济开局(CarrierOpener)把
            # first_expand_at 压到 150s,想开矿期间 core_allowed=False 导致 GATEWAY
            # 也被冻结;到 4 分半仍零科技、零兵,被 Power 中局波次直接碾穿。
            # 解冻首 GATEWAY:即使持有期也要拍下兵营,保证起码的地面产能和防御。
            if not self._structure_present_or_pending(UnitID.GATEWAY):
                await self._build_core_structure(UnitID.GATEWAY)
            # O307-①(o306c game_03/05 实证):holding 期放行 CYBERNETICSCORE ——
            # 仅 50 矿(Nexus 的 1/8),却是追猎/星门链总开关;两局败局气烂
            # 700-1300 零追猎。兵营就绪才建(链序不乱),限 Zerg Timing。
            if (
                holding_allows_cyber(
                    self._opp_race == "zerg" and self._ai_build == "timing",
                    any(s.is_ready for s in structures_dict[UnitID.GATEWAY]),
                )
                and not self._structure_present_or_pending(UnitID.CYBERNETICSCORE)
            ):
                await self._build_core_structure(UnitID.CYBERNETICSCORE)
            # O215:Zerg Timing 开矿持有期仍允许 FleetBeacon——Nexus 在建时 FB
            # 被冻是舰队成型过晚的主因。此处只放行 FB,其它核心科技继续让位。
            if self._is_zerg_timing_fb_exempt():
                if (
                    not self._structure_present_or_pending(UnitID.FLEETBEACON)
                    and [s for s in structures_dict[UnitID.STARGATE] if s.is_ready]
                ):
                    await self._build_core_structure(UnitID.FLEETBEACON)
            return

        # O186:Zerg Timing/Rush 的 ground_spawn 延长到 500s,若仍冻结星门/航标,
        # 则 transition 退出后要花 100-200s 补舰队科技,被中局波次直接碾穿。
        # 这里改为不冻结舰队科技,仅由 ground_spawn 把舰队单位产出压到 500s,
        # 确保星门/航标提前就绪,transition 一退就能立刻转舰队。
        _zerg_rush_timing_fleet_tech = (
            self._opp_race == "zerg"
            and self._ai_build in ("rush", "timing")
            and self._transition_active
        )
        for structure_id in self._flow.core_structure_ids():
            # O92:过渡形态冻结星门/舰队航标(地面产能优先;CYBERNETICSCORE 保留,
            # 追猎要它)。已 pending 的不取消(冻结只拦新建),转舰队后自动解冻补建。
            # O186:Zerg Timing/Rush 例外——让舰队科技提前落成。
            if (
                transition_tech_frozen(self._transition_active, structure_id.name)
                and not (
                    _zerg_rush_timing_fleet_tech
                    and structure_id.name in ("STARGATE", "FLEETBEACON")
                )
            ):
                # O121-③(o120 局2/3/4 实证):防御评分达标(strong 同口径)→
                # SG 过渡期提前解冻 —— 退出时链上只剩 FB,空窗 190s→~100s;
                # FB 维持冻结(舰队本体不提前,波次资源仍优先生存)
                if not (
                    structure_id == UnitID.STARGATE
                    and transition_stargate_allowed(
                        self._transition_active, self._defense_score()
                    )
                ):
                    continue
            # O127-①(数据终裁,恢复 O118-②):防御紧急且 forge 未拍 →
            # 首兵营让位 forge;forge 一拍下 GW1 即紧随,不互抢
            if (
                structure_id == UnitID.GATEWAY
                and self._flow.transition is not None
                and forge_before_first_gateway(
                    self._defense_urgent,
                    self._structure_present_or_pending(UnitID.FORGE),
                    # O308-①:Zerg Timing 豁免(GW1 先拍,首叉 ~180s)
                    self._opp_race == "zerg" and self._ai_build == "timing",
                )
            ):
                continue
            if structure_id == UnitID.FLEETBEACON:
                # O213:power/macro 风格下,单基地且无 Nexus pending/在建时,
                # FB 让位二矿——O212 Lane1 game_03 实证:FB 抢先派工吸走 300 矿,
                # 首座 Nexus 拖到 466s 才落成,经济崩盘。先把二矿拍下去再舰队。
                if (
                    self._ai_build in ("power", "macro")
                    and self.ai.townhalls.amount == 1
                    and not self._structure_present_or_pending(UnitID.NEXUS)
                ):
                    continue
                # 特例:tech_requirement_progress 对舰队航标不准,需有就绪星门才建
                # O67(Terran Rush game_01 实证):E9 威胁期 FB(300 矿)让位塔链 ——
                # 敌压境窗口里 FB+追加星门抢光塔钱,0 塔基地被推平(3→2→1 连锁)。
                # O207:FB 已被摧毁且已转舰队时，舰队是唯一翻盘手段，威胁期也
                # 必须重建 FB；F2 目标已被 _fb_waiting 压到保命底限。
                # O209:Zerg Timing 在 transition 内若星门已就绪且 t≥360s，
                # 即使威胁期也允许建 FB——拖延 FB 是导致 FleetBeacon 过晚/不建、
                # 舰队无法成型的主因。 timing 波次间隙足够让 FB 落成。
                _fb_truly_missing = getattr(self, "_fb_truly_missing", False)
                _timing_fb_gate = (
                    self._opp_race == "zerg"
                    and self._ai_build == "timing"
                    and self._transition_active
                    # O216f:科技链 sprint 期间可建后,星门/FB 能提前到 200-250s
                    # 落成;把 FB 门从 280 降到 200,匹配新窗口,避免 FB 被 threat
                    # 门卡到 500s+。
                    and self.ai.time >= 200.0
                )
                if (
                    not self._structure_present_or_pending(UnitID.FLEETBEACON)
                    and [s for s in structures_dict[UnitID.STARGATE] if s.is_ready]
                    and (
                        not tech_yields_to_threat(
                            self._threat_active, self._rush_active
                        )
                        or (self._fleet_transitioned and _fb_truly_missing)
                        or _timing_fb_gate
                    )
                ):
                    # O259(o258 双 lane 0-10 尸检):ZT 直爬路线 FB 帧级抢钱
                    # 连败 —— game_02:FB 380s 起派,no_money 反复,667s 才落
                    # (Nexus/塔/农民每帧抽走 300 矿窗),首舰拖到 788s。
                    # O228 的钉点派工(驻点等钱=钱到立刻开工)从重建窗扩到
                    # ZT 直爬;威胁让位闸(threat/rush)不变。
                    # O276(A 方向结构改):FB 钉点等首艘虚空 —— SG 就绪即钉 FB
                    # 会把 O261 死窗虚空永远堵死(FB pending 整窗);虚空是
                    # 死窗波(零对空)的唯一真实战力。首艘虚空在产/就绪,或
                    # t≥320(等不起的兜底)才钉 FB;舰队成型只晚 ~30s。
                    if self._opp_race == "zerg" and self._ai_build == "timing":
                        _voids_now = (
                            self.manager_mediator.get_own_unit_count(
                                unit_type_id=UnitID.VOIDRAY
                            )
                            + cy_unit_pending(self.ai, UnitID.VOIDRAY)
                        )
                        if _voids_now >= 1 or self.ai.time >= 320.0:
                            self._dispatch_structure(
                                UnitID.FLEETBEACON,
                                self.ai.start_location,
                                critical=True,
                            )
                    else:
                        await self._build_core_structure(UnitID.FLEETBEACON)
            else:
                await self._build_core_structure(structure_id)

    def _morph_gateways(self) -> None:
        """WARPGATERESEARCH 完成后,把就绪空闲的 gateway 变形为 warpgate。

        关键背景(B2 baseline 0-10 的根因):ares `SpawnController.execute` 在 warpgate
        研究完成后,只要还有就绪空闲的 gateway 就 `return False` —— 主动停产等变形;
        而 vendored ares 全框架**没有**现成的变形行为,不下 MORPH_WARPGATE 的话,
        生产从研究完成那一刻起永久停摆。没研究(默认流派不含该升级)时 no-op。"""
        if UpgradeId.WARPGATERESEARCH not in self.ai.state.upgrades:
            return
        for gateway in self.manager_mediator.get_own_structures_dict[UnitID.GATEWAY]:
            if gateway.is_ready and gateway.is_idle:
                gateway(AbilityId.MORPH_WARPGATE)

    def _build_gas(self, near: Unit | None = None) -> None:
        """在离某个基地最近的空气矿上建一个气矿厂（自动选农民）。含分矿的气矿。
        near: 指定只建该基地 15 格内的气矿(O13 按基地补气);None=全局最近的。
        O26:去掉全局 assimilator!=0 一票否决(原 forcing 串行 → 3 矿双气被锁、
        气断航母补充不上),改由 _ensure_expansion_gas 的 have+pending<2 按基地
        自控 + can_afford 守卫 + assimilator_attempt_stuck 反卡死兜底。"""
        if (
            not self.ai.can_afford(UnitID.ASSIMILATOR)
            or not self.ai.townhalls
        ):
            return
        ref = near.position if near is not None else self.ai.start_location
        geysers: Units = self.ai.vespene_geyser.filter(
            lambda vg: not self.ai.gas_buildings.closer_than(2, vg)
            and vg.distance_to(ref) < 15
        )
        if not geysers:
            return
        if worker := self.ai.mediator.select_worker(target_position=ref):
            self.ai.mediator.build_with_specific_worker(
                worker=worker,
                structure_type=UnitID.ASSIMILATOR,
                pos=cy_closest_to(ref, geysers),
            )
            self.ai.mediator.assign_role(tag=worker.tag, role=UnitRole.BUILDING)

    def _ensure_expansion_gas(self) -> None:
        """O13:每个就绪基地必须双气满采 —— 气矿优先级高于一切矿物开销(司令拍板),
        每帧在 _build_extra_production/_spend_bank 之前调用,矿再富也得先把气买上。
        反卡死:在建气矿超 45s 没落地(工人被截/建造点被压) → 拆 tracker 重派
        (e3i game_01 实证:二矿 420s 无气,矿 6075 气 0)。rush 期间不调用(可缓)。"""
        # 反卡死:清超龄的在建气矿尝试(镜像 ares 计数维护)
        now = self.ai.time
        tracker = self.manager_mediator.get_building_tracker_dict
        for tag, info in list(tracker.items()):
            if info[TRACKER_ID] == UnitID.ASSIMILATOR and assimilator_attempt_stuck(
                now, info[TIME_ORDER_COMMENCED]
            ):
                self.manager_mediator.get_building_counter[
                    UnitID.ASSIMILATOR
                ] -= 1
                tracker.pop(tag)
        # O165-fix:defaultdict 的 key 被访问过即存在,用 len 判是否存在建筑。
        if (
            len(self.manager_mediator.get_own_structures_dict.get(UnitID.GATEWAY, []))
            == 0
        ):
            return  # 起手单气节奏归 _build_flow_structures,这里只管"有兵营后双气满采"
        # 在建气矿的落点(算各基地 pending 数用)
        pending_at = [
            info[TARGET].position
            for info in tracker.values()
            if info[TRACKER_ID] == UnitID.ASSIMILATOR and info.get(TARGET)
        ]
        for th in self.ai.townhalls.ready:
            have = self.ai.gas_buildings.closer_than(15, th).amount
            pending = sum(1 for p in pending_at if th.position.distance_to(p) < 15)
            if have + pending < 2:
                self._build_gas(near=th)

    def _ensure_expansion_pylon(self) -> None:
        """O79(o78d 实证):每个就绪基地保底 2 根 pylon(矿区 12 格内) —— 分矿
        电力基础设施跟 Nexus 走,不等防御注册(t=267)再补(t=290 才有电)。

        分矿恒 0-1 塔悬案的根底层:无电 → within_psionic_matrix 下所有塔落位
        返回 None。防御激活时塔要能立刻起建(t=267 接触前 ~200s 窗 = 4-6 塔,
        晚一秒都是命)。在建(pending)也算数,防每帧重复注册。
        O115-②(o114 局3 实证):在建 Nexus 同步供电 —— 局3 分矿 482 失守时
        0 塔:水晶等 Nexus 落成才开始,再落后 80-100s(工人走路+被截),
        塔链全程没赶上波次。与 Nexus 并行 → 落成即有电、塔立刻起建。
        O168:8 农民 carrier 核心科技缺失期间不铺保底水晶，把矿留给科技链。
        """
        if (
            getattr(self, "_early_core_missing", False)
            and not (
                self._opp_race == "zerg" and self._ai_build == "timing"
            )
        ):
            return
        tracker = self.manager_mediator.get_building_tracker_dict
        pending_at = [
            info[TARGET].position
            for info in tracker.values()
            if info[TRACKER_ID] == UnitID.PYLON and info.get(TARGET)
        ]
        # O115-②:供电目标 = 就绪基地 + 在建 Nexus 落点(并行建,不等落成)
        _targets = [th.position for th in self.ai.townhalls.ready]
        for info in tracker.values():
            if info[TRACKER_ID] == UnitID.NEXUS and info.get(TARGET):
                _targets.append(info[TARGET].position)
        for th_pos in _targets:
            have = self.ai.structures.ready.closer_than(12, th_pos).filter(
                lambda s: s.type_id == UnitID.PYLON
            ).amount
            pending = sum(1 for p in pending_at if th_pos.distance_to(p) < 12)
            if have + pending < 2 and self.ai.can_afford(UnitID.PYLON):
                # O79c:分矿 pylon 朝敌侧落位 —— 塔贴着它建(O38 精神),
                # 既供电又保塔在迎敌正面(不再是矿线背后)。
                _anchor = base_defense_anchor(
                    False,
                    (th_pos.x, th_pos.y),
                    (self.ai.focused_enemy_start().x, self.ai.focused_enemy_start().y),
                )
                self.ai.register_behavior(
                    BuildStructure(
                        th_pos, UnitID.PYLON, max_on_route=1,
                        closest_to=Point2(_anchor) if _anchor else None,
                        find_alternative=True,
                    )
                )

    def _ensure_expansion_wall_gateway(self) -> None:
        """O216:分矿 gateway 堵口——司令指示分矿 ramp 前/路口排一个兵营顶前,
        后方密集光子塔防守。只针对 Zerg Timing(当前最劣对局),在分矿 Nexus
        在建或就绪后,于其迎敌侧补一座 gateway,作为墙体/诱饵让塔集火。
        """
        if self._opp_race != "zerg" or self._ai_build != "timing":
            return
        # O216:即使 early_core_missing 也允许分矿 gateway 堵口,
        # 它与 cybercore/stargate/FB 是并行防御投资,不抢核心科技资金。
        if not self.ai.can_afford(UnitID.GATEWAY):
            return
        # O216c:Nexus 尚未开工时,gateway 150 矿可能把 Nexus 基金从 400+
        # 吃回 250+,导致二矿继续拖延。先保证 Nexus 能落地,再补 gateway。
        _nexus_unstarted = self.ai.not_started_but_in_building_tracker(
            UnitID.NEXUS
        )
        _nexus_price = self.ai.calculate_cost(UnitID.NEXUS).minerals
        if (
            _nexus_unstarted > 0
            and self.ai.minerals < _nexus_price + 150.0
        ):
            return
        # 找分矿落点:就绪基地中离主基最远的,或在建 Nexus 的目标位置
        _targets: list[Point2] = []
        _start = self.ai.start_location
        _ready = sorted(
            [th.position for th in self.ai.townhalls.ready],
            key=lambda p: p.distance_to(_start),
        )
        if len(_ready) >= 2:
            _targets.append(_ready[-1])
        tracker = self.manager_mediator.get_building_tracker_dict
        for info in tracker.values():
            if info[TRACKER_ID] == UnitID.NEXUS and info.get(TARGET):
                _targets.append(info[TARGET].position)
        if not _targets:
            return
        _enemy = self.ai.focused_enemy_start()
        _pending_at = [
            info[TARGET].position
            for info in tracker.values()
            if info[TRACKER_ID] == UnitID.GATEWAY and info.get(TARGET)
        ]
        for th_pos in _targets:
            # 该基地 10 格内是否已有 gateway/warpgate(就绪或在建)
            _have = (
                self.ai.structures.ready.closer_than(10, th_pos).filter(
                    lambda s: s.type_id in (UnitID.GATEWAY, UnitID.WARPGATE)
                ).amount
                + sum(1 for p in _pending_at if th_pos.distance_to(p) < 10)
            )
            # O277-④(司令观察):单兵营堵口挡不住蟑螂大军 —— 兵营血厚便宜,
            # 分矿口墙件 1→2(双兵营+塔阵+电池构成主防区);
            # 多出来的兵营后段照常当产能,不浪费。
            _wall_want = 2 if self.ai.townhalls.ready.amount >= 2 else 1
            if _have >= _wall_want:
                continue
            # O268-①(o267a-g03 实证):BuildStructure 在途不落 tracker TARGET,
            # _pending_at 恒查不到 → 每帧重注册+刷事件(80s+ 空转几百次,
            # 墙件实际没多建)。按落点 latch:派过就记,45s 后仍未落成才重派。
            _wlatch = getattr(self, "_o216_dispatched", None)
            if _wlatch is None:
                _wlatch = self._o216_dispatched = {}
            _key = (round(th_pos.x), round(th_pos.y))
            if self.ai.time - _wlatch.get(_key, -999.0) < 45.0:
                continue
            _anchor = base_defense_anchor(
                False,
                (th_pos.x, th_pos.y),
                (_enemy.x, _enemy.y),
                forward=4.0,
            )
            if _anchor is None:
                continue
            self.ai.register_behavior(
                BuildStructure(
                    th_pos,
                    UnitID.GATEWAY,
                    max_on_route=1,
                    closest_to=Point2(_anchor),
                    find_alternative=True,
                )
            )
            _wlatch[_key] = self.ai.time
            self.ai._events.append({
                "t": round(self.ai.time, 1),
                "msg": "O216:分矿 gateway 堵口",
            })
            break  # 每帧只派一座,避免抢矿

    def _build_extra_production(self, structures_dict: dict[UnitID, list[Unit]]) -> None:
        """矿有富余时按流派配置追加产兵建筑（治"矿堆花不出去"）。
        得先有第一个同类建筑（核心科技就位）才追加。GATEWAY 特例:升级成 WARPGATE
        后类型变了,两者都算产能。
        E2 气体闸门:星门目标数 = min(cap, 满采气基地数 + 1)——1 个满采气基地(2 个
        ready assimilator)≈ 养 1 个星门全力产航母;+1 是司令口径(气有存款可爆兵、
        风暴耗气更慢,产能可略超稳态气收入)。超出的不加
        (单矿 cap 6 是摆设,瓶颈是气;存款改由 _spend_bank/动态开矿去开矿)。"""
        ep = self._flow.extra_production
        if ep is None:
            return
        # O134-①(o133 局2 实证):非过渡地面保底的兵营产能位 —— 局2 单 GW
        # 拖到 ~350 才落地(核心链被塔/水晶/研究挤),floor 有配方无产能,
        # 525 波到脸仅 1 叉。pre_fleet 流派(现仅 carrier)非过渡期保底 2 GW;
        # 过渡激活后由过渡 gateway_cap 接管(不双管)。矿够就拍,不等矿门槛
        # O144-③:floor 未激活(纯运营局)→ 不保底 GW2(矿全进舰队科技)
        if (
            self._floor_active
            and ground_floor_gateways(
                self._flow.pre_fleet is not None,
                self._transition_active,
                len(structures_dict[UnitID.GATEWAY])
                + self.manager_mediator.get_building_counter[UnitID.GATEWAY]
                + len(structures_dict.get(UnitID.WARPGATE, [])),
            )
            and self.ai.can_afford(UnitID.GATEWAY)
        ):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, UnitID.GATEWAY)
            )
            return
        # O92:过渡形态期追加产能从星门改兵营(cap=transition.gateway_cap;
        # 不追加星门 —— 星门已冻,追它是无科技可用的死钱)。矿门槛沿用 ep.mineral_gate。
        # O101-Z(o100 局2/4/5 实证):舰队重建窗(转舰队→首舰)同样保兵营 ——
        # 窗内地面保底叉/追猎是 590-650 波的唯一答案(局4 兵营被打掉不补,
        # 4 叉+4 塔顶 30+ supply);首舰出场后恢复星门追加。
        _rebuild_win = self._flow.transition is not None and fleet_rebuild_window(
            self._fleet_transitioned, self._first_fleet_seen()
        )
        tr = (
            self._flow.transition
            if (self._transition_active or _rebuild_win)
            else None
        )
        if tr is not None:
            # O115-①(o114 局3 实证):重建窗内 FB 已拍且 SG<3 → 追加 STARGATE
            # 爬坡(局3 窗内一律 GATEWAY → SG 恒 1,产能爬坡断档);过渡期/
            # 其他情况仍 GATEWAY(地面保底)
            sid = getattr(
                UnitID,
                rebuild_extra_production_id(
                    _rebuild_win,
                    self._structure_present_or_pending(UnitID.FLEETBEACON),
                    len(structures_dict[UnitID.STARGATE])
                    + self.manager_mediator.get_building_counter[UnitID.STARGATE],
                ),
            )
            if sid == UnitID.GATEWAY:
                # O99-①/O102-①:GW2/GW3 等首 2 塔(已有+在建);GW1 与 forge 并行;
                # O112-①:GW3 还要给科技槽让位(主基 3x3 余量 <2 不拍);
                # O126-①:GW2+ 等首叉在产/出场(GW 链不抢现役兵营的首叉矿)
                _gw_have = (
                    len(structures_dict[UnitID.GATEWAY])
                    + self.manager_mediator.get_building_counter[UnitID.GATEWAY]
                    + len(structures_dict.get(UnitID.WARPGATE, []))
                )
                if gateway_chain_after_first_zealot(
                    _gw_have,
                    self.manager_mediator.get_own_unit_count(
                        unit_type_id=UnitID.ZEALOT
                    )
                    > 0
                    or cy_unit_pending(self.ai, UnitID.ZEALOT),
                ):
                    return
                # O133-②:timing 冲刺期科技槽让位旁路(GW3 优先,波必来)
                if not self._timing_sprint and gateway_yields_tech_slots(
                    _gw_have, self._main_free_3x3()
                ):
                    return
                if not transition_gateway_allowed(
                    _gw_have,
                    # O132-③:峰值口径 —— 塔损不反锁兵营链(o131 timing 局1)
                    self._cannons_peak,
                ):
                    return
        else:
            sid = getattr(UnitID, ep.id_name, None)
        if sid is None:
            return
        # O216d(O216c-vh-zerg-timing 0-9 实证):FleetBeacon 实体落成之前,
        # 追加星门会抢走 300/200 的 FB 资金窗,导致 3-4 星门空转、气体烂银行、
        # 舰队转型永远完不成。先拍完 FB(实体)再爬坡;FB 被摧毁后同理先重建。
        # O216e(o216d-vh-zerg-timing game_01/02 实证):FB 实体落成后仍不能追加 SG,
        # 必须等首艘舰队单位(Tempest/Carrier)已在产/已出,否则 3 星门空转、
        # pre_fleet 地面 floor 把资源吃干,首舰永远出不来。
        if (
            sid == UnitID.STARGATE
            and UnitID.FLEETBEACON in self._flow.core_structure_ids()
            and (
                self._fb_entities_now == 0
                or not self._first_fleet_seen()
            )
        ):
            return
        # P2:pivot 模式(风暴主 C)产能解放——豁免矿门槛+气体闸门放宽;
        # 非 pivot 时三处判据全走默认值,行为零变化
        pivot = self._pivot_tempest_mode()
        have_structures: list[Unit] = list(structures_dict[sid])
        if sid == UnitID.GATEWAY:
            have_structures += structures_dict[UnitID.WARPGATE]
        if not have_structures:
            return
        if tr is not None and sid == UnitID.GATEWAY:
            # O208:Zerg Timing 混编地面需要 2 兵营，Rush 用 flows.yml 的 cap。
            _gw_cap = (
                2
                if (self._opp_race == "zerg" and self._ai_build == "timing")
                else tr.gateway_cap
            )
            desired = _gw_cap  # O92:过渡期兵营目标 = gateway_cap(总数口径)
        elif sid == UnitID.STARGATE:
            gas_per_base = [
                # O152-③:在途气矿也算(SG 建造 43s,在途气 21s 后即产能)
                self.ai.gas_buildings.closer_than(12, th).amount
                for th in self.ai.townhalls.ready
            ]
            desired = gas_gated_stargate_target(
                ep.cap, gas_per_base,
                # P2b:pivot 模式气体闸门放宽(单矿 2→3 星门,留数据空间不一步到4)
                # O152-③:carrier 流再 +1(双矿四气 → SG 目标 3→4,
                # 胜局产速 25+ 艘的产能前提;tempest/stalker 基线不变)
                bonus=stargate_gas_gate_bonus(pivot)
                + carrier_sg_bonus(self._flow.transition is not None),
            )
        else:
            desired = min(ep.cap, ep.base + self.ai.townhalls.ready.amount)
        have = len(have_structures) + self.manager_mediator.get_building_counter[sid]
        if (
            have < desired
            # O176:FB 已派工但买不起时,追加产能会抽干 FB 资金窗,先让位。
            and not getattr(self, "_fb_waiting", False)
            # P2a:pivot 模式豁免「矿>400」追加门槛,两道前置:FB 就绪/在建
            # (E10c:追加星门抢 FB 的钱)+ 首艘 TEMPEST 已出/在产(E10d:追加
            # 星门卡「FB就绪→首艘风暴」窗,首艘晚 50-70s);非 pivot 门槛 400 原样
            and self.ai.minerals
            > extra_production_mineral_gate(
                pivot,
                self._structure_present_or_pending(UnitID.FLEETBEACON),
                self._first_tempest_seen(),
                # O53:carrier 提前第二星门(250);
                # O97-C:过渡期兵营追加门槛=0(o96 局1/局3 实证:兵营=过渡期
                # 命根,250 门槛让它排在塔/水晶/农民后面,gateway#2 迟到 40s+),
                # 只看下面的 can_afford;
                # O109-②:首舰后 SG 追加同设 0 —— 与 SG 爬坡预留配套
                # (攒够 150 的那一刻立刻拍出,不再等 250 门槛)
                default_gate=(
                    0.0
                    if (
                        tr is not None
                        or (
                            self._flow.transition is not None
                            and self._first_fleet_seen()
                        )
                    )
                    else ep.mineral_gate
                ),
                # O157: 气体富余但矿物紧缺时抬高追加产能门槛。
                vespene=self.ai.vespene,
                minerals=self.ai.minerals,
                fleet_total=(
                    self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST)
                    + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER)
                    + cy_unit_pending(self.ai, UnitID.TEMPEST)
                    + cy_unit_pending(self.ai, UnitID.CARRIER)
                ),
            )
            and self.ai.can_afford(sid)
        ):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, sid)
            )

    def _spend_bank(self) -> None:
        """滚雪球(Q3,司令要求):前 20 分钟存款淤积时把钱换成战场优势——
        能开矿先开(基地<4,钱生钱,维持原 800 矿阈值不动),否则突破流派常规上限
        追加产兵建筑(存款越多补得越多)。治"经济优势大但钱花不完,没转化成兵力"。
        B7②(12PoolBot add_production_at_bank=(400,400)):追加产能的存款判据抽纯函数
        bank_production_target —— 矿>400 且气>400 才追加(旧版只看矿≥800),封顶 12。
        ⚠️ 未验证:阈值改动未跑局(bank 局追加更早,且多一道气>400 闸门)。"""
        if self.ai.time > 1200:
            return
        # 开矿分支维持原阈值(矿≥800 才触发,Q3 已验证行为不变)
        # O93-B2/O96:转舰队后首舰(已出/在产)前不开矿 —— 局2 的 FB 资金窗被
        # 三矿吃掉;局4 实证等「FB 实体」不够,首舰前的二矿同样致命。
        # O171:o171 game_01 实证,Stargate 就绪后 FleetBeacon 因没钱停滞 250s+,
        # 此时 _spend_bank 却把 800 矿拿去开三矿,FB 永远落不了地。舰队饥饿期
        # (FB 缺失且星门就绪)禁止滚雪球开矿,先把 FB 拍出来。
        # O172/O175:o172 game_01 实证,FB pending 但工人被 O11 反复释放,实体永
        # 远不落地;用稳定「无实体」信号(连续 5s 无真正实体)而非 present_or_pending,
        # 确保 800 矿存款优先变成 FB。
        _fb_missing_starved = (
            UnitID.FLEETBEACON in self._flow.core_structure_ids()
            and (
                getattr(self, "_fb_truly_missing", False)
                or getattr(self, "_fb_waiting", False)
            )
            and any(
                s.is_ready
                for s in self.manager_mediator.get_own_structures_dict[
                    UnitID.STARGATE
                ]
            )
        )
        if (
            self.ai.minerals >= 800
            and self.ai.townhalls.amount < 4
            and self.ai.can_afford(UnitID.NEXUS)
            and not _fb_missing_starved
            # O250(o249-lane game_04/05 实证):O247 首舰前不开矿被 _spend_bank
            # 绕开(存款 800 早到 + SG 未就绪 → fb_missing_starved 永假,
            # 二矿 249s 落成即被轮抄);舰队先行门同步接入滚雪球开矿。
            # O258-①:与主闸同源改防御驱动(zerg_timing_expand_allowed)。
            # O262-①:去 threat 条件,窗 260s(同主闸)。
            # O263-①:窗 320s + 分矿点 35 格无敌(260 强开拍进波路径实证)。
            # O265:窗 220s + 首塔就绪前提(宗师速开二矿实验,同主闸)。
            and zerg_timing_expand_allowed(
                self._opp_race == "zerg" and self._ai_build == "timing",
                self._first_fleet_seen(),
                self.ai.time,
                sum(
                    1 for u in self.ai.enemy_units
                    if not u.is_structure and is_combat_type(u.type_id)
                    and u.position.distance_to(self.ai.start_location) < 40
                ),
                self._zt_enemy_near_expand_target(),  # O281:对着首扩目标点(口袋矿)
                self._cannons_ready_peak,
            )
            and not fleet_expand_holds(
                self._fleet_transitioned,
                self._first_fleet_seen(),
                self._defense_score(),  # O105-①:防御达标豁免首舰门
            )
        ):
            # O281:ZT 定点口袋矿;_zt_pocket_expand_target 非 ZT 返回
            # None,ExpansionController 走原 own_expansions 排序,行为不变。
            self.ai.register_behavior(
                ExpansionController(
                    to_count=self.ai.townhalls.amount + 1,
                    max_pending=1,
                    location=self._zt_pocket_expand_target(),
                )
            )
            return
        ep = self._flow.extra_production
        if ep is None:
            return
        # O166: 首矿扩张未落地/核心科技未出前，不拿追加产能(STARGATE/GATEWAY)
        # 和 Nexus/科技抢钱。transition 流因 transition_expand_blocked 会自然放行。
        # O176:FB 已派工但买不起时,追加产能/滚雪球会抽干 FB 资金,先让位。
        if (
            (self._expand_holding and self.ai.townhalls.amount < 2)
            or self._nexus_waiting
            or self._early_core_missing
            or getattr(self, "_fb_waiting", False)
        ):
            return
        # O92:过渡形态期滚雪球也追加兵营不追加星门(与 _build_extra_production 同旨),
        # 目标数压到 gateway_cap(银行公式 cap=12 是给星门群的,兵营不需要)。
        tr = self._flow.transition if self._transition_active else None
        sid = UnitID.GATEWAY if tr is not None else getattr(UnitID, ep.id_name, None)
        if sid is None or not self.ai.can_afford(sid):
            return
        # O216d:滚雪球追加星门同样要等国航标实体落成,否则 800 矿存款会先变成
        # 第二/三座星门,FB 建造窗被挤占、舰队产线继续空转。
        # O216e:FB 实体落成后仍要守到首艘舰队单位在产/已出,避免星门空转。
        if (
            sid == UnitID.STARGATE
            and UnitID.FLEETBEACON in self._flow.core_structure_ids()
            and (
                self._fb_entities_now == 0
                or not self._first_fleet_seen()
            )
        ):
            return
        desired = bank_production_target(
            self.ai.minerals,
            self.ai.vespene,
            base=ep.base,
            ready_bases=self.ai.townhalls.ready.amount,
        )
        if desired is None:
            return
        if tr is not None:
            # O208:Zerg Timing 混编地面需要 2 兵营滚雪球上限。
            _gw_cap = (
                2
                if (self._opp_race == "zerg" and self._ai_build == "timing")
                else tr.gateway_cap
            )
            desired = min(desired, _gw_cap)
        have = (
            len(self.manager_mediator.get_own_structures_dict[sid])
            + self.manager_mediator.get_building_counter[sid]
        )
        if sid == UnitID.GATEWAY:  # warpgate 也是产能
            have += len(self.manager_mediator.get_own_structures_dict[UnitID.WARPGATE])
        if have < desired:
            self.ai.register_behavior(BuildStructure(self.ai.start_location, sid))

    def _front_point(self) -> Point2:
        """F1: 前线折跃点 —— 敌我之间偏敌 60%。让 WarpInManager 优先把兵折跃到前线
        水晶塔（而非主基地），配合 _build_forward_pylon 实现远程投送。"""
        return self.ai.start_location.towards(self.ai.focused_enemy_start(), 0.6)

    def _mineral_income_per_sec(self) -> float:
        """当前矿收入速率(矿/游戏秒)——dispatch_viable 的「路上收入」估算(O19)。
        score 不可用时回退 0(=只认当前存款,最保守)。"""
        try:
            return self.ai.state.score.collection_rate_minerals / 60.0
        except (AttributeError, TypeError):
            return 0.0

    def _expansion_walk_time(self) -> float:
        """农民走到下一个空闲扩张点的估算时间(秒)——dispatch_viable 预走位用(O19)。
        取「我基地 → 空闲扩张点」的最短距离 ÷ 农民速度;没有空闲点 → 0(只认现钱)。"""
        if not self.ai.townhalls or not self.ai.expansion_locations_list:
            return 0.0
        free = [
            el
            for el in self.ai.expansion_locations_list
            if not self.ai.townhalls.closer_than(5.0, el)
        ]
        if not free:
            return 0.0
        dist = min(el.distance_to(th) for el in free for th in self.ai.townhalls)
        return dist / _WORKER_SPEED

    def _build_forward_pylon(self) -> None:
        """F1: 在前线造水晶塔，给折跃门提供前线电源（兵秒投前线，不全程走）。
        条件：warpgate 已研究（能折跃）+ 矿富余 + 还没造过（一次性）。
        ⚠️ 前线塔易被打，是最小方案的固有风险（完整方案会用折跃棱镜）。"""
        if self._forward_pylon_built:
            return
        # warpgate 研究好才值得造前线塔（否则 gateway train 用不上前线电源）
        if UpgradeId.WARPGATERESEARCH not in self.ai.state.upgrades:
            return
        # O166: 前期不拿前线塔和科技/Nexus 抢钱
        if self._early_core_missing or self._nexus_waiting:
            return
        if self.ai.minerals > 300 and self.ai.can_afford(UnitID.PYLON):
            self.ai.register_behavior(
                BuildStructure(self._front_point(), UnitID.PYLON)
            )
            self._forward_pylon_built = True

    def _should_build_defense(self, order: dict) -> bool:
        """F2: 是否铺防御塔(B+F+Cannon)。判据: 司令下令 defend=yes / 中后期(>6分钟)自动铺 /
        rush 检测成立立即铺(E3b) / rush 预警(≥2 敌作战单位压到家门口 40 格,农民侦查不算)。
        E1: rush 相关铺塔受 pivot.rush_cannons 开关控制(false = 臂 B 纯叉子不铺塔;
        defend=yes 和 6 分钟自动铺不受影响,司令始终能手动铺)。"""
        # O202:CarrierOpenerZergRush 的 build order 已硬编码 forge+双塔,
        # 在 build order 完成/二塔在途前,PSD 不插手,避免与 build order 抢工人抢矿。
        if self._carrier_rush_opener_early():
            return False
        if order.get("defend") == "yes":
            return True
        # vs Zerg 提前到 4 分钟自动铺塔(roach/ravager all-in ~5:00,hydra push ~5:30;原 6 分钟太晚)
        _er = getattr(self.ai, "enemy_race", None)
        if self.ai.time > (240 if _er == Race.Zerg else 360):
            return True
        pv = self._flow.pivot
        if pv is not None and not pv.rush_cannons:
            return False
        # E3l:分矿塔与 Nexus 同步 —— 有 Nexus 在建/已多基地立即启动分矿塔防
        # (原来要等落地+6 分钟自动线,分矿裸奔 30-100s 被敌反复拆,e3l 三局实证)
        if defense_syncs_with_nexus(
            self.manager_mediator.get_building_counter[UnitID.NEXUS],
            self.ai.townhalls.amount,
        ):
            return True
        # E3b: rush 检测成立即铺塔 —— 原来塔的触发只看"敌兵压到 40 格",
        # 炮塔 ~30s 建造 + 要水晶供电,压到门口再建来不及(e3b game_02:
        # 检测 130s 成立,首塔 221s 才立)。rush_cannons=False(臂 B)保持不铺。
        if rush_triggers_defense(
            self._rush_active, True if pv is None else pv.rush_cannons
        ):
            return True
        home = self.ai.start_location
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        attackers = sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and u.type_id not in workers
            and u.position.distance_to(home) < 40
        )
        return attackers >= 2

    def _carrier_rush_opener_early(self) -> bool:
        """O202:判断当前是否为 CarrierOpenerZergRush 早期。

        在该 opener 下,build order 已负责 forge+双塔的硬防御链;
        在 build order 完成或至少 2 座 photoncannon 在途/落地前,
        禁止 PSD/_presumed_defense_chain 插手,防止派工/矿物竞争把塔 timing 拖崩。
        """
        bor = getattr(self.ai, "build_order_runner", None)
        if bor is None or bor.chosen_opening != "CarrierOpenerZergRush":
            return False
        if bor.build_completed:
            return False
        return self._count_structure(UnitID.PHOTONCANNON) < 2

    def _is_zerg_rush_timing(self) -> bool:
        """O207:当前为 vs Zerg 的 Rush 或 Timing 对局。

        这类对局需要早期防御链(forge+首塔)在 cybercore/stargate 排队前启动,
        因此部分被 `_early_core_missing` 保护的注册点要对 Zerg Rush/Timing 放行。
        """
        return self._opp_race == "zerg" and self._ai_build in ("rush", "timing")

    def _is_zerg_timing_fb_exempt(self) -> bool:
        """O215:vs Zerg Timing 时,开矿持有期仍允许 FleetBeacon 派工。

        否则 Nexus 在途期间 core_allowed=False 会冻结 FB, Nexus 落成后 minerals
        又被塔/兵抽干,FB 系统性晚 50-150s,舰队无法成型。
        """
        return (
            self._opp_race == "zerg"
            and self._ai_build == "timing"
            # O216:从 240 降到 180,Nexus 在途更早放行 FB,避免 fleet 转型被拖 50-150s。
            and self.ai.time >= 180.0
        )

    def _main_townhall(self):
        """需求3:压境防御锚定的 townhall = 最靠近敌方的 ready townhall(前线门户/分矿)。
        司令战术:分矿=前线咽喉,守分矿=挡住正面陆军=主基自然安全(2026-07-25 修正:
        原选最靠近 start_location 的主基,方向错 → 敌压分矿时主基堆塔没用)。单基地
        时退化(唯一 townhall 即前线)。没有就绪基地 → None。"""
        ths = [t for t in self.ai.townhalls if t.is_ready]
        if not ths:
            return None
        enemy = self.ai.focused_enemy_start()
        return min(ths, key=lambda t: t.position.distance_to(enemy))

    def _main_under_siege(self) -> bool:
        """需求3:敌大军压上分矿(前线门户)。复用 is_combat_type 口径(排除工人/侦查/运输),
        前线 townhall(最靠近敌方)radius 内敌地面作战单位 ≥ threshold → True。radius
        放大(默认 25)给造塔 ~29s 留提前量(敌到 15 格再建来不及)。"""
        ms = self._flow.main_siege
        if ms is None:
            return False
        th = self._main_townhall()
        if th is None:
            return False
        n = sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and not u.is_flying
            and is_combat_type(u.type_id)
            and u.position.distance_to(th.position) < ms.radius
        )
        return main_siege_active(n, ms.threshold)

    def _resolve_buildable(self, name: str) -> UnitID | None:
        """build=<名> → UnitID。先走 levers.resolve_build_name 归一(复用 CLI 同一份逻辑),
        再 getattr(UnitID, ...)。认不出 → None。"""
        from bot.levers import resolve_build_name
        enum_name = resolve_build_name(name)
        if enum_name is None:
            return None
        return getattr(UnitID, enum_name, None)

    def _count_structure(self, sid: UnitID) -> int:
        """已有 + 在建 的数量（nexus 用 townhalls 计）。"""
        if sid == UnitID.NEXUS:
            return self.ai.townhalls.amount
        return (
            len(self.manager_mediator.get_own_structures_dict[sid])
            + self.manager_mediator.get_building_counter[sid]
        )

    def _handle_manual_build(self, order: dict, macro_plan: MacroPlan) -> None:
        """通用建筑杠杆 build=<结构>：参谋长只说造什么，选农民/选位置全归 bot（ares 原语）。
        一次性锁定："当前数量+1"为目标，造到就停；想再造先 clear 再下（同 scout/expand）。
        expand=yes 收编为 build=nexus 的别名。"""
        want = (order.get("build") or "").strip().lower()
        if not want and order.get("expand") == "yes":
            want = "nexus"
        if not want:
            self._build_key = None
            self._build_target = None
            return

        sid = self._resolve_buildable(want)
        if sid is None:
            return  # 认不出的结构名，忽略

        # 新的 build 请求 → 锁定目标数量
        if self._build_key != want:
            self._build_key = want
            self._build_target = self._count_structure(sid) + 1

        if self._count_structure(sid) >= self._build_target:
            return  # 已达目标，停（等 clear 重置）

        if sid == UnitID.NEXUS:
            macro_plan.add(
                ExpansionController(to_count=self._build_target, max_pending=1)
            )
        elif sid == UnitID.ASSIMILATOR:
            self._build_gas()
        elif (
            self.manager_mediator.get_building_counter[sid] == 0
            and self.ai.can_afford(sid)
        ):
            self.ai.register_behavior(BuildStructure(self.ai.start_location, sid))

    def _primary_unit_id(self) -> UnitID:
        """当前流派 spawn 里优先级最高(proportion>0 且 priority 最小)的兵种枚举。
        chrono 判断"主力是否在造"用它;换流派自动跟随 flows.yml 配置。"""
        candidates = [
            (name, cfg) for name, cfg in self._flow.spawn.items()
            if cfg["proportion"] > 0
        ]
        if not candidates:
            return UnitID.TEMPEST  # 兜底
        name = min(candidates, key=lambda kv: kv[1]["priority"])[0]
        return getattr(UnitID, name, UnitID.TEMPEST)

    def _chrono_structures(self):
        """按流派 chrono 配置加速:targets 顺序取第一个有建筑的;
        when=always 见忙就加速,primary_pending 等主力在产(或一次性 oracle 的首次加速)。"""
        # O141-②(o141 一轮 smoke 实证):forge chrono —— 防御紧急窗 forge
        # 在 warp 且首塔未出 → chrono forge(33s→~23s,完工 133→~104);
        # 首塔出现即让位首叉 chrono(下块),不双抢能量
        if self._flow.transition is not None and chrono_forge_first(
            self._defense_urgent,
            any(
                not s.is_ready
                for s in self.manager_mediator.get_own_structures_dict[
                    UnitID.FORGE
                ]
            ),
            any(
                s.type_id == UnitID.PHOTONCANNON for s in self.ai.structures
            ),
        ):
            _warping_forge = [
                s
                for s in self.manager_mediator.get_own_structures_dict[
                    UnitID.FORGE
                ]
                if not s.is_ready
                and not s.has_buff(BuffId.CHRONOBOOSTENERGYCOST)
            ]
            if _warping_forge:
                for nexus in self.ai.townhalls:
                    if nexus.energy >= 50:
                        nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, _warping_forge[0])
                        return
        # O125-②(o124 局1 实证):首叉 chrono —— rush/过渡窗内 SG 未建,
        # targets 空转能量闲置;GW 在产且首叉未出 → chrono 兵营(27s→~19s)
        if self._flow.transition is not None and chrono_first_zealot(
            self._defense_urgent,
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.ZEALOT)
            > 0,
        ):
            _busy_gw = [
                g
                for g in self.manager_mediator.get_own_structures_dict[
                    UnitID.GATEWAY
                ]
                if g.is_ready
                and not g.is_idle
                and not g.has_buff(BuffId.CHRONOBOOSTENERGYCOST)
            ]
            if _busy_gw:
                for nexus in self.ai.townhalls:
                    if nexus.energy >= 50:
                        nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, _busy_gw[0])
                        return
        targets: list[Unit] = []
        for name in self._flow.chrono.targets:
            sid = getattr(UnitID, name, None)
            if sid is None:
                continue
            targets = self.manager_mediator.get_own_structures_dict[sid]
            if targets:
                break
        if not targets:
            # O264(司令观察②):SG 落地前 chrono 全程闲置(0-260s 能量白攒
            # 50-100)—— 宗师开局惯例:前期 chrono 全给 Nexus 加速产农。
            # 目标=在产且未加速的 Nexus;任何能量 ≥50 的基地施放。
            # SG 出现后由下方流派 targets 接管(舰队科技优先),语义不回头。
            _busy_th = [
                t
                for t in self.ai.townhalls
                if t.is_ready
                and not t.is_idle
                and not t.has_buff(BuffId.CHRONOBOOSTENERGYCOST)
            ]
            if _busy_th:
                for nexus in self.ai.townhalls:
                    if nexus.energy >= 50:
                        nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, _busy_th[0])
                        return
            return
        # P2c:chrono 主 C 判定 verdict 化 —— pivot 风暴主 C 阶段认 TEMPEST
        # (否则 primary_pending 等航母在产,星门整段无 chrono,E10b 实锤星门 1-2);
        # 非 pivot 读 flows.yml 原主 C,行为零变化
        primary = chrono_primary_id(
            self._pivot_tempest_mode(), self._primary_unit_id(), UnitID.TEMPEST
        )
        for nexus in self.ai.townhalls:
            if nexus.energy < 50:
                continue
            non_idle = [
                s for s in targets
                if not s.is_idle
                and not s.has_buff(BuffId.CHRONOBOOSTENERGYCOST)
            ]
            if not non_idle:
                continue
            if self._flow.chrono.when == "always" or cy_unit_pending(self.ai, primary):
                nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, non_idle[0])
                return
            if not self._oracle_chrono:
                nexus(AbilityId.EFFECT_CHRONOBOOSTENERGYCOST, non_idle[0])
                self._oracle_chrono = True
