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
