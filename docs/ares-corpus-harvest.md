# ares 素材库萃取汇总 — 16 个 bot 的战术目录 / 模式库 / 证伪

> 目的：从 12 个开源 ares bot（+深读过的 QueenBot/oops/random-example）萃取三样东西，
> 喂给我们的代码：① 战术目录（验证 7 族杠杆够不够 + 攒"打法流派"内容）② 模式库（每样要写的东西取最干净范本）③ 证伪（野外有没有 7 族表达不了的战术）。
> 配套：`lever-layer-design.md`（杠杆层）、`experience-spec.md`（体验）。素材在 `scratchpad/ares-refs/`。

萃取的 bot：12PoolBot / Nani-Z / anglerbot / kitten / ravagers / hydras / banes / BruceBot / CustomMgr / qin / Aristaeus / DoopyBot（+ QueenBot / oops / random-example 已有独立导读）。

---

## 一、战术目录（三族通吃，= 打法流派候选 + 杠杆覆盖验证）

| 战术 | 范本 bot | 对应杠杆 |
|---|---|---|
| 正面平推（A-move 一坨） | kitten / ravagers / hydras | ①姿态 + ②目标 |
| 集火脆皮（health+shield 排序） | BruceBot / oops / anglerbot | ③焦点 |
| 风筝 kite（打了退） | ravagers / anglerbot / BruceBot / oops | ④机动(进退) |
| AOE 技能（腐蚀胆汁砸团） | ravagers | ③焦点群体版 / 技能轴 |
| 绕后偷家 runby | 12PoolBot | ④机动(绕后) |
| 空投骚扰 drop | 12PoolBot(OverlordDrop) | ④机动(空投) + 分队 |
| hit-and-run 骚扰 | Nani-Z / Aristaeus(Oracle) | ⑤持续模式 |
| 诱敌 bait（鱼饵+反打） | **anglerbot** | ④机动(诱敌)/G |
| 多路分兵牵制 | Nani-Z(3路) | 分队 |
| 巡逻织线 | BruceBot(BC patrol) | ⑤持续模式 |
| 侦察轮巡 | kitten / anglerbot / Aristaeus | ⑦侦察 |
| timing 一波 | BruceBot(BC) / 12PoolBot(ling) | ⑥择时 |
| 殊死冲脸（家没了 all-in） | hydras / banes | ⑥择时(殊死条件) |
| 建筑骚扰/偷布防 cannon rush | Aristaeus | **①姿态/打法开关**（非战斗族，见证伪） |
| 静态防御几何 | BruceBot(picket/tank) | 后台/守家 |
| 自爆散开避溅射 | banes(缺失!) | ④机动**缺"阵型/铺开"子语义** |

### 打法流派候选（按种族，goal 1 战术多样的内容来源）
- **Zerg**：速 ling rush(12Pool) / ravager AOE 压制 / hydra DPS / bane 自爆 / 多路骚扰(Nani-Z) / 纯女王运营(QueenBot) / nydus 背刺(QueenBot)
- **Terran**：bio 兵海(kitten) / 战列舰 timing 一波(BruceBot)
- **Protoss**：cannon rush + Tempest 空暴 + Oracle 骚扰(Aristaeus) / 诱敌 kite(anglerbot)

→ 三族都有 ≥2 个成型流派可做，goal 1 内容充足。

---

## 二、模式库（每样要写的东西，取最干净范本 + file 出处）

### 架构骨架（最该抄）
- **`register_managers() + Hub + ManagerMediator`**：Aristaeus `main.py:40-65`、CustomMgr `main.py:24-44`。
  五模块各做成一个 Manager；**注册顺序 = 优先级链**（CustomMgr 证实）。
- **Manager 最小骨架**：`(ai, config, mediator)` + `async update(iteration)`（CustomMgr `worker_rush_manager.py:10-43`）。
- **自定义 manager 跑在 ares manager 之后** → 直接消费 ares 算好的 squad/敌情/经济，不重算。
- **手动驱动口子**：production_manager 不进 Hub、在 on_step 手动 await（Aristaeus `main.py:51-52`）——给"条件门控的 manager"留口（参谋长的间接指令正是这种门控）。

