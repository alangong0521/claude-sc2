# KetrocBot(人族,mass raven)调研与可迁移方案(2026-07-24)

- 仓库:https://github.com/Ketroc/KetrocBot-for-Starcraft-II
  (GitHub 主页 https://github.com/Ketroc,pinned 仓库,描述 "competition-winning bot which plays terran",Java / ocraft s2client)
- 本地克隆:`/Users/calla/work/sc2-community/ketroc`(`git clone --depth 1`,HEAD = `cc797b5 -cyclone drop WIP`)
- 语言/Java,不可直接复用代码,只迁移机制思路。行号均基于上述 commit 的快照。
- 我们 bot:`ares-bot/bot/`(ares-sc2 框架,Python),现有流派 tempest / carrier / dt,已合并社区机制 B1-B9(见 docs/community-tactics-research.md)。

---

## 一、Ketroc mass raven 打法循环(拆解)

### 1.1 战略层配置
源:`src/main/java/com/ketroc/strategies/Strategy.java` `massRavenStrategy()`(L869-896)
- `MASS_RAVENS=true`、`PRIORITIZE_EXPANDING=true`、`DO_SEEKER_MISSILE=false`(优先机炮台流)、
  `DEFAULT_STARPORT_UNIT=TRAIN_RAVEN`(星港默认量产渡鸦)、首发升级 `RAVEN_CORVID_REACTOR`(渡鸦初始能量+);
- 对 Z 额外配 2 女妖清菌毯 + 舰船武器升级。

### 1.2 出手(进攻/收兵)判定:用"可用机炮台总数"当战斗力计量器
源:`src/main/java/com/ketroc/managers/ArmyManager.java` L677-689
- `numAutoturretsAvailable = Σ(每只渡鸦能量/50)`;有任意渡鸦能量 ≥180 且可用炮台数 >20 → `doOffense=true`;
  进攻中掉到 <8 → 收兵。**本质:能量即弹药,弹药攒满才出门,打光就回家**。
- 单体层面:血量 <100 且能量 <35 的渡鸦回"维修湾"(`ArmyManager.java` L1820-1825,
  维修湾 = 分基地前 4+ SCV 自动维修点,`models/Base.java` / `micro/ScvRepairBay*.java`)。

### 1.3 机炮台(auto-turret)投放:全局去重 + 批量 query 落点
源:`src/main/java/com/ketroc/managers/TurretingRaven.java`(全 138 行)
- 每只渡鸦报目标点 → 生成 9×9 候选格(`canFit2x2` 预过滤 + 距目标 <攻击射程 7);
- 按敌情排序:敌人不撤退/不可移动 → 炮台放自己脚边远处(`doPlaceFarBack`),否则放目标前 3 格;
- `onStepEnd` 汇总所有渡鸦的候选格,**一次批量 placement query**,先到先得分配落点,
  落点被占后从共享池删掉该格及周围 8 格(防炮台互相卡位);
- 渡鸦距落点 <4 直接施放,否则先 MOVE 过去;拿不到落点的渡鸦退回 SURVIVAL 微操。
- 能量门槛:平时 `AUTOTURRET_AT_ENERGY=170`(`Strategy.java` L97)攒能量,但
  `beLiberalWithRavenEnergy()`(`ArmyManager.java` L1861-1866):进攻且渡鸦 ≥8、在主/二矿、
  附近有残血行星要塞或己方坦克时放宽到 50。

### 1.4 干扰矩阵(interference matrix):专项微操类 + 时间预算
源:`src/main/java/com/ketroc/micro/RavenMatrixer.java`(全 103 行)、`ArmyManager.java` L2004-2052
- `RavenMatrixer` 是"一次性任务微操":目标(默认只打攻城坦克,`findMatrixTarget` L2041-2052)
  死了/自己被控就放归普通微操;
- 关键思路 `getRange()`:施放距离(9+半径) + `攒到 75 能量所需秒数 × 移速` ——
  **能量不够时不干等,提前往目标走,走到位时能量刚好够**,到位即放;
- `minTimeToMatrix(raven, target)`:给上层调度用的"最快几秒能沉默目标"估算(赶路时间 vs 攒能量时间取大);
- 节流:矩阵每 1 秒最多 1 次、对空弹每 4 秒最多 1 次(`castMatrix` L2004-2020 / `castSeeker` L1982-2002,
  共用 `prevSeekerFrame`)。

### 1.5 反装甲导弹(anti-armor missile / seeker):影响力地图选点
源:`ArmyManager.java` `castSeeker`(L1982-2002)+ `findSeekerTarget`(L2022-2039)
- 在施法半径 15 的网格上找 `pointSupplyInSeekerRange`(溅射范围内敌方人口总和)最大的格子;
- 满能量时门槛降 7 人口(`MIN_SUPPLY_TO_SEEKER - 7`)——能量要溢出了就别挑剔。

### 1.6 单体技能循环微操的通用骨架
源:`src/main/java/com/ketroc/micro/BasicUnitMicro.java`(619 行)
- 优先级枚举 `MicroPriority{SURVIVAL, DPS, GET_TO_DESTINATION, CHASER}`(`micro/MicroPriority.java`);
- onStep 固定顺序:活着?→ 武器好了就打(`attackIfAvailable`,目标 = 敌造价/击杀所需发数 最大,
  工博弈价按 75 虚高,L235-276)→ 被 cyclone 锁定直线逃 → 不安全就绕行(detour) → 到点收尾;
- 安全判定全部走影响力地图(`utils/InfluenceMaps.java`,按兵种/优先级选不同威胁层,L65-91),
  绕行是"绕威胁转圈找安全角"的角度扫描(L344-418),带顺逆时针防抖(3 秒内不反复换向,L440-448)。

---

## 二、运营调度(扩张/花钱优先级)

- 购买队列 + 每步只成交一单:`bots/KetrocBot.java` L266-289,`purchaseQueue` 遍历,
  第一个 SUCCESS 就停(一帧一动作,防指令风暴),CANCEL 的踢出队列。
- 扩张判定:`managers/BuildManager.java` `buildCCLogic()` L1828-1854
  - 矿物 >500 就拍基地;SCV 接近满采(差 4 以内)降到 400;
  - 队列里已有 CC 不重复排队;扩张位要求威胁地图为 0、可达、未被占(`getNextAvailableExpansionPosition` L2020-2037);
  - 优先级链 `addCCToPurchaseQueue()` L1957-1991:`BUILD_EXPANDS_IN_MAIN`(被打时)→ 口袋矿 macro CC →
    正常扩张 → 矿 >2000 时拍"额外 CC"当矿骡工厂(L1993-2000,敌人还有矿才拍)。
- 产能扩建触发器:`buildStarportLogic` L1904-1924 / `buildBarracksLogic` L1926-1939 ——
  **"所有产兵建筑都在忙"才加建筑**(`isAllProductionStructuresActive` L1947-1955,
  空闲/快造完 addon/训练 >80% 都算"不忙"),人口 >197 无条件加。这是比固定配比更稳的扩产能信号。
- 扩张位被堵的清除:`micro/ExpansionClearing.java`(301 行)——派渡鸦到被堵扩张点,
  用机炮台点杀堵位单位(王虫/菌毯瘤/地面单位),炮台还能被指挥优先打残血堵位者,
  清完 query 可放置才放行扩张。堵位处理与 BuildManager L2032-2034 联动。
- 建筑逃生:`micro/StructureFloater.java` / `StructureFloaterExpansionCC.java` ——
  被打建筑起飞按 SURVIVAL 微操逃命,落点前查威胁地图为 0 才降落;掉血分基地 CC 变矿骡 macro CC
  (`BuildManager.saveDyingCCs`,L58 调用)。

## 三、防守机制

- 防御是独立包 `src/main/java/com/ketroc/strategies/defenses/`:
  `CannonRushDefense`、`ProxyBunkerDefense`、`ProxyHatchDefense`、`GasStealDefense`、
  `WorkerRushDefense2/3` —— 每个都是**状态机(cannonRushStep 0/1/2)+ 专用 SCV 目标分配(ScvTarget)**,
  检测到即改全局策略(如取消先拍的 CC、切 BUILD_EXPANDS_IN_MAIN),防完自动复位
  (`CannonRushDefense.java` 全文 165 行)。
- 农民反 Rush 时 ≥4 个 SCV 会分一半绕到目标背后再 A,防自己人卡位(`CannonRushDefense.java` L67-77)。
- 气矿被偷(`GasStealDefense`)、每步检测(`KetrocBot.java` L222)这类"开局异常检测"全部
  模块化、可开关,在 onStep 里固定顺序轮询。

---

## 四、可迁移到我们神族 bot 的机制清单

格式:机制 → Ketroc 源文件 → 是否适用 → 落地建议(改哪个文件)→ 优先级。
(我们的文件路径均在 `ares-bot/bot/` 下;⚠️ 均为方案,未跑局验证。)

### K1. 施法循环的"能量-路程时间预算"(★ 最高价值)
- 源:`micro/RavenMatrixer.java` L73-102(`getRange` / `timeUntilMatrixEnergy` / `minTimeToMatrix`)
- 是否适用:**完全适用**,与种族无关。核心思想:施法单位能量差 X 点时,换算成秒,
  加上赶路时间,得出"什么时候能放技能",在此之前就朝目标走,杜绝"满能量站在后排看戏"和"空能量冲脸"。
- 落地建议:
  - `combat/templar_caster.py`:现在能量 <75 就原地 `KeepUnitSafe`。改为按
    `(75-energy)/0.5625`(高模回能速率,⚠️ 数值需跑局核对)算出攒能秒数,
    在此时间×移速的距离内就允许往前跟队,目标 = 敌集群预测点;
  - `combat/oracle_harass.py` / `behaviors/oracle_kite_forward.py`:启示/脉冲同理,
    能量不够时绕圈等 vs 压上的决策用同一时间预算;
  - `combat/raven_support.py`:加矩阵/对空弹时直接套 `minTimeToMatrix` 公式。
- 优先级:**P0**(改动小、三处施法单位共用一段工具函数,可放 `combat/base_unit.py` 或新 `utils/caster_timing.py`)。

### K2. 技能施放全局节流 + 去重
- 源:`ArmyManager.java` `castSeeker` L1982-2002(4 秒 1 发)、`castMatrix` L2004-2020(1 秒 1 次);
  `TurretingRaven.onStepEnd` L74-104(全局收集→统一分配→已占落点移出共享池)
- 是否适用:适用。我们 `templar_caster` 现在每只高模各自为政,可能多把风暴砸同一坨敌人;
  oracle/raven 同理。
- 落地建议:`combat/templar_caster.py` 加一个 manager 级登记(或复用 `mediator` 缓存):
  本帧已锁定的风暴落点半径 1.5 内不再选点;风暴施放加全局冷却(如每 0.5-1 秒最多 1 把,
  防一帧全交)。raven_support 的机炮台落点做简单去重集合。
- 优先级:**P0**(纯增量逻辑,风险低)。

### K3. "能量即弹药"的进攻/收兵判定
- 源:`ArmyManager.java` L677-689(Σ能量/单次技能耗能 >阈值才进攻,低于阈值收兵)、
  L1820-1825(残血+空能量个体回家)
- 是否适用:适用,直接映射到高模/舰队能量。我们 carrier/tempest 流推进目前主要看兵力人口
  (见 `managers/combat_manager.py`),没把"高模风暴弹药"计入战斗力。
- 落地建议:`managers/combat_manager.py` 的推进条件里加一项:
  `Σ(高模能量)/75`(可用风暴数)≥2 才主动求战,打空后撤等高模回能;
  个体层面:能量 <25 且盾不满的高模 `KeepUnitSafe` 到后排(替代现在的原地 KeepUnitSafe)。
- 优先级:**P1**(要动推进判定,需跑局调阈值,风险中)。

### K4. 目标选择 = 敌造价 / 击杀所需发数,工博弈价虚高
- 源:`micro/BasicUnitMicro.java` `selectTarget` L235-276(造价取 gas 加权,
  工人固定按 75 虚高;跳过开屏障的不朽)
- 是否适用:适用。我们各 offensive 文件多用 `cy_pick_enemy_target`(cy 默认价值表),
  可在其上加"击杀发数"权重和工人虚高。
- 落地建议:`combat/tempest_offensive.py` / `carrier_offensive.py` 的 pick target 处
  包装一层:value = UNIT_DATA cost / max(1, hp+dps 估算发数)。tempest 长射程点杀尤其受益。
- 优先级:P2(收益渐进,先 K1-K3)。

### K5. 产能扩建信号:"所有产兵建筑都忙才加"
- 源:`BuildManager.java` L1904-1955(`isAllProductionStructuresBusy/Active`)
- 是否适用:适用,通用运营。我们 `managers/production_manager.py` / `production_plans.py`
  若还是按固定配比/固定数量补 BG SG,可换成该信号。
- 落地建议:`managers/production_manager.py`:全部门/SG 非空闲(队列非空或训练进度 <80%)
  且能负担 → 补一座;人口 >197 无条件补。
- 优先级:P1(运营基本功,需先看 production_manager 现状再定改法)。

### K6. 扩张位被堵清除(机炮台点杀堵位者)
- 源:`micro/ExpansionClearing.java`(全文)、`BuildManager.java` L2020-2037
- 是否适用:部分适用。我们没有机炮台,但"扩张 query 失败 → 找堵位单位 → 派单兵点杀/引开 →
  再 query"的闭环可直接搬,执行者换成 1 只追猎/DT。
- 落地建议:`managers/production_manager.py`(或新 `behaviors/expansion_clearing.py`):
  nexus 放不下去且视野内有非隐身堵位单位 → 派最近的闲置战斗单位 A 掉 → 成功后重试扩张。
- 优先级:P2(不常见但卡死时是硬伤)。

### K7. 防 Rush 状态机模块化
- 源:`strategies/defenses/CannonRushDefense.java` 等 5 个文件
- 是否适用:思路上适用,细节不必搬(我们是被 Rush 方,检测对象相反——对面 cannon rush 我们
  恰好是受害者,Ketroc 的 SCV 反打分配对我们防 cannon rush 有参考价值:2 农民/probe、
  按炮台血量算农民数、≥4 农民分半绕后防卡位)。
- 落地建议:若我们尚无 cannon rush / 12 pool 应对,新 `managers/cheese_defense.py`,
  抄其状态机骨架(检测→改 build→分配农民→完成复位)与绕后防卡位细节。
- 优先级:P2(视我们现状,未核实是否已有应对)。

### K8. 威胁地图 + 绕行(detour)微操
- 源:`utils/InfluenceMaps.java`、`micro/BasicUnitMicro.java` L332-448
- 是否适用:大部分已被 ares 网格系统(grid + KeepUnitSafe/PathUnitToTarget)覆盖,
  **不建议重复造**。唯一可借鉴点:绕行方向的顺/逆时针防抖(3 秒不换向,L440-448),
  如果我们观察到单位在安全边缘抖动可单独吸收。
- 落地建议:暂不动;观察跑局录像后如需要,改 `behaviors/` 下对应寻路包装。
- 优先级:P3(低)。

---

## 五、未验证/注意事项

- WebSearch 不可用(配额 403),仓库地址通过直接抓 GitHub 用户主页确认,未做第二来源交叉验证。
- Ketroc "mass raven 出名"来自任务描述;代码中确有完整 mass raven 体系(Strategy.java `massRavenStrategy`),
  与描述一致。
- 本文所有行号基于 `/Users/calla/work/sc2-community/ketroc` 当前快照(commit cc797b5),
  上游更新后会漂移。
- K1 中能量回复速率(0.5625/s)为通用常识值,Ketroc 代码里人族渡鸦用 0.7875/s
  (`RavenMatrixer.java` L92-94);神族高模实际速率**需跑局核对**。
- K5/K7 落地前需先读 `managers/production_manager.py`、确认是否已有 cheese 应对,避免重复。
