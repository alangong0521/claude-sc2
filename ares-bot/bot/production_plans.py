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


def unknown_zt_floor_cap(now: float, visible_enemy: int, wave_incoming: bool) -> int:
    """O314-③(o313b game_02/03 实证):ZT unknown 死窗叉 cap 波窗内放开。纯逻辑,可单测。

    O255-③ 的 cap 3(死窗只要矿耗叉子省气)与 O298-③ 的钉点 floor 全停,
    在 O312 早二矿(241-265s 落成)落地后变成绞索:game_02/03 二矿已落,
    304s 波(敌 20-27)到脸时叉 cap 仍 3 → 我 11-13 supply 对 20-27,
    分矿 373-409s 失守。波窗(t≥240)且敌可见 ≥4 → cap 8(pre_fleet
    max 全量,叉子是此时唯一的矿耗战力);wave_incoming 保持 5(O279)。
    O316-①(o315b game_01 实证):cap 3 全程也是枷 —— 241s 银行 485
    叉仅 2(钱在,cap 锁死),波前(240s 敌未可见)攒不出守波兵力;
    常态 3→5(多 200 矿叉钱,银行数据证明付得起),波窗 8 不变。
    """
    if now >= 240.0 and visible_enemy >= 4:
        return 8
    return 5


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


