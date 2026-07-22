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
    UnitRole,
)
from cython_extensions.general_utils import cy_unit_pending
from cython_extensions.units_utils import cy_closest_to
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
    defense_syncs_with_nexus,
    expansion_cannon_count,
    expansion_reserve_active,
    gas_gated_stargate_target,
    gas_target,
    nexus_rebuild_active,
    pre_fleet_cap,
    pre_fleet_spawn,
    research_paused_for_rush,
    rush_needs_gateway,
    rush_triggers_defense,
    save_up_spawn,
    scout_verdict,
    should_expand_dynamic,
    should_register_autosupply,
    upgrade_tech_buildings,
    worker_target,
)

if TYPE_CHECKING:
    from ares import AresBot

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
        self._rush_active: bool = False
        self._rush_clear_since: float | None = None
        # 流派配置(flows.yml,神族生产侧单一真相源);Terran/Zerg 路径不走它。
        self._flow: FlowConfig = FlowConfig.load(os.environ.get("BUILD"))
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

        # can_afford 守卫：钱够才派农民去造 pylon，否则农民走过去干等不采矿（idle bug 根因）。
        if not self._built_extra_production_pylon and self.ai.can_afford(UnitID.PYLON):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, UnitID.PYLON)
            )
            self._built_extra_production_pylon = True

        # use ares-sc2 macro behaviors for building pylons and units
        macro_plan: MacroPlan = MacroPlan()
        # O15:基地清零 → 一切开销让位重建 Nexus(没经济一切免谈)。截断 = 不注册
        # 研究/出兵,只留 AutoSupply;命保防御(ProtossStaticDefence,无基地时自然 no-op)。
        _rebuild_nexus = nexus_rebuild_active(self.ai.townhalls.amount)
        # E3k:动态开矿触发判定(算一次,EC 注册/攒钱预留共用);rush 内建门,重建优先。
        _want_expand = (
            self._want_dynamic_expand() if not _rebuild_nexus else False
        )
        # E3k:开矿触发但买不起 → 攒钱预留(出兵/造农民让位,Nexus 不再排在塔/叉/农民后)
        _expansion_reserve = expansion_reserve_active(
            _want_expand, self.ai.can_afford(UnitID.NEXUS)
        )
        # O6: ares AutoSupply 同样不查 can_afford(auto_supply.py:52-55 直接调
        # BuildStructure),钱不够农民就钉在 pylon 建造点干等 —— 只在买得起时注册,
        # supply 缺口的判定仍归 ares 内部。
        # E3g:return_true_if_supply_required=False 必须显式给 —— 默认 True 时
        # supply 紧张期它每帧返回 True 截断 MacroPlan,后面的 UpgradeController/
        # SpawnController 整段饿死(e3g game_01:120s 零航母零研究,gas 囤 2000+)。
        # E3h:水晶紧急通道 —— supply_left ≤ 2 时即便买不起也注册(卡人口 68-100s
        # 的代价比钉一个工人大,见 should_register_autosupply)。
        if should_register_autosupply(
            self.ai.can_afford(UnitID.PYLON), self.ai.supply_left
        ):
            macro_plan.add(
                AutoSupply(
                    base_location=self.ai.start_location,
                    return_true_if_supply_required=False,
                )
            )
        # E3k-fix:开矿排在研究/出兵之前 —— UpgradeController(prioritize) 会把
        # plan 尾部的 ExpansionController 饿死(e3k game_03 实证)。
        # prioritize=True = 欠费也先派工人走位(钉在扩张点等 400 是正常开矿打法,
        # O11 watchdog 已对基地建筑豁免,见 main.py)。
        if _want_expand:
            macro_plan.add(
                ExpansionController(
                    to_count=self.ai.townhalls.amount + 1,
                    max_pending=1,
                    prioritize=True,
                )
            )
        # 升级(O1/O8/O10):研究交 UpgradeController 并进 MacroPlan 且 prioritize=True ——
        # 研究就绪但买不起时返回 True 截断 plan,SpawnController 暂停花钱 → 资源攒给
        # 研究(O8 长研究预留,Forge/科技建筑一好就点);建筑缺失/前置未就绪时返回 False
        # 不阻塞 plan(不会存款死锁)。前置科技建筑不走它的 auto tech-up(ares TechUp
        # 不查 can_afford,O1 实证),由带守卫的 _build_core_structure 补建(见 update 尾部)。
        # ⚠️ E3 回归:rush_active 期间研究整体让位(不注册)——预留会把 rush 响应包
        # (叉子/塔都在 plan 后续)饿死;rush 解除后自动恢复预留。
        # E3k:开矿攒钱预留期间研究同样让位(Nexus > 研究 > 出兵)。
        _upgrades = self._flow.upgrade_ids()
        if (
            _upgrades
            and not research_paused_for_rush(self._rush_active)
            and not _rebuild_nexus
            and not _expansion_reserve
        ):
            macro_plan.add(
                UpgradeController(
                    _upgrades,
                    base_location=self.ai.start_location,
                    auto_tech_up_enabled=False,
                    prioritize=True,
                )
            )
        # 兵种配方从 flows.yml 当前流派读(spawn_dict 只含 proportion>0 的兵种)。
        # freeflow_mode 按流派配置:多兵种流派必开(true=配比只当优先序不当上限),
        # 否则兵力在精确配比点永久死锁(C3c 诊断出的 stalker 停产第二根因)。
        # E3b: rush_active 期间 spawn_target 切回主基 —— 前线折跃点=敌群方向,
        # 响应兵种一落地就进狗群分批送死(trickle);平时才用 F1 前线投送。
        if not _rebuild_nexus and not _expansion_reserve:
            macro_plan.add(
                SpawnController(
                    army_composition_dict=self._effective_spawn(),
                    spawn_target=(
                        self.ai.start_location if self._rush_active
                        else self._front_point()  # F1: 折跃向前线(非主基地),配合前线水晶塔远程投送
                    ),
                    freeflow_mode=self._flow.freeflow,
                )
            )
        # 运营指挥·通用建筑杠杆 build=<结构>（expand=yes = build=nexus 别名）
        _order = getattr(self.ai, "steer_order", None) or {}
        self._handle_manual_build(_order, macro_plan)
        self.ai.register_behavior(macro_plan)

        # F2: 按局势铺防御塔(B+F+Cannon)——框架自动建 forge + 光子炮 + 护盾电池并补前置科技。
        # E2: 配了 expansion_cannons 的流派塔数动态化(min + 敌可见作战单位//4,封顶 max),
        # 每帧重算重注册,ProtossStaticDefence 参数本就支持每帧变。
        if self._should_build_defense(_order):
            ec = self._flow.expansion_cannons
            cannons = (
                2 if ec is None
                else expansion_cannon_count(
                    ec.min, ec.max, self._visible_enemy_army_count()
                )
            )
            self.ai.register_behavior(
                ProtossStaticDefence(
                    photon_cannons_per_base=cannons,
                    # E3d 实证:rush 期间电池必须让位 —— 电池要 CYBERNETICSCORE,
                    # ares 会先 TechUp 科技(无 can_afford 守卫,工人被钉在建造点)
                    # 且 _tech_required 满足前直接 return,炮塔整条被饿死
                    # (game_01 零炮塔败北)。rush 解除后恢复 1/矿。
                    shield_batteries_per_base=0 if self._rush_active else 1,
                    # E3f:允许 2 座同建 —— 塔目标随敌兵爬升(敌 30 → 10/矿),
                    # 单线建造 ~29s/座永远追不上两段式 rush 的主力波
                    max_on_route=2,
                )
            )

        # custom behavior for all other production, using ares-sc2 to help
        building_counter: dict[UnitID, int] = self.manager_mediator.get_building_counter
        structures_dict: dict[
            UnitID, list[Unit]
        ] = self.manager_mediator.get_own_structures_dict

        # E3d: rush 期间连造农民也让位(50 矿/个是防御链的最大竞争项)
        # E3k: 开矿攒钱预留期间同样让位(Nexus 不排在农民后)
        if not self._rush_active and not _expansion_reserve:
            self._build_probes(self.ai.ready_townhalls)
        self._ensure_townhall()  # Q4:保底主基地(被打爆到 0 且有矿区价值时重建)
        self._early_scout()      # pivot:2分钟自动派一个探机看对面开局
        self._evaluate_scout_intel()  # O9:侦查情报→开局决策(t≈170s,一局一次)
        self._update_rush_state()  # pivot:rush 检测/解除(响应包=叉子+塔+守家)
        # E3d: rush 期间资源全部让位防御链(叉子/塔) —— 暂停科技链(cybercore/星门/
        # 第二气)、造农民、追加产能、滚雪球、前线塔;rush 解除后各自恢复。
        # 保底:_rush_gateway_boost 保证兵营产能,升级循环保留 FORGE(炮塔前置,见下)。
        if not self._rush_active and not _rebuild_nexus:
            await self._build_flow_structures(building_counter, structures_dict)
            # O13:每个就绪基地双气满采,优先级高于一切矿物开销(气矿买上再谈产能/滚雪球)
            self._ensure_expansion_gas()
            # 按流派配置扩产能(矿富余追加产兵建筑,治"矿堆花不出去")
            self._build_extra_production(structures_dict)
            self._spend_bank()  # Q3:存款淤积时换成开矿/追加产能,经济优势→战场优势
            self._build_forward_pylon()  # F1: 前线水晶塔(投送),各流派共用
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
                    await self._build_core_structure(_tech_building)

        # one off task to build an oracle（流派配置里 one_off 含 ORACLE 才造；
        # 需舰队航标 + 有空闲就绪星门）
        if not self._built_single_oracle and UnitID.ORACLE in self._flow.one_off_ids():
            if (
                self.ai.can_afford(UnitID.ORACLE)
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
        """pivot·早侦查:t≈100s 自动派一个探机看对面开局(看有没有 rush 迹象),到点撤回。"""
        if self._early_scout_done or self.ai.time < 100:
            return
        self._early_scout_done = True
        enemy_main = self.ai.focused_enemy_start()
        if w := self.ai.mediator.select_worker(target_position=enemy_main):
            self.ai.mediator.assign_role(tag=w.tag, role=UnitRole.SCOUTING)
            w.move(enemy_main)

    # O9: 侦查情报→开局决策的评估时点(探机 100s 出发,留 70s 赶路/送死窗口)
    _SCOUT_VERDICT_AT: float = 170.0
    # O9: rush 征兆的"早出兵建筑"(看到 ≥2 个即判 rush;与判据早期多兵互补)
    _MILITARY_STRUCTS = {
        UnitID.BARRACKS, UnitID.GATEWAY, UnitID.SPAWNINGPOOL, UnitID.ROACHWARREN,
    }

    def _evaluate_scout_intel(self) -> None:
        """O9 侦查情报 → 开局决策闭环(carrier 流,一局一次,t≈170s)。

        探机(_early_scout)/steer scout 的情报 → 三档(判据纯函数
        production_plans.scout_verdict):
        (a) rush 征兆(早出兵建筑×2 / 早期多兵) → 提前置 _rush_active,
            复用现有响应包(出叉+铺塔+守家),比"敌兵压到 40 格"提前 ~1 分钟;
        (b) 对面开矿/科技开局 → 维持贪打法(什么都不做);
        (c) 没探到(探机被杀/没找到主家,enemy_structures 空) → 保守按疑似 rush。
        评估完把 SCOUTING 农民撤回采矿(情报已用,别留在敌家白送,同 O4 精神)。
        只挂 carrier:tempest/stalker 是已验证基线,行为一行不动。"""
        if self._scout_verdict_done or self._flow.name != "carrier":
            return
        if self._flow.pivot is None or self.ai.time < self._SCOUT_VERDICT_AT:
            return
        self._scout_verdict_done = True
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        military = sum(
            1 for s in self.ai.enemy_structures if s.type_id in self._MILITARY_STRUCTS
        )
        army = sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and u.type_id not in workers
        )
        verdict = scout_verdict(
            intel=bool(self.ai.enemy_structures),
            military_structs=military,
            early_army=army,
        )
        if verdict != "greedy":
            self._rush_active = True
            self._rush_clear_since = None
        for s in self.manager_mediator.get_units_from_role(role=UnitRole.SCOUTING):
            self.manager_mediator.assign_role(tag=s.tag, role=UnitRole.GATHERING)
            if self.ai.mineral_field:
                s.gather(self.ai.mineral_field.closest_to(s))

    @property
    def rush_active(self) -> bool:
        """rush 检测是否成立。combat 守家、O4 侦查农民撤回都读它。"""
        return self._rush_active

    def _rush_gateway_boost(self) -> None:
        """E3d: rush 期间敌可见兵力超过在场叉子数时追加 gateway(封顶 2)。
        单 gateway ~28s 一叉是实证瓶颈——叉子永远分批到场被围殴(在场恒 1)。"""
        pv = self._flow.pivot
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        enemy_army = sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and u.type_id not in workers
        )
        have = (
            len(self.manager_mediator.get_own_structures_dict[UnitID.GATEWAY])
            + len(self.manager_mediator.get_own_structures_dict[UnitID.WARPGATE])
            + self.manager_mediator.get_building_counter[UnitID.GATEWAY]
        )
        if rush_needs_gateway(
            rush_active=self._rush_active,
            rush_zealots=pv.rush_zealots if pv else 0,
            enemy_army=enemy_army,
            zealots=self.manager_mediator.get_own_unit_count(
                unit_type_id=UnitID.ZEALOT
            ),
            gateways_have=have,
        ) and self.ai.can_afford(UnitID.GATEWAY):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, UnitID.GATEWAY)
            )

    def _update_rush_state(self) -> None:
        """pivot·rush 检测与解除。判据(2026-07 初版):
        ≥2 敌作战单位压到家 40 格内(沿用 F2) 或 4 分钟前敌可见兵力 ≥6(兵力异常=快攻)。
        成立后:连出叉子顶(见 _effective_spawn) + F2 铺塔 + 全军守家(combat 读 _rush_active);
        40 格内无敌 60 秒后自动解除,恢复正常生产/进攻。"""
        if self._flow.pivot is None:
            return
        home = self.ai.start_location
        workers = {UnitID.SCV, UnitID.PROBE, UnitID.DRONE, UnitID.MULE}
        near = sum(
            1 for u in self.ai.enemy_units
            if not u.is_structure and u.type_id not in workers
            and u.position.distance_to(home) < 40
        )
        early_swarm = (
            self.ai.time < 240
            and sum(1 for u in self.ai.enemy_units
                    if not u.is_structure and u.type_id not in workers) >= 6
        )
        if near >= 2 or early_swarm:
            self._rush_active = True
            self._rush_clear_since = None
            return
        if self._rush_active:
            if self._rush_clear_since is None:
                self._rush_clear_since = self.ai.time
            elif self.ai.time - self._rush_clear_since > 60:
                self._rush_active = False
                self._rush_clear_since = None

    def _effective_spawn(self) -> dict:
        """当前实际 spawn 配方 = 流派配方 + pivot 动态修正:
        rush 中 → 只出叉子顶到 rush_zealots 个;对面爆空军 → 混入 anti_air_units。"""
        pv = self._flow.pivot
        if pv is None:
            return self._flow.spawn_dict()
        # rush 响应:叉子还没顶够数,全力补叉
        if self._rush_active and pv.rush_zealots:
            zealots = self.manager_mediator.get_own_unit_count(
                unit_type_id=UnitID.ZEALOT
            )
            if zealots < pv.rush_zealots:
                return {UnitID.ZEALOT: {"proportion": 1.0, "priority": 0}}
        # 反空军 pivot:敌可见空军主力 ≥ trigger → 混入对空兵种
        air_threat = sum(
            1 for u in self.ai.enemy_units
            if u.is_flying and not u.is_structure
            and u.type_id not in (UnitID.OBSERVER, UnitID.WARPPRISM,
                                  UnitID.MEDIVAC, UnitID.OVERSEER)
        )
        if air_threat >= pv.anti_air_trigger and pv.anti_air_units:
            spawn = dict(self._flow.spawn_dict())
            for name in pv.anti_air_units:
                uid = getattr(UnitID, name, None)
                if uid is not None:
                    spawn[uid] = {
                        "proportion": pv.anti_air_proportion, "priority": 0,
                    }
            return self._apply_save_up(self._apply_floor(spawn))
        return self._apply_save_up(self._apply_floor(self._flow.spawn_dict()))

    def _apply_floor(self, spawn: dict) -> dict:
        """E3e 舰队成型前地面保底:舰队主 C 出生前混入保底兵种(默认叉子,矿耗
        不吃气),达 cap 或主 C 上线自动退出。rush 响应的叉子覆盖优先(不进这里);
        保底兵种在 save_up 里走 exempt(保命不截断,见 _apply_save_up)。"""
        pf = self._flow.pre_fleet
        if pf is None:
            return spawn
        uid = getattr(UnitID, pf.id_name, None)
        if uid is None:
            return spawn
        return pre_fleet_spawn(
            spawn,
            floor_id=uid,
            floor_count=self.manager_mediator.get_own_unit_count(unit_type_id=uid),
            floor_cap=pre_fleet_cap(
                pf.cap, pf.per_enemy, pf.max, self._visible_enemy_army_count()
            ),
            fleet_online=self.manager_mediator.get_own_unit_count(
                unit_type_id=self._primary_unit_id()
            ) > 0,
        )

    def _apply_save_up(self, spawn: dict) -> dict:
        """O5 憋气机制(方案 b):spawn dict 喂 SpawnController 前过 save_up_spawn。
        freeflow 下 p0(航母)买不起就会被 p1(风暴)fall-through 吃掉每一滴气,
        永远攒不出 250 气 —— 这里按占比/气缺口动态截断低优先兵种。
        阈值 = flows.yml 的 save_up(气缺口,0=关);单兵种配方无需处理直接返回。
        E3c:pivot 反空军混编兵种(STALKER)走 exempt 永不截断 —— 它是保命的防空,
        不是副 C(敌 6 腐化时被截断 = 零对空团灭)。"""
        gap = self._flow.save_up
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

    def _want_dynamic_expand(self) -> bool:
        """动态开矿是否已触发(配了 max_bases 的流派,rush 内建门)。
        E3k:update 头部算一次,ExpansionController 注册与攒钱预留共用。"""
        ae = self._flow.auto_expand
        if ae is None or not ae.max_bases:
            return False
        return should_expand_dynamic(
            bases=self.ai.townhalls.amount,
            max_bases=ae.max_bases,
            nexus_pending=self.manager_mediator.get_building_counter[UnitID.NEXUS],
            supply_workers=self.ai.supply_workers,
            workers_per_base=ae.when_workers,
            own_army_supply=self.ai.supply_used - self.ai.supply_workers,
            enemy_army_supply=self._visible_enemy_army_supply(),
            advantage_supply=ae.advantage_supply,
            rush_active=self._rush_active,
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
        self.ai.register_behavior(
            BuildStructure(self.ai.start_location, UnitID.NEXUS)
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

    async def _build_core_structure(self, structure_id: UnitID) -> None:
        """Here to prevent repeated logic building core structures.

        Parameters
        ----------
        structure_id : UnitTypeId
            What we want to build
        """
        if (
            not self._structure_present_or_pending(structure_id)
            and self.ai.tech_requirement_progress(structure_id) >= 1.0
            and self.ai.can_afford(structure_id)
        ):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, structure_id)
            )

    def _build_probes(self, ready_townhalls: Units) -> None:
        """Add probes.

        Parameters
        ----------
        ready_townhalls : Units
            Current ready nexuses we can train from.
        """
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
    ) -> None:
        """按当前流派的 core_structures 爬科技链(flows.yml 配置驱动)。

        building_counter : Dict[UnitTypeId, int]
            What is currently pending in the building tracker
        structures_dict : Dict[UnitTypeId, Units]
            Data structure of current buildings.
        """
        # 气随基地数放大：每个已建好的基地采满 2 个气矿（吃气大户流派的命脉）。
        # 前期没兵营时先只开 1 个气（保持原起手节奏）。
        max_gas_buildings = (
            2 * self.ai.townhalls.ready.amount
            if UnitID.GATEWAY in structures_dict
            else 1
        )
        if self.ai.gas_buildings.amount < max_gas_buildings:
            self._build_gas()

        ready_pylons: list[Unit] = [
            p for p in structures_dict[UnitID.PYLON] if p.is_ready
        ]
        if not ready_pylons:
            return

        for structure_id in self._flow.core_structure_ids():
            if structure_id == UnitID.FLEETBEACON:
                # 特例:tech_requirement_progress 对舰队航标不准,需有就绪星门才建
                if (
                    not self._structure_present_or_pending(UnitID.FLEETBEACON)
                    and [s for s in structures_dict[UnitID.STARGATE] if s.is_ready]
                ):
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
        near: 指定只建该基地 12 格内的气矿(O13 按基地补气);None=全局最近的。"""
        if (
            self.manager_mediator.get_building_counter[UnitID.ASSIMILATOR] != 0
            or not self.ai.can_afford(UnitID.ASSIMILATOR)
            or not self.ai.townhalls
        ):
            return
        ref = near.position if near is not None else self.ai.start_location
        geysers: Units = self.ai.vespene_geyser.filter(
            lambda vg: not self.ai.gas_buildings.closer_than(2, vg)
            and vg.distance_to(ref) < 12
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
        if UnitID.GATEWAY not in self.manager_mediator.get_own_structures_dict:
            return  # 起手单气节奏归 _build_flow_structures,这里只管"有兵营后双气满采"
        # 在建气矿的落点(算各基地 pending 数用)
        pending_at = [
            info[TARGET].position
            for info in tracker.values()
            if info[TRACKER_ID] == UnitID.ASSIMILATOR and info.get(TARGET)
        ]
        for th in self.ai.townhalls.ready:
            have = self.ai.gas_buildings.closer_than(12, th).amount
            pending = sum(1 for p in pending_at if th.position.distance_to(p) < 12)
            if have + pending < 2:
                self._build_gas(near=th)

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
        sid = getattr(UnitID, ep.id_name, None)
        if sid is None:
            return
        have_structures: list[Unit] = list(structures_dict[sid])
        if sid == UnitID.GATEWAY:
            have_structures += structures_dict[UnitID.WARPGATE]
        if not have_structures:
            return
        if sid == UnitID.STARGATE:
            gas_per_base = [
                self.ai.gas_buildings.filter(lambda g: g.is_ready)
                .closer_than(12, th).amount
                for th in self.ai.townhalls.ready
            ]
            desired = gas_gated_stargate_target(ep.cap, gas_per_base)
        else:
            desired = min(ep.cap, ep.base + self.ai.townhalls.ready.amount)
        have = len(have_structures) + self.manager_mediator.get_building_counter[sid]
        if (
            have < desired
            and self.ai.minerals > 400  # 只在矿有富余时追加，别抢科技/造兵的钱
            and self.ai.can_afford(sid)
        ):
            self.ai.register_behavior(
                BuildStructure(self.ai.start_location, sid)
            )

    def _spend_bank(self) -> None:
        """滚雪球(Q3,司令要求):前 20 分钟存款淤积(>800)时把钱换成战场优势——
        能开矿先开(基地<4,钱生钱),否则突破流派常规上限追加产兵建筑(存款越多补得越多)。
        治"经济优势大但钱花不完,没转化成兵力"。"""
        if self.ai.time > 1200 or self.ai.minerals < 800:
            return
        if self.ai.townhalls.amount < 4 and self.ai.can_afford(UnitID.NEXUS):
            self.ai.register_behavior(
                ExpansionController(
                    to_count=self.ai.townhalls.amount + 1, max_pending=1
                )
            )
            return
        ep = self._flow.extra_production
        if ep is None:
            return
        sid = getattr(UnitID, ep.id_name, None)
        if sid is None or not self.ai.can_afford(sid):
            return
        have = (
            len(self.manager_mediator.get_own_structures_dict[sid])
            + self.manager_mediator.get_building_counter[sid]
        )
        if sid == UnitID.GATEWAY:  # warpgate 也是产能
            have += len(self.manager_mediator.get_own_structures_dict[UnitID.WARPGATE])
        if have < min(12, ep.base + self.ai.townhalls.ready.amount
                      + self.ai.minerals // 800):
            self.ai.register_behavior(BuildStructure(self.ai.start_location, sid))

    def _front_point(self) -> Point2:
        """F1: 前线折跃点 —— 敌我之间偏敌 60%。让 WarpInManager 优先把兵折跃到前线
        水晶塔（而非主基地），配合 _build_forward_pylon 实现远程投送。"""
        return self.ai.start_location.towards(self.ai.focused_enemy_start(), 0.6)

    def _build_forward_pylon(self) -> None:
        """F1: 在前线造水晶塔，给折跃门提供前线电源（兵秒投前线，不全程走）。
        条件：warpgate 已研究（能折跃）+ 矿富余 + 还没造过（一次性）。
        ⚠️ 前线塔易被打，是最小方案的固有风险（完整方案会用折跃棱镜）。"""
        if self._forward_pylon_built:
            return
        # warpgate 研究好才值得造前线塔（否则 gateway train 用不上前线电源）
        if UpgradeId.WARPGATERESEARCH not in self.ai.state.upgrades:
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
        if order.get("defend") == "yes":
            return True
        if self.ai.time > 360:  # 6 分钟后自动铺防御
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
        targets: list[Unit] = []
        for name in self._flow.chrono.targets:
            sid = getattr(UnitID, name, None)
            if sid is None:
                continue
            targets = self.manager_mediator.get_own_structures_dict[sid]
            if targets:
                break
        if not targets:
            return
        primary = self._primary_unit_id()
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
