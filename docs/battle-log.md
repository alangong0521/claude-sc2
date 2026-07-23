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

### O10 carrier 科技深度不足：终局只有 L1，拦截机容量没升

- **现象**（司令观察）：到对局结束，航母没有升拦截机容量（8 小飞机），护盾和
  其它科技也只到 L1。
- **影响**：航母流的后期强度一半在科技（容量=每航母火力翻倍，L2/L3 攻防盾
  是黄金舰队的本钱），只到 L1 = 流派没打完。
- **实证根因**（2026-07-22，以 stableid 数据为准，**改正猜测**）：
  - **当前 melee 版本没有任何航母容量/弹射升级可研究**——`CARRIERCARRIERCAPACITY`、
    `CARRIERLAUNCHSPEEDUPGRADE`、`INTERCEPTORLIMIT4/6`、`CARRIERLEASHRANGEUPGRADE`
    枚举存在但都不在 `UPGRADE_RESEARCHED_FROM`（coop/旧版残留）。容量没法升，
    航母火力只能靠空攻 L2/L3 补。
  - 升级链浅是真问题：carrier 原 upgrades 只有三个 L1。L2/L3 前置查实：
    空攻/空防 L2/L3 需 FLEETBEACON（已在科技链）；盾 L2/L3 需 TWILIGHTCOUNCIL
    （carrier 原本不建，缺）。
- **实现**（2026-07-22）：
  - `flows.yml` carrier upgrades 补全为 9 项全链（空攻/空防/盾 L1-L3）；顺序讲究
    ——UpgradeController 遇不可研究项会截断后续，故 L1 在前、盾 L2/L3 垫底。
  - `upgrade_tech_buildings()` 加 `done` 门控：`required_building`（如暮光议会）
    只在**同线上一阶完成后**才由守卫路径补建，避免开局抢 100 气拖慢星门/航标。
- **状态**：已修复（待 bench 验证：多矿经济起来后 L2/L3 应依次启动不空转）。

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
- **状态**：已实现（单测 121 例全绿 + carrier/tempest 编译过），**✅ bench 验证通过（2026-07-21，见文末 E2 结果）**。

---

## 2026-07-22 carrier @PaladinoTerminalLE vs Terran VeryHard/Rush（共驾局，**Victory**）

> 结局：司令接管玩了一会获胜，电脑打出 gg；日志无 Result 行是因接管后客户端
> 结束方式绕过了 bot 结果回报，traceback 是 python-sc2 局后查询竞态，无害。
> 升级节奏：SHIELDS L1 @3:45 / AIRWEAPONS L1 @4:11 / AIRARMORS L1 @6:21。
### O6 仍有农民干等钱造建筑（疑似等第二个水晶）

- **现象**：一个农民不干活干等着，疑似在等钱造第二个 pylon。
- **影响**：O1 类问题的残留——pylon 路径没被守卫覆盖。
- **实证根因**（2026-07-22，与原猜测一致）：pylon 走 ares `AutoSupply`，
  `auto_supply.py:52-55` 在 supply 不足时直接调 `BuildStructure`，全程无
  can_afford 检查 → 农民被钉在 pylon 建造点等 100 矿（同 O1 的 TechUp 模式）。
- **修复**：`production_manager.update` 只在 `can_afford(PYLON)` 时才把
  `AutoSupply` 加进 MacroPlan；supply 缺口判定仍归 ares 内部。
- **状态**：已修复（待 bench 验证）。

### O7 主矿区频繁鼠标点击（采集应是游戏自动行为）

- **现象**：屏幕上主矿区域有频繁的鼠标点击操作——农民采矿/采气本该是自动的，
  不需要 bot 反复下指令。
- **影响**：无谓的指令刷新；干扰司令观战，也可能顶掉司令手动操作（O2 类隐患）。
- **实证根因**（2026-07-22，**改正原猜测**）：不是 `_handle_idle_workers`——它只碰
  `workers.idle`（零命令农民），正常采集往返的农民手里恒有命令，扫不到。真正的
  点击源是 ares `Mining` 的 **mineral_boost 加速采矿微操**：每个农民每次往返在
  距离窗口内都被下 `move + SMART` 两条命令（speed_mining.py:91-94），16+ 农民
  就是满屏点击。这是框架刻意设计（挤一点采矿效率），但与「采集零打扰/司令观感」冲突。
- **修复**：`bot/main.py` 改 `Mining(mineral_boost=False)`——走 `_do_standard_mining`，
  只在农民闲置/挂错矿时补一条 gather，采集中零命令；代价是放弃加速采矿的微量
  经济收益。另给 `_handle_idle_workers` 加护栏：跳过 `is_gathering /
  is_carrying_resource / is_returning` 的农民（过渡帧也不误重下 gather）。
- **状态**：已修复（待 bench 验证，顺带看采矿收入变化是否可忽略）。

### O8 Forge 建好没有立即升 S 盾

- **现象**：Forge 建成后护盾 L1 没有立刻开始研究。
- **司令判断**：如果是钱不够——护盾升级时间长，应该**提前攒钱**，Forge 一好就点。
- **实证根因**（2026-07-22，**改正原猜测的"队列时序"说**）：不是队列卡位——
  盾在 Forge、空攻/空防在 Cybercore，不同建筑本就并行研究，排第三不挡道。
  真正原因是**资源竞争**：研究要一次付清 100/100，而 SpawnController/造农民/
  pylon 每帧都在花钱，轮到研究时存款总差一口气。
- **修复**（按司令意图的"预留"语义，用 ares 自带机制）：`UpgradeController` 移进
  MacroPlan 并置于 SpawnController **之前**，`prioritize=True`——研究就绪但买不起
  时返回 True 截断 plan，产兵暂停花钱、资源攒给研究；建筑缺失/前置未就绪时返回
  False 不阻塞（无存款死锁）。注意残留：plan 外的开销（造农民、_spend_bank、
  追加产能）不参与预留，属可接受误差。
- **状态**：已修复（待 bench 验证）。

### O9 5 分半前零战斗单位零塔：贪开局的依据不是侦查，是赌检测来得及

- **现象**（司令观察）：5:30 才出第一个战斗单位（Oracle），之前没有任何作战单位，
  光子塔也没修。敌一波 rush 基地可能直接被打穿。
- **机制解释**（读码确认）：
  - 天空体配方 spawn = CARRIER/TEMPEST，科技链 GATEWAY→BY→STARGATE→FLEETBEACON，
    Gateway 一个不产地面兵——**设计上就是「第一个兵 = Oracle（只需星门）」**；
  - 光子塔：6 分钟前不铺，除非 rush 预警（≥2 敌作战单位压到家 40 格，
    `_should_build_defense`）或 rush 检测（4 分钟前敌可见兵力 ≥6，
    `_update_rush_state`）触发；
  - 兜底就是 pivot 响应包：检测成立 → 4 叉子 + 铺塔 + 全军守家。
- **诚实结论：是赌**。开局贪不贪**不随侦查情报调整**——2 分钟派的探机看到的
  信息只喂给 rush 判据，不构成「确认对面不是 rush 才放心贪」的决策。
- **司令要求**：侦查确认对面建筑/科技不是 rush，才可以这么贪；否则就是赌，不可取。
- **实现**（2026-07-22，最简单可验证版本）：
  - `production_plans.scout_verdict()` 纯函数三档：无情报→unknown（保守按 rush）；
    早出兵建筑 ≥2 或早期可见作战单位 ≥6（阈值与 early_swarm 同源）→ rush；
    否则 → greedy（维持贪打法）。
  - `production_manager._evaluate_scout_intel()`：t≈170s 一局评一次
    （探机 100s 出发，留 70s 赶路/送死窗口）；rush/unknown → 直接置
    `_rush_active`（复用现有响应包：出叉+铺塔+守家，比"敌兵压到 40 格"提前
    ~1 分钟；误报 60 秒后自动解除）；评估完把 SCOUTING 农民撤回采矿（同 O4 精神）。
  - **只挂 carrier**：tempest/stalker 是已验证基线，行为一行不动。
- **状态**：已实现（待 bench 验证：Macro 局应在 170s 判 greedy 零响应；Rush 局
  应提前出叉/铺塔）。

---

## 优化 backlog（打完统一处理）