### 分队（谁）
- **正解**：`get_squads(role, squad_radius)` + squad 内按 `ground_range` 拆远/近战（anglerbot `main.py:264,289-291`）；`get_units_from_role(role, unit_type)`（Aristaeus `oracle_manager.py:111`）。
- **三轴选择**：数量=tag 列表切片、兵种=type_id 筛、位置=`cy_closest_to`。
- **临时征用 worker 入队**：从 GATHERING 偷 probe 改角色 + remove_worker_from_mineral（Aristaeus `cannon_rush_manager.py:464-477`）。
- **反面教训**：别用 enumerate 下标硬切（Nani-Z）；别靠 proximity 自动聚类（kitten 偏师会自己 merge 回主力）——**必须 role-based 持久指派**。

### 干什么（7 族落地）
- **combat class 模式**：每族 = 一个 `BaseUnit` Protocol 实现 `execute(units, **kwargs)`，Manager 选队传参、micro 内聚（Aristaeus `combat/base_unit.py:11-42`）。
- **或 per-unit 行为链**：`get_units_in_range(as_dict)` 感知 → 每兵 `CombatManeuver().add(...)` 按优先级（ravagers `main.py:56-89`）。我们 `[谁]×[干什么]` 几乎一对一编译到这个结构。
- **①姿态**：stance flag → 进攻 maneuver vs `KeepGroupSafe`/`MoveToSafeTarget` 撤。
- **②目标**：attack_target 决策树（kitten `unit_squads.py:358-400`）当默认；`center_mass`/KDTree（kitten `main.py:155-192`）。
- **③焦点**：type filter + `AttackTarget`；脆皮排序 health+shield（BruceBot `StandardRush.py:48`）；`cy_pick_enemy_target`。
- **④机动**：`PathGroupToTarget(grid)` 自动避威胁；绕后选点（12Pool runby / QueenBot nydus 选离敌最远基地）；诱敌三段式（anglerbot，见下）；空投状态机（12Pool `overlord_drop.py:25-106`）。
- **⑤持续模式**：hit-and-run 分支（Nani-Z `main.py:165-183`）；巡逻航线生成（BruceBot `BattleCruiserPatrol.py:51-90`）；按威胁自动切骚扰↔侦察（Aristaeus `oracle_manager.py:98-141`）。
- **⑥择时**：事件触发（anglerbot 盾掉血/敌上高地 `main.py:213-259`）；config 闸门 `AutoArmyAtTime`/`AttackAtSupply`（BruceBot）；有状态停止条件（BruceBot `ArmyAttack.py:25-40` 主矿+分矿全拆才收手）。
- **⑦侦察**：`cycle(expansions)` 轮巡 + is_visible 跳过（kitten `map_scouter.py`）；侦察完 `switch_roles` 归队（anglerbot `main.py:412`）。

### ★ 诱敌三段式（④/G 唯一成型范本，anglerbot）
鱼饵近战 `hold` 在视野遮挡埋伏点 + 远程主力后置待命 + **"鱼饵护盾挨打"作接战触发** → 全军反打。
三段直接映射杠杆：[鱼饵分队]×④埋伏 + [主力分队]×①待命 + ⑥事件触发(鱼饵挨打)。

### 状态导出（喂 LLM）
- **黄金范本 = kitten `squad_agent/features.py` 的 AlphaStar 三层**：
  - 实体列表（每单位类型/血盾能/坐标/武器CD/buff）
  - 全局标量（建筑数/主力位置/attack_target/rally）
  - 空间多通道（威胁/地形/视野 grid → 文本化降成"哪块区域有威胁"）
  - ⚠️ 注意 kitten 的 `state.py` 只是缓存，**别被名字骗**，要看 features.py。
- **决策数据结构**：12Pool 的 `StrategyDecision` frozen dataclass（`strategy.py:14-21`）——决策出不可变意图、下游翻译，正是 seam 范式。

### 后台运营（打法流派 = 3 旋钮）
- **①开局 yml + ②SpawnController 的 army_composition_dict + ③战斗加哪些 behavior**（ravager 三连证实：三个 bot 本质只差这三处）。
- `MacroPlan` 串 `AutoSupply`/`SpawnController`/`ProductionController`/`ExpansionController`/`UpgradeController`（Aristaeus/kitten/QueenBot）。
- `BuildSelection: WinrateBased` + `Cycle` 败后自动换招（qin / 三连）。

### seam 范式
- **决策/执行分离**：出不可变意图 → 下游翻译落地（12Pool `StrategyDecision`）。
- **dispatch 表**：int → 动作表 → (ability,target,参数) → 执行（kitten `consts.py:69-76` + `unit_squads.py:66-92`），跟"LLM 出指令 → 杠杆翻译 → 执行"同构。
- **DSL**：ares build DSL `[供给/触发][动作][@目标]`（qin）跟我们 `[谁]×[干什么]` 同构，可让 LLM 直接吐短语、seam 解析。

