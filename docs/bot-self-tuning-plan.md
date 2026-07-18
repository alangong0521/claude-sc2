# Bot 自调优回路方案（research → optimize → verify）

> 起草：2026-07-18
> 状态：**方案，未实现**。供排期。
> 一句话：让 bot 自己「查社区流派 → 改 build + 机制 → 启动游戏验证 → 反馈」，并把这套做成可重复跑的回路。

---

## 0. 问题陈述（来自司令）

当前会话里 Claude 默认「只做方案、不改生产代码」。司令的问题是：

> 能不能让 Claude 自己 ① 去社区查找各种流派 ② 自己优化流派和 bot 机制 ③ 自己启动游戏验证？这样是不是要分成多个 agent 来做？

本文档把**这个问题**和**讨论出来的方案**固化下来，供后续排期实现。

---

## 1. 现状勘察（决定方案形状的三个事实）

只读检查仓库得到，写在这里让方案落地：

1. **没有程序化的胜负信号。** `bot/main.py:316` 的 `on_end` 是注释掉的——bot 现在不记录任何「这局赢没赢」。机器读不出的「赢」，自动化验证就跑不起来。**这是头号缺口。**
2. **中间指标很全。** `_steer_snapshot`（`bot/main.py:197`）每 4 游戏秒发布 `time / minerals / vespene / supply / workers / bases / army 编成 / enemies / events` 到 `~/agent-rts-steer/state.json`。也就是说**经济 + 军力曲线的数据通道已经存在**，缺的只是「结局捕获」和「批量打 N 局聚合」。
3. **REALTIME 默认开**（`spike_config.py:15`）；headless（`REALTIME=False`）在 `CLAUDE.md`「约束/踩过的坑」里标注**本环境不稳**（websocket 超时）。所以现在「打一局验证」慢且半人工。

---

## 2. 核心判断：要不要拆多个 agent

**不要**拆成「3 个平级 agent，一人一阶段」。**要**拆成「1 个主循环当指挥 + 按需派子 agent 干读多/可并行的子活」。

理由：三阶段耦合极紧——

- research 的产出决定 optimize 改什么；
- optimize 的改动产生要验证的假设；
- verify 的结果**反馈回** research/optimize，而这条反馈回路正是学习发生的地方。

三阶段各自独立成 agent，反馈回路就断了。主循环的价值是**跨迭代持有记忆**（例：「上一版加 blink 微操后胜率没动 → 问题在产能不是微操」），这种记忆必须留在一个常驻 agent 里。

**更重要的：真正的瓶颈是验证成本，不是并行度。** research 用 5 个 agent 并行也只省几分钟；但如果不先把验证搞便宜，每改一次流派都得人盯一局，整个回路根本转不起来。**顺序比 agent 数量重要得多。**

---

## 3. 三个必须接受的现实（方案要落在这上面）

- **一局不算证据。** SC2 方差极大，对手/地图/种族一变结果就抖。必须**固定对手+地图，打 N 局，新旧 A/B 对比**。这是实验设计问题，agent 再多也救不了方差。
- **社区 build order 是给人用的**（按 supply/秒掐点、对抗人类微操）。可迁移的内核是「出什么兵 + 什么科技 + 什么升级 + 大致时机」，不是那些 supply 数字。社区研究有价值但**有上限**。
- **自评陷阱。** 写改动的 agent 有动机相信改动有效。对冲手段：①统计（N 局 A/B）②一个**对抗式 verify agent** 专门论证「这其实没用 / 只是对手这局弱」③偶尔人工抽查。

---

## 4. 推荐拓扑

```
                  ┌─ 主循环(常驻) ──────────────────────────────┐
   假设/迭代记忆 ◀─┤ 持有 baseline、决定改什么、写代码、判读结果  │─▶ 写代码(Edit/Write)
                  └──────┬──────────────────────────┬───────────┘
                         │ 派子 agent(只读/并行)      │ 派后台跑
                         ▼                           ▼
        ┌─────────────────────────────┐   ┌────────────────────────┐
        │ research 子agent × N        │   │ verify runner(后台)    │
        │ · 社区 build(spawningtool)  │   │ 打 N 局 → 聚合 W/L+曲线 │
        │ · aiarena 天梯流派          │   └────────────────────────┘
        │ · ares 上游 production 实现 │             │
        │ · 本仓库 git / CLAUDE.md    │             ▼
        │   (别重发现已知坑)          │   ┌────────────────────────┐
        └─────────────────────────────┘   │ adversarial verify     │
                                         │ agent(独立视角)        │
                                         │ "真提升 vs 噪声?"      │
                                         └────────────────────────┘
```

