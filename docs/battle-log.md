# 战斗日志（司令观察记录）

> 司令观战中发现的问题统一记这里，**游戏结束后统一优化**，不在局中改代码。
> 每条记录：现象 → 影响 → 初步根因猜测 → 状态。

## 2026-07-21 carrier @AbyssalReefLE vs Zerg Medium/Macro（进行中）

### O1 前期农民干等钱造建筑，浪费采矿时间

- **现象**：前期 2 个农民不采矿，干等钱造 Gateway 和 Forge。
- **影响**：开局经济直接亏几十个矿，航母流又是经济敏感流。
- **实证根因**（2026-07-21 修复，部分改正原猜测）：
  - **Forge（主因）**：走的是 `UpgradeController → TechUp → BuildStructure` 路径，
    全程**没有 can_afford 检查**（B1 守卫只加了 production_manager 自己的
    `_build_core_structure`）。第一个 pylon 一就绪 TechUp 就派农民去造 Forge，
    农民到位后 ares `BuildingManager` 只在 `can_afford` 时才下 build 命令
    （building_manager.py:386-391），钱不够就原地干等。
  - **每帧刷日志之谜**： TechUp 的 `logger.info("Building FORGE ...")` 打在
    BuildStructure 调用**之前**且无任何节流；开局没 pylon 时 powered placement
    求不到 → 每帧日志+失败重试，pylon 好后变成日志+成功派工。刷屏 ≠ 多派工人。
  - **次要因素**：`_handle_idle_workers` 不清除 building_tracker 里的工人，
    把干等中的 BUILDING 农民抓回采矿，BuildingManager 下一帧又拉回建造点，
    两边对抢（ping-pong），放大浪费。
  - Gateway 侧基本无此问题（`_build_core_structure` 有守卫），只有
    「派出后钱被别的开销花掉」的短窗口残留，可接受。
- **修复**（全在 bot 层，未动 ares）：
  - `bot/production_plans.py` 新增 `upgrade_tech_buildings()`（升级→研究建筑映射）；
  - `production_manager.update`：前置建筑改由带守卫的 `_build_core_structure` 补建，
    `UpgradeController` 改 `auto_tech_up_enabled=False`（只研究不补建）→ 日志刷屏同消；
  - `_handle_idle_workers` 跳过 building_tracker 里的工人（消除对抢）。
- **状态**：✅ 已修复并已验证（2026-07-21 验证局，见文末）。

### O2 司令接管被 bot 指令冲突顶掉，救不回来

- **现象**：一个农民被 bot 下令建造（如熔炉）后，司令手动控制也救不回来；
  bot 持续发出更多鼠标键盘指令，与司令的指示冲突。
- **影响**：司令零 APM 原则被破坏，关键时刻无法人工纠错。
- **实证根因**（2026-07-21 修复）：接管机制（`_handle_player_control` →
  PERSISTENT_BUILDER role + `_player_ctrl` 计时）本身工作正常，且 role 方案对
  **Mining / BuildStructure 选工 / _handle_idle_workers / combat** 都天然生效
  （它们都按 role 选单位）。**唯一破洞是 ares `BuildingManager._handle_construction_orders`**：
  它按 building_tracker 记账、**无视 role**，每帧给 tracker 里的工人下
  move/build 命令——司令把农民挪去 PERSISTENT_BUILDER 也没用，下一帧又被拉回建造点。
  这正是"救不回来"的对抢来源。
- **修复**：`bot/main.py` 新增 `release_from_build_tracker()`（从 tracker 摘除 +
  维护 building_counter，镜像 ares `remove_unit` 但不动 role），接管瞬间调用。
  摘除后生产侧下帧自动换别的矿工重派同一建筑；接管超时归还时若原 role 是 BUILDING，
  ares 的"BUILDING 但不在 tracker"清理会自动把它归回 GATHERING。3 秒让权窗口
  （有新操作自动续期）的设计不变。
- **状态**：✅ 已修复（机制验证见文末验证局）。

### O3 农民建完建筑后原地傻等，不回去采矿

