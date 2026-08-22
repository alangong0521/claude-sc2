from itertools import cycle
from typing import TYPE_CHECKING

from ares import ManagerMediator
from ares.consts import UnitRole
from ares.managers.manager import Manager
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.units import Units

from bot.combat.base_unit import BaseUnit
from bot.combat.carrier_offensive import CarrierOffensive
from bot.combat.dt_offensive import DtOffensive
from bot.combat.generic_offensive import GenericOffensive
from bot.combat.ghost_offensive import GhostOffensive
from bot.combat.infestor_caster import InfestorCaster
from bot.combat.medivac_support import MedivacSupport
from bot.combat.medivac_transport import MedivacTransport
from bot.combat.queen_support import QueenSupport
from bot.combat.raven_support import RavenSupport
from bot.combat.reaper_harass import ReaperHarass
from bot.combat.siege_offensive import SiegeOffensive
from bot.combat.stalker_offensive import StalkerOffensive
from bot.combat.templar_caster import TemplarCaster
from bot.combat.tempest_offensive import TempestOffensive
from bot.combat.warp_prism_offensive import WarpPrismOffensive
from bot.production_plans import (
    carrier_push_safe,
    carrier_push_fleet_floor,
    carrier_desperation_push_allowed,
    zerg_macro_golden_window_push,
    macro_golden_recall_threshold,
    macro_golden_zealot_holds_home,
    fleet_no_recall_threshold,
    carrier_rally_against_aa,
    defense_anchor_index,
    defensive_rally_point,
    fleet_recall_target,
    floor_army_defends_home,
    full_pop_all_in,
    hot_base_index,
    is_combat_type,
    rally_min_for_verdict,
    rush_defend_base,
    should_push_advantage,
    push_enemy_army_gate,
    push_commit_aa_retreat,
    aa_peak_sticky,
    transition_push_hold,
    zerg_aa_credited,
    zerg_aa_exemption_capped,
    zerg_departure_floor_ok,
    zerg_corruptor_departure_blocked,
    force_push_corruptor_ok,
    aa_reeval_due,
    blind_push_blocked,
    push_fleet_floor_ok,
    recipe_push_exempt,
    desperation_push_window,
    terran_economic_strike_window,
    zerg_rush_economic_strike_window,
    economic_strike_ground_holds_home,
    enemy_townhall_matches_focused_start,
    carrier_fleet_keeps_strategic_target,
    economic_strike_recall_threshold,
    two_base_guard_point,
    main_defense_first,
    zt_golden_window_push,
    terminal_cleanup_active,
    terminal_cleanup_limits,
    terminal_cleanup_profile,
    terminal_cleanup_target_class,
    terminal_cleanup_patrol_order,
    q5_last_stand_active,
    terran_timing_force_push_allowed,
)

if TYPE_CHECKING:
    from ares import AresBot


