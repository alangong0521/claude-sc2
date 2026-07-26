"""Shared steer vocabulary — single source of truth.

参谋长(LLM)能用的命令词都在这里。bot 侧(`steer.py`)和指挥 CLI(`steer_cli.py`)
都从本模块导入,避免两处各抄一份、改一处忘另一处。

纯字符串常量,不 import ares / sc2,所以 `steer_cli.py` 不用起游戏也能轻量导入。

The full set of high-level levers the LLM chief-of-staff can pull. Both the bot side
(`steer.py`) and the command CLI (`steer_cli.py`) import from here so the vocabulary
lives in exactly one place. Pure string constants — no ares/sc2 imports.
"""
from __future__ import annotations

STANCES: tuple[str, ...] = ("attack", "defend", "hold", "retreat")  # ①姿态 / posture
TARGETS: tuple[str, ...] = (  # ②语义目标 / where to push (bot resolves to a Point2)
    "enemy_main", "enemy_natural", "enemy_third", "enemy_fourth",
    "enemy_backdoor",   # 绕后/偷家点(离敌军重心最远的敌方分矿)/ backdoor expansion
    "map_center", "home",
)
FOCUS: tuple[str, ...] = ("weakest", "closest", "workers", "priority")  # ③焦点 / focus fire(priority=B2 静态优先级表)
# ④机动 / maneuver:只有 ambush / hold_position 会改变行为(令部队原地蹲守待机);
# 其余情况(不设)= 正常压上。别加没有实现的词,免得 CLI 广告空操作。
MANEUVERS: tuple[str, ...] = ("ambush", "hold_position")
HARASS: tuple[str, ...] = ("on", "off")          # ⑤持续 / oracle harass toggle
TRIGGERS: tuple[str, ...] = ("now", "when_enemy_away", "when_maxed")  # ⑥择时 / timing
EXPAND: tuple[str, ...] = ("yes", "no")           # 运营 / take an expansion
# 焦点敌人(多人混战用;1v1 只有 E1):所有"敌人相关"目标都相对它解析。
# Focus enemy (FFA); every enemy_* target resolves relative to it. E1 = nearest.
ENEMY_SLOTS: tuple[str, ...] = ("E1", "E2", "E3", "E4")
# 通用建筑杠杆 build=<结构>:一次性造一个,微操(选农民/选位置)全在 bot 层。
# Generic build lever: queue one structure; worker/placement micro stays in the bot.
# BUILD_ALIASES 是用户友好别名(如 gas=assimilator),bot 侧 _resolve_buildable 先查它。
# BUILDABLE 是 CLI `vocab` 展示的"规范名"集合;别名通过 BUILD_ALIASES 暴露,二者保持一致。
BUILDABLE: tuple[str, ...] = (
    "nexus", "assimilator", "stargate", "gateway",
    "cyberneticscore", "forge", "robo", "fleetbeacon", "twilight",
)
# build=<名> 的别名 → 规范名。CLI 校验/vocab 都认这些别名。
# ⚠️ 规范名 .upper() 后必须就是引擎枚举名(levers.resolve_build_name 靠它 getattr(UnitID,…)):
# 不一致的必须在本表映射到真枚举名 —— 如 twilight → twilightcouncil(枚举 TWILIGHTCOUNCIL),
# 否则 bot 侧拿不到枚举,build 命令被静默忽略。
BUILD_ALIASES: dict[str, str] = {
    "base": "nexus", "expand": "nexus", "nexus": "nexus",
    "gas": "assimilator", "geyser": "assimilator", "assimilator": "assimilator",
    "stargate": "stargate", "gateway": "gateway",
    "cyber": "cyberneticscore", "cyberneticscore": "cyberneticscore",
    "forge": "forge",
    "robo": "roboticsfacility", "roboticsfacility": "roboticsfacility",
    "fleetbeacon": "fleetbeacon",
    "twilight": "twilightcouncil", "twilightcouncil": "twilightcouncil",
    "pylon": "pylon",  # pylon 不在 BUILDABLE(非核心),但 bot 能造,CLI 也放行
}
# orders.json 里所有可写字段(bot 读取时按此列表取)/ every field the bot reads back.
FIELDS: tuple[str, ...] = (
    "stance", "target", "focus", "maneuver", "harass", "trigger",
    "expand", "build", "scout", "enemy", "note", "defend",
)
# 元字段(下划线前缀,内部用):不进 FIELDS、不进 vocab 展示、cmd_show 不展示、validate 跳过。
# 目前仅 _scout_ts:scout 命令刷新时间戳,让 bot 感知"scout 被重新下发"(Bug2:
# clear+scout=on 同步执行时 bot 4s 轮询读不到 clear 中间态,_scout_done 不重置)。
META_FIELDS: tuple[str, ...] = ("_scout_ts",)
# 每个字段的合法取值(用于 CLI 校验)。note/enemy 之外都是受限枚举。
# None 表示"自由取值/不校验":note=自由文本;build=BUILDABLE+别名+任意引擎结构名(运行时再判);
# focus 除 weakest/closest/workers 外还接受任意兵种名(如 SIEGETANK),故不封死。
_FIELD_VALUES: dict[str, tuple[str, ...] | None] = {
    "stance": STANCES,
    "target": TARGETS,
    "maneuver": MANEUVERS,
    "harass": HARASS,
    "trigger": TRIGGERS,
    "expand": EXPAND,
    "scout": ("on", "off"),
    "enemy": ENEMY_SLOTS,
    "defend": ("yes", "no"),   # F2: 铺防御塔(B+F+Cannon)开关
    "focus": None,    # weakest/closest/workers + 任意兵种名
    "build": None,    # BUILDABLE + 别名 + 任意引擎结构名
    "note": None,     # 自由文本
}