def worker_transfer_count(
    src_workers: int,
    src_target: int,
    dst_workers: int,
    dst_target: int,
    max_move: int = 4,
) -> int:
    """O266(司令观察):满载基地 → 欠饱和新矿的农民调拨量判据。纯逻辑,可单测。

    司令观察:主基农民 16+ 满载,新分矿只有 2-3 个 —— ares ResourceManager
    只给「未指派」农民派矿点,且矿线按 2/矿点封顶(主基矿线恒 ≤16,
    「超目标」永不成立 —— 首版用超额判据全程零触发,o266 实证)。
    改**均衡化**(人类 maynard 手法):两基地矿线人数差 ≥4 → 调差额一半,
    单批 ≤max_move,不超过目标基地缺口;源基地短缺的由新训农民回填。
    """
    gap = src_workers - dst_workers
    if gap < 4:
        return 0
    return min(gap // 2, max(0, dst_target - dst_workers), max_move)


def worker_last_stand(
    enemy_ground_near: int,
    cannons_near: int,
    ready_townhalls: int,
    threat_or_rush: bool,
    overwhelm_base: int = 6,
    overwhelm_per_cannon: int = 4,
) -> bool:
    """O256-①/O268-④:主基决死协防判据。纯逻辑,可单测。

    o255 全 9 局同一死因:280-350s 波(9 蟑螂+11 狗 ~20 单位)进主基,
    E6 被两道闸挡死(rush 期主基不撤 + 单基地无处可撤 target=None),
    22-26 农民白死(每局 →5-10),经济断气。算账:22 农民(≈100dps)
    + 4 塔(64dps)对 9 蟑螂是赢面,白死才是输面 —— 塔已被压垮
    (≥overwhelm)且无处可撤时,农民拉去塔下协战比站着被屠强。
    O268-④(4+2×塔 放宽)o269 双 lane 0-10 速败实证**回退 6+4×塔**:
    协战触发太早 = 农民提前离矿送死,崩得比不协战还快。
    O310-③(收紧 10+4×塔)o310b Harder 0/5 实证**回退 6+4×塔**:
    少拉/不拉 = 基地更快掉(game_03 分矿 317s 失守),塔1-2 区
    农民 micro 调不出胜负 —— 防御总量才是缺口(O311 转向)。
    """
    return (
        threat_or_rush
        and ready_townhalls <= 1
        and cannons_near >= 1
        and enemy_ground_near
        >= overwhelm_base + overwhelm_per_cannon * cannons_near
    )


def last_stand_demand_cap(enemy_ground_near: int) -> int:
    """O313-②(o312b game_03 实证):决死协防首批拉人需求封顶。纯逻辑,可单测。

    敌 10 地面塔 1 拉出 20 农民(2 倍过拉),10s 内 20 人全灭 ——
    1v1 + 塔/电池输出已是优势交换比,超出敌数的部分是纯喂。
    封顶 max(4, 敌地面数):小股(≤4)仍拉出最低响应量。
    """
    return max(4, enemy_ground_near)


def worker_last_stand_hopeless(
    enemy_ground_near: int,
    cannons_near: int,
    hopeless_base: int = 14,
    hopeless_per_cannon: int = 6,
) -> bool:
    """O306-③(o291-o304 系列「农民骤减 7-9」实证):决死协防的白送上界。
    纯逻辑,可单测。

    敌地面 > 14+6×塔(2 塔对 26+ 地面)时,农民冲锋(+~100dps,10s)
    改变不了结局 —— 基地照丢且经济火种全灭,下一波必死(连胜局剖面
    都是农民活、基地可重建)。此线以上不冲锋,改穿矿游走甩包围
    (O104 实证微操),塔阵/舰队打输出,农民保命留重建火种。
    """
    return enemy_ground_near > hopeless_base + hopeless_per_cannon * cannons_near


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


def gas_to_minerals_needed(
    vespene: float,
    minerals: float,
    vespene_threshold: float = 500.0,
    mineral_threshold: float = 200.0,
) -> bool:
    """O358-②(o357 尸检):矿气倒挂停气转矿触发判据。纯逻辑,可单测。

    o357 实证:三局气峰 779/1184/2524,矿常年 5-300 —— 航母 350 矿、
    母舰 300 矿、塔 150 矿全卡矿,6 气满采 + 塔/水晶/地面兵全吃矿;
    o357a g3 母舰窗空开 60s(气 ≥400 成立但矿 <300 买不起),期间
    分矿塔被压、940s 掉四矿。O157 的停气(气 ≥600/矿 ≤300 触发)
    在矿 >500 即回气,锯齿震荡下气持续烂银行;本判据触发更高
    但解除更低(调用方滞回),把气农更久地按在矿簇上,把烂气换成
    母舰/航母缺的矿。复用 O346/O347 的停气通道(_GAS_STOP_ROLE
    role 切换),不新发明框架。解除由调用方滞回实现,本函数只管触发。
    O359-②(o358 六局尸检):阈值 800/300 → 500/200 —— o358b g2 实测
    倒挂区间是气 712-1118/矿 5-250(1076-1201s 持续 124s),气 800
    线在窗口前段(气 712-767 而矿 55-195)恒假,触发被推迟 ~20s 且
    边界抖动;500/200 直接覆盖实测倒挂带。滞回解除同步降到气 <350
    (调用方),与触发档拉开 150 缓冲防抖动。
    """
    return vespene > vespene_threshold and minerals < mineral_threshold


def gas_pull_thresholds(
    zerg_timing: bool, now: float, early_until: float = 360.0
) -> tuple[float, float]:
    """O362-⑤(o361b 尸检):停气转矿阈值的 ZT 早窗档。纯逻辑,可单测。

    o361b lane 气银行 1500-2100 vs 矿常年 <100 —— O359-② 的 500/200
    触发太晚(气要烂到 500 才动,前期气需求低、矿是命)。ZT 且
    t<early_until → 阈值降 (气>300, 矿<150),把气农更早按回矿线;
    t≥360(舰队链开始吃气)保持 500/200。返回 (气阈值, 矿阈值),
    触发(gas_to_minerals_needed)与解除(gas_to_minerals_released
    的气档)共用,防「触发 300/解除 <500」单帧振荡。
    O363-④c(o362b g1 实证):早窗矿档摘掉 —— 「气>300 且 矿<150」
    并联在矿不低时气照囤(g1 气峰 684 零舰队:矿 200-400 振荡期
    触发恒假);早窗舰队科技未起、气本无消费者,气 >300 即停,
    矿档 +inf(恒真)。解除档由 gas_to_minerals_released 的 250
    滞回统一管,不在本函数。
    O366-②a(o365 双 lane 尸检):ZT 早窗气档 300→250 —— o365 六局
    矿常年 <200、气溢出 300-1700,星门 257-269s 就闲置:气要烂到
    300 才停,250-300 这段(≈2 个气农 40s 的死钱)正是矿枯窗;提前
    到 250 触发,与解除档(气 <250)贴边 —— 触发即停、气压回 250
    下才放人回气,滞回靠「停气侧只进不出」的实现(触发后 role
    脱离 Mining)而非阈值差。非 ZT (500,200) 不动。
    """
    if zerg_timing and now < early_until:
        return (250.0, float("inf"))
    return (500.0, 200.0)


def early_gas_overflow_pull(
    now: float,
    vespene: float,
    minerals: float,
    fleet_tech_ready: bool,
    window_start: float = 150.0,
    window_end: float = 420.0,
    vespene_threshold: float = 400.0,
    mineral_threshold: float = 250.0,
) -> bool:
    """O327-①(o326 双 lane 尸检):早窗气烂抽矿判据。纯逻辑,可单测。

    o326a 全 5 局 225-338s 气体已烂银行 472-876(6 个气农在产死钱),
    同期矿物恒 <200 —— Nexus(400)/农民(50)/塔(150) 全被矿物卡死,
    二矿拖到 518-647s(胜线 ≤310s),终局经济差 1.5×+。舰队科技(FB)
    就绪前气体无消费者,早窗气 ≥400 且矿 ≤250 时把气农抽回矿线:
    主基矿线 16/16 溢出后仍有 ~1/3 效率,窗口期(150-420s)累计
    ~+400 矿 ≈ 一个 Nexus。FB 就绪(舰队开始吃气)或出窗即解除,
    由调用方滞回(气 <200)复位,不棘轮。
    """
    if fleet_tech_ready:
        return False
    if not window_start <= now <= window_end:
        return False
    return vespene >= vespene_threshold and minerals <= mineral_threshold


def expand_pin_workers_ok(workers: int, bases: int, now: float) -> bool:
    """O327-②(o326 尸检+司令观察):扩张钉点的农民门槛。纯逻辑,可单测。

    旧门槛「农民 ≥16×基地+8」对 2 基地局 = 40 农;但败局农民峰值
    仅 22-28(波次收割 + 停产闸),40 永远等不到 → 三矿永不开,
    20 分钟仍 2 矿,经济差被滚雪球(司令观察实证)。2+ 基地放宽:
    农民 ≥26 即可钉;还等不到则 t≥600 时间兜底 —— 多一个 Nexus
    本身就是农民产能 ×1.5(波后回血翻倍),比攒农更治本。波间隙
    /无敌/矿 ≥350 守卫由调用方保留,不在本判据内。1 基地首扩的
    24 农门槛不变(O311-③ 的 24→20 已证伪,不在此复试)。
    """
    if workers >= 16 * bases + 8:
        return True
    return bases >= 2 and (workers >= 26 or now >= 600.0)


def mothership_economy_ok(bases: int, workers: int) -> bool:
    """O327-③(o326a 尸检):母舰训练的经济门。纯逻辑,可单测。

    母舰 300/300 + 占 Nexus 队列 ~71s(期间零农民)。o326a 母舰
    @811s 下水时全 5 局 2 基地 22-28 农、矿恒 <250 —— 这 300 矿
    正是 Nexus/农民/塔的资金窗,母舰成了压垮经济的最后一根。
    3 基地运转或农民 ≥36(2 基地接近硬饱和)才负担得起这张
    「舰队保命符」;达不到就先补经济,舰队靠电池/塔撑。
    """
    return bases >= 3 or workers >= 36


def sg2_pin_economy_ok(bases: int, minerals: float) -> bool:
    """O327-④(o326a vs o325a 对照):SG2 钉点让位二矿。纯逻辑,可单测。

    O326-② 的 SG2 critical 钉点(FB+气400 即触发,~400-500s)与
    二矿 Nexus 同资金窗:150 矿被 SG2 抢走后 Nexus 排队更晚,
    o326a 二矿均值 ~576s(样本 647/518/563)vs o325a ~503s
    (458/546/631/378),双双远离 ≤310s 胜线。2 基地已运转则
    SG2 随便拍(双 SG 的黄金窗收益不变);仍单基地时要求矿 ≥550
    —— 拍完 SG2 还剩 400 给 Nexus,不挤占扩张资金窗。
    O333-④(o332b game_04 实证):矿 ≥550 替代项去掉 —— 首扩驻点
    等钱期间矿过 550 是常态(收入没地方花),SG2 在 346s 放行 =
    又一次插队抢等钱中的 Nexus;只认 bases≥2(含在建,Nexus
    真开工)。minerals 参数保留不再入判据(向后兼容签名)。
    """
    return bases >= 2


def zt_fast_expand_pin(
    now: float,
    minerals: float,
    townhalls: int,
    nexus_in_flight: int,
    rush_confirmed: bool,
    at: float = 100.0,
    cost: float = 475.0,
    first_cannon_ready: bool = True,
    cannon_window_end: float = 330.0,
    cannon_reserve: float = 150.0,
) -> bool:
    """O329-②(司令 2026-08-18 拍板):速二矿钉点判据。纯逻辑,可单测。

    电脑 VeryHard Zerg 二矿 119-150s(录像实测,scripts/replay_bases.py),
    我方 377-500s 是经济差滚雪球的起点;t≥at 且矿够即拍口袋矿
    (O328 选址),开动 ≤120s 向电脑看齐。rush 确认 = fuse:不速开,
    走旧防御先行路径(O251 硬饱和钉点 280s+ 兜底)。与 O216i 的
    「首塔就绪才开矿」不冲突:本钉点独立于 _want_dynamic_expand,
    防御由 O329-③ 分矿预置塔链随 Nexus 并行到位。
    O330-①(o329a game_01 实证):门槛 400→350、at 105→100 ——
    矿门取造价全值时,opener 后续步(16叉/18forge/19core)在攒钱
    窗内持续抽水,矿永远摸不到 400,钉点整局哑火(O251 361s 兜底
    才开);350 近可负担门 + 驻点等钱,走位 ~15s 到账即开工。
    O343-①(o341/o342 累计 8 局实证):350→475 —— 350 门在 ~104s
    早钉,走位窗(104-190s)恰是 opener 流水高峰(3 水晶+10 农民
    +forge ≈800 矿),工人到位银行 <400,ares 等 ~30s 取消,在途
    1→0 反复蒸发,开工拖到 466-759s;475 = 造价 400 + 走位窗
    buffer 75(与 _preposition 同判据,o335 胜局 212-233s 开工
    实证有效),钉点 ~140-160s、到位即开工 ~170-190s。
    O358-⑤(o357 尸检):首塔资金优先于二矿 —— o357 实证首塔落成
    281-365s vs ZT 首波 280-330s 零裕度,塔资金被 233-237s 的
    二矿挤占(g1 塔链派工已出却干等 120s)。首塔未落成且 t<330
    (首波窗)时矿门抬高到 造价 400 + 塔 150 = 550:Nexus 吃掉
    400 后账上必剩 ≥150 给首塔;首塔落成或出窗(≥330s,首波已
    到、塔链命运已定)后回 475 原门。验收口径:左上首塔 <300s。
    """
    _gate = (
        cost
        if first_cannon_ready or now >= cannon_window_end
        else 400.0 + cannon_reserve
    )
    return (
        townhalls == 1
        and not rush_confirmed
        and nexus_in_flight == 0
        and now >= at
        and minerals >= _gate
    )


def zt_cannon_pending_probe_yield(
    now: float,
    cannon_pending: int,
    workers: int,
    window_end: float = 330.0,
    min_workers: int = 20,
    nexus_in_flight: int = 0,
) -> bool:
    """O359-③(o358 六局尸检):塔等钱期探机让位(150 矿短窗预算保护)。纯逻辑,可单测。

    o358 实证:O358-⑤ 的 Nexus 矿门 550 在钉点帧是生效的(5 局统一
    在矿 ~545-560 摸到 550 才放行,233-235s),但 O341-① latch 让
    派工在后续帧按 EC 可负担价(400)执行 —— Nexus 一拍账上只剩
    ~65-165,之后探机 50/个+水晶 100/根持续抽水,塔链工人干等:
    o358a g1 塔链 234s 派工已出、342s 首塔才落成(干等 ~100s,
    305-309s 致死波零塔)。门的语义是「Nexus 吃掉 400 后账上必剩
    ≥150 给首塔」,但这 150 没有任何人守护。本判据 = 单建筑 150
    矿的短窗口预算保护(章程明确不算全局面资金冻结):首波窗
    (t<window_end)内有塔在 building_tracker 等钱(已派工未放置)
    且农民 ≥min_workers(O146-① 的 16 农 floor 在上游调用方,
    双闸不打架)时,探机停训让位;塔放置(pending 归零)或出窗
    自动解除(自校正,无 latch)。O359-⑤ 的第二塔共用本判据,
    与 O358-⑤ 的 550 门是同一笔 150 预算的两端,不互相抢。
    O360-⑤(o359a 尸检):① min_workers 16→20 —— o359a g1 实证
    16 农线把扩张期农民冻在 16-18(84-204s),二矿拖到 526s,
    掐死的是经济本身;② Nexus 豁免 —— Nexus 在途/开工中
    (nexus_in_flight>0)不触发,扩张期经济优先于塔的 150 短窗。
    """
    if nexus_in_flight > 0:
        return False
    return now < window_end and cannon_pending > 0 and workers >= min_workers


def zt_second_cannon_pin_ok(
    now: float,
    ready_cannons: int,
    cannons_total: int,
    window_end: float = 330.0,
) -> bool:
    """O359-⑤(o358 六局尸检):波前第二塔钉点判据。纯逻辑,可单测。

    o358 实证:305-309s 致死波(12-16 狗+5-9 蟑螂)三局一致,单塔
    守不住(o358b g1 塔 257s 落成照样穿、342s 塔被拆归零);六局里
    仅 o358a g3(首塔 149s)在 300s 前有 ≥2 塔,其余第二塔 325-378s
    或整局没有。首塔 245-257s 已能达成 → forge 就绪后首塔落成
    (ready ≥1)即钉第二塔(critical 同构 O333),t<window_end 窗口;
    总数(实体+在途)≥2 或出窗自动停(自校正,无 latch ——
    o358a g3 首塔 149s/二塔 189s 的局不会被重复钉)。资金由
    zt_cannon_pending_probe_yield 的 150 矿短窗预算保护配套。
    验收口径:300s 前 ≥2 塔。
    """
    return now < window_end and ready_cannons >= 1 and cannons_total < 2


def new_base_defense_pins(
    forge_ready: bool,
    cyber_ready: bool,
    cannons_near: int,
    cannons_in_flight: int,
    batteries_near: int,
    batteries_in_flight: int,
    cannon_target: int = 2,
    battery_target: int = 1,
) -> tuple[bool, bool]:
    """O363-①(o362a/o362b 尸检):新矿落地即配塔的钉点判据。纯逻辑,可单测。

    o362 最高频单一死法(6 局 2 局同死):新基地落成零塔裸奔 ——
    o362a g2 敌 4 地面 515s 抄二矿杀 19 农;o362b g2 同法 605s 杀
    16+18 农判死;o362b g3 四矿 522s target=0 被连抄三次。旧
    O337-① 守卫两处漏:① for 循环钉完第一个分矿即 break,3/4 矿
    整局没人管;② 30s 节流是全局单簿记,首矿吃掉节流后其余基地
    排队。判据本体抽纯函数:返回 (钉塔, 钉电池) —— 塔走 forge
    科技闸,电池走 cyber 科技闸;就绪+在途合并计数(防重钉),目标
    默认 2 塔+1 电池(fb_fund 同款 critical 钉点通道在调用方,
    threat 时该通道本就无视资金守卫,天然优先)。
    """
    pin_cannon = forge_ready and (cannons_near + cannons_in_flight) < cannon_target
    pin_battery = cyber_ready and (batteries_near + batteries_in_flight) < battery_target
    return pin_cannon, pin_battery


def sg_pin_expand_ok(
    townhalls: int,
    nexus_in_flight: int,
    now: float,
    hard_at: float = 360.0,
    exempt_at: float = 240.0,
) -> bool:
    """O330-③(o329b game_01 实证):SG 钉点让位扩张判据。纯逻辑,可单测。

    O329-① 新 opener 无首塔 → O323 SG 钉点的「口袋攒钱期让位」守卫
    (要首塔就绪才激活)整局失效,342-366s 连拍 4 次 SG(150/150)
    抢光二矿资金窗,单基地到死。2 基地运转即放行(舰队科技不拖,
    司令「重心升级科技」);仍单基地时硬时限 360s 后放行(防 O261
    死窗零对空的旧教训)。
    O332-③(o331a game_01 实证):放行口径去掉 nexus_in_flight ——
    「在途」含驻点等钱(game_01 Nexus 226s 钉点后等钱 145s),
    此时放 SG = 插队抢等钱中的 Nexus(297s SG vs 395s 才开工的
    Nexus);只认 townhalls≥2(含在建,Nexus 真开工)。
    nexus_in_flight 参数保留不再入判据(向后兼容调用方签名)。
    O363-③(o362a 尸检):t≥exempt_at 后「单基地硬时限/扩张优先」整段
    豁免 —— O362-③ 把时间门降到 240 后本判据成了连环门的下一环:
    SG 钉点 401s 仍要等 Nexus 派工同 tick 才放行(o362a g3),SG
    354-450s 全超 ≤300s 验收线。t≥240(cyber 就绪在调用方上游)
    后 SG 与扩张并行预算,不再排在 Nexus 之后;can_afford 门在
    调用方原样保留(买得起才派,派了即开工,O337-③ 教义)。
    """
    if now >= exempt_at:
        return True
    return townhalls >= 2 or now >= hard_at


def zt_sg_pin_time_ok(now: float, open_at: float = 240.0) -> bool:
    """O362-③(o361b g1 实证):ZT SG 钉点时间门 300→240。纯逻辑,可单测。

    o361b g1:build order runner 的 PROBE 步骤排到 10:00 才结束,星门
    只能排其后拖到 643s;舰队首舰固定在 ~425-475s 上线的硬约束下,
    ZT lane 必须 SG ≤300s 才有活路。bot 层钉点走独立通道(O323-②
    critical 派工,在 core_allowed/_expand_holding 早退之前),本就不被
    runner 的全局 holding 挡 —— 只需把时间门 300→240(diff 最小方案),
    can_afford 与 sg_pin_expand_ok(让位 Nexus 资金窗)原样保留。
    """
    return now >= open_at


def zt_zealot_yield(
    townhalls: int,
    rush_confirmed: bool,
    threat_active: bool = False,
    wave_incoming: bool = False,
    now: float = 0.0,
    hard_at: float = 240.0,
) -> bool:
    """O332-②(o331 尸检+司令 doctrine):二矿开工前零兵种判据。纯逻辑,可单测。

    司令 2026-08-18 战术:2 矿没建造开始前不出战斗兵种,防御完全
    交给塔+电池。o331 实证 opener 零叉后,bot 层 floor(unknown 死窗
    cap 3/波前 cap 5/O314 cap 8)在 Nexus 开工前照出 5-6 叉
    (500-600 矿),与主基塔链一起把 O329 钉点资金窗抽干(矿窗
    226s+ 才摸到 350,game_03/04 整局哑火)。Nexus 开工
    (townhalls≥2,含在建)或 rush 确认后恢复产叉。
    O333-③(o332b game_01/02 实证):threat 激活豁免 —— 钉点晚局
    (185-286s)波 288-304s 到脸时零叉零塔,主基 359s 被推平;
    敌压境时零兵种 doctrine 立即让位(rush fuse 同源)。
    O339-②(o338a game_05 实证):波预警豁免 —— threat 触发时敌已
    到门口(296s 敌 11 vs 我 2),此时才产叉 = 28s 折跃后 330s 才
    接战,晚 30s 被滚;_wave_incoming(O279 波预警,40-60s 提前量)
    即恢复产叉,波到脸时叉已列队。
    O340-②(o339a game_03 实证):时间硬线兜底 —— 侦查早死局预警
    不 latch、threat 接触(275.6s 敌 12 vs 我 1)才产叉 = 裸接;
    波 280-310s 必来是 40 局取证规律,t≥hard_at 无条件恢复产叉
    (此时 Nexus 资金窗早过,零兵种使命已完成)。
    """
    if rush_confirmed or threat_active or wave_incoming or now >= hard_at:
        return False
    return townhalls < 2


def zt_vacuum_buffer_caps(
    gateway_ready: bool,
    core_ready: bool,
    now: float,
    open_at: float = 120.0,
) -> tuple[int, int]:
    """O362-①(o361b Harder Timing 0/3 尸检):真空窗地面缓冲 cap。纯逻辑,可单测。

    o361b:ZT opener 零兵种闸(O332-② 叉 floor_cap=0)下 GATEWAY 68s 落成
    后空转 ~200s,首叉 165-277s;Timing 首波 281-305s(20-25 supply 狗+
    蟑螂)到脸时我方=2 塔+1 电池+2-4 叉,首波杀农 20+ → 全链条塌方
    (对照 o361a VH Power:首波 410-446s 时配方已就位直接弹开)。零兵种
    闸内开缓冲口:GATEWAY 就绪且 t≥open_at → 叉 floor 0→3(300 矿);
    core 就绪后追猎 floor 1(吃烂气,不抢矿窗)。返回 (叉 cap, 追猎 cap)。
    二矿开工(townhalls≥2)后 _o332_zyt 翻假,原闸自动恢复;rush/threat/
    wave/t≥240 豁免在 zt_zealot_yield 上游,不动。资金与塔链冲突时塔
    优先(塔链走 critical 钉点,叉走 SpawnController 普通 can_afford)。
    """
    if not gateway_ready or now < open_at:
        return (0, 0)
    return (3, 1 if core_ready else 0)


def main_defense_bank_fuse(
    minerals: float,
    nexus_started: bool,
    fuse_on: bool,
    on_at: float = 600.0,
    off_at: float = 400.0,
) -> bool:
    """O334-③(o333a game_03 实证):主基塔封禁的银行熔断。纯逻辑,可单测。

    O332-① 主基塔全程归零是为了保 Nexus 的 400 资金窗;但钉点派工
    哑故障局(game_03:186-350s 连续失败)银行烂到 1315、主基仍零塔,
    波 289s 到脸裸接 —— 此时钱不是瓶颈(400 早够),主基塔不抢
    Nexus 资金窗。矿 ≥on_at 且 Nexus 未开工 → 熔断开(主基塔放行,
    滞回 off_at 复位);Nexus 一开工立即复位(回 doctrine)。
    """
    if nexus_started or minerals < off_at:
        return False
    if minerals >= on_at:
        return True
    return fuse_on


def zt_defense_at_natural(
    nexus_in_flight: int,
    has_expansion: bool,
    rush_active: bool,
) -> bool:
    """O329-④(司令 2026-08-18 拍板):防御重心在 2 矿判据。纯逻辑,可单测。

    塔+电池聚在一起才有效 —— Nexus 在途/分矿存在时,建造槽先喂分矿
    堵口阵,主基塔归零(放弃主基分散铺塔:3 矿边 1-2 座零散塔电池 =
    敌一波推上高地的白捐,司令观战实证)。rush 激活或分矿全丢
    (无在途无落成)→ 自动回退主基防御(O81 rush 教义)。
    """
    if rush_active:
        return False
    return nexus_in_flight > 0 or has_expansion


def builder_release_exempt(rush_active: bool, defense_urgent: bool) -> bool:
    """O117-②(o116 取证实证):O11 钉点撤回的豁免判据。纯逻辑,可单测。

    E4c 的豁免只看 rush_active;但 presumed/早评 rush 的防御紧急窗里
    rush_active 常常还没置位(接触才确认)—— 塔工钉点等钱 6s 被撤回 +
    15s 重派冷却(O19)= 21s/轮的派工循环,首塔永远慢半拍。
    defense_urgent(rush确认/过渡/presumed,调用方合成)期同样豁免。
    """
    return rush_active or defense_urgent


def pin_deadlock_fuse(
    workers: int,
    active_pins: int,
    waiting_s: float,
    min_workers: int = 10,
    max_pins: int = 1,
    timeout: float = 60.0,
) -> bool:
    """O362-②(o361b g2 僵尸局实证):钉点死锁保险丝。纯逻辑,可单测。

    o361b g2:三农民 481-832s 轮流钉点等 FORGE 重建钱(单钉跨度
    188-320s),矿钉死 47 —— 2-3 农全钉点=零收入死锁(O324 runner
    也有卡死记录)。两道闸合一(返回 True=跳闸,调用方拦新钉点或
    释放旧钉点):
    ① 农 <min_workers 时全场钉点(active_pins 含本钉)上限 max_pins
       —— 小农经济局农民就是收入本身,2+ 钉点=零收入等钱永远等不到;
    ② 任一钉点等钱 >timeout 秒 → 强制释放(调用方清 tracker 让农民
       回采,30s 冷却后才允许重钉,防「放→钉→等→放」空转循环)。
    """
    if workers < min_workers and active_pins > max_pins:
        return True
    return waiting_s > timeout


def pin_repin_blocked(now: float, blocked_until: float | None) -> bool:
    """O363-②b(o362b g2 实证):O307 撤派工后的防夺回冷却判据。纯逻辑,可单测。

    o362b g2:开矿钉点等钱 290s —— O307 撤派工 4 次(255/317/393/460s),
    每次 30s 冷却一过就被同一钉点夺回,二矿拖到 498s(胜局 128/241s)。
    撤派工后给同型钉点打 60s 封锁(调用方写 blocked_until),期内禁止
    重钉:资金/科技链真正解锁一轮,而不是「撤→钉→等→撤」空转。
    None = 无封锁。
    """
    return blocked_until is not None and now < blocked_until


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


def sprint_timer_update(
    sprint: bool,
    since: float | None,
    false_since: float | None,
    now: float,
    exit_grace: float = 10.0,
) -> tuple:
    """O353-②(o352 六局尸检):defense_sprint 计时累计制(滞回退出)。纯逻辑,可单测。

    旧逻辑「单帧 _sprint=False 即 _sprint_since=None 重计」被叉子数量/
    敌近家的单帧抖动反复重置,o352 g1 从 200s 到 440s 连续 sprint=True
    而 sprint_age 从未触顶,60s max_age 逃逸阀形同虚设,农民被钉死 240s。
    改累计制:进入 sprint 记录起始时刻;中断不清零,须连续 exit_grace 秒
    不满足才清零(真退出);抖动期间 age 照累计,逃逸阀真正生效。
    返回 (new_since, new_false_since)。
    """
    if sprint:
        return (since if since is not None else now), None
    if since is None:
        return None, None
    fs = false_since if false_since is not None else now
    if now - fs >= exit_grace:
        return None, None
    return since, fs


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


def multi_expand_threat_ok(
    rush_active: bool,
    threat_active: bool,
    townhalls: int,
    now: float,
    visible_enemy_army_supply: float,
    own_army_supply: float,
) -> bool:
    """O352-②(o351 18 局尸检):多矿(3 矿+)扩张钉点的 threat 闸。纯逻辑,可单测。

    O344-② 的 rush∧threat 锁在持续挨打局把三矿钉点永久锁死——
    threat_response_active 是滞回 latch,波 60-90s 一波下近常真
    (18 局三矿 17 局从不开,唯一开出局=唯一胜局)。保留 rush∧threat
    锁,加两道旁路:
    - t≥480 时间兜底(O353-④ 从 600 下调 —— o352 六局尸检:t≥600
      触发时局已崩;与 fb_missing_expand_hold 的豁免同口径);
    - 闸内放宽解除口径一档:敌可见 supply < max(8, 我方×1.25) 即视为
      威胁已退(只影响本闸;全局 latch 不动,其他消费方行为不变)。
    选址级判定(_zt_enemy_near_expand_target)只覆盖首扩口袋矿,多矿
    钉点取最近矿点、口径不一致,故选本方案(实现最简单)。
    首扩(townhalls<=1)不在本闸管辖(O274-① 已去 rush 闸),恒放行。
    """
    if townhalls <= 1:
        return True
    if not rush_active or not threat_active:
        return True
    if now >= 480.0:
        return True
    return visible_enemy_army_supply < max(8.0, own_army_supply * 1.25)


def fb_missing_expand_hold(
    townhalls: int,
    fb_truly_missing: bool,
    supply_workers: int,
    now: float,
    workers_exempt: int = 28,
    time_exempt: float = 480.0,
) -> bool:
    """O352-②(o351 18 局尸检):FB 缺失锁扩张闸(含豁免)。纯逻辑,可单测。

    O57/o172/o175 的「townhalls≥2 且 FB 真缺失 → 不开矿」闸与 O344-②
    threat 闸串联,把三矿彻底锁死(FB 被拆重建期动辄 100s+,期间经济
    硬饱和也不许开矿)。加豁免:农民 ≥workers_exempt(硬饱和,不开矿
    经济无出路)或 t≥time_exempt(拖后期兜底)时不锁。返回 True = 锁定(不开矿)。
    O353-④(o352 六局尸检):豁免口径可达成化 —— 原 40 农/t≥600 触发时
    局已崩;农民 28+ 在 ~450s 就出现,比 40 农早 60-150s。默认豁免改为
    28 农 / t≥480(与 multi_expand_threat_ok 的 O353-④ 旁路同口径)。
    """
    if townhalls < 2 or not fb_truly_missing:
        return False
    if supply_workers >= workers_exempt or now >= time_exempt:
        return False
    return True


def forge_pin_affordable(
    minerals: float,
    price: float = 100.0,
    threat_active: bool = False,
) -> bool:
    """O352-③(o351 18 局尸检):forge 钉点近可负担门。纯逻辑,可单测。

    O333 钉点在 Nexus 开工帧 critical 派工,驻点工人 232-300s 反复等钱
    (钱被探机/GW2/SG/水晶同帧即时消费抢走),forge 落成迟到 237-354s;
    O349 看门狗只是重排等钱循环。矿 ≥门(原 150=forge 造价)才实际派工;
    矿不够不派工、不驻点、不设 tracker(避免看门狗误清)。
    与 O262-③ 的 350 门同构。
    O353-①(o352 六局尸检):威胁豁免 —— threat/rush 激活期矿恒 <150,
    门成永久锁(g3 到死无 forge,首塔 tech_not_ready 空转 142-185s)。
    威胁期免门恢复 critical 驻点行为:驻点等钱是对的,forge 是救命建筑;
    非威胁期保持矿门。
    O354-⑤(o353b game_01 实证):非威胁期矿门 150→100 —— 非威胁期矿
    254-380s 持续 50-95,150 门恒关,forge 拖到 361.6s;100 门在矿
    100-149 窗内即派工驻点(等钱到 150 自然开工),威胁期免门不动。
    """
    if threat_active:
        return True
    return minerals >= price


def zt_forge_pin_gate(
    gateway_placed: bool,
    now: float,
    minerals: float,
    min_t: float = 75.0,
    min_minerals: float = 200.0,
) -> bool:
    """O357-③(o356 尸检):ZT forge 钉点门 —— 确定性 forge-first。纯逻辑,可单测。

    o356 尸检:开局 forge 落点是 dice roll —— forge-first(104.5s,
    o355 胜局走这条)vs cyber-first(forge 等 O333 的 Nexus 钉点
    217-237s,o356a g3/o356b g3 走这条,首塔 301s+ 晚于 274-322s
    致死窗)。钉点不再干等 Nexus 开工:t≥min_t 即放行
    (forge_pin_affordable 的矿 ≥100 近可负担门不变,钱够下帧
    即钉),forge ≤150s 落成从 dice roll 变确定性。rush 墙
    fallback(threat/rush 激活免矿门)与 ms_window/capped 拦截不在
    本门语义内,不受影响。
    O358-①(o357 尸检,实锤 opener 回归):O357-③ 的
    「townhalls≥2 or t≥60」让 forge 在 60s 吃掉 150 矿,GATEWAY
    从 68.3s(o356 基线全部)右移到 104.5-132.6s,干等造 GATEWAY
    (g1 103.9s/g3 100.7s),CYBERCORE 116-120→168-180s、首叉
    180-225→261-265s、二矿 132-193→233-237s,首叉晚 40-80s 撞上
    ZT 280-330s 首波。o356b g2 证明 forge 104.5s 与 gateway 68.3s
    可兼得 —— 是门放太早,不是 forge-first 本身的代价。判据改
    「GATEWAY 已下单(实体或在途)or (t≥75 且矿 ≥200)」:GATEWAY
    下单前 forge 不抢 opener 资金;t≥75 且矿 ≥200(150 forge +
    50 余量,GATEWAY 已在产)兜底放行,防 GATEWAY 卡死局 forge
    永锁。验收口径:GATEWAY ≤75s 基线恢复 + forge 仍 ≤150s。
    O359-①(o358 六局尸检,事件簿+structures 时间线实锤):「下单」
    口径仍是假放行 —— o358b g2 事件簿 70.7s「idle_builder:农民
    干等3s(等钱造GATEWAY)」(GATEWAY 此时已 pending,门已开),
    但放置拖到 124.6s:63.4s forge 钉点先吃 150(64.3s 矿 155→
    72.3s 35),随后 88/104/112s 三根水晶(300 矿)+探机连拍把
    等钱中的 GATEWAY 工人晾了 ~54s。pending(已派工)≠ placed
    (已放置):opener 一派工门就开,forge 的 150 照抢。判据改
    「GATEWAY 已放置(实体含在建)or (t≥75 且矿 ≥200)」——
    放置前 forge 不抢;兜底不变。验收口径不变:GATEWAY ≤75s。
    """
    return gateway_placed or (now >= min_t and minerals >= min_minerals)


def event_throttle_ok(now: float, last_ts: float, interval: float = 30.0) -> bool:
    """O357-④(O340 同规约):事件簿记节流判据。纯逻辑,可单测。

    只节流言、不节流行为:距上次簿记 ≥interval 秒才再记一次,下单/
    派工动作本身每帧照常。O340 首扩诊断/O356 母舰 supply 钉点的
    30s 规约显式化(O239 航母点单簿记用,o356b g3 同秒 8-14 条
    刷屏实证)。
    """
    return now - last_ts >= interval


def sg_rebuild_cooldown_ok(
    now: float, last_at: float, cooldown: float = 30.0
) -> bool:
    """O376-⑥(o375a 尸检):O182 紧急重建星门的冷却判据。纯逻辑,可单测。

    o375a g2 实证:1260s 一秒连发 15 条「O182:紧急重建星门」——
    register_behavior 每帧重注册(星门建造 43s,就绪+在途归零
    的窗口内每帧都满足触发条件),建造队列被重复注册刷爆。与
    event_throttle_ok(只节流言不节流行为)相反:本闸节流的是
    行为本身(注册动作),冷却期内不重注册;落成/在途出现
    (就绪+在途 >0)判据自灭,冷却只是建造窗内的防连发兜底。
    """
    return now - last_at >= cooldown


def fb_saving_window(sg_ready: bool, fb_present_or_pending: bool) -> bool:
    """O353-③(o352 六局尸检):FB 攒钱窗判据(虚空兜底禁用窗)。纯逻辑,可单测。

    SG 就绪且 FLEETBEACON 无实体未派工 = FB 攒钱窗。o352 实证:FB
    pending 长达 275s,矿恒 24-294 差 300 一口气;O261 虚空兜底要求
    FB 缺失才触发,恰好与本窗重合,2×250 矿反抢 FB 资金(game_03
    在 622s 还点 2 艘虚空)。窗内一切非关键开销让位 FB 钉点。
    """
    return sg_ready and not fb_present_or_pending


def tempest_dump_suppressed(
    carriers: int,
    tempests: int,
    fb_ready: bool,
    vespene: float,
    min_carriers: int = 2,
    tempests_restore: int = 4,
    min_gas: float = 500.0,
) -> bool:
    """O354-①(o353 五局尸检):O260 暴风兜底抑制 —— 航母破零优先。纯逻辑,可单测。

    o353 实证:航母 4/5 局破零但峰值 1-2 —— O260 兜底(vespene≥500 门)
    每帧抢矿点暴风(game_01 气 886 时点了第 7 艘暴风而非第 2 艘航母);
    航母 350 矿 vs 暴风 300 矿,矿是唯一硬约束,气终局烂 1125-1301。
    FB 已有实体 且 航母(含在产)<min_carriers 且 气 ≥min_gas 时,
    O260 不点暴风,把矿留给 O239 的航母订单;暴风 ≥tempests_restore
    或航母 ≥min_carriers 后 O260 恢复正常(返回 False)。
    """
    return (
        fb_ready
        and vespene >= min_gas
        and carriers < min_carriers
        and tempests < tempests_restore
    )


def mothership_window_open(
    fb_ready: bool,
    now: float,
    fleet_count: int,
    vespene: float,
    bases: int,
    workers: int,
    motherships: int,
    minerals: float,
    min_t: float = 700.0,
    min_fleet: int = 3,
    min_gas: float = 400.0,
    price: float = 400.0,
    min_minerals: float = 300.0,
) -> bool:
    """O354-②(o353 五局尸检):母舰资金窗判据。纯逻辑,可单测。

    o353 实证:母舰 0/5 —— O264/O325 经济门(FB+t≥700+fleet≥3,3 基地
    或 ≥36 农)多局满足,但 can_afford(400 矿)恒假,矿被 O260/塔/农
    每帧吃光;母舰隐身场正对腐化波(敌反隐仅眼虫),胜局配方里有母舰
    位置。母舰出门槛除 can_afford 外全部满足(FB 就绪、t≥700、
    fleet≥3、气 ≥min_gas、经济门过、无母舰含在产)且矿 <400
    时开窗:调用方抑制 O260 暴风兜底与新塔/电池钉点,把资金窗让给
    母舰;矿 ≥400 或条件不再满足时窗自动关(自校正,无 latch)。
    窄域优先级修正,不是全局面资金冻结。
    O355-①(o354 六局尸检):min_gas 600→400 —— 600 与 O260 泄气闸
    (气 ≥500 点暴风)构成数学死锁:气被 O260 永远压在 600 以下,
    窗永不二次开(o354a g3 实证 O260 在气 389/364 合法泄气;母舰
    0/9)。400 < 500 让窗先开,窗内 O260 被抑制,气自然续涨到
    O264 下单门(600)。
    O358-③(o357 尸检):开窗加矿判据 min_minerals=300 —— 窗语义
    从「攒钱期」改「攒够了才开」。o357a g3 实证:气 ≥400 成立但
    矿 <300 买不起,空窗 60s 期间塔/电池钉点被抑制,分矿塔被压、
    940s 掉四矿 —— 窗判据与下单判据(矿)对齐:矿 <300 时抑制
    防御链换来的钱也到不了 400,是净亏;矿 300-400 才是最后一脚
    的冲刺窗,让位有价值。O355-① 窗内探机让位与 O356-② 窗内
    抑制逻辑不变(窗开时仍生效)。
    O359-④(o358 六局尸检,母舰 0/6 实锤):O358-③ 的矿底对
    「奢侈品抑制」构成数学死锁 —— o358b g2 舰队 25、FB 462s、
    打到 1319s 母舰 0:矿 1040-1319s 峰值 250 恒 <300 → 窗永不
    开 → O260 暴风兜底(300 矿/艘,150s 内 10+ 次)与 O239 航母
    (350 矿)不被抑制 → 矿永远摸不到 300。「买不起」与「不抑制」
    互为前提。修复:调用方拆两档 —— 奢侈品/探机抑制(O260/O239/
    舰队新单/探机让位)传 min_minerals=0(抑制它们本身就是攒钱
    手段,无矿底);防御链(塔/电池钉点)保持 300 矿底(O358-③
    保四矿的初衷不动)。O264 下单路径从不读本窗(can_afford 自含
    矿判),本改动不涉及下单条件。
    """
    if motherships > 0 or minerals >= price:
        return False
    return (
        fb_ready
        and now >= min_t
        and fleet_count >= min_fleet
        and vespene >= min_gas
        and minerals >= min_minerals
        and mothership_economy_ok(bases, workers)
    )


def ms_window_probe_yield(
    ms_window: bool,
    workers: int,
    min_workers: int = 28,
) -> bool:
    """O355-①(o354 六局尸检):母舰资金窗内探机让位。纯逻辑,可单测。

    o354a g1 实证:窗口开过一次(728.6s),但窗口期矿 175→45→5 一路
    下滑(抄家+追猎重建吃矿之外,探机 50 矿/个也在帧级抽窗),从未
    到 400,母舰始终未下单。窗内(矿 <400 攒钱阶段)且农民 ≥28
    (与 O225 探机让位同口径,已超双矿饱和线 87%)→ 暂停探机训练,
    把资金窗让给母舰;窗随矿 ≥400/条件失效自动关(自校正,无 latch)。
    窄域优先级修正:追猎/叉 floor 生产不动(不做全局面冻结)。
    """
    return ms_window and workers >= min_workers


def rescue_pylon_anchor(
    free_slots: list,
    base_xy: tuple[float, float],
    fails: int,
    min_fails: int = 1,
) -> tuple[float, float] | None:
    """O355-②(o354b 三局 6 次 forge no_placement 尸检):自救水晶锚点
    升级。纯逻辑,可单测。

    o354b 实证:O348-① 自救水晶锚在主基中心(closest_to=基地)——
    主基中心带电 3x3 槽早被 GW/core/nexus/电池挤占,水晶落在建筑
    密集区旁,电力覆盖的全是已占槽,空闲槽仍在电外,forge 落成
    拖到 257-361s。连续 no_placement ≥min_fails 次起,锚点改对准
    「离基地最近的空闲 3x3 槽」——水晶贴着空闲槽落,落成即把该槽
    纳入电网,下轮重试 forge 自然有位。fails <min_fails 或无空闲
    槽 → None(调用方保持原锚点)。
    O356-①a(o355 尸检:败局 2/3 死于出生点确定性 no_placement):
    min_fails 2→1 首发即自救 —— AbyssalReef 右下出生点主基 forge
    钉点 ~135s 起确定性 no_placement(2/2 局逐帧一致),等第二次
    失败再救 = 首次失败→自救派工间隔 92-112s,forge 落成 257-301s,
    致死波 274-322s 到脸时首塔 333s+;首次失败立刻派自救水晶。
    """
    if fails < min_fails or not free_slots:
        return None
    bx, by = base_xy
    return min(
        free_slots, key=lambda s: (s[0] - bx) ** 2 + (s[1] - by) ** 2
    )


def second_rescue_pylon_needed(
    cannon_xy: tuple[float, float] | None,
    cannon_pin_powered: bool,
    rescue_anchor: tuple[float, float] | None,
    power_radius: float = 6.0,
) -> bool:
    """O356-①b(o355b g3 实证):forge 自救水晶之外,首塔钉点是否还要
    补第二根水晶。纯逻辑,可单测。

    o355b g3 实证:自救水晶锚的 3x3 槽没覆盖首塔 2x2 钉点 —— 水晶
    落成后首塔钉点仍无电(O116 报 (0,0,29):带电 0/空闲 0/总 29),
    0 塔接 271s 狗蟑波。判据:有首塔钉点 且 钉点当前不带电 且
    (无自救锚点 或 自救锚点距钉点 >power_radius,水晶落地也照不到)
    → 在首塔钉点旁补第二根。power_radius 默认 6.0(水晶电力场半径
    6.5,留 0.5 格落位偏差余量;偏小偏保守=宁多补不裸奔)。
    """
    if cannon_xy is None or cannon_pin_powered:
        return False
    if rescue_anchor is None:
        return True
    dx = rescue_anchor[0] - cannon_xy[0]
    dy = rescue_anchor[1] - cannon_xy[1]
    return dx * dx + dy * dy > power_radius * power_radius


def pin_reanchor(
    slots: list,
    ramp_xy: tuple[float, float],
    blacklist: list,
) -> tuple[float, float] | None:
    """O357-①(o356 尸检):钉点死槽拉黑换锚。纯逻辑,可单测。

    o356 实证:AbyssalReefLE 右下出生点(50% 出生概率)主基 forge
    钉点 ~135s 起确定性 no_placement(槽位三值 (0,23,25),多轮
    4/4 局逐帧一致),O356-① 自救水晶全部正常落地但无效 —— 是不
    可放置(几何)不是没电;机械台同样三连 no_placement,o356b
    game_01 右下 365s 早亡 forge/塔终生 0。钉点 no_placement 即把
    当前锚点(坐标取整)加黑,下次派工显式 closest_to=新锚:主基
    空闲 3x3 槽里「带电优先、离致死波入口(主基斜坡口)更近优先」
    重选一位。无候选 → None(调用方保持原锚点,O356 自救水晶照常
    补纯电问题)。
    slots: [(x, y, free, powered), ...](_free_3x3_slots_at 加电力
    标注);blacklist: [(round(x), round(y)), ...]。
    """
    rx, ry = ramp_xy
    cands = [
        (x, y, powered)
        for x, y, free, powered in slots
        if free and (round(x), round(y)) not in blacklist
    ]
    if not cands:
        return None
    x, y, _ = min(
        cands, key=lambda s: (not s[2], (s[0] - rx) ** 2 + (s[1] - ry) ** 2)
    )
    return (x, y)


def reanchor_bases(
    start_xy: tuple[float, float],
    townhall_xys: list,
) -> list:
    """O358-④a(o357 尸检):换锚槽池的基地清单 —— 扩出主基拥挤圈。
    纯逻辑,可单测。

    o357 实证:o357a g1 机械台 330.0-330.4s 连发 5 次换锚(黑1→黑5),
    365.4s 仍 no_placement,整局机械台=0 —— 5 个锚全在主基圈
    (坐标 30-56,116-134 拥挤区),换锚 ≠ 换得出。锚池纳入分基/
    副基(其它 townhall 的槽表),主基槽全黑/全占时还有圈外候选。
    返回 [主基, 各基地...](取整坐标去重;主基恒在首位,主基有候选
    时 pin_reanchor 的距离序仍优先主基附近)。
    """
    out: list = []
    seen: set = set()
    for x, y in [start_xy, *townhall_xys]:
        key = (round(x), round(y))
        if key not in seen:
            seen.add(key)
            out.append((x, y))
    return out


def reanchor_cooldown_until(
    blacklist_len: int,
    now: float,
    min_black: int = 3,
    cooldown: float = 60.0,
) -> float | None:
    """O358-④b(o357 尸检):换锚不收敛的冷却闸。纯逻辑,可单测。

    o357 实证:机械台换锚 5 次仍 no_placement 后每 30s 节流空转
    刷屏 + 占调度(g2 同剧情:958.6s 换锚×5 → 986.9/1123.5s 仍
    失败)。拉黑 ≥min_black 次仍 no_placement → 放弃该建筑的
    critical 钉点 cooldown 秒(返回冷却截止时刻);槽位随其它建筑
    落成/电网扩张会释放,60s 后重试比每 30s 空转便宜。未达
    min_black → None(不冷却,照常住换锚)。
    """
    if blacklist_len >= min_black:
        return now + cooldown
    return None


def cannon_stall_rescue(
    fail_streak: float,
    forge_ready: bool,
    threshold: float = 30.0,
) -> bool:
    """O356-①c(o355b g3 实证):首塔派工死等自救判据。纯逻辑,可单测。

    o355b g3 实证:O296-③ 的自救被 _in_flight_near 门挡死 —— forge
    自救水晶在途/在建 15 格内恒 >0,首塔到死 not_viable;落成后那根
    水晶又没覆盖首塔 2x2 钉点,带电槽恒 0。forge 就绪后首塔派工
    连续失败(no_placement/not_viable/tech_not_ready)超 threshold
    秒 → 无视在途门直接在首塔锚点旁补钉(调用方 30s 节流防刷)。
    """
    return forge_ready and fail_streak >= threshold


def ms_window_fleet_suppressed(
    ms_window: bool,
    fleet_count: int,
    min_fleet: int = 6,
) -> bool:
    """O356-②b(o355b g1/o355a g2 实证):母舰资金窗内星门舰队新单
    让位判据。纯逻辑,可单测。

    o355b g1 实证:904-952s 窗 48s 内舰队 8→13(5 艘×300 矿≈1500
    矿)把母舰 400 矿资金窗吃光;o355a g2:794.2s O239 在气 614 时
    花 350 矿点航母,母舰只差 ≤50 矿被截胡。窗内且舰队(TEMPEST+
    CARRIER+在产)≥min_fleet 时星门新单让位(舰队已够压制面,矿
    留给母舰);舰队 <min_fleet 不动 —— 窗内舰队太弱还得造。
    自校正无 latch:窗随矿 ≥400 自动关,产线即时恢复。
    """
    return ms_window and fleet_count >= min_fleet


def mothership_supply_ok(
    supply_left: float,
    min_left: float = 10.0,
) -> bool:
    """O356-②d(o355b g1 实证):母舰下单的 supply 余量门。纯逻辑,可单测。

    o355b g1 终局实证:矿 590/气 437 全满足但 supply 199/200,母舰
    8 人口卡死永远下不了单;O109-① 的舰队人口 buffer 闸要求
    _transition_active/_fleet_transitioned,ZT 两旗常年假(O297-①
    实证),buffer 在 ZT 局从不触发。母舰 8 人口 + 2 余量 = min_left
    10;不足时调用方钉一根水晶(O264 块 elif 分支)。
    """
    return supply_left >= min_left


def cannon_capped(
    now: float,
    fleet_count: int,
    cannons: int,
    threat_active: bool,
    min_t: float = 600.0,
    min_fleet: int = 4,
    max_cannons: int = 8,
) -> bool:
    """O354-④(o353 五局尸检):静态防御封顶判据。纯逻辑,可单测。

    o353 实证:败局塔峰值 8-13 座(≈1950 矿 ≈ 5 艘航母),舰队 ≥4 后
    仍在补塔 —— 舰队卡在 4-7 艘的一半资金死因。t≥min_t 且舰队
    (TEMPEST+CARRIER)≥min_fleet 且全局 PHOTONCANNON ≥max_cannons 时
    不再新钉塔;rush/threat 激活时豁免(被骑脸时该补还得补)。
    """
    if threat_active:
        return False
    return (
        now >= min_t
        and fleet_count >= min_fleet
        and cannons >= max_cannons
    )


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
    fleet_min: int = 4,
    carrier_target: int = 4,
    pending_tempest: int = 0,
    pending_carrier: int = 0,
) -> bool:
    """O155/O156: carrier 流舰队成型后强制补航母配额。纯逻辑，可单测。

    当前 carrier 配方为 TEMPEST p0 / CARRIER p1 + save_up=0，freeflow 下
    TEMPEST 便宜且永远可负担，CARRIER 被永久截断、整局不出（O154 终局
    编成 28 暴风 0 航母实证；o351 18 局尸检 CARRIER=0 贯穿全场——配额
    阈值达不到,截断从未被解除）。本函数在舰队成型后检测是否该强制补航母：
    - flow 必须是 carrier；
    - fleet_online（至少有一艘舰队主 C 出生/在产，保证气矿经济已运转）；
    - 舰队总数（暴风+航母+在产）已达 fleet_min（默认 4，O352-① 从 8 下调——
      o351 18 局暴风峰值仅 0-8，阈值 8 在这组对局永远等不到；O156 曾从
      12 下调到 8，对 VeryHard Zerg Timing 仍不可达）；
    - 航母数量 < carrier_target（默认 4）。
    O156 追加安全网：舰队成型中且 0 航母、同时离阈值还差至少 2 艘时，必须
    先把第一艘航母挤出来，避免“暴风憋到阈值前被推平、航母从未出场”。
    O352-①:fallback 暴风门槛 6→3（与 fleet_min=4 同档，o351 尸检同据）。
    触发后由调用方把 spawn 主次对调并开动态 save_up，逼出航母。
    """
    if flow_name != "carrier" or not fleet_online:
        return False
    if carrier_count >= carrier_target:
        return False
    fleet_total = tempest_count + carrier_count + pending_tempest + pending_carrier
    if fleet_total >= fleet_min:
        return True
    # O156 fallback：3+ 暴风且 still 0 航母（含在产），同时离 fleet_min 只差
    # 2 艘以内时，必须先把第一艘航母挤出来，避免“差一点到阈值被推平”。
    return (
        carrier_count == 0
        and pending_carrier == 0
        and (tempest_count + pending_tempest) >= 3
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
    enemy_ground_supply: float = 0.0,
    tank_seen: bool = False,
) -> bool:
    """风暴压制 → 航母终结的转型时点。纯逻辑，可单测。

    简单可工作判据（阈值走参数，不硬编码死）：进入中后期（时间到 at_time）
    **或**风暴压制阵容已成型（数量到 tempest_cap）→ 转航母主 C。
    压得住时局已在 200-500s 内结束（认证赢法），到点压不住就补航母终结。
    O374-④a(o373a 双负同谱系尸检):转型点与敌情挂钩 —— o373a
    两负 550-700s 舰队 2-6 艘对 MM 27-56 supply+维京 4-8 架
    点名必穿,E10 固定 600s 转型点防守厚度不够、航母始终没出来;
    敌可见地面 supply ≥35 或坦克首现(调用方 latch)即提前转
    (航母对 MM/坦克是质量答案,风暴耗不起)。默认参数旧调用零
    变化(敌情 0/False 时判据与原式逐项等价)。
    """
    return (
        now >= at_time
        or tempest_count >= tempest_cap
        or enemy_ground_supply >= 35.0
        or tank_seen
    )