class CombatManager(Manager):
    def __init__(
        self,
        ai: "AresBot",
        config: dict,
        mediator: ManagerMediator,
    ) -> None:
        """Handle all main combat logic.

        This manager is incharge of all the main offensive units.
        Combat classes should be called as needed to execute unit control.

        Parameters
        ----------
        ai :
            Bot object that will be running the game
        config :
            Dictionary with the data from the configuration file
        mediator :
            ManagerMediator used for getting information from other managers.
        """
        super().__init__(ai, config, mediator)
        self.expansions_generator = None
        self.current_base_target: Point2 = self.ai.focused_enemy_start()
        self.tempest_offensive: BaseUnit = TempestOffensive(ai, config, mediator)
        self.stalker_offensive: BaseUnit = StalkerOffensive(ai, config, mediator)
        self.generic_offensive: BaseUnit = GenericOffensive(ai, config, mediator)
        self.dt_offensive: BaseUnit = DtOffensive(ai, config, mediator)
        self.warp_prism_offensive: BaseUnit = WarpPrismOffensive(ai, config, mediator)
        self.siege_offensive: BaseUnit = SiegeOffensive(ai, config, mediator)
        self.medivac_support: BaseUnit = MedivacSupport(ai, config, mediator)
        self.medivac_transport: BaseUnit = MedivacTransport(ai, config, mediator)
        self.templar_caster: BaseUnit = TemplarCaster(ai, config, mediator)
        self.ghost_offensive: BaseUnit = GhostOffensive(ai, config, mediator)
        self.raven_support: BaseUnit = RavenSupport(ai, config, mediator)
        self.queen_support: BaseUnit = QueenSupport(ai, config, mediator)
        self.reaper_harass: BaseUnit = ReaperHarass(ai, config, mediator)
        self.infestor_caster: BaseUnit = InfestorCaster(ai, config, mediator)
        self.carrier_offensive: BaseUnit = CarrierOffensive(ai, config, mediator)
        # 兵种组成从 army_composition.yml 读(单一真相源,按 bot 种族选块),决定指挥哪些兵种、
        # 用哪个 combat class。不再写死只指挥 TEMPEST —— 加兵种只改 yaml。
        from bot.army_config import ArmyComposition, bot_race_name
        self._army = ArmyComposition.load(race=bot_race_name(ai))
        # C3a 集结阈值(flows.yml rally_min_army,缺省 0=关):低于阈值且司令没下 stance 时守家攒兵
        import os
        from bot.flow_config import FlowConfig
        self._flow: FlowConfig = FlowConfig.load(os.environ.get("BUILD"))
        self._rally_min: int = self._flow.rally_min_army
        # B3 刹车状态(事件去抖:只在"判负"边沿记一条,不每帧刷 events)
        self._sim_retreat_active: bool = False
        # O205:空军回防基地状态 —— 任一 Nexus 15 格内 ≥6 敌地面时召回,保留 10s 滞回
        self._fleet_recall_until: float = 0.0
        self._fleet_recall_target: Point2 | None = None
        # O217:基地残敌清剿事件去抖(激活边沿记一条,清除后复位)
        self._intruder_cleanup_active: bool = False
        self._o403_cleanup_logged: bool = False
        self._o403_cleanup_log_ts: float = -9999.0
        # O372-⑤(o371a g2 尸检):推进 commit 期 AA 重评簿记 —— 30s
        # 重评时刻与撤蹲旗标(旗标在重评间隔内粘滞,可见性抖动不
        # 反复收放);__init__ 初始化。
        self._o372_aa_eval_at: float = 0.0
        self._o372_aa_retreat: bool = False
        # O374-①(o373b g2 尸检):zerg AA 信用记忆簿记 —— 60s 粘滞
        # 峰值(可见 CORRUPTOR+BROODLORD 峰值与峰值时刻,期内不归零;
        # aa_peak_sticky 规约,腐化离视野 60s 内撤蹲/出发闸仍认账);
        # __init__ 初始化。
        self._o374_aa_peak: int = 0
        self._o374_aa_peak_at: float = -9999.0
        # O378-⑥b(o377b 三局团灭尸检):AA 重评的信用计数快照 ——
        # 「新增腐化显形 ≥4 立即重评」判据(aa_reeval_due)要比较
        # 上次重评时的计数;__init__ 初始化。
        self._o378_aa_last_credited: int = 0
        # O380-⑤:舰队长期未成型时的一次 60s 豁命推进窗。
        self._o380_desperation_used: bool = False
        self._o380_desperation_until: float = 0.0
        # O382-④:Terran 制空后打分矿窗的边沿簿记。
        self._o382_economic_strike_active: bool = False
        # O386-②:经济打击时地面守军清抄家、舰队继续斩经济的分流边沿。
        self._o386_strike_split_active: bool = False
        # O226:残敌清剿 3s 收尾滞回(防 attack_target 每帧翻转 yo-yo)
        self._intruder_last_seen: float | None = None
        self._intruder_last_target: Point2 | None = None
        # combat kind → combat class 分派表(oracle_harass 由 OracleManager 单独管,这里不收)
        self._combat_dispatch: dict[str, BaseUnit] = {
            "tempest_offensive": self.tempest_offensive,
            "stalker_offensive": self.stalker_offensive,   # 纯追猎 blink 流(BUILD=stalker)
            "default": self.generic_offensive,
            "dt_offensive": self.dt_offensive,              # DT:被反隐照到且盾不满即撤(Sharky)
            "warp_prism_offensive": self.warp_prism_offensive,  # B9:相位折跃+接残血(Sharky/sharpy)
            "siege_offensive": self.siege_offensive,        # M4:攻城坦克
            "medivac_support": self.medivac_support,        # M4:医疗船治疗
            "medivac_transport": self.medivac_transport,    # M4:医疗船空投
            "templar_caster": self.templar_caster,          # M4:高模风暴
            "ghost_offensive": self.ghost_offensive,        # 幽灵狙杀
            "raven_support": self.raven_support,            # 渡鸦机炮台
            "queen_support": self.queen_support,            # 女王输血
            "reaper_harass": self.reaper_harass,            # 死神手雷
            "infestor_caster": self.infestor_caster,        # 感染虫真菌
            "carrier_offensive": self.carrier_offensive,    # O12/O14:航母锚点放机+残血后撤
        }

    # 静态防御(镜像 bot/main.py _STATIC_DEFENCE,避免循环 import)
    _STATIC_DEFENCE = {
        UnitID.PHOTONCANNON,
        UnitID.MISSILETURRET,
        UnitID.SPORECRAWLER,
        UnitID.SPINECRAWLER,
        UnitID.PLANETARYFORTRESS,
    }
    # O45:航母推进的硬对空威胁集 —— 腐化/维京/凤凰是 counter,
    # 飞蛇 Abduct 点名航母(不能对空,但比腐化更致命,算进来)
    _HARD_AA = {
        UnitID.CORRUPTOR,
        UnitID.VIKINGFIGHTER,
        UnitID.PHOENIX,
        UnitID.VIPER,
    }

    def _defend_anchor(self) -> Point2:
        """O37(司令观察):防守锚点。主基塔够(≥2)且已多基地 → 塔最少的分矿
        (新开的矿最暴露,地面防守兵顶那儿);否则主基(start_location,行为同旧版)。
        判据纯函数 production_plans.defense_anchor_index。"""
        ai = self.ai
        ths = sorted(
            ai.ready_townhalls,
            key=lambda t: t.position.distance_to(ai.start_location),
        )
        if not ths:
            return ai.start_location
        counts = [
            sum(
                1 for s in ai.structures.ready
                if s.type_id in self._STATIC_DEFENCE
                and s.position.distance_to(t.position) < 12
            )
            for t in ths
        ]
        return ths[defense_anchor_index(counts)].position

    def _ramp_hold_point(self) -> Point2 | None:
        """O148-①:主坡口内侧卡位点(坡顶朝基地反方向 4 格,sharpy
        PlanHeatDefender 同款,塔/电池射程内)—— 防守战地面部队站这里
        让狗/枪兵排队上坡,而不是站矿线被包围。无 ramp 数据 → None。"""
        ramp = getattr(self.ai, "main_base_ramp", None)
        if (
            ramp is None
            or not getattr(ramp, "top_center", None)
            or not getattr(ramp, "bottom_center", None)
        ):
            return None
        try:
            return Point2(defensive_rally_point(
                (ramp.top_center.x, ramp.top_center.y),
                (ramp.bottom_center.x, ramp.bottom_center.y),
            ))
        except Exception:
            return None

    def _ground_defend_point(self) -> Point2:
        """O148-①/O149-③:地面防守集结点 —— 单矿 = 主坡口内侧卡位点;
        双矿 = 主基卡位点与分矿连线中点(两矿间机动位,哪边来波都能接应)。"""
        hold = self._ramp_hold_point() or self.ai.start_location
        if self.ai.townhalls.amount >= 2:
            nat = next(
                (
                    th for th in self.ai.townhalls
                    if th.position.distance_to(self.ai.start_location) > 5.0
                ),
                None,
            )
            if nat is not None:
                return Point2(two_base_guard_point(
                    (hold.x, hold.y), (nat.position.x, nat.position.y)
                ))
        return hold

    def _rush_defend_anchor(self) -> Point2:
        """O40:rush 时守哪个基地 —— rush_defend_base 判据(各基地 25 格敌地面
        计数,与 production_manager._update_rush_state/_rush_spawn_target 同源):
        分矿承压最高 → 救该分矿;主基承压/无威胁 → 主基(回退旧行为)。"""
        ai = self.ai
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        threats = [
            (
                th.position.x, th.position.y,
                sum(
                    1 for u in ai.enemy_units
                    if not u.is_structure and u.type_id not in workers
                    and u.position.distance_to(th.position) < 25
                ),
            )
            for th in ai.townhalls
        ]
        base = rush_defend_base(threats, (ai.start_location.x, ai.start_location.y))
        target = Point2(base) if base is not None else ai.start_location
        # O136-②:坡口墙模式 → 叉子墙后站位(gap 内侧 1.5 格,封口/堵缝)
        wall_hold = getattr(self.ai.production_manager, "_wall_hold_point", None)
        if wall_hold is not None and target.distance_to(ai.start_location) < 1.0:
            return wall_hold
        # O148-①:主基守军锚点从基地中心改坡口内侧卡位点(塔/电池射程内,
        # 让狗排队上坡;站基地中心 = 腹背开阔被围杀,o147 系列复盘);
        # O149-③:双矿时改主基-分矿连线中点(_ground_defend_point,
        # 两矿间机动位);分矿承压时救援目标不变
        if target.distance_to(ai.start_location) < 1.0:
            return self._ground_defend_point()
        return target

    def _hot_base_anchor(self, min_threat: int = 6) -> Point2 | None:
        """O63(o62-vh-zerg-power game_01 实证):中局动态防守锚点 —— 正被围攻的基地。

        威胁计数与 _rush_defend_anchor 同源(各基地 25 格敌非农民单位);计数
        ≥ min_threat 的最高压基地 → 舰队回防;无热点 → None(回退 O37 静态锚点)。
        O64:蹲守分支默认 6(小队就回防止血);推进分支传 14(主力级才召回,
        小队骚扰不值得打断满人口推进)。
        """
        ai = self.ai
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        ths = sorted(
            ai.ready_townhalls,
            key=lambda t: t.position.distance_to(ai.start_location),
        )
        if len(ths) <= 1:
            return None
        threats = [
            sum(
                1 for u in ai.enemy_units
                if not u.is_structure and u.type_id not in workers
                and u.position.distance_to(th.position) < 25
            )
            for th in ths
        ]
        idx = hot_base_index(threats, min_threat=min_threat)
        return ths[idx].position if idx is not None else None

    # O205:受威胁时强制召回的空军类型(ATTACKING 编制内)
    _FLEET_AIR_TYPES = {
        UnitID.CARRIER,
        UnitID.TEMPEST,
        UnitID.VOIDRAY,
        UnitID.PHOENIX,
        UnitID.MOTHERSHIP,
    }

    def _air_fleet_recall_target(self, min_threat: int = 6) -> Point2 | None:
        """O205:任一 Nexus 15 格内达到门限 → 空军回防,保留 10s 滞回。

        与 E6 工人撤离联动:触发 E6 的基地(阈值 4)与这里(阈值 6)部分重叠,
        大波(≥6)时空军同步回防。优先回防距主基最近的受威胁基地(主战方向)。
        O386 起经济打击期传入10，避免 O205 把 O384 的10人召回门旁路回6。
        """
        now = getattr(self.ai, "time", 0.0)
        if now < self._fleet_recall_until and self._fleet_recall_target is not None:
            return self._fleet_recall_target
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        ths = sorted(
            self.ai.ready_townhalls,
            key=lambda t: t.position.distance_to(self.ai.start_location),
        )
        if not ths:
            return None
        enemies = [
            (u.position.x, u.position.y)
            for u in self.ai.enemy_units
            if not u.is_structure and not u.is_flying and u.type_id not in workers
        ]
        target = fleet_recall_target(
            [(th.position.x, th.position.y) for th in ths],
            enemies,
            min_threat=min_threat,
            radius=15.0,
        )
        if target is not None:
            self._fleet_recall_target = Point2(target)
            self._fleet_recall_until = now + 10.0
            return self._fleet_recall_target
        return None

    def _base_intruder_target(self) -> Point2 | None:
        """O217(司令观察):基地内残敌清剿 —— 大战后敌小股(1-5 个,如一条狗)
        滞留我方基地拆建筑,现有回防通道(O205 空军召回/_hot_base_anchor,
        阈值均 ≥6)不触发,守军锚点又不指向它,任由其拆光建筑。

        敌作战单位(is_combat_type,排除王虫/侦查/运输/工人)在任一就绪基地
        15 格内 1-5 个 → 攻击目标改为离基地最近的那个残敌位置(先清再推);
        ≥6 走原有大波回防通道,返回 None。rush 急性窗(rush_active)不清剿
        —— 坡口墙/守军不能为一条狗离位;transition 期照常(残敌已在墙内)。
        """
        _pm = getattr(self.ai, "production_manager", None)
        # O338-③(o337a game_03/05 实证):rush 急性窗只豁免主基残敌
        # (坡口墙/守军不为一条狗离位,O217 原证据);分矿残敌照清 ——
        # E6 协防只记账不拉兵(main.py update_worker_evacuation),
        # 小股 4-5 在分矿杀农拆 Nexus 时主基守军全程看戏,379-507s
        # 三连速败。rush_active 时把清剿范围缩到非主基基地。
        _rush_on = _pm is not None and getattr(_pm, "_rush_active", False)
        ths = list(self.ai.ready_townhalls)
        if not ths:
            return None
        if _rush_on:
            _main_pos = self.ai.start_location
            ths = [t for t in ths if t.position.distance_to(_main_pos) > 5.0]
            if not ths:
                return None
        intruders = [
            u
            for u in self.ai.enemy_units
            if not u.is_structure
            and is_combat_type(u.type_id)
            and any(u.position.distance_to(th.position) < 15 for th in ths)
        ]
        now = getattr(self.ai, "time", 0.0)
        if 1 <= len(intruders) <= 5:
            target = min(
                intruders,
                key=lambda u: min(u.position.distance_to(th.position) for th in ths),
            )
            # O226(o222-lane2 game_04 实证):无滞回时残敌进出 15 格/目标死亡
            # 让 attack_target 每帧翻转,O217 激活 218 次,全军 yo-yo 磨死。
            # 激活期每帧重算最近残敌(位置新鲜),消失后 3s 收尾才退出。
            self._intruder_last_seen = now
            self._intruder_last_target = target.position
            return target.position
        if (
            self._intruder_last_seen is not None
            and now - self._intruder_last_seen < 3.0
            and self._intruder_last_target is not None
        ):
            return self._intruder_last_target
        return None

    def _enemy_near_their_base(self) -> bool:
        """敌主力是否还在自己家附近（⑥择时 when_enemy_away：在家就等他出门再打）。
        多人：看的是**焦点敌人**的家。"""
        home = self.ai.focused_enemy_start()
        return any(
            u.position.distance_to(home) < 25
            for u in self.ai.enemy_units
            if not u.is_structure
        )

    def _backdoor(self) -> Point2:
        """④机动·绕后：离敌军重心最远的敌方分矿（偷家）。无敌军可见 → 敌最远分矿。
        多人：绕后点相对**焦点敌人**的家算。"""
        ai = self.ai
        focus = ai.focused_enemy_start()
        enemy_exps = sorted(
            ai.expansion_locations_list,
            key=lambda p: p.distance_to(focus),
        )[:5]
        ground = [u for u in ai.enemy_units if not u.is_flying]
        if not ground:
            return enemy_exps[-1] if enemy_exps else focus
        cx = sum(u.position.x for u in ground) / len(ground)
        cy = sum(u.position.y for u in ground) / len(ground)
        center = Point2((cx, cy))
        return max(enemy_exps, key=lambda p: p.distance_to(center))

    def _known_enemy_townhalls(self) -> Units:
        """Known enemy bases near the focused enemy, sorted from main outward.

        Do not blindly target theoretical expansion points for enemy_natural/third.
        On some maps the geometric "second closest expansion to enemy start" is not
        where the AI actually expanded, which can park the army at an empty base.
        """
        townhall_types: set[UnitID] = {
            UnitID.NEXUS,
            UnitID.COMMANDCENTER,
            UnitID.ORBITALCOMMAND,
            UnitID.PLANETARYFORTRESS,
            UnitID.HATCHERY,
            UnitID.LAIR,
            UnitID.HIVE,
        }
        focus = self.ai.focused_enemy_start()
        enemy_starts = list(self.ai.enemy_start_locations)
        candidates = self.ai.enemy_structures.filter(
            lambda s: (
                s.type_id in townhall_types
                and enemy_townhall_matches_focused_start(
                    (s.position.x, s.position.y),
                    (focus.x, focus.y),
                    [(start.x, start.y) for start in enemy_starts],
                )
            )
        )
        return candidates.sorted(lambda s: s.position.distance_to(focus))

    def _terminal_cleanup_active(self) -> bool:
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        fleet = (
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST)
            + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER)
        )
        _pm = getattr(self.ai, "production_manager", None)
        (
            _cleanup_min_time,
            _cleanup_structure_cap,
            _cleanup_worker_cap,
            _cleanup_combat_cap,
        ) = terminal_cleanup_profile(
            getattr(_pm, "_opp_race", "") if _pm is not None else "",
            getattr(_pm, "_ai_build", "") if _pm is not None else "",
        )
        _visible_enemy_structures = sum(
            1
            for s in self.ai.enemy_structures
            if self.ai.is_visible(s.position)
        )
        active = terminal_cleanup_active(
            now=getattr(self.ai, "time", 0.0),
            fleet_count=fleet,
            enemy_structures=_visible_enemy_structures,
            enemy_workers=sum(1 for u in self.ai.enemy_units if u.type_id in workers),
            enemy_combat=sum(
                1
                for u in self.ai.enemy_units
                if not u.is_structure
                and u.type_id not in workers
                and is_combat_type(u.type_id)
            ),
            max_structures=_cleanup_structure_cap,
            max_workers=_cleanup_worker_cap,
            max_combat=_cleanup_combat_cap,
            min_time=_cleanup_min_time,
        )
        if active and self.ai.time - self._o403_cleanup_log_ts >= 30.0:
            self._o403_cleanup_logged = True
            self._o403_cleanup_log_ts = self.ai.time
            events = getattr(self.ai, "_events", None)
            if events is not None:
                events.append({
                    "t": round(self.ai.time, 1),
                    "msg": (
                        f"O403:残敌终结模式(fleet={fleet},"
                        f"可见结构={_visible_enemy_structures})"
                    ),
                })
        return active

    def _terminal_cleanup_target(self) -> Point2:
        """O403/O425:先断重建经济，再清结构/农民/残兵。"""
        focus = self.ai.focused_enemy_start()
        known_townhalls = self._known_enemy_townhalls()
        visible_structures = self.ai.enemy_structures.filter(
            lambda s: self.ai.is_visible(s.position)
        )
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        worker_units = self.ai.enemy_units.filter(lambda u: u.type_id in workers)
        combat_units = self.ai.enemy_units.filter(
            lambda u: u.type_id not in workers and is_combat_type(u.type_id)
        )
        patrol_xy = terminal_cleanup_patrol_order(
            [(p.x, p.y) for p in self.ai.expansion_locations_list],
            (focus.x, focus.y),
        )
        target_class = terminal_cleanup_target_class(
            known_townhalls=known_townhalls.amount,
            visible_structures=visible_structures.amount,
            visible_workers=worker_units.amount,
            patrol_points=len(patrol_xy),
            visible_combat=combat_units.amount,
        )
        if target_class == "townhall":
            return known_townhalls[-1].position
        if target_class == "structure":
            return visible_structures.closest_to(focus).position
        if target_class == "worker":
            return worker_units.closest_to(focus).position
        if target_class == "patrol":
            patrol_points = [Point2(p) for p in patrol_xy]
            if not hasattr(self, "_o425_cleanup_patrol"):
                self._o425_cleanup_patrol = cycle(patrol_points)
                self._o425_cleanup_target = next(self._o425_cleanup_patrol)
            if self.ai.is_visible(self._o425_cleanup_target):
                self._o425_cleanup_target = next(self._o425_cleanup_patrol)
            return self._o425_cleanup_target
        if target_class == "combat":
            return combat_units.closest_to(focus).position
        return focus

    def _resolve_steer_target(self, key: str) -> Point2 | None:
        """参谋长的语义目标 → Point2（不让司令点坐标）。认不出则 None。
        enemy_* 都相对**焦点敌人**（enemy=E2 切；默认最近 E1；1v1 就是唯一敌人）。"""
        ai = self.ai
        focus = ai.focused_enemy_start()
        if key == "home":
            return ai.start_location
        if key == "map_center":
            return ai.game_info.map_center
        if key == "enemy_main":
            return focus
        if key == "enemy_backdoor":
            return self._backdoor()
        # enemy_natural/third/fourth:纯选择抽到 levers.pick_known_base,这里只取候选
        from bot.levers import pick_known_base
        known = self._known_enemy_townhalls()
        idx = pick_known_base(key, range(known.amount))
        if idx is not None:
            return known[idx].position
        # 没探到那么多矿 → None(回退默认追敌,不硬冲空地)
        return None

    @property
    def attack_target(self) -> Point2:
        """进攻点。参谋长下了命令就听命令（覆盖默认）：
        defend → 防守锚点(O37:主基塔够蹲最暴露分矿)；retreat → 回主基；
        attack + 语义目标 → 求解该点；否则走默认追敌逻辑。
        pivot:rush 响应期间(_rush_active)全军守家(优先级仅次于司令命令)。"""
        order = getattr(self.ai, "steer_order", None) or {}
        # O65:推进承诺标记(commit_push)每帧重算 —— 只有 carrier 推进闸全开
        # (优势+对空安全+无主力级回防)时才置 True,供舰队行为层选择「行军模式」
        self._push_committed = False
        self._o427_macro_golden_active = False
        stance = order.get("stance")
        if stance == "defend":
            return self._defend_anchor()  # O37:主基塔够 → 蹲最暴露的分矿
        if stance == "retreat":
            return self.ai.start_location
        _q5_last_stand = q5_last_stand_active(
            now=getattr(self.ai, "time", 0.0),
            fleet_count=(
                self.manager_mediator.get_own_unit_count(
                    unit_type_id=UnitID.TEMPEST, include_pending=False
                )
                + self.manager_mediator.get_own_unit_count(
                    unit_type_id=UnitID.CARRIER, include_pending=False
                )
            ),
            deadline=getattr(
                self.ai, "_q5_last_stand_deadline", None
            ),
        )
        if _q5_last_stand:
            self._push_committed = True
            return self._terminal_cleanup_target()
        _cleanup_check = getattr(self, "_terminal_cleanup_active", None)
        if _cleanup_check is not None and _cleanup_check():
            self._push_committed = True
            return self._terminal_cleanup_target()
        if getattr(self.ai.production_manager, "_rush_active", False):
            # O40(game_01 实证):rush 守家不再恒守主基 —— 威胁计数最高的分矿
            # 承压 → 全军去救(死守主基 = 二矿落地 45s 被推白送);
            # 主基承压/无明确威胁 → 主基(旧行为)。
            return self._rush_defend_anchor()
        # O148-①/O149-③:过渡形态地面守坡口(双矿时守两矿中点)——
        # 过渡配方(叉/追猎)是防守兵,不推进不追敌(走出塔程进狗群 =
        # trickle 送死);坡口内侧卡位点让狗排队上坡,塔/叉双打
        # O152-②(o151 局2/局5 实证):波次指向分矿(敌进分矿 40 格 ≥3)
        # → 守军主动接应到该分矿,不再死蹲主基/中点(分矿 643/860 连掉)
        # O153-③修正:主基本身遇袭 ≥3 → 不接应(接应把主基抽真空 = 换家死)
        if getattr(self.ai.production_manager, "_transition_active", False):
            _main_threat = sum(
                1 for u in self.ai.enemy_units
                if not u.is_structure and not u.is_flying
                and u.position.distance_to(self.ai.start_location) < 25
            )
            if not main_defense_first(_main_threat):
                hot = self._hot_base_anchor(min_threat=3)
                if hot is not None:
                    return hot
            # O289-②(司令观察/A 案):坡口墙武装期守军锚点=缝位(gap 内侧
            # 1.5 格)——_wall_gap_point 原无消费方(死代码),rush 窗外缝
            # 无人把守,狗群从 1 格缝挤上高地;守军站缝=肉身堵件,农民
            # 照常穿行。分矿告急(hot)仍优先接应,主基不被抽真空。
            _wall_hold = getattr(
                self.ai.production_manager, "_wall_hold_point", None
            )
            if _wall_hold is not None:
                return _wall_hold
            return self._ground_defend_point()
        if tgt := order.get("target"):
            if (pt := self._resolve_steer_target(tgt)) is not None:
                return pt

        # E3g:舰队成型前(pre_fleet 保底阶段)地面兵默认守家 —— 无令时默认追敌会把
        # 保底叉子拉过全图送进蟑螂群(trickle,e3g game_01 实证:6 叉在敌波到脸前消失)。
        # stance/rush/司令 target 都在上面已 return,不受影响;主 C 上线恢复默认进攻。
        if floor_army_defends_home(
            has_pre_fleet=self._flow.pre_fleet is not None,
            primary_count=self.manager_mediator.get_own_unit_count(
                unit_type_id=self.ai.production_manager._primary_unit_id()
            ),
            enemy_race_name=getattr(getattr(self.ai, "enemy_race", None), "name", None),
        ):
            return self._defend_anchor()  # O37:保底地面兵蹲最暴露的基地,不扎堆主基

        # O44(carrier 流,o43 bench 实测):默认推进要决定性优势 —— 波间隙追敌,
        # 新一波刷出 → 模拟刹车半路拉回家 → 航母撤退途中被腐化点名(yo-yo 磨光舰队,
        # 4 基地防下 6 波 85 supply 却 60 分钟收不下比赛)。优势不够就蹲锚点,
        # 让对面继续往塔阵送(多矿消耗战我方必胜);敌被榨干(可见≈0)自然收割。
        # O45(Harder game_01 实证):推进还要过硬对空安全线 —— 14 航母撞
        # 腐化+飞蛇群 = 团灭;硬对空(CORRUPTOR/VIKING/PHOENIX/VIPER)够厚就继续蹲。
        if self._flow.name == "carrier":
            _carriers = self.manager_mediator.get_own_unit_count(
                unit_type_id=UnitID.CARRIER,
                # O378-①(o377b 尸检):O377-④ 是假修复 —— 注释写了在场
                # 口径但没传 include_pending=False(get_own_unit_count
                # 默认 include_pending=True 加算 cy_unit_pending),
                # 在产/队列仍虚高:o377b g2 @890 报 fleet=5 在场仅 2、
                # g1 @870.6 报 5 在场 3、o377a g2 @812.6 报 9 在场 6,
                # 真实出击舰队降到 2-4 出门捐给 76-96 supply 波。
                include_pending=False,
            )
            # O60:暴风主 C 配比 —— 推进判据的「舰队」按航母+暴风合计
            # (暴风射程 10 压腐化 6,本身就是对空答案,不能只数航母)
            _tempests = self.manager_mediator.get_own_unit_count(
                unit_type_id=UnitID.TEMPEST,
                include_pending=False,  # O378-①:同上,在产不计入出击口径
            )
            _hard_aa = sum(
                1 for e in self.ai.enemy_units
                if not e.is_structure
                and e.type_id in self._HARD_AA
            )
            _fleet_count: int = _carriers + _tempests
            # O377-④(o376a g3 尸检):舰队计数口径剔除在产/队列,只算
            # 在场 —— O376-⑤ 的含在产口径被实证击穿:g3 在 776.1s
            # 报 fleet=6,在场仅 3 艘(在产/队列虚高),按虚高数过
            # 下限出击 = 纸面舰队。出击下限(push_fleet_floor_ok)
            # 与配方推豁免(recipe_push_exempt)只吃在场口径;生产
            # 侧 _fleet_total_now 含在产口径不动(本判据只管出击)。
            _fleet_total: int = _fleet_count
            # O164/O195(o194-vh-zerg-rush game_01 实证):舰队成型后(航母+暴风 ≥8)
            # 且游戏时间 >9 分钟仍蹲家 → 强制推进,不再等待 supply 优势。
            # 原阈值 10 艘/10 分钟在 Rush 局优势顶点 9 艘不触发,导致被滚雪球。
            # O227(o224-lane1 game_01 实证):Zerg Timing 舰队顶点只有 6 艘
            # (气烂 1806 矿恒 <70,8 艘永远到不了),蹲 = 等敌 90 supply 滚平;
            # Timing 阈值降到 6 艘,带塔/地面窗口期反打一波断敌运营。
            _pm_o227 = getattr(self.ai, "production_manager", None)
            _is_zerg_timing = (
                _pm_o227 is not None
                and getattr(_pm_o227, "_opp_race", "") == "zerg"
                and getattr(_pm_o227, "_ai_build", "") == "timing"
            )
            _current_opp_race = (
                getattr(_pm_o227, "_opp_race", "")
                if _pm_o227 is not None else ""
            )
            _current_ai_build = (
                getattr(_pm_o227, "_ai_build", "")
                if _pm_o227 is not None else ""
            )
            _is_zerg_macro = (
                _current_opp_race == "zerg"
                and _current_ai_build == "macro"
            )
            _push_floor = carrier_push_fleet_floor(
                _current_opp_race, _current_ai_build
            )
            _push_fleet_need = (
                6 if _is_zerg_timing else max(8, _push_floor)
            )
            # O241(0-30 回归排查):O232 的劣势闸让 bot 全程被动挨打,zerg 自由
            # 运营到 2 倍兵力;回滚到舰队 6+t>540 即强推(两场胜局都是主动
            # 压出去打的)。其他组合保持原判据不变。
            _force_push: bool = (
                _fleet_count >= _push_fleet_need
                and getattr(self.ai, "time", 0.0) > 540.0
            )
            # O380-⑤(o379 六局出击 0-1 次):t>=900 仍只有 2-4 艘
            # 舰队、但家中防御达标时，开一次 60s 豁命推进/换家窗。
            # 对空安全、腐化信用硬闸与 commit 重评全部仍在下方统一执行。
            _now = getattr(self.ai, "time", 0.0)
            if (
                not getattr(self, "_o380_desperation_used", False)
                and carrier_desperation_push_allowed(
                    opp_race=_current_opp_race,
                    ai_build=_current_ai_build,
                )
                and _now >= 900.0
                and desperation_push_window(
                    _now,
                    _fleet_count,
                    self.ai.production_manager._defense_score(),
                )
            ):
                self._o380_desperation_used = True
                self._o380_desperation_until = _now + 60.0
                if (_evs := getattr(self.ai, "_events", None)) is not None:
                    _evs.append({
                        "t": round(_now, 1),
                        "msg": f"O380:舰队未成型豁命推进窗(fleet={_fleet_count},60s)",
                    })
            _force_push = _force_push or _now < getattr(
                self, "_o380_desperation_until", 0.0
            )
            # O302(司令 2026-08-17 拍板·先手压制专项):O241 强推闸实证整局
            # 不触发(舰队卡 4-6 艘)。跨 40 局敌编成取证:850s+ 敌必转腐化+
            # 大龙(暴风被克,0 胜);750-800s 敌纯蟑螂/刺蛇(蟑螂不能对空)
            # = 暴风无克制黄金窗。窗口内降闸(阈值见 zt_golden_window_push:
            # 舰队 ≥3 + 追猎 ≥6 + 腐化 ≤4,t≥750 追猎衰减到 4,O354-③),
            # 抢在腐化转型前打死/打残;召回/安全线不变,推不动会被波次
            # 自然叫回家。
            _timing_golden_push = (
                _is_zerg_timing
                and zt_golden_window_push(
                    getattr(self.ai, "time", 0.0),
                    _fleet_count,
                    self.manager_mediator.get_own_unit_count(
                        unit_type_id=UnitID.STALKER
                    ),
                    # O304-②:快尖塔局腐化早出 = 无黄金窗,否决(不送暴风)
                    corruptors=sum(
                        1 for u in self.ai.enemy_units
                        if u.type_id == UnitID.CORRUPTOR
                    ),
                    # O326-③:尖塔可见 = 腐化 30-60s 内必到,整局否决
                    spire_seen=any(
                        s.type_id in (UnitID.SPIRE, UnitID.GREATERSPIRE)
                        for s in self.ai.enemy_structures
                    ),
                )
            )
            _macro_golden_push = (
                _is_zerg_macro
                and zerg_macro_golden_window_push(
                    now=getattr(self.ai, "time", 0.0),
                    fleet_count=_fleet_count,
                    stalkers=self.manager_mediator.get_own_unit_count(
                        unit_type_id=UnitID.STALKER,
                        include_pending=False,
                    ),
                    corruptor_credit=max(
                        sum(
                            1 for u in self.ai.enemy_units
                            if u.type_id == UnitID.CORRUPTOR
                        ),
                        self._o374_aa_peak,
                    ),
                )
            )
            _golden_push = _timing_golden_push or _macro_golden_push
            self._o427_macro_golden_active = _macro_golden_push
            _force_push = _force_push or _golden_push
            # O325-②:黄金窗 near-miss 簿记(30s 节流)—— 舰队达线但被追猎/
            # 腐化闸挡住的窗口直接可见,下轮尸检不用逐帧重建。
            if (
                _is_zerg_timing
                and not _golden_push
                and getattr(self.ai, "time", 0.0) >= 650.0
                and _fleet_count >= 3
                and self.ai.time - getattr(self, "_o325_nm_ts", 0.0) > 30.0
            ):
                self._o325_nm_ts = self.ai.time
                self.ai._events.append({
                    "t": round(self.ai.time, 1),
                    "msg": (
                        f"O325:黄金窗near-miss(舰队{_fleet_count},"
                        f"追{self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.STALKER)},"
                        f"腐化{sum(1 for u in self.ai.enemy_units if u.type_id == UnitID.CORRUPTOR)})"
                    ),
                })
            # O371-②(o370b 尸检):推进加敌军校验闸 —— o370b g3 以
            # fleet=4 对敌 47 supply 主动推进(569.5s)纯送;g1 900s
            # 损失风暴×2、g2 敌 11 维京 vs 我 5 风暴(维京 ≥4 风暴
            # 被点名)。「优势推/满人口全攻」路径必须敌可见 supply ≤
            # 我方 army supply(O373-⑥ 由 ×1.5 收紧,并兼任 O302 出发
            # 闸:o372a g1 舰队 5 于 562.9s 顶波出击,3 秒后敌 46
            # supply 波进门连掉三矿;合并单判不双判)且 敌硬对空 <4;
            # 不满足 → 不推进,
            # 走下方既有热点回防/蹲守锚点(O63/O37 后撤逻辑,不发明
            # 新分支)。两处豁免:① _force_push(O164/O241 舰队成型
            # +timeout 强推,蹲=必输的兜底,g3 的 fleet=4 本就走不到
            # 这条);② zerg 全局(O302 黄金窗是胜局实证的主动压出,
            # zerg 侧行为一行不变)。
            _own_army = self.ai.supply_used - self.ai.supply_workers
            # O375-④(o374b g2 实证):敌 supply 口径改信用值
            # (max(当帧可见, remembered 峰值;O376-③ 起窗 120s),
            # _enemy_army_supply_credited)—— g2 两次 O302 commit 后
            # 3-10s 敌 51-79 supply 才显形,只认当帧 = 波进迷雾即
            # 归零,出击即顶波;与 O375-② 塔地板共用同一台账。
            _enemy_vis = self.ai.production_manager._enemy_army_supply_credited()
            _opp_is_zerg = (
                _pm_o227 is not None
                and getattr(_pm_o227, "_opp_race", "") == "zerg"
            )
            # O382-④(司令观察/o381b g1):Terran 空中部队已清零、
            # 场上只剩坦克等地面部队时，已成型的暴风+航母不应
            # 继续打「最近敌建筑」的低价值消耗。仅在现有出击闸最终
            # 放行后，把目标改为最外围已知分矿；主力级压家召回、
            # 维京/解放者等对空重评与硬安全线仍由原链统一处理。
            _opp_is_terran = (
                _pm_o227 is not None
                and getattr(_pm_o227, "_opp_race", "") == "terran"
            )
            if _force_push and not terran_timing_force_push_allowed(
                opp_race=(
                    getattr(_pm_o227, "_opp_race", "")
                    if _pm_o227 is not None else ""
                ),
                ai_build=(
                    getattr(_pm_o227, "_ai_build", "")
                    if _pm_o227 is not None else ""
                ),
                own_army_supply=_own_army,
                credited_enemy_supply=_enemy_vis,
            ):
                _force_push = False
            _visible_enemy_air_combat = sum(
                1
                for u in self.ai.enemy_units
                if u.is_flying and is_combat_type(u.type_id)
            )
            _zerg_econ_build = (
                getattr(_pm_o227, "_ai_build", "")
                if _pm_o227 is not None else ""
            )
            _opp_is_zerg_econ = (
                _opp_is_zerg
                and _zerg_econ_build in ("rush", "macro")
            )
            _known_economic_bases = ()
            if (
                (_opp_is_terran or _opp_is_zerg_econ)
                and self.ai.time >= 720.0
                and _fleet_count >= 8
                and _visible_enemy_air_combat == 0
                and _hard_aa == 0
            ):
                _known_economic_bases = self._known_enemy_townhalls()
            _economic_strike_target = None
            _economic_strike_race = ""
            if terran_economic_strike_window(
                opp_race="terran" if _opp_is_terran else "",
                now=self.ai.time,
                fleet_count=_fleet_count,
                visible_enemy_air_combat=_visible_enemy_air_combat,
                visible_hard_aa=_hard_aa,
                known_enemy_bases=len(_known_economic_bases),
            ):
                _economic_strike_race = "terran"
                _economic_strike_target = _known_economic_bases[-1].position
            elif zerg_rush_economic_strike_window(
                opp_race="zerg" if _opp_is_zerg_econ else "",
                ai_build=_zerg_econ_build if _opp_is_zerg_econ else "",
                now=self.ai.time,
                fleet_count=_fleet_count,
                visible_enemy_air_combat=_visible_enemy_air_combat,
                visible_hard_aa=_hard_aa,
                known_enemy_bases=len(_known_economic_bases),
            ):
                _economic_strike_race = "zerg"
                _economic_strike_target = _known_economic_bases[-1].position
            # O374-②(o373b g2/o373a g1 尸检):zerg 出发豁免收窄 —
            # 旧「zerg 全局豁免」使出发闸在 zerg lane 形同虚设
            # (o373b g2 顶波团灭、o373a g1 出击 6s 后被抄家);敌可见
            # supply ≥ 我方 ×1.5 即便 zerg 也拦(zerg_departure_floor_ok)。
            # 黄金窗豁免保留:_golden_push 走 _force_push 通道不过本闸,
            # 不动的胜局打法一行不变。
            # O376-②(o375 双 lane 尸检):盲推硬闸并入本判(不三判)——
            # 信用 supply=0(当帧可见+remembered 峰值全空)= 对敌情
            # 一无所知,出击即盲推(o375a g1 撞 57→85 supply 主力、
            # o375b g2 commit 后 0.3s 敌 37 supply 显形团灭);信用
            # supply 含 O376-③ 的 120s 粘滞峰值,真「被榨干」局末次
            # 接触 120s 内仍认账,不误伤收割;_force_push/黄金窗通道
            # 豁免不动。
            # O377-①b(o376a 三局 0/3 尸检):配方推豁免的主基就绪塔
            # 口径与下方 O375-① 同源(就绪 PHOTONCANNON 距主基 <12
            # 格),提到闸前只算一次,terran 才取(zerg 恒 0,豁免
            # 判据内部也限 terran,双保险)。
            _o375_main_cn = (
                sum(
                    1
                    for s in self.ai.structures.ready
                    if s.type_id == UnitID.PHOTONCANNON
                    and s.position.distance_to(self.ai.start_location) < 12
                )
                if (
                    _pm_o227 is not None
                    and getattr(_pm_o227, "_opp_race", "") == "terran"
                )
                else 0
            )
            # O377-①b:配方推豁免 —— terran 信用恒 0 时盲推闸常闭,
            # o373a 胜局配方首推(528.5s fleet=5 ×29)被整体删除,
            # o376a 首推推迟到 708-776s;豁免只豁免盲推闸,敌军校验
            # 闸与舰队下限仍生效(recipe_push_exempt)。
            _recipe_push = recipe_push_exempt(
                getattr(self.ai, "time", 0.0),
                _fleet_total,
                _o375_main_cn,
                getattr(_pm_o227, "_opp_race", "")
                if _pm_o227 is not None
                else "",
            )
            _army_gate_ok = (
                (
                    _opp_is_zerg
                    and zerg_departure_floor_ok(_own_army, _enemy_vis)
                )
                or push_enemy_army_gate(_own_army, _enemy_vis, _hard_aa)
            ) and (not blind_push_blocked(_enemy_vis) or _recipe_push)
            # O374-④b(o373a g1/g2 尸检):Terran 转型真空期(FB 落成→
            # 舰队成型)出击留守闸 —— g1 509.4s/g2 528.5s 的 O302 出击
            # 与敌 515/533s 抄家窗口重叠,舰队出门时家最空(550-700s
            # 舰队仅 2-6 艘对 MM 27-56 supply)。主基就绪塔 ≥2 或
            # 舰队达标才放行;否则 _army_gate_ok 收 False,风暴守家
            # 不跟压(走下方既有热点回防/蹲守锚点,不发明新分支)。
            # 塔口径与 production_manager 的 _cannons_near 同源
            # (就绪 PHOTONCANNON 距基地 <12 格)。
            # O375-①(o374a 三局 0/3 尸检):去 min 化+条件收窄 ——
            # 旧「min(全基地就绪塔)<2 且 fleet<8」几乎常态成立(新矿
            # 0 塔即全局锁死),FB 落成起锁到死:O302 从 o373a 胜局
            # ×29 掉到 0/0/2;o374a g3 舰队 757.3s 刚到 8 立即解锁 ×2
            # (时间戳严丝合缝);「留守保家」被证伪(三局舰队全在家,
            # 527-561s 波照样穿)。塔口径改主基(新矿 0 塔不再全局锁;
            # 不选「任一基地 ≥2」—— 新矿 2 塔主基裸奔时放行 = 换家),
            # fleet 释放线 8→5(对齐胜局配方 528.5s fleet=5 起推
            # ×29),hold 只在 threat_active(敌波压境)时生效,无波
            # 不锁。
            if (
                _pm_o227 is not None
                and getattr(_pm_o227, "_opp_race", "") == "terran"
            ):
                # O377-①b:_o375_main_cn 已在闸前算好(与配方推豁免
                # 共用一次口径计算),本块直接复用。
                if transition_push_hold(
                    fb_done=(
                        getattr(_pm_o227, "_fb_completed_at", None) is not None
                    ),
                    fleet_count=_fleet_count,
                    main_base_cannons=_o375_main_cn,
                    threat_active=getattr(_pm_o227, "_threat_active", False),
                ):
                    _army_gate_ok = False
            # O372-⑤(o371a g2 尸检):推进 commit 期 AA 30s 重评 ——
            # g2 在 656-765s fleet=5-7 推进 ×4,维京 695s 才露面
            # (20 架)后仍 commit,舰队团灭:carrier_push_safe 只认
            # 当帧可见硬对空,维京出视野(或尚未露面)即放行,星港
            # (维京产能)曾见也不构成预警。每 30s 重评:可见硬对空
            # (_HARD_AA 口径)+ remembered 星港预警(+2,sc2 的
            # enemy_structures 含迷雾快照)≥4 → 撤蹲,回既有蹲守
            # 锚点(O63 热点/O37 静态锚,不发明新分支);重评间隔内
            # 旗标粘滞,可见性抖动不反复收放。zerg 豁免(同 O371-②
            # 教义:O302 黄金窗是胜局实证打法,自带腐化闸)。
            # O373-⑤(o372b g1 实证):zerg 豁免加上限 —— g1 蹲守
            # 不还,1117s 撞 20 腐化+4 大龙团灭(commit 期豁免零对空
            # 重评兜底);可见腐化+大龙 ≥8(zerg_aa_exemption_capped)
            # 即便 zerg 也走本重评撤蹲。
            _zerg_cb = sum(
                1
                for u in self.ai.enemy_units
                if u.type_id in (UnitID.CORRUPTOR, UnitID.BROODLORD)
            )
            # O374-①(o373b g2 尸检):zerg AA 信用记忆 —— g2 在
            # 1111.8s O302 出击:17 腐化 1098.7s 离视野,13s 后撤蹲
            # 和出发闸全开(只认当帧可见),舰队 11→1 团灭;1068.8s
            # 起 AA≥8(峰 22@1129)但无撤蹲日志。计数改信用口径:
            # 60s 粘滞峰值(aa_peak_sticky 簿记,期内不归零)+ 尖塔
            # 曾见 +2(SPIRE/GREATER_SPIRE = 腐化产能,与星港 +2
            # 同教义;enemy_structures 含迷雾快照),撤蹲豁免帽与
            # 重评输入都吃信用计数(zerg_aa_credited)。
            _spire_seen = any(
                s.type_id in (UnitID.SPIRE, UnitID.GREATERSPIRE)
                for s in self.ai.enemy_structures
            )
            self._o374_aa_peak, self._o374_aa_peak_at = aa_peak_sticky(
                self.ai.time,
                _zerg_cb,
                self._o374_aa_peak,
                self._o374_aa_peak_at,
            )
            _zerg_cb_eff = zerg_aa_credited(
                _zerg_cb, self._o374_aa_peak, _spire_seen
            )
            # O379-①(o378b g1 尸检):信用腐化硬闸接到 _force_push
            # 统一出口 —— O378-⑥a 的闸只收 _army_gate_ok 通道,zerg
            # lane 的 O302 出击几乎全走 _force_push(fleet≥8+t>540,
            # 设计上豁免),g1 五次在信用腐化 5-18 下出击(1442@9、
            # 1472@5、1611@8、1770@18、1871@5),舰队 13-18 艘分批
            # 喂腐化群全灭 —— O378-⑥ 要防的死法原样重演。同口径
            # (max(当帧,60s 粘滞峰),O374-① 台账)fleet ≥ 信用腐化
            # ×1.5 才放行,否则 _force_push 收 False 走下方既有蹲守/
            # 消耗逻辑(不发明新分支);黄金窗(_golden_push,
            # zt_golden_window_push 自带腐化 ≤4 闸)不受影响。
            if (
                _opp_is_zerg
                and _force_push
                and not _golden_push
                and not force_push_corruptor_ok(
                    _fleet_count, max(_zerg_cb, self._o374_aa_peak)
                )
            ):
                _force_push = False
            # O378-⑥a(o377b g1 实证):信用腐化硬闸 —— g1 同一秒
            # 「塔投资冻结(腐化≥4)」舰队却在出门(塔链认账腐化
            # ≥4,出击闸不认);三局共同死因 = 舰队峰 10/14/16 拖过
            # 1200s 进腐化+大龙窗口被全歼。信用腐化(当帧可见 ∪
            # 60s 粘滞峰值,与 O374-① 台账同源)≥4 → O302 出击闸
            # 收 False;zerg 不豁免本闸(暴风被腐化完克);黄金窗
            # (zt_golden_window_push 自带腐化 ≤4 闸)不动;_force_push
            # 通道由上方 O379-① 同口径闸覆盖(o378b 起,不再豁免)。
            if _opp_is_zerg and zerg_corruptor_departure_blocked(
                max(_zerg_cb, self._o374_aa_peak)
            ):
                _army_gate_ok = False
            if not _opp_is_zerg or zerg_aa_exemption_capped(_zerg_cb_eff):
                # O378-⑥b(o377b 三局团灭尸检):重评时机改
                # aa_reeval_due —— 30s 定期对暴风太短(28s 内舰队
                # 死在两次重评之间);信用对空计数 ≥4 且较上次重评
                # 上升(新增腐化显形)立即重评,下降/持平稳粘滞
                # 不反复收放。
                _aa_credited = (
                    # O374-①:zerg 走信用口径(腐化离视野 60s 内
                    # 仍计入,覆盖 g2 的 13s 视野洞);terran 原
                    # 口径(可见 _HARD_AA)一行不动。
                    max(_hard_aa, _zerg_cb_eff) if _opp_is_zerg else _hard_aa
                )
                if aa_reeval_due(
                    self.ai.time,
                    self._o372_aa_eval_at,
                    _aa_credited,
                    self._o378_aa_last_credited,
                ):
                    self._o372_aa_eval_at = self.ai.time
                    self._o378_aa_last_credited = _aa_credited
                    self._o372_aa_retreat = push_commit_aa_retreat(
                        _aa_credited,
                        any(
                            s.type_id == UnitID.STARPORT
                            for s in self.ai.enemy_structures
                        ),
                    )
                if self._o372_aa_retreat:
                    if (hot := self._hot_base_anchor()) is not None:
                        return hot
                    return self._defend_anchor()
            if not (
                (
                    _force_push
                    or (
                        _army_gate_ok
                        # O376-⑤(o375b 尸检):出击舰队下限 4→6
                        # —— g2 两次 fleet=4 出击无果+撞波;黄金窗/
                        # _force_push 通道不走本闸,一行不变。
                        # O377-①a/④(o376a 尸检):下限 6→5(对齐 o373a
                        # 胜局配方 528.5s fleet=5 首推),口径改在场
                        # (g3 报 6 实 3 的在产虚高剔除)
                        and push_fleet_floor_ok(
                            _fleet_total, floor=_push_floor
                        )
                        and (
                            should_push_advantage(
                                _own_army,
                                _enemy_vis,
                                # O59(o58 实证):航母 ≥6(临界质量)后均势即推 —— 龟到对面
                                # 也满人口(98 supply)就是 max-vs-max 必输局;
                                # 趁我方舰队成型、对面未满(60-75 supply)时打。
                                # O60:临界线按舰队合计(航母+暴风 ≥8)
            # O227/O420:临界线随 _push_fleet_need
            # (Zerg Timing 6、Zerg Macro 16、其余 8)
                                margin=(
                                    0.0
                                    if _fleet_count >= _push_fleet_need
                                    else 15.0
                                ),
                            )
                            # O70(司令观察,t≈1740 实证):接近满人口(≥95%)+存款充足
                            # (≥1500) → 全力进攻,跳过 supply 优势检查 —— 满人口攒不出
                            # 更多兵,蹲是纯亏;5000+ 存款换血永远我方赚(对面死一个少一个)。
                            # 硬对空安全线不动:舰队是产能瓶颈,存款买不回重建时间。
                            or full_pop_all_in(
                                self.ai.supply_used,
                                self.ai.supply_cap,
                                self.ai.minerals,
                            )
                        )
                    )
                )
                and carrier_push_safe(_fleet_count, _hard_aa)
            ):
                # O63(game_01 实证):蹲守阶段基地被围攻(≥6) → 舰队回防热点基地。
                # Power 的持续小队(10-18 地面)轮抄分矿,静态锚点蹲错位 → 基地被
                # 逐个蚕食(4→3→4→2→…→1);舰队对无对空地面小队是降维打击。
                if (hot := self._hot_base_anchor()) is not None:
                    return hot
                # O252(Zerg Timing 先手骚扰,唯一未试过的战略维度):家无热点
                # (波间隙)且舰队 ≥3 → 压向敌最远端已知基地(新矿防御最薄),
                # 狙 Nexus/农民拖慢 Zerg 90-supply 成型;全程蹲守=敌自由运营
                # 到 2 倍兵力(近 20 局复盘共同特征)。暴风射程 10 压孢子/皇后。
                # O297-③(o296b game_02 实证):舰队 3-7 艘正是出门骚扰档 —
                # 小舰队在外,82-supply 波换家时回防不及(952s 损失暴风×2);
                # 骚扰是成型舰队(≥8)的特权,小舰队蹲守锚点保家优先。
                if _is_zerg_timing and _fleet_count >= 8:
                    _known = self._known_enemy_townhalls()
                    if _known:
                        return _known[-1].position
                return self._defend_anchor()
            # O64(o63 game_01 实证):推进窗口里只有主力级威胁(≥14)才召回 ——
            # ≤13 的小队骚扰靠塔阵+电池+E6 撤离消化;见小队就召回 = 舰队被
            # 永久钉在防守跑步机(满人口 260+s 寸功未立,敌 4 hatch 无损,
            # 敌退缩避战 → 我们永远追不上,也永远推不出去)。
            # O113-②(o112 局4 实证):舰队 ≥12(临界质量)阈值抬到 25 ——
            # 波次喂食局(15-20 地面/波)阈值 14 每波必触发,22-29 暴风
            # 龟缩 500s 靠耗赢;塔+电池能消化的波不召回,换家比回防快
            _recall_threshold = fleet_no_recall_threshold(_carriers + _tempests)
            _recall_threshold = macro_golden_recall_threshold(
                _recall_threshold, _macro_golden_push
            )
            if _economic_strike_target is not None:
                # O384-②(o383 Terran g2):1064s 斩分矿后，1146s
                # 10地面抄矿因正常舰队11的召回门14而被忽略，1202s
                # 升到15才回头已连掉经济。经济打击不是决死 all-in，
                # 基地10地面威胁即撤；普通推进的14/25门不动。
                _recall_threshold = economic_strike_recall_threshold(
                    _recall_threshold
                )
            if (hot := self._hot_base_anchor(
                min_threat=_recall_threshold
            )) is not None:
                return hot
            # O65(o64 game_01 实证):闸全开放行 → 标记推进承诺,TempestOffensive
            # 进「行军模式」(不追 15 格内的过路敌,只打进了射程的,主力压向
            # attack_target)。否则小队骚扰在行为层把每艘暴风永久钩在原地
            # 风筝,attack_target 给得再对舰队也永远走不出去。
            # O302-②:推进/召回簿记 —— 压制窗是否触发、触发时兵力,下轮尸检
            # 直接读(此前推进静默,无法判断闸不开是没到窗还是被否决)。
            # O303-①(o302b game_04 实证):_push_committed 在集结期每帧复位,
            # 事件逐帧刷屏 —— 30s 节流。
            if not self._push_committed and (
                self.ai.time - getattr(self, "_o302_logged_at", 0.0) > 30.0
            ):
                self._o302_logged_at = self.ai.time
                _evs = getattr(self.ai, "_events", None)
                if _evs is not None:
                    _evs.append({
                        "t": round(self.ai.time, 1),
                        "msg": (
                            f"O302:先手压制推进(fleet={_fleet_count},"
                            f"追猎={self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.STALKER)},"
                            f"黄金窗={_golden_push})"
                        ),
                    })
            self._push_committed = True
            if _economic_strike_target is not None:
                if not getattr(self, "_o382_economic_strike_active", False):
                    _evs = getattr(self.ai, "_events", None)
                    if _evs is not None:
                        _evs.append({
                            "t": round(self.ai.time, 1),
                            "msg": (
                                (
                                    "O382:Terran制空后主动斩断分矿"
                                    if _economic_strike_race == "terran"
                                    else "O390:Zerg波间隙主动斩断分矿"
                                )
                                + f"(fleet={_fleet_count},已知基地={len(_known_economic_bases)})"
                            ),
                        })
                self._o382_economic_strike_active = True
                return _economic_strike_target
            self._o382_economic_strike_active = False

        # —— 默认逻辑（无命令时）：最近敌建筑 → 轮巡分矿 ——
        if self.ai.enemy_structures:
            return self.ai.enemy_structures.closest_to(self.ai.start_location).position
        else:
            # cycle through base locations
            if self.ai.is_visible(self.current_base_target):
                if not self.expansions_generator:
                    base_locations: list[Point2] = [
                        i for i in self.ai.expansion_locations_list
                    ]
                    self.expansions_generator = cycle(base_locations)

                self.current_base_target = next(self.expansions_generator)

            return self.current_base_target

    async def update(self, iteration: int) -> None:
        """This is only currently required to execute tempest micro.

        Parameters
        ----------
        iteration
        """
        # 参谋长喊"龟"(hold)：原地不动，不推进
        order = getattr(self.ai, "steer_order", None) or {}
        if order.get("stance") == "hold":
            return

        # ⑥择时：条件没到先按兵不动（now/None=立即；when_maxed=攒满再打；when_enemy_away=等敌出门）
        from bot.levers import should_hold_for_trigger
        if should_hold_for_trigger(
            order.get("trigger"),
            supply_used=self.ai.supply_used,
            enemy_near_base=self._enemy_near_their_base(),
        ):
            return

        # 按 army_composition 逐兵种指挥:取该兵种的 ATTACKING 单位,交给它配置的 combat class。
        # 同一 combat class 的多兵种会各自 execute 一次(tempest/追猎各打各的),攻击点/焦点/机动共享。
        # C3a 集结纪律:兵力低于 rally_min_army 且司令没下 stance 时,先守家攒兵(治分批送死);
        # 司令下了 stance(attack/defend/...)以司令为准,集结让位。
        # E8(O17/O18):阈值按侦查结论动态化(rally_min_for_verdict)——verdict=greedy
        # 减半(小股提早压);=rush 收紧到 max(×2, 6)(集结积攒再打);=unknown/None 维持。
        # 非 carrier 流 verdict 恒 None → 行为不变。
        _rally = rally_min_for_verdict(
            self._rally_min, getattr(self.ai.production_manager, "verdict", None)
        )
        # O23:航母流且敌有对空威胁时,舰队数<gate → 守家攒兵(1-2 艘撞雷神/维京=送)
        # O66(o65 game_01 实证):计数按航母+暴风合计(同 O60 推进判据口径) ——
        # 暴风主 C 配比下航母常只 1-2 艘,只数航母 = 任何对空单位一露面
        # _aa_hold 就锁死(carriers 1 < gate 3),22 暴风被 O23 钉死在集结锚点,
        # 推进闸/行军模式全成了摆设(O23 写于航母主 C 时代,口径过期)。
        _aa_hold = order.get("stance") is None and carrier_rally_against_aa(
            self._flow.name,
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER)
            + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST),
            self._enemy_aa_count(),
        )
        # O158:基地被压缩到 <2 个时舰队守家保经济——再丢基地=没收入,
        # 舰队出门推导致分矿/主矿被抄是 O156/O157 长时败局的主因。
        # O178(o176-vh-zerg-power-headless game_01 1800s 超时):2 基地且大舰队时
        # 仍守家导致永远推不出去,被 AI 拖到超时;改为 <2 基地才强制守家。
        # O195(o194-vh-zerg-rush game_01/03 实证):只剩 1 基地时若已有成型舰队,
        # 继续强制守家会进入「丢基地→推不出去→被滚雪球」死循环。舰队 ≥8 且
        # t>9min 时允许出门换家/抢回基地,而不是蹲家等死。
        # O195:单基地且成型舰队时不再强制蹲家(计算口径同 O60:航母+暴风合计)
        _fleet_now = (
            self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.CARRIER)
            + self.manager_mediator.get_own_unit_count(unit_type_id=UnitID.TEMPEST)
        )
        _home_guard = (
            order.get("stance") is None
            and self.ai.townhalls.amount < 2
            and not (_fleet_now >= 8 and getattr(self.ai, "time", 0.0) > 540.0)
        )
        _terminal_cleanup = self._terminal_cleanup_active()
        if (
            not _terminal_cleanup
            and (
                (order.get("stance") is None and 0 < self._own_army_count() < _rally)
                or _aa_hold
                or _home_guard
            )
        ):
            attack_target = self._defend_anchor()  # O37:守家攒兵蹲最暴露的基地
            self._push_committed = False  # O65:集结/对空攒兵期不算推进承诺
        else:
            attack_target = self.attack_target
        # B3 can_win_fight 接战刹车:模拟器判负 → 目标改为撤回主基地(只当一票否决)
        if not _terminal_cleanup:
            attack_target = self._apply_combat_sim_brake(attack_target)
        # O386-②:保留 O302/O382 算出的战略目标。下面 O217/O219 仍可把
        # 地面守军改派回家，但经济打击舰队只在真正达到10人召回门时让位。
        _strategic_attack_target = attack_target
        # O217(司令观察):基地内残敌清剿 —— 大战后敌小股(1-5)滞留基地拆建筑,
        # 攻击目标改为残敌位置,先清再推(≥6 的大波走 O205/_hot_base_anchor)。
        _intruder = None if _terminal_cleanup else self._base_intruder_target()
        if _intruder is not None:
            if not self._intruder_cleanup_active:
                self._intruder_cleanup_active = True
                events = getattr(self.ai, "_events", None)
                if events is not None:
                    events.append({
                        "t": round(self.ai.time, 1),
                        "msg": "O217:基地残敌清剿(敌小股滞留基地拆建筑,先清再推)",
                    })
            attack_target = _intruder
        else:
            self._intruder_cleanup_active = False
        # O219(司令观察):敌主力(≥6)压上任一基地 → 全军协防该基地(骚扰编制
        # 如 oracle 不在本 manager 分派内,天然除外)。此前各分支锚点各自为政:
        # 集结期/对空攒兵/蹲守 → 主基或最暴露分矿;transition → 坡口/两矿中点;
        # 结果大波打二矿时只有空军回防(O205),地面守军蹲主基看戏,空军孤立阵亡、
        # 二矿被推平。统一盖到所有分支(含 sim 刹车/残敌清剿)之后,主力优先。
        hot_all = self._hot_base_anchor(
            min_threat=25 if _terminal_cleanup else 6
        )
        if hot_all is not None:
            attack_target = hot_all
        # B6 Squad 化:主力 squad 中心做散兵归队锚点(拿不到 → None 降级现状)
        regroup_center = self._main_squad_center()
        # O148-②:防守战(rush/过渡/威胁)伤兵回撤点 —— 电池优先(能奶回来
        # 再上去),无电池取最近就绪塔;都不在 → None(不撤,站撸到底)
        _retreat_point = None
        _pm = self.ai.production_manager
        if (
            getattr(_pm, "_rush_active", False)
            or getattr(_pm, "_transition_active", False)
            or getattr(_pm, "_threat_active", False)
        ):
            _cover = [
                s
                for s in self.ai.structures.ready
                if s.type_id == UnitID.SHIELDBATTERY
            ] or [
                s
                for s in self.ai.structures.ready
                if s.type_id == UnitID.PHOTONCANNON
            ]
            if _cover:
                _retreat_point = min(
                    _cover, key=lambda s: s.distance_to(self.ai.start_location)
                ).position
        _economic_strike_active = getattr(
            self, "_o382_economic_strike_active", False
        )
        _air_recall_threshold = 6
        if _terminal_cleanup:
            _air_recall_threshold = 25
        elif _economic_strike_active:
            _air_recall_threshold = economic_strike_recall_threshold(
                fleet_no_recall_threshold(_fleet_now)
            )
        _air_recall = self._air_fleet_recall_target(
            min_threat=_air_recall_threshold
        )
        _ground_defenders = sum(
            self.manager_mediator.get_own_unit_count(
                unit_type_id=uid, include_pending=False
            )
            for uid in (
                UnitID.ZEALOT,
                UnitID.STALKER,
                UnitID.IMMORTAL,
                UnitID.ARCHON,
            )
        )
        _fleet_onfield_for_split = sum(
            self.manager_mediator.get_own_unit_count(
                unit_type_id=uid, include_pending=False
            )
            for uid in (UnitID.TEMPEST, UnitID.CARRIER)
        )
        _strike_split = (
            _economic_strike_active
            and _air_recall is None
            and (_intruder is not None or hot_all is not None)
        )
        if _strike_split and not self._o386_strike_split_active:
            events = getattr(self.ai, "_events", None)
            if events is not None:
                events.append({
                    "t": round(self.ai.time, 1),
                    "msg": (
                        "O386:经济打击兵力分流"
                        f"(舰队继续斩经济,地面守军回防,舰队召回门={_air_recall_threshold})"
                    ),
                })
        self._o386_strike_split_active = _strike_split
        for spec in self._army.by_role("ATTACKING"):
            combat = self._combat_dispatch.get(spec.combat)
            if combat is None:
                continue  # oracle_harass 等不由本 manager 指挥
            unit_id = getattr(UnitID, spec.id_name, None)
            if unit_id is None:
                continue
            if units := self.manager_mediator.get_units_from_role(
                role=UnitRole.ATTACKING, unit_type=unit_id
            ):
                # O205:空军基地遇袭回防 —— 仅对空军生效,地面仍按原 attack_target
                _is_fleet_air = unit_id in self._FLEET_AIR_TYPES
                if _air_recall is not None and _is_fleet_air:
                    _unit_attack_target = _air_recall
                elif economic_strike_ground_holds_home(
                    is_fleet_air=_is_fleet_air,
                    economic_strike_active=_economic_strike_active,
                ):
                    _unit_attack_target = self._defend_anchor()
                elif macro_golden_zealot_holds_home(
                    active=getattr(
                        self, "_o427_macro_golden_active", False
                    ),
                    unit_name=unit_id.name,
                ):
                    _unit_attack_target = self._defend_anchor()
                elif carrier_fleet_keeps_strategic_target(
                    is_fleet_air=_is_fleet_air,
                    air_recall_active=False,
                    economic_strike_active=_economic_strike_active,
                    small_intruder_active=_intruder is not None,
                    fleet_count=_fleet_onfield_for_split,
                    ground_defenders=_ground_defenders,
                ):
                    _unit_attack_target = _strategic_attack_target
                else:
                    _unit_attack_target = attack_target
                combat.execute(
                    units,
                    attack_target=_unit_attack_target,
                    focus=order.get("focus"),        # ③焦点
                    maneuver=order.get("maneuver"),  # ④机动意图
                    regroup_center=regroup_center,   # B6 归队锚点(仅 generic 用,其余忽略)
                    # O148-②:防守战伤兵回撤点(仅 generic 用,其余忽略)
                    retreat_point=_retreat_point,
                    # O65:推进承诺(闸全开)→ 行军模式(仅 tempest 用,其余忽略)
                    commit_push=getattr(self, "_push_committed", False),
                )

    def _enemy_aa_count(self) -> int:
        """O23:敌可见对空威胁单位数(雷神/维京/导弹塔/寡妇雷/枪兵等 can_attack_air)。
        复用 carrier_offensive._aa_threats 同款口径(e.can_attack_air)。"""
        return sum(
            1 for e in self.ai.enemy_units
            if not e.is_structure and getattr(e, "can_attack_air", False)
        )

    def _own_army_count(self) -> int:
        """当前 ATTACKING 编制内的兵力数(按 army_composition 登记兵种数)。"""
        count = 0
        for spec in self._army.by_role("ATTACKING"):
            uid = getattr(UnitID, spec.id_name, None)
            if uid is not None:
                try:
                    count += self.manager_mediator.get_own_unit_count(unit_type_id=uid)
                except KeyError:
                    # cy_unit_pending 对变形形态(如 WARPPRISMPHASING)无 pending
                    # 数据会 KeyError —— 该兵种按 0 计,不让一个 spec 崩掉整局
                    # (E6c game_01-05 五连 ERROR 实证)
                    continue
        return count

    def _apply_combat_sim_brake(self, attack_target: Point2) -> Point2:
        """B3 can_win_fight 接战刹车(来源:ares CombatSimManager + QueenBot combat_queens
        + 12PoolBot micro.py;治 bench 信号 trickle/overrun —— 兵力反复崩落=逐个上去送)。

        模拟器判负(LOSS_*)→ 把 attack_target 改为我方主基地(撤)而不是压上。
        只当一票否决,不当进攻触发器(判胜不主动加压,维持原目标)。
        司令已下 stance(attack/defend/...)时以司令为准,不刹车(同 rally 让位原则)。
        模拟器异常/不可用 → 维持原行为(try/except 兜底)。
        """
        order = getattr(self.ai, "steer_order", None) or {}
        if order.get("stance") is not None:
            return attack_target
        from bot.levers import sim_combatants
        try:
            # 官方警告:模拟器不含微操/施法 —— 过滤农民和建筑,免得污染战力评估
            own = sim_combatants(self.manager_mediator.get_own_army())
            enemy = sim_combatants(self.ai.enemy_units)
            if not own or not enemy:
                return attack_target
            result = self.manager_mediator.can_win_fight(
                own_units=own, enemy_units=enemy
            )
            if result.name.startswith("LOSS"):
                if not self._sim_retreat_active:
                    self._sim_retreat_active = True
                    events = getattr(self.ai, "_events", None)
                    if events is not None:
                        events.append({
                            "t": round(self.ai.time, 1),
                            "msg": f"can_win_fight 判负({result.name}),全军撤回主基地",
                        })
                return self.ai.start_location
            self._sim_retreat_active = False
        except Exception:
            pass  # 模拟器异常 → 维持原进攻目标,不影响现有行为
        return attack_target

    def _main_squad_center(self) -> Point2 | None:
        """B6 Squad 化(来源:ares SquadManager 教程 + group behaviors;治"行军散队、
        局部少打多")。取 ATTACKING 最大 squad 的中心,做散兵归队锚点。
        渐进式:只用于归队,不改交战细节;任何异常 → None(降级到现状)。"""
        try:
            squads = self.manager_mediator.get_squads(
                role=UnitRole.ATTACKING, squad_radius=9.0
            )
            if not squads:
                return None
            main = max(squads, key=lambda s: len(s.squad_units))
            return main.squad_position
        except Exception:
            return None
