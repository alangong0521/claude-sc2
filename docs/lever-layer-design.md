# 杠杆层设计 — 把"好玩的指令"翻译成 ares 动作

> 姊妹文档：`experience-spec.md`（讲体验，自上而下）。本文档是它的**中间层实现**：
> 用户嘴里"好玩的指令" → 一套杠杆 → ares 动作。
> **这版是从"哪些指令好玩"倒推出来的**（不是从 ares 能力自下而上凑）——这是它和被删掉的
> 旧 steer-layer-design 的根本区别。
>
> 设计前提（已与用户确认）：
> 1. **Stage 2 不好玩的病根 = 指令大多是"运营"（填表格），缺"战术机动"**。
> 2. 指挥的爽在"打得巧"，不在"管经济" → 杠杆层重心必须是战术机动，运营降为后台自动。
> 3. 好玩的指令归纳为 **8 个爽感原型**（见下表），杠杆层按它们倒推。

ares 接口均对照 vendored `ares-sc2/src/ares/`（2026-06-28/29 核实），真实类名/方法名见各族"ares 接法"。

---

## 0. 八个爽感原型（杠杆层要服务的目标）

| # | 爽感 | 玩家会说 |
|---|---|---|
| A | 大开大合 | "全军压上！""撤！" |
| B | 精准点杀 | "集火那辆攻城车""专杀医疗船" |
| C | 机动取角 | "绕后""埋伏在坡道""占住高地" |
| D | 分兵编排 | "主力守家，分一队偷袭" |
| E | 骚扰消耗 | "去烦他农民、别停" |
| F | 千钧一发 | "快撤！""拉回来！" |
| G | 声东击西 | "假装撤退引他追" |
| H | 抓时机一波 | "趁他兵出去了打！" |

---

## 1. 核心结构：杠杆层是一套小语法 `[谁] × [干什么]`

Stage 2 闷的根：主语永远"全军"，谓语只有 attack/retreat。新杠杆层拆成两维相乘：

```
[ 谁 ]                 ×      [ 干什么 ]
全军 / 主力 / 某支分队          姿态 │ 目标 │ 焦点 │ 机动 │ 持续模式 │ (择时)
```

一个"相乘"带来组合式表达力：`分一队飞龙(谁) × 骚扰二矿(干什么)` 和 `主力(谁) × 守家(干什么)`
可**同时下达**——这就是"像将军一样指挥"。原语数量依然小、可枚举。

**实现上**：杠杆层为每个"谁"维护一份当前命令 `{stance, target, focus, maneuver, mode}`；
每帧 seam 取出每组的命令，在该组单位上注册对应 ares 行为。详见 §5。

---

## 2. 维度一：「谁」—— 分队（新｜支撑 D、E）

「谁」= 一个 **UnitRole 桶**（ares 原生）。这是 Stage 2 完全没有的一维。

**「谁」的选择有三个轴**（可组合）——这是覆盖"派 N 个兵去…"这类指令的关键：
- **数量轴**："派一个兵""派十个兵"→ 从某角色 tag 列表里切 N 个
- **兵种轴**："分一队飞龙"→ 按 `type_id` 筛
- **位置轴**："左边那队""前面那批"→ 按位置 `cy_closest_to` 筛

| 用户会说 | 形成的"谁" | ares 表示 |
|---|---|---|
| 默认 | 全军 | `get_units_from_role(ATTACKING)` |
| "主力" | 主力大队 | `ATTACKING_MAIN_SQUAD`，或 `get_squads()` 里 `main_squad=True` 那支 |
| "派十个兵绕后" | 数量切出的偏师 | 取 ATTACKING 列表切前 10 个 → `batch_assign_role` |
| "派一个兵侦查" | 数量=1 | 选 1 个 → `batch_assign_role([tag], SCOUTING)` |
| "分一队飞龙去…" | 按兵种的偏师 | 按 type_id 筛 → `batch_assign_role(tags, HARASSING)` |
| "把骚扰那队撤回来" | 解散偏师 | `switch_roles(HARASSING → ATTACKING)` 并回 |

**ares 接法**：
- 切分队：`mediator.batch_assign_role(tags, UnitRole.HARASSING)`（或 `BASE_DEFENDER` 等）。
  选 tags 按上面三轴挑：**数量**=列表切片 `tags[:N]`、**兵种**=`type_id` 筛、**位置**=`cy_closest_to`。
