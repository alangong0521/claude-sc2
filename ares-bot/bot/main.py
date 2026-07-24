import os
from collections import Counter
from typing import Optional

from ares import AresBot, Hub, ManagerMediator
from ares.behaviors.macro import Mining, RestorePower
from ares.consts import ID as TRACKER_ID
from ares.consts import TIME_ORDER_COMMENCED, TOWNHALL_TYPES, UnitRole
from bot.production_plans import (
    builder_is_waiting,
    evacuation_clear,
    idle_builder_alarm,
    nexus_rebuild_viable,
    pick_evacuation_base,
    should_evacuate_workers,
    should_release_waiting_builder,
)
from bot.shield_battery import restore_with_batteries
from bot.selftune import SelfTuner
from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.position import Point2
from sc2.unit import Unit

from bot import steer
from bot.managers.combat_manager import CombatManager
from bot.managers.oracle_manager import OracleManager
from bot.managers.production_manager import ProductionManager

# 每隔几游戏秒发布 state.json + 读 orders.json
_STEER_EVERY: float = 4.0

# ── E6 农民被抄转移/协防 ──
_EVAC_RADIUS: float = 15.0    # 敌地面单位距 Nexus 多少格内算"进矿区"
_EVAC_THRESHOLD: int = 4      # 进矿区敌地面 ≥ 此数 → 该基地视为被抄
_CANNON_COVER: float = 9.0    # 就绪塔距 Nexus ≤ 此值 → 矿区在塔射程内
# 撤离农民挂 CONTROL_GROUP_ONE(ares 枚举里"use for anything not specified"的
# 兜底 role,vendored ares 无任何消费者):Mining/ResourceManager/idle 清扫/建造派工
# 都只认 GATHERING,撤离期间他们彻底不碰这些农民;敌退后归位 GATHERING 自动重上岗。
_EVAC_ROLE = UnitRole.CONTROL_GROUP_ONE
# 能覆盖矿区的静态防御(光子炮是神族主案;人/虫塔顺手兼容)
_STATIC_DEFENCE = {
    UnitID.PHOTONCANNON,
    UnitID.MISSILETURRET,
    UnitID.SPORECRAWLER,
    UnitID.SPORECANNON,
    UnitID.PLANETARYFORTRESS,
}


def release_from_build_tracker(mediator, tag: int) -> bool:
    """把工人从 ares 建造追踪（building_tracker）里摘除 —— 司令接管时调用。

    ares BuildingManager 每帧对 tracker 里的工人下 move/build 命令，**无视 role**
    （O2 实证：只把工人挪去 PERSISTENT_BUILDER，下一帧又被拉回建造点，司令抢不回来）。
    摘除后 BuildingManager 彻底放手，生产侧下帧会自动用别的矿工重新派建。
    镜像 ares `BuildingManager.remove_unit` 的计数维护，但不动 role（接管逻辑自己管）。
    纯记账操作，可单测。"""
    tracker: dict = mediator.get_building_tracker_dict
    if tag not in tracker:
        return False
    mediator.get_building_counter[tracker[tag][TRACKER_ID]] -= 1
    tracker.pop(tag)
    return True


def recall_scouting_workers(ai) -> int:
    """rush 确认后立即撤回全部侦查农民（O4）—— role 归 GATHERING 并派回最近矿脉。

    scout 是一次性指令（探完才自己回家），rush 征兆确认后农民还留在敌家等于白送。
    复用 pivot 的 rush 检测信号（production_manager.rush_active），不新造判据。
    steer scout 和 pivot 早侦查派出的农民都是 SCOUTING role，一处全覆盖。
    返回撤回数量（0 = 没有侦查农民在外，调用方据此只记一次事件）。纯操作函数，可单测。"""
    scouts = ai.mediator.get_units_from_role(role=UnitRole.SCOUTING)
    if not scouts:
        return 0
    for s in scouts:
        ai.mediator.assign_role(tag=s.tag, role=UnitRole.GATHERING)
        if ai.mineral_field:
            s.gather(ai.mineral_field.closest_to(s))
    return len(scouts)