### 小技巧（白送）
- idle 过滤再下令防抖动（banes `main.py:41`）；morph 造兵替代失效的 train（banes）；`in unit.abilities` 判技能可用（hydras）；用 ai 对象当黑板存 per-tag 状态（BruceBot）；多余建筑建到 90% Cancel 退钱（Aristaeus）。

---

## 三、证伪 + 设计修正（语法被 16 个 bot 压测后的结论）

### 确认能表达（语法够用）
骚扰 / 侦察 / 绕后 / 诱敌 / 巡逻 / 分兵 / 焦点 / 姿态 / Oracle 双模(⑤+触发) / Revelation(⑦) —— 全在 7 族 + 分队语法内。

### 需要修正（已纳入 `lever-layer-design.md`）
1. **②位置目标 = 语义目标**（敌主矿/后院/绕开敌军），底层求解点，不让司令点坐标。
2. **④机动加"动词/子类型"参数**：行军 / 绕后 / 空投(含装载前置) / 隧道 / 埋伏 / 占位 / 诱敌 / **阵型铺开(避溅射)**。线性进退不够。
3. **⑥择时加"事件谓词" + "停止条件"**：不止时间/兵力。事件=接敌/挨打(盾掉)/被绕后/敌近某点；停止条件="打到主矿+分矿全拆才收手"；殊死="家没了→all-in"。
4. **分队加"临时征用 worker 入队"**：不止已有军队（cannon rush 偷 probe）。
5. **加一条正交"技能/增益"轴**（可选）：stim/狂热/亚马托/揭示 —— 不改姿态、额外叠加。揭示/亚马托可塞③⑦，stim/frenzy 是 buff，单列一条轻量轴更干净。
6. **"建筑骚扰/打法"(cannon rush)不进战斗族**，升格为 **①姿态/打法开关** 由后台 manager 自动跑（整套自动选址，司令只下"开/关 X 打法"）。
7. **科技 gating 顺序写进流派卡片**：否则"司令喊爆刺蛇但没造 den"死局。

### 分层再确认
7 族 = 战术指令（军队级）；流派/科技/造兵厂地理/timing 的"何时" = 后台运营层。两层不混（12Pool 的 Strategy 组件独立于 Micro 组件就是证明）。

---

## 四、底座选择 + 落地架构（据此动工）

**底座 fork**：必须**真 ares 范式**（像 ravagers/Aristaeus），不裸手写（hydras/banes 反面：战斗智能 0 + bug），不空壳（DoopyBot 反面：ares 不白送）。
→ **fork `ares-random-example`**（种族无关、342 行干净基准、自带 SpawnController + CombatManeuver），嫁接 Aristaeus 的 `register_managers()+Hub` 骨架。

**五模块 = ares Manager**（注册顺序即优先级）：
```
register_managers():
  ManagerMediator()
  StateExportManager   # 读ares成品状态 → AlphaStar三层 → json给LLM (仿kitten features.py)
  SeamManager          # 读orders → 每个"谁"跑对应族的combat class behaviors
  ReflexManager        # 注册在Seam之后 → 同帧覆盖seam (保命优先, 天然实现"地板压过指挥官")
  Hub(additional_managers=[...]); init_managers()
```
- **vocab.py / orders.py** = 纯数据（DSL 枚举 + 每组粘性命令），LLM 写、Seam 读，经 mediator 传。
- **干什么 7 族** = 每族一个 `BaseUnit` Protocol 实现（combat class），Seam 选队传参。
- **打法流派** = 数据化 3 旋钮（build yml + comp dict + behavior set），可 WinrateBased 自学。

---

## 五、建议的第一里程碑（最小可玩、且明显比 Stage 2 好玩）

**做通 `分队 + ①②③ + ⑦侦察 + state导出 + 1个流派`，Claude 在对话里当参谋长试玩一局。**
- 分队（三轴选择，role-based 持久）
- ①姿态 / ②语义目标 / ③焦点打击（便宜且立刻"打得聪明"）
- ⑦侦察（给参谋长眼睛、喂决策点情报）
- StateExportManager（AlphaStar 三层喂 LLM）
- 1 套流派（建议 Zerg ravager 压制 或 Terran bio，范本最全）
- 验"比 Stage 2 好玩" → 再迭代 ⑤骚扰 / ④机动 / ⑥择时。
</content>