- 取分队：`mediator.get_units_from_role(role)`；空间分组用 `mediator.get_squads(role=, squad_radius=)`。
- 归队：`mediator.switch_roles(from_role, to_role)`。
- 现成角色枚举（`consts.py`）：`ATTACKING / ATTACKING_MAIN_SQUAD / HARASSING / DEFENDING /
  BASE_DEFENDER / BANE_FODDER …`（HARASSING 还有按兵种细分的 `HARASSING_MUTAS/REAPER/ORACLE…`）。

可见效果：军队当场**可见地分开**。

---

## 3. 维度二：「干什么」—— 六族战术杠杆

### ① 整体姿态（已有｜A、F）
- **指令**："出击 / 撤 / 守家 / 龟一会儿"
- **参数**：作用于哪个「谁」（默认全军）
- **可见**：**即时**，满屏部队转向
- **ares 接法**：本层给该组维护一个 stance 标志（沿用 Stage 2 的 `_commenced_attack` 思路）。
  - 出击 → 该组每帧跑"进攻 maneuver"（见 §3.2 的 target + 交战栈）
  - 撤 → `KeepGroupSafe` / `MoveToSafeTarget`（朝安全点撤，边撤边打）
  - 守家 → 移动目标设为我方基地，进攻触发关
  - 龟 → 不出击，原地（hold）

### ② 位置目标（已有｜A）
- **指令**："打他主基地 / 去二矿 / 压到中路"
- **参数**：目标点 `Point2` 或某基地
- **可见**：**即时**，部队改道
- **ares 接法**：override 该组的 `attack_target` 属性返回的 `Point2`；
  群体移动用 `PathGroupToTarget(grid, target)` 或 `AMoveGroup(target)`。
  基地坐标从 mediator 取：`get_enemy_nat / get_enemy_expansions / get_enemy_third`。

### ③ 焦点打击（新｜B）
- **指令**："集火那辆攻城车 / 专杀医疗船 / 先拆兵营 / 干掉最大的那个"
- **参数**：按 **type_id**（medivac/tank/worker）/ **具体单位** / "最大/最近的"
- **可见**：**即时**，火力收束到目标
- **ares 接法**：每帧在敌人里按 `type_id` filter 出焦点集合，给该组每个兵的交战 maneuver
  **最前面**插 `AttackTarget(unit, target)`（ares 现成 individual behavior，oops 反 Baneling 同款）。
  没有焦点目标在场时，回落到默认 `ShootTargetInRange`。
  "最大的"= 按身价/血量排序选目标（参考 oops `get_highest_value_target`）。

### ④ 机动意图（新｜C、G）—— 最有戏、最重
- **指令**："绕后 / 两边包抄 / 埋伏在坡道 / 占住高地 / 假装撤退引他追"
- **参数**：目标区域 + **意图**（意图决定怎么走/到了干嘛）
- **可见**：部队走**巧妙的路** / 蹲伏不动
- **ares 接法**（把"意图"翻译成 路径点 + 到点行为）：
  - **绕后/抄家**：目标点取敌方后方（`get_enemy_expansions` 里离敌军质心最远的，参考 QueenBot
    坑道选点），用 `PathGroupToTarget(grid, target)`——`get_ground_grid` 已含敌方威胁，**寻路自动绕开主力**。
  - **埋伏**：移动到指定点后 `hold` + 不主动开火（KeepUnitSafe / 关掉进攻触发），直到敌人进范围。
  - **占位**：移到坡道/高地点 `hold`（`mediator` 地形点 + `MoveToSafeTarget`）。
  - **假撤诱敌**：先 `MoveToSafeTarget` 后撤，敌人追入后翻 stance 回 ① 出击（可配合 ⑥ 择时）。
  > 注：意图→走位的映射是本族主要工作量，先做"绕后/埋伏/占位"三个，其余后置。

### ⑤ 持续模式（新｜E）
- **指令**："去骚扰他农民、别停 / 巡逻这条线 / 留一队断后"
- **参数**：作用的「谁」+ 目标区域，**一直跑到取消**
- **可见**：那队兵**反复 hit-and-run**，自跑循环
- **ares 接法**：与瞬时令的本质区别——这是个**持续状态**。给该组打 `HARASSING` 角色 + 本层每帧跑
  一个"骚扰 maneuver 循环"：`AttackTarget(最近经济单位)` → 受威胁则 `KeepUnitSafe`/`WorkerKiteBack`
  撤 → 安全后再进。模式标志保持，直到用户取消（`switch_roles` 归队）。结构同 oops 的 squad FSM。

