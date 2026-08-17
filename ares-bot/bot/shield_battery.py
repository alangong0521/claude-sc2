"""护盾电池主动充能微操 —— 从无到有(此前只有 ProtossStaticDefence 负责"建",
没人负责"奶";SC2 里电池充能不是自动施法,必须手动点)。

调研来源(docs/community-tactics-research.md §2.3,Sharky ShieldBatteryManager):
- 充能半径 = 技能射程 6 + 建筑半径 1.125 ≈ 7.125;
- 目标筛选:盾低于上限-5、非建筑;**按 DPS 降序、盾量升序**选(优先奶高输出单位);
- 防重复充能:跳过已被某块电池 Orders 锁定的单位;
- 能量守卫:电池能量 <20 不充(Overcharge 期间才无视能量,框架暂不支持,记 backlog)。

对「对 rush 防守」性价比极高:一块 100 矿电池 ≈ 每秒 50+ 盾回复。
所有流派受益但纯增量:没有电池/没有残盾单位时零指令,不改任何现有行为。
"""
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId as UnitID

RESTORE_RANGE: float = 7.125   # 技能射程 6 + 建筑半径 1.125(Sharky)
SHIELD_MARGIN: float = 5.0     # 盾低于上限 5 点才值得奶(防抖)
MIN_ENERGY: float = 20.0       # 电池能量守卫(Overcharge 无视能量暂不支持)
OVERCHARGE_MIN_ENERGY: float = 45.0  # 超载能耗(O121:50→45,电池出生 25 能量,
                                     # 波前充能时间常常不够 50,零触发实证)
OVERCHARGE_ENEMY_RADIUS: float = 15.0  # 电池此半径内有敌地面才超载(波次接触)


def should_overcharge(
    enemy_ground_near: int, energy: float,
    min_enemy: int = 2, min_energy: float = OVERCHARGE_MIN_ENERGY,
) -> bool:
    """O120-②(o119 系列实证):电池超载触发判据。纯函数,可单测。

    超载从没用过 —— 塔+电池+超载是神族防多波的标准答案(超载目标
    盾回翻倍,≈50 能量换一座塔/一个前排多站 10+s)。敌地面进电池
    OVERCHARGE_ENEMY_RADIUS 且能量够 → 超载;平时不烧(能量留着奶)。
    """
    return enemy_ground_near >= min_enemy and energy >= min_energy


def overcharge_with_batteries(ai) -> int:
    """每帧调用:波次接触时给电池射程内盾量最低的朋友(含塔)挂超载。
    返回本帧新下的超载指令数。异常静默(返回 0)—— 超载不上是小事。"""
    try:
        batteries = [
            s for s in ai.structures(UnitID.SHIELDBATTERY)
            # O121-②:去掉「not s.orders」过滤 —— 正在奶(restore 中)的电池
            # 恰好是接触中的电池,过滤它 = 超载永零触发(o120 三局实证);
            # 超载优先级 > 平奶,直接顶替当前指令
            if s.is_ready and s.energy >= OVERCHARGE_MIN_ENERGY
        ]
        if not batteries:
            return 0
        issued = 0
        for b in batteries:
            enemy_near = sum(
                1 for u in ai.enemy_units
                if not u.is_structure and not u.is_flying
                and u.distance_to(b) <= OVERCHARGE_ENEMY_RADIUS
            )
            if not should_overcharge(enemy_near, b.energy):
                continue
            # O122-③:塔优先(超载塔=DPS 续航最值),无残盾塔才给单位;
            # 目标名写进簿记(o121b 局1:超载 ×4 但基地还是掉,要看挂给谁)
            _structs = [
                s for s in ai.structures
                # O123-②:白名单(塔/主基地)—— o122 局3 超载挂给 PYLON 白烧能量
                if overcharge_struct_allowed(s.type_id.name)
                and s.shield_max > 0 and s.shield < s.shield_max - SHIELD_MARGIN
                and s.distance_to(b) <= RESTORE_RANGE
            ]
            _units = [
                u for u in ai.units
                # O293-③:农民不挂超载(盾回翻倍花在 PROBE 上=白烧能量)
                if overcharge_unit_allowed(u.type_id.name)
                and u.shield_max > 0 and u.shield < u.shield_max - SHIELD_MARGIN
                and u.distance_to(b) <= RESTORE_RANGE
            ]
            target = pick_overcharge_target(_structs, _units)
            if target is None:
                continue
            b(AbilityId.BATTERYOVERCHARGE_BATTERYOVERCHARGE, target)
            ai._last_oc_target = target.type_id.name
            issued += 1
        return issued
    except Exception:
        return 0