- **现象**：农民建造完成后傻傻待在原地，不自动回矿。
- **影响**：每建一个建筑亏一个农民的采矿时间，积少成多。
- **实证根因**（2026-07-21，**改正原猜测**）：role 归位其实**没问题**——ares 对神族
  在建筑**放下瞬间**（progress ≥ 1e-16）就把工人从 tracker 移除并归 GATHERING，
  BuildingManager.update 还会把"BUILDING 但不在 tracker"的工人立即归队。真正机制：
  ① 大头与 O1 同账——干等+ping-pong 的工人都算 idle；② 残留小头：矿线饱和时
  ares Mining 的长距离采矿找不到"无人矿脉"，freed 建造农民拿不到命令，只能靠
  `_handle_idle_workers` 兜底，而旧间隔 2 秒 → 每个建筑完工后最多傻站 2 秒。
- **修复**：清扫间隔 2.0 → 1.0 游戏秒（O1 修复消除干等后，这就是残余 idle 的上界）。
- **状态**：✅ 已修复并已验证（2026-07-21 验证局，见文末）。317 秒 idle worker time 的大头在 O1。

---

## 2026-07-21 carrier @BelShirVestigeLE vs Zerg Harder/Macro（验证局，进行中）

### O4 侦查农民发现 rush 后应立刻回家

- **现象**：侦查农民已看到虫族 rush 迹象（血池 + 虫卵变小狗），还留在敌家，
  白送一个人口（农民）。
- **影响**：航母流每个农民都是经济；rush 局里送农民 = 雪上加霜。
- **实证根因**（2026-07-21 修复，与原猜测一致）：scout 是一次性指令（探完才回家），
  没有「发现 rush 征兆 → 提前撤退」分支；pivot 的 `_update_rush_state` 只喂
  生产/守家，和侦查单位无联动。
- **修复**（复用现有 rush 信号，不新造判据）：
  - `bot/main.py` 新增 `recall_scouting_workers()`：把全部 SCOUTING role 农民
    归 GATHERING 并派回最近矿脉（steer scout 和 pivot 早侦查都是 SCOUTING role，
    一处全覆盖）；
  - `on_step` 在 production update 后检查 `production_manager.rush_active`（新增
    property，combat 守家读的同一个 `_rush_active`）→ 成立即撤回，事件只记一次；
  - steer scout 的 `_scout_tag` 一并清空、`_scout_done` 置 True，撤回后不会被
    `_handle_scout` 再派出去，也不补派新农民。
  - 注意：rush 判据之一是「4 分钟前敌可见兵力 ≥6」，侦查农民提供的视野本身就会
    喂给这个判据 —— 看到小狗群即触发撤回，符合预期。
- **状态**：已修复（未跑局验证）。

### O5 carrier 流编队滑向纯风暴，航母主 C 没打出来

- **现象**：carrier 流实战只出 1 艘航母、一堆风暴；中前期有优势时还在造风暴。
- **影响**：流派效果（航母黄金舰队）没打出来，实际打的是 tempest 流换皮。
- **实证根因**（读码确认，2026-07-21）：配方 `CARRIER 0.7 p0 / TEMPEST 0.3 p1` +
  `freeflow: true`。freeflow 下 ares SpawnController **忽略配比只按优先序**
  （spawn_controller.py:46），每帧轮询：航母买不起 → `continue` 落到风暴
  （:168-173）→ 风暴 175 气永远可负担，气一够就被吃掉，永远攒不到航母的 250 气。
  C5a 教训的镜像：次优先兵种永远可负担 → 饿死主 C。**没有任何憋气等航母的机制。**
- **修法选项**：
  - (a) 纯航母化：carrier 流 spawn 只留 `CARRIER: 1.0`（像 tempest 流一样单兵种，
    走 over_produce 豁免连 freeflow 都不用）——最简单，彻底解决问题；
  - (b) 保留风暴副 C + 憋气机制：p0 买不起时不 fall-through 到 p1（或加
    「气距 250 还差 X 以内就攒着」的保留逻辑）——复杂，要动 spawn 机制。
- **司令拍板**：方案 (b)（2026-07-21）。
- **实现**（bot 层，不动 ares）：
  - `bot/production_plans.py` 新增纯函数 `save_up_spawn()`：spawn dict 喂
    SpawnController 前按局势动态裁剪——p0 = 可造（`tech_ready_for_unit`）的最高
    优先兵种；**p0 占比 ≥ 配比 → 摘掉 p0 让 p1 补位**（副 C 语义保留，摘掉后
    无可造兵种则原样返回防 C5a 停产）；**p0 占比落后 → p0 买得起或气缺口 ≤
    阈值时只留 p0**（截断 p1 的 fall-through，攒气）；缺口还很大 → 原样返回。
  - 阈值走 `flows.yml` 新字段 `save_up`（气缺口，缺省 0=关），carrier 块配
    `save_up: 250`（= 航母气价，语义"占比落后就全力攒"；调小则允许差得远时
    先出风暴顶着）。
  - `production_manager._apply_save_up()` 在 `_effective_spawn` 正常路径出口
    统一应用（rush 单兵种分支不受影响；anti-air 分支也过一遍）。
  - 机制通用：按 priority 排序处理任意多兵种，key 无关；单兵种配方直接 no-op。