def update_worker_evacuation(ai) -> None:
    """E6 农民被抄转移/协防(E3m 死因:game_01 农民 42→22、game_02 47→29,
    经济断气后 2000+ 气烂掉)。每帧跑一次,三件事:

    1. **检测**:敌地面单位距某基地 Nexus <_EVAC_RADIUS 且 ≥_EVAC_THRESHOLD
       → 该基地视为被抄(纯判据 production_plans.should_evacuate_workers)。
    2. **响应**(按优先级):
       a) 矿区有就绪塔(_CANNON_COVER 内)且敌兵规模塔罩得住(<6+4×塔数)
          → 农民继续采,塔会打,本函数不动;塔被压垮(如 22 狗+9 蟑螂波)照撤
          (E6 bench 实证:塔覆盖≠安全,大波 ~20s 拆光塔再屠农);
       b) 无塔保护/塔被压垮 → 该矿线农民(role 归 _EVAC_ROLE 脱离 Mining/建造
          派工/idle 清扫)撤向最近有塔基地,都没有则最近基地;途中到点先就地采
          (别站着)。单基地无塔无处可撤 → 不动,交 ares Mining keep_safe 个体避险;
       c) 就近有地面防御兵力 → 事件里标记集结点(**不强行微操**,
          rush/stance/集结纪律的优先级都在 combat_manager,不抢)。
    3. **回采**:敌地面 <2(滞回,防边界抖动往返)或基地已丢(O15 重建接管)
       → 全员归 GATHERING 回最近矿脉,ares ResourceManager 自动重新分配。

    与现有机制的关系:
    - rush 期**主基**不新增撤离(六连动全权接管主基防守,行为不变);
      **分矿不受 rush 门**(E6 bench 实证:VeryHard/Rush 的 rush_active 从首接敌
      一路续过中段波,全局 rush 门让 E6 在目标场景永不触发=死代码;分矿撤离
      与 rush 守主基响应包互补);回采判定 rush 与否都照常,不滞留;
    - 跳过 building_tracker 里的建造农民(BuildingManager 的责任,O1/O2 教训)
      和司令接管的农民(_player_ctrl);
    - O11 watchdog 不冲突:撤离农民不在 tracker、不 idle(移动/就地采)。
    纯操作函数,可单测(假 ai 见 tests/test_worker_evacuation.py)。"""
    if not ai.townhalls:
        return
    worker_types = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
    evac_bases: dict[int, dict] = ai._evac_bases
    tracker = ai.mediator.get_building_tracker_dict

    def _enemy_ground_near(pos) -> int:
        return sum(
            1
            for u in ai.enemy_units
            if not u.is_structure
            and not u.is_flying
            and u.type_id not in worker_types
            and u.position.distance_to(pos) < _EVAC_RADIUS
        )

    def _cannons_near(pos) -> int:
        return sum(
            1
            for s in ai.structures
            if s.type_id in _STATIC_DEFENCE
            and s.is_ready
            and s.position.distance_to(pos) <= _CANNON_COVER
        )

    # —— 回采/途中维护(每帧都跑,rush 也不例外:撤离中的农民不能因 rush 状态滞留) ——
    for th_tag, info in list(evac_bases.items()):
        th = next((t for t in ai.townhalls if t.tag == th_tag), None)
        anchor = th.position if th is not None else info["pos"]
        if th is not None and not evacuation_clear(_enemy_ground_near(anchor)):
            for tag in list(info["workers"]):
                w = next((x for x in ai.workers if x.tag == tag), None)
                if w is None or tag in ai._player_ctrl:
                    info["workers"].discard(tag)  # 死了/被司令接管 → 出账
                    continue
                if w.is_idle:
                    if w.position.distance_to(info["target"]) < 10:
                        if ai.mineral_field:  # 已到安全基地 → 就地先采,别站着
                            w.gather(ai.mineral_field.closest_to(w))
                    else:  # 途中被卡/命令被打断 → 补 move
                        w.move(info["target"])
            continue
        # 敌退(或基地已丢,O15 重建接管) → 全员归 GATHERING 回采
        returned = 0
        for tag in list(info["workers"]):
            w = next((x for x in ai.workers if x.tag == tag), None)
            if w is None or tag in ai._player_ctrl:
                continue
            ai.mediator.assign_role(tag=tag, role=UnitRole.GATHERING)
            if ai.mineral_field:
                w.gather(ai.mineral_field.closest_to(th if th is not None else w))
            returned += 1
        evac_bases.pop(th_tag)
        if returned:
            ai._events.append(
                {"t": round(ai.time, 1), "msg": f"E6:敌退,{returned}农民回采"}
            )

    # —— 新撤离判定 ——
    # rush 门(E6 bench 修正):rush 期主基不新增撤离(六连动全权接管主基防守,
    # 行为不变);但**分矿不受 rush 门**——bench 实证 VeryHard/Rush 的 rush_active
    # 从 ~130s 首接敌一路续到中段波(game_03 t=520 仍在),E6 目标场景(分矿被抄)
    # 恰好全程落在 rush 态里,全局 rush 门 = 机制死代码。分矿撤离与 rush 响应包
    # (守主基/铺塔/出叉)互补不冲突。
    rush = ai.production_manager.rush_active
    main_pos = ai.start_location
    gathering = set(ai.mediator.get_unit_role_dict[UnitRole.GATHERING])
    th_of_worker = ai.mediator.get_worker_tag_to_townhall_tag
    for th in (t for t in ai.townhalls if t.is_ready):
        if th.tag in evac_bases:
            continue
        if rush and th.position.distance_to(main_pos) < 5:
            continue  # rush 期主基行为不变
        n = _enemy_ground_near(th.position)
        cannons = _cannons_near(th.position)
        if not should_evacuate_workers(
            n, cannon_cover=cannons > 0, cannons_near=cannons,
            threshold=_EVAC_THRESHOLD,
        ):
            continue
        candidates = [
            (o.position.x, o.position.y, _cannons_near(o.position) > 0)
            for o in ai.townhalls
            if o.tag != th.tag and o.is_ready
        ]
        target = pick_evacuation_base((th.position.x, th.position.y), candidates)
        if target is None:
            continue  # 无处可撤(单基地无塔):交 ares Mining keep_safe 个体避险
        moved: set[int] = set()
        for w in ai.workers:
            if th_of_worker.get(w.tag) != th.tag or w.tag not in gathering:
                continue
            if w.tag in tracker or w.tag in ai._player_ctrl:
                continue
            ai.mediator.assign_role(tag=w.tag, role=_EVAC_ROLE)
            w.move(Point2(target))
            moved.add(w.tag)
        if not moved:
            continue
        # 2c 协防标记:就近地面兵力在场 → 事件标记集结点(不强行微操)
        defenders = sum(
            1
            for u in ai.units
            if not u.is_structure
            and not u.is_flying
            and u.type_id not in worker_types
            and u.position.distance_to(th.position) < 20
        )
        cover_note = "无塔" if cannons == 0 else f"塔{cannons}座压不住"
        msg = f"E6:基地被抄(敌{n}地面,{cover_note}),撤离{len(moved)}农民"
        if defenders:
            msg += f";{defenders}地面兵力就近协防(集结点=被抄基地)"
        ai._events.append({"t": round(ai.time, 1), "msg": msg})
        evac_bases[th.tag] = {
            "pos": th.position,
            "target": Point2(target),
            "workers": moved,
        }