- [x] O1 建造排队不派活干等（钱不够不钉工人）— 2026-07-21 修复
- [x] O2 司令接管全链路生效（接管单位从所有 manager 行为中排除）— 2026-07-21 修复
- [x] O3 建造完成自动归矿 — 2026-07-21 修复
- [x] O4 rush 确认即撤回侦查农民 — 2026-07-21 修复
- [x] E1 pivot rush_cannons 换臂开关 — 2026-07-21 就绪（步骤见 E1 条）
- [x] O5 憋气机制保航母主 C（save_up_spawn + flows.yml save_up）— 2026-07-21 修复
- [x] E2 动态开矿/分矿塔数/星门气体闸门 — 2026-07-21 实现并 bench 验证（6-0）
- [x] O6 pylon 路径（AutoSupply?）也有干等钱问题 — 2026-07-22 修复
- [x] O7 主矿区频繁点击，采集疑似被 bot 反复下指令 — 2026-07-22 修复
- [x] O8 护盾升级未随 Forge 就绪即启动，需资源预留/队列时序排查 — 2026-07-22 修复
- [x] O9 贪开局不随侦查调整（赌检测来得及）→ 侦查情报→开局决策闭环 — 2026-07-22 实现
- [x] O10 carrier 升级链补全（拦截机容量 + L2/L3） — 2026-07-22 修复
- [x] E3-R1 rush 期间研究预留饿死响应包 — 2026-07-22 修复（rush_active 不注册 UpgradeController）
- [x] E3b-R1 塔触发与 rush 检测脱钩 + rush 前线折跃 — 2026-07-22 修复（rush 即铺塔 + spawn_target 回家）
- [x] E3c-R1 save_up 截断反空军混编 — 2026-07-22 修复（save_up_spawn exempt）
- [ ] E3c-R2 二矿被打掉（军队真空期+分矿塔节奏）— 2026-07-22 分析+候选建议（见 E3c 节，未动手）
- [x] E3d 塔链被电池科技饿死 + rush 矿饥荒 + 单兵营瓶颈 — 2026-07-22 修复（电池让位/资源集中/补 gateway）
- [x] E3e 舰队成型前军队真空 — 2026-07-22 修复（pre_fleet 地面保底，cap=6 叉）
- [x] E3f 保底下限不随威胁伸缩 + 塔建造单线慢 — 2026-07-22 修复（pre_fleet_cap 伸缩 + max_on_route=2）
- [x] E3g 保底兵无令进攻送死 + AutoSupply 饿死 MacroPlan — 2026-07-22 修复（保底阶段守家 + return_true_if_supply_required=False）
- [x] E3h save_up 矿物盲区 + 水晶紧急通道 — 2026-07-22 修复（resource_gap 矿气取大 + supply_left≤2 例外）
- [x] O13 扩张后不补气矿（矿 5000+/气 0）— 2026-07-22 修复（_ensure_expansion_gas 按基地双气 + 45s 反卡死 + 气矿优先级最高）
- [x] O11 农民干等钱造建筑（非水晶场景）— 2026-07-22 修复（钉点 >6s 撤回 watchdog + 扩张 can_afford 守卫）
- [x] O15 基地清零攒钱重建 Nexus — 2026-07-23 修复（MacroPlan 截断 + 矿干 ExpansionController + Q5 豁免）
- [x] E3k 开矿攒钱预留（one_base 可选项）— 2026-07-23 实现（expansion_reserve_active）
- [x] E3k 预留卡死（watchdog 杀扩张钉点 + UC 饿死 plan 尾部 EC）— 2026-07-23 修复（NEXUS 豁免 + EC 前置 prioritize + 预留期 UC 让位）
- [x] E3l 分矿裸奔（塔防启动晚于 Nexus 落地）— 2026-07-23 修复（defense_syncs_with_nexus：在建/多基地即启动）
- [x] E3m 验证塔同步生效（二矿存活 30-100s→290s+）— E3 系列机制层修尽，转入数值面振荡带（1-2/2-1）
- [x] O12/O14 航母专属 combat 类 — 2026-07-23 实现（carrier_offensive：锚点放机+残血后撤，待 E4 验证）
- [x] E4 停摆根因（O15 死锁：0 基地+存款<400 零收入永远攒不够）— 2026-07-23 修复（nexus_rebuild_viable 加存款门槛）
- [x] E4b 优势误判（敌 0 可见=未知非优势，预留自绞链路）— 2026-07-23 修复（should_expand_dynamic 优势触发要求敌现身）
- [x] E4c watchdog 杀塔（rush 期钉点撤回循环，首波穿）— 2026-07-23 修复（rush_active 期间建造钉点全豁免）
- [x] E4d 航母不放机（StutterUnitBack 对无武器航母恒走逃跑分支）— 2026-07-23 重写（AttackTarget 放机 + 威胁圈/锚点/残血三滞回）
- [x] CARRIER_COMBAT 环境变量开关（双通道对照实验）— 2026-07-23 实现（army_config env 覆盖 + bench.py --carrier-combat 透传/记录）
- [ ] E4 双通道对照（--carrier-combat default vs carrier_offensive，N=5）— 待跑（E4f 0-3 全死 550-666s 早于航母出生，微操非死因；E4e/E4f 差一局是噪声）
- [x] E4g 双通道判决：micro 0-5 vs default 2-3，微操类挂起、default 转正 — 2026-07-23（类代码与开关保留，待 replay 级调试重启）
- [ ] E5-B 臂先行（P2 叉厚 per_enemy 0.7/max 20，基线=e4g-default 2-3）— 待跑

---

## 2026-07-21 验证局结果：carrier @BelShirVestigeLE vs Zerg Harder/Macro —— Victory

- 升级链正常：SHIELDS L1 @3:06 / AIRWEAPONS L1 @3:18 / AIRARMORS L1 @5:35
  （`auto_tech_up_enabled=False` 后守卫路径补建锻炉，研究不断档）
- 日志零刷屏：`Building FORGE for ...` 出现 0 次（上局同期每帧刷）
- **Idle worker time：149.25s（上局 317.375s，-53%）**——O1/O3 主账消除；
  残存 ~149s 待后续观察构成（可能含司令接管期/长距离采矿空窗）
- 产量：击毁单位价值 8150，采集 8995 矿 / 2872 气

---

## 2026-07-21 E2 bench 结果：动态多矿验证（carrier vs Zerg VeryHard @AbyssalReefLE，各 N=3）

runner=bench.py，tag=`e2-carrier-vh-zerg-rush` / `e2-carrier-vh-zerg-macro`。
（注：Rush 第 1 局为旧气闸门公式，其后局为 +1 新公式；对结论无实质影响。）

| 系列 | 战绩 | 平均时长 | 终局编成(均值) | 基地数(终局) |
|---|---|---|---|---|
| Rush | **3-0** | 724s | CARRIER×5.3 TEMPEST×2.5 拦截机×32 | 4 / 3 / 2 |
| Macro | **3-0** | 711s | CARRIER×7.7 TEMPEST×3.0 拦截机×33 | 3 / 4 / 4 |

- **臂 A rush 响应不回归**：Rush 系列 3-0，顶住后顺势开到 2~4 矿；
  塔 10~15 座（敌兵力高档触发），电池 2~4。
- **多矿机制生效**：Macro 系列两局开满 4 矿，assimilator 8 个全满采；
  星门 3~5 个，与气闸门公式（满采基地+1，4 基地→5）一致；农民 57~67。
- **航母数量随气上涨**：Macro 终局航母 7.7（E1 单矿时代 5.0），
  CARRIER@355s 成型（比 E1 的 387s 还早，多矿经济反哺）。
- 残留：retro 仍有 one_base（rush g3 只到 2 矿——基地<4 但局势已赢，可接受）、
  trickle（零星送兵，老问题，后续看）。

---

## 2026-07-22 E3 bench 结果：O6-O10 验证局（carrier vs Zerg VeryHard @AbyssalReefLE，各 N=3）

tag=`e3-carrier-vh-zerg-rush` / `e3-carrier-vh-zerg-macro`。

| 系列 | 战绩 | 平均时长 | 备注 |
|---|---|---|---|
| Rush | **2-1**（E2 同期 3-0，回归） | 579s | 败局 game_02 见下方回归分析 |
| Macro | **3-0** | 1066s | 但存款峰值 11820、retro bank×2 |

### E3-R1 回归：O8 研究预留饿死 rush 响应包（已修复）

- **证据**（bench/e3-carrier-vh-zerg-rush/game_02/）：虫族 t≈241s 小狗 15 只冲家，
  我方 rush 响应只出 1 叉（rush_zealots 应为 4）、光子炮只有 2 座，t=275 基地全失；
  run.log 显示 SHIELDS L1 @3:03、AIRWEAPONS L1 @3:24 正在研究——正是 rush 窗口。
- **根因**：O8 把 `UpgradeController` 以 `prioritize=True` 放进 MacroPlan 最前——
  研究预留截断后续 plan，rush 响应包（叉子在 SpawnController、塔在后续行为）
  被活活饿死。rush 窗口与早期升级窗口天然重叠，优先级必须反转。
- **修复**（2026-07-22）：`production_plans.research_paused_for_rush()` +
  `production_manager.update` 在 `rush_active`（含 O9 scout verdict 提前触发）
  期间**不注册 UpgradeController**——响应包独占资源；rush 解除后自动恢复
  prioritize 预留。补回归单测 2 例（全量 130 例绿）。
- **状态**：已修复（待重跑 e3-rush 验证回 3-0）。

### 候选问题（只评估，未动手）

