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
    two_base_guard_point,
    main_defense_first,
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

    def _air_fleet_recall_target(self) -> Point2 | None:
        """O205:任一 Nexus 15 格内 ≥6 敌地面 → 空军回防该基地,保留 10s 滞回。

        与 E6 工人撤离联动:触发 E6 的基地(阈值 4)与这里(阈值 6)部分重叠,
        大波(≥6)时空军同步回防。优先回防距主基最近的受威胁基地(主战方向)。
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
            min_threat=6,
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
        if _pm is not None and getattr(_pm, "_rush_active", False):
            return None
        ths = list(self.ai.ready_townhalls)
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
        candidates = self.ai.enemy_structures.filter(
            lambda s: s.type_id in townhall_types and s.position.distance_to(focus) < 80
        )
        return candidates.sorted(lambda s: s.position.distance_to(focus))

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
        stance = order.get("stance")
        if stance == "defend":
            return self._defend_anchor()  # O37:主基塔够 → 蹲最暴露的分矿
        if stance == "retreat":
            return self.ai.start_location
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
                unit_type_id=UnitID.CARRIER
            )
            # O60:暴风主 C 配比 —— 推进判据的「舰队」按航母+暴风合计
            # (暴风射程 10 压腐化 6,本身就是对空答案,不能只数航母)
            _tempests = self.manager_mediator.get_own_unit_count(
                unit_type_id=UnitID.TEMPEST
            )
            _hard_aa = sum(
                1 for e in self.ai.enemy_units
                if not e.is_structure
                and e.type_id in self._HARD_AA
            )
            _fleet_count: int = _carriers + _tempests
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
            _push_fleet_need = 6 if _is_zerg_timing else 8
            # O241(0-30 回归排查):O232 的劣势闸让 bot 全程被动挨打,zerg 自由
            # 运营到 2 倍兵力;回滚到舰队 6+t>540 即强推(两场胜局都是主动
            # 压出去打的)。其他组合保持原判据不变。
            _force_push: bool = (
                _fleet_count >= _push_fleet_need
                and getattr(self.ai, "time", 0.0) > 540.0
            )
            if not (
                (
                    _force_push
                    or should_push_advantage(
                        self.ai.supply_used - self.ai.supply_workers,
                        self.ai.production_manager._visible_enemy_army_supply(),
                        # O59(o58 实证):航母 ≥6(临界质量)后均势即推 —— 龟到对面
                        # 也满人口(98 supply)就是 max-vs-max 必输局;
                        # 趁我方舰队成型、对面未满(60-75 supply)时打。
                        # O60:临界线按舰队合计(航母+暴风 ≥8)
                        # O227:临界线随 _push_fleet_need(Zerg Timing 6,其余 8)
                        margin=0.0 if _fleet_count >= _push_fleet_need else 15.0,
                    )
                    # O70(司令观察,t≈1740 实证):接近满人口(≥95%)+存款充足
                    # (≥1500) → 全力进攻,跳过 supply 优势检查 —— 满人口攒不出
                    # 更多兵,蹲是纯亏;5000+ 存款换血永远我方赚(对面死一个少一个)。
                    # 硬对空安全线不动:舰队是产能瓶颈,存款买不回重建时间。
                    or full_pop_all_in(
                        self.ai.supply_used, self.ai.supply_cap, self.ai.minerals
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
            if (hot := self._hot_base_anchor(
                min_threat=fleet_no_recall_threshold(_carriers + _tempests)
            )) is not None:
                return hot
            # O65(o64 game_01 实证):闸全开放行 → 标记推进承诺,TempestOffensive
            # 进「行军模式」(不追 15 格内的过路敌,只打进了射程的,主力压向
            # attack_target)。否则小队骚扰在行为层把每艘暴风永久钩在原地
            # 风筝,attack_target 给得再对舰队也永远走不出去。
            self._push_committed = True

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
        if (
            (order.get("stance") is None and 0 < self._own_army_count() < _rally)
            or _aa_hold
            or _home_guard
        ):
            attack_target = self._defend_anchor()  # O37:守家攒兵蹲最暴露的基地
            self._push_committed = False  # O65:集结/对空攒兵期不算推进承诺
        else:
            attack_target = self.attack_target
        # B3 can_win_fight 接战刹车:模拟器判负 → 目标改为撤回主基地(只当一票否决)
        attack_target = self._apply_combat_sim_brake(attack_target)
        # O217(司令观察):基地内残敌清剿 —— 大战后敌小股(1-5)滞留基地拆建筑,
        # 攻击目标改为残敌位置,先清再推(≥6 的大波走 O205/_hot_base_anchor)。
        _intruder = self._base_intruder_target()
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
        if (hot_all := self._hot_base_anchor(min_threat=6)) is not None:
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
        _air_recall = self._air_fleet_recall_target()
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
                _unit_attack_target = (
                    _air_recall
                    if _air_recall is not None and unit_id in self._FLEET_AIR_TYPES
                    else attack_target
                )
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
