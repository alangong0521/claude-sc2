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
) -> bool:
    """动态开矿触发判定（E2，carrier 流）。纯逻辑，可单测。

    爆仓触发：农民 ≥ workers_per_base × 当前基地数（矿线饱和，开分矿消化农民）；
    优势触发：我方 army supply ≥ 敌可见 army supply + advantage_supply（前线有优势提前开）。
    约束：rush_active 期间不开（rush 响应优先）、到 max_bases 停、已有 nexus 在建不叠加
    （配合 ExpansionController max_pending=1，逐矿评估，局势变了就停）。
    E4b 修正：敌可见 army supply 为 0 时**禁止优势触发**——0 可见不是优势是未知
    （敌兵藏迷雾时"假优势"曾导致裸奔扩张+预留停产自绞，E4b 实证）；
    爆仓触发不依赖敌情，不受影响。
    """
    if rush_active or bases >= max_bases or nexus_pending:
        return False
    saturated = workers_per_base > 0 and supply_workers >= workers_per_base * bases
    advantage = (
        enemy_army_supply > 0
        and own_army_supply >= enemy_army_supply + advantage_supply
    )
    return saturated or advantage


def expansion_cannon_count(ec_min: int, ec_max: int, enemy_army: int) -> int:
    """分矿塔数估算（E2）：clamp(min, min + 敌可见作战单位//4, max)。
    min=保守线(给回援争取时间)，每多 4 个敌兵 +1 塔，max 封顶防塔烧钱。纯逻辑。"""
    return max(ec_min, min(ec_max, ec_min + max(0, enemy_army) // 4))


def full_gas_bases(gas_per_base: list[int], full: int = 2) -> int:
    """满采气基地数（E2 气体闸门）：每基地 ready assimilator ≥ full(默认 2) 算满采。
    1 个满采气基地 ≈ 养 1 个星门全力产航母（210+ 气/分钟 vs 航母 234 气/分钟）。"""
    return sum(1 for c in gas_per_base if c >= full)


def gas_gated_stargate_target(cap: int, gas_per_base: list[int]) -> int:
    """星门目标数的气体闸门（E2）：min(cap, 满采气基地数 + 1)。
    +1 的理由（司令 2026-07-21）：气矿会有存款积累可爆兵，且风暴耗气更慢
    （175气/43s vs 航母 250气/64s），产能可以略超稳态气体收入。
    例：单矿双气满采 → 2 星门；双矿四气满采 → 3 星门。纯逻辑。"""
    return min(cap, full_gas_bases(gas_per_base) + 1)


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


def research_paused_for_rush(rush_active: bool) -> bool:
    """rush 期间研究是否整体让位（E3 回归修复）。纯逻辑，可单测。

    O8 把 UpgradeController 以 prioritize=True 放进 MacroPlan 最前——研究预留
    截断后续 plan，把 rush 响应包（叉子/塔都在 SpawnController/后续行为里）饿死
    （bench e3-carrier-vh-zerg-rush game_02 实证：rush 窗口只出 1 叉 2 塔败北）。
    rush_active（含 O9 scout verdict 的提前触发）期间不注册 UpgradeController，
    响应包独占资源；rush 解除后恢复 prioritize 预留。
    """
    return rush_active


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


def floor_army_defends_home(has_pre_fleet: bool, primary_count: int) -> bool:
    """舰队成型前（pre_fleet 保底阶段）地面兵是否默认守家（E3g trickle 实证）。
    纯逻辑，可单测。

    E3g game_01：无 stance、rush_active=False 时 combat 默认 attack_target=最近
    敌建筑，6 个保底叉子被拉过全图送进蟑螂群（敌波到脸前清零）。规则：
    流派配了 pre_fleet 且舰队主 C 计数为 0（未成型）→ 默认守家；主 C 上线
    恢复默认进攻。司令 stance/target 命令与 rush 联动优先级更高，不受影响。
    """
    return has_pre_fleet and primary_count == 0


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
    can_afford: bool, attempt_age: float, grace: float = 6.0
) -> bool:
    """钱不够被派出钉点的建造工人是否撤回采矿（O11）。纯逻辑，可单测。

    ares 多条路径（ProtossStaticDefence / ExpansionController / TechUp）不查存款
    就派工人，到位后 BuildingManager 等得起才下 build 命令 → 工人钉点干等。
    原则（司令）：派了等 grace 秒钱仍不够 → 拆 tracker 撤回采矿（行为下帧会
    重新派工，往返途中钱照采）。人口紧急态的水晶例外（E3h-B，故意钉）。
    """
    return (not can_afford) and attempt_age > grace


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


def idle_builder_alarm(wait_age: float, threshold: float = 1.0) -> bool:
    """O19：连续干等超过 threshold 秒 → 该发 idle_builder 事件。纯逻辑，可单测。

    1s 是司令章程的观测线（「>1s 不干活干等建造」要曝光）；与 O11 watchdog
    的 6s 撤回不冲突——本判据只观测发事件，不改任何行为。
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


def dispatch_viable(
    minerals: float, income_per_sec: float, walk_time: float, cost: float
) -> bool:
    """派建造工人前的可负担估算（O19 钉点修复）。纯逻辑，可单测。

    到位时钱够才派：当前矿 + 走位时间 × 收入速率 ≥ 造价 → 派（到位即开工，
    零钉点）；不够 → 不派（建筑等下帧重估，农民继续采矿——缺钱时正确行为
    是**不派**，不是派了再撤，E4c 撤回循环前科）。

    背景：ares BuildStructure / ExpansionController(prioritize) 不查 can_afford
    就派工，农民钉在建造点等钱（e7e8 bench idle_builder 实证：
    PHOTONCANNON 9-21 次/局、NEXUS 2-7 次/局）。
    """
    return minerals + income_per_sec * walk_time >= cost