- **Macro 存款峰值 11820 / retro bank×2**：根因判断——主要是**气瓶颈下矿花不出去**
  （航母流矿:气消耗比远低于采集比，多矿后矿必然淤积）叠加 `_spend_bank` 触发阈值
  （>800 且 <20 分钟）窗口偏窄；O8 研究预留的攒钱量级（一次几百）不足以解释 11k，
  不是主因。候选方向：提高 `_spend_bank`  aggressiveness（更低阈值/更高产能上限）、
  矿富余转航母外的矿耗出口（更多塔/电池）。记入下批观察。

---

## 2026-07-22 E3b bench 结果：E3-R1 修复后重跑 Rush（仍 2-1，死因不同）

tag=`e3b-carrier-vh-zerg-rush`（carrier vs Zerg VeryHard/Rush N=3）。研究暂停已生效
（败局 run.log 全程无 Researching），但 game_02 仍败，逐帧 state 快照实证如下。

### E3b-R1 败局分析（证据：bench/e3b-carrier-vh-zerg-rush/game_02/）

时间线：t=130 rush 检测成立（early_swarm：探机看到 6 狗，O4 撤回事件记录）→
首叉 t=181（一个接一个死：197 亡 → 209 第二个 → 225 又没，在场兵力恒 1）→
首座光子炮 t=221 → t=225 敌 15 狗、229 敌 18 狗 → t=232 基地掉判负。

**主因排序（实证）**：

1. **塔启动与 rush 检测脱钩（主因，已修）**：rush 130s 就检测成立，但
   `_should_build_defense` 的 rush 分支只看「敌兵压到家 40 格」→ 塔 ~215s 才开建。
   炮塔 ~30s 建造 + 要水晶供电，压到门口再建根本来不及——响应包名义含铺塔，
   实际塔触发是另一套判据。
2. **单 Gateway 产能瓶颈（结构性，未动）**：rush 响应只改 spawn 配方，1 兵营
   ~28s 一叉 → 到 225s 最多 2-3 叉且永远分批到场（trickle 送死的直接形态）。
   E1 证明"4叉+塔"包能赢的前提是塔及时成阵，单靠叉子产能顶不住 15 狗。
3. **rush 窗口科技/气矿继续花钱（次因，候选）**：130-180s 间 FORGE(150) +
   CYBERCORE(150) + 第二气(75) 照建，首叉拖到 181s、塔钱紧张。
4. ~~前线折跃送死~~：**嫌疑不成立**——carrier 无 warpgate 研究，叉子是兵营
   训练在主基出生，spawn_target 只影响折跃。但对 stalker 等有 warpgate 的流派
   逻辑上确实错（rush 时前线=敌群），仍一并修复。
5. ~~侦查判定太晚~~：**嫌疑不成立**——early_swarm 130s 就触发（探机视野），
   离狗到脸有 ~95s，输在执行不在检测。O9 verdict(170s) 本局根本没用到。

**修复**（2026-07-22，bot 层）：

- `_should_build_defense`：`rush_active` 成立即铺塔（`production_plans.rush_triggers_defense`，
  `rush_cannons=False` 的臂 B 保持不铺）→ 同类局面塔提前 ~85s 开建；
- rush_active 期间 `SpawnController.spawn_target` 切回主基（不前线折跃）。
- 未动（候选）：rush 期暂停非 rush 科技开销（forge/cybercore/第二气）、
  rush 期追加 Gateway 产能——看 E3c 重跑结果再定。
- **方差说明**：E2 同图同档曾 3-0，单局败北有方差成分；但塔触发脱钩是
  实打实的机制缺陷，与方差无关，必须修。
- **状态**：已修复（单测 133 例绿），待 E3c 重跑验证。

---

## 2026-07-22 E3c bench 结果：rush 顶住但输转型（Rush 系列仍 2-1）

tag=`e3c-carrier-vh-zerg-rush`。E3b 修复成立（rush 响应包顶住了第一波），
败局 game_01 是新的失败模式：中期二矿被打掉 → 单矿憋航母 → 敌转腐化+巢虫领主
→ 我方零追猎混编团灭。

### E3c-R1 save_up 吃掉 pivot 反空军混编（实证，已修复）

- **实证**：敌 t=964 有 6 腐化+3 巢虫领主（空军 ≥3 触发 anti_air pivot），
  但终局 STALKER=0。读码确认：anti-air 分支生成的 spawn dict 也过
  `save_up_spawn`（O5 设计如此），save_up=250 且航母占比落后时 dict 只留
  CARRIER——追猎作为"低优先"被永久截断。二矿掉后航母占比更难达标，
  截断几乎恒成立 → 零追猎。
- **修复**（2026-07-22）：`save_up_spawn` 加 `exempt` 参数（永不截断的兵种），
  `_apply_save_up` 把 pivot `anti_air_units` 传进去——反空军混编是保命的防空，
  不是副 C，不参与憋气截断。副 C（TEMPEST）截断语义不变。
- **状态**：已修复（单测 135 例绿），待下轮 bench。

### E3c-R2 二矿死因分析（只分析，候选未动手）

时间线（逐帧快照）：t≈349 二矿建成 → t=514 敌 8 蟑螂+11 狗+4 刺蛇+1 感染虫
压到 → t=538→542 二矿掉（农民随后骤减 12）。死因拆解：

1. **军队真空期挨打（主因）**：航母和风暴都需舰队航标（ares
   UNIT_TECH_REQUIREMENT 实证 TEMPEST 也要 FLEETBEACON）——航标 ~520s 才就绪，
   此前 3 个星门全闲、全场兵力 = 1 先知（+1 叉）。钱花在科技/星门上，
   挨打时没有一兵可回援。
2. **分矿塔数量/节奏不够**：敌 18 作战单位 → 塔目标 ~7/矿（expansion_cannons
   动态公式），挨打时全局只有 8 座（两矿合计），二矿实际就位 ~3 座，
   挡不住 8 蟑螂强拆 Nexus。
3. **开矿时机**：二矿在 t≈349 敌 15 狗可见时开出（优势判据没拦住——我方
   兵力 0 也满足？不，是爆仓触发：农民 ≥22×1）。开矿本身没错（之后有 ~160s
   和平期），问题是和平期全投科技没补兵力/塔。
- **修复建议（候选，下批定）**：
  ① 舰队航标就绪前限制星门数 ≤1（气体闸门的 +1 不该超前于航标，杜绝星门闲置）；
  ② 军队真空期（stargate 兵种不可造且敌可见兵力 ≥N）用 gateway 出叉/追猎保底；
  ③ 分矿塔建造优先级/供电节奏（natural 先供电再排塔）；
  ④ 爆仓开矿触发加"敌可见兵力 < 阈值"安全门。

---

## 2026-07-22 E3d bench 结果：Rush 0-3（判定：方差放大结构缺陷，非 exempt 回归）

tag=`e3d-carrier-vh-zerg-rush`。E3c(2-1) 与 E3d(0-3) 之间只改了 save_up exempt。

### 回归 vs 方差判定

- **exempt 无机制性影响（已核实）**：rush 时 `_effective_spawn` 走叉子单兵种分支，
  直接 return 不过 `save_up_spawn`——exempt 改动对 rush 响应路径零接触。
- **E3c 胜局 vs E3d 败局对比**：两边的塔链都依赖同一个抽签——ProtossStaticDefence
  的 `_tech_required` 每帧先给电池 TechUp 核心（无 can_afford 守卫），核心在建时
  返回 False 才轮到炮塔。E3c game_02 抽中了（首塔 172s），E3d game_01 没抽中
  （206s 基地掉时仍 0 塔）。**0-3 = 方差（狗波时机）× 结构缺陷（塔链被电池科技阻塞）**。

### 「零炮塔」真相（改正 brief 的"无 FORGE"说）

逐帧快照：FORGE 从 t=124 就存在；真正断的是炮塔。链条：
rush 130s 检测成立 → E3b 修复让防御立即启动 → `shield_batteries_per_base=1`
→ `_tech_required` 先给电池 TechUp CYBERNETICSCORE（无守卫，工人钉在建造点等
150 矿）→ 科技未就绪前 execute 直接 return → **pylon/炮塔段永远轮不到**。
同时探机照造（15→22 个）、第 3 水晶照下，矿永远凑不够 150 → 核心也起不来，
互相饿死。run.log 只有 `Adding CYBERNETICSCORE to tech towards SHIELDBATTERY` 一行
反复出现，与快照完全吻合。

### 结构性修复（2026-07-22，rush_active 资源集中防御）

1. **暂停非必要开销**：rush_active 期间跳过 `_build_flow_structures`（核心/第二气）、
   `_build_probes`（造农民）、`_build_extra_production`、`_spend_bank`、
   `_build_forward_pylon`；升级建筑循环只保 FORGE（炮塔前置）。
2. **电池让位**：rush_active 期间 `shield_batteries_per_base=0`（电池要核心，
   是塔链被饿死的直接原因）；rush 解除恢复 1/矿。
3. **补兵营产能**：`_rush_gateway_boost`（`production_plans.rush_needs_gateway`）
   ——rush_active 且敌可见兵力 > 在场叉子数且 gateway（含 warpgate/在建）< 2 时
   追加一个 gateway（can_afford 守卫；臂 C rush_zealots=0 不补）。
