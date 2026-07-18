# 神族新流派方案总览

> 来源：2026-07 社区调研（SpawningTool 神族 build 库 / Liquipedia 神族 BO 分类 / TL.net 流派讨论），
> 按「零 APM、宏观杠杆、微操全归 bot」的架构筛选。**本目录只是方案，未合入代码**；
> 排期确定后按单份方案独立实施、独立验收，验收标准见各文件末节。
> 筛选时已排除依赖单位级精准施法的流派（使徒分身、干扰者瞄准、哨兵力场、凤凰抬人），
> 它们与 0-APM 架构天然相冲。

## 现状

- 已验证流派 1 个：`BUILD=tempest`（暴风舰天空体 + 先知骚扰，默认）。
- 骨架 1 个：`BUILD=stalker`（纯追猎 blink，代码落地但未跑局验证）。
- 流派入口：`spike_config.BUILD` 或 env `BUILD=xxx`，`run.py` 在 import 前写入
  `os.environ`，`production_manager.py` 在**模块导入时**读死——当前一局内不可切换。

## 共同前置（所有流派都依赖，建议最先做）

### P0 · 流派差异配置化（解锁后续一切）

现状：两个流派的差异**硬编码**在 `production_manager.py` 的 `if is_stalker_flow` 分支里
（spawn 配方 `_STALKER_SPAWN`、核心建筑链 `CORE_STRUCTURES` / `EXTRA_CORE_STRUCTURES`、
升级列表 `DESIRED_UPGRADES`、chrono 目标、一次性 oracle）。第三个流派会让 if 分支爆炸。

目标：流派差异全部进配置，按 flow 名选块（仿 `army_config._select_block` 的种族选块）：

- `army_composition.yml` 增加 per-flow 层（或新建 `ares-bot/flows.yml`）：
  `flow 名 → { units/spawn 配比, upgrades, core_structures, extra_structures, chrono 目标,
  一次性建造(如 oracle) }`。
- `production_manager.py` 按 flow 名选块，删掉所有 `is_stalker_flow` 分支；
  `_primary_unit_id()` / `_research_upgrades()` / `_chrono_structures()` 已读配置，顺势打通。
- `spike_config.BUILD` 变成只选「初始流派」；`bot_race_name` 同款回退（认不出 → tempest）。
- `build_meta.md` 扩成 per-flow 多段（frontmatter 按 flow_id 索引），SKILL.md 开局介绍按
  当前流派读对应段。
- 测试：`test_army_config` 增加 flow 选块用例；`test_combat_kinds_count`（冻结 12）只在
  新增 combat class 时才动。

### P1 · 局中切换流派（可选，依赖 P0）

steer 词表加 `flow=<名>` 杠杆（`steer_vocab.FIELDS` + 校验 + `gen_skill_vocab.py` 重生成
SKILL.md）。切换语义 = **只改之后造什么**：已造建筑/升级不回收（沉没成本），场上存量兵由
CombatManager 按 yml 逐兵种分派继续指挥（指挥侧本就流派无关，混编自动成立）。
切换时机由参谋长讲清（科技链交集省钱、分叉浪费）。

## 流派一览与排期建议

| 顺序 | 流派 | 方案文件 | 核心兵种 | 新增科技链 | 依赖 | 预计改动量 |
|---|---|---|---|---|---|---|
| 0 | stalker 验证（白捡） | （骨架已在仓库） | STALKER | twilight+blink | 只需跑局 | 0（跑局调参） |
| 1 | 航母黄金舰队 | [carrier-skytoss.md](carrier-skytoss.md) | CARRIER(+TEMPEST) | 复用暴风舰链 | P0 | 小 |
| 2 | 隐刀 DT | [dt-rush.md](dt-rush.md) | DARKTEMPLAR | twilight→darkshrine | P0 | 中 |
| 3 | 巨像地面流 | [robo-colossus.md](robo-colossus.md) | COLOSSUS+IMMORTAL | robo→robo bay | P0 + B0 | 中 |
| 4 | 提速叉白球 | [chargelot-archon.md](chargelot-archon.md) | ZEALOT+ARCHON+HT | twilight→templar archives | P0 + 合球行为 | 中大 |
| 5 | 4-gate/3-gate 一波 | [gateway-timing.md](gateway-timing.md) | STALKER/ZEALOT | warp gate 研究 | P0 | 小 |
| 6 | 凤凰+虚空 | [phoenix-voidray.md](phoenix-voidray.md) | PHOENIX+VOIDRAY | 复用星门链 | P0 | 小 |
| 7 | 修地堡 cannon rush | [cannon-rush.md](cannon-rush.md) | （建筑流） | forge | 独立 feature，不依赖 P0 | 大 |

排期逻辑：先白捡的（0），再复用度最高的（1），再接梗的（2），再补战略短板的（3、4），
B 级（5、6）看心情，cannon rush（7）是独立 feature 随时可插队。

## 每个流派的通用验收流程

1. 离线：`python -m unittest discover -s tests` 全绿 + `py_compile` + `gen_skill_vocab.py --check`。
2. 无头胜负：`REALTIME=False BUILD=<新流派> poetry run python run.py` 跑完一局出胜负（对 Hard 应能赢）。
3. 实机手感：`REALTIME=True` 看一局，记调优点（节奏/产能/微操），写进对应方案文件的「跑局调优记录」节。
4. 收尾：更新 `docs/status-and-roadmap.md`、`CHANGELOG.md`、README 流派表、`build_meta.md` 档案。