def enemy_slot_index(sel: str | None) -> int | None:
    """焦点敌人槽位字符串 → 0 基索引:'E2' → 1。认不出 → None(调用方回退到最近 E1)。

    Focus-enemy slot string → 0-based index ('E2' → 1); None if unparseable.
    """
    if not sel:
        return None
    s = sel.strip().upper()
    if s.startswith("E") and s[1:].isdigit() and int(s[1:]) >= 1:
        return int(s[1:]) - 1
    return None


def canonical_build(name: str) -> str:
    """build=<名> → 规范名(走别名表)。原样返回未知名(交给 bot 运行时再判能不能造)。

    Canonicalize a build lever name via BUILD_ALIASES. Unknown names pass through
    so bot-side `_resolve_buildable` can still try `UnitID[name.upper()]`.
    """
    if not name:
        return name
    key = name.strip().lower()
    return BUILD_ALIASES.get(key, key)


def validate_field(field: str, value: str) -> list[str]:
    """校验单个 key=value,返回错误信息列表(空=合法)。

    规则:
      - field 必须在 FIELDS 内;
      - 受限枚举字段(stance/target/maneuver/harass/trigger/expand/scout/enemy)
        值必须在对应元组里;
      - focus 接受 weakest/closest/workers 或任意大写兵种名(只做形式校验);
      - build 自由放行(规范名/别名/任意结构名都行,运行时再判可否建造);
      - note 自由,不校验。

    Validate one key=value; return list of human-readable error strings (empty=ok).
    Pure logic — no ares/sc2 import, safe to run headless.
    """
    errs: list[str] = []
    if field.startswith("_"):
        # 元字段(下划线前缀,CLI 内部维护如 _scout_ts):不校验、不让用户直接写。
        # 比白名单更通用,未来加 _* 元字段不用改这里。
        return errs
    if field == "target" and str(value).strip() == "":
        # O28:target= 空值 = 清空固定目标(bot 轮巡清图)。attack_target property
        # 对 "" falsy 走默认轮巡,无需改 bot 侧。skill 词表"清图=set target= stance=attack"。
        return errs
    if field not in FIELDS:
        errs.append(f"未知命令字段 '{field}'(可用: {' '.join(FIELDS)})")
        return errs
    allowed = _FIELD_VALUES.get(field)
    if allowed is None:
        # 自由取值字段,只做轻形式校验
        if field == "focus" and value:
            v = value.strip()
            # 兵种名通常全大写;weakest/closest/workers/priority 小写。空串无意义。
            if v.lower() not in ("weakest", "closest", "workers", "priority") and not v.isupper():
                errs.append(
                    f"focus 值 '{value}' 看着不像兵种名(应全大写如 SIEGETANK)"
                    f"或关键字 weakest/closest/workers/priority"
                )
        return errs
    v = value.strip()
    if v not in allowed:
        errs.append(f"{field} 值 '{value}' 不合法(可用: {' '.join(allowed)})")
    return errs


def validate_order(order: dict) -> list[str]:
    """校验整份 order dict,返回所有错误信息(空=全合法)。纯逻辑,不起游戏。"""
    errs: list[str] = []
    for k, v in order.items():
        if v is None:
            continue
        errs.extend(validate_field(k, str(v)))
    return errs