4. rush_active 既有三连动（研究让位/spawn_target 回家/rush 即铺塔）不变。

- **状态**：已修复（单测 139 例绿），待 E3e 重跑验证。

---

## 2026-07-22 E3e bench 结果：rush 顶住了，输在舰队成型前的军队真空（Rush 1-2）

tag=`e3e-carrier-vh-zerg-rush`。六连动生效（game_01：161s 塔开建、4 塔 3 叉
挡住 20 狗），rush 阶段从必败变为能顶住。新失败模式：rush 解除 → 顺利开 2-3 矿
→ **军队真空**（t=402-562 army=1 先知：rush 的 4 叉死在消耗里，航母/风暴都要
舰队航标，首艘航母 ~640s 才出生）→ t=562 敌 11 蟑螂+8 刺蛇+14 狗一波连穿两矿
→ t=723 判负。正是 E3c-R2 候选②「军队真空期地面保底」，数据证明是绑约束。

### E3e-R1 实现：舰队成型前地面保底（pre_fleet）

- **设计**（2026-07-22）：
  - 触发/退出：舰队主 C（`_primary_unit_id`，carrier=航母）计数为 0 期间，
    spawn 混入保底兵种；主 C 出生（或达 cap）自动退出，回归主配方。
  - 配置：`flows.yml` carrier 块 `pre_fleet: {id: ZEALOT, cap: 6}`——叉子纯矿耗，
    不抢航母的气；`flow_config.PreFleet` 解析，缺省 None=关（tempest/stalker 不动）。
  - 纯函数 `production_plans.pre_fleet_spawn`：混入时 priority=5 压最低
    （舰队能产时舰队优先）；cap/上线即退出。
  - **优先级与交互**：rush 响应的叉子覆盖分支最先 return（优先于保底）；
    保底与 anti-air 可叠加（先混防空再混保底）；**保底兵种进 save_up 的 exempt**
    （保命不截断，与反空军同原则）——保底叉子吃矿不吃气，不与憋气攒 250 冲突。
- **状态**：已实现（单测 143 例绿），待 E3f 验证。
- **残留候选**：二矿分矿塔节奏（E3c-R2 的①③④）仍未动，看 E3f 数据。

---

## 2026-07-22 E3f bench 结果：早期全绿，输在两段式 rush 的主力波（Rush 1-2）

tag=`e3f-carrier-vh-zerg-rush`。game_02 逐帧：181s 首塔、241s 4 塔、301s 5 塔 4 叉、
362s 6 叉开二矿（六连动+保底全部工作）→ t=373 敌第二波主力到脸（19 狗+8 蟑螂+
刺蛇，Zerg VeryHard Rush 两段式：小狗试探 → ~7 分钟蟑螂刺蛇主力）→ 6 叉瞬间熔化、
t=446 二矿掉 → 推平。

### E3f-R1 保底随威胁伸缩（已修复）

- **死因**：保底 cap=6 是和平期数字，敌 30 作战单位时 6 叉只是纸；且叉子是纯矿
  兵种，多矿经济本可支撑 3 倍量。
- **修复**：`production_plans.pre_fleet_cap`——上限 = clamp(cap, 敌可见作战单位 ×
  per_enemy, max)，flows.yml carrier 配 `{cap: 6, per_enemy: 0.5, max: 16}`
  （敌 30 → 15 叉）；max=0 时固定 cap（向后兼容）。航母上线退出逻辑不变。

### E3f-R2 分矿塔节奏评估（顺带最小修）

- **评估结论**：t=373-446 敌 ~30 单位时动态塔目标 ~10/矿，实际全局只有 6→7 座。
  两个节奏问题：①和平期敌兵=0 → 塔目标=min 3，主矿 5 塔即停建，主力波可见时
  （已到脸）才爬目标，塔 ~29s/座追不上——**公式只能反应不能预测，这是固有局限**；
  ②单线建造（max_on_route=1）+ 分矿先供电后立塔，二矿 85s 只 +2 座。
- **最小修**：`ProtossStaticDefence(max_on_route=2)` 允许 2 座同建（建造吞吐翻倍）。
  供电顺序是 ares 行为内序列（先 pylon 后 cannon），不动。
- **状态**：已修复（单测 147 例绿），待 E3g 验证。
- **候选（未动）**：主力波预测（按时间窗/敌产能建筑而非可见兵力抬塔目标）；
  保底叉子配电池站位（ battery 回血让叉子站住）。

---

## 2026-07-22 E3g bench 结果：rush 稳定顶住，败在中期转型（Rush 1-2）

tag=`e3g-carrier-vh-zerg-rush`。早期 rush 已稳定顶住，game_01 败因锁定两个机制问题。

### E3g-R1 地面保底兵无令外出送死（trickle 实证，已修）

- **实证**：t=542-603 和平期攒回 6 叉，t=642 前消失大半（敌波 663 才到脸）。
  读码确认：无 stance、rush_active=False 时 `combat_manager.attack_target` 默认
  = 最近敌建筑，叉子（on_unit_created 归 ATTACKING role）被 GenericOffensive
  拉过全图进攻，半路送进蟑螂群。carrier 的 rally_min_army=0，集结纪律不生效。
- **修复**：`production_plans.floor_army_defends_home`——流派配了 pre_fleet 且
  舰队主 C 计数为 0（未成型）时 attack_target 默认守家；主 C 上线恢复默认进攻。
  插入点在 stance/rush/司令 target **之后**，司令命令与 rush 联动不受影响。

### E3g-R2 航母节奏卡点：不是气，是 MacroPlan 被 AutoSupply 饿死（已修）

- **数据**（逐帧快照）：航标 t≈603 就绪时 gas=1752 且一路涨到 2400；
  矿却在 5~415 间徘徊。**气从来不是瓶颈**；且 t=610-618 矿 385 ≥ 350、
  气 1792 ≥ 250、双星门+航标就绪，航母仍然没下——同时 AIRWEAPONS L2
  （前置航标已就绪）到 t=755 也没开始研究。升级和生产同时停摆 → 锁定 plan 层。
- **根因**：`AutoSupply` 的 `return_true_if_supply_required` 默认 True——supply
  紧张期（多生产建筑下 supply_left 长期 ≤ 阈值）它**每帧返回 True 截断
  MacroPlan**，排后面的 UpgradeController / SpawnController 整段不执行。
  同一窗口叉子战损后也补不上（6→1），两个症状同一根因。
- **修复**：注册时显式 `AutoSupply(return_true_if_supply_required=False)`
  ——pylon 照建（execute 内部已派工），但返回 False 让 plan 继续走到
  研究/生产。这正是 ares 该参数为 MacroPlan 预留的用法。
- **候选（未动）**：矿分配优先级（保底叉子上限 × 塔 × 农民 × 二矿同时分流，
  610 后矿很少再上 350）；「航母提速」结构项：更早开二矿/先气后塔。
- **状态**：已修复（单测 150 例绿），待 E3h 验证。

---

## 2026-07-22 E3h bench 结果：0胜2负1异常（方差 × 结构性回归，已修 A+B）

tag=`e3h-carrier-vh-zerg-rush`。战绩 0-2-1（game_03 ERROR 为 SC2 进程连接中断，
headless 基建抖动非 bot 逻辑）。retro：supply_block×2 one_base×2 overrun×2 trickle×1。

### 根因（逐帧实证）

1. **save_up 矿物盲区（主因，E3h-A 已修）**：航标 ~534s 就绪后 gas 1500-2600 躺着，
   矿恒定 <350。save_up 截断判据只看气缺口（=0）→ 永远截断到 {CARRIER}∪exempt，
   把 TEMPEST(175矿) 也锁死；exempt 叉子照吃矿 → 矿更不够 → 死锁。
   首艘航母拖到 787s（250 秒空窗），敌 6-7 分钟主力波打的是纯叉子+塔。
2. **supply_block（E3h-B 已修）**：矿物饥荒时 O6 的 can_afford(PYLON) 守卫完全
   屏蔽 AutoSupply → 水晶不排队 → 卡人口 68-100s（59/58、66/66 实证）。
3. **E3f/E3g 的加重作用（诚实记录）**：保底 cap 随敌兵爬（8-10 叉常驻）+
   双塔同建 + 守家叉子持续重建，三者把矿耗拉高一截，把气瓶颈局翻成矿瓶颈局，
   恰好踩进盲区。守家/AutoSupply 修复本身逻辑正确（叉子死在防线非送死；
   787s 后航母/风暴/追猎接连出生证明产线已通）。
4. one_base×2 = 矿物饥荒拖慢农民节奏的结果，非独立 bug；trickle×1 是 retro
   把防守战损误记（候选：检测口径区分）。

### 修复（2026-07-22，司令拍板 A+B，C 暂缓）

