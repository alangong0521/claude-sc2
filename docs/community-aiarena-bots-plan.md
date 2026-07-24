# 社区调研:AI Arena / sc2ai 开源 bot 清单、机制提取与迁移方案

- 调研日期:2026-07-23/24
- 调研范围:aiarena.net wiki、GitHub 搜索(API)、Alkurbatov 开源 bot 清单 wiki、Liquipedia/WebSearch(后两者受限,见下)
- 代码落点:`/Users/calla/work/sc2-community/`(均为 `git clone --depth 1`,浅克隆未记录 commit hash)
- 约束说明:本次 **WebSearch 配额用尽(HTTP 403)**,bot 发现主要靠 ①[aiarena getting-started wiki](https://aiarena.net/wiki/bot-development/getting-started/) ②[Alkurbatov 开源 bot 清单](https://github.com/alkurbatov/suvorov-bot/wiki/Open-source-StarCraft2-bots) ③GitHub Search API(curl)。aiarena.net 的 bot 列表页与 API 需要登录/JS 渲染,**天梯档次多取自各仓库 README 自述,未独立核实**,已逐项标注。
- 我们已调研过的(不重复):sharpy-sc2(见 `community-sharpy-dummies-plan.md`)、ares 生态 QueenBot/12PoolBot/Sharky/h3nnn4n(见 `community-tactics-research.md` B1-B9,已全部落地)。

## 一、开源 bot 总表

### 1.1 本次成功克隆(6 个)

| Bot | 种族 | 作者/仓库 | 语言/框架 | 天梯档次(来源) | 本地路径 |
|---|---|---|---|---|---|
| OctopusV3 | **P** | [takado8/starcraft2_ai_octopus_v3](https://github.com/takado8/starcraft2_ai_octopus_v3) | Python / python-sc2 | ProBots 2023 S1 八强、AI Arena 第 14/64、sc2ai 夏季赛 11/16(均 README 自述,未独立核实) | `sc2-community/OctopusV3/` |
| MicroMachine | T | [RaphaelRoyerRivard/MicroMachine](https://github.com/RaphaelRoyerRivard/MicroMachine) | C++ / CommandCenter 深度分叉 | README 自述"社区最强 bot";AI Arena 主页 aiarena.net/bots/49(需登录,未打开) | `sc2-community/MicroMachine/` |
| Lambdanaut | Z | [Lambdanaut/Lambdanaut-sc2](https://github.com/Lambdanaut/Lambdanaut-sc2) | Python / python-sc2(内嵌魔改版 lib/sc2) | README 自述 "trophy-winning ladder bot",具体赛事未核实 | `sc2-community/Lambdanaut/` |
| sludge-revived | Z | [aiarena/sludge-revived](https://github.com/aiarena/sludge-revived)(原仓 [gitlab.com/Blodir/sludgement2](https://gitlab.com/Blodir/sludgement2)) | Python / python-sc2 | 2019 Reaktor Artificial Overmind 冠军、约高钻/低大师(原 README);现由 aiarena 官方维护为 housebot | `sc2-community/sludge-revived/` |
| Kagamine | Z | [Hjax/Kagamine](https://github.com/Hjax/Kagamine) | Java / ocraft-s2client | 未标注;Hjax 为 sc2ai 老作者 | `sc2-community/Kagamine/` |
| HarstemsAunt | **P** | [FredNoonienSingh/HarstemsAunt-SC2-AI](https://github.com/FredNoonienSingh/HarstemsAunt-SC2-AI) | Python / python-sc2 | 自述"competing on the SC2 AI Ladder",档次未标注 | `sc2-community/HarstemsAunt/` |

### 1.2 任务点名但**未找到公开源码**(跳过,不硬凑)

| Bot | 结论 | 依据 |
|---|---|---|
| Eris(Z) | GitHub 仓库搜索 `eris sc2/eris zerg bot/eris starcraft` 均 0 命中 | GitHub Search API,2026-07-23 |
| HjaxAI | 无此名仓库;Hjax 本人 GitHub 下 SC2 相关为 `Hjax/Kagamine`(Z,Java)与 `Hjax/Ene`(旧 Python bot),已用 Kagamine 替代调研 | [github.com/Hjax](https://github.com/Hjax) 仓库列表 |
| ThreeEyedRaven | GitHub 同名仓库均与 SC2 无关(iOS/个人主页等) | GitHub Search API |
| Tyr(P) | AI Arena wiki 的 .NET 栏确有 "Tyr Bot" 条目;GitHub 用户 [TyrSC2](https://github.com/TyrSC2) 存在但仅公开 `AsgardBackend`,bot 本体未开源 | aiarena wiki + GitHub API |
| OssaviBot / Zozo | GitHub 搜索 0 命中 | GitHub Search API |

> 这几个名字在 aiarena.net bot 列表里应该存在,但列表页需 JS 渲染、API 需鉴权(curl 返回 `Authentication credentials were not provided`),**无法核实其天梯身份**,待主 agent 有浏览器/账号条件时补查。

### 1.3 其他已知开源 bot(未克隆,备查)

来自 [Alkurbatov 清单](https://github.com/alkurbatov/suvorov-bot/wiki/Open-source-StarCraft2-bots) 与 GitHub 搜索:CommandCenter(C++,三族通用框架,MicroMachine 的底座)、5minBot(T,空投生化,[Archiatrus/5minBot](https://github.com/Archiatrus/5minBot))、ByunJR(T,proxy Reaper)、zerGG(Z,蟑螂+坑道虫 all-in)、BotWithAPlan(目标导向)、seebot2(P)、ascyZergs(Z,C++,[ascyrax/ascyZergs](https://github.com/ascyrax/ascyZergs))、StarcraftStockfish(P,基于 sharpy)。价值密度低于已克隆 6 个,暂不入库。

## 二、逐 bot 机制提取

### 2.1 OctopusV3(P)—— 神族微操最丰富的开源仓,对我们直接对口

仓库含 **30 个神族流派**(`strategy/`,含 skytoss_tempest、skytoss_carriers、dts、fortress_skytoss 等,与我们 flows.yml 的 tempest/carrier/dt 直接可比)和 **30 个单位微操文件**(`army/micros/`)。注意:macOS 克隆时报 `army/Army.py` 与 `army/army.py` 大小写冲突,大小写不敏感文件系统上只落了一个文件,读码时注意。

1. **暴风舰集火伤害预算表**(`army/micros/tempest.py`):维护 `targets_dict: 目标→已分配伤害列表`,每艘 tempest 出手前只选"剩余血量 > 已累计分配伤害"的目标,**从机制上消除过度集火浪费弹药**;撤退判据用威胁总 DPS(`total_dps > 50 且护盾 < 85%` 后退 4 格),而非简单血量阈值。
2. **Warp Prism 农民电梯**(`army/micros/warpprism_elevator.py`):用棱镜把远矿农民空运往返于矿区之间(`distant_mining_workers` 装载→在最近安全矿区卸载),解决远距分矿采矿走路损耗。全社区仅见此一家。
3. **护盾电池回盾循环 + 全军回盾暂停**(`army/micros/zealot_shield.py`):叉子护盾 <50% 自动走向最近有能量的护盾电池;若全队 >65% 单位低盾则触发 `shield_regen_pause` 整体停战回盾。
4. 加分项:按敌族分池的策略管理(`bot/strategy_manager.py`,PvT/PvP/PvZ 各一套策略池)+ 数值化进攻/撤退条件(`bot/conditions.py` 的 `army_value_n_times_the_enemy(n)`,要求侦查 ≥2 次后才比较军力价值)。

### 2.2 MicroMachine(T)—— 微操天花板,机制跨族通用

1. **内嵌 libvoxelbot 战斗模拟器**(`src/Util.h` 引用 `libvoxelbot/combat/simulator.h`):C++ 级快速战斗推演,用于接战胜负判断。思路同我们 B3 的 ares CombatSimManager,但保真度更高。
2. **RangedManager 威胁缠斗逻辑**(`src/RangedManager.cpp`):逐单位计算威胁射程/攻速,逃跑时不是直线退,而是**查 influence map 选最优逃离路径**(约 `RangedManager.cpp:610-625`);每种技能硬编码帧数表(锁敌 9 帧施法+321 帧引导、坦克架/收 65/57 帧等)做精确时序。
3. **骚扰编队的引力/斥力常量组**(同文件头部 `HARASS_*` 常量):骚扰单位与友军保持 5~10 格的吸引/排斥平衡、按射程差 ≥2 选目标,是一套可调参的骚扰力场模型。

### 2.3 Lambdanaut(Z)—— 唯一带机器学习组件的开源天梯 bot

1. **PyTorch 战斗胜负预测器**(`lambdanaut/learning/combat.py`):输入双方兵种计数向量(42 维,三族兵种索引表),输出 平局/胜/负 三分类;训练数据由 `learning/generate_combat_data.py` 实战生成,模型存 `data/combat_model.pt` 跨局持久化。
2. **按 rush 距离选开局**(`lambdanaut/managers/build.py:104-145`):用地形 rush 距离(平均≈153)阈值分档——近图一波、远图偷经济,按敌族分别设阈值。
3. **Manager 间 pub-sub 消息总线**(`lambdanaut/managers/intel.py` 等):所有 manager 只发消息,仅 IntelManager 有权改全局状态,单向数据流防状态污染。
4. 加分项:OverlordManager 有自杀式强袭侦查(`do_suicide_dive`)和毒爆空投(`baneling_drops`)状态机(`managers/overlord.py`)。

### 2.4 sludge-revived(Z)—— 声明式建造顺序 DSL,与我们 flows.yml 思路同构

1. **建造顺序声明式字典 + 条件解释器**:流派写成纯数据 dict(`bot/logic/spending/build_order_v2/build_orders/zvall/cheese_ling_bane.py`,`economy/supply/gas/gas_ratio/bases` 分节,`[人口阈值, 数量]` 元组列表),由 `bo_interpreter.py` 编译成带 `完成条件/激活条件` 的 BOStep 列表——**流派即配置,与我们 flows.yml 哲学一致且更细**(它支持"人口≤x 且农民≥y 时停补农"这类双边条件)。
2. **手工调参的单位克制系数表**(`bot/util/zerg_unit_counters.py`):`我方兵种→敌方兵种→资源效率比`(如 9 狗 225 矿胜 1 不朽 375 矿 → 系数 0.6),注释标明哪些经过实测(`#tested`)。轻量级 can_win_fight 替代品。
3. **按 matchup 分目录的流派库**(`build_orders/zvt|zvp|zvz|zvall/`):2019 年冠军 bots 的对策组织方式,直接对照我们 protoss_builds.yml 的分族结构。

### 2.5 Kagamine(Z,Java)—— 情报建模独一档

1. **敌方收入推算**(`enemymodel/ResourceTracking.java`):逐矿脉记录可见资源值变化差分,归属"我方采/敌方采",从而**估算对手实时收入与饱和矿数**——不靠猜,靠资源点账面。
2. **空投王虫势场寻路**(`unitcontrollers/zerg/Dropperlord.java`):目标基地引力 + 对空单位按距离平方反比斥力 + 地图边界斥力,合成向量决定空投航线,可安全绕开防空。
3. **采矿优化器**(`economy/MiningOptimizer.java`):农民↔矿脉显式指派表,避免抢矿碰撞(等价于 speed mining 的指派版)。

### 2.6 HarstemsAunt(P)—— 结构可参考,独创性一般

1. **ArmyGroup 群体抽象**(`bot/HarstemsAunt/Army/army_group.py`):聚合查询 `supply_delta/ground_dps/air_dps/平均血盾百分比/has_detection`,群体状态一眼可读——我们 B6 Squad 化已有同类概念,可作查询接口补全参考。
2. 如实标注:其 `economy/speedmining.py` 文件头自承 "Stolen Code needs to be reviewed",`pathing/map_sector.py` 标了 `#TODO Rewrite or remove`——该仓工程完成度低,**迁移优先级最低**。

## 三、迁移建议(对我们:ares 底座神族,flows.yml + B1-B9 已落地)

| # | 机制 | 来源 | 落点建议 | 价值 | 工作量 |
|---|---|---|---|---|---|
| A1 | 暴风舰伤害预算集火(防过度集火) | OctopusV3 `army/micros/tempest.py` | tempest 流派微操;与 B2 静态优先级表叠加:先按 B2 选目标池,再用伤害预算去重 | ★★★ | 小 |
| A2 | 按 rush 距离/地图特征选开局流派 | Lambdanaut `managers/build.py:104` | 开局 flow 选择器:近图 charge/一波类,远图 fortress/tempest 类 | ★★★ | 小 |
| A3 | 护盾电池回盾 + 全军回盾暂停 | OctopusV3 `zealot_shield.py` | 补 B4 防守三角:低盾单位就近找电池;与 expansion_cannons 协同 | ★★☆ | 中 |
| A4 | 数值化进攻/撤退条件(`army_value_n_times_enemy`,侦查次数门限) | OctopusV3 `bot/conditions.py` | flows.yml 的 rally/进攻触发条件表达增强,替代纯兵力数阈值 | ★★☆ | 中 |
| A5 | 克制系数表(轻量 can_win_fight 对照组) | sludge `zerg_unit_counters.py` | 做 P 版三族克制表,与 B3 ares CombatSim 双跑对照,校验模拟器可信度 | ★★☆ | 中 |
| A6 | 敌方收入推算(资源点差分) | Kagamine `ResourceTracking.java` | 情报侧:估算对手饱和矿数→驱动换家/压制决策 | ★☆☆ | 大,缓做 |
| A7 | NN 战斗预测器 | Lambdanaut `learning/combat.py` | 暂不引入 torch 依赖;B8 selftune 成熟后再评估 | ★☆☆ | 大,缓做 |
| A8 | 棱镜农民电梯 | OctopusV3 `warpprism_elevator.py` | 远矿图专用,鸡肋偏彩蛋 | ★☆☆ | 中,缓做 |

明确不做:libvoxelbot(C++,我们 Python 栈无法直接用,且 B3 已有等位机制);HarstemsAunt 的 speedmining(其自承是偷来的代码,且 ares 已有工人分配)。

## 四、排期建议

- **第 1 批(下次跑局周期)**:A1 + A2。都是小改动、可直接进 flows.yml/tempest 微操,跑局对照 tempest 流派胜率。
- **第 2 批**:A3 + A4。补防守与进攻触发条件,与 B4 联动验证。
- **第 3 批**:A5。P 版克制表需要实测标定(参照 sludge 的 `#tested` 做法,用 unit tester 跑比值)。
- **Backlog**:A6/A7/A8,等 B8 selftune 与 B6 Squad 化稳定后再议。

## 五、本次调研的未决项(如实标注)

1. Eris/ThreeEyedRaven/Tyr(P)/OssaviBot/Zozo 源码未找到,天梯身份未核实(需 aiarena.net 账号或浏览器渲染)。
2. 各 bot 天梯档次均来自 README 自述,未经第三方核实;Liquipedia ProBots 页面 FetchURL 404、WebSearch 配额耗尽,未能交叉验证。
3. OctopusV3 大小写冲突导致 `army/Army.py`/`army/army.py` 只落其一,若精读该仓需在大小写敏感环境重新克隆。
4. Kagamine/MicroMachine 为 Java/C++,只做了机制级速读,未编译运行验证。
