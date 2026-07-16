"""军队组成配置加载 —— 从 army_composition.yml 读兵种,供 Production/Combat 复用。

纯逻辑:只用 pyyaml + sc2 的 UnitTypeId(把字符串名转成枚举)。不依赖 ares 运行时,
可离线单测(传 yaml 路径或 dict)。ProductionManager 造兵、CombatManager 指挥都从
这里取"该造哪些兵/各兵种什么角色/怎么指挥"。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

try:
    import yaml
except ImportError:  # 离线单测环境可能没 pyyaml,允许退化
    yaml = None

try:
    from sc2.ids.unit_typeid import UnitTypeId as UnitID
    _HAS_SC2 = True
except Exception:
    UnitID = None  # type: ignore
    _HAS_SC2 = False


# 默认配置文件位置(相对 ares-bot/)
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "army_composition.yml"

# combat 指挥方式的合法取值
#   tempest_offensive = 暴风舰远射风筝  |  oracle_harass = 先知(OracleManager 管)
#   default           = 通用 attack-move+基础风筝(generic_offensive)
#   siege_offensive   = 攻城坦克架起/撤(M4, ares SiegeTankDecision)
#   medivac_support   = 医疗船治疗跟队(M4, ares MedivacHeal)
#   medivac_transport = 医疗船装兵空投(M4, ares PickUpAndDropCargo)
#   templar_caster    = 高模放灵能风暴(M4, ares UseAOEAbility)
COMBAT_KINDS = (
    "tempest_offensive", "oracle_harass", "default",
    "siege_offensive", "medivac_support", "medivac_transport", "templar_caster",
)

# 种族块键(army_composition.yml 支持 per-race:顶层 protoss/terran/zerg 各一套 units)
RACE_KEYS = ("protoss", "terran", "zerg")


def bot_race_name(ai) -> str | None:
    """从 ares/bot 对象安全取自己的种族名('Protoss'/'Terran'/'Zerg')。

    取不到 → None(调用方 _select_block 回退 protoss)。防御式写法:ai.race 是 sc2 的
    Race 枚举,.name 给字符串;Random 在开局已被引擎解析成实际种族。运行时用,纯测试不碰。
    """
    try:
        r = getattr(ai, "race", None)
        name = getattr(r, "name", None)
        return name if isinstance(name, str) else None
    except Exception:
        return None


def _select_block(data: dict, race: str | None) -> dict:
    """从 yaml 顶层取该 race 的兵种块;兼容旧的\"扁平 units:\"结构。

    - 顶层直接有 `units:` → 扁平结构(旧),原样返回(忽略 race)。
    - 顶层是 per-race(protoss/terran/zerg) → 取 race 对应块;race 缺省/不存在 → 回退
      protoss,再回退第一个存在的块。返回 {} 兜底(空组成)。
    纯逻辑,可单测。
    """
    if not isinstance(data, dict):
        return {}
    if "units" in data:               # 扁平结构(向后兼容)
        return data
    key = (race or "protoss").lower()
    if key in data:
        return data[key] or {}
    if "protoss" in data:             # race 认不出 → 回退 protoss
        return data["protoss"] or {}
    for rk in RACE_KEYS:              # 再回退第一个存在的种族块
        if rk in data:
            return data[rk] or {}
    return {}


@dataclass(frozen=True)
class UnitSpec:
    """单个兵种的配置。"""
    id_name: str            # 引擎枚举名(大写),如 "TEMPEST"
    proportion: float
    priority: int
    role: str               # "ATTACKING" / "HARASSING" / ...
    combat: str             # COMBAT_KINDS 之一
    notes: str = ""


@dataclass
class ArmyComposition:
    """整份军队组成(兵种 + 该种族要研究的升级)。"""
    units: list[UnitSpec]
    upgrades: list[str] = None  # 引擎 UpgradeId 名(大写);默认空,见 __post_init__

    def __post_init__(self):
        if self.upgrades is None:
            self.upgrades = []

    @classmethod
    def from_dict(cls, data: dict) -> "ArmyComposition":
        """从已解析的 dict 构造(可单测,不读文件)。"""
        specs: list[UnitSpec] = []
        for u in data.get("units", []):
            combat = u.get("combat", "default")
            if combat not in COMBAT_KINDS:
                raise ValueError(f"未知 combat 方式 '{combat}'(可用: {COMBAT_KINDS})")
            specs.append(UnitSpec(
                id_name=u["id"].upper(),
                proportion=float(u.get("proportion", 0.0)),
                priority=int(u.get("priority", 5)),
                role=u.get("role", "ATTACKING").upper(),
                combat=combat,
                notes=u.get("notes", ""),
            ))
        _validate(specs)
        # 升级列表(M3):字符串名归一大写、去空、去重保序。运行时再转 UpgradeId 枚举。
        upgrades: list[str] = []
        for up in data.get("upgrades", []) or []:
            name = str(up).strip().upper()
            if name and name not in upgrades:
                upgrades.append(name)
        return cls(specs, upgrades)

    @classmethod
    def load(cls, path: Path | str | None = None, race: str | None = None
             ) -> "ArmyComposition":
        """从 yaml 文件加载。path=None 用 DEFAULT_CONFIG;race 选种族块(见 _select_block)。

        race 传 bot 自己的种族名(如 'Protoss'/'Terran'/'Zerg',大小写不敏感)。
        yaml 是旧扁平结构时 race 被忽略,行为与之前一致。
        """
        if yaml is None:
            raise RuntimeError("pyyaml 未安装,无法加载 army_composition.yml")
        p = Path(path) if path else DEFAULT_CONFIG
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        return cls.from_dict(_select_block(data, race))

    # ── 给 ares SpawnController 用的 dict ──
    def spawn_dict(self):
        """{UnitID: {proportion, priority}} —— 给 SpawnController/ProductionController。
        需要 sc2;离线无 sc2 时抛错(调用方在 bot 运行时才有 sc2)。

        只收 proportion>0 的兵种(真正在产的);proportion=0 的\"已登记但不入产\"兵种
        (如 ORACLE 走单独建造、新加的备选兵种)不喂给 SpawnController。
        默认 protoss 块因此退化成原来的 {TEMPEST: 1.0},与已验证行为逐位一致。
        """
        if not _HAS_SC2:
            raise RuntimeError("sc2 未安装,spawn_dict 需运行时")
        return {
            getattr(UnitID, u.id_name): {
                "proportion": u.proportion, "priority": u.priority,
            }
            for u in self.units if u.proportion > 0
        }

    # ── 升级(M3):给 ares UpgradeController 用 ──
    def upgrade_names(self) -> list[str]:
        """升级枚举名列表(纯字符串,可离线单测)。"""
        return list(self.upgrades)

    def upgrade_ids(self):
        """[UpgradeId] —— 名字转引擎枚举,认不出的静默跳过(容忍手误/版本差异)。
        需要 sc2;离线无 sc2 时抛错(调用方在 bot 运行时才用)。"""
        if not _HAS_SC2:
            raise RuntimeError("sc2 未安装,upgrade_ids 需运行时")
        from sc2.ids.upgrade_id import UpgradeId
        out = []
        for name in self.upgrades:
            uid = getattr(UpgradeId, name, None)
            if uid is not None:
                out.append(uid)
        return out

    def by_combat(self, combat: str) -> list[UnitSpec]:
        """取某种指挥方式的所有兵种。"""
        return [u for u in self.units if u.combat == combat]

    def by_role(self, role: str) -> list[UnitSpec]:
        """取某种角色(如 ATTACKING)的兵种。"""
        role = role.upper()
        return [u for u in self.units if u.role == role]

    def unit_ids(self, combat: str | None = None):
        """兵种枚举名列表(可选按 combat 过滤)。运行时用 getattr(UnitID, name)。"""
        specs = self.by_combat(combat) if combat else self.units
        return [u.id_name for u in specs]


def _validate(specs: Sequence[UnitSpec]) -> None:
    """配置合理性校验:proportion 非负、combat 合法、id 唯一。"""
    ids: set[str] = set()
    total = 0.0
    for s in specs:
        if s.id_name in ids:
            raise ValueError(f"重复兵种配置: {s.id_name}")
        ids.add(s.id_name)
        if s.proportion < 0:
            raise ValueError(f"{s.id_name} proportion 不能为负: {s.proportion}")
        total += s.proportion
    # proportion 之和应在 1.0 附近(允许 oracle 这种 0 占比单独存在,松校验)
    if specs and total > 1.0 + 1e-6:
        raise ValueError(f"proportion 总和 {total} 超过 1.0")