def carrier_transition_time_box(
    now: float,
    fb_completed_at: float | None,
    opp_race: str,
    fb_delay: float = 150.0,
    hard_at: float = 480.0,
) -> bool:
    """O377-②(o376a 三局 0/3 尸检):vs Terran E10 航母转型时间盒。
    纯逻辑,可单测。

    o376a 实证:航母转型挂「敌坦克首现」被动扳机,坦克 514/585s
    才露面 → 首航母 498-671 vs o373a 胜局配方 454,等坦克 = 等死。
    vs Terran 改时间盒:FB 落成 +fb_delay 秒(舰队产能/资金窗,
    对齐配方 FB~300s+150≈454s 首航母)即转,硬顶 hard_at(480s)
    兜底(FB 迟落也不等坦克);坦克首现扳机(carrier_transition_
    ready 的 tank_seen)保留为更早的提前条件,不再是必要条件。
    非 terran 恒 False(zerg/protoss 原判据一行不动)。
    """
    if opp_race != "terran":
        return False
    if fb_completed_at is not None and now >= fb_completed_at + fb_delay:
        return True
    return now >= hard_at


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


def oracle_gas_yield(
    carriers: int,
    vespene: float,
    min_carriers: int = 2,
    min_vespene: float = 300.0,
) -> bool:
    """O367-④b(o366 双 lane 尸检):先知 one_off 让位闸。纯逻辑,可单测。

    o366a/o366b 三局实证:754-784s 各出 1 先知(150 矿/150 气 +
    37-43s 星门产能),基准胜局全程无先知 —— 穷局先知白吃航母的
    气和星门产能。航母(含在产)<min_carriers 或 气 <min_vespene
    时不造先知(返回 True = 让位);舰队成型且气宽裕才放行。
    """
    return carriers < min_carriers or vespene < min_vespene


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
    hopeless: bool = False,
) -> bool:
    """O94-C/O104-①/O123-③:首波农民协防判据。纯逻辑,可单测。

    敌地面进主基 ≥min_enemy → 拉农民协防。
    O104-①:1 塔不放人(转塔下作战),2 塔/叉够/敌退才归队。
    O123-③(叉海 A/B):叉子接管线 2→4 —— 叉海成型后农民不再参战
    (协防战损是速败局的经济癌症),只在「叉<4 且敌进家」才出手。
    O309-②(o308a game_03/04 实证):白送上界 —— 敌地面超 14+6×塔
    (同 O306-③口径)时不拉,协防从「顶 10-20s」变成「×6 添油四轮
    骤减 4-11/波」的纯放血(game_04:敌27-30 地面照拉 ×6)。
    白送线以上农民留矿保命(ares keep_safe 个体避险),留经济火种。
    hopeless 缺省 False → 旧签名行为不变。
    """
    if hopeless:
        return False
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


def probe_floor_cap(
    is_zerg_timing: bool,
    townhalls: int,
    two_base_floor: int = 28,
    one_base_floor: int = 16,
) -> int:
    """O353-②(o352 六局尸检):农民下限 floor 的两矿提升判据。纯逻辑,可单测。

    o352 g1:两矿局 sprint 连续 240s + floor=16 把农民钉死在 16,
    全局采矿仅 ~756/min(两矿饱和应 ~1800/min),是一切 no_money 的上游。
    ZT 流程两矿(townhalls≥2)floor 提到 28;一矿保持 16
    (一矿要冲刺出兵,矿给防御链)。
    """
    if is_zerg_timing and townhalls >= 2:
        return two_base_floor
    return one_base_floor


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


def zt_wave_read(warren_seen: bool, enemy_bases: int, now: float) -> str | None:
    """O320-①(o306-o319 共 14 轮尸检):ZT 快慢波分档判据。纯逻辑,可单测。

    verdict(O9)是一发 latch(t≈109-170s),后到的情报(ROACHWARREN ~136s、
    敌分矿)无人消费 → 每局盲打 presumed 包(~500 矿),快慢波不分。
    分档:
    - fast:已见 ROACHWARREN 且敌 ≤1 基地(t≥150)—— 蟑螂巢先行不开矿
      = 280-330s 快波,武装 rush 证实包(O107 先例:情报确认算证实);
    - slow:敌 ≥2 基地且未见 warren(t≥200)—— 开矿优先 = 波 ≥440s,
      presumed 退保省包 + 开矿窗提前(波间隙是经济的,不是防御的);
    - 其余 → None(情报不足,维持现状不押注)。
    """
    if warren_seen and enemy_bases <= 1 and now >= 150.0:
        return "fast"
    if enemy_bases >= 2 and not warren_seen and now >= 200.0:
        return "slow"
    return None


def zerg_timing_expand_allowed(
    is_zerg_timing: bool,
    first_fleet_seen: bool,
    now: float,
    enemy_home: int,
    enemy_near_natural: int,
    cannons_ready: int = 1,
    at: float = 280.0,
    hard_gate: float = 620.0,
    gw_ready: bool = False,
) -> bool:
    """O258-①/O262-①/O263-①/O265/O278-②:ZT 二矿窗判据(防御驱动)。纯逻辑,可单测。

    O263(t≥320+踩点检查):o263 lane2 3-1 打穿,二矿 353s。
    O265(220s)证伪回退 320s。
    O278-②(司令观察②):窗 320→280,与分矿口预置塔(t≥250 起铺水晶/塔/
    电池)联动 —— Nexus 落在已设防的口子上;280s 开工 ~355s 落成,
    卡在 O236 胜负线(≤400s)内。首塔就绪/家无敌/分矿点无敌前提不变。
    O312(司令 2026-08-17 拍板 A 案,GM 式经济优先):窗 280→200 + 防御
    前提放宽(首塔就绪 或 GW1 就绪)—— O265 的 220s 证伪发生在 natural
    直开时代;O281 口袋矿(离波行进路径)落地后,早开的安全前提变了:
    波打主基时口袋矿零压力落成。胜局二矿 309s vs 败局 478-546s 是
    胜负线,200s 开工 ~270-310s 落成,直取胜局画像。
    """
    if not is_zerg_timing:
        return True
    if first_fleet_seen or now >= hard_gate:
        return True
    return (
        now >= at
        and (cannons_ready >= 1 or gw_ready)
        and enemy_home == 0
        and enemy_near_natural == 0
    )


def ring_openness(grid, pos, radius: float = 14.0, samples: int = 24) -> int:
    """O328(司令观察):扩张点环上可通行采样数 —— 口袋度的反向指标。纯逻辑,可单测。

    背靠墙体的防守矿,环上采样点大量落在悬崖/墙体/图缘外(不可通行);
    敞开矿几乎全可通行。grid 只需有 is_set((x:int, y:int)) -> bool
    (burnysc2 PixelMap 即此接口);出界/异常按不可通行计(= 背靠掩体)。
    radius=14:小于此半径会被矿线/气矿 footprint 污染,大于此半径
    信号被邻近地形稀释(探针 scripts/dump_map_geo.py 实测口径)。"""
    open_count = 0
    for i in range(samples):
        a = i * math.tau / samples
        x = int(round(pos.x + radius * math.cos(a)))
        y = int(round(pos.y + radius * math.sin(a)))
        try:
            if grid.is_set((x, y)):
                open_count += 1
        except Exception:
            pass
    return open_count


def pick_pocket_expansion(
    free_expansions,
    enemy_start,
    playable_rect=None,
    main=None,
    openness=None,
    open_weight: float = 4.0,
    main_weight: float = 0.5,
):
    """O281(o280 基线复测 0-9 裁决打法上限):ZT 首扩远位口袋矿。纯逻辑,可单测。

    natural 在 305-320s 死窗波行进路径上,Nexus 建筑期被首波打断/白捐
    (o280 复盘 one_base×2:420s 仍单矿)。首扩改取**离敌出生点最远**的空闲
    扩张点 —— 波打主基/natural 塔阵时口袋矿零压力落成,经济曲线不断。
    入参任一为空 → None(调用方退回原 natural 选址)。
    O291(司令观察):选址加地形分 —— 优先「背靠地图边缘」的矿点(背后
    墙体天然封口,防御只需封正面 1-2 个口);score = 离敌距离 -
    0.5×离图缘距离,贴缘矿点在同等离敌距离下胜出。playable_rect=
    (x, y, w, h),None 时退化为纯离敌距离。
    O328(司令观察+探针取证):加开阔度/距主基两项 —— AbyssalReefLE 主基
    右下时,旧分把首扩拍到北侧 (157.5,50.5)(open14=14/24 敞开、四面
    临敌,建筑学+塔守不住),而非司令指定的西侧 (129.5,26.5)
    (open14=10/24,背靠墙体只封 1-2 口)。openness=环上可通行采样数
    (ring_openness 口径,越少越口袋),每点权重 4.0;距主基权重 0.5
    (防御整合 + 农民/增援短链路)。两项缺省 None → 旧分逐位不变。"""
    if not free_expansions or enemy_start is None:
        return None
    if playable_rect is None:
        return max(free_expansions, key=lambda el: el.distance_to(enemy_start))
    rx, ry, rw, rh = playable_rect

    def _score(el):
        edge = min(el.x - rx, rx + rw - el.x, el.y - ry, ry + rh - el.y)
        s = el.distance_to(enemy_start) - 0.5 * edge
        if openness is not None:
            s -= open_weight * openness(el)
        if main is not None:
            s -= main_weight * el.distance_to(main)
        return s

    return max(free_expansions, key=_score)


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


def rebuild_window_spawn(
    spawn: dict, rebuild_window: bool, voidray_id,
    voidray_field: int = 0, voidray_cap: int | None = None,
) -> dict:
    """O121-①(o120 局2/3/4 实证):重建窗(FB 未就绪)星门填窗兵种。
    纯逻辑,可单测。

    局2/3/4 同型:退出 → SG→FB→首舰 ~190s 空窗,波次 exit+60s 到脸时
    舰队 0-1 艘 = 没有。VOIDRAY 不需 FB、37s 成型、棱镜对齐烧地面 ——
    退出后 SG 立刻有产出,exit+60s 有 1-2 虚空、exit+120s 有 3-4,
    配合塔/电池顶过空窗;FB 就绪后 TEMPEST 入队即自然挤占(p0 同档,
    dict 序 TEMPEST 在前),首舰出场窗关、配方复原。
    O379-②(o378b g1 实证):虚空总量帽 —— O378-④ 的 cap=2 只接了
    pre-FB/post-FB 两条填线 lane(合计仅产 3 次),真正量产源是本
    重建窗注入无帽:g1 重建窗 = 转舰队(295s)→首风暴(892s)近
    600s,虚空全程在配方,矿穷期 Tempest(300 矿)买不起就
    fall-through 产虚空,10 艘×150 气=1500 气反过来饿死风暴/航母。
    voidray_cap 非 None 且场上虚空(含在产,调用方口径)≥cap →
    不注入;terran lane 不传帽(None)一行不动。
    """
    if not rebuild_window:
        return dict(spawn)
    if voidray_cap is not None and voidray_field >= voidray_cap:
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
    defense_urgent: bool, forge_present_or_pending: bool,
    is_zerg_timing: bool = False,
) -> bool:
    """O118-②/O127-①(数据终裁):防御紧急窗 forge 先于首兵营。纯逻辑,可单测。

    o126b 算术终裁:最快波 ~154;forge 优先链(forge 75-80 拍 → 首塔
    ~140-145)赢 10-14s,GW 优先链(GW ~145 完工 → 首叉 ~155-165)输
    0-10s。O118 方向对,O125 反转为误 —— O118 当时失败是 forge 没在
    75-80 开拍(资金被 O79 水晶/农民偷),不是顺序错。
    严格前提「forge 未拍(无实体且无在建)」:forge 一拍下 GW1 即紧随,
    不互抢;forge 掉了重建期 GW 让位(塔链是防御本体)。

    O308-①(o307a game_02/03 尸检):Zerg Timing 豁免 —— o126b 的算术基于
    ~154s 狗波(Zerg Rush);ZT 首波是 ~240s 蟑螂波,forge-first 把首叉
    拖到 218s,波到脸仅 4-6 supply + 1 塔(game_02/03 均因此崩)。
    ZT 改 GW1 先拍(司令 GM 录像口径:兵营先于 BF),首叉 ~180s 上岗,
    forge/首塔随其后。Rush 保持 O127 终裁不动。
    """
    return defense_urgent and not forge_present_or_pending and not is_zerg_timing


def serialize_presumed_cannons(cannons_ready: int) -> bool:
    """O308-③(o307a game_03/o306c game_05 实证):presumed/unknown 窗炮塔串行化。
    纯逻辑,可单测。

    125-143s 连续三农民「等钱造 PHOTONCANNON」—— 3 塔同排(450 矿窗口)
    把资金摊薄,首塔拖到 200-225s 才就绪,而 ZT 首波 ~240s 到脸。
    首塔就绪前目标压到 1(资金集中,首塔 ~60s 提前),落地后恢复正常目标。
    """
    return cannons_ready == 0


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
    enemy_supply: float = 0.0,
    own_supply: float = 9999.0,
    ground_supply: float = 9999.0,
    ground_floor: float = 12.0,
    expand_reserve_exempt: bool = False,
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
        not expand_reserve_exempt  # O366-④a:敌 supply>30/t>500 豁免(调用方滞回)
        and is_zerg_timing
        and expand_holding
        and nexus_unstarted > 0
        and minerals < nexus_price
        # O298-②(o297a game_03 实证):742s 45-supply 波在途,expand_reserve
        # 仍停产攒 Nexus(707/761/791s 三连停)——波到脸时地面兵 3。
        # 与 O296-① carrier 闸同口径:敌可见 supply ≥ 我方时产线永不停
        # (开矿攒钱是波间隙特权), Nexus 资金由 O298-③ 的开销让位解决。
        and enemy_supply < own_supply
        # O307-②(o306c game_03/05 实证):地面低于保底时停产攒 Nexus = 裸奔
        # —— game_03 地面 2(4 supply)停产,306s 15-supply 波到家仅 7 兵;
        # game_05 地面 5(10 supply)停产,304s 波穿主基。侦查断链期
        # enemy_supply=0 让 O298-② 闸失效,地面保底是盲期最后防线。
        and ground_supply >= ground_floor
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


def expand_holding_should_abort(
    holding_for: float,
    nexus_unstarted: int,
    can_afford_nexus: bool,
    timeout: float = 60.0,
) -> bool:
    """O307-③(o306c game_05 实证):开矿持有死锁自愈判据。纯逻辑,可单测。

    game_05:Nexus 预走位未开工,holding 从 ~300s 持续到 626s(326s)——
    科技链(core_allowed=False)全程冻结,星门 0、气烂 1325,两波滚死。
    持有 >timeout 且 Nexus 仍未开工、仍买不起 → 撤销派工解锁科技链,
    冷却后再由动态开矿重评(波间隙特权,不是永久取消)。
    O309-③(o308a game_02 实证):90s 超时 + 45s 冷却 = 135s 重试周期,
    二连 abort(355/474s)把二矿拖到 546s;胜局二矿 309s vs 败局
    478-546s,每 30s 都值钱 —— 超时压到 60s(周期 90s)。
    O336-①:ZT 首扩的撤销豁免见 holding_abort_keep_first_expand
    (调用方分支,本判据不变)。
    """
    return holding_for > timeout and nexus_unstarted > 0 and not can_afford_nexus


def holding_abort_keep_first_expand(is_zerg: bool, townhalls: int) -> bool:
    """O336-①(o335a game_02 实证):Zerg 首扩的 holding abort 只解锁不撤销。纯逻辑,可单测。

    o335a game_02:O329 启动 104s,但 257s 首波 rush_active 解锁主基
    防御链(forge+2塔+电池+5叉+追猎 1150+ 矿),等钱的 Nexus 被 O307
    二连撤销(281/457s)→ 落成 578s vs 胜局 212-233s。首扩是全村
    希望:撤销重派 = 工人再走 20s + 资金窗重算,只会更晚。Zerg 首扩
    (townhalls==1)abort 时保留派工,仅释放 holding 30s 让科技链
    恢复(o306c 的科技冻结死因不回潮);3 矿+ 与原语义(撤销)不变。
    O365-③a(o364b g1 实证):适用面 timing → zerg 全 build ——
    rush 局同样被旧 O307 撤销路径坑(o364b g1 二矿裸建 69s 被拆),
    O364-① 的 hold 分支被 _ai_build=="timing" 门住从未接线。
    """
    return is_zerg and townhalls == 1


def holding_allows_cyber(is_zerg_timing: bool, gateway_ready: bool) -> bool:
    """O307-①(o306c game_03/05 实证):holding 期放行 CYBERNETICSCORE。纯逻辑,可单测。

    开矿持有期 core_allowed=False 把整条科技链冻结;Cybercore 仅 50 矿
    (Nexus 的 1/8),却是追猎/星门链的总开关 —— 两局败局气烂 700-1300
    无追猎可出。仅限 Zerg Timing(证据所在),兵营就绪才建(链序不乱)。
    """
    return is_zerg_timing and gateway_ready


def gateway_chain_after_first_zealot(
    gateways_have: int, first_zealot_seen: bool
) -> bool:
    """O126-①(o125 局1 实证):GW2+ 是否该等首叉。纯逻辑,可单测。

    局1:GW2(150)在 GW1 完工前 10s 抢走矿,首叉从 ~163 拖到 ~178
    (再叠加 forge 的 137)——GW 链优先级不得高于「现役兵营的首叉」。
    GW1(have=0)不受此闸(开局刚需);首叉在产/出场后 GW2+ 恢复正常。
    """
    return gateways_have >= 1 and not first_zealot_seen


def pocket_saving_cannons(cannons: int, cap: int = 3) -> int:
    """O293-②(o292a game_01 实证):口袋激活期塔目标地板。纯逻辑,可单测。

    O290 的「激活期塔归 0」实证过狠:首波(236-320s)正好落在攒钱窗里,
    波到脸 threat 才翻真,29s 建造+dispatch 来不及 —— game_01 塔恒 2、
    Nexus 也没攒出,两头落空。胜局对照(o290b-g05):波前 3 塔 285s 成型
    是存活地板。激活期塔目标收到 ≤3(保留 O290 拦 3→10 塔链的本意),
    急性(threat)期仍不冻。
    """
    return min(cannons, cap)


def zt_golden_window_push(
    now: float,
    fleet_count: int,
    stalker_count: int,
    min_t: float = 650.0,
    min_fleet: int = 3,
    min_stalkers: int = 6,
    corruptors: int = 0,
    max_corruptors: int = 4,
    spire_seen: bool = False,
    decay_t: float = 750.0,
    decay_min_stalkers: int = 4,
) -> bool:
    """O302(司令 2026-08-17 拍板·先手压制专项):ZT 黄金窗推进闸。纯逻辑,可单测。

    跨 40 局敌编成取证:850s+ 敌必转腐化+大龙(暴风被克,我方 0 胜);
    750-800s 敌纯蟑螂/刺蛇(蟑螂不能对空,暴风白打)= 先手黄金窗。
    O241 的强推闸(fleet≥6 & t>540)实证整局不触发 —— 舰队卡 4-6 艘。
    窗口内降闸:舰队 + 追猎达线即推(刺蛇由追猎接,暴风自由输出);
    召回/安全线(carrier_push_safe/热点回防)不变,推不动会被波次自然
    叫回家,推得动就抢在腐化转型前打死/打残。
    O303-②(o302b game_01/game_04 实证):原参数(t≥700/舰队≥4/追猎≥10)
    两局推进都差一点没够上(3+12@650s、7+5@830s),且腐化转型 ~870s
    就到,压制需要 60-90s 造成杀伤 —— 窗口提前到 650s、阈值放宽到
    舰队 ≥3 + 追猎 ≥8(7 舰队局仍由 O241 闸覆盖,语义不重叠)。
    O304-②(o303a game_05 实证):快尖塔局腐化 723s 就出场,无克制窗
    根本不存在 —— 黄金窗推进把 6 暴风送进腐化区喂掉。可见腐化
    >max_corruptors → 否决(该局没有黄金窗,蹲守等配方)。
    O325-①(o324b game_04 实证):追猎阈 8→6 —— 暴风6+追6@800s 就是
    o305/o313 胜局编成,被 cap 8 挡在窗外,868s 腐化波收尸。
    O326-③(o325a game_04 实证):尖塔否决 —— 腐化计数闸反应太慢
    (990s 推时腐化 ≤2 过闸,28s 后涨到 4-6,暴风喂转型);尖塔可见
    = 腐化 30-60s 内必到(O304-②),整局按无黄金窗处理(蹲守等配方)。
    O354-③(o353 五局尸检):黄金窗永久 near-miss —— game_01 从 728s
    到 999s 报 12 次 near-miss,舰队 6-7 艘+敌腐化 0-4 的最佳窗口
    不推,等腐化爬到 13-17 舰队原地蒸发;胜局 g3 的 740s 果断推进
    就是胜因模板。放宽:腐化上限 2→4;t≥decay_t(750)后追猎阈
    6→4 时间衰减(越晚越等不起齐编,窗口在关闭)。尖塔否决/时间/
    舰队门不动。
    O356-③(o355a g2 实证):零腐化真窗追猎闸软化 —— 140s 零腐化
    真窗(679-819s)因追猎 5<6/2<4 被否 9 次 near-miss;暴风零腐化
    时射程白嫖纯地面,不需要追猎护航。corruptors==0 时追猎门降 0;
    corruptors 1-4 保持现有阈(6,t≥decay_t 降 4)。
    """
    if spire_seen:
        return False
    # O356-③:零腐化真窗不需要追猎护航(暴风白嫖纯地面),门降 0。
    if corruptors == 0:
        min_stalkers = 0
    # O354-③:时间衰减 —— t≥decay_t 后追猎门降到 decay_min_stalkers
    # (只降不升,自定义更低阈不被 decay 抬升)。
    elif now >= decay_t:
        min_stalkers = min(min_stalkers, decay_min_stalkers)
    return (
        now >= min_t
        and fleet_count >= min_fleet
        and stalker_count >= min_stalkers
        and corruptors <= max_corruptors
    )


def pivot_stalker_cap(corruptors: int, base: int = 12) -> int:
    """O303-③(o302b game_04 实证):反空军 pivot 追猎上限动态化。纯逻辑,可单测。

    O301-① 的固定 cap 12 治「追猎洪水挤暴风」,但腐化海(19-20 条,
    1080-1170s 实证)时暴风被 massive 加成克死,追猎是唯一能还手的
    兵种 —— cap 12 等于缴械。动态:腐化 0-8 时 cap 12(防洪水);
    腐化 ≥9 时按 1.5×腐化 放量(换比有利:追猎 blink 集火克腐化)。
    """
    return max(base, round(1.5 * corruptors))


