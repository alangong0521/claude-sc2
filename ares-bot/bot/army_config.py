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
COMBAT_KINDS = ("tempest_offensive", "oracle_harass", "default")


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
    """整份军队组成。"""
    units: list[UnitSpec]

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
        return cls(specs)

    @classmethod
    def load(cls, path: Path | str | None = None) -> "ArmyComposition":
        """从 yaml 文件加载。path=None 用 DEFAULT_CONFIG。"""
        if yaml is None:
            raise RuntimeError("pyyaml 未安装,无法加载 army_composition.yml")
        p = Path(path) if path else DEFAULT_CONFIG
        data = yaml.safe_load(p.read_text(encoding="utf-8"))
        return cls.from_dict(data or {})

    # ── 给 ares SpawnController 用的 dict ──
    def spawn_dict(self):
        """{UnitID: {proportion, priority}} —— 给 SpawnController/ProductionController。
        需要 sc2;离线无 sc2 时抛错(调用方在 bot 运行时才有 sc2)。"""
        if not _HAS_SC2:
            raise RuntimeError("sc2 未安装,spawn_dict 需运行时")
        return {
            getattr(UnitID, u.id_name): {
                "proportion": u.proportion, "priority": u.priority,
            }
            for u in self.units
        }

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