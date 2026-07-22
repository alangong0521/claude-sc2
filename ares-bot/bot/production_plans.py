"""生产计划纯逻辑 —— 种族无关的\"该造多少农民/多少气\"计算,可离线单测。

ProductionManager 各种族路径(Protoss 现有、Terran M1)都从这里取目标数量,把\"算多少\"
和\"怎么造(ares 行为)\"分开:前者纯逻辑可测,后者需运行时。
"""
from __future__ import annotations


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
    gas_gap: dict,
    buildable: dict,
    max_gas_gap: float,
) -> dict:
    """憋气机制（O5 方案 b）：给 freeflow 配比加「攒资源等高优先兵种」的动态截断。

    freeflow 下 ares SpawnController 忽略配比只按优先序：p0 买不起就 fall-through
    到 p1，低优先兵种若永远可负担就把瓶颈资源永远吃掉（C5a 镜像，O5 实证：
    风暴 175 气吃掉每一分钱，航母 250 气永远攒不出）。本函数在 spawn dict 喂给
    SpawnController 前按当前局势裁剪，bot 层实现、不动 ares：

    - p0 = 当前可造（科技就绪）的最高优先兵种；可造兵种 <2 个 → 原样返回（没得截）。
    - p0 编队占比 ≥ 配比 → 把 p0 摘出 dict，低优先兵种照常补位（副 C 语义保留）；
      摘掉后剩下的没有可造兵种 → 原样返回（防精确配比点停产，C5a 教训）。
    - p0 占比落后 → p0 买得起，或气缺口 ≤ max_gas_gap（「接近买得起」，阈值走
      flows.yml 的 save_up）时，只留 p0（截断后续低优先，攒资源等它）；
      缺口还很大 → 原样返回，低优先兵种先顶着生产。

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
    if not affordable.get(p0, False) and gas_gap.get(p0, 0) > max_gas_gap:
        return dict(spawn)
    return {p0: spawn[p0]}


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
    """
    if rush_active or bases >= max_bases or nexus_pending:
        return False
    saturated = workers_per_base > 0 and supply_workers >= workers_per_base * bases
    advantage = own_army_supply >= enemy_army_supply + advantage_supply
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
