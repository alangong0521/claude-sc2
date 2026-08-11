"""生产计划纯逻辑 —— 种族无关的\"该造多少农民/多少气\"计算,可离线单测。

ProductionManager 各种族路径(Protoss 现有、Terran M1)都从这里取目标数量,把\"算多少\"
和\"怎么造(ares 行为)\"分开:前者纯逻辑可测,后者需运行时。
"""
from __future__ import annotations

import math


def worker_target(num_townhalls: int, per_base: int = 22, cap: int = 70) -> int:
    """农民目标数:每基地 per_base 个(16 矿+6 气),全局封顶 cap 给军队留供给。

    单基地 = per_base(与旧 Protoss _build_probes 行为一致);开矿后线性抬升到 cap。
    num_townhalls<=0 → 0。纯逻辑,可单测。
    """
    if num_townhalls <= 0:
        return 0
    return min(cap, per_base * num_townhalls)


def gas_target(
    ready_townhalls: int, has_production: bool, per_base: int = 2, opener: int = 1
) -> int:
    """气矿目标数:有兵营/军事建筑后每个已建好基地采 per_base 个气;开局没军事建筑先只开 opener 个
    (保持起手农民节奏,吃气单位少时不浪费农民采气)。

    ready_townhalls<=0 → 0。纯逻辑,可单测(镜像 Protoss _build_tempest_rush_structures 的气逻辑,
    但种族无关:Terran 的\"has_production\"= 有 BARRACKS/FACTORY 等)。
    """
    if ready_townhalls <= 0:
        return 0
    if not has_production:
        return min(opener, per_base * ready_townhalls)
    return per_base * ready_townhalls


def upgrade_tech_buildings(upgrade_ids: list, done=frozenset()) -> list:
    """升级链当前该补的科技建筑（去重保序）。

    交给带 can_afford 守卫的 _build_core_structure 补建；UpgradeController 只负责
    研究（auto_tech_up_enabled=False）——ares TechUp 自动补建不查存款就把农民
    钉在建造点干等（O1 实证），所以前置建筑由 bot 层守卫建造。

    - 研究建筑(researched_from)全量列出（便宜,如 FORGE）；
    - 高级前置(required_building,如盾 L2/L3 的 TWILIGHTCOUNCIL)只在**同线上
      一阶完成后**才补(O10)——否则开局就抢 100 气建暮光议会,拖慢星门/航标。
    done = 已完成升级集合（运行时用 ai.state.upgrades）。纯逻辑，可单测。
    """
    from sc2.dicts.unit_research_abilities import RESEARCH_INFO
    from sc2.dicts.upgrade_researched_from import UPGRADE_RESEARCHED_FROM

    done = set(done)
    buildings: list = []
    for i, uid in enumerate(upgrade_ids):
        researched_from = UPGRADE_RESEARCHED_FROM[uid]
        if researched_from not in buildings:
            buildings.append(researched_from)
        required = RESEARCH_INFO[researched_from][uid].get("required_building")
        if required and required not in buildings:
            same_line_earlier = [
                e for e in upgrade_ids[:i]
                if UPGRADE_RESEARCHED_FROM[e] == researched_from
            ]
            if all(e in done for e in same_line_earlier):
                buildings.append(required)
    return buildings


def save_up_spawn(
    spawn: dict,
    *,
    counts: dict,
    affordable: dict,
    resource_gap: dict,
    buildable: dict,
    max_gap: float,
    exempt: set | None = None,
) -> dict:
    """憋气机制（O5 方案 b）：给 freeflow 配比加「攒资源等高优先兵种」的动态截断。

    freeflow 下 ares SpawnController 忽略配比只按优先序：p0 买不起就 fall-through
    到 p1，低优先兵种若永远可负担就把瓶颈资源永远吃掉（C5a 镜像，O5 实证：
    风暴 175 气吃掉每一分钱，航母 250 气永远攒不出）。本函数在 spawn dict 喂给
    SpawnController 前按当前局势裁剪，bot 层实现、不动 ares：

    - p0 = 当前可造（科技就绪）的最高优先兵种；可造兵种 <2 个 → 原样返回（没得截）。
    - p0 编队占比 ≥ 配比 → 把 p0 摘出 dict，低优先兵种照常补位（副 C 语义保留）；
      摘掉后剩下的没有可造兵种 → 原样返回（防精确配比点停产，C5a 教训）。
    - p0 占比落后 → p0 买得起，或资源缺口 ≤ max_gap（「接近买得起」，阈值走
      flows.yml 的 save_up）时，只留 p0（截断后续低优先，攒资源等它）；
      缺口还很大 → 原样返回，低优先兵种先顶着生产。
      资源缺口 = max(气缺口, 矿缺口)（E3h 实证：只看气会在矿瓶颈局把 p1 也锁死——
      气 2000+ 躺着、矿永远不够 p0，截断永不解除 = 双锁死局）。
    - exempt：永不截断的兵种集合（如 pivot 反空军混编——追猎是保命的防空，
      不是副 C；E3c 实证：被 save_up 截断后敌 6 腐化时 STALKER=0 团灭）。

    key 不限类型（测试用字符串,运行时用 UnitTypeId）。纯逻辑，可单测。
    """
    if len(spawn) < 2:
        return dict(spawn)
    units = sorted(spawn, key=lambda n: spawn[n]["priority"])
    ready = [u for u in units if buildable.get(u, True)]
    if len(ready) < 2:
        return dict(spawn)
    p0 = ready[0]
    total = sum(counts.get(u, 0) for u in units)
    share = counts.get(p0, 0) / total if total else 0.0
    if total and share >= spawn[p0]["proportion"]:
        rest = {u: c for u, c in spawn.items() if u != p0}
        if any(u in ready for u in rest):
            return rest
        return dict(spawn)
    if not affordable.get(p0, False) and resource_gap.get(p0, 0) > max_gap:
        return dict(spawn)
    kept = {p0: spawn[p0]}
    for u in exempt or ():
        if u in spawn:
            kept[u] = spawn[u]
    return kept


def should_expand_dynamic(
    *,
    bases: int,
    max_bases: int,
    nexus_pending: int,
    supply_workers: int,
    workers_per_base: int,
    own_army_supply: float,
    enemy_army_supply: float,
    advantage_supply: float,
    rush_active: bool,
    now: float = 0.0,
    first_expand_at: float = 0.0,
    minerals: float = 9999.0,
    fleet_total: int = 999,
    fleet_min_for_expand: int = 3,
    mineral_floor_for_expand: float = 500.0,
) -> bool:
    """动态开矿触发判定（E2，carrier 流）。纯逻辑，可单测。

    爆仓触发：农民 ≥ workers_per_base × 当前基地数（矿线饱和，开分矿消化农民）；
    优势触发：我方 army supply ≥ 敌可见 army supply + advantage_supply（前线有优势提前开）；
    O30 首扩时间触发：bases==1 且 first_expand_at>0 且 now>=first_expand_at（carrier 该
      t≈200 早开 2 矿,不等爆仓——爆仓 when_workers 模式在塔吃矿下永不可达致单矿锁死）。
    约束：rush_active 期间不开（rush 响应优先）、到 max_bases 停、已有 nexus 在建不叠加。
    O159/O160(o157-vh-zerg-power game_01/02 实证): 首扩之后(bases>=2)舰队未成规模
    **且**矿物不足时禁止继续扩张,防止fleet=0或只有钱但无舰队时连开三/四矿、
    防御面被Power一波穿一个。
    """
    if rush_active or bases >= max_bases or nexus_pending:
        return False
    saturated = workers_per_base > 0 and supply_workers >= workers_per_base * bases
    # O222(o217-lane2 game_05 实证):硬饱和(溢出 ≥8 农民)时舰队门/矿门全旁路 ——
    # 敌 97 supply vs 我 63 的败局里,2 矿 44 农硬饱和仍被 fleet<3 门拦死三矿,
    # Zerg 无压力自由运营滚到 2 倍兵力;硬饱和不开矿 = 农民人口纯浪费。
    hard_saturated = (
        workers_per_base > 0 and supply_workers >= workers_per_base * bases + 8
    )
    # O160: 首扩后必须同时满足「有基本舰队」和「矿物够再撑一矿」才扩,
    # 原OR门导致矿多时 fleet=0 仍扩(500矿瞬间被Nexus+塔吃掉)。
    # O216g(司令观察/o216f 尸检实证):矿线饱和(如主基 26 农/分矿 16 农满载)
    # 时矿门不再拦——不开新矿=农民占人口零产出,舰队门(fleet>=3)保留防裸奔。
    if (
        bases >= 2
        and not hard_saturated
        and (
            fleet_total < fleet_min_for_expand
            or (minerals < mineral_floor_for_expand and not saturated)
        )
    ):
        return False
    advantage = (
        enemy_army_supply > 0
        and own_army_supply >= enemy_army_supply + advantage_supply
    )
    first_due = bases == 1 and first_expand_at > 0 and now >= first_expand_at
    return saturated or advantage or first_due