def forge_rebuild_probe_yield(
    forge_ready: bool,
    defense_acute: bool,
    minerals: float,
    forge_price: float = 150.0,
) -> bool:
    """O294-①(o293a game_04 实证):forge 重建资金窗,探机让位。纯逻辑,可单测。

    局4:forge 随分矿阵亡后,重建的 150 矿资金窗被探机(50/个)+叉子吃干,
    塔链 tech_not_ready 刷 80s+(666-697s),塔 8→0 连锁丢三基。无就绪
    forge + 急性防御(threat/rush)+ 矿不够 forge → 暂停探机训练把资金窗
    让给 forge;forge 开工有钱/就绪后自动恢复(自校正,无 latch)。
    """
    return not forge_ready and defense_acute and minerals < forge_price


def carrier_reserve_ok(
    sg_ready: bool,
    threat_active: bool,
    enemy_supply: float = 0.0,
    own_supply: float = 9999.0,
) -> bool:
    """O294-②(o293a game_04 实证):航母攒钱预留的前置判据。纯逻辑,可单测。

    局4 675s:主基决死窗(敌 28-31 地面进家、我方地面兵 3、SG 已毁),
    carrier_reserve 停产攒 350 —— SG 死了航母根本产不出,停产=自杀。
    预留只在「有就绪 SG(产得出)+ 非急性威胁期(停得起)」才成立。
    O295-②(o294a game_02 实证):threat 侦测滞后 —— 911s 停产时 76-supply
    死亡波已在途(E9 到 915.5 才翻 threat);加敌我可见兵力对比闸:
    敌可见 supply > 我方军队 supply 时产线永不停(攒钱是波间隙特权)。
    O296-①(o295b game_02 实证):地面 0 + 敌不可见 0 时 0<=0 仍停产
    (791-851s 三连停)——改严格闸:敌 < 我才停,敌我同为 0 也不停
    (未知敌情下停产是赌博,波随时在盲区里)。
    """
    return sg_ready and not threat_active and enemy_supply < own_supply


def fleet_infra_rebuild_active(
    first_fleet_seen: bool, now: float, min_time: float = 300.0
) -> bool:
    """O294-③(o293a game_04 实证):舰队基建重建链开闸判据。纯逻辑,可单测。

    局4:SG 642s/FB 679s 被拆,到判负 100s+ 零重建 —— 开矿持有冻核心链、
    FB 重建闸要就绪 SG、威胁让位闸三层堵死,878 气烂银行。舰队曾成型
    (first_fleet_seen 证明基建曾存在过,非开局误触发)+ t≥300 → 允许
    cyber→SG→FB 链式钉点补建,不受 core_allowed 冻结。
    """
    return first_fleet_seen and now >= min_time


def zt_prewave_trickle_needed(
    fleet_infra_live: bool,
    gateway_ready: bool,
    ground_count: int,
    cap: int = 6,
) -> bool:
    """O292(D1,o291a game_01 实证):Zerg Timing 首波预备产兵判据。纯逻辑,可单测。

    实证:GW1 156s 就绪后空转 93s(rush 确认=波到脸才开闸),首叉 249s,
    波 278s 到脸只 1 叉+2 塔;同期矿 415/气 552 烂银行。GW 就绪即开闸
    预备产兵,cap 自校正(够数回舰队配方)——只动用闲置 GW 产能,不冻
    科技链(与 O208 证伪的 transition 冻星门不同)。
    fleet_infra_live(SG 就绪+FB 在场/在建)即关闸:舰队产能让位第一优先,
    地面只留 rush 分支/舰队配方比例补,防 trickle 压死舰队上量(败局层②)。
    注意 ZT 的 _fleet_transitioned 永假(transition 禁入),不能用它当闸。
    """
    return (
        not fleet_infra_live
        and gateway_ready
        and ground_count < cap
    )


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


def townhall_skips_placement(structure_name: str) -> bool:
    """O360-①(o359b 尸检):城镇厅(5x5)不走 ares 落位簿记。纯逻辑,可单测。

    o359b game_01 实证:O251 硬饱和钉点(_dispatch_structure(NEXUS))每帧
    刷「No BuildingSize.FIVE_BY_FIVE present in placement bookkeeping」
    (256 条/局,g2/g3 同命中)—— ares 神族落位簿记只生成 2x2/3x3 槽
    (placement_manager._solve_protoss_building_formation),5x5 请求恒
    warning+None → 钉点恒 no_placement 哑故障(O93/O334-④ 已两次记录
    同根因)。城镇厅落在矿点坐标本身(ExpansionController 同款,实战建成
    了全部 Nexus),调用方对名单内结构直接用 base_location 当落点。
    """
    return structure_name in ("NEXUS", "COMMANDCENTER", "HATCHERY")


def fb_fund_window(
    sg_ready: bool,
    fb_entities: int,
    fb_in_core: bool,
    threat_active: bool,
    timed_out: bool,
    vespene: float = 400.0,
    minerals: float = 150.0,
    window_open: bool = False,
    sg_started: bool = False,
    open_minerals: float = 300.0,
) -> bool:
    """O360-②(o359b 尸检):FB 专项基金窗判据。纯逻辑,可单测。

    o359b 实证:FB(300矿/200气)被塔/探机/Nexus/升级帧级插队,O110 自救
    3 局 ×10 全是 no_money(g1:490.8 派工 no_money、511s 工人干等、
    569.7 才 dispatched)。SG 就绪且 FB 无实体(在建即关窗)且无威胁
    (threat/rush 豁免,被骑脸时塔链优先)且未超时 → 开窗:调用方抑制
    探机(农≥28)/第 3+ 座塔/≥200 矿升级,把资金窗让给 FB 钉点。
    带 90s 超时(调用方计时,超时强制按现状派工一次后关窗)—— 吸取
    O106 全局资金冻结死锁教训:单建筑专项基金 + 超时 + threat 豁免,
    不做全局暂停。与 O353-③ fb_saving_window(禁 O261 虚空,口径
    present_or_pending)并存不打架:那道只管派工前,本窗管到实体落成。
    O362-④(o361b 尸检):开窗判据加资源路径 —— o361b 窗开 5 次
    (407-748s)零成交:判据不看资源,矿 <200 时抑制面再宽 FB 也买不
    起,白压经济。改「气 ≥400(FB 200 气耗就绪,成交只差矿)且
    (矿 ≥150 或窗已开)」:矿 <150 时不开窗白抑制;窗开后矿波动不
    关窗(滞回 —— 抑制攒矿正是窗的职责)。
    O366-①a(o365 双 lane 尸检):开窗触发从「SG 就绪」提前到「SG
    在途/动工」(sg_started)—— o365b g2 FB 自救 10+ 次 no_money、
    唯一落地 626.8s 仅 12s 即消失:SG 落成(~300s)才开窗,300/200
    在 SG 建造期(~60s)早被塔/探机/升级吃光,窗开了也只剩空银行;
    SG 一动工就开抑制,FB 钉点挂出时资金窗已攒好。
    O367-①(o366 双 lane 0/6 尸检):①a 回退,恢复 sg_ready 才开窗
    —— o366b g1 钱序倒错实证:胜局 Nexus(297)→SG(498)→FB(562)
    变 SG(329)→FB(406)→Nexus(430,被挤晚 133s),农峰 44 vs 72
    经济封顶;窗判据矿≥150 与 FB 造价 300 不匹配,o366a g2 连开
    3 次纯抑制窗(457/491/714s,矿 165/260/359 全买不起)零成交。
    sg_started 参数保留签名但不再入判据(向后兼容)。
    O368-①a(o367 双 lane 尸检):开窗矿判据 150→300(对齐 FB 造价)
    —— o367a 三局窗 452/599/627s 才开,开窗时矿净积累已 ≤0;o367b
    g1 四次开窗(768/835/1038/1181)两次零积累关窗空转:矿 150-299
    开窗,FB(300 矿)仍买不起,窗纯压经济。「矿≥150 且 10s 预期净
    收入 ≥150」的备选方案要多一条收入采样链,选实现简单的直接对齐
    造价;窗内矿波动不关窗的滞回保留(攒矿正是窗的职责)。
    """
    return (
        fb_in_core
        and sg_ready  # O367-①:回退 sg_started 前置(o366b g1 钱序倒错)
        and fb_entities == 0
        and not threat_active
        and not timed_out
        and vespene >= 400.0
        and (minerals >= open_minerals or window_open)  # O368-①a:150→300
    )


def fb_fund_window_stalled(
    minerals_delta: float,
    elapsed: float,
    window: float = 10.0,
) -> bool:
    """O367-①(o366a g2 实证):FB 基金窗健康监控 —— 窗开期间矿净
    积累 ≤0(10s 滑窗)立即关窗放行。纯逻辑,可单测。

    o366a g2 实证:窗连开 3 次(457/491/714s,矿 165/260/359 全买
    不起 300 的 FB)零成交 —— 旧关窗条件只有 FB 落成/90s 超时/
    气 <400,买不起时窗纯压经济(探机/塔/升级/trickle 全让位,
    矿却一点不涨)。调用方每 10s 采样一次矿量:净积累 ≤0 → 关窗
    放行一轮(冷却后再评),窗的职责是攒矿,攒不动就别压。
    """
    return elapsed >= window and minerals_delta <= 0.0


def fb_fund_probe_yield(fund_window: bool, workers: int, min_workers: int = 28) -> bool:
    """O360-②:FB 基金窗内探机让位判据。纯逻辑,可单测。

    窗内且农民 ≥min_workers(双矿近饱和口径,与 O355-① 母舰窗探机
    让位同阈值)→ 停训探机,50 矿/个让给 FB;窗随 FB 实体落成/超时
    自动关(自校正,无 latch)。
    """
    return fund_window and workers >= min_workers


def fb_fund_cannon_blocked(fund_window: bool, cannons: int, allowed: int = 2) -> bool:
    """O360-②:FB 基金窗内第 3+ 座塔抑制判据。纯逻辑,可单测。

    窗内且全局塔(实体+在途)≥allowed → 不再新钉塔(返回 True 让调用方
    拦派工);前 2 座保命塔照钉,threat 豁免在窗判据上游(fb_fund_window
    的 threat_active 参数),被压境时本判据恒 False。
    """
    return fund_window and cannons >= allowed


def fb_fund_upgrade_kept(
    fund_window: bool, upgrade_minerals: float, threshold: float = 200.0
) -> bool:
    """O360-②:FB 基金窗内升级注册过滤判据。纯逻辑,可单测。

    窗内 ≥threshold 矿的升级不注册(空军 2 攻/2 防 175-250 矿级,一笔
    顶大半座 FB);<threshold 的便宜升级与窗外一切升级照常(返回 True)。
    """
    return (not fund_window) or upgrade_minerals < threshold


def fb_fund_ground_yield(fund_window: bool) -> bool:
    """O362-④(o361b 尸检):FB 基金窗内 gateway 单位(floor 之上的部分)
    让位判据。纯逻辑,可单测。

    o361b 窗零成交共犯:窗内探机/塔/升级让位了,兵营单位没让 ——
    trickle 混编(O292,cap 3-6 叉/追猎 ≈300-700 矿)同帧抽干 FB 矿窗。
    窗内停 trickle(floor 保底不动,threat 豁免在窗判据上游)。
    """
    return fund_window


def fb_fund_sg2_blocked(fund_window: bool, stargates: int, allowed: int = 1) -> bool:
    """O362-④(o361b 尸检):FB 基金窗内第 2+ 星门抑制判据。纯逻辑,可单测。

    窗内且星门(实体+在途)≥allowed → 不再钉第 2 座(O326 SG2 钉点要
    FB pending 即放行,其 150 矿+150 气正是 FB 300/200 的同台竞争者);
    首座 SG 是 FB 前置,不在本判据管辖区。
    """
    return fund_window and stargates >= allowed


def fb_fund_probe_brake(
    window_open_s: float | None,
    minerals: float,
    workers: int,
    timeout: float = 45.0,
    fb_minerals: float = 300.0,
    min_workers: int = 20,
) -> bool:
    """O362-④(o361b 尸检):FB 基金窗 45s 凑不够矿的强制停探机判据。
    纯逻辑,可单测。

    o361b 窗开 5 次零成交的兜底:窗开 >timeout 秒矿仍 <fb_minerals
    (FB 造价)→ 既有抑制面失效,强制停探机一轮(农 ≥min_workers 才刹,
    小农局探机是收入本身);窄口刹车(窗随成交/90s 超时自关),非全局
    冻结(O106 证伪边界不动)。
    """
    if window_open_s is None or window_open_s < timeout:
        return False
    return minerals < fb_minerals and workers >= min_workers


def fb_bankrupt_needed(
    no_money_streak: int,
    threshold: int = 3,
    fb_missing_s: float | None = None,
    missing_window: float = 120.0,
) -> bool:
    """O368-①b(o367 双 lane 尸检):FB 破产分支触发判据。纯逻辑,可单测。

    o367a 实证:O110「FB 建造停滞>45s 自救=no_money」从 330-362s 起
    每 45s 循环到死(g1/g3 各 6-8 次)—— 基金窗+健康监控都救不回
    「塔+农+二矿吸干、开窗即穷」的局。O110 FB no_money 自救连续
    ≥threshold 次 → 调用方暂停一切非必要支出(O337 分矿塔/O363
    电池钉点/第 2+ 星门/升级,保命塔除外),直到 FB 钉下去或 threat
    激活。对单建筑的窄域暂停(O360 单建筑基金窗先例),不是全局
    资金冻结(O106 证伪边界不动)。
    O369-①b(o368 双 lane 尸检):触发口径放宽 —— ① no_money 改
    **累计** ≥threshold(不再要求连续:o368a g2 破产分支 526s 被
    threat 解除后 rush 常亮,连击再也攒不到 3,FB 到死没落);
    ② FB 缺失超 missing_window 秒直接触发(调用方只在 SG 就绪
    且 truly_missing 口径下传 fb_missing_s,opener 期不误触)。
    """
    return no_money_streak >= threshold or (
        fb_missing_s is not None and fb_missing_s >= missing_window
    )


def fb_bankrupt_cleared(fb_entities: int, threat_active: bool) -> bool:
    """O368-①b:FB 破产分支解除判据。纯逻辑,可单测。

    FB 实体出现(钉下去了,含在建)或 threat/rush 激活(被骑脸时
    防御链恢复优先)→ 解除暂停;无 latch,解除后 O110 连击计数
    重新积累,再破产再进。
    O369-①b(o368a g2 实证):解除去掉 rush 常亮屏蔽 —— g2 破产
    分支 526s 被 threat 解除后 rush 常亮,旧口径(threat or rush)
    下 latch 再也保不住;调用方改只传 threat_active(rush 期也保
    latch,只有 threat_active 才临时解除)。
    """
    return fb_entities > 0 or threat_active


def fb_fund_gas_gate(
    fund_window: bool,
    vespene: float,
    unit_gas: float,
    fb_gas: float = 200.0,
) -> bool:
    """O368-①c(o367b g3 实证):FB 基金窗内 SG 气耗闸。纯逻辑,可单测。

    o367b g3 实证:虚空 514s 产于 FB 窗 427-558 内(150 气),窗
    558s 零积累关窗 —— 窗内 SG 气耗单位把 FB 的 200 气预留吃掉。
    窗开期间气耗单位(虚空/风暴)只在 气 ≥ FB 气耗预留 + 单位气耗
    时才放行(造完仍够 FB 的 200 气);窗外恒放行。「SG 只许产不
    耗气单位」的备选要动配方层,选 diff 小的气线预留。
    """
    return (not fund_window) or vespene >= fb_gas + unit_gas


def stargate_deadlock_voidray(
    sg_idle_since: float | None,
    now: float,
    fb_entities: int,
    idle_threshold: float = 60.0,
) -> bool:
    """O368-②(o367 双 lane 尸检):星门死锁自救判据。纯逻辑,可单测。

    o367a 实证:g1 SG 277s 落成→699s 死零产出(空转 422s)、g3
    空转 388s —— 产线绑 fb_entities,FB pending(派工挂出但落不了)
    期 O261 虚空兜底被 O353-③ 攒钱窗抑制,SG 恒闲。就绪 SG 全闲
    连续 ≥idle_threshold 秒且 FB 未落成 → 调用方解绑转产虚空
    (VOIDRAY 只需 SG,不耗 FB 前置;o367b 胜局 VOIDRAY@418 证明
    虚空能撑中段);FB 落成(实体 >0)判据自灭,正常产线接管。
    """
    return (
        sg_idle_since is not None
        and fb_entities == 0
        and now - sg_idle_since >= idle_threshold
    )


def power_precheck_needed(powered_free: int, free: int) -> bool:
    """O368-③(o367a g1 (162,22) 尸检):SG/FB 钉点前供电预检判据。
    纯逻辑,可单测。

    o367a g1 实证:主基槽位(带电余=0, 空闲余=12, 总=25)—— 12 个
    空槽全部无电,FB no_placement 死等整局;贴槽水晶自救(O110)
    挂在 can_afford(FB) 分支内,no_money 循环里永不执行。带电
    空闲 3x3 槽 =0 且仍有空闲槽(补电能救,区别于 O357 的几何死槽)
    → 钉点前先在空闲槽旁 critical 钉一根水晶,水晶落地前建筑钉点
    挂起(「失败后补救」改成「钉点前预检」)。
    """
    return powered_free == 0 and free > 0


def new_base_f2_cannon_floor(
    age_s: float | None,
    target: int,
    window: float = 120.0,
) -> int:
    """O368-④a(o367 双 lane 尸检):新基地 F2 塔目标下限。纯逻辑,可单测。

    o367 实证:F2 注册 target=0(fb_missing 让位 FB)—— o367b g2
    二矿 450s 无塔掉落、g3 三矿全程无塔(两负直接死因),o367a g3
    二矿落成 28s 被拆;f2_wave_cannon_floor 触发 5 次但稳态
    target=0(35+ 波瞬时地板抬不解稳态裸奔)。落成 <window 秒的
    新基地 target 下限抬 1(首座保命塔不依赖敌 supply 瞬时地板);
    老基地/未知落成时刻 → 原值不动。
    """
    if age_s is not None and age_s < window:
        return max(target, 1)
    return target


def f2_survival_floor(
    target: int,
    cannons_ready: int,
    cannons_in_flight: int,
) -> int:
    """O372-①a(o371 双 lane 尸检):F2 target=0 的保命地板。纯逻辑,可单测。

    o371a g1 实证:主基整局 0 塔、首塔晚 234s —— 日志「F2 注册
    target=0」印的正是被 O210「买不起即归零」压 0 的 cannons,主基
    PSD target 直接归 0(分矿侧 O216j 有 min(_ec_min,2) 兜底,主基
    没有);o371b g3 三矿/o369b g3 二矿 target=0 同谱系(④a 的
    120s 新矿下限窗外 + O370 冻结钳可再压 0)。零塔基地(就绪+
    在途皆 0)target 下限 1 —— 首座保命塔豁免征用(O216j 分矿
    「保底塔不走归零」/O367-⑤a 保命塔同教义:钉点等几秒 > 基地
    整局裸奔);已有塔(含在途)或 target >0 → 原值不动。
    O373-②a(o372 三局 7 次 F2 注册 target=0 尸检):在途豁免收窄
    口径合同 —— cannons_in_flight 必须是「距本基 <15 格且派工
    工人存活」的局部口径(调用方 _in_flight_near;全图在途/工人
    已死的残留条目不算数)。在途塔黄了(订单取消/工人死/被拽走
    闲置)由调用方清 tracker 台账,清后本函数当帧抬 1 补注册。
    """
    if target == 0 and (cannons_ready + cannons_in_flight) == 0:
        return 1
    return target


def f2_target_literal(
    target: int,
    cannons_ready: int,
    cannons_in_flight: int,
) -> int:
    """O374-⑤(o373b 尸检):F2 注册 target 字面收口。纯逻辑,可单测。

    o373b 仍有 4 次「F2 注册 target=0」(全为在途豁免:就绪 0+
    在途 ≥1 时 f2_survival_floor 不动 target,字面 0 每轮尸检
    要人工解读)。在途/已有塔计入注册值:target=0 且(就绪+
    在途)>0 → 字面抬 1(报在途;to_count 口径含在途/已有,不
    会多建),「零 target=0」成字面硬口径 —— 再出现 target=0
    即真异常,尸检直读。在途黄了仍走 O373-②b 清台账补注册
    (分工不变)。
    """
    if target == 0 and (cannons_ready + cannons_in_flight) > 0:
        return 1
    return target


