import os
from collections import Counter
from typing import Optional

from ares import AresBot, Hub, ManagerMediator
from ares.behaviors.macro import Mining, RestorePower
from ares.consts import ID as TRACKER_ID
from ares.consts import TIME_ORDER_COMMENCED, TOWNHALL_TYPES, UnitRole
from bot.production_plans import (
    builder_is_waiting,
    builder_release_exempt,
    evacuation_clear,
    idle_builder_alarm,
    is_combat_type,
    nexus_rebuild_viable,
    pick_evacuation_base,
    pick_walk_patch,
    resource_contested,
    scout_next_step,
    should_evacuate_workers,
    should_release_waiting_builder,
    worker_last_stand,
    worker_last_stand_hopeless,
    worker_transfer_count,
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
_EVAC_RADIUS: float = 20.0    # 敌地面单位距 Nexus 多少格内算"进矿区"
                              # O306-①(o291-o304「农民骤减 7-9」实证):15 格时狗
                              # (4.7 速)进圈到咬到农民仅 ~2s,撤离命令到走位启动
                              # 来不及;20 格 ≈ 提前 2-3s 撤离,波后农民存活率升
_EVAC_THRESHOLD: int = 4      # 进矿区敌地面 ≥ 此数 → 该基地视为被抄
_CANNON_COVER: float = 9.0    # 就绪塔距 Nexus ≤ 此值 → 矿区在塔射程内
_SCOUT_FLEE_RADIUS: float = 8.0  # O22:侦查探机邻近此距离内遇敌地面作战单位 → 立即逃跑(marine 射程 5+缓冲)
_SCOUT_LOOP_INTERVAL: float = 60.0  # O34:vs Zerg 循环 scout 间隔(持续盯兵力/转型)
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


def recall_pivot_scout_after_intel(ai) -> bool:
    """O35(司令观察,tempest vs Zerg 实证):pivot 早侦查探机(production_manager
    `_early_scout` t≈100s 派出)一旦看到敌建筑(情报已送达)即撤回采矿。

    tempest/stalker 没有 carrier 的 O9 评估撤回路径,O4 又只在 rush 确认时触发 ——
    探机留在敌家只会干等小狗孵化白送。carrier 走 O9 自有撤回,这里不动(已验证基线)。
    探机已死/已被 O4 撤回(role 非 SCOUTING)时只清 tag 不重复下令。
    返回 True=本帧执行了撤回。纯操作函数,可单测。"""
    pm = ai.production_manager
    if pm._flow.name == "carrier":
        return False
    tag = pm._pivot_scout_tag
    if tag is None or not ai.enemy_structures:
        return False
    pm._pivot_scout_tag = None
    scout = ai.units.find_by_tag(tag)
    if scout is None or ai._current_role(scout.tag) != UnitRole.SCOUTING.name:
        return False
    ai.mediator.assign_role(tag=scout.tag, role=UnitRole.GATHERING)
    target = home_mineral(ai) or ai.start_location
    if isinstance(target, Unit):
        scout.gather(target)
    else:
        scout.move(target)
    return True


def release_contested_miners(ai) -> int:
    """O39(司令观察):敌地面主力盘踞的矿线,摘掉农民的矿/气资源指派。

    基地被推平后,持旧指派的 GATHERING 农民会被 ares Mining 一路派回死矿
    (keep_safe 只在脸上遇敌时躲一下,躲完继续走)——反复重进敌军主力区域送死。
    摘除指派后 ResourceManager 下帧把他重派到活着基地的资源线。
    判据纯函数 production_plans.resource_contested(与 E6 回采滞回线同源)。
    返回摘除数。纯操作函数,可单测。"""
    worker_types = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
    threats = [
        u for u in ai.enemy_units
        if not u.is_structure and not u.is_flying and u.type_id not in worker_types
    ]
    if not threats:
        return 0

    def _near(pos) -> int:
        return sum(1 for t in threats if t.position.distance_to(pos) < _EVAC_RADIUS)

    released = 0
    mediator = ai.mediator
    for patch_tag in list(mediator.get_worker_to_mineral_patch_dict.values()):
        mf = ai.unit_tag_dict.get(patch_tag)
        if mf is not None and resource_contested(_near(mf.position)):
            mediator.remove_mineral_field(mineral_field_tag=patch_tag)
            released += 1
    for g_tag in list(mediator.get_worker_to_vespene_dict.values()):
        g = ai.unit_tag_dict.get(g_tag)
        if g is not None and resource_contested(_near(g.position)):
            mediator.remove_gas_building(gas_building_tag=g_tag)
            released += 1
    return released


def home_mineral(ai):
    """离主基 townhall 最近的矿脉(撤回侦查农民用,Bug1)。

    撤回/重派场景必须用「离主基最近的矿」,不能用 mineral_field.closest_to(worker)
    ——后者含敌方矿,探机在敌家会被派去采对面矿越走越深送死(Bug1:t=128 被 marine)。
    主基 townhall = 最靠近 start_location 的 ready townhall(全代码惯例,见
    update_worker_evacuation main.py:182 同款 <5 格判定)。返回 None = 没就绪基地/
    没矿(调用方回退 move(start_location))。纯函数,可单测。"""
    ths = getattr(ai, "ready_townhalls", None)
    mfs = getattr(ai, "mineral_field", None)
    if not ths or not mfs:
        return None
    main_th = min(ths, key=lambda th: th.position.distance_to(ai.start_location))
    return mfs.closest_to(main_th)


def scout_should_redispatch(prev_ts, new_ts, scout_done) -> bool:
    """scout 命令是否该重派探机(Bug2)。纯函数,可单测。

    clear+scout=on 同步执行时 bot 4s 轮询读不到 clear 中间态(_scout_done 不重置),
    改用 steer_cli set scout 时盖的 _scout_ts 时间戳判"scout 又被下发一次"。
    返回 True → 重置 _scout_done 重派。判定:
      - scout_done 已 False → 本来就能派,不需要这个机制(返回 False)
      - new_ts None → 没时间戳(老 CLI 或被清),不触发(返回 False)
      - prev None / new > prev → True(第一次下令 / 又下了一次)
      - new == prev → False(同一个 scout 持续中,不补)"""
    if not scout_done:
        return False
    if new_ts is None:
        return False
    return prev_ts is None or new_ts > prev_ts


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
    3. **回采**:敌地面 <2(滞回,防边界抖动往返) → 全员归 GATHERING 回最近矿脉,
       ares ResourceManager 自动重新分配;**基地已丢(th None)但敌地面仍盘踞死矿
       → 维持撤离**(O39 司令观察:不放农民回死矿送死),敌真撤了才回采
       (死矿矿脉还有资源,安全后照常回去采)。

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
        # O39:基地已丢(th None)也按同一判据 —— 敌地面仍盘踞死矿就维持撤离,
        # 不放农民回敌军主力中间采矿(司令观察:推平二矿后农民回流送死)。
        if not evacuation_clear(_enemy_ground_near(anchor)):
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
        # 敌真退了(含基地已丢、死矿已安全) → 全员归 GATHERING 回采
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


# 决死协防农民挂 CONTROL_GROUP_TWO(与 E6 撤离的 CONTROL_GROUP_ONE 互斥,
# ares 无消费者):Mining/idle 清扫/建造派工都不碰,敌退后归 GATHERING 重上岗。
_LAST_STAND_ROLE = UnitRole.CONTROL_GROUP_TWO
# O256-③:决死协防的塔覆盖口径比 E6 宽 —— 坡口塔距 Nexus 常 >9 格
# (o256a game_03:塔 3 座在坡口,9 格口径判 0 塔 → 协防没触发,农民白死),
# 18 格 ≈ 主基矿区+坡口全域,塔在坡口开火时农民在矿线协战仍吃塔输出。
_LAST_STAND_COVER: float = 18.0


def update_worker_last_stand(ai) -> None:
    """O256-①(o255 双 lane 0-9 尸检):主基决死协防 —— 无处可撤的农民不再白死。

    o255 全 9 局同一死因:280-350s 波(如 9 蟑螂+11 狗)进主基,E6 被两道闸
    挡死(rush 期主基不撤 + 单基地 target=None 无处可撤),22-26 农民保持
    采矿被逐个屠掉(每局 →5-10),经济断气后 FB/舰队/扩张全停。算账:22 农民
    (≈100dps)+4 塔(64dps)对 9 蟑螂是赢面,站着被屠才是输面。

    触发(纯判据 production_plans.worker_last_stand):急性窗(rush/threat)+
    就绪基地 ≤1(无处可撤)+ 矿区有就绪塔可依 + 敌地面达压垮线(6+4×塔数)。
    动作:GATHERING 农民(跳过建造 tracker/司令接管/E6 撤离中)拉去攻击离
    主基最近的敌地面单位,role 归 _LAST_STAND_ROLE。
    退出:敌地面 <2(与 E6 同滞回口径)或基地丢失 → 全员归 GATHERING 回采。
    多基地局不触发(E6 撤离更稳);非急性窗不扰动运营。
    纯操作函数,判据可单测。"""
    stand: set[int] = ai._last_stand
    worker_types = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
    ready_ths = [t for t in ai.townhalls if t.is_ready]
    main_th = (
        min(ready_ths, key=lambda t: t.position.distance_to(ai.start_location))
        if ready_ths
        else None
    )

    def _enemy_ground_near(pos) -> int:
        return sum(
            1
            for u in ai.enemy_units
            if not u.is_structure
            and not u.is_flying
            and u.type_id not in worker_types
            and u.position.distance_to(pos) < _EVAC_RADIUS
        )

    # —— 退出维护:敌退/基地丢 → 回采;战死/被接管 → 出账 ——
    anchor = main_th.position if main_th is not None else ai.start_location
    if stand and (main_th is None or evacuation_clear(_enemy_ground_near(anchor))):
        returned = 0
        for tag in list(stand):
            w = next((x for x in ai.workers if x.tag == tag), None)
            if w is None or tag in ai._player_ctrl:
                stand.discard(tag)
                continue
            ai.mediator.assign_role(tag=tag, role=UnitRole.GATHERING)
            if ai.mineral_field:
                w.gather(ai.mineral_field.closest_to(w))
            stand.discard(tag)
            returned += 1
        if returned:
            ai._events.append(
                {"t": round(ai.time, 1), "msg": f"O256:敌退,{returned}协防农民回采"}
            )
    if main_th is None:
        stand.clear()
        return
    # 战死者出账(每帧顺带清,防 tag 滞留)
    for tag in list(stand):
        if not any(w.tag == tag for w in ai.workers):
            stand.discard(tag)

    # —— 触发判定 ——
    n = _enemy_ground_near(main_th.position)
    cannons = sum(
        1
        for s in ai.structures
        if s.type_id in _STATIC_DEFENCE
        and s.is_ready
        and s.position.distance_to(main_th.position) <= _LAST_STAND_COVER
    )
    pm = ai.production_manager
    if not worker_last_stand(
        n,
        cannons,
        len(ready_ths),
        threat_or_rush=(
            pm.rush_active or getattr(pm, "_threat_active", False)
        ),
    ):
        return
    enemies = [
        u
        for u in ai.enemy_units
        if not u.is_structure
        and not u.is_flying
        and u.type_id not in worker_types
        and u.position.distance_to(main_th.position) < _EVAC_RADIUS
    ]
    if not enemies:
        return
    # O306-③(o291-o304 系列「农民骤减 7-9」实证):决死加白送上界 ——
    # 敌地面 > 14+6×塔 时农民冲锋改变不了结局(基地照丢+火种全灭=
    # 下波必死),改穿矿游走甩包围(O104 实证微操),塔阵/舰队打输出,
    # 农民保命留重建火种。
    _hopeless = worker_last_stand_hopeless(n, cannons)
    _patches = ai.mineral_field.closer_than(11, ai.start_location) if _hopeless else []
    tracker = ai.mediator.get_building_tracker_dict
    gathering = set(ai.mediator.get_unit_role_dict[UnitRole.GATHERING])
    pulled = 0
    # O308-②(o307a game_02/03 实证):同一场接战不添油 —— 首批拉完后
    # stand 非空期间不再拉新农民(「拉9→战死→再拉1→再送」×5 的添油
    # 循环 = 农民逐个喂给蟑螂,还赔走位/采矿复位时间);首批未决出
    # 胜负就交给塔/电池/部队,农民死在矿位和死在冲锋位之差是纯亏。
    # 敌退 stand 清仓后,下一场接战重新拉首批(自校正)。
    # O309-①(o308a game_02/04 实证):o308 的「stand 空才拉」被死亡绕过
    # —— 首批战死 stand 即空,下帧重拉(game_02 拉1×5 复活)。加 30s
    # latch:首批拉人后 30s 内 stand 空了也不重拉(整批阵亡 = 这场
    # 接战农民救不了,再拉是纯喂)。
    _can_pull = not stand and (
        ai.time - getattr(ai, "_last_stand_pulled_at", -9999.0) > 30.0
    )
    # O311-②:O310-① 首批封顶(2+4×塔)回退 —— o310b Harder 0/5,
    # 拉 3-6 人基地掉得更快;首批恢复全量拉(30s 添油 latch 保留)。
    for w in ai.workers:
        if not _can_pull:
            break
        if w.tag in stand or w.tag not in gathering:
            continue
        if w.tag in tracker or w.tag in ai._player_ctrl:
            continue
        ai.mediator.assign_role(tag=w.tag, role=_LAST_STAND_ROLE)
        if _hopeless and _patches:
            _threat = min(enemies, key=lambda e: e.position.distance_to(w.position))
            _wp = pick_walk_patch(
                [(m.position.x, m.position.y) for m in _patches],
                (_threat.position.x, _threat.position.y),
            )
            if _wp is not None:
                from sc2.position import Point2 as _P2
                w.move(_P2(_wp))
            else:
                w.attack(min(enemies, key=lambda e: e.position.distance_to(w.position)))
        else:
            w.attack(min(enemies, key=lambda e: e.position.distance_to(w.position)))
        stand.add(w.tag)
        pulled += 1
    # 已在协战但闲置(目标死了/命令断)的农民补刀最近敌
    # O306-③:游走模式闲置 = 已到矿簇/命令断,补下一跳穿矿而不是补刀
    # (补刀=白送上界失效)
    for tag in list(stand):
        w = next((x for x in ai.workers if x.tag == tag), None)
        if w is None or not w.is_idle:
            continue
        if _hopeless and _patches:
            _threat = min(enemies, key=lambda e: e.position.distance_to(w.position))
            _wp = pick_walk_patch(
                [(m.position.x, m.position.y) for m in _patches],
                (_threat.position.x, _threat.position.y),
            )
            if _wp is not None:
                from sc2.position import Point2 as _P2
                w.move(_P2(_wp))
                continue
        w.attack(min(enemies, key=lambda e: e.position.distance_to(w.position)))
    if pulled:
        ai._last_stand_pulled_at = ai.time  # O309-①:30s 添油 latch 起点
        ai._events.append({
            "t": round(ai.time, 1),
            "msg": (
                f"O256:主基决死协防(敌{n}地面,塔{cannons}),拉{pulled}农民塔下协战"
                if not _hopeless
                else f"O306:敌{n}地面超白送线(塔{cannons}),{pulled}农民穿矿游走保命"
            ),
        })


def update_worker_transfer(ai) -> None:
    """O266(司令观察):满载基地农民调拨到欠饱和基地(maynard)。

    司令观察:主基 16+ 满载时新分矿只有 2-3 个农民 —— ares ResourceManager
    只给「未指派」农民派矿点,已指派农民永不跨基地再平衡,新矿只靠新训
    农民慢慢填(~3 分钟才满)。本函数每 3s 扫一次:某基地矿线农民超
    (2×矿点+2) 且另一基地欠 (2×矿点-2) → 把超额农民(每批 ≤4,
    worker_transfer_count 判据)从 ares 簿记摘除并 gather 到目标基地
    矿点,ResourceManager 随后在新矿自然重派。
    守卫:急性窗(rush/threat)不动;目标基地 20 格有敌地面不调;
    跳过建造 tracker/司令接管/E6 撤离/决死协防中的农民;
    每农民 30s 冷却防往返。纯操作函数,判据可单测。"""
    if ai.time - getattr(ai, "_last_transfer_scan", 0.0) < 3.0:
        return
    ai._last_transfer_scan = ai.time
    pm = ai.production_manager
    if pm.rush_active or getattr(pm, "_threat_active", False):
        return
    ready_ths = [t for t in ai.townhalls if t.is_ready]
    if len(ready_ths) < 2 or not ai.mineral_field:
        return
    th_of_worker = ai.mediator.get_worker_tag_to_townhall_tag
    on_minerals = ai.mediator.get_worker_to_mineral_patch_dict
    worker_types = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}

    def _enemy_ground_near(pos, r=20.0) -> int:
        return sum(
            1
            for u in ai.enemy_units
            if not u.is_structure
            and not u.is_flying
            and u.type_id not in worker_types
            and u.position.distance_to(pos) < r
        )

    # 每基地:矿线农民数 / 饱和目标(2×矿点)
    stats = []
    for th in ready_ths:
        patches = ai.mineral_field.closer_than(10, th).amount
        if patches == 0:
            continue  # 死矿不调出也不调入
        count = sum(
            1
            for tag, th_tag in th_of_worker.items()
            if th_tag == th.tag and tag in on_minerals
        )
        stats.append((th, count, patches * 2))
    if len(stats) < 2:
        return
    tracker = ai.mediator.get_building_tracker_dict
    cd: dict = ai._transfer_cd
    gathering = set(ai.mediator.get_unit_role_dict[UnitRole.GATHERING])
    for dst, dst_count, dst_target in sorted(stats, key=lambda s: s[1]):
        if _enemy_ground_near(dst.position):
            continue  # 目标基地被踩,不往里调
        for src, src_count, src_target in sorted(
            stats, key=lambda s: -s[1]
        ):
            n = worker_transfer_count(
                src_count, src_target, dst_count, dst_target
            )
            if n <= 0 or src.tag == dst.tag:
                continue
            moved = 0
            for w in ai.workers:
                if moved >= n:
                    break
                if th_of_worker.get(w.tag) != src.tag:
                    continue
                if w.tag not in on_minerals:
                    continue
                if w.tag in tracker or w.tag in ai._player_ctrl:
                    continue
                if cd.get(w.tag, 0.0) > ai.time:
                    continue
                if w.tag not in gathering:
                    continue
                ai.mediator.remove_worker_from_mineral(worker_tag=w.tag)
                w.gather(ai.mineral_field.closest_to(dst.position))
                cd[w.tag] = ai.time + 30.0
                moved += 1
            if moved:
                ai._events.append({
                    "t": round(ai.time, 1),
                    "msg": (
                        f"O266:农民调拨 {moved} 人"
                        f"(矿线 {src_count}→{src_count - moved},"
                        f"新矿 {dst_count}→{dst_count + moved})"
                    ),
                })
                dst_count += moved
                src_count -= moved


