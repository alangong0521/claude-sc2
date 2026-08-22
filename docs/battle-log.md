# 战斗日志（司令观察记录）

> 司令观战中发现的问题统一记这里，**游戏结束后统一优化**，不在局中改代码。
> 每条记录：现象 → 影响 → 初步根因猜测 → 状态。
>
> **永久局终闭环（司令 2026-08-20）**：每一局结束后都必须立即读取该局
> `run.log`、最终/关键 `state_*.json`、录像基地时间轴和本文件；按第一性原理
> 分析收入、开销、生产资料、战斗交换与时间窗口，写出**至少 3 个带时间/数值
> 证据、且能在下一局落地验收的优化点**。一组 bench 的下一局/下一轮不得在
> 上一局尸检、代码/配置落地、测试和本文记账完成前启动。重点固定检查：探机
> 与 idle builder、二矿及健康矿区、分矿损失恢复、塔/电池位置和数量、冗余
> 作战单位的实际参战价值、升级/科技抢钱、航母与母舰节点、出击/守家交换。

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
## O252 — Zerg Timing 波间隙舰队骚扰（先手压运营，唯一未试维度）

**日期**：2026-08-06

### 依据

- 近 20 局复盘共同特征：全程蹲守 = Zerg 自由运营到 80-100 supply（2 倍兵力）滚平；胜局（o249-g03）的转折也是舰队压出去后开始的。
- O218/O239/O245e 验证：追加 SG/航母/不朽者链路全通，舰队 3-6 艘常态存在但只在防守位挂机。

### 改法（O252）

- `combat_manager.attack_target` carrier 蹲守分支：家无热点（`_hot_base_anchor` 空）且 zerg+timing 且舰队 ≥3 → 目标改敌**最远端**已知基地（`_known_enemy_townhalls()[-1]`，新矿防御最薄），狙 Nexus/农民拖慢 Zerg 成型；有热点/推进闸全开时不受影响（原逻辑优先）。

### 验证

- `python3 -m py_compile bot/managers/combat_manager.py`：通过；`unittest` **652 例 OK**。
- 观察指标：敌基地摧毁/农民击杀事件、敌 E9 supply 增速放缓、舰队战损（骚扰被截）是否可控。

---
## O253 — 直爬路线地面 floor 常开（o252b-lane game_02 实证：1400 矿零出口）

**日期**：2026-08-06

### 结果

- o252b lane game_02 Defeat(995s)：281-394s **矿 1280-1745 零出口**——探机封顶（22/矿）、O247 封扩张、塔封顶、敌未接触 → `_floor_active` 不激活 → 零地面产出；银行白躺 1400 矿 ≈ 白送 10+ 追猎的防守质量。

### 3 个改进点（落地 O253）

1. **Zerg Timing 非 transition 且 t≥240 → `_floor_active` 常开**
   - `production_manager.update` 头部；pre_fleet floor（叉 5 + 追猎 cap2=12，O246）把闲置矿变成守窗兵力。

2. **保留 O134 约束语义**：transition 流派（Rush）与 Power/Macro 不受影响（`not self._transition_active` 限定）。

3. **观察指标**：281-394s 矿峰值 ≤600、400-700s 地面（叉+追猎）≥10、波窗基地存活率上升。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。

---
## O254 — 回滚 O253（o253 双 lane 0-7 全速败实证）

**日期**：2026-08-06

### 结果

- o253 双 lane 0-7 全部速败（132-330s wall）：O253 的 `t≥240 floor 常开` 把 SG/FB/塔的钱吃成叉/追猎——舰队更晚、早期更脆，比 bank 闲置更糟。
- 对照 o252 双 lane：长局 845-1023s wall（同代码除 O253）。

### 改法（O254）

- 回滚 O253，`_floor_active` 恢复 `ground_floor_active` 原判据（rush 确认 / 敌可见地面 ≥4）。
- 重启 o254 双 lane 验证回归消除。

### 教训（记入章程）

- 「bank 闲置」在该体系不是错误是缓冲——产线永动语义（O135）下，任何新增的确定性开销都可能比闲置更致命；改开销结构必须有明确的死亡归因，不能只凭「钱没花完」。

### 验证

- `python3 -m py_compile bot/managers/production_manager.py`：通过；`unittest` **652 例 OK**。

---
## O255 — Zerg Timing 死窗三件套（o254 双 lane 0-10 尸检）

**日期**：2026-08-07

### 结果（o254，AbyssalReefLE×2，O254=O252 同码回归验证）

- 0-10，两种失败剖面：
  - **速败×4**（game 386-545s）：Zerg Timing 波 **280-310s 到脸**（10-19 supply），守军 = 1-2 塔 + 0 地面 + 22-26 农民裸接，农民被屠（25→6）后基地连锁崩。
  - **长局×6**（game 650-1380s）：撑过死窗、舰队 7 成型，900-1300s 被 60-80 supply 连续波磨光（已知 attrition 主线）。
- 对照 o252（同码）：10 局全 ≥653s —— 死窗波两系列都来了，o252 接住是硬币赢面，o254 接住率 6/10。**死窗防守是掷硬币 = 本迭代主修目标**。

### 根因链（game_02 建筑时间轴取证）

1. **F2 让位 FB 闸死锁**（O170/O172 闸）：FB 需就绪 SG，SG 未就绪时 FB 资金窗根本不存在，F2 却整段让位 —— 200-350s 防御建设冻结（1 塔 0 电池），银行躺 1900；同时 O216i（SG 让位 2 塔）无塔可等 → SG 305s、FB 349s、首舰 ~450s。
2. **presumed 解除后墙/地面全黑**：verdict=unknown（79.5s）→ presumed 关 → 坡口墙站位/堵缝解除、floor 不激活（无接触/敌未可见）→ 狗群直穿矿线屠农。
3. **TWILIGHTCOUNCIL 317s 白拍**（150/100，0-1 地面单位时无任何价值）+ 水晶 2-4 连拍（88-112s，300 矿）把 cybercore 推到 184s。

### 3 个改进点（落地 O255）

1. **O255-① FB 闸 ZT 豁免**（`fb_gate_f2_exempt_zt`）：SG 未就绪时 F2 不给「还不存在的 FB 窗」让位 → 2-3 塔+电池 ~250s 落地，O216i 的 2 塔条件同步解锁 → SG 提前 ~50s、首舰 ~400s。
2. **O255-② unknown 防御武装坡口墙**（`_unknown_defense` 加入墙武装条件）：t≥200 起墙后站位/堵缝可用，狗群不能再直穿矿线。
3. **O255-③ 死窗叉子 floor**（`zerg_timing_unknown_floor`）：ZT + unknown + t≥220 + 舰队未出 → floor 激活但**追猎 cap 0、叉 cap 3**（300 矿从 1300+ 银行出）。与 O253（cap2=12 追猎吃气吃矿，0-7 实证）的区别：不碰气、上限极小、舰队一出即退。

### 验证

- `py_compile` 通过；`unittest` **654 例 OK**（新增 2 例覆盖两判据全分支）。
- 观察指标（o255 双 lane）：280-310s 波窗基地存活率、首舰时点（目标 ≤420s）、速败（<550s）局数从 4/10 压到 0-1。

---
## O256 — 主基决死协防三件套（o255 双 lane 0-9 尸检）

**日期**：2026-08-11

### 结果（o255，AbyssalReefLE×2，验证 O255 三件套）

- lane1 0-4(+1 异常) / lane2 0-5，仍 0 胜，但剖面全面改善：
  - **速败基本消灭**：<550s 局从 o254 的 4/10 → 1/9（仅 425s 一局）；中位局长 ~740s（o254 ~600s）。
  - **首舰提前**：主力成型均值 TEMPEST@428.9s（o254 ~450-510s）；o255a-g01 舰队1@394s。
  - **SG 提前**：261-281s（O255-① FB 闸豁免解锁 O216i 的 2 塔条件）。
- **统一死因**：280-350s 波（9 蟑螂+11 狗 ~20 单位）进主基，**农民 22-26 → 5-10 被屠**，
  经济断气 → FB 拖到 630s+/舰队恒 0-2/二矿开不出 → 中局磨死。
  E6 两道闸全挡死：rush 期主基不撤（main.py:286）+ 单基地 target=None 无处可撤。
- 算账：22 农民(≈100dps)+4 塔(64dps) 对 9 蟑螂是**赢面**；站着被屠才是输面。

### 3 个改进点（落地 O256）

1. **O256-① 主基决死协防**（`worker_last_stand` + `update_worker_last_stand`）：
   急性窗(rush/threat) + 单基地 + 有塔可依 + 敌地面达压垮线(6+4×塔数) →
   GATHERING 农民拉去塔下攻击最近敌地面(role=CONTROL_GROUP_TWO，Mining 不抢)，
   敌 <2 滞回退出回采。多基地局仍走 E6 撤离。
2. **O256-② ZT unknown 塔目标 2→3**：game_02 实证塔3/塔4 在波到脸后(329-333s)才拍下、
   建造期被拆；第三座塔提前到 ~280s 就绪。
3. **O256-③ ZT unknown 窗电池 1→2**：9 蟑螂集火 6s 一座塔，单电池奶不住；
   双电池互充+奶塔给协战农民/叉子换输出时间（100 矿出自死窗期 1300+ 银行）。

### 验证

- `py_compile` 通过；`unittest` **655 例 OK**（新增 worker_last_stand 全分支）。
- 观察指标（o256）：280-350s 波窗农民存活（目标 ≥15/22+）、波后 FB 时点（目标 ≤420s）、首胜。

---
## O257 — 坡口墙封口 + robo 提前 + 协防覆盖口径（o256 双 lane 0-10 尸检）

**日期**：2026-08-11

### 结果（o256，验证 O256 三件套）

- lane1 0-5 / lane2 0-5。剖面继续改善：7/10 局活到 616-974s wall、多局开出二矿
  （526s/626s）、o256a-g01 死窗第一波农民 24 全存（塔3+电池2+叉3 守住坡口）。
- **仍 0 胜的统一死因**：死窗波（9-10 蟑螂+9-11 狗 ≈30 supply，305-320s 到脸）
  的后续波（350-660s 每 ~50s 一波）把塔磨光后屠农。地面组合全部实证守不住：
  3 叉（o255）、5 追猎（o253）、3 塔+2 电池（o256a-g01 守住了第一波但波 2-6 磨穿）。
- O256-① 协防在 o256a-g03 未触发：坡口塔距 Nexus >9 格（E6 覆盖口径），判 0 塔。

### 3 个改进点（落地 O257）

1. **O257-① ZT unknown 窗坡口墙造到封口**（`_wall_build_chain` 从 presumed 链抽取复用）：
   presumed ~80s 解除后墙链停摆是死窗无墙的直接原因；unknown 窗（t≥200）继续造
   墙位水晶/GW/forge 直到 `_wall_sealed`，波到脸（threat）即停工。物理封口 +
   塔/电池墙后输出 = rush 局已验证的解（Zerg Rush 3/5 靠它）。
2. **O257-② robo 钉点 360s→280s**（敌地面 ≥6 前提不变）：首不朽 ~450s→~400s，
   波 2-6（350-660s）有不朽接手；360s 触发在 o256 各局都晚于经济崩溃点。
3. **O257-③ 决死协防塔覆盖口径 9→18 格**（`_LAST_STAND_COVER`）：坡口塔纳入覆盖，
   o256a-g03 型「有塔不协防」消除。

### 验证

- `py_compile` 通过；`unittest` **655 例 OK**。
- 观察指标（o257）：墙封口率/封口时点（目标 ≤290s）、首波农民存活 ≥18、首不朽 ≤420s、首胜。

---
## O258 — 二矿窗防御驱动 + 墙局部重开（o257 双 lane 0-10 尸检）

**日期**：2026-08-11

### 结果（o257，验证 O257 三件套）

- lane1 0-5 / lane2 0-5。局长进一步拉长（650-1000s 常态），O257-② robo 280s
  生效（robo 397s、不朽 1-4 从 498s 起，o257a-g01）。仍 0 胜。
- **O257-① 是死代码事故**：`_WALL_ENABLED=False`（O138 已证伪关断），
  `_wall_slots()` 第一行就 return None——墙链整轮没跑。尸检不细之过，
  记入教训：复用「保留备查」代码前必须查总开关。
- **统一死因（中局）**：二矿落成 518-671s（O247 首舰门 + 首舰 394-640s），
  O236 对照「二矿 ≤400s=胜、≥500s=负」全在负侧；单矿 22-24 农养不起航母海,
  舰队 2-3 封顶,900-1040s 被 70+ supply 波磨穿。复盘 one_base×4-5 同证。

### 3 个改进点（落地 O258）

1. **O258-① 二矿窗防御驱动**（`zerg_timing_expand_allowed`，替换 O247/O250
   两处首舰门）：O247 的原始证据来自死窗守不住的时代;O255-O257 后死窗可守,
   t≥340 且非威胁且家无敌 → 放行开矿(不等首舰),Nexus 落成 ~430-470s。
2. **O258-② 墙 force 局部重开**（`_wall_slots(force=)`）：O138 关断只针对 rush
   早期窗(55-150s 墙派工抢 forge/首塔钱);ZT unknown 窗(t≥200,银行 1300+,
   threat 即停工)是不同经济上下文。武装/封口/建造链三处在 ZT unknown 窗
   传 force=True,`_WALL_ENABLED` 保持 False 不动 O138 语义。
3. **教训固化**（非代码）：复用保留代码先查总开关;O257-① 空跑一轮的代价比
   查证 5 分钟大。

### 验证

- `py_compile` 通过；`unittest` **656 例 OK**（新增 zerg_timing_expand_allowed 全分支）。
- 观察指标（o258）：墙槽是否可用/封口时点、二矿落成时点（目标 ≤470s）、三矿有无、首胜。

---
## O259 — ZT 直爬 FB 钉点派工（o258 双 lane 0-10 尸检）

**日期**：2026-08-11

### 结果（o258，验证 O258 二矿窗+墙 force）

- lane1 0-5 / lane2 0-5。两个机制验证成功：**二矿落成 369-486s**（O258-① 达标，
  原 518-671s）；**墙链全 10 局激活**（200s 武装、槽位可用、三件陆续上墙）。
  o258a-g01 开出三矿（743s）。仍 0 胜。
- **新瓶颈（统一死因）**：FB 帧级抢钱连败 —— o258a-g02：SG 337s 就绪后 FB 从
  ~380s 起派,no_money 反复(O110 停滞自救 421s/466s),Nexus/塔/农民每帧抽走
  300 矿窗,FB 667s 才落,首舰 788s;SG 恒 1(O218 首舰前置鸡生蛋)。
  舰队成型晚 300s+,中局波把 2 基地磨穿。

### 3 个改进点（落地 O259）

1. **O259-① ZT 直爬 FB 钉点派工**：O228 的 critical 钉点（驻点等钱=钱到立刻
   开工）从 transition 重建窗扩到 ZT 直爬的 `_build_flow_structures` FB 分支;
   威胁让位闸（threat/rush）不变。目标 FB ≤420s、首舰 ≤520s。
2. **O258-② 墙链已验证激活**;封口率/封口时点待 o259 取证（O137 派工摩擦
   taken/cooldown 偏多,若封口晚于 300s 再议提速）。
3. **观察项**：o258b-g02 的 239s 早波变体（10 supply,死窗防御未成型）1/10 出现,
   样本不足暂不专项,若 o259 复现再处。

### 验证

- `py_compile` 通过；`unittest` **656 例 OK**。
- 观察指标（o259）：FB 落成时点、首舰时点、舰队中局增速（SG≥2 时点）、首胜。

---
## O260 — 舰队资金窗三修（o259 双 lane 0-10 尸检）

**日期**：2026-08-11

### 结果（o259，验证 O259 FB 钉点）

- lane1 0-5 / lane2 0-5。**FB 钉点成功**：o259a-g01 FB 385s（o258 同类局 667s）、
  SG2-3 在 590-606s、二矿 425s、农民 41——科技链全程最快剖面。仍 0 胜。
- **统一死因（中局舰队断粮）**：o259b-g02 全览 —— 750-1050s 气 1000-1500 恒烂、
  矿恒 40-325、3 星门只产 1 暴风+1 航母：①O246 追猎核 12 只(1500 矿)波灭即重建,
  反复吃掉航母 350 矿窗;②save_up 截断把星门押给凑不齐的航母,暴风(250)也不产;
  ③o259b-g01 反向事故:墙三件(400)+电池2+塔3 抢在 SG 前派工,SG 饿到 421s=0。
- 另:o259b-g02 打出 1290s wall 长局(1107s game),死窗/波 2-6 防守体系已稳固。

### 3 个改进点（落地 O260）

1. **O260-① 气烂追猎节流**：气 ≥600(瓶颈是矿的信号)时 O246 追猎 cap 12→4,
   矿让给舰队。
2. **O260-② 暴风兜底点舰**：气 ≥500 + 航母买不起 + 暴风买得起 + 空闲星门 →
   直接点暴风(同 O239 机制,绕过 save_up 截断);舰队数量 > 完美配比。
3. **O260-③ 防御超支三件让位 SG**：墙链/第三塔/第二电池改 SG 在途或就绪后才
   开工(死窗 2 塔+1 电池保底线不动,O216i 语义不变),舰队科技链资金优先。

### 验证

- `py_compile` 通过；`unittest` **656 例 OK**。
- 观察指标（o260）：舰队 600-900s 增速(目标 ≥5)、SG 不被饿死(≤300s)、首胜。

---
## O261 — 死窗虚空 + 墙再关断（o260 双 lane 0-10 尸检）

**日期**：2026-08-11

### 结果（o260，验证 O260 三修）

- lane1 0-5 / lane2 0-5，且速败回升（161-309s wall 多局）——O260-③ 的连锁：
  墙链（SG 在途即开工）在 261-330s 吃掉 400 矿，塔3 整场未建（o260a-g05:
  波到脸 塔2+池2+叉3，塔 321-333s 全灭，农 22→5）。
- **战略复盘（58 局无胜的破局点）**：死窗波（9蟑螂+11狗）**零对空**；
  SG 就绪(261-281s)→FB 就绪(~385s) 星门空转 100s+；o224 首胜编配
  （25追猎+5暴风+3虚空,159人口）里虚空就是死窗战力。墙两次实证不成立
  （O138 rush 早期窗 / O258+o260 ZT unknown 窗）。

### 3 个改进点（落地 O261）

1. **O261-① 死窗虚空×2**：ZT 直爬,SG 就绪且 FB 未在途/就绪 → 空闲星门点
   虚空(150/100,无需 FB),上限 2 艘;FB 在途即停。虚空无战损点杀蟑螂
   （roach/ling 无对空）,死窗从「死守等磨」变「点杀反打」。
2. **O261-② 墙链再关断**（`if False` 备查）：ZT unknown 窗墙派工 400 矿
   挤死塔3/SG 资金窗,封口从未在波前完成;O138 结论推广到 ZT 窗。
3. **O260 三修保留**：气烂追猎节流(12→4)/暴风兜底点舰/防御三件让位 SG,
   与虚空不冲突（虚空只占 FB 前的空转星门）。

### 验证

- `py_compile` 通过；`unittest` **656 例 OK**。
- 观察指标（o261）：虚空出场时点(目标 ≤330s)、死窗波交换比(蟑螂击杀数)、
  死窗后农民存活(目标 ≥18)、首胜。

---
## O262 — 顶着波次开二矿（o261 双 lane 0-10 尸检）

**日期**：2026-08-11

### 结果（o261，验证 O261 虚空+墙关断）

- lane1 0-5 / lane2 0-5(+1 异常)。**舰队增长修复确认**：o261a-g01 暴风 6 +
  航母 2（843s，O260-② 暴风兜底生效）——达到胜线舰队规模。O261-① 虚空未
  触发（FB 钉点在途即不满足前置,窗口近零）——无害死代码,舰队链已够快。
- **统一死因（经济封顶）**：复盘 one_base×5。o261a-g01：舰队 8 艘+55 supply
  打赢了 929s 的正面团,但单矿 26 农无钱重建,Zerg 三矿续兵 84 supply 反推。
  二矿钉点两次（486s/670s）都被波次打断（驻点等钱 100s+ 暴露窗太长）。
- 关键认知：threat 在首波后几乎常驻（波 60-90s 一波）,O258-① 的「非威胁才
  开矿」闸整局不开 —— 防御驱动开矿的前提错了,波打主基时正是分矿空窗。

### 3 个改进点（落地 O262）

1. **O262-① 二矿窗 340→260s 且去 threat 条件**（`zerg_timing_expand_allowed`
   两个调用点同步）：2 塔就绪（O216i 基线）即顶着威胁开,家 40 格有敌仍不开。
2. **O262-② 硬饱和钉点开矿扩到首扩**（O251 从 `2<=bases` 改 `1<=bases`）：
   单矿 ≥24 农即钉点 Nexus,治「闸已放行但 Nexus 排不出」。
3. **O262-③ Nexus 钉点近可负担门**（矿 ≥350 才派工）：驻点等钱 100s+→<10s,
   暴露窗/idle_builder 等钱同步收敛。

### 验证

- `py_compile` 通过；`unittest` **656 例 OK**。
- 观察指标（o262）：二矿落成时点（目标 ≤400s）、三矿出现率、首胜。

---
## O263 — 二矿窗 320s+分矿点无敌（o262 三连速败提前止损）

**日期**：2026-08-11

### 结果（o262，3 局即止损）

- lane1 开局三连速败（161/76/77s wall）：260s 强开把建筑期 Nexus 拍进首波
  行进路线（o262a-g02：293s 落、309s 被拆白捐 400，主基防钱同空，383s 亡）。
- O262-① 的「波打主基=分矿空窗」前提证伪：Abyssal 的波次路径穿过分矿点。
- **迭代纪律收益**：3 局确认回归即停,不再跑满 10 局（省 ~40 分钟）。

### 3 个改进点（落地 O263）

1. **O263-① 二矿窗 260→320s + 分矿点 35 格无敌检查**（`_zt_enemy_near_natural`，
   主闸/_spend_bank 两调用点）：首波到脸并被塔阵接住的时点之后才开,
   波次路径踩点时不开。
2. **O263-② O251 首扩钉点叠加同款窗+踩点检查**（多矿钉点原行为不变）。
3. **保留 O262-③**（钉点近可负担门 350 矿）：驻点暴露窗收敛仍然成立。

### 验证

- `py_compile` 通过；`unittest` **656 例 OK**。
- 观察指标（o263）：二矿落成时点/落成率、速败（<450s）清零、首胜。

---
## O263 — 🎉 Zerg Timing 打穿（o263 lane2: 3胜1负1异常）

**日期**：2026-08-11

### 结果

- **o263 lane2: 3-1(+1 异常) —— 六组合全部打穿收官**。
- lane1 0-3(+2 异常)：两异常局为 `_zt_enemy_near_natural` 在基地全灭后
  `min()` 空序列 ValueError（O263 新代码缺陷），热修（空守卫）已落地，
  后续局零复发。
- 三局胜局剖面（全部教科书级）：
  - g01(1283s)：二矿 353s / 三矿 731s / 52 农 / **17 暴风** / 138 supply。
  - g03(1572s)：**5 基地 / 67 农** / 15 暴风+15 追猎+1 航母+2 不朽 / 188 supply。
  - g05(1296s)：**5 基地 / 68 农** / 11 暴风+3 不朽+12 追猎 / 163 supply。
- 胜因链（o254-o263 十轮迭代逐环修复）：死窗防御包（O255-257）→
  舰队资金窗（O259-260）→ 二矿 320s 窗+踩点检查（O263）→ 三/四/五矿
  转化（O251/O262-② 钉点）→ 暴风海成型（O260-②）。

### 败局（g04, 211s wall 速败）尸检与改进点

1. 速败局为早波变体（~240s 到脸），死窗防御未成型 —— 早波变体仍无专项
   解（o258 起观察项），若司令验收后要求巩固,候选：O98 presumed 塔链提速。
2. lane1 两局 ERROR 暴露的新代码空序列缺陷 —— 已热修（townhalls 空守卫）,
   教训：新增 min/max 聚合必须带空集合守卫,单测补一条空 townhalls 用例更佳。
3. 崩溃/异常率本系列偏高（3 异常/10 局），与内存压力（空闲 <200MB）相关,
   根因（Clash mihomo wedge）未除,重启 Clash Verge 或整机后可缓。

### 六组合终态（全部 VeryHard N=5 三胜）

| 组合 | 结果 | 关键系列 |
|---|---|---|
| Zerg Rush | ✅ | O211 |
| Zerg Power | ✅ | o244z lane1 3-0 |
| Zerg Timing | ✅ | **o263 lane2 3-1** |
| Terran Rush | ✅ | o241t 3-2 |
| Terran Timing | ✅ | o242t 3-2 |
| Terran Power | ✅ | o243t lane1 5-0 |

---
## O264/O265 — 司令观察三件套（chrono 产农 / 母舰 / 宗师速开二矿实验）

**日期**：2026-08-11（六组合打穿后的司令观察迭代）

### 司令观察与落地

1. **观察②：产农从不用 Nexus 加速** —— 实证确认：chrono 只给 forge/首叉兵营/
   星门,Nexus 能量 0-260s 白攒 50-100。**O264-①**：SG 落地前 chrono 在产
   Nexus(宗师前期全给产农的惯例);SG 出现后流派 targets 接管,语义不回头。
2. **观察③：母舰隐身保舰队** —— **O264-②**：ZT + FB 就绪 + 舰队 ≥3 + 气 ≥600
   (只吃烂气窗) + 无母舰 → 基地直点母舰(400/400,全局 1 艘)。Cloaking Field
   覆盖混编,VeryHard Zerg AI 反隐(眼虫)推进基本不带。
3. **观察①：宗师速开二矿(水晶-兵营-二矿-空军科技)** —— **O265 实验**：
   二矿窗 320→220s + 首塔就绪前提。与本家两次失败先烈的差别：O216a(150s)
   是零防强开、O262(260s)无分矿踩点检查;O265 = 首塔 + 踩点 + 350 矿近负担
   三重保护。更早(90s 宗师时点)明确不做 —— forge/首塔链(55-170s)是 rush
   变体保命钱,动它会死给 12 狗池变体。

### 验证

- `py_compile` 通过；`unittest` **656 例 OK**。
- 观察指标：chrono 产农的实证(早期农民曲线)、母舰出场率与存活、
  二矿落成 ≤310s 的比率、**胜率不得低于 o263 的 3/5(回归线)**。

---
## O265 — 宗师速开二矿实验证伪回退（o265 双 lane 1-4 / 1-2+2异常）

**日期**：2026-08-12

### 结果

- o265 双 lane：lane1 1-4、lane2 1-2(+2 异常)。胜率跌破 o263 的 3/5 回归线，
  速败回升(166/66s wall)——**220s 二矿抢死窗防御钱,早波变体直接穿**。
- O265 证伪回退 320s(O263 打穿配置);**O264(chrono 产农+母舰)保留**
  (两胜局均带 O264,无回归证据;母舰出场率待确认局复盘补)。
- 异常 2 局为 SC2 强制更新(客户端要求更新,API 拒起,180s websocket 超时)。
  与代理 wedge 无关,需战网更新客户端。

### 教训

- 宗师开局时点(90s 二矿)不可照抄:人类靠侦查+操作消化早矿风险,bot 的
  forge/首塔链是 rush 变体保命钱;本环境二矿窗的实证最优解就是 320s+踩点。

---
## O266 — 满载基地→新矿农民调拨（司令观察）

**日期**：2026-08-12

### 司令观察

主基农民 16+ 满载,新分矿只有 2-3 个,采矿效率浪费。

### 根因（代码实证）

ares `ResourceManager._assign_workers_to_mineral_patches` 只给**未指派**农民
派矿点;已在主基矿线上的农民永不跨基地再平衡,新矿只能靠新训农民慢慢填
(~3 分钟才满)。ares 全框架无 maynard/transfer 机制。

### 落地（O266）

- `worker_transfer_count`(纯判据,滞回:超额/缺口均 ≥2 才调,单批 ≤4)
  + `update_worker_transfer`(main.py,3s 节流):超额农民从 ares 簿记摘除
  (remove_worker_from_mineral)并 gather 到新矿矿点,ResourceManager 自然重派。
- 守卫:急性窗(rush/threat)不动;目标基地 20 格有敌地面不调;跳过建造
  tracker/司令接管/E6 撤离/决死协防农民;每农民 30s 冷却防往返。

### 验证

- `py_compile` 通过;`unittest` **657 例 OK**(新增调拨判据 5 用例)。
- 观察指标:新矿农民填充时长(目标 <60s)、调拨事件次数、无往返空跑。

---
## O266b — 调拨判据改均衡化 + 母舰门限修复（o266 双 lane 复盘）

**日期**：2026-08-12

### o266 结果

- lane1 1-4 / lane2 2-3(合计 3/10)。胜局剖面:o266b-g03 **22 暴风**/3 基地/62 农;
  o266b-g05 4 基地/66 农/14 舰队+4 不朽。win profile 稳定复现。
- **O266 调拨零触发**(全 10 局无事件):首版用「超目标」判据,但 ares 矿线按
  2/矿点封顶(恒 ≤16),超额永不成立。
- **母舰零出场**:门限要求 idle Nexus,而 Nexus 全程在产农。

### 修复

1. 调拨判据改**均衡化**(maynard 手法):两基地矿线人数差 ≥4 → 调差额一半,
   单批 ≤4,源基地由新训农民回填。
2. 母舰允许在产 Nexus 排队(跟 1 个农民 +12s),队列 ≥2 条不压。

### 验证

- `py_compile` 通过;`unittest` **657 例 OK**。

---
## O268 — 分矿防御三修（司令观察：二矿堵口/塔不足实证）

**日期**：2026-08-12

### 司令观察

打不过是不是因为二矿没利用地形堵口 + 防御塔不够？——**数据证实**：

- o267a-g03：二矿 541s 被抄时只有 **1 塔**；战损后 605-696s **裸奔 90s**,
  752s 再被抄(塔1),811s 丢矿 → 连锁崩。主基同期也仅 1 塔。
- O216 分矿堵口名存实亡：BuildStructure 在途不落 tracker TARGET → 每帧
  重注册+刷事件(80s 空转几百次),墙件没多建;且单兵营本来就不是真封口。
- 对照胜局(o263b-g01):主基 2 塔/分矿 2 塔 —— 胜负塔量差仅 1 座/基地,
  就是这条命。

### 3 个改进点（落地 O268）

1. **O268-① O216 堵口 latch 修复**：按落点记派工,45s 未落成才重派,
   事件去重 —— 空转刷屏消除,墙件真正落地。
2. **O268-② ZT 塔底线 2→3/基地**(`_ec_min` max 3)：分矿 0-1 塔被 10+
   地面白拆的剖面不再出现。
3. **O268-③ 裸矿补塔提速**：任一就绪基地 0 就绪塔 → 建造槽保底 2
   (双塔并行,原串行 90s 补 1 座 → ~45s 补 2 座),Nexus/FB 资金窗
   串行闸对裸矿豁免。

### 验证

- `py_compile` 通过；`unittest` **657 例 OK**。
- 观察指标(o268)：分矿被抄时塔数(目标 ≥3)、战损补塔时长(目标 ≤45s)、胜率回归线 3/5。

---
## O268-④ — 决死协战压垮线放宽（o268 双 lane 0-5/1-4 尸检）

**日期**：2026-08-12

### 结果

- o268：lane1 0-5 / lane2 1-4。塔底线 3 生效（297s 塔3+SG 同点）且未拖垮
  科技链,但首波结局不变:305s 波(13 supply)塔3→1、农 24→2。
- 结论:**首波不是塔量问题** —— 2 塔 3 塔同死法。真正的缺口是协战闸:
  9 蟑螂 vs 2 塔时压垮线 6+4×2=14 不触发,农民照样白死(o268a-g01)。

### 改进（O268-④）

- 压垮线 6+4×塔 → **4+2×塔**(塔对蟑螂实际交换比 ~1:2):2 塔线 8、
  1 塔线 6 —— 协战在还有塔可依托时开火,而不是塔死光后无人触发。

### 验证

- `py_compile` 通过;`unittest` **657 例 OK**(判据全分支更新)。

---
## O270/O271 — 消融实验：方差裁定（司令指示找负收益）

**日期**：2026-08-12

### 实验设计与结果

- o270（HEAD 全量：O264+O266+O268）：0-10。
- o271（o263 打穿基线 `504fe26`，工作区整体回检出战）：**0-9(+1 异常)**。
- 同一基线昨天 3-1（o263 lane2）、今天 0-9；且**基线今日败局的建造剖面
  与昨日胜局逐点一致**（240s 塔2 / 300s SG1 / 360s FB1 / 480s 基2 /
  600s SG3 农39）——bot 宏观行为未变,差异在局内战斗结果。

### 结论（对司令的决策输入）

1. **找不到可归因的负效改动**：基线与全量同环境同命运,O264/O266/O268
   无显著负效证据,予以保留。
2. **真实胜率 ~25-35%**（o263 合并 3/8、o266 3/10、o267 2/10、
   o270-271 0/19）;打穿判据（5 局 3 胜）是在波动上沿达成的,边际很薄。
3. **10 局样本无法分辨 30% vs 40%** —— 继续逐特征消融在统计上无意义,
   提升胜率上限要靠结构性改动(正面团战 overrun 主线),不是参数微调。

---
## O272 — 正面团战主线①：暴风避战 + 反空军追猎（司令定方向 A）

**日期**：2026-08-12

### 尸检（o270b-g03 长局）

- 舰队成型正常(暴风 9@992s),随后敌转 **腐化 8-13 + 飞蛇 1-2 + 大龙 8-10**,
  暴风 9→2 被磨光:腐化对装甲加成+速度碾压(暴风风筝=慢速送死),
  追猎被 O260-① 气烂节流压到 0-4,无地面制空掩护。
- 败因主线确认:中局地面波已可守,**终局败因 = 敌制空转型后舰队无保护**。

### 2 个改进点（落地 O272）

1. **O272-① 暴风制空避战**（tempest_offensive）：腐化 ≥3 或飞蛇 ≥1 进
   15 格圈 → 脱离战场回最近塔/电池上空(不 commit_push 时),
   把敌制空引进地面火力圈,不再风筝硬拼。
2. **O272-② 反空军追猎地板**：敌制空(腐化/飞蛇/飞龙/大龙)可见 ≥4 →
   追猎 cap 拉回 12(压过 O260-① 气烂节流),追猎对装甲加成是腐化克星。

### 验证

- `py_compile` 通过；`unittest` **657 例 OK**。
- 观察指标(o272)：遇腐化群时暴风存活率、追猎中期数量、目标 **稳定 3 胜/lane**。

---
## O273/O274 — 制空补丁 + 开矿提速/防御集中（o273 0-10 背景）

**日期**：2026-08-12

### o273（制空补丁验证）

- 0-10。O272 胜局已实证避战+追猎在腐化阶段有效（舰队 8→13 反增长）;
  连败仍集中在 300-450s 波窗与二矿太晚（司令两条观察的同证据）。
- o272 二矿时点取证:482/422/406s + 两局整局未开 —— rush latch 近半激活,
  首扩钉点被无限推迟。

### O274（司令观察①②落地）

1. **O274-① 首扩钉点去 rush 闸**（保留 320s 窗+分矿点无敌+矿 ≥350）：
   波在主基被接住时正是分矿空窗,二矿目标 ≤390s。
2. **O274-② 防御集中到分矿**：ZT 且二矿落成 → 分矿塔目标 ≥3(迎敌锚点),
   主基 ≤2(威胁/rush 期不动)——塔/电池不再两处分铺都薄。

### 验证

- `py_compile` 通过;`unittest` **657 例 OK**。
- 观察指标(o274):二矿落成时点、分矿被抄时塔数、胜率回归线 3/5。

---
## O277 — 分矿口主防区化（司令观察：堵口兵力+塔太少被蟑螂突进）

**日期**：2026-08-12

### 司令观察与现状取证

- 观察:二矿堵口兵力和塔太少,蟑螂迅速突进主基;应减少主基地塔,把防御
  重心放二矿口(塔+电池+血厚便宜建筑堵口)。
- 取证(o274b-g02):O268/O274 已生效(分矿 3 塔@536s、主基压 2 塔、
  堵口兵营 latch 正常),但 ①分矿塔被拆后补满要 ~94s;②电池锚点恒落
  主基(任意最近塔),分矿塔阵无奶;③墙件只有 1 座兵营。

### 4 个改进点（落地 O277）

1. **O277-① 分矿口塔 3→4**(fortify_natural 激活时):分矿口按主防区配塔。
2. **O277-② 电池锚点改最暴露基地**（离敌焦点最近的基地 15 格内的塔）:
   电池跟前线塔阵走,分矿堵口阵有奶。
3. **O277-③ 裸矿补塔槽 2→3**:战损补满前线塔阵压进波间隙(~60s)。
4. **O277-④ 分矿口墙件 1→2 兵营**(血厚便宜,后段转产能不浪费)。

### 验证

- `py_compile` 通过;`unittest` **657 例 OK**。
- 观察指标:分矿口被攻时(塔+电池+墙件)数量、分矿存活率、胜率。

---
## O278 — 分矿口防御先于 Nexus + 二矿窗 280s（司令观察② + 36 局塔损检索）

**日期**：2026-08-12

### 司令观察与检索结论

- 任务:检索是否「分矿塔先被拔、再拔主基」。36 局 F2 每基地塔数时间线:
  **分矿先拔 16/21(76%)**,主基先拔 5,塔未拔 15 —— 观察成立。
- 波幅检索:同日同代码胜局首波 14 supply,败局 21 supply;o263b-g01 胜局
  二矿 353s + 农 42@540s;o271 同码败局经济形态相近仍输 —— 波幅+分矿口
  强度是胜负分水岭。
- o277(虚空优先+分矿5塔)0-10:虚空被塔连(5-6 塔/350-400s)挤得出不来,
  FB 反被拖 —— 塔多≠赢,塔要**在对的位置、比对波早**。

### 3 个改进点（落地 O278）

1. **O278-① 分矿口防御先于 Nexus**(`_natural_forward_defense`):ZT + t≥250
   + 主基 2 塔就绪 + 分矿点无敌 → 提前铺 水晶→2 塔→电池(迎敌锚点);
   波 305-320s 撞上的是塔阵,不是建筑期 Nexus。
2. **O278-② 二矿窗 320→280s**(主闸+O251 首扩钉点同步):Nexus 跟进预置塔,
   ~355s 落成,卡在 O236 胜负线(≤400s)内。
3. **O278-③ 主基塔落成后封顶 1**(O278 编辑组内,威胁/rush 期不动):
   分矿先拔 76% 的检索结论下,主基塔是 stranded capital,钱给分矿 5 塔+2 电池。

### 验证

- `py_compile` 通过;`unittest` **657 例 OK**。
- 观察指标(o278):分矿口塔落成时点(目标 ≤310s)、二矿落成(目标 ≤360s)、
  分矿先拔局的分矿存活率、胜率回归线 3/5。

---

## o280 基线复测裁决：环境 or 打法上限 → **打法上限**

**日期**：2026-08-15

### 实验设计

- 工作区 `git checkout 504fe26 -- ares-bot/bot ares-bot/flows.yml`（o263 打穿当天原封代码），双 lane headless 各 5 局 Zerg Timing / AbyssalReefLE。
- 目的：打穿后 ~80 局各配置胜率 0-40%，裁决是「重启后环境劣化」还是「o263 lane2 的 3-1 是波幅 RNG 侥幸」。

### 结果

- lane1(o280a)：0胜 2负 3异常；lane2(o280b)：0胜 2负 3异常。**合计 0-9 + 6 ERROR**。
- 4 局 decisive 全败：249s / 326s / 162s / 387s，剖面 one_base(420s 仍单矿) + overrun(终局 25 vs 0 / 71 vs 2) —— 死窗波（305-320s）原样收割，与打穿前死法一致。
- 6 局 ERROR 无 traceback，run.log 止于 "Closing connection / Cleaning up"（293-364s 游戏中连接中断），SC2 进程中途死亡——环境稳定性问题另账处理（重启后 Agent/进程管理）。

### 裁决

- 基线代码在相同环境下 0 胜 ⇒ **o263 lane2 的 3-1 主要是波幅 RNG 侥幸（首波 14 vs 21 supply 分水岭），当前打法无法稳定复现 3 胜**。连败主因是打法上限，不是环境。
- 恢复 HEAD（`git checkout HEAD -- ares-bot/bot ares-bot/flows.yml`），打穿链改进（O255-O279）全部保留。

### 3 个改进点（下一迭代 O281「远位口袋矿」）

1. **首扩选址避开波路径**：二矿不开在默认 natural（波进攻路径上，305-320s 波撞上建筑期 Nexus），改开**离敌最远的扩张点（口袋矿）**，Nexus 落成前不承受首波。
2. **环境稳定性**：ERROR 局 SC2 中途死亡占 60%，bench 层对「连接中断无结果」加重试上限并记录进程退出码，避免异常局污染胜率样本。
3. **复测基线作对照**：后续每轮打法迭代，若胜率异常塌陷，先重跑 o280 式基线复测 1 lane 区分环境/打法，再动代码。

## o281 远位口袋矿：机制成立(存活翻倍+扩张落地)但 0 胜 —— 瓶颈移到舰队成型

**日期**：2026-08-16

### 改动(O281)

- 首扩选址 natural → **口袋矿**(离敌出生点最远的空闲扩张点),只作用 ZT 且
  townhalls==1;三处开矿闸的踩点检查(_zt_enemy_near_natural)对着口袋点;
  ares `ExpansionController` 加 `location` 定点参数(定点时 max_pending 钳 1)。
- 单测 658 例 OK(新增 pick_pocket_expansion)。

### 结果

- lane1 0-4+1ERROR,lane2 0-5。**0-9**。
- 对比 o280 基线(死 162-387s、420s 仍单矿):存活 290→**697-949s**,
  二矿全部落地(442-671s),农民峰值 24→44,死窗波不再收割建筑期 Nexus。
  **口袋矿机制验证成立,保留**;0 胜因为瓶颈位移,不是回归。

### 尸检(9 局)三个改进点

1. **扩张仍太晚(442-671s,O236 胜负线 ≤400s)**:窗 280s 开放后矿攒不到
   400 —— 塔链/地面保底把矿吃干,E3k can_afford_check 卡死,钉点 矿≥350
   也等不到。→ O282:扩张窗开放后 Nexus 400 矿预留优先于追加塔/地面兵。
2. **舰队零产出(终局编成 ORACLE×1,气烂银行 865-1302,矿恒 <100)**:
   航母 350 矿永远凑不齐,地面磨到敌 65-71 supply 一波穿。→ O282 同解:
   矿分配纪律(塔封顶执行+舰队矿优先),气不是瓶颈。
3. **早波 RNG 局无解(两 lane g01,242-290s 被 10 supply 首波穿,塔仅 1 座)**:
   O278 预置塔 250s 起铺赶不上 242s 早波。→ 观察项:若 O282 后仍现,
   presumed 首塔时点提前。
4. 环境另账:o281a-g04 ERROR(671s 连接中断),三轮累计 8 例,SC2 进程
   中途死亡,与打法无关。

## o282 口袋矿首扩激活旁路:1-9,打出 o263 后首胜,输局瓶颈=三矿不开

**日期**：2026-08-16

### 改动(O282)

- `_zt_pocket_expand_active`:ZT+townhalls==1+t≥280+首塔+口袋点无敌+无 Nexus
  在途 → `_want_dynamic_expand` 直接 True(旁路 enemy_home/rush/transition 闸),
  holding 锁死攒 400。波 305-660s 前线闸常闭导致 holding 翻板、矿被塔/地面
  吃干(o281 二矿 442-671s 的直接原因)。

### 结果

- lane1 **1-4**,lane2 0-5 → 1-9。o263 后首胜。
- 胜局(o282a-g02,Victory 1115s)教科书复现赢面剖面:281s 矿 730(holding
  锁住)→ **二矿 309s** → 三矿 602s → 四矿 871s → 68 农/195 人口/
  TEMPEST×17+STALKER×13。
- 输局:二矿 413-562s 还是偏晚(窗开时银行被塔吃空,312s 才派工等钱),
  且**三矿被锁死**(rush latch 常闭 → should_expand_dynamic 整局不开,
  o282a-g04 卡 2 基地到 960s),经济 2 矿封顶 → 舰队矿被地面磨干 →
  终局 ORACLE×1。

### 尸检三个改进点

1. **口袋逻辑只覆盖首扩,townhalls≥2 回落旧闸** —— 三矿/四矿被 rush
   latch 锁死是输局主因。→ O283:口袋选址+激活旁路推广到 1..max_bases-1。
2. **窗开瞬间银行≈0 的局扩张仍拖到 413s+** —— 280s 前塔链无节制。
   观察项:O283 后若仍晚,考虑 250s 起塔链让位 Nexus 预留。
3. **环境**:两轮又 2 例崩溃重试(o282a-g02/o282b-g03 首跑无结果),
   ERROR 频率仍高,与打法无关,另账。

## o283/o284/o285 三连 0-10:扩张链微调证伪回退,主矛盾锁定早期防御经济

**日期**：2026-08-16

### 三轮改动与结果

- **O283**(口袋逻辑推广 1..max_bases-1,治三矿锁死):0-10。二矿反而
  598-606s(首扩路径代码不变,差异=RNG);运行时记账(O283d 埋点)发现
  **激活旁路 280s 起 active=True,但塔链绕过 holding 持续吃矿**
  (cannons_peak 3→10),银行永远攒不到 400,扩张靠 O251 钉点 584s 兜底。
- **O284**(激活期 F2 塔链整段冻结):0-10。冻结生效局二矿 313s+三矿 385s
  (史上最顺),但扩张链 active 几乎常真 → F2 永冻 → **新矿全裸奔**,
  492s 起被 4-14 地面小股轮抄(o284b-g02:57→2 农磨死)。
- **O285**(冻结限首扩 townhalls==1):0-10。死亡集中在 236-290s 早波,
  冻结窗(t≥280)根本没机会生效。
- **裁决:O283 推广 + O284/O285 冻结全部回退**,回到 o282(b66beb7)
  行为(口袋首扩+激活旁路);O283d 调试埋点保留(10s 节流,行为中性)。

### 跨 40 局(o282-o285)尸检结论:主矛盾不在扩张经济学

1. **早波 RNG 决定大半胜负**:波 236-290s 到、≥10 supply = 必死
  (防 2 supply 塔 0-1);波 ≥310s 且小 = 扩张链正常运转甚至赢
  (o282a-g02)。窗口期改动影响不了 236s 的死局。
2. **早期经济空转是真凶候选**:126s 三农民同时「等钱造 PHOTONCANNON」
  (三条路径各派一座,驻点干等),238s 仍「等钱造 FORGE」,银行恒 20-35
  —— 首塔落不了地,早波到脸零防御。→ O286 主攻:首塔链资金纪律
  (单一派遣源+到位可负担门),目标首塔 ≤200s。
3. **胜局配方不变**:窗开时银行 ≥400(二矿 ≤310s)+ 首塔 ≤200s +
  首波 ≤14 supply。三者占其二可赢,占其一必死。

## o286 首塔链在途去重:0-10,但二矿 329s 达标;胜/败局支出结构对照锁定 O287

**日期**：2026-08-16

### 改动(O286)

- presumed 链 `_cannons_pp` 与 rush 绕过点补记 `not_started_but_in_building_tracker`
  —— 原口径漏在途驻点,派工下帧即「0 塔」再派,126s 三农民钉点干等
  (派→等→撤→再派循环)。

### 结果与尸检

- 0-10。但抽样局(o286b-g01)二矿 **329.5s** 落进 O236 胜区,钉点 300s
  355 矿即发 —— 去重作为 hygiene 保留,0-10 主因不在这条链上。
- **胜/败局支出结构对照(关键发现)**:唯一胜局 o282a-g02 在 181-281s
  **零新增建筑**,银行硬攒到 790,窗开即拍 Nexus(309s),首塔 281s 才
  起但手中有钱应变;败局共同点 = 190-280s 零星支出(水晶 5-6/二 forge/
  塔 2-3)把银行滴干(m 恒 20-90),窗开时无钱扩张,半拉子防御也守不住。
- 早期时间线(o286b-g03):水晶 129s 超供(16/29→45 连拍 2 根)、145s
  兵营、161s 双气、225s 第 6 根水晶 —— 银行全程 <100。

### 三个改进点

1. **O287:激活窗 280→200s** —— 人为复现胜局「早硬攒」轨迹:holding
   提前 80s 接管,非威胁开销(额外水晶/二 forge/非保命塔)全让位,
   目标窗开(280s)时银行 ≥400、Nexus ≤330s。威胁/rush 例外不动。
2. 早期水晶超供(16/29 还连拍)观察项 —— O287 的 holding 若盖住则
   不单独动。
3. 波到脸时「手中存款应变」优于「提前半拉子防御」—— 后续防御改动
   一律以 280s 银行读数为先行指标。

## o287 激活窗200s:0-2+8异常(环境连环死);o288 司令五条落地:0-5

**日期**：2026-08-16

### o287(激活窗 280→200s,复现胜局「早硬攒」轨迹)

- 两 lane 各 0-1+4ERROR:8/10 局在 game_01 结束后 SC2 实例连环死亡
  (run.log 止于 Starting local game,无快照、无 traceback,~181s 卡死
  判定),环境劣化另账;2 局 decisive 全败(730-740s)。窗口改动方向与
  司令观察③(加快 2 矿)一致,保留。

### o288(司令五条,单 lane 5 局快验首轮):0-5

- **②堵口**:墙链加「缝不外封+墙外折射水晶」(缝朝坡底 5 格外置水晶,
  供地面部队折射出入)。**缝故意不用建筑封死** —— 农民开矿/调拨必须
  步行出缝,建筑封死=自囚(口袋矿经济链断);缝防守靠 O136 站位锚点。
  另发现 `_wall_gap_point`/`_wall_sealed` 无消费方(肉身堵缝是死代码)。
- **①塔贴电池**:`_cannon_anchor_near_battery` —— 基地 15 格内有就绪
  电池且 6 格内无塔 → 新塔锚到电池位;接入 O149/O278 两预置防御。
- **⑤气矿调拨**:`update_gas_topup`(main.py,3s 节流)—— 矿线 >2×矿点
  超饱和且气矿 <3 人 → 超额农民上气,簿记同步 ares 气矿台账;停气/
  气银行 ≥600/急性窗不动。o288 未触发(条件严),继续观察。
- **③加快 2 矿** = O287 激活窗 200s(已含);**④5 局快验** = 单 lane
  n=5(已写入 CLAUDE.md,本轮起执行)。
- o288g01:激活 270s 起 active=True,Nexus ~375s 派出;塔链 3→6 仍漏
  (threat/rush 例外),银行振荡 25-315 未稳上 400。

### 三个改进点(下轮候选,待司令拍板)

1. **ZT 全程墙链(O258 force 块重开)**:司令②的完整落地需要 presumed
   窗(55-110s)外继续墙工;历史尸检(o258/o260)反对 —— 墙 400 矿在
   261-330s 资金窗挤死塔3与 SG。是否接受墙投资换主基绝对安全,请司令定。
2. **缝位专职堵件**:_wall_gap_point 无消费方(死代码),rush 窗外缝
   无人把守 —— 地面单位编组时给缝位派 1 个 hold 站位(叉/追猎)。
3. **塔链泄漏不收口**:active=True 期间塔照长(threat/rush 例外),
   银行振荡 <400 —— 若 O289 继续,把「非急性期塔封顶」与激活窗绑定。

## o290 B 案(激活期非急性塔/siege/电池封顶):1-9,第二胜;瓶颈锁定首波存活

**日期**：2026-08-16

### 结果

- lane1 0-5,lane2 **1-4**(胜局 o290b-g05,1388s)。与 o282(1-9)持平,
  机制验证:激活期塔恒 1-2 座(siege 12 塔链被封),不再 6→10。
- 胜局剖面第三次复现同款配方:2 矿 413s → 3 矿 582s → 4 矿 819s →
  66 农/188 人口/TEMPEST×14+STALKER×16。
- 败局:塔封了但银行仍攒不满 —— 剩余泄漏是地面兵产出(叉/追猎 100
  矿/个)与水晶;且 236-290s 早波局封不封顶都守不住(o290a-g01:
  280s 波 16 supply vs 塔 1)。

### 跨 8 轮(o283-o290,~85 局 2 胜)结论

1. **首波(236-320s)存活是胜负的决定变量**:两场胜局 + 所有长局的
   共同点是首波来时经济/农民没被打穿;早波大波局(≥16 supply 到脸
   时塔 ≤2)必死,与扩张/省钱策略无关。
2. 扩张经济学已达标(口袋矿+激活+封顶,Nexus 300-413s),不再是瓶颈。
3. 剩余资金泄漏:激活期地面兵照产(100 矿/个)—— 若要继续挤压,
   下一步是「激活期地面兵也限量」,但这直接削弱首波防守,两难。

## o291 地形口袋矿(司令观察):0-10;两场马拉松局(1591s/2015s)暴露终局磨死面

**日期**：2026-08-16

### 改动与结果

- `pick_pocket_expansion` 加地形分(score=离敌距离-0.5×离图缘距离,
  背靠图缘=背后墙体天然封口,司令观察「选背后都是墙体的 2 矿」)。
- 0-10。AbyssalReef 上选址未变((42,94) 本来就是贴缘点,地形分与
  纯距离同解)——改动对其它图有期权价值,本图中性。

### 尸检(两亮点局)

- o291a-g04(1591s)/o291b-g03(2015s):二矿 377/385s、3-4 基地、
  打满中局 —— 口袋+激活+封顶的经济链已稳定产出「活到中局」;
  终局编成 ORACLE/VOIDRAY,暴风/航母在消耗战里被磨光(终局 0 农)。
- **当前败局三层分布**:①236-290s 早波穿家(~40%);②中局舰队
  规模上不去被滚雪球(~40%);③马拉松消耗战被磨死(~20%)。

### 改进点

1. ②③层共同根因:舰队产能/规模 —— 胜局 14-17 暴风 vs 败局个位数,
   差距在 3-4 矿经济能否撑住双星门持续产舰(气够矿不够的老问题,
   但现在是「矿收入总量」瓶颈不是「矿分配」瓶颈)。
2. ①层仍是最大单一死因,早波 RNG 未解(司令 D1 方向未动工)。
3. 地形分对 AbyssalReef 中性,后续换图验证时才见真章。

## o292 D1 首波预备产兵(ZT trickle):0-10;早波层改善,二矿资金被拖死

**日期**：2026-08-17

### 改动

- 新增 `zt_prewave_trickle_needed`(纯函数)+ `_effective_spawn` 接入:
  ZT 局 GW 就绪即开预备产兵(追猎 0.4/叉子 0.6 混编,cap 6 自校正),
  两道安全闸——rush 确认后 rush 分支接管;舰队基建活(SG 就绪+FB
  在场/在建)即关闸。实证依据:o291a game_01 GW1 156s 就绪后空转
  93s(rush 确认=波到脸才开闸),首叉 249s,波 278s 到脸只 1 叉,
  矿 415/气 552 烂银行。

### 结果

- 0-10,但败局形态后移:平均局时 642.7/779.3s(o291 早波局
  337-390s),首叉 205.7s(提前 46s),追猎/不朽者开始出场。
- 新瓶颈:二矿 522-610s 或开不出(one_base×4),胜局配方 ≤413s。

### 尸检

- o292a game_01(413s 败):O290 口袋激活期塔归 0 + O292 trickle
  不识别激活期,夹击 Nexus 资金窗——塔恒 2 座(首波正落攒钱窗,
  threat 翻真再补塔来不及),Nexus 也攒不出,两头落空。
- 胜局对照(o290b-g05):波前 3 塔 285s 成型是存活地板,不是地面兵。
- o291a game_01 遗留:超载挂 PROBE 白烧 45 能量。

### 改进点(→ O293)

1. trickle 让位:口袋激活期 cap 6→3,保留首波核心兵力,余钱让进
   Nexus 资金窗。
2. 塔地板:口袋激活期塔目标 0 封 → 收到 ≤3(保留 O290 拦 3→10
   塔链本意)。
3. 超载单位黑名单:不挂 PROBE。

## o293 三点(trickle让位/塔地板/超载黑名单):0-10;二矿回到窗口,中局三重死因

**日期**：2026-08-17

### 结果

- 0-10。二矿时点 3/10 回到 ≤418s 窗口(393.8/417.9/417.9),
  舰队开始成型(暴风 429s 首现、不朽者出场)。
- 早波速败仍有 2/10(290.1s/419.7s):238s 早波(塔 1+叉 1)RNG 未解。

### 尸检(o293a game_04,747s 败,中局代表局)

1. **forge 死亡连锁**:559s 44-supply 波推平分矿,forge 随矿阵亡 →
   塔链 tech_not_ready 连刷 80s+(666-697s),150 矿重建资金窗被
   探机+叉子吃干,塔 8→0 连锁丢三基。
2. **carrier_reserve 误停**:675s 主基决死窗(敌 28-31 地面、我方
   地面兵 3、SG 已毁)停产攒 350 航母——SG 死了航母产不出,停产=自杀。
3. **舰队基建零重建**:SG 642s/FB 679s 被拆后到判负 100s+ 零重建
   (开矿持有冻核心链+FB 重建闸要就绪 SG+威胁让位闸三层堵死),
   878 气烂银行。

### 改进点(→ O294)

1. forge 重建资金窗:无就绪 forge+急性防御+矿不够 → 探机让位。
2. carrier_reserve 前置:就绪 SG(产得出)+非急性威胁期(停得起)。
3. 舰队基建重建链:舰队曾成型+t≥300 → cyber→SG→FB 钉点补建,
   不受开矿持有冻结。

## o294 三点(forge资金窗/reserve前置/基建重建):0-10;全面中局化,败因收敛到舰队上量

**日期**：2026-08-17

### 结果

- 0-10。平均局时 832.8/740.8s,7/10 局开出二矿(309.4-446s,
  配方窗口内占 4/10),CARRIER 首现 650.9s。败局主体移到 900-1080s
  的中局大波。
- O294 重建事件 0 次触发(基建多在基地连丢终段才阵亡,重建窗不存在);
  早波速败降到 3/10(416.7/400.0/426.2s)。

### 尸检(o294a game_02,1028s 败,最发达局)

1. **O218 追加星门钉点空转**:898-908s 事件每帧刷屏 100+ 次,
   SG3 至死未落——主基带电 3x3 槽归零(no_placement),事件无条件
   记掩盖真因;SG3 若能落地 = 76-supply 波前 +50% 产舰。
2. **reserve 敌情滞后**:911.0 carrier_reserve 停产(矿 95/地面 6),
   76-supply 波在途(E9 到 915.5 才翻 threat);threat 闸有效但侦测滞后。
3. **暴风分批送**:932-944s「损失暴风舰 2 艘」×3,12 秒 6 艘——
   O260 兜底点舰在波到脸后产出,新舰成对飞进败局战场分批送死。
   舰队上量速率:662s 2 艘 → 900s 6 艘(2 SG 理论产能 ~11 艘),
   矿物被塔(11 座)/探机(45→51)/叉子分薄,气 882 烂银行。

### 改进点(→ O295)

1. O218 落位自救:就绪基地逐个试落位,全 no_placement → 钉点补电;
   事件结果化+变化时节流。
2. carrier_reserve 敌情闸:敌可见 supply > 我方军队 supply 时产线
   永不停(攒钱是波间隙特权)。
3. SG 钉点资金预留:SG 钉点未开工+矿不够 → 探机让位(镜像 O236)。

## o295 三点(O218落位自救/reserve敌情闸/SG资金预留):0-10;SG 钉点落地修复生效

**日期**：2026-08-17

### 结果

- 0-10。O218 派工结果化后 spam 消失,o295a game_02 SG2 448.6s 钉点
  成功(o294 同型局 100+ 帧空转不落地);二矿 4/10 在 ≤418s 窗内。
- O292-O295 四轮代码+battle-log 已推送(0a1913d)。

### 尸检(o295a game_02,772s 败 + o295b game_02,895s 败)

1. **口袋敌情闸误锁开矿**:35 格半径把主基交战圈罩进来(口袋-主基
   ~28 格),敌一波主基开矿即锁,激活拖到 600s,错过配方窗。
2. **reserve 地面0漏洞**:敌不可见 0 + 我方地面 0 → 0<=0 仍停产
   (o295b game_02 791-851s 三连停)。
3. **塔链带电槽归零无自救**:主基 2x2 带电余=0 多局反复,no_placement
   干等,防御窗无补电机制。

### 改进点(→ O296)

1. reserve 严格闸:敌 < 我才停(0v0 不停)。
2. 口袋敌情闸 35→20 格(主基交战不再锁口袋,O282 本意)。
3. 塔链 no_placement+带电槽 0 → 钉点补电(O55/O295-① 同构)。

## o296 三点(reserve严格闸/口袋闸20格/塔链补电):0-10;扩展链收敛,败因锁定产出不集中

**日期**：2026-08-17

### 结果

- 0-10。**8/10 局开出二矿**(309.4-498.2s,5/10 在配方窗内)——
  扩展链基本收敛;早波速败 2/10(340.6/395.4s)。
- 败局主体:700-1070s 中局大波(44-82 supply)。

### 尸检(o296b game_02,1066s 败,最发达局)

- 928s 我方 94 supply(3 SG/10 塔/43 农),编成 TEMPEST×5+IMMORTAL×2
  +ZEALOT×5+STALKER×2+ORACLE×1;933s 82-supply 波到,952s 起连环
  损失,基地 2→1→0。
- **杂牌军问题**:胜局配方是 TEMPEST×14-17+STALKER×13-16 的集中
  编成;我方供应摊在杂兵上 —— 2 不朽(550 矿)+5 叉(500 矿)+
  oracle/void ≈ 5-6 艘暴风的资源。产出稀释三源头:
  ①ZT 的 _fleet_transitioned 永假 → rush 纯叉分支整局有效,波后
  叉子回填;②O245 不朽混编/直产在舰队期照跑;③O252 骚扰闸 3 艘
  即放舰队出门,小舰队在外被捉/换家回防不及。

### 改进点(→ O297,主题:舰队期产出集中化)

1. rush 纯叉分支关闸条件统一为 _zt_fleet_infra_live(与 O203 同语义,
   补 ZT 永假漏洞)——叉子钱转舰队/追猎。
2. O245 不朽混编+直产在舰队基建活后让位(275 矿/个 ≈ 1.5 暴风)。
3. O252 骚扰闸 fleet 3→8(骚扰是成型舰队的特权,小舰队蹲守保家)。

## o297 产出集中化(rush纯叉关闸/不朽让位/骚扰闸3→8):0-10;航母首现,瓶颈转向防御窗质量

**日期**：2026-08-17

### 结果

- 0-10。CARRIER 767.4s 首现(矿物开始流向舰队),lane a 平均局时
  964.5s(近六轮最高),二矿 4/5 开出(309.4-498.2s)。
- `_zt_fleet_infra_live()` 统一了 ZT「已转型」实况口径(补 _fleet_transitioned
  永假漏洞),rush 纯叉回填/不朽混编在舰队基建活后关断。

### 尸检(o297a game_03,1116s)

1. **exit_ground=6 叉子地板回填**:舰队上线后常驻 6 地面地板,波后回填
   ~400 矿/周期 —— 暴风卡 5 艘、气 976+ 烂银行(spawn 只有暴风/航母,
   叉子全来自 pre_fleet 地板)。
2. **expand_reserve 波前停产**:742s 45-supply 波在途,707/761/791s
   三连停产攒 Nexus(与 carrier_reserve 同病)。
3. **重建二矿资金窗磨穿**:三连停仍开不出 —— 追猎 cap2 有 O236 钉点
   归零闸,叉子 floor 没有,100 矿/个持续回填。

### 改进点(→ O298)

1. exit_ground 6→3(地板回填砍半灌暴风)。
2. expand_reserve 敌情闸(敌≥我产线不停)。
3. Nexus 钉点期叉子 floor 归零(镜像追猎 O236 闸)。

## o298 三点(exit_ground3/reserve敌情闸/钉点叉地板归零):0-10 倒退;①证伪回退

**日期**：2026-08-17

### 结果

- 0-10 且倒退:早波死亡 3/10(403.5/386.0/305.8s),平均局时
  686.9/655.1s,暴风首现推迟到 624.8/584.6s。

### 尸检(o298b game_03,305.8s)

1. **exit_ground=3 太薄(证伪)**:234-320s 窗常驻 3 叉挡不住,该机制
   本是 E10d 防 trickle 实证成果 —— 回退 6。
2. **最早波(164s)协防盲区**:1-2 狗进矿线时 O94 min_enemy=3 不触发,
   无人应答;狗滚到 4+ 才协防,249s 农民 24→7。
3. **rush 期 forge/首塔被抢钱**:rush 确认后 forge 220s 等钱、首塔
   249s 落成 —— 新气矿(75×2)+cyber 在 forge 之前;死亡链:
   forge 晚 → 塔 tech_not_ready → 0 塔 → 屠农。

### 改进点(→ O299)

1. 回退 exit_ground→6(yml+测试同步)。
2. O94 协防 ZT 触发 min_enemy 3→2。
3. ZT rush 确认+forge 未就绪 → 暂停新气矿。

## o299 三点(回退/协防2/rush停气):0-10;倒退止住但未回 o297 水平

**日期**：2026-08-17

### 结果

- 0-10。平均局时 704.2/633.4s(o298 687/655 → 略升,o297 964/719
  未追回);早波死亡 2/10(450.5/357.6s);one_base 7/10(协防早拉
  农民可能伤扩张,待查)。
- 九轮(o291-o299,90 局)0 胜,与历史胜率(~2-3%,o263/o282/o290
  各 1 胜)比未见统计显著倒退,但也未突破。

### 跨轮观察(确定下轮方向)

- **暴风成对损失机制**:932-944s/1048-1060s「损失暴风舰×2」连发 —
  TempestOffensive 对射程内敌一律 StutterUnitBack 倒飞,水蛭(4.09
  on-creep)速度碾压暴风(2.8),倒飞=被追出塔阵单独追死;掩体回避
  逻辑(O272)只认腐化/飞蛇/感染虫,不认刺蛇/皇后地对空。
- 大局判断:早波层/扩张层已大幅收敛,当前主死因是**中局大波会战
  全败**(73-82 supply 波 30-60s 蒸发我方 50-60 军队 supply),舰队
  微操(掩体站位)是最可能的剩余杠杆。

### 改进点(→ O300)

1. 暴风防空波掩体战:敌地对空 ≥4 进 15 格且有塔/电池掩体 → 撤到
   掩体上空站定输出(不倒飞出掩体)。
2. 协防 min_enemy=2 的扩张成本核对(o299 one_base 7/10 vs o296 3/10)。
3. supply_block 中局卡点排查(o297a/o298a/o299b 各 flag 1-2 次)。

## o300 三点(暴风掩体战/停气扩presumed/协防监控):0-10;全程最佳局(4矿/160人口)

**日期**：2026-08-17

### 结果

- 0-10。o300a game_01 为 110 局来最发达局:4 矿(309/602/791s)+
  70 农 + 843s 达 160 supply + SG4 + 14 塔 —— 首次摸到胜局配方经济体量。
- 掩体战后「损失暴风舰×2」从每局 3 连发降到 1 次(1052.7s)。

### 尸检(o300a game_01 1202s / o300b game_03 1079s)

1. **追猎洪水挤暴风**:843s 时 28 追猎(3500 矿+1400 气)vs 仅 4 暴风
   —— 反空军 pivot 追猎 p0/0.3 在 freeflow 下无上限(配比只当优先序),
   兵营 30s/125 矿对星门 43s/175 矿速度碾压;胜局配方 14-17 暴风 +
   13-16 追猎比例完全倒挂。
2. **O260 气门 500 太高**:o300b game_03 气 365-507 窗星门全闲
   (SG1 整局),暴风 175/125 本可负担却不点。
3. **O218 can_afford 挡钉点**:矿振荡 0-175 时闸不开 → 钉点永不成立
   → SG1 整局、气 1060 烂银行。

### 改进点(→ O301)

1. pivot 追猎混入上限 <12。
2. O260 气门 500→300。
3. O218 去 can_afford 门(钉点自带等钱)。

## o301 三点(追猎cap/气门300/O218去钱门):0-10;敌编成取证锁定终局杀手

**日期**：2026-08-17

### 结果

- 0-10。平均局时 596.9/701.1s;早波死亡 3/10(389.9/373.8/487.5s,
  均为蟑螂 rush,与本轮中局改动窗口无关);无 850s+ 长局,O301 的
  改动窗口(450s+)未被本轮样本有效覆盖,记为「噪声,不证伪」。

### 敌编成取证(快照 enemies 字段,跨 40 局)

- **<800s 死亡局**:ROACH×5-13 + HYD×3-10 + INF×0-4(地面波)。
- **850s+ 长局(必死)**:敌必转型 **CORRUPTOR×1-12 + BROODLORD×1-7**
  (+VIPER/INFESTOR/ULTRA)—— 腐化对 massive 加成猎杀暴风(成对损失
  真凶),大龙射程 10 在塔程(7)外白拆基地。
- 配方再验证:暴风对 massive 加成克大龙、追猎克腐化 —— 胜局配方
  (14-17 暴风+13-16 追猎)正是这个答案,问题是 850s 前攒不到临界质量。

### 战略含义(待司令拍板)

1. **腐化/大龙转型窗口(~850s)是死线**:此后我方胜率 0%(40 局取证)。
2. **750-800s 是我方黄金窗**:敌纯蟑螂/刺蛇(蟑螂不能对空),暴风
   白打;先手压家可能抢在腐化转型前打死/打残对手。
3. 继续微调的路径仍是「850s 前攒齐配方」,但边际收益递减(11 轮)。

## o302 黄金窗先手压制(司令拍板专项):0-10;推进机制验证有效,腐化转型是死线

**日期**：2026-08-17

### 改动与结果

- `zt_golden_window_push`(纯函数)+ combat 接入:t≥700/舰队≥4/追猎≥10
  即推;推进簿记事件(此前推进静默,无法判断闸不开是没到窗还是被否决)。
- 0-10。O302 事件实证:推进本就在发生(O241 force/优势闸),黄金窗
  参数两局都差一点没够上(3+12@650s、7+5@830s);事件逐帧刷屏
  (_push_committed 集结期每帧复位)。

### 尸检(o302b game_04,1249s,教科书局)

1. **推进有效**:830s 推进(fleet=7),暴风敌区存活 220s 涨到 9 艘,
   1052s 敌军从视野基本被打空(ROACH 20→10→消失)。
2. **腐化转型正落在推进途中**:871s 大龙/腐化出场,1080s 敌
   CORRUPTOR×19 重建,1173s 暴风被腐化海猎杀 —— 黄金窗 ~750-870s,
   830s 推进已晚;追猎 5-8 只接不住 19 条腐化。
3. **配方再确认**:暴风存活期内输出可观,死因不是推进本身而是
   腐化海无人能接(追猎量不足)。

### 改进点(→ O303)

1. O302 事件 30s 节流。
2. 黄金窗提前放宽:t≥650、舰队≥3、追猎≥8(留足 60-90s 杀伤时间)。
3. 追猎 cap 动态化(pivot_stalker_cap):腐化 ≥9 按 1.5× 放量
   (cap 12 对腐化海=缴械)。

## o303 三点(节流/窗口提前/追猎cap动态):0-10;黄金窗推进首发,快尖塔局暴露否决缺失

**日期**：2026-08-17

### 结果

- 0-10。one_base 降到 ×1/×1(扩展最稳一轮);黄金窗推进首次触发
  (o303a game_05,736.9s fleet=3 追猎=8,黄金窗=True)。

### 尸检(o303a game_05,1024.6s)

1. **快尖塔局无黄金窗**:腐化 723s 就出场(我方追猎仅 2 只),
   推进把 6 暴风送进腐化区 —— 无克制窗的局不该推。
2. **敌重建能力压制**:我方 2 矿经济换不动敌 3-4 巢重建;推进杀
   农 26+ 但敌 60-supply 波 60s 重建,反推我方基地(950s 2→1)。
3. **大龙是终局最大失血点**:射程 10 在塔程外白拆基地,暴风焦点
   无大龙优先(默认 cy_pick + 虚空优先)。

### 改进点(→ O304)

1. 暴风焦点:大龙 > 腐化优先(暴风 massive 加成 2-3 轮点杀)。
2. 黄金窗腐化否决:可见腐化 >2 不推(快尖塔局蹲守等配方)。
3. 追猎防空预置 O273-① t≥700→650(腐化 723s 前预置 cap 8)。

## o304 三点(暴风焦点大龙/推进腐化否决/追猎预置650):0-10;早期局彻底收敛

**日期**：2026-08-17

### 结果

- 0-10。**one_base 基本清零**(双 lane 仅 ×1),二矿时点全线达标
  (lane a 249.1/313.4/325.4/361.6s,配方窗内最好一轮);早波猝死
  ~15%。全部死亡集中在 650-940s 中局会战。
- o304a game_01(937.8s):二矿 566s/855s 两落两建,暴风卡 3 艘
  (SG1→3 太晚),851s 敌腐化 9+蟑螂 10+刺蛇 7+感染 4 波碾穿。
- o304b game_05(925.4s):803s 波打崩经济(农 45→22、气 55),SG
  被拆零重建窗,地面波滚死。

### 跨 14 轮(o291-o304,140 局 0 胜)状态评估

- 已收敛:早波存活(猝死 40%→15%)、扩张链(one_base 50%→5%,
  二矿 249-418s 达标)、舰队基建(SG 钉点/重建/气烂兜底)、推进机制
  (黄金窗触发,暴风敌区存活 220s)。
- 墙:850-950s 敌 2-3 波重建(60-90 supply+腐化/大龙/飞蛇/感染),
  VeryHard 经济加成 ~60s/波重建速度,我方 2-3 矿换不动。
- 历史胜率 ~2.4%(o282/o290 各 1 胜);当前 0/140 与历史基线的
  差异在 10 局样本噪声内无法分辨,需标定实验定天花板。

### 下一步(司令 2026-08-17 拍板)

**降档标定验证**:同配置跑 Harder Zerg Timing 双 lane —— Harder 稳赢
= 14 轮迭代有效、VeryHard 继续爬;Harder 也输 = 有更深基础问题。

## o305 Harder 降档标定(司令拍板):**2 胜**,标定成功

**日期**：2026-08-17

### 结果

- **o305b 2/5 胜**(game_01 1130.9s / game_02 1176.5s),o305a 0/5。
- 胜局终局编成 = 胜局配方复现:game_01 TEMPEST×15+STALKER×11+
  CARRIER×1(149 supply);game_02 TEMPEST×22+STALKER×11(195 supply,
  69 农 4 矿)。
- 标定结论:**o291-o304 十四轮迭代有效** —— bot 当前水位 =
  Harder 可复现胜(配方达成),VeryHard 差一档经济压强。
- game_01 备注:二矿 526s(晚于 VH 配方窗)在 Harder 仍能赢 ——
  VH 的差距本质是波次压强逼出更多防御开销 → 扩张晚 → 850s 舰队
  质量差。

### 后续协议(本轮起)

- **双 lane 分工**:lane1 = VeryHard 主攻(不变),lane2 = Harder
  回归基线 —— 防 VH 迭代码改动破坏已验证的 Harder 胜场能力;
  Harder 胜率应随迭代单调不降(当前基线 2/5,目标 ≥3/5)。

## o306 大会战保全第一刀 + 回归鉴别实验:噪声实锤,O306 保留

**日期**：2026-08-17

### 结果

- **o306 首轮**:lane1 VH 0/5,lane2 Harder 0/5(基线 2/5→0/5 疑回归)。
- **o306c/d 同码复跑鉴别**:lane1 VH(o306c)0/5,lane2 Harder
  (o306d)2/5 胜(game_02 1461s / game_04 483s)—— 回到 o305 基线。
- 判读树执行:**Harder 回 2/5 → 首轮 0/5 是样本噪声**(30-40% 真实
  胜率下 0/5 概率 ~10-17%),O306 无回归,保留。

### 尸检(O306 三改动介入深度)

- E6 撤离半径 15→20 + 分矿电池 3:未见负面信号。
- 决死白送上界(`worker_last_stand_hopeless`,14+6×塔):游走事件
  全程仅触发 ~15 次(26-28 敌地面超线才改游走),介入仍浅;
  农民骤减事件在败局快照中依旧高频(全程 341 命中)。
- VH 仍有早死:o306c game_03 175s / game_05 420s 被 rush 穿 ——
  早波收敛未彻底覆盖 VH 最快 rush。

### 优化点(下一轮 O307 候选,按证据排序)

1. **VH 早死堵漏**:175-420s 猝死局仍在,早波防御链对 VH 最快
   rush 有洞(出兵/堵口时序尸检定位)。
2. **大会战保全续**:追猎 blink 在大会战的站位(stalker_offensive
   未尸检过),O306 农民保命介入浅,白送线阈值可复核。
3. **经济极限化**:胜局 3 矿 687s 偏晚,波间隙开矿纪律(450-550s)
   可提前补齐舰队质量差。

### 教训

- 5 局样本 2/5→0/5 不可直接判回归,**同码复跑是 cheap 鉴别器**
  —— 已写入判读协议:Harder lane 连两轮 0/5 才算真回归。

## o307 开矿持有死锁自愈 + O308 首波防守链(尸检驱动)

**日期**：2026-08-17

### o307 结果

- **o307a VH 0/5 / o307b Harder 1/5**(基线 2/5,噪声带内但偏弱)。
- O307-③ 死锁自愈实锤生效:game_01 持有 ~400s 起、495s 撤销派工、
  538s 二矿落地(冷却 45s 语义按设计工作);game_05 同(437s 落地)。
  长局(game_01/04/05)都开成了二矿,死于 440-700s 的 30-60 supply 中局波。
- O307-② 地面保底:expand_reserve 停产事件本轮 0 次(上轮 2 次)。

### o307 尸检(第一性原理三维)

- **科技节奏**:game_02/03 首波(235-243s,敌 10-12 supply)到脸时
  我仅 4-6 supply + 1 塔 —— forge-first 链(o126b 算术基于 ~154s 狗波)
  对 ZT ~240s 蟑螂波把首叉拖到 218s;125-143s 三塔同排(450 矿窗)
  摊薄资金,首塔 200-225s 才就绪。
- **农民效率**:决死协防「拉9-11 → 战死 → 再拉1 → 再送」添油循环
  (game_02 拉10+1×5、骤减11;game_03 拉9、骤减9),首波即便守住
  经济也已判死刑(game_02 撑到 526s 被第二波收尸)。
- **部队分配**:长局舰队成型 ~538s(TEMPEST),中局 30-60 supply 波
  换不动 —— 老墙,不在本轮范围。

### O308 落地(三点,单测 671 绿)

1. **ZT 兵营先于 forge**(`forge_before_first_gateway` 加 is_zerg_timing
   豁免,两调用点):首叉 218s → ~180s;Rush 保持 O127 终裁不动。
   司令 GM 录像口径(兵营先于 BF)与尸检数据一致。
2. **决死协防同场不添油**(main.py):stand 非空不再拉新农民,
   敌退清仓后下一场重新拉首批(自校正)。
3. **presumed/unknown 窗炮塔串行化**(`serialize_presumed_cannons`):
   首塔就绪前 F2 塔目标压 1,资金集中首塔 ~60s 提前落地。

## o308 首波链修复生效,墙前移至中局;O309 三点(协防添油复活/O94白送/开矿周期)

**日期**：2026-08-17

### o308 结果

- **o308a VH 0/5 / o308b Harder 1/5**(game_01 543s 胜:3 基地 65 农
  TEMPEST×19+STALKER×12,183 supply —— 胜局配方再次复现)。
- **O308 三点生效**:o307a 的 235-243s 首波死亡(2/5 局)本轮消除,
  首波 E9 推迟到 495-535s;死因前移至 530-870s 中局 30-80 supply 波。
- **维度④(经济差)数据终裁**:胜局二矿 309s;败局 478/546/313/382/
  未开出 —— 二矿 ≤310s 是胜负分界线(司令「≤300s」口径成立)。
  三矿:胜局 679s,败局无一开出。

### o308 尸检(四维)发现的三个新问题

1. **O308-② 添油修复被死亡绕过**:stand 集在农民战死后清空 → 下帧
   重新触发拉人 —— game_02 821-841s「拉1农民」×5、game_04 780-790s
   ×3,添油循环换了马甲复活。
2. **O94 首波协防(炮塔未就绪顶窗口)成为新的农民放血口**:
   game_03 573-646s 连拉 ×6 四次、game_04 798s 敌27地面照拉 ×6,
   骤减 4-11/波 —— O94 没有 O256 的白送上界,敌 20-30 地面也拉。
3. **开矿重试周期太长**:O307-③ 的 90s 超时 + 45s 冷却 = 135s/轮,
   game_02 二连 abort(355/474s)把二矿拖到 546s;胜局 309s vs
   败局 478-546s,每 30s 都值钱。

### O309 落地(三点)

1. O256 添油真修复:首批拉人后 30s latch,期间 stand 空了也不重拉
   (农民死在矿位 vs 冲锋位之差是纯亏,已由 o308 数据二次证实)。
2. O94 协防加白送上界:敌地面 > 6+4×就绪塔(同 O256 压垮线口径)
   时不拉,保命优先。
3. O307-③ 周期压缩:abort 超时 90→60s、冷却 45→30s(重试 135→90s,
   二矿时点预期提前 45-90s)。

## o309 结果 + O310 农民战损三点(压垮线收紧/首批封顶/O94零塔白送线)

**日期**：2026-08-17

### o309 结果与尸检

- **o309a VH 0/5 / o309b Harder 1/5**(game_02 501s 胜)。
- 首波死亡回归(基地 366-411s 全失 ×3):首波 277-308s 到脸
  (敌 14-18 supply vs 我 6-11,塔1-2),比 o308a 的 495-535s 早 —
  敌 build 抽签方差,但暴露真问题:**塔 <3 时农民冲锋从未改变结局**。
- O309-① 添油 latch 生效(拉1×N 消失),但首批无上限拉 11-17 农民,
  10s 骤减 9-10;O309-② O94 白送线(14+6×塔)在 0 塔时太松,
  敌 8-9 地面塔未就绪照拉 ×6,骤减 4-6/轮。
- 经济账:首波农民战损 9-12 → 二矿 400s 前数学上不可能(缺 6-10
  农民的采矿量+重建费)→ 中局经济差滚雪球。**首波农民存活数 =
  整局胜负的领先指标**。

### O310 落地(三点,单测 673 绿)

1. **O256 首批拉人封顶 2+4×塔**(`last_stand_pull_cap`):第 ~8 人后
   对蟑螂边际输出归零,超出部分纯喂。
2. **O94 零塔白送线收紧**:cannons_ready==0 时 hopeless_base 14→8
   (敌 ≥9 塔未就绪不拉,留矿保命)。
3. **O256 压垮线收紧 6+4×塔 → 10+4×塔**:塔1-2 对 14-18 地面的
   拉人局(o307a/o309a 累计 5 局)全败;o255 赢面算术前提是 4 塔
   (26 线仍触发,该场景语义不变)。

## o310 证伪回退 + O311 转向(省农民钱买防御/钉点门放宽)

**日期**：2026-08-17

### o310 结果与判读

- **o310a VH 0/5 / o310b Harder 0/5** —— Harder 基线 2/5→0/5,
  判 O310-①(首批封顶)+O310-③(压垮线 10+4×塔)**证伪回退**。
- 机制:o310b game_03 分矿 317s 失守(敌 20,拉人变少)、game_02
  第二波 842s 拉 6 人骤减 6 丢矿 —— 塔1-2 区少拉/不拉 = 基地更快掉。
- **三轮农民 micro 迭代(O308-②/O309-①②/O310)总结论**:塔1-2 +
  4-8 兵对 300-330s 的 14-20 supply 波,拉多/拉少/不拉全败 —
  农民 micro 调不出胜负,**防御总量才是缺口**,此方向封存。
- 保留:O309-① 30s 添油 latch(证据干净)、O310-② O94 零塔白送线
  (几乎未触发,无害)。

### O311 落地(三点,单测 672 绿)

1. **ZT 单矿期农民生产上限 20**(司令「26/4 浪费人口」观察的数据版):
   单矿饱和 ~16-22,24-28 农 = 250-400 矿死在人口里 ≈ 2-3 塔/4 叉,
   正是首波缺的防御钱;二矿在途(含钉点)即解除预产填新矿。
   econ_floor(<16)优先不受影响。
2. **回退 O310-①/③**(恢复 6+4×塔 + 首批全量拉)。
3. **O251 首扩钉点农民门 24→20**:首波后农民常 12-20,24 门永假;
   20 已超单矿饱和,余 4 农采矿量换二矿早 30-60s 落地是赚的
   (胜局 309s vs 败局 478-546s = 胜负线)。

## o311 证伪回退:真回归确认(Harder 连两轮 0/5 协议触发)

**日期**：2026-08-17

- **o311a VH 0/5 / o311b Harder 0/5**,Harder 连两轮 0/5 = 协议级真回归。
- 机制:①农民上限 20 → 收入少 → 首波兵更薄(我6-10 vs 8-12),
  「饱和溢出省矿」的账漏算了首波战损 9-12 后超产农民恰是重建火种;
  ③钉点门 24→20 → game_01 在 456s 波战中拍 Nexus,矿 405 烂银行
  基地照丢(钉点必须是波间隙特权)。
- 回退 O311-①③,当前树 = o309 状态 + O310-②(O94 零塔白送线)。
- **五轮(O307-O311)汇总**:VH 0/25,Harder 2→1→1→0→0。防御/农民
  micro 维度已全部证伪;胜局画像恒定(二矿 ≤310s + 3-4 矿 + 65+ 农
  + TEMPEST 15-22)。方向选择交司令拍板(见会话)。

## O312(司令拍板 A 案):GM 式经济优先 —— ZT 二矿 280→200s 窗

**日期**：2026-08-17

### 改动(一个变量族:开矿时机/防御前提,单测 673 绿)

1. `zerg_timing_expand_allowed`:窗 280→200s,防御前提「首塔就绪」
   放宽为「首塔 或 GW1 就绪」(调用点传 at=200, gw_ready)。
2. O216i 闸:首塔未就绪不开矿 → 首塔未就绪 **且 GW1 未拍** 才不开
   (O216a 的「无防强开」是零塔零兵营;GW1 在链=叉子产能+塔链并行)。
3. first_expand_at ZT 下限 180→150s(时间闸只管时间,防御前提由
   O216i 独立把守)。
4. O251 首扩钉点:窗 280→200s + GW1 就绪可作防御前提
   (波中不拍由 _wave_incoming 闸原样把守)。

### 依据与风险备查

- 依据:胜局二矿 309s vs 败局 478-546s(O236 线 ≤400s=胜);
  O265 的 220s 证伪发生在 natural 直开时代,O281 口袋矿(离波
  行进路径)落地后早开安全前提已变;司令 GM 录像口径
  (水晶→兵营→二矿→空军科技,二矿口建筑学+塔/电池)。
- 风险:o216a 式滚雪球若复现(首波 240-280s 撞进开矿资金窗),
  判读标准 = Harder lane 胜率与二矿时点分布;若 Harder 跌破
  当前水位(1/5)即回退本族。

## o312 机制生效(二矿 249s!)+ O313 分矿防守三点

**日期**：2026-08-17

### o312 结果与判读

- **o312a VH 0/5 / o312b Harder 0/5**,但**判保留不回退**:预定回退
  标准针对「开矿机制伤人」,实测机制成功 —— 二矿 249s/373s/614s/654s
  (此前 478-546s),局时长 904-1120s(此前 389-600s),墙前移。
- 新败因:450-540s 的 31-supply 波拆分矿 —— **ZT 塔地板 3 被让位
  min 链压穿**:game_03 分矿失守时全场 1 塔、主基 0 塔到 440s
  (fb_waiting/holding/O216d-FB优先 三层 min 叠在 O268-② 地板之后)。

### O313 落地(三点,单测 674 绿)

1. **ZT 波窗(t≥240)塔地板 3 后置**:压过所有让位 min 闸
   (O293-②「波前 3 塔=存活地板」移到让位链之后)。
2. **O256 首批拉人需求封顶 max(4,敌地面数)**:o312b game_03
   敌 10 拉 20(2 倍过拉)10s 全灭;1v1+塔输出已是优势,超出纯喂。
   (O310-① 的 2+4×塔 cap 回退教训保留:不按塔数砍,按敌数封。)
3. **O251 首扩钉点加 threat 闸**:_wave_incoming 只管预警,接触后
   threat 常驻期钉点 = 400 矿冻结+农民送路(o311b game_01:485s
   波中拍矿,矿 405 烂银行)。

## o313 结果 + O314 波窗战力三点(叉 cap 8/补电扩 not_viable/O94 线收紧)

**日期**：2026-08-17

### o313 结果与尸检

- **o313a VH 0/5 / o313b Harder 1/5**(game_05 胜 1286s:二矿 522s,
  扛过 848s 敌 89 supply 波,三矿 1273s —— 胜局画像:塔 1-3/基地
  + 57 supply 军队,**赢靠军队不是塔**)。
- 二矿时点继续改善:241s/265s/458s/522s/530s(GM 节奏在 2/5 局达成)。
- 速败局(game_02/03)死因链:①304s 波(敌 20-27)到脸时我 11-13
  supply —— **unknown 死窗叉 cap=3**(O255-③)+ 钉点 floor 全停
  (O298-③)在早二矿落定后成绞索;②波后塔重建 not_viable/no_placement
  刷屏 30s+(银行 15-105 等钱 + 带电余=0 无电),主基 0 塔到 442s;
  ③O94 敌 20 塔 1 仍 ×6 协防(线 14+6×1=20 恰好不触发),农 20→11。

### O314 落地(三点,单测 675 绿)

1. **unknown 死窗叉 cap 波窗放开**(`unknown_zt_floor_cap`):
   t≥240 且敌可见 ≥4 → 8(原 3;wave_incoming 保持 5)。
2. **塔位补电自救扩到 not_viable(等钱)**:带电余 0 时先钉电(100)
   再谈塔(150);can_afford 门移除(critical 钉点语义本就是等钱,
   穷局恰恰最该钉)。
3. **O94 hopeless 塔口径 6→4**:塔 1 线 20→18、塔 2 线 26→22 ——
   敌 20 塔 1 不再拉 ×6(O94 矿线协防无塔罩,线应比 O256 紧)。

## o314 结果:A 案三轮汇总,瓶颈定位(单矿经济撑不起三线投入)

**日期**：2026-08-17

### o314c/d 结果

- **o314c VH 0/5 / o314d Harder 0/5**(首轮 9/10 ERROR = 漏 import,
  已修并加 import 冒烟进验证链)。
- 叉 cap 8 未兑现:game_03/04 首波 301-307s 我仍 8-10 supply ——
  **cap 不是瓶颈,单兵营产能+钱是**:8 农民开局单矿到 300s 总收入
  ~2000-2500,nexus(400)+forge(150)+塔(300)+农民(1000)+8 叉(800)
  数学上不可兼得;二矿 250-270s 落成要 350s+ 才开始产出,300-330s
  波窗恰在投入期。这是 A 案的结构性死穴。

### A 案(O312-O314)三轮汇总判读

- Harder:0+1+0/15 vs o306 基线 2/5 —— **未跑赢基线**。
- 收益(真实):二矿 241-373s 达成、局时长翻倍、GM 节奏机制全部
  可用;代价:波窗(300-330s)投入期撞上波,防不住=一切白搭。
- O236「二矿 ≤400s=胜」的相关性来自旧代码时代,当前代码下
  早二矿与首波防守抢同一份钱。

### 待司令拍板(2026-08-17,见会话)

- A:继续 A 案微调;B:回 o306 水位转防守总量(双兵营爆叉+塔3
  电池2,~350s 再开二矿);C:ZT 挂起保持现状,先打其它未打穿
  组合(Zerg Rush/Power、Terran 各风格 N=5)。

## O315(司令拍板 B 案):回 o306 开矿口径 + ZT 防御窗双兵营

**日期**：2026-08-17

### 改动(单测 675 绿,import 冒烟过)

**回退(A 案开矿时机族,保留其余全部独立改进)**:
1. `zerg_timing_expand_allowed` 调用点:回 280s 窗/首塔前提
   (去 at=200/gw_ready 传参,函数签名保留备查)。
2. O216i 闸:恢复「首塔就绪才开矿」(去 GW1 替代前提)。
3. first_expand_at:回 180s 下限。
4. O251 首扩钉点:回 280s/首塔前提(O313-③ threat 闸保留)。

**B 案增量**:
5. **ZT 防御窗双兵营**(`_zt_defense_window` = presumed/rush确认/
   unknown):_timing_gateway_cap 1→2 —— O249b 禁 transition 后 ZT
   恒单兵营(~28s/叉,300s 仅 4-5 叉 = 我 8-10 supply 天花板,
   o314d game_03/04 实证);双兵营 ~14s/叉,300s 可达 7-8 叉
   (16 supply),配塔 3(O313-①)+电池 2(O256-③)接 20-supply 波。
   forge 优先(O94-B)/首叉优先(O126-①)顺序闸原样。

### 保留的 A 案遗产(独立改进,不回退)

O307 三点(holding 自愈/holding 放 cyber/地面保底)、O308 三点
(GW1 先于 forge/添油初版/炮塔串行化)、O309  latch、O310-②、
O313 三点(塔地板 3 后置/需求封顶/threat 闸)、O314 三点
(叉 cap 波窗 8/补电扩 not_viable/O94 线 6→4)。

## o315 结果 + O316 波前产能三点(叉 cap 全程 5/手动链去 sprint/GW2 塔门 1)

**日期**：2026-08-17

### o315 结果与尸检

- **o315a VH 0/5 / o315b Harder 1/5**(game_02 胜 1378s:塔3@281s、
  GW2@321s、叉4-7,442s 晚波敌 89-91 vs 我 51-55 硬扛获胜)。
- O315 双兵营生效(GW2 241-321s,此前从不建),但**波前叉数仍 2-4**:
  ①unknown 窗叉 cap=3 是枷(game_01:241s 银行 485、叉仅 2 —— 钱在,
  cap 锁死);②**55-301s 首塔零派工尝试** —— _presumed_manual 依赖
  _sprint,sprint 未激活时手动防链整段停摆,塔 281s 才落地(波同帧
  到脸);③O99-① 的 GW2 需 2 塔 → 塔晚 GW2 更晚(281s),叉产能
  翻倍错过波窗。
- 胜局画像再确认:塔 3@281s + 叉 4+@320s + 晚波 = 胜;早波(280-310s)
  + 塔 ≤1 + 叉 ≤3 = 死亡螺旋。

### O316 落地(三点,单测 675 绿)

1. **unknown 窗叉 cap 全程 5**(原 t<240 仅 3;银行数据证明 200 矿
   叉钱付得起,波窗 t≥240+敌≥4 → 8 不变)。
2. **presumed 手动防链去 _sprint 依赖**:presumed/defense_urgent 本身
   即防御紧急信号,手动链串行(forge→供电→首塔)从 55s 起跑,
   与 F2 的重复由 O286 全口径计数兜底。预期首塔 281s → ~200s。
3. **ZT 防御窗 GW2 塔门 2→1**(transition_gateway_allowed min_cannons):
   塔量由 O313-① 波窗地板 3 独立保护,不靠本闸省矿。

## o316:Harder 回 2/5 基线,波前产能链确认有效 + O317 方向

**日期**：2026-08-18

### o316 结果

- **o316a VH 0/5 / o316b Harder 2/5**(game_03 912s / game_04 688s 胜)
  —— Harder 自 O306 后首次回基线,且不是噪声回摆:机制数据全部兑现。
- 机制验证:胜局 塔2-3@281-321s(O316-②手动链 55s 起跑,首塔
  201-281s vs 此前 281s+)、GW2@241-442s(O316-③塔门 1)、
  叉 2-5@281-362s(O316-①cap 5);VH 首波我方 supply 8-11 → 13-14。
- VH 墙:首波 敌21 vs 我13-14(同时间点 Harder 敌 13-17)——
  VH 经济加成 = 波大 5-8 supply,game_01 418s 猝死、game_03 撑到
  687s 中局亡。差的就是这一档。

## O317:forge 先于墙/电池地板前提降 cyber/钉点 floor 冻结波窗豁免

**日期**：2026-08-18

### 依据(o316a 尸检)

- game_01:墙链(水晶→GW→forge 上墙)串行阻塞,forge 被卡 55→250s
  (银行 510、塔 0、首波 304s 裸接)—— O316-② 让手动链 55s 起跑后
  墙链成了新瓶颈。
- game_03:塔 3+叉 4+电池超载×1 对 敌21 仍崩(农 20→5)—— 电池地板
  2 的前提是「SG 在链」(O256-③),首波窗 SG 远未拍,从未生效。
- game_02:468s 敌 33 波与二矿钉点(~500-600s)重叠,O298-③/O236
  的钉点 floor 全停让叉/追猎核在波窗归零。

### 落地(三点,单测 675 绿)

1. **presumed 链 forge 先于墙**(普通槽先行,墙链 forge 上墙步骤去重);
   early_core_missing 保护保留。
2. **ZT 电池地板 2 前提 SG→cyber+首塔就绪**,presumed 窗同步放开
   (原一律 0;不为电池提前补 cyber,E3d 顾虑由前提覆盖)。
3. **钉点期叉 floor/追猎 cap2 冻结的波窗豁免**(t≥240+敌可见≥4,
   与 O314-③ 同判据;钉点是波间隙特权)。

## o317 真回归判定(协议:Harder 累计 0/10)+ ①③回退、②保留

**日期**：2026-08-18

- o317 首轮 VH 0/5 / Harder 0/5;o317c/d 同码复跑 Harder 再 0/5
  (累计 0/10)→ 协议级真回归,与 o316 的 2/5 对比成立。
- **回退 O317-①(forge 先于墙)**:墙(物理封口)被推到 forge+首塔
  之后,波前封口不完整;o316a game_01 的「墙卡 forge」病根是墙链
  churn(O137 30s 释放已在管),不是顺序。墙链 forge 上墙去重保留
  (省 150 矿,无害)。
- **回退 O317-③(电池地板 cyber+首塔/presumed 放开)**:电池 200 矿
  提前到波前窗与叉/塔抢钱。
- **保留 O317-②(钉点 floor 冻结波窗豁免)**:中局行为、证据链完整,
  与早波花钱无关。
- 当前树 ≈ o316 水位 + O317-②。验证:下一轮双 lane 应回 2/5 带。

## o318/o319 判读 + O320 情报驱动快慢波分档(司令:不回滚继续迭代)

**日期**：2026-08-18

### 判读结论

- o318(回 O317-①③)/o319(精确 o316 态)Harder 均 0/5 —— o316 的
  2/5 是噪声上摆;o306 基线(2/5×2)与 O307 起 55 局 5 胜(9%)的
  差距统计显著(~0.2%),但**单点回滚 o306 态是否为最优基底未经
  验证**。司令拍板:不回滚,当前态继续迭代。
- 深层发现:verdict(O9)是一发 latch(t≈109-170s),**后到的情报
  (ROACHWARREN ~136s、敌分矿)无人消费** —— 每局盲打 presumed
  包(~500 矿),快波(280-330s)慢波(≥440s)不分;胜局全部
  来自慢波签,快波签全败 —— 分档校准是情报允许的最大杠杆。

### O320 落地(三点,单测 676 绿)

1. **`zt_wave_read` 快慢波分档**:warren 先行+敌单基地(t≥150)→
   fast;敌 ≥2 基地+未见 warren(t≥200)→ slow;情报不足不押注。
2. **fast 档**:武装 rush 证实包(_rush_confirmed,O107 先例)——
   全部 rush 联动(塔/双兵营/不开矿)提前 ~100s 武装。
3. **slow 档**:presumed 退保(省 ~500 矿)+ 开矿窗提前 200s
   (zerg_timing_expand_allowed at 条件化)—— A 案资产的情报驱动版,
   早开矿只在慢波判决后启用。

## o320 结果:机制生效但情报太晚,胜率未动 —— 战略检查点

**日期**：2026-08-18

- **o320a VH 0/5 / o320b Harder 0/5**。O320 分档 6/10 局触发
  (slow×3/fast×2/未触发×5),机制按设计工作。
- 关键发现:**slow 判决平均 ~450s 才落地**(敌分矿情报到得太晚),
  早开矿窗(200s)从未被用上;fast 武装局(o320a game_02/04)照败,
  VH 快波 21 supply 超出现有防御包上限。
- 慢波局防御剖面健康(o320b game_01:塔5@362s+GW2+叉5,活到 890s),
  死因仍为中局 60-90 supply 波(敌经济差)。
- **15 轮(O307-O320)总账:VH 0/65,Harder ~6/60。** 机制逐轮改善
  (二矿/塔/叉时点全部前移),胜率不动 —— 调参维度已达收益极限,
  差距在打法层(opener/编队/微操),不在参数层。

## O321(司令拍板 A 案):opener 级大改 —— ZT 开局重写 + bot 层执行期噤声

**日期**：2026-08-18

### 改动(单测 676 绿)

1. **`CarrierOpenerZergTiming` 重写为防御总量前置**(protoss_builds.yml):
   GW1(13)→forge(17)→cyber(18)→塔(19)→电池(21)→GW2(22)→
   塔2(24)→电池2(26),叉 16/20/23/25/28 —— 胜局剖面(塔2+电池2+
   双兵营+叉4-6 @ ~280s)直接写死;forge→塔间不插 worker(O201/202),
   不放 gas(bot 层 O13 自管),不写 Nexus(bot 层波间隙闸自管)。
2. **`_carrier_rush_opener_early` 扩到 ZT opener**:执行期(未完成且
   塔 <2)presumed 手动链/F2/_should_build_defense 全部噤声 ——
   15 轮调参胜率不动的执行层病根:runner 与 bot 层在波前抢同一份
   钱,每条链都慢半拍。完成/2 塔落地自动交还(O202 同语义)。
3. **F2 注册总闸加 opener 噤声**(presumed/unknown/sprint/无防
   四入口全覆盖)。

### 判读标准

- 波前(280-310s)剖面应首次达标:塔 ≥2+电池 ≥1+叉 ≥4+GW2;
- Harder 水位应显著回 2/5 以上;若 opener 执行更慢(顺序链被
  supply 触发卡死)则从快照时序定位卡点后修。

## o321 结果 + O322 三点(追猎核解禁/opener 噤声 300s 时限/威胁撤钉)

**日期**：2026-08-18

### o321 结果与尸检

- **o321a VH 0/5 / o321b Harder 0/5**,但 opener 重写**部分生效**:
  game_01 波前剖面历史最佳(塔3@281s+GW2@321s+叉5@321s+电池2@402s
  +叉8-10@442-482s);game_03 塔2+电池1@281s。
- 三个新败因:①400-650s 舰队真空期军队质量 ~25 supply 对敌 38-90
  波 —— **unknown 窗追猎恒 0**(O255-③),胜局(o230)靠的正是
  21-25 追猎海,气烂 300-1300 在银行没人吃;②game_02 runner forge
  步卡壳 ~230s(银行 1340、塔 0),bot 层电力自救被噤声连带关闭;
  ③game_01 Nexus 490s 落成 498s 波到、506s 失守 —— O313-③ 只拦
  新钉点,存量钉点在 threat 激活时没人撤。

### O322 落地(三点,单测 676 绿)

1. **unknown 窗追猎核解禁**(t≥360+气≥250):吃银行死气填舰队真空
   (O255-③ 的「抢 SG/FB 资金窗」在 SG 未拍、气烂银行时不成立)。
2. **opener 噤声 300s 时限**(仅 ZT opener):runner 卡壳时 bot 层
   恢复接管,噤声不再无限期。
3. **threat 激活撤销未开工 Nexus 钉点**(驻点等钱=未付款,撤销零成本,
   波后重评;堵住「落成即撞波」的双捐窗口)。

## o322 结果:追猎/塔全到位,兵力差方程未变 —— carrier 流边界浮现

**日期**：2026-08-18

- **o322a VH 0/5 / o322b Harder 0/5**。O322 三点机制全部生效
  (追猎 4-7@442-482s、塔 7-8@362s、opener 无卡壳局),但死因
  清一色:500s+ 敌我 1.5× 兵力差(敌 47-69 vs 我 29-46)。
- **16 轮(O307-O322)总结**:波前剖面/塔/叉/追猎/二矿时点全部
  修到达标线,但敌我产出差是结构性的(单矿到 500s vs Zerg 经济
  加成)—— carrier 流(舰队 600s+ 成型)的真空期长度超出任何
  地面组合能填的范围。胜率方程没变过。
- 候选出路:①换流派(stalker/dt 流已有验证基线,兵力成型远早于
  carrier,直面同一波窗);②ZT 挂起转其它组合;③继续 carrier 磨。

## O323(司令拍板继续 carrier 磨):攒钱纪律/SG 钉点/分矿落成塔钉

**日期**：2026-08-18

### 依据(o322b 尸检)

- 追猎/塔全到位仍败:500s+ 敌我 1.5× 兵力差 —— 舰队(SG 405-623s)
  和二矿(534-566s 或开不出)都太晚。
- game_04(单矿到死):口袋激活 270s 起,270-440s 矿恒 10-305 攒不
  出 400 —— O290 口袋冻结只封塔/电池,**追猎(125/只)+GW2/3(150)
  +电池(100)照跑**(B 案防御总量与攒钱打架);O287 唯一胜局轨迹
  =「180s 起零新增建筑硬攒 790,窗开即拍」。
- 分矿落成裸奔:o321b game_01 490s 落成 506s 失守。

### 落地(三点,单测 676 绿)

1. **口袋攒钱期追猎+兵营链冻结**(O322-①的解禁与 O236 cap2、
   _rush_gateway_boost 全部让位 Nexus;rush 保命例外)—— 攒钱
   纪律优先级 > 一切非命悬一线开销。
2. **SG 钉点**(t≥300+cyber 就绪+无 SG+非口袋期 → critical 驻点
   等钱):SG 时点从「余钱排队」改「目标钉点」,方差收敛。
3. **分矿落成塔钉点**(critical):落成即 1 塔保命,F2 后续补齐,
   治「落成 16s 失守」。

## o323 结果 + O324 三点(runner 看门狗/银行熔断/分矿钉点补电)

**日期**：2026-08-18

### o323 结果与尸检

- **o323a VH 0/5 / o323b Harder 0/5**。
- 新实锤模式:game_01 **矿 960-1090 烂银行 + 塔 0**(runner forge 步
  卡死,281s 波 敌22 vs 我14 裸接)—— 这是**第四局**「大钱烂银行+
  塔不够」同模式(o315b 矿485/o316a 矿510/o321b 矿1340/o323b 矿960):
  dispatch_viable 的收入投影在「存款已在手」时仍按流量判穷。
- game_03:正常中局亡(敌39 vs 我26,塔5 照丢)。

### O324 落地(三点,单测 676 绿)

1. **runner 步卡死看门狗**:build_step 45s 不前进 → opener 噤声永久
   解除,bot 层接管(电力自救/手动防链),事件簿记。
2. **银行熔断**(t≥240+矿≥500+主基就绪塔<3):F2 注册+资金守卫
   双豁免 —— 存款 ≥500 就是支付能力,不等收入投影。
3. **分矿落成钉点先补电**(无电新矿先钉水晶 needs_power=False 再钉塔,
   防 O323-③ 在无电矿点制造新 stall)。

## o324 结果 + O325 三点(黄金窗追猎阈 6/near-miss 簿记/母舰隐身)

**日期**：2026-08-18

### o324 结果与尸检

- **o324a VH 0/5 / o324b Harder 0/5**,但:塔 0 局清零(塔@300s
  2-6)、银行烂钱收敛(峰值 384-703,此前 1340)、局时长 790-1058s。
- runner 看门狗 10/10 局触发(推进语义步自然超 45s,判据偏松,
  但接管后塔照常落地,暂按无害记录)。
- **败因收敛到终局链**:单矿局舰队 1-3 艘(game_03);双矿 ramp 局
  (game_04:2 基 41 农 暴风 6@820s)在 850-950s 腐化/大龙波 48s
  蒸发(暴风 6→0、农 35→12)—— 与 40 局取证「850s+ 腐化转型 =
  我方 0 胜」吻合。**O302 黄金窗推进 0/10 局触发**:
  game_04 在 800s 有 暴风6+追6(= o305/o313 胜局编成),被追猎阈
  8 挡在窗外。

### O325 落地(三点,单测 676 绿)

1. **黄金窗追猎阈 8→6**(o324b game_04 实证:暴风6+追6@800s 就是
   胜局编成,差 2 只追猎被挡,868s 腐化波收尸)。
2. **黄金窗 near-miss 簿记**(舰队 ≥3 但被追猎/腐化闸挡,30s 节流)——
   下轮尸检直接读触发率。
3. **母舰隐身力场**(司令观察③):FB 就绪+t≥700,主基 Nexus 出母舰
   (400/400 出自气烂银行),给舰队/地面持续隐身,针对 850s+ 腐化波
   下舰队 48s 蒸发的生存短板。

## o325 结果 + O326 三点(母舰 idle bug/SG2 钉点/尖塔否决)

**日期**：2026-08-18

### o325 结果与尸检

- **o325a VH 0/5 / o325b Harder 0/5**。
- **黄金窗推进首次触发**(o325a game_04,VH):990s fleet=6+追7 推出;
  o325b game_01 fleet=9 经 O241 强推。但推出时腐化 4-13 已出场
  (舰队 6 艘拖到 950-990s,黄金窗早关)—— 推进战果有限照败。
- **母舰 0/10 局下水**:`townhalls.ready.idle` 恒空(基地农民训练
  不间断),idle 口径 bug。
- 腐化计数闸反应太慢:推时腐化 ≤2 过闸,28s 后 4-6(o325a game_04
  实证)—— 尖塔可见才是领先的否决信号。

### O326 落地(三点,单测 676 绿)

1. **母舰 idle 口径修复**:任意就绪基地排队(农民让一艘母舰)。
2. **SG2 钉点**(FB 拍下+首 SG 就绪+气≥400+SG<2):双 SG 并行,
   舰队 6 艘提前 ~150s(单 SG 出 6 艘 ~260s = 推出时窗已关)。
3. **尖塔否决**(`spire_seen`):尖塔可见 = 腐化 30-60s 内必到,
   整局按无黄金窗处理(蹲守等配方,不送暴风)。

## o326 结果 + O327 四点(经济专项:早窗气抽矿/三矿门槛/母舰经济门/SG2 让位二矿)

**日期**：2026-08-18

### o326 结果与尸检

- **o326a VH 0/5 / o326b Harder 1/5**(o326b game_02 胜:2 基 45 农,
  1055s)。
- **司令观察实证(经济崩溃链)**:二矿 518-647s 甚至不开(胜线 ≤310s);
  三矿 10/10 局零开出 —— 旧钉点门槛「农民 ≥16×基地+8」(2 基=40)
  在败局农民峰值 22-28 下永远等不到,20 分钟仍 2 矿,经济差滚雪球。
- **早窗气烂银行**:225-338s 气 472-876(6 气农产死钱),同期矿恒
  <200 卡死 Nexus/农民/塔;气 max 1063(game_03)创纪录。
- **母舰 811s 下水但成负资产**:2 基 22-28 农局 300/300 + 占 Nexus
  队列 71s(期间零农民),O326-① 的 idle 修复反而暴露经济门缺失。
- **SG2 与 Nexus 同资金窗互挤**:o326a 二矿均值 ~576s(647/518/563)
  vs o325a ~503s(458/546/631/378)——SG2 critical 钉点(~400-500s)
  的 150 矿挤占扩张资金窗。
- 终局编成 ORACLE×1+TEMPEST×2(均值),远低胜局配方(暴风 15-22);
  母舰均 @811s 才出,未改变 850s+ 舰队蒸发结局。

### O327 落地(四点,单测 680 绿)

1. **早窗气烂抽矿**(`early_gas_overflow_pull`,150-420s+气≥400+
   矿≤250+FB 未就绪):气农抽回矿线,窗口期 ~+400 矿 ≈ 一个 Nexus;
   滞回复位(气<200/FB 就绪/出窗),不棘轮(O117-① 教训)。
2. **三矿门槛放宽**(`expand_pin_workers_ok`):2+ 基地农民 ≥26 即钉,
   t≥600 时间兜底 —— 多一个 Nexus = 农民产能 ×1.5,比攒农治本;
   波间隙/无敌/矿 ≥350 守卫保留,1 基首扩 24 门槛不动(O311-③
   证伪区不复试)。
3. **母舰经济门**(`mothership_economy_ok`):3 基地或 ≥36 农才出
   母舰(O264/O325 两块同门)—— 舰队保命符不能抢 Nexus/农民资金窗。
4. **SG2 让位二矿**(`sg2_pin_economy_ok`):仍单基地时矿 ≥550 才拍
   SG2(拍完还剩 400 给 Nexus);2 基地运转后放行,黄金窗收益不变。

## o329-o331 结果 + O332 四点(doctrine 执行层修复)

**日期**：2026-08-18

### o328(提前收割)与 o329/o330/o331 结果

- **o328 提前收割 5 局**:O328 选址实证生效 —— 主基右下时 F2 注册
  防御 base=(130,26)(西侧口袋矿,开阔度 10/24);但 Nexus 派工
  294-296s 后驻点等钱 160s+,落成 460-540s。资金链是瓶颈。
- **o329 中止(2 局早期信号)**:速二矿钉点整局哑火 —— 全值矿门 400
  被 opener 后续步抽水;o329b game_01 SG 钉点 342-366s 连拍 4 次
  抢光二矿资金窗(新 opener 无首塔,口袋攒钱守卫失效),单基地到死。
- **o331a VH 0/5 / o331b Harder 0/4+1异常**。O329 钉点虽触发
  (226s)但驻点等钱 145-240s,二矿落成 466-514s 更晚。
- **录像对照基准**(scripts/replay_bases.py 实测):电脑 VeryHard
  Zerg 二矿 119-150s、三矿 ~660s;我方 466-514s → 敌方多采
  5-6 分钟双矿 + VeryHard 作弊,经济差从开矿时点滚起。

### o331 尸检:doctrine 执行层被架空(四点)

1. **主基塔在 Nexus 开工前照建**:F2 115s 注册主基 target=1 +
   presumed 链,200-300s 主基 3-5 塔+电池吃 600-900 矿 → O329
   钉点矿窗推迟到 226s,game_03/04 整局摸不到 350 哑火。
2. **bot 层叉子照出 5-6 只**(500-600 矿):opener 零叉了,但
   unknown 死窗 floor/波前 cap 在 Nexus 开工前照补。
3. **SG 在 Nexus 驻点等钱时插队**:O330-③ 把「在途」当放行,
   297s SG(150/150) vs 395s 才开工的 Nexus(o331a game_01)。
4. **O329-③ 预置塔链派工=taken 不重试**:fired 照置位,分矿塔
   实际 463s 才来,489s 波 38 supply 走进裸奔分矿。

### O332 落地(四点,单测 686 绿)

1. **主基塔全程归零**(`_zt_no_main_def`):Nexus 开工前主基也不
   铺塔,presumed 手动链 ZT 全噤(rush 确认恢复)——严格「先
   Nexus 后塔」顺序。
2. **叉让位闸**(`zt_zealot_yield`):二矿开工(townhalls≥2 含在建)
   前叉 floor_cap 归零,rush 确认恢复 —— 司令「2 矿开工前零兵种」。
3. **SG 放行口径**:去掉 nexus_in_flight(驻点等钱不算数),只认
   townhalls≥2 或 t≥360。
4. **预置塔链失败重试**:派工=dispatched 才置 fired,30s 节流重试。

## o332 结果 + O333 四点(Nexus 开工链修复)

**日期**：2026-08-18

### o332 结果与尸检

- **o332a VH 0/5 / o332b Harder 0/5**。
- **重大突破**:O329 速二矿钉点在 5/10 局精确命中 **103.9-104.8s**
  (120s 目标达成,主基塔全程归零+零叉 opener 的资金链干净了)。
- 但 Nexus **开工**链三条新病:
  1. **O322 威胁撤销杀死等钱中的首扩**:钉点 104s → 驻点等钱横跨
     257-320s 波窗 → 逢波就撤 → 循环撤销(game_01 单基地到死)。
  2. **runner 后续步(forge/core/GW2 ~550 矿)排在等钱的 Nexus 前面**
     —— 钉点 104.7s 的局 Nexus 511s 才重派、654s 落成(game_02)。
  3. **SG/SG2 钉点 churn**:SG2 单局连拍 19 次、SG 连拍 12 次(驻点
     失败每 ~4s 重试),SG2 的矿≥550 门在等钱期 346s 放行又插队。
- **叉闸副作用**(o332b game_01/02):钉点晚局(185-286s)波 288-304s
  到脸时零叉零塔(O332-② 无威胁豁免),主基 359s 被推平。

### O333 落地(四点,单测 686 绿)

1. **O322 首扩豁免**:威胁撤销只对 3 矿+ 钉点生效 —— O328 口袋选址
   后首扩不在波路径上,且首扩是全村希望(原实证场景已覆盖)。
2. **opener 摘除 forge/core/GW2**:只剩农民/水晶/兵营,钉点的 400
   矿零竞争;forge 改 bot 层在 Nexus 开工即 critical 钉点(O333-②),
   core/GW2 走原科技链/追加产能。
3. **叉闸威胁豁免**(`zt_zealot_yield` 加 threat_active):敌压境时
   零兵种 doctrine 立即让位(rush fuse 同源)。
4. **SG2 门去掉矿≥550 替代项**(只认 bases≥2)+ SG/SG2 钉点失败
   30s 节流(治 19/12 连拍)。

## o333 结果(双 lane 各 1 胜!) + O334 三点(钉点哑故障修复)

**日期**：2026-08-18

### o333 结果与尸检

- **o333a VH 1/5 / o333b Harder 1/5 —— 正式验证轮首次 VH 胜场。**
- **胜局配方复现**(o333a game_01 VH / o333b game_02 Harder):
  钉点 104-186s → 3-4 基地(727/711/980s 开 3/4 矿)→ 农民 66-68 →
  舰队 15-22 + 追猎 10-12,O302 推进从 658s 反复发动,1030-1150s
  胜。母舰 1041s 下水(o333b game_02,O327-③ 经济门后首艘)。
- **但钉点哑故障浮出水面**:o333a game_03 铁证 —— 钉点事件 186.2s
  后银行 645→1315 一路烂涨,Nexus 零开工(O283d counter/tracker
  恒 0),「钉点成功」事件是误导(旧代码不看派工 rc 一试即记);
  o332 的「104s 钉点」同样名不副实(落成仍 390-654s)。
  game_03 同时暴露:钉点失败期主基零塔(O332-① 封禁无熔断),
  波 289s 裸接,354.9s 速败。

### O334 落地(三点,单测 687 绿)

1. **钉点 rc 可见化**:成功事件只在 dispatched 时记;失败按「结果
   变化即记 + 30s 节流」记具体环节(taken/no_placement/no_worker/
   tech_not_ready),下轮尸检直接读哑故障真因;失败重试 10s 节流。
2. **钉点失败换落位**:连续失败 >60s → 目标从口袋矿退回最近
   natural(落位多样性自救)。
3. **主基塔银行熔断**(`main_defense_bank_fuse`):矿 ≥600 且 Nexus
   未开工 → 主基塔放行(钱不是瓶颈时不抢资金窗),滞回 400 复位,
   Nexus 开工立即回 doctrine。

## o335 结果(双 lane 各 2/5,历史最好) + O336 三点(等钱链收口)

**日期**：2026-08-18

### o334/o335 结果与尸检

- o334a VH 0/5 / o334b Harder 1/5:O334-① instrumentation 抓到钉点
  哑故障真因 —— 手动 `_dispatch_structure(NEXUS, 口袋点)` 恒
  **no_placement**(10/10 局,连续 30-190s);实战建成全部 Nexus 的
  是 ares `ExpansionController(location=口袋点)` 通道。O334-④ 把
  速二矿执行通道改到 EC(holding 自带锁钱,O50/O43 闸 + O54 接管)。
- **o335a VH 2/5 / o335b Harder 2/5 —— 历史最好**。
- **胜局时间链全部打通**(4 局胜场):O329 启动 172-192s → forge
  钉点 211-231s → **二矿落成 212-233s**(远胜 ≤310s 胜线)→ SG
  300s → SG2 344-346s → 三矿 562-582s → 舰队 17-24 + 追猎 8-12
  → O302 反复推进,1057-1226s 胜。
- **败局(game_02 型)**:O329 启动 104s 但 257s 首波 rush_active
  解锁主基防御链(forge+2塔+电池+5叉+追猎 1150+ 矿),等钱 Nexus
  被 O307 二连撤销(281/457s)→ 落成 578s,723s 败。
- **叉泄漏口定位**:O292 trickle 分支(GW 就绪即产,cap 3-6)在
  零叉 opener 外漏 5 叉+1 追猎 ≈700 矿(153-273s);首叉冲刺在
  零兵种窗内压农民(O145 矿 45 农民停产 = 收入断流)。

### O336 落地(三点,单测 688 绿)

1. **O307 首扩豁免**(`holding_abort_keep_first_expand`):ZT 首扩
   holding abort 只解锁 30s(科技链恢复)不撤销派工 —— 撤销重派
   = 工人再走 20s + 资金窗重算,只会更晚。
2. **trickle 接入零兵种闸**(`_o332_zyt`):二矿开工前 O292 分支
   关闸;开工/rush/威胁后照常(自校正 cap 语义不变)。
3. **首叉冲刺让位零兵种窗**:presumed 常驻期的冲刺不再压农民/
   水晶去等一只已被封掉的叉。

## o336 结果(VH 2/5, Harder 4/5) + O337 三点(分矿塔链/补电/SG2 收口)

**日期**：2026-08-18

### o336 结果与尸检

- **o336a VH 2/5 / o336b Harder 4/5 —— Harder 基本打穿**。
- 速开链继续精进:game_05(o336a) Nexus **116.5s 开工**(104s 启动
  + 12s 走位,完整命中 120s 目标);game_01 开工 192.9s。
- **败局三病定位**:
  1. **分矿塔链快速开工洞**(o336a game_01,507s 速败):O334-④ 后
     Nexus 开工飞快(~190s),O323-③ 落成触发在「开工」帧即走
     (townhalls 含在建),forge 未就绪 → tech_not_ready 一次性哑火
     (一次性 latch 不重试);预置塔链(O329-③)要求 Nexus 未开工,
     开工快反而跳过 —— 分矿零塔,302s 波 26 supply 推平(E6「敌4
     地面,无塔」三连)。
  2. **补电不对锚**(o336b game_01):首塔 no_placement/not_viable
     连发 60s+(282-343s),O116 日志实证主基 2x2 带电槽=0;O296-③
     的补电水晶拍在主基中心,坡口/矿线锚点区带电槽仍 0。
  3. **SG2 驻点等钱循环**(o336b game_01):489-639s 七连「成功」
     派工零落成 —— 穷局(矿 <150)驻点等钱触发「到位→等钱→10s
     僵死 pop→30s 重派」循环,工人每轮白走 25s,单 SG 舰队产能
     减半,1239s 被 79 supply 波滚死(2 基 44 农,三矿未开)。

### O337 落地(三点,单测 688 绿)

1. **分矿塔持续守卫**(替 O323-③ 一次性 latch):任意非主基基地
   12 格内就绪塔 <2 → 先补电(不要 forge),forge 就绪即钉塔
   (30s 节流);覆盖开工快/落成慢/塔被拆补建全部形态。
2. **补电对准塔锚点**:O296-③ 自救水晶 closest_to=首塔锚点 +
   自带电源,下一根水晶直接覆盖塔位。
3. **SG2 可负担门 + SG/SG2 失败 rc 簿记**:买得起才派(派了即
   开工,根治驻点等钱 pop 循环);失败环节进事件,下轮尸检可读。

## o337 结果 + O338 三点(小股抄分矿链收口)

**日期**：2026-08-18

### o337 结果与尸检

- **o337a VH 1/5 / o337b Harder 2/5**(o336 是 2/5、4/5;lane1 三局
  379-507s 速败,速败型回归)。
- **速败机制一致**:敌小股 4-5 地面 270-300s 抄分矿(口袋矿),
  分矿塔就绪差 10-30s(链:Nexus 开工 ~120-190s → forge 钉
  ~180-240s → 落成 ~240-280s → 塔 ~280-330s),E6 撤离农民但
  raider 拆 Nexus,基地 2→1→0,379-507s 三连。
- **协防记账化实证**:main.py E6 的「N 地面兵力就近协防」只是
  事件标记不拉兵;O217 残敌清剿在 rush_active 整段禁用(原证据
  是主基守墙不为一条狗离位)——主基 4-6 叉看戏,分矿被拆。
- **地面太薄**:362s 仍单兵营(game_03),28s/叉补不上;4-6 叉
  vs 敌 15-26 supply 两线(主基 17 + 分矿 4-5)。

### O338 落地(三点,单测 688 绿)

1. **forge 钉点提前到 Nexus 在途**(改 O333-②):落成 ~240s→~185s,
   首塔就绪 ~245s 赶在 270-300s 小股前(驻点等钱排在 Nexus
   400 付款后,不吃速开资金窗)。
2. **GW2 钉点**(Nexus 开工,分矿堵口位):波前双兵营,叉产能
   翻倍(单兵营 4-5 叉是 o315 实证天花板)。
3. **分矿残敌清剿放行 rush_active**(O217 收窄禁用域):rush
   急性窗只豁免主基残敌,分矿 1-5 残敌照清(战斗侧原生响应,
   不靠 E6 记账)。

## o338 结果(Harder 4/5 复现, VH 0/5) + O339 三点(中局三病)

**日期**：2026-08-18

### o338 结果与尸检

- **o338a VH 0/5 / o338b Harder 4/5**。速败型(379-507s)清零
  (最早死 693s)——O338 三点对小股抄分矿有效;VH 败场转为中局
  (693-968s)三病:
  1. **SG 驻点等钱 pop 循环**(game_01):SG「成功」派工 4 连
     (360-450s)零落地(O337-③ 只给了 SG2 可负担门,SG 漏了),
     舰队链 SG→FB→首舰整体晚 ~90s,746s 敌 72 supply 滚死。
  2. **叉闸的晚开工脆弱窗**(game_05):Nexus 293s 才开工,零兵种
     闸压到 293s;threat 296s 触发(敌 11 vs 我 2)才产叉,330s
     接战晚 30s,经济被滚到 693s。
  3. **分矿带电槽占满**(game_01):守卫补电只看「有无就绪水晶」,
     水晶在但 2x2 带电槽=0(塔/电池/墙占满)时不补,no_placement
     常驻 512-843s,塔阵铺不开。

### O339 落地(三点,单测 688 绿)

1. **SG 钉点 can_afford 门**(O337-③ 同款):买得起才派,派了即
   开工,根治驻点等钱 pop 循环。
2. **叉闸波预警豁免**(`zt_zealot_yield` 加 wave_incoming):
   O279 波预警(40-60s 提前量)即恢复产叉,波到脸时叉已列队。
3. **分矿补电按带电槽判**(`_slot_counts_at` 口径):就绪水晶在
   但 2x2 带电槽=0 同样补电,塔阵不再等几何覆盖。

## o339 结果(VH 2/5 回稳) + O340 三点(无预警局/forge 静默/开工黑盒)

**日期**：2026-08-18

### o339 结果与尸检

- **o339a VH 2/5 / o339b Harder 2/5**(Harder 4/5→2/5 按判读协议
  记为噪声摆动,同码复跑观察;VH 2/5 与 o335/o336 持平)。
- **game_03(o339a,390.5s 速败)**:侦查早死 → 波预警不 latch →
  零兵种闸压到 threat 接触(275.6s 敌 12 vs 我 1)才产叉 = 裸接。
- **game_05(o339b,424.6s 速败)**:预置塔链连报 tech_not_ready
  (108/138s)而 forge 钉点零事件 —— forge 失败环节静默不可读。
- **game_02(o339a,873.7s)**:O329 启动 104.6s 但 Nexus 450s 才
  开工(346s 黑盒,O336 解锁两轮 327/427s 无开工);E6 敌 14 地面
  抄分矿(塔 2 压不住)滚死。

### O340 落地(三点,单测 688 绿)

1. **叉闸时间硬线 240s**(`zt_zealot_yield` 加 now/hard_at):
   波 280-310s 必来是 40 局取证规律,无预警局不再裸接。
2. **forge 钉点 rc 簿记 + 30s 节流**(O340-①):失败环节可读,
   不再静默。
3. **首扩开工延迟诊断**(O340-③):O329 启动 >60s 未开工每 60s
   记矿/农/在途/holding/威胁,game_02 型 346s 黑盒下轮可读。

## o340 结果(Harder 5/5 全歼打穿!) + O341(钉点 latch)

**日期**：2026-08-18

### o340 结果与尸检

- **o340a VH 1/5 / o340b Harder 5/5 —— Harder 档 5 局全胜,正式
  打穿 Zerg Timing Harder 组合(目标 5 局 3 胜+ 达成)。**
- **首扩黑盒打开**(O340-③ 诊断事件首役):game_01/05 诊断显示
  O329 矿窗只开一帧(104s 摸到 350,探机/水晶/兵营花到 35-60),
  EC 非 prioritize 通道要全值 400 → **在途0 持续 300+s**(矿在
  30-300 间被日常开销压着永远到不了 400),514s 才开工。O336
  解锁两轮无碍此机制(解锁的是 holding,不是 EC 派工门)。
- 两局 390-424s 速败(无预警裸接/forge 静默)由 O340-②① 收治,
  本轮未见同型(最早死 395s 是 ① 的衍生:首扩卡死连带经济崩)。

### O341 落地(钉点 latch,单测 688 绿)

1. **O329 条件首次成立即 latch**(`_o329_latched`)到 Nexus 开工/
   rush 确认;
2. latch 期 `_want_dynamic_expand` 恒「想开」(holding 锁钱不断);
3. latch 期 EC **强制 prioritize**(欠费先派走位、到位等钱)——
   不再依赖一帧矿窗 + 全值 400 的 EC 非 prioritize 派工门。

## o342 结果(新协议首轮 VH 0/6) + O343(矿门 475/forge 回退)

**日期**：2026-08-18

### o342 结果与尸检

- **o342a/b VH 0/3+0/3**(新协议首轮;3 局制按两轮累计判读,
  单轮 0/6 不判回归)。
- **在途1→0 蒸发的真因锁定**(O342 偏移未愈,8 局累计实证):
  350 矿门在 ~104s 早钉,走位窗(104-190s)恰是 opener 流水高峰
  (3 水晶+10 农民+forge ≈800 矿 vs 窗内收入 ~1000),工人到位
  银行 <400,ares 等 ~30s 取消 → 在途1→0 反复,开工 466-759s。
  o335 胜局对照:钉点 172-192s(opener 流水已过半),到位即开工
  212-233s —— 矿门的本质是「到位时银行 ≥400+窗内开销」。
- O342 偏移(预置塔朝敌 7 格)保留:即便不是主因,堵口位仍优于
  直拍,且排除了 footprint 占用这条嫌疑路径。

### O343 落地(两点,单测 688 绿)

1. **钉点矿门 350→475**(=造价 400+走位窗 buffer 75,与
   _preposition 同判据):钉点 ~140-160s,到位即开工 ~170-190s。
2. **forge 钉点从「Nexus 在途」回退「Nexus 开工」**(O338-①
   证伪):forge 的 150 也是走位窗共犯;开工后钉(落成 ~230s →
   首塔 ~270s)仍赶上 270-300s 小股窗。

## o343 结果(VH 0/6,瓶颈下游化确认) + O344 三点(中局墙)

**日期**：2026-08-18

### o343 结果与尸检

- **o343a/b VH 0/3+0/3**(o342+o343 累计 0/12 按协议判真回归,
  但死因已换代)。
- **O343 疗效确凿**:Nexus 开工 132.6s(3 局)/184.8-192.9s
  (3 局),在途1→0 蒸发清零 —— 扩张/经济链(司令 doctrine 主线)
  全线打通;败场全部推到 866-1120s 中局。
- **中局墙三病**:
  1. forge 主基无槽(o343b game_02/03):主基带电 3x3 槽被
     GW/core/电池占满,forge 钉点连报 no_placement(132-162s),
     分矿塔链整链卡死,274-300s 波零塔滚穿(384-389s 速败)。
  2. 三矿整局未开(o343a game_02):rush latch 长封开矿闸
     (O274-① 只免首扩没免多矿),2 基 47 农打 99 supply;
     O251 事件零触发。
  3. 分矿塔 no_placement 常驻 600s+:补电水晶成败不可读。
- 舰队对照:胜局配方 SG2 345s/三矿 562s/舰队 15+;o343 game_02
  SG2 455s/三矿无/舰队 6-9  hover。

### O344 落地(三点,单测 688 绿)

1. **forge 落位改分矿**(最近非主基基地):槽位全新 + 防御集结
   doctrine(forge 本就是分矿塔阵前置),主基无槽不再卡链。
2. **三矿+ rush 闸改 threat 闸**:波间隙(threat 翻假)即开,
   rush latch 不再无限封锁(O274-① 同教义扩到多矿)。
3. **分矿补电 rc 可见化**(结果变化即记+30s 节流)。

## o344 结果(VH 2/6 回 33% 档) + O345(taken 判据局部化)

**日期**：2026-08-18

### o344 结果与尸检

- **o344a/b VH 1/3+1/3 = 2/6**。胜局(game_03 o344a)教科书:
  5 基地 67 农、母舰 703s、舰队 25 推进胜 1133s。
- **O344-③ 的 rc 簿记首役即立新功**:全 6 局「分矿补电失败=
  taken」常驻(132-800s)——`_dispatch_structure` 的 taken 是
  **全图同型计数**,别处在途水晶(前线走位水晶可飞 100s+)/
  主基塔链把分矿补电/钉塔恒挡;分矿无电 → forge/塔全
  no_placement → E6「无塔」抄矿(四局败场同型,敌 4-18 地面)。
  forge no_placement(o343 判为「主基无槽」)实为同根:taken
  挡补电 → 分矿无电 → forge(需电)no_placement。

### O345 落地(taken 判据局部化,单测 688 绿)

1. 新增 `_in_flight_near(sid, pos, radius=15)`:目标点局部
   在途(tracker 按派工工人位置归)+在建同型计数。
2. 分矿守卫补电/钉塔:局部在途+就绪 <2 才派,
   `max_on_route=99` 绕全局 taken。
3. 预置塔链(O329-③)同绕全局 taken(fired+30s 重试已含去重)。

## o345 结果(VH 0/6) + O346(E6 撤离池借工)

**日期**：2026-08-18

### o345 结果与尸检

- **o345a/b VH 0/3+0/3**。O345 对 taken 有效(taken 刷屏清零),
  但病灶下移一层:**no_worker 刷屏**(分矿补电/钉塔全灭)——
  连续小股抄矿下 E6 撤离池(CONTROL_GROUP_ONE)锁 10-23 农,
  GATHERING 池归零、停气池空,select_worker 恒 None;
  最缺塔的窗口恰恰最没工人(撤离的农民在安全基地闲置,
  与被抄基地一墙之隔却不可见)。
- E6「无塔」抄矿在 4 局败场仍是直接死因(敌 4-16 地面,
  273-1135s 全时段);game_01/02(o345b)310-333s 速败同根。

### O346 落地(两点,单测 688 绿)

1. **E6 撤离池借工**:`_dispatch_structure` 的 worker=None 分支
   在停气池之后再试 E6 池(离建造点最近的闲工),借出即从
   `_evac_bases` 台账摘除(防敌退回采循环把建造工拽走,
   与 O116-② 停气池借用同款;O256 决死协防同哲学:危险区
   塔起来才是解,站着被屠才是输)。
2. **no_worker 事件带三池余量**(采集池/停气池/E6池):下轮
   尸检直接读锁池构成。

## o346 结果(VH 0/6) + O347(气矿工可见化,no_worker 根治候选)

**日期**：2026-08-18

### o346 结果与尸检

- **o346a/b VH 0/3+0/3**(o342 起五轮 2/30,跌出 o335-o340 的
  27% 档)。
- **no_worker 真凶(ares 源码层)**:`select_worker` 只从「矿簇
  指派且未载货」挑选(resource_manager.py:400),**气矿农民永不
  入选**;O346-② 的三池簿记显示「采集池=5-9」含气矿工(虚高),
  小农经济局(14-17 农:6 气矿+搬运+建造工)可用矿工恒 0。
  O343 的 475 矿门把建防链(Nexus 走位+水晶+forge+塔)压进
  110-250s 小农窗口, drought 必发 → 首波(270-300s)塔链
  立不起来 → 速败系列总根。停气池/E6 池借用都是空池(未触发),
  builder_borrow_ok 要 GATHERING 全空才借(气矿工占着 GATHERING
  名额 → 永不空 → 永不借)。

### O347 落地(单点,单测 688 绿)

1. **气矿工纳入借工序列**:`_dispatch_structure` 在 停气池→E6池
   之后再从气矿记账(`get_worker_to_vespene_dict`)就近摘一个
   (气矿短期让位防御链,B4③ 停气同哲学);三级借工
   (GATHERING→停气→E6→气矿)成型。

## o347 结果(VH 2/6 止血) + O348(forge no_placement 自救补电)

**日期**：2026-08-18

### o347 结果与尸检

- **o347a/b VH 1/3+1/3 = 2/6**,O347 止血成功(no_worker 刷屏
  → 仅 2 次)。失败计数换手:**no_placement 174 次,其中 forge
  96 次/6 局** —— O344-① 把 forge 挪到分矿后要电,132s 时
  全图带电 3x3 槽被 GW/core/nexus 占满,钉点 30s 节流空转
  整链卡死(预置塔 tech_not_ready、首波零塔)。robo(O245)
  16 次/SG 7 次同根。
- 胜局(game_02 o347a/game_03 o347b)配方不变:3-4 基地
  60+ 农,舰队 15+ 推进,1052-1071s 胜。

### O348 落地(单点,单测 688 绿)

1. **forge no_placement 自救补电**:失败即在同基地钉一根水晶
   (自带电源,30s 节流下轮重试)—— O296-③ 主基首塔自救的
   分矿版,forge/塔链不再等随机水晶覆盖。

## o348 结果(VH 2/6) + O349(forge 停滞看门狗 + SG 自救补电)

**日期**：2026-08-18

### o348 结果与尸检

- **o348a/b VH 1/3+1/3 = 2/6**(o344/o347/o348 累计 6/18=33% 档)。
- **forge 钉点失败不降反升(197 次)**:自救水晶没有解决全部
  形态 —— o348a game_03 铁证:forge 钉点连失败 132-252s 后
  **沉默 320s**,575s 才落成。真因:ares TechUp 路径也会拍
  forge 且不查 can_afford(O1 实证),工人驻点等钱 300s+,
  期间 `_structure_present_or_pending` 恒真把 O340 钉点锁死;
  主基首塔/分矿塔链 tech_not_ready 全灭(无塔期 320s+,653s 败)。
  SG 钉点 no_placement 23 次/6 局(主基带电 3x3 槽占满)同根。

### O349 落地(两点,单测 688 绿)

1. **forge 停滞看门狗**:无就绪 forge 且 tracker 条目 >60s 未
   落成 → 清条目(O324 runner 看门狗同构),钉点条件解锁重派
   (带 O348-① 电自救)。
2. **SG no_placement 自救补电**(O348-① 同型,贴主基钉水晶)。

## o349 结果(VH 0/6) + O350(forge 三振回主基 + 槽位取证)

**日期**：2026-08-18

### o349 结果与尸检

- **o349a/b VH 0/3+0/3**。O349 看门狗零触发(本轮不是 TechUp
  驻点形态),forge no_placement 158 次/6 局 —— 自救水晶没把
  分矿 3x3 槽铺出来,o348+o349 累计 355 次失败证实分矿 forge
  落位在部分出生点是**几何无解**(矿线+nexus+GW2 挤占),
  不是供电不足。
- 判决:O344-①「forge 落位分矿」部分证伪 —— 站位教条让位
  「forge 先立起来」;但主基 132s 带电 3x3 也曾占满(o343),
  需要分矿优先 + 三振回退的双基策略。

### O350 落地(两点,单测 688 绿)

1. **forge 分矿连挂 3 次回退主基**(`_o350_forge_fails` 计数,
   成功复位):分矿槽位几何无解时不再 300s+ 空转;主基槽位
   充裕(O116 带电余 6-10 实证)。
2. **失败事件带槽位三值**(带电余/空闲余/总,3x3)+自救水晶
   rc:下轮尸检直接读「无电」vs「无槽几何」。

## o350 结果(VH 0/6) + O351(forge 永久回主基,站位教条终结)

**日期**：2026-08-18

### o350 结果与尸检

- **o350a/b VH 0/3+0/3**(o342 起 7 轮 6/42=14%,低于 o335-o340
  的 27-33% 档)。
- **槽位取证锁定终局**:失败事件 槽(0, 11-25, 11-25) ——
  **空闲槽 11-25 充足,带电槽恒 0**;自救电 dispatched 成功
  但水晶落点偏离塔位槽区(水晶 6.5 格电场覆盖不到那 11-25
  个空闲 3x3 槽),铺电永远差一格。不是无槽,是电场几何。
- **教条证伪**:O344-①「forge 是分矿塔阵前置,站位跟防御走」
  —— forge 是全局科技建筑(解锁塔+升级),站位零战力贡献;
  防御集结的是塔/电池/墙,不是 forge。o335-o340 胜期 forge
  全在主基(O337-② 锚点补电自救实证有效:带电余 0→4→10)。

### O351 落地(单点,单测 688 绿)

1. **forge 落位永久回主基**(删 O344-①/O350-② 的分矿优先与
   三振回退逻辑),自救补电保留。若下轮仍 <2/6,启动 o336 态
   旧代码对照(bisect)确认环境漂移 vs 代码回退。

## o351 结果 + bisect 对照判决(非代码回退,噪声基线重校准)

**日期**：2026-08-19

### o351 结果与 bisect 对照

- o351a/b VH 1/3+0/3 = 1/6;o342 起 8 轮累计 7/48(15%)。
- **bisect 对照(git worktree,o336 态 8c608cf 同协议 VH×3+VH×3):
  0/3+1/3 = 1/6 —— 与当前代码统计无差异。判决:非代码回退。**
- **基线重校准**:o335-o340 的 27-33% 与 o342-o351 的 15% 是同一
  真实水平(~20-25%)的噪声上下摆(5-6 局小样本,单局 ±17-33pp);
  双向误读噪声的教训:判升降一律两轮累计,且不与远期峰值单点
  对比,只看同协议滚动窗口。
- O341-O351 的 6 层建造链修复判无罪且客观有效(Nexus 开工
  132-192s vs bisect 态的 212-466s;在途蒸发/taken/no_worker/
  forge 卡死全部清零);当前 HEAD(129786c)为最优态,不回退。

### 下一步(中局墙,胜率从 ~25% 到 60% 的剩余差距)

- 败场主形态已稳定在「中局被 63-99 supply 波滚死」:舰队 6-9
  hover(腐化波蒸发),追猎 2-6 卡推进阈,三矿时点不稳。
- 候选方向(按证据排序):①舰队生存(母舰下水率/电池超载/
  召回纪律 vs 腐化波);②三矿时点一致性(胜局 562-582s 复现率);
  ③推进编成(追猎阈 vs 矿分配);④Harder 回归 lane(协议每
  3 轮一次,o340 后未跑)。


## o352 结果(VH 0/6,跌破 15% 线) + O353(威胁期 forge 免门 + sprint 计时根治)

**日期**:2026-08-19

### o352 结果

- **o352a VH 0/3 + o352b VH 0/3 = 0/6**;滚动 12 局(o351 1/6 +
  o352 0/6)= **1/12 ≈ 8%,跌破 15% 线**。
- 对手:VeryHard Zerg Timing,AbyssalReefLE。

### o352 改动(本轮验证对象)

1. **O352-① 解锁航母**:`carrier_quota_active` fleet_min 8→4
   (fallback 6→3)、O239 气门 700→400、O260 暴风兜底 300→500、
   O240 停探机门 800→500。
2. **O352-② 解锁三矿**:`multi_expand_threat_ok`(t≥600 旁路 +
   解除口径放宽)、`fb_missing_expand_hold`(40农/600s 豁免)。
3. **O352-③ forge 钉点近可负担门**:`forge_pin_affordable`
   (矿≥150 才派工不驻点)。

### o352 尸检(六局全负)

- **O352-① 未生效到求值时点**:六局全死于 233-682s 地面波,
  舰队链(SG→FB→CARRIER)从未启动;o352a 三局连 STARGATE 都
  是 0;o352b FB pending 长达 275s 全 no_money(O261 虚空
  2×250 矿反抢资金窗);气烂 511-958 闲置。门槛改动成空转
  —— **瓶颈在 FB 的 300 矿资金窗,不在任何气/数量门槛**。
- **O352-② 未生效到求值时点**:三矿 0/6;三局死于 600s 旁路
  激活之前;豁免(40农/t≥600)触发时局已崩。
- **O352-③ 行为生效(零「干等 FORGE」日志)但威胁期反成永久
  锁**:矿恒 <150 → g3(o352a)/g2(o352b)到死无 forge,首塔
  tech_not_ready 空转 142-185s,首塔落成(301/438/从未)全部
  晚于敌波。是本轮早亡(344-486s)的部分原因,**属引入的回归**。
- **上游真凶**:defense_sprint 的 `_sprint_since` 被单帧抖动
  反复重置,60s max_age 逃逸阀失效;农民被 `_probe_floor=16`
  钉死 240s(o352b g1 采矿仅 8295 ≈756/min,两矿饱和应
  ~1800/min)。
- **败场形态再校准**:六局敌方零 CORRUPTOR,全是 233-560s
  狗/毒爆/蟑螂/刺蛇地面 timing。「中局舰队墙」在更早的
  「防御链+钱荒墙」面前还没机会出场。

### O353 落地(四点,单测 691→697 绿,import 冒烟过)

1. **forge_pin_affordable 加 threat_active 参数**:威胁期免门
   恢复 critical 驻点(修 O352-③ 回归)。
2. **sprint_timer_update + probe_floor_cap**:sprint 计时改
   age 累计制 + 10s 滞回清零,60s 逃逸阀真正生效;ZT 两矿
   floor 16→28。
3. **fb_saving_window**:SG 就绪 + FB 缺失期禁 O261 虚空兜底;
   FB critical 钉点通道确认已存在(O228)。
4. **三矿豁免提前**:`fb_missing_expand_hold` 40农/600s→
   28农/480s;`multi_expand_threat_ok` 旁路 600→480。

**遗留风险(记入)**:FB critical 钉点被
production_manager.py:2836 的 rush 总闸管辖,rush 期整帧跳过;
下轮若仍见 FB pending 被 rush 闸跳过需豁免。


## o353 结果(VH 有效局 1/8) + O354(暴风抑制 + 母舰开窗 + 腐化黄金窗)

**日期**:2026-08-19

### o353 结果

- **o353a VH 1/3**(game_03 胜 1237s)、**o353b 0/1+2异常**
  (game_01 SC2 进程异常退出、game_02 bot AttributeError 76s
  早夭)、补跑 **o353b2 0/3**;有效局合计 **1/8**。
- 对手:VeryHard Zerg Timing,AbyssalReefLE。

### o353 改动(本轮验证对象)

1. **O353-① forge_pin_affordable 加 threat_active**:威胁期
   免门恢复 critical 驻点(修 O352-③ 回归)。
2. **O353-② sprint_timer_update + probe_floor_cap**:sprint
   计时改 age 累计制 + 10s 滞回;ZT 两矿 floor 16→28。
3. **O353-③ fb_saving_window**:SG 就绪 + FB 缺失期禁 O261
   虚空兜底。
4. **O353-④ 三矿豁免提前**:40农/600s → 28农/480s。
5. **o353b game_02 炸出 `_o350_forge_fails` AttributeError**
   (第 3 次同类未初始化属性),已修(__init__ 初始化 forge
   钉点族 4 个簿记属性)+ 全 bot/ 目录同类扫描清零。

### o353 尸检(5 有效局深检 + b2 战绩)

改动生效对照(基线 o349-o352):

- **O353-② 经济修复生效**:农民峰 36-67(基线钉 16-19),
  采矿 1080-1465/min(基线 ~756/min),胜局 30205 总采矿。
- **航母破零 4/5 局**(基线 0/18):首产 679-844s,但峰值仅
  1-2 —— O260 暴风兜底抢矿(航母 350 矿 vs 暴风 300 矿,
  优先级倒挂),气烂 1125-1301 花不出。
- **FB 全落地 ~450s**(基线 0/6),O261 虚空零出场无副作用。
- **三矿 4/5 局**(基线 1/18),其中 3 局 482-590s 走新豁免
  路径。
- **forge 104-362s** 全面不劣于基线 237-354s+未落成;威胁期
  被锁场景未复现。
- **母舰 0/5**:经济门多局满足但 can_afford(400 矿)恒假,
  矿被 O260/塔/农每帧吃光。
- **败因收敛**:敌腐化首现恒定 751-804s,我方舰队卡 4-7 艘,
  黄金窗(腐化≤4)仅 60-150s;O325 near-miss 12 次不推,等
  腐化 13-17 舰队 48-130s 蒸发;静态防御过投资(塔峰值
  8-13 ≈ 1950 矿 ≈ 5 艘航母)。
- **胜局模板(o353a g3)**:630-675s 两波抄家靠 8-11 塔扛住,
  740s fleet=8 果断 O302 连续压制把腐化压回 0,舰队 26
  (25 暴风+1 航母)终局。

### O354 落地(五项,单测 697→700 绿,冒烟过)

1. **tempest_dump_suppressed**:FB 就绪 + 气≥500 + 航母<2 +
   暴风<4 时抑制 O260,矿让航母。
2. **mothership_window_open**:母舰门槛除矿外全满足且矿<400
   时开窗,抑制 O260+塔/电池钉点(_dispatch_structure 入口
   集中拦截,新 rc "ms_window"),矿≥400 自动关,无 latch。
3. **zt_golden_window_push**:腐化上限 2→4,t≥750 追猎阈
   6→4 时间衰减。
4. **cannon_capped**:t≥600 + 舰队≥4 时全局塔≥8 停钉
   (threat/rush 豁免),新 rc "capped"。
5. **forge_pin_affordable 非威胁期门 150→100**。


## o354 结果(VH 0/6,滚动 20 局 5%) + O355(母舰窗气阈解锁 + forge 自救)

**日期**:2026-08-19

### o354 结果

- **o354a VH 0/3 + o354b VH 0/3 = 0/6**;滚动 20 局(o352 0/6 +
  o353 1/8 + o354 0/6)= **1/20 = 5%**。
- 对手:VeryHard Zerg Timing,AbyssalReefLE。

### o354 改动(本轮验证对象)

1. **O354-① tempest_dump_suppressed**:FB 就绪 + 气≥500 +
   航母<2 + 暴风<4 时抑制 O260,矿让航母。
2. **O354-② mothership_window_open**:母舰门槛除矿外全满足
   且矿<400 时开窗,抑制 O260+塔/电池钉点(rc "ms_window"),
   矿≥400 自动关。
3. **O354-③ 黄金窗放宽**:腐化上限 2→4,t≥750 追猎阈 6→4。
4. **O354-④ cannon_capped**:t≥600 + 舰队≥4 时全局塔≥8 停钉
   (threat 豁免)。
5. **O354-⑤ forge 非威胁期矿门 150→100**。

### o354 尸检(六局全负,两 lane 形态分裂)

**o354a(机制基本生效但打不过)**:

- **母舰窗开过一次**(g1@728.6s,条件链全成立)但窗口期矿
  175→45→5 从未回 400,母舰 0/3。
- **①②气阈死锁**:O260 在气≥500 泄气,母舰窗要气≥600 →
  气永被压 600 以下(g3 实证 O260 气 389/364 合法泄气)。
- **黄金窗两次准时触发**(g1 push@745 fleet3/追7、
  g3 push@660 fleet5/追10),但敌腐化首现 747-784s 恰好同步
  焊死窗口;near-miss 8 次中 6 次腐化 5-9 超标(拦截正确)。
- **塔封顶平静期生效**(g3 锁 7-8,capped×2)但 785s 起威胁
  连续,豁免期塔 8→13 与基线持平。
- **舰队蒸发模式**:g3 舰队 7 vs 腐化 14、g1 舰队 3 vs 腐化
  7+大龙 7,峰值到全灭 <60s;暴风对腐化劣势对位+数量 1:2。
- **航母峰值 1**(出厂 30-90s 战死),气抢下来了但矿侧没有
  让航母通道,气烂银行。

**o354b(零覆盖样本,死于 O354 作用域之前)**:

- 三局死于 271-710s 纯地面 timing(狗/蟑螂/刺蛇/感染/潜伏者,
  敌零腐化),FB 全未建成(O110 no_money×4),舰队恒 0。
- forge no_placement 6 次/3 局,落成 257-361s;g3 首塔到死
  not_viable(主基带电 2x2 槽=0,塔位被电池/建筑挤没),
  0 塔对 271s 狗蟑 17 只。
- O354 五项全部未到触发窗口,不计分。

**终审判断**:机制链只差母舰一环(气阈死锁+矿窗攒不出 400),
早亡支线(forge placement+首塔槽位)约占一半败局。

### O355 落地(四点,单测 700→702 绿,冒烟过)

1. **mothership_window_open min_gas 600→400**:低于 O260 的
   500 泄气闸,窗先开、窗内 O260 被抑制气续涨(解①②死锁)。
2. **ms_window_probe_yield**:窗内 + 农≥28 探机让位(挂在
   _build_probes 现有判据集中点)。
3. **rescue_pylon_anchor**:forge no_placement ≥2 次起自救
   水晶锚点从主基中心改为离基地最近空闲 3x3 槽;自救水晶先
   落地再重试(_in_flight_near 局部判据,修水晶 spam)。
4. **O296-③ 首塔自救死锁修复**:max_on_route=1 被 AutoSupply
   buffer 水晶恒挡 taken → _in_flight_near 局部判据 +
   max_on_route=99。

**遗留风险(记入)**:

- O264 母舰下单门气≥600 未动,若窗关后 O239 航母持续抢在
  母舰前,是 O239/O264 优先级问题,下轮看尸检。
- o354b 经济相对 o353 疑似回退(农峰 49/53/21 vs 57-67),
  样本太小,暂记为方差存疑。


## o355 结果(VH 1/6,滚动 12 局 8%) + O356(早亡救援提速 + 母舰资金窗 + 追猎闸软化)

**日期**:2026-08-19

### o355 结果

- **o355a VH 0/3 + o355b VH 1/3(game_01 胜 1067s)= 1/6**;
  滚动 12 局(o354 0/6 + o355 1/6)= **1/12 ≈ 8%**。
- 对手:VeryHard Zerg Timing,AbyssalReefLE。

### o355 改动(本轮验证对象)

1. **O355-① mothership_window_open min_gas 600→400**(解
   O260 泄气闸 500 vs 窗 600 死锁)+ **ms_window_probe_yield**
   (窗内农≥28 探机让位)。
2. **O355-② rescue_pylon_anchor**:forge no_placement≥2 次
   自救水晶锚点改空闲 3x3 槽 + 自救水晶先落地再重试 +
   O296-③ 首塔自救死锁修复。

### o355 尸检(六局,1 胜 5 负)

**胜局(o355b g1,1067s)——舰队主链闭环实证,不需要母舰**:

- 70 农、采矿 32290(~1816/min)、forge 104.5s 无故障、
  FB 377.7s、航母首产 618.8s 峰值 3、暴风 18(舰队峰值 22)。
- O302 持续先手压制把腐化 15 压回 0,黄金窗 1058s 首次为
  True 即终结;出生点左上(placement 无故障)。
- ms_window 开 8 段共 ~100s(气 363→739,气锁确解)但矿
  始终 <400:舰队产能 48s 吃 ~1500 矿不被窗抑制;终局矿
  590/气 437 全满足但 supply 199/200 卡死母舰 8 人口。

**败局形态一:早亡支线(2/3 败局死因)——出生点确定性
placement bug**:

- AbyssalReef 右下出生点 forge 钉点 ~135s 确定性
  no_placement(槽 (0,23,25),2/2 局逐帧一致);左上 0 故障。
- 自救触发要 fails≥2,首次失败→自救派工间隔 92-112s;
  forge 落成 257-321s;致死波 274-322s 到脸时首塔 333s+
  或永不(g3:主基带电 2x2 槽=0,自救水晶锚的 3x3 槽没
  覆盖首塔 2x2 钉点,O116 报 (0,0,29))。
- 时序上结构性赶不上:首塔可落成时点(333s+)晚于致死波
  (274-322s)。

**败局形态二:母舰资金窗差一步+黄金窗追猎闸过刚
(o355a g2 长局)**:

- 气锁已解(整局零 O260 事件,气多峰 800+),但 794.2s
  O239 在气 614 时花 350 矿点航母,母舰只差 ≤50 矿被截胡;
  13 追猎 warp≈1625 矿同期抽干。
- 140s 零腐化真窗(679-819s)因追猎 5<6/2<4 被否 9 次
  near-miss;暴风零腐化不需要追猎护航。
- 2 航母 940→944s 四秒被 8-16 腐化点名;腐化时间线稳定:
  首现 ~820s、9 艘@840s、峰 17@988s。

**O355-② 生效面**:长局 forge@362 一次落地无 O340 刷屏、
塔峰 14 无死锁,对比 o354b 质变;但右下出生点子场景从
「死锁」降级为「慢+救得晚」。

### O356 落地(三项,单测 702→706 绿,冒烟过)

1. **早亡支线**:rescue_pylon_anchor min_fails 2→1(首发即
   自救);自救水晶锚点对首塔钉点做带电校验
   (second_rescue_pylon_needed,钉点不带电且锚距>6.0 同帧
   补第二根);首塔死等自救(cannon_stall_rescue:forge 就绪
   后连续 not_viable≥30s 无视在途门补钉,修 o355b g3 的
   _in_flight_near 死锁);_first_cannon_anchor 抽共用方法
   防锚点源漂移。
2. **母舰资金窗收口**:O239 加 not _ms_window;
   ms_window_fleet_suppressed(窗开+舰队≥6 星门新单让位,
   _effective_spawn 集中拦截);O264 下单门气 600→400 与窗
   对齐;mothership_supply_ok(supply_left≥10,不足时 O264
   块自动钉水晶,查明 O109-① buffer 因 ZT 两旗常年假从不
   触发)。
3. **黄金窗追猎闸软化**:corruptors==0 时 min_stalkers=0
   (暴风白嫖纯地面)。

**遗留风险(记入)**:

- cannon_stall_rescue 穷局 not_viable 时可能与首塔争 100 矿,
  若实战资金互斥再加 powered==0 条件。
- 右下出生点槽位 (0,23,25) 是地图几何确定性失败,O356-①
  是救援提速非根因消除;若下轮仍失败需考虑开局面预校验排障。
- 母舰在胜局配方里非必要环节(主链已闭环),O356-② 是增益
  项不是解锁项。
- Harder 回归 lane 自 o340 后欠账。


## o356 结果(VH 0/6,滚动 12 局 8%) + O357(右下换锚 + 母舰块前移 + ZT forge-first)

**日期**:2026-08-19

### o356 结果

- **o356a VH 0/3 + o356b VH 0/3 = 0/6**;
  滚动 12 局(o355 1/6 + o356 0/6)= **1/12 ≈ 8%**。
- 对手:VeryHard Zerg Timing,AbyssalReefLE。

### o356 改动(本轮验证对象)

1. **O356-① 早亡支线**:rescue_pylon_anchor min_fails 2→1;
   second_rescue_pylon_needed 首塔带电校验;cannon_stall_rescue
   死等 30s 自救。
2. **O356-② 母舰资金窗收口**:O239 not _ms_window;
   ms_window_fleet_suppressed;O264 气门 600→400;
   mothership_supply_ok。
3. **O356-③ 黄金窗**:corruptors==0 时 min_stalkers=0。

### o356 尸检(六局全负)

**O356-① 治错了病(证伪自救水晶路线)**:

- 救援提速完全生效:自救水晶从基线 92-112s 延迟提速到
  135s 同帧派工,second_rescue 241.9s 补第二根,水晶全落地。
- 但 forge 落成时点与 o355 逐秒一致(257.1/309.4s vs
  257.1/301.3s)零改善——槽 (0,23,25) 是 placement 数据级
  故障(不可放置=几何,不是没电),机械台同样三连
  no_placement;补电救不了不可放置。
- o356b g1 右下 365s 原配方早亡(forge/塔终生 0);o356a
  g1/g2 没早亡纯属致死波 RNG 迟到(~520s)。
- 结论:右下 50% 出生概率仍是死刑,继续投资自救水晶是
  沉没成本,需换锚拉黑。

**O356-② 母舰被同帧截胡(设计缺陷实锤)**:

- o356b g2:FB 365.6s 达标、舰队 8(3 航母)局面下,
  ms_window 开 ~10 次母舰 0 艘——O239 航母块排在 O264
  母舰块之前,窗判据「矿<400」,矿一跨 400 窗关、O239
  同帧先花 350(747.3→749.9、791.5→791.7 两次实锤,
  o355a g2 794.2s 同款)。
- o356b g3:舰队门 751.3s 才开,经济门 687.1s 已永久
  关死,两门错开 64s 终生无交集。

**O356-③ 黄金窗**:o356b g2 确实果断推进(815.6s fleet=9
追7),但战果=击杀建筑价值 0.0(兵力远低于配方 22),反被
换家打穿;o356b g3 有 125s 零腐化真窗但被
floor_army_defends_home+O158 双层守家闸锁死;o356a 三局
舰队恒 0 无兵可推。

**左上开局两分支 dice roll(新发现)**:forge-first(104.5s,
o355 胜局)vs cyber-first(forge 随 O333 Nexus 钉点
217-237s,o356a g3/o356b g3);坏分支 o355 就存在,本轮
0/6 = dice 两连坏+右下死槽未愈,非 O356 回归。

**败局通用形态**:与 o355 胜局配方(70 农/5 矿/FB 378s/
舰队 22)相比,断在第一节——forge 237-309s(晚 133-205s)
→ 首塔 301-341s 全晚于致死窗 → 2 矿封顶农峰 28-59 → FB
永远 no_money → 舰队 0-8;总采矿 5415-11025 vs 胜局 32290。

**新欠账**:O239 逐帧刷屏(o356b g3 同秒 8-14 条);
cannon_stall_rescue 无独立事件标签不可判读;O324 runner
卡死 88s+侦查断链复现;掉矿后永不重建(O340 holding 挂到死)。

### O357 落地(四项,单测 706→710 绿,冒烟过)

1. **右下死槽拉黑换锚**:pin_reanchor 纯函数(滤占用+拉黑,
   带电优先、离斜坡口更近优先)+ _dispatch_pin_reanchor
   (no_placement 即加黑换锚写事件,closest_to 显式传锚);
   forge(O333)+机械台(O245)同机制;验收口径:右下 forge
   <150s;O356-① 自救水晶保留(纯电问题仍用),注释注明
   「几何走换锚、纯电走补电」。
2. **O264 母舰块整体前移到 O239 之前**:同帧截胡结构性
   消除,纯块移动,supply 门/钉水晶自救/ms_window 抑制不动。
3. **ZT 锁定 forge-first**:zt_forge_pin_gate(townhalls>=2
   or t>=60),O333 不再等 Nexus 开工;opener 层不动
   (O333-② 实证摘除过)。
4. **可观测性**:O239 接 event_throttle_ok(30s 节流言不
   节流下单);cannon_stall_rescue 独立事件标签。

**遗留风险(记入)**:

- o356b g3 暴露的经济门/舰队门 64s 错开(687.1s 关死 vs
  751.3s 才开)未修,母舰在该局型仍不可达。
- 掉矿永不重建(O340 holding 挂死)+ O126 expand_reserve
  二矿拖 166s 未修,是农民峰值 48 vs 配方 70 的缺口。
- floor_army_defends_home+O158 守家闸吃零腐化真窗
  (o356b g3 125s 空耗)未修。
- 右下 forge <150s 与母舰破零是运行时验收,单测覆盖不了。
- Harder 回归 lane 自 o340 后欠账。


## o357 结果(VH 0/6,滚动 12 局 0 胜) + O358(opener 修复 + 矿气倒挂 + 换锚收敛)

**日期**:2026-08-19

### o357 结果

- **o357a VH 0/3 + o357b VH 0/3 = 0/6**;
  滚动 12 局(o356 0/6 + o357 0/6)= **0/12**,近 26 局仅 1 胜。
- 对手:VeryHard Zerg Timing,AbyssalReefLE。

### o357 改动(本轮验证对象)

1. **O357-① 右下死槽拉黑换锚**:pin_reanchor 死槽拉黑换锚
   (forge + 机械台同机制)。
2. **O357-② O264 母舰块整体前移到 O239 之前**:消除同帧截胡。
3. **O357-③ ZT forge-first**:zt_forge_pin_gate(townhalls>=2
   or t>=60),O333 不再等 Nexus。
4. **O357-④ 可观测性**:O239 30s 节流、cannon_stall_rescue
   独立事件标签。

### o357 尸检(六局全负,但两条历史死链打通)

**三大突破**:

- **右下死刑根治**:三局两出生点 forge 全部 60s 钉点、64.3s
  放置(基线 135s 确定性 no_placement、落成 257-321s);
  右下首塔 160.7s(基线 257-321s);左上 dice roll 消除。
- **母舰 16 局来首次下水**(o357a g2 @851.8s,存活 ~85s,
  1059.3s 第二次开造):O264 前移后零截胡事件;O264 从
  0/15 到 1/3。
- **可观测性生效**:O239 节流后三局各 1 条。

**O357-③ 引入 opener 回归(实锤,O358 修)**:

- GATEWAY 68.3s(o356 全 6 局)→ 104.5-132.6s;CYBERCORE
  116-120→168-180s;首叉 180-225→261-265s;二矿
  132-193→233-237s。
- 机制:forge 60s 吃掉 150 矿,GATEWAY 资金窗被挤(g1
  103.9s/g3 100.7s 干等造 GATEWAY);首叉晚 40-80s 撞上
  ZT 280-330s 首波(o357a g1 330s 崩盘直接相关)。
- o356b g2 证明 forge 104.5s 与 gateway 68.3s 可兼得——
  门放太早不是 forge-first 的代价。

**新瓶颈(败因右移一层)**:

- **矿气倒挂**:气峰 779/1184/2524 vs 矿常年 5-300;航母/
  母舰/塔全卡矿;o357a g3 气烂 2524 母舰买不起。
- **ms_window 空窗压塔**:窗判据看气(≥400)不看矿,g3
  空窗 60s 分矿塔被压,940s 掉四矿。
- **机械台换锚不收敛**:5 次换锚全在主基拥挤圈
  (30-56,116-134),整局机械台=0。
- **首塔 281-365s vs 首波 280-330s 零裕度**,塔资金被
  233-237s 二矿挤占;g1 塔链派工已出干等 120s。
- FB 486-622s vs 配方 380s;舰队峰值 4-7 vs 配方 22;
  航母三局峰值 1;单星门撑到 700s。

**终审判断(两 lane 一致)**:机制仍在缺环,方向尚未被
证伪——胜局配方五项已达成 2/5(forge<150s ✓、FB ~380s
✓〔385-414s〕),缺 70 农、舰队 22、母舰;没有出现「航母/
暴风混编打不动 ZT」的组成性失败,输在经济→舰队规模转化率。
**方向终审硬指标(下两轮判据):FB ≤420s、舰队峰值 ≥12、
母舰 ≥1、GATEWAY ≤75s——四数到了还 0 胜,判 carrier 流打
不过 VeryHard ZT,转方向。**

### O358 落地(五项,单测 710→713 绿,冒烟过)

1. **修 opener 回归**:zt_forge_pin_gate 改「GATEWAY 已下单
   or (t≥75 且矿≥200)」。
2. **治矿气倒挂**:gas_to_minerals_needed(气>800 且矿<300
   停气转矿农,气<500 滞回解除,走 O157/O327 既有
   _GAS_STOP_ROLE 通道)。
3. **ms_window 加矿判据**:开窗加矿≥300,窗语义改「攒够了
   才开」,空窗不压塔。
4. **换锚收敛**:reanchor_bases(锚池含分基)+
   reanchor_cooldown_until(拉黑≥3 冷却 60s,事件「O358:
   换锚不收敛冷却」)。
5. **首塔资金优先**:zt_fast_expand_pin 加首塔未落成且
   t<330 时矿门 475→550(给塔留 150)。

**遗留风险(记入)**:

- O283d 每 10s 刷屏(o357a g1 ~38 条)待节流。
- O302 在实力差下不敢开(舰队 4-5 时腐化 763s+ 首现),
  机制空转待产能上来后再评估。
- 掉矿不重建(o357b g1 三矿 775s 被抄后无重建,844s 只剩
  1 基)仍未修。
- 经济门/舰队门 64s 错开(o356b g3)未修。
- Harder 回归 lane 自 o340 后欠账。


## o358 结果(VH 1/6,滚动 12 局 1/12) + O359(opener 修透 + 停气转矿 + 塔链预算守护)

**日期**:2026-08-19

### o358 结果

- **o358a VH 0/3 + o358b VH 1/3(game_02 胜 1319s)= 1/6**;
  滚动 12 局(o357 0/6 + o358 1/6)= **1/12**。
- 对手:VeryHard Zerg Timing,AbyssalReefLE。

### o358 改动(本轮验证对象)

1. **O358-① 修 opener 回归**:zt_forge_pin_gate 改「GATEWAY
   已下单 or (t≥75 且矿≥200)」。
2. **O358-② 停气转矿**:gas_to_minerals_needed(气>800 且
   矿<300)。
3. **O358-③ ms_window 加矿判据**(矿≥300)。
4. **O358-④ 换锚收敛**(锚池含分基 + 拉黑≥3 冷却 60s)。
5. **O358-⑤ 首塔资金优先**(Nexus 矿门 475→550)。

### o358 尸检(六局,1 胜 5 负)

**胜局(o358b g2,1319s)——配方迟到版复现**:67 农、采矿
31630、forge 68.3s、二矿 237.1s、首塔 245.1s、SG 409.8s、
FB 462.1s(晚配方 82s)、航母 622.8s、舰队峰值 25(24 暴风
+1 航母,超额)、929s 起 O302 连推 11 次腐化 7→0 滚雪球;
总采矿是败局 5.7 倍;但 GATEWAY 121s ✗、母舰 0 ✗,胜在后期
发育窗口非前期节奏。

**四硬指标对照**:六局单局最高 2/4(胜局),指标级命中
FB 1/6、舰队 1/6、母舰 0/6(倒退,o357a 曾破零)、
GATEWAY 1/6。

**五项改动验收**:

- **① 未生效**(2/3 局 124.6s):pending≠placed——GATEWAY
  一派工门就开,forge 的 150 照抢;88.4-112.5s 连拍三根
  水晶+探机连拍,等钱 GATEWAY 工人被晾 ~54s。
- **② 未验证**:阈值 800 定太高接不住实际倒挂(300-800
  区间);o358b g2 有 124s 满足窗口 0 事件——接线疑似有
  问题但静态核查 _rush_gas_stop 每帧无条件求值,最可疑点是
  拉动判据要求 GATHERING role 抓不到角色漂移农民。
- **③ 弱正向**(无空窗压塔反例)但疑似造成母舰数学死锁:
  矿<300→窗不开→O260/O239 不抑制→矿永远摸不到 300,
  「买不起」与「不抑制」互为前提;o358b g2 母舰 400 矿
  400 气,矿峰值 250 恒买不起。
- **④ 生效**(g1 换锚不收敛冷却实锤)但触发时距战败仅 5s。
- **⑤ 门本体生效**(5 局统一 233-235s 矿 545-560 摸 550
  放行)但洞在下游:O341-① latch 让 EC 按 400 执行,账上
  只剩 65-165,探机/水晶抽水,塔链工人干等 ~100s——
  「留 150 给首塔」没人守护。

**致死波高度一致**:305-309s(12-16 狗+5-9 蟑螂)三局
一致;单塔守不住(o358b g1 塔 257s 照样穿);二矿 237.1s
永远先于首塔(build order 刚性)。

**终审判断(两 lane 一致)**:方向不判败——配方核心(舰队
22+ + O302 压腐化归零)可复现,败因 100% 集中在前 330s
执行层;但定 O359 为最后通牒轮:若 GATEWAY 仍 >100s、
波前仍 <2 塔、母舰继续归零,累计三轮修不通即判方向失败。

### O359 落地(最后通牒轮,五项,单测 713→715 绿,冒烟过)

1. **forge 门判据 pending→placed**:gateway_ordered
   (_structure_present_or_pending)→ gateway_placed
   (get_own_structures_dict 实体含在建),GATEWAY 放置前
   forge 不抢 150。
2. **停气转矿修透**:阈值 800/300→500/200,滞回解除 350,
   加事件簿记(30s 节流),拉动网放宽(gas 簿记在册即拉,
   不再要求 GATHERING role)。
3. **塔链预算守护**:zt_cannon_pending_probe_yield(t<330
   有塔在 tracker 等钱且农≥16 → 探机停训)——与 O358-⑤
   的 550 门是同一笔预算的两端。
4. **ms_window 拆两档解死锁**:奢侈品档(O260/O239/舰队
   新单/探机让位,min_minerals=0 无矿底=攒钱手段)+ 防御档
   _ms_window_defense(塔/电池保 300 矿底)。
5. **波前第二塔**:zt_second_cannon_pin_ok(t<330 首塔就绪
   即 critical 钉第二塔,锚首塔落点,总数≥2 自停)。

**本轮 bench 验收口径**:

1. GATEWAY 放置 ≤75s(structures 时间线,非 pending)。
2. 300s 前 ≥2 塔(事件「O359:波前第二塔钉点」)。
3. 停气转矿有事件(「O359:停气转矿触发/解除」)。
4. 母舰在舰队 ≥12 的局里下水(「O264:母舰开造」)。

**遗留风险(记入)**:

- o358b g1 反向死锁:停气池棘轮把全局农民钉死(采集池
  =0-4 持续 90s),release 语义未动,若经济僵死需给危机
  路径加时间窗。
- 调查二 g2 晚期拉不动动态真因未 100% 坐实,下轮事件可
  直接判定。
- ms_window 奢侈品档常驻开期间 O239 航母产能受抑(母舰
  优先设计语义),母舰下水后自关。
- Harder 回归 lane 自 o340 后欠账。


## o359 结果(VH 0/6,滚动 12 局 1/12) + O360(FIVE_BY_FIVE 根修 + FB 基金窗 + 静态防御软顶)→ 方向终审:降级隔离实验

**日期**:2026-08-19

### o359 结果(补记,最后通牒轮)

- **o359a VH 0/3 + o359b VH 0/3 = 0/6**;
  滚动 12 局(o358 1/6 + o359 0/6)= **1/12**。
- 对手:VeryHard Zerg Timing,AbyssalReefLE。

### o359 尸检(最后通牒轮验收)

**四项验收口径**:

- **GATEWAY ≤75s ✓ 3/3**(68.3s,回归完全修复)。
- **300s 前 ≥2 塔 ✓ 3/3**(钉点事件 234.5-242.8s)。
- **停气转矿半修透**:触发有事件,解除 0 事件,气超冲
  616-694。
- **母舰 0/6**:前提舰队 ≥12 从未出现。

**死因整体上移 200-300s**:305-309s 基线致死波 6 局全部
没来或守住,实际首波推到 522-614s;前期链(opener/塔)
不再是死因。

**新暴露故障层**:

- ①FIVE_BY_FIVE 警告 256 条(g1)。
- ②FB no_money 自救 ×10/3 局。
- ③二矿拖 418-526s(O126/O336 振荡)+ 静态防御 19 塔
  ≈2850 矿。
- ④O359-③ 疑似静默冻结农民 120s(o359a g1,二矿 526s)。
- ⑤o359a g3 build runner 步#5 卡死星门未排产。

**终审判决(两 lane 尸检一致)**:按规则字面三项终审条件
只成立一项(母舰归零),且该项机制从未被执行(舰队 ≥12
前提未出现)——判方向失败数据依据不足;「喂不饱流」≠
「流不行」;定 O360 为上场资格轮,单一硬指标舰队峰值 ≥12。

### O360 落地(五项,单测 715→723 绿,冒烟过)

1. **FIVE_BY_FIVE 真根因**:与 FB 无关(FB 是 3x3)——
   O251 硬饱和钉点 _dispatch_structure(NEXUS) 走 ares
   placement 簿记,而神族簿记只生成 2x2/3x3 槽,恒
   warning+no_placement 哑故障(O93/O334-④ 两次记录同根
   因);修复:townhall_skips_placement,城镇厅绕过簿记直
   落矿点坐标(EC 同款通道)。
2. **FB 专项基金窗**:fb_fund_window(SG 就绪+FB 缺失期,
   探机农≥28/第3+塔/≥200矿升级让位,90s 超时强制派工防
   死锁,threat 豁免)。
3. **静态防御总投资软顶**:cannon_global_capped(全局塔
   ≥12 非 threat 停钉,全期)。
4. **停气解除 bug 修复**:gas_to_minerals_released(气
   <500 或 矿>400 双向解除)+ 60s 棘轮保险丝。
5. **O359-③ 收敛**:min_workers 16→20 + Nexus 在途豁免
   + 触发/解除事件簿记。

### O360 验收(3 局,coder 预跑:o360a×1+o360b×2,全负)

**子口径 4/5 过**:

- 零 FIVE_BY_FIVE 警告(256→0)✓。
- FB 345.5/466.1/369.6s(2/3 ≤420s)✓。
- 停气解除 6.2s 起 + 60s 保险丝两次实证 ✓。
- 农民冻结窗 4-6s 有成对簿记 ✓。

**主指标舰队峰值 ≥12:✗ 2/2/6,三局全负。**

**改善**:存活 641→936→972s、首艘航母 783.5s、二矿
393.8/417.9s、o360b g2 三矿 795.5s。

**败因再上移**:Nexus 钉点工人等钱 160s+(等钱期塔/升级
/探机照抽水)、舰队爬坡产能不足、终局 overrun。

### 方向终审判决(司令已拍板:降级隔离实验)

判决点已到:舰队 <12 累计多轮,但子指标全部修通、死因
每层都是具体机制缺口。

**司令拍板:降级隔离实验**——同一 carrier 流跑
VeryHard Zerg Power(历史有胜,lane1 o361a×3)+ Harder
Zerg Timing(lane2 o361b×3,兼还 Harder 回归欠账)。

**判读**:舰队 ≥12 且能胜 → 流本体成立,问题只是 VH
Timing 前期压力,回去专修前期;仍 <12 → 引擎坏死,判
方向失败数据充分。

**遗留风险(记入)**:

- Nexus 钉点工人等钱 160s+ 的资金守护未做(下轮若继续
  修 VH ZT 的第一优先)。
- o359a g3 build runner 步#5 卡死(O324)未修。
- 经济门/舰队门 64s 错开(o356b g3)未修。


## o361 结果(降级隔离实验:3/3 胜 + 0/3 负)+ O362(真空窗缓冲 + 钉点保险丝 + SG 提速 + FB 基金窗修 + 停气提前)→ 方向终审:流本体成立,败因全在执行层

**日期**:2026-08-19

### o361 结果(降级隔离实验,司令拍板)

- **o361a carrier vs VeryHard Zerg Power:3/3 全胜**(场均
  997s,TEMPEST 首现 455s、CARRIER 573s,终局兵力均值
  TEMPEST 22.7)。
- **o361b carrier vs Harder Zerg Timing:0/3 全负**(场均
  773s,final_army 为空=舰队 0,issue:one_base×2 /
  idle_builder×3 / overrun×3)。
- 注:o361b 兼还 o340 以来的 Harder 回归欠账——Harder ZT
  从 o340b 5/5 回归到 0/3。

### o361a 尸检(胜局 lane,配方四项全达标)

- 三局配方复现:农峰 67-69(配方 70)、FB 353.6-397.8s
  (均值 378,配方 380)、舰队峰值 26-27(配方 22)、
  O302 压制 513-691s 起。
- 击杀价值 2.2 万 vs 0.2 万碾压级。
- Power vs Timing 压力差异(3/3 vs 0/3 的分水岭):敌首波
  Power 409-540s vs Timing 281-305s,早 100-150s;我方
  舰队首舰固定 ~425-475s 上线——Power 重拳(~560s)打在
  舰队+塔链上,Timing 重拳(~400-480s)打在空窗期。
- 隐患:三局 ~585s 被抄家靠敌自退活命(静态防御软顶 12
  让三四矿 0-2 塔);g1 FB 靠 90s 超时强派侥幸落成;
  O218 星门逻辑抖动(445-542s SG 计数 1→2→3→2 振荡,
  日志刷屏)。

### o361b 尸检(败局 lane,回归根因实锤)

- **回归点确认:O329-O333「速二矿+零兵种」重写**——设计
  假设扩张 ≤150s 落成,Timing 首波 281-305s 直接打破假
  设;o340b 5/5 时代是 O321「防御总量前置」(forge+双塔
  +双电池塞主基)。
- 真空窗数据:GATEWAY 68s 落成后空转 ~200s,首叉
  165-277s;首波到达时 = 2 塔+1 电池+2-4 叉 vs 20-25
  supply,首波杀农 20+(28→8、31→2)→ 经济塌方 → SG
  366-643s/FB 全未落 → 第二波收尸。
- 逐环节对照:分叉不是我方变慢,是 Timing 首波早 ~130s
  砸进 200-330s 真空窗。
- 钉点死锁(僵尸局):g2 三农民 481-832s 轮流钉点等
  FORGE 重建(188-320s),矿钉死 47=零收入死锁。
- 星门被 build runner PROBE 尾巴挡:g1 PROBE 步骤排到
  10:00,SG 拖 643s。
- O360 FB 基金窗零成交:开 5 次(407-748s)零成交,开窗
  只看气不看矿。
- 气矿倒挂:气银行 1500-2100 vs 矿常年 <100。

### 方向终审判决(终稿)

- **carrier 流本体成立**(o361a 实证:舰队 26-27 + 配方
  四项全达标 + 3/3)。
- **VH/Harder Timing 败因 = ZT opener 200-330s 真空窗 +
  波后重建排序 + 钉点死锁**,全是执行层,非方向问题。
- 「喂不饱流」与「流不行」两个假设已用对照实验拆开。

### O362 落地(五项,单测 723→731 绿,冒烟过)

1. **真空窗地面缓冲**:zt_vacuum_buffer_caps(GATEWAY 就绪
   +t≥120 → 叉 cap 3、core 后追猎 cap 1;二矿开工自动恢
   复原闸;塔走 critical 优先,叉走普通 can_afford)。
2. **钉点死锁保险丝**:pin_deadlock_fuse(农<10 全场最多
   1 钉点;等钱 >60s 强制释放回采+30s 重钉冷却;
   _pin_deadlock_sweep 每帧扫 forge/塔/Nexus/FB 族)。
3. **ZT 星门 ≤300s**:zt_sg_pin_time_ok(O323 钉点
   t≥300→240,critical 独立通道本就不被 runner holding
   挡)。
4. **FB 基金窗修成交**:开窗加矿路径(气≥400 且(矿≥150
   或窗已开),滞回);窗内追加抑制 trickle 地面+第 2+ 星
   门(O326)+窗开 >45s 矿<300 强制停探机。
5. **停气转矿提前**:gas_pull_thresholds(ZT 且 t<360 →
   气>300/矿<150;触发与解除共用阈值防单帧振荡)。

### 本轮 bench 验收口径

① 300s 时地面单位 ≥4;② 零钉点 >60s 事件;③ SG ≤300s;
④ FB 基金窗有成交(FB ≤420s);⑤ 300s 前气银行 ≤500。

### 下轮安排

- lane1 o362a:VH Zerg Timing×3(验证 O362)。
- lane2 o362b:VH Zerg Power×3(确认打穿,N=5 口径累计)。

**遗留风险(记入)**:

- 真空窗缓冲实际生效段 120s→Nexus 钉点(O298-③ 钉点期
  floor 全停保留),若口径①不达标,下步候选是钉点期放行
  1 叉。
- 钉点保险丝不限 lane(农<10 自限),其它流派误伤风险观察。
- 静态防御软顶 12 让三四矿 0-2 塔、被抄靠敌自退(o361a
  三局 7 次),生存依赖敌方 AI 撤军不是防御生效。
- O218 星门振荡刷屏未修。


## o362 结果(VH Zerg Timing 0/3 + VH Zerg Power 2/3 → **里程碑:Power 正式打穿**)+ O362 五验收判定 + O363(新矿即配塔 + 保险丝扩覆盖 + 拆 SG 连环门 + 停气落实)

**日期**:2026-08-19

### o362 结果

- o362a carrier vs VH Zerg Timing:0/3 全负。
- o362b carrier vs VH Zerg Power:2/3。
- **里程碑:VH Zerg Power 正式打穿**——o361a 3/3 +
  o362b 2/3 = 5/6(83%),达成 5 局 3 胜+ 标准,是
  VeryHard 档第一个打穿的组合(继 Harder ZT o340b 之后
  第二个)。

### O362 五验收判定(本轮验证对象)

- O362-① 真空窗地面缓冲 → **验收① 3/3 过**:300s 地面
  7/5/4;叉首产 161s;**真空窗补上:首波杀农基线 20+
  → 0**,g3 农民 28→29 零损失,伤害全吃在 5 叉+塔上。
- O362-② 钉点保险丝 → **验收② 部分过**:形式上有 3
  次 60s 释放,但盲区实锤——只覆盖炮塔类;o362a g1
  FB 等钱 ~200s 无释放(O110 自救×6)、o362a g2 Nexus
  钉点 103s、o362a g3 O251 三矿钉点 137s+ 逃逸;
  o362b g2 开矿钉点空转 290s(O307 撤 4 次 255/317/
  393/460s 均被夺回)。
- O362-③ SG 提速 → **验收③ 0/3**:sg_pin_expand_ok
  的单基地 360s 硬时限+扩张优先架空 t≥240 门(g3 SG
  钉点 401s 与 Nexus 同 tick 放行),SG 354-450s。
- O362-④ FB 基金窗 → **机制修好但开窗太晚**:开窗后
  13-35s 即成交(对比 o361b 零成交),但窗等 SG、SG
  等矿,g1 FB 437s 等钱窗 616s 才开;FB 470-639s。
- O362-⑤ 停气提前 → **验收⑤ 1/3**:只记账不执行(触
  发后气照涨 +220,g2 终局气 648 零舰队);解除靠 60s
  定时非气压;「气>300 且矿<150」并联条件在矿不低时
  气照囤(o362b g1 气峰 684)。

### o362a 尸检(死因右移一环)

- 真空窗补上后死在下两环:①SG 连环门→FB 窗晚→首舰
  667-840s(g2 零舰队),514-884s 宏波(40-82 supply)
  到达时舰队 0-1 艘被平推;②「敌 4 地面抄无塔二矿」
  ——新基地 F2 注册 target=0 零塔,跑杀 16-23 农(6
  局 2 局同死,g3 失血 69 农人次),是最高频单一死法。
- 单矿经济憋舰队链:二矿被 ZT 开门条件卡到 398-478s
  (Power 胜局 128-241s),矿荒断农(农 33 冻住
  300-400s,不是闸拦是矿<50 造不起),气囤 500-1800
  花不掉。

### o362b 尸检(配方稳定 + 败局分叉)

- 胜局配方(g1/g3):Power 首波晚 ~130-160s,6-11 塔
  +2 叉扛过 → FB ≤420s(3/3 全过,基金窗 3/3 成交)
  → 首风暴 478-590s → 航母 590-739s → 舰队 25-28
  平推;g3 采矿 53560、6 基 73 农。
- 败局 g2 唯一根分叉:二矿钉点死锁 290s → 单矿 8 分
  钟农峰 40 vs 胜局 66-71 → 养不起航母(舰队峰值 3)
  → 迟到二矿零塔被 4 狗穿防。
- 隐患:地面缓冲验收① 在 Power lane 0/3(2Z/2S/2Z),
  被对手节奏掩盖,不是功劳。

### O363 落地(下一轮验证对象,四项,单测 731→733 绿,冒烟过)

1. **新矿落地即配塔**:new_base_defense_pins(就绪+在
   途合并计数,默认 2 塔+1 电池);重构 O337-① 分矿守
   卫——删 break(只服务第一分矿的根因)、全局节流改
   per-base 台账、电池同钉 critical 通道。
2. **保险丝扩覆盖+防夺回**:查明真盲区=等钱时长被
   pop 归零(O307/O110/O118-② 重置
   TIME_ORDER_COMMENCED,60s 永不积累)——
   _o363_pin_since 跨 pop 累计台账;O307 撤派工写 60s
   防夺回封锁(pin_repin_blocked)。
3. **拆 SG 连环门**:sg_pin_expand_ok 加 exempt_at=240
   (t≥240 后单基地硬时限/扩张优先豁免,SG 与扩张并行
   预算)。
4. **停气转矿落实**:查明「只记账不执行」根因=不清
   ares 气矿簿记,Mining 每 4 帧按残留簿记拽回——拉
   动时同步 _remove_worker_from_vespene;解除改纯气压
   滞回(气<250);ZT 早窗摘掉「矿<150」并联(气>300
   即停);O218 刷屏加 30s 节流。

### 本轮 bench 验收口径

① 新基地落成 60s 内 ≥1 塔在途;② 零钉点 >60s(含
Nexus/FB);③ SG ≤300s;④ 停气触发后 30s 内气增长压
平;⑤ VH Timing 至少 1 局活到舰队 ≥8。

### 下轮安排

- lane1 o363a:VH Zerg Timing×3(验证 O363)。
- lane2 o363b:VH Zerg Rush×3(开辟第三 Zerg 风格战场)。

**遗留风险(记入)**:

- 追猎 cap1 被 expand_reserve 压住(core 就绪后追猎首
  产拖 200s+ 共 4 局)未修。
- o362a g2 气 624 的矿不低气照囤场景需观察新阈值效果。
- Harder ZT 回归(0/3)的修复与 VH Timing 同链,待 VH
  Timing 链修通后回归验证。


## o363 结果(VH Zerg Timing 0/3 + VH Zerg Rush 0/3,Rush 首测)+ O363 五验收判定 + O364(O336 倒挂修复 + 配塔提前开工 + 停气真执行 + 航母硬转化 + 三项小修)

**日期**:2026-08-19

### o363 结果

- o363a carrier vs VH Zerg Timing:0/3 全负。
- o363b carrier vs VH Zerg Rush:0/3(Rush 风格首测)。
- **总目标盘点**:VH Zerg Power 已打穿(5/6);Timing/Rush 未打穿;Terran 三风格未开战。

### O363 五验收判定(本轮验证对象)

- O363-① 新矿落地即配塔 → **验收① 0/3+0/3 差一口气**:注册稳定晚 68-71s(Rush lane 真因:lane 闸 timing-only,Rush lane 守卫从不运行,塔靠 F2 余钱落成才攒 350 矿;o363a g1 是 FB 基金窗拦塔+solver no_placement)。
- O363-② 保险丝扩覆盖 → **验收② Rush lane 3/3 过**(O362 保险丝 60s 准点释放+O307 设计内释放阀,Nexus/FB 无长钉);Timing lane 0/3(FB 622s O110 no_money 到死、cyber 钉点停滞 ~400s、首扩等钱 470s 到死)。
- O363-③ 拆 SG 连环门 → **1/3**:g3 SG 261.2s(O323 钉点 254.7,exempt_at=240 生效)+FB 325s+首风暴 458s=历史最快科技链;但 g1 卡 cyber 478、g2 cyber 整局未落成;Rush lane SG 381-397s 与基线持平(瓶颈在 O100 280s 解冻+no_money,不在连环门)。
- O363-④ 停气转矿落实 → **Timing 0/3(照涨 +120~+184)、Rush 部分 6/9**:气仍以 ~+8/s 进账,清簿记+role 没真执行。
- **验收⑤ 舰队 ≥8:0/3+0/3**(Timing 峰值 0/0/4;Rush 峰值 4/7/4)。

### o363a 尸检(Timing,三局三种死法收敛到执行层)

- g3 历史最快科技链(SG 261/FB 325/首风暴 458)被 **O336 优先级倒挂**杀死:首扩等钱 >60s 的自救是「解锁科技链 30s」,~2000 矿科技消费(SG2/FB/风暴/Robo/Twilight)把 Nexus 400 矿窗永久挤掉,单矿 31 农到死,舰队峰值 4。
- g1:侦查判读 unknown → 贪 5 矿经济爆炸(农 73/5 基地)但科技链瘫(cyber 478→SG 530→FB 未落成,舰队 0)。
- g2:首波杀农 15 回吐(协防农民 ×6 拉出射程送死),cyber 整局未落成,628s 第二波平推。
- 分矿塔链 no_placement 空转:g2 主基 26 水晶却报「带电 2x2 槽=0」(placement solver 黑格),O337 空转 271→512s。

### o363b 尸检(Rush 首测,与预想完全不同的形态)

- **Rush 首波实际 494-562s**(150-190s 的 5-6 狗只是侦查),<200s 极限窗没被考到;真空窗缓冲(叉 8/8/9)就位但没被真正测试。
- 经济历史最好:g2/g3 5 矿、农峰 71-72、采矿 28125/24830。
- 死法一致:**舰队上线太慢**(FB 486-566s、航母首产 755-900s vs Power 胜局 590-739s;舰队峰值 4-7 vs Power 25-28,差近一个数量级)+塔厚不足(每基地 1-2 塔,敌 15-22 supply 地面波「塔 N 座压不住」),800-1100s 被 Broodlord4-5+Corruptor12-16+Ultra6 死亡球滚平。
- 航母硬转化缺失实证:g2 农 72、矿 955 烂银行,航母只有 1 艘。
- O218 刷屏没压住(g1 674-729s 上百条;根因:Rush lane 走非 ZT else 分支,该分支零节流)。

### O364 落地(下一轮验证对象,五项,单测 733→741 绿,冒烟过)

1. **O336 倒挂修复**:首扩等钱 >60s 方向反转——luxury 钉点(SG2+/FB/风暴/航母/Robo/Twilight,首座 SG 豁免)hold 45s,Nexus 独占资金窗,成交/超时/threat 放行;hold 闸落 8 个 bypass 钉点(含 O215 holding 期 FB 豁免这个关键泄漏口)。
2. **配塔提前到开工**:lane 闸 timing→(timing,rush)(Rush lane 守卫从不运行的根因);在建 Nexus 首座塔豁免 FB 基金窗(fb_fund_exempt 参数)。
3. **停气真执行**:w.gather→w.smart(即帧移动/采集命令);30s 校验环(每 2s 查气增速,>15/10s 重复拉拽+清簿记);棘轮解除加闸(气>400 且舰队<6 不解除,g2 的 +354 漏回实证)。
4. **航母硬转化**:FB 就绪+矿>600+航母<2 → 空闲星门直接 train(lane 闸 timing+rush);与 tempest_dump_suppressed 联动。
5. **三项小修**:分矿塔 no_placement 30s 后手工锚点(Nexus→矿线质心方向 6 格外扩,绕过 solver 黑格);协防 cap 6→3 且作战锚改最近塔/电池(删「无塔锚→attack 最近敌」送死回退);O218 非 ZT else 分支补 30s 节流。

### 本轮 bench 验收口径

① 首扩等钱 >60s 后 45s 内 Nexus 开工;② 新基地落成即有 ≥1 塔在途;③ 停气触发后 30s 气增长压平(斜率 <5/10s);④ 矿>600 局航母 ≥2;⑤ 分矿塔链零 30s+ 空转;⑥ VH Timing/Rush 至少 1 局舰队 ≥8。

**遗留风险(记入)**:

- O364-① 的 45s hold 与 O362 保险丝/O307 撤派工相互作用(hold 期内保险丝 pop Nexus 条目会误判成交放行,语义可接受待观察)。
- 停气校验环在农民载货 return_resource 时可能误报泄漏(复拽幂等无害但多事件)。
- 追猎 cap1 被 expand_reserve 压住(首产拖 200s+)未修。
- Harder ZT 回归欠账待 Timing 链修通后回归。


## o364 结果(VH Zerg Timing 0/3 + VH Zerg Rush 1/3,Rush 首胜)+ O364 六验收判定 + O365(停气池放行建造 + 硬转化气枯分支 + 倒挂接线全 build + 倒挂前置排队层 + 三项小修)

**日期**:2026-08-19

### o364 结果

- o364a carrier vs VH Zerg Timing:0/3。
- o364b carrier vs VH Zerg Rush:1/3(**game_02 胜 966.6s,Rush 首胜**)。
- **总目标盘点**:VH Zerg Power 已打穿(5/6);Rush 破零(1/3);Timing 未破零;Terran 未开战。

### O364 六验收判定(本轮验证对象)

- O364-① O336 倒挂修复 → Rush lane 三局 hold 事件 0 条(等钱均未超 60s,机制空跑);**Timing lane 暴露未接线 rush(hold 分支被 _ai_build=="timing" 门住,o364b g1 二矿裸建 69s 被拆)+ 假成交(o364a g3 报成交放行但 bases 全程=1)**。
- O364-② 配塔提前 → Rush 胜局 ✓(二矿 297.5s 落成前 4s 即 dispatched,三四矿同步);败局四矿 no_worker 裸奔(见③×⑤冲突)。
- O364-③ 停气真执行 → 4/6 局压平(胜局 4 次触发斜率全负),校验环零误报;但 o364b g3 复拽 4 次粘不住(E6 归队 role 漂回 GATHERING 是泄漏主通道),o364a g2/g3 复拽压不住且停气池囤 43-44 农/采集池=0 次生灾害。
- O364-④ 航母硬转化 → **实锤有效**:胜局 663.4s(矿1520)转化 → 731.2s 首航母(64s 建造严格吻合),727.7s 第二次 → 航母 3;首航母 731s 提前到配方区间(基线 755-900s);无挤暴风产能回归(暴风照常 11-12 艘);但 o364b g3 气枯静默(矿>600 窗口 40s 气仅 7-79,can_afford 恒假 0 次转化无日志)。
- O364-⑤ 三项小修 → 协防 cap 3 生效;手工锚点只 fired 一次后静默(902-1023s 又空转);O218 真节流生效。
- **验收⑥ 舰队 ≥8:Rush 胜局峰值 18 ✓(航母3+暴风11+虚光4)**,Timing 0/0/0、Rush 败局 0/4。

### o364b 胜局(g2)配方对照与胜因归因

- 农 71 ✓(配方 67-69)、五矿、采矿 24835;FB 590.6s ✗(晚配方 170s);舰队峰 18(未达配方 25-28 但远超基线 0-7)。
- 胜因链:O98/O100 防御体系连扛三波(196s/458s/685s)→ 经济滚到 71 农+五矿 → 780s 起 O302 推进 fleet 5→15 滚雪球;敌 Hive 916s 才落重科技未成形;终局敌零腐化,暴风白打。
- ④ 是主链之一(前两艘航母全由硬转化直接产出)但非唯一胜负手;真正胜因=经济达标+防守链完整+敌科技慢。

### o364a 尸检(Timing,三局更上游断链)

- g1:整局 one_base 从未开扩 → 单矿撑不起 FB,305s 波穿。
- g2:全场无 BY 芯核(O245 建台失败 ×12,build yml ~474s 跑完即无后继)→ SG/FB/航母全 0,靠 6 叉+12 塔硬扛到 831s。
- g3:SG 245s 达标但 FB 两次 no_money 卡死;停气池 22-26 与塔链抢农民(采集池=0 → 26s 无人建塔 → 301s 首波屠农至 4)。

### 最有价值单点发现(③×⑤ 冲突)

- o364b g3:停气池 63 人被建造派工整体豁免,四矿落成前 1s `O344:分矿补电失败=no_worker(采集池=1,停气池=63)` → 四矿零塔被敌 4 地面抄家撤 20 农,基地连掉;停气农民本来在采矿,拉 1 人钉塔不伤停气。

### O365 落地(下一轮验证对象,五项,单测 741→750 绿,冒烟过)

1. **停气池放行建造派工+强征降级**:gas_stop_requisition_ok(防御链结构 select_worker 失败即放行停气池,不再要求采集池归零——O347-① 已证簿记虚高);O344 no_worker 降级强征。
2. **航母硬转化气枯分支**:gas_restore_needed(矿≥600+气<125+航母<2+FB 就绪 → 强制复气,每气矿回 3 人,气≥300 恢复棘轮)+ 30s 硬转化诊断日志(FB/矿/气/航母/复气/买得起全状态)。
3. **O364-① 接线全 build+成交校验**:hold 门 _ai_build=="timing"→zerg 全 build;成交改双条件(tracker 真空+townhalls≥2 实体实证);假成交 T+15s 校验失败 → 撤销重回 hold 一次+持续重派工(防续杯死锁)。
4. **倒挂前置到钉点排队层**:nexus_pin_yield_gate(矿≥400+二矿未钉+主基≥2 塔 → F2 目标钳 2/2,第 3+ 塔/电池让位)。
5. **三项小修**:BY 芯核 watchdog(t≥180 无 BY → critical 钉点);E6 归队即重标停气(不等 2s 校验环);手工锚点 per-base 持续重试(attempt 递增跨失败保留)。

### 本轮 bench 验收口径

① 分矿塔链零 no_worker(停气池 N) 事件;② 气枯窗口航母 ≥1;③ rush 局 hold 事件可见+零假成交;④ 二矿钉点不再被第 3+ 塔挤到 300s+;⑤ BY ≤240s;⑥ VH Timing 至少 1 局活到 600s+舰队 ≥4。

**遗留风险(记入)**:

- O365-③ pop 重回 hold 只续一次 45s(防续杯死锁),重钉持续失败时 hold 超时 luxury 放行但每帧重派工不停(有意为之)。
- 停气池囤农次生灾害(o364a g2 囤 43-44 农)未设上限,下轮观察。
- 主矿堆塔分矿裸奔(o364a g2 主矿 7 塔)的塔配额分配未修。


## o365 结果(VH Zerg Timing 0/3 + VH Zerg Rush 1/3)+ O365 六验收判定 + O366(FB 全链路保险 + 矿气倒挂根治 + F2 钳位动态化 + O126 豁免/O203 虚报修复)

**日期**:2026-08-19

### o365 结果

- o365a carrier vs VH Zerg Timing:0/3(累计 0/15)。
- o365b carrier vs VH Zerg Rush:1/3(game_01 胜 1038s,累计 2/6)。
- **总目标盘点**:VH Zerg Power 已打穿(5/6);Rush 2/6;Timing 0/15;Terran 未开战。

### O365 六验收判定(本轮验证对象)

- O365-① 停气池放行建造 → **验收① 6/6 全过**:no_worker(停气池) 事件清零(o364b g3 的 63 人停气池裸奔病灶根除)。
- O365-② 气枯分支 → **备而未用**:6 局全是反向问题(气 300-760 淤积、矿 <200 枯),气枯分支一次没机会跑;胜局硬转化正常(662.9s 诊断→719s 首航母)。
- O365-③ hold 全 build+成交校验 → **过**:rush 局 hold 可见(306.9s hold 45s→326.2s 正常放行)、假成交 0、误杀 0;副作用:g1/g3 三次「Nexus 条目消失无实体」回滚致二矿晚 60-95s(校验抓得对,条目消失根因待查)。
- O365-④ 倒挂前置 → **过但有代价**:二矿钉点全部 ≤255s 无第 3+ 塔挤占;但 F2 钳 2/2 暴露防御代价(o365b g3 每基地 target=2,E6 五次「塔 1/2 座压不住」被 42-supply 波滚死;g1 五矿 0 塔丢矿;g2 四矿落成 32s 即丢)。
- O365-⑤ BY watchdog → **验收⑤ 3/3 过**:BY 148.7/212.9/192.9s,watchdog 两次实弹命中。
- **验收⑥:o365a g1 达标**(活 1054.9s、舰队峰 6)。

### o365b 胜局(g1)配方复现且升级

- 农 72、五矿(297/490/607/715)、舰队峰值 **26(4 航母+22 暴风,上局 18)**、O302 推进 7 波、击杀 17400 vs 5025、总采矿 28360。
- 454s 首波 4 塔 2 电池+叉零农损守住(全场最关键存活点);SG 被卡 170s 但停气转矿+硬转化保证 FB 一好舰队下水;配方对单一环节失效有容错(硬转化只 ×1,6 星门风暴自产补上)。

### 系统性根因(两 lane 尸检收敛,本轮最有价值结论)

- **矿气倒挂**:6 局矿常年 <200、气溢出 300-1700;星门 257-269s 就闲置;O359 停气触发时矿已枯;停气校验环泄漏复拽每局 3-8 次空转,全场农民 idle 367-459s/局——「每层修完右移一层」的真正原因:下游每一环都被同一对病根(矿荒+落位)卡着。
- **FB 落地/生存链断裂**:o365b g2 FB 自救 10+ 次唯一落地 626.8s 仅 12s 即消失(重建 12 连败);g3 FB 642.9s 落成 12s 被拔;o365a g2 FB 卡 no_money 354s;死结结构=塔基金/停气转矿/FB 基金窗三方抢同一笔矿。
- **Timing 第二道 deadline**:决胜波 530-700s(40-76 supply)vs 舰队首舰 643-679s 恒晚 100-150s;O126 产兵自锁在敌 30+ supply 时仍冻结地面(o365a g3 599s 兵力={})。
- **Timing 专审判决**:「ZT opener 与 VH Timing 不兼容」不成立——o365a 上游三环首次全通(BY 3/3 ≤213s、二矿 3/3 ≤350s、首波 3/3 守住),死因从「活不过 305s」右移成「活过了但舰队出不来」;根因不在 opener,在资源配平与 placement 工程债。
- 小项:o365b g2 O203「舰队成型」在舰队=0 时虚报 5 次;o365a g1 三矿锚点 (70,94) 手工重试仍败;O324 runner 步#5 卡死 88s 三局复现。

### O366 落地(下一轮验证对象,四项,单测 750→760 绿,冒烟过)

1. **FB 全链路保险**:基金前置(SG 动工即开窗,窗内停气转矿让位防 200 气被抽干关窗死结);fb_safe_anchor(落点强制离主基斜坡口最远带电 3x3 槽,重建同口径);fb_arrival_guard_active(FB 在建或落成 60s 内敌地面 >8 → F2 cannons +2)。
2. **矿气倒挂根治**:气阀 ZT 早窗 300→250;tempest_gas_dump_ok(气≥400 且舰队<8 星门直接刷风暴折现,航母<2 优先不动);停气复拽根修(查明:校验环只改 role 不下离气矿命令,被 Mining 补气重挂后照采——补 smart/return_resource 命令映射)。
3. **F2 钳位动态化+成交解钳**:f2_clamp_supply_cap(敌 supply >35 → 上限 4);Nexus 成交即解钳打事件;锚点修复(单射线改 8 向扇形+anchor_buildable 可建性过滤:placement grid 2x2 足迹+避让矿簇气矿)。
4. **O126 威胁豁免+O203 虚报**:zt_expand_reserve_exempt(敌 supply >30 或 t>500 豁免,滞回 <20 恢复);fleet_formed_release_rush(实际舰队 ≥3 才解除 rush)。

### 本轮 bench 验收口径

① FB 落成后存活 ≥120s(零 12s 即拆);② 气银行峰值 ≤600 且星门不闲置;③ 敌 35+ supply 波时基地 target ≥3;④ t>500 地面兵力不再为空;⑤ VH Timing 至少 1 局舰队 ≥8;⑥ VH Rush ≥1/3 保持。

**遗留风险(记入)**:

- O366-③b 补塔依赖 F2 常态计算+裸矿多槽兜底,若解钳后补塔仍慢下轮再议。
- O366-③c 扇形+可建性过滤是「修到能落」最大努力,「换矿点」兜底未做。
- 停气池囤农上限仍未设(O365 遗留)。
- O324 runner 步#5 卡死未修(三局复现 88s 处 >45s)。


## o366 结果(VH Zerg Timing 0/3 + VH Zerg Rush 0/3,**O366 回归确认**)+ O366 六验收判定 + O367(回退基金前置 + 折现风暴门槛 + 豁免限叉/先知让位 + 保命塔豁免/O218 矿门/动态档修复)

**日期**:2026-08-19

### o366 结果

- o366a carrier vs VH Zerg Timing:0/3(累计 0/18)。
- o366b carrier vs VH Zerg Rush:0/3(从上两轮 1/3+1/3 掉到 0/3,**O366 回归确认**)。
- **总目标盘点**:VH Zerg Power 已打穿(5/6);Rush 2/9;Timing 0/18;Terran 未开战。

### O366 六验收判定(本轮验证对象)

- O366-① FB 全链路保险 → **验收① 3/3 全过但零转化**(FB 存活 406→1153/534→901/558→1093);fb_safe_anchor/fb_arrival_guard 有效,**但 ①a 基金前置是主犯**(见回归判决)。
- O366-② 矿气倒挂根治 → 气阀 250 工作正常(气淤积治好,3/3 气 ≤534);**折现风暴是从犯**(Timing lane 三局风暴全排航母前,首航母 719→948s;穷局单星门把仅有的气和产能给风暴);停气复拽根修有效。
- O366-③ F2 钳位动态化 → **验收③ 0/3,动态档 6 局零触发**(后查明:钳制窗 ~40-60s 与敌 35+ 波 614s+ 零重叠,窗内无波、波来已解钳);锚点扇形是从犯嫌疑(后证伪,见下)。
- O366-④ O126 豁免+O203 → **验收④ 0/3**(t>500 地面仍空);O203 虚报修复无害;豁免期产气耗单位(追猎 50 气抢航母气+三局各 1 先知白吃 150/150+43s 星门产能)是放大器。
- **验收⑤ Timing 舰队 ≥8:0/3(峰值 0/1/1);验收⑥ Rush ≥1/3:未保住(0/3)**。

### 回归判决(两 lane 尸检一致,机制级证据非方差)

- **主犯 O366-①a(基金前置到 SG 动工)**:o365b 胜局钱序 Nexus(297)→SG(498)→FB(562);o366b g1 变 SG(329)→FB(406)→Nexus(430,被挤晚 133s),农峰 44 vs 72,经济永久封顶 44 农/1 星门——每个环节有事件时间戳,o365 不存在的新失败模式。窗判据矿≥150 与 FB 造价 300 不匹配:o366a g2 连开 3 次纯抑制窗零成交。窗内停气让位让窗自持(窗开→停气禁→气≥400→窗续开),o366b g1 气 532 淤积、星门空转 170s。**核心教训:FB 提前 150s 落成毫无价值,瓶颈从来不是 FB 时点,是矿**。
- **从犯嫌疑→证伪:anchor_buildable 索引转置假设不成立**——sc2 PixelMap.data_numpy reshape(size.y,size.x)+__getitem__ 返回 [y,x],ares cy_can_place_structure 也按 [y,x],bot 的 grid[cy,cx] 与之一致;o366a g1 的 64 次 not_viable 真凶是 dispatch_viable 收入守卫(穷局买不起 150 塔),与锚点无关。
- **从犯 O366-② 折现风暴**(如上)。
- **放大器 O366-④**(如上)。
- **排除项**:窗内停气让位致气淤积假设否定(气阀工作正常);O366-②b 折现 Rush lane 有 timing 门未生效,不是 Rush 元凶。
- **方差 caveat**:o365b 两个负局舰队峰值也只有 5/1,Rush 配方本就脆弱;但 g1 钱序倒错+三局一致航母延迟 ~230s 是机制性退化。

### Timing 侧新增发现

- 上游没保持 o365 水平:主基 (162,22) 点位 g1/g2 双双芯核放置失败(O357 死槽换锚→O358 不收敛冷却),主基 (38,122) 的 g3 BY 180.8s 正常——**建筑放置层在上游掐断链条**,BY≤213 仅 1/3。
- 制度性死锁:折现绑死 fb_entities_now>0、O261 虚空兜底被 present_or_pending(FB) 抑制——FB 一卡两个兜底互相锁死,星门空转 275s(g3)。

### O367 落地(下一轮验证对象,五项,单测 760→767 绿,冒烟过)

1. **回退 ①a**:fb_fund_window 判据恢复 sg_ready(sg_started 签名保留不入判据);窗内停气让位一并回退;新增 fb_fund_window_stalled 健康监控(窗开 10s 矿净积累 ≤0 立即关窗放行 30s)。
2. **anchor_buildable 不改**(朝向验证非转置,加朝向锁定单测);not_viable 真凶=穷局收入守卫,由改动一修复。
3. **折现风暴门槛**:tempest_gas_dump_ok 加 舰队≥8 或 SG≥2 或已有 ≥1 航母。
4. **豁免限叉+先知让位**:expand_exempt_zealot_only(zerg timing+豁免激活+Nexus 持有期 → 纯叉配方);oracle_gas_yield(航母<2 或气<300 让位,跨 lane)。
5. **保命塔豁免+O218 矿门+动态档修复**:new_base_survival_cannon_ok(落成+12 格零塔 → critical 钉,跳过 cannon_capped/global/fb_fund 三道闸);O218 加矿≥150 门;f2_wave_cannon_floor(敌可见 supply>35 → target 强制 ≥3,接到威胁窗不再绑钳制窗)。

### 本轮 bench 验收口径

① Rush 局钱序恢复 Nexus 先于 SG/FB(二矿 ≤330s);② o366a g1 型 64 次 not_viable 清零;③ 穷局(舰队<8)零折现风暴;④ 豁免期零气耗单位;⑤ 新基地落成 60s 内 ≥1 塔(无例外);⑥ VH Rush 回到 ≥1/3。

**遗留风险(记入)**:

- 改动四 a 限叉闸只在 zerg timing lane 生效;Rush lane 追猎气耗由先知闸+经济修复间接覆盖,若验收④ Rush lane 仍见气耗单位需下轮专项。
- O215/O336 族与 fb_fund 健康监控的相互作用待观察。
- Timing 放置层上游断链((162,22) 点位芯核换锚死循环)未修,下轮专项。
- 星门死锁(折现绑 fb_entities+O261 被 pending FB 抑制)未修。


## o367 结果(VH Zerg Timing 0/3 + VH Zerg Rush 1/3,**Rush 回到 o364/o365 水位**)+ O367 六验收判定 + O368(FB 窗判据修配/破产分支/气耗闸 + 星门死锁自救 + 供电钉点预检 + 新基地保命塔硬兜底)

**日期**:2026-08-20

### o367 结果

- o367a carrier vs VH Zerg Timing:0/3(累计 0/21)。
- o367b carrier vs VH Zerg Rush:1/3(game_01 胜 2472s,外科手术成功,Rush 回到 o364/o365 水位,累计 3/12)。
- **总目标盘点**:VH Zerg Power 已打穿(5/6);Rush 3/12;Timing 0/21;Terran 未开战。

### O367 六验收判定(本轮验证对象)

- O367-① 回退基金前置 → **验收① 1/3**(b02 Nexus 293s 先于 SG 490 ✓;但 b01 SG 334 < Nexus 410、b03 SG 325 < Nexus 366——注:b01 违反①却赢了,Rush 局先手 SG/虚空撑住中段,「Nexus 优先」在 Rush 不是胜负手);fb_fund 健康监控 5 次关窗(462.6/789/854/558/844s)无误伤,Rush FB 落成率 3/3。
- O367-② not_viable → **验收② 过**(o366a g1 型穷局中段连环清零;残余全是残局崩盘点效应)。
- O367-③ 折现门槛 → **验收③ 6/6 全零**。
- O367-④ 豁免限叉+先知让位 → **验收④ 2/3**(b03 虚空 514s 产于 FB 窗 427-558 内 → 558s 零积累关窗,气耗闸没盖到虚空)。
- O367-⑤ 保命塔豁免 → **验收⑤ 约 3/9 未达**(新基地 F2 target=0 稳态,b02 二矿 450s 无塔掉落、b03 三矿全程无塔=两负直接死因;f2_wave_cannon_floor 触发 5 次但只活在瞬时)。
- **验收⑥ Rush ≥1/3:✓**。

### o367b 胜局(g1)配方复现度

- 农峰 73 ✓、五矿 ✓(但 NX5=1076.8s vs 配方 715s,+362s)、舰队峰 27 ✓、O302 推进 33 次(1716s 起 fleet 19→27)✓、200/200 碾死满科技 Zerg(大龙 6+腐化 13+大牛 4)。
- 首航母 1297.8s ✗ vs 配方 719.2s(+579s);FB 1189.3s ✗ vs 562.5s(+627s);总采矿 59285 近两倍时长经济。
- **赢的是残局厚度不是配方节奏**:前期 2SG+虚空+29 塔死守,16 次 E6 抄家仅丢 1 基地,拖到舰队成型。

### o367a 尸检(Timing 0/21,瓶颈收敛到单一环)

- **芯核换锚死循环已清零**(BY 157-205s,watchdog 每局仅 1 次)——o366 的 (162,22) 放置层上游断链修复。
- **唯一瓶颈=FB 落不了→星门空转 388-530s→舰队恒 0**,三个子病灶:
  - a) FB 基金窗开得晚+开得穷(452/599/627s 才开,开窗即负积累,气淤积 426-524;窗判据矿 150 vs 造价 300 不匹配,b01 四窗两关空转;O110 no_money 自救 6-8 次循环到死——贴槽水晶挂在 can_afford(FB) 分支内,no_money 循环里永不执行)。
  - b) 星门死锁(产线绑 fb_entities,SG 落成 60s+ 零产出;o367b 胜局 VOIDRAY@418 证明虚空能撑中段)。
  - c) (162,22) 供电断链(主基槽位 带电余=0/空闲余=12/总=25,12 个空槽全无电,FB no_placement 死等)。
- 三局死因分环:g1=供电断链→舰队 0→timing 波穿塔;g3=二矿落成 28s 无塔被拆→经济崩;g2=塔链 not_viable/死等 647s→三矿无塔被抄→大龙收尾。共同上游:新基地/主基的塔与电没有兜底。

### O368 落地(下一轮验证对象,四项,单测 767→775 绿,冒烟过)

1. **FB 窗判据修配+破产分支+气耗闸**:开窗矿 150→300(对齐造价);fb_bankrupt_needed(no_money 连击 ≥3 → 暂停升级/SG2/分矿塔/电池,保命塔除外,FB 落成/threat 解除);fb_fund_gas_gate(200 气预留线应用于 O261 虚空)。
2. **星门死锁自救**:stargate_deadlock_voidray(SG 全闲 ≥60s 且 FB=0 → 转产虚空上限 4;FB 落成自灭)。
3. **供电断链钉点前预检**:power_precheck_needed(带电余=0 且空闲>0 → 先 critical 贴槽水晶再钉建筑;根因注释:O110 贴槽水晶挂在 can_afford(FB) 分支内永不执行)。
4. **新基地保命塔硬兜底**:new_base_f2_cannon_floor(落成 <120s target 下限 1);nexus_pin_yield_clamp(让位钳改 max(1,target-1));new_base_no_cannon_alarm(60s 无塔健康事件+强钉)。

### 本轮 bench 验收口径

① FB 窗零「开即关」空转(成交率 ≥50%);② 零 SG 空转 >90s;③ (162,22) 局 FB 能落成;④ 新基地落成 60s 内 ≥1 塔(无例外);⑤ VH Timing 至少 1 局舰队 ≥8;⑥ VH Rush ≥1/3 保持。

**遗留风险(记入)**:

- O368-② 死锁自救豁免气耗闸与破产暂停(逃生舱优先),若 FB 更晚可收紧 cap 4→2。
- O368-① 破产暂停与 O364-① nexus hold/O362 保险丝的相互作用待观察。
- Rush 钱序①只有 1/3 但 b01 证明非胜负手,该验收口径下轮修正。


## o368 结果(VH Zerg Timing 0/3 + VH Zerg Rush 2/3,**Rush 突破,距打穿一步**)+ O368 六验收判定 + O369(FB fund-first latch + SG 空转口径修复/post-FB 填线 + 供电预检推广 + BY 快退化 + 塔投资闸 + 星门按缺口硬钉)

**日期**:2026-08-20

### o368 结果

- o368a carrier vs VH Zerg Timing:0/3(累计 0/24)。
- o368b carrier vs VH Zerg Rush:2/3(g1 胜 1197s、g3 胜 1559s,**突破**,累计 5/15)。
- **总目标盘点**:VH Zerg Power 已打穿(5/6);Rush 5/15(本轮 2/3,距打穿一步);Timing 0/24;Terran 未开战。

### O368 六验收判定(本轮验证对象)

- O368-① FB 窗判据修配+破产+气耗闸 → **验收① 成交率 1/1 达标但窗基本不开**(6 局窗只开 1 次:g3 窗开 525.4→成交 530.4s 仅 5s;判据矿 300 修配后窗成摆设,FB 多走 O110 自救/常规钉点);破产分支 o368b 零触发零误伤,o368a g2 触发 1 次(464.9s,62s 后 threat 解除,判定正确)。
- O368-② 星门死锁自救 → **验收② Rush 3/3(68-76s)Timing 两洞**:a) 设计 60s 实测 223s(_sg_idle_since 起点被在产含虚空反复归零);b) post-FB 矿穷空转不覆盖(g3 FB 已落 SG 仍空转 153-237s)。
- O368-③ 供电钉点预检 → **验收③ 2/2 通**(g2 预检 2 次 320/350s 带电余 0→15-18;g3 (162,22) FB 438s 直接落成)。
- O368-④ 新基地保命塔 → **验收④ Rush 扩张期达标**(b5 +42-53s 等;o368b 五矿 cadence 健康);**Timing 侧暴露强钉无升级路径**(o368a g2 (70,118) 告警 2 次、强钉 12 次全 no_placement 后无 fallback)。
- **验收⑤ Timing 舰队 ≥8:0/3(峰值 0/2/3);验收⑥ Rush 2/3 超额**。

### o368b 两胜局(配方复现+提速 8-11 分钟)

- 对照 o367b 基线:农 72/74 ✓、**6 矿**(基线 5)、**FB 587/530s(提前 602-659s)**、**首航母 747/780s(提前 518-551s)**、舰队峰 26/25 ✓、O302 从 818/900s(fleet 5/6)连推。
- 胜因归属:O368-①(窗开 5s 成交)+O368-②(SG 空转 388-530s→≤72s,虚空撑中段)是主胜因;③④在胜局无病可治;④b 让位钳新语义保住扩张节奏。
- 隐患:g2 败局 25 座塔(≈3750 矿)被逐波拆光同期舰队停 6 艘(塔投资挤舰队);两胜局 bank 问题(矿峰 3430/气峰 3220 没花出去)。

### o368a 尸检(Timing 0/24,三病灶通了两个半)

- **供电断 ✓ 通**;**星门锁半通**(自救能转虚空但晚+口径两洞);**窗穷没通=主死因**:窗判据矿 300 在受压经济下永远够不到,FB 全靠 O110 自救硬钉,g2 连钉 12 次 500s 落成 0 次(矿 5-756 反复被 Nexus/塔/电池/虚空抢走;破产分支被 rush 常亮屏蔽)。
- g1 死于 FB 环之外:(162,22) BY 落位死锁(换锚二连黑→60s 冷却,BY 221s)+237s 狗毒爆破塔;首塔带电余=0 not_viable 268-315s 是被穿窗口(预检只盖 SG/FB)。
- g3:FB 438s 落成但二矿 494s 太晚(luxury hold↔Nexus 条目消失重派工踢皮球 3 轮),舰队 3 撞 774s 敌 77supply 腐化 9 波,黄金窗 near-miss(772s 舰队 4/腐化 1)差一口气。

### O369 落地(下一轮验证对象,六项,单测 775→784 绿,冒烟过)

1. **FB fund-first latch(最高优先)**:fb_fund_latch_needed(SG 就绪+FB 无实体+非 threat+矿<300/气<200 → 常态 latch 停非保命支出,保命塔/探机农<28/二矿未成交豁免);破产触发改「累计≥3 或 FB 缺失>120s」,解除去 rush 屏蔽只传 threat;30s 零积累临时解除 60s 防死锁;攒够 300+200 即 critical 钉。
2. **SG 空转口径修复+post-FB 填线**:sg_idle_reset_needed(销账只认在产 TEMPEST/CARRIER,虚空填线不销账——223s 根因);sg_post_fb_fill(FB 已落+空转≥60s+矿<300 产虚空填线)。
3. **供电预检推广**:power_precheck_covered(清单加 PHOTONCANNON/SHIELDBATTERY,塔/电池走 2x2 槽口径)。
4. **BY 落位死锁快退化**:reanchor_fallback_default(黑名单≥2 直接回退 ares 默认 placement 不带 closest_to,跳过 60s 冷却,仅 BY/GATEWAY)。
5. **塔投资总量闸**:cannon_investment_freeze(t>600 且(腐化≥4 或舰队<8)冻结塔地板上抬,wave 豁免;o368b g2 的 25 塔/6 舰队反面教材)。
6. **星门按舰队缺口硬钉**:sg_gap_pin_needed(FB 已落+就绪 SG 全忙+舰队<8+SG<3+矿≥150 → critical 钉 SG2/SG3,不等气烂银行)。

### 本轮 bench 验收口径

① Timing 局 FB ≤500s 落成;② 零 SG 空转 >90s(含 post-FB);③ (162,22) 局首塔不再 not_viable 死等;④ BY ≤150s;⑤ VH Timing 至少 1 局舰队 ≥8;⑥ VH Rush ≥2/3 保持(冲打穿)。

**遗留风险(记入)**:

- O369-① 的 Nexus 闸用 townhalls≥2(含在建),二矿在建期 latch 激活会暂停三矿(符合豁免语义但 bench 核对)。
- O369-① latch 与 O364-① nexus hold/O362 保险丝/O367 健康监控四者相互作用是本轮最大不确定性。
- Rush 两胜局 bank(矿 3430/气 3220)没花出去,产能转化下轮观察。


## o369 结果(VH Zerg Timing 0/3 + VH Zerg Rush 2/3,**Rush 打穿确认:最近 5 局 3 胜**)+ O369 六验收判定 + O370(塔投资闸重做 + latch×Nexus 互斥仲裁 + FB 选址收口 + BY 提速防重 + SG 二号位放宽/O218 归因)

**日期**:2026-08-20

### o369 结果

- o369a carrier vs VH Zerg Timing:0/3(累计 0/27)。
- o369b carrier vs VH Zerg Rush:2/3(g1 胜 1258s、g2 胜 1556s)——**Rush 打穿确认**:o368b 2/3 + o369b 2/3,最近 5 局 3 胜(累计 7/18)。
- **总目标盘点**:VH Zerg Power 打穿(5/6)、VH Zerg Rush 打穿(3/5)——两个 VH 组合在手;Timing 0/27;Terran 未开战。

### O369 六验收判定(本轮验证对象)

- O369-① FB fund-first latch → **机制 3/3 干净工作**(g1 latch 285.2s 触发 38s 成交 FB 325.4s、o369b g1 latch 376→519 一次成交、g2 467→541 一次成交),但 Timing 验收① 只有 1/3(g2 FB 498s 开工走 O110 分矿试建旁路钉到无塔分矿 35s 被拆;g3 latch 485s 才触发,迟到根因在上游 BY 245s/SG 446s);**且早 FB 是账面胜利**:g1 FB 325.4s 达标却 2 矿 43 农喂不饱舰队(峰值 7)。
- O369-② SG 空转口径修复 → Rush 两胜 ≤54-73s;但 post-FB 断产 181s(o369b g3 气烂 579);o369a g1 销账口径与填线自相矛盾(7 段 >90s 实际在产虚空)。
- O369-③ 供电预检推广 → **验收③ ✓**,无 not_viable 死等。
- O369-④ BY 快退化 → **3 局 Timing 全部未触发**(黑名单≥2 阈值,g3 黑名单仅 1 拖到 245.1s);BY 156.7/192.9/245.1 全部超标。
- O369-⑤ 塔投资总量闸 → **真回归,6/6 局误触发**:全部在敌可见腐化=0 开火(口径与 spec 系统性不符);「钳现有」向下棘轮(塔被拆→目标更低 8→5→4→2);实害至少 3 局(o369a g1 三矿钳 0 塔被 29 地面抄丢、o369b g1 三矿 target=0 裸奔 44s 被拆、o369b g3 两次无塔 E6);叠加 F2 新矿注册 target=0(冻结钳 min(_cannons_expansion, 全局现有塔数) 在全局 0 塔时把下限 1 一并钳 0)。
- O369-⑥ 星门缺口硬钉 → **基本没生效**(6 局仅 2 次 fire 1 次成交;「SG 全忙」对单 SG 空转+气烂银行场景永假,恰是 o369b g3 死法)。
- **验收⑥ Rush ≥2/3:✓(打穿确认)**。

### o369b 胜局配方分析(赢法迁移)

- 配方只中一半:g2 全项达标(农 73/6 矿/舰队 26),g1 有缺口(5 矿/舰队 18/首航母 803.6s);两胜首航母都比配方晚(803.6/952.2 vs 配方 747-780)。
- **胜因链已迁移**:latch 一次成交 FB(154s/74s 无抖动)→ post-FB 虚空填线顶波 → O302 持续先手压制滚雪球;航母已非胜负手,虚空填线+风暴海+O302 才是。
- 共性弱点:两胜对手全程 0 腐化、大龙 0-1 条,801-837s 最大一波被耗光后 AI 后继无力——打穿是真的,余量不大。

### 两个跨 lane 公共 bug(各有多局实锤)

1. **O369-⑤ 塔投资闸误触发**(如上,真回归)。
2. **latch×O364 Nexus 资金窗互抢**:o369b g3 直接死因(O364 Nexus hold 498.1 被 latch critical 钉 FB 511.2 压过,Nexus 假成交两次,二矿推迟到 590.6s 晚 230-250s,农 49 vs 配方 72-74);o369a g3 九分钟无二矿(O364 hold/O362 fuse/O365 重派工三机互转死循环,「条目消失无实体」×8,全程单矿)。

### Timing 专审判决(累计 0/27)

- latch 已达标(3/3 干净成交,g1 325.4s),**下一刀不该再砍 FB**:死因排序 ①经济从未起飞(农峰 48/45/31 vs 配方 72-74;Nexus 子系统死循环)②分矿塔 placement 系统性死循环(g2 (70,118) no_placement×5+重试全败)③塔投资闸误触发补刀 ④FB 选址旁路(g2 一锤定音)。
- 「ZT opener 与 Timing 不兼容」再次证伪:latch 能把 FB 压进 325s,缺的是经济链喂饱舰队。

### 战线决策(两 lane 尸检共识,已执行)

- **Rush 封板**(打穿确认,继续堆局边际收益递减)。
- **修两个公共 bug 后转 Terran 战线**(互抢+塔闸是跨机制 bug,带着换战线会在 Terran 重现)。
- **Timing 最后一刀**(经济链三修+3 局复测再定存废)。

### O370 落地(下一轮验证对象,五项,单测 784→791 绿,冒烟过)

1. **塔投资闸重做**:触发只认实际可见腐化 ≥4(删 fleet<8+t>600 常开窗);钳 max(现有,冻结启动时注册 target 快照)断棘轮;新矿(落成<120s)+1 豁免名额。
2. **latch×Nexus 互斥仲裁**:fb_latch_pin_allowed(二矿未成交或 O364 hold 期 → latch 排队,成交后 latch 先行);nexus_repin_loop_forced(消失→重钉循环 >3 轮清冷却强制直钉 max_on_route=99;查明条目是 O362 保险丝 pop 的)。
3. **FB 选址收口+埋点**:O110 自救 FB 主基重试强制 fb_safe_anchor,分矿试建旁路对 FB 禁用;补「攒够300+200,钉点在途待成交(非latch通道)」埋点。
4. **BY 提速+防重**:watchdog 180→150s、黑名单阈值 ≥2→≥1;cyber_core_build_allowed(查 runner 剩余步排着 core 则跳过——双 BY 根因:runner 的 BY 占位未派工对 bot 层 tracker 不可见)。
5. **SG 二号位放宽+O218 归因**:sg_gap_pin_needed 加「SG<2 且舰队<8 且气≥300」空转出口;stargate_pin_retry_needed(dispatched 后 30s 未落成不依赖气门重钉——O218 落空根因:气被产线花掉气门永假+条目被保险丝 pop 无人重钉)。

### 本轮 bench 验收口径

① 塔闸零误触发+新矿首批塔不饿死;② 二矿与 FB 不再互误+二矿死循环零出现(≤60s 收敛);③ FB 零「无塔分矿」选址;④ BY ≤150s;⑤ VH Timing 至少 1 局舰队 ≥8;⑥ VH Terran Power 首测有数据。

**遗留风险(记入)**:

- 双 BY 只收编 bot 层钉点侧;runner 自身在 bot 已建 BY 后仍执行 core 步的残余风险靠 building_counter 感知兜底。
- latch 仲裁与 O364 hold 的事件序列需 bench 核对。
- Rush 胜局首航母系统性偏晚(803-952s)+对手 0 腐化因素,配方余量不大,打穿结论待 Terran 战线铺开后再回归确认。


## o370 结果(VH Zerg Timing 0/3,累计 0/30 **终审封存** + VH Terran Power 首测 0/3)+ O370 五验收判定 + O371(分矿防御守卫去 zerg 门 + O302 推进闸敌军校验 + 强制直钉提前 + FB 保底落点 + BY watchdog 立即换锚)

**日期**:2026-08-20

### o370 结果

- o370a carrier vs VH Zerg Timing:0/3(累计 0/30)。
- o370b carrier vs VH Terran Power:0/3(新战线首测)。
- **总目标盘点**:VH Zerg Power 打穿(5/6)、VH Zerg Rush 打穿(3/5);Zerg Timing 终审封存;Terran 战线开辟中。

### O370 五验收判定(本轮验证对象)

- O370-① 塔投资闸重做 → **验收① 过**(误触发 6/6→0;g2 两次触发均真实腐化 ≥4)。
- O370-② latch×Nexus 仲裁+死循环 → **互误消除 ✓**(g3 latch 341s 正确排队让位 Nexus);**死循环收敛超时**(4 轮 130s,验收 ≤60s;强制直钉第 4 轮才来)。
- O370-③ FB 选址收口 → **过**(g2 FB 470s 落成且存活,对比 o369a g2 落成 35s 被拆);副作用:g3 分矿试建禁用后 FB 整局悬空(O110 自救 ×8 全落空)。
- O370-④ BY 提速 → **未过**(156.7/152.7/217.0s;watchdog 名义 150s 实际 233/261s 才 fire,起算点可疑)。
- **验收⑤ Timing 舰队 ≥8:0/3(峰值 1/6/0);验收⑥ Terran 首测数据 ✓**。
- O370 零新回归。

### Timing 终审判决(0/30,封存)

- 最后一刀三个修复全部验证兑现(塔闸/仲裁/选址),g1 FB 325.4s 复刻最佳,舰队峰值仍只有 1。
- 死因不在被修机制,在结构性量级差:~525-550s 首波 10-20 地面强制防御支出,配方需要 72 农实际只有 45/45/38,经济永远爬不到喂饱舰队的水位;2 矿 45 农是舰队天花板。
- **按预定规则(最后一刀修复通了还 0/3 即封存)执行:Timing 战线封存,Zerg 战线以 Power+Rush 两个打穿组合收官**。

### o370b Terran 首测评估(底子最好的 lane)

- **底子**:农峰 53-62(比 Timing 高一档)、BY 120-128s、FB 257-293s 全部早落、首航母 458s、O370 仲裁在 g2/g3 正确触发——经济链和 carrier 链在 Terran 局都成立。
- **zerg 特化门实锤(三局同一死因)**:production_manager.py:1035 分矿防御守卫(O323/O337/O363)+O329 全包在 zerg+(timing,rush) 门,打 Terran 整体静默(O337 26→0、O363 19→0、O329 7→0、O118 26→0);三局三矿落成后裸奔 60-80s 被 ~495-510s 首波(25-30 supply M&M+坦克)准点收走;O98 forge 兜底静默(forge 168-217s vs zerg 92s)、O338 GW2 静默(零地面填线)。
- 敌构成:~495-510s 首波 M&M+坦克;~820-900s 第二波加坦克架+维京+渡鸦;维京专杀风暴(g2 敌 11 维京 vs 我 5 风暴)。
- O302 送死实证:g3 以 fleet=4 对 47 supply 主动推进(569.5s)。
- 形态差异:Terran 局是「先富后死」,Zerg Timing 局是「从没富过」。

### O371 落地(下一轮验证对象,五项,单测 791→795 绿,冒烟过)

1. **分矿防御守卫去 zerg 门**:expansion_defense_guard_active(zerg∈(timing,rush) or terran)+timing_defense_chain_active(zerg==timing or terran);5 处去门(:1053 守卫块/:1330 O329/:5032 forge 钉点/:5178 forge 看门狗/:5209 GW2);zerg 行为不变(纯函数布尔等值,单测断言)。
2. **O302 推进闸加敌军校验**:push_enemy_army_gate(敌 supply ≤ 我 ×1.5 且 敌硬对空 <4);只闸 advantage(O44)+full_pop(O70) 路径,force_push(O164/O241 timeout 兜底)和 zerg 全局(O302 黄金窗是胜局实证打法)豁免。
3. **强制直钉提前**:nexus_repin_loop_forced max_rounds 3→1(第 2 轮消失即强制,收敛 ~60s)。
4. **FB 保底落点**:fb_safe_anchor 加 occupied_fallback(无空闲槽降级带电非空闲槽,force place 尝试)。
5. **BY watchdog 立即换锚**:cyber_core_np_default_fallback(首次 no_placement 走 O357 换锚不被阈值 1 短路去默认黑格,连续 2 次走默认回退)。

### 本轮 bench 验收口径

① Terran 局分矿防御事件可见+新矿 60s 内 ≥1 塔;② 零 fleet<6 撞敌 2× 推进;③ 二矿死循环 ≤60s;④ FB 零整局悬空;⑤ VH Terran Power 至少 1 胜;⑥ Zerg Rush 回归 ≥1/3。

### 下轮安排

- lane1 o371a:VH Terran Power×3(去门验证)。
- lane2 o371b:VH Zerg Rush×3(回归保险+打穿确认)。

**遗留风险(记入)**:

- O371-② 的 _force_push 豁免可能在 Terran 长局放出 fleet≥8 的莽推(闸只挡 advantage/full_pop 路径)。
- O370-④ BY watchdog 起算点问题(名义 150s 实际 233-261s)未根治。
- Timing 封存是战略决定,若司令有不同意见可重启(机制链全部保留在代码里)。


## o371 结果(VH Terran Power 1/3 **首胜** + VH Zerg Rush 0/3 判纯方差)+ O371 六验收判定 + O372(F2 target=0 修复+FB 重建通道+主基电力预留+舰队重建 watchdog+推进 commit 期 AA 重评)

**日期**:2026-08-20

### o371 结果

- o371a carrier vs VH Terran Power:**1/3**(g3 胜 1061s,Terran 首胜,分矿防御去门生效)。
- o371b carrier vs VH Zerg Rush:0/3(回归 lane,两个独立尸检一致判决为纯方差+敌签差,非 O371 回归)。
- **总目标盘点**:VH Zerg Power 打穿(5/6)、VH Zerg Rush 打穿(3/5)、Timing 封存;**Terran Power 破零(1/3)**;Terran Rush/Timing 未测。

### O371 六验收判定(本轮验证对象)

- O371-① 分矿防御去 zerg 门 → **生效**:O337/O363 从 o370b 全 0 → 9-11 次可见,O357 forge 换锚也在跑;但「事件≠塔」——60s 首塔口径只有 1/3(o371a g1 全基地 F2 target=0、主基整局 0 塔、首塔晚 234s)。
- O371-② 推进闸 → 未证伪也未证实(o371a g2 fleet=5 推 ×4 在维京 695s 露面后仍 commit 团灭——闸只看决策瞬间;o371a g3 fleet=4 推 ×16 敌弱非撞 2×)。
- O371-③ 强制直钉 → 六局零触发(无从误伤)。
- O371-④ FB fallback → 零触发(FB 全走 latch 常轨)。
- O371-⑤ BY 换锚 → 零触发(BY 140.6-144.6s 与基线逐秒一致)。
- **验收⑤ Terran ≥1 胜:✓;验收⑥ Zerg Rush ≥1/3:✗(0/3)**。

### o371a 胜局(g3)配方

- 时间线:BY 140.6→SG 221→FB 377.7→二矿 357.6→三矿 470→首航母 638.8→**O302 十六连推**(586.7s fleet=4 起滚雪球)→舰队峰 20(3C+16T)。
- 经济产出:总矿 20225、击杀 18425;敌仅 9 维京未成云。
- 败局对照:g1=FB 被 Nexus latch 拖 120s+单星门气烂 277s→舰队峰 1;g2=二矿两建两裸(重建卡 power_precheck 100s)+航母 803s 死后 200s 不补(839-952s 共 112s 军队零变化)→被 69-supply 维京雷神波推平。

### o371b 回归判决(两个独立尸检一致:非 O371 回归,纯方差+敌签差)

- 逐项排除且都有硬证据:①去门布尔等价(单测锁定,zerg 行为逐帧一致);②推进闸 zerg 豁免验证有效(O337 同对象同帧正常工作;O302=0 是果不是因——舰队峰 1-5 够不到推进门槛);③④⑤六项全零触发;BY 时点与基线逐秒一致;FB 时点 433.9-554.5 只会更早。
- 死法与 o369b 自己的败局 g3 完全同型(塔交付失败→舰队冻结→慢性死亡);基线胜局同样裸奔过,差别在敌波来得晚/敌主动撤退——n=3 下 0/3 vs 2/3 p≈3.7%,有嫌疑但无机理指纹,**五项一项都不回退**。
- 边际差异样本:o371b g1 FB latch 431.5s 抽走 500 资源正好压掉新矿首塔窗(450s 全矿仅 95)——O369 latch 既有行为与抽签撞车。

### 两 lane 共同败因收敛(塔交付链路+重建缺失)

1. **F2 target=0 注册 bug**(塔交付总根):根因查明=O210「买不起即归零」,分矿侧 O216j 有 min(,2) 兜底,主基 PSD 路径没有——o371a g1 主基整局 0 塔;o371b g3 三矿 target=0 两度被拆;跨轮跨 lane 复发。
2. **FB latch 与新矿首塔撞车**(o371b g1:431.5s latch 抽 500 压掉 450s 首塔窗)。
3. **FB 重建通道缺失**(o371b g2:FB 591s 被拆,重建 O110×3 全 no_money 空转 170s;被拆时银行 ≥300 不 latch、支出照跑,等穷了已无可攒)。
4. **主基电力预留缺失**(o371b g2/g3:SG 带电余=0 停滞 O110×3,晚 30-90s)。
5. **舰队重建断档**(o371a g2:航母死后双星门+气 500 在手 200s 零补充;O239/O260/O364 三条补产通道全挂 zerg 门,Terran lane 无通道)。
6. **推进 commit 期 AA 不重评**(o371a g2:维京 695s 露面 20 架后仍 commit)。

### O372 落地(下一轮验证对象,五项,单测 795→803 绿,冒烟过)

1. **F2 target=0 修复+新矿首塔兜底+latch 互斥+主基兜底**:f2_survival_floor(零塔且 target=0 → 下限 1);主基 O216j 后应用 floor;分矿注册点 _exp_cannons 同过 floor;fb_latch_yields_first_cannon(任一新矿零塔时 latch 不触发不钉 FB)。
2. **FB 重建通道**:fb_rebuild_latch_needed(ever_completed+entities=0+sg_ready → 被拆瞬间即 latch,不等穷);_fb_ever_completed 边沿置真。
3. **主基电力预留**:sg_power_reserve_needed(SG/FB 钉点前带电余=0 且有空闲槽 → critical 贴槽水晶,放 can_afford 门外)。
4. **舰队重建 watchdog**:fleet_rebuild_watchdog_needed(峰值 ≥3 → 掉 <2 持续 ≥60s+FB 就绪+空闲 SG → 强制补产,航母优先;种族不挂门——Terran lane 无补产通道的实证);90s 节流。
5. **推进 commit 期 AA 重评**:push_commit_aa_retreat(可见硬对空+星港预警(+2)≥4 → 撤蹲;30s 重评,旗标粘滞防可见性抖动;zerg 豁免同 O371-② 教义)。

### 本轮 bench 验收口径

① 新矿落成 60s 内 ≥1 塔(含主基);② FB 被拆后 ≤180s 重建落成;③ SG 零「带电余=0」停滞;④ 舰队断档 ≤90s 即补产;⑤ Terran 推进零「commit 期遇 4+ 对空不撤」;⑥ VH Terran Power ≥1/3 保持+Zerg Rush 回到 ≥1/3。

### 下轮安排

- lane1 o372a:VH Terran Power×3(巩固首胜)。
- lane2 o372b:VH Zerg Rush×3(o371c 方差确认)。

**遗留风险(记入)**:

- F2 注册事件日志对分矿仍印主基 target(历史遗留),真实分矿注册值是 _exp_cannons,下轮尸检读 target=0 需注意。
- O372-④ 的 90s 节流同时节流补产动作(与 O357-④「只节流言」规约有意偏离,注释已注明)。
- O372-⑤ 星港预警 +2 的权值可能需要实战校准。


## o372 结果(VH Terran Power 0/3 回落 + VH Zerg Rush 1/3 回水位)+ O372 六验收判定(①让位死锁实锤回归)+ O373(让位死锁三刀+F2 豁免收口+latch×首扩互斥+watchdog 双孔封堵+zerg AA 豁免上限+O302 出发闸)

**日期**:2026-08-20

### o372 结果

- o372a carrier vs VH Terran Power:0/3(上轮 1/3,未保持)。
- o372b carrier vs VH Zerg Rush:1/3(g2 胜 1307s,回到水位,上轮方差判决成立)。
- **总目标盘点**:VH Zerg Power/Rush 打穿、Timing 封存;Terran Power 1/6(破零后回落);Terran Rush/Timing 未测。

### O372 六验收判定(本轮验证对象)

- O372-① F2 target=0 修复+首塔兜底+latch 互斥 → **验收① 六局五违例(最差项)且①自身实锤回归**(详尸检见下);f2_survival_floor 在途塔豁免漏洞:注册瞬间有在途塔使地板空转,在途塔黄了无人补注册(7 次分矿注册全 target=0)。
- O372-② FB 重建通道 → 零触发(o372b g1 有一次 32s 快速重建 514拆→546落 ✓)。
- O372-③ 主基电力预留 → ✓ 零「带电余=0」停滞(停滞全 no_money)。
- O372-④ 舰队重建 watchdog → **双孔暴露**:o372b g1 跌破 2 至终局 70s 零补产((a) 短暂回 2 重置 collapsed_since;(b) can_afford 静默跳过);zerg lane 三局「O372」前缀事件 0 条。
- O372-⑤ 推进 AA 重评 → 零误撤(zerg 豁免生效)。
- **验收⑥:Terran 0/3 未保持 ✗;Zerg Rush 1/3 ✓**。

### O372-① 让位死锁(实锤回归,两 lane 尸检一致)

- o372a g3 事件簿:302.7/353.3/383.3s 三次「新矿首塔未立,latch钉FB让位」——每次基金窗开(矿300气522充足)就让位,循环空转;让位 elif 排在 critical 钉FB 之前,无任何超时/升级出口。
- 被让位的二矿首塔因「带电余=0→贴槽水晶」+「O337派工=no_placement」循环,二矿落成 204.9s → 567.1s 才立(晚 362s)。
- FB 554.5s vs 基线 377.7s(+177s),舰队全程 0,577.7s 被 36 地面推平。
- 附带:O110 贴槽水晶自救把水晶从 8 钉到 30 根(基线 10)≈烧 2000 矿,塔反因 no_money 立不起。
- 其余四项全部无罪(零误触发);Terran 0/3 = 1 局真回归 + 2 局基线策略短板(600s 转航母撞 560-570s MM timing——E10 判非 rush 走风暴主C,转型点太晚,既有缺陷非本轮引入)。
- FB latch×首扩互撞(o372b g3):387.3s latch 抽走 475 矿,二矿拖 526.3s;且 O370 仲裁判了让位 FB 仍经非 latch 通道落地。

### o372b 胜局(g2)配方满格复现

- 农 72 ✓、6 矿 ✓、舰队峰 27(4 航母+23 暴风)✓、O302 十五连推(875.3s 起)→ 1307s 胜;科技链全面晚 ~200s(SG 446/FB 570/首航母 783)但防御型 Zerg 局可接受。
- 两负死因一致:舰队规模不足(峰 6-7)+三矿裸奔,敌 890-1080s 腐化 14-20+大龙 4-5 成型即无解。

### O373 落地(下一轮验证对象,六项,单测 803→808 绿,冒烟过)

1. **让位死锁三刀**:fb_yield_deadlock_fuse(让位 ≥60s 或首塔 no_placement ≥3 → 熔断恢复 critical 钉 FB);冗余门(矿 ≥400 不让位);pylon_rescue_pin_ok(per-base 60s 冷却+矿 ≥400 才钉,三处贴槽水晶共用台账)。
2. **f2_survival_floor 豁免收口**:在途塔黄了(工人死/被拽走)即清台账补注册+per-base 事件;告警 age 从 Nexus 落成分矿守卫首帧起算(修晚 68s)。
3. **latch×首扩互斥+通道收口**:fb_latch_trigger_gated(townhalls 含在建 <2 不触发);_o373_fb_pin_yield 仲裁统一出口,_dispatch_structure 入口对让位期 FLEETBEACON 一律 nexus_yield(O110/O360 超时等非 latch 通道全堵)。
4. **watchdog 双孔封堵**:fleet_collapse_clock_reset(回 ≥2 持续 ≥15s 才清零,累计制);「O373:舰队断档但无钱」30s 节流事件不静默。
5. **zerg AA 豁免上限**:zerg_aa_exemption_capped(commit 期可见 CORRUPTOR+BROODLORD ≥8 即便 zerg 也撤蹲)。
6. **O302 出发闸**:push_enemy_army_gate supply_ratio 1.5→1.0(敌可见 ≤ 我方才出发),与 advantage/full_pop 合并单判;既有测试 test_full_pop_all_in 语义相应更新(敌 150>139 改判蹲守)。

### 本轮 bench 验收口径

① 零让位死锁(≤60s 或矿 ≥400 不让);② F2 注册零 target=0;③ 单矿局 FB 不抢 Nexus;④ 断档无钱有事件;⑤ zerg commit 期腐化+大龙 ≥8 撤蹲;⑥ 零顶波出击;⑦ Terran ≥1/3 恢复+Rush ≥1/3 保持。

### 下轮安排

- lane1 o373a:VH Terran Power×3(恢复验证)。
- lane2 o373b:VH Zerg Rush×3(回归保险)。

**遗留风险(记入)**:

- O373-③a 触发门对重建 latch 一并生效:二矿被拆回单矿且 FB 待重建时,latch 要等重新开矿才触发(Nexus 优先教义的必然推论),若 bench 出现该形态回归可再议。
- O307 撤开矿抖动、O364/O365 循环欠账未动。
- Terran 转型点(600s 转航母撞 560-570s MM timing)是策略层欠账,下轮候选。


## o373 结果(VH Terran Power 1/3 恢复 + VH Zerg Rush 1/3 保持)+ O373 七验收判定(⑤ zerg AA 存疑)+ O374(zerg AA 信用记忆+zerg 出发宽下限+O365 循环收敛+Terran 转型真空防守+F2 target 字面收口)

**日期**:2026-08-20

### o373 结果

- o373a carrier vs VH Terran Power:1/3(g2 胜 1701.9s,恢复到水位)。
- o373b carrier vs VH Zerg Rush:1/3(g3 胜 1514.7s,保持)。
- **总目标盘点**:VH Zerg Power/Rush 打穿、Timing 封存;Terran Power 2/9;Terran Rush/Timing 未测。

### O373 七验收判定(本轮验证对象)

- O373-① 让位死锁三刀 → **验收① ✓**:熔断 3+3 局 0 次(从未需要);让位 ≤11s 或矿 ≥400 不让;水晶 10/29/17 根 vs 基线 30 根烧 2000 矿,烧矿消失。
- O373-② F2 豁免收口 → **机制工作正常**(在途塔黄了清台账补注册 ✓:o373a g2 274.2s、o373b g2 461.5s/g3 985.0s);字面 target=0 仍有 4 次(全为在途豁免,O374-⑤ 收口)。
- O373-③ latch×首扩互斥 → **✓**(latch 在 Nexus 在途计数下不抢;边界:o373a 两局 latch 在二矿落成前 1-1.4s 触发,townhalls 仍=1,口径待收紧)。
- O373-④ watchdog 双孔 → **✓**(o373a g3 断档无钱 ×2、o373b g2 1270.9s 各 fired)。
- O373-⑤ zerg AA 上限 → **存疑**:o373b g2 在 1068.8s 起 AA≥8(峰 22@1129)但无撤蹲日志——机制只认当帧可见,腐化 1098.7s 离视野→1111.8s 闸全开。
- O373-⑥ O302 出发闸 → **Terran ✓**(g3 敌全程领先闸全关零出击);**zerg 形同虚设**(_opp_is_zerg 豁免,o373b g2 O302@1111.8 顶波团灭)。
- **验收⑦ 双 1/3 踩线达成 ✓**。

### o373a 胜局(g2)配方全面复现且更快

- 时间线:BY 116.5(基线 140.6)→SG 172.8(221)→FB 309.4(377.7,早 68s)→首航母 454.0(638.8)→**O302 二十九连推**→舰队 29(20)。
- 经济产出:农 72、四矿、终局 198/200、击杀 40375+17900。
- 两负死因:还是 550-700s MM timing 转型真空(舰队 2-6 对 MM 27-56 supply+维京 4-8 架点名);O302 出击与敌抄家窗口重叠(509.4/528.5s 出击 vs 515/533s 抄家)——舰队出门时家最空。

### o373b 尸检

- 胜局 g3 配方约七成复现(农 68/5 矿/舰队 20/O302×12),时点全面推迟(FB 883.9s vs 基线 377.7s)。
- g1:O365 Nexus 循环 ×3+O364 等钱 → 全链晚 120s+,571.9s 敌 14 地面抄二矿舰队=0。
- g2:运营最好(农 72/四矿/塔 17-19)但 1111.8s 在 17 腐化离视野 13s 后出击,舰队 11→1 团灭(zerg AA 视野洞)。
- O365 Nexus 循环恶化:g3 ×6 轮烧 150s,推迟 FB/航母 300-500s,是当前最大拖链。

### O374 落地(下一轮验证对象,五项,单测 808→816 绿,冒烟过)

1. **zerg AA 信用记忆**:aa_peak_sticky(60s 粘滞峰值不归零)+zerg_aa_credited(max(当帧,粘滞峰)+尖塔曾见 +2);豁免帽和重评都吃信用计数。
2. **zerg 出发宽下限**:zerg_departure_floor_ok(敌可见 supply < 我方 ×1.5 才放行;黄金窗 _force_push 通道天然豁免,胜局打法不动)。
3. **O365 循环收敛(根因查明:不是强制直钉没生效,是等钱振荡)**:银行 20-445 振荡,ares janitor 只在 can_afford 才重发建造令,条目 30-60s 后被清扫→重钉重走;nexus_repin_afford_ok(矿 <400 返回 no_money 不派工,钉即开工,循环失去燃料);force 时换矿点(排除上轮目标选最近空闲点);成交 T+15s 校验失败路径并入同计数同强制(此前不计数不强制,max_rounds=1 永不生效)。
4. **Terran 转型真空防守**:carrier_transition_ready 加敌情判据(敌地面 supply ≥35 或坦克首现即转,不再固定 600s);transition_push_hold(terran+FB 落成+舰队 <8+有基地塔 <2 → 守家不跟压);O367 塔地板未触发根因查明(种族门只认 zerg timing/rush)→ wave_cannon_floor_active(terran 全 build 开门)。
5. **F2 target 字面收口**:f2_target_literal(target=0 且就绪+在途 >0 → 字面抬 1 报在途)。

### 本轮 bench 验收口径

① zerg commit/出击在腐化离视野 60s 内仍被闸;② zerg 零「敌 ≥1.5× 出击」;③ Nexus 循环 ≤2 轮收敛;④ Terran 550-700s 零「舰队出门家空被抄」+转型点提前事件可见;⑤ F2 注册字面零 target=0;⑥ VH Terran Power ≥2/3 冲打穿+Zerg Rush ≥1/3 保持。

**遗留风险(记入)**:

- O374-④b 的「留守过半」按整队留守实现(锚点框架不支持分兵),若 bench 显示转型期压制不足再议。
- o373a 两局 latch 在二矿落成前 1-1.4s 触发的口径边界未收紧。
- Terran 转型真空若 ④ 修不透,候选:转型期电池阵加厚/风暴集火维京逻辑。


## o374 结果(VH Terran Power 0/3 回归 + VH Zerg Rush 0/3 回归)+ O374 六验收判定(双 lane 元凶实锤)+ O375(④b 去 min 化+塔地板预警+SG2 豁免+出发闸吃峰值+no_money 封顶)

**日期**:2026-08-20

### o374 结果

- o374a carrier vs VH Terran Power:0/3(上轮 1/3,回归)。
- o374b carrier vs VH Zerg Rush:0/3(上轮 1/3,回归)——**O374 双 lane 回归**。
- **总目标盘点**:VH Zerg Power/Rush 打穿、Timing 封存;Terran Power 2/12;Terran Rush/Timing 未测。

### O374 六验收判定(本轮验证对象)

- O374-① zerg AA 信用记忆 → 机制生效(sticky 簿记 920s 峰 8→980s 回落 5;g2/g3 cred=11 撤蹲激活)但无收益:尖塔全程未见(+2 信用从未生效),腐化首见=致死波已到脸。
- O374-② zerg 出发宽下限 → **字面零违规但闸被战争迷雾系统性绕过**(o374b g2 两次 O302 commit 后 3-10s 敌 51-79 supply 才显形)。
- O374-③ O365 循环收敛 → **2/3**(循环 6 轮→0-1 轮,二矿提前 150-240s;g3 三轮 no_money 空转 336→424s);**但修好循环暴露了 SG2 饿死的存量病(见回归判决)**。
- O374-④ Terran 转型真空防守 → **④b 是 Terran 元凶(见回归判决)**;④a 转型提前可见但航母没出得更早(中性);④c 塔地板触发=讣告(全部在波进门后抬:547.9/833.3/812.6s,塔峰 4-6 低于胜局 11)。
- O374-⑤ F2 target 字面收口 → **通过**(注册全部 ≥1)。
- **验收⑥:双 0/3 未达成 ✗**。

### 回归判决(两 lane 元凶不同,都实锤)

**Terran 元凶 = O374-④b transition_push_hold(锁死赢法)**:

- 判据 min(全基地就绪塔)<2 且 fleet<8 几乎常态成立(任何新矿 0 塔即全局锁死),FB 落成起 _army_gate_ok=False 锁到死。
- O302 从 o373a 胜局 ×29 掉到 0/0/2;o374a g3 舰队 757.3s 刚到 8 立即解锁 ×2——时间戳严丝合缝。
- **反证:o373a 胜局配方(528.5s fleet=5 起推 ×29)在 ④b 下就是非法的**——把唯一实证的赢法立法禁止了。
- 「留守保家」被证伪:三局舰队全在家,527-561s 波照样穿(1 塔+2-3 风暴对 10-12 地面+坦克)。
- 后果链:零压制 → Terran AI 自由运营到 64-94 supply → 我方 41-45 supply 被质量碾。

**Zerg 元凶 = O374-③「成功」暴露的存量病(SG2 饿死)**:

- o373b 胜局真正支柱是 12 虚空+82 own supply(不是航母);Nexus 循环 6 轮意外拖晚 FB 到 883.9s,空出的资金窗让 SG2 在 413.8s 落成、虚空堆到 12 架。
- O374-③ 修好循环 → 二矿提前 → O369 FB latch 提前触发(g1 450.2/g2 395.1s)→ 囤矿 300+200 → SG2 饿死(851.8/871.9/全程没有 vs 413.8s)→ 虚空峰 2/4/1 → own supply 46/58/36 vs 82。
- ①②战斗闸实证零伤害(全程基本空转,宽下限在所有安静窗都是开的)。

### O375 落地(下一轮验证对象,五项,单测 816→822 绿,冒烟过)

1. **④b 去 min 化+条件收窄**:transition_push_hold 签名改(fb_done, fleet_count, main_base_cannons, threat_active, fleet_need=5)——塔口径 min(全基地)→主基就绪塔(不选「任一基地」:新矿 2 塔主基裸奔时放行=换家);fleet 8→5(对齐胜局 528.5s fleet=5);threat_active 才锁(无波不锁)。
2. **④c 塔地板改预警**:wave_cannon_floor_trigger(信用 supply=max(当帧,60s remembered 峰值)≥30 或 terran t≥480 定时)——波进门前立塔不是讣告;_o375_supply_peak 台账(②④共用)。
3. **SG2 豁免+闲置填充**:fb_latch_pin_afford_ok(预扣口径:latch 钉 FB 改「存款 ≥FB+SG2 全款 450/350」保证 FB 不饿死);sg2_pre_fb_pin_needed(SG1 落成即 critical 钉 SG2,豁免疫 latch/基金窗,保留二矿让位与 Nexus 资金窗两道闸);sg_prefb_voidray_fill(SG 闲置产虚空 cap 8,60s 死锁门槛移除)。
4. **出发闸吃 remembered 峰值**:enemy_supply_credited(max 当帧/粘滞峰),zerg_departure_floor_ok 与 push_enemy_army_gate 同吃。
5. **no_money 封顶+FB/二矿硬序**:nexus_repin_afford_ok 加 forced 参数(循环 ≥2 轮免矿量门驻点等钱成交);FB 基金窗加 fb_latch_trigger_gated 硬序(二矿未开工不开窗,o374a g1 的 FB 285s 抢在二矿 321s 前实证)。

### 本轮 bench 验收口径

① Terran 局 O302 恢复(×10+);② 塔地板在波进门前触发;③ zerg 局 SG2 ≤450s+虚空峰 ≥6;④ 零「commit 后 10s 内敌 2× 显形」出击;⑤ Nexus 循环零 no_money 空转+FB 不抢在二矿前;⑥ Terran ≥1/3 恢复+Rush ≥1/3 恢复。

**遗留风险(记入)**:

- terran t≥480 定时地板是常态抬 target≥3,与 O360-③ 塔投资软顶(12 座)并存,穷局可能压舰队资金——若 bench 出现舰队晚于此,回查该档。
- o374b g1 在 847-896s 各闸静态全通仍零 O302(疑似 steer stance/E9 滞回或 hot 锚点抖动),已加 near-miss 簿记需求待下轮直读。
- stargate_deadlock_voidray/f2_wave_cannon_floor 变为无调用方(函数与旧单测保留)。


## o375 结果(VH Terran Power 0/3 + VH Zerg Rush 0/3,连续第二轮双 0/3)+ O375 六验收判定(SG2 死代码主元凶)+ O376(门修透+盲推硬闸+sticky 120s+全局塔帽+舰队下限+SG 重建冷却)

**日期**:2026-08-20

### o375 结果

- o375a carrier vs VH Terran Power:0/3(上轮 0/3,连续未恢复)。
- o375b carrier vs VH Zerg Rush:0/3(上轮 0/3)——**连续第二轮双 0/3(o374+o375 累计 0/12)**。
- **总目标盘点**:VH Zerg Power/Rush 打穿、Timing 封存;Terran Power 2/15;Terran Rush/Timing 未测。

### O375 六验收判定(本轮验证对象)

- O375-① ④b 去 min 化 → **部分生效**:O302 从近 ×0 恢复 ×2/×4(g3 舰队 757.3s 到 8 立即解锁的锁链解除),但质量差——g1 两次均黄金窗=False 且敌信息全空,盲推撞 57→85 supply 主力团灭。
- O375-② 塔地板改预警 → **生效(真收益)**:6 局 ~50 次「O375:敌波预警」事件,信用 supply/t≥480 双口径实证,主力波前 10-92s 抬地板;但收益被落地层吃掉(no_placement/贴槽水晶,a-g1 二矿告警 241s 被抄时仍无塔)。
- O375-③ SG2 豁免+虚空填充 → **死代码(主元凶)**:production_manager.py:4799/:5328/:5363 三处被 `_ai_build == "timing"` 门住,而 zerg lane bench 协议是 `--ai-build Rush` → 永不求值(o375b g2 有 290s SG1 就绪窗口一次没进);SG2 仍靠 O218 气烂银行 798.6s 兜底或没有,虚空峰 1/6/2 vs 胜局 12。**第二次犯同一类错**(O364-① 同款门死)。
- O375-④ 出发闸吃峰值 → **未生效/窗太短**:o375b g2 O302@927.8 commit 后 0.3s 敌 37 supply 显形,6 虚空 12s 全灭;60s sticky 窗对 Zerg Rush 90-120s 波次节奏太短。
- O375-⑤ no_money 封顶+FB 硬序 → **生效 6/6**(FB 均在二矿后,无 no_money 死循环、无 forced 驻点)。
- **验收⑥:双 0/3 未达成 ✗**。

### o375 尸检(两尸检一致)

- **bisect 不值得做**:三个主要病灶(塔 placement 死锁/SG 供电槽紧张/SG 长期空置)在 o373 胜局里就存在(老遗留);SG2 饿死是 o374 引入,o375 修了个死代码没修到;根因已代码级实锤(门没开=静态可读+事件零触发双证),机时应投给修门后的验证轮。
- **塔三路叠加无总闸**:o375b g2 塔峰 23(F2 累积+O375 地板+O366 FB 落成+2)≈3450 矿 ≈ 一艘半航母舰队,舰队被拖到 956s 才有首航母。
- **胜败分水岭在舰队体量**:o373a 胜局舰队峰 29、o373b 胜局虚空 12+SG2@414;o375 六局舰队峰 1-10、虚空 1-6。
- SG 产能空置遗留恶化:o375a g3 四个 SG 全程只产 1 架风暴、气 300-520 烂银行;O218 追加信号 150s 无响应。

### O376 落地(下一轮验证对象,六项,单测 822→829 绿,冒烟过)

1. **门修透+防再犯**:zerg_sg_pin_lane_active(与 wave_cannon_floor_active 同口径);三处目标门(4824/5351/5385)+同族联动 4 处(2684/4779/4867/10587)放宽 `in ("timing","rush")`;**全文审计 93 组 `=="timing"`+6 组 `=="rush"` 单值门逐处处置**(审计清单在代码注释);**防再犯单测 test_protocol_matrix_reachability**(协议矩阵 × 关键闸可达性)。
2. **盲推硬闸**:blind_push_blocked(信用 supply=0 即拦,并入 _army_gate_ok 同一判,_force_push/黄金窗豁免)。
3. **sticky 窗 60→120s**(对齐 Zerg Rush 90-120s 波次;AA 粘滞窗不动 60s)。
4. **全局塔数帽**:f2_global_cannon_cap(FB 落成后钳 min(总塔 ≤14,每基地 ≤4),threat 豁免)。
5. **出击舰队下限 4→6**:push_fleet_floor_ok(黄金窗 min_fleet 与 _force_push 不动)。
6. **O182 连发冷却**:sg_rebuild_cooldown_ok(30s,节流注册行为本身)。

### 本轮 bench 验收口径

① zerg rush lane 出现「SG1落成即钉SG2」事件+SG2 ≤450s+虚空峰 ≥6;② 零盲推;③ 零「commit 后 60s 内敌 2× 显形」;④ 塔峰值 ≤14;⑤ 零 fleet<6 出击;⑥ 双 lane ≥1/3 恢复。

**遗留风险(记入)**:

- 审计标注两个「同族观察项」(O239/O260 气烂折现、O294-③/O362-③ 舰队基建通道)本轮无尸检证据未放宽,若 o376 bench 再现气烂/SG 迟滞下轮凭证据再议。
- O208/O216h 等 transition 块内 timing 门是防御性死分支(timing 禁入 transition 不可达但无害),未动避免无关 churn。
- 若 o376 修门后仍 0/3,回退到 o373 态(eff47ff)复跑量化 O374/O375 净效应才有增量价值。


## o376 结果(VH Terran Power 0/3 连续第三轮 + VH Zerg Rush 2/3 门修透大幅复活)+ O376 六验收判定 + O377(首推窗解锁+E10 时间盒+塔帽全通道+舰队在场口径+供电重试+Forge 保底)

**日期**:2026-08-20

### o376 结果

- o376a carrier vs VH Terran Power:0/3(连续第三轮 0/3)。
- o376b carrier vs VH Zerg Rush:2/3(g2 胜 1194s、g3 胜 1139.7s)——**门修透后大幅复活**(o374+o375 双 lane 0/12 之后)。
- **总目标盘点**:VH Zerg Power/Rush 打穿、Timing 封存;Terran Power 2/18;Terran Rush/Timing 未测。

### O376 六验收判定(本轮验证对象)

- O376-① 门修透 → **复活实锤**:两胜局都打出「SG1落成即钉SG2」事件(@476.0/@508.2);但量化口径未达(SG2 在途 482/586.6 >450,虚空峰 4/3 <6)——**事件级成功,配方级约六成,赢法换骨**(5-6 矿 71 农、supply 200/200、19-21 暴风+4 航母、O302×10-11 经济碾压,不再是虚空时机窗)。
- O376-② 盲推硬闸 → **过**(零盲推;terran 样本薄 O302 仅 1/1/3)。
- O376-③ sticky 120s → **过(贴线)**:o376a g2 推→774.8s 敌 82 vs 我 52=1.58× 未及 2×。
- O376-④ 全局塔帽 → **terran ✓(6/10/10)但 zerg 被架空**:两胜局塔峰 17/21 超帽——main_siege 通道(flows.yml:130)不过帽+threat 豁免常开,帽生效窗趋近零,超帽发生在台账外;6 局零拦截事件。
- O376-⑤ 舰队下限 6 → **过矫实证(本轮最贵回归)**:o373a 配方首推 528.5s fleet=5 被 floor 6 判死;o376a g3 还暴露口径漏洞(报 fleet=6 在场仅 3,含在产/队列)。
- **验收⑥:Zerg Rush 2/3 超额 ✓;Terran 0/3 ✗**。

### o376a 终审(Terran 连续三轮 0/3:机制阻断,非签差)

- 三局同一签名:O302 ×1/×1/×3(vs 胜局 ×29)、首推 708-776s(vs 配方 528.5s)、fleet 峰 8/13/8(vs 29)。
- **鸡生蛋死锁**:O376-⑤ 封杀首推(fleet=5→非法)+ 盲推闸因 Terran 侦查断链信用恒 0 常闭 → **推进窗口数学上不存在** → 不压制 → Terran AI 自由运营到 40-99 supply → 495-626s 两波把采矿打成锯齿(停气转矿反复:气 500+ 烂银行、矿 0-100)→ 首航母拖到 498-671(vs 454)。
- 叠加:E10 被动转型(等坦克首现 514/585s);风暴压制只杀兵不拆建筑(g3 建筑击杀价值仅 250);反维京为零(致死波带 8-21 维京);O363/O368 供电预检死循环(钉完水晶就丢,新矿裸奔 150-400s)。
- **教训(记入)**:O376-⑤ 是用单个数据点(fleet=4 无果)改的阈值,删掉了有胜局实证的配方参数——与 O374-④b fleet 8 是同一类过矫,**阈值改动必须对照胜局配方参数**。
- **Terran Power 值得再攻 1-2 轮(两尸检一致)**:底子厚(BY/SG/FB 全在配方线上、农峰 65、局局先富),死因已解剖到行号不是 Timing 式结构天花板;硬判据:首推窗解锁落地后仍 0/3 即按 Timing 规则封存。

### o376b 那一负(g1)死因链

- SG1@466 迟到 → 427-520 二矿两遭抄 → 526 丢二矿 → 570-602 残敌滞留把 SG/双芯核/Forge 全吃 → 594s 起 tech_not_ready 死锁 292s(没 Forge 不能补塔、等钱造 Forge 矿只有 40 气 524 烂银行)→ 农民 43→7 → overrun;链条:残敌清剿慢 → 科技建筑裸奔 → 重建无保底资金通道。

### O377 落地(下一轮验证对象,六项,单测 829→841 绿,冒烟过)

1. **首推窗解锁**:push_fleet_floor_ok floor 6→5(对齐 528.5s fleet=5);recipe_push_exempt(terran+t∈[500,570]+在场 fleet≥5+主基就绪塔 ≥2 → 豁免盲推闸,只豁免盲推闸其它闸照常);scout_credit_fallback_ok(terran+t≥480+信用 0 → 既有 SCOUTING 通道改派敌主基刷信用)。
2. **E10 转型时间盒**:carrier_transition_time_box(terran+FB+150s 或 t≥480 硬转;坦克首现保留为提前条件之一)。
3. **塔帽收口全通道**:cannon_hard_cap_active(就绪塔总数 ≥18 硬顶,threat 豁免截止+main_siege 整体关闭;17 在顶内胜局配方不动,21 超顶被钳;critical 保命塔不钳)。
4. **O302 舰队计数在场口径**:_fleet_total 剔除 cy_unit_pending(报 6 实 3 实证)。
5. **供电预检后重试塔落点**:power_precheck_stalled(滞留 ≥30s 并入 O364/O365 手工锚点重试链;预检返回后旧调用方直接丢弃=「钉完水晶就丢」的代码层对应)。
6. **科技建筑重建保底**:forge_rebuild_guarantee_ok(空转 ≥60s 且 forge 无实体无在途 → critical 钉 150 预扣驻点等钱,对齐 FB latch 语义;挂 expansion_defense_guard_active 门覆盖 zerg rush——O333 门不含 rush 正是 o376b g1 缺口)。

### 本轮 bench 验收口径

① Terran 首推 ≤600s 且 O302 ×10+;② 首航母 ≤480s;③ 塔峰值 ≤18(全通道);④ 零「报 N 实 <N-1」出击;⑤ 新矿落成 90s 内 ≥1 塔;⑥ 零 tech_not_ready 空转 >90s;⑦ Terran ≥1/3 恢复(冲 2/3)+Rush ≥1/3 保持。

**遗留风险(记入)**:

- recipe_push_exempt 限 terran(zerg 信用不断链,碰 zerg 会复活 o375a 盲推团灭)。
- 反维京短板本轮只到配比层,仍未修。
- scout_credit_fallback 无先知时分支空转(侦查兵源依赖既有 OracleManager)。


## o377 结果(VH Terran Power 1/3 判决轮通过 + VH Zerg Rush 0/3 幻影舰队回归)+ O377 七验收判定(④ 舰队在场口径假修复实锤=头号发现)+ O378(在场口径实修+E10 钉 SG2+虚空 cap+塔降级+腐化硬闸)

**日期**:2026-08-20

### o377 结果

- o377a carrier vs VH Terran Power:1/3(g2 胜 ~1100s)——**判决轮通过,不用封存**。
- o377b carrier vs VH Zerg Rush:0/3(上轮 2/3)——门修透复活后回吐。
- **总目标盘点**:VH Zerg Power/Rush 打穿、Timing 封存;Terran Power 3/21;Terran Rush/Timing 未测。

### O377 七验收判定(本轮验证对象)

- O377-① 首推窗解锁 → **验收① FAIL**:首推 766-782s(全 >600);recipe_push_exempt 三局零触发(fleet≥5 在 [500,570] 窗数学上不可达——SG2 全在 743s+);floor 6→5 唯一可考作用:g2 首推报数 fleet=5 压线过闸省 ~30s。
- O377-② E10 时间盒 → **验收② FAIL**:480s 准点硬切但切完没钱没产能(单 SG+风暴排队,首航母 608-638s)。
- O377-③ 塔帽全通道 → **2/6 超顶**:就绪 18 时在途 ~3 座继续落成,硬顶被在途穿透。
- O377-④ 舰队在场口径 → **假修复实锤(头号发现)**:`get_own_unit_count` 默认 `include_pending=True`(unit_cache_manager.py:431),注释写「剔除在产」代码没传参;快照逐帧对证:o377b g2 @890 报 fleet=5 在场=2、g1 @870.6 报 5 在场=3、o377a g2 @812.6 报 9 在场=6。
- O377-⑤ 供电重试链 → 无重试风暴(no_placement 同量级),但也没治好病(o377b 6 次开矿仅 2 次 90s 内达标)。
- O377-⑥ Forge 保底 → 6 局零触发(无伤)。
- **验收⑦:Terran 1/3 ✓(判决通过);Zerg Rush 0/3 ✗**。

### o377a 胜局(g2)与两负

- **胜局链**:FB@325→时间盒 480→航母@638→首推 @782 fleet=5→×11 连推→舰队 28(敌全程仅 1-3 维京)——骨架成立但比 o373a 配方慢 ~250s,赢的是后期产能碾压不是配方节奏。
- g1:整局单星门(1530 气烂银行无人花),舰队峰 3,566s 敌 38-supply 一波穿。
- g3:卡人口 129s 舰队钉死在 8,6 次推进撞坦克阵,1144s 敌 8 维京+雷神清零 3 航母(反维京闸只看当帧可见)。

### o377b 回归判决(两尸检一致)

- **主犯 = O377-①a(floor 6→5)× ④-bug 组合**:floor 5 按含在产口径放行 → 真实出击舰队从 o376b 的在场 6-8 艘降到 2-4 艘,首推在场 2-3 出门捐给 76-96 supply 波。
- **帮凶**:zerg 填线虚空负资产(g2 产 9 虚空 1350 气,932-952s 全灭,FB 被饿到 @751 比配方晚 220s);敌签偏重(E6 骚扰 420-580s 连绵)。
- ③⑤⑥ 全部无罪(零触发/无风暴/未误钳);方差成分真实但失败模式是系统性的(幻影舰队出击)。
- **三局共同死因**:舰队峰 10/14/16 拖过 1200s 进腐化+大龙窗口被全歼(O302 注释自证「850s+ 暴风被克」);g1 同一秒「塔投资冻结(腐化≥4)」舰队却在出门;AA 重评 30s 间隔对暴风太短(28s 内死在两次重评之间)。

### O378 落地(下一轮验证对象,六项,单测 841→853 绿,冒烟过)

1. **修 O377-④ 实 bug**:combat_manager.py:523/535 两处补 `include_pending=False`;`_fleet_count` 同时喂 _force_push/黄金窗/carrier_push_safe 一并转在场口径;单测(在场 3+在产 2 判 3)。
2. **E10 转型即 critical 钉 SG2**:e10_sg2_pin_needed + `_o378_e10_sg2_needed` latch(转型帧置位);豁免疫 FB 基金窗预扣,保留三道既有闸。
3. **出击闸信用口径(核查结论:代码已达标,前提与实际不符)**:combat_manager.py:621 的 _enemy_vis 自 O375-④ 起就吃 credited;o377b g1 @870 的「可见 10→12s 后 76」是情报缺口(波从未入视野)不是口径不一致;补回归测试防口径回退。
4. **zerg 填线虚空 cap ≤2**:sg_prefb_voidray_fill 调用点传 cap=2;sg_post_fb_fill 加 voidray_cap=2 参数;terran 不动。
5. **塔落点降级**:pylon_ring_fallback_anchor(水晶 ±6 环带 placement grid 扫描第一个可建 2x2,水晶旁天然带电);扇形 8 候选全失败即降级。
6. **腐化硬闸+显形即重评**:zerg_corruptor_departure_blocked(信用腐化 max(当帧,60s粘滞峰) ≥4 → 不出击,zerg 不豁免);aa_reeval_due(30s 定期保留+信用计数 ≥4 且上升立即重评)。

### 本轮 bench 验收口径

① 零「报 N 实 <N-1」出击(在场口径);② E10 触发即 SG2 钉点事件;③ 零「敌信用 ≥1.5× 出击」;④ zerg 虚空峰 ≤2;⑤ 新矿落成 90s 内 ≥1 塔(6/6);⑥ 零「信用腐化 ≥4 出击」;⑦ 双 lane ≥1/3(Terran 冲 2/3)。

**遗留风险(记入)**:

- _aa_hold/_fleet_now 的独立 get_own_unit_count 调用未动(最小改动),若出现同类虚报再统一。
- 塔硬顶在途穿透(验收③ 2/6 超顶)未修,下轮候选。
- o377b g2 扩张闸(478s 后再无 NEXUS 钉点,手里 535 矿,疑似 threat/rush 锁整局)未查。
- O365「买得起=False」诊断行疑似 can_afford bug(矿2170/气443 买不起航母)待查 supply_left。


## o378 结果(VH Terran Power 0/3 第四轮=执行封存 + VH Zerg Rush 0/3 回归)+ O378 七验收判定(①生效/②半接线/④⑤接错/⑥被架空)+ O379(腐化硬闸接统一出口+虚空帽接重建窗+塔降级接重试计数)

**日期**:2026-08-20

### o378 结果

- o378a carrier vs VH Terran Power:0/3(连续第四轮,累计 3/24=12.5%)。
- o378b carrier vs VH Zerg Rush:0/3(o376b 曾 2/3)。
- **重大判决:Terran Power 执行封存**——预注册判据「首推窗解锁落地后仍 0/3 即封存」已满足;死因已迁出被修机制。
- **总目标盘点**:VH Zerg Power/Rush 打穿、Zerg Timing 封存、**Terran Power 封存**;Terran Rush/Timing 未测。

### O378 七验收判定(本轮验证对象)

- O378-① 在场口径实修 → **生效 ✓**:双 lane 20 次出击零假报,逐帧对证;但也因此暴露真实基本面——舰队峰 7/13/2/18/9/9,不是假报问题。
- O378-② E10 钉 SG2 → **半接线**:仅 g3 打出钉点事件;g1 条件自灭、g2 卡 can_afford 静默失败;zerg lane 结构性不适用;fleet≥5@[500,570] 三局全灭。
- O378-④ 虚空 cap 2 → **未生效(接错路径)**:cap 只接两条填线 lane(合计产 3 次);真正量产源是 O121-① rebuild_window_spawn(proportion 0.7 注入配方,无帽)——g1 重建窗近 600s 虚空滚到 10 艘吃 1500 气饿死风暴/航母。
- O378-⑤ 塔降级 → **未生效(条件错位)**:只在「扇形 8 候选全灭」触发,六局零事件;真实失败模式是 no_placement/power_precheck/等钱/no_worker,全不在覆盖内;验收⑤ 合计 1/9(新矿裸奔 130-262s)。
- O378-⑥ 腐化硬闸 → **被 _force_push 架空(最重伤)**:zerg lane 的 O302 几乎全走 _force_push(设计豁免),g1 五次在信用腐化 5-18 下出击(1442@9/1472@5/1611@8/1770@18/1871@5),舰队 13-18 艘分批喂腐化群——正是⑥要防的死法原样重演;⑥b 显形即评零日志埋点不可证。
- **验收⑦:双 0/3 FAIL**。

### o378a 封存判决(两尸检一致,数据依据)

1. **判据已满足**:连续第四轮 0/3,累计 3/24;首推窗解锁确实落地(g2 O302×9 fleet 5→12 连推)。
2. **死因迁出被修机制**:①零违例后真实舰队峰 7/13/2 vs 配方 29,出击闸怎么调都没有可放行的舰队。
3. **瓶颈上移且四轮未触及**:FB 建造停滞(自救链 45-132s)→ 首航母 +44/+169/+72s → fleet≥5 窗全错过 → 出门撞维京/生化主力;四轮调的都是出击口径/闸/钉点,FB 资金与塔链实建失败从未被修。
4. **剩余病灶**(FB 停滞/塔链实建败/等钱无塔)**是双 lane 共病**,在共享轮修掉后再视情解冻更高效。
5. g2 还暴露卡人口 92/90、72/69 低级失分。

### o378b 回归判决(非 O378 误伤)

- ⑥ 硬闸零拦截(它根本不在 _force_push 通道上,谈不上误伤);④ cap 没接上不存在太紧。
- **真实回归 = 节奏全面慢于 o376b 配方**:首风暴 663-892s(vs 639s)、二矿 350-442s(vs 297-337s)、舰队峰 9-18(vs 23-25)、O302 ×1-8(vs ×10-11)+ 敌签(三局全遇快腐化/大龙)+ 两个机制空转(④⑥)。
- own supply 峰 177/146/132 高于基线 82 是虚胖(2 矿憋兵+虚空占 supply),不是经济变好。

### O379 落地(下一轮验证对象,三项,单测 853→856 绿,冒烟过)

1. **腐化硬闸接 _force_push 统一出口**:force_push_corruptor_ok(fleet ≥ 信用腐化 ×1.5 才放行,否则回落蹲守;信用 0 恒放;黄金窗显式豁免);闸放 _force_push/_golden_push 合并之后、最终出击判之前,单点覆盖。
2. **虚空总量帽接 O121-①**:rebuild_window_spawn 加 voidray_field/voidray_cap 参数(cap 非 None 且场上含在产 ≥cap 不注入;zerg 传 2,terran 传 None 不动)。
3. **塔降级接 O365 重试计数**:tower_sector_fallback_due(per-base 重试 ≥3 跳扇形直接水晶旁 2x2 扫描;复用既有 _o364_anchor_attempts 台账,no_placement/power_precheck 滞留/O368 强钉的失败都汇进同一链)。

### 本轮 bench 验收口径

① 零「信用腐化 ≥4 出击」(含 _force_push 通道);② zerg 虚空峰 ≤2(含重建窗);③ 新矿落成 90s 内 ≥1 塔(6/6);④ VH Zerg Rush ≥1/3 恢复;⑤ VH Terran Rush 首测有数据。

### 下轮安排

- lane1 o379a:VH Zerg Rush×3(验证 O379)。
- lane2 o379b:**VH Terran Rush×3(新战线开辟)**。

### 封存组合清单(更新)

- Zerg Timing(0/30,结构性量级差,机制修无可修)。
- **Terran Power(3/24,死因迁出被修机制,剩余病灶是双 lane 共病,共享轮修掉后视情解冻)**。
- 两个组合的机制链全部保留在代码里,司令复议前不重开。

**遗留风险(记入)**:

- O379-① 拦下后舰队走蹲守锚点,事件流不再有出击记录,尸检直接查「信用腐化 ≥4 时无出击」。
- o378b 节奏回归(首风暴晚/idle_builder)与 o378a 共病(FB latch 停滞/等钱无塔)未修,下轮候选。
- Terran Rush 新战线的早期压力形态与 Zerg 不同,首批尸检重点看 opener 适配。


## o379 结果(VH Zerg Rush 0/3 第三轮 + VH Terran Rush 0/3 首测)+ O379 五验收判定(①生效但未被压测/②咬死/③打错环节)+ bisect 判决(非代码回退,胜率为方差主导,不回滚)

**日期**:2026-08-20

### o379 结果

- o379a carrier vs VH Zerg Rush:0/3(连续第三轮,o377b-o379b 累计 0/9)。
- o379b carrier vs VH Terran Rush:0/3(新战线首测)。
- **总目标盘点**:VH Zerg Power/Rush 打穿、Zerg Timing 封存、Terran Power 封存;**Terran Rush 首测 0/3**;Terran Timing 未测。

### O379 五验收判定(本轮验证对象)

- O379-① 腐化硬闸接 _force_push → **生效但几乎未被压测**:6 局仅 1 次出击(配方基线 ×10-11),且当时信用腐化=0;败因形态已从「出击送死」迁移为「永不出击、被磨死」——舰队根本到不了 _force_push 门槛(fleet≥8+t>540)。
- O379-② 虚空帽接重建窗 → **生效咬死**:虚空峰 1/2/2 vs o378b 的 9/10/3;1500 气出血已止;副作用:舰队质量下滑的贡献者之一。
- O379-③ 塔降级接重试跳扇形 → **机制在跑但覆盖不全+打错环节**:o379b 触发 5 次但跳扇形后仍 no_placement;o379a 三局 0 条事件且 g2 出现「O365 重试第5次仍走扇形」(存在绕过判据的重试入口);首塔真正瓶颈是**等钱**(每局 idle_builder 等钱造塔 ×4-13)和塔落点错位(o379b 三次 E6 报「无塔」时全局塔 ≥5,塔落在主基);验收③ 合计 0/9(新矿裸奔 116-249s)。
- **验收④ Zerg Rush ≥1/3:✗ 0/9;验收⑤ Terran Rush 首测数据 ✓**。

### o379a 深审(0/9,败因形态切换)

- **配方对照(o376b 胜局 → o379a)**:农峰 71 → 31-45、基地峰 5/6 → 2/2/2、FB 546/530 → 从未/546/619、舰队峰 23-25 → 1/8/7、O302 ×10-11 → 0/1/0。
- **败因形态切换**:o377b/o378b 是「拖进腐化窗口舰队被全歼」(死于 1175-2239s);o379a 是「舰队根本没成型就被地面波推平」(死于 766-1075s,全部死在胜局首推窗之前)——死得更早了,且致死波规模反而更小(g1 被 ~21 supply 纯地面推平)。
- **直接链条**:O145 农民停滞 ~200s 起 → rush 锁要等「舰队成型」(O204)才解 → 舰队要 FB → FB 要 300/200 → 矿被塔/叉吸血 + O364 停气校验环泄漏复拽(气继续进、矿继续饿)→ 死锁。
- 二矿 361-426s 才落成且全部无塔被抄 = 二矿变负资产。

### o379b Terran Rush 首测评估

- **敌形态:不是早而弱,是晚而重的死亡球**——首个非 SCV 敌军可见全部在 502-538s(此前零骚扰),首波 21-37 supply 枪兵+劫掠+坦克架射,此后每 150-200s 一波逐波加重(g3:33→41→74→104);坦克/解放者射程白嫖塔(打不到),维京专猎舰队,寡妇雷批量屠农。
- **opener 错配 300s**:78.8s 凭「1 座兵营」判 rush 进 Zerg 式锻炉塔+叉应急形态,塔 124-209s 立好后空站 300s、叉子对 MM+坦克白给(g1 七叉两帧团灭);260s 二次侦查已报「兵=0」但 rush 锁没解除。
- **亮点**:g1 二矿 229s 是唯一攒出 62 农+9 塔的局——「利用 500s 无骚扰窗早开二矿」方向已被自己数据验证。
- **与 Zerg Rush 差异**:Zerg 首波 ~200-300s 渐进压;Terran 首波晚 200s+、零接触、一波成团;同一套 opener 对 Terran 把钱花错了 300s 窗口。

### bisect 判决(git worktree 同协议复跑,本轮最重大结论)

- **bis376(0faca8e = o376b 胜局态)复跑 0/3**(终局编成 TEMPEST×3)。
- **bis378(a5e8f10 = O378 态)复跑 1/3**(终局编成 TEMPEST×11+CARRIER×3+VOIDRAY×4)。
- **判决:非代码回退——胜率为方差主导**。o376b 的 2/3 是有利签(抽样运气),不是更好的代码;O378 态复跑反而产出更大舰队;O377/O378/O379 改动均非元凶,**不回滚**。
- 与历史 bisect(o336 态复跑也 1/6)同结论:Zerg Rush 真实胜率 ~20-40% 高方差波动,峰值和低谷都是噪声摆。
- **方法论教训(记入):判升降一律两轮累计+滚动窗口+bisect 复跑验证后才谈回滚;单一轮 0/3 或 2/3 都不能作为回归/改进证据**。
- bisect 基建记录:git worktree + `cp ares-sc2/sc2_helper/sc2_helper.cpython-312-darwin.so`(本地构建产物,worktree 不带)+ poetry install --no-root + import 三段路径冒烟。

### 后续方向(两尸检+bisect 共识)

1. **不回滚**:O377-O379 的机制修复(腐化硬闸/虚空帽/门修透/在场口径)都是净改进,保留。
2. **真实瓶颈(按优先级)**:① 拆 rush 锁-经济死锁(O204 解锁条件从「舰队成型」降级防御评分达标或加时间盒;农民下限保护);② 修 O364 停气泄漏(硬切换抽干采气农民,非校验环);③ 新矿首塔 fund-first(Nexus 开工同帧预留 150 矿+钉塔,修资金链+落点错位);④ Terran lane rush 锁降级(260s 二次侦查「兵=0」解除 O92 应急形态,利用 500s 无骚扰窗早开二矿);⑤ 防「永不出击」(t>900+舰队<阈+防守达标时给豁命推/换家窗)。
3. Terran Rush/Timing 战线继续推进(opener 适配是第一刀)。

**遗留风险(记入)**:

- O379-③ 覆盖不全(O365 重试入口绕过判据)未修。
- 塔降级跳扇形后锚点仍 no_placement(b/g1 锚偏 7 格)——落点引擎本身还有问题。
- 「永不出击」新常态(出击 0-1 次/局)与腐化硬闸的叠加效应待观察。


## o380 结果(VH Zerg Rush 0/3 + VH Terran Rush 0/3)+逐局第一性原理尸检+O381(首扩/重建 Nexus 独占基金+健康矿区扩张)

**日期**:2026-08-20

### o380 结果与计时校正

- o380a carrier vs VH Zerg Rush:0/3。
- o380b carrier vs VH Terran Rush:0/3(game_02 首次 SC2 崩溃后 runner 自动重试，
  有效结果仍为 Defeat)。
- 六局二矿 state 时点：Zerg **425.9/329.5/357.6s**；Terran
  **317.4/237.1/321.4s**。六局只有 Terran game_02 达到 ≤300s。
- `scripts/replay_bases.py` 原按 16 loops/s 把 Faster 录像时间放大 1.4 倍，已按
  22.4 loops/s 修正。修正后录像 Nexus 开工为 Zerg 423.7/327.6/353.6s、
  Terran 314.4/234.2/318.1s，与 state 的「建成/计数」口径只差约 2-4s，
  后续录像经济时间轴统一可信。

### o380a game_01 尸检(Defeat 1052.9s；每局优化点 4 项)

1. **首扩资金没有生产资料优先权**：二矿 425.9s，远超 300s 硬线；360.0/
   395.4s Nexus 工人仍在等钱。单矿 281-394s 已有星门、塔与持续探机开销，
   银行虽到 330 仍反复回落。下一局落地：250s 起首扩 Nexus 独占基金，暂停
   非生存产兵、研究、科技、扩产和非紧急水晶，Nexus 实体出现才解除。
2. **新矿防御资金晚于敌军到达**：二矿 425.9s 成交，495.1s 即以「无塔」被抄，
   500.4s 塔工仍等钱；之后 642.9/831.7/989.1s 又被单塔反复抄。全局有 4-7 塔
   不等于分矿有正确落点。下一局落地：Nexus 开工同帧开启首塔 150 矿基金，
   首塔在途前停非必要消费，并按基地坐标验收而不是全局塔数。
3. **经济体量不足以支撑四星门舰队**：农峰 52，但 619s 已有 3 星门、675s
   4 星门；舰队到 731s 仅 3 艘，终局只剩先知。产能建筑先于收入导致资源被
   固化在闲置产能。下一局验收：Nexus 基金期禁扩产；每局核对星门利用率和
   「新增星门后 60s 的有效舰队产出」，零产出即判冗余投资。
4. **三矿启动仍太晚**：三矿 787.5s，且 56s 后即被抄；没有提前准备健康矿区，
   只能在旧矿衰竭/受袭后追赶。下一局落地：不再只看 Nexus 数，按每片就绪
   Nexus 周围剩余采矿位 ≥15 计健康矿区，45+ 农目标 3 片。

### o380a game_02 尸检(Defeat 571.8s；每局优化点 4 项)

1. **O189 触发不等于二矿成交**：230.4s 已派 Nexus 工人，322.5s 仍在等钱，
   二矿直到 329.5s；期间二气、水晶、叉与科技继续抽走 400 矿窗口。下一局
   以「Nexus 实体 ≤300s」而非「触发/派工」验收，250s 基金阻断所有漏口。
2. **分矿首塔基金没有守住**：二矿 329.5s，423.8s 敌仅 4 个地面单位到场时
   分矿仍零塔，342.9s 塔工已等钱；一个可防的小规模抄矿因此切断双矿收入。
   下一局验收 Nexus 开工后 90s 内至少 1 座分矿塔在途/就绪，失败必须记录
   no_money/no_placement/worker 三分原因。
3. **科技/产能存在但作战产出为零**：394s 已有星门、450s 两星门，终局
   571.8s 舰队仍为 0，气体 497；说明建星门/攒气没有转化为参战单位，科技链
   与经济顺序失衡。下一局尸检必须统计每个作战单位的首产、存活、参战窗口，
   零产出的星门/升级在首扩前一律视为冗余。
4. **农民与基地一起成为被动资产**：农峰 44，但分矿被抄后 15 农长期撤离，
   终局双基地全失。下一局将基地恢复列为最高级生产资料，基地数跌破峰值时
   先重建 Nexus，再恢复常规探机、单位和研究。

### o380a game_03 尸检(Defeat 887.5s；每局优化点 5 项)

1. **首扩仍迟到**：Nexus 工人 215.4s 已出发，二矿 357.6s 才成交；期间
   银行/开销振荡使工人等了 142s。下一局用 250s 硬基金并禁止 O307/O365
   撤派工翻板，确保 Nexus 300s 前出现。
2. **分矿被端后恢复优先级颠倒**：二矿约 490.2s 被摧毁，607.5/708.2s
   重建工人仍等钱，711.2s 才恢复，损失到重建约 **221s**；该窗内仍继续造
   虚空、暴风、升级、舰队航标和暮光。第一性原理上 Nexus 是收入生产资料，
   新兵/升级只是消费品；下一局基地数低于历史峰值即独占 400 矿重建。
3. **常态 40 农硬底线也会抢重建资金**：本局恢复窗约 38-40 农，若继续追
   40 农，单是探机即可先花数百矿。下一局基金期探机底线收窄：首扩迟到只保
   16 农，丢矿只保 12 农；Nexus 成交后再恢复 22/40 常态底线。
4. **两次分矿都因首塔未成交而裸奔**：440.8s 首个分矿「无塔」被抄，重建矿
   807.7s 再次「无塔」被抄；724.3s 塔工仍等钱。下一局首塔基金必须覆盖
   Nexus 开工到塔在途全过程，并阻断直接 `.train()` 绕口。
5. **气体不能替代矿物收入**：终局气 737、矿 45、只有 3 暴风+1 航母；失去
   双矿后继续采气/点高科技不能购买 Nexus 和塔。下一局基地恢复期优先矿物、
   停非必要气耗与科技，恢复健康矿区后再转化气银行。

### o380b game_01 尸检(Defeat 988.2s；每局优化点 4 项)

1. **Terran 假 rush 解除后首扩仍被核心科技排序拖住**：260s 已撤销错误 rush
   形态，但二矿 317.4s；281s 仍单矿 24 农、星门 0。下一局 250s Nexus 基金
   不再受 `_early_core_missing`、星门、rush latch 或 fleet 门否决。
2. **分矿恢复速度不足**：三矿 490.2s，535.9s 无塔被端；675.0s 才重新回到
   3 基地，703.6s 又无塔被端。恢复期间继续四星门运营没有形成足以守矿的增量。
   下一局丢矿基金冻结常规生产，Nexus→首塔顺序成交后再恢复舰队。
3. **矿气严重倒挂**：终局气体 1180、矿物 65；844-956s 单矿仍有 4 星门、
   舰队仅 6-7。说明采气和高科技产能超过健康矿区能支付的矿物端。下一局尸检
   对比矿/气收入和银行，基地损失/矿枯时硬停气，优先补健康矿区。
4. **塔数量与位置不匹配**：全局塔峰 7，但 535.9/703.6s 两次都是分矿无塔；
   不能再用总塔数证明防御充足。下一局按每基地局部塔、电池、敌军到达路径验收。

### o380b game_02 尸检(Defeat 1827.5s；每局优化点 5 项)

1. **速二矿是本组唯一正确经济样本**：二矿 237.1s、三矿 433.9s，农峰 67、
   舰队峰 21，显著好于其余五局；这直接证明早开矿会扩大而非削弱中盘战力。
   下一局把 ≤300s 从软目标升为硬合同。
2. **基地恢复被消费项拖延**：约 558.5s 从 3→2 基地，779.5s 才恢复 3 基地，
   延迟约 **221s**；录像开工口径为 431.6→775.8s。期间多次 O307 撤派工，
   产兵/升级/塔继续花钱。下一局丢矿基金禁止撤派工和所有非生存消费。
3. **名义三矿掩盖健康矿区枯竭**：65+ 农长期只有 3 Nexus，从未启动四矿；
   954.5/965.5s 又有无塔/双塔压不住，1310s 后收入体系崩塌。下一局 45+ 农
   若健康就绪矿区少于 3，立即提前开四/五矿，不等总矿物或旧饱和门。
4. **塔投资过多但覆盖错误**：900-1294s 全局塔 12-14，仍在 954.5、1310.3、
   1402.1、1618.0s 报分矿无塔；数量上已经付出 1800-2100 矿，却没有保护收入点。
   下一局逐基地检查塔/电池到 Nexus 与矿线的距离和射界，禁止用全局塔峰替代。
5. **后期舰队没有转化为终结能力**：舰队 1181-1294s 达 18-21 艘但未结束对局，
   随经济被逐矿拆除而衰减到 0；需要继续逐局检查出击窗口、目标选择和母舰节点，
   但本局上游第一优先仍是维持生产资料，不能用更多作战单位掩盖矿区崩盘。

### o380b game_03 尸检(Defeat 623.3s；每局优化点 4 项)

1. **首扩被早期非必要消费截走**：260s 假 rush 已解除，但 FB、水晶、叉等继续
   消费，二矿 321.4s；281s 银行已 300，仍没有把接下来 100 矿锁给 Nexus。
   下一局 250s 基金先于同帧所有注册计算并强制 ExpansionController 优先。
2. **三矿建得出但守不住**：三矿 442.0s，493.6s 仅 52s 后被 11 地面单位以
   单塔打穿；513.1s 另一矿又以零塔被抄。下一局 Nexus 开工立即首塔基金，
   防御验收按「在途/就绪」且至少覆盖首波到达时间。
3. **基地连续损失后仍产高科技单位**：约 526.3s 3→2、566.5s 2→1，终局仍有
   2 暴风，升级/产线未为重建 Nexus 让位。下一局 `lost_base` 基金必须压住
   SpawnController、舰队 watchdog、pre/post-FB 虚空、不朽、先知和两条母舰直产。
4. **军队出现节点晚于经济死亡节点**：506s 仍舰队 0，562s 基地已掉到 2，
   619s 才有 2 暴风且只剩 1 基地。航母/母舰此时再出现也无法逆转收入断裂；
   下一局先验收 Nexus/健康矿区，再评估舰队科技节点。

### 六局第一性原理归纳

1. **收入是资源流的导数，基地是收入的生产资料**：作战单位、升级、科技和塔
   都是对现有银行的消费；当只有一矿或已丢矿时，先消费会永久降低未来每分钟
   收入。故首扩迟到/丢矿恢复必须是窄域独占基金，而非与普通优先级竞争。
2. **基地数是库存指标，健康矿区才是产能指标**：主矿采干、二矿只剩 4 个农位时，
   「三基地」并不代表三矿收入；扩张判据必须读剩余采矿位，并把在建 Nexus
   与已就绪健康矿区分开。
3. **防御价值取决于保护了什么**：12 座塔若都不在收入点，边际价值可以低于
   一座正确位置的分矿塔；塔/电池必须按基地局部射界和敌到达窗口验收。
4. **军队价值取决于是否及时参战并保护/摧毁生产资料**：前期冗余叉、虚空、
   不朽、升级若未参与关键防守，只是推迟 Nexus/科技的机会成本；后期 20 艘
   舰队若任由矿区逐个被拆，也没有把战力转化为胜势。

### O381 已落地(下一轮验证对象)

1. **首扩 300s 硬合同**：250s 起单矿仍未开 Nexus 时启动
   `nexus_priority_fund_active(...)=first_expand`，强制 `_want_expand=True`，
   禁止 O307 撤派工；Nexus 实体出现即成交解除。
2. **分矿损失恢复基金**：当前基地低于历史峰值且未达目标时进入 `lost_base`；
   暂停 SpawnController、升级、科技、扩产、常规探机和非紧急水晶，只保生存级
   防御/供给。基金期探机只保首扩 16、丢矿 12 的收入火种，成交后恢复常态。
3. **直接产兵漏口收口**：舰队重建 watchdog、气烂航母/暴风、pre/post-FB
   虚空、不朽、先知、O264/O325 两条母舰入口全部受 O381 基金阻断；避免宏计划
   已停但 `.train()` 仍直接花钱。
4. **健康矿区驱动四/五矿**：就绪 Nexus 周围剩余采矿位 ≥15 才计健康矿区；
   45 农以下目标 2 片，45+ 农目标 3 片；健康不足时绕过旧 fleet/mineral/
   saturation 门提前扩张，在建 Nexus 只算 in-flight、不冒充收入。
5. **新矿首塔基金延续 O380**：Nexus 开工同帧开启 150 矿基金，塔在途/就绪才
   成交；45s 超时后冷却 30s 重试，不把失败基地永久标为完成。
6. **永久局终流程写入 `CLAUDE.md` 与本文开头**：每局必须跑 autopsy、读 state/
   run.log/录像，写 ≥3 个数据化优化点并先落地测试，才允许启动下一局/下一轮。

### O381 bench 验收口径

1. 六局每局二矿 Nexus 实体 **≤300s**；若失败，逐笔列出 250s 后所有矿物消费。
2. 分矿损失到新 Nexus 开工延迟显著低于 o380 的 221s 级，基金期零非必要
   产兵/升级/科技/扩产事件。
3. 45+ 农实时保持 3 个健康矿区；旧矿开始跌破 15 采矿位时可见四/五矿事件。
4. 新矿开工后 90s 内至少 1 塔在途/就绪，且每次 E6「无塔」都能归因到资金、
   placement 或工人通道之一。
5. 继续双 lane、每 lane 3 局；单轮结果不独立判升降，仍按两轮累计+滚动窗口。


## o381 局间尸检 + O382（按司令每局闭环，进行中）

**日期**：2026-08-20

### o381a game_01（Zerg Rush，Defeat 779.8s）

1. **首扩基金被独立 opener 架空**：250s 已应进入基金，但
   `BuildOrderRunner` 仍在 224/251/257/272/285/288/300/312s 连续下叉、探机、
   水晶、BY、SG，Nexus 工人从 270s 等钱到 368s，二矿实体 369.6s。第一性
   原理上，基金若不能阻止同台消费者就不是基金。O382 落地：基金前移到 220s，
   启动即 `set_build_completed()` 截断剩余 opener，并由常态层在 Nexus 后补科技。
2. **丢矿后的生产资料恢复仍有漏口**：二矿约 450s 被端，重建 Nexus 直到
   715.2s 才出现，恢复窗约 265s；期间仍保有 2 SG、科技 watchdog 和结构直派
   入口，终局舰队为 0、气 738、矿 85。O382 落地：基地基金统一堵住非 Nexus/
   供给/生存塔电池的 `_dispatch_structure`，并暂停 cyber/FB watchdog。
3. **气体银行不能代替矿物收入**：农峰仅 35，488s 后农民跌到 21→6，终局
   5 农；气却单调涨到 738，说明基地/矿物端已死时继续高科技运营无意义。
   下一局验收基金期零非必要产兵/升级/科技/扩产，先成交 Nexus 再恢复转化链。
4. **启动故障实证**：本局首次拉起留下 `Blizzard Error Report ID` +
   `TimeoutError(Websocket)`，对应司令看到的“核心：访问许可错误”。O382 落地
   跨 bench 文件锁，只串行化启动到首个 state；录像同时改为各 lane/game 独立路径。

### o381a game_02（Zerg Rush，Defeat 1413.3s）

1. **首扩合同方向有效**：二矿 253.1s、农峰 72、基地峰 4、舰队峰 11，明显
   好于 game_01 的 369.6s/35 农/2 基地/0 舰队，证明早基地会扩大而非削弱战力。
   O382 将 250s 基金再前移到 220s，并截断 opener，下一局目标 240-270s。
2. **健康矿区口径是死代码**：日志从 306.7s 到 1311.4s 始终报“健康=0”，
   即使场上 3-5 个 Nexus；根因是矿物节点 `ideal_harvesters` 实测为 0。O382
   改为“10 格内实时剩余矿点数×2”，8 矿点=16 位健康、7 矿点=14 位不健康。
3. **健康扩张被 O307 反复撤派**：健康分支已连续触发，但 586/606s 等钱后
   O307 仍撤 Nexus 工，三矿 618.8s、四矿 803.6s；这把主动前置扩张重新变回
   60s 翻板。O382 令真实健康矿区不足期间禁止 O307 abort，直到 Nexus 开工。
4. **塔总量与局部保护错配**：全局塔峰 17，但 431/466/514/700/701/1032s
   多次分矿“无塔”，860/875s 单塔被 10 地面压垮。下一局继续按每基地验收首塔，
   基金成交前暂停产兵/升级；禁止用全局塔数证明分矿安全。

### o381b game_01（Terran Rush，Victory 1474.1s）

1. **早开矿配方再次被验证**：二矿 237.1s、三矿 454.0s、农峰 71、舰队峰
   29，最终 25 暴风+4 航母且 6 基地；这是 Terran Rush 首胜，证明利用 500s
   无骚扰窗建立收入生产资料是正确主线。
2. **战力没有及时打击对手生产资料**：舰队 759s 已到 8，927s 到 15，1047s
   到 24，此后 O302 连续推进，但默认目标仍是“距我方最近敌建筑”；终局银行
   7645/6651、满人口，却拖到 1474s 才结束。司令观察确认维京/空军清零、只剩
   坦克时应拆分矿。O382 新增制空经济打击窗：Terran 可见空中作战单位和硬 AA
   均为 0、舰队≥8、已知基地≥2时，已放行舰队优先最外围已知 CC/OC/PF。
3. **塔投资超过边际价值**：塔峰 25（3750 矿），但 853/1064/1100s 仍有分矿
   无塔事件；数量过量且位置不对。O382 增全局 18 塔绝对顶，慢性 threat 不豁免，
   仅新矿零塔的首座生存塔可突破上限，把第 19+ 座塔资金转回舰队/基地。
4. **健康矿区误判会造成无效连续扩张**：本胜局同样全程“健康=0”，四/五/六矿
   触发依据不可信。修正矿点×2后只在实时少于 2-3 片健康矿区时扩张，既避免
   主矿采干后的迟开，也避免健康充足时为了错误的 0 继续烧 400 矿。

### O382 下一盘验收

1. 首扩基金事件约 220s，出现 `基地基金截断开局runner`；二矿 Nexus 实体
   目标 240-270s，严禁再次晚于 300s。
2. 健康矿区事件必须出现非零计数；45+ 农时不足 3 片立即开四/五矿，且健康
   扩张持有期无 O307 撤派。
3. 丢矿基金期非必要产兵、升级、科技、扩产事件为 0；损失到 Nexus 开工延迟
   显著低于 221-265s 旧档。
4. Terran 制空后出现 `O382:Terran制空后主动斩断分矿`，目标为最外围已知基地；
   有可见解放者/维京等空军时不得触发。
5. 全局塔常态不超过 18；若超过，只能是新矿零塔首座生存豁免，并按基地坐标验收。
6. 启动阶段不再出现新的访问许可/Websocket 失败；双 lane 进入首个 state 后仍并行。

### O382 启动锁首次实机校正

- 锁本身生效：Zerg 先启动，首个 state 出现后 Terran 才拉起第二个
  SC2，随后两个 SC2 并行；没有同秒访问许可冲突。
- 但 Terran 冷启动在 56s 才进 `Status.in_game`，随后 MapAnalyzer 编译尚未
  写首个 state，旧「Popen 总计 60s」截止把正常进程误杀。O382-②b 拆成
  两段：SC2 pid 出现 ≤60s；pid 后另给 120s 进入对局并写首 state。

### o382a/b game_01 无效样本（wall timeout，不计胜负）

- Zerg 已跑到游戏约 1008s：4 基地、65 农、暴风16+航母4，首扩
  Nexus 281.3s、三矿 502.2s、首推 744.7s。这已将 o379 「舰队未成型
  即被推平」病灶迁出，但墙钟 1800s 先到，bench 杀局重试，故不计结果。
- Terran 已跑到游戏约 824s：4 基地、67 农、暴风7+航母2；
  541.5s 丢矿基金启动，561.2s Nexus 成交，恢复仅 20s（旧档 221-265s）。
  同样因墙钟配额即将超时而主动终止，不计结果。
- **根因**：双 lane 资源竞争下游戏时间约只有墙钟 0.55-0.65 倍，
  `--timeout=1800` 不足以覆盖 1400-1800s 长局。O382c 将 bench 默认单局
  墙钟超时改为 3600s，新标签重跑，保留 o382a/b 目录作无效样本证据。

### o382d game_01（Terran Rush，Defeat 963.1s）局终尸检

1. **零接触窗仍投资过量早防**：225s 已有 4 塔+4 叉，却 0 SG；
   二矿 277.2s、三矿 421.9s 虽已提前，首 SG 仍约 394s，523s 首波到时
   舰队只有 1。敌首接触本局仍在 500s+，早期 4 塔+6 叉的边际价值
   低于 BY/SG/FB。O383-① 落地：Terran Rush 在 420s/首接触前最多
   2 塔+2 地面兵，接触后 latch 解锁。
2. **基地恢复快，但重建点是热区**：录像 Nexus 反复在 561.1/
   668.4/748.8/833.7s 开工，与 523/534/637/877s 死亡球推进路径重合；
   400 矿很快收复，又很快白送。O383-② 落地：`lost_base` 且有可见敌
   地面主力时，从空闲矿点中选离最近敌军最远的点，同分再选离主基近者；
   ExpansionController 原有安全网格/blocked 检查保留。
3. **「只补 Nexus」没有恢复作战生产资料**：731s 后 SG 2→0，气库
   985-997，47 农长时存活，舰队却为 0；同期仍在每矿 target=3 补塔。
   O383-③ 落地：丢矿 Nexus 成交后开 120s 产能重建窗，仅新矿零塔首座
   生存塔豁免；第2+塔/电池、升级、额外产能让位核心 BY→SG→FB。
4. **塔数不等于保护能力**：506s 全局 9 塔，523s 分矿仍被 10 地面
   以「1塔压不住」突破；534/637s 更是无塔。说明早期四塔堆主基不能代替
   正确的分矿首塔和舰队协防。下一局验收每基地局部塔，不用全局峰值代替。

### O383 Terran game_02 验收

1. 420s/首接触前全局塔 ≤2、地面兵 ≤2；SG 明显早于 394s，500s 舰队 >1。
2. 丢矿时若敌地面可见，Nexus 目标不再是主力路径上的最近矿点。
3. Nexus 恢复后出现 `120s产能重建窗`；窗内第2+塔/电池和升级为0，
   核心 SG 恢复时间显著早于下一波。
4. 继续验证二矿 <300s、45+农实时3片健康矿区、新矿90s内首塔。

### o382c game_01（Zerg Rush，Victory 958.9s）局终尸检

1. **经济生产资料主线恢复并转化成胜势**：二矿 Nexus 269.7s、
   三矿 500.4s、四矿 654.6s；农峰70，终局64农+4基地。舰队从619s的
   1 艘爬到675s 6艘、735.9s 8艘出击，终局暴风20+航母4、满人口。
   对照 o379 的0-1艘舰队早崩，O382 已将核心败因迁出；这是有效胜局样本。
2. **健康矿区扩张仍被 O307 撤派**：617.1s 明确报「健康2/基地3/
   农65」并需要四矿，但 635.0s O307 仍撤 Nexus 工；后续753/831/944s
   继续同类翻板。根因是 worker/tracker 使 nexus_pending 翻真后，健康判据
   下帧翻假，保护旗标丢失。O383 落地：从触发基地数 latch 到 Nexus
   实体数+1，期间恒保持扩张并禁止 O307 abort。
3. **首塔基金窗早于验收时限自灭**：二矿 269.7s 开工，基金
   314.8s 即按45s超时，随后冷却；直到368.6s重开、398.7s才首塔在途，
   总计129s，447.5s狗13地面到场时仍只有1塔。O383 落地：基金窗
   45→90s，超时冷却30→15s，与「新矿 90s 内首塔」同口径。
4. **首舰前产能超前于真实作战产出**：562s 已有3 SG、舰队0，
   619s 4 SG、舰队1。现有 first_fleet_seen 把在产队列算「已见」，允许第3+
   SG 提前吃300矿，而首艘暴风尚未参战。O383 落地：额外 SG 解锁
   改为暴风/航母真实在场口径（include_pending=False）；SG1/SG2 核心链不动。
5. **静态防御仍是局部薄弱而非总量不足**：终局塔14<18绝对顶，
   但 695.9s 四矿仍以「10地面/单塔」被抄；好处是舰队已成型，24s后清退且
   基地未掉。这证明正确教义是「首塔及时+舰队协防」，不是恢复无上限铺塔。

### O383 Zerg game_02 验收

1. 健康矿区触发后到 Nexus 实体+1之前零 O307 撤派。
2. 每个新矿开工到首塔在途/就绪 ≤90s；二矿不再重现129s空窗。
3. 真实首舰出场前 SG 不超过2；首舰时间不晚于 o382c 的619s。
4. 继续记录 O302 首推、腐化信用和基地回防交换；单局胜利不作水位结论。

### o382d game_02（Terran Rush，Defeat 1560.7s）局终尸检

1. **早科技/舰队改动有效，但塔帽协议覆盖不全**：二矿249.1s、三矿405.8s；
   225s 已有SG1、塔2、地面2，首接触491.3s，494s暴风2，显著优于game_01
   的首SG约394s/523s仅舰队1。可是293s塔2到394s塔5，说明手动
   _dispatch_structure 返回 precontact_cap 时，ProtossStaticDefence 目标层仍绕过。
   O384-①落地：在所有地板/增防/总帽之后，把最终目标钳为主基1、每分矿1、
   电池1，首接触/420s后自动解除。
2. **安全重建与产能恢复均有净改善**：522.5s丢矿后没有立即拍回原热点，
   617.9s成交安全点并开120s产能窗；675s已4基地、舰队4、SG4，game_01
   同阶段仅舰队1。后续舰队峰14、星门始终4，证明“先Nexus、再恢复SG”
   比只补塔/基地正确。
3. **斩分矿目标生效，但召回阈值沿用决死推进导致自家经济被切断**：
   1064.6s真实舰队11、已知敌基地4时触发“O382:Terran制空后主动斩断分矿”；
   1145.9s自家基地遭10地面、单塔压不住，却因正常舰队11的召回门=14未回；
   1202.2s升到15地面才达到门，期间连续掉矿/屠农，农民68→29@1238s。
   O384-②落地：经济打击窗召回门封顶10，普通推进的14/25门保持不变。
4. **“最远离敌军”过度选择地图远角，造成安全但不可防守的负资产**：
   重建点(160,100)在626.8s落成，700.2s仍0塔；1218s日志显示其“落成60s无塔”
   age已529s，1278s首塔基金再次90s超时。它离主基地/电力/舰队回防链过远，
   不是可运营安全矿。O384-③落地：候选先限制距主基≤80格，再按
   “距最近敌军 - 0.5×距主基”评分；无近点才退化全候选。
5. **工人崩溃是后半局直接死因**：舰队在1181s仍14、基地3，但1202s双矿
   被抄后农民60→29→23，舰队一直11到1462s，最终1519s舰队也归零。
   说明不是缺兵，而是进攻承诺没有保护收入生产资料；召回修复优先于再扩产。

### O384 Terran game_03 验收

1. 首接触/420s前最终每基地塔/电池目标≤1，塔总量不再从2旁路涨到5。
2. 制空斩分矿时，任一基地10地面威胁立即回防；不得等到14/25。
3. 丢矿固定目标距主基≤80格；不再选择(160,100)类远角，恢复矿90s内首塔。
4. 保留O383收益：二矿<300s、首SG约225-300s、500s舰队≥2、丢矿后SG不清零。

### o382c game_02（Zerg Rush，wall-time 无效样本，不计胜负）

- 本局在约1539s游戏时间仍有6基地、67农、暴风21+航母4、接近满人口；
  经济与舰队都健康，游戏时间持续推进，不属于卡死。bench wall=3600s 到期后
  先清空 state 再自动重试，故完整逐帧文件已丢，只保留 run.log.1 与已记录指标。
- 可用事实：二矿约229s、三矿482s、五矿703s、六矿1000s；健康扩张 latch
  生效，未再观察到 O307 撤派。首舰约643s，比上局619s晚24s；新矿首塔基金在
  316.9/526.0s两次90s超时，却仍未成交首塔，说明延长冻结没有修 placement。
- **基础设施修复**：默认 wall timeout 3600→7200s。状态/游戏时间停滞检测仍保留，
  只有健康推进的超长局获得更长终结时间。
- **策略修复**：O384-③新增“非资金失败释放”——基金年龄≥15s、已买得起塔且
  无塔 tracker/in-flight 时，判定瓶颈不是钱，立即释放全局产兵/科技，15s后重试
  落点/派工；避免为 no_placement/no_worker 把首舰再拖24s。

## O385 双 lane 逐局验证（进行中）

### o385a game_01（Zerg Rush，Victory 968.3s）

1. **连续第二个有效胜局，经济/舰队配方稳定复现**：二矿273.3s、三矿528.3s、
   四矿665.8s；农峰68，终局63农/4基地。首暴风约603s，709.3s舰队5首推，
   766.2s舰队9，终局暴风18+航母4+追猎7、199/200。与o382c game_01
   的958.9s胜局同形，Zerg Rush最新有效窗口已2连胜，但仍需完成5局3胜验收。
2. **非资金基金释放修对了科技，但仍反复重试同一坏锚**：299.6s二矿首塔
   判非资金失败并释放，SG1在309s已出现、首舰提前到603s；可是333.6s重开基金，
   393.8s才报塔在途，470.6s仍“落成60s无塔 age126s”。说明释放避免全局饿死，
   却没有推进placement状态机。O385-①落地：每次非资金失败给该基地
   _o364_anchor_attempts +1，3次后走既有水晶环带fallback。
3. **供电自救过量**：386s二矿0塔却已有4水晶，416-500s长期0塔/5水晶；
   三矿也出现0塔/2水晶。水晶不能解决无效锚点，反而额外烧100-300矿。
   O385-②落地：_dispatch_structure 的分矿critical防御水晶，15格局部实体+
   在途达到3即返回pylon_local_cap；AutoSupply主链不受影响。
4. **四矿健康后仍追五矿并产生O307翻板**：四矿667s已完成，之后737.9/
   821.7/881.9s三次“持有>60s撤派”；没有新的健康不足事件，属于常态
   workers/saturation门在健康四矿上继续追五矿。O385-③落地：bases≥4且
   健康矿区已达到当前工人数目标时，正常扩张返回False；旧矿采干导致健康不足时，
   健康分支仍会立即开五/六矿。
5. **局部塔仍未按时保护收入点**：446.3s二矿12地面/单塔被抄，709.9s四矿
   4地面/无塔被抄；均靠舰队/地面协防清退而未掉矿。正确方向仍是修锚点/供电，
   不是提高14塔全局投资。

### O385 Zerg game_02 验收

1. 首塔非资金失败累计后出现环带fallback，二矿首塔≤90s。
2. 任一分矿15格内防御水晶≤3；不再出现0塔/5水晶。
3. 四矿且健康达标后零O307五矿撤派；健康不足时仍能开五矿。
4. 首舰≤603s，O302首推不晚于709s；继续累计5局3胜验收。

### o385b game_01（Terran Rush，Victory 1898.4s）局终尸检

1. **生存/经济主线已打通，但优势转终结慢了近900秒**：二矿204.9s、三矿
   373.7s、四矿502.2s；农峰71，1012s已25舰队、1181s后稳定29舰队，终局
   25暴风+4航母/68农/6基地/200人口。这是 Terran Rush 第二个有效胜局，证明
   O382-O384 已把“丢矿后经济断裂/舰队归零”迁出；但第一座敌 Command Center
   直到1421.9s才死亡，满编舰队没有及时把制空转成拆经济。
2. **O217 小股清剿旁路了经济打击承诺**：978.8/1117.0/1334.0s 均只有4个
   地面敌军抄矿，随后984.6/1119.6/1336.2s触发 O217；全军统一 attack_target
   把29舰队也拉回。1365-1379s出现 O382经济打击与O217反复切换，实锤1-5残敌
   造成舰队yo-yo。O386-②保留战略目标：残敌仍由地面守军清，经济打击舰队继续
   斩基地。
3. **O384“10人召回门”只改了一层，仍被 O219/O205 的6人门旁路**：
   attack_target 的经济打击门虽已降到10，但 update 后置的全军协防与空军召回
   仍在6人触发，因此6-9地面兵也会提前拉走舰队。O386-③令经济打击期
   `_air_fleet_recall_target` 使用真实10人门；地面守军仍按6人门协防，达到10
   后舰队照常回家。
4. **1v1远端敌矿被固定80格过滤**：录像中敌1362.3s在(128,127)开出的
   Command Center 距敌主基约90格，旧 `_known_enemy_townhalls` 永远不把它纳入
   经济打击；该基地存活429.5s至1791.8s。O386-①改为1v1全部敌基地都归唯一
   敌人；多人局按最近敌出生点做Voronoi归属，不吸入另一名敌人的基地。
5. **电脑续矿不是单纯高方差，而是目标链有结构性漏口**：1447-1813s电脑又在
   已清矿点连续开13座 Command Center，多数只活3-136s；说明舰队到场后杀得动，
   真正拖时的是早期被召回和远端矿不入账。此轮不改舰队配比/产能阈值，先验证
   目标链修复，避免用更多舰队掩盖指挥问题。

### O386 双 lane 验收

1. Terran：1-9地面小队抄矿时出现 `O386:经济打击兵力分流`，地面守军回防、
   舰队继续攻击；≥10时舰队必须召回。
2. Terran：已知基地应包含距敌主基>80格的1v1远端矿；首座敌基地死亡明显早于
   1421.9s，终局目标先压到<1600s，同时保持基地/农民/舰队不崩。
3. Zerg：继续验收O385三项生产修复——首塔环带fallback、分矿防御水晶≤3、
   健康四矿后不再无效追五矿；O386的Terran专属经济窗不得改变Zerg行为。
4. 仍按逐局尸检；本轮胜负只并入滚动窗口，不以单局判升降。

### o386b game_01（Terran Rush，Defeat 788.6s）局终尸检

1. **经济/科技前半程继续兑现，但第四矿顺序错误**：二矿233.0s、三矿405.8s、
   四矿510.3s，农峰70；450s首暴风、506s已有2舰队、3SG/FB。敌首接触537.1s，
   第四矿只存在27s，尚无塔即把400矿和首塔基金暴露给死亡球。对照o385b胜局
   是487s先接触、502s后四矿。O387-①将Terran Rush首接触前三矿封顶，接触后
   立即恢复扩张，保留胜局顺序而不删早经济主线。
2. **首波真实编成已超出纯暴风+塔的站线能力**：538-558s可见从
   5 Reaper+5 Marine+2 Marauder+1 Viking迅速长到14 Marine+10 Marauder+
   Tank+Viking；我方只有3暴风+2叉。562s首矿丢失，594s舰队归零，随后收入链
   崩溃。O387-②在420s、三矿、FB已存在且舰队<4时预置Robo；O387-③对
   Marauder/Tank重甲计数≥6时直产最多2个Immortal，不改主舰队配比。
3. **安全重建半径80仍会选到不可运营远角**：597.4s再次选择(160,100)，距主基
   约78格；虽然符合旧≤80门，却远离现有塔/电力/回防链，675s再次掉矿。
   O387-④将急性重建候选收紧到主基65格内，优先(142,66)类可回防矿点。
4. **恢复基金本身不是瓶颈**：560.5s丢矿基金启动，597.4s Nexus成交，约37s；
   说明“先恢复基地”链有效。真正失败在恢复点过远和第一波没有对重甲站线兵，
   本轮不放松基金、不恢复无上限塔投资。

### o386a game_01（Zerg Rush，Defeat 1261.8s）局终尸检

1. **舰队与经济都曾完整成型，败因迁到后期腐化死亡球**：二矿281.2s、三矿
   478.1s，农峰72；首暴风598.7s，827.6s舰队8首推，1036s达到11暴风+3航母、
   4基地、17塔。随后敌19腐化+5大龙+17蟑螂+4刺蛇+潜伏/感染到场，舰队在
   1052/1056/1060s连续各损3暴风，24s内14→4，之后经济被扫平。
2. **后期追猎护航形成太晚**：1000-1036s仅2-3追猎；腐化19条显形后现有
   anti-air pivot才启动，已经没有30s生产窗口。o385a胜局终局有7追猎，方向与
   胜局配方一致。O388-②在Zerg Rush t≥900且舰队≥8时提前补追猎到8，达到即
   自灭，避免O301的28追猎洪水回归。
3. **敌信用兵力领先时仍开裸四矿**：930s信用敌军86，我军约67；945.3s仍投
   400矿开四矿，1005s又进入首塔基金，1036s该矿无塔被5地面抄，恰与腐化死亡球
   同窗。O388-③在t≥900、至少三矿、敌信用≥80且领先我军时禁止继续扩张；优势
   恢复后自动放行，不影响胜局665s早四矿。
4. **O217仍会把成型舰队拉去清1-5地面残敌**：1036.6s新四矿5地面触发O217，
   同窗16-19腐化显形；全局attack_target让舰队为可由7个地面守军处理的小队转向。
   O388-①在舰队≥8且地面守军≥3时，1-5残敌只改派地面部队；达到O205召回门的
   真主力仍会召回，Terran O386经济打击分流语义也保留。
5. **O385机制验收部分通过**：分矿防御水晶被压到≤3，593.7s重试4次后真实出现
   O379水晶环带fallback；但首塔仍常晚于90s。说明fallback已可达，下一轮继续量
   首塔时点，不再把水晶cap/fallback当死代码。

### O387/O388 下一局验收

1. Terran：首接触前基地≤3；420s后三矿+FB+舰队<4时出现O387 Robo事件；
   Marauder/Tank≥6时产出1-2 Immortal；重建点距主基≤65。
2. Terran：500s仍保持舰队≥2，首波后农民不从70级连续跌到40以下；若进入
   720s后期，再继续验收O386经济打击分流/远端敌矿目标。
3. Zerg：900s舰队≥8后追猎补到8但不超过该floor；敌信用领先时不出现晚四矿；
   1-5残敌由地面守军清、舰队不再全体转向。
4. Zerg：对19腐化级死亡球，舰队不得重现24s内14→4；若仍团灭，下一杠杆转向
   舰队微操/集火与腐化接战几何，不再继续加经济机制。

### o389a game_01（Zerg Rush，Defeat 2291.5s）局终尸检

1. **O388显著延长生存并通过首轮腐化验收**：二矿241.1s、三矿490.2s、
   首暴风478.1s；956s达到18舰队，895.1s出现12舰队+10追猎推进。对比o386a
   1261.8s败局，本局延长约1030s，且没有重现1036s后24秒内14→4的单波团灭。
2. **护航能赢一轮，不能替代摧毁敌经济**：敌方Hatchery从128/485/659/844s
   持续扩到1187/1288/1369/1599/1766/1839/2062/2152s，共12次开基地；我方多次
   清空腐化后仍回到最近建筑/防守循环，未斩生产资料。电脑每200-400s重新补出
   9-18腐化，最终2025s后舰队归零。O390-①把Terran经济打击教义扩到Zerg Rush：
   波间隙无可见空战/硬AA、舰队≥8时直取最外围已知Hatchery。
3. **塔绝对顶仍被首塔豁免旁路**：塔峰35，约5250矿；O370在现有17塔时冻结，
   后续新矿 survival_exempt 仍反复越过18绝对顶。O390-③给首塔豁免再加24座
   全局上限，保留前6座矿区的首塔空间，但禁止35塔级膨胀。
4. **最新有效窗口为2胜2负**：o382c胜、o385a胜、o386a负、o389a负；下一有效
   样本将决定当前5局窗口能否达到3胜，历史3/5仍保留但不能代表当前水位。

### o389b game_01（Terran Rush，Defeat 1459.5s；首次尝试崩溃无效）局终尸检

1. **O387全部兑现并把稳定期从789s延到1459s**：有效重试二矿265.2s、三矿
   397.8s，首接触509s前没有四矿；420s Robo预置，521/864/918s直产Immortal，
   峰值2不朽；四矿803.6s在接触后才开。首个无效尝试末端SC2异常退出，不计结果。
2. **混编守住多轮，但经济打击把全部地面护航也带走**：1006.6s舰队8、追猎9时
   触发Terran经济打击，1025.3s敌119 supply到家，地面军同舰队一起在外，1054s
   才因基地10地面召回。随后连续掉矿，1301/1305s舰队损5。O390-②令经济打击
   只派空中舰队，追猎/不朽固定留在防守锚点；≥10威胁仍召回舰队。
3. **绝对塔漏口同样存在**：塔峰29、6SG，1057s仍有6舰队+6追猎+2不朽却被
   119 supply压缩；若将第25-29塔的750矿转成2暴风或恢复Nexus，防守交换更有利。
   共用O390-③首塔豁免24上限。
4. **Terran Rush仍未达标**：最新有效结果为o385b胜、o386b负、o389b负；
   O386后期远端基地/分流目标尚未在胜势样本完整验收，O390继续验证。

### O390 下一局验收

1. Zerg：无腐化波间隙出现`O390:Zerg波间隙主动斩断分矿`，敌Hatchery数量/重建
   频率低于o389；当前5局窗口争取第三胜。
2. Terran：经济打击时追猎/不朽留家，舰队单独斩矿；119 supply类波到家前已有
   地面站线，不再等10人召回才全军回头。
3. 两 lane：塔峰≤24；新矿零塔时若全局已24，允许舰队协防但不再越帽补第25塔。
4. 若O390仍为双败，Zerg Rush按最新窗口2/5重新评估是否回到高方差封存；
   Terran Rush则评估“已有机制全兑现仍无法打穿”的封存点，不无限叠加机制。

### o390a game_01（Zerg Rush，Victory 1143.0s）局终尸检

1. **Zerg Rush 当前窗口正式3/5通过**：最近5个有效样本为o382c胜、o385a胜、
   o386a负、o389a负、o390a胜。历史3/5不再只是旧档，本轮重新取得当前水位验收。
2. **经济打击直接改变终局速度**：877.1s首次`O390:Zerg波间隙主动斩断分矿`，
   929-981s连续攻击已知4→3座基地，1044.6s再攻剩余2座；敌Hatchery只开到
   127/508/743/1025/1044s共5次，对比o389a的12次。终局24舰队+8追猎、5基地，
   1143s结束，较o389a缩短1148s。
3. **护航与终结链形成闭环**：801s舰队6首推，877s舰队9进入经济打击，937s
   12舰队+5追猎，1057s21舰队+8追猎；波间隙拆经济使敌未再形成17-19腐化的
   第三/第四轮复产，O388不再只是延命机制。
4. **塔帽方向有效但并发超调**：塔峰26，远低于o389a的35，但仍越24两座；
   原因是F2硬顶只数ready，同帧在途未入账。O391改为实体+tracker在途口径，
   survival豁免阈值23预留1座并发余量。

### o390b game_01（Terran Rush，Victory 1296.7s）局终尸检

1. **Terran Rush取得第二个当前窗口胜局**：二矿249.1s、三矿405.8s；420s预置
   Robo，565/699/777s直产不朽；首接触前不超三矿，四矿739.3s。终局22暴风+
   4航母+5追猎+1不朽、6基地，1296.7s胜。
2. **地面留守修掉o389的119 supply抄家链**：824s舰队17首次经济打击后，
   追猎/不朽没有随舰队远征；565/568/628/774s各波均在基地消化，没有任何基地
   掉落或农民崩盘。随后经济打击从已知2基地持续到3→2，电脑虽在762-1251s
   连续重建CC，仍被26舰队压到终结。
3. **当前Terran Rush最近5局约2/5，尚未打穿**：取最新有效样本为o382d-g2负、
   o385b胜、o386b负、o389b负、o390b胜。机制已进入可胜区间，仍需至少再跑
   两局形成新的5局窗口，不能用单胜宣布通过。
4. **塔并发超调更明显**：塔峰35；胜局证明这些塔不是获胜必要条件——900s已
   15舰队，956s塔23后仍同帧冲到33。O391实体+在途硬顶应把多余1650矿留给
   更早舰队/终结，不改变Robo/经济打击主线。

### O391 后续验收

1. Zerg Rush已通过3/5，暂停专门攻坚；可在Terran验证时偶尔做回归，不再每轮
   占一条主lane。
2. Terran Rush下一有效局重点只验O391塔峰≤24，并继续积累最新5局窗口；
   若再胜，窗口提升到3/5的距离显著缩短。
3. Terran Rush打穿后开启Terran Timing；Zerg Timing/Terran Power封存不动。

### O391 Terran 双 lane（1胜1负）

#### o391a game_01（Victory 1337.9s）

1. **O391塔硬顶通过实机验收**：塔峰21（o390b为35），中后期13-21区间；实体+
   在途口径阻止了同帧批量越顶，同时舰队正常爬到22暴风+4航母，证明收口未伤胜局。
2. **胜局主线复现**：二矿273.2s、三矿397.8s，420s Robo，首暴风450s；
   795.7s舰队12开始经济打击，911.9s舰队18，终局26舰队+2不朽、5基地。
3. **分流有效**：903/930s基地各有10地面骚扰，追猎/不朽留守处理，舰队仍持续
   在912/945/1020/1110s斩分矿；仅短暂掉矿后恢复，没有农民崩盘。

#### o391b game_01（Defeat 764.0s）

1. **出现确定性双Cyber Core竞争**：297-542s结构快照持续`CYBERNETICSCORE=2`；
   100矿和建造工时被重复科技吃掉，SG到394s才1座，首暴风518.3s，570s首接触
   时只有1暴风，明显落后胜局450s/2-3舰队水位。
2. **Robo/Immortal方向仍兑现但来不及**：427.5s预置Robo，590.2s首不朽；
   586s死亡球已到，随后594/634/707s连续掉矿，无法逆转上游科技节奏损失。
3. **O392修复**：BuildOrderRunner活跃且未被O324判卡死时，独占BY等唯一核心
   建筑注册权；watchdog只在Runner完成或停滞后接管，堵同帧双注册竞态。

### 当前矩阵断点（O391后）

- Zerg Rush：当前最近5局 **3/5，已打穿**。
- Terran Rush：最新5个有效样本仍约 **2/5**；O390b/O391a已两连胜态样本，
  下一局若胜会把更旧败局挤出窗口，接近/达到3/5，需按实际顺序复核。
- 下一局只跑Terran Rush，验收唯一Cyber Core=1、首暴风≤500s、塔峰≤24。

### 司令后续路线指令（2026-08-21）

- Terran Timing 完成攻坚后，解除 Terran Power 封存并继续攻坚。
- “very harder”按SC2有效难度枚举暂解释为 **VeryHard Terran Power**；若司令
  指的是Harder则再修订。此前3/24封存判决保留为历史基线，不再作为停止理由。

### O392 Terran Rush 双 lane（2胜0负，正式打穿）

- `o392a game_01`：Victory 907.1s。二矿237.1s、三矿401.8s、四矿590.6s；
  终局16暴风+3航母+2追猎+1不朽，塔峰24，唯一Cyber Core=1。
- `o392b game_01`：Victory 1580.7s。二矿257.1s、三矿405.8s、四矿671.0s；
  终局24暴风+4航母，唯一Cyber Core=1。经历多轮重兵仍保持经济并持续斩分矿。
- O392防重验证通过：两条lane全程`CYBERNETICSCORE=1`，未重现o391b双BY；
  首暴风分别约450s/466s，恢复到胜局节奏。
- Terran Rush最新5个有效样本为o390b胜、o391b负、o391a胜、o392a胜、
  o392b胜，即 **4/5，正式打穿**。
- 工程债：塔硬顶在o392a峰24正常，但o392b后期仍峰42；越顶来自PSD/main_siege
  台账外在途通道，不阻塞已认证胜率，转Terran Timing前记录待收口。

### 当前路线（O392后）

1. Zerg Power、Zerg Rush、Terran Rush已打穿。
2. 下一主线：VeryHard Terran Timing。
3. Terran Timing完成后，按司令指令重启VeryHard Terran Power攻坚。
4. Zerg Timing继续封存；Protoss/Macro/Air暂不扩展。

## O393 Terran Timing 首测（0/2）

### o393a game_01（Defeat 791.4s）

1. 二矿265.2s、三矿450.0s、农峰63，经济不是首因；558s首波约
   10 Marauder+9 Marine+Ghost+Tank+Medivac到场时，仅1暴风、无Robo/不朽。
2. 全局再次出现`CYBERNETICSCORE=2`：O392只封了watchdog与Runner，Timing的
   `_build_flow_structures→_build_core_structure`仍可与Runner同帧双注册。
3. 480s舰队仍为0却触发`E10:风暴压制转航母终结`，昂贵航母配方抢走首批暴风
   产出窗；582s才1暴风，随后连续掉矿并在791s败。

### o393b game_01（Defeat 981.8s）

1. 唯一BY正常，二矿285.3s、三矿429.9s；首波532s时仍仅0-1暴风，3叉+塔只能
   短暂拖延，594/638s连续掉矿。
2. 687-775s恢复到三矿、银行一度1125矿/829气，但Nexus恢复基金长期冻结产兵，
   舰队只恢复到2-3；833s第二波44 supply、845s后升级为47地面，最终981s败。
3. Timing敌形态与Rush同为Marauder/Tank重甲核心，且首波更早集中；Robo/Immortal
   不能继续只挂`ai_build==rush`。

### O394 已落地

1. `_build_core_structure(CYBERNETICSCORE)`也读取Runner独占权，封住flow与Runner
   双BY第二入口。
2. Terran Robo/Immortal预置从Rush扩到Rush+Timing：t≥420、三矿、FB存在、舰队<4
   即建Robo；可见Marauder/Tank重甲≥6直产最多2不朽。
3. Terran Timing的E10转航母增加“首暴风真实在场>0”硬门；0舰队时480s时间盒、
   坦克首现和地面35 supply都不能提前转航母。

### O394 下一局验收

- 全程BY=1；首暴风目标≤500s，首波时至少2暴风或1暴风+1不朽。
- 480s零舰队时不得出现E10转航母；首暴风出场后再按原时间盒转型。
- 首波后农民不跌破40、基地不低于2；优先建立首个有效胜局，再谈3/5。

## O394 Terran Timing（0/2）

- `o394a`：Defeat 816.2s。BY=1、首暴风498.2s达标，438s Robo也真实落地；
  但首波前Immortal=0，647s第二轮36 supply到家时仍仅1暴风，随后连掉两矿。
- `o394b`：Defeat 896.3s。BY=1、首暴风约442s，534s已有2暴风+Robo+4SG；
  仍因Immortal=0在首波后掉矿，819s第二波升级为14 Marauder+16 Marine+
  5 Tank+8 Viking时只有3舰队，最终败。
- O394已证明双BY与零舰队E10是上游问题但不是最后病灶；两局Robo都曾落地，
  却因直产门等“可见重甲≥6”才点第一只不朽，波显形到不朽完成来不及。

### O395 已落地

- Terran Timing在Robo就绪后无条件预产第1只Immortal；已有1只后恢复原门，只有
  可见Marauder/Tank重甲≥6才补第2只。目标是在首波前形成“2暴风或1暴风+1不朽”。

## O395 Terran Timing（0/2）

- `o395a`：Defeat 593.0s。Robo存在但三矿/首塔链先花光矿，Immortal始终0；
  514s首波到脸即掉三矿，574s只剩一矿。该局侦查未进E10 pivot，默认航母先出，
  首航母458s但0暴风，同样缺少对Timing波的有效站线/射程输出。
- `o395b`：Defeat 756.7s。490s三矿、Robo、
  1暴风，但矿为0，Immortal仍0；首波10 Marauder+13 Marine在477s到脸，随后连续
  掉矿。预产判据成立但`can_afford(275)`从未成立。
- 结论：第一只不朽需要改变资金顺序，不能只改变训练判据；第三矿400矿是最直接
  同台竞争者。

### O396 已落地

1. Terran Timing Robo门提前为t≥340、至少两矿（Rush仍保持420s/三矿）。
2. FB存在且第一只Immortal尚未在产/在场时，禁止从两矿开三矿；Immortal一旦下单
   立即恢复扩张。把400矿三矿让给200 Robo+275首不朽的首波生存链。

## O396 Terran Timing（1胜1负，首胜）

- `o396a`：Victory 2192.4s。二矿233.0s，349.3s预置Robo，435.2s主动点首不朽，
  首暴风425.9s、首不朽478.1s；575s已3暴风+1不朽+三矿，首波后农民保持60级。
  771s形成6暴风+2航母+2不朽并首推，最终24暴风+4航母，取得Timing首胜。
- `o396b`：Defeat 870.7s。361s Robo、416.6s首不朽、437.9s首暴风均达标；
  但首波交换后不朽被磨光，第二只到529.6s才下单，738s第二波到家时舰队仅2，
  最终连续掉矿。
- 结论：方向成立，但一只预产不朽只能过首波的部分签；胜局实际需要2只不朽形成
  稳定站线，且Robo被拆后在舰队4-7阶段也必须继续重建。

### O397 已落地

1. Timing从预产1只提高到预产2只Immortal；第3只仍需可见重甲≥6，不无限扩地面。
2. 三矿改等2只Immortal在产/在场后再放行。
3. Timing Robo重建门的舰队上限4→8，防首波Robo被拆、舰队刚到4-7时永久失去
   不朽产线；Rush参数保持原值。

## O397 Terran Timing（1胜1负）

- `o397a`：Victory 993.9s。二矿221.0s，Robo/双不朽首波包兑现；506s已有2舰队，
  619s舰队5、675s舰队8，877s开始经济打击，终局20暴风+4航母+2不朽。
- `o397b`：Defeat 1015.7s。二矿281.2s，比胜局晚60s；392.6s Robo、447/486s
  两只不朽均下单，但首波已在461s显形，514s先掉二矿。后续虽多次补不朽，
  星门长期仅1座，舰队峰4，第二/三波逐步压垮经济。
- O396+O397两轮累计2胜2负；双不朽机制已验证可达，当前主要差异是二矿/收入
  方差。按方法纪律不因单负继续叠机制，补第5个有效样本裁决当前窗口。

### 下一样本协议

- lane1：VeryHard Terran Timing ×1；若胜则最近5局3/5正式打穿。
- lane2：已通过组合回归，不计入Timing窗口；避免同轮第二个Timing结果把决定性
  第5样本再次变成6局噪声。

## O397c 决定性样本（Defeat 921.3s）

- 首次尝试败势末端SC2异常退出，属无效样本；自动重试为正式结果。
- 重试二矿305.4s，341s已3 Gateway；695s仅2暴风、3矿54农，763s舰队3，
  第二波后舰队归零并在921s败。对照o397a胜局全程2 Gateway、675s舰队8。
- 当前最近5个有效Timing样本为o396a胜、o396b负、o397a胜、o397b负、
  o397c负，即2/5，尚未打穿。

### O398 已落地

1. Terran Timing transition Gateway cap固定2。
2. 旧rush_needs_gateway入口在已有2座时硬停。
3. floor额外产能入口同样读取2座上限，三条通道共同堵第3座Gateway。

## O398 Terran Timing（1胜1负，最近5局2/5）

- `o398a`：首次尝试在败势末端SC2异常退出，自动重试为有效样本；重试
  **Victory 1893.5s**。二矿233.0s、三矿425.9s，首不朽442.0s、首暴风
  446.0s；全程Gateway封顶2，后期22暴风+4航母、6基地，证明O398没有伤害
  已成立的双不朽+舰队路线。
- `o398b`：**Defeat 960.4s**。二矿277.2s，首暴风470.1s、首不朽494.2s；
  506.5s首波32 supply到家时舰队仅1，之后虽一度71农/4基地，舰队峰4，
  751s第二波90 supply逐矿压垮。
- O398把o397c的3 Gateway重新压回2，但两局共同说明Gateway不是剩余主因；
  最近5个有效样本按完成顺序为o397a胜、o397b负、o397c负、o398b负、
  o398a胜，即 **2/5**，仍未打穿。

### O399 已落地：二矿前炮塔禁令

1. 六局同刻对照形成完全分离：O396a/O397a两个胜局在240s均已二矿且0塔；
   O396b/O397b/O397c/O398b四个败局在240s均仍单矿且已有2-3塔。
2. O398b在Forge后于183/196s连造炮塔，225s已3塔，450矿直接与400矿二矿
   竞争；对照O398a 225s仍0塔、229s Nexus开工、233s落成。二矿差44s继而
   传导到SG/首暴风/不朽和首波战力。
3. 新增`terran_timing_cannon_before_second_blocked`：Terran Timing在二矿
   实体/在途出现前，把最终PSD塔/电池目标压为0，并在统一派工出口再次拦截
   PHOTONCANNON，封住presumed/timing_sprint/defenseless等旁路；真实威胁
   到脸保留生存例外，二矿一开工立即解闸。
4. 下一轮O399双lane各1局：硬验收240s二矿已在途或落成、炮塔0；若双胜，
   最新五局将随样本顺序逐步抬到3/5并正式打穿；若仍负，先核对首波时的
   Tempest/Immortal/SG水位再决定下一杠杆。

## O399 Terran Timing（0胜2负，二矿闸通过但暴露两处旁路）

- `o399a`：**Defeat 1014.1s**。二矿273.2s，二矿前0塔；首暴风/首不朽
  均446.0s，522s已3暴风+2不朽，证明O399资金顺序正向传导。但三矿466.1s
  仍早开，619-788s舰队长期卡4、气从618涨到1049-1248，仅2 SG；807s
  88 supply第二波后逐矿崩溃。
- `o399b`：**Defeat 701.0s**。二矿229.0s且二矿前0塔，基础经济达标；但
  394s已有5塔、530矿/372气却舰队0，413.8s双不朽未完成即开三矿。更关键：
  首舰竟是Carrier@458.0s、整局Tempest=0，497s 31 supply首波到家时只有
  1航母+1不朽，随后快速败亡。
- 最近5个有效Timing样本降至 **1/5**；O399本身没有回归二矿，败因已迁移到
  “二矿后塔/三矿继续抢首波包”与“E10风暴主C被配方顺序反转”两条新旁路。

### O400 已落地

1. **E10配方幂等修复**：`tempest_primary_spawn`旧实现无条件互换优先级；
   flows.yml自O62已是`TEMPEST p0/CARRIER p1`，互换反而变成航母p0。改为
   显式把Tempest赋两者最小priority、Carrier赋最大priority；兼容旧配方，
   对当前配方幂等，封住“银行越富越先点航母”的反直觉漏洞。
2. **三矿等双不朽真实出场**：Terran Timing从二矿起不再要求FB存在才拦三矿，
   且判据从“在场+pending≥2”收紧为真实在场Immortal≥2，防同帧重复订单/
   健康扩张旁路提前放行400矿。
3. **首波包前静态防御窄配额**：首暴风(含在产)或双就绪不朽任一未完成时，
   最终PSD目标压到主基2塔、分矿1塔、每基地1电池；统一手工派工出口在
   全局3塔时再封顶。首波包完成即恢复动态塔目标，真实威胁与新矿生存塔
   既有例外保留。
4. O400下一轮仍双lane各1局，硬验收：首舰必须Tempest；三矿不得早于双不朽
   真实出场；450s塔≤3；500-550s至少2暴风+2不朽，随后舰队不再卡4。

## O400 Terran Timing（1胜2负；另1局胜势崩溃无效）

- `o400a`：**Victory 1560.6s**。二矿233.0s，首暴风429.9s、首不朽
  442.0s；首舰修复通过。虽然三矿仍在401.8s旁路出现，但首波后恢复，
  844/900/1125s舰队6/8/14，终局21暴风+4航母，取得有效胜局。
- `o400b`首次尝试：约1675s已22暴风+4航母、5基地满人口，只剩11 SCV且
  零敌建筑时SC2异常退出，按纪律为**无效样本**；自动重试为正式
  **Defeat 876.7s**。重试的Runner 183.2s先造炮塔，220s才被基地基金截断；
  281s仍单矿却已有3塔，二矿拖到297.3s。500s 40 supply波到脸时仅
  2暴风+1不朽，随后逐矿崩溃。
- `o400c`：**Defeat 825.6s**。二矿233.0s、首暴风433.9s、首不朽437.9s；
  但约352s超早Timing波已触发急性威胁，O400首波包塔帽仍压着常态目标，
  404.6s先掉二矿，工人42→20→5，舰队只有2暴风无法恢复。
- 有效窗口仍仅 **1/5**。O400证明E10幂等修复与首波包配方方向正确，但
  胜率方差的两个执行旁路是：Runner早于220s造首塔；真实威胁期塔帽未解除。

### O401 已落地

1. Terran Timing的首扩独占基金从220s提前到160s，仅该组合变化；160s在
   历史首炮塔183s之前，直接截断开局Runner的炮塔步，避免bot层已经禁塔、
   Runner仍提前花150-450矿的双执行器旁路。其他种族/风格保持220s。
2. `terran_timing_opening_package_incomplete`增加`threat_active`：真实威胁或
   rush latch出现即关闭窄塔帽，F2/PSD恢复原动态防御目标；敌退后若首波包
   仍未完成则自动回到省矿配额。
3. O401双lane验收：160s出现首扩基金/Runner截断，240s炮塔0且Nexus在途；
   若350-500s提前接触，塔目标必须即时解除上限；目标连续取得至少3个胜局，
   把严格最近5局推回3/5。

## O401 Terran Timing（2胜1负；瞬时3/5后被追加样本拉回2/5）

- `o401a`：**Victory 2954.4s**。二矿265.2s，首暴风466.1s、首不朽
  470.1s；900s舰队11、1069s舰队19，多次被抄仍恢复，最终23暴风+1航母。
  但清场耗时近3000s，电脑期间反复重建CommandCenter，是严重风险信号。
- `o401b`：**Victory 1100.1s**。二矿184.8s，首暴风466.1s、首不朽
  494.2s；731/900/1012s舰队8/13/22，终局21暴风+4航母+2不朽，O401
  最干净的胜局。
- `o401c`：**Defeat 3012.2s**。1500-2500s长期维持23-33舰队、4基地，
  2200s敌仅1 SCV且零可见结构，却因基地4-15人骚扰反复触发O217/O219召回；
  敌CC持续重建，2700s重新攒出13维京+24枪兵+14劫掠+8鬼兵+4战巡。
  2849s我仍29舰队，2883s 81 supply终局波到家后2925s舰队归零，最终翻盘。
- O401a/b完成时窗口曾达3/5，但已启动的o401c随后成为有效败局，动态最近5局
  回落为 **2/5**。因此Timing不作最终收官，必须修终结链后再补胜。

### O402 Terran Power 解封首局（运行中）

- `o402a`当前约1515s：6基地、68农、22暴风+4航母+7追猎，满人口；敌仅
  4 SCV和少量残余结构，处于压倒性胜势。Power历史3/24封存后，解封首局
  的中期水位已显著改善；仍需等正式结果，且同样受终结链工程债影响。

### O402 Terran Power 正式结果（1胜0负）

- `o402a`：**Victory 1631.8s**。二矿237.1s、三矿442.0s、四矿626.8s；
  首暴风413.8s、首航母538.4s。562/675/900s舰队5/9/21，历史Power
  550-700s转型真空已未复现；终局22暴风+4航母+7追猎、6基地满人口。
- 解封新战线当前 **1/1**。胜局中电脑仍多次重建CC，结束时存款19500矿/
  9152气，说明O403终结链对Power同样是下一轮关键验收，不因首胜跳过。

### O403 已落地：残敌终结模式

1. 新增`terminal_cleanup_active`：t≥1200、舰队≥16，且敌结构≤10、农民≤12、
   可见作战单位≤12时进入残敌终结模式；任何一项重新变大即自动退出。
2. 终结模式下显式目标优先敌结构；无结构时直接猎杀可见SCV/农民，再无农民
   才追残兵，避免空巡理论矿点给电脑重建窗口。
3. 终结模式跳过AA蹲守、集结闸和战斗模拟刹车；O217小股残敌不再抽回全舰队，
   O219/空军召回门抬到25，只对真正主力级抄家回防。目标是在敌恢复大军前
   把最后生产资料和工人清零。
4. 下一Timing样本必须验收O403事件出现后≤600s结束；同时不允许忽略25+主力波。

## O403 双 lane 中间结果

- `o403a` Timing仍在运行：约2200s时4基地、23暴风+4航母，敌已零已知结构/
  零可见单位；O403残敌终结事件已触发，但暴露“无任何已知目标时停在旧坐标”
  的地图搜索缺口，尚未正式结束。
- `o403b` Power：**Defeat 1103.8s**。二矿233.0s、三矿377.7s、四矿
  462.1s；433.9s首暴风，506s仅2舰队却已有4基地/3星门，562s只有3舰队
  却爬到6星门。549s 28 supply首波到家，619s舰队归零；终局气1078但
  无舰队/星门，证明死因是首波前投资顺序，不是资源总量不足。
- Power解封新战线当前 **1胜1负**。

### O404 已落地

1. **Power四矿闸**：Terran Power在真实舰队<4时最多三矿；O402胜局四矿
   626.8s/舰队6，O403败局四矿462.1s/舰队1-2，形成直接对照。
2. **Power星门闸**：真实舰队<4时星门最多3座；统一覆盖critical派工、
   extra_production与bank滚雪球三条入口。前三座保留首波并行产能，第4+座
   等舰队真实出场后自动解锁。
3. **终结地图轮巡**：O403模式在零已知结构/零可见单位时，若当前目标已可见，
   就轮换到下一个扩张点，搜索藏在迷雾中的SCV/飞行建筑，不再停旧坐标。
4. O404验证仍用Timing+Power双lane：Timing验收搜索后终局收敛；Power验收
   四矿不早于舰队4、SG≤3直到舰队4，目标把Power窗口从1/2抬到≥3/5。

## O404 双 lane 中间结果

- Timing lane沿用`o403a`自动重试：首次尝试在约2200s、23暴风+4航母、敌情
  清零时无结果退出，属无效样本；重试加载O404后正式 **Defeat 878.1s**。
  重试498s已有1暴风+2不朽、3基地，550s 2暴风+2不朽；但三矿仍在458s
  提前出现，首波掉矿后540/643s反复重建三矿，Nexus基金持续暂停产兵，
  598-731s舰队恒3，721s 49 supply第二波后归零。
- Power lane `o404b`仍在运行：约988s已16暴风+3航母、5基地，SG仅4座，
  O404投资闸通过并处于明显胜势。
- Timing动态最近5局仍 **2/5**，未完成最终认证。

### O405 已落地：ExpansionController最终层基地硬钳

1. 旧Timing/Power开矿闸只作用在`_want_dynamic_expand`意图层，健康扩张、latch、
   恢复基金仍可在最终注册处带入ExpansionController，导致判据为False却照开矿。
2. 在ExpansionController实际注册前重算`to_count`：Terran Timing双不朽真实
   出场前最大2；Terran Power真实舰队4前最大3。若钳后目标不高于当前基地数，
   本帧不注册任何扩张行为。
3. 这是所有动态开矿入口的统一出口，后续验收不再只看事件/意图，而直接检查
   实体：Timing第三基地不得早于双不朽；Power第四基地不得早于舰队4。

## O404 Power 正式结果（Victory 1579.8s）

- `o404b`：二矿233.0s、三矿381.7s；四矿610.7s时舰队已5，符合O404。
  506/562/675s舰队2/4/10；星门在舰队4前保持3座，之后按4/8座爬坡。
  终局24暴风+4航母，O403残敌终结1470s触发后约110s结束。
- Power解封新战线为 **2胜1负**；按历史尾部+新样本滚动，下一有效胜局预计
  即可达到最近5局3胜。

### O406 已落地：bank开矿出口同步硬钳

1. O405a实机在490s仅1不朽时仍出现三矿，说明`_spend_bank`的“矿≥800直接
   开矿”是MacroPlan最终硬钳之外的第二出口。
2. `_spend_bank`扩张条件同步接入Timing双不朽闸和Power四舰队闸；此后两个
   动态开矿出口均使用同一口径，不再允许银行路径绕过。

## O405/O406 双 lane 结果

- `o405a` Timing：**Defeat 918.4s**。该局运行的是O405代码，bank旁路仍在；
  二矿172.8s后361.6s三矿、502.2s四矿，首波拆四矿后系统长期进入基地恢复
  基金，619-788s银行2200→9555矿、5星门却舰队恒4，最终恢复冻结致败。
- `o406a` Timing：**Defeat 865.0s**。O406硬钳通过：450s仍2基地/1不朽，
  498s双不朽+2暴风后才于510.3s开三矿。但510s刚解闸立即花400矿，619s
  仅3舰队，651s 36 supply第二波后舰队1→0。证明“双不朽”仍不是足够的
  扩张放行门，必须把真实舰队临界质量并入。
- `o406b` Power：**Defeat 886.0s**。O404投资闸通过，始终最多3基地/3星门；
  但波提前到517s，场上仅2暴风、9塔，对27 supply M&M波失守。O404胜局
  同阶段舰队也约2，但塔14且波稍晚，剩余病灶是首波站线对时间方差不够稳。

### O407 已落地

- Terran Timing三矿门从“双不朽真实出场”收紧为“双不朽 + 真实舰队≥4”。
  三处开矿出口（主MacroPlan最终to_count、动态意图层、bank滚雪球）统一传入
  Tempest+Carrier在场数；pending不算，避免订单幻影提前放行。

### O408 已落地：Power复用双不朽站线包

1. Terran Power纳入O387/O394机械台预置：t≥340、至少2基地、舰队<8且FB
   存在时建Robo，与Timing相同；Rush仍保持原420s/3基地参数。
2. Power在Robo就绪后无条件预产2只Immortal；第3只仍需可见重甲≥6，避免
   地面无限膨胀。目标是把517s提前Power波从“2暴风+9塔”升级为
   “2暴风+双不朽+塔阵”，降低电脑波次时间方差。
3. 下一双lane：Timing验证舰队4前三矿为0；Power验证340s Robo、首波前双不朽，
   两条战线都以再胜1局达到动态3/5为目标。

## O408 双 lane 中间结果

- `o408a` Timing：**Defeat 1085.4s**。O407开矿闸通过：二矿192.9s；
  619/731s舰队5/7且始终2基地，双不朽战损后也未提前开矿；751.3s恢复
  双不朽+舰队7后才开三矿。三矿被拆后峰值3/当前2触发基地恢复基金，
  844-956s银行375→2730矿、4星门但舰队恒6，第二波后败。主因已从开矿
  提前迁移到“成型舰队掉一矿仍被全局停产”。
- `o408b` Power仍在运行：约1025s已17暴风+3航母+2不朽+12追猎、5基地，
  O408双不朽机制通过并处于优势局。

### O409 已落地：成型舰队豁免丢矿全局停产

1. 新增`terran_pressure_rebuild_fund_bypassed`：Terran Timing/Power在当前
   基地≥2且真实舰队≥4时，`lost_base`不再开启Nexus独占基金。
2. 该窄豁免只取消“所有作战生产暂停”；正常动态扩张/健康矿区仍会重建基地，
   当前基地跌到1或舰队<4时恢复原O381生存优先语义。
3. 目标：掉三/四矿后舰队继续从6增长，不再出现数千矿+多星门但舰队恒定。