# 人机共驾：司令一旦亲手操作某单位，bot 让权 N 游戏秒；期间不再自动指挥它，
# N 秒内没有新手操 → 自动收回控制权。停放在 PERSISTENT_BUILDER（"不自动重指派"）role，
# combat/oracle/mining 都按 role 选单位，自然全部跳过它；唯一例外是 ares
# BuildingManager（按 building_tracker 记账、无视 role）→ 接管时用
# release_from_build_tracker 把它从 tracker 摘除（O2 修复）。
_PLAYER_YIELD: float = 3.0


class MyBot(AresBot):
    combat_manager: CombatManager
    oracle_manager: OracleManager
    production_manager: ProductionManager

    def __init__(self, game_step_override: Optional[int] = None):
        """Initiate custom bot

        Parameters
        ----------
        game_step_override :
            If provided, set the game_step to this value regardless of how it was
            specified elsewhere
        """
        super().__init__(game_step_override)
        # 人机共驾关键开关：默认 True 会让 bot 每条 raw 命令都改变 UI 当前选中 →
        # (a) 不停抢走司令的手动框选/点选；(b) bot 自己的命令回显进 state.actions，
        # 污染让权检测（把 bot 命令误当玩家手操）。设 False：bot 命令不碰 UI 选择、
        # 不回显进 actions → 司令手操顺畅，且 actions 只剩真正的玩家操作，让权信号变干净。
        self.raw_affects_selection = False
        # 参谋长指挥：粘性命令（全部字段见 steer_vocab.FIELDS），combat_manager 每帧读它覆盖默认进攻
        self.steer_order: dict = {}
        self._last_steer: float = -999.0
        # 侦察：一次 scout=on 只派一个农民，看完撤回/死了不补（_scout_done 防止无限续命送死）
        self._scout_tag: int | None = None
        self._scout_done: bool = False
        # 滚动事件日志：bot 侧检测值得注意的事（丢矿/被骚扰/损兵/发现敌情），
        # 只留最近 N 条写进 state.json，参谋长只读这个尾巴 → 拿"最近发生了啥"而不必翻旧对话。
        self._events: list[dict] = []
        self._prev_metrics: dict | None = None
        self._enemy_seen_types: dict[str, set] = {}
        # 人机共驾·让权：tag -> {"until": 归还时间, "role": 接管前的原 role 名}
        self._player_ctrl: dict[int, dict] = {}
        # 闲置农民清扫的时间戳(每 1 游戏秒扫一次)
        self._last_idle_sweep: float = -10.0
        # 敌方打出 gg(投降意向)检测,一局只记一次
        self._enemy_gg: bool = False
        # B8 自调参(leitwerk ask/tell):只记录+学习,ask 出的参数暂不接消费点
        # (先攒 bench 数据,接法见 docs/selftune.md §4)——对局内行为零变更。
        self._selftuner = SelfTuner()
        self._selftune_params = None

    async def on_start(self) -> None:
        await super(MyBot, self).on_start()
        try:
            self._selftune_params = self._selftuner.ask(
                {"enemy_race": os.environ.get("OPPONENT_RACE", "")}
            )
        except Exception:
            pass  # 调参失败不挡开局
        # E6 农民被抄转移:被抄基地 th_tag -> {"pos","target","workers"}(撤离台账)
        self._evac_bases: dict[int, dict] = {}
        # O19 idle_builder 检测:tag -> [干等起点时间, 本 episode 已发过事件]
        self._builder_wait: dict[int, list] = {}
        self._last_builder_scan: float = -10.0

    async def on_step(self, iteration: int) -> None:
        await super(MyBot, self).on_step(iteration)

        if iteration == 0 and not os.environ.get("STEER_NO_RESET"):
            steer.reset()  # 清上一局残留命令/战况（STEER_NO_RESET=1 保留预设命令，测试用）

        self._handle_player_control()  # 人机共驾：先处理让权，Mining/production 随后自动跳过被接管单位
        # O7: mineral_boost=False 关掉 ares 加速采矿微操 —— 它每个往返给每个农民下
        # move+SMART 两条命令(speed_mining.py:91-94),主矿区满屏点击、还可能顶司令手操。
        # 关掉后走 _do_standard_mining:只在农民闲置/挂错矿时补一条 gather,采集零打扰。
        self.register_behavior(Mining(mineral_boost=False))
        self._handle_scout()
        self._handle_idle_workers()

        await self.production_manager.update(iteration)
        # E6:农民被抄转移/协防(塔覆盖不撤/无塔撤向有塔基地/敌退回采)。
        # 放在 production 之后:rush_active 是本帧最新;role 改动先于 _after_step
        # 的 Mining 执行生效,不会与 Mining 抢命令。
        update_worker_evacuation(self)
        # O19(司令章程「对局后检查」):曝光 >1s 干等建造的农民(纯观测发事件)
        self._detect_idle_builders()

        # 调研合并(community-tactics-research §2.3):电池主动充能 —— 纯增量微操,
        # 没电池/没残盾单位时零指令。异常静默,绝不崩主循环。
        restore_with_batteries(self)
        # 调研合并(ares 调研 A3):水晶被拆导致产兵建筑断电 → 自动补水晶。
        # can_afford 守卫防 O11 钉点(RestorePower 自身无守卫,与 ProtossStaticDefence 同类风险)。
        if self.can_afford(UnitID.PYLON):
            self.register_behavior(RestorePower())

        # O4: rush 检测成立 → 侦查农民立刻放弃探路回家采矿（rush 局白送农民雪上加霜）。
        # role 归 GATHERING 后下帧起 recall 返回 0，事件只记一次；
        # steer scout 的 _scout_tag 一并清掉（防 _handle_scout 把撤回农民再派出去），
        # _scout_done 置 True 保持"不补派"语义。
        if self.production_manager.rush_active and recall_scouting_workers(self):
            self._scout_tag = None
            self._scout_done = True
            self._events.append(
                {"t": round(self.time, 1), "msg": "确认rush,侦查农民撤回(O4)"}
            )

        # Q5 早负判负(bench 省垃圾时间):前 10 分钟基地全没 → 投降离场。
        # 与 _ensure_townhall 互补:10 分钟后才谈重建;早期被打穿没有翻盘点。
        # O15:有工人且场上还有矿 → 不判负,交给 O15 重建(攒钱 > save_up > 出兵)。
        if self.townhalls.amount == 0 and self.time < 600:
            minerals_left = (
                sum(mf.mineral_contents for mf in self.mineral_field)
                if self.mineral_field
                else 0
            )
            if not nexus_rebuild_viable(
                self.workers.amount, minerals_left, self.minerals
            ):
                self._events.append(
                    {"t": round(self.time, 1), "msg": "前10分钟基地全失,判负离场(Q5)"}
                )
                steer.publish_state(self._steer_snapshot())  # bench 拿最后状态
                await self._client.leave()

        # 参谋长接缝：每几秒发布战况、读最新命令
        if self.time - self._last_steer >= _STEER_EVERY:
            self._last_steer = self.time
            steer.publish_state(self._steer_snapshot())
            self.steer_order = steer.read_order()

        # 敌投降检测(司令要求):AI 聊天打出 gg → 记事件,bench 收到后帮点"接受投降"提前终局
        if not self._enemy_gg:
            for _msg in self.state.chat:
                if _msg.player_id != self.player_id and _msg.message.strip().lower() in (
                    "gg", "ggwp", "gg wp", "g g",
                ):
                    self._enemy_gg = True
                    self._events.append(
                        {"t": round(self.time, 1), "msg": "敌方打出gg(投降意向)"}
                    )
                    break

    def _handle_scout(self) -> None:
        """⑦侦察·派农民：scout=on 只派**一个** probe 去敌方主基探查。
        它摸到对面就撤回来采矿；死了就死了，**绝不补新的**（否则粘性命令会无限续命送死）。
        想再派一个 → 参谋长先 clear/scout=off 再 scout=on（_scout_done 被重置）。
        多人混战：默认摸**最近的敌人**（E1）；想摸别家先 enemy=E2 再 scout=on。"""
        enemy_main = self.focused_enemy_start()
        if (self.steer_order or {}).get("scout") != "on":
            # 命令撤销 → 把还在路上的侦查农民拉回采矿(别留着 SCOUTING role 继续送),
            # 并重置 _scout_done 允许下次重新派
            if self._scout_tag:
                scout = self.units.find_by_tag(self._scout_tag)
                if scout is not None:
                    self.mediator.assign_role(tag=scout.tag, role=UnitRole.GATHERING)
                self._scout_tag = None
            self._scout_done = False
            return

        if self._scout_done:
            # 已经派过一个了：活着的就管它撤回，死了不补
            scout = self.units.find_by_tag(self._scout_tag) if self._scout_tag else None
            if scout is not None:
                if scout.distance_to(enemy_main) < 12:
                    # 摸到对面了，看够了 → 撤回家采矿（"要么回来"）
                    self.mediator.assign_role(tag=scout.tag, role=UnitRole.GATHERING)
                    self._scout_tag = None
                elif scout.is_idle:
                    scout.move(enemy_main)
            return

        # 还没派过 → 抽一个去侦察，标记已派（之后绝不补）
        w = self.mediator.select_worker(target_position=enemy_main)
        if w:
            self.mediator.assign_role(tag=w.tag, role=UnitRole.SCOUTING)
            w.move(enemy_main)
            self._scout_tag = w.tag
            self._scout_done = True

    def _handle_idle_workers(self) -> None:
        """闲置农民清扫(司令观察实证):除被司令接管(PERSISTENT_BUILDER)/侦查(SCOUTING)
        /E6 撤离中(_EVAC_ROLE)的之外,任何无命令农民立刻派回最近矿脉,role 归 GATHERING。
        ares Mining 只管 GATHERING role;且矿线饱和时 freed 建造农民在 ares 长距离采矿里
        找不到"空闲矿脉"拿不到命令 —— 这里兜底,每 1 游戏秒扫一次(O3:2 秒显得"傻等")。
        跳过 ares building_tracker 里的建造农民:他们是 BuildingManager 的责任,扫了会
        和 BuildingManager 每帧的 move 命令对抢(O1  ping-pong 根因之一)。"""
        if self.time - self._last_idle_sweep < 1.0:
            return
        self._last_idle_sweep = self.time
        if not self.mineral_field:
            return
        tracker = self.mediator.get_building_tracker_dict
        for w in self.workers.idle:
            role = self._current_role(w.tag)
            # E6: _EVAC_ROLE 的撤离农民由 update_worker_evacuation 全权维护
            # (途中补 move/到点就地采/敌退回采),这里别抢回去采被抄矿区的矿。
            if role in (
                UnitRole.SCOUTING.name,
                UnitRole.PERSISTENT_BUILDER.name,
                _EVAC_ROLE.name,
            ):
                continue
            if w.tag in tracker:
                # E4c:rush 期间一切建造钉点豁免 —— 矿紧时塔/兵营工人到点等钱
                # 是防御链的一部分;此时撤回会陷入「派出→钉点→6s 撤回→重派」
                # 循环,炮塔永远起不来(e4c game_02 实证:矿 170-390 而首塔
                # 拖到 206s 才 warp-in,首波被穿)。
                if self.production_manager.rush_active:
                    continue
                # O11:钉在建造点等钱的工人(ares 无守卫路径:ProtossStaticDefence/
                # TechUp)——钉点超 6s 且结构仍买不起 → 拆 tracker 撤回采矿,
                # 行为下帧重派(往返途中钱照采)。两个例外:
                # - 人口紧急态的水晶(E3h-B 紧急通道,故意钉点保人口);
                # - 基地建筑(E3k 实证:工人提前走到扩张点等 400 矿是正常开矿打法,
                #   6s 撤回会让 Nexus 永远拍不下)。
                info = tracker[w.tag]
                sid = info[TRACKER_ID]
                if sid == UnitID.PYLON and self.supply_left <= 2:
                    continue
                if sid in TOWNHALL_TYPES:
                    continue
                if should_release_waiting_builder(
                    self.can_afford(sid),
                    self.time - info[TIME_ORDER_COMMENCED],
                ):
                    release_from_build_tracker(self.mediator, w.tag)
                    self.mediator.assign_role(tag=w.tag, role=UnitRole.GATHERING)
                    w.gather(self.mineral_field.closest_to(w))
                continue
            # O7:采集往返/搬资源的农民零打扰 —— idle 判定漏掉过渡帧也别重下 gather
            if w.is_gathering or w.is_carrying_resource or w.is_returning:
                continue
            self.mediator.assign_role(tag=w.tag, role=UnitRole.GATHERING)
            w.gather(self.mineral_field.closest_to(w))

    def _detect_idle_builders(self) -> None:
        """O19(司令章程「对局后检查」):曝光「>1s 不干活干等建造」的农民。

        纯观测,不改任何行为 —— 撤回是 O11 watchdog 的职责(钉点 >6s 且买不起),
        这里 1s 只发事件,供 bench retro 的 idle_builder 标签归因(等钱/钉点/无指令)。
        对象 = ares building_tracker 里有建造指派但闲置(无任何命令)的农民:
        典型是钉在建造点等 can_afford,或被 TechUp/BuildStructure 派出却没拿到
        建造命令。豁免:走位途中的(有 move 命令→非 idle)/侦查/司令接管/
        E6 撤离(_EVAC_ROLE)。同一农民同一次干等只发一次(episode 去重:
        干等结束出账,再干等算新 episode)。每 1 游戏秒扫一次。"""
        if self.time - self._last_builder_scan < 1.0:
            return
        self._last_builder_scan = self.time
        tracker = self.mediator.get_building_tracker_dict
        now = self.time
        waiting: set[int] = set()
        for w in self.workers:
            if w.tag not in tracker:
                continue
            role = self._current_role(w.tag)
            exempt = w.tag in self._player_ctrl or role in (
                UnitRole.SCOUTING.name,
                UnitRole.PERSISTENT_BUILDER.name,
                _EVAC_ROLE.name,
            )
            if not builder_is_waiting(True, w.is_idle, exempt):
                continue
            waiting.add(w.tag)
            episode = self._builder_wait.get(w.tag)
            if episode is None:
                self._builder_wait[w.tag] = [now, False]  # [干等起点, 已发过事件]
                continue
            age = now - episode[0]
            if not episode[1] and idle_builder_alarm(age):
                episode[1] = True
                sid = tracker[w.tag][TRACKER_ID]
                reason = "等钱" if not self.can_afford(sid) else "未开工"
                self._events.append(
                    {
                        "t": round(now, 1),
                        "msg": (
                            f"idle_builder: 农民{w.tag}"
                            f"@{w.position.x:.0f},{w.position.y:.0f} "
                            f"干等{age:.0f}s({reason}造{sid.name})"
                        ),
                    }
                )
        # 干等结束(拿到命令/被 O11 撤回/死了) → 出账,下次干等算新 episode
        for tag in list(self._builder_wait):
            if tag not in waiting:
                self._builder_wait.pop(tag)

    def _current_role(self, tag: int) -> str | None:
        """反查某单位当前的 role 名（用于接管前记住、归还时恢复）。"""
        for role, tags in self.mediator.get_unit_role_dict.items():
            if tag in tags:
                return role.name if hasattr(role, "name") else str(role)
        return None

    def _handle_player_control(self) -> None:
        """人机共驾·让权：司令**操作**（选中并对其下命令）某单位 → bot 让权，超时无新操作自动收回。

        两个信号叠加，既准又不误判：
        - 门控 = `Unit.is_selected`（raw_affects_selection=False 保证它纯反映司令的鼠标选择）；
        - 触发 = 本帧 state.actions 里有针对它的命令 = 司令下了令。
        二者同时满足才让权，从而把"bot 给没被选中的农民下的采矿命令"挡在外面。让权后挪到
        PERSISTENT_BUILDER role（combat/oracle/mining 都按 role 选兵→自然跳过它），**bot 不再
        碰它** → 此后针对它的命令必是司令的，每有新命令就把倒计时刷回 _PLAYER_YIELD 秒。倒计时
        只由操作刷新、不由持续选中刷新 → 选着不动、超时无操作即挪回原 role，bot 重新接管（无需
        手动取消选择）。STEER_DEBUG=1 打印接管/刷新/归还，供实测校验。"""
        now = self.time
        debug = bool(os.environ.get("STEER_DEBUG"))

        cmd_tags: set[int] = set()
        for a in self.state.actions_unit_commands:
            cmd_tags.update(a.unit_tags)

        for u in self.units:  # 自己的非建筑单位（农民 + 军队）
            if not u.is_selected:
                continue
            tag = u.tag
            already = tag in self._player_ctrl
            has_cmd = tag in cmd_tags
            if not already and not has_cmd:
                continue  # 选中但还没下命令 → 先不让权（严格"操作即让权"）
            if not already:
                prev = self._current_role(tag)
                self.mediator.assign_role(tag=tag, role=UnitRole.PERSISTENT_BUILDER)
                # O2: 若它正被 ares 派去造建筑（在 building_tracker 里），必须从
                # tracker 摘除 —— 否则 BuildingManager 每帧无视 role 继续给它下
                # move/build 命令，与司令指令对抢，救不回来。摘除后生产侧下帧自动
                # 换别的矿工重派同一建筑。
                release_from_build_tracker(self.mediator, tag)
                self._player_ctrl[tag] = {"role": prev, "until": now + _PLAYER_YIELD}
                self._events.append(
                    {"t": round(now, 1), "msg": f"司令接管 {u.type_id.name}"}
                )
                if debug:
                    print(f"[player-ctrl] t={now:.1f} 接管 {u.type_id.name} "
                          f"tag={tag} 原role={prev}", flush=True)
            elif has_cmd:  # 已让权 + 又有新命令（bot 不碰它→必是司令的）→ 刷新倒计时
                self._player_ctrl[tag]["until"] = now + _PLAYER_YIELD
                if debug:
                    print(f"[player-ctrl] t={now:.1f} 刷新 tag={tag}", flush=True)

        for tag in list(self._player_ctrl):
            if now >= self._player_ctrl[tag]["until"]:
                prev = self._player_ctrl.pop(tag)["role"]
                unit = self.all_own_units.find_by_tag(tag)
                if unit is not None:
                    # prev 正常都有;拿不到(接管瞬间的一帧窗口)给兜底 role —— 别让它
                    # 滞留在 PERSISTENT_BUILDER 永远不干活
                    role = UnitRole(prev) if prev else (
                        UnitRole.GATHERING
                        if unit.type_id.name in ("PROBE", "SCV", "DRONE")
                        else UnitRole.ATTACKING
                    )
                    self.mediator.assign_role(tag=tag, role=role)
                if debug:
                    print(f"[player-ctrl] t={now:.1f} 归还 tag={tag} → {prev}",
                          flush=True)

    def enemy_starts_ranked(self) -> list:
        """敌方起始点按"离我家距离"排序 → 稳定槽位 E1(最近)..EN。
        全 bot（combat / oracle / 侦查 / 敌情分栏）统一走它，保证大家对"哪个是 E1"一致。
        1v1 时列表长度为 1，一切退化成原来的 enemy_start_locations[0]。"""
        return sorted(
            self.enemy_start_locations,
            key=lambda p: p.distance_to(self.start_location),
        )

    def focused_enemy_start(self):
        """当前焦点敌人的起始点：参谋长 enemy=E2 选槽，默认最近的 E1。
        所有"敌人相关"的目标解析都相对它；1v1 恒为唯一敌人，行为与旧版一致。"""
        starts = self.enemy_starts_ranked()
        idx = steer.enemy_slot_index((self.steer_order or {}).get("enemy"))
        if idx is None or idx >= len(starts):
            idx = 0
        return starts[idx]

    def _steer_snapshot(self) -> dict:
        """整理战况发布给参谋长：经济 + 我方军队 + 敌情 + 生效命令。

        敌情统一放在 enemies[]（按敌人分栏，不再另存冗余的全体合计）：每个敌方起始点一个
        槽位 E1..EN（E1=离我最近），单位/建筑按最近的敌方起始点归类；army 只报实时可见，
        建筑分 visible（此刻看得到）/ remembered（曾侦查、现在迷雾里，可能已变）。
        1v1 时 enemies 长度为 1。另附 events[]（最近事件流）供参谋长读近况。
        """
        army = Counter(u.type_id.name for u in self.units if u.type_id != UnitID.PROBE)

        # —— 按敌人分栏：每个敌方起始点一个槽位，单位/建筑归到最近的槽位 ——
        starts = self.enemy_starts_ranked()
        enemies = [
            {
                "id": f"E{i + 1}",
                "base": [round(s.x), round(s.y)],
                "dist": round(s.distance_to(self.start_location)),
                "visible": {"army": Counter(), "structures": Counter()},
                "remembered": {"structures": Counter()},
            }
            for i, s in enumerate(starts)
        ]

        def _slot(pos) -> int:
            return min(range(len(starts)), key=lambda i: starts[i].distance_to(pos))

        if starts:
            for u in self.enemy_units:
                if u.is_visible:  # 移动单位只报实时可见（迷雾快照位置不准）
                    enemies[_slot(u.position)]["visible"]["army"][u.type_id.name] += 1
            for st in self.enemy_structures:
                bucket = "visible" if st.is_visible else "remembered"
                enemies[_slot(st.position)][bucket]["structures"][st.type_id.name] += 1
            for e in enemies:  # Counter → dict，方便 JSON
                e["visible"]["army"] = dict(e["visible"]["army"])
                e["visible"]["structures"] = dict(e["visible"]["structures"])
                e["remembered"]["structures"] = dict(e["remembered"]["structures"])

        bases = self.townhalls.amount
        workers = self.workers.amount
        self._detect_events(round(self.time, 1), bases, workers, dict(army), enemies)

        return {
            "time": round(self.time, 1),
            "minerals": self.minerals,
            "vespene": self.vespene,
            "supply": f"{self.supply_used}/{self.supply_cap}",
            "workers": workers,
            "bases": bases,
            "army": dict(army),
            # 自调优诊断字段(纯增量,参谋可忽略):我方建筑编成 + 已研究升级
            # —— 回答「gateway 还在吗/ pylons 够吗/ blink 研究了吗」这类验证台常问的问题
            "structures": dict(
                Counter(u.type_id.name for u in self.structures)
            ),
            "upgrades": sorted(u.name for u in self.state.upgrades),
            "enemies": enemies,
            "events": self._events[-12:],
            "order": self.steer_order,
        }

    def _detect_events(
        self, t: float, bases: int, workers: int, army: dict, enemies: list
    ) -> None:
        """对比上一帧，检测值得注意的事，追加到滚动事件日志（只留最近 12 条）。"""
        prev = self._prev_metrics
        if prev is not None:
            if bases < prev["bases"]:
                self._events.append({"t": t, "msg": f"丢失基地：{prev['bases']}→{bases}"})
            elif bases > prev["bases"]:
                self._events.append({"t": t, "msg": f"新基地建成：共 {bases}"})
            dw = prev["workers"] - workers
            if dw >= 4:
                self._events.append({"t": t, "msg": f"农民骤减 {dw}（疑被攻击/抄家）"})
            lost = prev["army"].get("TEMPEST", 0) - army.get("TEMPEST", 0)
            if lost >= 2:
                self._events.append({"t": t, "msg": f"损失暴风舰 {lost} 艘"})
        # 敌方建筑类型首见（按槽位）→ 帮参谋长察觉对手在憋什么
        for e in enemies:
            seen = self._enemy_seen_types.setdefault(e["id"], set())
            cur = set(e["visible"]["structures"]) | set(e["remembered"]["structures"])
            for s in sorted(cur - seen):
                self._events.append({"t": t, "msg": f"{e['id']} 发现 {s}"})
            seen |= cur
        self._events = self._events[-12:]
        self._prev_metrics = {"bases": bases, "workers": workers, "army": army}

    def register_managers(self) -> None:
        """
        Override the default `register_managers` in Ares, so we can
        add our own managers.
        """
        # 多人混战：python-sc2 用 `3 - player_id`（只对 2 人局成立）算敌方种族，
        # 多人局算不出 → enemy_race 为 None，ares 挑 build 时 .name 崩。
        # 兜底当作 Random（protoss_builds.yml 有 Random build）；1v1 恒非空 → no-op。
        if self.enemy_race is None:
            self.enemy_race = Race.Random
        manager_mediator = ManagerMediator()
        self.combat_manager = CombatManager(self, self.config, manager_mediator)
        self.oracle_manager = OracleManager(self, self.config, manager_mediator)
        # update this one manually (don't add to ares manager hub)
        self.production_manager = ProductionManager(self, self.config, manager_mediator)

        self.manager_hub = Hub(
            self,
            self.config,
            manager_mediator,
            additional_managers=[
                self.combat_manager,
                self.oracle_manager,
            ],
        )

        self.manager_hub.init_managers()

    """
    Can use `python-sc2` hooks as usual, but make a call the inherited method in the superclass
    Examples:
    """

    # async def on_start(self) -> None:
    #     await super(MyBot, self).on_start()
    #
    #     # on_start logic here ...
    #
    # async def on_building_construction_complete(self, unit: Unit) -> None:
    #     await super(MyBot, self).on_building_construction_complete(unit)
    #
    #     # custom on_building_construction_complete logic here ...
    #
    async def on_end(self, game_result) -> None:
        """结局捕获:bench runner 注入 BENCH_DIR 时把本局结果写成 JSON(胜负信号,
        见 docs/bot-self-tuning-plan.md Phase A)。缺省(正常玩法)不写文件。
        纯增量,不影响对局内行为。"""
        await super(MyBot, self).on_end(game_result)
        bench_dir = os.environ.get("BENCH_DIR")
        if not bench_dir:
            return
        import json
        import uuid
        from pathlib import Path

        d = Path(bench_dir)
        d.mkdir(parents=True, exist_ok=True)
        army = Counter(u.type_id.name for u in self.units if u.type_id != UnitID.PROBE)
        payload = {
            "result": getattr(game_result, "name", str(game_result)),
            "game_time": round(self.time, 1),
            "flow": os.environ.get("BUILD", "tempest"),
            "map": os.environ.get("MAP", ""),
            "army": dict(army),
            "bases": self.townhalls.amount,
            "workers": self.workers.amount,
            "supply": f"{self.supply_used}/{self.supply_cap}",
        }
        (d / f"game_{uuid.uuid4().hex[:8]}.json").write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        # B8 tell:每局结局落进 selftune 记录(bench 环境变量带 race/diff/build;
        # 异常静默——记录失败不影响结局上报)
        try:
            self._selftuner.tell({
                "flow": payload["flow"],
                "difficulty": os.environ.get("DIFF", ""),
                "race": os.environ.get("OPPONENT_RACE", ""),
                "build": os.environ.get("AI_BUILD", ""),
                "result": payload["result"],
                "game_time": payload["game_time"],
            })
        except Exception:
            pass

    async def on_unit_created(self, unit: Unit) -> None:
        await super(MyBot, self).on_unit_created(unit)

        if unit.type_id == UnitID.ORACLE:
            self.mediator.assign_role(tag=unit.tag, role=UnitRole.HARASSING)
            return

        # assign all units to ATTACKING role by default
        if unit.type_id != UnitID.PROBE:
            self.mediator.assign_role(tag=unit.tag, role=UnitRole.ATTACKING)

    async def on_unit_took_damage(self, unit: Unit, amount_damage_taken: float) -> None:
        await super(MyBot, self).on_unit_took_damage(unit, amount_damage_taken)

        self.oracle_manager.on_unit_took_damage(unit)