- **A 补矿物盲区**：`save_up_spawn` 判据 gas_gap → `resource_gap = max(气缺口,
  矿缺口)`（矿缺口 = `calculate_cost.minerals - ai.minerals`）——矿差得远时
  不截断，风暴在富矿窗口能补位，舰队不再双锁。
- **B 水晶紧急通道**：`should_register_autosupply`——supply_left ≤ 2 时即便
  买不起也注册 AutoSupply（钉一个工人换人口不断链）。
- **状态**：已修复（单测 155 例绿），待 E3i 验证。

## 2026-07-22 司令观察（E3i bench 后台对局期间）

### O11 仍有农民干等钱造建筑（复发）
B 水晶紧急通道修的是「人口余量 ≤2 才注册」，但一般建筑（非水晶）缺钱时
工人仍可能钉点干等。需排查当前哪些注册路径还带 can_afford 守卫、
哪些建筑队列允许工人在钱不够时被派出。待 E3i 后统一处理。

### O12 carrier 微操：航母主体站位利用地形
司令建议：航母主体尽量停在地面部队打不到的位置（高坡/低地交界处、
山谷/悬崖对面），只放拦截机跨越地形攻击地面部队。
实现方向候选：
- 站位评估：选目标点附近对地面不可达的坐标（无地面路径/悬崖隔离）作为
  航母锚点，拦截机射程内覆盖目标；
- 需要地图地形数据（cliff/不可通行格）+ 敌防空分布评估；
- 与现有进攻目标选择（attack_target）解耦，作为 carrier 专属站位层。
复杂度高，先记 backlog，E3 收官后评估。

### 环境确认：双通道验证可行
司令确认当前人机共驾观战与后台 bench 可并行（此前按单车道规则串行）。
后续验证可双通道跑，但注意 CPU/内存负载对 bench 时序的影响。

### O13 扩张不造气矿：5000 矿 / 个位数气的资源倒挂（carrier 流致命）
司令观察（E3i 后台对局）：3 矿已开但**没造气矿（Assimilator）**，
矿存款 5000+、气存款个位数。carrier 流航母 350/250、风暴 175/125、
空攻空防全吃气，气是硬约束、矿是副产品——倒挂说明：
- 扩张逻辑（E2 auto_expand）只拍 Nexus，没跟进气矿建设；
- 或气矿建设有 can_afford/优先级守卫被 5000 矿场景绕过（买得起但没排）。
排查方向：1) Nexus 落成后 Assimilator 是否自动排队、有无 cap；
2) 5000 矿时 _spend_bank 是否该优先买气矿+农民转气；
3) save_up/截断机制是否误伤气矿注册。
原则（司令拍板）：carrier 流派中**气矿优先级高于一切矿物开销**，
新矿落成应立即双气满采，随时补气。

### O14 无「残血后撤、满血顶前」机制（与 O12 同属 carrier 微操层）
司令问：残血航母躲到满血航母/风暴后面继续放小飞机——当前**没有**。
实证：CARRIER 在 army_composition.yml 用的是 `combat: default`
（GenericOffensive），只有 StutterUnitBack 节奏微操；全代码库无任何
health/shield 驱动的后撤换位逻辑。army_composition.yml:95 自己也标了
「放机微操待专属类」。
实现方向（carrier 专属 combat 类时一并做）：
- 按 shield+health 百分比排序编队，残血（如 <40%）航母锚点向阵后/地形
  后方收（与 O12 地形站位共用锚点逻辑）；
- 航母特性利好：拦截机放飞后主体可远离战场，残血航母输出零损失；
- 风暴射程 14 比航母站位更远，天然是「满血在前」的掩护位。

---

## 2026-07-22 E3i bench 结果：1胜2负（A+B 见效，O13 矿气倒置实锤）

tag=`e3i-carrier-vh-zerg-rush`。CARRIER@669s（E3h 为 787s，A+B 修复见效，
save_up 死锁已解）；终局编成均值 CARRIER×5。新信号：bank 6075、one_base×3、
supply_block 降至 ×1。

### 败因复盘（逐帧）

- **game_01（1474s 长局败）= O13 教科书**：二矿 341s 落成，**assimilator 停在 2 个
  长达 420s**（763s 才到 4）；三/四矿后续也都没跟上气。后期矿 6075/气 0——
  4 矿纯采晶，航母被气卡死，矿存成死钱。卡因（读码+时间线推断）：在建气矿尝试
  卡 tracker（工人被截/钉点）+ rush 暂停窗口（六连动④暂停科技链连带停气）
  + 单线建造 120s 超时才自愈，三者叠加。
- **game_03（快速败）**：rush 顶住 → 二矿 409s → 气正常跟上（as=4 @482）→
  t=578-602 敌 72 单位主力波，舰队未出生（单星门 + oracle 插队 + 矿紧），
  5 塔 8 叉被 overrun。与 E3g/E3h 同族的"两段式 rush 中期波"问题，
  不是新 bug；bank→气→航母提速是正解方向。

### 修复（2026-07-22，O13+O11）

- **O13 按基地补气（气矿优先级 > 一切矿物开销）**：
  - `production_manager._ensure_expansion_gas()`：每个就绪基地 ready 气矿+在建 <2
    就派建（`_build_gas(near=th)` 泛化支持按基地选气矿），调用点在
    `_build_extra_production`/`_spend_bank` **之前**；rush 期间缓（六连动不变）。
  - 反卡死：在建气矿超 45s 没落地 → 拆 tracker 重派
    （`production_plans.assimilator_attempt_stuck`）。
- **O11 钉点撤回（钱不够不钉工人）**：
  - `_handle_idle_workers` 扩 watchdog：tracker 里钉点 >6s 且结构仍买不起 →
    `release_from_build_tracker` 撤回采矿（`should_release_waiting_builder`）；
    例外：人口紧急态的水晶（E3h-B 故意钉）。覆盖 ares 全部无守卫路径
    （ProtossStaticDefence/ExpansionController/TechUp）。
  - `_auto_expand` 动态路径加 `can_afford(NEXUS)` 守卫（最贵的钉点先防住）。
- **状态**：已修复（单测 159 例绿），待 E3j 验证。

### O15 主矿采干+分矿被爆时，应攒钱重建 Nexus 而非继续出兵
司令观察：分矿被敌方爆掉、主基地矿气双干（无矿可采）时，bot 仍按
build order 继续造叉兵等进攻兵种——这是死路。正确策略：
**最高优先级攒钱（400 矿）重建 Nexus**，恢复经济才有后续。
实现方向候选：
- 触发条件：我方 Nexus 数 == 0 或（所有基地矿脉+气矿残余 ≈ 0 且
  无在建 Nexus）；
- 触发后 MacroPlan 截断到 {NEXUS} ∪ 保命防御（类比 save_up 机制，
  复用 resource_gap 判据）；工人转移到尚有矿的点位或拉去新开矿点；
- 与 rush 资源集中、save_up 的优先级关系：重建 Nexus > save_up 航母 >
  出兵（没经济一切免谈）。

---

## 2026-07-23 E3j bench 结果：GS2 1-2 / GS4 0-3（步长实验结论：维持 GS2）

- **GS2 标准臂 1-2**：Defeat 764s / Victory 404s / Defeat ~224s（第3局首次无结果
  重试后）。存款峰值 930（O13 见效，E3i 为 6075）；CARRIER@606.7s（系列最快）；
  终局 CARRIER×4。one_base×3、trickle×2 仍在。
- **GS4 臂 0-3 全快速败**（trickle×3 overrun×3）：步长实验结论已定，维持 GS2，
  gs4 局文件不做分析。

### 败因分析（逐帧 + run.log）

1. **one_base×3 = 阈值+经济问题，非 auto_expand bug（已核实）**：
   ares `ExpansionController` 默认 `can_afford_check=True`（不欠费派工），
   触发与执行链路本身无 bug。迟到原因：①爆仓触发要农民 ≥22×基地，rush 期
   造农民暂停（六连动④）→ 300s 时农民仅 18-20；②优势触发要 army supply ≥
   敌+12（6 叉=12 supply，~340s 才凑齐）；③rush 收尾矿紧，400 矿的 Nexus
   排队在塔/叉/农民之后（_spend_bank >800 更难够到）。game_01 二矿 341s 落成
   （优势触发）即此路径。可选项（未做）：ExpansionController(prioritize=True)
   进 MacroPlan 给 Nexus 攒钱预留，或下调 advantage_supply/爆仓阈值。
2. **game_03（重试局 224s 速败）**：run.log 实证——163s 敌 ling rush（首波
   ~17 只，本系列最大），forge 2:09 才开建、塔链来不及，224s 基地全失。
   属「最早最重波 vs 塔链速度」的方差极值，E3 系列已知结构边界。
   （注：该局 state 快照混有首次无结果尝试的帧，以 run.log 为准。）

### O15 修复：基地清零 → 一切让位重建 Nexus（2026-07-23）

- 触发 `nexus_rebuild_active`（townhalls==0）：MacroPlan 不注册
  UpgradeController/SpawnController（只留 AutoSupply），非 rush 开销块
  （科技链/补气/追加产能/滚雪球/前线塔/开矿/chrono）整体暂停 → 攒钱 400 重建。
  优先级：重建 Nexus > save_up > 出兵。
