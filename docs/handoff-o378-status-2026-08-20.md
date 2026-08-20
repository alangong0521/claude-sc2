# 工作交接:carrier 流 VeryHard 攻坚(o378 轮快照,2026-08-20)

> 给下一个 AI 接力用的完整状态快照。读这份 + `docs/battle-log.md`(10800 行全量迭代日志)+
> `docs/handover-carrier-vh-matrix.md`(2026-08-02 上一阶段交接)即可开工。
> 先读「## 五、血泪教训」,不要重复踩坑。

---

## 一、项目是什么

`~/work/claude-sc2` —— SC2 神族 bot(vendored ares-sc2 框架)+ bench 自调优回路。
本阶段目标(司令定):**carrier 流打穿 VeryHard 电脑的 Zerg 和 Terran 的 Rush/Timing/Power
三风格,每组合 N=5 标准(5 局 ≥3 胜)**。

本体在 `ares-bot/`:

- `bot/managers/production_manager.py`:生产/经济/防御塔链/科技链钉点(O97-O378 迭代主战场,~11k 行)
- `bot/managers/combat_manager.py`:战斗指挥(O302 推进/黄金窗/AA 重评/出击闸)
- `bot/production_plans.py`:纯逻辑判据库(新判据一律纯函数,~6.6k 行)
- `bench.py`:跑局器(`--flow carrier --diff VeryHard --race Zerg --map AbyssalReefLE --ai-build Timing -n 3 --tag oXXx --replay`)
- `tests/`:**853 个单测全绿**(`cd ares-bot && poetry run python -m unittest discover -s tests`)
- `docs/battle-log.md`:O97-O378 每轮的结果/改动/尸检/验收判定全录

## 二、当前验证状态(2026-08-20)

### 六组合战绩矩阵(VeryHard @ AbyssalReefLE)

| 组合 | 状态 | 备注 |
|---|---|---|
| Zerg Power | ✓ **打穿 5/6** | o361a 3/3 + o362b 2/3,首个 VH 组合 |
| Zerg Rush | ✓ **打穿 3/5** | o368b 2/3 + o369b 2/3,最近 5 局 3 胜 |
| Zerg Timing | **封存 0/30** | o352-o370 十二轮攻坚,终审:结构性量级差(见下) |
| Terran Power | **攻坚中 3/21** | o371/o373/o377 各 1/3,判决轮已过,冲 2/3 |
| Terran Rush | 未开战 | 排期中 |
| Terran Timing | 未开战 | 排期中 |

难度阶梯参考:Harder Zerg Timing 曾打穿(o340b 5/5),后在迭代中回归。

### 正在跑的(o378 轮,本文落笔时)

- lane1 `o378a`:VH Terran Power ×3(冲 2/3)
- lane2 `o378b`:VH Zerg Rush ×3(恢复验证)
- 验证 O378 六项修复,核心是修掉 **O377-④ 假修复**(出击舰队计数误含在产 = 幻影舰队出门捐掉,上轮 Zerg Rush 0/3 主犯,已实锤 `include_pending=False`)。
- 监视器挂后台,结果出来按协议:尸检(≥3 优化点)→ battle-log 记账 → commit+push。

### 胜局配方(两个打穿组合的共同打法,有 10+ 局实证)

速二矿(132-250s)→ 70+ 农 5-6 矿经济 → SG ~250-450s → **FB(舰队航标 Fleet Beacon)400-550s**
→ 舰队(暴风+航母)15-29 → **O302 连续先手压制**(每 30s 一推,把敌科技/兵力压在成型线下)
→ 滚雪球终结。关键指标:农峰 ≥67、FB ≤550s、舰队峰值 ≥18、O302 ≥10 次。
变体:Zerg Rush 早期靠 12 虚空+塔链过渡;Terran 靠 E10 转型时间盒(480s 硬转航母)。

### Zerg Timing 封存判决(数据依据,勿轻易重启)

- 0/30;「最后一刀」机制修复(塔闸/互斥仲裁/FB 选址)**全部验证兑现后仍 0/3**。
- 死因是结构性量级差,不是 bug:Timing 决胜波 520-560s 到脸时,配方需要 72 农,
  实际只有 45(敌波强制防御支出,经济永远爬不到喂饱舰队的水位)。