def f2_global_cannon_cap(
    cannons_main: int,
    cannons_expansion: int,
    bases: int,
    fb_done: bool,
    threat_active: bool,
    total_cap: int = 14,
    per_base_cap: int = 4,
) -> tuple[int, int]:
    """O376-④(o375b 尸检):F2 塔目标的全局总闸。纯逻辑,可单测。

    o375b g2 实证:塔目标三路叠加无总闸 —— F2 常态累积 + O375-②
    波次地板(≥3) + O366-①c FB 落成+2,塔峰 23 ≈3450 矿 ≈ 一艘
    半航母舰队,舰队资金被塔吃光。FB 落成后(舰队成型资金窗):
    全局帽 = min(总塔 ≤total_cap, 每基地 ≤per_base_cap),主基先
    占份额,分矿均摊余额;波到脸(threat/rush)豁免 —— 生死窗
    塔不设顶(O375-② 地板语义优先)。FB 未落成不钳(前期塔链
    /O268-② 底线/O274-② 分矿 fortify 原样)。帽内账:3 基地
    主 4+余额 10 均摊 5 取小 4 → 4+4×2=12;4 基地 4+10//3×
    3=13;均 ≤14。O375-② 地板 3 在任何基地数下都活(主 3+
    分 3×(n-1) ≤ 3n ≤ 14 对 n≤4 成立)。
    """
    if not fb_done or threat_active:
        return cannons_main, cannons_expansion
    main = min(cannons_main, per_base_cap, total_cap)
    remaining = max(0, total_cap - main)
    exp_cap = min(per_base_cap, remaining // max(1, bases - 1))
    return main, min(cannons_expansion, exp_cap)


def cannon_hard_cap_active(cannons_ready_total: int, hard_cap: int = 18) -> bool:
    """O377-③(o376b 尸检):全通道塔硬顶判据(就绪塔总数硬账)。
    纯逻辑,可单测。

    o376b 实证:O376-④ 的总帽被两处架空 —— ① main_siege 通道
    (carrier 流 6 塔/前线基地,flows.yml:130)不过
    f2_global_cannon_cap;② threat/rush 豁免 + O375 预警 30s 一
    循环,FB 落成后 threat 几乎常开,帽生效窗趋近零 —— 两胜局
    塔峰 17/21 全发生在台账外。判据:就绪塔总数(全图,与通道
    无关)≥hard_cap → 调用方对一切量产通道收口:threat 豁免在
    硬顶处截止(f2_global_cannon_cap 恢复钳制),main_siege 加强
    通道整体关闭(回退已钳制的常态目标)。豁免保留语义不变:
    <hard_cap 时 threat/rush 生死窗塔仍不设顶。17 在顶内(胜局
    配方不动),21 超顶被钳(o376b 实证口径)。
    """
    return cannons_ready_total >= hard_cap


def nexus_pin_yield_clamp(target: int) -> int:
    """O368-④b(o367 双 lane 尸检):Nexus 钉点让位钳新语义。纯逻辑,可单测。

    O365-④ 旧钳 min(target, cap) 整钳到固定档,把保命塔一并让位
    (o367b g2 二矿 450s 无塔掉落、g3 三矿全程无塔实证);改钳
    max(1, target-1) —— 让位只减 1 座,保底 1 座保命塔豁免于让位。
    """
    return max(1, target - 1)


def new_base_no_cannon_alarm(
    age_s: float | None,
    cannons_near: int,
    cannons_in_flight: int,
    window: float = 60.0,
) -> bool:
    """O368-④c(o367 双 lane 尸检):新基地 60s 无塔健康告警判据。
    纯逻辑,可单测。

    Nexus 落成 ≥window 秒仍零塔(就绪+在途皆为 0)→ 调用方打健康
    事件(30s 节流,只节流言)并走 critical 强钉通道(survival
    豁免基金/钳制闸)。落成时刻未知(台账外基地)→ 不告警。
    """
    return (
        age_s is not None
        and age_s >= window
        and (cannons_near + cannons_in_flight) == 0
    )


def fb_safe_anchor(
    slots: list,
    ramp_xy: tuple[float, float],
    occupied_fallback: bool = False,
) -> tuple[float, float] | None:
    """O366-①b(o365 双 lane 尸检):FB 落点保护锚 —— 主基塔阵后方。
    纯逻辑,可单测。

    o365b 实证:FB 唯一落地 626.8s 仅 12s 即消失(g3 落成 12s 被蟑螂
    黄金窗拔掉)—— FB 落在默认钉点(基地朝向/坡口侧),敌地面一
    波顺手就拆;重建 12 连败。派工锚强制选「离主基斜坡口最远的
    带电 3x3 空闲槽」(塔阵/基地本体挡在前面,蟑螂要穿整条防线才
    摸得到)。slots: [(x, y, free, powered), ...](_free_3x3_slots_at
    加电力标注,与 _dispatch_pin_reanchor 同口径);无带电空闲槽 →
    None(调用方退回默认落位,别为落点把 FB 卡死)。重建同口径
    (每次派工都过本判据)。
    O371-④(o370a g3 实证):occupied_fallback 保底落点 —— 无带电
    「空闲」槽时降级到「带电但非空闲」槽(force place 尝试,
    placement solver 在锚点周边自找空位)。g3 分矿试建禁用后
    O110 自救 ×8 全部落空、FB 整局悬空 = 科技链全断,落点判据
    不得成为 FB 的整局否决项;全无带电槽仍 None(退回默认落位)。
    """
    rx, ry = ramp_xy
    cands = [(x, y) for x, y, free, powered in slots if free and powered]
    if not cands and occupied_fallback:
        # O371-④:降级分支 —— 带电但非空闲槽(同取离坡口最远)
        cands = [(x, y) for x, y, free, powered in slots if powered]
    if not cands:
        return None
    return max(cands, key=lambda s: (s[0] - rx) ** 2 + (s[1] - ry) ** 2)


def fb_rescue_expansion_bypass(sid_name: str) -> bool:
    """O370-③a(o369a g2 实证):O110 自救「分矿试建」旁路收口
    判据。纯逻辑,可单测。

    o369a g2 实证:latch 攒到 345/320 后,FB 498.2s 开工走 O110
    自救「分矿试建」旁路,绕过 critical 钉点选址,钉在全场唯一
    无塔的分矿(落成后 333s 零塔,no_placement 死循环),534.4s
    被 4 个地面单位 35s 拆掉。FB 禁用分矿旁路(调用方改走主基
    critical 钉点+fb_safe_anchor 安全锚);SG 保留旁路(分矿
    3x3 槽位全新,O110 原语义)。
    """
    return sid_name != "FLEETBEACON"


def fb_arrival_guard_active(
    now: float,
    fb_building: bool,
    fb_completed_at: float | None,
    enemy_ground_visible: int,
    window: float = 60.0,
    min_enemy: int = 9,
) -> bool:
    """O366-①c(o365 双 lane 尸检):FB 落成增防闸。纯逻辑,可单测。

    o365b g3 实证:FB 642.9s 落成 12s 即被蟑螂黄金窗拔掉 —— 落成
    窗口敌地面一波到脸,塔目标还是常态值,防线没有为 FB 落成加厚。
    FB 在建 或 落成后 window 秒内,敌可见地面 >8(min_enemy=9)→
    调用方把主基塔 target 临时 +2(在 F2 全部钳制之后加,与 F2
    钳制体系兼容:钳制管常态,本闸管 FB 落成的生死窗)。
    """
    if enemy_ground_visible < min_enemy:
        return False
    if fb_building:
        return True
    return fb_completed_at is not None and now - fb_completed_at < window


def fb_fund_latch_needed(
    sg_ready: bool,
    fb_entities: int,
    threat_active: bool,
    minerals: float,
    vespene: float,
    fb_minerals: float = 300.0,
    fb_gas: float = 200.0,
) -> bool:
    """O369-①a(o368 双 lane 尸检):FB fund-first latch 常态判据。
    纯逻辑,可单测。

    o368a 实证:O368-①a 把基金窗判据改矿≥300 后 Timing 三局窗
    0 开(受压经济矿存永远够不到 300),FB 全靠 O110 no_money
    自救硬钉,g2 连钉 12 次(374→825s)落成 0 次 —— 矿 5-756
    反复被 Nexus/塔/电池/虚空抢走。改 latch 常态生效:SG 就绪
    且 FB 无实体且非 threat 且(矿 <fb_minerals 或气 <fb_gas)
    → 调用方停一切非保命支出(升级/SG2/分矿塔/电池 + 探机(农
    ≥28)/三矿+,保命塔与二矿未成交的 Nexus 豁免),攒够 300+200
    即钉。单建筑窄域暂停(O360 基金窗/O368 破产分支同谱系的
    加强),非全局资金冻结(O106 证伪边界不动)。
    """
    return (
        sg_ready
        and fb_entities == 0
        and not threat_active
        and (minerals < fb_minerals or vespene < fb_gas)
    )


def fb_latch_pin_afford_ok(
    minerals: float,
    vespene: float,
    sg2_reserve: bool,
    fb_minerals: float = 300.0,
    fb_gas: float = 200.0,
    sg_minerals: float = 150.0,
    sg_gas: float = 150.0,
) -> bool:
    """O375-③a(o374b 三局尸检):latch 钉 FB 的可负担判据(SG2
    预扣口径)。纯逻辑,可单测。

    o374b 实证:O374-③ 修好 Nexus 循环后二矿提前 150-240s,
    latch 提前触发(g1 450.2s/g2 395.1s)囤矿 300+200,SG2 饿死
    (851.8/871.9/全程没有 vs o373b 胜局 413.8s)—— 旧判据
    can_afford(FB) 在 300/200 即钉,SG2 的 150/150 永被 latch
    暂停清单压住。sg2_reserve=True(调用方:zerg timing 且 SG1
    就绪且 SG2 未钉)时攒矿口径改「存款 ≥FB+SG2 全款」—— SG2
    豁免钉点(见 sg2_pre_fb_pin_needed)在 latch 期随时可钉,
    本预扣保证 SG2 钉走后 latch 仍能攒回 FB 全款,FB 不被饿死;
    SG2 已在途/落成 → 预扣自灭,恢复 300/200 原口径。
    """
    if sg2_reserve:
        return (
            minerals >= fb_minerals + sg_minerals
            and vespene >= fb_gas + sg_gas
        )
    return minerals >= fb_minerals and vespene >= fb_gas


def fb_rebuild_latch_needed(
    fb_ever_completed: bool,
    fb_entities: int,
    sg_ready: bool,
) -> bool:
    """O372-②(o371b g2 尸检):FB 被拆后的重建 latch 触发分支。
    纯逻辑,可单测。

    o371b g2 实证:FB 554.5s 落成、591s 被拆,重建只剩 O110 自救
    通道 ×3 全 no_money 空转 170s 到死 —— 常态 latch 判据
    (fb_fund_latch_needed)要求矿 <300 或气 <200 才开攒,被拆瞬间
    银行若 ≥300 不 latch,其它支出照跑,等矿被花到 <300 已无可攒;
    threat 常亮期 latch 又临时解除,重建通道整段缺失。FB 曾落成
    (调用方簿记)且实体归零(被拆)且 SG 就绪 → 被拆瞬间直接进
    fund-first latch(同首建口径:停非保命支出+攒够 300+200
    critical 钉+fb_safe_anchor occupied_fallback 落点,O371-④ 起
    首建/重建同锚);解除沿用 fb_bankrupt_cleared(FB 实体出现/
    threat 临时解除)。
    """
    return fb_ever_completed and fb_entities == 0 and sg_ready


def forge_rebuild_guarantee_ok(
    tech_stall_s: float | None,
    forge_present_or_pending: bool,
    stall_window: float = 60.0,
) -> bool:
    """O377-⑥(o376b g1 尸检):forge 重建保底判据(科技建筑重建
    的 critical 资金通道)。纯逻辑,可单测。

    o376b g1 实证:594s 起分矿塔链 tech_not_ready 空转 292s —
    — forge 被拆后重建只靠 O333 常态钉点,非威胁期矿门
    (forge_pin_affordable 矿 ≥100)在「矿只有 40、气 524 烂
    银行」的受压局恒关,forge 永远不钉 → 没 forge 不能补塔,
    农民 43→7。判据:forge 无实体无在途 且 塔需求空转(调用方
    簿记:forge 缺失期间任一非主基基地就绪+在途塔 <2 的起点)
    ≥stall_window → 调用方走 critical 资金通道 critical 钉
    FORGE(150 预扣 = critical 钉点驻点等钱,critical 天然绕过
    dispatch_viable/矿门,对齐 FB latch 的「攒够即 critical
    钉」语义;落点走 O357 换锚 _dispatch_pin_reanchor,主基锚
    O351-① 教义)。只保 FORGE(diff 最小:BY/SG 空转无尸检
    证据,不同口径扩张)。
    """
    return (
        not forge_present_or_pending
        and tech_stall_s is not None
        and tech_stall_s >= stall_window
    )


def fb_latch_stalled(
    stall_since: float | None,
    now: float,
    window: float = 30.0,
) -> bool:
    """O369-①c(o368 尸检):FB latch 健康监控 —— latch 期矿净积累
    ≤0 持续 ≥window 秒 → 临时解除(调用方 60s 后重评估)。纯逻辑,
    可单测。

    与 O367-① 基金窗健康监控同教义:latch 的职责是攒矿,攒不动
    (受压局收入=支出)就别压 —— 暂停面再宽,零积累时它只压经济
    不攒 FB。stall_since: 最近一次 10s 采样仍零积累的起点(None=
    上一采样矿在涨,健康)。
    """
    return stall_since is not None and now - stall_since >= window


def fb_latch_pin_allowed(
    second_base_dealt: bool,
    nexus_hold_active: bool,
) -> bool:
    """O370-②a(o369b g3/o369a g3 实证):latch×Nexus 资金窗互斥
    仲裁判据。纯逻辑,可单测。

    o369b g3 实证:O364 Nexus 独占资金窗(498.1s hold 45s)被
    latch 的 critical 钉 FB(511.2s)压过,Nexus 假成交两次
    (528.2/558.2s),二矿推迟到 590.6s(晚 230-250s),农 49
    vs 配方 72-74。互斥仲裁:二矿未成交(无实体无在建,
    nexus_deal_confirmed 同口径)或 Nexus 资金窗独占期 → latch
    的 critical 钉 FB 排队等 Nexus 成交(Nexus 优先,单矿局不
    得出现 latch 压过 Nexus 窗);二矿成交且窗已放行 → latch
    钉点先行(舰队链恢复常态优先)。
    """
    return second_base_dealt and not nexus_hold_active


def fb_latch_trigger_gated(townhalls: int) -> bool:
    """O373-③a(o372b g3 实证):FB latch 触发门 —— 单矿局不触发。
    纯逻辑,可单测。

    o372b g3 实证:387.3s FB fund-first latch 在矿够 Nexus 时抽走
    475 矿,二矿派工 4 轮失败拖到 526.3s(420s 仍单矿)—— latch
    与首扩抢同一笔矿,latch 先攒先钉,Nexus 永远差一口气。二矿
    Nexus 无实体无在建(townhalls 含在建口径 <2)→ latch 不触发;
    Nexus 开工后恢复常态(钉点先后另受 O370-②a/O373-③b 仲裁)。
    """
    return townhalls >= 2


def fb_latch_yields_first_cannon(
    new_base_cannon_missing: bool,
    minerals: float = 0.0,
    reserve: float = 400.0,
) -> bool:
    """O372-①b(o371b g1 尸检):FB latch × 新矿首塔专款互斥判据。
    纯逻辑,可单测。

    o371b g1 实证:FB latch 431.5s 抽走 500 资源(攒够 300+200 即
    critical 钉),正好压掉新矿首塔窗 —— 450s 全矿仅 95 矿,首塔
    无款可钉。新矿首塔未立(任一落成新矿零塔,O367-⑤a
    new_base_survival_cannon_ok 保命塔口径,调用方算)→ latch 不
    触发、已激活也暂停钉 FB(150 矿首塔专款优先;首塔立起判据
    自灭,latch 恢复常态)。
    O373-①b(o372a g3 尸检):资金冗余门 —— 矿 ≥reserve(默认 400
    =塔 100+FB 300)时不让位,首塔与 FB 二者并行(g3 基金窗开时
    矿 300 气 522 充足仍让位空转三次实证,302.7/353.3/383.3s)。
    """
    return new_base_cannon_missing and minerals < reserve


def fb_yield_deadlock_fuse(
    yield_since: float | None,
    now: float,
    cannon_np_streak: int,
    timeout: float = 60.0,
    max_np: int = 3,
) -> bool:
    """O373-①a(o372a g3 尸检):让位死锁超时熔断判据。纯逻辑,可单测。

    o372a g3 实证:302.7/353.3/383.3s 三次「新矿首塔未立,latch
    钉 FB 让位」—— 被让位的二矿首塔因「带电余=0→贴槽水晶」+
    「O337 派工=no_placement」循环立不起(204.9s 落成→567.1s 才
    立,晚 362s),让位无任何超时/升级出口,FB 拖到 554.5s(vs
    基线 377.7s,+177s),舰队全程 0。让位持续 ≥timeout 秒 或 首塔
    (survival 豁免)派工连续 no_placement ≥max_np 次 → 判首塔链路
    坏死,调用方令让位自灭、恢复 critical 钉 FB(事件簿记;首塔
    立起后复位)。
    """
    return cannon_np_streak >= max_np or (
        yield_since is not None and now - yield_since >= timeout
    )


def pylon_rescue_pin_ok(
    last_pin_at: float,
    now: float,
    minerals: float,
    cooldown: float = 60.0,
    reserve_after: float = 300.0,
    pylon_cost: float = 100.0,
) -> bool:
    """O373-①c(o372a g3 尸检):O110 贴槽水晶自救冷却判据。
    纯逻辑,可单测。

    o372a g3 实证:O110 贴槽水晶自救把水晶从 8 钉到 30 根(基线
    10)≈烧 2000 矿,塔反因 no_money 立不起。同一基地 cooldown
    秒内不重复钉贴槽水晶(per-base 台账,调用方簿记),且钉后矿
    不得击穿 FB/塔专款下限(minerals-pylon_cost ≥reserve_after,
    即矿 ≥400 才钉);last_pin_at 传 -9999 = 本基地从未钉过。
    """
    return (
        now - last_pin_at >= cooldown
        and minerals - pylon_cost >= reserve_after
    )


def nexus_repin_loop_forced(loop_count: int, max_rounds: int = 1) -> bool:
    """O370-②b(o369a g3 实证):Nexus「条目消失无实体」死循环
    计数判据。纯逻辑,可单测。

    o369a g3 实证:Nexus 子系统 4 hold+3 fuse+8 次「条目消失无
    实体」死循环,9 分钟没落下二矿,全程单矿 —— O362 保险丝
    pop(等钱 >60s 强制释放)+30s 重钉冷却构成「钉→等→放→等
    冷却→重钉」空转。循环 >max_rounds 轮 → 调用方强制 critical
    直钉(EC 通道 max_on_route=99,清保险丝重钉冷却绕开 30s
    空等),「消失→重钉」60s 内收敛;成交即清零(调用方)。
    O371-③(o370a g3 实证):max_rounds 3→1(第 2 轮消失即强制
    直钉)—— o370a g3 二矿死循环 4 轮 279.6→409.8s=130s(验收
    ≤60s),旧阈第 4 轮才强制、每轮 ~30s 保险丝重钉冷却空等;
    第 2 轮即清冷却 critical 直钉,收敛 ~60s(2 轮 ×~30s)。
    """
    return loop_count > max_rounds


def nexus_repin_afford_ok(
    minerals: float,
    nexus_cost: float = 400.0,
    forced: bool = False,
) -> bool:
    """O374-③a(o373b g3 实证):Nexus 重派工的矿量门。纯逻辑,可单测。

    o373b g3 实证:「条目消失无实体」6 轮烧 150s,强制直钉
    (O371-③)第 2 轮起已生效(日志「强制直钉」可见)仍不收敛
    —— 发动机是等钱:银行在 20-445 振荡(381.7s 唯一一次够
    400,20s 内被保命开销吃掉),工人到位没钱,条目 30-60s 后被
    ares 清扫/保险丝 pop,重钉重走空转。矿 <400 不派工(调用方
    返回 "no_money",O364 hold 资金窗与 O51/O54 holding 让位
    继续攒钱),够了才钉 —— 钉即开工,循环失去燃料;循环计数
    只在「派了工又消失」时涨,no_money 期不涨。
    O375-⑤a(o374b g3 尸检):forced(循环 ≥2 轮,O371-③ 强制
    直钉同门槛)免矿量门 —— g3 三轮 no_money 重派工 336→424s
    原地空转(银行 88s 没过 400,保命开销持续吃钱):门后无派工
    = 零进展,驻点钉出后 O364/O51/O54 让位继续攒钱、矿到 400
    自动开工,等钱从「每帧空判」变「驻点等成交」。forced 路径
    自带 max_on_route=99+清保险丝冷却(O370-②b),与旧驻点空转
    (无强制、被 pop 即 30s 冷却)不同构。
    """
    return forced or minerals >= nexus_cost


def sg_idle_reset_needed(ready_sg: int, fleet_busy: bool) -> bool:
    """O369-②a(o368a g2 实证):星门空转计时器销账判据。纯逻辑,
    可单测。

    o368a g2 实证:自救报空转 223s(设计 60s)—— 旧口径「就绪
    SG 全闲,任何在产即销账」被在产虚空/先知(O261 死窗兜底/
    oracle 产线)打断:填线在产 ≠ 舰队产线复活,却把计时反复
    归零。新口径:只有「无就绪 SG」或「有 SG 在产舰队单位
    (TEMPEST/CARRIER)」才销账;在产 VOIDRAY/ORACLE(填线)
    保留计时(填线本身就是空转期的产物,不该销空转的证据)。
    """
    return ready_sg == 0 or fleet_busy


def sg_post_fb_fill(
    sg_idle_since: float | None,
    now: float,
    fb_entities: int,
    minerals: float,
    idle_threshold: float = 60.0,
    tempest_minerals: float = 300.0,
    voidrays: int = 0,
    voidray_cap: int = 2,
) -> bool:
    """O369-②b(o368a g3 实证):post-FB 矿穷填线判据。纯逻辑,可单测。

    o368a g3 实证:O368-② 自救按设计在 FB 落成后自灭,但矿穷期
    SG 照样空转 153-237s(FB 建成 ~481s→首风暴 590s)—— 舰队
    产线绑 can_afford(TEMPEST 300 矿),矿 <300 期 SG 全闲零
    产出。FB 已落、空转计时 ≥idle_threshold 且买不起风暴
    (矿 <tempest_minerals)→ 调用方允许产虚空填线(与 ① 的
    latch 兼容:latch 只活在 FB 未落时,本分支 FB 已落,天然
    不打架;矿够 300 正常产线接管,判据自灭)。
    O378-④(o377b g2 实证):虚空总量帽入判据(voidrays ≥cap 不
    填)—— g2 pre/post-FB 矿穷填线共产 9 虚空(1350 气),
    932-952s 在腐化+刺蛇环境全灭,FB 被饿到 @751(配方
    530-546),虚空在该环境是负资产;cap 默认 2,与 pre-FB
    填充帽(sg_prefb_voidray_fill 调用方 cap=2)同口径。
    """
    return (
        sg_idle_since is not None
        and fb_entities > 0
        and minerals < tempest_minerals
        and now - sg_idle_since >= idle_threshold
        and voidrays < voidray_cap
    )


def power_precheck_covered(sid_name: str, needs_power: bool) -> bool:
    """O369-③(o368a g1 (162,22) 实证):供电预检覆盖清单判据。
    纯逻辑,可单测。

    o368a g1 实证:首塔 O116 not_viable(带电余=0)268-315s 正是
    被穿窗口 —— O368-③ 的钉点前供电预检只盖 SG/FB,PHOTONCANNON
    钉点(needs_power 的防御建筑)同样需要「先贴槽水晶再钉」。
    覆盖清单:SG/FB(3x3)+ PHOTONCANNON/SHIELDBATTERY(2x2,
    needs_power 的防御建筑);水晶自身(needs_power=False)与
    无电建筑(Nexus/ASSIMILATOR 等)不入清单。
    """
    return needs_power and sid_name in (
        "STARGATE",
        "FLEETBEACON",
        "PHOTONCANNON",
        "SHIELDBATTERY",
    )


def power_precheck_stalled(
    now: float,
    precheck_since: float | None,
    window: float = 30.0,
) -> bool:
    """O377-⑤(o376a 尸检):供电预检滞留判据(钉水晶后塔落点必须
    重试)。纯逻辑,可单测。

    o376a 实证:O363/O368「带电余=0→先钉水晶」返回
    power_precheck 后调用方把结果直接丢弃 —— 不记失败簿记、不进
    O364/O365 手工锚点重试链;水晶在途/贴槽水晶资金门
    (pylon_rescue_pin_ok 矿 <400 不钉)卡住时塔落点永不再试,
    重建/新矿裸奔 150-400s(g1 二矿、g3 三矿直接因此丢基地)。
    判据:首次 power_precheck 起算(调用方 per-base 簿记)滞留
    ≥window(水晶早该落地)仍无塔 → True,调用方把该基地并入
    no_placement 重试链(手工锚点 30s 持续重试,O357 换锚同
    教义);dispatched/其它结果销账。
    """
    return precheck_since is not None and now - precheck_since >= window


def sg_power_reserve_needed(powered_free: int, free: int) -> bool:
    """O372-③(o371b g2/g3 尸检):SG 钉点前主基电力预留判据。
    纯逻辑,可单测。

    o371b 实证:g2 SG 停滞 O110 自救 ×3(446s 带电余=0)卡到 490s
    (晚 30-90s)、g3 SG 429.9s(O110×3)—— _build_core_structure
    通道(ares BuildStructure)没有 O368-③ 的钉点前供电预检,带电
    余=0 时 SG 落位静默 None 死等。判据与 power_precheck_needed
    同口径(带电余=0 且仍有空闲槽可救;几何死槽归 O357 换锚,
    簿记拿不到 (99,99,-1) 不触发),调用方在 SG 钉点前 critical
    钉 1 根贴槽水晶(在途水晶守卫防重复钉,与既有 precheck 合并,
    别重复钉),把「带电余=0」从 SG 停滞原因里消掉。
    """
    return power_precheck_needed(powered_free, free)


def reanchor_fallback_default(
    sid_name: str,
    blacklist_len: int,
    threshold: int = 1,
) -> bool:
    """O369-④(o368a g1 实证):opener 关键链换锚死锁的快退化判据。
    纯逻辑,可单测。

    o368a g1 实证:BY 换锚黑名单二连黑后进 O358-④b 的 60s 冷却,
    BY 拖到 221s,237s 狗毒爆破塔时没活到 SG —— 冷却对 opener
    关键链是死等:60s 里科技链全停。黑名单 ≥threshold → 不进
    冷却,调用方直接回退主基内侧常规槽(ares 默认 placement
    通道,不带 closest_to)。仅 CYBERNETICSCORE/GATEWAY 等
    opener 关键链生效:forge 已有 O351 主基锚,机械台非 opener
    关键链,维持原冷却。
    O370-④a(o369a Timing 三局实证):阈值 ≥2→≥1 —— 三局黑
    名单 ≥2 全部未触发(g3 黑名单仅 1 就把 BY 拖到 245s),首
    次换锚失败即回退默认槽,不等二连黑。
    """
    return sid_name in ("CYBERNETICSCORE", "GATEWAY") and (
        blacklist_len >= threshold
    )


def cannon_investment_freeze(
    enemy_corruptors: int,
    wave_active: bool,
    corruptor_min: int = 4,
) -> bool:
    """O369-⑤(o368b g2 实证):塔投资总量闸。纯逻辑,可单测。

    o368b g2 反面教材:956s 有 25 座塔(≈3750 矿 ≈ 9 艘航母)
    被腐化波逐波拆光,同期舰队停 6 艘 —— 塔保不住被狙的舰队,
    腐化波需要的是舰队数量。threat 波(wave_active,敌 35+
    supply,O367-⑤c 同口径)仍可按 wave floor 补 —— 冻结管常态
    投资,不管波到脸的生死窗。
    O370-①a(o369 双 lane 尸检,6/6 局误触发真回归):触发口径
    改认**实际可见腐化 ≥corruptor_min** —— 旧判据「t>600 且
    (腐化≥4 或舰队<8)」在舰队成型前恒真,t>600 常开,全部在
    敌可见腐化=0(或腐化首见前 270-360s)开火,与 spec「腐化
    ≥4」系统性不符(o369a g1 三矿钳 0 塔被 29 地面抄丢、o369b
    g1 三矿 target=0 裸奔 44s 被拆)。腐化计数从 enemies 读,
    与 zt_golden_window_push 的腐化口径一致(调用方同一计数)。
    """
    return (not wave_active) and enemy_corruptors >= corruptor_min


def cannon_freeze_clamp(
    target: int,
    existing: int,
    floor_snapshot: int,
    new_base_exempt: int = 0,
) -> int:
    """O370-①b/①c(o369 双 lane 尸检):冻结钳制断向下棘轮+新矿
    首批豁免。纯逻辑,可单测。

    ①b 断棘轮:旧钳「min(target, 现有塔数)」是向下棘轮 —— 塔被
    拆 → 现有更少 → 目标更低(o369a g1:8→5→4→2,871.8s 无塔)。
    改钳 min(target, max(现有, 冻结启动时的注册 target 快照)):
    冻结期被拆的塔按快照补回,快照外不再新增投资(钱让给舰队)。
    ①c 新矿豁免:新矿(落成 <120s,O368-④a 同口径)首批塔
    (注册 target 内)不计入冻结钳制 —— 旧钳把全局 0 塔的新矿
    F2 target 钳 0(o369b g1 三矿 target=0 裸奔 44s 被拆);
    每个新矿名额 +1,与 O368-④a 的首座保命塔下限对齐。
    """
    return min(target, max(existing, floor_snapshot) + new_base_exempt)


def zerg_sg_pin_lane_active(opp_race: str, ai_build: str) -> bool:
    """O376-①(o375 双 lane 尸检):SG/FB 钉点家族(SG2 预扣/舰队缺口
    硬钉/pre-FB 虚空填充/post-FB 填线/30s 重钉/SG2 紧随 FB)的
    种族门。纯逻辑,可单测。

    o375b 实证:bench zerg lane 协议含 `--ai-build Rush`
    (_ai_build=="rush"),SG 钉点家族三处 `== "timing"` 单值门把
    rush lane 整族关门外 —— g2 有 341.5→630.8 整整 290s 的
    「SG1 就绪+FB 未落」窗口,SG2 钉点/虚空填充一次没进。同款
    前科:O364-① 被同一 "timing" 门门住(见本文件 4016 行附近
    注释)。口径与 wave_cannon_floor_active(O374-④c)对齐:
    zerg timing/rush 开门(rush 出 transition 后舰队成型走同一
    SG/FB 通道,判据内的经济/威胁闸不变);zerg power/terran/
    protoss 无尸检证据,不开。
    """
    return opp_race == "zerg" and ai_build in ("timing", "rush")


def sg2_pre_fb_pin_needed(
    sg1_ready: bool,
    sg_total: int,
    fb_entities: int,
) -> bool:
    """O375-③a(o374b 三局尸检):zerg lane SG1 落成即钉 SG2 判据。
    纯逻辑,可单测。

    o373b 胜局配方:SG2@413.8s + 12 虚空 + 82 supply 是中段支柱;
    o374b latch 提前触发后 O326-②(FB 在途+气 ≥400+豁免 latch/
    基金窗全不满足)与 O369-⑥(要求 FB 已落成)双双够不到,SG2
    饿死到 851.8/871.9/全程没有。SG1 就绪且 SG 总数(含在途)<2
    且 FB 未落成 → 调用方 critical 钉 SG2(豁免疫 FB latch 暂停
    清单与基金窗 SG2 让位;150/150 由 fb_latch_pin_afford_ok 的
    预扣口径保底,FB 不被饿死)。FB 落成后本判据自灭,SG2+/SG3
    回归 O326-②/O369-⑥ 常态通道。二矿/Nexus 资金窗两道既有
    让位闸(sg2_pin_economy_ok、nexus_fund_hold_blocks)在调用
    方保留 —— SG2 不抢扩张全款。
    """
    return sg1_ready and sg_total < 2 and fb_entities == 0


def e10_sg2_pin_needed(e10_transitioned: bool, sg_total: int, sg_max: int = 2) -> bool:
    """O378-②(o377a 三局尸检):E10 航母转型点即钉 SG2 判据。
    纯逻辑,可单测。

    o377a 实证:E10 时间盒(O377-②)480s 准点触发,但单 SG+风暴
    排队,首航母落地还要 +130-155s(608-638s,验收 ≤480s 永远
    FAIL),三局 SG2 全在 743s+ —— fleet≥5@[500,570] 数学上不可
    达,recipe_push_exempt(O377-①b)的 [500,570] 窗成死代码。
    转型点/时间盒触发(调用方 latch)即 critical 钉 SG2:豁免
    FB 基金窗预扣(fb_fund_sg2_blocked 不入闸,与 O375-③a 的
    「豁免疫 FB latch/基金窗」同教义;FB 已落成或时间盒硬转时
    基金窗已关,语义不冲突);SG 总数(含在途)≥sg_max 判据自灭,
    回归常态通道。二矿让位(sg2_pin_economy_ok)与 Nexus 资金窗
    独占(nexus_fund_hold_blocks)两道既有闸在调用方保留 ——
    SG2 不抢扩张全款。
    """
    return e10_transitioned and sg_total < sg_max


def sg_prefb_voidray_fill(
    ready_sg: int,
    fb_entities: int,
    voidrays: int,
    cap: int = 8,
) -> bool:
    """O375-③b(o374b 三局尸检):pre-FB 星门闲置即产虚空填充判据。
    纯逻辑,可单测。

    o374b 实证:O368-② 死锁自救要 SG 全闲 60s 才转产,叠加 latch
    期不产,虚空峰 2/4/1 vs o373b 胜局 12(胜局中段支柱正是
    虚空群);SG 落成到 FB 落成动辄 100-200s,60s 死锁门槛把
    填充窗砍掉大半。改为就绪 SG 存在且 FB 未落成即允许填充
    (O368-② 同通道合并,不另立分支;O369-②a 的空转计时器保留
    给 ②b post-FB 矿穷填线),cap 4→8(验收口径虚空峰 ≥6,胜局
    12 含常态产线;填充通道留气给舰队接力)。latch 期不产
    (攒钱给 FB+SG2,调用方闸),latch 解除自动恢复。
    O378-④(o377b g2 实证):zerg lane 调用方 cap 8→2 —— 腐化+
    刺蛇环境虚空是负资产(g2 pre/post-FB 矿穷填线共产 9 虚空
    1350 气,932-952s 全灭,FB 被饿到 @751);cap 参数化不动
    函数本体,terran lane 不经本通道(zerg_sg_pin_lane_active
    门),行为一行不变。
    """
    return ready_sg > 0 and fb_entities == 0 and voidrays < cap


def sg_gap_pin_needed(
    fb_entities: int,
    ready_sg: int,
    ready_sg_all_busy: bool,
    fleet: int,
    sg_total: int,
    minerals: float,
    vespene: float = 0.0,
    fleet_min: int = 8,
    sg_max: int = 3,
    min_minerals: float = 150.0,
    gas_min: float = 300.0,
) -> bool:
    """O369-⑥(o368b g2 实证):星门按舰队缺口硬钉判据。纯逻辑,可单测。

    o368b g2 实证:O218 追加星门等气烂银行(气 ≥400)触发,794s
    才动、到死只有 3 座(胜局 844s 已 7 座)—— 舰队缺口在前、
    气淤积在后,等气就是等死。FB 落成后:就绪 SG 全忙(产线
    满载,再加产能不浪费)且舰队(含在产)<fleet_min 且 SG 总数
    <sg_max → 调用方直接 critical 钉 SG2/SG3(不等气烂银行);
    矿 <min_minerals 不钉(与 O367-⑤b 矿门兼容:穷局钉点
    no_money 事件空转,o366b 三次实证)。
    O370-⑤a(o369b g3 实证):「就绪 SG 全忙」对「单 SG 空转+气烂
    银行」场景永假 —— g3 单 SG 空转、气烂 579 无人转化,条件
    永远够不到全忙。追加出口:SG 总数 <2 且气 ≥gas_min(单 SG
    空转局直接钉 SG2,与 O218 的气烂银行同语义但不等 400);
    全忙路径(SG2→SG3)保留不动。
    """
    return (
        fb_entities > 0
        and fleet < fleet_min
        and sg_total < sg_max
        and minerals >= min_minerals
        and (
            (ready_sg > 0 and ready_sg_all_busy)
            or (sg_total < 2 and vespene >= gas_min)
        )
    )


def stargate_pin_retry_needed(
    pin_at: float,
    now: float,
    sg_pending: bool,
    window: float = 30.0,
) -> bool:
    """O370-⑤b(o369 尸检):O218/O369-⑥ 追加星门钉点 30s 未落成
    重试判据。纯逻辑,可单测。

    o369 实证:O218 两次追加「dispatched 后没落成」—— 钉点派工
    后气被产线花掉,气门(≥400)回落,触发闸永久关闭;条目若被
    O362 保险丝/O118-② 快回收 pop(工人走位中死亡/被拽)就再也
    没人重钉。钉点时刻起 window 秒仍无 SG 实体无在途 → 调用方
    无条件重钉一次(不依赖气门),并重计 30s;sg_pending(实体
    含在建+tracker 在途任一)即销账。
    """
    return pin_at > 0.0 and now - pin_at >= window and not sg_pending


def tempest_gas_dump_ok(
    vespene: float,
    fleet_total: int,
    vespene_threshold: float = 400.0,
    fleet_cap: int = 8,
    stargates: int = 2,
    carriers: int = 1,
) -> bool:
    """O366-②b(o365 双 lane 尸检):气爆折现判据。纯逻辑,可单测。

    o365 实证:6 局矿常年 <200、气溢出 300-1700,星门 257-269s 就
    闲置 —— O260 兜底要「气 ≥500 且买不起航母」才点风暴,矿枯局
    烂气永远折不成舰队。放宽:气 ≥400 且舰队(TEMPEST+CARRIER 含
    在产)<fleet_cap 时,O260 通道不再要求「买不起航母」,空闲就绪
    星门直接点风暴(把烂气折成舰队)。与 tempest_dump_suppressed
    联动不打架:航母(含在产)<2 时仍航母优先(本判据只在抑制闸
    下游起效)。舰队 ≥8 停止折现(数量够了,气留给航母接力)。
    O367-③(o366a Timing 0/3 尸检):折现加门槛 —— o366a 三局风暴
    全排航母前(g1 风暴×3@711-799→航母 964;g3 ×3@715-828→932;
    基准胜局航母前只有 1 艘),首航母 719→948s:穷局(舰队<8、
    单星门)把仅有的气和星门产能给了风暴。舰队 ≥8 或 SG ≥2 或
    已有 ≥1 航母(含在产)才允许折现;穷局单星门保航母气和产能。
    """
    return (
        vespene >= vespene_threshold
        and fleet_total < fleet_cap
        and (fleet_total >= fleet_cap or stargates >= 2 or carriers >= 1)
    )


def extra_stargate_minerals_ok(
    minerals: float, min_minerals: float = 150.0
) -> bool:
    """O367-⑤b(o366b 尸检):O218 追加星门矿判据。纯逻辑,可单测。

    o366b 实证:O218 追加星门三次在矿 <150 时钉点 no_money 事件
    空转,气随后被泄掉永不重试 —— 钉点挂出时根本买不起(星门
    150 矿),驻点等钱变驻点空转。矿 ≥150(SG 造价)才派工,否则
    等矿帧重试而非事件空转。与 O301-③ 移除 can_afford 帧判不
    矛盾:那是防「矿振荡 0-175 闸不开钉点永不成立」;本门只看
    单一矿价,钱到即钉,语义是「买得起才挂点」。
    """
    return minerals >= min_minerals


def gas_stop_repull_action(in_gas_book: bool, carrying_vespene: bool) -> str:
    """O366-②c(o365 双 lane 尸检):停气复拽的离气矿动作。纯逻辑,可单测。

    o365 实证:停气校验环复拽 3-8 次/局、增速越拖越大 —— 根因是
    O364-③b 校验环只改 role+台账,**不下离气矿命令**:被 ares
    Mining 补气重挂簿记的农民保持原 gather(气矿) 指令继续采气,
    气增速压不下去 → 下次校验再判泄漏再复拽(空转循环)。复拽必须
    与首次拉动同口径下命令:载气 → return_resource(卸货即离气);
    未载气 → smart 到最近矿簇;不在气矿簿记 → 不动。
    """
    if not in_gas_book:
        return "none"
    return "return_resource" if carrying_vespene else "smart_mineral"


def f2_clamp_supply_cap(
    enemy_supply: float,
    low_cap: int = 2,
    high_cap: int = 4,
    supply_tier: float = 35.0,
) -> int:
    """O366-③a(o365b g3 实证):F2 钳位的动态档。纯逻辑,可单测。

    o365b g3 实证:O365-④ 钳 2/2 期间每基地 target=2,E6 五次
    「塔 1/2 座压不住」被 42-supply 波滚死 —— 钳制是给 Nexus 钉点
    让资金的常态档,敌大波可见时还钳 2 = 拿基地换 Nexus。敌可见
    supply >35 → 钳位上限放宽到 4(波防得住,Nexus 晚几秒);
    ≤35 保持 2/2 原档。
    """
    return high_cap if enemy_supply > supply_tier else low_cap


def f2_wave_cannon_floor(
    enemy_supply: float,
    cannons: int,
    supply_tier: float = 35.0,
    floor: int = 3,
) -> int:
    """O367-⑤c(o366 六局尸检):F2 塔目标的 35+ 波地板。纯逻辑,可单测。

    O366-③a 动态档(钳位内 supply>35 → 上限 4)六局零触发 —— 根因
    不是 supply 源错,是作用窗错位:动态档只活在 nexus_pin_yield_
    gate 钳制窗内(矿≥400 且二矿未钉,~40-60s,250-530s),而 35+
    supply 波全部 614s+ 才可见(o366 六局日志实证:钳 2/2 事件
    与 supply>35 窗口零重叠),钳制随「Nexus 钉点成交」解除后波
    才来。改接到威胁窗:敌可见 supply >35 时 F2 塔目标强制 ≥3
    (在 fb_waiting/holding/O216d 等 min 链之后抬回,35+ 波是
    生死窗,基金让位不适用于波到脸);≤35 零变化。
    """
    if enemy_supply > supply_tier:
        return max(cannons, floor)
    return cannons


def wave_cannon_floor_active(opp_race: str, ai_build: str) -> bool:
    """O374-④c(o373a 三局尸检):F2 35+ 波塔地板的种族门。纯逻辑,可单测。

    O367-⑤c 旧门只认 zerg timing/rush —— o373a Terran 三局敌
    35+ supply 窗口地板零触发(门本身没开,f2_wave_cannon_floor
    判据无恙),550-700s 塔厚度不够被 MM 波连穿。terran 全 build
    开门(与 timing_defense_chain_active 的 O371-①b/c 去门同
    教义:terran 证据充分,zerg 原口径逐项等价);protoss 无尸检
    证据,不开。
    """
    return (opp_race == "zerg" and ai_build in ("timing", "rush")) or (
        opp_race == "terran"
    )


def enemy_supply_credited(visible_supply: float, sticky_peak: float) -> float:
    """O375-④(o374b g2 实证):敌 supply 信用口径。纯逻辑,可单测。

    o374b g2 实证:两次 O302 commit 后 3-10s 敌 51-79 supply 才
    显形 —— 出发闸/塔地板只认当帧可见(enemy_units),波在迷雾
    里集结时口径归零,出击即顶波。口径 = max(当帧可见, remembered
    峰值)(aa_peak_sticky 同构粘滞簿记,调用方每帧喂当帧可见值;
    O375-② 塔地板与本出发闸共用同一台账)。O376-③:supply 台账
    粘滞窗 60s→120s(对齐 Zerg Rush 90-120s 波次节奏,o375b 出击
    正撞 60s 侦察空窗实证);AA 粘滞窗不动(60s 已验证)。
    """
    return max(visible_supply, sticky_peak)


def wave_cannon_floor_trigger(
    credited_supply: float,
    opp_race: str,
    now: float,
    peak_need: float = 30.0,
    terran_time: float = 480.0,
) -> bool:
    """O375-②(o374 双 lane 尸检):F2 波次塔地板的预警触发判据。
    纯逻辑,可单测。

    O374-④c 的触发源「敌可见 supply>35」= 讣告:o374a 三局地板
    全部在波已进门后才抬(g1 547.9/g2 833.3/g3 812.6),塔峰 4-6
    反而低于胜局 11 —— 波在迷雾集结时可见 supply 归零,进门才
    显形,塔建造要 25-29s,进门再抬永远晚一拍。改预警口径:
    信用 supply(enemy_supply_credited = max(当帧可见, remembered
    峰值;O376-③ 起 supply 台账窗 120s))≥peak_need 即触发(波离
    视野一个波次周期内仍认账,进门前把塔立起来);terran 加
    t ≥terran_time 定时兜底
    (o374a 三局 MM 波全部 527s+ 到门,480s 起常态抬地板,
    不依赖侦察是否撞见集结)。峰值 35→30:粘滞峰值含已交战的
    波,30 即生死窗(O367-⑤c 的 35 是当帧口径,信用口径同量
    级前移)。种族门仍在调用方(wave_cannon_floor_active)。
    """
    return credited_supply >= peak_need or (
        opp_race == "terran" and now >= terran_time
    )


def zt_expand_reserve_exempt(
    enemy_supply: float,
    now: float,
    prev_exempt: bool,
    high: float = 30.0,
    low: float = 20.0,
    time_floor: float = 500.0,
) -> bool:
    """O366-④a(o365a g3 实证):O126 zerg_timing_expand_reserve 威胁
    豁免闸(带滞回)。纯逻辑,可单测。

    o365a g3 实证:599s 敌压境时 expand_reserve 仍锁死地面(兵力
    ={},纯塔独木撑)—— O298-② 的「敌 supply < 我方」闸在我方
    supply 也高时恒真,敌 40-76 supply 决胜波照停产。敌可见
    supply >30 或 t>500 → 强制解除(豁免期产线不停);滞回:豁免
    后敌 supply 降到 <20 才恢复预留(t>500 时间档不可逆,恒豁免)。
    """
    if now >= time_floor:
        return True
    if prev_exempt:
        return enemy_supply >= low
    return enemy_supply > high


def expand_exempt_zealot_only(
    exempt: bool,
    expand_holding: bool,
    nexus_unstarted: int,
) -> bool:
    """O367-④a(o366b g1 实证):expand_reserve 豁免期产兵限叉判据。
    纯逻辑,可单测。

    o366b g1 实证:矿 5-120 穷局豁免期维持 8-13 地面兵,追猎(50
    气/只)抢航母气 —— O366-④a 豁免的本意是「敌压境/t>500 时
    expand_reserve 别锁死地面产线」,不是放开气耗单位。判据与
    expand_reserve 分支同上下文(豁免激活 且 Nexus 钉点未开工的
    持有期)才限 ZEALOT:返回 True = 调用方把 spawn 换成纯叉
    (100 矿/个,零气耗);豁免外的常态产线(舰队/追猎核)零变化。
    """
    return exempt and expand_holding and nexus_unstarted > 0


def fleet_formed_release_rush(
    fleet_count: int,
    defense_score: float,
    min_fleet: int = 3,
    min_score: float = 15.0,
) -> bool:
    """O366-④b(o365b g2 实证):O203「舰队成型解除 rush」改判实际
    舰队数。纯逻辑,可单测。

    o365b g2 实证:「舰队成型解除 rush」在舰队=0 时虚报 5 次 ——
    旧判据拿 _fleet_transitioned(转型旗标)+防御评分当舰队,旗标
    可以被 SG/FB 基建单独撑起,实际 TEMPEST+CARRIER=0 也「成型」。
    改判实际舰队数(TEMPEST+CARRIER)≥min_fleet 且防御评分达标才
    解除 rush 经济锁。
    """
    return fleet_count >= min_fleet and defense_score >= min_score


def rush_economy_release(
    defense_score: float,
    workers: int,
    now: float,
    confirmed_at: float | None,
    min_score: float = 15.0,
    worker_floor: int = 40,
    hard_window: float = 180.0,
) -> bool:
    """O380-①:防御站稳或经济锁超时后解除 full rush-lock。纯逻辑。

    o379 三局的死锁链是 ``rush_active`` 要等舰队成型才解，而舰队又要
    依赖被 rush-lock 冻住的农民/扩张经济。解除条件改为两条并联：

    - 防御评分达到 O203 已验证的 15 分，说明塔/地面包已能接管守家；
    - 农民仍低于 40 且确认 rush 已持续 180 秒，硬时间盒防评分口径失效。

    这里只解除经济级 full rush-lock；E9 threat response 仍负责敌军压境时
    的守家、铺塔与暂停扩张。
    """
    if defense_score >= min_score:
        return True
    return (
        workers < worker_floor
        and confirmed_at is not None
        and now - confirmed_at >= hard_window
    )


def probe_economy_hard_floor(
    workers: int,
    bases: int,
    floor: int = 40,
    workers_per_base: int = 22,
) -> bool:
    """O380-①:探机不可被 hold/yield 压过的经济硬底线。纯逻辑。

    单矿仍按 22 农容量，避免开局为了追 40 农反而拖死二矿；Nexus 开工后
    基地数达到 2，目标立即抬到 40，覆盖 o379 的 31-45 农停滞区。
    """
    target = min(floor, workers_per_base * max(1, bases))
    return workers < target


def terran_false_rush_release(
    opp_race: str,
    verdict: str,
    military_structs: int,
    combat_units: int,
    now: float,
    release_at: float = 260.0,
) -> bool:
    """O380-④:Terran 二次侦查零兵时撤销早期 rush 误判。纯逻辑。

    o379b 在 78.8 秒仅凭一座兵营进入 O92 应急形态，但 260 秒复查仍是
    一兵营、零作战单位；真实首波直到 502-538 秒才出现。该形态不是早期
    all-in，继续冻结经济/舰队链只会白烧 300 秒运营窗。
    """
    return (
        opp_race == "terran"
        and now >= release_at
        and verdict == "unknown"
        and military_structs <= 1
        and combat_units == 0
    )


def gas_hard_stop_required(
    rush_window: bool,
    mineral_crisis: bool,
    early_pull: bool,
    imbalance_pull: bool,
    gas_restore: bool,
) -> bool:
    """O380-②:停气硬切换总闸。纯逻辑。

    返回 True 时调用方把 ares ``workers_per_gas`` 直接切到 0，并一次性
    抽干现有采气农；不再靠气增速校验环发现泄漏后反复复拽。
    """
    return (not gas_restore) and (
        rush_window or mineral_crisis or early_pull or imbalance_pull
    )


def new_base_cannon_fund_needed(
    is_expansion: bool,
    cannons_near: int,
    cannons_in_flight: int,
) -> bool:
    """O380-③:Nexus 开工即为首座分矿塔开启 150 矿窄域基金窗。"""
    return is_expansion and cannons_near + cannons_in_flight == 0


def cannon_fund_nonmoney_release_due(
    window_age: float,
    can_afford_cannon: bool,
    cannon_tracked_or_in_flight: bool,
    min_age: float = 15.0,
) -> bool:
    """O384-③:首塔基金只解决缺钱，placement/无工不冻结90s。"""
    return (
        window_age >= min_age
        and can_afford_cannon
        and not cannon_tracked_or_in_flight
    )


def local_defense_pylon_capped(
    pylons_near_base: int,
    cap: int = 3,
) -> bool:
    """O385-①:分矿防御供电自救局部最多3根水晶。"""
    return pylons_near_base >= cap


def healthy_mining_sufficient_to_stop_extra(
    *,
    bases: int,
    healthy_ready_bases: int,
    workers: int,
    normal_expand_floor: int = 4,
) -> bool:
    """O385-②:四矿后健康矿区已达标则停正常饱和扩张。"""
    return (
        bases >= normal_expand_floor
        and healthy_ready_bases >= healthy_mining_base_target(workers)
    )


def nexus_priority_fund_active(
    now: float,
    current_bases: int,
    peak_bases: int,
    target_bases: int | None,
    first_expand_arm_at: float = 220.0,
) -> str | None:
    """O381-①/②:首扩硬截止与分矿损失恢复共用的 Nexus 独占基金。

    第一性原理:基地是矿物收入的生产资料。单矿在 220s 后仍未开始扩张，
    或已拥有的分矿被摧毁后仍拿钱造兵/升级，都会让后续每一分钟收入永久
    低于对手，资源差按时间积分滚雪球。调用方在基金期暂停非生存开销并
    强制注册 ExpansionController，直到 Nexus 实体出现（townhalls 会计入
    在建 Nexus）自动解除。

    返回 ``first_expand`` / ``lost_base`` 供事件簿记，None 表示不启用。
    0 基地由既有 Q4 重建路径处理；未配置扩张目标的流派不介入。
    """
    if target_bases is None or target_bases < 2 or current_bases <= 0:
        return None
    if peak_bases > current_bases and current_bases < target_bases:
        return "lost_base"
    if (
        current_bases == 1
        and peak_bases <= 1
        and now >= first_expand_arm_at
    ):
        return "first_expand"
    return None


def nexus_fund_probe_hard_floor(
    workers: int,
    reason: str | None,
    first_expand_floor: int = 16,
    lost_base_floor: int = 12,
) -> bool:
    """O381-②:基地基金期只补维持收入火种所需的探机。

    常态 O380 经济底线会在两矿后追到 40 农；若分矿刚被摧毁时仍沿用，
    最多会先花 450 矿补 9 个探机，反而把 400 矿 Nexus 排到后面。
    基金期降为生存线：首扩迟到时保 16 农，丢矿恢复时只保 12 农；
    Nexus 成交后立即恢复常态 22/40 底线。
    """
    if reason == "first_expand":
        return workers < first_expand_floor
    if reason == "lost_base":
        return workers < lost_base_floor
    return False


def nexus_fund_should_cut_build_runner(
    fund_active: bool,
    build_completed: bool,
) -> bool:
    """O382-①:基地基金启动时终止仍在消费的独立开局执行器。

    ares ``BuildOrderRunner`` 在 ProductionManager/MacroPlan 之外运行；只暂停
    SpawnController/科技链并不能阻止它继续下叉、探机、水晶、核心和星门。
    基金启动后剩余开局步骤由常态生产层在 Nexus 成交后接管。
    """
    return fund_active and not build_completed


def healthy_mining_base_target(
    workers: int,
    high_worker_threshold: int = 45,
) -> int:
    """O381-③:实时健康矿区目标——中盘 2 片，45+ 农后 3 片。"""
    return 3 if workers >= high_worker_threshold else 2


def mineral_patch_worker_slots(
    mineral_patch_count: int,
    workers_per_patch: int = 2,
) -> int:
    """O382-③:矿区剩余实时采矿位。

    ``ideal_harvesters`` 在矿物节点上为 0，不能用来计算矿区容量；
    python-sc2 会在矿点采干后将它从 ``mineral_field`` 移除，因此实时
    矿点数 × 2 就是稳定的剩余采矿位口径。
    """
    return max(0, mineral_patch_count) * max(0, workers_per_patch)


def healthy_mining_expand_needed(
    *,
    bases: int,
    max_bases: int,
    nexus_pending: int,
    healthy_ready_bases: int,
    workers: int,
) -> bool:
    """O381-③:按剩余采矿位而非名义 Nexus 数触发四矿/五矿。

    调用方只把「就绪 Nexus 周围仍有 >=15 个矿工位」计为健康矿区；
    在建基地不能提前冒充收入。两矿以后若健康矿区低于目标(2/3)，立即
    开下一矿，绕过旧 fleet/mineral/saturation 门，防止 3 矿名义经济下
    主矿已干、二矿只剩 4 个采矿位却仍不扩张。
    """
    if bases < 2 or bases >= max_bases or nexus_pending:
        return False
    return healthy_ready_bases < healthy_mining_base_target(workers)


def terran_economic_strike_window(
    *,
    opp_race: str,
    now: float,
    fleet_count: int,
    visible_enemy_air_combat: int,
    visible_hard_aa: int,
    known_enemy_bases: int,
    min_time: float = 720.0,
    min_fleet: int = 8,
) -> bool:
    """O382-④:Terran 制空后主动斩断分矿的经济打击窗。

    只在已有成型暴风/航母、当帧可见敌空中作战单位和硬对空都已
    清零，且至少侦察到两座敌基地时开启。调用方仍保留基地主力级威胁
    召回，窗只把已放行的舰队目标从「最近敌建筑」改为「最外围已知
    分矿」，把经济优势转化为对手产能损失。
    """
    return (
        opp_race == "terran"
        and now >= min_time
        and fleet_count >= min_fleet
        and visible_enemy_air_combat == 0
        and visible_hard_aa == 0
        and known_enemy_bases >= 2
    )


def zerg_rush_economic_strike_window(
    *,
    opp_race: str,
    ai_build: str,
    now: float,
    fleet_count: int,
    visible_enemy_air_combat: int,
    visible_hard_aa: int,
    known_enemy_bases: int,
    min_time: float = 720.0,
    min_fleet: int = 8,
) -> bool:
    """O390-①:Zerg Rush 清空腐化的波间隙主动斩最外围经济。"""
    return (
        opp_race == "zerg"
        and ai_build == "rush"
        and now >= min_time
        and fleet_count >= min_fleet
        and visible_enemy_air_combat == 0
        and visible_hard_aa == 0
        and known_enemy_bases >= 2
    )


def economic_strike_ground_holds_home(
    *,
    is_fleet_air: bool,
    economic_strike_active: bool,
) -> bool:
    """O390-②:经济打击只派舰队，追猎/不朽等地面军留守收入点。"""
    return economic_strike_active and not is_fleet_air


def survival_cannon_absolute_capped(
    cannons: int,
    cap: int = 23,
) -> bool:
    """O391:新矿首塔豁免预扣1座并发余量，实峰不超过24。"""
    return cannons >= cap


def enemy_townhall_matches_focused_start(
    position: tuple[float, float],
    focused_start: tuple[float, float],
    enemy_starts: list[tuple[float, float]],
) -> bool:
    """O386-①:把已知敌基地归到当前焦点敌人，不用固定80格半径裁剪。

    1v1 的所有敌基地都属于唯一敌人，即使电脑已扩到地图远端；多人局则
    按离哪个敌方出生点最近做 Voronoi 归属，避免把另一名敌人的基地纳入
    当前经济打击目标。
    """
    if len(enemy_starts) <= 1:
        return True

    px, py = position
    nearest = min(
        enemy_starts,
        key=lambda start: (px - start[0]) ** 2 + (py - start[1]) ** 2,
    )
    return nearest == focused_start


def economic_strike_fleet_keeps_strategic_target(
    *,
    is_fleet_air: bool,
    economic_strike_active: bool,
    air_recall_active: bool,
) -> bool:
    """O386-②:经济打击舰队仅在真正达到召回门时让位基地战术目标。

    O217 的1-5残敌与 O219 的6-9地面威胁仍由地面守军处理；暴风/航母
    继续斩经济。达到经济打击召回门（当前10）后，空军照常回防。
    """
    return (
        is_fleet_air
        and economic_strike_active
        and not air_recall_active
    )


def carrier_fleet_keeps_strategic_target(
    *,
    is_fleet_air: bool,
    air_recall_active: bool,
    economic_strike_active: bool,
    small_intruder_active: bool,
    fleet_count: int,
    ground_defenders: int,
    min_fleet: int = 8,
    min_ground_defenders: int = 3,
) -> bool:
    """O388-①:成型舰队不为可由地面守军清掉的1-5残敌全体折返。"""
    if not is_fleet_air or air_recall_active:
        return False
    return economic_strike_active or (
        small_intruder_active
        and fleet_count >= min_fleet
        and ground_defenders >= min_ground_defenders
    )


def zerg_rush_late_stalker_escort_needed(
    *,
    opp_race: str,
    ai_build: str,
    now: float,
    fleet_count: int,
    stalkers: int,
    min_time: float = 900.0,
    min_fleet: int = 8,
    stalker_floor: int = 8,
) -> bool:
    """O388-②:Zerg Rush 后期腐化转型前补足8追猎护航。"""
    return (
        opp_race == "zerg"
        and ai_build == "rush"
        and now >= min_time
        and fleet_count >= min_fleet
        and stalkers < stalker_floor
    )


def zerg_rush_late_expand_blocked(
    *,
    opp_race: str,
    ai_build: str,
    now: float,
    current_bases: int,
    enemy_army_supply_credited: float,
    own_army_supply: float,
    min_time: float = 900.0,
    min_bases: int = 3,
    enemy_floor: float = 80.0,
) -> bool:
    """O388-③:敌后期信用兵力领先时不把400矿投入裸四矿。"""
    return (
        opp_race == "zerg"
        and ai_build == "rush"
        and now >= min_time
        and current_bases >= min_bases
        and enemy_army_supply_credited >= enemy_floor
        and enemy_army_supply_credited > own_army_supply
    )


def terran_precontact_cannon_capped(
    *,
    opp_race: str,
    ai_build: str,
    contact_seen: bool,
    now: float,
    cannons: int,
    cap: int = 2,
    release_at: float = 420.0,
) -> bool:
    """O383-①:Terran Rush 零接触窗不再提前堆4塔。"""
    return (
        opp_race == "terran"
        and ai_build == "rush"
        and not contact_seen
        and now < release_at
        and cannons >= cap
    )


def terran_precontact_ground_pause(
    *,
    opp_race: str,
    ai_build: str,
    contact_seen: bool,
    now: float,
    ground_count: int,
    cap: int = 2,
    release_at: float = 420.0,
) -> bool:
    """O383-①:Terran 首接触前只保留2个地面保底兵。"""
    return (
        opp_race == "terran"
        and ai_build == "rush"
        and not contact_seen
        and now < release_at
        and ground_count >= cap
    )


def terran_precontact_local_defense_targets(
    main_cannons: int,
    expansion_cannons: int,
    batteries: int,
    per_base_cap: int = 1,
) -> tuple[int, int, int]:
    """O384-①:Terran 首接触前目标层每基地最多1塔/1电池。"""
    return (
        min(main_cannons, per_base_cap),
        min(expansion_cannons, per_base_cap),
        min(batteries, per_base_cap),
    )


def terran_rush_fourth_before_contact_blocked(
    *,
    opp_race: str,
    ai_build: str,
    current_bases: int,
    contact_seen: bool,
    max_precontact_bases: int = 3,
) -> bool:
    """O387-①:Terran Rush 首接触前最多三矿，四矿等敌形态兑现。"""
    return (
        opp_race == "terran"
        and ai_build == "rush"
        and not contact_seen
        and current_bases >= max_precontact_bases
    )


def terran_rush_robo_needed(
    *,
    opp_race: str,
    ai_build: str,
    now: float,
    bases: int,
    fleet_count: int,
    fleet_beacon_present: bool,
    robo_present: bool,
    min_time: float = 420.0,
    min_bases: int = 3,
    fleet_gate: int = 4,
) -> bool:
    """O387/O394:Terran Rush/Timing 压力波前预置机械台。"""
    return (
        opp_race == "terran"
        and ai_build in ("rush", "timing")
        and now >= min_time
        and bases >= min_bases
        and fleet_count < fleet_gate
        and fleet_beacon_present
        and not robo_present
    )


def terran_rush_immortal_needed(
    *,
    opp_race: str,
    ai_build: str,
    visible_armored_ground: int,
    immortals: int,
    trigger: int = 6,
    cap: int = 2,
) -> bool:
    """O387/O394:Terran Rush/Timing 重甲波出现时直产最多2个不朽。"""
    return (
        opp_race == "terran"
        and ai_build in ("rush", "timing")
        and visible_armored_ground >= trigger
        and immortals < cap
    )


def timing_carrier_transition_allowed(
    ai_build: str,
    tempest_count: int,
) -> bool:
    """O394:Terran Timing 首暴风真实出场前禁止E10转航母。"""
    return ai_build != "timing" or tempest_count > 0


def pick_safest_rebuild_expansion(
    free_expansions,
    visible_enemy_ground_positions,
    home,
    max_home_distance: float = 65.0,
    home_weight: float = 0.5,
):
    """O383-②:丢矿急性窗选离当前敌地面主力最远的扩张点。

    没有实时敌地面情报时返回 None，让 ExpansionController 保留
    原生距离+安全网格排序；有情报时先最大化与最近敌军的距离，
    同分再选距我方主基较近的点，避免 400 矿重复拍进死亡球路径。
    """
    if not free_expansions or not visible_enemy_ground_positions:
        return None

    defensible = [
        pos for pos in free_expansions
        if pos.distance_to(home) <= max_home_distance
    ] or list(free_expansions)

    def _score(pos):
        nearest_enemy = min(
            pos.distance_to(enemy_pos)
            for enemy_pos in visible_enemy_ground_positions
        )
        return nearest_enemy - home_weight * pos.distance_to(home)

    return max(defensible, key=_score)


def terran_post_rebuild_recovery_active(
    opp_race: str,
    now: float,
    recovery_until: float,
) -> bool:
    """O383-③:Terran Nexus 恢复后120s生产资料窗。"""
    return opp_race == "terran" and now < recovery_until


def fleet_onfield_started(tempests: int, carriers: int) -> bool:
    """O383-⑥:首艘真实舰队已出场（在产不算）。"""
    return tempests + carriers > 0


def healthy_expand_latch_active(
    latched_from_bases: int | None,
    current_bases: int,
) -> bool:
    """O383-④:健康矿区扩张 latch 持有到 Nexus 实体数增加。"""
    return (
        latched_from_bases is not None
        and current_bases <= latched_from_bases
    )


def economic_strike_recall_threshold(
    normal_threshold: int,
    max_threshold: int = 10,
) -> int:
    """O384-②:斩分矿是可撤经济打击，基地10地面威胁即召回。"""
    return min(normal_threshold, max_threshold)


def desperation_push_window(
    now: float,
    fleet_count: int,
    defense_score: float,
    min_time: float = 900.0,
    min_fleet: int = 2,
    normal_fleet_floor: int = 5,
    min_defense: float = 15.0,
) -> bool:
    """O380-⑤:长期未成型局的一次豁命推进窗。纯逻辑。

    只覆盖 t>=900、仍有 2-4 艘舰队且家中防御评分达标的慢性败局；正常
    5+ 舰队继续走 O302 既有闸，0-1 艘不做无意义白送。对空安全闸仍由
    combat_manager 的既有逻辑统一判定。
    """
    return (
        now >= min_time
        and min_fleet <= fleet_count < normal_fleet_floor
        and defense_score >= min_defense
    )


def cannon_global_capped(
    cannons: int, threat_active: bool, cap: int = 12
) -> bool:
    """O360-③(o359b 尸检):静态防御全局总投资软顶。纯逻辑,可单测。

    o359b g2 实证:19 座塔 ≈2850 矿 ≈ 7 艘航母 —— 中盘塔链把舰队资金
    吃光。现有 cannon_capped(O354-④)只管 t≥600+舰队≥4 的舰队期;
    本软顶管全期:全局塔(实体+在途)≥cap 且非 threat/rush → 停钉新塔
    (任何时段);threat/rush 豁免保留(被骑脸该补还得补)。两道并存:
    cannon_capped 管舰队期,本判据管全期总投资。
    """
    return cannons >= cap and not threat_active


def cannon_absolute_capped(cannons: int, cap: int = 18) -> bool:
    """O382-⑤:静态防御绝对投资上限。

    o381b g1 胜局塔峰 25 座（3750 矿），同期舰队已到 29 艘且终局
    存款 7645；慢性 threat latch 让旧软顶全程豁免，不能防止非边际
    塔继续吃矿。绝对顶不读 threat；调用方仅对「新矿零塔的首座
    生存塔」保留豁免，把钱从第 19+ 座塔转回舰队/基地。
    """
    return cannons >= cap


def gas_to_minerals_released(
    vespene: float,
    minerals: float,
    vespene_threshold: float = 250.0,
    mineral_threshold: float = 400.0,
) -> bool:
    """O360-④(o359a/o359b 尸检):停气转矿解除判据。纯逻辑,可单测。

    O359-② 的滞回解除「气 <350」实证走不到 —— o359a 三局触发有事件、
    解除 0 事件(气超冲 616-694 期间气农被按住,气却永远花不到 350
    以下);o359b g1 触发后 194s 才解除(257.9→451.3)。解除改双向
    缓解即解:「气 <500(烂气被花掉)或 矿 >400(矿荒已缓)」——
    两个病因任治其一就放手,不再等气单独深跌。
    O363-④b(o362a/o362b 尸检):改纯气压滞回 —— 「矿 >400 即解」
    实证让停气形同虚设:矿一缓到 400 就把农民放回气矿,气根本压不
    下去(o362a g3 触发后气照涨 +220,o362b g1 气峰 684),解除
    事实上只剩 60s 棘轮在走。解除只认 气 <250:与 ZT 早窗触发档
    (气 >300)留 50 滞回带,与常规触发档(500)留 250;60s 棘轮
    保险丝(gas_pull_window_expired)保留为兜底。minerals 参数保留
    不再入判据(向后兼容签名)。
    """
    return vespene < vespene_threshold


def gas_pull_window_expired(
    pull_since: float | None, now: float, window: float = 60.0
) -> bool:
    """O360-④:停气最长窗口判据(棘轮保险丝)。纯逻辑,可单测。

    O117-① 同教义:停气通道在 ares Mining 持续补气的对抗下会单向
    棘轮(停气池越攒越大,经济角色被抽干);o359a 解除永不到达即
    钉死实证。连续停气 ≥window 秒 → 调用方强制解除一轮(30s 冷却
    后才允许再触发),防任何解除条件失效把停气钉成终局状态。
    """
    return pull_since is not None and now - pull_since >= window


def nexus_fund_hold_active(
    now: float,
    hold_until: float,
    nexus_pending: int,
    threat_active: bool,
) -> bool:
    """O364-①(o363a g3 直接死因):Nexus 资金窗独占期判据。纯逻辑,可单测。

    O336-① 旧自救「首扩等钱 >60s → 解锁科技链 30s」方向倒挂:解锁
    期 SG(261s)/FB(325s)/3 风暴/Robo/Twilight ≈2000+ 矿科技消费
    把 Nexus 的 400 矿窗永久挤掉(首扩 470s 到死没落成,单矿 31 农,
    752s 被 54-supply 波破主基)。方向反转:等钱 >60s 时 luxury
    钉点族 hold,Nexus 钉点独占资金窗;成交(nexus_pending=0 =
    开工后 tracker 无 NEXUS 条目)/45s 超时(防死锁)/threat
    豁免(被骑脸时塔/兵钱不能锁)三条件放行。
    """
    if threat_active or now >= hold_until:
        return False
    return nexus_pending > 0


def nexus_fund_hold_blocks(structure_name: str, stargates_total: int) -> bool:
    """O364-①:资金窗独占期被 hold 的 luxury 钉点族判据。纯逻辑,可单测。

    hold 清单 = o363a g3 挤死 Nexus 资金窗的科技消费:SG 第 2+ 座
    (首座是舰队链起点,不拦)/FB/ROBO/TWILIGHT;风暴/航母的
    train 通道(O239/O260/O364-④)在调用方另闸,不经本判据。
    """
    if structure_name == "STARGATE":
        return stargates_total >= 1
    return structure_name in (
        "FLEETBEACON",
        "ROBOTICSFACILITY",
        "TWILIGHTCOUNCIL",
    )


def new_base_cannon_fb_fund_exempt(
    nexus_ready: bool,
    cannons_near: int,
    cannons_in_flight: int,
) -> bool:
    """O364-②(o363a g1/o363b 三局实证):新矿配塔提前到 Nexus 开工 ——
    在建 Nexus 的首座塔豁免 FB 基金窗。纯逻辑,可单测。

    o363 实证新矿配塔稳定晚 68-71s:落成时才开始攒 350 矿(2 塔+
    1 电池),验收线 60s 稳定差一口气;o363a g1 塔链更被 fb_fund
    窗压到落成后 272s(529s 才来)。开工即发钉点(落成时已在途/
    已落成);资金紧张期(FB 基金窗)至少首座塔走 critical 不等窗,
    已有 ≥1 塔(含在途)后回归基金窗纪律。
    """
    return (not nexus_ready) and (cannons_near + cannons_in_flight) == 0


def new_base_survival_cannon_ok(
    nexus_ready: bool,
    cannons_near: int,
    cannons_in_flight: int,
) -> bool:
    """O367-⑤a(o366 双 lane 尸检):新基地保命塔豁免判据。纯逻辑,可单测。

    o366 三局丢矿共同直接死因:F2 注册 target=0(fb_missing 穷局
    O210 买不起归零)—— o366b g2 二矿 412s 被 5 蟑螂拔裸矿、
    o366b g3 三矿 691s 被拔、o366a g1 二矿落成 12s 被拔。O364-②
    的基金窗豁免只管「Nexus 在建」首塔;落成后(fb_missing 基金
    窗常开)首座保命塔反被 fb_fund/capped 闸拦死。新 Nexus 已落成
    且 12 格内零塔(实体+在途)→ 首座保命塔豁免一切基金/钳制闸
    (fb_fund_window/cannon_capped/cannon_global_capped),走
    critical 直接钉;已有 ≥1 塔(含在途)回归常规纪律。与
    O363-①/O364-② 配塔体系兼容:它们是常规路径,这是保命路径。
    """
    return nexus_ready and (cannons_near + cannons_in_flight) == 0


def gas_stop_leaking(
    vespene_gain: float,
    seconds: float,
    threshold_per_10s: float = 15.0,
) -> bool:
    """O364-③b(o363 尸检):停气 30s 校验环的泄漏判定。纯逻辑,可单测。

    触发后气照涨 +120~+184(斜率与触发前一致)= 农民被拽回气矿
    (ares Mining 补气/角色漂移漏网)。校验环每 ~2s 核气增速,折算
    10s 增速 >15(≈1 个气矿农民满采)即视为泄漏,调用方重复拉拽+
    清簿记。seconds ≤0(首帧建档)不判。
    """
    if seconds <= 0:
        return False
    return vespene_gain / seconds * 10.0 > threshold_per_10s


def gas_stop_release_blocked(
    vespene: float,
    fleet_count: int,
    min_fleet: int = 6,
    vespene_ceiling: float = 400.0,
) -> bool:
    """O364-③c(o363b g2 实证):停气解除加闸。纯逻辑,可单测。

    60s 棘轮强制解除在「气 >400 且舰队(TEMPEST+CARRIER)<6」时
    不放行 —— o363b g2 解除后 +354 漏回实证:气压没下去、舰队没
    成型,放回气矿只是再烂一轮。气压滞回(气 <250)解除不受本闸
    (调用方先行),本闸只拦棘轮兜底。
    """
    return vespene > vespene_ceiling and fleet_count < min_fleet


def carrier_hard_convert_ok(
    fb_ready: bool,
    minerals: float,
    carriers: int,
    can_afford: bool,
    min_minerals: float = 600.0,
    max_carriers: int = 2,
) -> bool:
    """O364-④(o363b g2 实证):航母硬转化判据。纯逻辑,可单测。

    矿烂银行局航母转化缺失:农 72/矿 955 烂银行,航母只有 1 艘
    (O239 的气 ≥400 门在矿烂气平局不 trigger);Rush lane 航母
    首产 755-900s vs Power 胜局 590-739s;舰队成分以暴风为主,
    遇腐化 12-16 毫无还手力。FB 就绪 + 矿 >600 + 航母(含在产)
    <2 + 买得起 → 调用方空闲星门直接 train(绕过 SpawnController
    比例分配)。与 tempest_dump_suppressed 联动不打架:O354-①
    已保证航母 <2 时 O260 不点暴风,矿窗不互抢。
    """
    return (
        fb_ready
        and minerals >= min_minerals
        and carriers < max_carriers
        and can_afford
    )


def fleet_rebuild_watchdog_needed(
    fleet_peak: int,
    fleet_now: int,
    collapsed_since: float | None,
    now: float,
    fb_ready: bool,
    idle_ready_sg: int,
    min_peak: int = 3,
    max_now: int = 2,
    collapse_window: float = 60.0,
) -> bool:
    """O372-④(o371a g2/g3 尸检):舰队重建断档 watchdog 判据。
    纯逻辑,可单测。

    o371a g2 实证:航母 803s 死后双星门+气 500 在手 200s 零补充,
    839-952s 共 112s 军队零变化;g3 航母 2→0 后同样长断档 ——
    O239/O260/O364 三条补产通道全挂 zerg 门,Terran lane(及任何
    非 ZT 局)舰队死后无人补产。舰队(TEMPEST+CARRIER,就绪+在建
    口径)曾 ≥min_peak 后掉到 <max_now 且持续 ≥collapse_window 秒,
    且 FB 就绪(产线前置齐)+有空闲就绪星门 → 调用方强制补产
    (critical train,航母优先,买不起航母退风暴),90s 节流+事件。
    种族不挂门:watchdog 只在「成型舰队塌掉 ≥60s」才开火,ZT 既
    有通道正常期先于它触发,天然不打架。
    """
    return (
        fleet_peak >= min_peak
        and fleet_now < max_now
        and collapsed_since is not None
        and now - collapsed_since >= collapse_window
        and fb_ready
        and idle_ready_sg > 0
    )


def fleet_collapse_clock_reset(
    recovered_since: float | None,
    now: float,
    grace: float = 15.0,
) -> bool:
    """O373-④a(o372b g1 实证):塌缩计时累计制的清零判据。
    纯逻辑,可单测。

    o372b g1 实证:舰队 1121s 跌破 2 后短暂回到 2 艘,旧连续制把
    collapsed_since 清零重计,断档永远攒不满 60s,至终局 70s 零
    补产。改累计制:回到 ≥max_now 持续 ≥grace 秒才清零(调用方
    簿记 recovered_since;再度跌破即放弃清零、计时原样累计),
    短暂假恢复不重置断档计时。
    """
    return recovered_since is not None and now - recovered_since >= grace


def manual_cannon_anchor(
    nexus_xy: tuple,
    mineral_xy: tuple | None,
    attempt: int,
    base_offset: float = 6.0,
    step: float = 1.0,
) -> tuple:
    """O364-⑤a(o363a g1/g2 实证):分矿塔链 no_placement 手工锚点。
    纯逻辑,可单测。

    placement solver 黑格实证:主基 26 个水晶却报「带电 2x2 槽=0」,
    O337 分矿守卫 no_placement 空转 271→512s(g2)/311→436s(g1)。
    连续 30s no_placement 后不再依赖 solver:锚点 = Nexus 坐标沿
    「Nexus→矿线质心」方向 base_offset 格(塔守矿线,同 O101-X
    首塔教义),放不进每次外扩 step 格(attempt 递增,调用方簿记);
    矿线取不到退化为正上方固定偏移。先立 1 塔再说(O357 死槽
    换锚的「拉黑-重锚」同教义,锚由几何直算不走槽表)。
    O366-③c(o365a g1 实证):单方向射线改 8 向扇形 —— o365a g1
    三矿 (70,94) 手工锚点重试连败:旧实现只沿「Nexus→矿线」一条
    射线外扩,该方向撞上矿簇本体/不可建地形时,attempt 递增只是
    沿同一条死线越走越远(扩进矿线更不可建)。改扇形:attempt
    低 3 位选方向(矿线方向起,每次 ±45° 旋转,8 向轮转),高
    位选圈(每轮转完一圈外扩 step 格)—— 死方向 8 次尝试内
    必然换向,不再在一条死线上空转。
    """
    nx, ny = nexus_xy
    dist = base_offset + (attempt // 8) * step
    dx, dy = 0.0, -1.0
    if mineral_xy is not None:
        vx, vy = mineral_xy[0] - nx, mineral_xy[1] - ny
        norm = (vx * vx + vy * vy) ** 0.5
        if norm > 0:
            dx, dy = vx / norm, vy / norm
    # 8 向旋转表(45° 步进,从矿线方向起,先右后左交替)
    _S = 0.7071067811865476  # √2/2
    _ROT = (
        (1.0, 0.0), (_S, _S), (_S, -_S), (0.0, 1.0),
        (0.0, -1.0), (-_S, _S), (-_S, -_S), (-1.0, 0.0),
    )
    cos_a, sin_a = _ROT[attempt % 8]
    rx, ry = dx * cos_a - dy * sin_a, dx * sin_a + dy * cos_a
    return (nx + rx * dist, ny + ry * dist)


def anchor_buildable(
    grid,
    x: float,
    y: float,
    resource_xys=(),
    min_res_dist: float = 2.5,
) -> bool:
    """O366-③c(o365a g1 实证):手工锚点可建性过滤。纯逻辑,可单测。

    o365a g1 三矿 (70,94) 实证:手工锚点重试连败 —— 锚点落在不可建
    地形/矿簇本体上,游戏侧直接拒建(不是 solver no_placement,
    重试只是换个坐标再被拒)。派工前先过滤:2x2 足迹四格全在
    placement grid 可建格(1=可建),且离矿簇/气矿 ≥min_res_dist
    (资源格 placement grid 不标,需显式避让)。grid =
    game_info.placement_grid.data_numpy(越界 = 不可建)。
    O367-②(o366 尸检复核):索引朝向验证结论 —— grid[cy, cx]
    即 [y][x] 为**正确**朝向,非转置。证据:sc2 PixelMap
    data_numpy = buffer.reshape(size.y, size.x)(pixel_map.py),
    其 __getitem__(Point2(x,y)) 返回 data_numpy[y, x];sc2
    game_info.py 的 playable_area 同以 (b, a) 即 (y, x) 枚举;
    ares placement_manager 的 cy_can_place_structure 对同一
    未转置数组索引 placement_grid[y, x]。o366a g1 的 64 次
    not_viable 实出自 O118 首塔派工的 dispatch_viable 收入守卫
    (穷局买不起 150 矿塔,采集池 0-5),手工锚点路径该局零触发,
    与本函数无关;穷局根由 O367-① 修复。
    """
    ax, ay = int(x), int(y)
    height, width = grid.shape
    for dx in (-1, 0):
        for dy in (-1, 0):
            cx, cy = ax + dx, ay + dy
            if cx < 0 or cy < 0 or cy >= height or cx >= width:
                return False
            if grid[cy, cx] != 1:
                return False
    return all(
        (x - rx) ** 2 + (y - ry) ** 2 >= min_res_dist * min_res_dist
        for rx, ry in resource_xys
    )


def pylon_ring_fallback_anchor(
    grid,
    pylon_xys,
    resource_xys=(),
    radius: int = 6,
):
    """O378-⑤(o377b 尸检):扇形锚连败降级 —— 水晶旁任意可建 2x2。
    纯逻辑,可单测。

    o377b 实证:AbyssalReef (130,26)/(130,50) 矿位手工锚点扇形
    4-7 向全失败(8 向候选无一过 anchor_buildable:撞矿簇/不可建
    地形),重试链空转 200s,6 次开矿仅 2 次 90s 内达标。扇形几何
    (Nexus±矿线方向)穷举失败 → 降级放宽锚点几何:按 pylon_xys
    顺序(调用方按离基地距离排序)在每根水晶 ±radius 环带内扫描
    placement grid,第一个过 anchor_buildable 的 2x2 即锚点(塔
    必须带电,水晶旁扫描天然满足供电;资源避让沿用 anchor_
    buildable 的 min_res_dist 口径)。全无可建 → None(调用方
    维持原重试簿记,下帧再来)。
    """
    offsets = sorted(
        (
            (dx, dy)
            for dx in range(-radius, radius + 1)
            for dy in range(-radius, radius + 1)
        ),
        key=lambda d: d[0] * d[0] + d[1] * d[1],
    )
    for px, py in pylon_xys:
        for dx, dy in offsets:
            cx, cy = px + dx, py + dy
            if anchor_buildable(grid, cx, cy, resource_xys):
                return (cx, cy)
    return None


def tower_sector_fallback_due(anchor_attempts: int, threshold: int = 3) -> bool:
    """O379-③(o378b g2/g3 尸检):手工锚点重试计数降级判据。纯逻辑,可单测。

    o378b 实证:O378-⑤ 的水晶旁兜底只在「扇形 8 候选全灭」触发,
    六局零事件;真实失败模式是预检过/实建败(no_placement/
    power_precheck 带电余=0/等钱/no_worker)后手工锚点重试连败仍
    在扇形里打转(g2/g3 第 5/6 次仍扇形,新矿裸奔 130-262s,验收
    ⑤ 合计 1/9)。per-base 重试计数(调用方台账 _o364_anchor_
    attempts,no_placement/滞留预检/O368 强钉同链并账)≥threshold
    → 跳扇形,直接水晶旁 2x2 扫描(pylon_ring_fallback_anchor);
    未满照旧走 8 向扇形(manual_cannon_anchor)。
    """
    return anchor_attempts >= threshold


def escort_hard_cap(
    enemy_ground_near: int,
    workers: int,
    keep_mining: int,
    cap: int = 3,
) -> int:
    """O364-⑤b(o363a g2 实证):协防农民硬限量 ≤3。纯逻辑,可单测。

    首波杀农 15(23→8)其中 6 个是协防拉出塔/电池射程送死的 ——
    协防是拖延(塔下作战/穿矿甩包围)不是决战,3 农塔下足够,
    ×6 纯放血。采矿底线逻辑复用 escort_pull_cap,只收 cap。
    """
    return escort_pull_cap(
        enemy_ground_near, workers, keep_mining=keep_mining, cap=cap
    )



def gas_stop_requisition_ok(
    structure_name: str, gathering_empty: bool, gas_stopped: int
) -> bool:
    """O365-①(o364b g3 实证):停气池建造派工放行+强征降级判据。
    纯逻辑,可单测。

    o364b g3:四矿落成前 1s 分矿补电 no_worker —— 采集池簿记=1
    (虚高,O347-① 已证簿记含气矿工,select_worker 实际无人可选),
    停气池=63 却被旧 builder_borrow_ok 的「采集池归零才借」整体
    豁免,四矿零塔被敌 4 地面抄家撤 20 农,此后基地连掉。停气
    农民本来在采矿,拉 1 人钉塔不伤停气(借出即从停气台账摘除,
    同 O116-②)。塔/电池/补电(防御链)select_worker 失败即放行
    停气池,不再要求采集池簿记归零;其余结构保持旧闸(防停气池
    被奢侈品派工抽干)。
    """
    if gas_stopped <= 0:
        return False
    return gathering_empty or structure_name in (
        "PHOTONCANNON",
        "SHIELDBATTERY",
        "PYLON",
    )


def gas_restore_needed(
    minerals: float,
    vespene: float,
    carriers: int,
    fb_ready: bool,
    min_minerals: float = 600.0,
    vespene_ceiling: float = 125.0,
    max_carriers: int = 2,
) -> bool:
    """O365-②(o364b g3 实证):航母硬转化的气枯强制复气判据。纯逻辑,可单测。

    o364b g3:矿 >600 窗口 908-948s(40s)气仅 7-79,can_afford
    (250 气)恒假,硬转化 0 次且无日志,航母 0 —— 停气棘轮把气
    锁死,矿烂银行换不成舰队。矿 >600 且气 <125 且航母(含在产)
    <2 且 FB 就绪 → 调用方强制复气(每气矿回 3 人,解除停气
    棘轮);气 ≥300(gas_restore_done)恢复正常,走原硬转化。
    """
    return (
        fb_ready
        and minerals >= min_minerals
        and vespene < vespene_ceiling
        and carriers < max_carriers
    )


def gas_restore_done(vespene: float, threshold: float = 300.0) -> bool:
    """O365-②:强制复气完成判据(气 ≥300 恢复停气棘轮+硬转化)。
    纯逻辑,可单测。300 > 航母 250 气价,复气一完成即够转化。"""
    return vespene >= threshold


def nexus_deal_confirmed(nexus_pending: int, townhalls: int) -> bool:
    """O365-③c(o364a g3 假成交实证):Nexus 开工成交双条件判据。
    纯逻辑,可单测。

    旧成交单条件(tracker 无 NEXUS 条目)被保险丝 pop/静默回收
    骗过:o364a g3 报「Nexus开工成交,放行」但 bases 全程=1
    (358.3/418.4s O340 仍诊断首扩未开工)。成交 = tracker 真空
    + Nexus 实体实证(townhalls ≥2,ares townhalls 含在建,见
    O364-② 注释)双条件;hold 期内保险丝 pop 条目只满足前者,
    不判成交(调用方重回 hold 并重派工)。
    """
    return nexus_pending == 0 and townhalls >= 2


def nexus_deal_verify_failed(
    now: float, deal_verify_at: float, townhalls: int
) -> bool:
    """O365-③b(o364a g3 实证):成交 T+15s placement 校验判据。
    纯逻辑,可单测。

    报成交后 deal_verify_at 时刻仍无 Nexus 实体(townhalls <2,
    含在建口径)→ 假成交:调用方撤销成交、重回 hold 并重派工。
    deal_verify_at=0(无待校验成交)不判。
    """
    return (
        deal_verify_at > 0.0 and now >= deal_verify_at and townhalls < 2
    )


def nexus_pin_yield_gate(
    minerals: float,
    second_base_pinned: bool,
    main_cannons_ready: int,
    min_minerals: float = 400.0,
    min_cannons: int = 2,
) -> bool:
    """O365-④(o364b g1 实证):第 3+ 塔/电池让位 Nexus 钉点判据。
    纯逻辑,可单测。

    o364b g1 倒挂:196-225s 先立 3 塔+2 电池(~500 矿),Nexus
    ~318s 才钉,二矿 381.7s 比胜局晚 80s —— O364-① 的 hold 在
    Nexus 钉点之后,根本轮不到武装。倒挂前置到钉点排队层:矿
    ≥400(Nexus 钱已够)且二矿未钉(无实体无在途)且主基防御
    ≥2 塔 → 调用方把第 3+ 塔/电池目标钳掉,Nexus 钉点独占银行。
    主基 <2 塔(保命塔未齐)不让位。
    """
    return (
        minerals >= min_minerals
        and not second_base_pinned
        and main_cannons_ready >= min_cannons
    )


def cyber_core_watchdog(
    now: float, cyber_present_or_pending: bool, min_time: float = 150.0
) -> bool:
    """O365-⑤a(o364a g2 实证):BY 芯核兜底 watchdog 判据。纯逻辑,可单测。

    o364a g2 全场无 BY 芯核(build yml ~474s 跑完即无后继,Timing
    lane 更上游断链):科技链断在第一节无人发现。t >min_time 且无
    CYBERNETICSCORE 实体无在途 → 调用方最高优先 critical 钉点
    (驻点等钱 = 资金走低时天然最优先;no_placement 走 O357
    死槽换锚)并打事件。
    O370-④a(o369a Timing 三局实证):watchdog 180s→150s ——
    BY 落成 156.7/192.9/245.1 全部超标(g3 落成 ~281s 直接压垮
    500s 舰队链),180s 才兜底对 opener 关键链是死等。
    """
    return now >= min_time and not cyber_present_or_pending


def cyber_core_build_allowed(
    present_or_pending: bool,
    runner_core_ahead: bool,
) -> bool:
    """O370-④b(o369b g2/g3 双 BY 白扔 100+ 矿实证):双 BY 防重
    判据。纯逻辑,可单测。

    BY 实体/在途已存在,或 opening runner 后续步仍排着 core
    (runner 会自己建,bot 钉点重复 = 白扔一座 BY) → 跳过钉点。
    runner 步卡死(O324 看门狗,bot 层接管)时调用方传
    runner_core_ahead=False,兜底钉点恢复。
    """
    return not present_or_pending and not runner_core_ahead


def build_runner_owns_unique_core(
    *,
    runner_present: bool,
    build_completed: bool,
    runner_stalled: bool,
) -> bool:
    """O392:Runner活跃且未卡死时独占BY等唯一核心建筑注册权。"""
    return runner_present and not build_completed and not runner_stalled


def expansion_defense_guard_active(opp_race: str, ai_build: str) -> bool:
    """O371-①a(o370b Terran Power 0/3 尸检):分矿防御持续守卫
    (O323/O337/O363 整块)的种族门。纯逻辑,可单测。

    o370b 实证:守卫整段包在「zerg and (timing,rush)」门内,打
    Terran 时事件簿对照 o370a→o370b = O337 26→0、O363 19→0、
    O329 7→0、O118 26→0、O216 13→0、O98 3→0,三局三矿落成后
    裸奔 60-80s 被 ~495-510s 首波(25-30 supply M&M+坦克)准点
    收走。去门:zerg timing/rush 返回值与原门完全一致(行为
    不变,只放宽),terran 全 build 生效;protoss 尚无尸检证据,
    不放宽。
    """
    return (opp_race == "zerg" and ai_build in ("timing", "rush")) or (
        opp_race == "terran"
    )


def timing_defense_chain_active(opp_race: str, ai_build: str) -> bool:
    """O371-①b/c(o370b 尸检):zerg-timing 防御钉点链(O329 分矿
    预置塔链/O333 forge 钉点/O349 forge 看门狗/O338 GW2)的种族
    门。纯逻辑,可单测。

    o370b 实证:O329 预置塔链 7→0;forge 兜底静默(forge 晚至
    168-217s vs zerg 局 92s);O338 GW2 静默(Terran 局零地面填线,
    M&M 波到脸无兵可填)。同 O371-①a 去门:zerg timing 返回值
    与原门完全一致,terran 全 build 生效;zerg rush/protoss 无
    证据,不放宽。
    """
    return (opp_race == "zerg" and ai_build == "timing") or opp_race == "terran"


def push_enemy_army_gate(
    own_army_supply: float,
    enemy_visible_supply: float,
    enemy_hard_aa: int,
    supply_ratio: float = 1.0,
    max_hard_aa: int = 4,
) -> bool:
    """O371-②(o370b 尸检):推进的敌军校验闸。纯逻辑,可单测。

    o370b g3 实证:fleet=4 对敌 47 supply 主动推进(569.5s),纯送;
    g1 900s 损失风暴×2、g2 敌 11 维京 vs 我 5 风暴 —— 维京 ≥4
    时风暴被点名。推进必须同时过两闸:敌可见 supply ≤ 我方
    army supply ×supply_ratio(量级不送死)且 敌硬对空(维京/
    腐化/凤凰/飞蛇,调用方 _HARD_AA 口径)<max_hard_aa(舰队不
    被点名)。敌可见 0(被榨干/迷雾收割)自然过闸(0 ≤ 任何)。
    O376-②(o375 尸检):「0 自然过闸」语义已被 blind_push_blocked
    在调用方覆盖 —— 信用 supply=0(当帧+粘滞峰值全空)= 盲推,
    不过闸。
    O373-⑥(o372a g1 实证):supply_ratio 1.5→1.0,并入 O302 出发
    闸 —— g1 舰队 5 于 562.9s 顶波出击离家,3 秒后敌 46 supply
    波进门,三矿→二矿→主基连掉(×1.5 时 own≥31 即放行);出发
    判据收紧为「敌可见 supply ≤ 我方 army supply」,与 advantage/
    full_pop 闸合并单判(_army_gate_ok),不双判。
    """
    return (
        enemy_visible_supply <= own_army_supply * supply_ratio
        and enemy_hard_aa < max_hard_aa
    )


def push_commit_aa_retreat(
    enemy_hard_aa: int,
    starport_seen: bool,
    max_hard_aa: int = 4,
    starport_aa_credit: int = 2,
) -> bool:
    """O372-⑤(o371a g2 尸检):推进 commit 期敌硬对空重评撤蹲判据。
    纯逻辑,可单测。

    o371a g2 实证:656-765s fleet=5-7 推进 ×4,维京 695s 才露面
    (20 架)后仍 commit,舰队团灭 —— carrier_push_safe 只认当帧
    可见硬对空,维京出视野(或尚未露面)即放行,星港(维京产能)
    曾见也不构成预警。重评口径:可见硬对空(维京/腐化/凤凰,
    调用方 _HARD_AA 口径)+ remembered 星港预警
    (+starport_aa_credit,敌星港曾见 = 维京潜在,单星港不够撤蹲
    线,2 架可见维京+星港即越线)≥max_hard_aa → 撤蹲(调用方回
    既有蹲守锚点,O63/O37 分支);30s 重评间隔内旗标粘滞(调用方
    簿记),可见性抖动不反复收放。
    """
    return (
        enemy_hard_aa + (starport_aa_credit if starport_seen else 0)
    ) >= max_hard_aa


def aa_reeval_due(
    now: float,
    last_eval_at: float,
    credited_now: int,
    credited_at_last: int,
    interval: float = 30.0,
    immediate_at: int = 4,
) -> bool:
    """O378-⑥b(o377b 三局团灭尸检):AA 重评时机判据。纯逻辑,可单测。

    o377b 实证:30s 定期重评对暴风太短 —— 腐化群显形后 28s 内
    舰队死在两次重评之间(g1 舰队峰 16 拖过 1200s 进腐化+大龙
    窗口被全歼,同一秒「塔投资冻结(腐化≥4)」舰队却在出门)。
    重评时机:① 距上次 ≥interval(原 30s 定期,不动);② 信用
    对空计数(腐化+大龙,zerg 走 zerg_aa_credited;terran 走可见
    _HARD_AA)≥immediate_at 且较上次重评上升(新增腐化显形)→
    立即重评,不等 30s。下降/持平不立即重评(防可见性抖动反复
    收放,旗标粘滞语义不变)。
    """
    return (now - last_eval_at >= interval) or (
        credited_now >= immediate_at and credited_now > credited_at_last
    )


def zerg_aa_exemption_capped(
    corruptor_broodlord_visible: int,
    cap: int = 8,
) -> bool:
    """O373-⑤(o372b g1 实证):zerg AA 豁免上限判据。纯逻辑,可单测。

    o372b g1 实证:884.2s 唯一推进后蹲守不还,1117s 撞 20 腐化
    +4 大龙团灭 —— commit 期 zerg 豁免(O371-②/O372-⑤ 教义:
    O302 黄金窗自带腐化闸)零对空重评兜底,腐化+大龙无上限膨胀。
    commit 期可见 CORRUPTOR+BROODLORD ≥cap → 豁免封顶,即便
    zerg 也走 push_commit_aa_retreat 重评撤蹲;cap 以下原豁免
    不动(黄金窗打法一行不变)。
    O374-①:入参口径升级为信用记忆计数(zerg_aa_credited 的
    输出),纯判据不变。
    """
    return corruptor_broodlord_visible >= cap


def aa_peak_sticky(
    now: float,
    visible: int,
    peak: int,
    peak_at: float,
    window: float = 60.0,
) -> tuple[int, float]:
    """O374-①(o373b g2 实证):AA 峰值粘滞簿记。纯逻辑,可单测。

    o373b g2 实证:17 腐化 1098.7s 离视野,13s 后(1111.8s)
    O302 出击闸全开(撤蹲/出发闸只认当帧可见 enemy_units),
    舰队 11→1 团灭;1068.8s 起 AA≥8(峰 22@1129)但无撤蹲
    日志。簿记规约(调用方每帧喂当帧可见数):可见 ≥峰值 →
    吸收并刷新时刻;峰值超 window 未刷新 → 回落当帧值(粘滞
    期内不归零,防可见性抖动反复收放)。返回 (新峰值, 峰值时刻)。
    """
    if visible >= peak or now - peak_at > window:
        return visible, now
    return peak, peak_at


def zerg_aa_credited(
    corruptor_broodlord_visible: int,
    sticky_peak: int,
    spire_seen: bool,
    spire_aa_credit: int = 2,
) -> int:
    """O374-①(o373b g2 实证):zerg 硬对空信用记忆计数。纯逻辑,可单测。

    口径 = max(当帧可见 CORRUPTOR+BROODLORD, 60s 粘滞峰值)
    + SPIRE/GREATER_SPIRE 曾见 +spire_aa_credit —— 尖塔 = 腐化
    产能预警,与星港 +2(push_commit_aa_retreat 的
    starport_aa_credit)同教义;sc2 的 enemy_structures 含迷雾
    快照,「曾见」天然成立。腐化出视野 60s 内撤蹲/出发闸仍认账
    (o373b g2 的 13s 视野洞被本信用覆盖)。
    """
    return max(corruptor_broodlord_visible, sticky_peak) + (
        spire_aa_credit if spire_seen else 0
    )


def zerg_departure_floor_ok(
    own_army_supply: float,
    enemy_visible_supply: float,
    ratio: float = 1.5,
) -> bool:
    """O374-②(o373b g2/o373a g1 实证):zerg 出发宽下限判据。纯逻辑,可单测。

    O373-⑥ 的 _army_gate_ok = _opp_is_zerg or ... 使出发闸在
    zerg lane 形同虚设:o373b g2 顶波出击团灭实证;o373a g1
    O302@509.4 出击 6s 后基地被抄同谱系。收窄:敌可见 supply
    ≥ 我方 army supply ×ratio → 即便 zerg 也拦(顶波不出发);
    黄金窗(zt_golden_window_push)走 _force_push 通道天然豁免,
    不动的胜局打法一行不变。
    """
    return enemy_visible_supply < own_army_supply * ratio


def zerg_corruptor_departure_blocked(
    corruptor_broodlord_credited: int, gate: int = 4
) -> bool:
    """O378-⑥a(o377b g1 实证):zerg 信用腐化硬闸 —— 不出击判据。
    纯逻辑,可单测。

    o377b g1 实证:同一秒「塔投资冻结(腐化≥4)」(cannon_
    investment_freeze 已认账)舰队却在出门 —— 塔链知道腐化
    ≥4 是舰队杀手,出击闸不知道;三局共同死因即舰队峰
    10/14/16 拖过 1200s 进腐化+大龙窗口被全歼。信用腐化
    (当帧可见 CORRUPTOR+BROODLORD ∪ 60s 粘滞峰值,调用方
    max(_zerg_cb, _o374_aa_peak)口径,与 O374-① 台账同源)
    ≥gate → O302 出击闸(_army_gate_ok)收 False。zerg 不豁免
    本闸(暴风被腐化完克,o377b 三局团灭实证);黄金窗
    (zt_golden_window_push 自带腐化 ≤4 闸)与 _force_push 通道
    不动。
    """
    return corruptor_broodlord_credited >= gate


def force_push_corruptor_ok(
    fleet_count: int, corruptor_broodlord_credited: int, ratio: float = 1.5
) -> bool:
    """O379-①(o378b g1 尸检):_force_push 通道信用腐化闸。纯逻辑,可单测。

    o378b g1 实证:O378-⑥a 的信用腐化硬闸只收 _army_gate_ok 通道,
    zerg lane 出击几乎全走 _force_push(fleet≥8+t>540,设计上豁免),
    五次在信用腐化 5-18 下出击(1442@9、1472@5、1611@8、1770@18、
    1871@5),舰队 13-18 艘分批喂腐化群全灭 —— O378-⑥ 要防的死法
    原样重演。_force_push 放行加同口径闸(调用方喂 max(当帧, 60s
    粘滞峰),O374-① 台账同源):fleet ≥ 信用腐化 ×ratio 才放行
    (1770s 信用 18 vs fleet 13 = 拦;信用 4 vs fleet 12 = 放),
    否则转蹲守消耗;黄金窗(zt_golden_window_push 自带腐化 ≤4 闸)
    由调用方豁免,本判据只管 _force_push 本通道。信用 0 = 无腐化
    情报,恒放行(旧语义不动)。
    """
    return fleet_count >= corruptor_broodlord_credited * ratio


def push_fleet_floor_ok(fleet_total: int, floor: int = 5) -> bool:
    """O376-⑤(o375b 尸检):O302 出击舰队下限。纯逻辑,可单测。

    o375b g2 实证:两次 fleet=4 出击无果+撞波 —— 4 艘舰队压不死人
    也跑不掉,出门就是送战损(下限 4 的口径被实证击穿)。出击闸
    路径(_army_gate_ok 分支,调用方并入)舰队 ≥floor 才放行;
    黄金窗 min_fleet(zt_golden_window_push,舰队 ≥3+追猎齐编)
    与 _force_push(舰队 ≥6/8+t>540)通道不动 —— 那两条自带
    数量/编成前提,豁免语义一行不变。
    O377-①a(o376a 三局 0/3 尸检):下限 6→5 —— floor 6 封杀了
    o373a 胜局配方的首推(528.5s fleet=5 起推 ×29),o376a 首推
    被推迟到 708-776s(Terran 已 40-99 supply,推进窗口数学上
    不存在);5 对齐胜局配方。O377-④ 起入参口径改在场舰队
    (剔除在产/队列,o376a g3 报 6 实 3 的虚高实证)。
    """
    return fleet_total >= floor


def blind_push_blocked(credited_supply: float) -> bool:
    """O376-②(o375 双 lane 尸检):盲推硬闸。纯逻辑,可单测。

    o375a g1 实证:两次 O302 出击时敌当帧可见+remembered 峰值
    全空(信用 supply=0),推出去撞 57→85 supply 主力团灭;
    o375b g2 O302@927.8 commit 后 0.3s 敌 37 supply 显形,
    6 虚空 12s 全灭。信用 supply(enemy_supply_credited =
    max(当帧可见, remembered 粘滞峰值))为 0 = 对敌情一无所
    知,出击即盲推 → 不推(调用方并入 _army_gate_ok,与
    O374-②/O373-⑥ 同判不三判;_force_push/黄金窗通道豁免
    不动)。push_enemy_army_gate 的「敌可见 0 自然过闸」旧
    语义由本闸在调用方覆盖 —— 0 不再等于「被榨干可收割」,
    而是「无情报不出击」。
    """
    return credited_supply <= 0.0


def recipe_push_exempt(
    now: float,
    fleet_total: int,
    main_base_cannons: int,
    opp_race: str,
    window_start: float = 500.0,
    window_end: float = 570.0,
    fleet_need: int = 5,
    min_cannons: int = 2,
) -> bool:
    """O377-①b(o376a 三局 0/3 尸检):o373a 胜局配方的「配方推」
    盲推闸豁免判据。纯逻辑,可单测。

    o376a 实证:Terran lane 侦查断链,信用 supply 恒 0 →
    blind_push_blocked 常闭,叠加 floor 6 后首推推迟到 708-776s,
    推进窗口数学上不存在(o373a 胜局配方首推 528.5s fleet=5
    ×29 被整体删除)。豁免窗口:t∈[window_start,window_end]
    (对齐配方首推 528.5s)且在场舰队 ≥fleet_need 且主基就绪塔
    ≥min_cannons(家有保底防线,不是裸推)→ 豁免盲推闸一次
    「配方推」。只豁免盲推闸:敌军校验闸(push_enemy_army_gate)
    与舰队下限(push_fleet_floor_ok)仍生效,撞波/硬对空照拦。
    限 terran(zerg lane 信用不断链,本豁免不碰 zerg 一行行为)。
    """
    return (
        opp_race == "terran"
        and window_start <= now <= window_end
        and fleet_total >= fleet_need
        and main_base_cannons >= min_cannons
    )


def scout_credit_fallback_ok(
    now: float,
    credited_supply: float,
    opp_race: str,
    stale_after: float = 480.0,
) -> bool:
    """O377-①c(o376a 三局 0/3 尸检):Terran 侦查信用兜底判据。
    纯逻辑,可单测。

    o376a 实证:Terran lane 侦查断链,480-546s 的 O375 预警全是
    「信用supply=0」—— 信用 supply(当帧可见+120s 粘滞峰值)为 0
    且 t≥stale_after → 调用方(OracleManager)把侦查目标从矿区
    轮转改派敌主基方向前出刷信用。无侦查单位时本判据自然空转
    (不新造兵,diff 最小方案);限 terran(zerg lane 不断链)。
    """
    return opp_race == "terran" and now >= stale_after and credited_supply <= 0.0


def transition_push_hold(
    fb_done: bool,
    fleet_count: int,
    main_base_cannons: int,
    threat_active: bool,
    fleet_need: int = 5,
    min_cannons: int = 2,
) -> bool:
    """O374-④b(o373a g1/g2 实证):Terran 转型真空期出击留守判据。
    纯逻辑,可单测。

    o373a g1 509.4s/g2 528.5s 的 O302 出击与敌 515/533s 抄家
    窗口重叠 —— FB 落成到舰队成型的转型真空期(550-700s 舰队
    仅 2-6 艘),舰队出门时家最空,MM 波必穿。留守条件:主基
    就绪塔 ≥min_cannons 或舰队 ≥fleet_need(转型完成);不满足
    → True(守家不跟压,舰队留守 = 蹲守锚点保家,调用方走既有
    热点回防/蹲守分支,不发明新分支)。FB 未落成(真空前半段归
    既有塔链/波次逻辑管)或非转型期 → False 原闸不动。
    O375-①(o374a 三局 0/3 尸检):去 min 化+条件收窄 —— 旧判据
    「min(全基地就绪塔)<2 且 fleet<8」几乎常态成立(新矿 0 塔即
    全局锁死),FB 落成起锁到死:o374a O302 从 o373a 胜局 ×29 掉
    到 0/0/2,g3 舰队 757.3s 刚到 8 立即解锁 ×2(时间戳严丝合缝,
    8 就是绑定约束);「留守保家」同时被证伪(三局舰队全在家,
    527-561s 波照样穿)。改法:①塔口径改主基就绪塔(主基 = 必须
    守住的基地,新矿 0 塔不再全局锁死;不选「任一基地 ≥2」——
    新矿立 2 塔而主基裸奔时放行等于换家);②fleet_need 8→5
    (对齐 o373a 胜局配方 528.5s fleet=5 起推 ×29);③hold 只在
    threat_active(敌波压境)时生效,无波不锁(无波时舰队在家
    也防不住任何东西,出击反而换战损)。
    """
    return (
        fb_done
        and threat_active
        and fleet_count < fleet_need
        and main_base_cannons < min_cannons
    )


def cyber_core_np_default_fallback(streak: int, threshold: int = 2) -> bool:
    """O371-⑤(o370a g3 实证):BY watchdog 连续 no_placement 走
    默认 placement 回退的判据。纯逻辑,可单测。

    o370a g3 实证:BY watchdog 211s no_placement 卡在不换锚死等
    (O370-④a 阈值 ≥1 让首次失败即走默认槽,O357 换锚重选被
    短路;默认槽同样是 solver 黑格时永循环)。调用方改序:首次
    no_placement 立即走 O357 换锚重选;连续 ≥threshold 次
    no_placement(换锚无候选/黑名单不涨时 streak 兜底)再走
    O369-④ 默认 placement 回退。
    """
    return streak >= threshold


def evac_return_gas_stop_remark(worker_tag: int, gas_stopped_tags) -> bool:
    """O365-⑤b(o364b g3 实证):E6 归队即重标停气判据。纯逻辑,可单测。

    E6 归队农民 role 漂回 GATHERING 是停气泄漏主通道(复拽 4 次
    实证):ares Mining 抢在 O364-③b 的 2s 校验环前按残留簿记把
    人拽回气矿。归队帧对停气台账在册者直接重标 _GAS_STOP_ROLE,
    不等校验环。
    """
    return worker_tag in gas_stopped_tags


def anchor_retry_ok(
    now: float,
    np_since: float,
    last_attempt_at: float,
    np_window: float = 30.0,
    retry_cd: float = 30.0,
) -> bool:
    """O365-⑤c(o364b g3 实证):手工锚点 per-base 持续重试判据。
    纯逻辑,可单测。

    旧簿记 taken/失败即销账,下次 no_placement 重等 30s 连续窗
    —— 手工锚点 fired 一次后静默 121s(902-1023s 又空转)。改为
    attempt 簿记跨失败保留:连续 no_placement ≥np_window 首开,
    此后每 retry_cd 持续重试(每次外扩 1 格+打日志),仅派工
    成功才销账(调用方)。last_attempt_at 传 -9999 = 从未试过。
    """
    return now - np_since >= np_window and now - last_attempt_at >= retry_cd
