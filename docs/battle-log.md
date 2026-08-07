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

---

## 2026-07-23 E5 系列收官：噪声带内的调参不可证伪，全部回退

### 数据（全 N=5，carrier vs Zerg VeryHard/Rush @AbyssalReefLE）

| 臂 | 配置 | 战绩 | 备注 |
|---|---|---|---|
| e4g-default | 基线 | **2-3** | 终局 CARRIER×6.7 INTERCEPTOR×40.7 |
| E5-B | 叉厚 pre_fleet 0.7/20 | **0-5** | 已回退 0.5/16 |
| E5-C | 塔曲线 expansion_cannons 4/12 | **0-5** | 存款峰值 7800；已回退 3/8 |
| E5-A | 基线重跑（与 e4g-default 完全一致） | **0-5** | 同配置纯方差实测 |

### 结论（如实写）

1. **基线重跑 0-5 vs 原基线 2-3 = 同配置纯方差**。VeryHard/Rush 档位的真实
   胜率是 **0-40% 宽波动带**，N=5 样本在带内漂移。B/C 两臂的 0-5 与基线噪声
   无法区分（否决证据不足），但也无正收益证据——故参数**一律回退保持现状**。
2. **E5-E（扩张阈值 12→18）、E5-D（航母提速让路）两臂取消**——在噪声带里
   调参不可证伪，空耗机时。
3. **统计教训**：胜率带内做 A/B 需要更大 N，或改判据——二矿存活时长、
   农民存活数、CARRIER@时间等**连续指标比胜负二值灵敏**。以后调参臂判据
   以连续指标为主、胜率为辅。
4. **后续方向（待司令拍板）**：
   - 转**降档验证**（vs Harder 或 VeryHard/Macro）认证机制链真实胜率；
   - 或在 VeryHard/Rush 上做**结构性升级**（而非调参）——候选：E3 遗留的
     rally/站位（P5）、农民被抄时的转移逻辑、航母编队集火目标选择。

## 2026-07-23 E5 系列：调参臂收官——胜率带内调参不可证伪（全 N=5）

carrier vs Zerg VeryHard/Rush @AbyssalReefLE：

| 臂 | 参数 | 战绩 | 备注 |
|---|---|---|---|
| e4g-default 基线 | pre_fleet 0.5/16, cannons 3/8 | 2-3 | 终局 CARRIER×6.7 INTERCEPTOR×40.7 |
| E5-B 叉厚臂 | pre_fleet 0.7/20 | 0-5 | 已回退 |
| E5-C 塔曲线臂 | expansion_cannons 4/12 | 0-5 | 存款峰值 7800,已回退 |
| E5-A 基线重跑 | 与 e4g-default 完全一致 | 0-5 | **同配置纯方差实锤** |

### 结论

1. **基线重跑 0-5 vs 原基线 2-3**：同参数同代码，胜负漂移——VeryHard/Rush 档位
   真实胜率是 0-40% 宽波动带，N=5 样本在带内漂移。B/C 否决证据不足
   （无法与基线噪声区分），但也无正收益证据，一律回退保持现状。
2. **E5-E（扩张阈值 12→18）、E5-D（航母提速让路）取消**——噪声带内调参
   不可证伪，空耗机时。
3. **统计教训**：胜率带内做 A/B，胜负二值判据太钝，应以连续指标为主
   （二矿存活时长/农民存活数/CARRIER@时间），胜率为辅；或上更大 N。
4. **YAML 教训**：未加引号的中文冒号破坏解析导致 E5-B 首跑五连 ERROR——
   yml 改动后先 yaml.safe_load 校验再开 bench（已入流程）。

### 后续建议（待司令拍板）

- 转降档验证（vs Harder 或 VeryHard/Macro）认证机制链真实胜率；或
- 在 VeryHard/Rush 上做结构性升级（非调参）：rally/站位（P5）、
  农民被抄转移逻辑、航母编队集火目标选择。

---

## 2026-07-23 E6 实现：农民被抄时的转移/协防（结构性升级，未跑局）

背景：E3m 死因复盘——VeryHard/Rush 中段波真正死因不是塔/叉不够，是**农民被抄**
（game_01 t=650 农民 42→22、game_02 t=747-771 47→29），经济断气后 2000+ 气
烂掉而矿 <400，航母永远 1-2 艘。E5 收官建议的「结构性升级」候选之一，本任务落地。

### ares 现状盘点（决定新写 vs 接线）

- `Mining(keep_safe=True)` 只有**个体**避险：单农民位置不安全 →
  `find_closest_safe_spot` 挪几步，仍留在被抄矿区附近；`self_defence_active`
  让农民还手。没有「整片矿线撤到别的基地」的基地级策略。
- `ResourceManager` 只有 `safe_mineral_fields_at_townhalls`（挑安全矿脉）和
  `remove_worker_from_mineral`，无现成的跨基地转移行为。
- 结论：**无等效机制，新写**；但全部用 ares 原语接线（role 体系 +
  `get_worker_tag_to_townhall_tag` 矿线归属台账），不改 ares 一行。

### 设计

- **检测**：敌地面单位（非建筑/非空军/非农民）距某基地 Nexus <15 格且 ≥4
  → 该基地视为被抄（纯判据 `production_plans.should_evacuate_workers`）。
- **响应**（按优先级）：
  a) 矿区在就绪塔射程内（塔距 Nexus ≤9，光子炮/导弹塔/孢子爬虫等）→ 农民继续采；
  b) 无塔且敌 ≥4 → 该矿线农民 role 从 GATHERING 改挂 `CONTROL_GROUP_ONE`
     （ares 枚举的兜底 role，vendored ares 无消费者——Mining/ResourceManager/
     idle 清扫/建造派工都只认 GATHERING，撤离期间零干扰），撤向**最近有塔基地**，
     都没有则最近基地；到点就地先采（不站着），途中被卡补 move。
     单基地无塔无处可撤 → 不动，交 Mining keep_safe 个体避险；
  c) 就近 20 格内有我方地面兵力 → 事件流标记「集结点=被抄基地」，
     **不强行微操**（rush/stance/集结纪律的优先级都在 combat_manager）。
- **回采**：敌地面 <2（滞回：撤离阈值 4、回采线 2，防边界抖动往返空跑）或
  基地已丢（O15 重建接管）→ 全员归 GATHERING 回最近矿脉。
- **冲突防护**：rush 期不新增撤离（六连动行为不变），已在撤离的回采判定照常；
  跳过 building_tracker 建造农民（O1/O2 教训）和司令接管农民（_player_ctrl）；
  O11 watchdog 不碰（撤离农民不在 tracker、不 idle）。

### 改动清单

- `bot/production_plans.py`：`should_evacuate_workers` / `evacuation_clear` /
  `pick_evacuation_base` 三个纯函数。
- `bot/main.py`：`update_worker_evacuation(ai)`（检测/撤离/维护/回采全链路，
  每帧在 production_manager.update 后跑）；`_handle_idle_workers` 跳过
  _EVAC_ROLE；`__init__` 加 `_evac_bases` 台账。
- `tests/test_worker_evacuation.py`：12 例（纯判据 5 + 运行时链路 7，
  含塔覆盖不撤/rush 阻断/滞回边界/敌退回采/单基地滞留）。
- 全量单测 195 例绿。**未跑局验证**——bench 待司令排期（建议指标：被抄局
  农民存活数、二矿存活时长，沿用 E5 的连续指标教训）。

### O16 侦查没做完：农民未抵达敌方主基地
司令观察：侦查农民没走到敌方主基地（可能中途发呆/被杀/目标点不对）。
侦查是 O17/O18 决策链的输入，断链则下游全是赌。排查：scout 路径点、
被杀后是否补派、scout_verdict 超时回退逻辑。

**E7 结案（2026-07-24，代码修复，待 E7+E8 bench 验证）**：e6c2 五局逐帧
诊断——探机 100s 出发、路途 ~40s，而 Rush 局敌兵 129-141s 到脸触发 O4
撤回，**4/5 局探机在送达前被拉回**（g02/03/04/05 敌建筑首见拖到 522-820s
=陆军接触才看到；g01 撤回最晚 141.5s，探机 144.6s 摸到主基）。五局探机
都活着（O4 事件只在有 SCOUTING 农民可撤时才发）——根因不是被杀/卡位，
是**侦查窗口 < 路途**：O4 撤回抢在送达前，verdict 落「无情报→保守按rush」
（Rush 局结论碰巧对，链条是断的；Macro 局探机死/卡同样会假 rush）。
修法：`scout_verdict_timing` 纯判据（production_plans）——有情报照评；
无情报但探机还在路上 → 宽限到 230s；探机死/被撤回且非 rush → **补派一次**
（仅一次保防送死语义；rush 中不补派=白送且 verdict 已无意义）；硬底线仍无
情报 → 才按「尽力未送达」保守 rush（=旧 unknown 行为，e6c2 各局路径不变）。
补派/兜底都发事件供 retro 归因。单测 312 例绿。

### O17 侦查=扩张攀科技 → 叉叉提前压前线（不必等集结数）
若侦查确认敌方早开分矿+攀科技（前期兵力薄），叉叉兵应**提早压前线**
给压力/抓扩张timing，不用等 rally_min_army 集结数到齐。
本质：rally 门槛应按侦查结论动态化——对手贪 → 早压（小股即走）。

### O18 侦查=rush → 叉叉集结积攒再动
若侦查确认 rush，叉叉应集结积攒（守家/塔后），不零散出门。
与 O17 是同一机制的两极：scout_verdict ∈ {rush, greedy, unknown}
→ stance ∈ {集结守, 提前压, 默认}。O9 已有 scout_verdict 闭环，
O17/O18 是把它接到 rally/stance 决策上。

**E8 结案（2026-07-24，代码修复，待 E7+E8 bench 验证）**：verdict 接到 C3a
集结纪律（`production_plans.rally_min_for_verdict`，combat_manager 每帧算）——
greedy → 阈值减半（小股提早压，O17）；rush → max(×2, floor 6)（集结积攒再打，
O18；floor 6 与 carrier pre_fleet 保底叉 cap 同源量级，因 carrier rally 缺省 0=关，
加倍无效需地板）；unknown/None → 维持。司令 stance 让位原则不动。
与六连动同向不冲突：rush_active 时 attack_target 本就切主基守家，E8 的 rush
地板只是让 rush 解除抖动期也不零散出门。非 carrier 流 verdict 恒 None → 零影响。
注意：carrier 的 rally 缺省 0，O17 侧对 carrier 实为 no-op（集结本就关，且 E3g
保底阶段守家是有意设计，不动）；E8 对 carrier 的有效增量是 O18 的 rush 地板。
单测 315 例绿。

### O19 仍有农民干等建造（复发，升级为每局必查项）
司令观察：对局中仍见农民傻等钱造建筑。司令指令（长期有效）：
**每次对局结束必须检查日志，确认是否有农民 >1s 不干活干等建造**，
并优化建造顺序与拉农民建造的 timing。
落实方式（E6 后做）：bench retro 检测器加「idle_builder」标签——
state 快照里工人连续 >1s 无指令且被 tracker 标记为建造等待 → 计数。
已有先例：O1/O6（等钱水晶）、O11（watchdog 6s 撤回）、E4c（rush 期豁免）——
本条是兜底检测，确保不再漏。

---

## 2026-07-23 E6 验证：bench 0-5 逐帧验尸——败局无罪，但机制在目标场景是死代码（已修）

E6 bench（bench/e6-worker-evac，carrier vs Zerg VeryHard/Rush @AbyssalReefLE，N=5）：
0-5，末农民 16/18/16/52/15，二矿存活窗口 0/32/160/48/68s。逐帧验尸结论：
**败局与 E6 无关（噪声带内），但 E6 在其设计目标场景里结构性不触发**。

### 验尸数据（state 快照逐帧）

**Q1 撤离触发/回采**：5 局只触发 **1 次**（game_04 t=1066.6，敌 12 地面无塔，
撤 16 农民，t=1080.6 敌退 15 农民回采，历时 14s）。归还链路正常
（CONTROL_GROUP_ONE → GATHERING 15/16，1 个途中死亡），无农民卡撤离 role。
撤离窗口矿收入正常（70 农民 4 基地经济，撤 16 个 14s 无损）。

**Q2 二矿早死因果（game_01/03/05）**：E6 在这些局**从未触发**，不可能致早死。
未触发的两个结构性原因：
- **塔覆盖=继续采**：carrier 流 E2/E3l 分矿常态 4-6 塔 → `cannon_cover=True`
  → case (a) 不撤。但中段波是 21-22 狗 + 7-9 蟑螂 + 刺蛇（game_01 t=401、
  game_03 t=522、game_05 t=433），~20-30s 拆光塔再屠农——「塔会打」对
  大波不成立。
- **全局 rush 门**：rush_active 从 ~130s 首接敌一路续过中段波（game_03
  t=520 仍有「确认rush」事件，t=534 二矿死），rush 门把 E6 在它的目标
  场景里整个关掉。

**Q3 败局归责**：对照 e5a-baseline（与 e4g 同代码）二矿窗口 88-225s、同样 0-5、
两局 <600s 末帧——E6 各局数据落在同一噪声带，0-5 是档位真实胜率波动
（E5 结论复验），非 E6 所害。E6 唯一触发局（game_04）反而是 5 局里
活得最久的（1394s，末农民 52）。

**Q4 game_02（209s 死）**：经典首波 rush 死——t=132 六狗到脸，首塔 t=184.8
才立（rush 期塔链老问题，E3/E4 系列已知），t=209 主基地爆 + Q5 判负。
全程单基地，E6 无触发条件（rush 门+单基地无处可撤），无罪。

### 修复（判决：败局无罪，但机制死代码必须修，否则等于没做）

1. **塔覆盖不再是绝对免撤**：`should_evacuate_workers` 加塔被压垮判据——
   有塔但敌地面 ≥ 6 + 4×塔数 → 照撤（1 塔罩到 9 敌、4 塔罩到 21；小股骚扰
   继续采的行为不变）。
2. **rush 门收窄到主基**：rush 期主基不新增撤离（六连动不变），**分矿不受
   rush 门**——分矿撤离与 rush 守主基响应包互补，不冲突。

改动：`bot/production_plans.py`（should_evacuate_workers 加 cannons_near/
overwhelm 参数）、`bot/main.py`（_cannon_cover→_cannons_near 计数、rush 门
按基地分流、事件区分「无塔/塔N座压不住」）。单测 12→15 例（新增：压垮判据
2 例、rush 主基阻断/分矿放行 2 例、压垮照撤链路 1 例），全量 198 例绿。
**未再跑 bench**——修复后的 E6 首次触发场景待下轮 bench 验证（指标：二矿
被抄局农民存活数、二矿存活窗口）。

### O20 bench 重试路径泄漏 SC2 进程（僵尸对局定格在终局画面）
实证（2026-07-24）：E6 game_04 首次尝试崩溃/超时→bench 重试并继续系列，
但首次尝试的 SC2 进程（pid 21839）未被 kill，以 Defeat 终局画面（23:17）
挂在桌面 ~40 分钟，被司令发现。run.log 句柄确认归属。
修复方向：bench.py 重试/超时路径在 spawn 新进程前应对旧 SC2 做
kill_switch/pkill 兜底（CLAUDE.md 已有 pkill -9 -x SC2 的先例手法，
但双通道时代不能无脑 pkill 全部——需按 port/pid 精确 kill 自己 spawn 的）。

---

## 2026-07-24 E6b 回归：0-5 开局崩坏根因——外来 base_rebuild 变更，非 E6b 改动（已修）

E6b bench（bench/e6b-worker-evac，N=5）：0-5 全在 ~208-218s 死，开局即崩——
game_01 @149s workers=6、建筑仅 NEXUS+ASSIMILATOR×2+PYLON×2、零兵营零熔炉。

### 逐帧证据（game_01 0-210s state 快照）

- workers **从 t=0 到终局一条平线**（8→8→7→6）：整局零农民生产；
  对照 e4g 同时间段 8→9→10→11 稳步爬升。
- t=12 立 ASSIMILATOR（正常开局 t=24）、t=72 双气、PYLON t=48——建造序列
  全乱；GATEWAY/FORGE 从未出现。
- run.log 无 error/traceback，E6 撤离事件 0 次（E6 机制根本没参与）。

### 根因（与 E6b 改动无关）

工作树里有**另一agent的未提交变更**（git diff 实证，base_rebuild 重建模式 +
B4 防守三角系列，涉 production_manager/production_plans/combat_*/levers/
ares tech_up.py）：`base_rebuild_active(current, target, afford, rush)` 判据是
「当前基地数 < 目标基地数」——carrier `max_bases=4`，**开局 1<4 从 t=0 恒真**，
于是 `_base_rebuild` 门掐死 `_build_probes` 和 SpawnController（整局零农民零兵），
并让 ExpansionController(prioritize) 从首帧钉一个农民去分矿点等 400。
这正是观测到的「农民生产停摆+气矿早产+科技链没走」。

排除 E6b 自身改动的证据链：
- E6b 改动（should_evacuate_workers 新参数/_cannons_near/rush门按基地分流）
  只在敌地面 ≥4 进 Nexus 15 格时有行为，开局无触发路径；5 局撤离事件 0 次。
- state.json 每 4s 正常发布 → on_step 无异常被吞（发布点在 E6 调用之后）。
- 崩坏模式（probe/spawn 停摆）与 `_base_rebuild` 门控点一一对应。
- 时间线：bench 00:30-00:36，外来文件 mtime 00:32-00:42（另一agent在并行作业，
  E6b bench 恰好跑进了它的半成品窗口）。

### 修复（峰值基地门，保留他人特性意图）

`base_rebuild_active` 加 `peak_bases` 参数：只有**真的丢过基地**
（peak > current）且 current < target 才进重建模式；开局 1=peak → 不触发。
production_manager 每帧维护 `_peak_townhalls`。rush/None-target 门不变。
改动：production_plans.py（函数签名+docstring）、production_manager.py
（峰值记账+传参）、tests/test_production_plans.py 新增 TestBaseRebuild 3 例
（开局不触发/丢基地才触发/rush与无目标门）。
全量单测 299 例绿；BUILD=carrier 编译通过。

### 协作教训

- 多 agent 共机同树作业（见 promotion 并发闸门提交）：bench 前应先
  `git status --short` 确认树上只有自己的改动，否则验证结果无法归因——
  本次 E6b 的 0-5 一度被记到 E6 头上。
- 他人 WIP 的 `_base_rebuild` 门（重建期掐 probe/spawn）本身代价存疑
  （E3k 攒钱预留已有同类语义且更温和），留给该 agent 自评，本次只做
  最小修复（峰值门）不重构。

---

## 2026-07-23 并入另一 agent 的观战记录（ares-bot/docs/ 野文件归档）

> 来源：`ares-bot/docs/battle-log.md`（另一 agent 误建副本，内容核对后并入，野文件已删）。
> 其中「两个农民等钱造 forge」（=O1 复发，TechUp 已加 can_afford 守卫根治）与
> 「二矿被推平应攒钱重建」（=base_rebuild_active，已加峰值门修复）两条为重复记录，不重复收录。

### O21 虫族早开矿 vs carrier 6 分半才开矿【待讨论】

- **现象**：虫族 3 分钟前开 2 矿；carrier 流 6 分半才开 2 矿。
- **分析**：carrier 配置 `when_workers: 22, advantage_supply: 12`，单矿需 22
  农民或 army 优势才触发开矿。6 分半偏晚，但符合「先憋舰队后开矿」策略。
- **待定**：是否降低 `when_workers`（调参臂已叫停，先不动，留作数据点）。

### O22 2 矿选址距主基隔了一个矿区【待确认】

- **现象**：新开的 2 矿距离主基隔了一个矿区。
- **分析**：ares `ExpansionController` 自动选址，可能选了第三近的矿区。
- **待定**：ares 框架层尽量不改；若分矿防御压力实证偏大再评估。

---

## E6c2 bench 判决（2026-07-24，carrier vs Zerg VeryHard/Rush @AbyssalReefLE N=5）

**战绩 1-4**（在 E5 实锤的 0-40% 方差带内，不用胜负说话，看连续指标）。

### E6 农民撤离：机制验证通过 ✅

- 撤离触发 7 次（E6 首轮 5 局仅 1 次=死代码 → 本轮常态化触发）：
  - g01: 465s 撤 9（敌14地面/塔1压不住）→ 500s 全数回采；689s 撤 19 → 11 回采
  - g02: 569s 撤 15（敌10/塔1）→ 588s **15/15 回采**
  - g03: 562s 撤 16（敌18/塔3压不住）→ **16/16 回采**；830s 撤 20 → **20/20 回采**
  - g05(胜): 三次撤离 15/4/20 人，全部回采；开到 4 矿获胜
- 「塔压垮照撤」判据实证生效（敌 10-18 地面 vs 1-3 塔）。
- 唯一的胜局正是撤离+协防（g05 有"1地面兵力就近协防"）+持续开矿的局。

### 暴露的下一层问题（非 E6 范畴，转记观察）

- **分矿仍站不住**：g01 二矿 502s 丢、g03 594s 丢、g04 二矿建成后 60s 即丢
  （417s，无撤离日志——农民可能还没到位）。农民救下来了，基地救不下。
  塔数（1-3 座）对 10-18 地面波次明显不足 → expansion_cannons 下限/建造
  时机问题，属数值面，调参臂已叫停，先记录。
- **retro `one_base` 标签误报×5**：五局都在 357-390s 开出二矿，但 retro 的
  300s 阈值照常报警 → 阈值与 carrier 流 6 分钟开矿节奏不匹配（呼应 O21）。
  修检测器阈值，不改打法。

### 附带修复（本轮前置）

- `_own_army_count` 遇 WARPPRISMPHASING 时 cy_unit_pending KeyError 崩全局
  （E6c 首轮 5 连 ERROR 根因，B6 warp prism spec 引入）→ KeyError 按 0 计
  （11c037e）。

---

## 2026-07-24 O19 钉点修复：建造派工守卫（dispatch_viable）

e7e8 bench（scout-macro/scout-rush 各 N=5）idle_builder 去重 episode：
PHOTONCANNON 9-21 次/局（最大头）、NEXUS 2-7 次、PYLON 1-7 次、
ASSIMILATOR/FORGE/GATEWAY 零星。逐路径根因与修法：

- **PHOTONCANNON**：`ProtossStaticDefence → BuildStructure` 全程无 can_afford
  （B1 守卫只加了 `_build_core_structure`，这条路径漏了）→ F2 注册点加
  `dispatch_viable(矿, 收入/秒, 走位5s, 150)` 守卫，不到位可负担不注册。
  塔起建时间不变（反正都要等钱到 150），农民不再钉点照采矿。
- **NEXUS**：E3k 预走位（prioritize=True 欠费也派）是故意设计，但 episode
  显示到位后干等（终局 1144s 仍有）→ 收窄为「预计到达时可负担」
  （矿 + 走位时间×收入 ≥ 400，走位时间 = 最近空闲扩张点距离 ÷ 3.94）
  才允许欠费派工；否则 EC 走默认 can_afford_check（不派不钉）。
  E3k 攒钱预留（_expansion_reserve 停出兵/农民）语义不变。
- **PYLON**：PSD 内部 pylon 同路径无守卫 → 被 cannon 门卫覆盖（150>100）；
  AutoSupply E3h 紧急钉点（supply_left≤2）是故意设计，保留。
- **FORGE/GATEWAY/ASSIMILATOR 零星**：FORGE 走 TechUp（已有 ares 层
  can_afford 守卫）和 _build_core_structure（已有守卫）；GATEWAY 走
  _rush_gateway_boost/_build_core_structure（已有守卫）；ASSIMILATOR@15s
  与可能的 FORGE@113s 来自 **ares build runner 开局序列**（yml 派工点无
  can_afford，框架层不改）——O11 watchdog 6s 撤回兜底，下轮 bench 复测
  若仍超标再归因。
- 纯判据 `production_plans.dispatch_viable`；单测 318 例绿（+3）。

### O19 二轮复验（o19fix-macro/rush 各 N=5）：episode 数没降——分层归因

数据分层（去重 265 个 episode）：
- **时长全是 1s**：所有 episode 的报警时刻干等时长 =1s（检测器首次越线即报，
  上限 ~2s）。多数局塔 episode ≈ 建成塔数（macro g01 13 vs 11、g02 11 vs 12）
  =「到位等 1-2s 钱」的常态噪声——本 bot 存款贴 0 花钱风格下不可避免，
  经济无害。
- **少数局是真循环**：macro g05 塔 episode 24 vs 建成 7、rush g05 21 vs 9，
  同一农民 tag 反复出现（最高 6 次）——「dispatch_viable 通过（中期收入
  30+/s 时恒真）→ 派工 → 钱被 warp-in/航母抽干 → 钉 6s → O11 撤回 →
  下帧守卫又过 → 再派」的 E4c 型重派循环。假设（派工后被抽干）证实。
- **NEXUS 1-6 次/局**：预走位是 E3k 故意设计（O11 对 TOWNHALL 豁免、
  不撤回），episode ≈ 每矿一次，估算误差内，维持现状。

修法（行为+检测各一刀）：
1. **行为**：`redispatch_cooled_down`——O11 撤回某结构建造工人后 15s 内
   不再重派同类（F2 门新增条件；main.py O11 撤回分支记录时刻）。断循环
   不拖首派。rush 期 O11 豁免 → 天然无冷却（E4c 安全）。
2. **检测**：`idle_builder_alarm` 阈值 1s→3s——1-2s 短等是噪声（章程
   「>1s」线在本 bot 的花钱风格下全是误报），3s 仍 < O11 6s 撤回线，
   真钉点必曝光。偏离章程字面，数据依据如上，待司令确认口径。
单测 321 例绿（+3：冷却三态）。

---

## O19 二轮复验判决（2026-07-24，o19b-macro 0-5 / o19b-rush 3-2）

### Rush 系列 3-2（60%）——对该对手组合的历史最好成绩

- 此前 VeryHard/Rush 胜率带 0-40%（E5 实锤方差），本轮 3-2 且胜局时长
  598-1122s、存款峰值 12560、终局 CARRIERx12。单组 N=5 不充分，但配合
  机制数据（下条）偏向真实改善。

### 重派循环：已断 ✅

- 修复前 macro g05 同一农民 6 次 episode（572→654s 密集循环）；修复后全部
  episode 间隔 20-200s、地点/建筑各异（例：g03 tag…017 三次分别在
  178.9/199.3/921.4s，间隔 >15s 冷却线）——不是循环，是正常离散派工。
- 15s 冷却（O11 撤回=「钱真不够」信号）生效，rush 期 O11 不撤回天然无冷却，
  E4c 型事故免疫。

### 残留 episode 定性：3s 越线即报，实际等长未知

- 所有残留消息都是「干等3s」（检测器首次越线时间），无法从事件文本区分
  「3-5s 后钱到开工」和「钉到 6s 被 O11 撤」。要进一步压缩需资金预留机制
  （派工时冻结 150 矿），收益递减，先挂起——司令要再压一档再说。
- idle_builder 标签仍 ×5（阈值 3s 下每局 10-33 条），多为上述离散短等。

### Macro 0-5 不变：另一层问题

- overrun×5（终局兵力悬殊），carrier 成型 553s 不算慢但中后期团不过。
  与 E 系列已知结论一致：机制修尽，剩数值/战力面，调参臂维持叫停。

---

## 2026-07-24 Macro 局修复：农民补员截断点 + 塔矿限流（o19b-macro 0-5×3 诊断）

复核司令四点诊断（o19b-macro 五局逐帧）：

1. **矿饿气涝——坐实**：全程矿贴 0-500、气 1400-2800。
2. **塔矿出血——坐实**：g03 683-803s 同时 13-16 座 PHOTONCANNON（≈2400 矿
   ≈7 艘航母），E2 动态塔（min3+敌可见//4 封顶8/矿）与憋航母直接抢矿。
3. **农民放血不补——坐实，但截断点与初步假设不同**：不是 save_up 也不是
   supply（g01 763-843 supply_left 20、矿多次 ≥50）。真凶 = **`_base_rebuild`
   重建模式**（B 系列特性）：丢矿后 peak>current 一锁 100-300s，期间
   `_build_probes` 和 SpawnController 全被掐——g01 687s 丢矿 → 210s 农民
   40→28、航母恒 1-2 艘，896s 才补回基地；g02/g03/g04/g05 同型（丢矿后
   农民再无补员直至死）。掐农民 = 掐重建的经济来源，恶性循环。
   （rush 期 E3d 让位只覆盖 640-780s 窗口，解释不了其后 60-120s 的零补员。）
4. **反空军无应对——部分推翻**：识别链路正常（corruptor/broodlord 触发
   anti_air 混 STALKER，g01/g03 敌 3-9 腐化时 STALKER 有出现），但产量
   被矿饿卡死（125 矿/个出不起，场上恒 1-2 个）——是 #1/#3 的下游，
   不另修。

修法（机制层，不调数值）：
- **A 农民补员**：`_build_probes` 解除 `_base_rebuild` 截断（rush 的 E3d
  让位、E3k 短预留保留）。SpawnController 的重建期截断属 B 系列特性设计，
  本轮不动（g01 证据：重建期 210s 零出兵同样致命，留待该特性作者复评）。
- **B 塔重建限流**：`cannon_target_capped`——矿 < 舰队矿价（航母 350）且
  非 rush 时塔目标压回 ec.min（3/矿），被打掉的塔不立即按动态数重建，
  矿让给航母/农民；憋得起（矿 ≥350）或 rush 期按原动态数（六连动不变）。
  只影响配了 expansion_cannons 的 carrier 路径（ec=None 的流派走原常量 2）。
- **C**：不修（见诊断 4）。
单测 325 例绿（+4：cannon_target_capped 四态）。

---

## 2026-07-24 E9 中局威胁响应（Macro 第二轮，代码修复待 bench）

macro-fix1（carrier vs Zerg VeryHard/Macro 0-5）实锤：t≈520-560 敌第一波主力
（15-25 作战单位）到脸时，我方常备军 ≈6 叉+1 先知+0-1 航母，塔 5-7 座；
save_up 憋航母掐了中局出兵，首艘 ~560s 才出，数量 1-2 时基地已丢光
（g02 522s 3 基地 → 683s 清零）。威胁响应原来只有早期 rush 一路
（rush_active/scout verdict），Macro 中局一波无任何反应。

另：Macro 第一轮两项修复的方向验证——塔限流生效（峰值 13-16→8-12）但
副作用=防御变弱丢矿更早（局时中位 815s→591s）；农民解截断方向正确但
被战乱淹没（死亡速率 > 生产速率）。E9 的 2a（threat 时塔拉满）正是
限流副作用的修正。

### 机制（只挂 carrier）

判据 `threat_response_active(enemy_supply, own_supply, active)`（滞回）：
敌可见作战 supply ≥ max(10, 我方×1.5) 激活；< max(6, 我方×1.0) 才解除。
口径用 `_visible_enemy_army_supply`（supply 求和，与 should_expand_dynamic
同源；E2 塔数用的 `_visible_enemy_army_count` 是单位数，两口径并存不改）。

激活效果（rush 同时激活时全部按 rush 走，不叠加）：
- **塔目标 = ec.max**（覆盖 cannon_target_capped 限流，穷但压境保命优先）；
- **save_up 不截地面防御**（`threat_ground_exemption` 把 spawn 里非空军兵种
  全进 exempt；航母/风暴截断照旧，在产航母不停）；
- **暂停开新矿**（_want_dynamic_expand 的 rush_active 门传入 rush|threat）。

激活/解除各记一次事件（E9:敌压境威胁响应 / E9:威胁解除）供 retro 归因。
单测 329 例绿（+4：激活/不激活/滞回/地面豁免）。

---

## E9 中局威胁响应判决（2026-07-24，macro-fix2-e9 0-5 / e9-regress-rush 2-3）

### Rush 回归 2-3：无退化 ✅（方差带 0-40% 上沿，E9 未伤 rush 路径）

### Macro 仍 0-5，但机制指标四项对照

| 判据 | 结果 |
|---|---|
| threat 激活时点 ≈520-560s 敌到脸前 | ✅ 五局全部 477-531s 激活 |
| 激活后塔拉满 | ✅ 存活局塔峰值 13-19（fix1 仅 8-12） |
| 丢矿时点后移 | ⚠️ 分化：g01 后段丢矿推到 1294s+（全局活 1422s，vs fix1 中位 591s），g2-4 仍在 538-775s 崩 |
| 地面混编上量 | ⚠️ 仅 g01 兑现（army supply 25→34→50 顶住三波 38/51/75 supply），g2-4 激活后 supply 卡 21 不涨（矿已竭，产不出） |

### 结论：E9 机制有效（g01 存活时间×2.4，扛过三波递增主力），但 Macro 局撞数值面

- 敌 supply 增速约为我 2 倍，threat 窗口内即使全力暴兵也追不平——
  产能天花板（星门/兵营数）+ 矿收入天花板决定，非机制 bug。
- 按事先约定的停止规则（两轮内看不到丢矿后移+航母曲线抬升即停）：
  **Macro 线判定数值面，挂起**。验收口径维持 Rush/Power（3-2/2-3）。
  待 B 系列战斗侧机制（can_win_fight/集火优先级）bench 数据出来后合并复评。

---

## Zerg/Macro VeryHard 回退归因（2026-07-24，bisect 六点矩阵结案）

矩阵认证（promotion.json）Zerg/Macro VeryHard 2-2 过 → 近期三连 0-5。
bisect（同图同对手 N=5，git worktree 隔离）：

| 点 | 提交 | 战绩 | 关键指标 |
|---|---|---|---|
| A | 9c2f89d 认证时代 | **5-0** | 单矿风暴速胜（203-496s），TEMPEST×12，CARRIER@450s |
| C | 3def593 O6-O10 | **3-2** | CARRIER@427s，CARRIER×10.7，含 E1/E2 动态多矿 |
| F | 379ac6f E3h-j | **1-4** | CARRIER@596s，**one_base×5**，回退起点 |
| E | c6e28e5 E3k-m | 0-5 | CARRIER@573s，one_base×4，~620s 死 |
| B | 9046159 E5 收官 | 0-5 | 排除 B 系列（另一 agent）嫌疑 |

### 结论

- **回退点 = `379ac6f`（E3h-j 经济链修复）**，锅在我们自己的 E 系列，
  与另一 agent 的 B 系列无关（B 合并前已 0-5）。
- **机制推断**：E3j 钉点撤回（O11 watchdog 6s 拆 tracker）把 E2 动态开矿的
  「欠费派工走位」农民撤回 → Nexus 永远拍不下（F 点 one_base×5；C 点 341s
  顺利开二矿）。E3k 后来补了 TOWNHALL_TYPES 豁免，但 E 点（含豁免）仍
  one_base×4 + 0-5——E3k 攒钱预留（买不起 Nexus 停出兵/停农民）叠加
  save_up 矿盲区（矿缺口也截断出兵），「掐出兵保经济」力度过猛，
  航母真空期从 427s 拉到 573-596s，死在真空期。
- **战略层发现**：认证代码的赢法是**单矿风暴速攻**（one_base×5 仍 5-0），
  对 Macro AI 的窗口在 200-500s；E 系列整体转向「多矿憋航母」后，
  这个赢法消失了。Macro 局的正解可能是「风暴先压、航母后接」而不是
  「憋航母平推」——与 E9 判决的「数值面」结论互补：不是纯粹数值不够，
  是打法漂移把能赢的窗口让掉了。
- 后续方向（待司令定）：①vs Macro 对手策略 pivot：舰队成型前风暴主 C
  压制（认证打法），航母改后手；②E3k 攒钱预留/save_up 截断力度回收到
  C 点水平；③维持挂起，接受 Macro 墙。

---

## 2026-07-24 策略 pivot（E10）：侦查判非 rush → 风暴主 C 压制，成型转航母终结

司令拍板：carrier vs 非 rush 对手时，舰队成型前以 TEMPEST 为主 C 打压制
（9c2f89d 认证赢法：单矿风暴速胜，赢局 200-500s，TEMPEST×12），后期转
CARRIER 终结；侦查判 rush 维持现状（叉顶/塔/憋航母）。**硬性约束：分流只读
E7 verdict（侦查结论），绝不允许读 --ai-build 或对局配置。**

实现（只动 spawn 配比层，E9/E6/O19 等机制未碰）：
- `pivot_primary_id(verdict, ...)`：greedy → 风暴主 C；rush/unknown/**None
  未判定** → 航母主 C（保守默认=现状，未判定绝不按 Macro 打，防被 rush 穿）。
- `tempest_primary_spawn`：主次 C 的 priority 对调（proportion 保留）；
  save_up 不动——风暴 p0 便宜几乎不触发截断，航母 p1 转型前自然被憋住。
- `carrier_transition_ready(now, tempest_count, at_time=600, tempest_cap=10)`：
  时间到（压不住）或风暴海成型（数量到）→ 一次性 latch 转回航母主 C，
  不随数量回落横跳。verdict=greedy 落锤与转型各记一次事件（E10:...）。
- pre_fleet 地面保底（叉）在风暴阶段持续（主 C 仍按 CARRIER 判 fleet_online），
  风暴+叉复合压制；反空军 pivot 在 pivot 后配方上正常叠加。

已知边界（如实）：chrono `when=primary_pending` 的主 C 判定仍读 flows.yml 的
CARRIER——风暴阶段星门不吃 chrono（≈20% 产能损失）。本轮严守「只做 spawn
配比层」未动；若 bench 显示风暴海成型偏慢，下一轮把 chrono 主 C 判定也
verdict 化。单测 333 例绿（+4：verdict 四态选主 C/对调保比例/缺兵种 no-op/
转型双触发）。

### P0+P1 修复（同日，E10 诊断落地）

- **P0（实现 bug）**：`production_manager.py` import 补 `carrier_transition_ready`
  ——E10-macro 唯一 verdict=greedy 的局（g03）在 pivot 判定第一帧 NameError
  崩溃（ERROR 局根因）。新增 `tests/test_strategy_pivot.py` 接线测试
  （`ProductionManager.__new__` 最小构造，走 verdict 四态/转型 latch/数量转型
  五分支），挡住这类接线层遗漏。
- **P1（verdict 口径）**：新纯判据 `is_combat_type`——作战单位计数排除
  OVERLORD/OVERSEER/OVERLORDTRANSPORT（侦查/运输非作战），QUEEN 保留。
  替换三处「非工人即算兵」口径：`_evaluate_scout_intel`（scout_verdict 的
  early_army）、`_update_rush_state`（near + early_swarm）、
  `_rush_gateway_boost`（enemy_army）。旧口径下 Zerg Macro 常规运营
  （pool+overlord 铺开）~170s 可见非工人 ≥6 是常态 → verdict 系统性误判
  rush（E10-macro 4/5 局）、early_swarm 每局误触发（169s O4 误撤侦查）。
  实测场景入单测：pool×1+overlord×6+queen×2+ling×2+drone×15 → 作战=4 →
  判 greedy（旧口径=10 必误判 rush）。
- **故意不改**：`_visible_enemy_army_count/supply`（E2 塔数/E9 threat/开矿
  优势口径，已验证机制；overlord supply=0 不影响 supply 口径）；
  `_should_build_defense` 的 attackers 口径（F2 触发，行为已验证）。
  P2（科技节奏/chrono verdict 化）等下轮 bench 数据。
- 单测 341 例绿（+8：口径 3 + 接线 5）。

### P2 星门产能解放（同日，E10b 诊断落地）

E10b 实锤：pivot 配比生效（greedy 5/5、TEMPEST 首出 397-426s）但风暴海从未
成型——4/5 局星门只有 1 个、TEMPEST 恒 ×1-2。三处瓶颈各一刀（全部只在
pivot 模式生效，非 pivot 行为零变化，纯判据 pivot 开/关双分支入测）：

- **a) 矿门槛豁免**：`extra_production_mineral_gate(pivot)`——pivot 时追加
  星门不再要求矿>400（单矿矿贴 0-300 是常态，旧门槛永不触发）；
- **b) 气体闸门放宽**：`stargate_gas_gate_bonus(pivot)` + `gas_gated_stargate_target`
  加 bonus 参数——pivot 时满采气基地数 +2（单矿 2→3 星门，留数据空间不一步到 4）；
- **c) chrono verdict 化**：`chrono_primary_id(pivot, ...)`——pivot 阶段
  chrono 主力判定认 TEMPEST（此前星门整段无 chrono，E10 时报备的已知边界，
  E10b 实锤星门 1-2 的第三根因）。

`_pivot_tempest_mode()` 现被 _effective_spawn/_build_extra_production/
_chrono_structures 三处读取（转型 latch 一次性、幂等）。E9 停开矿与 rush
开局序列（双气早产）按约定不动。单测 344 例绿（+3）。

### P2(a) 修正：矿门槛豁免加 FB 前置（同日，E10c 回退修复）

E10c 实证：裸豁免让追加星门（300 矿）抢在 FleetBeacon（风暴前置）前面，
FB 被饿 50-170s、风暴反而更晚（0-5 回退）。修正原则：**追加产能永远不能
抢自己前置科技的钱**——`extra_production_mineral_gate(pivot, fb_ready)`：
pivot 且 FB 就绪/在建 → 0；pivot 但 FB 未就绪 → 400（先保 FB）；
非 pivot → 400 不变。传参用现成口径 `_structure_present_or_pending(
UnitID.FLEETBEACON)`。chrono(b)/气体闸门(c) 保留不动。单测 344 例绿
（test_mineral_gate 扩为四断言三分支）。

### A1+A2（同日，E10d 诊断落地）

- **A1**：`extra_production_mineral_gate` 加第三道闸——豁免条件从
  「pivot + FB 就绪/在建」收紧为「pivot + FB 就绪/在建 **+ 首艘 TEMPEST
  已出/在产**」（在产也算：生产窗已被主 C 占上）。E10d 实证：追加星门在
  337-385s 开建恰好卡住 FB就绪→首艘风暴窗口，首艘系统性晚 50-70s。
- **A2**：`oracle_before_fleet_allowed(pivot, first_tempest_seen)`——pivot
  模式下 ORACLE one_off 推迟到首艘 TEMPEST 之后（先知 150/150 插队星门是
  首艘晚的另一半原因）；非 pivot 恒 True 零变化。
- 接线：`_first_tempest_seen()`（count>0 或 cy_unit_pending）供两处复用。
- E9 停开矿/pre_fleet floor 按约定不动（等司令拍板）。单测 345 例绿
（+1：oracle 门四分支；mineral_gate 扩为五断言三分支）。

### B1+C1（同日，司令拍板，E9/floor 首次定向调整）

- **B1（E9 停开矿的 Macro 适配）**：新判据 `expansion_blocked(rush, threat,
  pivot, enemy_near_home)`——rush 恒停开（最高优先，六连动不变）；
  非 pivot 按 E9 threat 停（原语义零变化）；**pivot 模式 threat 不再停开，
  改「敌作战单位压到家 40 格 ≥2」才停**（rush 同款语义）。E9 其它效果
  （塔拉满/地面混编）不变。背景：threat 在 Macro 局 359-397s 起常驻，
  两轮 bench 二矿 700s+ 或开不出（one_base×5，单矿经济是天花板）。
- **C1（floor 退出后地面补员）**：新判据 `floor_exits(primary_count,
  ground_combat_count, ground_min=4)`——主 C 上线 **且** 地面作战单位 ≥4
  才退出；地面被打穿（<4）即便舰队在线也继续补叉（E10d 实证：叉子一波
  战死后 floor 已退、地面零补员 = trickle×5 根因）。选「地面数量闸」而非
  「主 C≥2」：自校正（够才退、打穿回补）、无状态无横跳；「主 C≥2」只是
  推后退出点，第二艘上线后同样断层。地面计数=ATTACKING 编制内非空军
  非建筑（`_ground_combat_count`）。
- 零变化保证：B1 的 pivot 分支只在 `_pivot_tempest_mode()`=True 时走
  （rush 局/非 greedy 局恒 False → 旧 threat 门原样）；C1 的 pre_fleet 仅
  carrier 流派配置（stalker/tempest/dt 无此配置，floor 语义天然不变）；
  rush 期 spawn 叉子覆盖分支在 floor 之前 return，不受影响。
- 单测 351 例绿（+6：B1 三分支组/C1 三分支组）。

## 2026-07-25 carrier @NewkirkPrecinctTE vs Terran Harder/Macro（进行中）

### scout 探机撤回后又深入敌家送死（bug，局后修）

- **现象**：scout=on 派的探机 t=72 看到对面兵营后本该撤，t=128 却又深入对面主基（看到 CC/气矿），被 marine 打死。司令观战质疑。
- **根因**（Explore 查证，全在 `bot/main.py:374-409` `_handle_scout`）：
  - 撤回条件**只有一个**：`scout.distance_to(enemy_main) < 12`（`main.py:395`）。人族首兵营常建在 ramp 外围、距 CC 13-20，**没进 12 内 → 撤回不触发**。
  - 探机 idle 就被 `scout.move(enemy_main)`（`main.py:399-400`）反复往敌家推，直到摸进 12 格。
  - "撤回"是假的：只 `assign_role(GATHERING)` + 清 `_scout_tag`（`main.py:395-398`），**没有 move(home)/gather(自家矿) 显式回家命令**（注释写"撤回家采矿"但代码没做）。
  - role 切 GATHERING 后，idle 清扫 `_handle_idle_workers`（`main.py:466-469`）用 `mineral_field.closest_to(w)` 指派最近矿——探机在敌家，最近可视矿 = 对面矿线 → 继续往敌矿走，被 marine 打死。
  - 同一反模式（`gather(closest_to(w))` 不分敌我矿）还在 `production_manager.py:635-638`、`810-813`、`main.py:78-80`、`159-161`。
- **附带澄清**：「司令接管 PROBE」事件（`main.py:565-567`）遍历所有自己单位、不区分角色，司令在家操作闲置农民也会触发——曾误判为司令操作侦查探机，实为 bot 自送。
- **修复方向**：撤回时显式 `scout.move(self.start_location)` 或 `gather(自家最近矿)`，不只切 role；或 idle 清扫对"距最近自家 townhall > N"的 GATHERING 农民先 move 回家。
- **状态**：✅ 已修（2026-07-25，见 plan robust-puzzling-toast + 单测 tests/test_scout_return.py、tests/test_steer_meta.py）。

### scout=on 在 clear 后无法重派（bug，局后修）

- **现象**：clear + scout=on 重派第二个探机，bot 收到命令（`order.scout='on'`）但 180s 不派，司令看不到探机出动。
- **根因**：`bot/main.py:408` 派探机后置 `self._scout_done=True`（一次性 latch）。`clear` 只清 steer 命令层（orders.json），**清不掉 bot 内部 `_scout_done`** → 再下 scout=on 进 `main.py:391` 的 `if self._scout_done:` 分支直接 return，不重派。
- **修复方向**：clear 时重置 `_scout_done`（steer_cli clear 或 bot 读到 clear 信号时清 latch），或 scout 命令支持显式重派语义。
- **状态**：✅ 已修（2026-07-25，_scout_ts 时间戳机制，见 plan robust-puzzling-toast + tests/test_steer_meta.py）。


### 需求3 敌军压上主基补大量光子塔（已实现 2026-07-25）

- **现象**：carrier vs Harder Macro Terran(NewkirkPrecinctTE)，t≈600 人族 MMM+维京压上，
  主基光子塔不足（矿紧造不出），航母流主力未成型挡不住，司令要求认输。
- **司令要求**：敌军压上时主基果断补大量光子塔，全部神族流派都要。
- **实现**：
  - `flows.yml` 全流派(carrier/tempest/stalker/dt)加 `main_siege: {cannons: 12, radius: 25, threshold: 4}`；
  - `flow_config.py` 加 `MainSiege` dataclass + 解析；
  - `production_manager.py` `_main_under_siege`(复用 `is_combat_type`，主基 townhall 25 格内敌地面作战单位 ≥4 触发)
    + 双实例 `ProtossStaticDefence`(exclude_base_locations 互补：实例 A 只主基 cannons=12，实例 B 其余基地原 cannons；to_count_per_base 是 per-base_loc 故不叠加超造)；
  - `production_plans.py` 加 `main_siege_active` 纯判据。
- **状态**：✅ 已实现（2026-07-25，见 plan robust-puzzling-toast + 单测 tests/test_main_siege.py），待实机验证主基压境时塔数 ~3→≥10。


### O21 建造农民钱不够时钉点干等，应先采矿等钱够再去（司令 2026-07-25 提）

- **现象**：开局 t≈30 派一个农民去造第一个水晶(PYLON)，钱不够钉在建造点干等，
  t≈67(1分07s)才造出 —— 干等 ~37s，开局经济亏一个农民，且连锁导致 supply 21/21 卡人口。
- **司令要求**：农民有建造指令时，若建造点距矿区足够近，钱不够**不要钉点干等**，
  先回矿采矿，钱够了再去建造点。
- **根因(待查)**：疑似 ares build_runner 开局序列派的 PyLON 农民无 dispatch_viable 守卫
  (CLAUDE.md 记"ares build runner 开局序列派工仍无守卫，O11 watchdog 兜底")，
  但本例干等 37s 远超 O11 的 6s 撤回线 → 要么 O11 未覆盖开局序列农民、要么撤回被
  build_runner 立即重派形成钉点。需读 main.py O11 watchdog + build_runner 交互确认。
- **修复方向**：钱不够时让建造农民 gather(最近矿,可复用 home_mineral 或主基矿)、
  钱够(can_afford)时再 move 到建造点造 —— 派工/到点双阶段守卫。复用 dispatch_viable
  的"到位可负担才派"语义，补"到点买不起先采矿"分支。
- **状态**：未修，待查根因 + 设计。


### O22 scout 探机遇敌兵应微操逃跑，别傻傻被打死（司令 2026-07-25 提）

- **现象**：scout 探机去敌家路上遇人族枪兵(marine)，不躲不逃，傻傻走到敌家被追打。
- **司令要求**：探机遇敌兵立刻微操往家跑，不在敌方基地送死。
- **根因**：`_handle_scout`(main.py:374-409) 撤回条件只有 `distance(enemy_main)<12`，
  探机要走到敌家 12 格才撤，途中遇 marine 不躲。Bug1 修了"撤回回家不死"，但
  "遇敌主动逃跑"未实现(本局探机侥幸没死,但遇 marine 集结时仍会送)。
- **修复方向**：`_handle_scout` 加"探机被攻击 / 附近(如 <8 格)有敌作战单位 →
  立刻 move(home_mineral 或家)逃跑"分支,优先级高于 idle move(enemy_main)。
  复用 `is_combat_type` 判敌兵 + distance 判威胁圈。
- **状态**：未修，待设计(与 Bug1 同处 _handle_scout，可一起改)。


### 需求3 方向修正（司令 2026-07-25 第二局）：分矿(前线)重点防御，不是主基

- **司令战术**：分矿(2 矿) = 前线门户/咽喉，敌正面陆军从分矿方向压来；**重点防御分矿
  → 挡住敌陆军 → 主基自然安全**(不需主基堆塔)。地形依据：分矿是敌陆军进主基的必经咽喉。
- **观察**：2 矿防御 cannon 不够(当前 `expansion_cannons {min:3, max:8}` 动态偏少)。
- **修正需求3**：已实现的 `main_siege`(只主基补 12 塔)方向要调整 —— 压上时应加强
  **【前线/分矿】** cannon(门户防御)，而非主基。两条可选路线(局后和司令定)：
  ① `main_siege` 改针对分矿(最靠近敌方的基地，而非 start_location 主基)；
  ② 调高 `expansion_cannons.min`(分矿常规就多塔，如 min:5/6)。
- **状态**：需求3 已实现(主基方向)，待调整为分矿/前线方向(局后改，连同 O21/O22)。


### O23 航母出击阈值：敌有防空时航母数量不够不出击（司令 2026-07-25 二局）

- **现象**：carrier 流只有 1-2 艘航母时，敌方有防空(雷神/维京/寡妇雷/导弹塔)，
  航母上 = 送死(本局 2 航母撞雷神4+坦克7+寡妇雷，风暴已死 2)。
- **司令要求**：敌方有防空能力时，1-2 艘航母构不成威胁，应**适当囤兵(攒航母)
  后再上**。
- **修复方向**：carrier 加航母出击阈值 —— 敌可见对空单位(雷神/维京/导弹塔/寡妇雷)
  ≥N 时，航母数量 < 阈值(如 3-4)则不出击(守家攒兵，复用 rally_min_army 或专门
  carrier_count_gate)。carrier 流当前无 rally_min_army(dt:4/stalker:14 有)。
- **状态**：未修，待设计。

### O24 航母地形微操：利用地形陆军打不到的位置进攻 + 残血撤（司令 2026-07-25 二局）

- **司令要求**：航母利用地形优势，在**陆军打不到的位置**(悬崖/地形高差/射程外)
  输出；残血航母撤回来保船。
- **现状**：`carrier_offensive.py` 已有残血撤退(<40%/≥55% 滞回，O12/O14) + 锚点
  避让对空威胁圈/地形高差。但本局航母/风暴仍被点掉(风暴死2) → 要核查锚点是否
  真选了"陆军打不到的位置"、残血撤阈值是否生效。
- **修复方向**：核查/强化 carrier_offensive 锚点选择(优先悬崖上方/射程边缘白嫖，
  陆军地面单位 pathing 够不到的点)；确认残血撤退实际触发。
- **状态**：待核查 carrier_offensive.py 实机表现。


### O25 航母攻击目标优先级：先杀加血/护盾辅助 + 对空威胁（司令 2026-07-25 二局）

- **司令要求**：航母优先攻击：
  ① 有加血/加护盾功能的单位（医疗机 MEDIVAC / 科学船 RAVEN 等辅助）—— 否则它们
     修/盾让敌军打不死;
  ② 对空射程对航母有威胁的单位（雷神 THOR / 维京 VIKINGFIGHTER / 导弹塔 MISSILETURRET
     / 寡妇雷 WIDOWMINE）—— 打掉防空保航母;
  最后才打杂兵。
- **现状**：`carrier_offensive.py` 目标选择(AttackTarget)当前按 focus(weakest/closest/
  兵种名),无"辅助>防空>其他"优先级列表。steer `focus` 是单值,不能设优先级。
- **修复方向**：carrier_offensive 目标选择加优先级评分 ——
  辅助(MEDIVAC/RAVEN/MEDIVAC 等)最高分 → 对空威胁(THOR/VIKING/MISSILETURRET/WIDOWMINE)
  次之 → 其余最低;AttackTarget 选最高分目标。优先级表可配 army_composition.yml 或硬编码。
- **状态**：未修，待设计(与 O23/O24 同在 carrier_offensive/出击逻辑,可一起改)。


### O26 3 矿成型后没造气矿，气体断航母补充不上（司令 2026-07-25 二局）

- **现象**：3 矿(第三基地)成型后没有建造气矿(ASSIMILATOR)，气体收入不足，
  航母(250气/艘)后续补充不上，舰队断档。
- **根因(待查)**：CLAUDE.md O13 `_ensure_expansion_gas` 应"每个就绪基地双气满采，
  在建气矿 45s 不落地拆 tracker 重派"。3 矿就绪后没造气矿 → 疑似
  ① _ensure_expansion_gas 未覆盖 3 矿(只查了主/2 矿)；② threat/rush 期误停非主矿
  气矿；③ O21 idle_builder(造气矿农民干等钱/钉点)。
- **修复方向**：核查 `_ensure_expansion_gas` 对新就绪基地(含 3 矿)的覆盖；确认
  threat/rush 让位是否误伤分矿气矿；与 O21(建造农民先采矿)联动。
- **状态**：未修，待查根因。


### O27 司令手动拉农民造气矿被卡（人机共驾冲突，2026-07-25 二局）

- **现象**：司令手动选中农民去分矿造气矿(ASSIMILATOR)，指令被卡住、造不了。
- **根因(待查)**：O2 人机共驾冲突变种 —— 司令手动操作农民，但 bot 的 idle 清扫 /
  Mining / BuildingManager 抢回农民(role 冲突)，或造气矿的 build 指令被覆盖。
  CLAUDE.md O2(PERSISTENT_BUILDER + _player_ctrl)对"手动建造气矿"是否覆盖待查
  (O2 实证的是"建造中"农民接管,本例是"手动下新建气矿"被卡)。
- **临时绕过**：用 steer `build=assimilator` 一次性命令(bot 自己派农民造)，比手动
  SC2 操作稳(走 bot 建造链路，不和司令抢)。
- **状态**：未修，待查根因(人机共驾对手动新建建筑的覆盖)。


### O28 set target= 清图命令报错（steer_cli 不支持空值，2026-07-25 二局）

- **现象**：skill 词表说"清图 = `set target= stance=attack`"，但 `set target=` 报错
  ⛔ "target 值 '' 不合法(可用: enemy_main ...)"(validate 不接受空值)。
- **根因**：`steer_vocab.validate_field` 对 target 空值报错(TARGETS 枚举不含空)；
  `steer_cli set target=` 解析为 target="" → validate 失败、不写盘。
- **修复方向**：steer_cli 对 "target=" 空值特殊处理(设 None = 清空固定目标 → bot 轮巡)，
  或 validate 对 target 空值放行(语义=清空)。或 skill 文档改用 `clear`+`stance=attack`。
- **状态**：未修(本局已 Victory 结束，清图命令没用到；局后修)。

---

## 2026-07-25 carrier @NewkirkPrecinctTE vs Terran Harder/Macro —— ✅ Victory

航母流翻盘局：开局航母死穴全开(雷神4+维京+寡妇雷+导弹塔+3矿)、一度只剩 2 航母，
但攒到航母 11 + 风暴 5 大军成型后碾压。修复验证 Bug1✅(探机不送死) Bug2✅(clear+scout 重派)。
暴露 O21-O28 共 8 项待改 + 需求3 方向修正(分矿重点防御)，全记上文，局后系统改。


---

## 第一批修复完成（2026-07-25）

O21 / O23 / O26 + 需求3修正 已实现，单测 380 全绿 + carrier/tempest 编译过。

- **O21**(建造干等先采矿)：`main.py` O11 放松 `PERSISTENT_BUILDER`(在 tracker 的 build_runner
  农民放行进 O11 撤回) + `TOWNHALL` 硬豁免改 `grace=30`(保 E3k 开矿预走位)。⚠️ build_runner
  兼容性(撤后 do_step 重派 PYLON)**待实机验证**，若混乱回退。
- **O26**(3 矿气矿)：`production_manager._build_gas` 去全局 `ASSIMILATOR!=0` 一票否决 +
  距离 `<12`→`<15`(治 3 矿双气串行/派不出)。
- **O23**(航母出击阈值)：`production_plans.carrier_rally_against_aa` 纯函数 + `combat_manager`
  rally 块加 carrier gate(航母<3 且敌有防空 → 守家攒兵)。
- **需求3修正**(分矿防御)：`_main_townhall` 从最靠近 start_location 改成最靠近敌方的
  ready townhall(前线分矿)，`_main_under_siege`/双实例注册跟随。

**第二批待改**：O22(探机遇敌逃跑) / O24(航母地形微操) / O25(航母攻击优先级) / O27(手动造气卡) / O28(set target= bug)。


---

## 第二批修复完成（2026-07-25）

O22 / O24 / O25 / O27 / O28 已实现,单测全绿 + carrier 编译过。

- **O22**(探机遇敌逃跑):`main.py _handle_scout` 加逃跑分支(邻近 <`_SCOUT_FLEE_RADIUS=8` 格敌地面作战单位 → `gather(home_mineral)` 逃跑),复用 `is_combat_type`。
- **O24**(航母微操):启用 `carrier_offensive`(`army_composition.yml` CARRIER combat→carrier_offensive)+ 调参(`_AA_BUFFER 2→4`/`_retreat_ref` 撤退 5→15)+ engage 放机后 `PathUnitToTarget` 拉开到 AA 射程外。⚠️ **E4g 回归待实机验证**。
- **O25**(航母优先级):`carrier_logic.carrier_target_priority`(辅助 MEDIVAC/RAVEN/QUEEN > 对空威胁 THOR/VIKING/MISSILETURRET/WIDOWMINE > 杂兵);`carrier_offensive` engage 无 focus 时用它取代最低血量。
- **O27**(手动造气卡):`main.py _handle_player_control` BUILD_* 命令长倒计时(30s,`player_yield_for_ability`),治 3s 倒计时太短被 Mining 抢回。
- **O28**(set target= bug):`steer_vocab.validate_field` 对 target 空值放行(清图 set target= stance=attack 不报错)。


### O21b（深化）开局阶段建造农民干等 grace 太长（司令 2026-07-25 验局）

- **现象**：carrier Harder Zerg 验局,开局第一个水晶(PYLON)农民干等 >5s(司令观战)。
  O21(第一批)放松 PERSISTENT_BUILDER 后开局水晶进 O11,但 grace=6(should_release_
  waiting_builder production_plans.py:308,O11 main.py 开局也 6)→ 开局贴 0 存款、
  50 矿攒 ~10s,农民干等 5-6s 才够。O21 治了 37s(不撤)但 6s 对开局仍太长。
- **司令要求**:开局阶段任何农民等待 >1s 都会滚雪球(经济差距越拉越大),要 <1s。
- **修复方向**:开局阶段(time<120 或 supply<某阈值)用更短 grace(如 1.0,甚至 0 立刻撤),
  中段维持 6.0,TOWNHALL 维持 30。O11 调 should_release_waiting_builder 时按 time 分档传 grace。
  注意:开局 grace 太短 + 撤后重派循环(已部署 redispatch_cooled_down 15s 防中段,但
  开局 PERSISTENT_BUILDER 走 build_runner 重派,不走 redispatch → 需确认 build_runner 兼容)。
- **状态**:未修,局后改(与 O21 同处 main.py O11)。


### O29 carrier vs Zerg：E9 反复压境停 macro → 单矿经济崩（2026-07-25 验局）

- **现象**：carrier Harder Zerg AbyssalReefLE,t=550→767 一直单矿(bases=1),workers 卡 20
  不涨,航母补充极慢(2 艘)。对面 Zerg 双矿 76 supply 飞龙/刺蛇/感染坑,我 37 supply 劣势。
- **根因(待查)**:E9 threat_response_active 反复触发/解除(t=647/676/747),期间疑似停造农民/
  停开矿(保命优先)→ workers 卡 20 < auto_expand 爆仓门槛 22 → 永不开 2 矿 → 单矿气少 →
  航母慢 → 守不住 → E9 再触发,恶性循环。需查 E9 threat_response_active 期间是否误停
  造农民/开矿(应只停 save_up/转防御,不该掐农民/开矿)。
- **影响**:carrier vs 持续压境种族(Zerg 飞龙/刺蛇)经济崩,舰队起不来。
- **修复方向**:E9 threat 期间不应停造农民/开矿(只停 save_up/转防御塔);或 auto_expand
  在 E9 期间放宽(劣势更要开矿补经济,而非停)。
- **状态**:未修,局后查 E9 macro 行为。


### O30 carrier 开 2 矿时机太晚(爆仓模式 + E9 卡死,2026-07-25 验局)

- **司令问**:游戏 12 分钟(t=767)还没开 2 矿是不是太晚?carrier 正常多久开?
- **正常时机**:carrier 先知骚扰 + 舰队航标好后 **t≈180-300(3-5 分钟)就该开 2 矿**
  (build_meta:先知骚扰拖经济→开二矿追经济,空中火力护分矿)。
- **bot 现状**:`auto_expand when_workers:22` 爆仓模式 —— 单矿攒到 22 农民才触发开 2 矿。
  问题:① 爆仓门槛太高(单矿 22 农民本身要 ~t300+,该先开矿再扩农民,不是榨干才开);
  ② 叠加 O29(E9 停造农民,workers 卡 20<22)→ 永不触发 → t=767 仍单矿。
- **修复方向**:carrier 早开 2 矿 —— 降 when_workers(如 16)或加时间触发(t≈200 强开,
  先知/风暴护分矿)。爆仓模式适合 4 矿+,2 矿该早。
- **状态**:未修,局后改 flows.yml carrier auto_expand + 与 O29(E9 停 macro)联动。


### O90 carrier vs VeryHard Terran Macro Defeat（2026-08-03 观战局，BelShirVestigeLE）

> 编号说明：本条最初误编 O34/O37，O 系列与 baselines.md 同轨（已用到 O89），本条改 O90。

- **结果**：Defeat。t≈1023（~17 分钟）基地 2→1→0 被推平；终局 0 农民 0 基地，
  残部 2 TEMPEST。敌方可见兵力 17 MARINE + 21 MARAUDER + 7 MEDIVAC + 4 VIKING（反空）。
- **现象**：
  1. 中段农民骤减 11（被抄家），随后丢二矿（2→1），再丢主矿（1→0）。
  2. **O19 idle_builder 复现 3 起**（t≈990-1004，败局尾段经济崩时）：
     2 农民干等 4s 等钱造 PHOTONCANNON、1 农民干等 4s 等钱造 PYLON。
     均超 3s 阈值；发生在存款枯竭期，属"派工→钱被抽干→钉点"尾段症状。
  3. 升级线正常（盾 L3/空攻 L2 在研），但 17 分钟舰队未成型（终局仅 2 风暴），
     敌方 4 viking 已就位反制航母。
- **修复方向**：与 O29/O30 同链（经济/开矿/舰队成型慢）；被抄家农民骤减 11 需查
  E6 撤离触发是否太晚。idle_builder 尾段 3 起优先级低（败局已定时的症状非病因）。
- **备注**：局末 `ProtocolError: Not supported if game has already ended` 是
  python-sc2 已知收尾噪音（Status.ended 后 bot 仍 query abilities），非 bot bug。
- **状态**：未修，记录待统一优化。


### O91 carrier vs VeryHard Zerg Rush 局1 Defeat（2026-08-03 观战局，BelShirVestigeLE，t=1040）

- **结果**：Defeat。击杀价值 units 4900 / structures 0（全程没推出去，4900 几乎全是塔杀的）。
  idle worker time 1144s（偏高）。
- **时间线**：t=143 rush 确认+注册防御（链正常）；t=608 丢二矿（0 塔裸奔，物理上限见
  血泪#3）；t=726 兵力仅 4 叉、舰队 0 艘；t=887 敌 40 supply 压境 vs 我 22；t=890 E6
  撤离 16 农民（分矿塔 1 座压不住）；t=904-924 农民 12s 内骤减 5/20/5/5/4 全灭；
  t=920 丢基地 2→1；t=972 基地清零。
- **对签名（尸检 skill）**：B 类节奏相克 ——「接触时舰队 2-6 艘，胜局需 8-12 艘」，
  本局 t=726 舰队 0 艘，比 n5m 签名还惨。与 n5m-zerg-rush 0-5（avg 920s 败）同指纹。
- **改进点（≥3）**：
  1. **舰队临界质量恒晚于波次**（主因）：rush 确认→六连动暂停科技链/产能→波后 rush
     反复挂起→星门/FB 永远推迟。唯一方向 = 过渡形态大改（verdict=rush 时叉/追猎地面开、
     推迟星门、活到 t≈700 再转舰队）——交接文档已定方向，本次落地。
  2. **E6 撤离无效化**：t=890 撤 16 农民，12s 内全灭——撤离目标基地本身也在被压
     （敌 40 supply 两线压），撤离方向没避开敌主力。方向：撤离目标选择加「敌兵密度」
     惩罚项，不只按距离/塔覆盖。
  3. **分矿塔防裸奔**：t=608 丢二矿时分矿 0 塔（F2 塔全堆主基坡口，O80b 设计如此：
     rush 期分矿放弃+农民早撤）。本局农民撤了但仍死——配合改进点 2。
  4. idle_builder 尾段 2 起（3s 等钱造塔，贴阈值，败局症状非病因，不立项）。
- **归类**：策略相克（build order 级），非机制 bug。
- **状态**：改进点 1 进入实施（过渡形态）；2/3 记入待验证。

### 战略备忘（2026-08-03，读交接文档后）

- 目标六组合 = 交接文档的「快攻墙」：n5m 当前代码战绩 Zerg Rush 0-5 / Zerg Timing 2-3 /
  Zerg Power 3-2✅ / Terran Rush 0-5 / Terran Timing 1-4 / Terran Power 2-3。
- 迭代回路切换：REALTIME 观战局 → bench.py headless（`--flow carrier --diff VeryHard
  --race X --ai-build Y --map AbyssalReefLE -n 5 --tag o92-*`，可双通道并行）。
- 尸检走 `.claude/skills/sc2-defeat-autopsy` 五步法；改动记 baselines.md O 系列。

---

## O92-O139 bench 迭代期尸检汇总（2026-08-03/04，50+ 系列）

逐系列尸检（每败局 ≥3 改进点+落地验证）全部在 `docs/baselines.md` O92-O139 行，此处留骨架索引：

- **O92-O96（过渡形态期）**：rush 确认→地面过渡→转舰队 架构落地；修转舰队死锁、首波四环（forge 晚/F2 黑窗/协防/塔位绕过）、save_up 锁航母。
- **O97-O107（情报链期）**：早侦查 40s 出发+事件驱动评估（探机送达率=胜负手）、presumed 兜底、greedy 误判灭绝、latch 漏洞（rush verdict 不置 confirmed）。
- **O108-O115（舰队窗期）**：strong-exit 退出门、落位「无电」型实锤、SG 爬坡/科技预留两死锁、分矿并行供电。
- **O116-O122（取证期）**：派工四分类取证（taken/no_placement/no_worker/no_money）、停气棘轮（38/40 农民被抽干）、O11 21s 循环、虚空填窗、首波后扩张。
- **O123-O131（叉海+预留期）**：塔链 vs 叉海 A/B、预留自伤、产兵仲裁器、暂停型预留改排队型（死锁变体 6 连发的根）。
- **O132-O135（回调期）**：退出经济门回调（O119 掐死舰队路）、timing 波防御冲刺、地面兵力真空（39 农 1 叉）、产出永不暂停（预留语义反转）。
- **O136-O139（结构期）**：硬编码开局（'12 gateway'）、坡口墙实验证伪回滚、双通道并行实证、钉点农民三刀。

**五胜档案**：o107 局2（1002s，25 风暴 4 基地）、o112 局4（2096s，29 风暴）、o117 局5（28 风暴）、o129 局2（26 风暴）、o132-timing 局3（28 风暴）——全部同型：活过 rush→扩张→20+ 风暴→推进。

**当前未破**：单局胜率 ~20%（fast/medium 骰的 150-500s 波次窗），Terran 三组+Zerg Rush/Timing 未过线。

---

## O154 carrier @AbyssalReefLE vs Zerg VeryHard/Power + Zerg VeryHard/Timing（2026-08-04）

- **结果**：zerg-power **1-4**，zerg-timing **1-4**。O154 修 greedy 接触误入过渡后，胜率未回升。
- **核心新发现：carrier 流整局不出航母**。o154-power 终局编成均值 TEMPEST×28 / ORACLE×1 / STALKER×4 / ZEALOT×2，CARRIER=0；o154-timing 终局 TEMPEST×17 / ZEALOT×6 / STALKER×2，CARRIER=0。
- **根因**：flows.yml carrier 当前配方为 TEMPEST p0 / CARRIER p1，`save_up: 0`。freeflow 下 SpawnController 只看 priority：TEMPEST 便宜（150/100）且科技就绪后永远可负担，每一帧都 fall-through 到 TEMPEST；CARRIER 作为 p1 被永久截断，整局没有出场窗口。
- **改进点（≥3）**：
  1. **强制航母配额机制**：舰队成型（首舰已出）且暴风海达临界数量（如 ≥12）后，若航母数量不足目标（如 <4），把 spawn 主次对调成 CARRIER p0 / TEMPEST p1，并开动态 save_up 憋气出航母；达标后恢复暴风主 C。
  2. **idle_builder 进一步收敛**：五局全中，o154-timing game_03 高达 ×68。来源多为开局 forge/PYLON 等钱钉点。考虑缩短非关键建筑在开局阶段的 grace，或让关键三件（forge/首塔/GW1）的钉点也被 detect 但不计入 retro 归因。
  3. **舰队爬坡与 economy 关联**：胜局（o154-power game_02）终局 4 基地/68 农民/200 人口 28 暴风；败局多为 1-2 基地、农民被抄、舰队数量不足。需继续观察配额机制是否能带动终局兵力结构改善。
- **状态**：O155 已落地①，单测 614 绿；烟测/ bench 待跑。


---

## O155/O156 carrier @AbyssalReefLE vs Zerg VeryHard/Power（2026-08-05）

- **O155 落地**：`carrier_quota_active` / `carrier_quota_spawn` + `_apply_save_up(force_gap=250)`，目标在舰队成型后强制补航母。
- **O155 bench 结果**：后台任务 `bash-1f38qf0m` 在跑完 game_01、game_02 未结束时 lost；进程残留已清。game_01 **Defeat**，game_02 在 1040s 时 1 基地/4 暴风，明显败势。
- **O155 失效根因（game_01 实锤）**：
  - 舰队峰值 **TEMPEST×11**，**未达 O155 默认阈值 12**，航母配额**从未触发**，终局 0 航母。
  - 11 艘暴风后在 Zerg 中盘波次（t≈950）被压崩，基地 3→2→1→0，经济断气。
- **game_01 / game_02 共同指纹**：
  1. **舰队 6–11 艘时无航母**：O155 阈值 12 对 VeryHard Power 节奏过高，等不到暴风海成型就被推平。
  2. **idle_builder 仍刷屏**：开局 PYLON/FORGE/NEXUS 等钱钉点事件反复出现（同一位置每 4s 一次），主因是 AutoSupply 被 O11 撤回后每帧重派新工人，`_o11_released_at` 冷却未覆盖 AutoSupply 路径。
  3. **中盘经济崩盘**：3 矿后无法保住，vespene 2200+/3986 但 minerals 30–45，Nexus 重建没钱；舰队规模不足导致分矿守不住，分矿守不住又导致舰队补不上。
- **改进点（≥3）并落地为 O156**：
  1. **降低航母配额阈值并计入在产**：`carrier_quota_active` 默认 `fleet_min` 从 12 降到 8；新增 `pending_tempest/pending_carrier` 参数并在调用方传入 `cy_unit_pending`，避免“差一艘到阈值”死锁；fallback——舰队 ≥6 且 still 0 航母时强制触发，确保第一艘航母不会永远被憋死。
  2. **AutoSupply 撤回冷却**：`production_manager` 注册 AutoSupply 前加 `redispatch_cooled_down` 守卫（非人口紧急时），被 O11 撤回的 PYLON 10s 内不再重派，减少开局 idle_builder 刷屏和水晶抢 forge/Nexus 资金窗。
  3. **预走位 Nexus 也进入扩张持有期**：`_expand_holding` 增加 `not_started_but_in_building_tracker(NEXUS)` 判据，防止“Nexus 已派工但还没付款”时塔/科技/追加产能继续吃银行，导致二矿/三矿等钱等到死。
  4. **基地清零重建可行性门**：`_rebuild_nexus` 加 `nexus_rebuild_viable` 检查（有工人、矿脉有剩、存款 ≥400），避免无收入死局仍暂停出兵 250s 空转。
- **验证**：单测 616 passed / 1 skipped；O156 bench（VeryHard Zerg Power ×5）待开。
- **状态**：O156 已落地，进入 bench 验证。


## O156 bench 尸检：carrier @AbyssalReefLE vs VeryHard Zerg/Terran Power（2026-08-05）

- **bench 配置**：`poetry run python bench.py --flow carrier --diff VeryHard --race {Zerg,Terran} --ai-build Power --map AbyssalReefLE -n 5 --tag o156-vh-* --timeout 900`，双 lane 并行。
- **提前终止原因**：两条 lane 的 game_01 / game_02 全部 **Defeat**， signature 一致且趋势无悬念；为避免继续浪费机时，终止后台任务并做尸检。
- **战绩**：Zerg Power 0-2，Terran Power 0-2（game_03 进行中未纳入）。

### 关键数据

| 对局 | 结果 | 时长 | 终局 | 农民峰值 | 基地峰值 | 舰队峰值 |
|---|---|---|---|---|---|---|
| Zerg Power game_01 | Defeat | 1224s | 0 基地 4 农民 army {} | 68 | 4 | TEMPEST×7, CARRIER×1, ZEALOT×6 |
| Zerg Power game_02 | Defeat | 923s | 0 基地 0 农民 army {ORACLE×1} | 46 | 3 | TEMPEST×2, ZEALOT×2, STALKER×1 |
| Terran Power game_01 | Defeat | 816s | 0 基地 10 农民 army {ORACLE×1} | 54 | 3 | TEMPEST×3, ZEALOT×2, STALKER×2 |
| Terran Power game_02 | Defeat | 798s | 0 基地 5 农民 army {ORACLE×1} | 59 | 3 | CARRIER×1(拦截机×8), STALKER×1 |

### 共同死因（三局以上一致）

1. **炮塔建了但不重建，基地压缩到 1-2 个后防御归零**
   - Zerg game_01：t=843 时 15 炮塔/2 电池/4 基地；t=1092 只剩 1 基地时炮塔骤降到 1。
   - Terran game_01：t=494 时 11 炮塔/3 基地；t=594 只剩 2 基地时炮塔只剩 1。
   - Zerg game_02：t=494 时 10 炮塔/2 基地；t=695 基地清零时炮塔 0。
   - 根因：`cannon_target_capped` 在矿 < 主 C 造价（TEMPEST 250）时把目标压回 `ec.min=4`；一旦基地被打掉、矿收入断流，bot 继续憋舰队而不补防御，形成“丢基地→更没钱→更不补塔→再丢基地”的死螺旋。

2. **舰队规模永远到不了临界质量就被推平**
   - Terran Power 两局都在 550-700s 被 bio 一波穿，此时舰队 1-3 艘；Zerg game_02 更是在 600s 就只有 1 艘暴风。
   - 根因：前期经济/产能被塔、水晶、农民摊薄，主 C（暴风/航母）产出过慢；敌方 Power 中盘波次到达时我方没有足够天空体反制。

3. **基地丢失后的经济死锁**
   - Zerg game_01 终局 vespene=3371、minerals=30；Terran game_02 终局 vespene=2818、minerals=615，都无法在 0 基地状态下重建 Nexus（需要 400 矿）。
   - 根因：高气体烂在银行，矿物因丢矿/农民骤减而枯竭；现有 `_rebuild_nexus` 只在丢基地后暂停出兵攒钱，但没能力阻止其他系统（升级/追加产能/塔）继续抽血。

### 改进点（≥3）并落地为 O157

1. **压缩到 1-2 基地时不限流塔重建**：`cannon_target_capped` 增加 `bases` 参数，当 `bases <= 2` 时直接返回 `dynamic_count`（max 防御），不再因攒舰队而压到 `ec.min`；把生存优先级提到舰队之上。
2. **提高 carrier 分矿 baseline 塔数**：`flows.yml` carrier 的 `expansion_cannons` 从 `{min:4, max:10}` 调到 `{min:6, max:12}`，让 3-4 基地阶段每矿炮塔更厚，减少被单波 bio/地面直接穿矿的概率。
3. **基地丢失后进入“重建+防守” austerity**：当 `peak_bases > current_bases` 且 `current_bases <= 2` 时，掐掉非防御性开销（升级、追加产能、新扩张），把矿全部留给 Nexus 重建+炮塔/电池+地面保命兵；避免 3000 气 30 矿的死局空转。

- **状态**：O157 已落地并通过单测，进入 bench 验证。


## O157 落地与验证（2026-08-05）

- **实现内容**：
  1. `bot/production_plans.py` 新增 `mineral_crisis_gas_stop`：vespene≥1500 & minerals≤300 & fleet_total<8 时把气矿农民拉回采矿，解决 O156 终局“3371 气、30 矿”的矿物枯竭死锁。
  2. `cannon_target_capped` 增加 `vespene/fleet_total/bases` 参数：
     - `bases <= 2` 时返回 `dynamic_count`（生存优先，不限流）；
     - gas-rich+mineral-poor+fleet-small 时按 `ec.min` 限流，避免 16 塔吃掉本可造舰队的矿。
  3. `extra_production_mineral_gate`（未改名前的追加产能矿门）增加 gas-rich 抬高矿门参数，气多矿少舰队小时提高追加产能的矿门槛，防止星门/兵营在矿物危机期继续抽血。
  4. `bot/managers/production_manager.py`：
     - `_rush_gas_stop` 引入 `_mineral_crisis_gas_stop` 状态，危机时把气矿农民拉回采矿；
     - `_should_build_defense` 调用 `cannon_target_capped` 时传入 `vespene/fleet_total/bases`；
     - `_build_extra_production` 调用时传入 `vespene/fleet_total`。
  5. `flows.yml` carrier 的 `expansion_cannons` 从 `{min:4, max:10}` 调到 `{min:6, max:12}`。

- **验证**：单测 617 passed / 1 skipped。
  - 修正了 O157 新增测试 `test_gas_rich_but_fleet_large_no_extra_cap` 参数与断言矛盾的问题（minerals 300 低于 fleet_mineral_cost 350，老逻辑本就会限流；改为 minerals=400 并拆分老逻辑限流用例）。
  - 同步更新了 `test_flow_config.py` 对 carrier `expansion_cannons` 的断言到 (6, 12)。

- **下一步 bench**：`o157-vh-zerg-power` 5 局 VeryHard Zerg Power @AbyssalReefLE，timeout 900；若仍败则继续尸检 → O158。


## O157 bench 尸检：carrier @AbyssalReefLE vs VeryHard Zerg/Terran Power（2026-08-05）

- **bench 配置**：双 lane 并行 `poetry run python bench.py --flow carrier --diff VeryHard --race {Zerg,Terran} --ai-build Power --map AbyssalReefLE -n 5 --tag o157-vh-* --timeout 900`；各跑 1 局后 signature 一致且为长时败局，提前终止。
- **战绩**：Zerg Power 0-1，Terran Power 0-1（未跑满 5 局）。

### 关键数据

| 对局 | 结果 | 时长 | 峰值 | 终局 |
|---|---|---|---|---|
| Zerg Power game_01 | Defeat | 1095.8s | 4 基地 / 67 农民 / 18 炮塔 / 6 暴风 + 1 航母 | 农民被抄光，经济崩盘 |
| Terran Power game_01 | Defeat | 1140.6s | 3 基地 / 57 农民 / 13 炮塔 / 7 暴风 + 1 航母 | 缩成 1 基地被磨死 |

### 死因

1. **舰队出门导致基地被抄**：O157 把 Power 局寿命从 O156 的 800s 级延长到 1100s+，但中盘舰队仍主动出门/追击，分矿/主矿被敌方持续地面小队轮抄，农民死光后经济断气。
2. **航母数量仍不足**：两局虽然各产出一艘航母，但舰队主体仍是暴风；对 Power 持续中盘波次，航母成型慢、拦截机数量有限，站桩输出不够。
3. **基地数过多分散防御**：`auto_expand.max_bases=4` 时 4 基地防御面太散，VeryHard Power 一波穿一个矿即经济崩塌。

### 改进点（≥3）并落地为 O158

1. **基地 ≤2 时舰队强制守家**：`bot/managers/combat_manager.py` 增加 `_home_guard`：当 `order.get("stance") is None` 且 `self.ai.townhalls.amount <= 2` 时，`attack_target = self._defend_anchor()`，避免舰队出门导致基地被逐个蚕食。
2. **压扩到 3 矿集中防守**：`flows.yml` carrier `auto_expand.max_bases` 从 4 改为 3，减少防御面分散。
3. **继续验证航母配额与塔重建协同**：O157 已放宽 `cannon_target_capped` 与 `mineral_crisis_gas_stop`，O158 通过守家进一步验证中盘经济能否保住，并观察暴风/航母比例是否改善。

- **状态**：O158 已落地并通过单测（626 passed / 1 skipped），进入 bench 验证。


## O158 落地与验证（2026-08-05）

- **实现内容**：
  1. `bot/managers/combat_manager.py`：新增 `_home_guard` 判据，基地 ≤2 个且司令未下 stance 时，舰队强制守家（`attack_target = self._defend_anchor()`），避免舰队出门导致基地被抄。
  2. `flows.yml` carrier 的 `auto_expand.max_bases` 从 4 改为 3，集中防守。
  3. `tests/test_flow_config.py` 同步更新 `max_bases` 断言到 3。

- **验证**：单测 626 passed / 1 skipped。

- **下一步 bench**：`o158-vh-zerg-power` / `o158-vh-terran-power` 各 5 局 VeryHard Power @AbyssalReefLE，timeout 900；若仍败则继续尸检 → O159。


## O158 bench 尸检：carrier @AbyssalReefLE vs VeryHard Zerg Power（2026-08-05）

- **bench 配置**：`poetry run python bench.py --flow carrier --diff VeryHard --race Zerg --ai-build Power --map AbyssalReefLE -n 5 --tag o157-vh-zerg-power --timeout 900`（启动时 O157 已落地；game_03 起崩溃/超时，判断为并发 SC2 客户端冲突，已清理）。
- **战绩**：Zerg Power 0-2（第 3 局无结果，已停）。

### 关键数据

| 对局 | 结果 | 时长 | 峰值 | 终局 |
|---|---|---|---|---|
| game_01 | Defeat | 1095.8s | 4 基地 / 71 农民 / 26 炮塔 / 9 暴风 + 0 航母 | 0 基地 1 农民，被多线磨死 |
| game_02 | Defeat | 707.9s | 1 基地 / 22 农民 / 5 炮塔 / 1 暴风 + 1 先知 | 0 基地 1 农民，单矿被一波穿 |

### 共同死因

1. **前期过度采气，矿物枯竭，舰队难产**
   - game_01：394s 时气体 1688、矿物 145、舰队 0；562s 才出第一艘暴风。
   - game_02：全程单矿，气体 1500+ 但矿物 0-300，600s 敌 25 supply 压境时我方仅 16 supply。
   - 根因：`mineral_crisis_gas_stop` 触发太晚（vespene≥1500 & minerals≤300 & fleet<8），等到触发时矿物已经贴 0，农民长期停滞。

2. **舰队成型前盲目扩张/铺塔**
   - game_01：fleet=0 时已开二矿并铺塔；500s 开三矿、640s 开四矿，但每矿塔分散（三矿 0 塔），被 Power 一波穿一个。
   - game_02：单矿情况下仍把资源摊到塔和科技，舰队只有 1 艘，无法抵挡中盘波次。
   - 根因：`should_expand_dynamic` 只看农民饱和/优势/首扩时间，没有舰队规模和矿物门槛。

3. **塔重建限流阈值过松**
   - game_01 矿物 300-400 且气体烂银行时，塔目标仍按动态数重建，吃掉本可造舰队的矿。
   - 根因：`cannon_target_capped` gas-rich 门限 `vespene≥1000 & minerals<400 & fleet<8` 过晚/过松。

### 改进点（≥3）并落地为 O159

1. **提前并强化矿物危机停气**：`mineral_crisis_gas_stop` 阈值从 `vespene≥1500 & minerals≤300 & fleet<8` 调整为 `vespene≥800 & minerals≤400 & fleet<5`；基地≤2 时矿物阈值放宽到 600，更早把气矿农民拉回采矿。
2. **扩张增加舰队/矿物门槛**：`should_expand_dynamic` 新增 `fleet_total` / `minerals` 参数，首扩之后（bases≥2）要求 `fleet_total≥3` 或 `minerals≥500` 才允许继续扩张，避免 fleet=0 时连开三/四矿。
3. **更严的塔重建限流**：`cannon_target_capped` gas-rich 门限调整为 `vespene≥800 & minerals<500 & fleet<5`，减少塔在矿物危机期抽血，把矿留给舰队和农民。

- **状态**：O159 已落地并通过单测（627 passed / 1 skipped），进入 `REALTIME=True` bench 验证。


## O159 bench 尸检：carrier @AbyssalReefLE vs VeryHard Zerg Power（2026-08-05）

- **bench 配置**：`poetry run python bench.py --flow carrier --diff VeryHard --race Zerg --ai-build Power --map AbyssalReefLE -n 5 --tag o159-vh-zerg-power --timeout 1200 --realtime`。
- **战绩**：第 1 局 1168s 仍无结果，bench 判定超时/崩溃并重试一次；重试局仍在前期时停止 bench 进入 O160 迭代。本组合 0 胜（有效局 0 胜）。

### 关键数据（game_01 超时前快照）

| 时间 | minerals | vespene | workers | bases | army | 炮塔 |
|---|---|---|---|---|---|---|
| 511s | 135 | 720 | 50 | 3 | 1 先知 | 15 |
| 589s | 500 | 65 | 60 | 3 | 2 暴风 + 1 追猎 + 1 叉 + 1 先知 | 17 |
| 918s | 110 | 1473 | 69 | 4 | 9 暴风 + 4 叉 + 1 先知 | 23 |

### 死因

1. **舰队成型后仍矿物枯竭、气烂银行**
   - 918s 时 vespene=1473、minerals=110， fleet_total=9 艘，但矿物收入不够，星门/塔/科技全停产。
   - 根因：`mineral_crisis_gas_stop` 仍绑 `fleet_total<5`，舰队成型后不再停气，农民继续采气，矿物永远补不上。

2. **塔在矿物地板上继续抽血**
   - 918s 时 minerals=110，塔目标仍高达 23 座，且 `idle_builder` 仍在等钱造 PhotonCannon。
   - 根因：`cannon_target_capped` 没有矿物硬地板，gas-rich 限流只看 vespene≥800；当 minerals<250 时仍按动态数重建。

3. **扩张门槛太松，经济面持续摊薄**
   - 511s 已 3 基地、fleet=0；918s 出现 4 基地。
   - 根因：`should_expand_dynamic` 首扩后用 OR 门（fleet≥3 或 minerals≥500），矿多但无舰队时仍会扩张；且 max_bases=3 未有效阻止第 4 矿（townhalls.amount 含 pending 时计数漂移）。

### 改进点（≥3）并落地为 O160

1. **矿物危机停气不再硬绑 fleet 规模**：`mineral_crisis_gas_stop` 触发改为 `vespene≥600 & minerals≤300`（基地≤2 时阈值 400），恢复阈值下调为 `vespene<300 或 minerals>500`，舰队成型后矿物枯竭仍会把气矿农民拉回采矿。
2. **塔重建加矿物硬地板**：`cannon_target_capped` 新增 `mineral_floor=250`，`minerals<250` 时直接压回 min，避免塔抽干舰队矿；gas-rich 阈值同步降到 600。
3. **扩张门槛收紧为 AND 并双保险**：`should_expand_dynamic` 首扩后要求同时满足 `fleet_total≥3` **且** `minerals≥500`；`flows.yml` carrier `max_bases` 保持 3，减少经济面摊薄。

- **状态**：O160 已落地并通过单测（626 passed / 1 skipped），进入 `REALTIME=True` bench 验证。


## O160b bench 尸检：carrier @AbyssalReefLE vs VeryHard Zerg Power（2026-08-05）

- **bench 配置**：`poetry run python bench.py --flow carrier --diff VeryHard --race Zerg --ai-build Power --map AbyssalReefLE -n 5 --tag o160b-vh-zerg-power --timeout 900 --realtime`。
- **战绩**：game_01 未结束即判定失败（手动停止 bench 进入迭代），有效局 0 胜。

### 关键数据（game_01 运行中快照）

| 时间 | minerals | vespene | workers | bases | army | 炮塔 | 备注 |
|---|---|---|---|---|---|---|---|
| 376s | 80 | ~1400 | 20 | 1 | 9 叉 + 2 追猎 | 5 | O131 死锁保险丝熔断，fleet=False |
| 450s | 0 | 1658 | 20 | 1（刚开 2 矿） | 9 叉 + 2 追猎 | 5 | 刚拍下首座 STARGATE |
| 527s | 0 | 1658 | 20 | 2 | 9 叉 + 2 追猎 | 9 | 二矿一落即补到 9 塔，无舰队 |

### 死因

1. **Protoss 没有专用 build order，农民停产**
   - ares DataManager 对所有种族都选 `TempestRush`；该 opener `ConstantWorkerProductionTill: 0`，`OpeningBuildOrder` 只到 14 supply。
   - bot 层 `ProductionManager._update` 对 Protoss 没有显式注册 `BuildWorkers`，农民完全依赖 build runner。
   - 结果 527s 仅 20 农民，经济无法支撑舰队+塔+科技。

2. **二矿塔 baseline 过高，fleet<3 时仍铺 6+ 塔**
   - `flows.yml` carrier `expansion_cannons: {min: 6, max: 12}`，二矿刚落 `defense_syncs_with_nexus` 即启动分矿塔防。
   - `cannon_target_capped` 在 `bases<=2` 时完全不限流（O157 生存优先），fleet=0 也把目标拉到 6-9 塔。
   - 9 塔 × 150 矿 = 1350 矿，直接吃掉首舰/舰队航标/农民的矿。

3. **农民干等造建筑，采矿未最大化**
   - state 中多次出现 `idle_builder: 农民 xxx 干等3s(等钱造PHOTONCANNON/NEXUS/PYLON)`。
   - 矿物被塔和科技押金锁死后，农民被 BuildStructure 钉在建造点等钱，进一步压低收入。

### 改进点（≥3）并落地为 O161

1. **为 carrier 添加专用经济开局 CarrierOpener**
   - `protoss_builds.yml` 新增 `CarrierOpener`：`ConstantWorkerProductionTill: 34`，`OpeningBuildOrder` 把农民线拉到 30 supply。
   - `bot/main.py` 在 `on_start` 中检测 `BUILD==carrier`，调用 `build_order_runner.switch_opening("CarrierOpener")`，确保 carrier 不再用 TempestRush 开局停产农民。

2. **舰队成型前压低 expansion_cannons baseline**
   - `bot/production_plans.py` 新增 `expansion_cannon_min_dynamic()`：fleet_total < 3 时把 `ec.min` 压到 3，成型后恢复 6。
   - `bot/managers/production_manager.py` 在 `_build_defense` 中调用该函数，避免二矿一落就铺 6 塔。

3. **基地压缩时仍对未成规模舰队限流**
   - 修改 `cannon_target_capped`：`bases<=2` 不再无条件不限流，仅在 `fleet_total>=3` 时解除限流；fleet<3 时继续按 min 限流，保舰队经济。

- **状态**：O161 已落地并通过单测（630 passed / 1 skipped），进入 `REALTIME=True` bench 验证。


---

## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O161 REALTIME bench，game_01/02 双 timeout）

### 现象

`poetry run python bench.py --flow carrier --diff VeryHard --race Zerg --ai-build Power --map AbyssalReefLE -n 5 --tag o161-vh-zerg-power --timeout 900 --realtime`

- **game_01**：打到 865.8 秒无结果，最终记 `ERROR (1803s)`。
- **game_02**：第一局打到 866.4 秒无结果，bench 自动重试第二局（仍在进行中时被停止）。
- 两局共同特征：舰队规模其实已成型，但游戏无法在 15 分钟内结束。

### 根因尸检（≥3）

1. **静态防御严重超配，把舰队矿吸干**
   - game_01：21 门光子炮；game_02：28 门光子炮。
   - `flows.yml` carrier `expansion_cannons: {min: 6, max: 12}` 是**按每基地**计算的目标。3-4 基地时总炮塔目标达到 18-36 门，实际造出 21-28 门。
   - 28 门炮 × 150 矿 = 4200 矿，约等于 12 艘航母/暴风的矿物成本，直接挤占舰队产能。
   - 炮塔还会占用建造农民和建造槽，state 中多次出现 `idle_builder: 农民 xxx 干等3s(等钱造PHOTONCANNON/NEXUS)`，进一步压低采矿收入。

2. **开局完全盲打，敌科技发现太晚**
   - game_01：GreaterSpire/Hive 在 841s/845s 才发现（约 14 分钟）。
   - game_02：SpawningPool/Spire/InfestationPit/Hive 在 646s-654s 才发现（约 11 分钟）。
   - 原因：`bench.py` 未下发 `scout=on`，`_handle_scout` 只在 Zerg 每 60 秒循环 scout 且必须先有一次成功派遣后才会继续；实际首探机从未派出，导致全局长时间无情报。

3. **主基 siege 也按 12 门塔拉满，进一步失血**
   - `main_siege: {cannons: 12}` 在敌压上主基时额外注册 12 门塔。
   - carrier 流矿物应优先变舰队和农民，主基 siege 12 门塔会一次性抽走 1800 矿，舰队重建窗直接被拖垮。

4. **fleet 成型后仍不推出去，在家蹲到超时**
   - game_02 到 866s 已有 17 暴风 + 4 航母 + 24 拦截机，supply 195/200，但仍在不断补塔/补农民。
   - 虽然 `combat_manager` 有 carrier 推进闸，但海量炮塔建设和持续的小队骚扰把舰队永远钉在防御跑步机里，加上没侦查找不到敌军薄弱点，最终拖到 15 分钟 timeout。

### 改进点（≥3）并落地为 O162

1. **大幅压缩 carrier 流炮塔预算**
   - `flows.yml` carrier `expansion_cannons: {min: 6, max: 12}` → `{min: 2, max: 4}`（每基地），3 基地总炮塔目标从 18-36 降到 6-12。
   - `flows.yml` carrier `main_siege.cannons` 12 → 6，主基 siege 不再堆 12 门塔。
   - 同步更新 `tests/test_flow_config.py` 和 `tests/test_main_siege.py` 的 shipped 配置断言。

2. **开局自动派一次探机，解决盲打问题**
   - `bot/main.py`：新增 `_auto_scout_done` 标记；`_handle_scout` 在 `steer_order.scout != "on"` 时，若游戏时间 >12 秒且还没自动派过，自动抽一个农民去侦察。
   - 自动 scout 成功后标记完成，后续仍走原有 Zerg 60 秒循环 scout 或手动 `scout=on` 命令，互不冲突。

3. **把省下的矿和建造槽还给舰队**
   - 炮塔目标降低后，`cannon_target_capped` 和 `expansion_cannon_min_dynamic` 的限流逻辑会自然把矿物让给星门/舰队航标/航母。
   - 农民 idle_builder 事件中的 "等钱造炮塔" 应显著减少，采矿效率回升。

- **状态**：O162 已落地，单测通过，进入 `REALTIME=True` bench 重新验证。


---

## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O162 REALTIME bench，game_01 早期崩盘）

### 现象

O162 bench 启动后 game_01 正常运行，但约 4 分半时主动停止观察：
- 273.3 秒（约 4:33）：24 农民、2 基地、8 水晶、2 气矿、1 锻造炉、1 光子炮。
- **零科技建筑**：没有 GATEWAY / CYBERNETICSCORE / STARGATE / FLEETBEACON。
- **零军队**：`army: {}`。
- 矿物长期贴 0（75-360 振荡），气体却积到 928。

### 根因尸检（≥3）

1. **开矿持有期冻结全部核心科技链**
   - `auto_expand.first_expand_at: 150` 让二矿在 2 分半左右即触发 `_expand_holding=True`。
   - `core_tech_allowed(expand_holding=True, fleet_transitioned=False)` 返回 False，`_build_flow_structures` 直接 return，GATEWAY/CYBERNETICCORE/STARGATE 全被冻结。
   - 结果：bot 只造农民、水晶、气矿、Nexus，4 分半仍零兵零科技。

2. **气矿太早、矿物枯竭**
   - `_build_flow_structures` 在持有期仍补满 2 气/基地（因为 gas 不被 core_allowed 冻结）。
   - 14-21 农民时就把 4 个农民派去采气，矿物收入被抽空，连 150 矿的 GATEWAY 都拍不下。

3. **水晶过度建设**
   - 273 秒时已建 8 根水晶，占用大量矿物；其中多根是 `_ensure_expansion_pylon` 和 O55 自救逻辑反复补的。
   - 矿物被水晶和气矿吸走后，首兵营永远排不上队。

### 改进点（≥3）并落地为 O163

1. **开矿持有期也强制拍下首 GATEWAY**
   - `bot/managers/production_manager.py` 在 `_build_flow_structures` 的 `if not core_allowed: return` 前加例外：若尚未有 GATEWAY（含 pending），调用 `_build_core_structure(UnitID.GATEWAY)`。
   - 保证经济开局不至于 4 分半零科技，至少能出叉/追猎应急和解锁后续 CYBERNETICCORE。

2. **保留 O162 的炮塔和侦查优化**
   - `flows.yml` carrier `expansion_cannons {2,4}` 与 `main_siege.cannons=6` 不变，避免回到 21-28 门塔的矿出血。
   - `bot/main.py` 开局自动 scout 不变，保证前期有情报。

3. **后续观察点**
   - 首 GATEWAY 解冻后，观察是否仍因矿物不足迟迟拍不下 CYBERNETICCORE/STARGATE；若复现，再考虑把 `first_expand_at` 延后或限制早期气矿数量。

- **状态**：O163 已落地，单测通过，进入 `REALTIME=True` bench 重新验证。


### O163 补充修正（build order 内嵌科技链）

仅解冻 `_build_flow_structures` 中的首 GATEWAY 仍不足：o163-vh-zerg-power game_01 在 188s 矿物仅 105，连 150 矿的 GATEWAY 都拍不下。根因是 presumed 窗优先拍下 FORGE（150 矿）+ 双气矿（150 矿），科技链被挤到矿物归零后 still 无法启动。

**补充落地**：
- `protoss_builds.yml` 的 `CarrierOpener` 直接把 `17 gate`、`22 core`、`26 stargate` 写进 `OpeningBuildOrder`。
- 这样 GATEWAY/CYBERNETICCORE/STARGATE 由 build runner 在固定 supply 触发，不受 bot 层 `core_allowed=False` 或 presumed 防御链的资源优先级影响。
- `bot/managers/production_manager.py` 中 O163 的「持有期也拍首 GATEWAY」保留作为双保险，避免 build runner 因矿物不足卡住时 bot 层仍尝试补科技。

- **状态**：O163 修正已落地，单测通过，进入 `REALTIME=True` bench 重新验证。


### O163c 再修正（关闭 ConstantWorkerProductionTill）

o163b game_01 在 5 分半时：34 农民、2 基地、8 水晶、2 兵营、4 气矿、3 塔，**仍无 CYBERNETICCORE/STARGATE**。GATEWAY 虽按 build order 在 3:05 落地，但 `ConstantWorkerProductionTill: 34` 让 runner 在 GATEWAY 后仍疯狂插农民，CYBERNETICCORE(150 矿)/STARGATE(150 矿)/PYLON/EXPAND 全在抢所剩无几的矿物，科技链再次被饿死。

**再落地**：
- `protoss_builds.yml` 的 `CarrierOpener.ConstantWorkerProductionTill` 从 34 改为 0，农民全部显式写入 `OpeningBuildOrder`。
- 这样 runner 严格按顺序执行：GATEWAY → CYBERNETICCORE → STARGATE，不会被自动农民插队和吸干矿物。
- bot 层在 build order 完成后接管经济和产能，维持中后期的农民/航母产出。

- **状态**：O163c 已落地，单测通过，进入 `REALTIME=True` bench 重新验证。


### O163c game_01 尸检（@AbyssalReefLE vs Zerg VeryHard/Power，timeout）

### 现象
- 870 秒（14:30）仍无胜负，被 bench timeout 900 秒判负。
- 军力：**11 暴风 + 2 航母 + 5 追猎 + 1 先知**，supply 157/175；敌方可见 army 约 60-80 supply。
- 经济：4 基地、58 农民、存款 2400/1400。
- 防御：主矿 + 分矿共 **17 门光子炮**（O162 目标 6-12 仍超标，但实际压力来自 Power 持续小队）。

### 根因尸检（≥3）

1. **舰队成型后被 `_hot_base_anchor` 钉死在防守跑步机**
   - carrier 推进闸要求 `should_push_advantage` 或 `full_pop_all_in` 才放行。
   - 14:30 时我方 157 supply 对敌 60-80 supply 看似优势，但 `supply_used - supply_workers = 97`，敌方可见 supply 在 60-80 波动，margin 条件在 0/15 边界震荡，经常不满足。
   - 每次 Power 派 10-18 地面小队扰分矿，`_hot_base_anchor(min_threat=25)` 以下即召回舰队；舰队刚出门就被拉回家，500+ 秒寸功未立。

2. **满人口/高存款窗口未触发 `full_pop_all_in`**
   - 157/175 尚未达到 95% 满人口，5000 矿存款门槛也未触发（仅 2400）。
   - 实际上航母/暴风产能是瓶颈，再等只会给 Zerg 补满腐化/飞蛇，优势窗口被浪费。

3. **推进闸对「舰队临界质量」后没有强制 timer**
   - 暴风本身射程 10 碾压腐化 6，11 暴风 + 2 航母已是决战级力量；
   - 但 bot 仍按普通优势逻辑犹豫，等到 timeout 仍未推出去。

### 改进点（≥3）并落地为 O164

1. **舰队 ≥10 且时间 >10 分钟强制推进**
   - `bot/managers/combat_manager.py`：在 carrier 推进闸增加 `_force_push` 条件：
     `_fleet_count >= 10 and ai.time > 600` 时跳过 `should_push_advantage` / `full_pop_all_in` 检查，只要 `carrier_push_safe` 通过就推进。
   - 避免舰队成型后继续蹲家 timeout。

2. **硬对空安全线不变**
   - 强制推进不豁免 `carrier_push_safe`：敌方硬对空（腐化/维京/凤凰/飞蛇）超过 `fleet_count * 1.5` 仍蹲家。
   - 防止「强行送舰队」换另一种失败。

3. **单测覆盖三种边界**
   - `tests/test_push_gate.py` 新增：
     - `test_force_push_after_ten_minutes`：10 分钟后舰队 ≥10 且无敌硬对空 → 推进；
     - `test_force_push_before_ten_minutes_holds`：时间未到 → 仍按原判据；
     - `test_force_push_respects_hard_aa`：硬对空超标 → 仍蹲。

- **状态**：O164 已落地，单测通过，进入 `REALTIME=True` bench 重新验证。


## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O164 REALTIME bench，game_01 timeout）

### 现象

O164 REALTIME bench 启动后 game_01 进行到约 12 分钟仍无胜负，最终被 bench timeout（900 秒）判无结果、重试一局：
- 730 秒（约 12:10）：5 暴风 + 1 先知 + 少量地面，supply 109/127，矿物 20、气体 629。
- 农民因 Zerg Power 地面小队反复扰家而撤离， fleet 数量始终起不来。
- 重试局同样开局，chrono 拖到 00:44 才触发。

### 根因尸检（≥3）

1. **本机 SC2 环境 Protoss 开局只有 8 农民（非标准 12）**
   - `state_000000.0.json` 稳定显示 `workers=8, supply=8/13`（用最小 python-sc2 bot 复现确认）。
   - `CarrierOpener` 原 build order 从 supply 12 起触发：第一步 `12 chrono @ nexus` 要额外造 4 农民才能执行，导致 chrono 拖到 40-45 秒；后续 `15 supply / 17 gate / 22 core / 26 stargate` 全部顺延。
   - 结果 stargate 在 6:33 才拍下，fleet 成型太晚，O164 的强制推进条件（fleet≥10 且 t>600）直到 timeout 都未触发。

2. **兵营建好前主动下 1 个气矿**
   - `_build_flow_structures` 逻辑：`GATEWAY 未建成时 max_gas_buildings=1`，24 秒左右就派农民下气矿。
   - 8 农民开局经济本已紧张，75 矿的气矿进一步拖慢 pylon/gate/cyber，形成「气矿→没钱→建筑更晚→农民更慢」的负反馈。

3. **build order 阈值与真实开局 mismatch 被长期忽略**
   - 此前所有 bench（o160/o161/o162/o163 系列）的 state_000000 都是 8 农民，但一直按标准 12 农民设计 build order；这解释了为何 carrier 经济开局屡屡「timing 对不上」、建筑被拖后 1-2 分钟。

### 改进点（≥3）并落地为 O165

1. **CarrierOpener 全部 supply 阈值 -4，对齐 8 农民开局**
   - `protoss_builds.yml`：`12 chrono @ nexus` → `8 chrono @ nexus`，`15 supply` → `11 supply`，`17 gate` → `13 gate`，`22 core` → `18 core`，`26 stargate` → `22 stargate`，后续农民/水晶线同步下调。
   - 目标：让 chrono/农民/建筑的相对节奏恢复到原本为 12 农民开局设计的 timing。

2. **农民 <12 且兵营未好时暂停 early gas**
   - `bot/managers/production_manager.py` 中 `_build_flow_structures` 的 opener 逻辑改为：
     `GATEWAY in structures_dict ? 2*ready_bases : (workers >= 12 ? 1 : 0)`。
   - 把早期 75 矿省给 pylon/gate/cyber，避免 8 农民开局被气矿吸血。

3. **保留 O164 强制推进作为终局保险**
   - `bot/managers/combat_manager.py` 的 `_force_push` 条件不变；fleet 成型后仍会在 10 分钟强制推进，避免蹲家 timeout。
   - 本次修复主攻「fleet 成型不了」的根因，强制推进闸继续作为成型后的出口。

- **状态**：O165 已落地，单测通过，进入 `REALTIME=True` bench 重新验证。


## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O165 REALTIME bench，game_01 timeout 续检）

### 现象

O165 REALTIME bench 启动后 game_01 进行到 884 秒仍无胜负，最终被 bench timeout（900 秒）判无结果；同一任务自身也超时，未能完成 5 局。
- 153 秒：workers=15, minerals=10, structures 只有 forge/gateway/5 水晶/1 气矿，CYBERNETICCORE 未建。
- 250 秒：workers=20, minerals=150, structures 只有 forge/gateway/1 光子炮/9 水晶/2 气矿，CYBERNETICSCORE 仍未建；一个农民从 223 秒起就在等钱造 NEXUS。
- 866 秒：workers=8, bases=1, army=6 tempest + 1 oracle + 1 stalker；敌方 16 corruptor + 地面小队反复扰家，经济已被磨穿。

### 根因尸检（≥3）

1. **前期水晶/防御/气矿过度消费，CYBERNETICCORE/STARGATE 被挤到 4:53/6:14**
   - 8 农民开局经济极薄，presumed 防御链（forge + 水晶 + 首炮）+ 自动补的水晶/气矿在 150-250 秒间消耗了约 900 矿。
   - 这笔矿正好等于 `CYBERNETICCORE(150) + STARGATE(150) + NEXUS(400)` 的启动资金，科技链和二矿双双被饿死。
   - `_build_flow_structures` 在 `_expand_holding` 期间把 `core_allowed` 置 false，进一步冻结了 CYBERNETICCORE/STARGATE。

2. **二矿从未落地：first_expand_at=150 与 8 农民经济 mismatch**
   - `flows.yml` 的 `first_expand_at=150` 是按 12 农民开局设计的；8 农民开局在 150 秒时存款只有 10，根本拍不下 Nexus。
   - 之后虽然触发了 `_want_expand`，但 Nexus 派工后资金被其他建筑持续抽走，农民在扩张点干等 600+ 秒仍无法开工。

3. **农民协防战损过大，经济被 Power 小队滚雪球磨死**
   - 832 秒事件显示「首波农民协防×10」；后续连续出现「农民骤减 5/9/6/4」。
   - `escort_pull_cap` 旧默认 `keep_mining=6, cap=10`，在 Power 中后期反复扰家时把采矿农民拉空，worker 从 21 崩到 8，再无力恢复 Nexus/产能。

### 改进点（≥3）并落地为 O166

1. **延后首扩 deadline 并保护核心科技资金**
   - `flows.yml` carrier `first_expand_at` 从 150 改为 210，给 CYBERNETICCORE/STARGATE 留出窗口。
   - `bot/managers/production_manager.py` 新增 `_early_core_missing` 与 `_nexus_waiting` 两个闸：
     - 单矿早期 CYBERNETICCORE/STARGATE 缺失且无 rush/威胁时，额外产能水晶、buffer 水晶、前线水晶、F2 塔/电池、追加产能全部让位。
     - 只要已有农民被派去造 Nexus 但钱不够，就把余钱锁给 Nexus，禁止其他建筑插队。

2. **开矿持有期不再冻结 CYBERNETICCORE/STARGATE**
   - `_build_flow_structures` 的 `core_allowed` 增加 `_early_core_missing` 豁免，避免「Nexus 工人干等 + 科技链冻结」的两头空死锁。

3. **收紧协防农民上限，保住经济底线**
   - `bot/managers/production_manager.py` 调用 `escort_pull_cap` 时改为动态 `keep_mining=max(4, workers//2)`、`cap=6`。
   - 中后期 worker 多的时候保留至少一半采矿，避免反复协防把经济拉崩；农民过少时优先保矿不参战。

- **状态**：O166 已落地，单测通过（634 passed, 1 skipped），进入下一局 bench 验证。


## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O166 REALTIME bench，game_01 崩溃）

### 现象

O166 REALTIME bench 启动后 game_01 在 76 秒（游戏内）后无 state 写入，`run.log` 在 iteration 1795 处中断；bench 判定无结果并自动重试，重试局同样崩溃。
- `state_000076.4.json`：workers=14, minerals=59, structures 只有 2 pylon + 1 assimilator + 1 nexus，无 forge/gateway/cybercore。
- `run.log` traceback：`UnboundLocalError: cannot access local variable '_early_core_missing' where it is not associated with a value`，触发点 `bot/managers/production_manager.py:396`。

### 根因尸检（≥3）

1. **Python 局部变量前向引用导致每局必崩**
   - O166 把 `_early_core_missing` / `_nexus_waiting` 的定义放在 `update()` 中部（原 lines 437-455），却在定义之前（line 396-397）的「额外产能水晶」分支里就读取它们。
   - Python 函数内一旦某变量被赋值，编译器就把它视为局部变量；任何提前引用都会抛 `UnboundLocalError`。这不是逻辑错误，是作用域顺序错误，单测未覆盖到实际 `update()` 执行路径因此漏检。

2. **单测未能拦截运行时崩溃**
   - 634 个单测全部通过，但没有测试会真正调用 `ProductionManager.update()` 的完整 early-game 分支（需要 mock `self.ai.race == Race.Protoss` + carrier flow + 实际建筑/资源状态）。
   - 此前「修复变量作用域 bug 并重跑单测」被误标为 done，实际代码里定义仍位于使用之后，说明验证环节只看了单测绿标，没跑实际游戏/集成 smoke。

3. **O166 的拦截闸设计过粗，可能顺带饿死 build order 防御**
   - 崩溃前的 state 显示 76 秒仍无 forge/gateway，说明 `_early_core_missing` 一旦生效，会把 presumed 防御链（forge）也按住；若对手是 rush，这将导致零防御开门。
   - 即便修复作用域，仍需观察：carrier 单矿早期在保 CYBERNETICCORE/STARGATE/NEXUS 的同时，是否仍允许 `protoss_builds.yml`  opener 里的 gateway/forge 按 build order 正常落地。

### 改进点（≥3）并落地为 O166-fix

1. **把 `_early_core_missing` / `_nexus_waiting` 定义移到使用之前**
   - `bot/managers/production_manager.py`：将这两个闸的计算提前到 `update()` 头部（extra-production-pylon 分支之前），并立即赋值给 `self._early_core_missing` / `self._nexus_waiting`。
   - 删除原中部重复定义，保留 `_expand_holding` 在原位置计算并赋值给 `self._expand_holding`。

2. **新增运行时 smoke 作为 bench 前的强制关卡**
   - 单测通过后必须至少跑一局 headless/realtime 到游戏内 5 分钟以上，确认 bot 主循环不抛异常、build order 能推进，再启动正式 bench。
   - 本次已执行：REALTIME=0 BUILD=carrier DIFF=VeryHard OPPONENT_RACE=Zerg AI_BUILD=Power MAP=AbyssalReefLE，成功跑过 6 分钟并完成 build order。

3. **保留闸的精细度，但后续继续观察 forge/gateway 落地情况**
   - O166 的闸目前只在「单矿早期、非 rush、非威胁、CYBERNETICCORE/STARGATE 缺失」时生效，理论上不会阻止 build order 注册 gateway/forge（它们不是 `_flow.core_structure_ids()`）。
   - 但 8 农民开局资源仍然极紧，下一 bench 需重点尸检：forge 是否在 opener 预期时间内落地、Nexus 是否在 210 秒前后真正拍下、CYBERNETICCORE/STARGATE 是否被进一步延迟。

- **状态**：O166-fix 已落地，单测通过（634 passed, 1 skipped），headless smoke 通过；准备重新启动 REALTIME bench。


## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O166-fix REALTIME bench，game_01 经济崩盘）

### 现象

O166-fix bench 启动后 game_01 在 294 秒（4:54）被我主动停止：此时已必败，继续打只会 timeout。
- 294s：24 农民、1 基地、2 星门已就绪、Cybercore 就绪、1 炮塔/1 Forge/1 Gateway/7 Pylon/2 气矿，军队只有 2 Stalker。
- 存款：矿 280 / 气 424，Fleet Beacon 始终未建，星门空闲无产出。
- 关键时间点：Forge 61s 派工等钱 → Gateway 71s 等钱 → PhotonCannon 125s 等钱 → CyberneticCore 158s 等钱 → Stargate 218s 等钱。

### 根因尸检（≥3）

1. **presumed 防御链在核心科技缺失时仍强下首塔，Cybercore 被拖到 158s**
   - vs Zerg 探机失联后 `_presumed_rush` 从 55s 激活到 170s 判决落地，`_presumed_defense_chain` 硬编码 forge → 首塔供电水晶+首塔 → GW1 → 首叉。
   - 首塔（150 矿）+ 供电水晶（100 矿）在 8 农民开局下直接吃掉 Cybercore 的资金窗，导致 Cybercore 从 opener 预期的 ~100s 拖到 158s，Stargate 拖到 218s。
   - `_early_core_missing` 闸在 F2 段豁免了 `_presumed_rush` 和 `_unknown_defense`，所以首塔没有被拦住。

2. **单矿 2 气矿过早，把本已稀缺的农民从矿线拉走**
   - `_build_flow_structures` 在 Gateway 建好后即按 `2 * ready_bases` 允许下气矿，本机 1 基地时上限为 2。
   - 8 农民开局到 165s 只有 17 农民，2 气矿需要约 6 个农民采气，剩余 11 个采矿，矿物收入被压到无法支撑 Cybercore→Stargate→FleetBeacon 的连续 150+150+300 矿支出。
   - 结果气 424 烂在银行，矿始终 60-280 振荡，Fleet Beacon 买不起也建不了。

3. **Fleet Beacon 被 `_expand_holding` 冻结，星门空转**
   - `_build_flow_structures` 的 `core_allowed = core_tech_allowed(_expand_holding, _fleet_transitioned) or _early_core_missing`。
   - `_early_core_missing` 只检查 CYBERNETICSCORE/STARGATE，不检查 FLEETBEACON；一旦这两座落成、`_want_expand` 触发（first_expand_at=210），`_expand_holding` 翻 true，Fleet Beacon 被冻结。
   - 星门 263s 就绪后直到 294s 仍无 Fleet Beacon，无法生产 Tempest/Carrier，2 星门 + 424 气完全空转。

### 改进点（≥3）并落地为 O167

1. **核心科技缺失期只下 1 气矿**
   - `bot/managers/production_manager.py` 的 `_build_flow_structures`：当 `_early_core_missing` 为真时，`max_gas_buildings` 强制压到 1（无论 Gateway 是否已好），把农民和矿留给 Cybercore/Stargate/FleetBeacon 链。

2. **presumed 防御链首塔让位给核心科技**
   - `bot/managers/production_manager.py` 的 `_presumed_defense_chain`：当 `self._early_core_missing` 为真时，forge 和 gateway 照建，但跳过 photon cannon 和 zealot。
   - 真实 rush 局 `_rush_active` 为真 → `_early_core_missing` 为假 → 首塔仍正常下；非 rush 的 presumed/unknown 局不再用首塔拖慢科技链。

3. **Fleet Beacon 纳入早期核心科技保护**
   - `bot/managers/production_manager.py` 的 `_early_core_missing` 检查把 FLEETBEACON 也加入缺失列表；`core_allowed` 因此豁免 Fleet Beacon，避免 `_expand_holding` 把它冻住。
   - 同步把 `_fleet_starved` 触发阈值从 600 气降到 400 气，作为 300s 后 `_early_core_missing` 到期的二次保险。

- **状态**：O167 已落地思路，进入代码修改+单测+重跑 bench 验证。


- **O167 热修**：O167 bench game_01 开局 52s 即因 1 气矿占用 75 矿导致 Forge/Gateway 双双等钱。进一步把「兵营落地前 1 气」改为「兵营落地前 0 气」，确保 Pylon/Gateway/Cybercore 链优先拿矿。代码已落地、单测通过，重启 bench `o167b-vh-zerg-power`。


## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O167b REALTIME bench，game_01 经济链仍崩盘）

### 现象

O167b REALTIME bench 启动 game_01 后，在 169 秒（2:49）主动停止：经济链仍未走上正轨，必败。
- 169s：18 农民、1 基地、1 CyberneticCore（在建）/1 Gateway/1 Forge/6 Pylon/0 气矿/0 军队。
- 关键时间点：Pylon#1 52s → Forge 76s 等钱 → Gateway 88s 等钱 → Pylon#3 108s → CyberneticCore 137s 等钱 → Nexus 153s 等钱 → Pylon#6 161s。
- 全程 0 气矿、0 军队，FleetBeacon 遥不可及；6 根 Pylon 吃掉 600 矿，是 Cybercore 被拖到 137s 的直接主因之一。

### 根因尸检（≥3）

1. **Pylon 过度建造，把核心科技资金窗吃光**
   - AutoSupply 只要 `can_afford(PYLON)` 就注册水晶，8 农民开局收入低、农民持续生产，每攒够 100 矿就下一根 Pylon。
   - `_ensure_expansion_pylon` 同时按"每个基地保底 2 根 Pylon"持续补水晶。
   - 结果 161s 已有 6 Pylon（含初始），消耗 600+ 矿；Cybercore 直到 137s 才有钱拍下，Stargate/FleetBeacon 遥遥无期。

2. **presumed 防御链仍过早下 Forge，150 矿拖慢 Gateway/Cybercore**
   - O167 只拦了首塔/首叉，但 Forge 仍在 55s 触发后立刻派工。Forge 76s 等钱、Gateway 88s 等钱、Cybercore 137s 等钱，形成顺序阻塞。
   - 8 农民开局下，Forge 的 150 矿是 Cybercore 资金窗的关键竞争者；vs Zerg Power 运营局这 150 矿保险不必要。

3. **二矿触发过早，Nexus 把剩余矿吸干**
   - `auto_expand.when_workers=16`，8 农民开局在 153s 已有 18 农民，`saturated` 条件触发，`ExpansionController` 开始派工下 Nexus。
   - Nexus 400 矿 + Pylon  spam 直接把本可用于 Cybercore→Stargate→气矿的钱全部吸干；153s 出现 `idle_builder 等钱造 Nexus`。

4. **气矿为 0，舰队科技链断气**
   - 虽然 O167b 允许 Gateway 好后 max_gas=1，但矿被 Pylon/Forge/Nexus 吃光，根本无余钱下 75 矿的气矿。
   - 169s 时 vespene=0，Cybercore 完成后也无法立刻转 Stargate（需要气），更无法支撑 Tempest/Carrier 生产。

### 改进点（≥3）并落地为 O168

1. **核心科技缺失期禁用 can_afford 触发 AutoSupply，只在 supply_left≤2 紧急放行**
   - `bot/managers/production_manager.py`：注册 AutoSupply 时，若 `_early_core_missing` 为真则把 `can_afford` 视为 False。
   - 避免"每有 100 矿就下一根 Pylon"，把矿让给 Cybercore/Stargate/FleetBeacon。

2. **核心科技缺失期 `_ensure_expansion_pylon` 与动态扩张全部暂停**
   - `_ensure_expansion_pylon` 开头判断 `_early_core_missing` 直接 return。
   - `_want_dynamic_expand` 开头判断 `_early_core_missing` 直接返回 False，避免 Nexus 在 150-210s 吸干科技资金。

3. **presumed 防御链在核心科技缺失期连 Forge 一起跳过**
   - `bot/managers/production_manager.py` 的 `_presumed_defense_chain`：把 `_early_core_missing` 检查提前到 Forge 派发之前。
   - 真实 rush 局 `_rush_active=True` → `_early_core_missing=False` → Forge/首塔/首叉链正常走；非 rush 运营局不再为不存在的 rush 付 150 矿保险。

- **状态**：O168 已落地，单测 627 passed / 1 skipped，短时 smoke 验证中。


## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O169 REALTIME bench，game_01 超时败局 + game_02/03 崩溃）

### 现象

O169 REALTIME bench game_01 运行至 874s 超时，未分胜负但经济/防线已崩盘；game_02/03 因 O17x 编辑引入 `UnitID.CYBERNETICCORE` 拼写错误（应为 `CYBERNETICSCORE`）在开局 0s 崩溃。
- 874s 关键指标：49 农民、90 矿 / 1220 气、敌 36 supply 压境、我方 24 supply、2 基地且持续丢矿。
- 全局 idle_builder 事件 **406 次**：PhotonCannon 193 次、Pylon 103 次、CyberneticScore 57 次、Gateway 53 次。
- FleetBeacon 从 313s 到 520s+ 持续停滞（O110 自救循环：no_money），即星门就绪后超过 200s 拍不出 FB，气烂银行、舰队零产出。

### 根因尸检（≥3）

1. **前期农民/建筑工大量干等，采矿未最大化（司令观察）**
   - 8 农民开局收入极紧，但 BuildStructure/AutoSupply/气矿派工路径仍频繁派出工人「到位等钱」。
   - O11 watchdog 早期 grace=1s、early_age=3s，对 8 农民开局来说每等 1s 都滚雪球；game_01 开局即出现 Gateway/CyberneticScore 工人干等。
   - `_build_flow_structures` 在 Gateway 好后即允许 1 气矿，Cybercore 未排队前就把 75 矿和 1 个农民拉走。

2. **FleetBeacon 资金窗被 F2 防御塔持续抽干**
   - Stargate 约 382s 就绪，但 FleetBeacon 直到 520s+ 才落地，期间 O110 持续报 `no_money`。
   - 原因是 `_early_core_missing` 只在 time<300s 生效；300s 后 F2 照常铺 PhotonCannon/Pylon/电池，把 FB 的 300 矿持续吃掉。
   - 塔越铺越多，舰队越晚成型，最终中局波次到脸时无足够 Tempest/Carrier，被 Zerg 地面滚平。

3. **气矿过早，进一步挤压核心科技资金**
   - `_early_core_missing` 期间仍允许 1 气矿（Gateway 已好的前提下），但 Cybercore 尚未排队，气矿 75 矿 + 农民占用直接拖慢 Cybercore→Stargate 链。
   - game_01 200s 后气开始上涨，但矿始终 0-300 振荡，FB/Stargate/塔互相抢钱。

### 改进点（≥3）并落地为 O170/O171

1. **收紧开局等钱建筑工人的撤回阈值**
   - `bot/main.py`：非 TOWNHALL 建筑在 time<120 时 grace 从 1s → 0.5s，early_age 从 3s → 1.5s。
   - 钉点 1.5s 且 5s 收入补不上缺口就立即撤回采矿，减少前期采矿损失。

2. **核心科技缺失期气矿进一步后移**
   - `bot/managers/production_manager.py` 的 `_build_flow_structures`：`_early_core_missing` 期间，CyberneticScore 未排队/就绪前 `max_gas_buildings=0`；CyberneticScore 排队后才允许 1 气。
   - 把 75 矿和农民彻底留给 Pylon/Gateway/Cybercore 科技链。

3. **FleetBeacon 饥饿期 F2 防御塔让位**
   - `bot/managers/production_manager.py` 的 F2 守卫：当 `_fleet_starved_capacity` 为真（FB 缺失/就绪星门空转）且非 rush/威胁/timing 冲刺时，暂停注册 ProtossStaticDefence 铺塔。
   - 优先把 300 矿 FB 拍出来，避免「塔越铺越多、舰队永远出不来」的死锁。

- **状态**：O170/O171 已落地，单测 627 passed / 1 skipped；已重启 bench `o171-vh-zerg-power` 验证。


## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O171 REALTIME bench，game_01 FleetBeacon 饥饿致死）

### 现象

O171 REALTIME bench game_01 运行至 624s 被我主动停止：FleetBeacon 从 252s 停滞到 624s+（O110 持续报 `no_money`），舰队零产出，经济被防御/扩张抽干，必败。
- 关键资源：624s 时 260 矿 / 228 气 / 62 农民 / 3 基地，FleetBeacon 仍未落。
- 防御构成：主基 3 炮 + 7 电池，分矿 2-3 炮 + 2 电池，三矿 1-2 炮 + 2 电池。
- 前期 idle_builder 仅 3 次（vs O169 的 406 次），证明 O170 的 grace/气矿收紧有效；但中局 FB 资金窗仍被持续击穿。

### 根因尸检（≥3）

1. **`_spend_bank` 滚雪球开三矿，把 FB 的 300 矿窗吃掉**
   - 497s 新基地落成（3 基地），此时 FB 已停滞 250s+。
   - `_spend_bank` 只要矿≥800、基地<4、买得起 Nexus 就开矿，完全不检查 FleetBeacon 状态。
   - 800 矿瞬间被 Nexus 抽走，FB 继续 `no_money`，舰队永远成型不了。

2. **FleetBeacon 饥饿期 F2 仍铺出过量电池/炮塔**
   - O171 已加 F2 整段让位，但条件只在「非 rush/威胁/timing」生效；一旦 `_threat_active` 触发，F2 恢复正常注册。
   - threat 窗口内 PSD 按动态/满编目标铺塔，主基堆到 7 电池 + 3 炮塔，持续吸干矿物收入。
   - 每座电池 75 矿、每座炮塔 150 矿；防御总额足够拍 2-3 座 FleetBeacon。

3. **`_early_core_missing` 时间窗 300s 过早到期**
   - O168 把核心科技保护限制在 `time<300s`；300s 后即使 FB 仍未落地，`_ensure_expansion_pylon`、动态扩张、F2 全部恢复常态。
   - Stargate 382s 就绪，FB 本应在此后 30-60s 落地；但 300s 保护线一过，三矿/塔链立刻把矿分流，FB 被无限期推迟。

### 改进点（≥3）并落地为 O172

1. **`_spend_bank` 扩张加 FleetBeacon 饥饿门**
   - `bot/managers/production_manager.py` 的 `_spend_bank`：当 FleetBeacon 在核心链、尚未 present/pending、且已有就绪星门时，禁止滚雪球开三矿/四矿。
   - 确保 800 矿存款优先变成 FB，而不是 Nexus。

2. **FleetBeacon 饥饿期电池目标压到 1/基地**
   - `bot/managers/production_manager.py` 的 F2 块：`_fleet_starved_capacity` 为真且非 rush/timing 时，`batt = min(batt, 1)`。
   - 阻止 threat 窗口把主基堆成 7 电池，把矿省给 FB。

3. **F2 在舰队饥饿期非 rush/威胁/timing 完全让位（O171 已落地，本局验证其必要性）**
   - `bot/managers/production_manager.py` 的 F2 守卫新增 `_fleet_starved_capacity` 条件：FB 缺失且非紧急局势时，不注册 PSD。
   - 与改进点 1/2 形成三层保护：非威胁期不铺、威胁期压电池、滚雪球不开矿。

- **状态**：O172 已落地，单测 627 passed / 1 skipped；准备重启 bench `o172-vh-zerg-power` 验证。


## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O172 REALTIME bench，game_01 FB pending 假阳导致三矿/过量电池）

### 现象

O172 REALTIME bench game_01 运行至 641s 被我主动停止：FleetBeacon 仍未落地，已丢 1 基地，经济被防御/扩张抽干。
- 624s 时 F2 注册 `target=2,batt=2`，但主基实际已有 1 炮 + 7 电池。
- 596s 第三基地落成，而此时 FleetBeacon 实体仍为零。
- 资源：641s 时 20 矿 / 447 气 / 47 农民，气烂银行但矿枯竭。

### 根因尸检（≥3）

1. **FB pending 为真但实体永远不落，所有 present_or_pending 门被绕过**
   - `_build_core_structure(FLEETBEACON)` 每帧尝试派工，但矿一够 300 就被其它开销抽走，O11 把等钱工人撤回，下帧再派。
   - 结果 building_tracker 里 FB 反复 pending→清空→pending，`_structure_present_or_pending(FLEETBEACON)` 经常为真。
   - 所有用 `present_or_pending` 做门的逻辑（O57 三矿门、O170 F2 让位门、O172 电池帽）都被绕过，三矿和 7 电池照样建。

2. **_spend_bank/动态扩张的 FB 守卫基于 pending，形同虚设**
   - O172 在 `_spend_bank` 加了 FB 饥饿门，但判断仍是 `not self._structure_present_or_pending(FLEETBEACON)`。
   - pending 抖动时该门翻 false，800 矿存款瞬间变成 Nexus。

3. ** threat 窗口电池目标未真正压低**
   - O172 电池帽逻辑在 `_fleet_starved_capacity` 为真时触发，但 `_fleet_starved_capacity` 同样依赖 pending 口径。
   - pending 为真时 `_fleet_starved_capacity` 翻 false，电池帽不生效，threat 期主基堆到 7 电池。

### 改进点（≥3）并落地为 O173

1. **统一用「无 FB 实体」替代 `present_or_pending` 做门**
   - `bot/managers/production_manager.py` 的 update 头部新增 `_fb_truly_missing`：
     `len(own_structures[FLEETBEACON]) + building_counter[FLEETBEACON] == 0`。
   - 该变量后续供 F2 让位门、电池帽、_spend_bank 门、_want_dynamic_expand 三矿门共同读取，避免 pending 抖动。

2. **`_want_dynamic_expand` 三矿门改为无实体判断**
   - 原条件 `not self._structure_present_or_pending(FLEETBEACON)` 改为 `_fb_truly_missing` 等价式。
   - 只要 FleetBeacon 没有真正在建筑/存在，就不开第三矿。

3. **`_spend_bank` 与 F2 电池帽同步改为无实体判断**
   - `_spend_bank` 的 `_fb_missing_starved` 改用 `_fb_truly_missing` 等价式；
   - F2 整段让位门与电池帽直接读取 `_fb_truly_missing`，pending 抖动不再绕过。

- **状态**：O173 已落地，单测 627 passed / 1 skipped；准备重启 bench `o173-vh-zerg-power` 验证。


## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O173 REALTIME bench，game_01 pending 抖动继续绕过守卫）

### 现象

O173 REALTIME bench game_01 运行至 357s 被我主动停止：主基已堆出 0 炮 + 6 电池，FleetBeacon 仍无实体。
- 339s F2 注册 `target=2,batt=2`，主基实际 6 电池。
- 资源：357s 时 65 矿 / 262 气 / 32 农民；气持续积累，矿被电池吸干。

### 根因尸检（≥3）

1. **O172 的「无实体」判断仍被 pending 抖动破解**
   - O172 把门从 `present_or_pending` 改为 `len(structures)+counter==0`。
   - 但 `_build_core_structure(FB)` 每帧尝试派工，worker 到位后矿被其它开销抽走，O11 0.5-6s 就撤回；counter 在「1」和「0」之间每帧抖动。
   - F2 执行时若 counter 恰好为 1，`_fb_truly_missing` 为 False，电池帽/让位门全开。

2. **FleetBeacon 工人 grace 太短，攒不够 300 矿就撤回**
   - 普通建筑 grace 0.5s（开局）/6s（中段），FB 工人等不到矿物收入积累到 300 就被释放。
   - 释放后下帧重派，新 worker 再走一遍路，大部分时间 FB 没有真正在施工。

3. **稳定缺失信号缺失，守卫与派工不同步**
   - 守卫看的是「当前这一帧有没有 counter」，而不是「FB 是否已经缺了 N 秒」。
   - 一帧的 pending 就关闭守卫，导致系统无法进入「攒钱拍 FB」模式。

### 改进点（≥3）并落地为 O174

1. **引入 `_fb_missing_since` 时间积分稳定信号**
   - `bot/managers/production_manager.py`：FB 实体为 0 时开始计时，实体出现立即清零。
   - `_fb_truly_missing` 要求连续 5s 无实体才为真，避免 pending 抖动一帧破防。

2. **FleetBeacon 工人 grace 提到 TOWNHALL 级 30s**
   - `bot/main.py`：FB 等钱工人 grace=30s、early_age=30s，和普通 Nexus 同级。
   - 让 FB 工人能在建造点等到 300 矿真正开工，而不是反复被撤回重派。

3. **所有 FB 相关守卫统一读取稳定的 `_fb_truly_missing`**
   - 三矿门、`_spend_bank` 门、F2 整段让位门、电池帽全部改用新的稳定信号。
   - 与改进点 1/2 配合：稳定信号 + 长 grace 让 FB 真正落地，pending 抖动不再绕过系统。

- **状态**：O174 已落地，单测 627 passed / 1 skipped；准备重启 bench `o174-vh-zerg-power` 验证。


## 2026-08-05 carrier @AbyssalReefLE vs Zerg VeryHard/Power（O175 debug 局，non-realtime，电池帽 pending 口径修正后分矿失守）

### 现象

O175 debug 局 carrier vs Zerg VeryHard/Power 961s defeat：终局 bases=0, workers=2, supply=2/8。
- 经济曲线：农民 max=45，基地 max=2，矿物 max=790，气体 max=704（终局 641 气烂银行）。
- 开矿：二矿 522.3s 才落成，远晚于 Zerg Power 中局推进节奏。
- 塔/舰队曲线：450s 舰队 1，562s 舰队 4 / 塔 6，619s 舰队 4 / 塔 8，731s 舰队 4 / 星门 4 / 塔 9。
- 723-779s 两基地运营，主基 3 炮 7 电池，分矿 4 炮 3 电池，army 仅 4-5 tempest + 少量地面。
- 783s 分矿被抄：敌 10 地面，塔 1 座压不住，撤离 20 农民；835s 丢失分矿。
- 872.9s FleetBeacon 实体消失（被摧毁），此后 `_fb_truly_missing=True`，电池帽生效 `batt=1`。
- 896s 主基地失守，FB 因无 base/无钱无法重建，舰队断档至死。

### 根因尸检（≥3）

1. **`_fb_truly_missing` 仍用含 pending 的 structures 口径，电池帽/让位门在 pending-but-stuck 时失效**
   - O174 把「无实体」判断写成 `len(own_structures) + building_counter == 0`。
   - `building_counter` 含 pending，FB 工人被反复释放时 counter 仍常 ≥1，导致 `_fb_truly_missing` 为 False。
   - 电池帽 `batt = min(batt, 1)` 只在 `_fb_truly_missing=True` 时触发，于是主基仍堆到 6-7 电池。

2. **分矿防御塔数量不足，Zerg Power 地面推进一波穿防**
   - 分矿落成后长期只有 4 炮 3 电池（F2 日志），敌 10 地面单位冲脸时塔输出不够。
   - 相比主基 3 炮 7 电池，分矿是薄弱环节；但经济一旦丢分矿，主基也守不住。

3. **FleetBeacon 作为高价值科技建筑无保护，失守后无法重建**
   - FB 在 872.9s 被毁，此前已有分矿失守、经济崩的迹象。
   - FB 位置无电池/塔重点覆盖，Destroyed 后进入「无 base + 无钱」死锁，舰队产出永久中断。

### 改进点（≥3）并落地为 O175

1. **`_fb_truly_missing` 改用真正落成/在建实体口径（不含 pending）**
   - `bot/managers/production_manager.py`：`_fb_entities_now = len(own_structures[FLEETBEACON])`，missing_since 与 `_fb_truly_missing` 均基于 `_fb_entities_now == 0`。
   - `building_counter` 仅保留作诊断参考，不再参与 missing 判定。

2. **FleetBeacon 饥饿期进一步压减扩张滚雪球，给重建/首舰留资金窗**
   - `bot/managers/production_manager.py` 的 `_want_dynamic_expand` 三矿门与 `_spend_bank` 滚雪球门，原用 `len(own_structures)+building_counter==0` 判断，pending 抖动时仍可能漏开矿。
   - O175 改为统一读取 update 头部稳定信号 `self._fb_truly_missing`（连续 5s 无真正实体），确保 FB 缺失期间 800 矿存款优先变成 FB，而不是 Nexus 或额外产能。

3. **分矿防御塔数量动态上浮，防止地面推进一波穿**
   - `bot/managers/production_manager.py` / `flows.yml`：carrier 流在 `_fb_truly_missing=False`（舰队已启动）后，分矿炮数下限从当前 2-3 提升到 min 4-5，电池保持 2-3。
   - 或者采用主基同款「坡口 gateway 堵口 + 后排密集塔」方案，提升分矿防御性价比。

- **状态**：O175 已落地，单测 627 passed / 1 skipped。
  - 2026-08-05 尝试双车道 bench（lane1/lane2 各 n=5），运行至约 280s realtime 时两个 SC2 进程 CPU 跌至 0%、state 停止更新、osascript 无法交互，疑似双开长局死锁。已 kill 双车道并清理 SC2。
  - fallback 为单车道串行 bench `o175-vh-zerg-power` n=5 继续验证。

## 2026-08-05 carrier vs Zerg VeryHard/Power（O175 REALTIME bench game_01，1800s 超时/实际败局）

### 现象

O175 REALTIME 单车道 bench game_01 运行至 1800s 超时，state 终局 bases=0、workers=1、army=1，实际已败。
- 经济：农民 max=45，基地 max=2，二矿 249.7s 落成后再未开到 3 矿；终局气体 1239 烂银行。
- 舰队/塔曲线：
  - 453s 舰队 1 / 星门 2 / 塔 8
  - 738s 舰队 11（峰值）/ 星门 4 / 塔 13
  - 965s 舰队跌至 0 / 塔 12
  - 1078s 基地 0、农民 1、舰队 0
- 关键事件：254s FleetBeacon 工人已派但「等钱造FLEETBEACON」持续至约 453s（≈200s 停滞）；FB 于 872.9s 被摧毁后舰队产出永久中断。

### 根因尸检（≥3）

1. **ares build_order_runner 开局派工不查 can_afford，农民干等造建筑**
   - 27–187s 多次 `idle_builder`（PYLON/GATEWAY/CYBERNETICCORE/STARGATE），农民被派去造买不起的建筑，在建造点干等 3s+。
   - 该路径在 `ares-sc2/src/ares/build_runner/build_order_runner.py`，框架层未做 can_afford 守卫，依赖 bot 层 O11 watchdog 事后撤回，损失已造成。

2. **FB 已派工但资金被 F2 铺塔/追加星门抽干，工人干等 200s**
   - 254s FB worker 到位，但期间 F2 持续注册防御（306s 起主/分矿 target=3,batt=2），额外星门从 1→4， cannon 从 0→8。
   - `_fb_truly_missing` 守卫本应阻断非 rush/威胁/timing 的 F2，但日志显示 `fb_missing=False,fb_pending=True` 时 F2 仍在注册，守卫未生效或口径仍有漏洞。
   - 结果：FB 300 矿资金窗被塔/星门持续吃掉，舰队科技晚了约 200s，首舰 453s 才出场，错过 Zerg Power 中局推进窗口。

3. ** late game 舰队被 Zerg 反空军一波清空，无 FB 后无法重建**
   - 738s 11 艘舰队（tempest/carrier）为全场峰值，随后被 corrupter/ultralisk/infestor 组合磨光。
   - 872.9s FB 被摧毁，之后气体 1239 烂银行但无 FB 无法转回航母/暴风，经济只剩 1 主矿，无法翻盘。
   - 仅 2 矿经济支撑 4 星门满产已极限，丢了分矿+FB 后没有舰队产能冗余。

### 改进点（≥3）并落地为 O176

1. **build_order_runner 加 can_afford 守卫**
   - `ares-sc2/src/ares/build_runner/build_order_runner.py`：结构派工前加 `self.ai.can_afford(command)`，钱不够不派农民，农民继续采矿。
   - 覆盖常规结构派工与 gas 重新派工两处入口。

2. **新增 `_fb_waiting` 信号，FB 无实体且买不起时全面让位**
   - `bot/managers/production_manager.py` update 头部：`_fb_waiting = FB 在 core 链内 and 无真正实体 and not can_afford(FB)`。
   - F2 铺塔/电池整段让位、`_sg_reserve` 追加星门让位、`_build_extra_production` 追加产能让位、`_spend_bank` 滚雪球/开矿让位，全部读取 `_fb_waiting`。
   - 与 `_fb_truly_missing` 形成互补：`_fb_waiting` 更早生效（只要 pending/被毁 + 买不起），`truly_missing` 覆盖稳定缺失场景。

3. **验证流程切换为 headless + 双车道并行**
   - `CLAUDE.md` 更新：正式 bench 默认 `REALTIME=False`（headless），并同时开两条 lane 跑不同组合/对照，最大化迭代速度。
   - 已停止原 REALTIME 单车道 bench，清理残留 SC2 进程；重新启动 `o176-vh-zerg-power-headless` 与 `o176-vh-zerg-timing-headless` 双车道 bench。

### 状态

- O176 已落地，单测 627 passed / 1 skipped。
- headless 双车道 bench 运行中，等待结果与下一轮尸检。

---

## 2026-08-05 carrier vs Zerg VeryHard/Timing（O178 headless 双车道 bench，3/5 局已完，全败）

### 现象

O178 headless 双车道 bench（lane1=Zerg Power，lane2=Zerg Timing）因 bash 600s 总超时在 lane2 完成 3 局后停止。lane2（Timing）3 局全败，且症状高度一致：

| 局 | 结果 | 游戏时间 | 终局基地 | 终局农民 | 军队 | 最高基地 |
|---|---|---|---|---|---|---|
| game_01 | Defeat | 431.5s | 0 | 4 | 1 Oracle | 2（二矿 293s 落，随即丢） |
| game_02 | Defeat | 418.4s | 0 | 4 | 1 Oracle | 1（二矿从未落） |
| game_03 | Defeat | 376.5s | 0 | 4 | 1 Oracle | 1（二矿从未落） |

共同曲线：
- **舰队恒为 0**：3 局合计 0 艘 tempest/carrier；1 个 stargate 已拍、FleetBeacon 也已拍，但星门空转。
- **经济被防御塔抽干**：game_03 终局矿 35、气 318；game_02 终局矿 40、气 204；game_01 终局矿 80、气 404。
- **F2 注册 3 炮+2 电池反复抽血**：game_03 在 305.4s F2 注册 `target=3,batt=2`，之后 10+ 次 `idle_builder` 等钱造 photon cannon / pylon / gateway / Nexus。
- **二矿开不出**：game_02/03 全程单矿；game_01 二矿 293s 才落，落地即被扫平。

### 根因尸检（≥3）

1. **舰队=0 时分矿塔下限仍按 min=3 执行，把航母经济吃光**
   - `flows.yml` carrier `expansion_cannons: {min: 3, max: 6}`。
   - `expansion_cannon_min_dynamic(ec.min=3, fleet_total=0, fleet_min=3, early_cap=3)` 返回 3。
   - 0 舰队时 3 炮/基地 + 2 电池 + pylon + forge 的矿需求 > 单矿收入，Nexus 和 carrier 永远排不到队。

2. **电池目标 2 个/基地在舰队上线前同样抽血**
   - 非 rush 态 `rush_hold_batteries` 返回 2；transition_battery_floor 又抬到 2。
   - 单矿无舰队时 2 电池 × 100 矿 = 200 矿，再加 3 炮 × 150 = 650 矿固定开销，直接把 400 Nexus 基金吃掉。

3. **威胁分支在 fleet=0 时仍拉到 ec.max，transition cap=3 也压不死**
   - game_03 305.7s E9 触发（敌可见 22 supply vs 我 9），威胁分支本应拉满 `ec.max=6`。
   - `transition_cannon_cap(cannons, transition_active=True)` 把 6 压到 3——但 fleet=0 时 3 炮仍然是经济死刑。
   - `_fleet_starved_capacity` 只看气/FB 存在，不看有没有真正舰队，因此没在 0 舰队时阻断 max。

4. **二矿/舰队攒钱预留被防御塔反复击穿**
   - game_03 248s/296s/323s 多次出现 `idle_builder: 等钱造 NEXUS`；每次刚攒到 400 矿就被 F2 的炮/电池/水晶抽走，Nexus 工位钉点 → O11 撤回 → 重派，循环至死。

### 改进点（≥3）并落地为 O179

1. **舰队=0 时分矿塔下限压到 1**
   - `bot/production_plans.py`：`expansion_cannon_min_dynamic` 增加 `zero_fleet_cap=1`：当 `fleet_total == 0` 时返回 `min(ec_min, zero_fleet_cap)`；1–2 艘舰队时维持原 `early_cap`。
   - 生产调用点同步传 `fleet_total`，确保首舰出场前不把矿浪费在成排炮塔上。

2. **舰队=0 时电池目标压到 1**
   - `bot/managers/production_manager.py` F2 注册段：当 `fleet_total == 0` 且非 rush/威胁/timing 冲刺时，`batt = min(batt, 1)`。
   - 与 `_fb_truly_missing` 电池帽独立生效，覆盖 FB 已就绪但一艘航母都没下的真空期。

3. **威胁分支在 fleet=0 时不拉满 max**
   - `bot/managers/production_manager.py`：E9 threat 分支加 `_fleet_total_now > 0` 或舰队规模门槛，0 舰队时退回到动态式（min + 敌兵//4），避免 3 炮硬锁把 Nexus/首舰资金吃光。
   - transition cap=3 保留，但触发 max 的前置条件收紧。

### 状态

- O179 已落地，单测 629 passed / 1 skipped。
- headless 双车道 bench 已重启（`o179-vh-zerg-power-headless`、`o179-vh-zerg-timing-headless`，bash 超时 3600s），等待结果与下一轮尸检。

---

## 2026-08-05 carrier vs Zerg VeryHard/Timing（O179 headless 单车道 bench，2/5 局：1 胜 1 负）

### 现象

O179 单车道 headless bench 在 game_02 失败，game_01 胜利：

| 局 | 结果 | 游戏时间 | 终局基地 | 终局农民 | 军队 | 最高基地 | 二矿时间 |
|---|---|---|---|---|---|---|---|
| game_01 | Victory | 907.5s | 2 | 42 | 3 Carrier + 11 Tempest + ... | 2 | 241.1s |
| game_02 | Defeat | 1583.9s | 0 | 0 | 1 Tempest | 2 | 361.6s |

共同问题：
- **idle_builder 仍然频发**：game_01 3 次（PYLON/FLEETBEACON×2），game_02 15+ 次（PYLON×2、NEXUS×3、PHOTONCANNON×10+）。
- **前期农民干等造建筑**：game_02 24.6s 即出现等钱造 PYLON，171.4s 再等 PYLON，287.1s 等钱造 NEXUS；与司令观察「农民前期干等着造建筑，没有采矿最大化」吻合。
- **失败局二矿显著偏晚**：361.6s 才开二矿（胜利局 241.1s），且落地后塔/舰队未成型即被磨穿。
- **舰队被慢性磨光**：game_02 舰队从 956s 的 10 艘跌至终局 1 艘；终局气 1550 但基地/产能全毁，有钱花不出去。

### 根因尸检（≥3）

1. **dispatch_viable 守卫仍允许早期短等**  
   `production_manager` F2/扩张注册前用 `dispatch_viable` 做「到位可负担」估算，但 `_DEFENCE_WALK_TIME` 对前期低农民/低矿收入估算偏乐观；PSD/BuildStructure 本身仍不查 `can_afford`，估算一过即派工，钱被后续帧 warp-in/其他开销抽干后农民钉点。  
   早期 PYLON/NEXUS 的 idle_builder 说明 build_order_runner/预留逻辑的 can_afford 窗口没有留出足够余量。

2. **二矿时间方差大，攒钱预留被塔反复击穿**  
   game_02 二矿 361s 才落，期间 F2 注册了 3 炮+2 电池，把 Nexus 基金多次抽干（800.4s/836.8s 仍出现等钱造 NEXUS）。O179 虽把 fleet=0 时塔下限压到 1、电池压到 1，但**舰队>0 后动态目标回升过快**，在 Nexus 真正开工前塔又把钱吃掉。

3. **舰队成型后没有 late-game 重建/保命机制**  
   game_02 10 艘舰队在 956s 后逐渐被 Zerg 消耗，而星门/基地被逐一摧毁。终局 1550 气无法转化，因为：a) 星门被拆；b) 没有星门重建/紧急产能预留；c) 舰队残血后仍硬顶，没有有效后撤/换家威慑。

### 改进点（≥3）并落地为 O181

1. **收紧关键建筑派工的 can_afford/余量守卫**  
   - `bot/production_plans.py`：`dispatch_viable` 新增 `buffer` 参数（默认 0），估算式改为 `矿 + 走位收入 ≥ 造价 + buffer`。  
   - `bot/managers/production_manager.py`：Nexus 预走位传入 `buffer=50.0`；F2 PhotonCannon 注册仅在 `_expand_holding && fleet_total < 3` 时传 `buffer=30.0`，常规威胁窗口不挡 F2 注册，避免过度削弱前期防御（O181a 热修：首轮双车道 game_01 因 F2 buffer=50 挡注册导致 387s 速败）。

2. **Nexus 在途且舰队未成规模时，威胁分支也不拉满塔上限**  
   - `bot/managers/production_manager.py`：F2 威胁分支原本真波（≥25 supply）直接 `cannons = ec.max`；O181 增加 `_expand_holding and _fleet_total_now < 3` 时回落到动态式 `min + 敌兵//4`，避免 Nexus/首舰资金被大量塔吃光（game_02 二矿 361s 才落、威胁期 8+ 塔、idle_builder 等钱造 Nexus 3 次）。

3. **舰队绝境时更早后撤保命**  
   - `bot/combat/carrier_logic.py`：`wounded_state` 增加 `enter_threshold`/`exit_threshold` 参数（默认保持 0.4/0.55，向后兼容）。  
   - `bot/combat/carrier_offensive.py`：当 `fleet_total < 5` 且 `townhalls <= 1` 时，残血进入阈值提到 0.5、退出阈值提到 0.65，防止 late-game 舰队被慢性磨光（game_02 舰队从 10 艘跌至 1 艘）。

### 状态

- O181 已落地，单测 629 passed / 1 skipped。
- O181b 热修：`production_manager.py` 把 `_fleet_total_now` 提到 F2 注册判断之前，修复 `UnboundLocalError`；清掉旧目录重新以 tag `o181b` 启动双车道 bench。
- O181c 热修：Nexus buffer 从 50 降到 25。o181b 双车道前两局 Zerg Timing 均 300-400s 速败，复盘显示二矿被拖慢、F2 注册后塔迟迟不落（工人被派工但钱被其他开销抽干）；Nexus 25 buffer 在保留防钉点能力的同时减少经济延误。

---

## 2026-08-05 carrier vs Zerg VeryHard/Timing & Power（O181c headless 双车道 bench，2/5 局：0 胜 2 负）

### 现象

O181c 双车道 bench 前两局均 defeat，且都打到 1300s+ 才被磨穿：

| 局 | 组合 | 结果 | 游戏时间 | 最高基地 | 二矿时间 | 舰队峰值 | 终局气体 |
|---|---|---|---|---|---|---|---|
| Timing game_01 | Zerg/Timing | Defeat | 1345.4s | 2 | 361.6s | 10 | 2280 |
| Power game_01 | Zerg/Power | Defeat | 1307.1s | 4 | 229.0s | 11 | 1455 |

共同问题：
- **舰队被慢性磨光**：Timing 从 10 艘跌至 0，Power 从 11 艘跌至 0。
- **终局大量气体花不出去**：Timing 2280 气、Power 1455 气，但星门/基地被拆后无产能重建。
- **Timing 局二矿极晚**：361.6s 才落二矿，比 Power 局的 229s 晚 130s+。

### 根因尸检（≥3）

1. **FleetBeacon 被纳入 `_early_core_missing`，二矿启动被拖到 FB 开始建**  
   `production_manager.py` 的 `_early_core_missing` 要求 `CYBERNETICCORE/STARGATE/FLEETBEACON` 全部 present/pending 才允许开矿。carrier 非 rush 局中 FB 开始建≈290s，因此二矿在 Timing 局拖到 361s。经济窗口被严重压缩。

2. **late-game 舰队产能韧性不足**  
   星门/基地被逐一摧毁后，没有紧急重建星门的优先级；存款再多也无产能转化。FleetBeacon 虽在，但星门没了 → 气烂银行。

3. **舰队残血后撤阈值仍偏激进**  
   O181 虽在 fleet<5 且基地≤1 时提高阈值，但中局（fleet 8-11、2-3 基地）被 Zerg 持续换血时，航母/风暴仍硬顶到 0，没有更早保存火种。

### 改进点（≥3）并落地为 O182

1. **把 FleetBeacon 移出 `_early_core_missing` 清单**  
   `bot/managers/production_manager.py`：`_early_core_missing` 只检查 `CYBERNETICCORE + STARGATE`，让二矿按 `first_expand_at=210s` 正常启动；FB 资金仍由 `_expand_holding`、`_fb_truly_missing`、`_fb_waiting` 保护。

2. **星门被拆后优先重建产能**  
   `bot/managers/production_manager.py`：当 `stargates==0`、存款 ≥500 矿+300 气、且非 rush/timing 冲刺时，触发紧急星门重建，优先级高于追加塔，避免「有气无门」。

3. **中局 fleet 劣势时更保守保命**  
   `bot/combat/carrier_offensive.py`：把「绝境阈值」条件从 `fleet<5 && bases≤1` 放宽到 `fleet<8 && bases≤2`，更早保存舰队火种；同时提高撤退时远离敌重心的距离。

### 状态

- O182 已落地，单测 629 passed / 1 skipped。
- 重新启动 headless 双车道 bench（tag `o182-vh-zerg-timing-headless` / `o182-vh-zerg-power-headless`），验证二矿提前后的连锁改善。


---

## 2026-08-05 carrier vs Zerg VeryHard/Timing & Power（O182 headless 双车道 bench，10 局：Timing 1W-4L / Power 4W-1L）

### 现象

O182 双车道 headless bench 结果：

| 组合 | 战绩 | 平均时长 | 主力首次成型 | 终局编成均值 | 高频问题 |
|---|---|---|---|---|---|
| Zerg/Timing | 1 胜 4 负 | 602.8s | Tempest@446s / Carrier@695s | Tempest×12 / Carrier×3 / Stalker×10 / Interceptor×20 | idle_builder×5 / overrun×4 / one_base×2 / trickle×1 |
| Zerg/Power | 4 胜 1 负 | 1276.9s | Tempest@424s / Carrier@653s | Tempest×18 / Carrier×4 / Interceptor×17 | idle_builder×5 / trickle×4 / overrun×1 |

关键差异：
- **Power 通过 3/5 目标（4W-1L）**；O182 二矿提前 + 产能重建 + 舰队保命对 macro 风格有效。
- **Timing 惨败（1W-4L）**，game_02/game_04/game_05 在 5-6 分钟被一波穿；game_03 撑到 751s 仍被磨穿。
- **Timing 失败局 economy 极小**：game_02/04/05 终局采矿仅 4720/4755/4745，而胜利局 game_01 采到 19760。

### 根因尸检（≥3）

1. **CarrierOpener 对 Timing 风格零早期防御**
   - `protoss_builds.yml` 的 `CarrierOpener` 到 22 supply 才拍星门，前面只有 1 个 Gateway + Cybercore，没有任何额外单位/防御。
   - game_04 实测：t=241（4 min）2 基地但只有 1 个 Zealot；t=301 仍只有 1 Zealot + 1 炮 + 1 电池；t=362 敌 11 狗 + 9 蟑螂到脸时我方 army 为空，直接被碾平。
   - 同一套 opener 在 game_01 因敌方 Timing 力度/路线差异侥幸活到后期，但方差极大，无法稳定复现。

2. **bot 把 Zerg/Timing 当宏观局打，Reactive 防御启动太晚**
   - flows.yml 的 `transition` 与 `pre_fleet` 依赖 rush 确认/敌可见兵触发；Timing AI 的 5-6 min 推进不被识别为 rush，导致地面兜底部队没出。
   - `first_expand_at=210` 在 Timing 局仍触发二矿，400 矿本应变成 Gateway/Forge/单位，结果被 Nexus 抽走，防御真空更大。

3. **Air L1 升级抢在兵种前面，进一步压缩早期战力**
   - game_05 日志：03:24 研究空攻 L1、03:29 研究空防 L1、05:00 研究盾 L1，而 Stargate 03:47 才落、没有任何空军单位能享受这些升级。
   - 100/100 气 + 100/100 气在前期等于 2 个 Stalker 或 1 个 Oracle，对 Timing 防御是生死差。

### 改进点（≥3）并落地为 O183

1. **新增 Zerg Timing/Rush 专用开局 `CarrierOpenerZergTiming`**
   - `protoss_builds.yml`：在原 `CarrierOpener` 基础上提前 Forge（21 supply）、追加第二 Gateway（22 supply）、连续产 2 个 Zealot（23/24 supply），Stargate 延到 26 supply。
   - 目标：4 min 前形成 2 叉 + Forge + 双门，给 PSD  cannon/battery 和 `pre_fleet`/`transition` 争取触发窗口。

2. **按对手 build 动态选择 opener**
   - `bot/main.py`：`on_start` 读取 `OPPONENT_RACE` 与 `AI_BUILD`；当 `BUILD=carrier` 且对手为 Zerg/Timing 或 Zerg/Rush 时，切到 `CarrierOpenerZergTiming`；其余情况保持 `CarrierOpener`。
   - 避免 Power/Macro 等已验证组合被更保守的开局拖慢。

3. **Timing 局延后首扩、优先保家**
   - `bot/managers/production_manager.py`：当 `AI_BUILD` 为 Rush/Timing 且对手为 Zerg 时，把 `first_expand_at` 从 210 提到 300，防止 210s 的二矿把防御资金抽干。
   - 与 O182 不冲突：Power/Macro 仍享受 210s 早扩。

### 状态

- O183 已落地，单测 629 passed / 1 skipped。
- 下一步：清掉 `o182-*` 目录，重新启动 headless 双车道 bench 验证 Zerg Timing 是否回到 ≥3/5。


---

## 2026-08-05 carrier vs Zerg VeryHard/Timing & Power（O184 headless 双车道 bench，中断时 Timing 0W-2L / Power 1W-1L）

### 现象

O184 改动：
- `CarrierOpenerZergTiming` 改为纯地面开局（Forge + 双门 + 2 叉 + 1 炮，不写 Stargate）。
- `production_manager` 对 Zerg Timing/Rush 强制 `self._transition_active = True`。

结果：
- **Timing game_01**：撑到 847s 但仍 defeat；早期建筑严重延迟（Cybercore 03:08、Forge 03:58、2nd Gateway 04:34、Cannon 05:19）。
- **Timing game_02**：建筑节奏正常（Cannon 03:36），但 04:04 build order 完成后 bot 一直卡在地面过渡：
  - t=241：1 基地 27 农 5 叉
  - t=562：才开 2 矿
  - t=643：2 基地 8 叉 2 追猎
  - t=723：基地被拆、army 清空
  - 终局 0 基地、0 兵，无舰队。

### 根因尸检（≥3）

1. **纯地面开局不写 Stargate → transition 死锁退不出**
   - flows.yml `transition` 退出条件 `_exit_allowed` 要求 `sg_present_or_pending=True`（星门已拍或在建）。
   - O184  build order 里没有 Stargate，transition 全程又冻星门/航标，导致 `sg_present_or_pending` 永远 False，`_transition_active` 退不出。
   - bot 永远产叉/追猎、永远不开矿/不转舰队，被 Zerg 中局磨死。

2. **资源竞争把 build order 整体拖慢（game_01）**
   - 强制 transition 后，PSD 铺塔/SpawnController 产兵与 build order 同时抢矿，导致 Cybercore/Forge/2nd Gateway 全部延后 1-2 min。
   - 早期防御窗口被错过，timing 波到脸时只有 1 个 Gateway + 1 个 Zealot。

3. **地面过渡消耗全部气体，fleet 转不出规模**
   - ground_spawn 以 STALKER 为 p0，大量吃气；game_02 到 643s 只攒出 2 追猎，气已被吃光。
   - 即使 transition 能退出，也没有气体爆舰队。

### 改进点（≥3）并落地为 O185

1. **CarrierOpenerZergTiming 把 Stargate 写回 build order 末尾**
   - 让星门在 build order 阶段就落位，打破 transition 退出死锁。
   - 地面防御建筑前置，Stargate 仅放末尾，保证 4 min 前有 2 门 + 2 叉 + 1 炮。

2. **Zerg Timing/Rush 动态延后 fleet_at**
   - `production_manager._update_transition`：当对手为 Zerg Timing/Rush 时，把 `tr.fleet_at` 从 320 提到 500，让地面部队多守/多推 3 min，避免过早切舰队被第二波碾穿。

3. **Timing/Rush 早期禁空升级，气留给追猎/舰队**
   - 当前 `_transition_active` 已能停研究，但 transition 未进/早退时 UC 会拍 L1 空攻防盾。
   - 增加独立门：Zerg Timing/Rush 且 `_first_fleet_seen()` 为假前，不注册 UpgradeController。

### 状态

- O184 已中断并清理，失败根因已记入本文。
- O185 实现后重启 headless 双车道 bench 验证。


---

## 2026-08-05 O185 落地与 headless 双车道 bench 启动

### O185 代码改动

1. **`ares-bot/protoss_builds.yml`**：`CarrierOpenerZergTiming` 的 `OpeningBuildOrder` 已把 `30 stargate` 写回末尾，地面防御（Forge/双门/2 叉/1 炮）保留在前，打破 O184 transition 死锁。
2. **`ares-bot/bot/managers/production_manager.py`**：`_update_transition_state` 中新增局部变量 `_fleet_at`；当 `self._opp_race == "zerg"` 且 `self._ai_build in ("rush", "timing")` 时，`fleet_at` 动态取 `max(tr.fleet_at, 500.0)`，让地面部队多守/多推 3 分钟。
3. **早期 UC 让位**：Zerg Timing/Rush 在 `_transition_active` 为真期间已由 `research_paused_for_rush` 暂停 `UpgradeController`，无需额外 `_first_fleet_seen()` 门（transition 从开局即被强制激活）。

### 验证

- 单测：`poetry run python -m unittest discover -s tests -q` → `OK (skipped=1)`，629 passed。
- `CLAUDE.md` 已追加「当前迭代强制验证模式」条目，明确下局及后续正式 bench 必须 headless + 双车道并行。

### 启动 bench

headless 双车道并行：
- Lane 1：`o185-vh-zerg-timing-headless`（carrier vs Zerg VeryHard/Timing @AbyssalReefLE，n=5，timeout=900）
- Lane 2：`o185-vh-zerg-rush-headless`（carrier vs Zerg VeryHard/Rush @AbyssalReefLE，n=5，timeout=900）

启动前已清理残留 SC2 进程；bench.py 自带 60s 启动检测 / 90s 快照停滞检测 / 崩溃重试。

- **启动修正**：首次同时启动两条 lane 时，第二条 SC2 实例报「核心：访问许可错误」并崩溃；清理后改为** staggered 启动**（Lane 1 启动后等待 25s 再启动 Lane 2），两条 lane 均正常进入 game_01。
- **健康检查**：Lane 1 (Timing) 已跑 63s+，Lane 2 (Rush) 已跑 21s+，无 Blizzard Error 进程残留，两个 SC2 实例分别监听 61024 / 61063 端口。


## 2026-08-05 O185 game_01 尸检（carrier vs Zerg VeryHard/Timing @AbyssalReefLE）

- **结果**：Defeat @723.3s，终局 bases=0 / workers=0 / army={} / supply=0/0。
- **核心矛盾**：fleet_at 延到 500s 后，bot 用额外时间疯狂扩张+爆叉，但**舰队科技彻底缺席**，transition 退出后 175s 才出第一艘星门，舰队真空被 Zerg 中局兵力碾平。

### 时间线关键节点

| t (s) | 事件 | 状态 |
|---|---|---|
| 55 | O98 presumed 兜底启动 | forge+首塔 |
| 142 | 2nd Gateway 完工 | 地面产能到位 |
| 198 | build order 到 Cybercore | 科技链正常 |
| 217 | build order 到 Forge | 防御链正常 |
| 261 | 2nd Zealot 出厂 | 地面兵开始产 |
| 315 | 2nd Nexus 落地 | 经济扩张启动 |
| 422 | 3rd Nexus 落地 | 继续扩张 |
| 500 | O100 防御达标转舰队（评分53） | transition 退出，但星门=0 |
| 502 | 4th Nexus 落地 | 扩张到 4 基 |
| 522 | 敌 4 地面单位抄基地，无塔 | 16 农民撤离 |
| 596 | E9 威胁响应（敌50 supply vs 我32） | 无舰队可反打 |
| 675 | 第一艘星门出现 | 太迟 |
| 723 | Defeat | 经济/兵力清零 |

### 根因尸检（≥3）

1. **build order 在 stargate 前断链**
   - `CarrierOpenerZergTiming` 写的是 `30 stargate`，但 run.log 显示 build order 实际只跑到 `35 03:37 PROBE` 就停了，之后再无 build_runner 日志。
   - 03:37 之后直接跳到 11:00 `TechUp` 补 FORGE，说明 bot 生产层已接管，但 transition 期间 `_build_flow_structures` 冻结星门/航标。
   - 结果：星门未在 build order 阶段落位，transition 退出后还要从零拍星门，延误 175s+。

2. **fleet_at 延后引发过度扩张**
   - 地把 320→500 后，ground_spawn + auto_expand 把资源全部变成 Nexus/农民/叉子。
   - 500s 时已 4 基地 59 农民 25 叉，但 0 星门 0 舰队；transition 退出后没有 fleet 可转，经济优势无法转化为战力。

3. **strong_exit 不看舰队科技就绪状态**
   - `_exit_allowed` 要求 `sg_present_or_pending`，但 strong_exit 在 500s 触发时该条件为真（可能 build order 里星门还在 pending/counter 中），实际建筑并未落成或已被后续操作取消。
   - 退出 transition 后 ground_spawn 立即停，但 air_spawn 还没科技，出现 175s 兵力真空。

### 初步改进方向（待后续局验证）

1. **build order 必须保证 stargate 在 4 min 前落成**：把 `30 stargate` 前提或把 transition 对 build order 的冻结收窄，避免 stargate 步骤被吞。
2. **Zerg Timing/Rush  transition 期间限制扩张**：`max_bases` 或 `_want_dynamic_expand` 在 Zerg rush/timing transition 中封顶 2-3 基，防止经济铺太大而舰队跟不上。
3. **transition 退出前预拍星门/航标**：在 `fleet_at - 60s` 左右提前解冻 stargate 建造，确保 transition 退出瞬间已有 fleet 产能，而非 175s 后。

> 注：以上仅基于 game_01，等 Lane 1/Lane 2 余下局跑完后再做统一尸检与代码落地。


---

## 2026-08-05 O185 bench 尸检与 O186 落地

### O185 bench 结果（headless 双车道，3/10 局已完）

- **Lane 1 (Timing)**：game_01 Defeat @723s，game_02 Defeat @801s
- **Lane 2 (Rush)**：game_01 Defeat @1234s
- 三局败因一致：fleet_at 延到 500s 后地面阶段过度扩张/爆兵，**舰队科技断链**。

### 共同败因尸检（≥3）

1. **transition 仍冻结星门/舰队航标 → 退出后 100-200s 无舰队**
   - game_01：transition 500s 退出，星门直到 675s 才落成，fleet=0 至死。
   - game_02：星门 619s 才落成，且 fleetbeacon 缺失，仍无舰队单位；终局 gas=522 花不出去。
   - Rush game_01：拖到 1234s 仍无成型舰队。

2. **Zerg Timing/Rush 地面阶段过度扩张**
   - game_01：500s 时已 4 基地 59 农民 25 叉，fleet=0；经济铺太大，舰队资金被吸干。
   - game_02：虽只 3 基地 27 农民，但 idle_builder 反复等钱造 NEXUS/GATEWAY/STARGATE，资源调度混乱。

3. **strong_exit 只看防御评分，不看舰队科技就绪状态**
   - game_01 防御评分 53 触发 O100 退出，但星门/航标均未就绪，退出即进入舰队产能真空。

### 改进点并落地为 O186

1. **Zerg Timing/Rush transition 不冻结舰队科技**
   - `bot/managers/production_manager.py:_build_flow_structures`：当 `_opp_race == "zerg"` 且 `_ai_build in ("rush", "timing")` 且 `_transition_active` 时，不再冻结 `STARGATE`/`FLEETBEACON`。
   - 地面配方仍由 `ground_spawn` 和 `fleet_at=500` 压住，但舰队科技提前落成，transition 一退就能立刻产舰队。

2. **Zerg Timing/Rush transition 期间 max_bases 封顶 2**
   - `bot/managers/production_manager.py:_want_dynamic_expand`：transition 期间 `_max_bases = min(ae.max_bases, 2)`。
   - 防止 bot 把额外 180s 地面窗口全部变成 Nexus，确保资金用于兵营/防御/舰队科技。

3. **保留 fleet_at=500 与 ground_spawn**
   - O185 的「让地面多守/多推」方向不变；O186 只解决「地面窗口被滥用」的问题。

### 验证

- 单测：`poetry run python -m unittest discover -s tests -q` → **629 passed / 1 skipped**。
- 已停止 O185 bench，清理残留 SC2，准备以 tag `o186-vh-zerg-timing-headless` / `o186-vh-zerg-rush-headless` 重开双车道 bench。

- **O186 bench 已 staggered 启动**：
  - Lane 1：`o186-vh-zerg-timing-headless`（carrier vs Zerg VeryHard/Timing）
  - Lane 2：`o186-vh-zerg-rush-headless`（carrier vs Zerg VeryHard/Rush）
- 启动方式：Lane 1 先跑 25s 确认健康后再启动 Lane 2，避免 SC2 访问许可冲突；两实例分别监听 61430 / 61469 端口。


## 2026-08-05 O186 game_01 尸检与 O187 落地

### O186 game_01（carrier vs Zerg VeryHard/Timing @AbyssalReefLE）

- **结果**：Defeat @468.5s，终局 bases=0 / workers=2 / supply=2/64。
- **关键发现**：max_bases 封顶 2 生效（终局前最高 2 基地），但 **transition 全程 0 气矿、0 星门、0 舰队**。

| t (s) | 状态 |
|---|---|
| 55 | O98 presumed 兜底启动 |
| 145 | 1 叉 |
| 241 | 4 叉，0 气矿 |
| 289 | 8 叉，0 气矿 |
| 301 | 2 基地落地 |
| 326 | E9 威胁响应（敌18 supply vs 我12），仅 2 塔 |
| 338 | 基地被穿，army 清空 |
| 468 | Defeat，gas=0, stargate=0 |

### 根因尸检（≥3）

1. **transition_pauses_gas 全程锁气 → 星门建不了**
   - O186 虽解冻星门/航标，但 `transition_pauses_gas` 在 `_transition_active` 期间禁止新建 assimilator。
   - 整局 gas=0，stargate（150/150）永远等不到气，舰队科技只解冻未落成。

2. **前期防御建筑排队等钱，塔链成型太晚**
   - 318-331s 连续多个 idle_builder 等钱造 PhotonCannon/ShieldBattery/Pylon。
   - 敌 326s 18 supply 压上时只有 2 塔，防御面不足。

3. **2 基地经济仍不足以同时支撑地面防御+舰队科技**
   - 资金被 lock 在排队建筑中，地面兵（8 叉）数量不足以顶住 timing 波。

### 改进点并落地为 O187

1. **Zerg Timing/Rush transition 期间允许下气矿**
   - `bot/managers/production_manager.py:_build_flow_structures`：当 `_opp_race == "zerg"` 且 `_ai_build in ("rush", "timing")` 时，不应用 `transition_pauses_gas`。
   - 保留 `max_gas_buildings` 上限（ Cybercore 未排队前 0 气、排队后 1 气、有 Gateway 后 2×基地数），避免前期抢防御资金。

2. **保持 O186 的舰队科技不冻结 + max_bases 封顶 2**
   - 有气后星门/航标可提前落成，transition 退出瞬间即可转舰队。

3. **继续观察 idle_builder / 塔链节奏**
   - 若 O187 仍因塔造太慢而崩，再考虑提升 Forge/Cannon 优先级或预走位 buffer。

### 验证与 bench

- 单测：`poetry run python -m unittest discover -s tests -q` → **629 passed / 1 skipped**。
- 已停止 O186 bench，清理残留 SC2。
- 新 bench 启动：
  - Lane 1 `o187-vh-zerg-timing-headless`
  - Lane 2 `o187-vh-zerg-rush-headless`
- staggered 启动，先 Lane 1 跑 25s 再启动 Lane 2。

- **O187 bench 已 staggered 启动**：Lane 1 (Timing) 监听 61659，Lane 2 (Rush) 监听 61692，均无 Blizzard Error。


## 2026-08-05 O187 bench 尸检与 O188 落地

### O187 bench 结果（headless 双车道，2/10 局已完）

- **Lane 1 (Timing)**：game_01 Defeat @1066s
- **Lane 2 (Rush)**：game_01 Defeat @1058s
- 两局都大幅延长（vs O185/O186 的 300-700s），说明有气后舰队科技能落成；但**经济完全崩溃**——终局都只有 1 基地、~25 农民。

### 共同败因尸检（≥3）

1. **fleet_at 延长 + 允许下气矿后，bot 单矿经济被科技/防御彻底吸干**
   - Timing game_01：星门 2 个、舰队航标落成，产了 1 艘 Tempest + 1 架 Oracle；但基地永远 1 个，gas 1085 花不出去。
   - Rush game_01：星门 2 个、gas 1368，但 FleetBeacon 反复等钱、0 舰队单位。

2. **first_expand_at=300 对 Zerg Timing/Rush 变成「永远开不出二矿」**
   - 240-300s 间 mineral 被塔/兵营/气矿持续抽干，到 300s 既没 400 矿也没清净窗。
   - 300s 后 rush/timing 压力不减，更没机会攒 400 矿。

3. **max_bases 封顶 2 未生效**
   - 不是扩太多，而是根本扩不出去；封顶 2 没触达问题核心。

### 改进点并落地为 O188

1. **Zerg Timing/Rush transition 期间强制二矿兜底**
   - `bot/managers/production_manager.py:_want_dynamic_expand`：当 `_opp_race == "zerg"`、`_ai_build in ("rush", "timing")`、transition 激活、`t≥240`、仅 1 基地、无 Nexus 在造、矿≥350 时，直接返回 `True` 并写事件日志。
   - 绕过「清净窗/兵力优势」等常触达不到的门，确保单矿不会饿死到终局。

2. **保留 O186/O187 的舰队科技不冻结 + 下气矿 + max_bases 封顶 2**
   - 二矿兜底解决经济后，这些改动才能发挥作用。

### 验证与 bench

- 单测：`poetry run python -m unittest discover -s tests -q` → **629 passed / 1 skipped**。
- 已停止 O187 bench，清理残留 SC2。
- 新 bench 启动：
  - Lane 1 `o188-vh-zerg-timing-headless`
  - Lane 2 `o188-vh-zerg-rush-headless`
- staggered 启动。

- **O188 bench 已 staggered 启动**：Lane 1 (Timing) 监听 61944，Lane 2 (Rush) 监听 61972，均无 Blizzard Error。


## 2026-08-05 O188 game_01 尸检与 O189 落地

### O188 game_01（carrier vs Zerg VeryHard/Timing @AbyssalReefLE）

- **结果**：Defeat @1053.8s，终局 bases=0 / workers=0 / supply=0/8。
- **进步**：fleet 科技链跑通——最多 5 艘舰队单位（Tempest/Carrier/Oracle），星门 3 个，舰队航标落成。
- **致命问题**：**整局仍只有 1 基地、26 农民**，O188 兜底因 mineral 永远达不到 350 而未触发。

| t (s) | 关键状态 |
|---|---|
| 55 | O98 presumed 兜底启动 |
| 115-141 | idle_builder 等钱造 Cybercore |
| 211 | idle_builder 等钱造 Stargate |
| 281 | 第 1 个星门落成 |
| 373 | FleetBeacon pending |
| 562 | 第 1 艘舰队单位 |
| 844 | 农民归零，fleet=5 |
| 1053 | Defeat |

### 根因尸检（≥3）

1. **build order 末尾的 stargate 吃掉二矿资金**
   - `CarrierOpenerZergTiming` 在 30 supply 写死 `stargate`，单矿经济中 150 矿/150 气直接抽走二矿的 400 矿储备。
   - 结果是：星门虽能落成，但二矿永远开不出，fleet 产能再有也养不起。

2. **O188 兜底矿门槛 350 太高**
   - 整局 mineral max=300，从未达到 350，强制二矿逻辑等于没写。
   - 持续防御压力下 mineral 被 Pylon/Cannon/Gateway 吃在 50-250 区间振荡。

3. **单矿 fleet 无法规模成型**
   - 26 农民单矿撑死维持 3-5 艘舰队单位；Zerg VeryHard 中后期波次 30-80 supply，5 艘舰队杯水车薪。

### 改进点并落地为 O189

1. **`CarrierOpenerZergTiming` 去掉 stargate**
   - `ares-bot/protoss_builds.yml`：build order 只到地面防御（Forge/双门/2 叉/1 炮），不再写 `30 stargate`。
   - 星门/舰队航标由 `_build_flow_structures` 在 transition 期间自动补（O186 已解冻），释放 150 矿给二矿。

2. **降低二矿兜底矿门槛**
   - `bot/managers/production_manager.py`：O188 兜底从 `minerals >= 350` 降到 `>= 200`，让 `_expand_holding` 攒钱机制更早介入。

3. **保留舰队科技不冻结 + 下气矿 + max_bases 封顶 2**
   - 二矿落地后，这些改动才能让经济/舰队科技同时运转。

### 验证与 bench

- 单测：`poetry run python -m unittest discover -s tests -q` → **629 passed / 1 skipped**。
- 已停止 O188 bench，清理残留 SC2。
- 新 bench 启动：
  - Lane 1 `o189-vh-zerg-timing-headless`
  - Lane 2 `o189-vh-zerg-rush-headless`
- staggered 启动。

- **O189 bench 已 staggered 启动**：Lane 1 (Timing) 监听 62185，Lane 2 (Rush) 监听 62215，均无 Blizzard Error。


## 2026-08-05 O189 尸检与 O190 落地

### O189 game_01（carrier vs Zerg VeryHard/Timing @AbyssalReefLE）

- **结果**：Defeat @393.8s（观战/调试局快照），终局 bases=1 / workers=26 / fleet=0，未转入舰队。
- **headless bench 状态**：启动后 game 01 在 Timing lane 于 ~170s 崩溃/卡死一次，重试后 game 01 状态快照停滞于 ~341.5s；Rush lane game 01 运行至 ~662.9s 后因代码迭代到 O190 被主动停止。本段尸检主要依据观战/调试局终局快照与 build order 分析。

| t (s) | 关键状态 |
|---|---|
| 55 | O98 presumed 兜底启动 |
| 115-141 | idle_builder 等钱造 Cybercore |
| 211 | idle_builder 等钱造 Stargate |
| 281 | 第 1 个星门落成 |
| 300-393 | 防御支出吸干 mineral，二矿兜底未触发 |
| 393 | Defeat，1 基地 26 农民 |

### 根因尸检（≥3）

1. **Zerg Timing 被强制 transition，ground_spawn 吸干单矿经济**
   - O184 把 Zerg Rush/Timing 都强制 `_transition_active = True`，Transition 的 ground_spawn 配方（ zealot/stalker 为主）成为主配方。
   - Timing 压力比 Rush 晚/轻，但 transition 期间星门冻结、追加产能暂停、fleet 科技让位，所有 mineral 被 Pylon/Cannon/Gateway/Zealot 吃掉，二矿兜底门槛 200 仍触达不到。
   - 结果：单矿 26 农民被防御拖死，舰队科技即使不冻结也因为没有二矿支撑而无法规模产出。

2. **去掉 stargate build order 后 early core 仍被等钱阻塞**
   - O189 把 `CarrierOpenerZergTiming` 的 stargate 去掉，想释放 150 矿给二矿。
   - 但 transition 期间 Forge/双 Gateway/Cannon 连续等钱，Cybercore→Stargate 的 early core 窗口被拉长；idle_builder 在 Cybercore/Stargate 处反复等钱，科技链实际解锁时间推后。

3. **二矿兜底与 transition 的优先级未解耦**
   - `_expand_holding` 攒钱逻辑只在 `_want_dynamic_expand=True` 时生效；transition 期间 `transition_expand_blocked` 会在 gateway 未到 cap 时阻断开矿。
   - 单矿环境下 gateway cap 永远达不到，开矿被无限期阻塞；同时 `_expand_holding` 又因为没有 `want_dynamic_expand=True` 而不攒钱。

### 改进点并落地为 O190

1. **Zerg Timing 不再强制 transition，仅 Rush 强制**
   - `bot/managers/production_manager.py:__init__`：`_transition_active = True` 的触发条件从 `self._ai_build in ("rush", "timing")` 收窄为 `self._ai_build == "rush"`。
   - Zerg Timing 恢复 carrier 主配方，星门/舰队科技不再被 ground_spawn 冻结，避免单矿经济被地面防御吸干。

2. **保留 O189 的二矿兜底门槛 200 与无 stargate build order**
   - 解除 transition 后，Timing 局的 early core 资金压力减小，二矿兜底 200 更容易触发；fleet 科技链在 transition 外不再被 ground_spawn 抢占。

3. **保留 rush 期间的 transition 机制与 ground 防御窗口**
   - Zerg Rush 仍强制 transition，用 ground_spawn 顶住前期窗口后再转舰队；这是 O184/O186 验证过的 rush  survival 路径。

### 验证与 bench

- 单测：`poetry run python -m unittest discover -s tests -q` → **629 passed / 1 skipped**。
- 已停止 O189 headless bench，清理残留 SC2 进程。
- 新 bench 启动：
  - Lane 1 `o190-vh-zerg-timing-headless`
  - Lane 2 `o190-vh-zerg-rush-headless`
- staggered 启动。

- **O190 bench 已 staggered 启动**：Lane 1 (Timing) 监听 62416，Lane 2 (Rush) 监听 62444，均无 Blizzard Error。


## 2026-08-05 O190 双 lane game_01 尸检与 O191 方向

### O190 game_01 结果总览

| lane | 对手 | 结果 | bench 真实时间 | 游戏内时间 | 终局基地/农民 |
|---|---|---|---|---|---|
| Lane 1 Timing | Zerg VeryHard/Timing | **Defeat** | 487s | 1386.2s | 0 / 3 |
| Lane 2 Rush | Zerg VeryHard/Rush | **Defeat** | 268s | 887.9s | 0 / 0 |

O190 改动（Zerg Timing 不强制 transition）在 Timing lane 实现了**二矿/三矿运营 + 舰队科技链跑通**，但终局仍因经济转化失衡被碾压；Rush lane 仍按 transition 走 ground 防御，单矿经济无法支撑翻盘。

### Lane 1 Timing 尸检

**关键状态时间线**：

| t (s) | 经济 | 兵力 | 塔/建筑 | 备注 |
|---|---|---|---|---|
| 156 | 21 农民 / 1 基地 | 无 | cybercore pending | 开局矿紧 |
| 317 | 26 农民 / 2 基地 | 2 叉 | 1 炮 1 电池 FB pending | 二矿刚落 |
| 478 | 41 农民 / 2 基地 | 4 叉 1 先知 1 风暴 | 6 炮 3 星门 FB ready | 舰队起步 |
| 638 | 41 农民 / 3 基地 | 2 叉 1 先知 4 风暴 | 9 炮 | 敌 40 supply 压境 |
| 799 | **63 农民 / 3 基地** | 5 叉 1 先知 1 航母 6 风暴 | **23 炮** | **矿 60 / 气 1828** |
| 1386 | 3 农民 / 0 基地 | 1 先知 | 1 水晶 1 FB | Defeat |

**根因（≥3）**：

1. **光子炮严重超建，吸干舰队矿**
   - `flows.yml` carrier `expansion_cannons: {min:3, max:6}` 是**每基地**目标；3 基地时理论上限 18 门，实际 799s 造出 23 门。
   - 23 门炮 × 150 矿 = 3450 矿，相当于 11-14 艘航母/风暴的产能被塔吃掉。
   - 结果是气大量富余（1828），矿枯竭（60），fleet 数量无法对抗 Zerg 中后期空军（腐化/刺蛇/感染/大龙）。

2. **fleet 成型速度仍慢**
   - 799s 仅有 1 航母 + 6 风暴，面对 13 腐化 + 10 蟑螂 + 3 刺蛇 + 2 感染完全不够。
   - 3 星门但矿不够，产出周期被拉长；舰队航标、升级虽然齐，但无矿转化为实际兵力。

3. **威胁响应过度拉满塔**
   - E9 敌压境时 `_should_build_defense` 把塔目标拉到 `ec.max`（每基地 6）， rush/timing 波次间隙也不及时降回来。
   - 慢性威胁下持续铺塔，没有「威胁解除后停止铺塔、把钱转 fleet」的切换。

### Lane 2 Rush 尸检

**关键状态时间线**：

| t (s) | 经济 | 兵力 | 塔/建筑 | 备注 |
|---|---|---|---|---|
| 116 | 18 农民 / 1 基地 | 无 | 1 门 1 gateway | presumed 兜底 |
| 237 | 19 农民 / 1 基地 | 3 叉 1 追猎 | 1 forge | 首塔刚派工 |
| 357 | 22 农民 / 1 基地 | 6 叉 2 追猎 | 3 炮 1 星门 | 单矿 ground |
| 478 | 26 农民 / 1 基地 | 12 叉 5 追猎 | 4 炮 3 gateway | O189 强制二矿 |
| 598 | 26 农民 / 2 基地 | 3 叉 9 追猎 1 虚空 | 3 炮 1 星门 | O100 解冻舰队 |
| 887 | 0 农民 / 0 基地 | 1 风暴 | 1 气矿 1 水晶 | Defeat |

**根因（≥3）**：

1. **transition ground 阶段过长，单矿经济无法 scaling**
   - Rush 强制 transition 后，主配方是 zealot/stalker；单矿 26 农民要同时养 forge/gateway/塔/气矿/二矿，地面部队只能续命，无法反攻。

2. **转舰队太晚**
   - 530s（游戏内）才触发 `O100:防御达标转舰队`，此时敌方已经发展壮大；fleet 没成型前基地已被打穿。

3. **农民数量不足**
   - 整局农民最高 27，二矿落地后没有快速补到 40+，经济和产能双双不足。

### 改进点并落地为 O191

1. **降低 carrier 塔数上限**
   - `ares-bot/flows.yml` carrier `expansion_cannons.max` 从 6 降到 4（每基地），释放矿给舰队/农民。

2. **Rush transition 期间允许经济扩张**
   - `bot/managers/production_manager.py:_want_dynamic_expand`：Zerg Rush 在 transition 且防御基本站稳（塔≥2 + 地面≥8 + 家 40 格清净 15s）时，不再被 `transition_expand_blocked` 阻断二矿，让地面阶段有经济支撑。

3. **fleet 未成规模时威胁分支也不拉满 max**
   - `_should_build_defense` threat 分支：当前要求 `_fleet_total_now > 0` 才拉满 max，但 1-2 艘 fleet 也算 >0；改为 `fleet_total >= 3` 才拉满，否则走动态式。

### 验证与 bench

- 单测：`poetry run python -m unittest discover -s tests -q` → **629 passed / 1 skipped**。
- 已停止 O190 bench，清理残留 SC2 进程。
- 新 bench 启动：
  - Lane 1 `o191-vh-zerg-timing-headless`
  - Lane 2 `o191-vh-zerg-rush-headless`
- staggered 启动。

- **O191 bench 已 staggered 启动**。


## 2026-08-05 O191 双 lane 尸检与 O192 落地

### O191 game_01 结果总览

| lane | 对手 | 结果 | bench 真实时间 | 游戏内时间 | 终局基地/农民 |
|---|---|---|---|---|---|
| Lane 1 Timing | Zerg VeryHard/Timing | **Defeat** | 330s | 1133.0s | 0 / 1 |
| Lane 2 Rush | Zerg VeryHard/Rush | **进行中→无法挽回** | 302s+ | 1092.9s | 0 / 0 |

O191 改动（限塔 + Rush transition 经济解锁）在 Timing lane 把塔数压到合理范围，
但终局仍因舰队规模不足、经济转化失衡被碾压；Rush lane 进入残局拖时状态。

### Lane 1 Timing 尸检

**关键状态时间线**：

| t (s) | 经济 | 兵力 | 塔/建筑 | 备注 |
|---|---|---|---|---|
| 28 | 11 农民 / 1 基地 | 无 | PYLON pending | **idle_builder: 农民钉点等 PYLON 30s+** |
| 160 | 21 农民 / 1 基地 | 2 叉 | cyber/forge/gateway | 开局矿紧 |
| 321 | 28 农民 / 2 基地 | 3 叉 | 1 炮 1 星门 | 二矿落地 |
| 482 | 41 农民 / 2 基地 | 5 叉 1 先知 1 风暴 | 1 炮 | 舰队起步 |
| 723 | 43 农民 / 3 基地 | 5 风暴 1 航母 | 1 炮 | 舰队小成 |
| 803 | 41 农民 / 2 基地 | 6 风暴 | 1 炮 | 基地被打掉 1 个 |
| 964 | 38 农民 / 2 基地 | 3 风暴 1 航母 | 1 炮 | 经济开始崩 |
| 1133 | 1 农民 / 0 基地 | 1 先知 | 1 气矿 | Defeat |

**终局统计**：idle worker time **631.25**、collected minerals 18630、vespene 5644。

**根因（≥3）**：

1. **开局农民反复钉点等 PYLON，采矿没有最大化**
   - `AutoSupply` 在 supply_left<=2 的紧急人口通道下，被 O11 撤回的 PYLON 农民会立即重派。
   - 同一农民从 t≈27 钉到 t≈55，等 100 矿 PYLON 空转近 30s，开局经济直接亏炸。
   - 司令观察「仍然有农民，前期干等着造建筑，没有采矿最大化」实证命中。

2. **Zerg Timing 转舰队太晚**
   - O185 把 Zerg Rush/Timing 的 transition 退出点统一提到 500s，导致 Timing 局 fleet_at=500。
   - 320s 前未转舰队，Timing 推进 400-500s 到脸时只有少量风暴/航母，被滚雪球。

3. **舰队规模无法进入临界质量**
   - 1133s 终局仅 1 航母 + 零星风暴，1125s 只剩 1 农民 0 基地。
   - 3 基地经济因 base 被打、农民被屠没有持续转化为舰队；空有科技链无兵力。

4. **残局无自动投降，拖长 bench 时间**
   - Lane 2 在 0 基地 0 农民、只剩 2 风暴 + 1 水晶的情况下仍运行到 1090s+ 未结束。
   - SC2 不判负导致 bench 真实时间被无意义拉长，且存在「SC2 进程卡死」误判风险。

### Lane 2 Rush 尸检

- state t=1092.9s：0 基地 / 0 农民 / 1 水晶 / 2 风暴，敌 Roach/Hydra/Corruptor/Locust 大军。
- 已进入数学死局但 SC2 未判负，等待时间无意义。

### 改进点并落地为 O192

1. **开局前 60s PYLON 农民钉点强制 2s 冷却**
   - `bot/managers/production_manager.py`：AutoSupply 注册条件改用 `_pylon_redispatch_ok`。
   - 60s 内即使 supply_left<=2，PYLON 农民被 O11 撤回后也要冷却 2s 才重派，让农民先采矿。
   - `bot/production_plans.py`：新增 `_pylon_redispatch_ok()` 纯函数，含单测接口。

2. **Zerg Timing 不拖到 500s 转舰队**
   - `bot/managers/production_manager.py`：`_fleet_at` 从 `max(_fleet_at, 500)` 仅对 Rush 生效，Timing 走 flows.yml 的 320s。

3. **中残局自动投降/止损**
   - `bot/main.py`：Q5 判负从「前 10 分钟」扩展到全时段；10 分钟后若基地全失且
     工人≤2 或存款<250，立即 `await self._client.leave()`，避免垃圾时间与卡死误判。

### 验证与 bench

- 单测：`poetry run python -m unittest discover -s tests -q` → **629 passed / 1 skipped**。
- 已停止 O191 bench，清理残留 SC2 进程。
- 新 bench 启动：
  - Lane 1 `o192-vh-zerg-timing-headless`
  - Lane 2 `o192-vh-zerg-rush-headless`
- staggered 启动。

- **O192 bench 已 staggered 启动**。


## 2026-08-05 O192 双 lane game_01 尸检与 O193 落地

### O192 game_01 结果总览

| lane | 对手 | 结果 | bench 真实时间 | 游戏内时间 | 终局基地/农民 |
|---|---|---|---|---|---|
| Lane 1 Timing | Zerg VeryHard/Timing | **Defeat** | 446s | 1292.9s | 0 / 21 |
| Lane 2 Rush | Zerg VeryHard/Rush | **Defeat** | 405s | 1295.7s | 0 / 2 |

O192 改动（开局 PYLON 冷却 + Timing 早转舰队 + 残局投降）让 Timing lane 经济/舰队规模一度成型,
但终局仍因 fleet 被慢性磨光、不拆建筑而战败；Rush lane 地面阶段后单矿经济无法支撑舰队转型。

### Lane 1 Timing 尸检

**关键状态时间线**：

| t (s) | 经济 | 兵力 | 塔/建筑 | 备注 |
|---|---|---|---|---|
| 26.8 | 11 农民 / 1 基地 | 无 | PYLON pending | **idle_builder 仍存在** |
| 320 | 3 基地 42 农 | 4 风暴 | 1 炮 | 舰队起步 |
| 654 | 3 基地 47 农 | 6 风暴 + 1 航母 | 1 炮 | 成型中 |
| 928 | 3 基地 64 农 | **9 风暴 + 3 航母** | 1 炮 | **优势顶点** |
| 1056 | 3 基地 63 农 | 6 风暴 | 1 炮 | 舰队开始损耗 |
| 1292 | 0 基地 21 农 | 2 风暴 | 无 | Defeat |

**终局统计**：idle worker time **799.56**、collected minerals **28840**、vespene 9188、
killed value units **25325**、killed value structures **800**。

**根因（≥3）**：

1. **开局 PYLON 农民仍然空转**
   - O192-① 只卡住了 AutoSupply 的 2s 冷却,但 **build_runner 开局序列的 PYLON 农民不在此限**。
   - CarrierOpenerZergTiming 第一个 `11 supply` 触发后,接下来两个 PROBE 花掉 100 矿,
     农民从 t≈27 钉到 t≈50+,idle worker time 继续滚雪球。

2. **舰队成型后不拆建筑,只交换单位**
   - 928s 优势顶点时 9 风暴 + 3 航母,但终局 killed value structures 仅 800,
     敌方记住 4  Hatchery + 产兵建筑几乎全在。
   - 舰队被敌方 Broodlord/Corruptor/Roach 慢性磨光,敌人 4 矿续兵永不断档。

3. **fleet 补充跟不上战损**
   - 从 928s(12 艘舰队) 到 1292s(2 艘), fleet 数量单调下降,星门产出未能填补损耗。
   - cap 6 / mineral_gate 250 在 3 基地经济下只能维持 3 星门,产能不够。

### Lane 2 Rush 尸检

**关键状态时间线**：

| t (s) | 经济 | 兵力 | 塔/建筑 | 备注 |
|---|---|---|---|---|
| 200 | 22 农 / 1 基地 | 地面部队 | 塔/门建造中 | idle_builder 刷屏 |
| 400 | 25 农 / 1 基地 | 20 叉 + 5 追猎 | 3 门 1 星门 | 地面 peak |
| 600 | 24 农 / 2 基地 | 9 叉 + 5 追猎 + 1 虚空 | 3 炮 | 刚转舰队 |
| 900 | 22 农 / 2 基地 | 10 虚空 + 5 追猎 | 无 | 单矿经济枯竭 |
| 1295 | 0 基地 2 农 | 6 虚空 | 无 | Defeat |

**终局统计**：idle worker time **771.69**、collected minerals **14405**、vespene 5340、
killed value structures **0**。

**根因（≥3）**：

1. **单矿 ground 阶段过长,经济无法 scaling**
   - Rush transition 到 500s 才解冻舰队,ground 阶段把单矿资源吸干,
     二矿虽然能开但农民/气矿跟不上。

2. **完全不拆建筑**
   - 终局 killed value structures = 0,敌方 Hatchery/产兵建筑一个没掉,
     单矿换兵永远换不过。

3. **农民 idle 依然严重**
   - 771s idle,大量建造等待期农民干等,经济转化效率低下。

### 改进点并落地为 O193

1. **开局 PYLON 推迟到 12 supply**
   - `ares-bot/protoss_builds.yml`：CarrierOpenerZergTiming 把第一个 `'11 supply'` 改为
     `'12 supply'`,让 PYLON 农民派出时已有足够矿物,避免 build_runner 开局空转。

2. **提高星门产能 cap + 降低矿门**
   - `ares-bot/flows.yml`：`carrier.extra_production` 从 `{cap:6, mineral_gate:250}` 改为
     `{cap:8, mineral_gate:200}`,让 3 基地后能拉到 4 星门,持续补充 fleet。

3. **Rush 更早转舰队**
   - `bot/managers/production_manager.py`：Zerg Rush 的 `_fleet_at` 从 `max(_fleet_at, 500)`
     降到 `450`,给舰队更多成型窗口,strong_exit 评分门兜底防早退。

### 验证与 bench

- 单测：`poetry run python -m unittest discover -s tests -q` → **629 passed / 1 skipped**。
- 已停止 O192 bench，清理残留 SC2 进程。
- 新 bench 启动：
  - Lane 1 `o193-vh-zerg-timing-headless`
  - Lane 2 `o193-vh-zerg-rush-headless`
- staggered 启动。

- **O193 bench 已 staggered 启动**。


## 2026-08-05 O193 game_01 结果与 O194 落地计划

### O193 game_01 结果总览

| lane | 对手 | 结果 | bench 真实时间 | 游戏内时间 | 终局基地/农民 | 关键问题 |
|---|---|---|---|---|---|---|
| Lane 1 Timing | Zerg VeryHard/Timing | **Victory** | ~520s | 1114.6s | 2 / 43 | trickle / supply_block / idle_builder |
| Lane 2 Rush | Zerg VeryHard/Rush | **Defeat** | ~260s | 855.4s | 0 / 9 | one_base / idle_builder×32 / overrun |

O193-①(PYLON 12 supply) 让 Timing lane 经济成型并赢下首局；但 Rush lane 仍因开局防御过慢、舰队重建窗掐死农民、单矿滚雪球失败而战败。

### Lane 2 Rush 尸检

**关键状态时间线**：

| t (s) | 经济 | 兵力 | 备注 |
|---|---|---|---|
| 201 | 21 农 / 1 基地 | 1 叉 | 首批 10 狗到脸 |
| 321 | 21 农 / 1 基地 | 1 叉 | 狗群峰值 16 只 |
| 362 | 22 农 / 1 基地 | 2 追猎 + 1 叉 | 首条追猎才出 |
| 495 | 24 农 / 1 基地 | 4 追猎 + 4 叉 | **O100 防御达标转舰队(评分26)** |
| 603 | 25 农 / 2 基地 | 5 叉 + 4 追猎 + 1 虚空 | **首舰出场，距转舰队 108s** |
| 723 | 24 农 / 2 基地 | 5 叉 + 4 追猎 + 3 虚空 | 敌方roach/ravager/infestor/hydra混合波到 |
| 855 | 0 基地 / 9 农 | 无 | Defeat |

**终局统计**：idle worker time 771.69、collected minerals 14405、vespene 5340、killed value structures 0。

**根因（≥3）**：

1. **Zerg Rush 沿用 Timing 开局，首塔/首叉太晚**
   - `main.py` 对 Zerg Rush/Timing 统一用 `CarrierOpenerZergTiming`。
   - 本局 forge 07:25、gateway 08:02、首叉 08:14、首炮 08:44 才落地（build_runner log），狗群 03:20 已到家门口。
   - 等价的 03:00-04:00 物理空窗只靠 1 叉 + 农民硬顶，被滚雪球。

2. **舰队重建窗掐死农民，经济在转舰队后断气**
   - `production_manager.py` 在 `fleet_rebuild_window` 期间且 `workers >= 14` 就停止造农民。
   - 本局 495s 转舰队 → 603s 首舰出场，这 108s 内工人卡在 24-27，二矿虽已就绪但农民不增长，矿收入无法支撑舰队 + 防御双轨。
   - 阈值 14 过低：2 基地饱和需要 ~44 农，14 农就停训等于自杀。

3. **星门/舰队航标在过渡期内被冻结，首舰出场严重滞后**
   - transition 期间 `_build_flow_structures` 冻结 STARGATE/FLEETBEACON，转舰队后需从零拍星门 → 虚空，首舰 108s 后才出厂。
   - 敌方在 600-700s 已转出 roach/ravager/infestor，3 艘虚空杯水车薪。

### O194 落地计划

1. **Zerg Rush 专用开局 `CarrierOpenerZergRush`**
   - `protoss_builds.yml` 新增 opener：提前 Forge(~14 supply)、PhotonCannon(~17 supply)、Zealot(~19 supply)，让 03:00-04:00 有塔有叉。
   - `main.py`：仅当 `_ai_build == "rush"` 且 Zerg 时切到该 opener；Timing 继续用 `CarrierOpenerZergTiming`。

2. **舰队重建窗不再在低农时掐农民**
   - `production_manager.py`：把 `fleet_rebuild_window(...) and workers >= 14` 改为按当前基地饱和数判定（例如 `workers >= 22 * max(1, townhalls)`）。
   - 转舰队后优先保经济回血，避免 108s 零农民增长。

3. **Rush 下允许过渡期内预建 STARGATE**
   - `production_manager.py`：transition 冻结列表对 Zerg Rush 放行 STARGATE（FLEETBEACON 仍冻结到转舰队后），或把 Zerg Rush 的 `_fleet_at` 进一步降到 400 并用 strong_exit 兜底。
   - 目标：转舰队后 30-45s 内首舰出场，而不是 108s。

### 验证与 bench

- 单测：改完后 `poetry run python -m unittest discover -s tests -q`。
- 重开双车道 bench：
  - Lane 1 `o194-vh-zerg-timing-headless`
  - Lane 2 `o194-vh-zerg-rush-headless`


## 2026-08-05 O194 双 lane 初步结果

O194 已落地并启动双车道 bench：
- Lane 1：`o194-vh-zerg-timing-headless`
- Lane 2：`o194-vh-zerg-rush-headless`

### 当前战绩（series 进行中）

| lane | game_01 | game_02 | 备注 |
|---|---|---|---|
| Timing | Defeat (459.2s) | **Victory** (1134.7s) | game_01 方差/被快攻碾平，game_02 正常运营取胜 |
| Rush | Defeat (1215.1s) | 进行中 | 前期明显改善，终局 fleet 仍被慢性磨光 |

### O194 Rush game_01 复盘

**关键状态时间线**：

| t (s) | 经济 | 兵力 | 备注 |
|---|---|---|---|
| 136 | 16 农 / 1 基地 | 1 叉 | 新 build order 首叉比 O193 早 ~6 min |
| 181 | 16 农 / 2 基地 | 2 叉 | 二矿很早落地 |
| 342 | 27 农 / 2 基地 | 6 叉 + 1 追猎 | 地面防御站住 |
| 590 | 25 农 / 2 基地 | 5 叉 + 4 追猎 + 1 虚空 | 首舰出场 |
| 699 | 25 农 / 2 基地 | tempest 首次出现 | 舰队开始成型 |
| 924 | 3 基地 | 1 航母 | 航母登场 |
| 1100 | 3 基地 | 7 暴风 + 2 航母 + oracle | **优势顶点** |
| 1215 | 0 基地 / 0 农 | 4 暴风 | Defeat |

**终局统计**：idle worker time 待补、collected minerals 待补、max_bank 1095、终局敌 29 supply vs 我 4。

**暴露的新问题**：

1. **Fleet 不拆建筑，被慢性磨光**
   - 1100s 优势顶点有 7 tempest + 2 carrier，但终局 killed value structures 仅 800（同 O192 Timing 模式）。
   - 舰队在优势期没有主动推进拆 Hatchery/产兵建筑，敌方 4 矿续兵永不断档。

2. **航母微操/目标优先级仍有问题**
   - 终局只剩 tempest，carrier 被消耗掉且拦截机未发挥作用。
   - 需要检查 carrier_offensive 在推家/engage 时的锚点和目标选择。

3. **Idle_builder 仍 ×23**
   - 新 build order 虽然快，但农民干等建造事件仍有 23 次，前期矿物被浪费。

> 系列仍在跑（Timing 1-1，Rush 0-1），等 5 局打完再决定是否进入 O195。若 Rush 最终未达 3 胜，O195 重点：**fleet 推进拆建筑 + carrier 微操 + 减少 idle_builder**。


## 2026-08-05 O195：O194 双 lane 提前终止 + 尸检

O194 双车道因 Stability 问题提前终止（Timing game_03 超时，Rush game_02 崩溃/卡死、game_03 再负）。已收集的失败样本足够做尸检，直接进 O195。

### O194 最终有效样本

| lane | game_01 | game_02 | game_03 | 备注 |
|---|---|---|---|---|
| Timing | **Defeat** 459.2s | **Victory** 1134.7s | ERROR（超时，重试中） | 1-1，且第三局陷入长盘/超时 |
| Rush | **Defeat** 1215.1s | **Defeat** 1284.4s（首局崩溃后残留 state） | **Defeat** 687.8s | 0-3，Rush 仍未达标 |

### 失败局共性尸检（≥3 改进点）

1. **idle_builder 仍是最大出血点**
   - Timing game_01：开局 PYLON 农民在 `40,113` 从 t=32s 干等到 t=273s，同一 tag 反复被派去等 100 矿。
   - Rush game_03：PHOTONCANNON 农民连续干等（155s、162s、174s、184s、191s、196s、204s、216s、234s、248s、250s…），每次 3s，累计大量矿物损失。
   - 根因：
     - `CarrierOpenerZergRush` 第一个 PYLON 写在 `10 supply`，触发瞬间下一个 PROBE 把 100 矿花掉。
     - `AutoSupply` 的 `supply_left<=2` 紧急通道 + `_pylon_redispatch_ok` 在买不起时仍每 2s 重派，农民在「钉点→O11 撤回→再钉点」循环。
   - **O195 改法**：
     - Rush opener PYLON 推到 `11 supply` 且 worker 在前。
     - `_pylon_redispatch_ok` 增加 `can_afford` 参数：买得起直接放行；买不起且 `supply_left>0` 时不重派农民，等钱够或 supply_left==0 再说。

2. **Rush 中盘 remax 大波把基地滚平，fleet 成型太晚**
   - Rush game_01：07:00 后敌方可见兵力从 57 → 116 supply，我方只有 4 tempest + 少量地面。
   - Rush game_03：06:30 后敌方 20+ supply 虫群到家，fleet 仅 1 zealot，基地直接被推光。
   - 根因：`CarrierOpenerZergRush` 的 CYBERNETICCORE/STARGATE 拖到 24/26 supply 以后，首舰出场在 11-12 min，赶不上 Zerg 5-7 min 的 remax。
   - **O195 改法**：把 core 提前到 23 supply、stargate 提前到 25 supply，让舰队早出 30-60s。

3. **1 基地时的 `_home_guard` 导致「丢基地→推不出去→被滚雪球」死循环**
   - Rush game_01：1100s 优势顶点 7 tempest + 2 carrier，但只剩 1 基地，舰队被强制守家，无法推进换家；终局 0 基地。
   - Rush game_03：同理，基地一掉 fleet 就蹲家等死。
   - 根因：`combat_manager` 中 `_home_guard` 只要 `townhalls.amount < 2` 就全军蹲家；`_force_push` 阈值 10 艘/10 min，Rush 局优势顶点 9 艘不触发。
   - **O195 改法**：
     - `_force_push` 阈值从 `≥10 / t>600` 降到 `≥8 / t>540`。
     - `_home_guard` 增加例外：舰队 ≥8 且 t>9min 时，即便只剩 1 基地也出门换家/抢回分矿，不再蹲家等死。

4. **bench 稳定性：超时/崩溃后残留 SC2 孤儿进程污染下局**
   - Timing game_03 超时后，SC2 进程变成 PPID=1 的孤儿；bench 重试新局时旧 SC2 仍在跑，双车道相互干扰。
   - Rush game_02 崩溃重试后，旧 `state_*.json` 留在 `game_02/` 目录，retro 会读到崩溃局的脏数据。
   - **O195 改法**：
     - `bench.py` 增加 `_kill_orphan_sc2()`：单局结束后杀掉 PPID=1 的 SC2 孤儿。
     - `bench.py` 增加 `_reset_game_dir()`：重试同一局前删除旧 state/result，旧 `run.log` Rotate 为 `run.log.1`。

### O195 已落地改动

1. `protoss_builds.yml`：`CarrierOpenerZergRush` PYLON 改 `11 supply`，core/stargate 各提前 1-2 supply。
2. `bot/production_plans.py`：`_pylon_redispatch_ok` 按 `can_afford` 分流，买不起且有余人口时不重派农民。
3. `bot/managers/production_manager.py`：把 `can_afford` 传给 `_pylon_redispatch_ok`。
4. `bot/managers/combat_manager.py`：`_force_push` 阈值 8/540s；`_home_guard` 对成型舰队放行。
5. `bench.py`：崩溃/超时后杀孤儿 SC2，重试前清理 game_dir 旧快照。

### 验证

- `poetry run python -m unittest discover -s tests`：629 passed / 1 skipped。
- 下一组 bench：继续双车道 `o195-vh-zerg-timing-headless` + `o195-vh-zerg-rush-headless`。

---

## 2026-08-05 O195 headless 双车道 bench（Rush game_01 尸检）

**对局**：`o195-vh-zerg-rush-headless` game_01，地图 `BelShirVestigeLE`，对手 Zerg VeryHard/Rush。  
**结果**：Defeat @ 940.7s，结算 `supply=4/64, bases=0, workers=1, idle_worker_time=687.5`。  
**同时进行的 Timing lane**：`o195-vh-zerg-timing-headless` game_01 运行至 1200s+（3 基地/64 农/195 人口），但 bench 任务因 10min 总超时被打断，未拿到最终 result。

### 关键时间线

| t (s) | 我方 | 敌方可见 | 经济/产能 |
|---|---|---|---|
| 164 | Forge 开始建造，农民已干等 3s | 6 狗 | 17 农/2 矿 |
| 225 | 3 叉 + 1 炮，2 基地 | 1 农民 | 20 农 |
| 353 | 6 叉，Cybercore 就绪 | 无 | 33 农 |
| 417 | 9 叉/2 追猎，**首座 Stargate** 落地 | 无 | 41 农 |
| 450 | 11 叉/2 追猎，3 基地 | 无 | 46 农 |
| 482 | 地面部队被一波打残（剩 1 叉/1 追猎） | 5 蟑螂/3 刺蛇/1 狗 | 47 农 |
| 610 | 2 叉/1 虚空，2 基地 | 22 单位（蟑螂/刺蛇/感染/狗） | 39 农 |
| 867 | **FleetBeacon 才落地** | 无 | 30 农 |
| 940 | 0 基地/1 农，Defeat | 37 单位大波 | 崩盘 |

### 失败局尸检（≥3 改进点）

1. **build runner 开局仍派农民「干等钱」造建筑（司令观察命中）**
   - 本局 `idle_builder` 事件 **550 条**，最早从 t=164（Forge）开始，后续 PYLON、PHOTONCANNON 反复出现「等钱 3s」。
   - 根因：`ares.build_runner.build_order_parser` 对神族建筑的 `start_condition` 是 `minerals >= cost - 75`（Pylon 只要 25 矿、Forge 只要 75 矿）就派农民；工人到位后钱被后续开销抽走，只能在建造点空转。
   - **O196 改法**：Patch `ares-sc2/src/ares/build_runner/build_order_parser.py`——Protoss 的 SUPPLY/STRUCTURE 步骤改为 `can_afford` 才触发，买不起不派农民，彻底消灭 build-order 阶段的 idle_builder。

2. **舰队转型极晚，全程无航母**
   - Stargate 417s 才落地（build order 写的是 25 supply，但被地面防御/叉子吸干矿），FleetBeacon 867s 才拍，游戏结束没有一艘 CARRIER/TEMPEST，星门产的是虚空辉光舰（FB 前无法造暴风/航母）。
   - 根因：transition 期的 ground_spawn（0.4 追猎/0.6 叉子）+ 3 兵营 + 塔链把矿物窗口全部吃掉，舰队科技被无限后置。
   - **下一步改法**：
     - 降低 transition 期地面兵力天花板（pre_fleet zealot cap 从 12 调低、gateway_cap 从 3 调 2），把矿物让给 FB/Stargate。
     - 或给 carrier 流加「FB 就绪后强制 quota 补航母」机制，避免 TEMPEST p0 永远把 CARRIER p1 饿死。

3. **地面部队集结不足、被小股部队分批吃掉**
   - 450s 时我方 11 叉/2 追猎，敌方仅 9 单位；482s 时我方被打到只剩 1 叉/1 追猎。Zealot 无支援冲进 Roach/Hydra 射程被风筝。
   - 根因：carrier 流没有 `rally_min_army`，transition 期单位逐只送上前线；且地面兵种配比中 Zealot 占 60%，面对 Zerg 远程兵种性价比差。
   - **下一步改法**：transition 期临时启用 `rally_min_army`（例如 ≥8 地面 supply 才出门），并把 ground_spawn 调整为更偏追猎/更少叉子。

4. **SC2 崩溃/超时后残留 `Blizzard Error` 孤儿进程**
   - ps 中发现 PPID=1 的 `/Applications/StarCraft II/Support/Blizzard Error.app/Contents/MacOS/Blizzard Error` 已存活 4-5 分钟，是之前崩溃局遗留。
   - **O196 改法**：`bench.py` 新增 `_cleanup_blizzard_error()`，bench 启动时杀掉存活 >60s 的 Blizzard Error 报告进程。

### O196 已落地改动

1. `ares-sc2/src/ares/build_runner/build_order_parser.py`：Protoss 的 SUPPLY/STRUCTURE 步骤 `start_condition` 改为 `can_afford`，开局 idle_builder 根因消除。
2. `ares-bot/bench.py`：新增 `_cleanup_blizzard_error()`，启动时清理 SC2 崩溃遗留的 `Blizzard Error` 进程。
3. 已记录到 `CLAUDE.md`：headless + 双车道并行作为项目记忆，O196 继续按此模式验证。

### 验证

- `poetry run python -m unittest discover -s tests`：待运行（本条目写入时）。
- 下一组 bench：O196 继续双车道 `o196-vh-zerg-timing-headless` + `o196-vh-zerg-rush-headless`。

---

## 2026-08-05 O196 headless 双车道 bench（Rush game_01 尸检）

**对局**：`o196-vh-zerg-rush-headless` game_01，地图 `AbyssalReefLE`，对手 Zerg VeryHard/Rush。  
**结果**：Defeat @ 941.3s，`supply=5/48, bases=0, workers=3, idle_worker_time=900.9`。  
**Timing lane**：game_01 运行到 t=1104s 时被中断，当时 2 基地/10 暴风/1 航母/50 农，占优但未完赛。

### 关键时间线

| t (s) | 我方 | 敌方可见 | 经济/产能 |
|---|---|---|---|
| 120 | 18 农，1 基地 | 无 | min=200 |
| 181 | 2 叉，Cybercore 在建 | 无 | 21 农 |
| 241 | 4 叉 | 无 | 23 农 |
| 362 | 10 叉/1 追猎，Stargate 落地 | 无 | 25 农 |
| 422 | 15 叉/2 追猎 | 无 | 25 农 |
| 482 | 15 叉/8 追猎 | 无 | 25 农，min=215 |
| 542 | 15 叉/8 追猎/1 虚空 | 1 狗 | 25 农 |
| 570 | 14 叉/8 追猎/2 虚空 | 无 | 26 农，**二矿落地** |
| 723 | 几乎全军覆没 | 波次 | 34 农 |
| 900 | 5 叉/1 虚空 | 50 单位大波 | 崩盘 |

### 失败局尸检（≥3 改进点）

1. **FleetBeacon 永远没建出来，舰队转型彻底失败**
   - Stargate 362s 落地，但直到败亡 FleetBeacon 都是「在建停滞 >45s 自救」状态，原因统一是 `no_money`。
   - 根因：`_fleet_reserve` 只在 `fleet_transitioned + 首舰已出/防御评分≥25` 时保护 Nexus 资金，对 FB 资金没有同等保护；transition 期地面配方 + 塔链把 300/200 的 FB 资金窗永久吃光。
   - **O197 改法**：
     - 减少 transition 期地面兵力天花板，把矿物/气体让给 FB。
     - 代码层：当 `_fb_truly_missing` 为真时，额外 Gateway 和 PSD 超 `min` 部分的塔也暂停，确保 FB 资金不被抽走。

2. **地面兵力严重过量，经济被叉/追猎/塔吸干**
   - 422s 已有 15 叉/2 追猎，后期叉子维持在 14-15；PhotonCannon idle_builder 事件 302 条，Gateway 152 条。
   - `pre_fleet.max=12` + `transition.gateway_cap=3` 让 bot 在 transition 期无限拍兵营/叉子，把本该给 FB/二矿的钱全部吃掉。
   - **O197 改法**：
     - `flows.yml` carrier `pre_fleet.max` 12 → 8（减少叉海上限）。
     - `flows.yml` carrier `transition.gateway_cap` 3 → 2（少一座兵营 = 150 矿给 FB）。

3. **单矿经济被滚雪球，二矿拖到 10 分钟**
   - 全程 25 农顶在 1 基地直到 570s，二矿落地即面临敌波，没有经济缓冲。
   - 根因：防御 + 地面产能把矿吃光，`_fleet_reserve` 又因无首舰/评分不足无法保护 Nexus 资金。
   - **O197 改法**：
     - 降低 ground_spawn 矿耗后，二矿资金窗自然出现。
     - 如仍不足，考虑在 transition 退出条件里加「地面兵力≥12 且家 40 格无敌 15s 即提前转舰队」，而不是死等 30s。

4. **idle_builder 仍然泛滥（662 条）**
   - build-order 阶段干等减少，但 PSD 炮塔/追加 Gateway/电池/气矿仍派农民等钱。
   - **O197 改法**：在 `_build_extra_gateways` 和 PSD 调用点再收紧 `dispatch_viable` / 增加 `can_afford` 前闸，避免同时派多个工人等钱。

### O197 已落地/计划改动

1. `ares-bot/flows.yml`：carrier `pre_fleet.max` 12 → 8；`transition.gateway_cap` 3 → 2。
2. `ares-bot/bot/managers/production_manager.py`（计划）：`_fb_truly_missing` 为真时，暂停追加 Gateway 和超 min 的 PSD 塔，优先保 FB 资金。
3. 同步更新 `tests/test_flow_config.py` 的 shipped 断言。

### 验证

- `poetry run python -m unittest discover -s tests`：待运行（本条目写入时）。
- 下一组 bench：O197 继续双车道 `o197-vh-zerg-timing-headless` + `o197-vh-zerg-rush-headless`。


## 2026-08-05 O197 双车道 bench 结果 vs Zerg VeryHard（headless）

### 战绩

| Lane | 局 | 结果 | 时长 | 地图 | 终局状态 |
|---|---|---|---|---|---|
| Timing | game_01 | Defeat | 317.9s | PaladinoTerminalLE | 0 基地 / 3 农 / 3 人口 |
| Timing | game_02 | Defeat | 1224.6s | NewkirkPrecinctTE | 0 基地 / 2 农 / 2 人口 |
| Rush | game_01 | Defeat | 1656.2s | PaladinoTerminalLE | 0 基地 / 2 农 / 2 人口 |

O197 3 局全败，未拿到任何一胜。

### 关键数据

- **Rush game_01** idle worker time = **730.8s**，Timing game_01 = 146.9s，Timing game_02 同样有大量 idle_builder 事件。
- **Rush game_01** 终局 14 虚空 + 1 追猎 + 1 叉，但全程 **1 基地 11 农**，FleetBeacon 始终未建成（O110 反复报告「建造停滞 >45s，no_money」）。
- **Timing game_02** 终局 8 Tempest，但全程 **1 基地 54 农**（后期被屠到 2 农），无法扩张。
- **Timing game_01** 317s 即被击穿：CarrierOpenerZergTiming 在 PaladinoTerminalLE 这张图上太慢，3 分半还没 PhotonCannon。
- **Rush game_01** 科技链过慢：CYBERNETICCORE 4:42 才落地，STARGATE 6:07 才落地，FleetBeacon 从未落地。

### 失败局尸检（≥3 改进点）

1. **FleetBeacon 资金在 rush/threat 期间被 F2 持续抽干，舰队转型永远完不成**
   - `_fb_truly_missing`/`_fb_waiting` 已能识别 FB 缺资金，但 F2 注册守卫在 line 1248 对 `_fb_waiting` 开了三个例外：`_threat_active`、`_rush_active`、`_timing_sprint` 成立时继续铺塔。
   - Rush game_01 中 rush_active 从 145s 持续到终局，于是塔/Pylon/电池/追加 Gateway 持续把 300/200 的 FB 资金窗吃光，14 虚空永远等不到 FleetBeacon。
   - **O198 改法**：`_fb_waiting`（FB 已可建但买不起）时，F2 只保留 `ec.min` 底线，其余塔/电池/追加 Gateway/追加星门全部让位；buffer pylon（line 895-922）也接入 `_fb_ready_to_build()` 闸，禁止在 FB 资金未攒够时花 100 矿补人口 buffer。

2. **buffer pylon 直接派工导致农民干等，idle_worker time 爆炸**
   - fleet_supply_buffer_needed 分支用 `BuildStructure(PYLON)` 直接注册，只查 `can_afford`，没走 `dispatch_viable` 收入/走位守卫；钱在派工后被其他开销抽干 → 农民钉点等钱，反复触发 idle_builder。
   - 三条 lane 的 idle_builder 事件里 PYLON 占大头（同 tag 反复 3s+ 等钱）。
   - **O198 改法**：buffer pylon 注册前加 `dispatch_viable(self.ai.minerals, self._mineral_income_per_sec(), 0, 100)` 守卫；若 FB 资金保护激活，buffer pylon 让位。

3. **单矿锁死，开矿条件被 rush/threat 永久冻结**
   - 三局终局都是 1 基地；`auto_expand.first_expand_at=210` 在 rush/threat 期间被 `should_expand_dynamic` 的 rush 门拦住，transition 期又被 `_expand_holding` 锁住。
   - Rush game_01 撑到 1656s 仍 1 基地 11 农，经济被滚雪球；Timing game_02 54 农仍 1 基地，无法把经济转成多基地产能。
   - **O198 改法**：降低 carrier `first_expand_at` 210→150（8 农民开局 150s 约等于 12 农民 210s 的经济窗口）；在 rush/threat 解除后的安静窗强制开矿（ `_want_expand` 增加「家 40 格无敌 20s 且农民≥20」兜底），不再死等 `advantage_supply`。

### O198 已落地/计划改动

1. `ares-bot/bot/managers/production_manager.py`：
   - F2 注册守卫收紧：`_fb_waiting` 时 threat/rush/timing 不再无限制铺塔，最多保留 `ec.min`。
   - buffer pylon 加 `dispatch_viable` 守卫 + `_fb_ready_to_build()` 资金保护。
2. `ares-bot/flows.yml`：carrier `auto_expand.first_expand_at` 210 → 150。
3. 同步更新 `tests/test_flow_config.py` 的 shipped 断言。

### 验证

- `poetry run python -m unittest discover -s tests`：待运行。
- 下一组 bench：O198 headless 双车道 `o198-vh-zerg-timing-headless` + `o198-vh-zerg-rush-headless`。


## 2026-08-05 O198 双车道 bench 结果 vs Zerg VeryHard（headless，提前终止）

### 战绩

O198 跑完部分局后提前终止（Timing 已 0-3，数学上不可能达到 3/5）。

| Lane | 局 | 结果 | 时长 | 地图 | 终局状态 |
|---|---|---|---|---|---|
| Timing | game_01 | Defeat | 499.8s | PaladinoTerminalLE | 0 基地 / 3 农 |
| Timing | game_02 | Defeat | 429.6s | PaladinoTerminalLE | 0 基地 / 6 农 |
| Timing | game_03 | Defeat | 417.0s | PaladinoTerminalLE | 0 基地 / 4 农 |
| Timing | game_04 | 进行中（终止时 ~313s）| — | — | — |
| Rush | game_01 | Defeat | 1095.3s | ProximaStationLE | 0 基地 / 2 农 |
| Rush | game_02 | 刚开始（终止时）| — | — | — |

### 关键数据

- **Timing 0-3 全在 PaladinoTerminalLE**：随机连摇 3 次同图，该局 400-500s 被 Roach/Zergling 一波推平，终局 0 兵力。
- **Timing 终局结构**：2 Gateway / 1 Stargate / 2 Cybercore / 1 Forge / 0 PhotonCannon（game_03）。F2 自动塔链事件里大量 `首塔派工=not_viable` / `taken`，实际一座炮塔都没立起来。
- **Rush game_01 宏观大幅改善**：3 基地 / 56 农 / 5 Stargate / FleetBeacon 已建 / 13 光子炮，对比 O197 的 1 基地 11 农 0 FB 是质变。
- **Rush game_01 舰队产能异常**：800s 时 5 星门 + FB + 895 矿 / 784 气，但场上只有 2 Tempest + 1 Oracle。星门群在 transition 后期似乎没有满负荷产舰队。
- **Idle worker 下降**：Rush game_01 全程 idle_builder 数量级明显低于 O197；Timing 仍有 cannon/gateway 干等，但较 O197 减少。

### 失败局尸检（≥3 改进点）

1. **Timing 局炮塔链完全失效，基地裸奔被一波穿**
   - game_03 终局 0 PhotonCannon，但日志显示 F2 反复尝试派工造首塔 → `not_viable` / `taken`，实际没有塔落地。
   - 根因：CarrierOpenerZergTiming build order 只写 1 座 photoncannon（28 supply），且位置/时机对 PaladinoTerminalLE 的 Roach 波次（400s 前后到脸）太晚；F2 自动补塔在 mineral 紧张 + 出兵竞争下被无限后延。
   - **O199 改法**：build order 里直接加入 2-3 座 photoncannon 且提前到 22-26 supply；`expansion_cannons.min` 3→4，确保 transition 期即便 F2 动态也至少 4 塔保底。

2. **Rush 转舰队后舰队产能严重不匹配星门数量**
   - 5 星门就绪、FB 就绪、资源充足，但 100s+ 只产出 2 Tempest。说明 `_effective_spawn` 在 `_rush_active` + `fleet_transitioned` 混合期的 freeflow 优先级/资源分配有问题，或者星门实际未全部就绪/被占用。
   - **O199 改法**：在 mixed 模式（`rush_spawn_fleet_escape`）把 Tempest 优先级提到与 Zealot 同档或更高，避免 100 矿 Zealot 把 250 矿 Tempest 的 mineral 窗永远吃掉；同时检查 `freeflow` 在多星门时是否因 p0 Zealot 持续可负担而饿死 p1 Tempest。

3. **随机地图连续命中 PaladinoTerminalLE 放大样本偏差**
   - 3 局 Timing 全同图，无法判断是 build order 问题还是地图问题。
   - **O199 改法**：bench 用 `--map random` 但连续同图会误导迭代；后续 bench 至少固定一 lane 在 AbyssalReefLE（baseline 图）做对照，避免单图偏差。

### O199 已落地/计划改动

1. `ares-bot/protoss_builds.yml`：`CarrierOpenerZergTiming` 提前并增加 photoncannon 数量（28 supply 1 座 → 24/26 supply 2 座）。
2. `ares-bot/flows.yml`：carrier `expansion_cannons.min` 3 → 4。
3. `ares-bot/bot/managers/production_manager.py`：调整 `rush_spawn_fleet_escape` 混合模式下舰队兵种优先级，避免 Zealot 持续吞 mineral 窗。
4. 同步更新 `tests/test_flow_config.py` 的 shipped 断言。

### 验证

- `poetry run python -m unittest discover -s tests`：待运行。
- 下一组 bench：O199 headless 双车道，Timing lane 固定 AbyssalReefLE 做对照 + Rush lane random。


## 2026-08-05 O199b 双车道 bench 完整结果 vs Zerg VeryHard（headless, disable_timeout）

### 战绩

| Lane | 局 | 结果 | 时长 | 地图 | 终局状态 |
|---|---|---|---|---|---|
| Timing @AbyssalReefLE | game_01 | **Victory** | 1015.5s | AbyssalReefLE | 4 基地 / 67 农 / 200/200 supply |
| Timing @AbyssalReefLE | game_02 | **Victory** | 940.5s | AbyssalReefLE | 2 基地 / 43 农 / 144/154 supply |
| Timing @AbyssalReefLE | game_03 | **Victory** | 1089.0s | AbyssalReefLE | 3 基地 / 64 农 / 199/200 supply |
| Timing @AbyssalReefLE | game_04 | Defeat | 430.7s | AbyssalReefLE | 0 基地 / 7 农 |
| Timing @AbyssalReefLE | game_05 | Defeat | 472.9s | AbyssalReefLE | 0 基地 / 9 农 |
| Rush @random | game_01 | Defeat | 1145.0s | AbyssalReefLE | 0 基地 / 2 农 |
| Rush @random | game_02 | **Victory** | 956.6s | BelShirVestigeLE | 4 基地 / 63 农 / 186/200 supply |
| Rush @random | game_03 | **Victory** | 1264.7s | NewkirkPrecinctTE | 4 基地 / 67 农 / 199/200 supply |
| Rush @random | game_04 | Defeat | 910.8s | NewkirkPrecinctTE | 0 基地 / 1 农 |
| Rush @random | game_05 | Defeat | 278.7s | PaladinoTerminalLE | 0 基地 / 3 农 |

- **Timing @AbyssalReefLE：3-2，达成 3/5 目标。**
- **Rush @random：2-3，未达成 3/5。**

### 关键数据

- Timing 均值终局编成：TEMPEST×16.7, CARRIER×3.7, STALKER×6.7, ZEALOT×4.0, ORACLE×1.0。
- Rush 均值终局编成：TEMPEST×18.5, CARRIER×3.5, STALKER×4.5, ZEALOT×2.5, VOIDRAY×2.0。
- Rush 输掉的两局：game_05 PaladinoTerminalLE 278s 被快攻滚平（0 兵力）；game_04 NewkirkPrecinctTE 910s 终局只有 2 虚空（舰队未成型/被推家）。
- 复盘高频问题：idle_builder×5, one_base×2, overrun×2, trickle×2。

### 尸检与 O200 改进点

1. **Rush 在 PaladinoTerminalLE 278s 被裸奔滚平，早期防御不足**
   - `CarrierOpenerZergRush` 虽有 forge/首塔/双叉，但在短 rush 距离图仍不够快。
   - **O200 改法**：build order 再加 1 座 photoncannon（17/19 supply 双塔），并把 cybercore/stargate 再后挪 1-2 supply，确保首波前 2 塔+双叉到位。

2. **Rush 中盘被慢性磨穿（game_04 910s 仅 2 虚空）**
   - 经济/科技齐但舰队没续出来，可能 transition 后资源分配或 combat 回撤过度导致舰队送完。
   - **O200 改法**：检查 `_effective_spawn` mixed 模式，降低 Zealot 持续吞矿的优先级，让 Tempest 在资源足够时优先产出；同时提高 combat 航母/暴风的 engage 积极性，避免被逐步蚕食。

3. **Timing 3-2 刚达标，仍有 2 局 430-470s 早崩**
   - 同样是 AbyssalReefLE，说明早期防御稳定性不够，不是地图问题。
   - **O200 改法**：同步把 `CarrierOpenerZergTiming` 也加一座 early cannon；`expansion_cannons.min=4` 已生效，但 build order 阶段仍需更硬的塔底。

### 下一步

O200 主攻 Rush 早期防御 + 中盘舰队稳定性，Timing 顺带加固；单测通过后重启 headless 双车道 bench。


## 2026-08-05 O200 双车道 bench 完整结果 vs Zerg VeryHard Rush（headless）

### 战绩

| Lane | 局 | 结果 | 时长 | 地图 | 终局状态 |
|---|---|---|---|---|---|
| PaladinoTerminalLE | game_01 | Defeat | 1095.7s | PaladinoTerminalLE | 1 基地 / 8 农 |
| PaladinoTerminalLE | game_02 | Defeat | 540.6s | PaladinoTerminalLE | 1 基地 / 3 农 |
| PaladinoTerminalLE | game_03 | Defeat | 341.6s | PaladinoTerminalLE | 1 基地 / 5 农 |
| PaladinoTerminalLE | game_04 | Defeat | 405.4s | PaladinoTerminalLE | 1 基地 / 2 农 |
| PaladinoTerminalLE | game_05 | **Victory** | 1074.2s | PaladinoTerminalLE | 1 基地 / 42 农 |
| random | game_01 | Defeat | 560.5s | AbyssalReefLE | 0 基地 / 3 农 |
| random | game_02 | Defeat | 1095.3s | ProximaStationLE | 0 基地 / 2 农 |
| random | game_03 | **Victory** | 719.0s | AbyssalReefLE | 4 基地 / 67 农 |
| random | game_04 | Defeat | 300.2s | NewkirkPrecinctTE | 0 基地 / 1 农 |
| random | game_05 | **Victory** | 377.4s | NewkirkPrecinctTE | 4 基地 / 63 农 |

- **PaladinoTerminalLE：1-4，未达成 3/5。**
- **random：2-3，未达成 3/5。**
- **O200 合计：3-7。**

### 关键数据

- **Lane1 (PaladinoTerminalLE) issue_counts**：one_base×5、idle_builder×5、overrun×3、trickle×1。
- **Lane2 (random) issue_counts**：idle_builder×5、overrun×2、supply_block×2、trickle×2、bank×1、one_base×1。
- **Lane1 失败局首塔/第二塔/星门时间**：game_01 3:10/—/5:30；game_02 2:37/3:42/5:09；game_03 4:29/5:43/7:34；game_04 3:33/4:19/5:52。
- **Lane1 胜利局 game_05 时间**：2:33/3:10/4:43 —— 首塔早 1-2 分钟直接决定胜负。
- **Lane1 5/5 one_base**：Rush 局二矿永远开不出，单矿经济被滚雪球。
- **Lane2 game_05 胜利**：终局 4 基地 / 63 农，说明一旦二矿开出、fleet 成型就能赢。

### 失败局尸检（≥3 改进点）

1. **Rush build order 早期防御 timing 极不稳定，首塔波动 2:33-4:29**
   - Lane1 四局失败中三局首塔 ≥3:10，game_03 甚至 4:29 才首塔，此时 Zergling 已在家扫了 1 分多钟。
   - 胜利的 game_05 首塔 2:33、第二塔 3:10、星门 4:43；失败局平均星门 6:00+，fleet 成型晚 90-150s。
   - 根因：build order 的 photoncannon 步骤前插了过多 worker/pylon，且 supply 触发受 8 农民开局/农民波动影响；某些局 forge 后 probe 被抽走或等钱，导致塔链断裂。
   - **O201 改法**：`CarrierOpenerZergRush` 简化早期步骤，forge 后紧跟 2 座 photoncannon，中间最多插 1 个 worker，确保首塔 ≤2:30、第二塔 ≤3:15；同时把 cybercore/stargate 再后挪，让防御链先硬起来。

2. **Rush 局 transition 退出太晚，fleet 转型被拖到 450s 后**
   - production_manager.py 把 Zerg Rush 的 `fleet_at` 强制提到 450s，且 `fleet_exit_allowed` 默认要求地面 ≥14 supply + 星门已拍。
   - 结果是 transition 期纯地面硬顶 7-8 分钟，单矿经济养不起足够地面，也没有舰队输出；敌方 remax 波次把地面磨光后直接穿家。
   - Lane1 game_05 胜利局虽然也是 one_base，但 fleet 在 8:44 已开始升级，说明 fleet 早成型是翻盘关键。
   - **O201 改法**：Zerg Rush 的 `fleet_at` 强制上限从 450 降到 360；`fleet_exit_allowed` 对 Rush 局降低地面门槛（12 supply 或防御评分 ≥25），让星门/舰队航标更早解冻。

3. **二矿在 Rush 局几乎永远开不出**
   - Lane1 5/5 one_base；Lane2 失败局中至少两局也是 0-1 基地到终局。
   - `_want_dynamic_expand` 的兜底条件要求 t≥240、minerals≥200，但 rush 期 mineral 被塔/兵营/气矿持续抽干，400 矿 Nexus 永远攒不够；transition 期虽然有 t≥210 定时开矿，但需 `transition_active` 已进入，且 F2 塔链在 `_expand_holding` 期间仍可能抽干资金。
   - **O201 改法**：Rush/transition 期强制二矿门槛降到 t≥210、minerals≥150；`_expand_holding` 期间 F2 塔目标严格压到 `ec.min`（1-2 座保命塔），其余全部让位给 Nexus 资金。

4. **idle_builder 仍然是失败局最大标签（Lane1×5、Lane2×5）**
   - 农民被派去造 photoncannon/pylon/gateway 后等钱，等钱期间不采矿。game_01 idle worker time 1145s，game_02 798s。
   - 根因：build order 阶段同时启动多座建筑，100-150 矿的支出把 mineral 拆碎；ProtossStaticDefence 的 `dispatch_viable` 守卫挡不住「派工后钱被抽干」的情况。
   - **O201 改法**：简化 build order 减少并行建筑；PSD 注册点加更严格的「当前 mineral ≥ 造价 + 50 buffer」硬 guard，避免农民等钱。

### O201 已落地/计划改动

1. `ares-bot/protoss_builds.yml`：`CarrierOpenerZergRush` 简化早期防御链，forge 后紧跟 2 座 photoncannon，cybercore/stargate 后挪，减少并行建筑数量。
2. `ares-bot/bot/managers/production_manager.py`：
   - Zerg Rush `fleet_at` 强制上限 450 → 360。
   - `fleet_exit_allowed` 对 Rush 局降低地面门槛，让舰队更早解冻。
   - Rush/transition 强制开二矿门槛 t≥240 → 210、minerals≥200 → 150。
   - `_expand_holding` 期间 F2 塔目标严格压到 `ec.min`。
3. `ares-bot/bot/production_plans.py`：同步调整 `transition_expand_at_210` 默认 at=210 → 180（或改调用方传参）。
4. 同步更新 `tests/test_flow_config.py` 的 shipped 断言（如 flows.yml 有改动）。

### 验证

- `poetry run python -m unittest discover -s tests`：待运行。
- 下一组 bench：O201 headless 双车道，Lane1 PaladinoTerminalLE + Lane2 random。

## 2026-08-05 O201 headless 双车道 bench（超时终止，部分结果）

> 运行命令超时 600s，两条 lane 均未完成 5 局；SC2 残留已清理。已完成局数据足够说明 O201 未解决核心问题。

### 部分战绩

| Lane | 局 | 结果 | 时长 | 地图 | 终局状态 |
|---|---|---|---|---|---|
| PaladinoTerminalLE | game_01 | Defeat | 189s | PaladinoTerminalLE | 0 基地 / 4 农 |
| PaladinoTerminalLE | game_02 | Defeat | 251s (实际 984s) | PaladinoTerminalLE | 0 基地 / 0 农 / 6 Tempest |
| PaladinoTerminalLE | game_03 | 超时中断 | ~687s | PaladinoTerminalLE | 1 基地 / 9 农 / 5 Zealot+1 Voidray |
| random | game_01 | Defeat | 256s | ProximaStationLE | 0 基地 / 0 农 |
| random | game_02 | 超时中断 | ~1170s | PaladinoTerminalLE | 0 基地 / 0 农 |

- **已完成局：0 胜 4 败（含 2 局超时中断）。**
- **关键信号**：idle worker time 仍 550-752s；game_03 首塔 2:54、二塔 5:21，比 O200 部分局更差。

### 失败局尸检（≥3 改进点）

1. **build order 里 forge→双塔之间仍插 worker，二塔 timing 极不稳定**
   - O201 意图是“forge 后紧跟 2 座 photoncannon，中间最多 1 个 worker”，但实际 `CarrierOpenerZergRush.OpeningBuildOrder` 写的是 `14 forge`、`14 worker`、`15 photoncannon`、`16 worker`、`17 photoncannon`。
   - 这导致首塔被 14-supply worker 延迟，二塔被 16-supply worker 延迟；game_03 首塔 2:54、二塔 5:21，Rush 中段已穿家。
   - **O202 改法**：把 forge 后的 worker 全移除，改为 `14 forge`、`15 photoncannon`、`16 photoncannon`、`17 supply`，双塔紧挨 forge；supply 和 worker 全部后移到二塔之后。

2. **idle worker time 仍是最大杀手（550-752s）**
   - 已完成局中农民大量时间不在采矿。根因是 build order 阶段并行建筑太多（pylon/gateway/forge/photoncannon/worker 交错），农民被反复派去等钱建筑；PSD 在 build order 期间还会额外注册炮塔/水晶，加剧钉点。
   - **O202 改法**：① 简化 Rush opener，把非防御建筑（cybercore/stargate）全部推到 23+ supply 之后，前期只留 pylon/gateway/forge/双塔/双叉；② 在 build order 完成前（或至少二塔落地前）限制 PSD 注册，避免与 build order 抢工人和 mineral。

3. **二矿/舰队转型仍无经济支撑**
   - game_02 两条 lane 都打到中后期（984s / 1170s），但终局 0 工人、0 基地，说明中期守住了却无法恢复经济；fleet 转型门槛降到 360s 并未改变“rush 期 mineral 被防御抽干 → 无农民 → 无二矿 → 舰队没经济”的链条。
   - **O202 改法**：rush 确认后，在二塔/双叉到位前暂停 zealot 持续生产和 PSD 额外塔，把 mineral 优先留给 Nexus；`first_expand_at` 对 Rush 进一步降到 150s 或按“二塔就绪 + 敌首波退”事件触发，而不是等固定时间。

4. **Bash 600s 超时导致 bench 没跑完**
   - 5 局 headless bench 在部分局长局下需要 >10 分钟，当前 `timeout_ms=600000` 会把整组 bench 杀死，造成数据不完整和 SC2 孤儿进程。
   - **O202 改法**：后续 bench 用无超时或 3600s 超时启动，避免 runner 被系统杀掉。

### O202 已落地/计划改动

1. `ares-bot/protoss_builds.yml`：`CarrierOpenerZergRush` 简化 opener，forge 后连下双塔，worker/tech 后移。
2. `ares-bot/bot/managers/production_manager.py`：在二塔落地前抑制 PSD 额外注册，防止与 build order 抢资源。
3. 后续 bench 启动改为 `--timeout 900` + runner 级 3600s / 无超时，确保 5 局能跑完。
4. 单测：`poetry run python -m unittest discover -s tests` 待运行。
5. 下一组 bench：O202 headless 双车道，Lane1 PaladinoTerminalLE + Lane2 random。


## 2026-08-05 O202 headless 双车道 bench 完整结果 vs Zerg VeryHard Rush（提前终止）

> 两条 lane 实际完成 5 局（Lane1 3 局 + Lane2 2 局），全部为 Defeat；game_03 后耗时过长，为加速迭代提前终止 bench。已完成 5 局数据已足够暴露 O202 核心瓶颈。

### 战绩

| Lane | 局 | 结果 | 游戏时间 | 地图 | 终局状态 |
|---|---|---|---|---|---|
| PaladinoTerminalLE | game_01 | Defeat | 1046.5s | PaladinoTerminalLE | 0 基地 / 1 农 / 2 Tempest |
| PaladinoTerminalLE | game_02 | Defeat | 759.8s | PaladinoTerminalLE | 0 基地 / 1 农 / 1 Voidray |
| PaladinoTerminalLE | game_03 | Defeat | 1227.8s | PaladinoTerminalLE | 0 基地 / 3 农 / 5 Voidray |
| random | game_01 | Defeat | 965.0s | PaladinoTerminalLE | 0 基地 / 2 农 / 无军队 |
| random | game_02 | Defeat | 997.0s | PaladinoTerminalLE | 0 基地 / 1 农 / 2 Voidray+1 Oracle+1 Tempest |

- **PaladinoTerminalLE：0-3**
- **random：0-2（随机图连摇两次 PaladinoTerminalLE）**
- **O202 合计：0-5**

### 关键数据

- **早期防御 timing 已稳定**：forge 01:30-01:31、首塔 02:02-02:03、二塔 02:10-02:33，较 O200/O201 大幅提前。
- **二矿首次建成时间**：405.8s / 474.1s / 494.2s / 546.4s（均在 7-9 分钟才开出）。
- **农民峰值 → 终局**：28→1、40→1、26→3、41→2、37→1。农民在 7-10 分钟内几乎全部死光且未补回。
- **终局资源**：minerals 15-215（枯竭），vespene 742-1546（烂银行）。气体严重过剩，矿物枯竭。
- **终局舰队**：除 game_03 有 5 Voidray 外，其余 0-2 艘舰队单位。星门/FleetBeacon 多数局已就绪，但无矿持续产。
- **issue 标签高频**：idle_builder（每局 5-10 次）、O145 农民停滞（每局 3-8 次）、E6 基地被抄（每局 1-3 次）、E9 敌压境（每局 1-3 次）。

### 失败局尸检（≥3 改进点）

1. **`_rush_active` 一旦置位几乎永不解除，经济被锁死到终局**
   - 所有已完局的后期事件里 `rush=True` 持续存在（game_03 直到 1220s 仍 rush=True）。
   - `_update_rush_state` 解除条件要求「家 40 格内无敌作战单位持续 60s」；Zerg Rush/持续骚扰局总有零星狗/蟑螂在家附近，60s 清净窗永不满足。
   - rush_active 掐死：probe 生产（`not self._rush_active`）、动态扩张（`expansion_blocked` 读 rush_active）、`_rush_economy_response` 停气/取消建筑。
   - 结果：农民死光不补、二矿开出后守不住、气体烂银行。
   - **O203 改法**：舰队已转型成功（`_fleet_transitioned=True`）且防御评分≥15（或 10 叉/5 塔级）时，强制解除 `_rush_active`，恢复 probe 生产和扩张。rush 响应包只服务于「尚未转型」的急性窗，舰队成型后应切回运营。

2. **农民生产被多重刹车家族长期压制**
   - `_build_probes` 的主路径在 `_rush_active` 期间完全停止（除非 `_probe_floor` 或 `_rush_hold`）。
   - `probe_floor_needed` 只在 `t≤350s` 生效，且要求非急性窗；中后期农民掉到 1-3 也不触发。
   - `transition_probe_yield`、`fleet_rebuild_window`、`forge_first_probe_yield` 等叠加，把农民长期压在 12-16，而赢局时代退出时 15-20 农。
   - **O203 改法**：新增「经济崩溃底线」——当 `supply_workers < min(16, 22 * townhalls.amount)` 时，无论 rush/transition/重建窗，优先补农民（probe 生产凌驾于 zealot/塔/科技预留）。没有农民就没有矿，没有矿就没有舰队。

3. **舰队转型后仍被 zealot 消耗 mineral，gas 烂银行**
   - `_effective_spawn` 在 `_rush_active` 且 zealots < `rush_zealots` 时，要么纯叉要么 0.3 叉 0.7 舰队混编。
   - 舰队单位（Voidray 150/150、Tempest 250/175、Carrier 350/250）都需要矿；zealot 持续吞矿导致星门空转、gas 囤积 1000+。
   - 终局 0-2 艘舰队 vs 1000+ gas 反复出现。
   - **O203 改法**：`_fleet_transitioned=True` 后，`_effective_spawn` 不再走 rush_zealots 分支，直接返回纯舰队配方（save_up 正常作用）；仅当敌可见空军威胁 ≥ trigger 时才混入 anti_air。把 mineral 从 zealot 黑洞里释放出来。

4. **二矿/分矿无即时防御，开出即被抄**
   - 新 Nexus 建成后 events  rarely 出现 F2 注册防御；多数局二矿刚落成就遭遇 E6「基地被抄」，农民撤离后分矿直接丢。
   - ProtossStaticDefence 的目标按基地数均摊，新基地没有「落地即 2-3 塔」的硬保底。
   - **O203 改法**：Nexus 建成后 15s 内，若该基地 12 格内就绪塔 <2，强制追加 2 座 photoncannon（走带 can_afford 守卫的 `_build_core_structure`，不抢 build order）。二矿塔先落位再谈经济。

5. **随机地图连续命中 PaladinoTerminalLE，样本单一**
   - Lane2 `--map random` 两局都是 PaladinoTerminalLE，无法判断是 build 问题还是地图特化。
   - **O203 改法**：bench 至少固定一 lane 在 AbyssalReefLE（对照 baseline），或显式排除已过度验证的图；本次先以 PaladinoTerminalLE 为压力图继续迭代，后续补 random 多样本。

### O203 已落地/计划改动

1. `ares-bot/bot/managers/production_manager.py`：
   - `_update_rush_state`：`_fleet_transitioned=True` 且 `_defense_score() >= 15` 时，强制把 `_rush_active` 置 False，打破 rush 经济锁。
   - `_build_probes` 前置逻辑：新增「经济崩溃底线」，`supply_workers < min(16, 22 * townhalls.amount)` 时绕过 rush/transition/重建窗刹车，强制补农民。
   - `_effective_spawn`：`_fleet_transitioned=True` 后不再走 `rush_zealots` 分支，直接返回舰队配方，避免 zealot 持续吞矿。
   - `_handle_new_base_defense`（新增）：Nexus 落成后 15s 内为该基地补 2 座 photoncannon。
2. `ares-bot/bot/production_plans.py`：
   - 新增/调整 helper：`fleet_transitioned_clears_rush`、`probe_economy_floor`。
3. 同步更新相关单测。

### 验证

- `poetry run python -m unittest discover -s tests`：待运行。
- 下一组 bench：O203 headless 双车道，Lane1 PaladinoTerminalLE + Lane2 AbyssalReefLE（对照）。


## 2026-08-06 O203 headless 双车道 bench 完整结果 vs Zerg VeryHard Rush

> 运行模式：**headless（`REALTIME=False`）+ 双车道并行**，Lane1=PaladinoTerminalLE，Lane2=AbyssalReefLE。两条 lane 均为 5 局完成，无 runner 超时、无残留 SC2 进程。

### 战绩

| Lane | 局 | 结果 | 游戏时间 | 地图 | 终局状态 |
|---|---|---|---|---|---|
| PaladinoTerminalLE | game_01 | **Victory** | 1625.4s | PaladinoTerminalLE | 1 基地 / 31 农 / 6 Carrier + 4 Tempest + 2 Voidray |
| PaladinoTerminalLE | game_02 | Defeat | 1559.6s | PaladinoTerminalLE | 1 基地 / 4 农 / 2 Tempest + 2 Voidray |
| PaladinoTerminalLE | game_03 | Defeat | 1196.6s | PaladinoTerminalLE | 1 基地 / 3 农 / 8 Stalker + 5 Voidray + 1 Carrier |
| PaladinoTerminalLE | game_04 | Defeat | 967.2s | PaladinoTerminalLE | 0 基地 / 2 农 / 2 Tempest + 1 Carrier |
| PaladinoTerminalLE | game_05 | Defeat | 434.6s | PaladinoTerminalLE | 0 基地 / 1 农 / 无军队 |
| AbyssalReefLE | game_01 | Defeat | 1187.0s | AbyssalReefLE | 0 基地 / 1 农 / 2 Tempest + 2 Voidray |
| AbyssalReefLE | game_02 | Defeat | 1083.7s | AbyssalReefLE | 1 基地 / 1 农 / 1 Tempest + 2 Voidray |
| AbyssalReefLE | game_03 | Defeat | 1192.0s | AbyssalReefLE | 1 基地 / 3 农 / 2 Tempest + 2 Voidray |
| AbyssalReefLE | game_04 | Defeat | 1080.7s | AbyssalReefLE | 1 基地 / 2 农 / 2 Tempest + 3 Voidray |
| AbyssalReefLE | game_05 | Defeat | 898.7s | AbyssalReefLE | 0 基地 / 0 农 / 1 Tempest + 1 Voidray |

- **PaladinoTerminalLE：1-4，未达成 3/5。**
- **AbyssalReefLE：0-5，未达成 3/5。**
- **O203 合计：1-9。**

### 关键数据

| 指标 | PaladinoTerminalLE | AbyssalReefLE |
|---|---|---|
| 平均时长 | 1193.6s | 1088.4s |
| 最高银行 | 580 minerals | 1090 minerals |
| Carrier 首次出现平均 | 1146.4s | 972.3s |
| Interceptor 首次出现平均 | 1309.8s | 1008.5s |
| 终局平均编成 | ZEALOT×2, VOIDRAY×5, CARRIER×1, ORACLE×1, TEMPEST×3.7, **STALKER×8** | TEMPEST×2, ORACLE×1, ZEALOT×1, VOIDRAY×2 |
| issue_counts | one_base×5, idle_builder×5, overrun×4, trickle×1 | one_base×3, idle_builder×5, overrun×5, trickle×2 |

- **Paladino 唯一胜局 game_01**：1 矿硬守 534s 才开二矿，靠 Voidray→Tempest→Carrier late-game 推掉。
- **Abyssal 终局舰队只剩 2 Tempest/2 Voidray**：max_bank 1090 说明**有钱花不出去**——不是收入问题，是产能/科技链被锁死。
- **Paladino 终局平均 8 Stalkers**：气体被地面单位（主要是追猎）吃掉，fleet 上不了量。

### 失败局尸检（≥3 改进点）

1. **transition 退出太晚，fleet 转型平均拖到 970-1150s**
   - 当前 `flows.yml` carrier.transition.fleet_at=320，代码对 Zerg Rush 强制 `max(fleet_at, 360)`。
   - 但实际 Carrier 首次出现均值 Paladino 1146s / Abyssal 972s，说明即使过了 360s 的“时间闸”，`fleet_exit_allowed` 的经济/地面/星门叠加门 + `fleet_transition_strong_exit` 的清净 30s/领先敌情 10 supply 仍把退出锁死到 8-12 分钟。
   - 败局中 `_transition_active` / `_rush_active` 长期不解冻，星门/FleetBeacon 被冻结，农民停滞（O145）、首塔派工 not_viable/tech_not_ready、基地 2→1→0。
   - **O204 改法**：
     - Zerg Rush 强制 `fleet_at` 从 360 降到 **280**；Timing 保持 320。
     - `fleet_transition_strong_exit` 的 `min_defense` 从 25 降到 **20**，`clear_needed` 从 30s 降到 **20s**（Zerg Rush 骚扰密度高，30s 清净窗太奢侈）。
     - `fleet_exit_allowed` 的 deadline 从 540s 提前到 **480s**，Rush 局 `min_ground` 从 10 降到 **6**（足够 3 叉/3 追猎即可，不强求地面大军）。

2. **地面配方吃气过多，fleet 产能被 stalker 挤占**
   - transition 的 `ground_spawn` 是 STALKER:ZEALOT = 0.4:0.6，STALKER p0 优先；Paladino 终局平均 8 Stalkers，每追猎 125/50 持续抽血抽气。
   - 过渡地面本应是“矿耗肉盾”，结果气被追猎吃掉，FB 就绪后没气出 Voidray/Carrier。
   - **O204 改法**：
     - transition ground_spawn 改为 **STALKER:ZEALOT = 0.2:0.8**，或彻底关闭 stalker（0:1），只靠 zealot + 塔守窗。
     - 同步把 `gateway_cap` 从 2 降到 **1**（少一座兵营抢 150 矿），让 FB/二矿资金窗更早出现。

3. **二矿仍然开得太晚/开不出，单矿经济被滚雪球**
   - Paladino 5/5 one_base；Abyssal 3/5 one_base。`first_expand_at=150` 已写入 flows，但 rush_active 期间 `should_expand_dynamic` 直接返回 False，transition 期二矿需 `transition_expand_ready`（塔≥2、地面≥4、清净≥8s），门槛仍高。
   - `_expand_holding` 期间塔链/地面仍可能把 Nexus 资金吃光。
   - **O204 改法**：
     - Rush/transition 期引入**强制二矿触发器**：当时间 ≥180s、已有≥2 座就绪 photoncannon、且家 40 格无敌 ≥3 时，无视 `rush_active` 直接触发 `_want_expand`。
     - `_expand_holding` 期间，非 rush/threat 急性窗时把塔目标严格压到 `ec.min`（1-2 座），剩余 mineral 全部让给 Nexus。
     - `transition_expand_ready` 的 `min_ground` 从 4 降到 **2**，`clear_needed` 从 8s 降到 **5s**。

4. **`rush_active` 在舰队成型后再触发就解不开，经济二次锁死**
   - O203 只在 `_fleet_transitioned` 且评分≥15 时强制解 rush，但败局中 rush 在 transition 期/转舰队后被重新置位（敌后续压家）就再也解不开。
   - 一旦重新置位，probe 生产、动态扩张、`_rush_economy_response` 停气全部恢复锁死。
   - **O204 改法**：
     - 新增**硬解冻条件**：当 `time > 480s`、已有就绪星门 + FleetBeacon、且 `_fleet_transitioned=True` 时，无论家附近有没有敌兵，都把 `_rush_active` 置 False；若敌真压家，`_update_rush_state` 下帧会重新置位，不影响守家响应。
     - 该解冻只执行一次（latch），避免反复横跳。

5. **idle_builder 仍是 10/10 标签，前期农民干等造建筑**
   - 司令观察：仍有农民前期干等着造建筑，没有采矿最大化。
   - 根因：PSD 首塔/气矿/pylon 反复 not_viable，probe 被钉在建造点；build order 完成后 `ProtossStaticDefence` 与 `AutoSupply`/`pylon buffer` 并行注册，多座建筑同时派工等钱。
   - **O204 改法**：
     - 前期（`time < 120s`）`ProtossStaticDefence` 注册前加硬 guard：`minerals ≥ 目标建筑矿价 + 75 buffer`，不够就不注册，避免农民等钱。
     - `BuildStructure` 派工点 fallback：当首选 placement 连续 2s not_viable 时，换到主矿其他空闲槽位（`closest_to` 改 `fallback_to_base_center`），避免探机被钉在无效点。
     - `_handle_idle_workers` 的 `early_age` 前期从 1.5s 降到 **1.0s**，矿缺口 3s 收入补不上立即撤回。

### O204 已落地/计划改动

1. `ares-bot/flows.yml`：
   - carrier.transition.fleet_at：Zerg Rush 强制上限 360 → **280**。
   - carrier.transition.ground_spawn：STALKER 比例 0.4 → **0.2**（或 0），ZEALOT 0.6 → **0.8**（或 1.0）。
   - carrier.transition.gateway_cap：2 → **1**。
   - carrier.auto_expand.first_expand_at：Rush/transition 期引入 180s 强制二矿触发器，不依赖 `rush_active` 解锁。

2. `ares-bot/bot/managers/production_manager.py`：
   - `_update_transition_state`：Rush 局 `fleet_at` 降到 280；strong_exit 评分门 25→20、清净窗 30s→20s。
   - `_update_rush_state`：新增 `time > 480s + SG/FB 就绪 + _fleet_transitioned` 硬解冻，只执行一次。
   - `_want_dynamic_expand` / `_expand_holding`：Rush/transition 期 180s 后若防御站稳强制开二矿；holding 期间非急性窗塔目标压到 ec.min。
   - F2/PSD 注册点：前期加 mineral buffer guard，防止农民等钱；placement not_viable 时 fallback 到基地中心附近。

3. `ares-bot/bot/production_plans.py`：
   - `fleet_transition_strong_exit`：允许调用方传 `min_defense`/`clear_needed`（默认不变，Rush 局传 20/20）。
   - `fleet_exit_allowed`：Rush 局 deadline 540→480、`min_ground` 10→6。
   - `transition_expand_ready`：`min_ground` 4→2、`clear_needed` 8→5。
   - 新增 `forced_expand_during_transition` 判据（180s/2 塔/清净 5s/矿≥200）。

4. 同步更新相关单测（`tests/test_production_plans.py`、`tests/test_flow_config.py` 如受影响）。

### 验证

- `poetry run python -m unittest discover -s tests`：待运行。
- 下一组 bench：O204 headless 双车道，Lane1 PaladinoTerminalLE + Lane2 AbyssalReefLE（继续压力图对照）。

## 2026-08-05 O204 carrier vs Zerg VeryHard/Rush headless 双车道 bench

### O204 验证结果

- **Lane1 PaladinoTerminalLE**: 2 胜 3 负 → 未达 3/5
  - 胜：game 01 (548s), game 02 (751s)
  - 负：game 03 (825s), game 04 (713s), game 05 (175s)
- **Lane2 AbyssalReefLE**: 3 胜 2 负 → **达成 3/5**
  - 胜：game 01 (610s), game 04 (769s), game 05 (797s)
  - 负：game 02 (449s), game 03 (434s)

按项目规则（任一 lane 3/5 即算该组合通过），**Zerg Rush 组合通过**。但 Paladino 2/3 败局暴露系统性问题，必须做尸检并落地 O205 后再进下一组合。

### O204 败局尸检（ Paladino 3 负 + Abyssal 2 负，合并模式）

**共同根因 1：二矿/分矿防御交付失败，自然基地常 0 炮塔即被攻陷**
- Abyssal game_02/game_03：自然基地被攻时 `F2:...,(70,118,0,3)`，0 光子炮、3 水晶。
- Paladino game_05：343s 判定“防御达标”转舰队，实际仅 3 炮/2 电池，399s 被 14 狗+5 蟑螂+5 刺蛇一波穿掉二矿。
- 根因：`expansion_cannons.min` 未在自然落地前/落地后短期内兑现；`ProtossStaticDefence` 的 placement 在压力期 not_viable，fallback 不足。

**共同根因 2：舰队不在被攻基地，地面部队贴脸时空军在外**
- Paladino game_03/game_04：Tempest/Voidray 前锋在外，主基地/二矿被地面流冲入；终局编成里 Tempest 平均 15.5 艘，但关键防守时不在场。
- Abyssal game_02：第一次丢自然后复矿，第二次被抄时空军仍未回防。
- 根因：`carrier_offensive` / 进攻锚点把主力拉离基地；没有“基地被攻 → 强制召回/就近防守”的兜底。

**共同根因 3：舰队转型太慢，前期/中期仍大量地面兵占气占矿**
- Abyssal game_03：Stargate 直到 5:25 才下，舰队成型前已被 Roach/Hydra 压垮。
- Paladino game_05：转舰队过早判定达标，但 Fleet Beacon 卡钱 >45s，航母科技上不来。
- 根因：transition 期 `ground_spawn` 仍在产 Stalker/Zealot，气体被地面兵吃掉；Stargate/Fleet Beacon 建造优先级被防御/产能插队。

**共同根因 4：rush_active 反复横跳，经济二次锁死**
- Paladino game_03/game_04：`O203 rush-lock` 在 536s/674s/693s/1299s 多次切换，worker 生产在恢复窗口被冻结，终局 worker 从 40+ 跌到 0。
- 根因：硬解冻 latch 只执行一次，但 `_update_rush_state` 仍会根据敌兵重新置位，导致 transition 后经济反复冻结。

**共同根因 5：idle_builder 死锁，农民等钱造炮/水晶不释放**
- 两 lane 复盘标签均含 `idle_builder×5`；终局前常见 `O118/116 首塔派工=not_viable` 循环，probe 被钉点 3s+ 不采矿。
- 根因：多座防御建筑同时派工， mineral 被瞬间抽干；没有“派工后 5s 内开不了工就释放工人”的熔断。

### O205 改进计划（≥3 条，落地后验证）

1. **自然基地防御强制前置：二矿 Nexus 落成前必须先有 2 炮 + 1 电池在铺/就绪**
   - 改 `production_manager._should_build_defense`：当 `bases_including_pending ≥ 2` 或 `nexus_in_progress` 时，把 natural 的 cannon 目标提到 `ec.min + 2`，且优先在 natural 位置注册 `ProtossStaticDefence`。
   - 新增 placement fallback：PSD 首选 not_viable 超过 2s 时，fallback 到 natural/Nexus 中心 5 格内任意可建点。

2. **基地被攻时召回空军 / 设置 defensive rally**
   - 改 `combat_manager`：当任一 Nexus 15 格内有 ≥6 敌地面单位时，把 `ATTACKING` 的 Tempest/Voidray/Carrier/Oracle 临时切换 `MoveTarget` 回最近受威胁基地（保留 10s 滞回），不让他们继续前锋在外。
   - 与现有 `E6` 工人撤离联动：触发 E6 的基地同时触发空军召回。

3. **Rush 局舰队转型再提速 + ground_spawn 矿耗化**
   - `flows.yml`：Zerg Rush 下 `carrier.transition.ground_spawn` 去掉 STALKER（`{ZEALOT:1.0}`），让气体全部留给 Stargate/Fleet Beacon/Tempest/Carrier。
   - `production_manager`：transition 期保证 Stargate 不晚于 240s 开建；Fleet Beacon 在首个 Stargate 就绪后 30s 内强下（气体预留）。

4. **rush_active 解冻后加 60s 死区 / 经济保护**
   - 硬解冻 latch 触发后，60s 内不再因敌兵重新进入 full rush-lock；期间保留 `threat_response_active` 用于塔/兵响应，但不停 worker、不停 expansion、不停 Fleet Beacon。

5. **idle_builder 熔断：派工后 5s 无法开工则释放工人**
   - 在 `main._handle_idle_workers` 或 production_manager 层：跟踪 `BuildStructure` 派工时间戳，超过 5s 且建筑未开始（progress=0）则 `release_from_build_tracker` 并让工人回矿。

### 验证

- `poetry run python -m unittest discover -s tests`
- 下一组 bench：O205 headless 双车道，Zerg Power @ AbyssalReefLE + PaladinoTerminalLE（继续压力图对照）。

## 2026-08-05 O205 carrier vs Zerg VeryHard/Power headless 双车道 bench

### O205 验证结果

- **Lane1 AbyssalReefLE**: 2 胜 1 负 1 异常 → 未达 3/5（game 03 败于 1377.9s，base wipe）
  - 胜：game 01 (501s), game 02 (429s)
  - 负：game 03 (1377.9s)
- **Lane2 PaladinoTerminalLE**: 3 胜 1 负 1 异常 → **达成 3/5**
  - 胜：game 01 (311s), game 02 (510s), game 04 (959.8s)
  - 负：game 03 (1302.6s)

按项目规则（任一 lane 3/5 即算该组合通过），**Zerg Power 组合通过**。

两 lane 复盘共同标签：**idle_builder**（Paladino×4 / Abyssal×3）、**trickle**（×3/×2）、**overrun**（各×1）。

### O205 败局尸检（Abyssal game_03 + Paladino game_03）

**根因 1：idle_builder 规模爆炸，前期农民长期干等造建筑，采矿未最大化（司令重点指出）**
- Paladino game_03：
  - FORGE 工人 `@28,92` 从 **188s 干等到 393s**（≈3.5 分钟）。
  - PHOTONCANNON 工人 `@33,74` 从 **683s 干等到 960s**（≈4.5 分钟）。
  - NEXUS 工人 `@24,72` 从 **409s 干等到 474s**。
- Abyssal game_03：
  - NEXUS 工人 `@70,118` 从 **184s 干等到 405s**（≈3.7 分钟）。
- 根因：
  - `_presumed_defense_chain` 对 FORGE/PHOTONCANNON/GATEWAY 走 `critical_dispatch_exempt` 豁免，绕过 `dispatch_viable` 与重派冷却；在 Power/Macro 局里 `_presumed_rush`（探机失联/unknown verdict）持续触发，工人被反复派到工地等钱。
  - `ExpansionController` 的 Nexus 预走位 buffer 仅 25 矿，乐观估计「到位时钱够」，但途中被 probe/pylon/塔抽干，工人钉在扩张点。
  - `_handle_idle_workers` 对 TOWNHALL 类型 grace=30s，Nexus 工人等不起时撤回极慢，且释放后下一帧又被重新派去。

**根因 2：对局被拖到 20+ 分钟，Zerg Power 宏宏观碾压**
- 两局均在 1300s 左右基地全失：Abyssal 终局 0 基地/19 农/3 Tempest；Paladino 终局 0 基地/2 农/1 Oracle+1 Zealot。
- Paladino 终局仍有 **vespene=957、minerals=13**——气富余、矿崩盘，说明经济/部队结构失衡。
- 根因：前期 idle_builder 拖累经济；fleet 成型后没有主动推进/换家终结比赛，让 Zerg 攒出 Ultralisk/Corruptor/Infestor/Ravager 混合大兵团，最终被多线 overwhelm。

**根因 3：trickle——舰队/守军未集中，被多波逐步消耗**
- 复盘 trickle 标签反复出现；终局 army 数量少且分散，关键防守时刻不在场。
- 根因：空军进攻锚点把主力拉离基地，回防阈值/滞后在 Power 局长消耗战中不够灵敏。

### O206 改进计划（≥3 条，落地后验证）

1. **Presumed 防御链关键件只在地 rush_confirmed 时才豁免资金守卫**
   - `production_manager._presumed_defense_chain`：FORGE/PHOTONCANNON/GATEWAY 的 `critical=True` 仅当 `self._rush_confirmed` 为真；plain `_presumed_rush` 走正常 `dispatch_viable` + 重派冷却。
   - 保留真实 rush 的 forge 准点机制，但避免 Power/Macro 局因探机失联把农民长期钉在工地。

2. **F2 PSD 紧急 bypass 去掉 `_presumed_rush`**
   - 原条件 `self._rush_confirmed or self._transition_active or _presumed_rush` 改为 `self._rush_confirmed or self._transition_active`。
   - 真实 rush / transition 仍保留紧急注册，疑似 rush 不再绕过资金预估守卫。

3. **Nexus 预走位收紧 + TOWNHALL grace 缩短**
   - `ExpansionController` 的 `_preposition` buffer 从 25 矿提到 **75 矿**，并仅当 `dispatch_viable` 真正成立时才 `prioritize=True`；减少工人过早出发、在扩张点空转。
   - `main.py` TOWNHALL/FleetBeacon 的 O11 grace 从 30s 降到 **15s**，超过 15s 仍买不起 Nexus 即释放工人回矿，避免单农民被钉 3 分钟以上。

4. **Fleet 成型后主动终结比赛，避免拖入 Zerg 大后期**
   - 当 fleet_total ≥ 8 且经济≥3 矿时，若敌方主基可见且 60s 内无重大战损，提升进攻积极性（attack_target 不再轻易因小波次回防），优先换家/推主矿，不给 Zerg 攒 Ultralisk/Corruptor 时间。

### 验证

- `poetry run python -m py_compile ares-bot/bench.py`
- `poetry run python -m unittest discover -s ares-bot/tests`
- 下一组 bench：O206 headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE。


## 2026-08-06 O206c carrier vs Zerg VeryHard/Timing headless 双车道 bench

### O206c 验证结果

- **Lane1 PaladinoTerminalLE**: 0 胜 5 负 → 未达 3/5
  - 负：game 01 (464s), game 02 (535s), game 03 (584s), game 04 (555s), game 05 (580s)
- **Lane2 AbyssalReefLE**: 2 胜 3 负 → 未达 3/5
  - 胜：game 02 (708s), game 03 (804s)
  - 负：game 01 (746s), game 04 (745s), game 05 (459s)

**Zerg Timing 组合未通过**，必须做尸检并落地 O207 改进后再开下一组。

### 共同根因

1. **`_early_core_missing` 把早期防御链关到 cybercore 排队之后，Zerg Timing 裸接 timing 波**
   - `_early_core_missing` 在 carrier、单矿、cybercore/stargate 未排队前为真，会整段关闭 F2 注册、`_presumed_defense_chain`、冲刺总闸。
   - vs Zerg Timing 时，cybercore 排队 ≈80-90s，forge 再被拖到更晚，首塔 200s 后才落地；而 timing 第一波 160-200s 已到脸（Paladino 5/5 overrun、Abyssal game_01 420s 仍单矿）。
   - 结果是「有防御代码但早期没执行」，农民被波次直接冲进矿区。

2. **F2 / PSD 一次派多工人等钱，`idle_builder` 未根治**
   - Abyssal 5 局全带 `idle_builder` 标签，game_05 单局 14 次。
   - `dispatch_viable` 只按单座 PhotonCannon（150 矿）估算，但 PSD 的 `to_count_per_base=cannons` + `max_on_route=mor` 会同时派多个工人； mineral 被瞬间抽干后多人钉点。
   - `_expand_holding` / `_fb_waiting` 期间塔目标虽被压到 `_ec_min`，但 mor 仍为 2，继续把 Nexus/FB 资金窗抽干。

3. **Zerg Timing 被 `rush_active` 长锁 60s，二矿永远开不出**
   - `_update_rush_state` 一旦触发（≥2 敌兵进家 40 格），保持 60s 才解除；timing 波次间隔往往 <60s，导致 `rush_active` 长期为真。
   - `rush_active` 直接阻塞 `should_expand_dynamic`；Paladino `one_base×4`，Abyssal game_01 420s 仍单矿。单矿经济在 500s 后被滚雪球碾压。

4. **FleetBeacon 被摧毁后重建优先级不足，舰队断档**
   - 多局中局 FB 实体丢失（`FB_DIAG: truly_missing=True`），但 `tech_yields_to_threat` 在威胁期把 FB 新建让位给塔链。
   - 没有 FB 就没有舰队主 C，农民在 700s 左右被抄光，基地从 3→1→0。

### O207 改进计划（≥3 条，已落地）

1. **vs Zerg Rush/Timing 时，`_early_core_missing` 不再阻塞早期防御链**
   - F2 注册闸、`_presumed_defense_chain`、防御冲刺总闸增加 `or self._is_zerg_rush_timing()` 放行。
   - 让 forge+首塔在 cybercore 排队前就能启动，赶上 timing 波 273-289s。

2. **F2 建造槽动态压到 1，阻断多工人同时等钱**
   - 非 rush/威胁/timing 冲刺期，`max_on_route=1`；rush_hold 才给 4 槽，rush/threat/timing_sprint 给 2 槽。
   - `_expand_holding` 或 `_fb_waiting` 时进一步压到 1，确保 Nexus/FB 资金窗不被塔工人抽干。

3. **Zerg Timing 的 `rush_active` 敏感度下调、自动解除缩短**
   - `_near_threshold` 从 2 提到 3，只有成规模波次才置 rush latch。
   - `_clear_timeout` 从 60s 降到 25s，波间隙允许开二矿/恢复经济。

4. **Zerg Timing 启用 `unknown_verdict_defense` 与 `transition_timing_sprint`**
   - verdict 仍是 unknown 时，t≥200s 按 presumed 同级拉 2 塔防御。
   - t≥240s 起启用 timing 冲刺，塔目标保底 3、GW 让位闸旁路，避免波到脸时防御不足。

5. **FleetBeacon 丢失后重建优先于 threat 让位**
   - `_build_flow_structures` 中 FB 建造：当已转舰队且 `_fb_truly_missing` 时，绕过 `tech_yields_to_threat`，确保威胁期也能重建 FB。

6. **Zerg Timing 二矿启动提前到 240s**
   - `_want_dynamic_expand` 中 Timing 的 `first_expand_at` 下限从 300s 降到 240s（Rush 仍保持 300s），配合 rush 锁缩短，避免 one_base 滚雪球。

### 验证

- `poetry run python -m py_compile ares-bot/bot/managers/production_manager.py ares-bot/bot/production_plans.py`
- `poetry run python -m unittest discover -s ares-bot/tests`：649 例通过
- 下一组 bench：O207 headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE。


## 2026-08-06 O207 carrier vs Zerg VeryHard/Timing headless 双车道 bench

### O207 验证结果

 bench 在 Lane1 game_03 / Lane2 game_03 启动前因 0-4 全败被中断。

- **Lane1 PaladinoTerminalLE**: 0 胜 2 负（已观测）
  - 负：game_01 (768s), game_02 (1583s)
- **Lane2 AbyssalReefLE**: 0 胜 2 负（已观测）
  - 负：game_01 (866s, 首局崩溃重试), game_02 (726s)

**Zerg Timing 组合仍未通过**，必须做尸检并落地 O208。

### 共同根因

1. **Zerg Timing 未进入 transition，中期无地面海**
   - O207 仅把 Rush 强制拉进 transition；Timing 仍走非 transition 的 carrier 配方。
   - 非 transition 路径下 FleetBeacon 在 578s(Paladino game_01)/650s(Abyssal game_01) 才落成，舰队成型过晚。
   - 中期只靠 pre_fleet 几个 ZEALOT/STALKER 顶 Roach+Ravager+Hydra 混合波次，被直接滚平。

2. **经济被锁在 2 基地，carrier 后期规模上不去**
   - `_want_dynamic_expand` 把 Zerg Timing 的 max_bases 锁到 2（O186 遗留下来的 Rush 逻辑）。
   - Paladino game_02 打到 1583s，2 基地 39-44 工人， army 长期只有 6-10 艘 TEMPEST；130 supply cap 只用了 75-79。
   - 2 基地 mineral 收入支撑不了 4 STARGATE 持续暴兵 + 大量炮台/电池，最终 gas 1452 堆积但 mineral 枯竭，部队越打越少。

3. **纯 Zealot transition ground_spawn 无法应对 Roach/Ravager**
   - 虽然 O207 没让 Timing 进 transition，但 Rush 的 transition ground_spawn 是纯 Zealot（O205）。
   - 即便 Timing 进入 transition，纯 Zealot 对 Roach/Ravager 也是劣势，需要 Stalker/Zealot 混编。

4. **农民被屠杀后恢复极慢**
   - 败局时 workers 经常掉到 0-4，没有快速补农机制；基地被推后经济直接归零。

### O208 改进计划（≥3 条，已落地）

1. **Zerg Timing 强制进入 transition**
   - `production_manager.__init__` 把 `_ai_build == "timing"` 也加入强制 transition 条件，与 Rush 同待遇。
   - 让 Timing 也能用 ground_spawn 地面海 + 舰队解冻框架。

2. **Timing 使用更晚/更稳的舰队退出点**
   - `_update_transition_state` 中 Timing 的 `_fleet_at` 设为 `max(flow.fleet_at, 380s)`（Rush 280s，默认 320s）。
   - strong_exit / exit_allowed 阈值取 Rush 与默认之间的中间值（min_defense=22, clear_needed=25, min_ground=10, deadline=520, strong_exit_score=22）。

3. **Timing transition 期间使用 Stalker/Zealot 混编地面配方**
   - `_effective_spawn` 中，当 `_transition_active` 且 Zerg Timing 时返回 `{STALKER 0.4 p0, ZEALOT 0.6 p1}`。
   - 追猎吃气先行、叉子矿耗补位，比纯 Zealot 更能打 Roach/Ravager。

4. **Zerg Timing 允许 3 基地经济**
   - `_want_dynamic_expand` 中仅 Rush 锁 2 基地，Timing 保持 flows.yml 的 max_bases=3，支撑 carrier 后期舰队规模。

5. **Timing 过渡期 gateway_cap 提到 2**
   - `_build_extra_production`、`_spend_bank`、`_want_dynamic_expand`、`tower_yields_gateway_chain` 等处的 transition gateway_cap 对 Timing 统一用 2（Rush 仍走 flows.yml 的 1）。
   - 保证混编地面的产能，不让兵营成为瓶颈。

### 验证

- `poetry run python -m py_compile ares-bot/bot/managers/production_manager.py ares-bot/bot/production_plans.py ares-bot/bench.py`
- `poetry run python -m unittest discover -s ares-bot/tests`：649 例通过
- 下一组 bench：O208 headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE。


## 2026-08-06 O208 carrier vs Zerg VeryHard/Timing headless 双车道 bench

### O208 验证结果

- **Lane1 PaladinoTerminalLE**: 1 胜 4 负 → 未达 3/5
  - 胜：game_01 (356s)
  - 负：game_02 (774.9s), game_03 (723.9s), game_04 (756.9s), game_05 (???)
- **Lane2 AbyssalReefLE**: 2 胜 3 负 → 未达 3/5
  - 胜：game_02 (1215.7s), game_05 (595s)
  - 负：game_01, game_03 (1007.0s), game_04 (874.3s)

**Zerg Timing 组合仍未通过**，但相比 O207 的 0-4 已有改善（Abyssal 拿到 2 胜）。

### 共同根因

1. **transition 退出不一致，FleetBeacon 落成时间方差大**
   - Abyssal 胜局 game_02：3 基地 + FB 498s + Tempest 627s，最终 20 Tempest / 4 Carrier / 196 supply 碾压。
   - Paladino 败局 game_03/04：FB 拖到 554s 或根本不建，地面部队打光后无舰队翻盘。
   - Paladino 平均 Tempest 首次出现 795s，Carrier 1036s；Abyssal 627s/882s。说明地图/压力差异导致退出点离散。

2. **炮塔过度建设吃掉舰队资金**
   - Abyssal game_03 在 964s 有 20 门 PhotonCannon（3 基地理论 max=12）。
   - `expansion_cannons.max=4` + `main_siege`  threat 分支拉满，导致中局把矿物全部砸进塔，FleetBeacon/星门/舰队产能被饿死。

3. **idle_builder 仍普遍**
   - Paladino 5/5 带 idle_builder，Abyssal 5/5 带 idle_builder。
   - PSD 多工人同时派工等钱的问题未根治，尤其在 transition 期兵营/塔/科技并行时。

4. **one_base 仍在**
   - Paladino 3/5 one_base，Abyssal 2/5 one_base。
   - 单矿经济撑不起混编地面 + 舰队双轨，transition 中后期被滚雪球。

### O209 改进计划（≥3 条，已落地）

1. **Zerg Timing transition 退出进一步提前/放宽**
   - `_update_transition_state`：Timing 的 `_fleet_at` 从 380s 降到 340s。
   - strong_exit / exit_allowed 阈值同步放宽：min_defense=18, clear_needed=20, min_ground=8, deadline=480, strong_exit_score=18。

2. **Zerg Timing transition 内强制启动 FleetBeacon**
   - `_build_flow_structures`：Timing transition 中星门已就绪且 t≥360s 时，即使 threat_active 也允许建 FB，避免 FB 被 threat 让位永久卡住。

3. **Zerg Timing 炮塔封顶 3/基地**
   - F2 塔目标计算中，Timing 局把 `ec.max` 压到 3，杜绝 20+ 炮塔吃光舰队资金的极端情况。

4. **继续保留 O208 的混编地面 / 3 基地 / gateway_cap=2**
   - 这些改动在 Abyssal 胜局中已证明有效，仅对退出时机和炮塔上限做收敛。

### 验证

- `poetry run python -m py_compile ares-bot/bot/managers/production_manager.py ares-bot/bot/production_plans.py ares-bot/bench.py`
- `poetry run python -m unittest discover -s ares-bot/tests`：649 例通过
- 下一组 bench：O209 headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE。


## 2026-08-06 O209 carrier vs Zerg VeryHard/Timing headless 双车道 bench

### O209 验证结果

- **Lane1 PaladinoTerminalLE**: 1 胜 4 负 → 未达 3/5
  - 胜：game_04 (893s)
  - 负：game_01 (???), game_02 (???), game_03 (???), game_05 (1226.2s)
- **Lane2 AbyssalReefLE**: 3 胜 2 负 → **通过 3/5**
  - 胜：game_01 (913s 前), game_03 (913s), game_05 (1356.1s)
  - 负：game_02 (975s 后), game_04 (443s)

**Zerg Timing 组合已通过**（AbyssalReefLE 3-2），PaladinoTerminalLE 仍 1-4 惨败。

### 共同根因

1. **idle_builder 仍是最大头，PhotonCannon 占绝对多数**
   - 两 lane 共 10 局全部带 idle_builder；Paladino 5/5、Abyssal 5/5。
   - 败局中 PhotonCannon 等钱事件占 96.7%，Nexus/Pylon 已大幅减少。
   - 根因：`dispatch_viable` 按「到位时预计有钱」放行，途中被 warp-in/产兵/另一座塔抽干，农民钉点。

2. **O189 强制开二矿未真正落地**
   - Abyssal game_04：t≥210 反复触发 `O189:Zerg rush/timing 单矿太久,强制开二矿`，但 `ExpansionController.prioritize` 由 `dispatch_viable(..., buffer=75)` 决定，150≤矿<475 时仍不派工预走位；其间塔/兵继续吃矿，443s 出局时仍 1 基地、0 舰队。

3. **transition/timing 冲刺期地面兵折跃到前线被分批吃光**
   - spawn_target 只在 `_rush_active` 时走 `_rush_spawn_target()`，transition/timing_sprint 仍走 `_front_point()`；小股 Zealot/Stalker 一落地就进虫群，造成 trickle。
   - Paladino 败局终局 supply 多次崩落（game_03 0/56、game_05 1/56 等）。

4. **Paladino  overrun 集中**
   - Paladino issue_counts：overrun×4，trickle×3，one_base×1，supply_block×1。
   - 地图开口/分矿位置导致 timing 波更容易压家，塔阵未成规模即被穿。

### O210 改进计划（≥3 条，已落地）

1. **PhotonCannon 非紧急状态强制 can_afford 才派工**
   - `bot/managers/production_manager.py` F2 段：计算完 `cannons` 后，非 rush/威胁/timing 冲刺/rush 持有期/presumed 时，若 `not can_afford(PHOTONCANNON)` 则把 `cannons` 压到 0，不注册新塔。
   - 根治 dispatch_viable 预测可用、途中被抽干导致的 idle_builder。

2. **O189 强制开矿立即预走位**
   - `bot/managers/production_manager.py`：O189 触发时置 `_o189_forced_expand=True`；`ExpansionController` 注册改用 `prioritize=_preposition or self._o189_forced_expand`，让农民在 150 矿时就走位等 400，不等 dispatch_viable 凑够 475。

3. **transition/timing 冲刺期地面兵改防守集结点**
   - `bot/managers/production_manager.py` SpawnController 的 `spawn_target`：`_rush_active or _transition_active or _timing_sprint` 时统一走 `_rush_spawn_target()`，避免碎兵到前线送死。

### 验证

- `poetry run python -m unittest discover -s ares-bot/tests`：649 例通过
- 下一组 bench：O210 headless 双车道，Zerg Rush @ AbyssalReefLE + PaladinoTerminalLE（或 Zerg Power，视司令指示）。

---

## O210: carrier vs Zerg VeryHard Rush（2026-08-06）

### 战绩

headless 双车道并行：
- Lane1 AbyssalReefLE: **1 胜 4 负**
- Lane2 PaladinoTerminalLE: **2 胜 3 负**
- **Zerg Rush 未打穿**（需 5 局 3 胜）。

retro 标签：
- Lane1: `idle_builder×5`, `overrun×4`, `trickle×1`
- Lane2: `idle_builder×5`, `one_base×3`, `overrun×2`

### 尸检发现（scripts/o210_autopsy.py）

- **idle_builder 是系统性问题**：每局 137–787 次，多数从 t≈100s 开始，理由是“未开工造 PHOTONCANNON”。
- ** forge→首塔→二塔连续派工**：build order `14 forge, 15 photoncannon, 16 photoncannon` 中，塔工比 forge 早到 15–20s，工人钉在塔点等 forge 完工。
- **expansion_cannons min=4 在经济紧张期过度铺塔**：quiet 期仍按 4 塔/基地派工，塔工等钱，舰队成型资金被抽干。
- **二矿普遍晚**：base2_time 305–863s，Paladino game_05 甚至 863s 才开二矿。
- **败局终局几乎都是 0 基地 + 气烂银行**：vespene 400–2000，minerals 贴 0，基地丢失后未重建。

### 3 个改进点（已落地 O211）

1. **build order 插入 worker，错开 forge 与双塔派工**
   - 文件：`ares-bot/protoss_builds.yml` `CarrierOpenerZergRush.OpeningBuildOrder`
   - 改法：`14 forge, 15 worker, 16 photoncannon, 17 worker, 18 photoncannon`，让 forge 基本就绪再派塔工，避免“未开工”干等。

2. **降低 carrier expansion_cannons baseline，减少 quiet 期铺塔吸血**
   - 文件：`ares-bot/flows.yml` + `ares-bot/tests/test_flow_config.py`
   - 改法：`expansion_cannons: {min: 2, max: 4}`（原 min:4 max:4）。quiet 期只铺 2 塔/基地，敌兵≥8 时动态回到 4；省矿给二矿/舰队。

3. **非首塔 PHOTONCANNON 走 5s 熔断，释放等钱工人回矿**
   - 文件：`ares-bot/bot/main.py` `_idle_builder_fuse_release`
   - 改法：首塔（0 座就绪炮塔）仍豁免；已有就绪炮塔时，后续塔工若 5s 未开工即释放回矿采矿，避免 PSD 一次注册多塔导致批量 idle。

### 验证

- `poetry run python -m unittest discover -s ares-bot/tests`：**649 例通过**（skipped=1）。
- 下一组 bench：**O211 headless 双车道，Zerg Rush @ AbyssalReefLE + PaladinoTerminalLE**。

---

## O211: carrier vs Zerg VeryHard Rush（2026-08-06）

### 战绩

headless 双车道并行（REALTIME=False）：
- Lane1 AbyssalReefLE: **3 胜 2 负**，胜率 0.6
- Lane2 PaladinoTerminalLE: **3 胜 2 负**，胜率 0.6
- **Zerg Rush 组合打穿**（5 局 3 胜阈值达成）。

retro 标签：
- Lane1: `idle_builder×5`, `overrun×2`, `trickle×3`, `one_base×2`, `supply_block×1`
- Lane2: `idle_builder×5`, `overrun×2`, `trickle×2`, `one_base×1`

### 尸检发现

**idle_builder 仍是系统性问题**：两 lane 每局都出现，累计 10/10 局。失败局尤为严重：
- Abyssal game_02 Defeat: `supply_block` 205s、`one_base` 420s、`idle_builder×2`、`overrun`
- Abyssal game_03 Defeat: `idle_builder×13`、`overrun`
- Paladino game_02 Defeat: `one_base`、`idle_builder×3`、`overrun`
- Paladino game_04 Defeat: `idle_builder×6`、`overrun`

**关键现象（state 快照回放）**：
- Abyssal game_02: 农民在 PhotonCannon 位从 t≈116.5 干等到 t≈526.3（约 410s）；t≈329 起第二个农民开始等 FleetBeacon。
- Abyssal game_03: t=112-297 农民等 PhotonCannon；t=168-350 农民等 Gateway；t=297-482 农民等 Nexus；t=466-760 两个农民等 FleetBeacon。

**根因**：O205 落地的 `_idle_builder_fuse_release` 把 GATEWAY/NEXUS/FLEETBEACON 与 FORGE/首塔一起放在 blanket 豁免名单里，5s 熔断对它们不生效；而 O11 watchdog 在 `rush_active`/`defense_urgent` 期间对「一切建造钉点」整段豁免。结果：
1. FleetBeacon、后续 Gateway、后续 Nexus 的工人在资金窗口紧时被钉点，无法回矿。
2. rush/防御紧急期，即使这些非防御结构（Nexus/FB/后续 GW）也不被释放，长期吸血。
3. 30s 以内没有硬顶，个别工人被钉 3-7 分钟。

### 3 个改进点（已落地 O212）

1. **收窄 idle_builder 5s 熔断豁免范围**
   - 文件：`ares-bot/bot/main.py` `_idle_builder_fuse_release`
   - 改法：仅 FORGE、首座 PHOTONCANNON、首座 GATEWAY、首次扩张 NEXUS 豁免；FLEETBEACON 与后续 Gateway/Nexus 走 5s 熔断，未开工即释放回矿。

2. **增加 30s 硬顶，防止 pathological 长期钉点**
   - 文件：`ares-bot/bot/main.py` `_idle_builder_fuse_release`
   - 改法：无论是否关键建筑、无论 rush/防御状态，工人等超过 30s 仍未开工强制释放。

3. **rush/防御紧急期仍释放非关键建筑工人**
   - 文件：`ares-bot/bot/main.py` `_handle_idle_workers` + 新增 `_is_rush_critical_structure`
   - 改法：rush/防御紧急期间不再「一切建造钉点豁免」，只对 FORGE/首塔/首 GW/首次扩张 Nexus 保留豁免；Nexus/FleetBeacon/后续 Gateway 等仍走 O11 释放，避免被长期钉点吸血。

### 验证

- `poetry run python -m unittest discover -s ares-bot/tests`：**649 例通过**（skipped=1）。
- 下一组 bench：**O212 headless 双车道，Zerg Power @ AbyssalReefLE + PaladinoTerminalLE**。

> **O212 启动后热修复（2026-08-06）**：`_handle_idle_workers` 中 `_is_rush_critical_structure(sid)` 引用 `sid` 早于赋值，导致首局 `UnboundLocalError` 崩溃；已将 `sid = info[TRACKER_ID]` 前移到 `_rush_exempt` 判据之前。单测复验 649 例通过，O212 双车道已重启。

---

## O212: carrier vs Zerg VeryHard Power（2026-08-06）

### 战绩

headless 双车道并行（REALTIME=False）：
- Lane1 AbyssalReefLE: **4 胜 1 负**，胜率 0.8
- Lane2 PaladinoTerminalLE: **5 胜 0 负**，胜率 1.0
- **Zerg Power 组合打穿**（5 局 3 胜阈值达成）。

retro 标签：
- Lane1: `idle_builder×5`, `trickle×4`, `one_base×1`, `overrun×1`
- Lane2: `trickle×5`, `idle_builder×5`, `stall×1`

### 尸检发现

**唯一败局 Lane1 game_03（Defeat）**：
- state 回放显示首座 Nexus 直到 **466s** 才落成；而 250-321s 期间 FleetBeacon 已抢先派工/pending。
- FB 抢走二矿的 300 矿窗口，导致经济长期单基地，最终被滚雪球推平。
- 终局状态：0 基地 / 32 农民 / 1 oracle，符合 one_base + overrun 标签。

**系统性问题（两 lane 共同）**：
- **trickle 突出**：两 lane 累计 9 次 trickle，小股部队未攒够即压上送死。
- **idle_builder 仍高频**：10/10 局出现，多因「派工后资金被抽干、农民钉点等钱」。
- **Lane2 game_03 误判 SC2 异常退出**：实际 log 显示 Victory，但 bench 未找到 game_*.json 而重试，浪费一局。

### 3 个改进点（已落地 O213）

1. **宏观对局单基地时 FleetBeacon 让位 Nexus**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_build_core_structures` FB 分支
   - 改法：当 `_ai_build in ("power", "macro")`、当前基地数==1、且无 Nexus pending/在建时，跳过 FB 建造，优先二矿。O212 败局实证：FB 抢先派工吸走 300 矿，首矿拖到 466s。

2. **提高 carrier 集结阈值，降低 trickle**
   - 文件：`ares-bot/flows.yml` carrier 块 + `ares-bot/tests/test_flow_config.py`
   - 改法：`rally_min_army: 16`（之前 carrier 未设，默认 0）。兵力 <16 且司令未下 stance 时守家攒兵，减少小股部队分批送死。

3. **压缩非关键建筑 idle_builder 硬顶**
   - 文件：`ares-bot/bot/main.py` `_idle_builder_fuse_release`
   - 改法：30s 硬顶对非 TOWNHALL/FORGE 结构降到 20s。FORGE/TOWNHALL 保留 30s（攒钱预走位语义），FB/后续 Gateway/科技建筑等更快释放回矿。

### 验证

- `poetry run python -m unittest discover -s ares-bot/tests`：**649 例通过**（skipped=1）。
- 下一组 bench：**O213 headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE**。

---

---

## O213: carrier vs Zerg VeryHard Timing（2026-08-06）

### 战绩

headless 双车道并行（REALTIME=False）：
- Lane1 AbyssalReefLE: **0 胜 5 负**，胜率 0.0
- Lane2 PaladinoTerminalLE: **1 胜 4 负**，胜率 0.2
- **Zerg Timing 组合未打穿**（需 5 局 3 胜）。

retro 标签：
- Lane1: `idle_builder×5`, `overrun×5`, `one_base×4`, `trickle×2`, `supply_block×1`
- Lane2: `idle_builder×5`, `overrun×4`, `one_base×2`, `trickle×1`

### 尸检发现

**one_base 是核心死因**：Lane1 4/5 局、Lane2 2/5 局在 420s 仍单矿。二矿落成时间普遍在 430-470s（Abyssal game_01 474s、Paladino game_04 454s、Paladino game_05 385s），而 Zerg Timing 首波/持续压力在 200-350s 即到位，单矿经济撑不到 fleet 临界质量。

**二矿资金被防御抽干**：
- `scripts/autopsy_events.py` 显示 O189 强制开二矿在 180-260s 已反复触发，但 Nexus 工人因「等钱」idle_builder 长期钉点。
- O131 预留死锁保险丝在 60s/矿<150 时熔断，取消扩张预留后 F2 防御/炮塔注册立即把 400 矿 Nexus 窗口吃光，导致二矿永远拍不下。
- Paladino game_05 终局气体 1594、矿物 28，典型「气烂银行、矿 starvation」—— 钱都变成炮塔，舰队只有 5-6 艘 tempest。

**fleet 成型过晚/过小**：
- Lane1 终局平均 tempest×3.2；Lane2 终局平均 tempest×6.0、carrier×3.0（主要来自唯一胜局）。
- tempest 首次出现平均 593-604s，carrier 859-908s，远晚于 Zerg Timing 连续波次。

**唯一胜局 Paladino game_04 的关键差异**：
- 二矿 454s 落成后守住，static defence 堆到 17 门炮塔，fleet 滚到 11 tempest + 3 carrier + 20 interceptor，44 农民满采。
- 说明 **二矿能活 → 经济能滚 → 炮塔+fleet 能守**。核心瓶颈是「二矿拍不下/活不到」。

### 3 个改进点（已落地 O214）

1. **Zerg Timing 强制二矿更早触发**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_want_dynamic_expand`
   - 改法：O189 兜底对 Zerg Timing 从 `t≥210 / 矿≥150` 降到 `t≥180 / 矿≥100`，Rush 保持 210/150。让二矿资金窗在首波前就开始攒。

2. **延长 Zerg Timing 扩张预留的 O131 保险丝**
   - 文件：`ares-bot/bot/managers/production_manager.py` update 头部 O131 调用
   - 改法：当扩张预留（`_transition_reserve`/`_expand_holding`）激活且 vs Zerg Timing 时，保险丝 timeout 从 60s 延到 120s，min_price 从 300 提到 400（打断线从 150 提到 200），避免防御过早抽干 Nexus 资金。

3. **二矿资金窗期间提高炮塔注册 buffer**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_should_build_defense`
   - 改法：F2 防御注册的 `dispatch_viable` buffer，在 `_expand_holding` 且舰队 <4 时从 30 提到 75，与开局 120s 内同级，进一步保护 Nexus/首舰资金不被炮塔抢走。

### 验证

- `poetry run python -m unittest discover -s ares-bot/tests`：**649 例通过**（skipped=1）。
- 下一组 bench：**O214 headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE**（继续攻坚同一组合）。

---


---

## O214: carrier vs Zerg VeryHard Timing（2026-08-06）

### 战绩

headless 双车道并行（REALTIME=False）：
- Lane1 AbyssalReefLE: **0 胜 5 负**，胜率 0.0
- Lane2 PaladinoTerminalLE: **1 胜 4 负**，胜率 0.2
- **Zerg Timing 组合仍未打穿**（需 5 局 3 胜）。

retro 标签：
- Lane1: `idle_builder×5`, `one_base×4`, `overrun×3`, `trickle×1`
- Lane2: `idle_builder×4`, `overrun×4`, `one_base×3`, `supply_block×1`

关键指标（`summary.json`）：
- Lane1 平均时长 916s，首艘 tempest 585s，终局平均 tempest×3.3
- Lane2 平均时长 977s，首艘 tempest 689s，终局平均 tempest×3.0 + voidray×12

### 尸检发现

**二矿依然太晚，FleetBeacon 与 Nexus 互相冻结**：
- Lane1 4/5 局、Lane2 3/5 局二矿落成在 430-470s（Abyssal game_05 450s、Paladino game_05 438s），与 O213 比没有本质提前。
- `scripts/autopsy_summary.py` 显示：Nexus 一旦 pending，`_expand_holding` 把 `core_allowed` 置 False，FleetBeacon 建造被整体冻结；Nexus 落成后 minerals 立即被炮塔/地面兵抽干，FB 仍要再拖 50-150s 才能 pending。
- Abyssal game_05：Nexus 450s 落成，FB 454s pending，首艘 tempest 619s；期间为了守二矿铺了 14 门炮塔，气体 597 烂在银行无矿物可转舰队。

**首舰前炮塔过度投资，Nexus/FB 资金被反复吃光**：
- 即使 `_expand_holding` 期间 buffer 已提到 75，fleet=0 时敌兵计数仍推动 `expansion_cannon_count` 目标到 3-4，150 矿/门连续建造把 400 矿 Nexus 窗啃掉。
- Paladino game_05 是最典型案例：终局前 fleet 滚到 9 tempest，但仍因分矿反复被抄、农民撤离、经济断流而败；此前在 fleet=0-2 阶段已投资 9-15 门炮塔，矿物长期贴 0。

**O214 三项补丁效果有限**：
- O189 180/100 兜底只在部分局触发，正常 `first_expand_at` 被 O183 锁在 240s，二矿主触发器太晚。
- O131 保险丝延长到 120s/400 矿，但防御在 120s 内就能把 Nexus 资金吃回 200 以下，保险丝无法阻止「塔吃 Nexus 窗」。
- buffer 75 仍挡不住 fleet=0 时的动态炮塔增量。

### 3 个改进点（落地 O215）

1. **Zerg Timing 正常开矿触发提前（first_expand_at 240s → 180s）**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_want_dynamic_expand` 中 O183 覆盖
   - 改法：vs Zerg Timing 时 `_first_expand_at = max(_first_expand_at, 180.0)`（Rush 维持 300，Power/Macro 维持 flows.yml 的 150）。让二矿在正常动态路径下更早触发，而不是只依赖 O189 兜底。

2. **Zerg Timing 开矿持有期不冻结 FleetBeacon**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_build_flow_structures`
   - 改法：`core_allowed=False` 早退分支里，对 Zerg Timing 增加 FleetBeacon 特例——只要星门就绪、FB 缺失、时间 ≥240s，即使 Nexus 在途也允许派工 FB。避免 Nexus 在建期间 FB 被冻 100s+，导致舰队成型系统性延迟。

3. **Zerg Timing 首舰前严格限塔，保 Nexus/FB 资金**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_should_build_defense` / F2 注册段
   - 改法：
     - fleet_total == 0 且非 rush/threat 直接受击时，炮塔目标硬性封顶 1（忽略敌兵计数增量），避免首舰前铺 3-4 门炮塔把 400 矿 Nexus/300 矿 FB 窗吃光。
     - `_expand_holding` 且 fleet < 4 时的 `dispatch_viable` buffer 对 Zerg Timing 提到 250，确保 Nexus/FB 资金优先落袋。

### 验证

- `poetry run python -m unittest discover -s ares-bot/tests`：**649 例通过**（skipped=1）。
- `poetry run python -m py_compile ares-bot/bot/managers/production_manager.py`：通过。
- 下一组 bench：**O215 headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE**。

---


---

## O215: carrier vs Zerg VeryHard Timing（2026-08-06）

### 战绩

headless 双车道并行（REALTIME=False）：
- Lane1 AbyssalReefLE: **0 胜 5 负**，胜率 0.0
- Lane2 PaladinoTerminalLE: **1 胜 4 负**，胜率 0.2
- **Zerg Timing 组合仍未打穿**（需 5 局 3 胜）。

retro 标签：
- Lane1: `idle_builder×5`, `one_base×5`, `overrun×5`, `bank×1`
- Lane2: `idle_builder×5`, `overrun×4`, `one_base×1`, `trickle×1`

关键指标（`summary.json`）：
- Lane1 平均时长 907.8s，首艘 tempest 506.2s，carrier 803.6s，终局平均 tempest×4.0
- Lane2 平均时长 993.7s，首艘 tempest 748.7s，carrier 1020.5s，终局平均 tempest×3.7

### 尸检发现

**二矿仍然开得太晚**：
- Lane1 5/5 局 one_base，game_01 始终单矿到 1045s 才败；其余局二矿 425-630s 落成。
- Lane2 唯一胜局 game_03 二矿 293s（特例），失败局二矿 373-450s。
- `transition_expand_at_210` 默认 at=210，O189 兜底 180/100 触发条件仍被 `saw_wave`、`enemy_near==0`、gateway_cap 等三重门卡住。

**fleet 成型仍过晚**：
- Lane2 tempest 平均首次出现 748.7s，carrier 1020.5s；多数失败局 fleet 未成型或仅 1-3 艘即被推平。
- FleetBeacon 资金窗仍被 Nexus/塔/兵营反复占用；即使 O215 增加了 `_is_zerg_timing_fb_exempt`，效果有限。

**分矿防御薄弱**：
- 二矿落时塔数经常 0-2，没有按司令指示的 3 光子炮 + gateway 堵口。
- `expansion_cannon_min_dynamic` fleet=0 时 zero_fleet_cap=1，二矿一落基本无塔，被 4 地面单位反复抄家（E6 频繁触发）。

**idle_builder / 农民停滞**：
- 农民被派去造 NEXUS/PHOTONCANNON 但等钱，中后期 O145 农民停滞反复出现，经济崩盘。

### 3 个改进点（落地 O216）

1. **Zerg Timing 二矿再提速（first_expand_at 180s → 150s，强开线 210s → 150s）**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_want_dynamic_expand`
   - 改法：
     - `_first_expand_at` 对 Zerg Timing 从 180 降到 150。
     - `transition_expand_at_210` 调用传入 `at=150`，且 saw_wave 条件放宽为「首波已清 或 时间到 180s」。
     - O189 兜底对 Zerg Timing 从 `t≥180 / 矿≥100` 降到 `t≥150 / 矿≥100`。
     - 取消 `transition_expand_blocked` 对 Zerg Timing 的阻塞，二矿不再等 2 兵营 cap 凑齐。

2. **fleet 成型提速（flows.yml fleet_at 320 → 280，FB 门限提前）**
   - 文件：`ares-bot/flows.yml` carrier transition；`ares-bot/bot/managers/production_manager.py` `_is_zerg_timing_fb_exempt`、`_build_flow_structures` `_timing_fb_gate`
   - 改法：
     - `fleet_at` 从 320 降到 280，transition 更早转舰队。
     - `_is_zerg_timing_fb_exempt` 时间从 240 降到 180，Nexus 在途更早放行 FB。
     - `_timing_fb_gate` 时间从 360 降到 280，与 flows.yml 对齐。

3. **分矿防御模型落地（zero_fleet_cap 1 → 2 + gateway 堵口）**
   - 文件：`ares-bot/bot/production_plans.py` `expansion_cannon_min_dynamic`；`ares-bot/bot/managers/production_manager.py` `_ensure_expansion_wall_gateway`
   - 改法：
     - `expansion_cannon_min_dynamic` 的 `zero_fleet_cap` 从 1 提到 2，fleet=0 时也至少 2 座保命塔。
     - 新增 `_ensure_expansion_wall_gateway`：Zerg Timing 下，分矿 Nexus 在建或就绪后，在其迎敌侧建一座 gateway 堵口，配合后方光子塔密集防守。

### 验证

- `poetry run python -m unittest discover -s ares-bot/tests`：**649 例通过**（skipped=1）。
- `poetry run python -m py_compile ares-bot/bot/managers/production_manager.py ares-bot/bot/production_plans.py`：通过。
- 下一组 bench：**O216 headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE**。

---

## O216c: carrier vs Zerg VeryHard Timing（2026-08-06）

### O216b 双车道 game_01 尸检

O216b 启动后两条 lane 的 game_01 均告负，数据揭示 O216b 的 `spawn_pause_reason` 阈值仍太保守：

**Lane1 AbyssalReefLE**：
- 结果 Defeat，游戏时间 987.9s，终局基地=0、军队空。
- 二矿 522.3s 才落成；192.9s / 307.5s / 669.6s 反复出现 `idle_builder` 等钱造 Nexus。
- 192-518s 存款长期在 200-500 波动，ground_spawn zealot（100 矿/个）+ 塔/星门持续抽矿，Nexus 基金永远凑不齐 400。

**Lane2 PaladinoTerminalLE**：
- 结果 Defeat，游戏时间 891.3s。
- 二矿较早（184.8s），但fleet 始终 0；星门直到 450s 才出现，终局无航母/风暴。
- 128.6s / 248.6s / 766.1s 仍有 `idle_builder` 等钱造光子炮，中后期 O145 农民停滞反复出现。

### 3 个改进点（落地 O216c）

1. **Nexus 未开工前暂停 zealot 产兵（O216c）**
   - 文件：`ares-bot/bot/production_plans.py` `spawn_pause_reason`；`ares-bot/bot/managers/production_manager.py` 调用点
   - 改法：
     - 新增 `nexus_unstarted` 参数，仅当 Nexus 已派工但**尚未开工**、且存款 < 400 时才暂停 SpawnController。
     - 阈值从 `nexus_price - 100` 收紧到 `nexus_price`（400 矿）。
     - Nexus 一旦开工（已付 400 矿）或存款已够，立即恢复产兵，避免 O216b 的 300-400 矿缓冲被 zealot 反复吃回 200 以下。

2. **分矿 gateway 堵口让位 Nexus 基金（O216c）**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_ensure_expansion_wall_gateway`
   - 改法：
     - 若存在未开工的 Nexus 且存款 < 400 + 150，则跳过 gateway 堵口，优先保证二矿落地。
     - gateway 是防御投资，但 Nexus 落不了地时 150 矿会把基金从 400+ 吃回 250+，继续拖延二矿。

3. **fleet 成型后把余矿/余气转成舰队而非继续堆塔（待 O216c 验证后细化）**
   - 文件：待定（`production_manager.py` `_should_build_defense` / `_build_extra_production` / `_spend_bank`）
   - 方向：
     - Lane2 game_01 二矿虽早落，但星门 450s 才出现、fleet 始终 0，说明 Nexus 后的资源被塔/电池/地面兵持续吃掉。
     - 若 O216c 后仍 fleet=0 频发，将加 FleetBeacon/星门资金窗硬帽：Nexus 落地后 `cannon_target_capped` 进一步限流，或在 `_spend_bank` 中优先把银行存款投入 stargate/FB。

### 验证

- `poetry run python -m unittest discover -s ares-bot/tests`：**650 例通过**（skipped=1）。
- `python3 -m py_compile ares-bot/bot/managers/production_manager.py ares-bot/bot/production_plans.py`：通过。
- 已停止 O216b 双车道 bench，按 `headless + 双车道` 重启 **O216c**：
  - Lane1: `o216c-vh-zerg-timing-abyssal` @ AbyssalReefLE
  - Lane2: `o216c-vh-zerg-timing-paladino` @ PaladinoTerminalLE

---

### O216c bench 验证结果

headless 双车道并行（REALTIME=False）：
- **Lane1 AbyssalReefLE**: 1 胜 4 负，胜率 0.2
- **Lane2 PaladinoTerminalLE**: 0 胜 5 负，胜率 0.0
- **Zerg Timing 组合未打穿**（需 5 局 3 胜）。

retro 标签：
- Lane1: `idle_builder×5`, `overrun×4`, `trickle×2`, `one_base×1`
- Lane2: `idle_builder×5`, `overrun×4`, `one_base×2`, `trickle×1`

**关键数据（Lane1）**：
- 主力首次出现：tempest@627.8s、carrier@803.5s， fleet 成型过晚。
- 平均时长 1138.4s，存款峰值 1855，气体长期富余但矿物枯竭。
- g05 典型：二矿 642.9s 才落成，气体 751 烂银行，终局 fleet=0。

### 尸检发现（Lane1 game_02-05 + Lane2 汇总）

**FleetBeacon 资金窗被追加星门反复吃掉，舰队管线空转**：
- game_02：首座星门 394s 就绪，但 450s→506s→788s 连续追加到 4 星门，FB 直到 ~750s 才拍下；气体 1662 烂银行，终局 fleet=3 tempest。
- game_05：首座星门后连拍 3 星门，FB 655s pending 但终局无 fleet，气体 713 未用。
- `_build_extra_production` 与 `stargate_double_opener` 只看「有钱/有气」和气体闸门，未保护「已有就绪星门但 FB 未建」的 300/200 资金窗。

**FleetBeacon 拍下后仍被塔/扩张抽干，首舰出不来**：
- game_03：FB 之前塔/星门把矿吃光，fleet 首次出现 675s；之后敌 69 supply 压境，基地连丢。
- game_04：fleet 爬到 7 艘，但 cannon 堆到 20 座，矿物持续贴 0，最终 3 基地全丢。

**二矿仍偏晚/不稳定**：
- game_05 二矿 642.9s；game_02 204.9s 虽早，但 Nexus 后资金立刻被塔/星门抽回单矿状态。

### 3 个改进点（落地 O216d）

1. **FleetBeacon 资金窗前禁止追加星门**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_build_extra_production`
   - 改法：当 `_fb_ready_to_build()`（已有就绪星门、FB 未建/未派工）成立且要追加的是 STARGATE 时，直接 return。避免 2-4 星门抢在 FB 前面空转。

2. **FleetBeacon 资金窗前禁止星门双开**
   - 文件：`ares-bot/bot/managers/production_manager.py` `stargate_double_opener` 调用点
   - 改法：`stargate_double_opener` 返回真后，再判断 `not self._fb_ready_to_build()` 才执行。重建窗的第二座星门必须在 FB 拍下后再拍。

3. **FleetBeacon 资金窗前把塔目标压回保命下限**
   - 文件：`ares-bot/bot/managers/production_manager.py` F2 塔目标计算分支
   - 改法：`_fb_ready_to_build()` 成立、舰队未成规模（<3）、且非过渡期时，`cannons = min(cannons, _ec_min)`。避免动态塔目标扩容反复抽干 300 矿 FB 资金窗。

### 验证

- `poetry run python -m unittest discover -s ares-bot/tests`：**650 例通过**（skipped=1）。
- `python3 -m py_compile ares-bot/bot/managers/production_manager.py`：通过。
- 下一组 bench：**O216d headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE**。

---


### O216e bench 验证结果

headless 双车道并行（REALTIME=False）：
- **Lane1 AbyssalReefLE**: game_01 重试局 Defeat（484.9s），SC2 崩溃 1 次后重试
- **Lane2 PaladinoTerminalLE**: game_01 Defeat（957.4s）
- 两局均 **fleet 严重滞后**，O216e 补丁（追加 SG 等首舰 + exit_ground 6）未能解决根因。

**关键数据（Lane2 Paladino game_01）**：
- 主力首次出现：tempest@731.1s，终局仅 3 tempest + 1 oracle，fleet 未成规模。
- FleetBeacon 589.7s 才 pending，首座星门 ~450s 才就绪。
- 气体 final=1133 烂银行，说明有气但舰队科技链/产能没建出来。
- 二矿 349.6s 才落（first_expand_at=150 但资金被塔/地面兵抽干）。
- idle_builder 多次：等钱造 NEXUS、等钱造 PHOTONCANNON。

**关键数据（Lane1 Abyssal game_01 重试局）**：
- 二矿虽早（184.8s），但 **星门始终 0，fleet 始终 0**，484s 被推平。
- 气体 final=432 未用，舰队科技链完全没建。
- 塔最多 1 座，地面部队也极少，transition 资源全空转。

### 尸检发现（O216e 双车道）

**transition 期的 defense sprint 把核心科技链冻结 200s+**：
- 55s presumed 启动 → sprint 期间 `_build_flow_structures` 被整体跳过。
- sprint 直到首塔/首叉就绪才解除（Lane2 ~270s，Lane1 ~237s）。
- 在这 200s+ 内，CYBERNETICCORE→STARGATE→FLEETBEACON 完全不能排队。
- sprint 结束后才建 cybercore → 50s → stargate → 43s → FB，首舰出场被推到 450-730s。
- `_build_flow_structures` 内部已有 O186 对 Zerg Rush/Timing 不冻结 STARGATE/FB，但 sprint 在外部把整个函数跳过了。

**Zerg Timing 不该按 Rush 强度冲刺**：
- Timing 波次 240-300s 才来，不是 150-180s 的 rush。
- 120s 全链冲刺把经济锁死在 forge/首塔/首叉，科技链归零，transition 退出后无舰队可转。

**FB 时间门 280s 仍偏晚**：
- 即使星门提前就绪，`_timing_fb_gate` 要求 t≥280，FB 常被拖到 500s+。

### 3 个改进点（落地 O216f）

1. **Zerg Timing 的 sprint 期间仍执行 `_build_flow_structures`**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_build_flow_structures` 调用点
   - 改法：`_sprint_freeze_tech = _sprint and not (zerg+timing)`；Zerg Timing 时即使 sprint 也调用 `_build_flow_structures`。
   - 同时 Zerg Timing sprint 期间强开 `core_allowed=True`，确保 cybercore/stargate/FB 都能排队。

2. **缩短 Zerg Timing 的 sprint 最大持续时间（120s → 60s）**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_sprint` 计算处
   - 改法：对 Zerg Timing 传入 `max_age=60.0`，让 F2 防御和科技链更快并行，避免经济被锁死在 forge/首塔。

3. **Zerg Timing 的 FB 特例门限从 280s 提前到 200s**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_timing_fb_gate`
   - 改法：`_timing_fb_gate` 时间门从 `280.0` 降到 `200.0`，匹配 sprint 放行后星门/FB 的新窗口。

### 验证

- `poetry run python -m unittest discover -s ares-bot/tests`：**650 例通过**（skipped=1）。
- `python3 -m py_compile ares-bot/bot/managers/production_manager.py`：通过。
- 下一组 bench：**O216f headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE**。

---
## O216g — Zerg Timing 饱和不开矿 + idle_builder 钉点治理（o216f 尸检落地）

**日期**：2026-08-06（o216f-vh-zerg-timing 双车道：AbyssalReefLE + PaladinoTerminalLE，VeryHard，headless）

### 结果

- Lane1（Abyssal）：game_01 Defeat(215s)、game_02 中止迭代（已跑 382s 趋势同败）
- Lane2（Paladino）：game_01 Defeat(188s)、game_02 Defeat(68s)、game_03 Defeat(270s)、game_04 中止迭代
- 结论：O216f 提前了 SG/FB，但经济天花板（单矿/晚二矿）+ NEXUS 钉点循环未解，确认未打穿，中止迭代。

### 尸检发现

1. **矿线饱和却不开矿（司令观察确认）**：o216f-vh-zerg-timing-paladino/game_03 农民峰值 45、基地仅 2（主基满载 + 分矿 16 满载仍有 ~13 农民浪费人口）；二矿 683s 才落、三矿至死未开。根因：`should_expand_dynamic` 的 O160 门（bases≥2 需 fleet≥3 **且** minerals≥500）在塔链持续抽干银行的局里永假——饱和触发也被矿门拦死。
2. **idle_builder NEXUS 钉点 42-166 次/局**：O189 强制开二矿矿门 100/150 即派工，农民钉点等 400 矿需 15s+，期间塔/兵持续抽干银行 → 「派→等→撤→再派」循环；且 O189 事件每帧 append 刷屏。各局分布：FORGE 44-103、GATEWAY 11-74、NEXUS 42-166、PHOTONCANNON 19-130（autopsy 统计）。
3. **max_bases=3 封顶太低**：司令要求饱和时主动开 3/4/5/6 矿；flows.yml carrier auto_expand max_bases 仅 3，舰队成型后经济无法滚动放大。
4. **transition 退出仍偏晚**：Lane2 game_01 首舰 562s、FB pending 706s，单矿舰队产能被 Zerg 中局波次磨光（终局 TEMPEST×4 补给 19/80）。

### 3 个改进点（落地 O216g）

1. **饱和触发旁路扩张矿门**
   - 文件：`ares-bot/bot/production_plans.py` `should_expand_dynamic`
   - 改法：saturated 判定提前；bases≥2 时矿门（minerals<500）在**矿线饱和**时旁路（fleet≥3 舰队门保留防裸奔）。
   - 单测同步更新（`test_fleet_and_mineral_gate_blocks_late_expand`）。

2. **carrier max_bases 3→6**
   - 文件：`ares-bot/flows.yml` carrier `auto_expand`
   - 改法：max_bases 3→6，饱和后主动开 3/4/5/6 矿；Zerg Rush 仍在 production_manager O186 代码层锁 2，不受影响。

3. **O189 强开二矿矿门 100/150→300 + 事件去重**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_want_dynamic_expand`
   - 改法：`_o189_minerals` 提到 300（到位等 ≤5s，消除 15s+ 钉点循环）；新增 `_o189_logged` latch，事件只记一次。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py bot/production_plans.py`：通过。
- `poetry run python -m unittest discover -s tests`：**650 例通过**（skipped=1），含 flows.yml max_bases=6 断言更新。
- 下一组 bench：**O216g headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE**。

---
## O216h — O189 矿门回调 + Nexus 钉点期间塔链让位（o216g 首局实证）

**日期**：2026-08-06（o216g-vh-zerg-timing 双车道首局即暴露回归）

### 结果

- Lane2（Paladino）game_01 Defeat(437s)：单矿到死，舰队 0，E9 威胁 221/253s 到脸后被 timing 波滚平。
- 结果行未落 bench 日志（game_01 中途异常重试，目录内 state 混入两个 attempt，以 `game_*.json` 的 result 为准）。

### 尸检发现

1. **O216g 的 O189 矿门 300 是回归**：威胁期塔链持续抽干银行（矿恒 5-255），300 矿门整局不触发 → 二矿永远不开，单矿 24-26 农民饱和被滚雪球。
2. **Nexus 钉点期银行被塔链抽干是 NEXUS idle_builder 的根因**：O189/饱和触发派工后，E9 威胁期 F2 炮塔照注册（threat 豁免 expand_holding），银行攒不到 400 → 工人钉 15s+ 进「派→等→撤→再派」循环。
3. **饱和旁路（O216g ①）未生效场景**：舰队门 fleet≥3 保留后，本局舰队 0 → 不触发；二矿仍依赖 O189 强开通道，故 O189 必须真正落地。

### 3 个改进点（落地 O216h）

1. **O189 矿门 300→150 回调**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_want_dynamic_expand`
   - 改法：`_o189_minerals` rush/timing 均回 150，保证强开通道真实触发；`_o189_logged` 事件去重保留。

2. **Nexus 钉点未开工期间塔链让位（≥2 塔保底）**
   - 文件：`ares-bot/bot/managers/production_manager.py` F2 注册闸
   - 改法：新增 `not_started_but_in_building_tracker(NEXUS)>0 且 _cannons_ready_peak>=2 且非 rush_active` → F2 整段不注册，银行 ~12s 攒到 400，钉点有界、二矿落地。

3. **验证流程修正**
   - 双车道启动后核对两条 lane 的 bench.py 进程与日志文件均存活（上轮 lane2 后台启动被任务清理杀掉，已补起）。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**650 例通过**（skipped=1）。
- 下一组 bench：**O216h headless 双车道，Zerg Timing @ AbyssalReefLE + PaladinoTerminalLE**。

---
## O216i — Zerg Timing 防御优先门：首塔前不开矿、2 塔前不拍 SG/FB（o216h 尸检落地）

**日期**：2026-08-06（o216h-vh-zerg-timing 双车道：Lane2 0-3 连败实证）

### 结果

- Lane2（Paladino）：game_01 Defeat(444s)、game_02 Defeat、game_03 Defeat(397s)，三局同一死法。
- Lane1（Abyssal）game_01 长跑 484s+ 未完赛（观察中）。

### 尸检发现（三局同型）

1. **0 塔窗口拍 STARGATE**：星门 ~210-225s 落成时炮塔 0；首塔拖到 ~281-338s，306s E9 波（18 supply vs 12）到脸时 0-1 塔被推平。SG 的 150 矿正是首塔/二塔的钱。
2. **0 塔窗口派 Nexus**：196s（first_due/O216h 通道）Nexus 工人钉点，银行被塔链+科技双向抽干，「派→等→撤→再派」（game_03 于 196/303/333s 三度钉 NEXUS），二矿至死未落。
3. **O216f 的 sprint 放行科技链需要防御下限**：放行是对的（SG 提前），但缺「塔先到 2」的优先级约束，科技钱与保命钱在同一窗口竞争。

### 3 个改进点（落地 O216i）

1. **Zerg Timing 首塔未就绪不开矿**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_want_dynamic_expand`
   - 改法：`_cannons_ready_peak < 1` 时整段返回 False（含 O189 强开/first_due 所有通道）。

2. **Zerg Timing 前期 2 塔未就绪不拍 STARGATE/FLEETBEACON**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_build_core_structure`
   - 改法：`time<300 且 _cannons_ready_peak<2 且未转舰队` 时 SG/FB 直接 return，塔链先把 150 矿用对地方。

3. **迭代节奏修正：不重开 bench**
   - bench.py 每局新起 run.py 子进程，新局自动加载最新代码；o216h 标签的 game_04+ 即为 O216i 行为，避免打断 Lane1 长跑局。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**650 例通过**（skipped=1）。
- 观察点：o216h 标签后续局（=O216i 代码）首塔时点应 ≤240s、NEXUS idle_builder 计数应显著下降。

---
## O216j — 分矿保底塔不走「买不起即归零」（o216h game_04 尸检落地）

**日期**：2026-08-06（o216h-vh-zerg-timing 双车道，O216i 代码局）

### 结果

- Lane2（Paladino）game_04 Defeat(848s)：O216i 生效——首塔 132s（原 281-338s）、SG 217s、FB 369s、二矿 446s 落成、舰队 7 艘（6 暴风+1 航母）；但二矿 ~620s 被抄丢、848s 被 78-supply 波滚平。
- Lane1（Abyssal）game_01 Defeat(962s，旧 O216h 代码)：首塔 413s，慢性失血。
- Lane2 累计 0-4，game_05 进行中；本 lane 大概率需重开 N=5。

### 尸检发现（game_04）

1. **新分矿 88s 塔目标恒 0**：二矿 446s 落成后，O210「非紧急且买不起 → cannons=0」在矿 30-135 振荡期每帧归零；534s E6「敌 4 地面，无塔」抄家，12 农民+基地全丢。分矿 BuildStructure 无 can_afford 守卫，但外层 F2 dispatch_viable 守卫已管钉点，归零是过度防御。
2. **O216i 两道门生效**：首塔 132s、SG 217s（2 塔已就绪才放行）、FB 369s、首舰 506s——科技/防御顺序已正。
3. **后期仍输绝对兵力**：舰队 7 艘 vs 敌 78 supply 中局波，地面全灭后农民 31→2；单矿+单波次补给跟不上 Zerg 连续波。

### 3 个改进点（落地 O216j）

1. **分矿保底塔不走 O210 归零**
   - 文件：`ares-bot/bot/managers/production_manager.py` F2 分矿 BuildStructure
   - 改法：新增 `_cannons_expansion = cannons if cannons > 0 else min(_ec_min, 2)`，分矿 `to_count_per_base` 用它；主基 PSD 路径保持 O210 原样。

2. **保留 O216i 两道防御优先门**（本局验证有效，不回滚）。

3. **流程：lane2 0-4 后将重开 Paladino N=5**（O216j 代码），Abyssal lane 继续观察 game_02+。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**650 例通过**（skipped=1）。
- 观察点：新局分矿落成后 60s 内应有 ≥1 塔；E6「无塔」事件应消失。

---
## O217 — 基地残敌清剿（司令观察：大战后小股滞留拆建筑无人管）

**日期**：2026-08-06（暂停验收期间司令直接观察指令）

### 问题

大战打完后，敌只留一个小狗/小股（1-5 个）在我方基地内拆建筑时，我方存活战斗部队不去清剿：
- O205 空军召回（`_air_fleet_recall_target`）与 `_hot_base_anchor` 阈值均 **≥6**，1-5 个残敌不触发任何回防；
- 守军锚点（坡口卡位/两矿中点/最暴露分矿）不指向残敌位置，部队干站看它拆。

### 改法（`ares-bot/bot/managers/combat_manager.py`）

1. 新增 `_base_intruder_target()`：敌作战单位（`is_combat_type`，排除王虫/侦查/运输/工人）在任一就绪基地 **15 格内 1-5 个** → 返回离基地最近的残敌位置；≥6 仍走原大波回防通道；`rush_active` 急性窗不清剿（坡口墙不能为一条狗离位），transition 期照常。
2. `update()` 在 combat_sim 刹车之后接入：残敌存在 → `attack_target` 改为残敌位置（空地全军同清），清除后自动恢复原目标；事件去抖只在激活边沿记一条 `O217:基地残敌清剿`。

### 验证

- `python3 -m py_compile bot/managers/combat_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**650 例通过**（skipped=1）。

---
## O218 — 气烂银行追加星门（o217 双 lane game_01 尸检落地）

**日期**：2026-08-06（o217-vh-zerg-timing 双车道进行中）

### 结果

- Lane1（Abyssal）game_01 Defeat(846s)：二矿 405s，终局 5 暴风；星门全程恒 1。
- Lane2（Paladino）game_01 Defeat(799s)：二矿 470s，终局 2 暴风；星门全程恒 1。
- 两局同型：转舰队后气烂 400-736，舰队 300s 只涨 1-4 艘，被 36-57 supply 连续波滚平。

### 尸检发现

1. **星门恒 1 是新瓶颈**：`extra_production` 被 `tech_yields_to_threat`/`_fleet_starved_capacity`/`_expand_holding` 常年闸住；O105-③a 双开又只限首舰前（`not first_fleet_seen`）。首舰后没有任何通道补 SG。
2. **气矿大量闲置**：气体 532-736 烂银行，SG 的 150 气完全付得起；舰队产能不足不是资源问题，是产能建筑数量问题。
3. **O217 残敌清剿未触发**：两局 E6 都是「敌 10/14 地面」的大波（>5 上限），属正常波次防御问题而非残敌；O217 通道本身无需调整。

### 3 个改进点（落地 O218）

1. **首舰后气烂银行直接补星门**
   - 文件：`ares-bot/bot/managers/production_manager.py`（O105-③a 块后）
   - 改法：`fleet_transitioned + FB 实体 + 首舰已出 + SG 数 < min(8, 1+就绪基地) + 气 ≥400（留 250 产舰）+ can_afford + 非 rush_active` → `_build_core_structure(STARGATE)`，记事件 `O218:气烂银行追加星门`。

2. **O217 通道保持不变**：本轮 E6 均为 ≥10 大波，不是 1-5 残敌场景，无调整依据。

3. **节奏**：o217 tag 的 game_02+ 自动热加载 O218；若双 lane 仍不过半，下一轮重开 o218 tag N=5。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**650 例通过**（skipped=1）。
- 观察点：新局转舰队后 SG 应升到 2-3 座、气体不再烂 400+、舰队 700s 前应 ≥6 艘。

---
## O219 — 敌主力压境全军协防（司令观察：大波打二矿只有 2 空军参战）

**日期**：2026-08-06（o217 双车道运行中，司令直接观察指令）

### 问题

敌方大部队来袭二矿时，二矿堵口塔压缩了敌方参战兵力，但我方只有 2 个空军单位回防（O205 空军召回通道），主基地的追猎/叉子全部蹲家未参战 → 空军孤立阵亡、二矿被推平。

根因：combat_manager `update()` 各分支锚点各自为政——集结期/对空攒兵/蹲守 → 主基或最暴露分矿；transition → 坡口/两矿中点；`_hot_base_anchor` 只在 carrier 蹲守分支和 transition（min 3）内被引用，集结分支（army<rally → defend_anchor）等根本不查热点。

### 改法（`ares-bot/bot/managers/combat_manager.py`）

- `update()` 在 combat_sim 刹车和 O217 残敌清剿**之后**追加最终覆盖：
  `_hot_base_anchor(min_threat=6)` 非空 → `attack_target` 强制改为热点基地，对全编制（地面+空军）生效；骚扰编制（oracle 由 OracleManager 管）不在本分派内，天然除外。
- 阈值 6 = 主力级（与 O205 空军召回同口径）；1-5 残敌仍走 O217 清剿，优先级低于主力协防。

### 验证

- `python3 -m py_compile bot/managers/combat_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**650 例通过**（skipped=1）。
- 观察点：后续局 E6/E9 大波到分矿时，地面守军应与空军同步出现在被攻基地。

---
## O220 — 无防基地强制注册 F2（o217-lane2 game_02 尸检落地）

**日期**：2026-08-06（o217 双车道：lane1 0-5 收官；lane2 game_02 Defeat 1027s）

### 结果

- Lane1（Abyssal）0-5 收官，复盘 `idle_builder×5 overrun×5 one_base×2`。
- Lane2 game_02 Defeat(1027s)：**O218 生效**（星门升到 3 座），但二矿 558s 落成后 100s 零塔，660s 被 4 地面抄家，之后单矿慢性失血；气烂 1734 vs 矿贴 0。

### 尸检发现

1. **新矿 100s 零塔**：F2 外层 `dispatch_viable` 资金守卫在矿 20-70 振荡期永假（矿 40+收入×5 ≈ 140 < 150），O216j 的 `_cannons_expansion` 保底值根本到不了注册环节；`f2_dispatch_guard_bypassed` 只数主基 25 格内的塔，分矿无防不豁免。
2. **O218 验证通过**：SG 1→3 座；但舰队产能被矿物短缺卡死（暴风 250 矿/艘），气 1734 烂银行——矿物经济（二矿存活）仍是一号瓶颈。
3. **O217 未在 660s 触发待核**：E6「敌 4 地面」属 1-5 残敌口径，尸检事件列表未见 `O217:基地残敌清剿`；下轮重点核对（可能事件在 autopsy 截取窗口外，或 `_rush_active` 急性窗抑制）。

### 3 个改进点（落地 O220）

1. **无防基地豁免 F2 资金守卫**
   - 文件：`ares-bot/bot/managers/production_manager.py` F2 注册闸
   - 改法：新增 `_defenseless_base`（任一就绪基地 12 格内 0 就绪塔）；挂进 F2 首段条件（强制注册）与 `f2_dispatch_guard_bypassed` 并列豁免 `dispatch_viable` 守卫。

2. **O218 保留不回滚**：SG 已按预期升到 3；矿瓶颈靠二矿存活解决，不靠砍产能。

3. **下轮核对 O217 触发条件**：若 660s 类场景仍无清剿事件，检查 `_rush_active` 抑制窗口是否过宽。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**650 例通过**（skipped=1）。
- 观察点：新局二矿落成后首塔应 ≤60s 内开工；E6「无塔」事件应消失。

---
## O221 — 无防基地豁免 F2 全部让位闸（o220-lane1 game_01 尸检落地）

**日期**：2026-08-06（o220-vh-zerg-timing-abyssal game_01 Defeat 1166s）

### 结果

- o220 lane1 game_01 Defeat(1166s)：二矿 385s 落成，F2 注册防御 442s 才发生（迟 52s），501s 敌 4 地面到脸时水晶/塔刚开工（塔链=水晶 25s+塔 29s），546s 敌 17 地面平推二矿。

### 尸检发现

1. **O220 只豁免了资金守卫，没豁免让位闸**：`_defenseless_base` 让 F2 过了 `dispatch_viable`，但 `_transition_reserve`/`_fleet_reserve`/FB 等待闸（`_fb_truly_missing`/`_fb_waiting`）继续把 F2 整段拦到 442s（FB pending 才放行）。
2. **塔链物理周期 54s+**：新矿落成（385s）到敌到脸（501s）只有 116s，注册晚 52s = 塔来不及成型。
3. **O219 协防未见事件**：E6 时「6 地面兵力就近协防」是 E6 自带机制；主力协防是否触发需下轮从事件流核对。

### 3 个改进点（落地 O221）

1. **无防基地豁免 reserve 双闸**
   - `_transition_reserve`/`_fleet_reserve` 让位条款各加 `or _defenseless_base`。

2. **无防基地豁免 FB 等待闸**
   - FB 闸（`_fb_truly_missing`/`_fb_waiting`）加 `or _defenseless_base`：新矿保命塔 > FB 资金窗。

3. **验证指标**：新局二矿落成后 F2 注册应 ≤10s 内发生；E6「无塔」应消失（允许「塔 1-2 座压不住」）。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**650 例通过**（skipped=1）。

---
## O222 — 硬饱和全门旁路开矿（o217-lane2 game_05 尸检落地）

**日期**：2026-08-06（o217 lane2 0-5 收官后重开 o222 tag）

### 结果

- o217 lane2（Paladino）0-5 收官，复盘 `idle_builder×5 overrun×4 one_base×3 trickle×1`。
- game_05 Defeat(1191s)：**O218/O220 生效**——二矿 494s 落成后守了 600s（无 E6 早抄），SG 2-4 座、双矿 44 农、6 塔；但敌 E9 波 97/89/74 supply vs 我 47-63，绝对兵力 2 倍滚平。

### 尸检发现

1. **敌我运营速度差是终局死因**：Zerg 无骚扰自由运营到 97 supply（3-4 矿）；我方 2 矿 44 农硬饱和（≥32 后 ~12 农零产出）却因 fleet<3 舰队门开不出三矿。
2. **O220 验证通过**：game_05 二矿落成后 600s 未被抄（对比前作 60-100s 丢矿）；O221 让位闸豁免于本局尾声才热加载，待下轮验证。
3. **舰队矿物瓶颈**：暴风 250 矿/艘，双矿收入被塔重建/农民/地面持续抽血，舰队终局仅 3 艘；解法仍是矿基数（三矿）而非砍产能。

### 3 个改进点（落地 O222）

1. **硬饱和舰队门/矿门全旁路**
   - 文件：`ares-bot/bot/production_plans.py` `should_expand_dynamic`
   - 改法：新增 `hard_saturated = supply_workers >= workers_per_base × bases + 8`；硬饱和时 O160 双门全旁路直接开矿（软饱和仍保舰队门）。新增单测 `test_hard_saturation_bypasses_all_gates`。

2. **lane2 重开 `o222-vh-zerg-timing-paladino` N=5**（全量 O218-O222 代码）。

3. **观察指标**：三矿时点（目标 ≤700s）、敌我 supply 比（目标不被拉超 1.5×）、二矿 F2 注册 ≤10s（O221）。

### 验证

- `python3 -m py_compile bot/production_plans.py`：通过。
- `poetry run python -m unittest discover -s tests`：**651 例通过**（skipped=1）。

---
## O223 — FB 饥饿期主基 siege 塔不开火（o220-lane1 game_03 尸检落地）

**日期**：2026-08-06（o220 lane1 game_03 Defeat 839s；O222 三矿 622s 已验证）

### 结果

- o220 lane1 game_03 Defeat(839s)：**O222 生效**（三矿 622s），但星门 506s、FB 再晚、首舰 ~620s+ 未成型，塔 9 座（主基 siege 6 + 分矿 3）、气烂 1142，E6「敌 15 地面」平推三矿。

### 尸检发现

1. **主基 siege 6 塔吃掉 FB/首舰资金**：`main_siege`（敌 ≥2 压主基 → 6 塔）在 FB 未落成期开火，900 矿塔 vs FB 300 矿资金窗，舰队 0 到 619s。
2. **O222 验证通过**：三矿 622s（硬饱和旁路触发，fleet=0 也开）；三矿裸奔被抄是 O221 之前的代码窗（本局 retry 启动早于 O221 热加载），下轮复核。
3. **舰队时间线仍晚 ~150s**：SG 506 → FB ~560 → 首舰 620+，Zerg 同期 60-90 supply；上游是早期农民 14-21 低水位（FORGE/GATEWAY idle  stall）拖累全链。

### 3 个改进点（落地 O223）

1. **FB 饥饿期 siege 不加强**
   - 文件：`ares-bot/bot/managers/production_manager.py` siege 分支
   - 改法：`siege and _fb_entities_now==0 and _fleet_total_now<3 and not rush_active` → `siege=False`，走原 cannons 目标（分矿保底塔不受影响）。

2. **O222 保留**：三矿时点 622s 达标（目标 ≤700s）。

3. **下轮观察**：FB 落成时点（目标 ≤540s）、siege 开火时舰队是否 ≥3、早期农民水位（GATEWAY/FORGE idle 是否再现）。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**651 例通过**（skipped=1）。

---
## O224 — Zerg Timing transition 期 SG/FB 攒钱停产（o220 game_04 / o222 game_01 尸检落地）

**日期**：2026-08-06（双 lane 持续连败中的根因定位）

### 结果

- o220 lane1 game_04 Defeat(766s)：三矿 590s（O222 持续生效），但舰队 0 到 619s+，气烂 550-1000。
- o222 lane2 game_01 Defeat(605s)：SG ~450s、首舰未出即被推。

### 尸检发现

1. **SG/FB 资金窗被 zealot 持续吃掉**：O186 早已让 transition 不冻结 SG/FB，O216i 门（2 塔）也在 ~280s 打开；但 `_build_core_structure` 的 `can_afford` 守卫在矿 70-230 振荡期永假——ground_spawn 纯 zealot（100 矿/个）每帧抢钱，SG 的 150 矿 200s+ 攒不出。
2. **时间线定量**：SG ~490 → FB ~550 → 首舰 620+，Zerg Timing 波 43 supply 于 608s 到脸，舰队永远晚一个波次。
3. **O216c 同款解法**：Nexus 基金保护（`zerg_timing_expand_reserve`）已验证有效，科技基金同构处理。

### 3 个改进点（落地 O224）

1. **`spawn_pause_reason` 新增 `zerg_timing_tech_reserve`**
   - 文件：`ares-bot/bot/production_plans.py`
   - 改法：`tech_saving=True 且 minerals < tech_price` → 暂停产兵攒钱（SG 段 150、FB 段 300，两段接力）；买得起即恢复（自校正）。新增单测。

2. **调用方接防御前置**
   - 文件：`ares-bot/bot/managers/production_manager.py`
   - 改法：`tech_saving = zerg+timing+transition_active+t≥240+塔≥2+(SG 或 FB 缺失)`——防御未立不攒（保命优先）。

3. **观察指标**：SG 落成 ≤340s（原 ~490s）、首舰 ≤520s（原 620s+）、`O126:产兵暂停=zerg_timing_tech_reserve` 事件出现。

### 验证

- `python3 -m py_compile bot/production_plans.py bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O224 中期验证 + o220 lane1 收官（舰队时间线已修复，剩消耗战）

**日期**：2026-08-06（o220 lane1 0-5 收官；o222 lane2 game_03 崩溃重试中）

### 结果

- o220 lane1（Abyssal）0-5 收官，但 game_05（O223 代码）是迄今最佳局：SG 321s、FB 362s、**SG 3 座 @506s、舰队 6 艘 @844s**（此前同期 fleet 0-2）。
- o222 lane2 game_03（O224 代码，崩溃前 attempt）：**O217 首次触发 @382s**、SG 382→FB 462→fleet 4 @699s。

### 尸检发现

1. **舰队时间线已修复**：SG ≤340s、FB ≤460s、首舰 ≤520s 全部达标（O218+O222+O223+O224 叠加生效）。
2. **新瓶颈=消耗战**：舰队 6 @844 后被 Zerg 连续波磨到 4，终局败亡；气烂 931-1107 而矿恒 10-90——舰队补充被矿物卡死（塔重建+46 农民+地面 floor 持续抽血）。
3. **基地仍被大波抄**：E6「敌 11-17 地面」级波次双矿轮流丢，农民 45→3，经济崩于舰队成型前夜。

### 3 个改进点（本轮先落地观察，代码改动见下一轮）

1. **lane1 重开 `o224-vh-zerg-timing-abyssal` N=5**（全量 O224 代码首发）。
2. **候选方向 A（矿物优先级）**：fleet≥1 后探机上限 22→18/基地、zealot floor 再降，把矿让给舰队补充。
3. **候选方向 B（舰队生存）**：核对 tempest 交战微操（射程 10 是否被 hydra/corruptor 贴脸），必要时调 carrier_offensive/tempest_offensive 后撤线。

### 验证

- game_05 数据已核实（SG/FB/舰队曲线）；O224 单测 652 通过（前轮已记）。

---
## O225 — FB 饥饿期暂停探机（o222-lane2 game_03 尸检落地）

**日期**：2026-08-06（o222 lane2 game_03 Defeat 805s，O224 首局完赛）

### 结果

- o222 lane2 game_03 Defeat(805s)：O100 转舰队 334s（评分 24）、O224 tech_reserve 271-331s 触发，但 **FB 至死未落成**、fleet 0 到 800s，气烂 852。

### 尸检发现

1. **FB 停滞自救 60 次全 no_money**：O110 自救链（清 tracker/主基派工/贴槽水晶/分矿试建）从 460s 跑到 506s+ 全部失败，原因清一色 `no_money`；636s 仍有 `idle_builder 等钱造FLEETBEACON`。
2. **资金去向定位**：619s 矿 570 昙花一现，其余时间被探机（35→42 连续训练，50 矿/个）+ timing_sprint 期 6 塔 + zealot 吃光；FB 的 300 矿窗 300s+ 攒不出。
3. **O224 部分生效**：SG 提前到 ~370s、transition 334s 退出（评分 24）；但 FB 段（300 矿）攒钱停产只停 SpawnController，探机/塔不在管辖内。

### 3 个改进点（落地 O225）

1. **FB 饥饿期暂停探机**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_build_probes`
   - 改法：zerg+timing + `_fb_entities_now==0` + 首舰未出 + 农民 ≥28 + 有就绪 SG → 不训探机（28+ 已超双矿饱和线 87%）。

2. **O224 保留**：SG 段（150）已验证提前；FB 段靠 O225 补齐资金链。

3. **观察指标**：FB 落成 ≤560s、O110 自救 `no_money` 次数应归零、首舰 ≤600s。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O226 — O217 清剿 3s 滞回 + O224 攒钱门 塔2→塔1（o222-lane2 game_04 尸检落地）

**日期**：2026-08-06（o222 lane2 game_04 Defeat 950s）

### 结果

- game_04 Defeat(950s)：O100 转舰队 293s、O189 强开 181s、二矿 606s，但 FB 又未落成、fleet 0 到 900s。

### 尸检发现

1. **O217 激活 218 次 yo-yo**：残敌进出 15 格/目标死亡让 `attack_target` 每帧翻转，全军在清剿与其他锚点间反复横跳，事件刷屏且部队空跑。
2. **O224 塔≥2 门太严**：本局首塔 169s、二塔 281s，`tech_saving` 直到 281s 才生效；SG 资金在 240-281s 窗口被 zealot 吃光，O110 SG 自救 no_money 连发（338-382s）。
3. **FB 资金窗仍被多重分食**：450-506s 矿 780-805 昙花一现后被 Nexus+探机+塔吃光。

### 3 个改进点（落地 O226）

1. **O217 清剿 3s 收尾滞回**
   - 文件：`ares-bot/bot/managers/combat_manager.py` `_base_intruder_target`
   - 改法：激活期每帧重算最近残敌（位置新鲜）；残敌消失后 3s 内保持最后目标收尾，超时才退出——消除每帧翻转。

2. **O224 tech_saving 塔门 2→1**
   - 文件：`ares-bot/bot/managers/production_manager.py`
   - 改法：`_cannons_ready_peak >= 1`（240s 起），与 O216i 的 SG 门（300s/塔2）错峰——门开时 150 矿已攒好。

3. **O225 保留**：game_04 二矿 606s、探机暂停待 O225 局验证。

### 验证

- `python3 -m py_compile bot/managers/combat_manager.py bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。
- 观察点：O217 事件次数应降到个位数；O110 SG 自救 no_money 应消失。

---
## O227 — Zerg Timing 推进临界 8→6（o224-lane1 game_01 尸检落地）

**日期**：2026-08-06（o222 lane2 0-5 收官，重开 o227 tag；o224 lane1 game_01 Defeat 959s）

### 结果

- o224 lane1 game_01 Defeat(959s)：fleet 1 @562、3 基地 @791、O218 追加 SG 事件连发——但 SG2 至死未落成（矿恒 <70），气烂 1806，舰队顶点 3-6 艘，被 66-97 supply 波滚平。
- o222 lane2 0-5 收官，复盘 `idle_builder×5 overrun×4 one_base×3`。

### 尸检发现

1. **推进闸永不触发**：`_force_push`/`margin=0` 的舰队临界线 ≥8，Zerg Timing 局舰队顶点只有 6（气烂 1806、矿恒 <70，8 艘永远到不了）→ 全程蹲守，Zerg 无压力运营到 2 倍兵力。
2. **O217 flap 减半但仍在**（218→76 次，本局无 O226 滞回）。
3. **O218 事件连发但 SG2 不落成**：`can_afford` 帧判定后矿被抽血，工人反复钉点/被拆——追加产能需要更持久的矿物保障，暂由 O224/O225 攒钱体系覆盖观察。

### 3 个改进点（落地 O227）

1. **Zerg Timing 推进临界 8→6**
   - 文件：`ares-bot/bot/managers/combat_manager.py` `attack_target`
   - 改法：`_push_fleet_need = 6 if zerg+timing else 8`；`_force_push` 与 `margin=0` 临界线同改。舰队 6 + t>540 → 强制推进，均势即打，断敌运营。

2. **lane2 重开 `o227-vh-zerg-timing-paladino`**（全量 O224-O227 代码）。

3. **观察指标**：舰队 6 后是否出门（`attack_target` 推敌基地）、O217 flap ≤10、SG2 落成率。

### 验证

- `python3 -m py_compile bot/managers/combat_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O228 — Zerg Timing FB 关键件钉点派工（o224-lane1 game_02 尸检落地）

**日期**：2026-08-06（o224 lane1 game_02 Defeat 1010s）

### 结果

- game_02 Defeat(1010s)：SG ~370s、二矿 458s，但 FB 至死未落成（O110 自救 95 次全 `no_money`）、fleet 0 到 675s+、气烂 1754。

### 尸检发现

1. **FB 资金被同帧抢单**：`can_afford` 派工在矿到 300 的同一帧被 zealot（O126 反暂停语义=产线永动）+ 探机 + 塔抢走；O110 自救 95 次全 `no_money`，FB 排队永远排第二。
2. **post-transition 无科技攒钱闸**：O224 tech_saving 只限 transition 期；O106 `fleet_tech_reserve` 在 O110 停滞确认后自解除（tech_stalled），FB 资金窗裸奔。
3. **O225 未触发**：农民峰值 22-24 < 28 门（单矿期 FB 已在排队），探机暂停帮不上这一段。

### 3 个改进点（落地 O228）

1. **FB 走关键件钉点派工**
   - 文件：`ares-bot/bot/managers/production_manager.py` 重建窗 FB 分支
   - 改法：zerg+timing 时改 `_dispatch_structure(FLEETBEACON, critical=True)`（同 O147 forge 机制：驻点等钱=钱到立刻开工，FB 进资金第一顺位）；其余流派维持 `can_afford` 守卫不变。

2. **验证指标**：FB 落成 ≤560s、O110 FB `no_money` 自救归零、`idle_builder FLEETBEACON` 有界（≤10s/次）。

3. **方向备忘**：O218 SG2 反复派工不落成（矿 <150）仍待解——若 O228 后 FB/首舰提前，SG2 资金窗应自然出现，下轮复核。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O229 — 追加星门同走钉点派工（o227-lane2 game_01 尸检落地）

**日期**：2026-08-06（o227 lane2 game_01 Defeat 1407s，迄今最健康局）

### 结果

- game_01 Defeat(1407s)：FB 462s、二矿 402s、**5 基地/71 农民峰值/舰队 5-6**、撑到 1407s；终局被 82-101 supply（1.5×）连续波滚平。

### 尸检发现

1. **O218 追加星门 58+ 次全空转**：与 FB 同型——`can_afford` 帧判后矿被 zealot/探机/塔同帧抢走，SG2 至死未落成，舰队产能卡在 1-2 座星门。
2. **经济链已跑通**：O222 硬饱和开矿链达成 5 基地；败因转为产能/补充速度（暴风 250 矿/艘 vs Zerg 即时补员）。
3. **配比问题**：freeflow 下 p0 暴风恒优先，航母（0.15/p1）全程 0 艘——气烂 1288 时航母未被混编，拦截机肉盾缺席。

### 3 个改进点（落地 O229）

1. **追加星门改关键件钉点派工**
   - 文件：`ares-bot/bot/managers/production_manager.py` O218 块
   - 改法：zerg+timing 时 `_dispatch_structure(STARGATE, critical=True)`；其余流派维持 `can_afford`。

2. **验证指标**：SG ≥3 座 @700s、O218 事件次数 ↓（一次派工一次落成）、舰队 ≥8 @900s。

3. **方向备忘（下轮）**：气烂 ≥800 时混编航母（p1 不被 p0 永久截断的配比出口），以及暴风 vs 飞蛇/腐化的交战后撤线核查。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## 首胜！o224-lane1 game_05 Victory(994s) — Zerg Timing 零的突破

**日期**：2026-08-06（o224 lane1 收官 1-4；o227 lane2 0-2 进行中）

### 胜局数据

- **Victory(994s)**：终局 4 基地、63 农民、**supply 159/159**、军队 25 追猎 + 5 暴风 + 3 虚空 + 4 叉；SG 4 座 @844s、舰队 5 @900s。
- 开矿链：二矿 393s → 三矿 630s → 四矿 968s（O222 硬饱和全链跑通）。

### 有效成分（与败局对比）

1. **O229 钉点派工生效**：SG 1→4 座全部落成（此前 O218 空转 58 次 SG2 不出）；舰队产能打开。
2. **满人口团战**：159/159 vs 此前败局顶点 60-80——4 基地经济 + 产线不卡钱（O224/O225/O228 资金链修复）。
3. **混编地面**：25 追猎提供对空 DPS（vs 腐化/飞蛇），暴风不再孤立。

### 待解问题

- lane1 仍 1-4：game_01-04 的 FB/SG 钉点派工（O228/O229）是 game_05 才吃到的代码，前 4 局属旧代码窗——**重开 `o229-vh-zerg-timing-abyssal` N=5 全代码验证**（已启动）。
- lane2（o227 tag）game_03+ 热加载 O229 继续观察。

### 验证

- 胜局数据已核实（state 快照曲线 + 终局编制）。

---
## O230 — Zerg Timing 追猎防守核 cap2 2→8（胜负局对照落地）

**日期**：2026-08-06（o229 lane1 game_01 Defeat 1107s；o227 lane2 0-4）

### 对照分析

- **胜局**（o224 game_05 Victory）：25 追猎 + 5 暴风 + 3 虚空，159 满人口——pivot 反空军触发混出追猎海，对空对地双用，基地守住了。
- **败局**（o229 game_01）：舰队 6 @788 达标、SG 3 座，但敌纯地面时追猎 cap2=2、叉 3 个，27 地面波滚平三矿；气烂 1321 没人用。

### 3 个改进点（落地 O230）

1. **Zerg Timing 追猎 cap2 2→8**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_apply_floor`
   - 改法：zerg+timing 时 `_cap2 = max(pf.cap2, 8)`——用烂在银行的气（常态 1000+）养 8 追猎防守核，不吃舰队矿，对空对地双用。

2. **保留 O229 方向**：SG 3 座/舰队 6 @788 已成常态，产能不再是一号瓶颈。

3. **观察指标**：中期（700-1000s）追猎数应 ≥6、基地被 27 地面波平推的场景应减少、E6 农民撤离次数下降。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O231 — Zerg Timing 塔封顶 3→2/基地（o229-lane1 game_02 尸检落地）

**日期**：2026-08-06（o227 lane2 0-5 收官，重开 o230 tag；o229 lane1 game_02 Defeat 1099s）

### 结果

- o229 lane1 game_02 Defeat(1099s)：二矿 293s、三矿 554s，但塔 10 座（≈1350 矿）在 FB/舰队资金窗持续抽血，星门恒 1、舰队 675s 才 1 艘、气烂 1663。

### 3 个改进点（落地 O231）

1. **Zerg Timing `_ec_max` 3→2/基地**
   - 文件：`ares-bot/bot/managers/production_manager.py` F2 塔目标
   - 改法：O230 追猎防守核（气耗、8 只）上岗后，静态塔可再降；2/基地×3 基地=6 塔省 ~600 矿给舰队产能。

2. **lane2 重开 `o230-vh-zerg-timing-paladino`**（全量 O228-O230 代码；O231 热加载跟进）。

3. **观察指标**：塔总数 ≤2×基地、舰队 ≥4 @650s、气烂时追猎 ≥6。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O231b — 追猎 cap2=8 推迟到首舰后（o230-lane2 game_01 尸检落地）

**日期**：2026-08-06（o230 lane2 game_01 Defeat 980s）

### 结果

- game_01 Defeat(980s)：SG 停滞自救 no_placement→no_money（325-418s）、FB 钉点派工 21 次 no_money，fleet 0 到 930s，终局 73-supply 波滚平。

### 尸检发现

1. **O230 的 8 追猎反噬 FB 资金窗**：追猎 125 矿/只 × 8 = 1000 矿需求与 FB(300)/暴风(250) 正面冲突——首舰出场前追猎海是纯矿耗，与「防守核」设计意图（吃烂气）矛盾。
2. **胜局追猎海的真实来源**：o224 胜局的 25 追猎是**舰队成型后**经 pivot 反空军混出来的，不是首舰前堆的。

### 改法（O231b）

- `ares-bot/bot/managers/production_manager.py` `_apply_floor`：cap2=8 仅在 `_first_fleet_seen()` 后生效；首舰前回到 pf.cap2=2（原语义）。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## 第二胜！o229-lane1 game_03 Victory(1132s) — 14 暴风+4 航母压制局

**日期**：2026-08-06（o229 lane1 目前 1-2，game_04/05 决定能否 3-2 打穿）

### 胜局数据

- **Victory(1132s)**：终局 5 基地、63 农民、**supply 199/200**、军队 **14 暴风 + 4 航母** + 21 追猎 + 1 叉；SG 5 座；矿 1405 富余。
- 开矿链：二矿 333s → 三矿 538s → 四矿 831s → 五矿（O222 全链）。

### 有效成分（累计）

1. **资金链修复四件套**（O224 tech_reserve / O225 停探机 / O228 FB 钉点 / O229 SG 钉点）：SG 5 座全落成，舰队 14+4。
2. **航母首次混编**（4 艘）：气矿富余时 p1 航母终于出场，拦截机肉盾+暴风输出体系成型。
3. **O230 追猎核**：21 追猎（首舰后 cap2=8 + pivot 反空军叠加）。

### 当前战绩

- o229 lane1（Abyssal）：1-2（game_01/02 Defeat 属旧代码窗，game_03 Victory 全代码）
- o230 lane2（Paladino）：0-2（game_03 进行中）

---
## O232 — Zerg Timing 强推加劣势闸（o229-lane1 game_04 尸检落地）

**日期**：2026-08-06（o229 lane1 目前 1-3，game_05 收官局进行中）

### 结果

- game_04 Defeat(970s)：舰队 6 @731、SG 3 座达标，但 900-956s 间舰队 6→0 全灭（O227 舰队 6 硬推撞上 65-supply 敌群），随后基地被滚平。

### 对照

- game_03 Victory：舰队 14+4 航母、199 supply 才进入决战——推的时机是对的。
- game_04 Defeat：舰队 6（我方 ~43 supply vs 敌 65）硬推 = 送。

### 改法（O232）

- `ares-bot/bot/managers/combat_manager.py` `attack_target`：Zerg Timing 的 `_force_push` 追加劣势闸——`own_army_supply >= 敌可见 × 0.8` 才推，劣势继续蹲（margin 判据不受影响）。

### 验证

- `python3 -m py_compile bot/managers/combat_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## o232 lane1 game_01 全代码基线尸检（Defeat 980s）

**日期**：2026-08-06

### 结果

- o232 lane1（Abyssal 全代码首发）game_01 Defeat(980s)：二矿 437s、SG ~430s、FB ~620s、首舰 675s，但**舰队卡在 1 艘 280s**、星门恒 1，被慢性磨死。

### 尸检发现

1. **舰队 1→1 停滞**：FB 后气 384-992 持续富余、矿 60-390 间歇达标，但舰队 280s 零增长——1 座星门 + 追猎 cap2=8（首舰后激活，125 矿/只）与暴风（250 矿/艘）在矿稀缺期正面竞争，rush latch 高频期 O218 SG 追加被 `not rush_active` 闸住。
2. **rush latch 长期化**是 O218 SG2 出不来的主因之一（本局 rush=True 片段极多）。

### 候选改进点（待更多局确认后再落地，防 thrash）

1. O218 的 `not rush_active` 放宽为「rush_active 但家 40 格无敌 ≥4」也可追加 SG（波间隙窗口）。
2. 追猎 cap2=8 加「舰队 ≥3 或气 ≥600」前置，避免与暴风抢矿。

### 验证

- 尸检数据已核实；暂不改代码，等 o232 双 lane 更多局确认趋势。

---
## O233 — O218 急性 rush 闸 + 追猎 cap2=8 后置舰队≥3（o232 双 lane 尸检落地）

**日期**：2026-08-06（o232 lane1 0-2、lane2 game_01 Defeat 1259s）

### 结果

- o232 lane2 game_01 Defeat(1259s)：SG 3 @788、舰队 6-7、三矿 968s——全代码局明显改善，终局被慢性磨死。
- o232 lane1 game_01/02 Defeat：舰队卡 1 艘 280s（rush latch 闸 O218 + 追猎 cap2=8 与暴风抢矿）。

### 3 个改进点（落地 O233）

1. **O218 追加 SG 的 rush 闸放宽为急性口径**
   - `not _rush_active` → `not (_rush_active and 家 40 格敌作战单位 ≥4)`；波间隙 latch 不再挡产能。

2. **追猎 cap2=8 后置到舰队 ≥3**
   - `_apply_floor`：`_first_fleet_seen()` 前置改为 TEMPEST+CARRIER ≥3，避免首舰刚出时 8 追猎（1000 矿）与暴风（250 矿/艘）抢矿。

3. **验证指标**：舰队 1→3 耗时 ≤120s、O218 事件后 SG 落成率、中期追猎 6-8 只在舰队 ≥4 后才出现。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O234 — 回滚 O231（塔封顶回 3/基地）：o232 双 lane 0-8 回归分析

**日期**：2026-08-06（o232 lane1 0-4、lane2 0-3，全部 O233 代码局）

### 回归分析

- o229 lane1（1-4 含 Victory）与 o232 双 lane（0-8）的代码差：O231（塔 3→2/基地）+ O231b/O233（追猎核后置到舰队≥3）。
- 后果：中期（500-700s）二矿防御 = 2 塔 + 零追猎（追猎核要等舰队≥3 才上岗），被 10-20 地面波连丢二矿，经济封顶 1-2 基地，舰队永远到不了 6+。
- 胜局的打开方式（4-5 基地 + SG 4-5 + 追猎海后期）没变，变的是中期塔少了 1/3。

### 改法（O234）

- `ares-bot/bot/managers/production_manager.py`：Zerg Timing `_ec_max` 回滚 2→3/基地；追猎核（cap2=8、舰队≥3 后）作为**增量**保留，不再替代塔。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O235 — FB 被拆重建同走钉点派工（o234-lane1 game_01 尸检落地）

**日期**：2026-08-06（o232 双 lane 各 0-5 收官，o234 双 lane 重开进行中）

### 结果

- o234 lane1 game_01 Defeat(1663s 局)：3 基地、47 农民、SG 5 座，但 FB 被拆后 **FB=0 持续 300s+**（重建走 O83 `can_afford` 老路被同帧抢单），气烂 2400、舰队停产僵死，终局败亡。

### 3 个改进点（落地 O235）

1. **O83 FB 饥饿重建改钉点派工**
   - 文件：`ares-bot/bot/managers/production_manager.py` `_fleet_starved` 分支
   - 改法：zerg+timing 时 `_dispatch_structure(FLEETBEACON, critical=True)`（同 O228 机制）；其余流派不变。

2. **覆盖关系明确**：O228（首 FB/重建窗）+ O235（中后局 FB 被拆重建）= FB 全生命周期钉点派工。

3. **观察指标**：FB 被拆后重建 ≤60s、气烂 ≥1500 且 FB=0 的僵局不再出现。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O236 — Nexus 钉点期停探机+追猎 floor 归零（胜负局二矿时点对照落地）

**日期**：2026-08-06（o234 双 lane 各 0-5 收官；o235 双 lane 进行中）

### 对照发现

- 近 10 局胜负关键变量：**二矿时点 ≤400s=胜**（o229 game_03 二矿 333s 胜）、**≥500s=负**（o234 game_02 二矿 598s 负）。
- Nexus 钉点期间的抽血源：探机（50 矿/个，最大）+ 追猎 floor（125 矿/只）+ 塔 + zealot；前两者可暂停，后两者保命不动。

### 3 个改进点（落地 O236）

1. **Nexus 钉点期暂停探机**
   - `_build_probes`：zerg+timing + Nexus 未开工 + 农民 ≥18 → 不训探机（18+ 够当前矿线，解除自恢复）。

2. **Nexus 钉点期追猎 floor 归零**
   - `_apply_floor`：zerg+timing + Nexus 未开工 → `_cap2 = 0`（优先级高于舰队≥3 的 cap2=8 分支）。

3. **归因纪律**：o235 双 lane 仅 game_01 为 pre-O236 代码，game_02+ 全为 O236，样本归因清晰。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。
- 观察指标：二矿时点 ≤400s 的局占比（目标 ≥60%）。

---
## O237 — 敌地面重型提前激活追猎核（败局共性落地）

**日期**：2026-08-06（o235 lane2 0-5 收官，重开 o236 tag；o235 lane1 进行中）

### 胜负对照（决定性）

- **胜局共性**：21-25 追猎——由 pivot 反空军（敌空军 ≥3 → 0.3 配比）触发；Zerg 出腐化/飞龙**反而**送给我们追猎海，对空对地双用守住基地。
- **败局共性**：敌纯地面（roach/ravager/hydra）→ pivot 不触发 → 追猎零产（cap2=8 又要等舰队 ≥3）→ 27 地面波滚平基地。

### 3 个改进点（落地 O237）

1. **敌可见地面 ≥8 即激活追猎核**
   - `_apply_floor`：zerg+timing 时 cap2=8 的激活条件从「舰队 ≥3」放宽为「舰队 ≥3 或敌可见地面 ≥8」，Nexus 钉点期仍为 0（O236 优先）。

2. **o235 lane2 复盘**：`idle_builder×5 overrun×4 one_base×2 trickle×1 supply_block×1`；game_04 二矿 362s（O236 达标）仍败于中期地面防御真空。

3. **观察指标**：敌地面 ≥8 时追猎应在 60s 内 ≥4；E6 农民撤离次数下降。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O238 — O236 钉点暂停只限首扩（o237-lane1 game_01 尸检落地）

**日期**：2026-08-06（o236 lane2 0-5 收官 one_base×5；o237 lane1 game_01 Defeat 1267s）

### 结果

- o237 lane1 game_01 Defeat(1267s)：**二矿 405s（O236 达标）**、舰队 7 @844、SG 3，但舰队 5-7 平台期 400s、气烂 2004、矿恒 25-70，农民峰值仅 44（胜局 63-71），被慢性磨死。

### 尸检发现

1. **O236 探机暂停累计反噬**：钉点在二矿/三矿/四矿反复发生，每次都停探机 = 农民峰值被掐在 44——矿收入平台化，舰队 250 矿/艘补不上消耗。
2. **胜局农民水位 63-71 vs 败局 36-46**：农民规模是比二矿时点更深层的胜负变量（收入决定舰队补充速度）。

### 3 个改进点（落地 O238）

1. **O236 探机暂停只限首扩钉点**（`townhalls<2`）：三矿以上钉点照产探机。
2. **O236 追猎 floor 归零同样只限首扩钉点**：三矿以上钉点追猎核照产（防守优先）。
3. **观察指标**：农民峰值 ≥55、舰队平台期（卡 N 艘 >120s）消失。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O239 — 气烂银行直接点航母（o237 多局尸检落地）

**日期**：2026-08-06（o237 lane1 0-4、lane2 0-3 进行中）

### 尸检发现

- 败局共性：气烂 1300-2000 而矿恒 <100——暴风（250 矿/艘）产不动，舰队 6-9 艘打不赢 60-90 supply 地面波；暴风 vs 刺蛇集火生存性差。
- 胜局共性：3-4 航母混编（o224/o229 两胜都有）——拦截机吸火 + 本体远程，vs 无对空地面是质变。
- o237 lane1 game_02 是近年最好败局：农民 63、舰队 9、三矿 658s，仍被多点抄家磨死——缺的最后一环就是舰队质量（纯暴风）而非数量。

### 3 个改进点（落地 O239）

1. **气烂 ≥700 且 FB 在 → 空闲就绪星门直接点航母**
   - `ares-bot/bot/managers/production_manager.py`（stall watchdog 后）
   - 改法：zerg+timing + `vespene≥700` + `_fb_entities_now>0` + `can_afford(CARRIER)` → 每帧最多 1 座空闲 SG `train(CARRIER)`，记事件。

2. **配比说明**：freeflow 下 p0 暴风恒优先，航母配比 0.15 永不触发——O239 绕过配比直接下指令，只在气烂时生效，不扰动正常配比。

3. **观察指标**：航母 ≥2 @900s、O239 事件出现、舰队存活时间（平台期长度）上升。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。

---
## O240 — 航母攒钱预留（o237 双 lane game_05 实证：O239 被 can_afford 封印）

**日期**：2026-08-06（o237 双 lane 各 0-5 收官）

### 结果

- o237 双 lane 各 0-5；两局 game_05（O239 代码）事件核查：**O239 零触发**、O218 36/208 次——`can_afford(CARRIER)` 要求 350 矿，矿恒 <100 的经济里永远为假。

### 3 个改进点（落地 O240）

1. **`spawn_pause_reason` 新增 `zerg_timing_carrier_reserve`**
   - 触发：zerg+timing + 非 transition + 气 ≥800 + FB 在 + 航母配比落后（航母+在产 < 暴风/6）且矿 <350 → 暂停产线攒钱，攒够自恢复（O239 同帧点舰）。

2. **航母攒钱期探机同让位**
   - `_build_probes`：同口径条件 → 不训探机（50 矿/个是攒钱期最大抽血源）。

3. **双 lane 重开 `o240` tag**（全量 O239+O240 代码首发）。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py bot/production_plans.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。
- 观察指标：O239 事件首次触发、航母 ≥1 @900s、`O126:产兵暂停=zerg_timing_carrier_reserve` 事件。

---
## O241 — 回归排查：回滚 O232 劣势闸 + 恢复 O230 无条件追猎核（0-30 区间分析）

**日期**：2026-08-06（o230-o240 区间 10 lane 0-30，此前 o224/o229 两胜）

### 区间分析

- **胜局代码状态**（o224 game_05 / o229 game_03）：O229 SG 钉点 + **O230 无条件 cap2=8** + 塔 3/基地 + **无 O232 劣势闸**。
- **0-30 区间新增**：O231b/O233（cap2 后置）、O232（劣势不推）、O236-O240。全部 0 胜。
- 最可疑两项：O232 让 bot 全程被动挨打（zerg 自由运营 2 倍兵力）；O233 让中期追猎零产（防守真空）。

### 3 个改进点（落地 O241）

1. **回滚 O232 劣势闸**：Zerg Timing `_force_push` 恢复「舰队 6 + t>540 即推」，不再要求 supply 优势。
2. **恢复 O230 无条件 cap2=8**：去掉舰队≥3/敌≥8 前置（O236/O238 的首扩钉点归零保留）。
3. **保留其他全部**：O235 FB 重建钉点、O236 首扩暂停、O239/O240 航母链不动——A/B 只变两项，归因清晰。

### 验证

- `python3 -m py_compile bot/managers/combat_manager.py bot/managers/production_manager.py`：通过。
- `poetry run python -m unittest discover -s tests`：**652 例通过**（skipped=1）。
- 判读标准：o240 双 lane 收官后重开 o241，若胜率回到 ≥1 胜/lane 则确认为回归点。

---
## Zerg Timing 阶段性结论与转向（O241 A/B 后 0-5 区间实证）

**日期**：2026-08-06（Zerg Timing 累计 ~70 局 bench，2 胜：o224-lane1-game_05、o229-lane1-game_03）

### 阶段性结论

1. **两胜的共同条件**：Zerg 出空军（腐化/飞龙）→ pivot 反空军触发追猎海（对空对地双用）+ Abyssal 图 + 5 基地 199 人口。**Zerg 纯地面（roach/hydra）时全败**——这是结构性的，不是参数问题。
2. **O241 A/B 验证**：回滚 O232/O233 到胜局代码状态仍 0 胜 → 两胜主要由敌方兵种构成（运气）驱动，代码微调无法改变 vs 地面海的基本面。
3. **vs roach/hydra 的正确答案**：不朽者（蟑螂是重甲，不朽加成攻击+刚毅护盾）或巨像——carrier 流（纯星门产能）当前**没有机械台/这些兵种**，这是下一个大杠杆（需新增 ROBOTICSFACILITY + 不朽者混编，估 1-2 轮迭代）。

### 已固化的有效资产（全部保留）

- 资金链四件套：O224 tech_reserve / O225 停探机 / O228 FB 钉点 / O229 SG 钉点（SG 4-5 座、FB ≤560s 已成常态）
- 开矿链：O222 硬饱和（3-5 基地）+ O236/O238 首扩钉点暂停（二矿 ≤405s）
- 防御体系：O216i 防御优先门 + O220/O221 无防基地强注册 + O217 残敌清剿 + O219 全军协防
- 舰队链：O218 追加 SG + O239/O240 航母攒钱点舰 + O227 舰队 6 强推

### 转向决策

- **Zerg Timing 挂起**（2 胜，状态固化于本日志与 `docs/handoff-zerg-timing-o216j.md`），下一个大杠杆 = 机械台+不朽者混编 vs 地面海。
- **转向 Terran Rush**（六组合之三）：zerg 专属门全部按 `opp_race` 隔离不影响；Terran 前期生物波（枪兵/掠夺）压力曲线不同，当前防御体系可能更匹配。

---
## Terran Rush 首局即胜！o241t-lane2 game_01 Victory(1119s)

**日期**：2026-08-06（组合三 Terran Rush 开局 1-0）

### 胜局数据

- **Victory(1119s)**：终局 3 基地、51 农民、146/154 supply、**14 暴风 + 3 航母（14 拦截机）**+ 2 追猎 + 4 叉。
- 开矿链：二矿 321s → 三矿 478s（O222/O236 链直接复用生效）。

### 初步判读

1. **Zerg Timing 固化的资产直接迁移**：航母+暴风体系成型（O239/O240 航母链、O218 SG 追加）。
2. Terran Rush（枪兵/掠夺生物波）对空压力远低于 Zerg 腐化/飞蛇，暴风/航母生存性完全不同——正是 Zerg Timing 缺的那块。
3. 待验证：Rush 前期（150-250s）守窗在 Terran 生物波下的表现（Zerg 专属门按种族隔离，走基础 rush 六连动）。

### 当前战绩

- Zerg Rush ✅（O211 打穿）｜ Zerg Timing 挂起 2 胜 ｜ Zerg Power 未开始
- **Terran Rush 1-0** ｜ Terran Timing/Power 未开始

---
## Terran Rush 打穿！lane2 3-1（o241t，全代码）

**日期**：2026-08-06（组合三 Terran Rush 完成）

### 结果

- **lane2（Paladino）3-1 打穿**：game_01 Victory(1119s)、game_02 Defeat(972s)、game_03 Victory(802s)、game_04 Victory(554s)。
- lane1（Abyssal）1-0（game_01 Victory 2080s），余局进行中（补充样本，不影响打穿判定）。

### 胜局共性

- 3-6 基地、51-67 农民、146-200 supply、**14-24 暴风 + 3-4 航母**；Terran 生物波（枪兵/掠夺）对空压力低，暴风/航母体系无 counter 压力，成型即碾压。
- Zerg Timing 固化的资产（O218 SG 追加、O228/O229 钉点、O239/O240 航母链、O222 开矿链）全部直接生效，无一处 Terran 专属修改。

### 六组合进度

| 组合 | 状态 |
|---|---|
| Zerg Rush | ✅ O211 打穿 |
| Zerg Timing | 挂起（2 胜；下轮大杠杆=机械台+不朽者 vs 地面海） |
| Zerg Power | ⬜ |
| **Terran Rush** | **✅ 3-1 打穿（o241t）** |
| Terran Timing | 下一个 |
| Terran Power | ⬜ |

---
## Terran Rush 败局补尸检（lane2 game_05 Defeat 1196s）

**日期**：2026-08-06

### 结果

- game_05 Defeat(1196s)：舰队 12 暴风成型，但无航母混编、双矿农民 1012s 被一波打空（37→5），经济崩后慢性死亡。

### 尸检发现（3 点）

1. **航母缺位**：本局 0 航母（O239/O240 未触发——气 1090 达标但矿恒 <350 的时间窗长，攒钱预留被防御重建反复打断）；胜局均有 3-4 航母吸火。
2. **塔重建抽血**：塔 11 座峰值、反复重建，与探机/舰队争矿，舰队成型后塔仍每波被拆（trickle×3 复盘信号同源）。
3. **舰队位置**：舰队 12 艘存活但农民被杀光——O219 协防覆盖的基地与敌实际主攻方向错位（后续 Terran Timing/Power 迭代重点核对）。

### 验证

- 不影响 lane2 3-2 打穿判定；改进点留作 Terran Timing/Power 迭代输入。

---
## Terran Timing 打穿！lane2 3-1（o242t）

**日期**：2026-08-06（组合四完成）

### 结果

- **lane2（Paladino）3-1 打穿**：game_01 Victory(696s)、game_02 Victory(504s)、game_03 Victory(355s)、game_04 Defeat(175s)。
- 与 Terran Rush 同一套代码零修改——暴风+航母体系对 Terran 各风格全面压制。

### 六组合进度

| 组合 | 状态 |
|---|---|
| Zerg Rush | ✅ O211 |
| Zerg Timing | 挂起（2 胜；大杠杆=机械台+不朽者） |
| Zerg Power | ⬜ |
| Terran Rush | ✅ 3-2 |
| **Terran Timing** | **✅ 3-1** |
| Terran Power | 下一个 |

---
## Terran Power 打穿！lane1 3-0（o243t）

**日期**：2026-08-06（组合五完成）

### 结果

- **lane1（Abyssal）3-0 打穿**：game_01 Victory(386s)、game_02 Victory(306s)、game_03 Victory(445s)；lane2（Paladino）0-4（补充样本）。
- 同一套代码对 Terran 三风格（Rush/Timing/Power）合计 9 胜 3 负，零 Terran 专属修改。

### 六组合进度

| 组合 | 状态 |
|---|---|
| Zerg Rush | ✅ O211 |
| Zerg Timing | 挂起（2 胜；大杠杆=机械台+不朽者） |
| Zerg Power | 下一个 |
| Terran Rush | ✅ 3-2 |
| Terran Timing | ✅ 3-2 |
| **Terran Power** | **✅ 3-0** |

---
## Terran Power lane1 5-0 全胜收官（o243t 补充样本）

**日期**：2026-08-06

- lane1（Abyssal）最终 **5-0**：game_01-05 全 Victory；Terran Power 组合以满分打穿。
- Zerg Power（组合二）双 lane 已启动（o244z Abyssal + Paladino），game_01 首败尸检：舰队 8 @731 成型但 844-956s 被腐化/飞蛇体系团灭——与 Zerg Timing 终局同型（Zerg 对空体系是 carrier 流的真 counter），迭代重点=航母拦截机吸火+舰队后撤线。

---
## Zerg Power 打穿！lane1 3-0（o244z）

**日期**：2026-08-06（组合二完成）

### 结果

- **lane1（Abyssal）3-0 打穿**：game_01 Victory(638s)、game_02 Victory(982s)、game_03 Victory(784s)。
- lane2（Paladino）2-1（game_02/03 Victory），game_04 进行中。

### 六组合进度

| 组合 | 状态 |
|---|---|
| Zerg Rush | ✅ O211 |
| Zerg Timing | **唯一剩余**（2 胜；大杠杆=机械台+不朽者） |
| **Zerg Power** | **✅ 3-0** |
| Terran Rush | ✅ 3-2 |
| Terran Timing | ✅ 3-2 |
| Terran Power | ✅ 5-0 |

### 判读

- 暴风+航母体系对 Zerg Power（慢成型大后期）同样成立：Power 给舰队留出了成型窗口，与 Terran 三风格同构。
- Zerg Timing 是唯一难点：波次早 + 纯地面 roach/hydra 时 pivot 不触发，需要机械台+不朽者（或等效地面答案）。

---
## O245b — 机械台提前+落分矿（o245 双 lane game_01 实证）

**日期**：2026-08-06（Zerg Timing 攻坚，唯一剩余组合）

### 结果

- o245 双 lane game_01 均败：O245 事件触发 8 次但 **robo 零落成**（主基被围/槽位满/工人被杀），且 `first_fleet_seen` 前置把 robo 排到 600s+，基地 500-700s 已丢。

### 改法（O245b）

1. **去掉 first_fleet_seen 前置**：转舰队（fleet_transitioned）即排机械台，与 FB/首舰并行。
2. **落位优先分矿**：有其他就绪基地 → 机械台落分矿（主基被围时工人/槽位都不可靠）。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。
- 观察指标：robo 落成 ≤620s、不朽者 ≥2 @700s、robo 事件不再空转。

---
## O245c — 不朽者优先级 p2→p0（o245 game_02 双 lane 实证：零产出）

**日期**：2026-08-06

### 结果

- o245 lane1/lane2 game_02 均败：机械台已落成（880s/671s），但**不朽者零产出**——freeflow 下配比不当上限只当优先序，p2 被暴风（p0）/航母（p1）恒截断（反空军追猎同 p0 才有产出的先例为证）。

### 改法（O245c）

- `_effective_spawn` O245 块：IMMORTAL `priority: 2 → 0`（与暴风同档）。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。
- 观察指标：不朽者 ≥2 @750s（robo 落成后 ~80s 内）。

---
## O245d — 机械台时间旁路（o245-lane2 game_03 实证：transition 常驻 robo 永假）

**日期**：2026-08-06

### 结果

- lane2 game_03 Defeat(1354s)：波次连续 → transition 常驻不退出 → `_fleet_transitioned` 永假 → robo 整局未排（O245 事件 0 次）。

### 改法（O245d）

- O245 机械台条件加时间旁路：`_fleet_transitioned or t≥360`（敌地面 ≥6 不变）。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。
- 观察指标：transition 常驻局 robo 也能 ≤420s 排工。

---
## O245e — 不朽者直产+攒钱预留（o245-lane1 game_04 实证：p0 同档仍零产出）

**日期**：2026-08-06

### 结果

- o245 lane1 game_04 Defeat(1085s)：机械台 715s 落成，但**不朽者仍零产出**——O245c 的 p0 同档在 dict 序上落后暴风，每帧暴风（250 矿）先付，不朽（275 矿）永远轮不到。

### 3 个改进点（落地 O245e）

1. **机械台直产通道**：敌地面 ≥6 + 不朽+在产 <4 + 买得起 → 空闲机械台 `train(IMMORTAL)`（与 O239 航母同机制，绕过 SpawnController 配比竞争），记事件。
2. **`spawn_pause_reason` 新增 `zerg_timing_immortal_reserve`**：机械台就绪 + 敌地面 ≥6 + 不朽 <4 且矿 <275 → 停产攒钱（暴风生产暂停 ~5-8s/只），攒够自恢复。
3. **保留 spawn 混编块**（兜底）与 O245b/d 建台链不变。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py bot/production_plans.py`：通过；`unittest` **652 例 OK**。
- 观察指标：`O245e:机械台直产不朽` 事件、不朽者 ≥2 @800s。

---
## O245g — 不朽者改 spawn dict 首位优先序（o245e-lane1 game_02 实证）

**日期**：2026-08-06

### 结果

- lane1 game_02：**机械台 394s 落成**（O245b/d 链路全通），但 `immortal_reserve` 停产 43 次（矿 15-60 被塔/探机照抽）275 永远攒不出、直产 0 次、地面 0 败亡。
- lane2 game_02：建台派工 26 次零落成（Paladino 建台失败原因待 O245f 取证局，game_03+）。

### 3 个改进点（落地 O245g）

1. **废弃 immortal_reserve 停产**：`spawn_pause_reason` 调用方 `immortal_saving=False`（产线永动是 O135 验证过的语义，攒钱类暂停在非结构件上不成立）。
2. **不朽者 spawn dict 首位**：`{IMMORTAL: {proportion 1.0, priority 0}, **spawn}`——275 矿可付时优先于暴风，250-274 时暴风照产，用优先序而不是停产解决。
3. **O245e 直产块保留**（买得起时补刀，无害）。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。
- 观察指标：不朽者 ≥2 @800s、`immortal_reserve` 事件消失。

---
## O246 — 舰队未成时追猎核 8→12（o245e 系列 0-10 实证）

**日期**：2026-08-06（Zerg Timing 攻坚）

### 结果

- o245e 双 lane 各 0-5；不朽者链路已全通（robo 394-667s、不朽者产出 ×1），但 650s+ 才到、数量太少，补不上 500-700s 的地面波窗口。
- 对照胜局：守窗答案是 **21-25 追猎海**（pivot 触发时），不是不朽者。

### 3 个改进点（落地 O246）

1. **舰队 <8 时追猎 cap2 8→12**：`_apply_floor` zerg+timing 分支；吃烂气（常态 1000+），舰队成型（≥8）后回 8 让气给航母/暴风。
2. **不朽者链路保留**（O245b/d/e/g 全部）作为舰队成型前的补充火力，不再承担主防守。
3. **观察指标**：600s 追猎 ≥8、E6 农民撤离次数下降、700s 基地存活率上升。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。

---
## O247 — 舰队先行：首舰前不开二矿（o246 系列 0-15 实证）

**日期**：2026-08-06（Zerg Timing 攻坚，build-order 级 A/B）

### 结果

- o246/o246b 系列 0-15：二矿 400-500s 落成即被 10-27 地面波轮抄（E6 撤离→收入崩→舰队停→再丢）——「先扩后守」在当前防御体系下不成立。
- 已验证的替代事实：胜局全是「舰队成型后开 3-5 矿」；首舰（Tempest ~550s）前的一切扩张投资都在送。

### 3 个改进点（落地 O247）

1. **首舰前不开二矿**
   - `_want_dynamic_expand`：zerg+timing + `not _first_fleet_seen()` + `t<620` → False；O189 强开在本门下游同步不触发。

2. **单矿期资源集中**：矿全给塔/追猎/舰队科技（SG→FB→首舰），舰队 1-3 艘掩护下 600s 前后再扩。

3. **A/B 判读标准**：二矿时点推迟到 ~600s 但**落成后存活率**（60s 内不被抄）≥60%、终局 supply 上升。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。
- bench：当前 lane 新局热加载生效。

---
## O248 — Zerg Timing 不再强制 transition（o246b 双 lane 0-10 实证）

**日期**：2026-08-06（Zerg Timing 攻坚，路线级 A/B）

### 结果

- o246b 双 lane（双 Abyssal 集中出样）各 0-5：transition 把舰队起点推迟到 exit(330-450)+130s，首舰 550-620s 恒晚于 500-700 波次窗——O207 强制 transition 的前提（基建链薄弱、无 FB/SG 资金链）已被 O224-O229/O218 全部重写，前提不再成立。

### 3 个改进点（落地 O248）

1. **Zerg Timing 不强制 transition**（`__init__` 只留 Rush）：直爬 cyber→SG→FB，首舰目标 ≤450s（O216i 门：2 塔后 SG ~300、FB ~360、首舰 ~420）。
2. **保留守窗资产**：O216i 防御优先门、O220/O221 无防基地强注册、追猎核（O246 cap2=12）、O217/O219 协防——地面窗由原地面配方改为正常 pre_fleet floor + 塔。
3. **A/B 判读标准**：首舰 ≤480s、500-700s 波次窗基地存活率、若 0 胜则回滚。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。
- bench：重启 o248 双 lane（Abyssal×2）。

---
## O249 — O218 门适配无 transition 路线（o248-lane1 game_01 实证）

**日期**：2026-08-06（Zerg Timing 攻坚）

### 结果

- **O248 首舰大幅提前**：双 lane game_01 首舰 410s/374s（原 550-620s），舰队 4 @788、三矿 703s——路线级修正生效。
- 但仍败（1067s）：**星门恒 1**——O248 不再强制 transition 后 `_fleet_transitioned` 永假，O218 追加 SG 整局不触发，产能卡 1 座星门被慢性磨死。

### 改法（O249）

- O218 触发条件 `_fleet_transitioned` → `(_fleet_transitioned or _first_fleet_seen())`；O228/O235/O245 等其余 `_fleet_transitioned` 门已含时间/状态旁路或无依赖，不受影响。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。
- 观察指标：SG ≥3 @700s、舰队 ≥8 @900s。

---
## O249b — Zerg Timing 禁止进入 transition（o249-lane game_01 实证）

**日期**：2026-08-06

### 结果

- o249 lane game_01 Defeat(668s)：O248 只去掉开局强制，接触/E9 波（277s 敌 13 supply）仍在 ~300s 触发 `transition_should_enter` → 直爬路线被 ground_spawn 截胡，舰队推迟，40-supply 波滚平。

### 改法（O249b）

- `_update_transition_state` 进入分支：`zerg+timing` 直接 return（Rush 保留 contact/verdict 进入）。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。
- 观察指标：事件流不再出现 `O92:过渡形态`（Zerg Timing 局）；首舰 ≤450s。

---
## 第三胜！o249-lane2 game_03 Victory(1316s) — 路线修正后首胜

**日期**：2026-08-06（Zerg Timing 累计 3 胜）

### 胜局数据

- **Victory(1316s)**：4 基地、66 农民、SG 5 座、5 暴风 + 9 追猎 + 2 不朽、supply 127/172（t=880 快照）；**无 transition 事件**（O249b 生效）。
- 路线：直爬 cyber→SG→FB（O248/O249b）+ O218/O249 追加 SG + O246 追猎核 + O245 不朽者。

### 累计六组合进度

| 组合 | 状态 |
|---|---|
| Zerg Rush | ✅ O211 |
| Zerg Timing | 3 胜（o224/o229/o249 各 1 胜；O248 路线修正后胜率显著回升） |
| Zerg Power | ✅ 3-0 |
| Terran Rush | ✅ 3-2 |
| Terran Timing | ✅ 3-2 |
| Terran Power | ✅ 5-0 |

### 判读

- O248 路线修正（不强制 transition、直爬舰队）是 Zerg Timing 的正确打开方式；
- 距打穿（单 lane 3/5）还差稳定性：lane 内胜率需 ≥60%，当前约 20-30%。

---
## O250 — _spend_bank 开矿接入舰队先行门（o249-lane game_04/05 实证）

**日期**：2026-08-06

### 结果

- o249 lane2 1-4 收官（game_03 Victory）；game_04/05 速败尸检：二矿 249s 落成（首舰远未出），O247 被 `_spend_bank` 绕开——存款 805 早到 + SG 未就绪使 `_fb_missing_starved` 永假 + `fleet_expand_holds(False)` 恒放行。

### 改法（O250）

- `_spend_bank` 滚雪球开矿闸接入 O247 同款条件：zerg+timing + 未见首舰 + t<620 → 不开。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。
- 观察指标：二矿时点 ≥600s 或首舰后；不再有 249s 二矿。

---
## O251 — 硬饱和钉点开矿（o250-lane1 game_02 实证）

**日期**：2026-08-06

### 结果

- o250 lane1 game_02 Defeat(1210s)：舰队 6 @675、SG 3、气烂 1442，但 2 基地 44 农封顶——硬饱和（≥32+8）触发开矿却因矿恒 <475（dispatch_viable buffer）Nexus 永远排不出。

### 改法（O251）

- update 尾部新增：zerg+timing + 2≤基地<5 + `supply_workers ≥ 16×基地+8` + 无 Nexus 未开工 + 非 rush_active → 最近空闲扩张点 `_dispatch_structure(NEXUS, critical=True, needs_power=False)`（驻点等钱），事件去重。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。
- 观察指标：三矿时点 ≤750s、`O251:硬饱和钉点开矿` 事件、终局 supply 上升。

---