- 机制链完整保留在代码里;司令复议前不重开。

## 三、方法协议(司令拍板,必须遵守)

1. **双 lane 并行**:每轮同协议 2 lane × 3 局(headless 加速,无窗口;`pgrep -x SC2` 验证进程)。
   启动前:`pkill -9 -x SC2` + 确认代理关(`scutil --proxy` HTTPEnable=0)+ Battle.net Agent 在
   (`open -a "/Users/Shared/Battle.net/Agent/Agent.app"`;**单机版不更新 SC2**)。
2. **每局结束立即尸检**,提炼 ≥3 个优化点落地,下轮验证(写进了 CLAUDE.md)。
   尸检工具:`poetry run python scripts/autopsy_summary.py bench/<tag>/game_XX`;
   快照 state_*.json 是 dict(time/minerals/vespene/supply/workers/bases/army/structures/enemies/events),
   事件簿合并所有快照按 (t,msg) 去重。
3. **判读强制两轮累计**(3 局制噪声大);回退判决必须有机制级证据(事件时间戳链),不看单点胜率。
4. **落地纪律**:逻辑写纯函数(production_plans.py)+ 单测;**实例属性一律 `__init__` 初始化**
   (三次 AttributeError 烧掉整轮样本);import 冒烟
   `poetry run python -c "import sys; sys.path.insert(0,'ares-sc2/src'); import bot.managers.production_manager, bot.main"`。
5. **每轮 commit+push**(develop 分支);push 偶发 SSL_ERROR_SYSCALL,后台重试循环必成。
6. 监视器模式:`while pgrep -f "bench.py --flow carrier"; do sleep 60; done` 后台 task,完成自动通知,**不轮询**。

## 四、关键代码地标(迭代至今的资产)

- **O329-O333 速二矿体系**:ZT opener(protoss_builds.yml CarrierOpenerZergTiming),bot 层钉点族
- **O360/O369 FB 基金窗+fund-first latch**:SG 就绪+FB 未落时窄域暂停非保命支出攒 300+200;
  O370 仲裁(二矿未成交 Nexus 优先);O373 触发门(townhalls<2 不触发)+通道收口
- **O375-③/O376-① SG2 体系**:SG1 落成即钉 SG2(豁免 latch)+SG 闲置产虚空;
  **门必须 `in ("timing","rush")`**(见血泪教训)
- **O302 推进体系**(combat_manager.py):黄金窗 zt_golden_window_push(腐化≤4+舰队≥3,胜局实证);
  出击闸链:盲推闸(信用 supply=0 不推)+ 敌军闸(敌 supply ≤ 我)+ fleet 下限 5 + 腐化硬闸(O378:信用腐化 ≥4 不推)
- **O373 让位/互斥族**:让位死锁三刀(60s 熔断+矿≥400 冗余门+水晶自救冷却)
- **O377-① 首推窗**:fleet floor 5(对齐 o373a 胜局 528.5s fleet=5 首推);recipe_push_exempt(terran 配方推)
- **O374-① 信用体系**:aa_peak_sticky(60s 粘滞)+ enemy_supply_credited(120s 粘滞,抗战争迷雾)

## 五、血泪教训(每条都烧过整轮样本)

1. **协议矩阵门死(犯过两次!)**:`_ai_build == "timing"` 把 rush lane 关门外,改了一轮死代码。
   防线:`tests/test_production_plans.py::test_protocol_matrix_reachability`(协议矩阵×关键闸可达性单测)。
2. **阈值改动必须对照胜局配方参数**:O374-④b fleet 8、O376-⑤ floor 6 都是用单点数据改的阈值,
   删掉了有胜局实证的配方参数(fleet=5 首推),各烧一轮。改阈值前先查胜局配方的对应值。
3. **「修好了」必须有事件级证据**:O377-④ 注释写「在场口径」代码没传参 = 假修复,
   幻影舰队(报 5 实 2)出门捐掉。验收一律看事件簿+快照对证。