- `_ensure_townhall`：主矿已干时不再 no-op，改交 `ExpansionController(to_count=1)`
  找新矿点。
- Q5 早负判负加豁免：`nexus_rebuild_viable`（有工人+场上还有矿）时不投降，
  让 O15 打完；不可行（无工人或全图矿干）才判负。
- **状态**：已修复（单测 161 例绿），待下轮 bench 验证。

### E3k 修复：开矿攒钱预留（one_base 可选项落地，2026-07-23 司令拍板）

- **实现**：`production_plans.expansion_reserve_active` + `production_manager._expansion_reserve_active()`——动态开矿已触发（爆仓/优势，阈值不变）但暂时
  买不起 Nexus 时：不注册 SpawnController + 暂停造农民（防御塔保命不动），
  攒钱到 400 立即由 `_auto_expand` 原有路径拍下 Nexus。不钉工人
  （与 O11 watchdog 无冲突）。
- **优先级**（已理清）：rush 期间不开矿（`should_expand_dynamic` 内建 rush 门，
  六连动不变）；O15 基地清零重建 > 开矿预留（rebuild 先判，预留不启动）；
  开矿预留 > 出兵/造农民；save_up 在 SpawnController 内部，预留期间自然挂起。
- 没做：阈值（农民≥22×基地、优势+12）不动；ares ExpansionController 的
  prioritize 参数（它是"欠费也派工钉点"语义，与 O11 冲突，弃用）。
- **状态**：已实现（单测 164 例绿），待 E3k 验证。

---

## 2026-07-23 E3k bench 结果：2-1（历次最好）但开矿预留卡死（已修）

tag=`e3k-carrier-vh-zerg-rush`。CARRIER@508.9s（系列最快）、存款峰值 485（健康）。
但三局全部 one_base：触发后 50-200s Nexus 始终没拍下去。

### 预留卡死根因（逐帧+读码实证，两条叠加）

1. **O11 watchdog 杀扩张钉点（主因）**：O11 的「钉点 >6s 且买不起 → 拆 tracker
   撤回」对 Nexus 是致命的——工人提前走到扩张点等 400 矿是正常开矿打法，
   走路 10-20s 期间其他开销把矿花掉，工人到位 → 钉点 → 6s 后被撤回 →
   钱够再派 → 再被花 → 无限循环（game_03 在 281-285s 有 430-480 矿的干净
   窗口仍没拍下，此后每次 400 窗口都重复这一循环）。
2. **UC(prioritize) 饿死 plan 尾部的 EC（次因）**：舰队航标就绪后
   UpgradeController 研究/预留 9 项升级链，几乎每帧返回 True 截断 plan，
   排在最后的 ExpansionController 永远轮不到执行（E3j 时升级链短/航标晚，
   侥幸躲过）。叠加结果：航标前被 watchdog 杀、航标后被 UC 饿死。

### 修复（2026-07-23）

- `main.py` watchdog：**基地建筑（TOWNHALL_TYPES）豁免**——扩张钉点不撤回。
- `update()`：**ExpansionController 从 plan 尾部上移到 UC 之前**（
  `_want_dynamic_expand()` 算一次，EC/预留共用），并改 `prioritize=True`
  （欠费也先派工人走位，与 watchdog 豁免配套）；
  `_auto_expand` 动态分支删除（旧式 stalker 分支保留）。
- 开矿攒钱预留期间 **UpgradeController 也让位**（优先级：Nexus > 研究 > 出兵）。
- O15 重建路径不变（rebuild 优先，plan 内 EC 不启动）。
- **状态**：已修复（单测 164 例绿），待 E3l 复验。

---

## 2026-07-23 E3l bench 结果：0-3（开矿修通，新败因=分矿裸奔）

tag=`e3l-carrier-vh-zerg-rush`。开矿修复生效（E3k 卡死已解）：
game_01 334s 二矿/538s 三矿、game_02 330s 二矿、game_03 386s 二矿——
但分矿落地后被敌反复拆（3→2→1→…），农民和经济被拖死，三局全败。

### 两个问题（逐帧实证）

1. **是什么触发的扩张（司令第一问）**：EC 注册有 `_want_dynamic_expand` 门控
   （E3k 修复时就是门控的），不是 ares 自己乱扩——330-386s 时农民 18-20
   （没到爆仓线 22），触发的是**优势判定**：6-7 叉 = 12-14 army supply ≥
   敌可见 0 + 12。敌主力藏在战争迷雾里 → 「优势」是假象，扩张撞在
   敌方主力波成型前夜。**判定：门控工作正常，是优势信号本身被迷雾骗过。**
2. **分矿塔没跟上（裸奔根因）**：三局 Nexus 落地时全局塔只有 3-5 座
   （全在主矿），分矿 ~0 座。`_should_build_defense` 原来要等落地 +
   6 分钟自动线（或 rush/压门 40 格）才启动，分矿裸奔 30-100s；
   敌 30-70 单位的波到达时塔刚开始爬（敌 30 → 目标 10/矿 vs 实际 6-8）。

### 修复（2026-07-23）

- `production_plans.defense_syncs_with_nexus` + `_should_build_defense` 接入：
  **有 Nexus 在建或已多基地 → 立即启动分矿塔防**（ProtossStaticDefence
  自己排先供电后塔序；rush_cannons=False 的臂 B 语义不变，仍在前面拦截）。
- 没做「敌可见兵力 > 阈值缓开」：三局的波次在到达前都不可见（迷雾），
  可见兵力门挡不住；且 `ExpansionController.check_location_is_safe`
  已按影响力网格跳过危险点。
- **状态**：已修复（单测 165 例绿），待 E3m 复验。
- **残留候选**：分矿塔建造速度（单线 29s/座 vs 敌波成型速度）若仍不够，
  下一候选是「扩张触发时把塔目标临时抬到 min+2」或「分矿先下 1 塔再下 Nexus」。

---

## 2026-07-23 E3m bench 结果：1-2（塔同步生效，进入数值面振荡带）

tag=`e3m-carrier-vh-zerg-rush`。Defeat 512s / Defeat 544s / Victory 482s。
终局 CARRIER×3 INTERCEPTOR×40，CARRIER@592s，存款峰值 505。
retro：one_base×3（按终局计，实际都开过矿）trickle×2 overrun×2。

### 分矿塔同步修复生效（存活时长对比）

| 局 | 二矿落地 | 二矿存活到 | 对比 E3l |
|---|---|---|---|
| E3m game_01 | ~362s | 651s（~290s） | E3l 同期 30-100s 即被拆 |
| E3m game_02 | ~370s | 759s（二/三矿） | 同上 |
| E3l 三局 | 330-386s | 30-100s | —— |

裸奔窗口从「30-100s 被拆」改善到「撑过 4-6 分钟、多轮波次」，
`defense_syncs_with_nexus`（在建/多基地即启动塔防）确认有效。

### 两局败因：敌中段兵力数值面

两局败局同型：扩张正常落地、塔随矿同步、航母 592s 起产——但 Zerg
VeryHard/Rush 中段（7-10 分钟）主力波兵力厚度超出「6-10 叉 + 动态塔 +
刚起步的航母群」的承接上限，二矿在反复波次中被磨穿后崩盘。机制链
（rush 响应 → 保底 → 塔同步 → 气矿跟进 → 舰队成型）已无明显断点，
输的是数值不是逻辑。

### E3 系列判断（2026-07-23）

E3 系列 12 轮（E3→E3m）机制层 bug 已逐轮修尽：研究预留饿死响应包、
塔触发脱钩、电池阻塞塔链、rush 矿饥荒、单兵营瓶颈、save_up 截断防空/
矿物盲区、AutoSupply 饿死 plan、保底兵无令送死、气矿跟进卡死、
扩张钉点被杀/UC 饿死 EC、分矿塔启动过晚——每一轮都有实证根因和修复。
**剩余败因以 VeryHard/Rush AI 中段兵力数值面为主，胜率在 1-2/2-1 振荡带**。
后续提升方向是数值调参（保底配比/塔数曲线/扩张阈值）而非新机制，
建议转入参数面实验（类 E1 的换臂矩阵）或升档验证 Macro 系。

---

## 2026-07-23 O12/O14 实现：航母专属 combat 类（carrier_offensive）

- **需求**：O12 航母主体站地面打不到的位置（高坡/悬崖隔离）只放拦截机越地形
  输出；O14 残血航母（盾+血<40%）后撤到满血编队后面，拦截机继续输出零损失。