def update_gas_topup(ai) -> None:
    """O288-⑤(司令观察):矿线红色超饱和(>2×矿点)而气矿 <3 人 → 超额农民上气。

    前 7 分钟常见:钱矿 20+ 农民(红色,边际零产出)气矿却 1-2 人 —— ares
    每帧只补 1 个气工且 select_worker 常被建造/协防抽干,气常年欠员。
    3s 节流:某基地矿线农民 > 2×矿点 且其就绪气矿某座 <3 人 → 超额农民
    从矿线簿记摘除、同步写入 ares 气矿簿记再 gather 上气(簿记一致,
    Mining 下帧不会把人拽回)。守卫:停气台账非空(rush/O157 停气激活,
    不打架)/气银行 ≥600(气在烂银行就别再采,与 O157 语义一致)/急性窗
    不动;跳过建造中/司令接管/撤离农民,每农民 30s 冷却(与 O266 共用)。"""
    if ai.time - getattr(ai, "_last_gas_topup_scan", 0.0) < 3.0:
        return
    ai._last_gas_topup_scan = ai.time
    pm = ai.production_manager
    if pm.rush_active or getattr(pm, "_threat_active", False):
        return
    if getattr(pm, "_gas_stopped_tags", None):
        return
    if ai.vespene >= 600:
        return
    if not ai.gas_buildings or not ai.mineral_field or not ai.townhalls:
        return
    rm = ai.manager_hub.resource_manager
    th_of_worker = ai.mediator.get_worker_tag_to_townhall_tag
    on_minerals = ai.mediator.get_worker_to_mineral_patch_dict
    tracker = ai.mediator.get_building_tracker_dict
    cd: dict = ai._transfer_cd
    gathering = set(ai.mediator.get_unit_role_dict[UnitRole.GATHERING])
    for gas in ai.gas_buildings.ready:
        th = ai.townhalls.closest_to(gas.position)
        if th is None or th.position.distance_to(gas.position) > 12:
            continue
        assigned = sum(
            1 for g in rm.worker_to_geyser_dict.values() if g == gas.tag
        )
        need = 3 - assigned
        if need <= 0:
            continue
        patches = ai.mineral_field.closer_than(10, th).amount
        if patches == 0:
            continue
        mineral_workers = sum(
            1 for tag, th_tag in th_of_worker.items()
            if th_tag == th.tag and tag in on_minerals
        )
        surplus = mineral_workers - patches * 2
        if surplus <= 0:
            continue
        moved = 0
        for w in ai.workers:
            if moved >= min(need, surplus):
                break
            if th_of_worker.get(w.tag) != th.tag or w.tag not in on_minerals:
                continue
            if w.tag in tracker or w.tag in ai._player_ctrl:
                continue
            if cd.get(w.tag, 0.0) > ai.time or w.tag not in gathering:
                continue
            rm.remove_worker_from_mineral(w.tag)
            rm.geyser_to_list_of_workers.setdefault(gas.tag, set()).add(w.tag)
            rm.worker_to_geyser_dict[w.tag] = gas.tag
            w.gather(gas)
            cd[w.tag] = ai.time + 30.0
            moved += 1
        if moved:
            ai._events.append({
                "t": round(ai.time, 1),
                "msg": (
                    f"O288:气矿补员 {moved} 人"
                    f"(矿线 {mineral_workers}/{patches * 2} 超饱和,"
                    f"气工 {assigned}→{assigned + moved})"
                ),
            })