分工原则：

| 子活 | 归属 | 为什么 |
|---|---|---|
| research / Explore | **派子 agent**（只读、可并行、上下文隔离） | 这块用多 agent 真划算 |
| 综合 + 写代码 + 判读 | **留主循环** | 迭代记忆在这里 |
| verify | **后台 runner + 指标提取**（更像 harness） | 跑 detached，主循环继续 |
| 自评对冲 | **独立对抗式 judge agent** | 解决「写改动者自评」的偏差 |

---

## 5. 落地顺序（这个顺序本身就是杠杆）

### Phase A — 先造验证台【所有后续工作的前提】
- [ ] 实现 `on_end`：写一局结果 JSON（胜/负、用时、终局 army 编成）。
- [ ] 写一个 runner：**固定对手 + 地图**，连打 N 局，聚合 W/L + 军力曲线 / 存款峰值 / 主力何时成型何时死。
  **曲线录制复用现成的 `STEER_RECORD=<dir>`**（`steer.py` 每拍把快照存成 `state_<time>.json`，
  就是军力曲线；别去抓会被下一拍覆盖、被 `steer.reset()` 清掉的 live `state.json`）。
- [ ] 决定 headless 路线：要么**把 headless 稳住**（优先，能并行多局），要么**接受 REALTIME 但排队跑**。
- [ ] 定义晋升门槛 → 见 **§6**（难度阶梯 + smoke/series/回滚/审查触发）。

### Phase B — 测 baseline【要有「要打败的数」】
- [ ] tempest 流各打 N 局，拿数字。
- [ ] stalker 流各打 N 局，拿数字。
- [ ] 把数字写进本文件或 `CHANGELOG.md`，作为后续每轮改动的对照基线。

### Phase C — 改进回路【这才上多 agent】
- [ ] 主循环持假设 → research 子 agent（fan-out）喂候选改动。
- [ ] 主循环综合 → 写代码：**改 `flows.yml` 的流派配置**（P0 已落地：spawn/科技链/升级/chrono/
  追加产能/一次性建造都在这里）、`production_manager.py` 的机制逻辑（防御/前线塔/气矿节奏）、
  `stalker_offensive.py` 等微操——见 CLAUDE.md「约束」。
- [ ] verify runner 后台打局。
- [ ] adversarial verify agent 判「真提升 vs 噪声」。
- [ ] 反馈下一轮。

> **Phase A/B 不做好，Phase C 再多 agent 也是空转。**

---

## 6. 验证门槛：难度阶梯 + 晋升 / 回滚 / 审查触发

**固定变量（关键）。** 一个 series 内必须固定 **地图 + 对手种族 + AI build**，否则方差爆炸。`OPPONENT_RACE=Random` 会把种族相克性噪声塞进来——测试时固定单种族（或三种族各跑一组分别统计）。

**难度阶梯（python-sc2 `Difficulty` 枚举实测值，由低到高）：**

```
Medium → MediumHard → Hard → Harder → VeryHard → CheatVision → CheatMoney → CheatInsane
```

> 注意：枚举里**没有 Elite**（别和战网天梯段位搞混），VeryHard 之上直接是 cheat 三档。
> README 标注 bot 默认能赢 Hard；CLAUDE.md 提到 stalker 流在 Harder 崩过。所以 tempest baseline 估在 Hard~VeryHard，stalker 在 Hard~Harder。

**晋升 gate（分档收紧）：**

| 档位 | smoke 门 | 晋升 series | 门槛 | 说明 |
|---|---|---|---|---|
| Medium~Hard（快速档） | 连胜 3 局 | best-of-5 | 先到 3 胜 | 快迭代，统计松（真胜率 50% 的骰子 bot 也有一半概率过）—— 低档成本低，可接受 |
| Harder~VeryHard | 连胜 3 局 | N=10 | ≥7 胜（70%） | 误晋升率（对真胜率 50% 的 bot）≈17%；真 70% 的 bot 过 ≈65% |
| CheatVision 及 cheat 档 | 连胜 3 局 | N=20 | ≥14 胜（70%） | 收紧：高档边际提升小、误判成本高，多打降噪声 |