- **实现**（bot 层，只动 carrier，地面部队/风暴不卷入）：
  - `bot/combat/carrier_logic.py`（纯逻辑，可离线单测）：`is_wounded`
    （盾+血<40% 残血判定）、`anchor_score`（距 ideal 距离扣分 + 地形高差+3 +
    防空每单位 -4）、`best_anchor`（同分取首位=保守退路，找不到优势锚点天然
    退化为最大射程保守站位）。
  - `bot/combat/carrier_offensive.py`（运行时胶水，仿 tempest_offensive 接口）：
    每航母独立算锚点——绕参考点 12 方向候选环（进攻 ref=attack_target、
    防守 ref=主基），评分用 `ai.get_terrain_height` 的地形高差 +
    `can_attack_air` 敌单位 10 格内计防空；O14 残血时参考点收向最近满血
    航母/风暴（没有则主基方向 5 格）。射程内有敌 → StutterUnitBack 放机点杀
    （焦点逻辑与 tempest 同源 pick_focus_key），否则 PathUnitToTarget 赴锚点。
  - 接线：`army_composition.yml` CARRIER `combat: carrier_offensive`；
    `bot/army_config.py` COMBAT_KINDS 加项；`combat_manager` 实例化+分派表。
- **单测**：新增 `tests/test_carrier_logic.py` 10 例（残血三态/评分三项/
  选址四态）；全量 175 例绿；carrier/tempest 编译 OK。
- **状态**：已实现，待 E4 bench 验证（重点看：航母是否停在高坡/悬崖后放机、
  残血航母是否后撤且拦截机不断档、地面防空附近航母是否避让）。

---

## 数值调参方案 E5 候选（2026-07-23，只分析不改码，E4 航母微操 bench 期间）

素材：E3 系列 12 轮记录、E3m 两局败局逐帧、E3l 塔数时间线。
**E3m 定量画面**：中段两波——t=500-650s 敌 23→42→60 单位、终局波 70-88 单位；
我方承接 = 6-10 叉 + 4-8 塔 + 1-2 艘刚起步航母；真正死因是农民被抄
（game_01 t=650：42→22；game_02 t=747-771：47→29）后经济断气，
矿 <400 而气 2000-2800 烂掉，航母永远 1-2 艘。

### 参数改动点（按优先级）

**P1 分矿塔曲线**（现值：flows.yml carrier `expansion_cannons: {min: 3, max: 8}`，
公式 `min + 敌可见//4`，production_plans.expansion_cannon_count）
- 建议：`{min: 4, max: 12}`，系数 //4 → //3（敌 30 → 13 → 封顶 12）。
- 依据：E3m game_02 t=554 敌 60 单位压到时分矿塔 4-5 座（目标封顶 8/矿，
  2-3 矿需 16-24 座，实际全局 5-8 座）；E3l 塔线同型。
- 预期：中段波次分矿存活率↑；代价 150 矿/座，矿紧时挤航母/叉。
- 注意：上限 12 可能永远到不了（29s/座单线），先看建造队列是否成新瓶颈。

**P2 保底叉子厚度**（现值：flows.yml carrier `pre_fleet: {cap: 6, per_enemy: 0.5, max: 16}`）
- 建议：`per_enemy: 0.7, max: 20`（敌 60 → 20 叉）。
- 依据：E3m game_01 t=530 敌 42 vs 我 6 叉瞬熔；game_02 t=554 敌 60 vs 6 叉同型。
- 预期：地面承波厚度 ~2 倍，给塔/航母争取输出时间；代价 100 矿/叉。

**P3 首艘航母提速**（现值：无；E3h 候选 C 当时暂缓）
- 建议：舰队航标就绪且航母=0 且矿 <400 时，保底叉重建 + 塔爬升暂停，
  攒 350+250 给首艘（航母出生即恢复）。
- 依据：E3m game_01 t=506-530 敌波到达时 fb 已就绪、gas 1386、矿 25、
  航母 0；CARRIER@592s vs 敌主力波 ~510s 起，差一口气。
- 预期：首艘提前 60-90s，第二波时场上 1-2 航母。
- ⚠️ **等 E4 定稿**：航母微操改变航母性价比与战损结构，P3 的取舍
  （让多少矿给首艘）取决于 E4 后航母的实际输出/存活。

**P4 扩张优势阈值**（现值：flows.yml carrier `advantage_supply: 12`）
- 建议：12 → 18（6 叉=12 supply 不再够，需 9 叉或舰队起步才判优势）；
  或爆仓线 when_workers 22 → 20（二选一，别同改）。
- 依据：E3l 三局 330-386s 敌迷雾藏兵，「优势」假象撞波（已实证门控正常、
  信号被骗）。
- 预期：扩张推迟到真有承接力时；代价经济放缓，one_base 复古风险。

**P5 守家 rally**（现值：carrier `rally_min_army: 0`；⚠️ 这是机制不是纯参数）
- 建议：rally_min_army 0 → 12（兵力 <12 且司令无 stance 时守家攒兵，
  stalker 流已有同款）。
- 依据：E3m game_02 t=554-578 敌 59-60 压境时部队仍按 attack_target 分散。
- 优先级最低：机制改动，先验证 P1-P3 再看是否需要。

### 耦合标注（不能同臂改）

- **P1 × P2 × P3 三者抢同一笔矿**（塔 150/叉 100/航母 350+250）——全加 = 经济崩，
  必须分臂单独测。
- **P2 × P4**：叉子变多 → army supply 虚高 → 优势判定更容易触发（P4 调的就是它），
  同臂改会互相污染读数。
- **P1 × E3m 塔同步机制**：塔目标抬高 = 建造队列拉长，若 29s/座成瓶颈，
  P1 的效果会打折（观察后再考虑 max_on_route=3）。
- 等 E4 再定稿的参数：**P3**（航母节奏）、save_up 阈值（E4 改变航母存活 →
  占比曲线）、P1 上限（航母站悬崖后塔的兜底角色变化）。P2/P4 与地面有关，
  E4 影响小，可先跑。

### E5 实验臂划分（vs Zerg VeryHard/Rush @AbyssalReefLE，每臂 N=3，2026-07-23 更新）

| 臂 | 改动 | 目的 |
|---|---|---|
| B（先行） | P2：pre_fleet per_enemy 0.7 / max 20 | 地面厚度 |
| C | P1：expansion_cannons {min:4, max:12} + //3 | 塔承波 |
| D（待定） | P3：首艘航母矿物让路 | 航母提速 |
| E（后续轮） | P4：advantage_supply 18（与 B 分开跑） | 扩张时机 |

- **基线更新**：A 对照不再复跑，直接用 **e4g-default 的 2-3**（N=5，同图同档，
  CARRIER@653s、终局 CARRIER×6.7 INTERCEPTOR×40.7）作为各臂判负线。
- 判据：胜率 > 二矿存活时长 > 农民存活数 > CARRIER@时间。
- 注：P3（D 臂）原「等 E4 定稿」的前置已消解——E4g 判决微操类挂起，
  但航母性价比评估应基于 default 组数据重做，D 臂细节待 B/C 出结果后定。

---

## 2026-07-23 E4 回归定位：0-3 停摆不是航母微操，是 O15 死锁（已修）

tag=`e4-carrier-micro`。初判疑点（Idle worker 10660 / 10 分钟 1795 矿 / 无
Traceback）指向 bot 停摆，逐帧+三局对比后排除航母微操类：

### 排除项（司令三问）

1. **carrier_offensive 抛异常？** 否——run.log 无 Traceback；且 game_01/02
   停摆时**全场没有一艘航母**（连星门都没有），execute 从未运行；
   game_03 航母正常出战（终局 CARRIER×3 + 拦截机 13 活到最后一帧）。
2. **combat_manager 分派带崩其他兵种？** 否——game_02/03 的 rush 防御、
   叉子生产、开矿全部正常（game_03 甚至打到 3 矿 3 航母）。
3. **异常起点**：game_01 = 241s（基地清零帧）、game_02 = 707s（同）——
   都从 `bases → 0` 那一帧开始冻结，不是全程异常。

### 根因：O15 重建的数学死局

基地清零时 O15 截断攒钱重建 Nexus，但**没有 townhall 就没有资源入库口**
——工人采了矿交不了，收入恒 0，存款（game_01 仅 45 矿）永远到不了 400，
`_ensure_townhall` 等钱、Q5 豁免（有工人+有矿脉）不判负 → bot 空转 400+
秒垃圾时间。game_01 rush 破防（200s 前零叉子，矿太紧）+ 死局 =
表面上的"航母类回归"。

### 修复（2026-07-23）

- `production_plans.nexus_rebuild_viable` 加 `bank`/`nexus_cost` 参数：
  豁免 Q5 必须「有工人 + 场上有矿 + **存款 ≥ 400**」——0 基地=零收入，
  拿不出重建款就是死局，直接 Q5 判负离场（省垃圾时间，也省错误数据）。
- `bot/main.py` Q5 调用点传入 `self.minerals`。
- 单测：更新 + 新增死局用例（viable(10,1500,45)=False）。全量 176 例绿。

### E4 顺带结论（航母微操本身）

game_03 是有效样本：3 矿、CARRIER@610s、终局 3 航母+拦截机 13，
未见微操导致的异常战损；但 0-3 里两局是死局局，**微操验证需要 E4b
重跑补齐 N=3 有效局**。rush 期零叉子（game_01 200s 前）记为观察项，
与 E3f/E3g 同期的叉子节奏对比后再定是否单列。