- **状态**：已修复（待跑局验证）。

### E1 对局实验：carrier 遇 rush，叉子顶 vs 塔防憋航母，哪个最优？
- **司令问题**：侦查确认 rush 流后，(a) 出叉子顶前方战场，还是 (b) 防御塔顶一波
  然后直接憋航母平推？哪个是最优？
- **现状**：pivot 的 rush 响应是**组合包**（`rush_zealots: 4` 叉子 + 铺塔 + 守家联动），
  两个单一臂都没单独验证过。
- **实验设计**（vs Zerg/Rush，同图同档，每臂 N=3 起步）：
  - 臂 A（对照）：现有组合包（4 叉 + 塔 + 守家）
  - 臂 B：纯叉子顶（rush_zealots 保留，关铺塔——需加一个 pivot 开关）
  - 臂 C：纯塔憋航母（rush_zealots: 0，只铺塔 + 守家，航母节奏不变）
- **换臂步骤**（2026-07-21 已实现，只改 `ares-bot/flows.yml` 的 `carrier.pivot` 块，
  无需动代码，改完按正常流程起局）：
  - 臂 A（默认，无需改）：`rush_zealots: 4`，不写 `rush_cannons`（缺省 true）。
  - 臂 B：carrier.pivot 加一行 `rush_cannons: false` —— rush 预警不再提前铺塔
    （`defend=yes` 手动铺塔、6 分钟自动铺不受影响）；`rush_zealots: 4` 保留。
  - 臂 C：carrier.pivot 改 `rush_zealots: 0`（rush 时不出叉子；`_effective_spawn`
    的叉子覆盖分支对 0 是 falsy 跳过，已确认），`rush_cannons` 保持缺省 true。
  - 三臂的守家联动（combat 读 `rush_active`）与 rush 检测判据不变。
  - ⚠️ tempest/stalker 块有 shipped 测试冻结，实验只在 carrier 块上做。
- **判据**：胜率优先；其次看航母成型时间是否被拖慢、农民损失数。
- **实验结果**（2026-07-21 跑完，VeryHard/Rush @AbyssalReefLE，每臂 N=3，
  runner=`ares-bot/e1_matrix.py`，数据 `bench/e1-carrier-vh-zerg-rush-arm*/summary.json`）：

| 臂 | 战绩 | 平均时长 | 复盘问题 | 终局编成(均值) |
|---|---|---|---|---|
| A 组合包(4叉+塔) | **3-0** | 630s | one_base×3 | CARRIER×5.0 + TEMPEST×2.0 + 拦截机×22 |
| B 纯叉子(无塔) | 0-3 | 249s | overrun×3（全部被打穿） | （没撑到成型） |
| C 纯塔憋航母(无叉) | 0-3 | 200s | overrun×2 clean×1 | （没撑到成型） |

- **结论**：**两个单臂都站不住，组合包就是最优解**。纯叉子没有锚点，叉子被小狗
  数量磨死后直接穿家；纯塔没有机动兵力，塔未成阵前农民/塔位被穿。叉子买时间 +
  塔做锚点缺一不可——维持现状（rush_zealots: 4 + rush_cannons: true）。
- **顺带验证 O5**：臂 A 终局 CARRIER×5.0 / TEMPEST×2.0 = **71%/29%**，精确收敛到
  设计的 7:3（对照 O5 修复前「1 航母 N 风暴」）；CARRIER@387s 成型。
- **暴露的新问题**：臂 A 三局全部 one_base（单矿打到底）——天空流 auto_expand
  默认关是「已验证单矿打法」的刻意选择，但 vs Rush 赢后可以考虑开二矿滚雪球，
  列入后续候选。
- **状态**：✅ 已跑完，结论落定。

### E2 carrier 动态多矿 + 分矿塔防估算 + 气/航母平衡（臂 A 改造）

