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
