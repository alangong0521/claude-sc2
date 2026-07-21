# code-agent-sc2

**用本地 Coding Agent 指挥《星际争霸 II》——一次 0 APM 的即时战略尝试。**

[🇬🇧 English](README_en.md) · 🇨🇳 中文

![截图：左边本地 Coding Agent 实时解读战况、给建议，右边是它指挥的自动驾驶 bot 在打](docs/hero.jpg)

*左边——本地 Coding Agent（图中是 Claude Code）当你的参谋长：读战况、报敌情、给选项（「开个分矿吧」）。
右边——它指挥的会自己打全场的 bot。你只用人话下达意图，它读战况、拉战略杠杆，你完全不碰微操。*

---

一个够强的 bot（基于 [ares-sc2](https://github.com/AresSC2/ares-sc2)）自己打完整局。对局中，
作为**司令**的你只用自然语言说**意图**（「派个农民侦查」「压他二矿」「转空军别送」），一个扮演
**参谋长**的 LLM 读实时战况、分析敌情、给你几个选项——等你**下令**后，把它翻译成一小组
**高层杠杆**。它从不微操单位。于是这是一个**零 APM 的 RTS**：你负责「指挥」，不负责「操作」。

本项目对外的官方方向是**神族（Protoss）**——Aristaeus 风格的**暴风舰天空体 + 先知骚扰**流派，
这条线已实机验证。底层是**种族无关 + 兵种配置化**的：一份 `army_composition.yml` 登记三族全部兵种，
生产（造什么兵）与指挥（每个兵种用哪套战斗微操）都从它读——**加一个兵种通常只改这份 yaml，不用动
Python**。人族、虫族的生产层，以及坦克架起 / 医疗船治疗空投 / 高模风暴 / 幽灵狙杀等专属微操，骨架均已
搭好（control-ready），但尚未逐一实机验证，详见 `docs/status-and-roadmap.md`。

```
   你(chat)  ──意图──▶  LLM 参谋长
                          │  读  state.json     （现在什么情况）
                          │  写  orders.json    （几个高层杠杆）
                          ▼
      ~/agent-rts-steer/   （两个 JSON 文件，原子替换）
                          ▲
                 ares bot │ 每 ~4 游戏秒：发布战况、读命令、应用
                          ▼
            星际争霸 II（免费客户端）  vs  内置 AI
```

五层结构：**SC2 免费客户端** ← **python-sc2** ← **ares 自驾 bot** ← **两个 JSON 文件**
（`~/agent-rts-steer/`）← **一套受约束的杠杆词表** ← **LLM 司令**。

## 为什么有意思

- **指挥 vs 操作。** 多数 RTS AI 在自动化微操，这个反过来：机器管操作，人（通过 LLM）出**战略**。APM ≈ 0。
- **LLM 实时在环。** LLM 不是赛前规划器——它读战争迷雾里的情报、口播威胁、在打团中途重新 steer，全靠文件信道。
- **接口极小、可读。** 整个指挥面就 ~10 个粘性字段（`stance / target / focus / build / scout / …`）。
  好读、好扩、**任何**会用工具的 LLM 都能驱动，不限于 Claude。

## 仓库结构

| 路径 | 作用 |
|---|---|
| `smoke.py` | Stage-0 探针：python-sc2 能不能拉起客户端打完一局？（裸 burnysc2，不用 ares） |
| `ares-bot/` | 真正的 bot + steer 层（Python 3.11 + Poetry） |
| `ares-bot/bot/main.py` | `AresBot` 子类：自己打全场 + steer 接缝 + 人机共驾让权 |
| `ares-bot/bot/managers/` | 三个 manager：`combat`（指挥军队）/ `production`（造兵运营）/ `oracle`（先知骚扰） |
| `ares-bot/bot/combat/` | 各兵种专属 combat class（借 ares 战斗原语）；无专属类的兵种走 `generic_offensive` |
| `ares-bot/army_composition.yml` | 兵种单一真相源（三族全兵种登记）；生产与指挥都读它，**加兵种改这里** |
| `ares-bot/flows.yml` | 流派单一真相源（spawn/科技链/升级/chrono/pivot 自适应，按 `BUILD` 选块），**加流派改这里** |
| `ares-bot/bot/flow_config.py` | 读 `flows.yml`、校验、回退 tempest |
| `ares-bot/bot/army_config.py` | 读 `army_composition.yml`、按种族分块、校验 |
| `ares-bot/bench.py` | **自调优验证台**：串行打 N 局（剥代理/随机图/失败重试），聚合 W/L + 曲线 + 每局自动复盘（retro.md） |
| `ares-bot/promotion.py` | **晋升矩阵 runner**：3 族 × 5 风格逐档打穿晋级（Medium→…→CheatInsane），断点续跑 |
| `ares-bot/bot/levers.py` | 操纵杆纯逻辑（语义→坐标/枚举的纯计算，可离线单测） |
| `ares-bot/bot/steer.py` | bot 侧：与 `~/agent-rts-steer/` 的原子 JSON 收发 |
| `ares-bot/bot/steer_vocab.py` | 共享杠杆词表（单一真相源） |
| `ares-bot/steer_cli.py` | 指挥 CLI：`state` / `set k=v` / `show` / `clear` / `vocab` |
| `docs/baselines.md` | baseline 数据 + 晋升矩阵全景 + 迭代日志 |
| `docs/pitfalls.md` | 踩坑总集（框架/环境/进程/UI/实验设计五类） |
| `docs/lever-map.md` | 操纵杆 → bot 动作 映射图（每个杠杆最终落到哪段代码） |
| `ares-bot/spike_config.py` | 一处管对局设置（难度 / 地图 / 种族 / realtime / 存 replay） |
| `ares-bot/run.py` | 启动入口 |
| `.claude/skills/sc2-claude/` | Claude Code「参谋长」技能（LLM 的行动手册） |
| `docs/` | 设计笔记与图片素材（README 配图） |

## 前置要求

- 已安装 **[星际争霸 II](https://starcraft2.com/)**（免费的 Starter Edition 就够）。
- **天梯地图**——下一个地图包放进 SC2 的 `Maps/` 目录（见 [sc2ai 地图 wiki](https://sc2ai.net/wiki/maps/)）。
- bot 需要 **Python 3.11 或 3.12** + **[Poetry](https://python-poetry.org/)**。
- **Git**。
- **macOS** 是主力测试平台。**Windows** 理论上开箱即用——每个编译依赖都有 Windows wheel，
  vendored 的 `sc2_helper` 也自带 `win_amd64` 版本——但还没实机跑过，详见下方 [Windows](#windows)。
  **Linux** 改一下 `MAPS_PATH` 即可。

## 安装

```bash
git clone https://github.com/Asklear/code-agent-sc2.git
cd code-agent-sc2/ares-bot
poetry install          # 装虚拟环境和依赖；首次要下载不少东西，会慢一点
```

> **关于 vendored 的 `ares-sc2`。** 仓库把 ares-sc2 整包放在 `ares-bot/ares-sc2/`，让 bot
> 自包含、可直接上传天梯。它为每个受支持的 Python（macOS/Linux/Windows）自带预编译的
> `sc2_helper` 二进制，所以 `poetry install` **不需要 C/Rust 工具链**。Poetry 的虚拟环境按
> **项目路径**定位——挪动目录后再跑一次 `poetry install` 重新关联（依赖已缓存，很快）。

## 跑一局

所有对局设置在 `ares-bot/spike_config.py`；任一设置都能用同名环境变量临时覆盖（单次跑用）。

```bash
cd ares-bot
# 实时观战，打 Hard 内置 AI，深海暗礁图：
REALTIME=True MAP=AbyssalReefLE DIFF=Hard OPPONENT_RACE=Random poetry run python run.py

# 无头快速看胜负（不限速，约 1–2 分钟）：
REALTIME=False poetry run python run.py
```

默认（不下任何命令）bot 自己就能赢 Hard 内置 AI。

**平台说明。** `run.py` 按操作系统自动选 `MAPS_PATH` 默认值（macOS 是
`/Applications/StarCraft II/Maps`，Windows 是 `C:\Program Files (x86)\StarCraft II\Maps`）。
若你的路径不同，用环境变量覆盖：`MAPS_PATH="/你的/StarCraft II/Maps" poetry run python run.py`。
Linux 无标准安装位置，必须设置 `MAPS_PATH`。

<a name="windows"></a>
### Windows

Windows 其实是 SC2 自动化支持最好的平台（python-sc2 本来就是 Windows-first）。bot 应能直接运行：

- 装 **Python 3.11 或 3.12**（别用 3.13——bot 锁了 `<3.13`）、Poetry、Git。
- `poetry install` 会为每个编译依赖拉 Windows wheel；vendored 的 `sc2_helper` 已带
  `cp311`/`cp312` 的 `win_amd64` 版本，因此**不需要 C/Rust 工具链**。
- 在 **PowerShell** 里跑（环境变量语法和 bash 不同）：
  ```powershell
  cd ares-bot
  $env:REALTIME="True"; $env:MAP="AbyssalReefLE"; $env:DIFF="Hard"; poetry run python run.py
  ```
- 结束一局：`taskkill /F /IM SC2_x64.exe`（Windows 上 SC2 进程叫 `SC2_x64.exe`，而 macOS 上是
  `SC2`），再停掉 `run.py` 的 Python 进程。

状态：已做静态验证（依赖全部可解析、路径平台感知），但尚未在 Windows 机器上端到端跑过。
你若试了，无论成败，欢迎提 issue 反馈。

**用代理？** 如果你的 shell 导出了 `HTTP_PROXY`/`HTTPS_PROXY`，SC2 客户端可能连不上本地。
在命令前加 `env -u HTTP_PROXY -u HTTPS_PROXY NO_PROXY=127.0.0.1,localhost …`。不用代理就忽略。

### Stage-0 smoke 探针（可选）

`smoke.py` 是个最简的「到底能不能拉起一局」检查，不用 ares，跑在独立的轻量环境
（Python 3.13 + burnysc2）。详见 `smoke.py` 文件头。

## 用 LLM 指挥它

bot 自己也能打。但**重点**是实时指挥它。

**用 Claude Code（开箱即用）。** 仓库自带一个技能 `.claude/skills/sc2-claude/`。用
[Claude Code](https://claude.com/claude-code) 打开本仓库，说一句*「当参谋长」*。Claude 会起 bot、
读战况、给你分析敌情、给选项——你**下令**后再拉杠杆。它遵守两条铁律：
**主动分析但绝不擅自下你没下过的命令**；你一旦下令，就**「回应 + 执行」同一次做完**。

**用任何别的 LLM（或手动）。** 接口就是个 CLI。游戏运行时：

```bash
cd ares-bot
poetry run python steer_cli.py state              # 读战况（bot 每 ~4 秒刷新）
poetry run python steer_cli.py set stance=attack target=enemy_natural note="压二矿"
poetry run python steer_cli.py show               # 看当前生效的命令
poetry run python steer_cli.py clear              # 清命令，回 bot 默认行为
poetry run python steer_cli.py vocab              # 列全部杠杆
```

命令是**粘性**的：下了一直生效，直到你改它或 `clear`。把任何会用工具的 LLM 指到这五条命令上，
它就能当参谋长。

### 杠杆词表

`steer_cli.py vocab` 会打印全集。神族指挥面速览：

| 你会说 | 杠杆 |
|---|---|
| 出击 / 撤 / 守家 / 龟一会儿 | `stance=attack \| retreat \| defend \| hold` |
| 打主基 / 二矿 / 绕后偷家 / 压中路 / 回家 | `target=enemy_main \| enemy_natural \| enemy_backdoor \| map_center \| home`（还有 `enemy_third/fourth`） |
| 集火攻城车 / 打农民 / 打最脆的 / 打最近的 | `focus=<兵种名 如 SIEGETANK> \| workers \| weakest \| closest` |
| 埋伏 / 占住高地 | `maneuver=ambush \| hold_position` |
| 先知骚扰 开 / 关 | `harass=on \| off` |
| 攒满再打 / 等他兵出去打 | `trigger=when_maxed \| when_enemy_away` |
| 开分矿 | `expand=yes`（= `build=nexus` 别名；一次只开**一个**矿） |
| 造某建筑 | `build=<结构>` 如 `stargate` / `assimilator` / `gateway`（选农民/选位置全归 bot） |
| 派侦查 | `scout=on`（只派一个农民，看完自己回家） |
| （混战）打哪家 | `enemy=E2`（焦点敌人；`E1`=离我最近，默认） |
| 全部拆掉 / 清图 | `set target= stance=attack`（清掉固定目标 → 自动巡场清干净） |

**人机共驾。** 你可以在 SC2 客户端里选中任何我方单位亲自微操；bot 每次操作让权 3 游戏秒，
你松手后无缝接管。

## 能打什么

- **1v1 打内置 AI**（默认）。
- 本机 **人 vs bot**、**bot vs bot**。
- **1 bot + N 电脑 FFA 大乱斗**开箱即用——设 `OPPONENTS=3` 并用 4 人图（如 `MAP=CactusValleyLE`）。
  参谋长会逐家报敌情；用 `enemy=E2` 切换焦点。
- 固定组队 / 我方多 bot / Battle.net 在线对战**不支持**。

## 观战与复盘

- bot 已设 `raw_affects_selection=False`，观战时不抢你的选择框。
- 常显血条：SC2 → Options → Gameplay → Show Unit Status Bars → **Always**。
- 在 `spike_config.py` 把 `SAVE_REPLAY=True`，每局会存到 `ares-bot/replays/`，双击有完整观战 UI。

## 现状与路线

已跑通：Stage 0（拉起一局）、Stage 1（bot 无指挥即胜 Hard 内置 AI）、Stage 2（实时 steer 闭环——
读 → 下令 → 应用 → 赢）。

**流派配置化（P0 已落地）**：`flows.yml` 是流派单一真相源（spawn/科技链/升级/chrono/追加产能），
加流派只改 yaml。当前三流：**tempest**（暴风舰天空体，已验证）、**stalker**（追猎 blink 流，骨架）、
**carrier**（航母黄金舰队，已验证）。`BUILD=<flow> poetry run python run.py` 切换。

**pivot 自适应（2026-07）**：天空流内置反 rush/反空军机制——2 分钟自动侦查；检测到 rush
（敌军压家或早期兵力异常）→ 自动出叉子顶 + 铺塔 + 全军守家，威胁解除自动复工；检测到对面
爆空军主力 → spawn 自动混入追猎，敌空军散了自动恢复。

**自调优回路（已运转）**：`bench.py`（串行打 N 局 + 聚合 + 每局自动复盘 retro.md）+
`promotion.py`（3 族 × 5 风格逐档打穿的晋升矩阵，断点续跑）。**已认证天花板**：
tempest 一路杀到 **CheatMoney 全穿**、CheatInsane 12/15（仅负三族 Rush）；
carrier 认证到 **Harder**、VeryHard 11/15（负于维京/凤凰/Rush）。数据全在 `docs/baselines.md`。

已落地（骨架，随时可扩）：兵种/流派**配置化**（`army_composition.yml` 三族全兵种登记，
生产 + 指挥都从它读）、**多兵种分派指挥**（`CombatManager` 按配置把各兵种交给对应 combat class）、
Terran / Zerg **生产层**（全走 ares 种族无关宏行为，绕开只支持 P/T 的 `ProductionController`）、
升级配置化、一批专属 combat class（坦克架起 / 医疗治疗空投 / 高模风暴 / 幽灵 / 渡鸦 / 女王 / 死神 / 感染虫）。
这些多为**离线骨架、尚未逐一实机验证**。

下一步：Zerg 的**女王注卵 + 铺菌毯**（爆兵与运营核心，目前女王只造不注）、各专属微操的实战手感调优、
更丰富的产能/扩张杠杆、robo-colossus 地面流（`docs/flows/` 排期）、侦查记忆、自动驾驶 advisor 模式。
见 `docs/status-and-roadmap.md` 与 `CHANGELOG.md`。

## 给司令的观察工具（`~/.kimi-code/bin/`）

- **`sc2watch [秒]`**：观察模式——把后台对局窗口钉在前台 N 秒，这期间小地图点击/拖动不被 macOS 吞掉。
- **`sc2cam <left|right|top|bottom|center>`**：合成点击把镜头切到指定方位（不受焦点争抢影响，稳定可靠）。
- 原理与坑见 `docs/pitfalls.md` D 类（bot 局小地图点击失灵的完整排查）。

## 参与贡献

见 [CONTRIBUTING.md](CONTRIBUTING.md)。欢迎 issue 和 PR。

## 关于我们 · 一起玩

这个项目是我们「让 Coding Agent 去玩点真东西」系列尝试的第一个公开 demo——我们准备用 Coding Agent
去折腾各种各样的 Agent 玩法，**游戏只是一个开始**（星际 2 是起点，不是终点）。


*左：交流群直入二维码（会定期过期，失效了就扫右边）。右：小澈的个人企业微信，随时有效。*

## 致谢

本项目站在《星际争霸 II》AI 社区的肩膀上：

- **[ares-sc2](https://github.com/AresSC2/ares-sc2)**（MIT）——bot 框架，本仓库 vendored 打包。
- **[ares-random-example](https://github.com/AresSC2/ares-random-example)**（MIT）——`ares-bot/`
  fork 自这个模板。
- **[python-sc2 / burnysc2](https://github.com/BurnySc2/python-sc2)**（MIT）——SC2 API 绑定。
- 神族 build 的战术思路借鉴了开发期研究过的社区 bot（Aristaeus、12PoolBot、QueenBot、BruceBot 等）。
  它们的代码**不**随本仓库分发——见 `NOTICE`。

## 许可

[MIT](LICENSE)。打包的上游组件各自保留其许可（见 `NOTICE` 与 `ares-bot/LICENSE`）。
《星际争霸 II》为暴雪娱乐产品；本项目与暴雪无关联、未获其背书，你需自行拥有游戏并接受其 EULA 才能运行。