- **需求**（司令 2026-07-21，E1 结论的后续）：E1 证明臂 A 最优但三局全单矿。
  要求：① 有能力就开到 4 矿（不设死 2 矿）；② 农民爆仓或前线优势就开矿；
  ③ 分矿塔数按敌兵力估算（保守 3~封顶 8）；④ 开矿与产航母不矛盾（矿多→气多→
  星门多，bot 自己找平衡）。
- **实现**（2026-07-21，全在 bot 层 + flows.yml carrier 块，冻结块未动）：
  - **动态开矿**：`auto_expand: {max_bases: 4, when_workers: 22, advantage_supply: 12}`；
    `_auto_expand` 配了 `max_bases` 走动态路径——爆仓（农民 ≥ 22×基地数）或
    优势（我方 army supply ≥ 敌可见 + 12）→ `ExpansionController(to_count=当前+1,
    max_pending=1)` 逐矿评估；rush_active 期间不开。判定纯函数
    `production_plans.should_expand_dynamic`。
  - **分矿塔数动态**：`expansion_cannons: {min: 3, max: 8}`；`ProtossStaticDefence`
    每帧重注册，`photon_cannons_per_base = clamp(3, 3 + 敌可见作战单位//4, 8)`
    （`production_plans.expansion_cannon_count`；敌兵力口径与 rush 判据同源，
    排除农民/建筑）。护盾电池仍 1/矿。
  - **气/航母平衡**：`_build_extra_production` 星门目标数 = min(cap, 满采气基地数 + 1)（司令修正：气有存款积累可爆兵、风暴耗气更慢，产能可略超稳态气收入；单矿双气→2 星门，双矿四气→3 星门）
    （满采 = 该基地 2 个 ready assimilator；`production_plans.gas_gated_stargate_target`）
    ——单矿只养得起 1 星门，cap 6 不再虚挂；气体不够时存款走 `_spend_bank`/动态开矿。
  - **新矿 assimilator 补齐**：走**现有** `_build_gas` 路径（`_build_flow_structures`
    里 `max_gas_buildings = 2×就绪基地数` + can_afford 守卫 + 选任意基地 12 格内
    空气矿），新基地就绪后自动补双气，无需新代码（查了 ares `GasBuildingController`
    但现有 bot 层逻辑已等价且带守卫，不重复造）。
- **验证设计**（待司令跑 bench，沿用 e1_matrix.py 模式）：
  ① carrier vs Zerg VeryHard/Rush N=3 —— 臂 A 语义不回归 + 终局基地数 >1；
  ② carrier vs Zerg VeryHard/Macro N=3 —— 看是否开到 3~4 矿、塔数在 3~8 区间、
  航母数随气增加。
- **风险**：优势判据可能被敌藏兵误导（默认 12 偏保守 + rush 不开缓解）；
  8 塔=1200 矿只在敌兵真多时爬到。分矿农民转运不在本期。
- **状态**：已实现（单测 121 例全绿 + carrier/tempest 编译过），**待 bench 验证**。

---

## 优化 backlog（打完统一处理）

- [x] O1 建造排队不派活干等（钱不够不钉工人）— 2026-07-21 修复
- [x] O2 司令接管全链路生效（接管单位从所有 manager 行为中排除）— 2026-07-21 修复
- [x] O3 建造完成自动归矿 — 2026-07-21 修复
- [x] O4 rush 确认即撤回侦查农民 — 2026-07-21 修复
- [x] E1 pivot rush_cannons 换臂开关 — 2026-07-21 就绪（步骤见 E1 条）
- [x] O5 憋气机制保航母主 C（save_up_spawn + flows.yml save_up）— 2026-07-21 修复
- [x] E2 动态开矿/分矿塔数/星门气体闸门 — 2026-07-21 实现，待 bench 验证

---

## 2026-07-21 验证局结果：carrier @BelShirVestigeLE vs Zerg Harder/Macro —— Victory

- 升级链正常：SHIELDS L1 @3:06 / AIRWEAPONS L1 @3:18 / AIRARMORS L1 @5:35
  （`auto_tech_up_enabled=False` 后守卫路径补建锻炉，研究不断档）
- 日志零刷屏：`Building FORGE for ...` 出现 0 次（上局同期每帧刷）
- **Idle worker time：149.25s（上局 317.375s，-53%）**——O1/O3 主账消除；
  残存 ~149s 待后续观察构成（可能含司令接管期/长距离采矿空窗）
- 产量：击毁单位价值 8150，采集 8995 矿 / 2872 气
