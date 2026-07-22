import os
from collections import Counter
from typing import Optional

from ares import AresBot, Hub, ManagerMediator
from ares.behaviors.macro import Mining
from ares.consts import ID as TRACKER_ID
from ares.consts import TIME_ORDER_COMMENCED, UnitRole
from bot.production_plans import should_release_waiting_builder
from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId as UnitID
from sc2.unit import Unit

from bot import steer
from bot.managers.combat_manager import CombatManager
from bot.managers.oracle_manager import OracleManager
from bot.managers.production_manager import ProductionManager

# 每隔几游戏秒发布 state.json + 读 orders.json
_STEER_EVERY: float = 4.0


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
        if self.townhalls.amount == 0 and self.time < 600:
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
        的之外,任何无命令农民立刻派回最近矿脉,role 归 GATHERING。
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
            if role in (UnitRole.SCOUTING.name, UnitRole.PERSISTENT_BUILDER.name):
                continue
            if w.tag in tracker:
                # O11:钉在建造点等钱的工人(ares 无守卫路径:ProtossStaticDefence/
                # ExpansionController/TechUp)——钉点超 6s 且结构仍买不起 → 拆 tracker
                # 撤回采矿,行为下帧重派(往返途中钱照采)。例外:人口紧急态的水晶
                # (E3h-B 紧急通道,故意钉点保人口)。
                info = tracker[w.tag]
                sid = info[TRACKER_ID]
                if sid == UnitID.PYLON and self.supply_left <= 2:
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
