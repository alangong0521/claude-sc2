"""流派配置加载 —— 从 flows.yml 读流派(神族生产侧单一真相源)。

纯逻辑:只用 pyyaml + sc2 的枚举(字符串名转枚举)。不依赖 ares 运行时,可离线单测
(from_dict 路径)。ProductionManager 按 BUILD env 选流派,造兵配方/科技链/升级/
chrono/追加产能/一次性建造全从它读。战斗侧不读本模块(CombatManager 走
army_composition.yml 兵种注册表,流派无关)。
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError:  # 离线单测环境可能没 pyyaml,允许退化
    yaml = None

try:
    from sc2.ids.unit_typeid import UnitTypeId as UnitID
    from sc2.ids.upgrade_id import UpgradeId
    _HAS_SC2 = True
except Exception:
    UnitID = None  # type: ignore
    UpgradeId = None  # type: ignore
    _HAS_SC2 = False


# 默认配置文件位置(相对 ares-bot/)
DEFAULT_CONFIG = Path(__file__).resolve().parent.parent / "flows.yml"
# 未指定/未知名时的回退流派(已验证行为)
DEFAULT_FLOW = "tempest"
# chrono.when 合法取值
CHRONO_WHEN = ("always", "primary_pending")


@dataclass(frozen=True)
class ExtraProduction:
    """矿富余时追加的产兵建筑(治"矿花不出去")。desired = min(cap, base + 就绪基地数)。"""
    id_name: str            # 引擎枚举名(大写),如 STARGATE / GATEWAY
    cap: int = 6            # 封顶
    base: int = 1           # 随基地数放大的基数


@dataclass(frozen=True)
class ChronoConfig:
    """chrono 加速配置。targets 按顺序取第一个有建筑的;when 见 CHRONO_WHEN。"""
    targets: tuple[str, ...] = ()
    when: str = "primary_pending"


@dataclass(frozen=True)
class AutoExpand:
    """自动开矿(缺省不开,司令 expand=yes 不受影响)。两种模式:
    旧式(stalker):at 秒到达 或 农民数 ≥ when_workers 触发,一次扩到 to 个;
    动态(carrier,配了 max_bases):爆仓(农民 ≥ when_workers×当前基地数)或
    前线优势(我方 army supply ≥ 敌可见 army supply + advantage_supply)时
    逐矿 +1,上限 max_bases,rush_active 期间不开。"""
    at: float = 0.0
    to: int = 2
    when_workers: int = 0      # 旧式:触发农民数(0=只看时间);动态:每矿饱和农民数
    max_bases: int = 0         # >0 走动态模式,基地数上限
    advantage_supply: int = 0  # 动态:我方 army supply 领先敌可见 army supply 此值 → 提前开


@dataclass(frozen=True)
class ExpansionCannons:
    """分矿塔防估算:photon_cannons_per_base = clamp(min, min + 敌可见作战单位//4, max)。
    min 是保守线(给回援争取时间),max 封顶防塔烧钱拖垮经济。"""
    min: int = 3
    max: int = 8


@dataclass(frozen=True)
class PreFleet:
    """舰队成型前地面保底(E3e):舰队主 C 出生前混入保底兵种(矿耗地面兵,
    不吃气不抢舰队资源),达 cap 或主 C 上线自动退出。None=关。
    E3f:cap 随敌可见兵力伸缩(pre_fleet_cap):base 和平期下限,
    敌兵×per_enemy 威胁伸缩,hard max 封顶;max=0 时固定 cap。"""
    id_name: str = "ZEALOT"
    cap: int = 6
    per_enemy: float = 0.0
    max: int = 0


@dataclass(frozen=True)
class PivotConfig:
    """自适应 pivot(反rush/反空军):对面爆空军 → spawn 混入 anti_air_units;
    rush 检测成立 → 先出 rush_zealots 个叉子顶 + 全军守家,威胁解除自动恢复。
    rush_cannons(E1 实验开关):rush 预警时是否提前铺塔(默认 true=现状臂 A;
    false=臂 B 纯叉子不铺塔;臂 C 纯塔 = rush_zealots: 0 + rush_cannons: true)。"""
    anti_air_units: tuple[str, ...] = ()
    anti_air_proportion: float = 0.0
    anti_air_trigger: int = 3
    rush_zealots: int = 0
    rush_cannons: bool = True


@dataclass
class FlowConfig:
    """一个流派的完整生产配置。"""
    name: str
    spawn: dict                  # {引擎兵种名(大写): {"proportion": float, "priority": int}}
    core_structures: list[str]   # 有序科技链(引擎结构名大写)
    upgrades: list[str]          # 引擎 UpgradeId 名(大写)
    extra_production: ExtraProduction | None
    chrono: ChronoConfig
    one_off: list[str]           # 一次性建造(引擎结构/兵种名大写,如 ORACLE)
    rally_min_army: int = 0      # 集结阈值:兵力低于它且司令没下 stance 时先守家(0=关)
    auto_expand: AutoExpand | None = None  # 自动开矿(None=关)
    freeflow: bool = False       # SpawnController.freeflow_mode:不按配比卡产(多兵种流派必开)
    pivot: PivotConfig | None = None  # 自适应机制(反rush/反空军),None=关
    save_up: int = 0             # O5 憋气机制:p0 气缺口 ≤N 时截断低优先生成攒气(0=关)
    expansion_cannons: ExpansionCannons | None = None  # 分矿塔数区间(None=固定 2)
    pre_fleet: PreFleet | None = None  # E3e 舰队成型前地面保底(None=关)

    @classmethod
    def from_dict(cls, name: str, data: dict) -> "FlowConfig":
        """从已解析的 dict 构造(可单测,不读文件)。"""
        spawn: dict = {}
        total = 0.0
        for uid, cfg in (data.get("spawn") or {}).items():
            uid_n = str(uid).strip().upper()
            cfg = cfg or {}
            prop = float(cfg.get("proportion", 0.0))
            prio = int(cfg.get("priority", 5))
            if prop < 0:
                raise ValueError(f"流派 {name} 的 {uid_n} proportion 不能为负: {prop}")
            spawn[uid_n] = {"proportion": prop, "priority": prio}
            total += prop
        if spawn and total > 1.0 + 1e-6:
            raise ValueError(f"流派 {name} spawn 比例和 {total} 超过 1.0")

        ep_raw = data.get("extra_production")
        extra = None
        if ep_raw:
            extra = ExtraProduction(
                str(ep_raw["id"]).strip().upper(),
                int(ep_raw.get("cap", 6)),
                int(ep_raw.get("base", 1)),
            )

        ch_raw = data.get("chrono") or {}
        when = str(ch_raw.get("when", "primary_pending")).strip()
        if when not in CHRONO_WHEN:
            raise ValueError(f"流派 {name} chrono.when '{when}' 非法(可用: {CHRONO_WHEN})")
        targets = tuple(
            str(t).strip().upper() for t in (ch_raw.get("targets") or []) if str(t).strip()
        )

        core = [
            str(s).strip().upper()
            for s in (data.get("core_structures") or []) if str(s).strip()
        ]
        upgrades: list[str] = []
        for u in (data.get("upgrades") or []):
            n = str(u).strip().upper()
            if n and n not in upgrades:
                upgrades.append(n)
        one_off = [
            str(s).strip().upper()
            for s in (data.get("one_off") or []) if str(s).strip()
        ]
        ae_raw = data.get("auto_expand")
        auto_expand = None
        if ae_raw:
            auto_expand = AutoExpand(
                float(ae_raw.get("at", 0.0)), int(ae_raw.get("to", 2)),
                int(ae_raw.get("when_workers", 0)),
                int(ae_raw.get("max_bases", 0)),
                int(ae_raw.get("advantage_supply", 0)),
            )
        ec_raw = data.get("expansion_cannons")
        expansion_cannons = None
        if ec_raw:
            expansion_cannons = ExpansionCannons(
                int(ec_raw.get("min", 3)), int(ec_raw.get("max", 8)),
            )
        pf_raw = data.get("pre_fleet")
        pre_fleet = None
        if pf_raw:
            pre_fleet = PreFleet(
                str(pf_raw.get("id", "ZEALOT")).strip().upper(),
                int(pf_raw.get("cap", 6)),
                float(pf_raw.get("per_enemy", 0.0)),
                int(pf_raw.get("max", 0)),
            )
        pv_raw = data.get("pivot") or {}
        pivot = None
        if pv_raw:
            pivot = PivotConfig(
                anti_air_units=tuple(
                    str(u).strip().upper() for u in (pv_raw.get("anti_air_units") or [])
                ),
                anti_air_proportion=float(pv_raw.get("anti_air_proportion", 0.0)),
                anti_air_trigger=int(pv_raw.get("anti_air_trigger", 3)),
                rush_zealots=int(pv_raw.get("rush_zealots", 0)),
                rush_cannons=bool(pv_raw.get("rush_cannons", True)),
            )
        return cls(
            name=name, spawn=spawn, core_structures=core, upgrades=upgrades,
            extra_production=extra, chrono=ChronoConfig(targets=targets, when=when),
            one_off=one_off,
            rally_min_army=int(data.get("rally_min_army", 0) or 0),
            auto_expand=auto_expand,
            freeflow=bool(data.get("freeflow", False)),
            pivot=pivot,
            save_up=int(data.get("save_up", 0) or 0),
            expansion_cannons=expansion_cannons,
            pre_fleet=pre_fleet,
        )

    @classmethod
    def load(cls, flow: str | None = None, path: Path | str | None = None
             ) -> "FlowConfig":
        """从 yaml 加载指定流派。flow=None/空 → 默认 tempest;未知名 → 警告并回退 tempest
        (防 BUILD 拼写错误静默打成别的流派)。"""
        if yaml is None:
            raise RuntimeError("pyyaml 未安装,无法加载 flows.yml")
        p = Path(path) if path else DEFAULT_CONFIG
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        flows = data.get("flows", {}) or {}
        name = (flow or "").strip().lower() or DEFAULT_FLOW
        if name not in flows:
            print(f"⚠️ 未知流派 '{name}',回退 {DEFAULT_FLOW}"
                  f"(flows.yml 可用: {' '.join(flows)})")
            name = DEFAULT_FLOW
        return cls.from_dict(name, flows[name] or {})

    # ── 运行时方法(需 sc2;离线无 sc2 时抛错,调用方在 bot 运行时才用) ──
    def spawn_dict(self):
        """{UnitID: {proportion, priority}} —— 喂 ares SpawnController(只收 proportion>0)。"""
        if not _HAS_SC2:
            raise RuntimeError("sc2 未安装,spawn_dict 需运行时")
        return {
            getattr(UnitID, k): v for k, v in self.spawn.items() if v["proportion"] > 0
        }

    def upgrade_ids(self):
        """[UpgradeId] —— 名字转引擎枚举,认不出的静默跳过(容忍手误/版本差异)。"""
        if not _HAS_SC2:
            raise RuntimeError("sc2 未安装,upgrade_ids 需运行时")
        out = []
        for n in self.upgrades:
            uid = getattr(UpgradeId, n, None)
            if uid is not None:
                out.append(uid)
        return out

    def core_structure_ids(self):
        """[UnitID] —— 有序科技链转枚举,认不出的静默跳过。"""
        if not _HAS_SC2:
            raise RuntimeError("sc2 未安装,core_structure_ids 需运行时")
        return [
            sid for sid in (getattr(UnitID, n, None) for n in self.core_structures)
            if sid is not None
        ]

    def one_off_ids(self):
        """[UnitID] —— 一次性建造列表转枚举,认不出的静默跳过。"""
        if not _HAS_SC2:
            raise RuntimeError("sc2 未安装,one_off_ids 需运行时")
        return [
            uid for uid in (getattr(UnitID, n, None) for n in self.one_off)
            if uid is not None
        ]