### ⑥ 择时触发（新｜H｜可后置第二轮）
- **指令**："趁他兵出去了打 / 等我升级好再上 / 他一过坡道就发动埋伏"
- **参数**：**条件 + 动作**
- **可见**：触发前无动静，条件满足即发
- **ares 接法**：本层维护一个 watcher，每帧读 mediator 信号（`get_main_ground_threats_near_townhall`、
  敌军位置、`already_pending_upgrade` 等）判断条件，满足则翻对应组的 stance/maneuver。
  较复杂（要持续盯条件），放第二轮。

### ⑦ 侦察（新｜实用任务，非爽感原型但高频）
- **指令**："派个兵去侦查 / 看看他在干嘛 / 他家里有啥"
- **参数**：选 N 个单位（通常 1，数量轴）+ 去哪看（敌方主基 / 某分矿 / 未知区，参谋长补全）
- **可见**：一个兵脱队跑去敌方，**参谋长读 state 把看到的报回来**（"他开了三矿、在憋空军"）——
  "汇报"本就是参谋长的活，侦察族负责"派出去 + 活着看"
- **ares 接法**：`batch_assign_role([tag], SCOUTING)` + 一个侦察循环（去侦察点 → `KeepUnitSafe` 保命
  → `PathUnitToTarget`），仿 QueenBot `ScoutManager`（~248 行）。**ares 无 turnkey，需自写**，范本现成。
- 注：它本身不"爽"，但前面 11 类指令里"侦察"很常见，且**阶段 3（决策点）的情报全靠它喂**——属基础设施。
- 高度线：派 1 个兵给"侦察任务" ✅（任务级）；"让这个兵走到 37,42" ❌（逐兵微操）。二者别混。

---

## 4. 后台：运营杠杆 —— 降级成"基本自动"

兵种 / 生产 / 扩张 / 升级 / 开局，**不进前台命令面**：
- 默认按 `experience-spec` 阶段 1 选的**打法流派自动跑**（build runner 的 opening +
  `SpawnController`/`ProductionController` 的 army_comp + `ExpansionController`/`UpgradeController`）。
- 只在**真战略岔路**由参谋长**主动问一句**（"要不要转空军？"），用户答了才翻背景杠杆
  （改 army_composition_dict / `switch_opening`）。

→ 对 Stage 2 最核心的纠正：把"填表格"从用户面前撤走，注意力全留给前台战术。
（运营杠杆的具体签名见本仓库 git 历史里旧文档的核实结果，或直接看
`ares-sc2/src/ares/behaviors/macro/`：`SpawnController/ProductionController/ExpansionController/
UpgradeController/GasBuildingController`，均 `@dataclass` + `register_behavior`。）

---

## 5. 实现模型：每组一份命令 + 每帧 seam 执行

```
本层状态（粘性，改了才变）：
  orders = {
    "ATTACKING":      {stance:"出击", target:"enemy_main", focus:null,    maneuver:null,  mode:null},
    "HARASSING":      {stance:null,   target:null,         focus:"worker", maneuver:null,  mode:"骚扰"},
  }

每帧 seam（main.py 里）：
  for role, order in orders.items():
      units = mediator.get_units_from_role(role)
      maneuver = build_maneuver(order, units)   # 按 order 把对应 ares 行为按优先级叠进 CombatManeuver
      for u in units: register_behavior(maneuver_for(u))
```

`build_maneuver` 的优先级栈（沿用 ares 范式，参考 random-example/oops）：
```
KeepUnitSafe(避伤)  →  [focus] AttackTarget  →  ShootTargetInRange  →
[maneuver/mode 的特定行为]  →  [stance] 撤/守/出击的移动  →  AMove 兜底
```
**seam 仍是"零决策"**：它只把 order 翻译成行为栈，不判断"该不该撤"——那是参谋长（慢）或
反射地板（快，保命）的事。orders 谁来写见 `experience-spec` 的四阶段。

---

## 6. 高度纪律（不可破）

六族全部是**"战术意图"**，没有一条下沉到逐兵操作：
- "绕后抄家" = 一个意图，bot 自己选路走位（`PathGroupToTarget`）。
- "集火攻城车" = focus 某类目标（`AttackTarget` + type filter），不是"3 号兵打 7 号兵"。
- 逐兵微操永远在 ares/behavior 层，不暴露给参谋长。LLM 驱动逐兵（LLM-PySC2）是验证过的死路。

---

## 7. 可行性总表（杠杆 × ares 机制 × 状态）