---

## 2026-07-23 E4b 结果：0-3 与「预留自绞」假设的验证（部分成立，已修）

tag=`e4b-carrier-micro`。game_02 207s 速崩、game_01 二矿 385s 落地 482s 被拆、
game_03 撑到 1121s。司令假设：优势阈值太低（敌 0 可见恒真）→ 预留激活 →
停产自绞。逐帧验证：

### 假设验证（三局时间线）

1. **预留激活线**：game_01 约 265-313s（6 叉=14 supply ≥ 敌 0+12、矿 <400）
   激活；game_03 约 289-385s 激活。game_02 **从未激活**（全程 0-1 叉，
   army supply 2-7 < 12，优势判据不成立）。
2. **激活期间停产**：属实——game_03 预留窗内农民停滞 ~100s（18→20），
   叉子停补（但彼时已达保底 cap 6，本来也不补）；两局扩张均在预留结束后
   落地（385s），机制按设计工作。
3. **game_02 207s 死因**：rush 145s（7 狗）→ 首叉 192s → 207s 敌 14 狗破家
   （1 叉 1 塔）。预留此时未激活，死因是**首波规模方差极值**（同 E3j game_03
   的 17 狗局）+ 矿紧叉慢，与假设无关。

**结论：假设部分成立**——「敌 0 可见 = 优势」语义确实错误（0 可见是未知），
预留窗内停造农民属实（~100s/局，经济被拖）；但它不是这三局的直接死因
（死因同 E3l/E3m 的中段波 + game_02 的首波方差）。

### 修复（2026-07-23）

- `should_expand_dynamic`：优势触发增加 `enemy_army_supply > 0` 前置——
  敌未现身（可见 0）时禁止优势开矿，只留爆仓触发（不依赖敌情）。
  避免「迷雾假优势 → 裸奔扩张 + 预留停产」的自绞链路（E3l 起三轮实证）。
- 附带核查（上次留的观察项）：rush 期叉子节奏与 E3f/E3g 同期基本一致
  （首叉 176-192s，E4b game_01/03 192s 首叉），未见新增变慢。
- **状态**：已修复（单测 177 例绿），待下轮 bench。

---

## 2026-07-23 E4c 结果：0-3 首波验尸（watchdog 杀塔锤实，已修）

tag=`e4c-carrier-micro`。game_01 210s / game_02 261s / game_03 808s，首波即穿，
死得比任何前序系列早——判定回归而非方差。

### 首波验尸（game_01/02 的 120-260s 逐帧）

1. **敌首波**：132-140s 检测（7-8 狗，rush 检测正常），压家 190-210s
   （9-15 狗）。规模与 E3m 存活局同量级，死因在我方防御链。
2. **塔线（核心证据）**：
   - game_01：首塔 ~150s warp-in（花掉 150 矿），~190s 被狗拆（战斗损失，
     非取消）；此后矿 0-170 波动，塔再没起来。
   - game_02：**矿 170-390 闲置的 172-200s 窗口里塔数恒 0**，首塔拖到 ~206s
     才 warp-in——与 O11 watchdog 的「派出→钉点→6s 撤回→重派」循环完全吻合
     （TOWNHALL_TYPES 豁免不含 PHOTONCANNON，司令预判命中）。
   - 对比 E3m：同期矿更宽松或循环窗口更短，塔 181-241s 就位 → 存活。
3. **叉子**：rush 分支未被任何机制截断（rush 单兵种 dict 直接 return，
   不过 save_up/floor）——game_01 零叉是矿被塔+兵营+水晶吃光
   （152s 塔 150 + 140s 兵营 150 + 2 水晶），game_02 首叉 217s 与矿线吻合。
4. **工人拉防**：rush 期造农民已暂停（E3d 六连动④），工人 w 15-19 低位
   但属设计内。

### 修复（2026-07-23）

- `main.py` O11 watchdog：**rush_active 期间一切建造钉点豁免**（塔/兵营工人
  到点等钱是防御链的一部分）。豁免范围定为 rush 期而非防御建筑类，
  因 O11 的原始价值场景（平时 TechUp/扩张钉点）均在非 rush 期；
  扩张钉点的 TOWNHALL_TYPES 豁免保留不变。
- **状态**：已修复（单测 177 例绿），待 E4d 复验。
- **连带记录**：game_01 首塔 ~190s 被拆说明单塔对 7-9 狗不够，
  塔数量/节奏属 E5-P1 数值面，不在本轮修。

---

## 2026-07-23 二分判决：E4-E4d 四连 0-3 罪魁 = carrier_offensive 的 StutterUnitBack（已重写）

- **二分结果**：yml 回退 default（E4e）→ 立刻 1-2，终局 CARRIER×13 +
  INTERCEPTOR×76；带微操类（E4d）→ CARRIER×1，拦截机比航母晚 100+s 出生。
- **根因（读码锤实）**：`StutterUnitBack.execute` 第一行是
  `if cy_attack_ready(ai, unit, target)`——它按武器冷却判定。**航母没有常规
  武器**（拦截机是子单位），cy_attack_ready 对航母恒 False → 永远走
  `KeepUnitSafe` 逃跑分支 → 航母只逃不打、拦截机 100+s 不放。
  tempest 能用是因为它有常规武器。锚点/防空/残血逻辑根本没机会背锅。
- **修复（司令原则：微操是增强不是替代）**：
  1. **放机对齐 GenericOffensive**：射程（8+1.5）内有敌就 `AttackTarget`
     （纯 unit.attack，无任何冷却判定）——输出永不因站位逻辑中断，
     锚点只在「赶路时站哪」生效；
  2. **防空降权改对空威胁圈**：按敌实际对空射程（`air_range`，缺省 7）+2
     缓冲计数，不再全图 -4 吓跑自己；
  3. **锚点滞回**：本舰当前位置恒为候选首位，无更优点不动（防每帧变点打转）；
  4. **残血滞回**：<40% 进 / ≥55% 出（`carrier_logic.wounded_state`），
     防盾回充在 40% 线上反复进出。
- **改动**：`bot/combat/carrier_offensive.py`（重写 execute/_anchor，
  StutterUnitBack → AttackTarget，加 _wounded_tags 状态）；
  `bot/combat/carrier_logic.py`（+WOUNDED_RECOVER_PERC + wounded_state）；
  测试 +3（滞回三态），全量 180 例绿，编译 OK。
- **状态**：yml 保持 default 不动，待司令切回 carrier_offensive 开 E4f 复验。
- **E4f 观察重点**：拦截机应在航母遇敌即放（不再 100+s）；航母不应对
  刺蛇群过度后撤（威胁圈 9 外照打）；残血航母应只撤一次（不乒乓）。

---

## 2026-07-23 E4g N=5 双通道对照判决：微操类挂起，default 转正

### 对照设计

- 双臂同图同档（carrier vs Zerg VeryHard/Rush @AbyssalReefLE），各 N=5，
  唯一变量 = CARRIER 的 combat 类（`--carrier-combat default /
  carrier_offensive`，CARRIER_COMBAT env 覆盖机制首秀）。
- 目的：消除 N=3 噪声，对「重写后的 carrier_offensive 是否转正」做可靠判决。

### 双臂数据

| 臂 | 战绩 | avg 时长 | CARRIER@ | 终局编成(均值) |
|---|---|---|---|---|
| e4g-default | **2-3** | 1236s | 653s | CARRIER×6.7 INTERCEPTOR×40.7 |
| e4g-micro | **0-5** | 713s | —— | 终局航母清零 |

### 判决与处置

- **判决**：重写后的 carrier_offensive 仍显著拖后腿（0-5 vs 2-3，
  时长减半、航母清零 vs 6.7 艘——不是边际差异，是显著负优化）。
- **处置**：yml 的 CARRIER combat 回 `default` **转正**（司令已改）；
  `carrier_offensive` 类代码与 `CARRIER_COMBAT` 开关保留，
  **微操类挂起**，待 replay 级调试（看锚点轨迹/放机帧）定位负优化点后
  再决定是否重启。

### 教训（记入方法论）

1. **关键判决必须 N=5 对照**：E4e(default 1-2) vs E4f(micro 0-3) 只差一局，
   当时已倾向「类仍有问题」，但只有 N=5 双臂才能把 0-5 vs 2-3 的显著性
   坐实——N=3 是噪声带。
2. **时间线误读**：E4f 的 0-3 全死在 550-666s，而航母 823s 才出生——
   微操类当时根本没运行，不可能是死因；但当时（E4d 诊断期）曾把
   「航母不放机」的嫌疑泛化到类整体。教训：**判死因先看嫌疑机制的
   首次运行时间是否在死亡时间之前**。
3. 二分/对照通道（yml 回退、CARRIER_COMBAT env）是本轮最高效的
   排障工具，后续新 combat 类默认先过 N=5 双通道再谈转正。