- **smoke 门**（连胜 3 局）：便宜的「这版没坏」信号，先于完整 series 跑，过滤明显坏掉的 build。连胜 3 局在真胜率 50% 时仅 12.5% 概率出现，能挡住骰子。
- **回滚**：新 build 在某 series 拿 ≤2/10（或对应低胜率）→ adversarial verify agent 判定后**自动回滚**到上一版 + 标记，不等人。
- **统计依据**：二项分布——「≥7/10」在真胜率 0.5 时概率 17%、0.7 时 65%、0.8 时 88%。学术 SC2 AI 评测（CIG/AIIDE/SSCAIT）常用 10–30 局/对阵，[CMU CHI'16 论文](http://www.cs.cmu.edu/~sjunikim/publications/CHI2016_LBW_Starcraft.pdf) 指出这个量级仍可能统计不可靠，所以高档我们收到 N=20。[AI Arena](https://aiarena.net/wiki/bot-development/) 天梯靠几百~上千局收敛 ELO——那是评分不是 gate，套到快速迭代太慢。

**人工审查触发（不按周期，按事件）：**

- **晋升触发**：跨过 VeryHard→CheatVision（即进入 cheat 档）→ `PushNotification` 推司令，附 series 统计 + 当版 diff + replay 路径。司令提的「到 cheat 难度就推送给人审」正是这条——打赢开挂 AI = 要么真强要么退化套路，都值得人看一眼。
- **异常触发**（不限档位）：adversarial verify agent 检出 ①回归（连输 3 局给曾稳定赢的档）②退化胜法（把把龟到 200/200 这类）③重复死循环 → 推人审。

---

## 7. research 子 agent 的具体信源（Phase C 用）

| 信源 | 拿什么 | 注意 |
|---|---|---|
| `lotv.spawningtool.com` | 人类 build order（按 supply） | 只取「兵种+科技+升级+大致时机」，别照搬 supply 数字 |
| `aiarena` / SC2AI 天梯 | 顶级 bot 的种族/兵种编成 | 看赢的 bot 出什么，不看人类 timing |
| `ares-sc2` GitHub + 其他 ares bot | **怎么在本框架表达一个 build**（production 范式） | 这是最直接可迁移的 |
| 本仓库 `git log` / `CLAUDE.md` / `docs/flows/` | **已知坑**（如 stalker 流 8 问题、idle 农民、漏升 blink）+ 已立项的流派方案 | 别让 research 重发现 |

---

## 8. 工具备忘

- research 阶段天然适合 fan-out：可用 **Workflow**（或 `deep-research` skill）并行派多个研究 agent，分头查，回来汇总。**需司令显式开口（「用 workflow」/ 开 ultracode）才调**，不主动调。
- verify runner 用 **Bash `run_in_background`** 跑 detached，`Monitor` 或轮询结果文件收尾。
- 对抗式 verify 用 **Agent**（独立子 agent、独立上下文）。

---

## 9. 决策结果（2026-07-18 司令拍板）

1. ✅ **验证台谁写**：**Claude 来写**（Phase A 本会话可直接接，有 Edit/Write/Bash）。
2. ✅ **headless**：见下方「headless 释义」；headless 路线 = `REALTIME=False` 快速档，Phase A 要把它在本环境稳住（`CLAUDE.md` 记录本环境不稳：websocket 超时）。
3. ✅ **N + 门槛**：Claude 调研后定，见 **§6**。初值：低档 best-of-5 先到 3 胜；中档 N=10 ≥7 胜；高档 N=20 ≥14 胜；前置 smoke = 连胜 3 局。
4. ✅ **先做哪条流**：**先 tempest**（README 官方方向、标「已验证」，baseline 估更高）；stalker 后做（刚大修完，baseline 在变）。
5. ✅ **人工审查频率**：不按周期，**按事件**——晋升到 cheat 档（CheatVision+）或异常检出时推送（见 §6）。

> **headless 释义。** SC2 里「无头(headless)」= 不渲染图形窗口、只跑模拟——快、不给人看、好批量连打 N 局，正是验证台想要的。本仓库用 `REALTIME=False` 当快速档（README 称「无头」，约 1–2 分钟/局），`REALTIME=True` 是 1x 可观战档。严格说 `REALTIME=False` 在本仓库仍可能弹窗、只是不限速；真正彻底无头要额外配置 SC2 二进制启动参数。Phase A 的活儿之一就是让这条快速档在本机稳定可连打。

---

## 10. 本文件相关

- 原始讨论：2026-07-18 会话（司令问「能否 self research/optimize/verify + 是否多 agent」）。
- 受约束于 `CLAUDE.md` 的「约束 / 踩过的坑」（spawn 比例和 ≈1.0、升级/流派配置的冻结测试、ares 是本地包等）。
- 流派体系：`ares-bot/flows.yml`（配置单一真相源，P0 已落地）+ `docs/flows/`（7 份流派方案，航母已落地待跑局）。
- 与 `docs/status-and-roadmap.md` 的「下一步」互补：那份是**功能**路线图，本份是**自调优工程回路**的方案。