def expansion_cannon_count(ec_min: int, ec_max: int, enemy_army: int) -> int:
    """分矿塔数估算（E2）：clamp(min, min + 敌可见作战单位//4, max)。
    min=保守线(给回援争取时间)，每多 4 个敌兵 +1 塔，max 封顶防塔烧钱。纯逻辑。"""
    return max(ec_min, min(ec_max, ec_min + max(0, enemy_army) // 4))


def expansion_cannon_min_dynamic(
    ec_min: int,
    fleet_total: int,
    fleet_min: int = 3,
    early_cap: int = 3,
    zero_fleet_cap: int = 2,
) -> int:
    """O161/O179: 舰队成型前降低分矿塔 baseline，防止二矿一起就铺 6 塔把舰队矿吃光。

    carrier 流 expansion_cannons.min=6 是为 Power 中局波次设计的;但 fleet<3 时
    6 塔×150 矿=900 矿，直接把首舰/科技憋死。fleet 未成规模时把 min 压到 early_cap，
    成型后再恢复到 ec_min。

    O179(o178-vh-zerg-timing game_01-03 实证):fleet=0 时 early_cap=3 仍把 Nexus/首舰
    资金吃光(3 炮+2 电池+forge+水晶 > 单矿收入)，进一步压到 zero_fleet_cap=1，
    确保星门/FB 就绪后有钱造出第一艘舰队。
    O216(o215-vh-zerg-timing 0-9 实证):zero_fleet_cap 1→2，fleet=0 时仍需 2 座
    保命塔配合 gateway 堵口，避免二矿一落就被 4 地面单位反复抄家;2 塔 300 矿
    在 Timing 局可承受，且为后续动态扩容打底。
    rush 期由调用方另走 rush_hold 拉满，不进这里。
    """
    if fleet_total <= 0:
        return min(ec_min, zero_fleet_cap)
    if fleet_total >= fleet_min:
        return ec_min
    return min(ec_min, early_cap)


def main_siege_active(enemy_ground_near: int, threshold: int) -> bool:
    """需求3:敌大军压上主基 → 触发主基加强光子塔(只在主基,双实例 exclude)。
    主基 townhall radius 内敌地面作战单位 ≥ threshold → True。纯判据,可单测。
    radius 放大(默认 25,比 E6 矿区 15 大)给造塔 ~29s 留提前量(敌压脸上再建来不及)。
    enemy_ground_near 由调用方按 is_combat_type 口径算好(排除工人/侦查/运输/飞行)。"""
    return enemy_ground_near >= threshold


def full_gas_bases(gas_per_base: list[int], full: int = 2) -> int:
    """满采气基地数（E2 气体闸门）：每基地 ready assimilator ≥ full(默认 2) 算满采。
    1 个满采气基地 ≈ 养 1 个星门全力产航母（210+ 气/分钟 vs 航母 234 气/分钟）。"""
    return sum(1 for c in gas_per_base if c >= full)


def gas_gated_stargate_target(cap: int, gas_per_base: list[int], bonus: int = 1) -> int:
    """星门目标数的气体闸门（E2）：min(cap, 满采气基地数 + bonus)。
    +1 的理由（司令 2026-07-21）：气矿会有存款积累可爆兵，且风暴耗气更慢
    （175气/43s vs 航母 250气/64s），产能可以略超稳态气体收入。
    例：单矿双气满采 → 2 星门；双矿四气满采 → 3 星门。
    P2b：pivot 模式 bonus=2（单矿 → 3 星门，见 stargate_gas_gate_bonus）。纯逻辑。"""
    return min(cap, full_gas_bases(gas_per_base) + bonus)


def scout_verdict(*, intel: bool, military_structs: int, early_army: int) -> str:
    """侦查情报 → 开局决策（O9）。纯逻辑，可单测。

    - "rush"：看到 rush 征兆（早出兵建筑 ≥2，或早期可见作战单位 ≥6——与
      `_update_rush_state` 的 early_swarm 阈值同源）→ 提前触发 rush 响应包；
    - "greedy"：有情报且没有 rush 迹象（对面开矿/科技开局）→ 维持贪打法；
    - "unknown"：探机没探到（被杀/没找到主家，intel=False）→ 按疑似 rush 保守处理。
    """
    if not intel:
        return "unknown"
    if military_structs >= 2 or early_army >= 6:
        return "rush"
    return "greedy"


def research_paused_for_rush(rush_active: bool, transition_active: bool = False) -> bool:
    """rush 期间研究是否整体让位（E3 回归修复）。纯逻辑，可单测。

    O8 把 UpgradeController 以 prioritize=True 放进 MacroPlan 最前——研究预留
    截断后续 plan，把 rush 响应包（叉子/塔都在 SpawnController/后续行为里）饿死
    （bench e3-carrier-vh-zerg-rush game_02 实证：rush 窗口只出 1 叉 2 塔败北）。
    rush_active（含 O9 scout verdict 的提前触发）期间不注册 UpgradeController，
    响应包独占资源；rush 解除后恢复 prioritize 预留。
    O103-①（o102 局3/局5 实证）：transition_active 全程同样让位 —— 接触式
    rush_active 60s 无接触自动解除（t≈141），而波次 155-185 才到脸；研究在
    守窗恢复注册，prioritize 攒资截断把 SpawnController 压死（forge 就绪 →
    SHIELDS L1 买得起前的每一帧，兵营空转，26s 零叉）。过渡形态本身就是
    「这局在被 rush」的持久状态，研究让位语义应与 rush_active 同长。
    transition_active 缺省 False → 旧签名行为逐位不变。
    """
    return rush_active or transition_active


def rush_triggers_defense(rush_active: bool, rush_cannons: bool) -> bool:
    """rush 检测成立时是否立即启动铺塔（E3b 实证修复）。纯逻辑，可单测。

    rush 响应包名义上含铺塔，但塔的触发（`_should_build_defense`）原来只看
    「敌兵压到家 40 格」——炮塔要 ~30s 建造 + 水晶供电，压到门口再建来不及
    （e3b game_02 实证：检测 130s 成立，首塔 221s 才立，基地 232s 掉）。
    修复：rush_active 即铺塔（提前 ~85s）。rush_cannons=False（E1 臂 B 纯叉子）
    时保持不铺。
    """
    return rush_active and rush_cannons


def rush_needs_gateway(
    *,
    rush_active: bool,
    rush_zealots: int,
    enemy_army: int,
    zealots: int,
    gateways_have: int,
    cap: int = 2,
) -> bool:
    """rush 期间是否追加 gateway 产能（E3d 实证修复）。纯逻辑，可单测。

    E3d 实证：响应包只改 spawn 配方，单 gateway ~28s 一叉，叉子永远分批到场
    被围殴（在场兵力恒 1）。触发：rush_active 且响应包要出叉（rush_zealots>0）
    且敌可见兵力 > 在场叉子数，产能封顶 cap 个。
    """
    if not rush_active or not rush_zealots:
        return False
    return enemy_army > zealots and gateways_have < cap


def pre_fleet_spawn(
    spawn: dict,
    *,
    floor_id,
    floor_count: int,
    floor_cap: int,
    fleet_online: bool,
    priority: int = 5,
) -> dict:
    """舰队成型前地面保底（E3e 实证）。纯逻辑，可单测。

    背景：carrier 流 spawn 双兵种（航母/风暴）都要舰队航标——航标就绪前
    星门全闲、军队真空（e3e game_01：t=402-562 兵力=1 先知，被一波穿两矿）。
    规则：舰队主 C 出生前（fleet_online=False）把保底兵种（矿耗地面兵，
    不吃气不抢航母资源）混入 spawn，priority 压低（舰队能产时舰队优先）；
    达 floor_cap 或舰队上线（fleet_online=True）自动退出，回归主配方。
    与 save_up 的交互：调用方把 floor_id 加进 exempt（保底=保命,不截断）。
    rush 响应的叉子覆盖优先级更高，不进本函数。
    """
    if fleet_online or floor_count >= floor_cap:
        return dict(spawn)
    out = dict(spawn)
    out[floor_id] = {"proportion": 1.0, "priority": priority}
    return out


def pre_fleet_cap(base: int, per_enemy: float, hard_max: int, enemy_army: int) -> int:
    """保底上限随敌可见兵力伸缩（E3f 实证）。纯逻辑，可单测。

    E3f game_02：固定 cap=6 的叉子在敌第二波（19 狗+7 蟑螂+4 刺蛇）面前瞬间
    熔化——保底量必须随威胁走：clamp(base, round(敌作战单位×per_enemy), hard_max)。
    hard_max ≤ 0 → 固定 base（向后兼容 E3e 行为）。base 是和平期下限，
    per_enemy 是威胁系数，hard_max 防把经济全砸进地面兵。
    """
    if hard_max <= 0:
        return base
    return max(base, min(hard_max, round(enemy_army * per_enemy)))


def ground_floor_gateways(
    has_pre_fleet: bool,
    transition_active: bool,
    gateways_have: int,
    min_gw: int = 2,
) -> bool:
    """O134-①(o133 局2 实证):非过渡地面保底的兵营产能位。纯逻辑,可单测。

    局2:carrier 标准路径(core_structures 单 GW)GW1 拖到 ~350 才落地,
    地面 floor 有配方无产能,525 波到脸仅 1 叉。配了 pre_fleet 的流派
    (现仅 carrier)在非过渡期保底 min_gw 座兵营;过渡激活后由过渡配方的
    gateway_cap 接管(不双管)。
    """
    return has_pre_fleet and not transition_active and gateways_have < min_gw


def ground_floor_unmet(
    has_pre_fleet: bool,
    transition_active: bool,
    ground_count: int,
    floor_target: int,
) -> bool:
    """O134-②(o133 局2 实证):地面保底未达判据。纯逻辑,可单测。

    局2 资金链根因:cyber 就绪(~400)后 UpgradeController prioritize=True
    为空军升级攒钱、每帧截断 MacroPlan,SpawnController 拿不到帧也拿不到矿
    (矿恒 0-50,气 2900 烂着),叉子卡 1 直到 525 波。地面保底未达时
    研究不得截断产兵(调用方:prioritize 翻假,研究只在买得起时点);
    过渡期由过渡配方接管,不适用。
    """
    return (
        has_pre_fleet and not transition_active and ground_count < floor_target
    )


def floor_army_defends_home(
    has_pre_fleet: bool, primary_count: int, enemy_race_name: str | None = None
) -> bool:
    """舰队成型前（pre_fleet 保底阶段）地面兵是否默认守家（E3g trickle 实证）。
    纯逻辑，可单测。

    E3g game_01：无 stance、rush_active=False 时 combat 默认 attack_target=最近
    敌建筑，6 个保底叉子被拉过全图送进蟑螂群（敌波到脸前清零）。规则：
    流派配了 pre_fleet 且舰队主 C 未成型 → 默认守家；主 C 上线恢复默认进攻。
    O32:vs Zerg(primary<3 才出门,攒 3 航母龟缩憋航母);非 Zerg(primary==0,原行为)。
    司令 stance/target 命令与 rush 联动优先级更高,不受影响。"""
    if not has_pre_fleet:
        return False
    if enemy_race_name == "Zerg":
        return primary_count < 3
    return primary_count == 0


def should_pivot_tempest(
    verdict: str | None, flow_name: str, enemy_race_name: str | None = None
) -> bool:
    """O32:是否走风暴主 C pivot(E10)。纯逻辑,可单测。
    - 非 carrier / 非 greedy → False(不 pivot);
    - vs Zerg → False(Zerg Macro 双矿爆兵,风暴压不死;carrier 该航母主 C 龟缩
      憋航母 + 早 2 矿,不烧舰队链矿给 Nexus);
    - 其余(carrier + greedy + 非 Zerg) → True(风暴压制 vs Terran/Protoss 贪开局速胜)。
    注:转型点(carrier_transition_ready)由调用方判,本函数只判 pivot 倾向。"""
    if flow_name != "carrier" or verdict != "greedy":
        return False
    if enemy_race_name == "Zerg":
        return False
    return True


def should_register_autosupply(
    can_afford: bool, supply_left: float, emergency: float = 2.0
) -> bool:
    """是否注册 AutoSupply（O6 守卫 + E3h 水晶紧急通道）。纯逻辑，可单测。

    O6：常态只在买得起时注册（AutoSupply 不查存款，工人会钉在建造点干等）。
    E3h 实证：矿物饥荒局里"买不起"会长期屏蔽水晶排队 → 卡人口 68-100s,
    代价比钉一个工人大 → supply_left ≤ emergency 时即便买不起也注册
    （工人钉在水晶点等 100 矿，人口一解农民链不断）。
    """
    return can_afford or supply_left <= emergency


def should_release_waiting_builder(
    can_afford: bool, attempt_age: float, grace: float = 6.0,
    deficit: float = 0.0, income_5s: float = 0.0, early_age: float = 3.0,
) -> bool:
    """钱不够被派出钉点的建造工人是否撤回采矿（O11/O139-②）。纯逻辑，可单测。

    ares 多条路径（ProtossStaticDefence / ExpansionController / TechUp）不查存款
    就派工人，到位后 BuildingManager 等得起才下 build 命令 → 工人钉点干等。
    原则（司令）：派了等 grace 秒钱仍不够 → 拆 tracker 撤回采矿（行为下帧会
    重新派工，往返途中钱照采）。人口紧急态的水晶例外（E3h-B，故意钉）。
    O139-②(o137 两 lane 事件实证,干等 3s 即亏):提前撤回通道 —— 钉点
    >early_age 且矿缺口靠 5s 收入补不上(deficit > income_5s)→ 别等 grace,
    立即撤回采矿(撤回后同型进 10s 重派冷却,见 _DEFENCE_REDISPATCH_CD);
    TOWNHALL 调用方传 early_age=30(开矿预走位语义不动,O21)。
    缺省 deficit=0/income_5s=0 → 提前通道不触发,旧签名行为逐位不变。
    """
    if can_afford:
        return False
    if attempt_age > early_age and deficit > income_5s:
        return True
    return attempt_age > grace


def assimilator_attempt_stuck(
    now: float, commenced: float, timeout: float = 45.0
) -> bool:
    """气矿建造尝试是否卡死（O13 反卡死）。纯逻辑，可单测。

    e3i game_01 实证：二矿落成后 420s 无气（在建尝试卡 tracker + rush 暂停窗口
    叠加，矿 6075 气 0）。在建气矿超过 timeout 秒没落地 → 拆 tracker 重派。
    """
    return now - commenced > timeout


def nexus_rebuild_active(townhalls: int) -> bool:
    """O15：是否需要一切让位重建 Nexus（基地清零 → 没经济一切免谈）。纯逻辑。"""
    return townhalls == 0


def nexus_rebuild_viable(
    workers: int, minerals_left: int, bank: int = 0, nexus_cost: int = 400
) -> bool:
    """O15：重建是否还有意义（有工人 + 场上还有矿 + 拿得出重建的钱）。纯逻辑。

    E4 实证（game_01）：基地清零且存款 <400 时重建是数学死局——
    没有 townhall 就没有资源入库口，工人采了矿也交不了，收入恒 0、
    存款永远到不了 400，bot 空转 400 秒垃圾时间。
    所以豁免 Q5 判负必须同时满足：工人 >0、矿脉有剩、存款 ≥ nexus_cost。
    """
    return workers > 0 and minerals_left > 0 and bank >= nexus_cost


def expansion_reserve_active(want_expand: bool, can_afford_nexus: bool) -> bool:
    """E3k：动态开矿已触发但暂时买不起 Nexus → 攒钱预留（出兵/造农民让位）。
    纯逻辑，可单测。

    背景（one_base×3）：rush 收尾矿紧，400 矿的 Nexus 无限排在塔/叉/农民之后。
    预留期间不注册 SpawnController、暂停造农民（防御塔保命不动）；
    rush 期间不开矿（六连动不变），O15 重建路径优先级更高。
    """
    return want_expand and not can_afford_nexus


def base_rebuild_active(
    current_bases: int,
    peak_bases: int,
    target_bases: int | None,
    can_afford_nexus: bool,
    rush_active: bool = False,
) -> bool:
    """判断是否需要进入"重建基地"模式（当基地被打掉后）。

    触发条件：
    1. **真的丢过基地**（peak_bases > current_bases）——E6b 回归实证：
       没有这条时开局 1 基地 < carrier max_bases 4，从 t=0 就进"重建模式"，
       造农民/出兵整局被掐死（bench e6b 五局 8 农民封顶、零兵营，~208s 全灭）；
    2. 当前基地数 < 目标基地数；
    3. rush 期间不开（复用六连动不变）。

    纯逻辑，可单测。
    """
    if rush_active or target_bases is None:
        return False
    return peak_bases > current_bases and current_bases < target_bases


def should_evacuate_workers(
    enemy_ground_near: int,
    cannon_cover: bool,
    cannons_near: int = 0,
    threshold: int = 4,
    overwhelm_base: int = 6,
    overwhelm_per_cannon: int = 4,
) -> bool:
    """E6：某基地矿区的农民是否该撤离。纯逻辑，可单测。

    判据（E3m 死因复盘：game_01 农民 42→22 / game_02 47→29，经济断气后
    2000+ 气烂掉）：
    - 敌地面 < threshold → 不撤；
    - 无塔保护（cannon_cover=False）且敌 ≥ threshold → 撤；
    - 有塔但敌 ≥ overwhelm_base + overwhelm_per_cannon×塔数 → 塔被压垮也撤
      （E6 bench 实证：carrier 分矿常态 4-6 塔，VeryHard/Rush 中段波 22 狗
      +9 蟑螂 ~20s 拆光塔再屠农，「塔覆盖就继续采」对此类波是送死；
      小股骚扰（几条狗）塔确实罩得住，继续采）。
    """
    if enemy_ground_near < threshold:
        return False
    if not cannon_cover:
        return True
    return enemy_ground_near >= overwhelm_base + overwhelm_per_cannon * cannons_near


def evacuation_clear(enemy_ground_near: int, clear_below: int = 2) -> bool:
    """E6：被抄基地的敌情是否已退（农民可回采）。纯逻辑，可单测。

    滞回设计：撤离阈值 4，回采判据 <2（而不是 <4）——边界抖动（敌兵在
    3-4 之间徘徊）不会造成「撤离→回采→再撤离」的往返空跑。
    """
    return enemy_ground_near < clear_below


def worker_last_stand(
    enemy_ground_near: int,
    cannons_near: int,
    ready_townhalls: int,
    threat_or_rush: bool,
    overwhelm_base: int = 6,
    overwhelm_per_cannon: int = 4,
) -> bool:
    """O256-①(o255 双 lane 0-9 尸检):主基决死协防判据。纯逻辑,可单测。

    o255 全 9 局同一死因:280-350s 波(9 蟑螂+11 狗 ~20 单位)进主基,
    E6 被两道闸挡死(rush 期主基不撤 + 单基地无处可撤 target=None),
    22-26 农民白死(每局 →5-10),经济断气。算账:22 农民(≈100dps)
    + 4 塔(64dps)对 9 蟑螂是赢面,白死才是输面 —— 塔已被压垮
    (≥overwhelm)且无处可撤时,农民拉去塔下协战比站着被屠强。
    只在「就绪基地 ≤1(无处可撤)+ 有塔可依 + 急性窗(rush/threat)
    + 敌地面达压垮线」四条件同时成立时触发;多基地局走 E6 撤离(更稳),
    非急性窗不扰动运营。
    """
    return (
        threat_or_rush
        and ready_townhalls <= 1
        and cannons_near >= 1
        and enemy_ground_near
        >= overwhelm_base + overwhelm_per_cannon * cannons_near
    )


def pick_evacuation_base(raided_pos, candidates):
    """E6：撤离目标基地选择。纯逻辑，可单测。

    raided_pos : (x, y) 被抄基地坐标
    candidates : [(x, y, covered), ...] 候选基地（**不含被抄基地本身**），
                 covered = 该基地矿区是否有塔覆盖。
    规则：优先「有塔覆盖」的基地（就近），都没有则撤向最近的基地；
    候选为空 → None（无处可撤，交 ares Mining keep_safe 个体避险）。
    """
    if not candidates:
        return None

    def _key(c):
        x, y, covered = c
        d2 = (x - raided_pos[0]) ** 2 + (y - raided_pos[1]) ** 2
        return (0 if covered else 1, d2)

    best = min(candidates, key=_key)
    return (best[0], best[1])


def defense_syncs_with_nexus(nexus_pending: int, townhalls: int) -> bool:
    """分矿塔防是否与 Nexus 同步启动（E3l 实证修复）。纯逻辑，可单测。

    E3l 三局实证：分矿 330-386s 落地后，塔防要等落地 + 6 分钟自动线才启动，
    分矿裸奔 30-100s 被敌反复拆。规则：有 Nexus 在建（nexus_pending>0）或
    已多基地（townhalls≥2）→ 立即启动分矿塔防（先供电后塔序由
    ProtossStaticDefence 自己排）。
    """
    return nexus_pending > 0 or townhalls >= 2


# ────────────────────── B4 防守三角(2026-07,来源:sharpy/QueenBot) ──────────────────────


def defensive_rally_point(
    ramp_top: tuple[float, float],
    ramp_bottom: tuple[float, float],
    offset: float = 4.0,
) -> tuple[float, float]:
    """B4① 防守集结点 = 主坡口顶端朝坡底的反方向 offset 格(sharpy PlanHeatDefender:
    base_ramp.top_center.towards(bottom_center, -4))。纯逻辑,可单测。

    集结在坡后高地(而不是基地中心):响应兵落地即占坡口,射程覆盖上坡敌军;
    基地中心则腹背开阔。top==bottom(退化)→ 原样返回 top。
    """
    dx = ramp_top[0] - ramp_bottom[0]
    dy = ramp_top[1] - ramp_bottom[1]
    dist = math.hypot(dx, dy)
    if dist == 0:
        return (ramp_top[0], ramp_top[1])
    return (ramp_top[0] + dx / dist * offset, ramp_top[1] + dy / dist * offset)


def rush_defend_base(
    threats: list[tuple[float, float, int]],
    main: tuple[float, float],
    main_tol: float = 5.0,
) -> tuple[float, float] | None:
    """B4② rush 时哪个基地承压(sharpy 防御性折跃的目标选择)。纯逻辑,可单测。

    threats : [(x, y, 敌地面单位数), ...] 每个基地的威胁计数(调用方按 25 格口径统计,
              与 _update_rush_state 的威胁口径同源);
    main    : 主基坐标。
    返回 None = 主基承压或无明确威胁(走 B4① 坡口集结点);
    否则返回敌地面单位最多的**分矿**坐标(折跃到被攻击的分矿)。
    计数并列时主基优先(threats 主基在前即可,> 不取 =)。
    """
    best: tuple[float, float] | None = None
    best_n = 0
    for x, y, n in threats:
        if n > best_n:
            best, best_n = (x, y), n
    if best is None or best_n == 0:
        return None
    if abs(best[0] - main[0]) < main_tol and abs(best[1] - main[1]) < main_tol:
        return None  # 承压的是主基 → 坡口集结点
    return best


def rush_stops_gas(rush_active: bool) -> bool:
    """B4③-a(QueenBot rush 应激清单):rush_active 时停气(气矿农民拉去采矿)。
    纯逻辑,可单测。

    理由:rush 响应包(叉子/炮塔/电池)全是矿耗,气在 rush 窗口是死钱;
    多 3 个农民采矿 ≈ +120 矿/分钟,正好喂叉子链。rush 解除自动回气。"""
    return rush_active


def rush_gas_stop_window(
    rush_active: bool, stop_age: float, window: float = 45.0
) -> bool:
    """O117-①(o116 局3/局1 实证):停气的时间窗判据。纯逻辑,可单测。

    B4③-a 停气是给急性 rush 窗(几十秒)设计的;波次 60-90s 一波的慢性
    骚扰下 rush_active 长期 latch,停气变成单向棘轮 —— ares Mining 持续
    把 GATHERING 农民补进气矿,我们持续摘进停气台账,最终全局农民
    38/40 进池、采集池=0、经济停摆(局3 t=480-571 簿记实证)。
    rush 激活的前 window 秒停气(急性窗的矿 > 气);超过窗口自动回气
    (追猎/科技要气,慢性局气不是死钱)。非 transition 流派调用方传
    window=inf(旧行为逐位不变)。
    """
    return rush_active and stop_age < window


def mineral_crisis_gas_stop(
    vespene: float,
    minerals: float,
    fleet_total: int,
    vespene_threshold: float = 600.0,
    mineral_threshold: float = 300.0,
    fleet_min: int = 5,
    bases: int = 99,
    low_base_threshold: int = 2,
    low_base_mineral_threshold: float = 400.0,
) -> bool:
    """O157/O159/O160: 气体相对矿物过剩、矿物枯竭时，把气矿农民拉回采矿。

    背景（o156/o157-vh-zerg-power game_01/02 实证）：vespene 1500+、minerals 0–300、
    舰队 0–2 艘，星门因缺矿停产。继续采气 = 浪费农民时间，拉去采矿才能恢复
    舰队产出。阈值带滞回：触发阈值高于恢复阈值（见调用方），避免边界抖动。
    O159: 阈值提前（vespene≥800 / minerals≤400 / fleet<5），在气体开始烂银行、
    矿物尚有余量时就转矿，避免等到矿物贴 0 才反应。
    O157-b: 基地被压缩到 ≤2 个时，矿物危机阈值放宽到 600——丢基地后每一点
    矿物收入都决定 Nexus 能不能重开，提前停气转矿避免死锁。
    O160(o159-vh-zerg-power game_01 1168s 超时): 舰队成型后(fleet≥5)仍可能
    矿物枯竭(vespene 1473 / minerals 110)，此时 fleet 单位/塔/科技全需矿，
    继续采气 = 气烂银行而矿永远不够。因此触发不再硬绑 fleet<5，改为
    「气体明显富余(≥600)且矿物紧缺(≤300)」即停气；基地≤2 时矿物阈值放宽
    到 400。保留 fleet_total 参数供向后兼容与调用方簿记，不再进入判据。
    """
    _mineral_thr = (
        low_base_mineral_threshold
        if bases <= low_base_threshold
        else mineral_threshold
    )
    return vespene >= vespene_threshold and minerals <= _mineral_thr


def builder_release_exempt(rush_active: bool, defense_urgent: bool) -> bool:
    """O117-②(o116 取证实证):O11 钉点撤回的豁免判据。纯逻辑,可单测。

    E4c 的豁免只看 rush_active;但 presumed/早评 rush 的防御紧急窗里
    rush_active 常常还没置位(接触才确认)—— 塔工钉点等钱 6s 被撤回 +
    15s 重派冷却(O19)= 21s/轮的派工循环,首塔永远慢半拍。
    defense_urgent(rush确认/过渡/presumed,调用方合成)期同样豁免。
    """
    return rush_active or defense_urgent


def reserve_deadlock_break(
    active_since: float | None,
    now: float,
    minerals: float,
    min_price: float = 300.0,
    timeout: float = 60.0,
) -> bool:
    """O131-③(o130 局2/局5 实证):预留死锁保险丝。纯逻辑,可单测。

    任何预留连续 active >timeout 且矿 < min_price/2 → 强制解除(暂停
    攒钱的对象把钱吃光 = 永久暂停)。机制失败的保险丝,事件簿记。
    """
    return (
        active_since is not None
        and now - active_since > timeout
        and minerals < min_price / 2
    )


def defense_sprint_active(
    has_transition: bool,
    defense_urgent: bool,
    forge_ready: bool,
    first_cannon_ready: bool,
    first_zealot_seen: bool,
    enemy_home: int,
    sprint_age: float = 0.0,
    max_age: float = 120.0,
) -> bool:
    """O129(o128b 局2 实证):首波防御冲刺总闸。纯逻辑,可单测。

    逐路径让位修了 6 轮修不完(水晶 4 连拍 400 矿偷 forge) —— 换打法:
    presumed/rush 确认起,到「forge 就绪 + 首塔落地 + 首叉在产」全链路
    完成前 = 冲刺期,一切非链开销(农民/水晶/GW2+/气矿/研究)统一掐死,
    链内顺序硬编码 forge → 首塔 → GW1 → 首叉。接触(敌进家 ≥2)即退出
    (急性窗交还 F2/响应包);链完成即退出(自校正)。只挂 transition 流派。
    """
    if not (has_transition and defense_urgent):
        return False
    if enemy_home >= 2:
        return False
    # O130-①(o129 局3/局4 实证):逃逸阀 —— 冲刺 >120s 强制退出。
    # 链断(兵营被拆/落位失败)时 sprint 永真 → 农民永冻 → 2-3 农死局;
    # 超时回退 F2/正常路径,链断了不能拖死全局。
    if sprint_age > max_age:
        return False
    return not (forge_ready and first_cannon_ready and first_zealot_seen)


def sprint_blocks_probes(workers: int, floor: int = 8) -> bool:
    """O130-①(o129 局3/局4 实证):冲刺期农民训练冻结的豁免判据。纯逻辑,可单测。

    局3/局4:首波农民战损 14→2-3,sprint 锁死探针训练 → 经济归零 →
    链更完不成 → 死亡螺旋。农民 <floor(8) → 冲刺闸不拦探针
    (经济活命优先于链纯洁);≥floor 照拦(冲刺期矿给链)。
    """
    return workers >= floor


def tracker_entry_stale(
    worker_alive: bool, worker_idle: bool, age: float, timeout: float = 10.0
) -> bool:
    """O118-②(o117 局1/2/4 实证):建造 tracker 条目的快速回收判据。
    纯逻辑,可单测。

    三局速败同指纹:首塔派工 = taken,工人被入侵狗群杀在路上,45s 的
    停滞周期对 190s 死局是 eternity。工人死了 → 立即清(不等年龄);
    活着且闲置超 timeout(被别的系统拽走/卡死)→ 清;活着走位中 → 保留。
    """
    return (not worker_alive) or (worker_idle and age > timeout)


def cannon_safe_anchor(
    centroid_xy: tuple, ramp_xy: tuple, depth: float = 2.5
) -> tuple:
    """O118-③(o117 局1/2/4 实证):首塔锚点 = 矿线质心朝远离坡口方向
    再退 depth 格(矿线深处/基地遮蔽位)。纯逻辑,可单测。

    三局速败:首塔(矿线质心锚点)在建造期 25-29s 被入侵狗两口咬掉。
    退到矿线深处后,狗要先穿矿线/基地才够得着建造点 —— 建造期不吃狗,
    成型后照样覆盖矿线(射程 7)。坡口迎敌位留给第二座以后(F2 主链)。
    """
    dx = centroid_xy[0] - ramp_xy[0]
    dy = centroid_xy[1] - ramp_xy[1]
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return centroid_xy
    return (centroid_xy[0] + dx / d * depth, centroid_xy[1] + dy / d * depth)


# B4③-b(QueenBot rush 应激清单):rush 时可取消换现金的在建科技建筑白名单(极其保守)。
# 兵营/电池/水晶/炮塔/基地/气矿是 rush 防御链本身,永远不动(守人口水晶);
# FORGE 是炮塔前置(E3d),STARGATE/CYBERNETICSCORE 是流派核心链,同样不动。
RUSH_CANCELLABLE_TECH: frozenset = frozenset({
    "TWILIGHTCOUNCIL",
    "ROBOTICSFACILITY",
    "ROBOTICSBAY",
    "FLEETBEACON",
    "TEMPLARARCHIVE",
    "DARKSHRINE",
})


def rush_cancellable_structure(
    rush_active: bool, type_name: str, is_ready: bool
) -> bool:
    """B4③-b 在建科技建筑是否可取消换现金(QueenBot 应激清单,极保守白名单)。
    纯逻辑,可单测。

    只取消 rush 激活且未完工(is_ready=False)且命中 RUSH_CANCELLABLE_TECH 的建筑;
    兵营/电池/水晶等防御链结构天然不在白名单(守人口水晶:水晶永不取消)。
    """
    return rush_active and not is_ready and type_name in RUSH_CANCELLABLE_TECH


# ────────────────────── B7 运营队列(2026-07,来源:QueenBot/12PoolBot) ──────────────────────


def bank_production_target(
    minerals: float,
    vespene: float,
    *,
    base: int,
    ready_bases: int,
    cap: int = 12,
    bank: tuple[float, float] = (400.0, 400.0),
    step: float = 800.0,
) -> int | None:
    """B7② 存款自动补产能的目标数(12PoolBot ProductionController
    add_production_at_bank=(400,400),治 bank)。纯逻辑,可单测。

    矿 > bank[0] 且气 > bank[1] 才追加:目标 = min(cap, base + ready_bases + 矿//step)
    (公式沿用 _spend_bank 旧逻辑,矿越多补得越多,cap=12 封顶);
    存款不达标 → None(不追加,常规上限内的补建归 _build_extra_production)。
    """
    if minerals <= bank[0] or vespene <= bank[1]:
        return None
    return min(cap, base + ready_bases + int(minerals // step))


def expansion_max_pending(
    minerals: float,
    *,
    headroom: int = 1,
    rich_threshold: float = 1250.0,
    rich_pending: int = 3,
) -> int:
    """B7③ 扩张动态 max_pending(QueenBot:矿>1250 时 3~4,治 bank+扩张慢)。
    纯逻辑,可单测。

    矿存款 > rich_threshold 且离 max_bases 还有富余(headroom>1)→ 允许多片矿同建
    min(rich_pending, headroom);否则 1(逐矿评估,局势变了就停)。
    rush 否决在判据层(should_expand_dynamic / base_rebuild_active),不进这里。
    """
    if minerals > rich_threshold and headroom > 1:
        return min(rich_pending, headroom)
    return 1


def builder_is_waiting(in_tracker: bool, is_idle: bool, exempt_role: bool) -> bool:
    """O19：有建造指派的农民此刻是否处于「干等建造」状态。纯逻辑，可单测。

    干等 = 在 ares building_tracker 里（有建造指派）+ 闲置（无任何命令）。
    - 走位途中有 move 命令 → is_idle False → 自动排除；
    - 已下建造命令（warp-in/建造中）→ 有命令非闲置 → 排除；
    - 侦查 / 司令接管（PERSISTENT_BUILDER）/ E6 撤离（_EVAC_ROLE）→ exempt_role 排除。
    """
    return in_tracker and is_idle and not exempt_role


def idle_builder_alarm(wait_age: float, threshold: float = 3.0) -> bool:
    """O19：连续干等超过 threshold 秒 → 该发 idle_builder 事件。纯逻辑，可单测。

    阈值沿革：1s（章程原始线）→ **3s**（o19fix bench 复验实证：全部 265 个
    episode 干等时长都是 1s——本 bot 存款贴近 0 的花钱风格下，「到位等 1-2s
    钱」是常态噪声而非问题；真问题是钉到 6s 被 O11 撤回的）。3s 仍 < O11
    watchdog 的 6s 撤回线，真钉点必曝光；只观测发事件，不改任何行为。
    """
    return wait_age > threshold


def scout_verdict_timing(
    intel: bool,
    scout_en_route: bool,
    redispatched: bool,
    rush_active: bool,
    now: float,
    verdict_at: float = 170.0,
    hard_deadline: float = 230.0,
) -> str:
    """E7/O16 侦查断链：verdict 时机决策。纯逻辑，可单测。

    背景（e6c2 五局实证）：探机 100s 出发、路 ~40s，而 Rush 局敌兵 129-141s
    到脸触发 O4 撤回——4/5 局探机在送达情报前被拉回，verdict 落在
    「无情报→保守按 rush」（结论碰巧对，但链条是断的；Macro 局探机死/卡
    同样会假 rush）。本判据区分「侦查还没走到」和「侦查已尽力未送达」：

    - "pending"：还没到评估窗（now < verdict_at）；
    - "evaluate"：有敌基情报 → 按 scout_verdict 正常评；
    - "wait"：无情报但侦查农民还在路上（慢/绕路）→ 等它，不超 hard_deadline；
    - "redispatch"：无情报 + 侦查农民死/被提前撤回 + 没补派过 + 非 rush
      → 补派一次（仅一次，保 O9 防无限续命送死语义；rush 中不补派——
      走进狗群是白送，且 rush 响应包已在跑，verdict 无关痛痒）；
    - "fallback"：到 hard_deadline 仍无情报 / rush 中无法补派 →
      侦查已尽力未送达，保守按 rush（= 旧「无情报→unknown」行为）。
    """
    if now < verdict_at:
        return "pending"
    if intel:
        return "evaluate"
    if scout_en_route and now < hard_deadline:
        return "wait"
    if not redispatched and not rush_active and now < hard_deadline:
        return "redispatch"
    return "fallback"


def rally_min_for_verdict(
    base_min: int, verdict: str | None, rush_floor: int = 6
) -> int:
    """E8/O17/O18：侦查结论驱动 C3a 集结阈值。纯逻辑，可单测。

    - greedy（敌贪，前期兵力薄）→ 减半：小股提早压前线，不等集结数（O17）；
      base 0（集结关，如 carrier）保持 0；
    - rush → 收紧到 max(base×2, rush_floor)：集结积攒再打，叉不零散出门（O18）；
      base 0 的流派也至少有 rush_floor 的纪律（rush_floor 取 carrier pre_fleet
      保底叉 cap 6 同源量级）；
    - unknown / None（未评估/非 carrier 流）→ 维持 base_min（保守）。
    司令 stance 让位原则在调用方（combat_manager），不进本判据。
    """
    if verdict == "greedy":
        return base_min // 2
    if verdict == "rush":
        return max(base_min * 2, rush_floor)
    return base_min


def carrier_rally_against_aa(
    flow_name: str, carrier_count: int, enemy_aa_count: int, gate: int = 3
) -> bool:
    """O23:航母流且敌有对空威胁时,舰队数 < gate → 守家攒兵(不送)。
    carrier 主 C 是高价值慢产兵(250气/64s),1-2 艘撞雷神/维京/导弹塔/寡妇雷=送;
    gate=3 让它攒齐再出门。flow_name != 'carrier' 恒 False(基线零变化);
    enemy_aa_count<=0(没防空)恒 False(没威胁不必守)。纯逻辑,可单测。
    司令 stance 让位在调用方(combat_manager)。
    O66:carrier_count 实参按航母+暴风合计传(暴风主 C 配比下只数航母会
    在 1-2 航母时永久锁死集结 —— o65 game_01 实证)。"""
    if flow_name != "carrier" or enemy_aa_count <= 0:
        return False
    return carrier_count < gate


def dispatch_viable(
    minerals: float,
    income_per_sec: float,
    walk_time: float,
    cost: float,
    buffer: float = 0.0,
) -> bool:
    """派建造工人前的可负担估算（O19 钉点修复）。纯逻辑，可单测。

    到位时钱够才派：当前矿 + 走位时间 × 收入速率 ≥ 造价 + buffer → 派（到位即开工，
    零钉点）；不够 → 不派（建筑等下帧重估，农民继续采矿——缺钱时正确行为
    是**不派**，不是派了再撤，E4c 撤回循环前科）。

    背景：ares BuildStructure / ExpansionController(prioritize) 不查 can_afford
    就派工，农民钉在建造点等钱（e7e8 bench idle_builder 实证：
    PHOTONCANNON 9-21 次/局、NEXUS 2-7 次/局）。

    O181:增加 buffer 参数，用于 F2/Nexus 等关键注册点，留出 small cushion，
    避免「估算刚好够 → 下帧被 warp-in/其他开销抽干 → 农民钉点」的残余 idle_builder。
    """
    return minerals + income_per_sec * walk_time >= cost + buffer


def redispatch_cooled_down(
    last_release: float | None, now: float, cooldown: float = 15.0
) -> bool:
    """O19 防重派循环：O11 撤回某结构的建造工人后，cooldown 秒内不再重派同类。
    纯逻辑，可单测。

    背景（o19fix bench 实证）：矿紧期「派工 → 钉点 6s → O11 撤回 → 下帧
    dispatch_viable 守卫又过（收入高时恒真）→ 再派」循环，同一农民反复进
    idle_builder episode（macro g05 同一 tag 6 次）。撤回本身说明钱真不够，
    冷却让经济先攒起来再派。rush 期 O11 豁免不撤回 → 天然无冷却（E4c 安全）。
    """
    if last_release is None:
        return True
    return now - last_release >= cooldown


def _pylon_redispatch_ok(
    now: float,
    supply_left: float,
    last_release: float | None,
    cooldown: float = 10.0,
    can_afford: bool = False,
) -> bool:
    """O192-①/O195: AutoSupply 注册前的 PYLON 重派闸门。

    开局前 60s 经济窗口极紧,PYLON 农民被 O11 撤回后若立即重派,
    同一农民会反复钉点空转(实测 o191/o194 开局 PYLON 农民空转 30s+)。
    因此 60s 内强制 2s 冷却,让农民先采矿;60s 后只有真的买不起且
    supply_left>0 时才继续冷却,避免同一农民被反复派去等钱。
    买得起时直接放行(不卡人口)。
    """
    if can_afford:
        return True
    if now < 60.0:
        return redispatch_cooled_down(last_release, now, cooldown=2.0)
    # O195:买不起且还有 1-2 人口余量时,没必要每帧重派农民去钉点,
    # 等钱够了(上分支 can_afford)或 supply_left==0 才派。
    if supply_left > 0:
        return False
    return redispatch_cooled_down(last_release, now, cooldown=cooldown)


def cannon_target_capped(
    dynamic_count: int,
    min_count: int,
    minerals: float,
    fleet_mineral_cost: float = 350.0,
    rush_active: bool = False,
    vespene: float = 0.0,
    fleet_total: int = 999,
    fleet_min: int = 5,
    gas_threshold: float = 600.0,
    mineral_threshold: float = 500.0,
    mineral_floor: float = 250.0,
    bases: int = 99,
) -> int:
    """Macro 局塔重建限流（诊断 #2：塔矿出血）。纯逻辑，可单测。

    憋舰队期（矿存款 < 舰队矿价 且非 rush）塔目标压回 min——被打掉的塔
    不立即按动态数重建，矿让给航母/农民（o19b-macro 实证：g03 同时 16 座塔
    ≈2400 矿 ≈ 7 艘航母，气 2200+ 烂掉而矿贴 0）。矿 ≥ 舰队矿价（憋得起）
    或 rush 期（保命优先，六连动不变）→ 按原动态数。
    O157/O159/O160 追加：
    1. 气体富余（vespene≥600）且 minerals<500 且舰队未成规模
       (<5) 时，即使矿 ≥350 也按 min 限流，避免 16 塔吃掉本可造舰队的矿。
    2. O160(o159-vh-zerg-power game_01 918s): 矿物跌破 mineral_floor(250)
       时直接按 min 限流，不管舰队规模——塔再抽矿会让舰队/农民/科技全面停产。
    3. 基地已被压缩到 ≤2 个时不再限流——丢基地后矿物收入本就骤降，此时
       再憋舰队等于放弃最后阵地；优先把塔/电池补满保住现有经济。
    """
    if rush_active:
        return dynamic_count
    # O157-② / O161: 基地压缩时若舰队已成规模(≥3)才不限流;
    # 舰队未成规模时二矿盲目堆塔会吃掉舰队科技/产能的矿，继续限流保经济。
    if bases <= 2 and fleet_total >= 3:
        return dynamic_count
    # O160: 矿物极低时硬地板限流，防止塔把舰队矿抽干。
    if minerals < mineral_floor:
        return min(dynamic_count, min_count)
    # O157-①/O160: 气体富余但矿物紧缺、舰队未成规模 → 塔只补 min。
    if (
        vespene >= gas_threshold
        and minerals < mineral_threshold
        and fleet_total < fleet_min
    ):
        return min(dynamic_count, min_count)
    if minerals >= fleet_mineral_cost:
        return dynamic_count
    return min(dynamic_count, min_count)


def threat_response_active(
    visible_enemy_army_supply: float,
    own_army_supply: float,
    currently_active: bool = False,
) -> bool:
    """E9 中局威胁响应（Macro 局敌大部队压境）。纯逻辑，可单测。

    背景（macro-fix1 五局实证）：威胁响应原来只覆盖早期 rush（rush_active /
    scout verdict），Macro AI 的中局一波（t≈520-560 敌 15-25 作战单位到脸）
     bot 毫无反应——继续开矿、继续憋航母（save_up）、塔还被限流压着，常备军
    ≈6 叉对敌 20+，基地连丢。

    滞回判据（防边界抖动反复横跳）：
    - 未激活 → 敌可见作战 supply ≥ max(10, 我方 army supply × 1.5) 激活；
    - 已激活 → 敌可见 supply < max(6, 我方 × 1.0) 才解除。
    """
    if currently_active:
        return visible_enemy_army_supply >= max(6.0, own_army_supply * 1.0)
    return visible_enemy_army_supply >= max(10.0, own_army_supply * 1.5)


def threat_ground_exemption(spawn: dict, flying: set) -> set:
    """E9：threat 激活时 spawn 配方里的地面（防御）兵种集合。纯逻辑，可单测。

    进 save_up_spawn 的 exempt——敌大部队压境时还憋舰队截地面就是裸奔
    （E4b「敌可见 0=未知不是优势」同类教训）。航母/风暴等空军不在此集，
    截断逻辑对它们照旧。
    """
    return {uid for uid in spawn if uid not in flying}


def pivot_primary_id(verdict: str | None, carrier_id, tempest_id):
    """策略 pivot：舰队成型前的主 C 选择（只挂 carrier 流，侦查驱动）。纯逻辑。

    司令硬性约束：判定依据**只能是侦查结论**（E7 scout verdict），不许读
    --ai-build 或任何对局配置。
    - verdict == "greedy"（侦查判非 rush：Macro/扩张/攀科技）→ 风暴主 C
      压制（9c2f89d 认证赢法：单矿风暴速胜，赢局 200-500s，TEMPEST×12）；
    - rush / unknown / None（未判定）→ 航母主 C（保守默认=现状：
      未判定期间绝不按 Macro 打，防被 rush 一波穿）。
    """
    return tempest_id if verdict == "greedy" else carrier_id


def tempest_primary_spawn(spawn: dict, carrier_id, tempest_id) -> dict:
    """把 spawn 配方的主次 C 对调：航母 p0/风暴 p1 → 风暴 p0/航母 p1。纯逻辑。

    只换 priority（主 C 位），proportion 保留；save_up 机制不动——风暴 p0
    便宜（150/100）几乎不触发截断，航母 p1 在转型前自然被憋住（省钱给风暴海）。
    缺任一兵种 → 原样返回。
    """
    out = dict(spawn)
    if carrier_id not in out or tempest_id not in out:
        return out
    carrier_pri = out[carrier_id]["priority"]
    out[carrier_id] = {**out[carrier_id], "priority": out[tempest_id]["priority"]}
    out[tempest_id] = {**out[tempest_id], "priority": carrier_pri}
    return out


def carrier_quota_active(
    flow_name: str,
    fleet_online: bool,
    tempest_count: int,
    carrier_count: int,
    fleet_min: int = 8,
    carrier_target: int = 4,
    pending_tempest: int = 0,
    pending_carrier: int = 0,
) -> bool:
    """O155/O156: carrier 流舰队成型后强制补航母配额。纯逻辑，可单测。

    当前 carrier 配方为 TEMPEST p0 / CARRIER p1 + save_up=0，freeflow 下
    TEMPEST 便宜且永远可负担，CARRIER 被永久截断、整局不出（O154 终局
    编成 28 暴风 0 航母实证）。本函数在舰队成型后检测是否该强制补航母：
    - flow 必须是 carrier；
    - fleet_online（至少有一艘舰队主 C 出生/在产，保证气矿经济已运转）；
    - 舰队总数（暴风+航母+在产）已达 fleet_min（默认 8，O156 从 12 下调——
      VeryHard Zerg Power 局舰队常在 11 艘时就被压崩，永远到不了 12）；
    - 航母数量 < carrier_target（默认 4）。
    O156 追加安全网：舰队 6+ 且 0 航母、同时离阈值还差至少 2 艘时，必须
    先把第一艘航母挤出来，避免“暴风憋到 11 艘被推平、航母从未出场”。
    触发后由调用方把 spawn 主次对调并开动态 save_up，逼出航母。
    """
    if flow_name != "carrier" or not fleet_online:
        return False
    if carrier_count >= carrier_target:
        return False
    fleet_total = tempest_count + carrier_count + pending_tempest + pending_carrier
    if fleet_total >= fleet_min:
        return True
    # O156 fallback：6+ 暴风且 still 0 航母（含在产），同时离 fleet_min 只差
    # 2 艘以内时，必须先把第一艘航母挤出来，避免“差一点到阈值被推平”。
    return (
        carrier_count == 0
        and pending_carrier == 0
        and (tempest_count + pending_tempest) >= 6
        and fleet_total >= fleet_min - 2
    )


def carrier_quota_spawn(spawn: dict, carrier_id, tempest_id) -> dict:
    """O155: 把 spawn 配方主次对调成 CARRIER p0 / TEMPEST p1。纯逻辑，可单测。

    与 tempest_primary_spawn 互逆：配额窗口内让航母吃气、暴风 fall-through
    补位；save_up 由调用方动态开启。
    """
    out = dict(spawn)
    if carrier_id not in out or tempest_id not in out:
        return out
    carrier_pri = out[carrier_id]["priority"]
    out[carrier_id] = {**out[carrier_id], "priority": out[tempest_id]["priority"]}
    out[tempest_id] = {**out[tempest_id], "priority": carrier_pri}
    return out


def carrier_transition_ready(
    now: float,
    tempest_count: int,
    at_time: float = 600.0,
    tempest_cap: int = 10,
) -> bool:
    """风暴压制 → 航母终结的转型时点。纯逻辑，可单测。

    简单可工作判据（阈值走参数，不硬编码死）：进入中后期（时间到 at_time）
    **或**风暴压制阵容已成型（数量到 tempest_cap）→ 转航母主 C。
    压得住时局已在 200-500s 内结束（认证赢法），到点压不住就补航母终结。
    """
    return now >= at_time or tempest_count >= tempest_cap


def is_combat_type(type_id) -> bool:
    """P1 作战单位口径：排除工人与侦查/运输单位，QUEEN 保留。纯逻辑，可单测。

    背景（E10 bench 诊断）：rush/verdict 的「早期多兵」判据原来是
    「非工人即算兵」，把 OVERLORD/OVERSEER（侦查/运输）也算进作战单位——
    Zerg Macro 常规运营（pool + overlord 铺开）在 ~170s 可见非工人 ≥6 是常态
    （实测 23-25），导致 scout_verdict 对 Zerg 系统性误判 rush、
    early_swarm 每局误触发（macro 组 169s 全误中）。排除
    OVERLORD/OVERSEER/OVERLORDTRANSPORT；QUEEN 能打仗，保留算作战。
    """
    from sc2.ids.unit_typeid import UnitTypeId as UnitID

    return type_id not in {
        UnitID.SCV,
        UnitID.PROBE,
        UnitID.DRONE,
        UnitID.MULE,
        UnitID.OVERLORD,
        UnitID.OVERSEER,
        UnitID.OVERLORDTRANSPORT,
    }


def extra_production_mineral_gate(
    pivot_active: bool,
    fleet_beacon_ready: bool = False,
    first_tempest_seen: bool = False,
    default_gate: float = 400.0,
    vespene: float = 0.0,
    minerals: float = 0.0,
    fleet_total: int = 999,
    fleet_min: int = 8,
    gas_threshold: float = 1500.0,
    mineral_threshold: float = 400.0,
) -> float:
    """P2a：追加产兵建筑的「矿富余」门槛。纯逻辑，可单测。

    E10b 实证：pivot 配比生效但 4/5 局星门只有 1 个——单矿矿贴 0-300，
    「矿>400 才追加」永不触发，风暴海出不来。pivot 模式（风暴主 C）下
    豁免门槛（风暴 150/100，矿紧也要产）；非 pivot 行为零变化。
    E10c 实证：裸豁免让追加星门（300 矿）抢在 FleetBeacon（风暴前置）前面，
    FB 被饿 50-170s → 加 FB 前置。
    E10d 实证：FB 前置还不够——追加星门在「FB 就绪 → 首艘风暴」窗口开建
    （337-385s，300 矿/200 气 + 2×43s 建造周期），首艘 TEMPEST 系统性晚
    50-70s → 再加首艘闸：**pivot 且 FB 就绪/在建 且首艘 TEMPEST 已出/在产**
    才豁免为 0。原则：追加产能永远不抢自己前置科技/首艘主 C 的生产窗。
    O157 追加：vespene 烂银行（≥1500）且 minerals<400、舰队未成规模（<8）时，
    追加产能门槛提高到 600，避免在矿物紧缺期继续花 250–300 矿造 idle 建筑。
    """
    if pivot_active and fleet_beacon_ready and first_tempest_seen:
        return 0.0
    if (
        vespene >= gas_threshold
        and minerals < mineral_threshold
        and fleet_total < fleet_min
    ):
        return max(default_gate, 600.0)
    return default_gate


def stargate_gas_gate_bonus(pivot_active: bool) -> int:
    """P2b：星门气体闸门的富余数（gas_gated_stargate_target 的 +N）。纯逻辑。

    常规 +1（单矿满采 2 气 → 2 星门）；pivot 模式 +2（单矿 → 3 星门——
    留数据空间，不一步到 4）。非 pivot 行为零变化。
    """
    return 2 if pivot_active else 1


def carrier_sg_bonus(has_transition: bool) -> int:
    """O152-③(o151 尸检):carrier 流 SG 气体闸额外富余。纯逻辑,可单测。

    胜局(局3/4)= 暴风 27-29 艘/SG 3-9;败局 SG 恒 1-3、暴风峰值 3-7 ——
    舰队爬坡慢是分水岭。carrier(transition 流)bonus +1(双矿四气 →
    SG 目标 3→4);非 transition 基线流(tempest/stalker)0,逐位不变。
    """
    return 1 if has_transition else 0


def chrono_primary_id(pivot_active: bool, default_primary, tempest_id):
    """P2c：chrono 的主力兵种判定。纯逻辑，可单测。

    E10 已知边界：chrono `when=primary_pending` 的主 C 判定读 flows.yml 的
    CARRIER——pivot 风暴阶段星门整段无 chrono（≈20% 产能损失，E10b 实锤
    星门峰值 1-2）。pivot 模式认 TEMPEST；非 pivot 行为零变化。
    """
    return tempest_id if pivot_active else default_primary


def oracle_before_fleet_allowed(
    pivot_active: bool, first_tempest_seen: bool, fleet_transitioned: bool = False
) -> bool:
    """A2：ORACLE one_off 是否允许现在造。纯逻辑，可单测。

    E10d 实证：先知（150/150）在「FB 就绪 → 首艘风暴」窗口插队星门生产，
    是首艘 TEMPEST 系统性晚 50-70s 的另一半原因（另一半是追加星门抢窗，
    已由 extra_production_mineral_gate 的首艘闸管）。pivot 模式下推迟到
    首艘 TEMPEST 已出/在产之后；非 pivot 行为零变化。
    O96（o95 局3/局4 实证）：转舰队后（fleet_transitioned）同一闸门 ——
    局4 先知 t≈618 在舰队零产出时抢走 150/150，首暴风拖到 t=791。
    fleet_transitioned 缺省 False → 旧调用签名行为逐位不变。
    """
    if pivot_active or fleet_transitioned:
        return first_tempest_seen
    return True


def expansion_blocked(
    rush_active: bool,
    threat_active: bool,
    pivot_active: bool,
    enemy_near_home: bool,
    bases: int = 99,
) -> bool:
    """B1：开矿阻断判据（E9 停开矿的 Macro 适配）。纯逻辑，可单测。

    - rush_active → 永远停开（六连动不变，最高优先）；
    - O29 首扩放行:bases<=1(1→2 矿)→ 不停(carrier 该早开 2 矿,配合 O30 first_expand_at;
      被拆也比单矿经济崩强 —— 验局 carrier vs Zerg 单矿锁死 t=767 的根因);
    - O29 扩散 pivot 修复:pivot/非 pivot 统一走 enemy_near_home(敌压家 40 格≥2 才停),
      不再裸 threat_active(threat 在 Macro 局常驻曾锁死非 pivot carrier 单矿)。
    threat_active 参数保留兼容签名但不再单独使用;E9 塔拉满/地面混编不受影响。
    """
    if rush_active:
        return True
    if bases <= 1:
        return False
    return enemy_near_home


def floor_exits(
    primary_count: int, ground_combat_count: int, ground_min: int = 4
) -> bool:
    """C1：pre_fleet floor（地面保底）退出判据。纯逻辑，可单测。

    现状「主 C>0 即退出」的实证问题（E10d）：叉子一波战死后 floor 已退，
    地面零补员（trickle 根因）。改为**主 C 上线 且 地面作战单位 ≥ ground_min**
    才退出——地面被打穿（<ground_min）即便舰队在线也继续补叉。
    选这个方案（而非「主 C≥2 才退出」）的理由：它自校正——地面够才退、
    被打穿就回补，无状态无横跳；「主 C≥2」只是把退出点推后，第二艘上线后
    同样会断层。
    """
    return primary_count > 0 and ground_combat_count >= ground_min


def scout_next_step(route: list, arrived: bool, intel_found: bool) -> str:
    """O36(司令观察,4人图 CactusValley 实证):多出生点侦查的逐点排查决策。纯逻辑,可单测。

    4人图 1v1 敌人只占 3 个候选出生点之一,探机只摸最近一个点≈赌运气:
    摸到空点不算完,应逐个排查,情报到手或全部摸完才回家。

    route: 待排查出生点(近→远),调用方持有并弹出,本函数只决策不修改。
    arrived: 探机是否已到 route[0](调用方按距离判定)。
    intel_found: 是否已看到敌建筑(敌人定位=情报送达)。
    返回:
      "home" → 情报到手 / 全部摸完 / 无点可摸,回家
      "next" → 当前点是空的,弹出并前往 route[1]
      "stay" → 还在路上,继续朝 route[0] 走
    """
    if not route or intel_found:
        return "home"
    if arrived:
        return "home" if len(route) == 1 else "next"
    return "stay"


def hot_base_index(threats: list[int], min_threat: int = 6) -> int | None:
    """O63(o62-vh-zerg-power game_01 实证):哪个基地正被围攻 —— 中局动态防守锚点。
    纯逻辑,可单测。

    Power 的压迫是持续小队(10-18 地面)轮抄各分矿:静态锚点(塔最少的基地)蹲错
    位置,12 暴风全程看戏,4 基地被逐个蚕食(bases 4→3→4→2→…→1)。威胁计数
    ≥ min_threat 的最高压基地 → 舰队回防(暴风对地面小队是降维打击,回防即止血);
    无热点 → None(回退 O37 静态锚点)。计数并列时靠前的基地优先(调用方按距主基
    排序,> 不取 =)。阈值 6:2-4 个的挠痒级骚扰不值得拉动整支舰队。
    """
    best: int | None = None
    best_n = 0
    for i, n in enumerate(threats):
        if n > best_n:
            best, best_n = i, n
    if best is None or best_n < min_threat:
        return None
    return best


# ────────────── O136 坡口墙(vs Zerg 速骰:波 154-160,叉/塔竞速到极限后的真人标准解) ──────────────


def pick_wall_positions(
    wall_buildings,
    anchor: tuple[float, float],
    n: int = 2,
) -> list[tuple[float, float]]:
    """O136-①:坡口墙 3x3 建筑位排序选取。纯逻辑,可单测。

    burnysc2 的 ramp.protoss_wall_buildings 是 frozenset(序不定)——
    按离 anchor(主基)距离排序取前 n,GW/forge 落位逐局一致(尸检可复现)。
    None/空/不足 n → 有多少返多少(调用方 len<2 判无墙位,回退原防链)。
    """
    if not wall_buildings:
        return []
    pts = [(float(p[0]), float(p[1])) for p in wall_buildings]
    pts.sort(key=lambda p: (p[0] - anchor[0]) ** 2 + (p[1] - anchor[1]) ** 2)
    return pts[:n]


def wall_hold_point(
    gap: tuple[float, float],
    base: tuple[float, float],
    back: float = 1.5,
) -> tuple[float, float]:
    """O136-②:叉子墙后站位 = 墙缝点向基地内侧回退 back 格。纯逻辑,可单测。

    封口后叉子蹲缝内侧(堵漏/打钻进缝的狗),不主动出击不出去追
    (combat 的 rush 守家锚点改写);back=1.5 保持物理封缝。
    """
    dx, dy = base[0] - gap[0], base[1] - gap[1]
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return (float(gap[0]), float(gap[1]))
    return (gap[0] + dx / d * back, gap[1] + dy / d * back)


def wall_escort_needed(wall_mode: bool, wall_sealed: bool, enemy_near: int) -> bool:
    """O136-③:墙未封死前农民肉身堵缝判据。纯逻辑,可单测。

    墙模式 + 未封口 + 敌地面近家 ≥2 → 协防农民去墙缝填缝(墙建筑完工前
    的空窗 = 速骰局的死刑窗);封口/敌退 → 翻假归队(O130 留 6 采矿
    语义在调用方 escort_pull_cap 保留)。
    """
    return wall_mode and not wall_sealed and enemy_near >= 2


def wall_fallback_due(
    fail_since: float | None, now: float, patience: float = 30.0
) -> bool:
    """O137-①(o136b 0-5 大回退实证):墙派工失败超 patience 秒 → 回落普通槽。
    纯逻辑,可单测。

    墙是增益不是前提 —— 落位失败/无工人/钱不够时墙链每帧 return 会把
    原防链(forge→首塔→GW)挡死(o136b 局1:慢骰都 0 防具死 223)。
    patience 30s > 墙位水晶建造窗(~20-25s,等电的 no_placement 是正常
    等待,不算失败);远小于 o136b 的 90s+ 驻车事故。
    """
    return fail_since is not None and now - fail_since > patience


def wall_disabled_after(strikes: int, max_strikes: int = 2) -> bool:
    """O137-②:墙派工失败 max_strikes 次 → 本局墙逻辑整体关闭(latch)。
    纯逻辑,可单测。墙不能比命重要 —— 关闭后防链回退 o135 行为。"""
    return strikes >= max_strikes


def defense_anchor_index(cannons_per_base: list[int], min_main_cannons: int = 2) -> int:
    """O37(司令观察):防守锚点 = 防守兵力蹲哪个基地。纯逻辑,可单测。

    开二矿后地面防守兵(保底叉子等)不该全堆主基:主基塔够(≥min_main_cannons)
    → 蹲塔最少的分矿(最暴露,通常是新开的);主基塔不够/单基地 → 主基(先保本,
    行为同旧版)。cannons_per_base[0] 必须是主基(调用方按距 start_location 排序)。
    """
    if len(cannons_per_base) <= 1 or cannons_per_base[0] < min_main_cannons:
        return 0
    return min(range(1, len(cannons_per_base)), key=lambda i: cannons_per_base[i])


def base_defense_anchor(
    is_main: bool,
    base_xy: tuple[float, float],
    enemy_xy: tuple[float, float],
    main_rally_xy: tuple[float, float] | None = None,
    forward: float = 6.0,
) -> tuple[float, float] | None:
    """O38(司令观察·建筑学):某基地塔/电池的落位锚点。纯逻辑,可单测。

    主基 → main_rally_xy(ramp 口,O31;None=不 override,走 ares 默认);
    分矿 → 基地朝敌方向 forward 格 —— 塔落在正面迎敌一侧(敌来犯路径与矿区之间),
    不再矿区背后扎堆;电池同锚点 → 自然贴着塔(射程 6 内)。
    敌未定位时 enemy_xy 传最近候选出生点(方向猜测,总好过默认的基地中心)。
    基地与敌重合(退化)→ None。
    """
    if is_main:
        return main_rally_xy
    dx, dy = enemy_xy[0] - base_xy[0], enemy_xy[1] - base_xy[1]
    d = math.hypot(dx, dy)
    if d < 1e-6:
        return None
    return (base_xy[0] + dx / d * forward, base_xy[1] + dy / d * forward)


def rush_hold_batteries(rush_active: bool, hold_active: bool) -> int:
    """O73:防御电池目标。接触式 rush(早期,CYBERNETICSCORE 未就)让位=0;
    O71 持有期(t=330+,cyber 早成)双电池互充奶塔=2;非 rush 常态=2。
    """
    return 0 if (rush_active and not hold_active) else 2


# O133-①(o132-vh-zerg-timing 1-4 尸检):二次侦查窗口提前 —— VeryHard
# Timing 波 273-289 到脸、~200-250 蟑螂/刺蛇成型;250 派出/330 截止
# 看到兵时波已出门,全废。195 派出/260 截止 = 波出门前读真实开局。
RESCOUT_DISPATCH_AT: float = 195.0
RESCOUT_HARD_DEADLINE: float = 260.0


def rescout_verdict(
    has_expo: bool, military_structs: int, combat_units: int
) -> str:
    """O71(二次侦查,t≈280-330):rush 复核判定。纯逻辑,可单测。

    首判(t≈170,O9)时点 rush 兵营还没成型(3BB/3BG 要 t=210-240 才完工,
    看到的只是 1-2 个兵营,只能判 greedy)——Terran Rush 两局实败(3→2→1→0
    连锁、t=845 早夭)的根因就是首判后 6 分钟零情报,敌兵到脸上才确认。
    二次侦查在敌兵出门前读真实开局:

    - has_expo(对面已开二矿) → "greedy"(运营开局,放心贪);
    - 单基地且兵营类 ≥3 → "rush"(产能 all-in,兵没入镜也算 —— o71 局实证:
      t=330 敌 4 兵营 0 开矿,枪兵在基地视野外/已出门,兵=0 漏判 unknown);
    - 单基地且兵营类 ≥2 且作战单位 ≥6 → "rush"(3BB 枪兵/3BG 叉追猎暴兵);
    - 单基地兵营 1 个但作战单位 ≥10 → "rush"(Zerg 单矿狗池爆狗,兵营类只有 pool);
    - 其余(单基地科技开局/慢打) → "unknown"(维持现状,不动响应包)。
    """
    if has_expo:
        return "greedy"
    if military_structs >= 3:
        return "rush"
    if military_structs >= 2 and combat_units >= 6:
        return "rush"
    if combat_units >= 10:
        return "rush"
    return "unknown"


def full_pop_all_in(
    supply_used: float,
    supply_cap: float,
    minerals: float,
    min_frac: float = 0.95,
    min_bank: float = 1500.0,
) -> bool:
    """O70(司令观察):接近满人口+存款充足 → 全力进攻,不再等 supply 优势。
    纯逻辑,可单测。

    t≈1740 实证:199/200 + 5000+ 存款时,推进闸仍因「敌可见 supply ≥ 我方」
    蹲守(max-vs-max 僵局)——满人口意味着攒不出更多兵,蹲是纯亏;
    5000+ 存款+多矿经济意味着换血永远我方赚(对面死一个少一个)。
    此时应把经济优势转化为战场优势,积极求战。
    注意:本判据只放开 supply 优势检查,硬对空安全线(carrier_push_safe)
    不动——舰队是产能瓶颈(20 艘暴风重建 ~10 分钟),存款买不回时间。
    """
    if supply_cap <= 0:
        return False
    return supply_used >= supply_cap * min_frac and minerals >= min_bank


def tech_yields_to_threat(threat_active: bool, rush_active: bool) -> bool:
    """O67(VeryHard Terran Rush game_01 实证):E9 威胁激活时,追加产能/舰队航标
    让位塔链。纯逻辑,可单测。

    rush 期科技链本已全停(调用方 rush 分支,不进这里);本判据只管 E9 threat:
    敌压境(t=471)到 rush 确认(t=505)的窗口里,3 星门+舰队航标(~600 矿)
    抢光塔钱 —— 塔链「等钱造PHOTONCANNON」干等,0 塔基地被 5 枪兵推平,
    3→2→1 连锁崩。威胁期这些钱必须先变成塔/电池,科技解除后再补。
    """
    return threat_active and not rush_active


def fleet_gas_starved(
    vespene: float,
    fb_present_or_pending: bool,
    stargates: int,
    fb_in_core: bool,
    min_vespene: float = 600.0,
) -> bool:
    """O83(n5m-zerg-rush game_03 实证):舰队管线被冻结门饿死 = 舰队航标豁免信号。
    纯逻辑,可单测。

    背景:Zerg Rush 的慢性威胁/持续抄家让 rush 分支(科技链全停)与 E9 让位
    (tech_yields_to_threat)把 FLEETBEACON 永久冻结 —— 3 就绪星门 250s 零产出、
    气银行烂到 2500+(流派出兵全是耗气的暴风/航母,无 FB 则气无处可去),
    腐化/飞龙波到达时零舰队败亡。O67 的让位是给 ~34s 急性窗设计的,慢性威胁下
    防御早已饱和(7 塔 5 电池),让位的钱没有去处,唯一翻盘点是舰队成型。
    判据:气银行 ≥600(其它开销不吃气 = 管线明确停转)+ 无 FB + 有星门
    + 流派科技链本就要 FB —— 四条件同时成立时 FB 豁免一切冻结。
    stargates 口径由调用方定(O86 实证):救 FB 传**就绪**数(FB 需要就绪星门);
    拦追加产能传**已有+在建**数 —— 星门群会在首座就绪前就一起排进队,
    只数就绪的拦不住(n5m-terran-power game_04:t=425 零星门,t=502 三座)。
    """
    return (
        fb_in_core
        and not fb_present_or_pending
        and stargates > 0
        and vespene >= min_vespene
    )


def rush_spawn_fleet_escape(
    vespene: float,
    ready_stargates: int,
    fb_present_or_pending: bool,
    min_vespene: float = 400.0,
) -> bool:
    """O89(n5m-terran-air game_05 实证):rush 纯叉配方的舰队逃生门。纯逻辑,可单测。

    背景:E3d rush 响应「叉子没顶够数就全力补叉」(_effective_spawn 返回纯
    ZEALOT 配方)是给急性 rush 窗(几十秒)设计的;慢性接触下叉子即出即死、
    永远填不满 cap → 纯叉配方永久生效,星门全程闲置、气烂 2000+
    (game_05:4 星门+FB 就绪、气 2344、124s+ 零舰队败亡)。舰队基建齐备
    (就绪星门+FB)且气银行 ≥800 时逃生门打开:调用方改混编(叉子续防吃矿,
    舰队吃叉子用不上的气)。急性 rush 早期 SG/FB 未齐,门不开,急性语义不变。
    # O199(o198-vh-zerg-rush game_01 实证):800 气阈值太高,FB 就绪后还要攒很久
    # 才开混编;降到 400 让舰队更早进入 spawn,避免星门空转。
    """
    return (
        ready_stargates > 0
        and fb_present_or_pending
        and vespene >= min_vespene
    )


# ────────────────────── O92 过渡形态(快攻四墙 build order 级修复) ──────────────────────


def transition_should_enter(
    verdict: str | None,
    rush_confirmed: bool,
    fleet_transitioned: bool = False,
    rush_confirmed_at: float | None = None,
    contact_limit: float = 360.0,
) -> bool:
    """O92/O150:过渡形态进入判据(一次性 latch 的触发端)。纯逻辑,可单测。

    verdict == "rush"(O9 首判情报确认) 或 rush 已被证实(接触式检测/O71 二次
    侦查确认,rush_confirmed latch) → True。unknown(侦查尽力未送达)不进入 ——
    unknown 的保守处理仍是 60s rush 响应包(照跑不误),而过渡形态是冻星门到
    fleet_at 的大承诺,没确认的保守档不该押上去。greedy/unknown 且从未接触
    → False(Macro/Air 优势对阵现状完全不变)。
    O150-①(o149-zerg-power 实证):单程化 —— 转过舰队(fleet_transitioned)
    后永不重进(管理器早退之外加判据层硬关断)。
    O150-②:接触确认的 rush 只认早期(confirmed_at ≤ contact_limit)——
    o149-zerg-power 五局:verdict=greedy 的局 500s 推进波(正常 mid-game
    push)触发接触检测 → rush_confirmed → 进过渡冻舰队链 = 自残。
    verdict=rush 的情报确认不受时点限(情报本身是早期产物)。
    rush_confirmed_at 缺省 None → 视为 0(旧签名行为不变)。
    O154-①(o153-zerg-power 局1 实锤):greedy 一票否决接触进过渡 ——
    237 的小股接触(在 360 时限内)照样把 Power 局烧进过渡;greedy
    判错的兜底是 E9 威胁包(塔+守家,不动科技链),不是冻舰队。
    只有 rescout/新情报把 verdict 改判 rush 才进。
    """
    if fleet_transitioned:
        return False
    if verdict == "rush":
        return True
    if verdict == "greedy":
        return False
    if rush_confirmed:
        return (rush_confirmed_at or 0.0) <= contact_limit
    return False


def rush_contact_arms(verdict: str | None) -> bool:
    """O154-②:接触检测是否允许置 rush latch。纯逻辑,可单测。

    verdict=greedy(侦查确认运营)后,接触一律不置 rush_active/
    rush_confirmed —— o153 局1:greedy 局 rush=True 在 248-278 闪烁,
    农民/科技被接触语义反复掐;小股骚扰由 E9 威胁响应包处理。
    greedy 判错(真 rush)的兜底同样是威胁包,不是 rush latch。
    """
    return verdict != "greedy"


def cancel_presumed_forge(verdict: str | None, now: float, at: float = 110.0) -> bool:
    """O150-③(o149 zerg-power 实证):greedy 早判退保判据。纯逻辑,可单测。

    vs Zerg Power/Macro 局 presumed(55s 无条件启动)的 forge+塔 ≈250 矿
    是纯开销;verdict=greedy(侦查确认运营)且 t≤at → 调用方取消在建
    forge(退 75%),不再拍塔(presumed 在 verdict 落地时已自动关)。
     verdict 晚到(>at) → forge 已完工,不折腾。
    """
    return verdict == "greedy" and now <= at


# O92 过渡形态冻结的科技建筑:星门/舰队航标让位地面产能。
# CYBERNETICSCORE 不在此列 —— 追猎要它(与 RUSH_CANCELLABLE_TECH 同风格白/黑名单)。
TRANSITION_FROZEN_STRUCTS: frozenset = frozenset({"STARGATE", "FLEETBEACON"})


def transition_tech_frozen(transition_active: bool, type_name: str) -> bool:
    """O92:过渡形态期科技链冻结判据。纯逻辑,可单测。

    STARGATE/FLEETBEACON 冻结(地面配方不吃舰队科技,450 矿先变兵营/叉/追猎);
    CYBERNETICSCORE 保留(追猎前置)。未激活 → 全不冻(基线零变化)。
    """
    return transition_active and type_name in TRANSITION_FROZEN_STRUCTS


def fleet_transition_ready(
    now: float,
    fleet_at: float,
    enemy_near_home: int,
    clear_since: float | None,
    clear_for: float = 30.0,
) -> bool:
    """O92:过渡形态 → 转舰队判据(latch,不回头)。纯逻辑,可单测。

    到点(now >= fleet_at) 且 家(start_location 40 格,调用方口径)无敌作战
    单位已持续 clear_for 秒 → True。fleet_at 到了但威胁未清 → False(保持
    过渡形态直到清,防"转舰队瞬间被波次打死");clear_since=None(威胁刚清,
    计时未起)→ False。enemy_near_home>0 时调用方应已把 clear_since 清零,
    这里仍兜底判一遍。
    """
    if now < fleet_at or enemy_near_home > 0 or clear_since is None:
        return False
    return now - clear_since >= clear_for


# ────────────────────── O93 转舰队死锁修复(o92-vh-zerg-rush 局2/局3 实证) ──────────────────────


def core_tech_allowed(expand_holding: bool, fleet_transitioned: bool) -> bool:
    """O93-B1(o92 局3 实证):开矿持有期是否冻结核心科技链。纯逻辑,可单测。

    O43/O51 原语义:持有期(想开矿/Nexus 在建)核心科技让位 Nexus。O92 转舰队后
    该语义死锁 —— 局3:转舰队 t=819 时 bases==1,first_expand_at 早过 →
    first_due 每帧 True → 持有期每帧 True → core_allowed 恒 False →
    t=819→1000(败亡)星门零建;塔/兵持续吃矿,Nexus 400 永远攒不出,
    持有永不解除。转舰队后舰队科技就是全部翻盘点,不再让位 Nexus。
    未转舰队(tempest/stalker/dt/carrier 未触发 O92) → 原语义逐位不变。
    """
    return not expand_holding or fleet_transitioned


def fleet_expand_holds(
    fleet_transitioned: bool,
    first_fleet_seen: bool,
    defense_score: float = 0.0,
    min_defense: float = 25.0,
) -> bool:
    """O93-B2/O96/O105-①:转舰队后一切开矿是否等舰队。纯逻辑,可单测。

    局2(o92):FB 资金窗(t≈936)的 400 矿被砸进三矿,FB 到死没建 → 初版
    等「FB 实体」。O96(o95 局3/局4):等「首艘 TEMPEST/CARRIER 已出或在产」。
    O105-①(o104 局2):首舰门与 strong-exit 接力把扩张连挡 ~260s
    (420 转舰队 → 首舰 ~680 → 单矿被 723 波磨死)—— 加防御评分豁免:
    评分达标(≥25,与 strong-exit 同口径)即便首舰未出也放行扩张;
    防御没站稳的局维持首舰门(o95 的 Nexus 抢 FB 钱教训不回头)。
    defense_score 缺省 0 → 旧签名行为(拦)逐位不变。
    """
    return (
        fleet_transitioned
        and not first_fleet_seen
        and defense_score < min_defense
    )


def fb_stall_recovery_needed(
    fb_in_core: bool,
    stargates_ready: int,
    fb_present: bool,
    stall_age: float,
    timeout: float = 45.0,
) -> bool:
    """O93-B3:FB 建造停滞自救判据。纯逻辑,可单测。

    FB 在科技链 + 有就绪星门 + 买得起(调用方把 can_afford 编进 stall_age
    计时) 却始终没有 FB 实体(含在建) —— 落位请求静默返回 None(主基拥挤/
    生产区 3x3 槽耗尽,o92 局2 实证:t=936 买得起但 FB 从未出现)或工人
    tracker 泄漏(O13 同构)。停滞超 timeout → 调用方自救:清超龄 FB
    tracker 条目 + 换落位池(production=False)重试 + 发事件。
    """
    return (
        fb_in_core
        and stargates_ready > 0
        and not fb_present
        and stall_age > timeout
    )


# ────────────── O94 首波速败级联修复(o92/o93-vh-zerg-rush 四局实证) ──────────────


def rush_defense_past_holding(rush_confirmed: bool, has_transition: bool) -> bool:
    """O94-A:rush 确认过的局,F2 防御注册是否无视开矿持有期拦截。纯逻辑,可单测。

    o93 局1/局2、o92 局1 实证:rush 确认(t≈130)后,first_expand_at=150 的
    first_due 让 _expand_holding 每帧恒真;rush_active 60s 自动解除(t≈190)
    到首波再接触(t≈195-200)之间,F2 被「holding 且非 threat 且非 rush」
    条款整段拦下 —— 锻造炉恰在 t≈185 就绪,炮塔派工的容错窗被砍光,
    矿 435-540 躺着、0 炮塔败亡。rush 确认(latch)过的局:防御 > 扩张持有期。
    has_transition 门:只挂配了 transition 的流派(carrier),其余流派零变化。
    """
    return rush_confirmed and has_transition


def rush_defers_second_gateway(
    rush_confirmed: bool, has_transition: bool, forge_present: bool,
    gateways_have: int = 1,
) -> bool:
    """O94-B:rush 确认后追加兵营是否让位锻造炉。纯逻辑,可单测。

    速败局实证:F2 注册(t≈130)后 forge 的资金窗被追加兵营(t≈144,150 矿)
    吃掉,forge 拖到 ~152 开工(~185 就绪),炮塔链(forge 33s + 塔 29s)
    物理赶不上首波(t≈195-201)。第二兵营的叉子 t≈215 才出得来,赶不上首波;
    唯一能赶上的是炮塔链。rush 确认且 forge 无实体(含在建) → 缓建追加兵营;
    forge 实体落地(钱已付)后追加恢复。forge_present 用实体口径不用 tracker
    pending —— 钉点等钱的 pending 反而会被兵营抢钱(e4c 教训同族)。
    O102-①(o101 局3/4/5 实证):只拦 GW2/GW3(gateways_have≥1),不拦 GW1 ——
    塔先排序让 GW1 拖到 ~165-181 完工,首叉 195+ 错过首波守窗(155-185);
    GW1 与 forge 并行双开(t≈110 前各 150),首叉 ~140-155 正好进守窗。
    gateways_have 缺省 1 → 旧签名行为逐位不变。
    """
    return (
        rush_confirmed
        and has_transition
        and not forge_present
        and gateways_have >= 1
    )


def rush_cannon_bypass(
    rush_confirmed: bool, has_transition: bool, cannons_ready: int
) -> bool:
    """O94-D:rush 确认后主基炮塔的 static_defence 槽池绕过判据。纯逻辑,可单测。

    o93 局1 实证:F2 注册正常、forge t≈185 就绪、矿 435,炮塔仍零派出 ——
    PSD 的 static_defence 槽(坡口锚点+要电)静默返回 None;O78c 在分矿
    已绕过同类失败(槽位检索静默 None)。rush 确认且主基无就绪炮塔 →
    额外注册通用 2x2 槽(static_defence=False)炮塔实例对冲:槽池大得多,
    有电即可,closest_to 坡口锚点优先。首座就绪后退出绕过,回归 PSD 槽池。
    """
    return rush_confirmed and has_transition and cannons_ready == 0


def rush_worker_escort_needed(
    enemy_ground_near: int,
    cannons_ready: int,
    zealots: int,
    min_enemy: int = 3,
    zealots_enough: int = 4,
    cannons_enough: int = 2,
) -> bool:
    """O94-C/O104-①/O123-③:首波农民协防判据。纯逻辑,可单测。

    敌地面进主基 ≥min_enemy → 拉农民协防。
    O104-①:1 塔不放人(转塔下作战),2 塔/叉够/敌退才归队。
    O123-③(叉海 A/B):叉子接管线 2→4 —— 叉海成型后农民不再参战
    (协防战损是速败局的经济癌症),只在「叉<4 且敌进家」才出手。
    """
    if zealots >= zealots_enough or cannons_ready >= cannons_enough:
        return False
    return enemy_ground_near >= min_enemy


def escort_stance(cannons_ready: int, cannon_pending: bool = False) -> str:
    """O104-①(o103 局1/3/4/5 实证)/O127-③:协防站位决策。纯逻辑,可单测。

    「攻击最近敌」范式证伪:协防农民主动 charge 狗群,赢战斗也输经济
    (局1:13→4;局2/3/4 骤减 4-7)——农民的任务是拖时间等塔/叉,不是换战损。
    - 有就绪塔 → "tower":塔下作战(attack 塔位,敌进塔程才被塔+农民双打);
    - 无就绪塔 → "mineral_walk":穿矿拖延(朝离威胁最远的矿簇 move 往返,
      利用矿碰撞体积甩包围,不接敌;其余农民照采不接管)。
    O127-③:有塔在建(cannon_pending)也按 "tower" 处理 —— 协防回撤守
    建造点,塔的 29s 建造窗是新的死亡窗(o126b 实证:塔工/在建塔被咬)。
    cannon_pending 缺省 False → 旧签名行为不变。
    """
    return "tower" if (cannons_ready > 0 or cannon_pending) else "mineral_walk"


def escort_pull_cap(
    enemy_ground_near: int, workers: int, keep_mining: int = 6,
    base: int = 5, cap: int = 10,
) -> int:
    """O130-③(o129 局3/局4 实证):协防拉人保留采矿底线。纯逻辑,可单测。

    局3/局4:协防按 敌数+2 拉到 8-10 人,采矿归零 → 赢了接触战输了经济
    (农民 14→2-3,之后什么都续不起)。拉人数 = min(威胁需求, 农民-6):
    任何时候留 keep_mining 个农民在矿上。
    """
    return min(
        escort_worker_count(enemy_ground_near, base, cap),
        max(0, workers - keep_mining),
    )


def escort_worker_count(enemy_ground_near: int, base: int = 5, cap: int = 10) -> int:
    """O96(o95 局2/局5 实证):协防农民数随威胁伸缩。纯逻辑,可单测。

    局2/局5:首波 6-8 狗 t≈145 进家,固定 5 农民打不赢(农民 17→11 战损,
    狗只掉 6→5)。下限 base(挠痒级 3-5 狗够顶),敌 ≥6 时按 敌数+2 拉,
    cap 封顶(全拉 = 采矿断气,forge/炮塔反而更慢)。
    """
    return min(cap, max(base, enemy_ground_near + 2))


def transition_expand_blocked(
    transition_active: bool, gateways_have: int, gateway_cap: int
) -> bool:
    """O96(o95 局1 实证):过渡期兵营产能未满 → 不开矿。纯逻辑,可单测。

    局1:过渡期二矿 t≈290(400 矿)+ 12 农民 + 第 4 气把矿吃光,而兵营 #2
    拖到 t≈280 才落地 —— 单兵营 1 叉/28s,t=413 只有 7 叉迎 30-supply 波,
    地面被穿后慢性死亡(气烂 1600 用不掉)。先兵营到 cap(地面产能 =
    过渡形态的命根),再谈开矿。gateways_have 用「已有+在建」口径
    (GATEWAY+WARPGATE+counter,与 _build_extra_production 同源)。
    """
    return transition_active and gateways_have < gateway_cap


# ────────────── O97 早侦查/扩张重启/过渡产能(o96-vh-zerg-rush 0-5 尸检) ──────────────


def early_scout_verdict(
    intel: bool, military_structs: int, early_army: int, enemy_townhalls: int,
    enemy_is_zerg: bool = False,
) -> str:
    """O97(o96 局1/2/4 实证):早期事件驱动评估(探机抵达敌家即评,t≈95-130)
    的开局决策。纯逻辑,可单测。

    背景:首波 155-195 到脸,而 verdict 定时评估(_SCOUT_VERDICT_AT=170)
    到手太晚 —— 局2 探机 t=144.6 已看到 SPAWNINGPOOL,干等 170 纯浪费 25s+,
    防链就绪 ~190-205 vs 首波 155,缺口 30-60s = 三局速败的全部差距。
    判据(保守方向不变:误判 rush 亏经济,误判 greedy 亏比赛):
    - 无情报 → "unknown"(走老路径);
    - 敌已开二矿 → "greedy"(运营开局,t≈100 前二矿落地=贪的直接证据);
    - 敌单基地且有出兵建筑(SPAWNINGPOOL/BARRACKS/GATEWAY≥1)或可见兵 ≥6
      → "rush"(Zerg 正常运营 t≈100 二矿已落,单基地+pool = 狗池爆狗;
      单基地兵营/gateway 同理直读);
    - 其余 → 回落 scout_verdict 老三档。
    O100-③(o99 局2 实证):vs Zerg 见出兵建筑时即使有二矿也不开 greedy
    绿灯 —— hatch-first+狗 rush 是真实开局(局2:二矿+SPAWNINGPOOL 误判
    greedy,接触 t=193 才进过渡死 249);但证据也不足判 rush(可能真是
    运营)→ "unknown"(保守中间档:不 pivot 贪,也不进过渡 latch)。
    enemy_is_zerg 缺省 False → 旧签名行为逐位不变。
    """
    if not intel:
        return "unknown"
    if enemy_townhalls >= 2:
        # O100-③(o99 局2)+O104-③(o103 局2):vs Zerg 早评永不给 greedy ——
        # hatch-first+pool 是真实 rush 开局(局2 两连实证:看到二矿+pool 判
        # greedy 被 rush;补派只看到二矿、pool 在主基地视野外,判 greedy 又被
        # rush)。「没看到 pool」≠「没 rush」。unknown = 保守中间档(不 pivot
        # 贪、不进 transition latch);vs Zerg 反正不 pivot(should_pivot_tempest
        # 已排除),greedy 的实际收益≈0,误判成本是全局。
        if enemy_is_zerg:
            return "unknown"
        return "greedy"
    if military_structs >= 1 or early_army >= 6:
        # O169:Zerg 单基地+一个 SPAWNINGPOOL 不一定是 rush(Power/Timing 运营
        # 也常先池后矿);无早期作战单位时保守判 unknown,避免 Power 局被
        # 误判进 transition、舰队永远出不来。真 12pool 通常带 ≥6 条狗,
        # 仍会被 early_army 门槛捕获。
        if enemy_is_zerg and military_structs < 2 and early_army < 6:
            return "unknown"
        return "rush"
    # O107(o106 局3/4/5 实证):vs Zerg 的 greedy 出口连回落分支也删掉 ——
    # 补派探机只看到主基地 HATCHERY(单基地、无 pool、无兵)时,scout_verdict
    # 回落会给 greedy(o106 三连误判回潮:presumed 被关、F2 拖到接触才注册)。
    # vs Zerg 一律 rush/unknown 二选一。
    if enemy_is_zerg:
        return "unknown"
    return scout_verdict(
        intel=intel, military_structs=military_structs, early_army=early_army
    )


def fleet_expansion_reserve(
    fleet_transitioned: bool,
    first_fleet_seen: bool,
    bases: int,
    want_expand: bool,
    can_afford_nexus: bool,
    threat_active: bool,
    rush_active: bool,
    defense_score: float = 0.0,
) -> bool:
    """O97-B(o96 局5 实证):首舰后攒钱开二矿的出兵预留判据。纯逻辑,可单测。

    局5:首舰 t≈655 后 300s+ 没开出二矿 —— 矿恒 50-250,舰队(150/艘)+塔
    持续吃矿,Nexus 400 永远攒不出,单矿 20 农民 supply 顶 45,被 Hive 波次
    (t=968,24 地面)磨死。O56 的「持有期不冻出兵」是给舰队未成型的局设计
    的;首舰已出+单矿时,二矿就是赢的方式 —— 想开矿且买不起 → SpawnController
    暂停攒钱(农民照造=收入来源)。买得起/威胁/rush → 翻假(自校正,无 latch,
    急性窗绝不停产)。只挂转舰队后的 carrier,其余路径零变化。
    O135 后语义:SpawnController 永不停,预留只闸建筑注册(塔/水晶/科技链)。
    O145-②(o144 局3 实证):first_fleet_seen 前提放宽为「首舰 或 评分≥25」——
    局3 strong-exit(400)后首舰要等 SG→FB→首舰 ~300s,预留死等首舰 =
    科技链(SG 570/FB 616)把 Nexus 的 400 吃光,bases=1 到死;评分 ≥25
    (O105 豁免同口径)即允许为首舰前的二矿攒钱(防御站稳,等得起)。
    defense_score 缺省 0 → 旧签名行为逐位不变。
    """
    return (
        fleet_transitioned
        and (first_fleet_seen or defense_score >= 25.0)
        and bases <= 1
        and want_expand
        and not can_afford_nexus
        and not threat_active
        and not rush_active
    )


def transition_probe_yield(
    transition_active: bool,
    workers: int,
    ground_army: int,
    min_workers: int = 14,
    army_target: int = 12,
    acute: bool = True,
) -> bool:
    """O97-C(o96 局1/局3 实证):过渡期农民训练是否让位地面产能。纯逻辑,可单测。

    局1:农民 17→29(≈600 矿)而叉子只有 7 个迎 30-supply 波;局3:农民(50)
    每次矿到 50 就吃走,叉子(100)永远攒不出 —— 116s 零叉。过渡期 =
    生存窗,地面兵是命根:农民够保底(min_workers)且地面未到目标
    (army_target) → 农民让位;任一翻假即恢复(自校正;O42 的「不掐农民」
    是给开矿运营期的,过渡期反着来)。
    O146-②(o133 以来 14 连零胜元诊断):持续型改窗口型 —— 过渡态本身是
    持续 300s+ 的慢性条件,叠加其余刹车把农民长期压在 12(赢局时代退出
    时 15-20 农)。acute=False(非急性窗:无敌进家 40 格且 threat 25s 内
    未激活)→ 不让位;acute 缺省 True → 旧签名行为逐位不变。
    """
    return (
        transition_active
        and acute
        and workers >= min_workers
        and ground_army < army_target
    )


def probe_floor_needed(
    now: float,
    workers: int,
    acute: bool,
    floor: int = 16,
    until: float = 350.0,
) -> bool:
    """O146-①(o133 以来 14 连零胜元诊断):农民下限判据。纯逻辑,可单测。

    胜局时代(o107-o132,5 胜)与零胜时代最干净的差异:赢局退出时
    13-15 叉+4 塔+15-20 农;现局 7-8 叉+3 塔+12 农 —— 刹车家族
    (O97-C/O111/O125/O129)各省 50 矿换几秒防御时点,叠加代价是 400s
    收入腰斩。t≤until 且非急性窗(敌进家 40 格 / threat 25s 内)且
    农民 <floor → 必产(调用方绕过一切 yield/brake);急性窗内旧刹车
    语义全保留。
    """
    return now <= until and not acute and workers < floor


# O147-①:关键三件(forge/首塔/GW1)—— 钉点豁免名单
CRITICAL_DISPATCH_IDS = frozenset({"FORGE", "PHOTONCANNON", "GATEWAY"})


def critical_dispatch_exempt(type_name: str, have: int) -> bool:
    """O147-①(o146b 局1 实证):关键三件豁免钉点守卫判据。纯逻辑,可单测。

    O139 的钉点治理(dispatch_viable+早撤回+冷却)把首波防链治死:
    钉点(驻点等钱、钱到立刻开工)恰是 forge 准点的关键机制(O118 时代
    forge 95-110 靠它);禁钉后 forge 漂回 125-155、forge→首塔 43s 空档。
    正确解 = 只许关键三件的钉点:首个 FORGE/PHOTONCANNON/GATEWAY
    (have=0)的派工豁免收入守卫与撤回冷却,其余建筑维持 O139 守卫。
    """
    return have == 0 and type_name in CRITICAL_DISPATCH_IDS


# ────────────── O98 探机送达率/断链兜底/二波强度(o97-vh-zerg-rush 0-5 尸检) ──────────────


def scout_early_redispatch_needed(
    has_transition: bool,
    intel: bool,
    scout_lost: bool,
    redispatched: bool,
    now: float,
    at: float = 95.0,
) -> bool:
    """O98-①/O99-②/O106-③(at 105→95):探机失联后的早补派判据。纯逻辑,可单测。

    o97 实证:探机 t=55 出发,4/5 局从未送达,而 E7 的补派被
    scout_verdict_timing 的 verdict_at=170 闸住 —— 无情报干等 30-50s。
    o98 实证(局5):scout_dead 判据(单位没了)漏掉两种失联 ——
    a) 派发根本没执行(tag=None,select_worker 没选到人);
    b) 探机活着但被 idle 清扫摘了 SCOUTING role 扫回采矿(单位在、role 没了)。
    失联(tag 无/单位无/role 无三态任一)+ 无情报 + 没补派过 + 到 at 秒
    → 不等 170,立即补派一次(仍只一次,防无限续命送死)。
    """
    return (
        has_transition
        and not intel
        and scout_lost
        and not redispatched
        and now >= at
    )


def presumed_rush_defense(
    enemy_is_zerg: bool,
    has_transition: bool,
    verdict_done: bool,
    rush_confirmed: bool,
    now: float,
    at: float = 55.0,
    scout_lost: bool = False,
    lost_at: float = 95.0,
) -> bool:
    """O98-②/O99-②/O100-④/O111-①:vs Zerg 侦查断链的保守兜底。纯逻辑,可单测。

    按疑似 rush 先启动节制版防御链(F2 target=1:forge+首塔,电池让位)。
    verdict 落地(任何结论)或接触确认 → 翻假交还正常路径 —— 自校正无
    latch,不进 transition(贪开局只亏 1 塔+forge 的钱,不扭曲整局 build)。
    O100-④:探机失联 + t≥lost_at → 立即启动不等 120。
    O111-①(o110 局1/局2 实证):at 120→78 无条件启动 —— O107 后 vs Zerg
    早评只有 rush/unknown,侦查对首波防御的情报价值已为零。
    O113-③(o112 局1/局3 实证):at 78→65 —— 首塔 ~150-165 vs 波次
    ~150-165 仍是掷硬币,再提前 13s 掰硬币(双农民速建不适用于神族
    warp-in,时点提前是唯一杠杆);对 Zerg Macro 的代价 = forge+1 塔
    ≈250 矿保险,可接受。
    O141(o141 一轮 smoke 实证):at 65→55 —— 65 启动时第 12/13 农民已在
    55-60 进队(各 50,供应冻结下堵到 ~90 才落地),forge 的 150 被挤到
    ~100 才攒出(完工 133);55 启动 = 农民冻结(≥11 让位)+ forge 链
    整体提前 10s,完工 ~96-104。
    """
    if not (
        enemy_is_zerg
        and has_transition
        and not verdict_done
        and not rush_confirmed
    ):
        return False
    return now >= at or (scout_lost and now >= lost_at)


def hurt_retreat_needed(
    shield: float, health: float, shield_max: float, health_max: float,
    threshold: float = 0.3,
) -> bool:
    """O148-②:防守战伤兵后拉判据。纯逻辑,可单测。

    盾+血合计占比 <threshold → 后拉到电池/塔覆盖圈(电池奶回再随下波
    顶上;伤兵白死 = 每波少 2-3 叉,o147 系列守军战损复盘)。
    只对地面近战(叉子)有意义 —— 追猎/舰队自带风筝,调用方过滤。
    """
    total_max = shield_max + health_max
    return total_max > 0 and (shield + health) / total_max < threshold


def transition_expand_at_210(
    transition_active: bool,
    saw_wave: bool,
    enemy_near: int,
    now: float,
    at: float = 210.0,
) -> bool:
    """O149-①(o133-o148 二十轮元诊断):定时强开二矿判据。纯逻辑,可单测。

    五胜局全部 3-4 基地,败局全部 1-2 基地 —— 二矿存活率=胜率;而
    transition_expand_ready/after_first_wave 的触发率极低(timing 局
    清净窗永远不够)。改定时:过渡/rush 局 t≥at 且首波已清(见过波 +
    当前家 40 格无敌)→ 立即开二矿,不等清净秒数/评分/兵力优势。
    """
    return transition_active and saw_wave and enemy_near == 0 and now >= at


def two_base_guard_point(
    main: tuple[float, float], nat: tuple[float, float]
) -> tuple[float, float]:
    """O149-③:双矿防守集结点 = 主基卡位点-分矿连线中点。纯逻辑,可单测。

    扩张后地面部队站两矿间机动位(哪边来波都能接应),不再只蹲主基
    坡口(O148 的 _ramp_hold_point 只盖主基)。
    """
    return ((main[0] + nat[0]) / 2, (main[1] + nat[1]) / 2)


def main_defense_first(main_threat: int, min_main: int = 3) -> bool:
    """O153-③修正(o152 回退评估):主基遇袭优先判据。纯逻辑,可单测。

    分矿接应(O152-②)的安全例外:主基本身被 ≥min_main 敌作战单位进犯
    时,守军不去分矿(接应把主基抽真空 = 换家死)。敌情口径与
    _rush_defend_anchor/_hot_base_anchor 同源(基地 25 格计数)。
    """
    return main_threat >= min_main


def transition_needs_gateways(
    transition_active: bool, gateways_have: int, cap: int
) -> bool:
    """O98-③b(o97 局2 实证):过渡期兵营直补到 cap 判据。纯逻辑,可单测。

    局2:首波守住后敌可见=0,rush_needs_gateway 的「敌兵>叉子」条件停,
    GW2 拖到 t=301(extra_production 又要等 rush 解除)——二波(t=449,
    30 supply)时只有 8 叉。过渡期产能就是命根:兵营(已有+在建)< cap
    且买得起就补,不等敌兵对比、不等 rush 状态。O94-B 的 forge 优先
    语义在调用方保留(forge 实体前仍缓建)。
    """
    return transition_active and gateways_have < cap


def transition_needs_cybercore(
    transition_active: bool, cyber_present_or_pending: bool,
    ground_army: int = 2,
) -> bool:
    """O98-③c(o97 局2 实证):过渡期 CYBERNETICSCORE 豁免 E3d rush 全停。
    纯逻辑,可单测。

    局2:二波是蟑螂+刺蛇(30 supply),纯叉被克;气烂 2000 而追猎(气耗、
    对重甲关键 DPS)因 cyber 被 rush 全停压住出不来。过渡期 cyber 单独
    豁免(星门/FB 仍冻结);can_afford 守卫让急性窗自然让位塔/叉。
    O103-①(o102 局3/局5 实证):但首波守窗(0 叉)cyber 也不能抢 ——
    局3/局5 矿 250 时 cyber 先吃 150,首叉从 ~156 拖到 ~183。加
    ground_army≥2 门(先有两个叉站岗,再谈追猎科技)。
    ground_army 缺省 2 → 旧签名行为逐位不变。
    """
    return (
        transition_active
        and not cyber_present_or_pending
        and ground_army >= 2
    )


def transition_cannon_cap(cannons: int, transition_active: bool, cap: int = 3) -> int:
    """O102-②/O123-①/O132-②:过渡期塔目标封顶。纯逻辑,可单测。

    O102 版 cap=4(o101 局1/2:第 5-6 座塔的钱换 3-4 叉)。
    O123(o122 系列战略转向):cap 4→2 —— 塔链对最快骰物理无解
    (presumed→forge→首塔 ~185 vs 波次 154 是材料极限),forge 只带
    1-2 塔保底,余钱全进兵营/叉海。非过渡期原样返回。
    O132-②(o131 timing 局实证):cap 2→3 —— cap=2 时 timing 波
    (540+ 的 20+ supply)稳定穿防,2 塔+电池 DPS 不够;3 塔是
    「塔能换掉波次战损」的最低密度,且峰值 latch(O132-③)保证
    兵营链不再被塔数反锁,第 3 座塔的钱不再挤兵营。
    """
    return min(cannons, cap) if transition_active else cannons


def transition_timing_sprint(
    transition_active: bool,
    verdict: str | None,
    now: float,
    at: float = 240.0,
    enabled: bool = False,
) -> bool:
    """O133-②(o132 timing 系列尸检):过渡期 250-300 防御冲刺判据。纯逻辑,可单测。

    四败同指纹:timing 波 273-289 到脸,守军只有 6-8 叉+1-2 塔 —— 清净期
    (波未出门,威胁/接触全无)防御建设被各类预留/持有闸压速。冲刺窗
    (t≥at 且过渡 active 且 verdict≠greedy)不管清净/威胁状态,调用方把
    塔补到 3、GW 链让位闸旁路、电池保底(O120-③ 已兜 2)。greedy 局
    不冲刺(对面运营,防御照威胁走,不扭曲经济)。
    O144-②(o133 以来 10+ 系列零胜尸检):回滚关断(enabled 缺省 False)——
    无差别冲刺(GW3+塔3+电池1 不管敌情)在非 rush 局白吃矿,经济/
    科技全慢半拍。代码保留备查,重开 = 调用方传 enabled=True。
    """
    return enabled and transition_active and verdict != "greedy" and now >= at


def ground_floor_active(
    rush_confirmed: bool, enemy_ground_visible: int, min_enemy: int = 4
) -> bool:
    """O144-③(o133 以来 10+ 系列零胜尸检):非过渡地面 floor 的激活闸。
    纯逻辑,可单测。

    O134 的地面保底(2 GW + 叉/追猎 10-14 supply)在纯运营局挤舰队科技钱
    (SG/FB 慢半拍)。收窄:rush 确认 或 敌可见地面 ≥min_enemy 才激活;
    纯运营局(敌情未见)不产地面,矿全进舰队科技链。
    """
    return rush_confirmed or enemy_ground_visible >= min_enemy


def zerg_timing_unknown_floor(
    is_zerg_timing: bool,
    verdict: str | None,
    now: float,
    fleet_seen: bool,
    at: float = 220.0,
) -> bool:
    """O255-③(o254 双 lane 0-10 尸检):Zerg Timing 死窗叉子 floor 判据。
    纯逻辑,可单测。

    o254 实证:Zerg Timing 波 280-310s 到脸(10-19 supply),verdict=unknown
    时 ground_floor_active 不激活(无接触、敌未可见),守军 = 1-2 塔 + 0 地面
    + 22-26 农民裸接,农民被屠(25→6)后基地连锁崩。o252/o254 长局与速败的
    唯一分野就是这波硬币是否接住。
    开一条窄通道:Zerg Timing + verdict==unknown + t≥at + 舰队未出 →
    floor 激活,调用方把追猎 cap 压 0、叉 cap 压 3(300 矿,从常态 1300+
    银行出 = 白捡的死窗防守)。与 O253(t≥240 floor 常开 + 追猎 cap2=12,
    吃气吃矿把 SG/FB 挤死,o253 0-7 实证)的区别:不碰气、上限极小、
    舰队一出即退。
    """
    return is_zerg_timing and verdict == "unknown" and now >= at and not fleet_seen


def fb_gate_f2_exempt_zt(is_zerg_timing: bool, sg_ready: bool) -> bool:
    """O255-①(o254 双 lane 0-10 尸检):F2 让位 FB 闸的 Zerg Timing 豁免。
    纯逻辑,可单测。

    O170/O172 的 FB 闸(FB 无实体 → F2 整段让位,保 FB 300 矿资金窗)在
    Zerg Timing 直爬路线构成死锁:FB 需就绪星门,星门未就绪时 FB 资金窗
    根本不存在,F2 却给「还不存在的窗」让位 —— game_02 实证 200-350s
    防御建设整段冻结(1 塔 0 电池接 300s 波),银行躺 1900;同时 O216i
    (SG 让位 2 塔)无塔可等,SG 被推到 305s、首舰 ~450s。
    SG 就绪前豁免该闸:2-3 塔+电池 250s 前落地,O216i 的 2 塔条件同时
    解锁 → SG 提前 ~50s。SG 就绪后(FB 窗真实存在)闸恢复原语义。
    """
    return is_zerg_timing and not sg_ready


def zerg_timing_expand_allowed(
    is_zerg_timing: bool,
    first_fleet_seen: bool,
    now: float,
    enemy_home: int,
    enemy_near_natural: int,
    at: float = 320.0,
    hard_gate: float = 620.0,
) -> bool:
    """O258-①/O262-①/O263-①:ZT 二矿窗判据(防御驱动)。纯逻辑,可单测。

    O247/O250 的「首舰前 t<620 不开二矿」把二矿落成压到 518-671s ——
    O236 胜负对照「二矿 ≤400s=胜、≥500s=负」全落在负侧。
    O258(t≥340+非威胁):threat 首波后常驻,闸整局不开(o261a-g01 单矿 900s)。
    O262(t≥260+去 threat):260s 强开把建筑期 Nexus 拍进波的行进路线
    (o262a-g02:293s 落 309s 被拆,白捐 400,主基防钱同空)——窗太早。
    O263:t≥320(首波 305-320s 到脸、被塔阵接住的时点之后) + 家 40 格无敌
    + **分矿点 35 格无敌**(波次路径不再踩分矿) 三条件;首舰/t≥620 硬门原样。
    """
    if not is_zerg_timing:
        return True
    if first_fleet_seen or now >= hard_gate:
        return True
    return now >= at and enemy_home == 0 and enemy_near_natural == 0


def unknown_verdict_defense(
    enemy_is_zerg: bool,
    has_transition: bool,
    verdict: str | None,
    rush_confirmed: bool,
    transition_active: bool,
    now: float,
    at: float = 200.0,
    enabled: bool = False,
) -> bool:
    """O133-③(o132 timing 局1/2/5 实证):unknown 判决的保守防御。纯逻辑,可单测。

    局1/2/5 直接死因:verdict=unknown → 过渡形态等到接触(273-276)才进,
    零防御接 timing 波。unknown 不再等于「等到接触再说」:vs Zerg 且
    t≥at 仍 unknown → 按 presumed 同等级拉防御(F2 target 2 塔,
    presumed 是 1 塔节制版 —— 200s 的 unknown 信息量 ≠ 65s 的 unknown,
    波 273 必来,多一座塔是命)。rush 确认/过渡已进 → 交还各自路径;
    greedy/rescout 翻案 → 自动解除(无 latch)。
    O144-①(o133 以来 10+ 系列零胜尸检):回滚关断(enabled 缺省 False)——
    对 Zerg Timing/Power(非 rush),t=200 起白拍 forge+2 塔 ≈400 矿,
    经济/科技全慢半拍,正好覆盖 o133 以来所有系列的非 rush 局。
    代码保留备查,重开 = 调用方传 enabled=True。
    """
    return (
        enabled
        and enemy_is_zerg
        and has_transition
        and verdict == "unknown"
        and not rush_confirmed
        and not transition_active
        and now >= at
    )


def transition_gateway_allowed(
    gateways_have: int, cannons: int, min_cannons: int = 2
) -> bool:
    """O99-①/O102-①:过渡期兵营补建的资金顺序闸。纯逻辑,可单测。

    O99-①(o98 局3/4):GW2/GW3 必须等首 2 塔(已有+在建)——O98-③b 的
    「买得起就补」把塔链饿死(局3:兵营×3 吃光矿,300s 零塔)。
    O102-①(o101 局3/4/5):但 GW1 不受此闸 —— 塔先排序让 GW1 拖到
    ~165-181 完工,首叉 195+,完美错过首波守窗(155-185);rush 确认后
    资源够 forge+GW1 并行双开(t≈110 前各 150),GW1 t≈110 完工 →
    首叉 ~140-155 正好进守窗。cannons 用「已有+在建」口径;
    O132-③ 起调用方喂峰值 latch(塔被 wave 拆掉不再反锁兵营链)。
    """
    return gateways_have == 0 or cannons >= min_cannons


# ────────────── O100 过渡形态卡死/误判/断链兜底提前(o99-vh-zerg-rush 0-5 尸检) ──────────────


def transition_expand_ready(
    transition_active: bool,
    cannons_ready: int,
    ground_army: int,
    clear_for: float,
    min_cannons: int = 2,
    min_ground: int = 4,
    clear_needed: float = 8.0,
) -> bool:
    """O100-①(o99 局1/局5 实证):过渡期防御站稳 → 开二矿判据。纯逻辑,可单测。

    局1/局5:波次 60-90s 一波,30s 清净退出门永假 → 卡死过渡形态,单矿
    12-15 农民缓慢必死。破法:防御站稳(塔 ≥min_cannons + 地面 ≥min_ground
    + 家 40 格清净 ≥clear_needed 秒,三重门)就允许开二矿,不等转舰队 ——
    双矿地面产能翻倍,要么地面打死对面,要么攒出退出门。站不稳 → 不开
    (先保命)。rush 否决在调用方旁路(站稳三重门已含敌情考量)。
    O102(o100 系列实证):min_ground 8→5、clear 15→12 —— 8 叉门槛全系列
    0 触发,鸡生蛋死结。
    O119-②(o118 局5 实证):5/12 仍 0 触发 —— 波次间隙实测 8-12s,
    清净窗被波次节奏切碎;降到 4 叉/8s(局5 在 350-400 有多次 8s+ 间隙)。
    O204:调用方对 Zerg Rush 可传 min_ground=2/clear_needed=5 进一步降低门槛。
    """
    return (
        transition_active
        and cannons_ready >= min_cannons
        and ground_army >= min_ground
        and clear_for >= clear_needed
    )


def forced_expand_during_transition(
    transition_active: bool,
    now: float,
    cannons_ready: int,
    enemy_near_home: int,
    minerals: float,
    nexus_pending: int,
    nexus_cost: float,
    min_time: float = 180.0,
    min_cannons: int = 2,
    clear_for: float = 5.0,
    mineral_buffer: float = 50.0,
) -> bool:
    """O204:Rush/transition 期强制二矿触发器。

    原 should_expand_dynamic 在 rush_active 期间直接返回 False,transition_expand_ready
    又要求地面≥4/清净≥8s,导致 Zerg Rush 局二矿永远开不出(one_base×5)。
    破法:transition 已激活、时间≥180s、已有≥2 座就绪塔、家 40 格无敌≥3 已持续≥5s、
    当前 mineral 足够付 Nexus+buffer 且无 Nexus 在建 → 强制触发二矿。
    该触发器与 rush_active 解耦,只看 transition 和实际防御站稳情况。
    """
    if not transition_active or nexus_pending:
        return False
    if now < min_time or cannons_ready < min_cannons:
        return False
    if enemy_near_home >= 3:
        return False
    return minerals >= nexus_cost + mineral_buffer


def fleet_exit_allowed(
    bases: int,
    ground_supply: float,
    now: float,
    defense_score: float = 0.0,
    sg_present_or_pending: bool = True,
    deadline: float = 540.0,
    min_ground: float = 14.0,
    strong_exit_score: float = 25.0,
) -> bool:
    """O119-①③/O121-③/O132-①:转舰队退出闸的经济+地面+星门前提前提。纯逻辑,可单测。

    局5(o118):400 单矿退出即崩 —— 经济达标 + 地面 ≥14 supply 才许退;
    t>deadline 仍不达标 → 经济门放行(再等也是死)。
    O121-③(o120 局2/3/4):加星门前提 —— SG 未拍就退出 = SG→FB 链 190s
    空窗,exit+60s 波到脸时舰队 0 艘;SG 已拍/在建才退(配套
    transition_stargate_allowed:防御达标后过渡期即解冻 SG)。
    O132-①(o131 系列 0-N 尸检):经济门从「bases≥2 或 Nexus 在建」改
    三选一 —— bases≥2 / 地面 ≥20 supply / 防御评分 ≥35(评分口径同
    strong-exit:地面×2+就绪塔×3+就绪电池×2,实时值)。O119 的
    bases≥2 门是系统性败笔:上线后 0 胜(单矿死守局永远等不到二矿,
    此前四胜全靠 strong-exit 评分门)。死线 600→540:o131 局 540 后
    经济/产能已无翻盘窗口,早放行走 strong-exit/死线通道博舰队。
    O140-①(o139 terran-rush 局2 实证):SG 前提对高评分解锁 —— 局2
    t=498 评分 35(12叉1追猎+3塔)、地面 26 达标,但 SG 前提永假:
    SG 解冻(transition_stargate_allowed 评分≥25)虽已亮,单矿经济
    矿恒 25-75,SG 的 150 矿永远攒不出 → 「SG 已拍才准退、SG 要退了
    才有钱拍」死锁,543 波穿防死 575。评分 ≥35(防御能扛过 SG→FB
    空窗)→ 不要 SG 也准退;退出后科技链自然解冻 + O106 科技预留
    攒钱,SG→FB 在舰队配方下重建。
    O143(o142 双系列 0-10 实证):评分 ≥25(strong-exit 阈值)直接放行 ——
    叠加门(bases/SG/地面)在评分门之上是死锁放大器:o129 局5 评分 41、
    敌可见 0 持续 60s+,因单矿+无 SG 不 exit,590 波一波清零;o142
    timing 局5 评分 29+清净窗 482-542,被经济三选一(34<35)卡死。
    评分 ≥25 本身已含防御质量(塔×3/电池×2/地面×2),strong-exit 的
    领先+清净 30s 在调用方另查 —— 这里不再叠加。评分 <25 的低防局
    仍走原三门(防裸奔退出自杀)。
    O204:strong_exit_score 参数化,允许 Zerg Rush 局降到 20 放宽转舰队。
    """
    if now > deadline:
        return ground_supply >= min_ground or defense_score >= strong_exit_score
    if defense_score >= strong_exit_score:
        return True
    return (
        (bases >= 2 or ground_supply >= 20.0)
        and sg_present_or_pending
        and ground_supply >= min_ground
    )


def tower_yields_gateway_chain(
    transition_active: bool,
    gateways_have: int,
    gateway_cap: int,
    cannons_ready: int,
) -> bool:
    """O131-②(o130 局2/局5 实证):塔让位兵营链(排队型,替代暂停型预留)。
    纯逻辑,可单测。

    o130 实证:暂停型 gw_reserve 是死锁发生器 —— 暂停产兵攒 150,
    但 F2 塔不在仲裁器管辖内照建照吃,矿恒 15-95 永远攒不到
    (局2:产兵暂停=gw_reserve 从 297 刷到 568+ 直到死)。排队型:
    SpawnController 永不停(叉子照产),2 塔保底后 GW<cap 时塔/水晶让位,
    GW 钱到就拍(叉子 27s 周期之间自然留出 100→150 的窗)。
    O132-③:调用方喂的是就绪峰值 latch(塔被拆不反锁兵营链),
    判据本身的「≥2」语义不变。
    """
    return (
        transition_active
        and cannons_ready >= 2
        and gateways_have < gateway_cap
    )


def transition_gateway_reserve(
    transition_active: bool,
    gateways_have: int,
    cannons_ready: int,
    gateway_cap: int,
    can_afford_gw: bool,
    threat_active: bool,
    rush_active: bool,
    zealot_producible: bool = False,
) -> bool:
    """O120-①/O123-①/O124-①:过渡期兵营攒钱预留。纯逻辑,可单测。

    O123 版:常态预留(GW<cap 且买不起即攒)。
    O124-①(o123 局1 实证):预留不得饿现役产能 —— 局1 为 GW2 攒钱时把
    GW1 的叉子生产也暂停了(SpawnController 整段停),GW1 完工后空转
    76s、首叉 201。加 zealot_producible(有空闲兵营且矿 ≥100,调用方算)
    → 不预留:攒 GW 只能攒叉子剩下的钱,任何时刻「有 GW 空闲 + 100 矿
    = 叉子在产」。缺省 False → 旧签名行为逐位不变。
    """
    return (
        transition_active
        and gateways_have < gateway_cap
        and not can_afford_gw
        and not threat_active
        and not rush_active
        and not zealot_producible
    )


def transition_pauses_gas(transition_active: bool) -> bool:
    """O124-②(o123 局1 实证):过渡期不建新气矿(已有的照采)。纯逻辑,可单测。

    叉海不吃气 —— 局1 气 468-588 烂着,每个新气矿 75-150 矿正是
    forge/GW/叉的钱。退出后(cyber/追猎/舰队要气)自动恢复
    (transition_active 翻假即不停)。非 transition 流派恒 False。
    """
    return transition_active


def first_zealot_sprint(
    defense_urgent: bool,
    gateway_ready: bool,
    zealot_seen_or_pending: bool,
    minerals: float,
    zealot_cost: float = 100.0,
) -> bool:
    """O124-③(o123 系列实证):首叉冲刺判据。纯逻辑,可单测。

    首叉时点是所有速骰局的胜负手。rush 确认/过渡 + 有就绪兵营 +
    首叉未出未在产 + 矿 <100 → 一切非防御开销(水晶/农民)暂停,
    直到首叉在产。自校正:首叉在产/落地即翻假。
    """
    return (
        defense_urgent
        and gateway_ready
        and not zealot_seen_or_pending
        and minerals < zealot_cost
    )


def transition_battery_floor(
    transition_active: bool, cyber_present_or_pending: bool,
    batt: int, floor: int = 2,
) -> int:
    """O120-③(o119 局2 实证):过渡期电池保底。纯逻辑,可单测。

    局2:全程 0-1 电池 —— rush_hold_batteries 在接触窗给 0(E3d 让位),
    塔群无电池续航 = 一次性防御,波次磨塔必崩。cyber 在链上(有/在建)
    时电池 target 抬到 floor(2);cyber 没有时不抬(E3d 教训:为电池
    先补 cyber 会阻塞塔链)。非过渡期原样返回。
    """
    if transition_active and cyber_present_or_pending:
        return max(batt, floor)
    return batt


def rebuild_window_spawn(spawn: dict, rebuild_window: bool, voidray_id) -> dict:
    """O121-①(o120 局2/3/4 实证):重建窗(FB 未就绪)星门填窗兵种。
    纯逻辑,可单测。

    局2/3/4 同型:退出 → SG→FB→首舰 ~190s 空窗,波次 exit+60s 到脸时
    舰队 0-1 艘 = 没有。VOIDRAY 不需 FB、37s 成型、棱镜对齐烧地面 ——
    退出后 SG 立刻有产出,exit+60s 有 1-2 虚空、exit+120s 有 3-4,
    配合塔/电池顶过空窗;FB 就绪后 TEMPEST 入队即自然挤占(p0 同档,
    dict 序 TEMPEST 在前),首舰出场窗关、配方复原。
    """
    if not rebuild_window:
        return dict(spawn)
    out = dict(spawn)
    out[voidray_id] = {"proportion": 0.7, "priority": 0}
    return out


def transition_stargate_allowed(
    transition_active: bool, defense_score: float, min_defense: float = 25.0
) -> bool:
    """O121-③(o120 局2/3/4 实证):过渡期防御达标 → 提前解冻星门。
    纯逻辑,可单测。

    局2/3/4:strong-exit 时 SG 还没拍(冻结中),退出后 SG→FB 链 190s
    空窗必死。防御评分达标(strong-exit 同口径)即解冻 SG —— 退出时
    链上只剩 FB(~60s),空窗压到一波周期内。不达标 → 冻结照旧
    (塔/叉优先,build order 不变)。
    """
    return transition_active and defense_score >= min_defense


def forge_first_pylon_yield(
    defense_urgent: bool, forge_present: bool, supply_left: float,
    emergency: float = 4.0,
) -> bool:
    """O103-③(o102 局3/局5 实证):rush 确认/presumed 且 forge 未落地时,
    AutoSupply 的水晶是否让位 forge。纯逻辑,可单测。

    局3/局5:早评 rush t=81、F2 注册 t≈100,forge 却 t=125-129 才落地 ——
    中间水晶 #3(t≈108-116,100 矿,supply_left 还有 15!)抢了 forge 的资金窗,
    首塔 190-225 vs 波次 155-237。defense_urgent(rush_confirmed 或 presumed)
    且 forge 无实体 → 水晶让位;forge 落地即恢复。
    O141(o141 一轮 smoke 实证):人口紧急例外(≤emergency 照建)删除 ——
    局1 供应 13/13 从 58 堵到 88,E3h 应急水晶(100)在 forge 的 150 前面
    落地;但农民已被 forge_first_probe_yield 冻在 11,卡人口什么都不堵
    (无兵无新农民),应急水晶是纯浪费。forge 落地后水晶照建,GW/叉子
    的供应不受影响。
    """
    return defense_urgent and not forge_present


def forge_first_probe_yield(
    defense_urgent: bool, forge_present: bool, workers: int,
    min_workers: int = 11,
    now: float = 0.0, until: float = 200.0,
) -> bool:
    """O111-③(o110 局1/局2 实证):forge 未落地前农民训练是否让位。
    纯逻辑,可单测。

    presumed/早评 rush 后 forge 落地仍有 ~10s 延迟 —— 剖开看是 2-3 个
    农民(各 50 矿)排在 forge(150)前面训练。defense_urgent(rush 确认/
    过渡/presumed)且 forge 无实体且农民 ≥min_workers(12,保底采矿量)
    → 农民让位;forge 落地即恢复(自校正)。目标:首塔 ≤150。
    O146-②:持续型改窗口型 —— defense_urgent 的 rush_confirmed 是 latch
    (一旦确认全程为真),forge 被打掉的局农民会冻在 11 到终局;本判据
    的正当语义只在开局 forge 竞速窗 → 加 until(默认 200s)截止。
    now 缺省 0 → 旧签名行为逐位不变。
    """
    return (
        defense_urgent
        and not forge_present
        and workers >= min_workers
        and now <= until
    )




def forge_before_first_gateway(
    defense_urgent: bool, forge_present_or_pending: bool
) -> bool:
    """O118-②/O127-①(数据终裁):防御紧急窗 forge 先于首兵营。纯逻辑,可单测。

    o126b 算术终裁:最快波 ~154;forge 优先链(forge 75-80 拍 → 首塔
    ~140-145)赢 10-14s,GW 优先链(GW ~145 完工 → 首叉 ~155-165)输
    0-10s。O118 方向对,O125 反转为误 —— O118 当时失败是 forge 没在
    75-80 开拍(资金被 O79 水晶/农民偷),不是顺序错。
    严格前提「forge 未拍(无实体且无在建)」:forge 一拍下 GW1 即紧随,
    不互抢;forge 掉了重建期 GW 让位(塔链是防御本体)。
    """
    return defense_urgent and not forge_present_or_pending


def chrono_first_zealot(defense_urgent: bool, first_zealot_seen: bool) -> bool:
    """O125-②(o124 局1 实证):rush/过渡窗内 chrono 给兵营首叉。纯逻辑,可单测。

    过渡期 SG 未建,chrono 配置目标(STARGATE)不存在,能量整段闲置;
    首叉 27s → chrono ~19s,正好是速骰局差的那 10s。首叉出场即恢复正常
    chrono 分配(自校正)。
    """
    return defense_urgent and not first_zealot_seen


def chrono_forge_first(defense_urgent: bool, forge_warping: bool, first_cannon: bool) -> bool:
    """O141-②(o141 一轮 smoke 实证):防链竞速期 chrono 给 forge。纯逻辑,可单测。

    forge 33s warp 是首塔的前置瓶颈(一轮:forge 完工 133 → 首塔 181);
    chrono 后 ~23s(完工 ~104→~96)。首塔出现(含在建)即让位首叉
    chrono(chrono_first_zealot 接管),不双抢能量。
    """
    return defense_urgent and forge_warping and not first_cannon


def tower_zone_pylon_needed(
    cannons_ready: int, cannons_pending: int, pylons_near: int
) -> bool:
    """O128-②(o106/o113/o114/o127 四局同点累犯):塔位供电水晶判据。
    纯逻辑,可单测。

    主基水晶全锚在坡口/生产区,塔位区(矿线)带电槽恒 0 —— 首塔落位
    no_placement 循环的直接死因。首塔未就绪且未在建 + 塔位锚点旁无水晶
    → 先派一根「塔位供电水晶」(锚点=矿线质心,O101 已有),一石二鸟:
    供电 + 塔位。别等 watchdog 的贴槽水晶自救(45s 周期,太慢)。
    """
    return cannons_ready == 0 and cannons_pending == 0 and pylons_near == 0




def spawn_pause_reason(
    *,
    rebuild_nexus: bool,
    expand_holding: bool = False,
    is_zerg_timing: bool = False,
    nexus_unstarted: int = 0,
    minerals: float = 9999.0,
    nexus_price: float = 400.0,
    tech_saving: bool = False,
    tech_price: float = 150.0,
    carrier_saving: bool = False,
    carrier_price: float = 350.0,
    immortal_saving: bool = False,
    immortal_price: float = 275.0,
) -> str | None:
    """O135(o134-vh-zerg-timing 0-5 尸检):产出永不暂停 —— 暂停型预留体系
    整体证伪。纯逻辑,可单测。

    O126-② 的六道预留闸(fleet/transition/tech/sg/gw reserve)都在「暂停
    SpawnController 攒钱」,但建筑注册侧(塔/水晶/农民)不在同一管辖 ——
    攒钱期间建筑把钱吃光 → 矿恒 <100 → 叉子保底判据翻假 → 预留继续停产
    = 兵营空转/死锁循环/产出真空(o134 局1:42 农 2 矿 2 GW 就绪,
    t=542 仅 3 叉;40 轮里这类 bug 出了至少 6 次变体)。
    语义反转:SpawnController 永动,钱永远先喂产线;「攒钱」只暂停建筑
    注册(塔>cap/水晶非应急/科技追加/扩张 —— F2/水晶侧闸门保留,各有
    can_afford 守卫),建筑用余钱。
    仅剩 rebuild_nexus(基地清零应急,没经济一切免谈)可暂停产兵;
    威胁急性窗的应急由 first_zealot_sprint/_sprint 管水晶/农民侧,不停产兵。
    返回暂停原因字符串(簿记用),None = 照常产。

    O216c(o216b game_01 实证):Zerg Timing 下二矿是生存前提,但 ground_spawn
     zealot(100 矿/个)把 Nexus 资金窗吃光,单矿经济撑不到二矿落地。
     仅当 Nexus 已派工但**尚未开工**、且存款买不起 Nexus 时暂停产兵,
     一旦 Nexus 开工(已付 400 矿)或存款够 400 矿立即恢复。
     避免 O216b 的 300-400 矿缓冲被 zealot 反复吃回 200 以下。

    O224(o220-lane1 game_04 实证):Zerg Timing transition 期 zealot 持续吃掉
     SG(150)/FB(300) 资金窗,SG 拖到 ~500s、首舰 620+,被 43-supply 波碾穿。
     防御已立(调用方保证 t≥240+塔≥2)且 SG/FB 缺失买不起时暂停地面产兵攒钱,
     买得起即恢复(同 O216c 的自校正语义,SG→FB 两段式接力)。
    """
    if rebuild_nexus:
        return "rebuild_nexus"
    if (
        is_zerg_timing
        and expand_holding
        and nexus_unstarted > 0
        and minerals < nexus_price
    ):
        return "zerg_timing_expand_reserve"
    if (
        is_zerg_timing
        and tech_saving
        and minerals < tech_price
    ):
        return "zerg_timing_tech_reserve"
    # O240(o237 双 lane game_05 实证):O239 点航母被 can_afford 的 350 矿
    # 永假封印——矿恒 <100 的经济里航母永远点不起。气烂 ≥800 且航母配比
    # 落后(航母 < 暴风/6)时暂停产线攒 350,攒够即恢复(O239 同帧点舰)。
    if (
        is_zerg_timing
        and carrier_saving
        and minerals < carrier_price
    ):
        return "zerg_timing_carrier_reserve"
    # O245e(o245-lane1 game_04 实证):SpawnController 优先级竞争中不朽者
    # (p0 同档、dict 序在后)每帧让位暴风,零产出;机械台就绪且敌地面 ≥6
    # 且不朽 <4 时停产攒 275,直产通道(O245e 训练块)同帧消化。
    if (
        is_zerg_timing
        and immortal_saving
        and minerals < immortal_price
    ):
        return "zerg_timing_immortal_reserve"
    return None


def gateway_chain_after_first_zealot(
    gateways_have: int, first_zealot_seen: bool
) -> bool:
    """O126-①(o125 局1 实证):GW2+ 是否该等首叉。纯逻辑,可单测。

    局1:GW2(150)在 GW1 完工前 10s 抢走矿,首叉从 ~163 拖到 ~178
    (再叠加 forge 的 137)——GW 链优先级不得高于「现役兵营的首叉」。
    GW1(have=0)不受此闸(开局刚需);首叉在产/出场后 GW2+ 恢复正常。
    """
    return gateways_have >= 1 and not first_zealot_seen


def fleet_transition_strong_exit(
    defense_score: float,
    enemy_visible_supply: float,
    clear_for: float = 0.0,
    min_defense: float = 25.0,
    margin: float = 10.0,
    clear_needed: float = 30.0,
) -> bool:
    """O100-②/O108/O110-②:退出门放宽 —— 防御达标 + 领先敌情 + 清净深度。
    纯逻辑,可单测。

    「家 40 格无敌 30s」(fleet_transition_ready)对 60-90s 一波的持续骚扰局
    永假 → 永远转不了舰队。defense_score 调用方口径:地面兵×2 + 就绪塔×3
    + 就绪电池×2。阈值依据(o99 局1 实测):站稳期 ≈ 8-10 叉 + 4-5 塔 ≈
    28-35 分,取 min_defense=25;敌波间隙可见 supply ≤14 → margin=10 放行,
    波到脸上(28-45 supply)不放行 —— 防「带波转舰队瞬间被打死」。
    fleet_at 时间闸在调用方保留。
    O110-②(o108 局2/局4 实证):加 clear_for ≥ clear_needed(30s)——
    strong 通道在 score 一够就放,可能落在波前 40s(退出即撞 440 波);
    要求清净深度 = 退出只落在波间隙深位,舰队链换来整段 ~190s 波周期。
    """
    return (
        defense_score >= min_defense
        and clear_for >= clear_needed
        and defense_score >= enemy_visible_supply + margin
    )


def fleet_rebuild_window(fleet_transitioned: bool, first_fleet_seen: bool) -> bool:
    """O101-Y/Z(o100 局4 实证):转舰队后 → 首舰出场前的「舰队重建窗」。
    纯逻辑,可单测。

    局4:480 准点转舰队,但 cyber 没建(过渡期矿恒 <150 买不起)、SG 被
    农民 13→20(350 矿)+电池(100)挤到 t=605 才落地 —— 重建窗内一切
    非舰队开销都是凶手。窗内语义:农民让位(≥14 停训)、兵营保持 cap
    (地面保底产能,应对 590-650 波),首舰出场即关窗(自校正)。
    """
    return fleet_transitioned and not first_fleet_seen


def gateway_yields_tech_slots(
    gateways_have: int, free_3x3: int, reserve: int = 2, min_gw: int = 2
) -> bool:
    """O112-①(o110 局1/3/4 实证):兵营给科技槽让位判据。纯逻辑,可单测。

    主基 3x3 槽被 GW×3+cyber+forge 物理占满后,SG/FB 无家可归(落位
    持续 None,watchdog 自救三招全败)。GW1/GW2 是开局刚需不让;
    GW3+ 在主基 3x3 余量(available 且非预约)< reserve 时让位 ——
    给 cyber/SG/FB 留位。free_3x3 由调用方读 placement 簿记计算。
    """
    return gateways_have >= min_gw and free_3x3 < reserve


def tech_goes_to_expansion(fleet_phase: bool, other_bases_ready: int) -> bool:
    """O112-②(o110 局1/3/4 实证):转舰队/重建窗科技(SG/FB)落分矿判据。
    纯逻辑,可单测。

    主基槽位被塔/兵营占满是必然(rush 局主基铺满塔),分矿槽位全新。
    有其他就绪基地 → SG/FB 优先落那边;没有 → False(主基硬挤 +
    watchdog 自救链)。
    """
    return fleet_phase and other_bases_ready >= 1


def pick_slot_anchor(slots: list, base_xy: tuple) -> tuple | None:
    """O113-①(o112 局2/局5 实证):贴空闲 3x3 槽落水晶的锚点选择。纯逻辑,可单测。

    局2 watchdog 簿记实锤:主基 3x3 余 20/总 25 —— 槽根本没占满,
    是带电槽为零(水晶全锚在坡口/矿线,生产区无电);泛泛补水晶
    (production=True 默认槽)落点不覆盖空闲槽,自救空转。
    slots = [(x, y, free), ...](调用方读 placement 簿记);
    选离基地最近的空闲槽 → 水晶贴它建 = 槽位通电。无空闲槽 → None。
    """
    free = [(x, y) for x, y, ok in slots if ok]
    if not free:
        return None
    return min(free, key=lambda p: (p[0] - base_xy[0]) ** 2 + (p[1] - base_xy[1]) ** 2)


def fleet_no_recall_threshold(
    fleet_count: int, base: int = 14, overwhelming: int = 25, fleet_gate: int = 12
) -> int:
    """O113-②(o112 局4 实证):舰队压倒性时,推进中的基地遇袭召回阈值。
    纯逻辑,可单测。

    局4:22-29 暴风在 1100-1500 被召回跑步机钉死 —— 对面波次喂食
    (15-20 地面/波),O64 召回阈值 14 每波必触发,暴风腿短(2.8)来回
    跑,500s 龟缩靠耗赢。舰队 ≥fleet_gate(12,临界质量)时阈值抬到
    overwhelming(25):塔+电池+地面能消化的波不召回,换家比回防快;
    真正的大波(25+)照回。不满临界质量 → 原阈值 14 不变。
    """
    return overwhelming if fleet_count >= fleet_gate else base


def f2_dispatch_guard_bypassed(defense_urgent: bool, cannons_ready: int) -> bool:
    """O114-③(o113 局3/局4 实证):防御紧急且 0 塔时,F2 注册跳过
    dispatch_viable 资金预估守卫。纯逻辑,可单测。

    局3:presumed 65 准时启动,但守卫(矿+收入×5s ≥ 塔价 150)把 F2 整段
    拦到 t=110 —— forge 133 才落地、首塔 185 vs 波次 160,45s 全丢在这。
    紧急窗内守卫反智:工人钉点等钱(O11 超龄撤回、下帧重派)比晚 45s
    注册划算。defense_urgent = rush确认/过渡/presumed(调用方合成)。
    """
    return defense_urgent and cannons_ready == 0


def builder_borrow_ok(gathering_empty: bool, gas_stopped: int) -> bool:
    """O116-②(o115 局3 实证):建造工借用判据。纯逻辑,可单测。

    局3:钱够槽够电够,炮塔 218→266 死也不建 —— GATHERING 池被协防
    (≤10)+停气(6)抽干,select_worker 恒 None,BuildStructure 静默
    返回 False。池空时从停气池借(塔/科技 > 短期停气;借出即从停气
    台账摘除,rush 解除的回气循环不会把它从建造点拽走)。
    """
    return gathering_empty and gas_stopped > 0




def pick_walk_patch(patches: list, threat_xy: tuple) -> tuple | None:
    """O118-③(o117 局1 实证):mineral-walk 目标选择。纯逻辑,可单测。

    旧版「离自己最远的矿簇」会把农民径直送进狗嘴(狗在农民与远簇
    之间 = 穿狗群,协防 30s 死 10)。改为离**威胁**最远的矿簇 ——
    农民沿矿线背狗侧走位,矿碰撞体积只卡狗不卡己。patches=[(x,y),...],
    空 → None(调用方回落蹲点)。
    """
    if not patches:
        return None
    return max(
        patches,
        key=lambda p: (p[0] - threat_xy[0]) ** 2 + (p[1] - threat_xy[1]) ** 2,
    )


def fleet_supply_buffer_needed(
    fleet_phase: bool, supply_left: float, buffer: float = 8.0
) -> bool:
    """O109-①(o108 局3 实证):舰队期人口 buffer 判据。纯逻辑,可单测。

    暴风 6 人口/艘,ares AutoSupply 的默认阈值(~2-4)在舰队产能爬坡期
    必卡(局3 supply_block×3:89/90、86/82 反超)。supply_left ≤ buffer
    且处舰队相关阶段(过渡/重建/舰队期)→ bot 侧直接补水晶,不等
    AutoSupply 的紧阈值。fleet_phase 由调用方按 transition 流派门控。
    """
    return fleet_phase and supply_left <= buffer


def fleet_stargate_reserve(
    fleet_seen: bool, sg_have: int, sg_target: int, can_afford_sg: bool
) -> bool:
    """O109-②(o108 局3 实证):首舰后 SG 爬坡攒钱预留。纯逻辑,可单测。

    局3:SG 恒 2 座 600s+,暴风 5→6 用了 129s —— 矿贴 0(每艘 150 矿
    即产即吃),追加产能的矿门槛 250 恒不触发,SG3 永远排不上。
    首舰已出 + SG(已有+在建) < 气体闸目标 + 买不起 → SpawnController
    暂停攒钱(产能复利:1 艘暴风晚 43s,换此后 +50% 产能);买得起即解除,
    由 _build_extra_production 的 0 门槛接力拍出。
    """
    return fleet_seen and sg_have < sg_target and not can_afford_sg


def rush_blocks_reserve(rush_active: bool, enemy_near: int) -> bool:
    """O151-①(o150-zerg-power 局2 实证):攒钱预留的 rush 否决改急性口径。
    纯逻辑,可单测。

    局2:235 的 5 兵接触 → rush_active latch(60s 无接触才解),扩张攒钱
    预留(transition/fleet_expansion_reserve 都以 rush_active 否决)被压住,
    塔照建照吃,Nexus 拖到 546。rush 但家 40 格无敌(波间隙/骚扰尾声)
    = 非急性 → 允许预留;敌在家 = 急性 → 照旧不预留(保命优先)。
    """
    return rush_active and enemy_near >= 1


def transition_expand_reserve(
    transition_active: bool,
    expand_ready: bool,
    can_afford_nexus: bool,
    threat_active: bool,
    rush_active: bool,
) -> bool:
    """O105-①b(o104 局2 实证):过渡期站稳想开矿但买不起 → 出兵暂停攒钱。
    纯逻辑,可单测。

    局2:t=360 起站稳(13叉4塔),但矿恒 0-170 被第 14+ 叉/塔吃光,
    Nexus 400 永远攒不出 —— 扩张门(O100-①)形同虚设。站稳 = 防线已够,
    暂停的是溢出产能(第 14+ 个叉)不是防线;rush/threat 期不预留
    (保命优先);买得起即解除(自校正,无 latch)。
    """
    return (
        transition_active
        and expand_ready
        and not can_afford_nexus
        and not threat_active
        and not rush_active
    )


def stargate_double_opener(
    fleet_transitioned: bool,
    first_fleet_seen: bool,
    stargates: int,
    minerals: float,
    vespene: float,
    cost_m: float = 200.0,
    cost_g: float = 150.0,
) -> bool:
    """O105-③a/O115-①:舰队重建窗星门双开判据。纯逻辑,可单测。

    局2/局5(o104):转舰队后 SG1→SG2 串行亏一整个建造周期(~45s)。
    已有/在建恰好 1 座且钱够 → 立即补第二座。
    O115-①(o114 局3 实证):门 300/200 → 200/150 —— 局3 矿在 25-325
    振荡,300 档零触发;气烂 2000+ 的局 200/150 是务实档。
    """
    return (
        fleet_transitioned
        and not first_fleet_seen
        and stargates == 1
        and minerals >= cost_m
        and vespene >= cost_g
    )


def rebuild_extra_production_id(
    rebuild_window: bool,
    fb_present_or_pending: bool,
    stargates: int,
    sg_cap: int = 3,
) -> str:
    """O115-①(o114 局3 实证):重建窗追加产能选择。纯逻辑,可单测。

    局3:重建窗内追加产能一律 GATEWAY(O101-Z 地面保底)→ SG 恒 1 座,
    首舰(需 FB 就绪)没出窗户永不关,产能爬坡断档。修正:FB 已拍
    (present/pending)且 SG(已有+在建)< sg_cap → STARGATE(爬坡优先);
    否则 GATEWAY(地面保底)。过渡期(非重建窗)恒 GATEWAY。
    """
    if rebuild_window and fb_present_or_pending and stargates < sg_cap:
        return "STARGATE"
    return "GATEWAY"


def fleet_rebuild_cannon_cap(
    cannons: int, rebuild_window: bool, cap: int = 4
) -> int:
    """O105-③b/O106-②:舰队重建窗塔目标封顶。纯逻辑,可单测。

    O105 定 6(首舰前顶 1-2 波);O106(o105 局3 实证)回 4 —— 窗内电池×2+
    塔重建把 SG 的 150 矿挤了 110s(SG t=707 才落地),塔 5-6 座的钱必须
    先变 SG/FB:资金优先级 = cyber→SG→FB > 塔 5-6 > 溢出叉。窗关恢复原逻辑。
    """
    return min(cannons, cap) if rebuild_window else cannons


def fleet_tech_reserve(
    fleet_transitioned: bool,
    first_fleet_seen: bool,
    next_tech_missing: bool,
    next_tech_affordable: bool,
    threat_active: bool,
    rush_active: bool,
    tech_stalled: bool = False,
    voidray_pending_or_seen: bool = True,
) -> bool:
    """O106-②/O115-③/O122-①:舰队重建窗的科技链攒钱预留。纯逻辑,可单测。

    (O106/115 原义:下一件科技缺失且买不起 → 停产攒钱;威胁/rush/停滞
    解除见前。)
    O122-①(o121b 局1 实证):预留不得挡虚空填窗 —— 局1 SG 就绪后预留
    为 FB(300/200)攒资,把 VOIDRAY(150/100,37s)也掐死,波到脸时
    两头都没有。改为:至少一艘虚空已出/在产后才允许为 FB 停产
    (先有一艘能打的,再攒 FB)。voidray_pending_or_seen 缺省 True →
    旧签名行为逐位不变。
    """
    return (
        fleet_transitioned
        and not first_fleet_seen
        and next_tech_missing
        and not next_tech_affordable
        and not threat_active
        and not rush_active
        and not tech_stalled
        and voidray_pending_or_seen
    )


def transition_expand_after_first_wave(
    transition_active: bool,
    wave_seen_and_cleared: bool,
    cannons_ready: int,
    ground_army: int,
    min_cannons: int = 2,
    min_ground: int = 4,
) -> bool:
    """O122-②(o121b 系列实证):首波清除后立即开二矿判据。纯逻辑,可单测。

    transition_expand_ready 的清净秒数窗(8-12s)被波次节奏切碎,
    全系列触发率≈0;而「唯一出路 = 早扩张」(中骰局单矿 exit 必死,
    三个胜局全是安心扩张局)。改为:见过一波且当前已清 + 塔/地面达标
    → 立即开,不等清净秒数(波刚清 = 离下波最远,就是最好窗口)。
    wave_seen_and_cleared 由调用方维护(见过敌进家 40 格 ≥3 且当前为 0)。
    """
    return (
        transition_active
        and wave_seen_and_cleared
        and cannons_ready >= min_cannons
        and ground_army >= min_ground
    )


def resource_contested(threats_near: int, min_threats: int = 2) -> bool:
    """O39(司令观察):资源点(矿脉/气)是否被敌地面盘踞 —— 派农民过去=送死。
    阈值与 E6 回采滞回线(<2 才安全)同源。纯判据,可单测。"""
    return threats_near >= min_threats


def should_push_advantage(
    own_army_supply: float, enemy_visible_supply: float, margin: float = 15.0
) -> bool:
    """O44(o43 bench 实测):默认推进是否需要「决定性优势」。纯逻辑,可单测。

    carrier 流的惨痛教训(4 基地防下 6 波 68-85 supply 冲击却 60 分钟收不下比赛):
    波间隙默认追敌 → 新一波刷出 → 战斗模拟刹车半路拉回家 → 航母慢速撤退途中
    被腐化点名,推-撤 yo-yo 把舰队磨光。改为只有我方 army supply ≥ 敌可见 + margin
    才推进;否则蹲防守锚点让对面继续往塔阵里送(消耗战我方 4 矿经济必胜)。
    敌可见为 0(被榨干/迷雾)→ 推进(收割)。
    """
    if enemy_visible_supply <= 0:
        return True
    return own_army_supply >= enemy_visible_supply + margin


def carrier_push_safe(
    carriers: int, enemy_hard_aa: int, per_carrier: float = 1.5
) -> bool:
    """O45(Harder game_01 实证):航母舰队推进的对空安全线。纯逻辑,可单测。

    O44 纯 supply 优势的推进在 Harder 撞墙:14 航母推进 77-supply 虫族
    (腐化+飞蛇为主的硬对空) → 舰队团灭、经济再好也翻不回来。
    硬对空口径(调用方算):CORRUPTOR/VIKINGFIGHTER/PHOENIX/VIPER —
    腐化/维京/凤凰是 counter,飞蛇 Abduct 点名航母(不能对空但比腐化更致命)。
    enemy_hard_aa ≥ carriers × per_carrier → 不推(继续蹲塔消耗,等对空变薄)。
    """
    return enemy_hard_aa < carriers * per_carrier


def natural_predefense_allowed(
    nexus_started: bool,
    minerals: float,
    nexus_cost: float,
    defense_cost: float = 350.0,
    buffer: float = 25.0,
) -> bool:
    """O205:分矿 Nexus 落成前是否允许预铺 2 炮+1 电池。纯逻辑,可单测。

    Nexus 已开工 → 允许(塔 29s 比 Nexus 71s 先完工,预派不抢基金)。
    Nexus 仅 pending 未开工 → 必须保证 Nexus 基金不被抽干才允许预派:
    当前矿 ≥ Nexus 造价 + 防御预估 + buffer。
    """
    if nexus_started:
        return True
    return minerals >= nexus_cost + defense_cost + buffer


def fleet_recall_target(
    bases: list[tuple[float, float]],
    enemies: list[tuple[float, float]],
    min_threat: int = 6,
    radius: float = 15.0,
) -> tuple[float, float] | None:
    """O205:空军回防目标 —— 任一基地 radius 格内敌地面 ≥min_threat 时返回该基地坐标。
    纯逻辑,可单测。多基地受威胁时返回最靠前(调用方已按主→分排序)的受威胁基地。
    """
    for bx, by in bases:
        n = sum(
            1
            for ex, ey in enemies
            if (ex - bx) ** 2 + (ey - by) ** 2 <= radius * radius
        )
        if n >= min_threat:
            return (bx, by)
    return None


def rush_deadzone_active(hard_cleared_at: float | None, now: float, deadzone: float = 60.0) -> bool:
    """O205:舰队成型后硬解 rush_active 后 60s 内不再因敌兵重新进入 full rush-lock。
    纯逻辑,可单测。
    """
    return hard_cleared_at is not None and now - hard_cleared_at < deadzone


def idle_builder_fuse_exempt(sid_name: str, critical_ids: set[str] | None = None) -> bool:
    """O205:idle_builder 5s 熔断豁免名单。纯逻辑,可单测。

    关键防御链(forge/首塔/GW1)、基地、FleetBeacon 在资金窗口紧时允许驻点等钱,
    不被 5s 熔断误伤。
    """
    if critical_ids is None:
        critical_ids = {"FORGE", "PHOTONCANNON", "GATEWAY", "NEXUS", "FLEETBEACON"}
    return sid_name in critical_ids