# 人机共驾：司令一旦亲手操作某单位，bot 让权 N 游戏秒；期间不再自动指挥它，
# N 秒内没有新手操 → 自动收回控制权。停放在 PERSISTENT_BUILDER（"不自动重指派"）role，
# combat/oracle/mining 都按 role 选单位，自然全部跳过它；唯一例外是 ares
# BuildingManager（按 building_tracker 记账、无视 role）→ 接管时用
# release_from_build_tracker 把它从 tracker 摘除（O2 修复）。
_PLAYER_YIELD: float = 3.0
_PLAYER_BUILD_YIELD: float = 30.0  # O27: 司令下 BUILD_* 命令(造建筑)的让权倒计时(远位气矿要走+拍)


def player_yield_for_ability(ability_name: str) -> float:
    """O27:司令下 BUILD_* 类命令(造建筑) → 长倒计时(30s,远位气矿要走+拍);
    其他命令(移动/攻击)→ 默认 _PLAYER_YIELD(3s)。纯函数,可单测。
    根因:3s 倒计时太短,农民走向气矿途中 role 还原 GATHERING 被 Mining 抢回,
    gather(mineral) 覆盖 BUILD → 气矿拍不下(司令手动造气被卡)。"""
    if ability_name.startswith("BUILD"):
        return _PLAYER_BUILD_YIELD
    return _PLAYER_YIELD


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
        # O162:开局自动派一次探机,解决 bench 未下 scout=on 时完全盲打(11 分钟才见敌科技)的问题
        self._auto_scout_done: bool = False
        # O36: 待排查出生点(近→远)。4人图 1v1 敌人只占其一,逐点排查;显式 enemy=E# 锁槽时=[该点]。
        self._scout_route: list = []
        # Bug2:上次见到的 scout 命令时间戳(steer_cli set scout 时盖的 _scout_ts)。
        # clear+scout=on 同步执行时 bot 4s 轮询读不到 clear → _scout_done 不重置,
        # 改用时间戳变化判"又下了一次 scout",见 scout_should_redispatch。
        self._last_scout_ts: float | None = None
        # 滚动事件日志：bot 侧检测值得注意的事（丢矿/被骚扰/损兵/发现敌情），
        # 只留最近 N 条写进 state.json，参谋长只读这个尾巴 → 拿"最近发生了啥"而不必翻旧对话。
        self._events: list[dict] = []
        self._prev_metrics: dict | None = None
        self._enemy_seen_types: dict[str, set] = {}
        # 人机共驾·让权：tag -> {"until": 归还时间, "role": 接管前的原 role 名}
        self._player_ctrl: dict[int, dict] = {}
        # 闲置农民清扫的时间戳(每 1 游戏秒扫一次)
        self._last_idle_sweep: float = -10.0
        # O39:危险矿线资源指派摘除的节流(与 idle 清扫同 1s 节奏)
        self._last_contested_scan: float = -10.0
        # 敌方打出 gg(投降意向)检测,一局只记一次
        self._enemy_gg: bool = False
        # B8 自调参(leitwerk ask/tell):只记录+学习,ask 出的参数暂不接消费点
        # (先攒 bench 数据,接法见 docs/selftune.md §4)——对局内行为零变更。
        self._selftuner = SelfTuner()
        self._selftune_params = None

    async def on_start(self) -> None:
        await super(MyBot, self).on_start()
        # O161: carrier 流需要经济型开局;ares DataManager 按 race 循环选 opener，
        # 默认 TempestRush 只到 14 supply 且停农民。这里按 BUILD 显式切到 CarrierOpener。
        # O183:Zerg 的 Timing/Rush 风格 5-6 min 一波，原 CarrierOpener 零早期防御被碾平，
        # 切到更保守的 CarrierOpenerZergTiming（提前 Forge + 多 1 叉）；其余情况保持经济开局。
        _build = os.environ.get("BUILD", "")
        _opp_race = os.environ.get("OPPONENT_RACE", "")
        _ai_build = os.environ.get("AI_BUILD", "")
        if _build == "carrier" and hasattr(self, "build_order_runner"):
            _opener = "CarrierOpener"
            if _opp_race.lower() == "zerg" and _ai_build.lower() == "rush":
                # O194: Rush 需要比 Timing 更早的塔/叉防御链
                _opener = "CarrierOpenerZergRush"
            elif _opp_race.lower() == "zerg" and _ai_build.lower() == "timing":
                _opener = "CarrierOpenerZergTiming"
            try:
                self.build_order_runner.switch_opening(_opener, remove_completed=False)
            except Exception:
                pass  # 切换失败不挡开局，回退 TempestRush
        try:
            self._selftune_params = self._selftuner.ask(
                {"enemy_race": os.environ.get("OPPONENT_RACE", "")}
            )
        except Exception:
            pass  # 调参失败不挡开局
        # E6 农民被抄转移:被抄基地 th_tag -> {"pos","target","workers"}(撤离台账)
        self._evac_bases: dict[int, dict] = {}
        # O256-①:决死协防农民账(tag 集;update_worker_last_stand 全权维护)
        self._last_stand: set[int] = set()
        # O266:农民调拨冷却(tag → 解锁时刻;防满载/欠饱和边界往返)
        self._transfer_cd: dict[int, float] = {}
        # O162:每局重置开局自动 scout 标记
        self._auto_scout_done = False
        # O19 idle_builder 检测:tag -> [干等起点时间, 本 episode 已发过事件]
        self._builder_wait: dict[int, list] = {}
        self._last_builder_scan: float = -10.0
        # O19 防重派循环:O11 撤回记录(结构 -> 撤回时刻),production_manager 读
        self._o11_released_at: dict = {}

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
        # O256-①:主基决死协防(E6 两道闸都挡死的场景:rush 期主基+单基地
        # 无处可撤 → 农民拉去塔下协战,不再站着被屠)。E6 之后跑:撤离优先,
        # 无处可撤才协战。
        update_worker_last_stand(self)
        # O266(司令观察):满载基地 → 欠饱和新矿的农民调拨(ares 只派未指派
        # 农民,新矿靠新训慢慢填的缺口)。E6/决死之后跑,3s 节流。
        update_worker_transfer(self)
        # O288-⑤(司令观察):矿线红色超饱和而气矿欠员 → 超额农民上气,
        # 簿记同步 ares 气矿台账;停气/气烂银行/急性窗不动。
        update_gas_topup(self)
        # O39:敌主力盘踞的矿线摘掉农民资源指派(基地被推平后持旧指派回流送死),
        # 1s 节流;摘除后 ResourceManager 把人重派到活着基地
        if self.time - self._last_contested_scan >= 1.0:
            self._last_contested_scan = self.time
            release_contested_miners(self)
        # O19(司令章程「对局后检查」):曝光 >1s 干等建造的农民(纯观测发事件)
        self._detect_idle_builders()

        # 调研合并(community-tactics-research §2.3):电池主动充能 —— 纯增量微操,
        # 没电池/没残盾单位时零指令。异常静默,绝不崩主循环。
        restore_with_batteries(self)
        # O120-②(o119 系列实证):波次接触时给残盾塔/前排挂超载(盾回翻倍,
        # 神族防多波标配;此前从没用过)。异常静默,同 restore。
        from bot.shield_battery import overcharge_with_batteries
        _oc = overcharge_with_batteries(self)
        if _oc and self.time - getattr(self, "_oc_logged_at", 0.0) > 30.0:
            # O121-②/O122-③:超载触发簿记(含目标名,验证挂给谁)
            self._oc_logged_at = self.time
            self._events.append({
                "t": round(self.time, 1),
                "msg": f"O121:电池超载×{_oc}→{getattr(self, '_last_oc_target', '?')}",
            })
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
        # O35: 非 rush 场景,pivot 早侦查探机看到敌建筑(情报送达)也撤回 ——
        # O4 只在 rush 确认时统一撤,carrier 走 O9,这条补 tempest/stalker 的空档。
        if recall_pivot_scout_after_intel(self):
            self._events.append(
                {"t": round(self.time, 1), "msg": "侦查完成,探机撤回(O35)"}
            )

        # Q5/O192-③ 判负离场(bench 省垃圾时间/防 SC2 残局卡死):基地全没且
        # 无法重建 → 投降离场。早期(前10分钟)交给 O15 重建;10 分钟后放宽条件,
        # 工人过少(≤2)或存款不足即判负,避免 1 农 100 矿空转 10 分钟+。
        if self.townhalls.amount == 0:
            minerals_left = (
                sum(mf.mineral_contents for mf in self.mineral_field)
                if self.mineral_field
                else 0
            )
            viable = nexus_rebuild_viable(
                self.workers.amount, minerals_left, self.minerals
            )
            # O192-③: 10 分钟后放宽,避免残局拖时间/SC2 卡死不结束。
            if self.time >= 600.0:
                viable = viable and self.workers.amount >= 3 and self.minerals >= 250
            if not viable:
                phase = "前10分钟" if self.time < 600.0 else "中残局"
                self._events.append(
                    {"t": round(self.time, 1), "msg": f"{phase}基地全失,判负离场(Q5)"}
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
        多人混战：默认摸**最近的敌人**（E1）；想摸别家先 enemy=E2 再 scout=on。
        O36(司令观察,4人图实证):多出生点地图默认**逐点排查**全部候选出生点(近→远),
        找到敌建筑或全部摸完才回家(纯函数 production_plans.scout_next_step);
        司令显式 enemy=E# 锁槽时保持老语义,只摸该点。"""
        enemy_main = self.focused_enemy_start()
        _scout_on = (self.steer_order or {}).get("scout") == "on"
        _er = getattr(getattr(self, "enemy_race", None), "name", None)
        # O162:开局自动派一次探机(约 12 秒),避免 bench/未下 scout 时完全盲打。
        # 触发后走正常派遣逻辑,并在成功派遣后标记完成。
        _auto_dispatch = (
            not _scout_on
            and not self._auto_scout_done
            and self.time > 12.0
        )
        if not _scout_on and not _auto_dispatch:
            # O34 循环 scout(vs Zerg 持续盯兵力/转型):司令没下 scout + vs Zerg +
            # 距上次派 >_SCOUT_LOOP_INTERVAL → 自动重派(不 return,继续下面派新探机)
            if (
                _er == "Zerg"
                and self._scout_done
                and self.time - getattr(self, "_last_scout_finished", 999.0)
                > _SCOUT_LOOP_INTERVAL
            ):
                self._scout_done = False  # 重置 → 不 return,下面派新探机
            else:
                # 原逻辑:命令撤销 → 撤回侦查农民 + 重置
                if self._scout_tag:
                    scout = self.units.find_by_tag(self._scout_tag)
                    if scout is not None:
                        self.mediator.assign_role(tag=scout.tag, role=UnitRole.GATHERING)
                    self._scout_tag = None
                self._scout_route = []
                self._scout_done = False
                return

        # Bug2:clear+scout=on 同步执行时 bot 4s 轮询读不到 clear → _scout_done 不重置。
        # steer_cli set scout=on 时盖了 _scout_ts,这里检测时间戳变化判"又下了一次 scout"。
        new_ts = (self.steer_order or {}).get("_scout_ts")
        if scout_should_redispatch(self._last_scout_ts, new_ts, self._scout_done):
            self._scout_done = False
            self._scout_tag = None  # 清旧 tag,否则还指着已撤回/已死的探机
        self._last_scout_ts = new_ts if new_ts is not None else self._last_scout_ts

        if self._scout_done:
            # 已经派过一个了：活着的就管它撤回，死了不补
            scout = self.units.find_by_tag(self._scout_tag) if self._scout_tag else None
            if scout is not None:
                # O22: 途中遇敌(marine/坦克等)立即逃跑 —— 邻近 <_SCOUT_FLEE_RADIUS 格内有
                # 敌地面作战单位 → gather(home_mineral) 撤退。优先级高于摸敌家撤回/idle 推进,
                # 否则探机傻傻走到敌家被打死。复用 is_combat_type(排除工人/overlord/飞行)。
                threat = next(
                    (e for e in self.enemy_units
                     if is_combat_type(e.type_id) and not e.is_flying
                     and scout.distance_to(e) < _SCOUT_FLEE_RADIUS),
                    None,
                )
                if threat is not None:
                    self.mediator.assign_role(tag=scout.tag, role=UnitRole.GATHERING)
                    target = home_mineral(self) or self.start_location
                    if isinstance(target, Unit):
                        scout.gather(target)
                    else:
                        scout.move(target)
                    self._scout_tag = None
                    self._scout_route = []
                    return
                if not self._scout_route:
                    self._scout_route = [enemy_main]  # 兜底:无 route 记录时退化为单点
                step = scout_next_step(
                    self._scout_route,
                    arrived=scout.distance_to(self._scout_route[0]) < 12,
                    intel_found=bool(self.enemy_structures),
                )
                if step == "home":
                    # 情报到手/全部摸完 → 撤回家采矿。必须显式下回家命令(Bug1):
                    # 仅 assign_role 不给指令 → 下一帧 _handle_idle_workers 用
                    # mineral_field.closest_to(w) 派去"离探机最近的矿"=敌方矿线,
                    # 深入送死(t=128 实证)。改用离主基最近的矿(home_mineral)。
                    self.mediator.assign_role(tag=scout.tag, role=UnitRole.GATHERING)
                    target = home_mineral(self) or self.start_location
                    if isinstance(target, Unit):   # 矿脉 → gather
                        scout.gather(target)
                    else:                           # Point2 回退 → move
                        scout.move(target)
                    self._scout_tag = None
                    self._scout_route = []
                elif step == "next":
                    # 当前出生点是空的 → 去下一个候选点(O36)
                    self._scout_route.pop(0)
                    scout.move(self._scout_route[0])
                elif scout.is_idle:
                    scout.move(self._scout_route[0])
            return

        # 还没派过 → 抽一个去侦察，标记已派（之后绝不补）
        # O36: 显式 enemy=E# → 只摸该点;否则近→远逐点排查全部候选出生点
        _slot = steer.enemy_slot_index((self.steer_order or {}).get("enemy"))
        self._scout_route = (
            [enemy_main] if _slot is not None else list(self.enemy_starts_ranked())
        )
        if not self._scout_route:
            return
        w = self.mediator.select_worker(target_position=self._scout_route[0])
        if w:
            self.mediator.assign_role(tag=w.tag, role=UnitRole.SCOUTING)
            w.move(self._scout_route[0])
            self._scout_tag = w.tag
            self._scout_done = True
            # O162:开局自动 scout 成功派遣后标记完成,后续走正常循环/手动命令
            self._auto_scout_done = True
            self._last_scout_finished = self.time  # O34:循环 scout 计时(距此 >60s 自动重派)

    def _building_started_near(self, sid: UnitID, target: Point2, radius: float = 3.0) -> bool:
        """O205:目标点附近是否已有该类型建筑(含在建)——idle_builder 5s 熔断用。"""
        return any(
            s.type_id == sid and s.position.distance_to(target) < radius
            for s in self.structures
        )

    def _is_rush_critical_structure(self, sid: UnitID) -> bool:
        """O212:rush/防御紧急期间应保留钉点的关键建筑;其余结构可释放回矿。"""
        if sid == UnitID.FORGE:
            return True
        if sid == UnitID.PHOTONCANNON:
            return True
        if sid == UnitID.GATEWAY:
            # 首座 GATEWAY 是 rush 产能核心,保留;后续 Gateway 可释放
            return not any(
                s.type_id == UnitID.GATEWAY for s in self.structures.ready
            )
        if sid in TOWNHALL_TYPES:
            # 首次扩张(就绪基地 ≤1)保留;后续开矿释放
            return self.townhalls.ready.amount <= 1
        # PYLON 紧急态在调用方单独处理;其它科技建筑非关键
        return False

    def _idle_builder_fuse_release(self, w: Unit, info: dict) -> bool:
        """O212:派工后建筑未开工 → 释放工人回矿,最大化采矿。

        5s 熔断专治「多建筑同时派工、mineral 被瞬间抽干、农民钉点等钱」的死锁。
        仅保留真正的关键链豁免:FORGE、首座 PHOTONCANNON、首座 GATEWAY、首次
        扩张 NEXUS。FLEETBEACON 与后续 Gateway/Nexus 不再 blanket 豁免,
        防止 O211 中农民被钉数分钟吸血。

        任何情况都有 30s 硬顶:工人等超过 30s 仍未开工,强制释放,避免 pathological
        长期钉点。
        """
        sid: UnitID = info[TRACKER_ID]
        commenced = info.get(TIME_ORDER_COMMENCED)
        target = info.get("target")
        if commenced is None or target is None:
            return False

        age = self.time - commenced
        started = self._building_started_near(sid, target)

        # O213:FORGE/TOWNHALL 保留 30s 硬顶(攒钱预走位语义),
        # 其余结构降到 20s,进一步压缩 idle_builder 吸血窗口。
        _hard_cap = 30.0 if sid == UnitID.FORGE or sid in TOWNHALL_TYPES else 20.0
        if age > _hard_cap and not started:
            return True

        # 已开工 或 5s 内 → 不释放
        if started or age <= 5.0:
            return False

        # FORGE:关键防御链,永远豁免
        if sid == UnitID.FORGE:
            return False

        # PHOTONCANNON:首塔(无就绪炮塔附近)豁免;已有就绪塔则后续塔走熔断
        if sid == UnitID.PHOTONCANNON:
            has_ready_cannon = any(
                s.type_id == UnitID.PHOTONCANNON
                and s.position.distance_to(Point2(target)) < 25.0
                for s in self.structures.ready
            )
            return has_ready_cannon

        # GATEWAY:首座 GATEWAY(无就绪兵营)豁免;后续 Gateway 走熔断
        if sid == UnitID.GATEWAY:
            has_ready_gateway = any(
                s.type_id == UnitID.GATEWAY for s in self.structures.ready
            )
            return has_ready_gateway

        # NEXUS:首次扩张(当前就绪基地 ≤1)豁免;后续开矿走熔断
        if sid in TOWNHALL_TYPES:
            return self.townhalls.ready.amount > 1

        # FLEETBEACON 及其它:不再豁免,走 5s 熔断
        return True

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
            if role in (UnitRole.SCOUTING.name, _EVAC_ROLE.name):
                continue
            # PERSISTENT_BUILDER:司令接管的(已摘 tracker,O2)不抢;但在 tracker 里的是
            # ares build_runner 开局序列农民(如第一个 PYLON),钱不够钉点干等 → 放行进下面
            # O11 分支撤回采矿(O21:治开局水晶干等 37s)。build_runner 兼容性靠实机验证
            # (撤后 do_step 发现 PYLON 没建应重派新 worker)。
            if role == UnitRole.PERSISTENT_BUILDER.name and w.tag not in tracker:
                continue
            if w.tag in tracker:
                info = tracker[w.tag]
                # O205:idle_builder 5s 熔断 —— 派工后 5s 未开工且非关键建筑,
                # 立即释放回矿,避免多建筑同时派工抽干 mineral 导致农民长期钉点。
                # 关键防御链/基地/FB 由下方 O11 路径按各自 grace 处理。
                if self._idle_builder_fuse_release(w, info):
                    sid = info[TRACKER_ID]
                    release_from_build_tracker(self.mediator, w.tag)
                    self._o11_released_at[sid] = self.time
                    self.mediator.assign_role(tag=w.tag, role=UnitRole.GATHERING)
                    w.gather(self.mineral_field.closest_to(w))
                    continue
                # E4c:rush 期间一切建造钉点豁免 —— 矿紧时塔/兵营工人到点等钱
                # 是防御链的一部分;此时撤回会陷入「派出→钉点→6s 撤回→重派」
                # 循环,炮塔永远起不来(e4c game_02 实证:矿 170-390 而首塔
                # 拖到 206s 才 warp-in,首波被穿)。
                # O117-②(o116 取证实证):豁免扩到防御紧急(rush确认/过渡/
                # presumed)—— presumed 期 rush_active 未置位,塔工被「6s 撤回
                # +15s 重派冷却」循环折腾(21s/轮),首塔永远慢半拍
                sid = info[TRACKER_ID]
                _rush_exempt = builder_release_exempt(
                    self.production_manager.rush_active,
                    getattr(self.production_manager, "_defense_urgent", False),
                )
                # O212: rush/防御紧急期间仍释放非关键建筑工人,防止 Nexus/FleetBeacon/
                # 后续 Gateway 被长期钉点吸血;关键防御链(FORGE/首塔/首GW/首次扩张)
                # 保留豁免,避免首塔/首叉产能链断裂。
                if _rush_exempt and self._is_rush_critical_structure(sid):
                    continue
                # O11:钉在建造点等钱的工人(ares 无守卫路径:ProtossStaticDefence/
                # TechUp)——钉点超 6s 且结构仍买不起 → 拆 tracker 撤回采矿,
                # 行为下帧重派(往返途中钱照采)。两个例外:
                # - 人口紧急态的水晶(E3h-B 紧急通道,故意钉点保人口);
                # - 基地建筑(E3k 实证:工人提前走到扩张点等 400 矿是正常开矿打法,
                #   6s 撤回会让 Nexus 永远拍不下)。
                if sid == UnitID.PYLON and self.supply_left <= 2:
                    continue
                # O21:TOWNHALL 不再硬豁免,改加长 grace(Nexus 400 矿攒钱需时间,
                # grace=30s 保 E3k 开矿预走位语义;原硬豁免致 Nexus 农民干等到死)。
                # 其余建筑 grace=6s(短暂等钱容忍,真没钱就撤回采矿、钱够再来)。
                # O17x/O206:司令观察「前期农民仍干等造建筑」——把开局 grace 再收紧:
                # time<120 普通建筑 grace 从 1s→0.5s,early_age 从 3s→1.5s,
                # 钉点 1.5s 且 5s 收入补不上缺口就立即撤回采矿,不滚雪球。
                # 中段 6s;TOWNHALL 预走位语义保留,但 grace 从 30s 降到 15s
                # (o205 Nexus 工人被钉 3.5min+,采矿损失超过预走位收益)。
                # O173:FleetBeacon 300 矿攒钱窗口长,工人被反复释放导致 FB 永远
                # 落不了地;给 FB 同 TOWNHALL 级 grace,让工人等到矿够真正开工。
                if sid == UnitID.FLEETBEACON or sid in TOWNHALL_TYPES:
                    # O21: Nexus/FB 预走位允许等钱,但 30s grace 在 o205 败局里
                    # 让工人被钉 3min+;降到 15s,仍保留预走位语义,但等不起时
                    # 更快回矿采矿(O206)。
                    grace = 15.0
                    _early_age = 15.0
                elif self.time < 120:
                    grace = 0.5
                    # O204:前期资金窗口紧，钉点 1s 且 3s 收入补不上缺口就撤回采矿。
                    _early_age = 1.0
                else:
                    grace = 6.0
                    _early_age = 1.5
                if should_release_waiting_builder(
                    self.can_afford(sid),
                    self.time - info[TIME_ORDER_COMMENCED],
                    grace=grace,
                    deficit=max(
                        0.0, self.calculate_cost(sid).minerals - self.minerals
                    ),
                    # O204:前期用 3s 收入估算替代 5s,与 _early_age=1.0 匹配。
                    income_5s=self.production_manager._mineral_income_per_sec()
                    * (3.0 if self.time < 120.0 else 5.0),
                    early_age=_early_age,
                ):
                    release_from_build_tracker(self.mediator, w.tag)
                    # O19 防重派循环:记录撤回时刻,production_manager 对同类结构
                    # 冷却 10s(O139-②:15→10)不再派工(o19fix 实证:撤回→下帧
                    # 守卫又过→再派的循环让同一农民反复钉点)。
                    # rush 期 O11 豁免 → 无冷却(E4c)。O139-②:手动派工链
                    # (_dispatch_structure)同读此冷却,不再只 F2 管
                    self._o11_released_at[sid] = self.time
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
        cmd_ability: dict[int, str] = {}  # O27: tag→ability_name(判 BUILD 长倒计时)
        for a in self.state.actions_unit_commands:
            cmd_tags.update(a.unit_tags)
            aname = getattr(getattr(a, "ability_id", None), "name", "")
            if aname:
                for t in a.unit_tags:
                    cmd_ability[t] = aname

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
                self._player_ctrl[tag] = {
                    "role": prev,
                    "until": now + player_yield_for_ability(cmd_ability.get(tag, "")),
                }
                self._events.append(
                    {"t": round(now, 1), "msg": f"司令接管 {u.type_id.name}"}
                )
                if debug:
                    print(f"[player-ctrl] t={now:.1f} 接管 {u.type_id.name} "
                          f"tag={tag} 原role={prev}", flush=True)
            elif has_cmd:  # 已让权 + 又有新命令（bot 不碰它→必是司令的）→ 刷新倒计时
                self._player_ctrl[tag]["until"] = now + player_yield_for_ability(
                    cmd_ability.get(tag, "")
                )
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