4. **实例属性未初始化**:三次 AttributeError(o334/o353b/o365)各烧一轮。
   防线:`__init__` 初始化 + bot/ 全目录 `self._x +=` 扫描(脚本在 battle-log 有记录)。
5. **暂停型预留体系(O106 全局资金冻结)已证伪**;可用的是单建筑窄域基金窗
  (FB latch/破产分支,带超时+threat 豁免+健康监控)。
6. **已证伪勿再试**(完整清单在 battle-log 开头):ZT 全程墙链、O283 口袋推广、全量 F2 冻结、
   O310 农民 cap、O312 A 案早二矿无条件版、O317 forge 先于墙、forge 落位分矿(O344-①)。
7. **自救水晶治不了 placement 几何死槽**(O356 实证):no_placement=不可放置时,补电无用,
   要走 O357 死槽拉黑换锚/O378 水晶环带降级。
8. **场强判据要看「就绪+在途」合并口径**,且出击计数剔除在产(O378-①)。

## 六、后续要做的事(按优先级)

### 立即(o378 轮闭环)
1. o378 双 lane 结果出来 → 尸检 → 记账 → commit/push。
   看点:Zerg Rush 是否恢复 ≥1/3(④ 假修复实修后);Terran Power 是否到 2/3。

### 短期(1-3 轮)
2. **Terran Power 冲打穿**:胜局链已成立(FB@325→时间盒 480→航母@638→O302×11→舰队 28),
   差 ~250s 节奏。已知欠账:
   - recipe_push_exempt 还是死代码(fleet≥5@[500,570] 不可达,SG2 全在 743s+;O378-② E10 钉 SG2 修的就是这个)
   - 反维京为零(致死波带 8-33 维京,纯暴风+航母白给;候选:追猎/白球混编护航、航母优先配比)
   - 卡人口 129s(o377a g3,31/24 低级失分)
3. **Zerg Rush 巩固**:腐化墙是剩余主死因(O378-⑥ 腐化硬闸已落地待验证);
   填线虚空负资产已 cap 2。
4. **硬判据**:若 Terran Power 在首推窗解锁(O377-①)验证轮后仍 0/3,按 Timing 同款规则封存。

### 中期(打穿 Power 后)
5. **开 Terran Rush / Terran Timing 战线**(bench 参数现成:`--race Terran --ai-build Rush/Timing`)。
   预期:zerg 门已去(O371),主力机制全种族可达;Rush/Timing 的早期压力形态与 Zerg 不同,
   首批尸检重点看 opener 适配。
6. **打穿后暂停交司令验收**(司令原话:very hard 档位 zerg timing 5 局 3 胜达成后暂停。
   Timing 已封存,等司令对验收口径的最终解释)。
7. 可选扩展(司令提过):Protoss 三风格(镜像局)、Macro/Air 风格(Air=制空硬碰硬,最难签)。

### 长期/工程债(不阻塞,顺手修)
- O324 build runner 步#5 卡死(88s 处 >45s,多轮复现)
- O365「买得起=False」诊断疑似 can_afford bug(矿2170/气443 买不起航母,查 supply_left)
- 塔硬顶在途穿透(就绪 18 时在途继续落成)
- o377b g2 扩张闸(478s 后无 NEXUS 钉点,手里 535 矿,疑似 threat 锁整局)
- O307 撤开矿抖动、O364 停气复拽(收敛中未根除)

## 七、环境与运维

- bench 一律在 `ares-bot/` 子目录跑;每个 `&` 分段会丢 cwd,用「先 cd 再两个 nohup」写法。
- 单测 853 个全绿;改动后必跑 `poetry run python -m unittest discover -s tests` + import 冒烟。
- git:develop 分支,HEAD 附近 `a5e8f10`;push 失败用后台重试循环
  `for i in $(seq 1 20); do git push origin develop && break; sleep 60; done`。
- SC2 进程卡死处理:`pkill -9 -x SC2`,检查 Battle.net Agent 是否在,不要在战网点更新(单机版)。
- 录像:bench 带 `--replay` 存 `bench/<tag>/game_XX/replay_XX.SC2Replay`;
  解析工具 `scripts/replay_bases.py`(依赖 s2protocol,已装 venv)。