OVERCHARGE_STRUCT_WHITELIST = frozenset({"PHOTONCANNON", "NEXUS"})

OVERCHARGE_UNIT_BLACKLIST = frozenset({"PROBE"})


def overcharge_unit_allowed(type_name: str) -> bool:
    """O293-③(o291a game_01 实证):超载单位黑名单。纯函数,可单测。

    局1:超载挂给 PROBE —— 农民盾薄血少,超载的盾回翻倍花在农民身上
    =白烧 45 能量,同帧塔/叉子在挨打。与 O123-② 建筑白名单同构:
    超载只给作战单位(叉/追猎/舰队),农民不挂。
    """
    return type_name not in OVERCHARGE_UNIT_BLACKLIST


def overcharge_struct_allowed(type_name: str) -> bool:
    """O123-②(o122 局3 实证):超载建筑白名单。纯函数,可单测。

    局3:超载挂给了 PYLON(775)—— 水晶不是战斗单位,白烧 45 能量。
    白名单 = 光子塔(前排 DPS)/ 主基地(经济命脉);其余建筑不挂。
    """
    return type_name in OVERCHARGE_STRUCT_WHITELIST


def pick_overcharge_target(friend_structs: list, friend_units: list):
    """O122-③:超载目标选择。纯函数,可单测。

    塔优先(超载塔 = DPS 续航最值,塔在阵在);无残盾塔 → 盾量百分比
    最低的单位。入参仅需 .shield/.shield_max 属性(离线可测轻量假对象)。
    """
    if friend_structs:
        return min(
            friend_structs, key=lambda u: u.shield / max(u.shield_max, 1)
        )
    if friend_units:
        return min(friend_units, key=lambda u: u.shield / max(u.shield_max, 1))
    return None


def pick_restore_target(candidates: list, busy_tags: set[int]):
    """从候选里选充能目标:DPS 降序优先,同 DPS 取盾最少(Sharky 规则)。
    candidates: 任意带 .tag/.shield/.shield_max(或 shield_percentage)/DPS 属性的对象列表
    (用 getattr 取,方便离线单测喂轻量假对象);busy_tags: 已被电池锁定的单位 tag。
    返回选中对象或 None。纯函数,可单测。"""
    best = None
    best_key = None
    for u in candidates:
        if u.tag in busy_tags:
            continue
        dps = max(getattr(u, "ground_dps", 0) or 0, getattr(u, "air_dps", 0) or 0)
        shield = getattr(u, "shield", 0)
        key = (-dps, shield)  # 越小越优:DPS 高、盾少
        if best_key is None or key < best_key:
            best, best_key = u, key
    return best


def restore_with_batteries(ai) -> int:
    """每帧调用:让有能量的电池给射程内残盾友军充能。返回本帧新下的充能指令数。
    异常静默(返回 0)—— 奶不上是小事,绝不能让这个增量逻辑崩主循环。"""
    try:
        batteries = [
            s for s in ai.structures(UnitID.SHIELDBATTERY)
            if s.is_ready and s.energy >= MIN_ENERGY
        ]
        if not batteries:
            return 0
        # 已被电池锁定的目标(防重复充能)
        busy: set[int] = set()
        for b in batteries:
            for o in b.orders:
                if o.ability.id == AbilityId.EFFECT_RESTORE and o.target:
                    busy.add(o.target if isinstance(o.target, int) else 0)
        issued = 0
        for b in batteries:
            if b.orders:  # 这块电池正在奶,不打扰(防抖,Sharky 同规则)
                continue
            candidates = [
                u for u in ai.units
                if not u.is_structure
                and u.shield_max > 0
                and u.shield < u.shield_max - SHIELD_MARGIN
                and u.distance_to(b) <= RESTORE_RANGE
            ]
            target = pick_restore_target(candidates, busy)
            if target is not None:
                b(AbilityId.EFFECT_RESTORE, target)
                busy.add(target.tag)
                issued += 1
        return issued
    except Exception:
        return 0
