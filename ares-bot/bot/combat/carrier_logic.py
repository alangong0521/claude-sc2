"""O12/O14 航母专属微操的纯逻辑 —— 锚点评分 / 残血判定 / 站位排序。

不依赖 ares / sc2 运行时,可离线单测(起游戏只测这里,运行时胶水在
bot/combat/carrier_offensive.py)。
"""
from __future__ import annotations

# O14: 残血阈值(盾+血合计百分比,低于它后撤)
WOUNDED_PERC: float = 0.4
# O14: 残血恢复阈值(乒乓抑制:撤出去要回到 ≥55% 才重新进场,
# 否则护盾回充会在 40% 线上反复进出)
WOUNDED_RECOVER_PERC: float = 0.55
# O12: 拦截机放飞机动半径(航母主体距目标的理想距离)
LAUNCH_RANGE: float = 8.0


def is_wounded(shield_health_perc: float, threshold: float = WOUNDED_PERC) -> bool:
    """残血判定(O14):shield+health 合计百分比 < threshold → 后撤到阵后。"""
    return shield_health_perc < threshold


def anchor_score(
    *,
    dist_to_target: float,
    ideal_dist: float,
    height_diff: bool,
    aa_threats: int,
) -> float:
    """锚点评分(O12,越大越好)。纯逻辑,可单测。

    - 距目标偏离 ideal_dist 越远越差(守在拦截机放飞机动半径上);
    - 与目标有地形高差(悬崖/高台隔离,地面部队打不到) → 加分;
    - 锚点防空半径内敌可对空单位越多 → 大幅降权(送航母不如不站)。
    """
    return (
        -abs(dist_to_target - ideal_dist)
        + (3.0 if height_diff else 0.0)
        - 4.0 * aa_threats
    )


def best_anchor(candidates: list[dict]) -> dict | None:
    """从候选锚点里选评分最高的,空表 → None。

    candidates: [{"point","dist","ideal","height_diff","aa"}, ...]。
    同分取靠前 —— 调用方把「保守退路」放候选首位,
    找不到地形/防空优势锚点时天然退化为最大射程保守站位(O12 退化要求)。
    """
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda c: anchor_score(
            dist_to_target=c["dist"],
            ideal_dist=c["ideal"],
            height_diff=c["height_diff"],
            aa_threats=c["aa"],
        ),
    )


def wounded_state(
    shield_health_perc: float,
    currently_wounded: bool,
    enter_threshold: float = WOUNDED_PERC,
    exit_threshold: float = WOUNDED_RECOVER_PERC,
) -> bool:
    """残血状态(带滞回,O14 乒乓抑制)。纯逻辑,可单测。

    进入:< enter_threshold;退出:≥ exit_threshold;中间带维持原状态。
    航母护盾回充快,单阈值会在 40% 线上反复进出,滞回消除之。

    O181:增加 enter/exit 参数，允许舰队绝境时（fleet<5 且基地≤1）提高阈值，
    更早后撤保命，避免慢性磨光舰队。
    """
    if shield_health_perc < enter_threshold:
        return True
    if shield_health_perc >= exit_threshold:
        return False
    return currently_wounded


# O25:航母攻击目标优先级(辅助 > 对空威胁 > 杂兵)
_CARRIER_SUPPORT_TYPES = ("MEDIVAC", "RAVEN", "QUEEN")  # 加血/护盾/输血辅助
_CARRIER_AA_THREAT_TYPES = (  # 对空威胁(航母死穴)
    "THOR", "THORAP", "VIKINGFIGHTER", "MISSILETURRET",
    "WIDOWMINE", "WIDOWMINEBURROWED", "CYCLONE", "LIBERATORAGMODE",
)


def carrier_target_priority(type_name: str) -> int:
    """O25:航母攻击优先级评分(高=优先打)。纯逻辑,可单测。
    辅助(医疗机/科学船/皇后,修/盾让敌军打不死)最高;对空威胁(雷神/维京/导弹塔/
    寡妇雷,航母死穴)次之;杂兵最低。与 levers.FOCUS_PRIORITY 解耦(航母 Thor 必杀≠地面兵)。"""
    if type_name in _CARRIER_SUPPORT_TYPES:
        return 100
    if type_name in _CARRIER_AA_THREAT_TYPES:
        return 50
    return 10