| 族 | 爽感 | ares 机制 | 状态 |
|---|---|---|---|
| 分队（谁） | D、E | `batch_assign_role` / `get_units_from_role` / `get_squads` / `switch_roles` | ✅ 已核实 |
| ① 姿态 | A、F | stance 标志 + `KeepGroupSafe`/`MoveToSafeTarget` | ✅ Stage 2 已验证基本款 |
| ② 目标 | A | override `attack_target` + `PathGroupToTarget`/`AMoveGroup` | ✅ Stage 2 已验证 |
| ③ 焦点 | B | type filter + `AttackTarget`（个体 behavior） | ✅ 类已存在（oops 用） |
| ④ 机动 | C、G | `PathGroupToTarget`(grid 含威胁) + hold + mediator 地形/分矿点 | ⚠️ 意图→走位需自实现 |
| ⑤ 模式 | E | `HARASSING` 角色 + 每帧骚扰 maneuver 循环 | ⚠️ 循环需自实现（仿 oops FSM） |
| ⑥ 择时 | H | 本层 watcher 读 mediator 信号翻 stance | ⚠️ 后置第二轮 |
| ⑦ 侦察 | （实用） | `SCOUTING` 角色 + 侦察循环，仿 QueenBot `ScoutManager` | ⚠️ 自写，范本现成 |

数量/兵种/位置三轴的「谁」选择：纯 tag 列表切片/筛选，机制零难度，✅。

✅ = ares 现成/已验证；⚠️ = ares 有底座、上层逻辑要自己写。

---

## 8. 建议的落地优先级（供取舍）

1. **先做「分队」（含数量轴）+ ①②③ + ⑦侦察**：分队是新表达力的地基；①②是 Stage 2 已通的、
   ③（焦点）便宜又立刻提升"打得聪明"；⑦侦察虽不爽但**给决策点喂情报、是基础设施**，要早。
   这一档做完，`分队 × 姿态/目标/焦点 + 侦察` 就已远比 Stage 2 好玩、且参谋长有眼睛了。
2. **再做 ⑤ 持续模式（骚扰）**：E 是最独特的爽点之一，且有 oops FSM 可仿。
3. **再做 ④ 机动**（绕后/埋伏/占位三个意图先行）：最有戏但最重。
4. **⑥ 择时**：第二轮。

> 注：本表只排杠杆层；它要跑起来还依赖 `experience-spec` 的参谋长（写 orders 的人）和后台运营自动化。
> 三者的总装顺序另议。

---

## 9. 素材库萃取带来的修正（2026-06-29，依据 `ares-corpus-harvest.md`，16 个 bot 压测）

7 族 + 分队语法整体被验证**够用**（骚扰/侦察/绕后/诱敌/巡逻/分兵/焦点/姿态全可表达）。需打的补丁：

1. **②位置目标 = 语义目标，不是坐标**：收"敌主矿 / 后院 / 绕开敌军 / 某高地"这类语义，由底层求解具体
   `Point2`（人类司令没法点坐标）。参考 kitten `attack_target` 决策树、12Pool runby 选点。
2. **④机动加"动词/子类型"参数**：行军 / 绕后 / 空投(含**装载**前置) / 隧道 / 埋伏 / 占位 / 诱敌 /
   **阵型铺开(避溅射)**。线性进退不够（毒爆散开、空投装载都表达不了）。诱敌范本=anglerbot 三段式。
3. **⑥择时加"事件谓词"+"停止条件"**（不止时间/兵力）：
   - 事件谓词：接敌 / 挨打(盾掉) / 被绕后 / 敌近某点（anglerbot 的精华切换全是事件式）
   - 停止条件：如"打到主矿+分矿全拆才收手"（BruceBot `ArmyAttack`）
   - 殊死条件：家没了→all-in（hydras/banes）
4. **分队加"临时征用 worker 入队"**：不止已有军队，可从采矿队偷单位改角色（Aristaeus cannon 偷 probe）。
   分队仍 **role-based 持久**（`get_squads`+UnitRole），绝不靠 proximity 自动聚类（kitten 偏师会自己跑回主力）。
5. **加一条正交"技能/增益"轴**（与 7 族正交，可选）：stim / 狂热 / 亚马托 / 揭示——不改姿态、额外叠加。
6. **"建筑骚扰/打法"(cannon rush) 不进战斗族**：升格为 **①姿态/打法开关**，整套自动选址后台跑，
   司令只下"开/关 X 打法"（Aristaeus `CannonRushManager` 就是独立 manager，不散在 micro）。
7. **科技 gating 顺序写进"流派卡片"**：否则"司令喊爆刺蛇但没造 den"死局——属后台运营层但必须声明。

> 落地架构（五模块=ares Manager、注册顺序=优先级、流派=3旋钮、底座 fork ares-random-example）
> 见 `ares-corpus-harvest.md` 第四节。
</content>
