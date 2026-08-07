# claude-sc2

SC2 bot（神族 Aristaeus），基于 [ares-sc2](ares-bot/ares-sc2/) 框架。核心模式：**参谋长(LLM / `steer_cli`)下令，bot 执行**——司令(用户)零 APM，靠 steer 命令指挥。

## 当前验证模式（司令 2026-08-06 最终口径，O216e 更新）

> **2026-08-06 司令确认（O216e 重启前）**：下局及后续所有正式 bench 强制走 **headless（`REALTIME=False`）+ 双车道 SC2 并行**。本节作为项目记忆，每次迭代前重读；`REALTIME=True`/单车道仅用于双车道崩溃排查或司令临时观战，不作为默认验证。
>
> **O216e 双车道计划**：Lane1 `o216e-vh-zerg-timing-abyssal`（AbyssalReefLE）与 Lane2 `o216e-vh-zerg-timing-paladino`（PaladinoTerminalLE）按 headless 双车道后台启动，命令不带 `--realtime`，SC2 进程以 `-displayMode 0` 无渲染运行。启动前必须 `pkill -9 -x SC2` 清理残留进程；两条 lane 错峰 20-30s，先起 Lane1，SC2 完成授权/监听后再起 Lane2，避免实例冲突崩溃。
>
> **人机共驾 / 观战模式定义**：凡 `REALTIME=True` 或人工在 SC2 窗口内输入指令（移动镜头、施放技能、点单位）即属人机共驾；O216e 及后续为 `REALTIME=False` 且 bot 自主决策，仅因 macOS 窗口管理偶发显窗，本质上仍是 headless 后台加速。
>
> **司令观察（O216d 验证期）**：仍有农民前期干等着造建筑，没有采矿最大化。已记录为持续优化方向：核心科技建筑/追加产能的派工需引入 `dispatch_viable` 收入守卫（当前仅 F2 塔与扩张使用），避免农民被派去造暂时买不起的建筑而空转。

## 当前验证模式（司令 2026-08-06 最终口径，O216 续接）

> **2026-08-06 司令最终确认（O216 启动前）**：当前 O216 及后续所有正式 bench 强制走 **headless（`REALTIME=False`）+ 双车道 SC2 并行**。本节作为项目记忆，每次迭代前重读；`REALTIME=True`/单车道仅用于双车道崩溃排查或司令临时观战，不作为默认验证。
>
> **O216 双车道实况**：Lane1 `o216-vh-zerg-timing-abyssal`（AbyssalReefLE）与 Lane2 `o216-vh-zerg-timing-paladino`（PaladinoTerminalLE）已按 headless 双车道后台启动，命令未带 `--realtime`，SC2 进程以 `-displayMode 0` 无渲染运行。若窗口短暂闪现后被 `_hide_sc2_windows()` 隐藏属于正常启动动画，不构成「人机共驾」。
>
> **人机共驾 / 观战模式定义**：凡 `REALTIME=True` 或人工在 SC2 窗口内输入指令（移动镜头、施放技能、点单位）即属人机共驾；O216 当前为 `REALTIME=False` 且 bot 自主决策，仅因 macOS 窗口管理偶发显窗，本质上仍是 headless 后台加速。

## 当前验证模式（司令 2026-08-06 最终口径，O206c 后）

> **2026-08-06 司令最终确认（O214 重申）**：下局及后续所有正式 bench 强制走 **headless（`REALTIME=False`）+ 双车道 SC2 并行**。本节作为项目记忆，每次迭代前重读；`REALTIME=True`/单车道仅用于双车道崩溃排查或司令临时观战，不作为默认验证。
>
> **2026-08-06 司令再次确认（O215 续接）**：当前 O215 及后续所有正式 bench 继续强制 **headless（`REALTIME=False`）+ 双车道 SC2 并行**；已启动的 O215 双车道（AbyssalReefLE / PaladinoTerminalLE）即按本模式后台运行，非人机共驾。
>
> **O214 当前运行实况**：O214 Zerg Timing bench 已按本模式启动，两条 lane（AbyssalReefLE + PaladinoTerminalLE）均为 `REALTIME=0` headless 后台加速，无人工输入；SC2 窗口仅作为视频输出显示，不构成「人机共驾」。后续 O215 及所有 bench 继续强制本模式。
>
> 启动前必须执行 `pkill -9 -x SC2` / `bench.py` 的 `_cleanup_stale_sc2()` 清理残留 SC2 进程；双车道启动时两条 lane **错峰 20-30s**（先起 Lane1，SC2 完成授权/监听后再起 Lane2），避免 SC2 访问许可冲突导致第二个实例崩溃。单局内精确跟踪本局 SC2 PID，检测 60s 未启动 / 崩溃 / 90s 无 snapshot 更新即判定卡死并杀进程重试。
>
> 若双车道反复崩溃/卡死，先杀进程再重启；仍不稳时临时降级 `REALTIME=True` 单车道观战排查，但需记录并继续修复稳定性，不能长期停留单车道。
>
> **2026-08-06 O212 更新**：O211 Zerg Rush 双车道 bench 已按本模式完成（Abyssal/Paladino 各 3-2 打穿）；O212 及后续继续强制 headless + 双车道并行，不允许以人机共驾/观战模式作为默认验证。
>
> **2026-08-06 O213 司令确认**：下局及后续所有正式 bench 继续强制走 **headless（`REALTIME=False`）+ 双车道 SC2 并行**。若出现单车道/人机共驾/观战模式，只能是双车道崩溃排查或司令临时观战，排查完必须切回 headless 双车道，不能长期停留。O212 期间因双车道稳定性问题曾临时降级观战排查，现稳定性已恢复，回归默认验证模式。

## 当前验证模式（司令 2026-08-06 最终口径）

> **2026-08-06 司令再次确认（O206c 重启前）**：下局及后续所有正式 bench 继续强制走 **headless（`REALTIME=False`）+ 双车道 SC2 并行**。本节已作为项目记忆，每次迭代前重读。
> **2026-08-06 司令确认**：所有正式 bench 必须 **后台 headless（REALTIME=False）+ 双车道 SC2 并行**，不允许以人机共驾/观战模式作为默认验证；单车道/REALTIME=True 仅用于双车道崩溃排查或司令临时观战。
> **2026-08-06 O206c 更新**：`ares-bot/bench.py` 的 SC2 CPU 冻结检测在双车道 headless 下连续误杀正常对局，已禁用；真卡死由「状态快照停滞 180s」+「游戏时间停滞 150s」+「进程异常退出检测」兜底捕获。
> **2026-08-05 23:46 司令确认**：下局及后续所有正式 bench 继续强制走 **headless（`REALTIME=False`）+ 双车道 SC2 并行**。本节已作为项目记忆，每次迭代前重读。
> **2026-08-05 23:29 再次确认**：下局及后续所有正式 bench 统一走 **headless（`REALTIME=False`）+ 双车道 SC2 并行**。本节已作为项目记忆，每次迭代前重读。
> **2026-08-05 追加确认**：下局及后续所有正式 bench 统一走 **headless（`REALTIME=False`）+ 双车道 SC2 并行**。本节已作为项目记忆，每次迭代前重读。
> **2026-08-05 17:12 项目记忆更新**：O195 因 Rush game_01 败北已中断，O196 仍按 headless + 双车道并行重启；每次失败先尸检并落地 ≥3 个改进点再开下一组。

- **所有正式 bench 必须同时满足**：
  1. **headless**：`REALTIME=False`（非观战/非排查场景）。
  2. **双车道并行**：同一时刻开两条 lane 跑不同组合或对照，最大化迭代速度；单车道仅作为双车道临时故障时的降级或观战排查。
- 启动前必须调用 `pkill -9 -x SC2` / `_cleanup_stale_sc2()` 清理残留 SC2 进程；单局内精确跟踪本局 SC2 PID，检测 60s 未启动 / 崩溃 / 90s 无 snapshot 更新即判定卡死并杀进程重试。
- 若双车道反复崩溃/卡死，先杀进程再重启；仍不稳时临时降级 `REALTIME=True` 单车道观战排查，但需记录并继续修复稳定性，而不是长期停留单车道。

- `ares-bot/bot/`：我们的代码（**改动重点**）
- `ares-bot/ares-sc2/`：ares 框架（本地子包，**尽量不改，用其原语**）
- `steer_cli.py` / `bot/steer_vocab.py`：参谋长指挥 CLI + 命令词表（单一真相源）
- 参谋长玩法见 `.claude/skills/sc2-claude/SKILL.md`；流派档案见 `ares-bot/build_meta.md`
- `docs/battle-log.md`：司令观战问题记录，局中只记录，**打完统一优化**

## 流派（BUILD env，开局前锁定）
`BUILD=tempest|stalker|carrier`，**启动参数**，不能局中换。流派配置在 `ares-bot/flows.yml`（spawn/科技链/升级/chrono/追加产能/一次性建造/save_up 憋气/动态开矿/分矿塔数，单一真相源），加载/校验在 `bot/flow_config.py`。
- `run.py` 在 `import bot.main` **之前** setdefault BUILD 并调 `FlowConfig.load` 归一（未知名警告并回退 tempest）；`production_manager` 在 `__init__` 才读，不再模块级锁定。
- 切换：`BUILD=carrier poetry run python run.py`（在 `ares-bot/` 下）。

## 关键架构（改动热点）
- **`bot/managers/production_manager.py`** — Protoss macro 主战场。流派差异已全部进 `flows.yml`（P0 配置化），本文件只剩机制逻辑。`update()` 每帧注册 macro behaviors。**改机制（产能逻辑/防御/前线塔）在这，改流派数值去 `flows.yml`**。
- **`bot/managers/combat_manager.py`** — 战斗分派。`attack_target` property（解析 steer target 成 Point2）+ 按 `army_composition` 的 `by_role("ATTACKING")` 分派 combat class。
- **`bot/combat/stalker_offensive.py`** — 追猎 blink 微操。
- **`bot/combat/carrier_offensive.py`** — 航母专属微操（O12/O14）：射程内有敌就 `AttackTarget` 放机（**严禁 StutterUnitBack——cy_attack_ready 对无常规武器的航母恒 False，会恒走逃跑分支**，E4d 二分判决实证），锚点只决定赶路站位（地形高差+对空威胁圈避让+当前位置滞回），残血 <40%/≥55% 滞回后撤。army_composition.yml 的 combat 键接线，加新 combat 类要同步 `bot/army_config.py` 的 COMBAT_KINDS 与 combat_manager 分派表（test_army_config 有数量冻结）。
- **`bot/steer_vocab.py`** — 命令词表（`FIELDS` + `_FIELD_VALUES`），bot 和 steer_cli 共用，加命令只改这里。

## ares 原语（优先复用，不改框架）
- `UpgradeController(upgrades, base_location)` — 研究升级 + 打 `logger.info`。**神族路径用 `auto_tech_up_enabled=False` + `prioritize=True` 并放进 MacroPlan 的 SpawnController 之前**（O8：研究就绪但买不起时截断 plan 攒钱给研究）；**`rush_active` 期间不注册**（E3 回归：预留会饿死 rush 响应包，`research_paused_for_rush`）；前置科技建筑改由 `_build_core_structure`（can_afford 守卫）补建，否则 ares `TechUp` 不查存款就把农民钉在建造点干等（O1 实证）；`required_building`（如盾 L2 的暮光议会）只在同线上一阶完成后补建（`upgrade_tech_buildings(done=)`，O10）。注意：当前 melee 无航母容量/弹射升级可研究（coop 残留枚举）。
- `AutoSupply(base_location)` — 补 pylon。**不查 can_afford**（O6 实证）→ 常态只在 `can_afford(PYLON)` 时注册，**supply_left ≤ 2 的紧急态除外**（E3h：缺钱屏蔽水晶会卡人口，`should_register_autosupply`）；**进 MacroPlan 必须 `return_true_if_supply_required=False`**（E3g 实证：默认 True 会在 supply 紧张期每帧截断 plan，饿死后面的研究/生产）。
- `Mining(mineral_boost=False)` — **必须关加速采矿**（O7 实证）：开着你每农民每往返 2 条 move+SMART，主矿区满屏点击。
- `ProtossStaticDefence(photon_cannons_per_base, shield_batteries_per_base, ...)` — 自动每基地铺 pylon+光子炮+护盾电池 + 建 forge。
- `SpawnController(army_composition_dict, spawn_target=)` — 造兵，`spawn_target` 控折跃位置（WarpInManager 按距离选最近电源）。
- `TechUp(desired_tech)` — 自动补兵种所需科技建筑。

## 2026-07-18 stalker 流大修（8 问题，分两批）
实战 stalker 流 vs Harder 崩盘暴露 8 问题。3 个 Explore agent 查清根因，分两批改。

### 第一批：核心 bug（决定胜负）
| 项 | 根因 | 改法 |
|---|---|---|
| **B1 idle 农民** | ares `BuildStructure` 不查 `can_afford`，农民到建造点干等（`Mining` 只管 GATHERING role） | `production_manager` 每处 `register_behavior(BuildStructure)` 前加 `can_afford` 守卫（开局 pylon + `_build_core_structure`） |
| **B2 兵营产能**（矿堆 3000+） | Protoss 分支没注册 `ProductionController`，`_build_core_structure` 防重让 gateway 永远封顶 1 | 新增 `_build_extra_gateways`（仿 `_build_extra_stargates`，按存款扩，封顶 8），stalker 流也调用 |
| **B3 科技升级**（漏 blink/攻防） | 手写 `_research_upgrades` 三 bug：气体门槛要 310 气 / 不建 FORGE / 无日志 | Protoss 改走 `UpgradeController`（照抄 Terran 189-190 范例）+ 扩 `DESIRED_UPGRADES`（stalker 加 WARPGATERESEARCH/blink/地面武器/装甲/护盾 L1；tempest 加护盾 L1） |
| **B4 zealot 混编** | `_STALKER_SPAWN` 硬编码纯追猎 | `{STALKER:0.7, ZEALOT:0.3}`（比例和=1.0；zealot 只需 GATEWAY，combat 自动指挥零改） |

### 第二批：feature
- **F1 前线折跃**（最小方案）：`SpawnController(spawn_target=_front_point())`（敌我中点偏敌 60%）+ `_build_forward_pylon`（warpgate 研究后造前线水晶塔）。⚠️ 前线塔易被打，完整方案会用 warp prism。
- **F2 防御塔**：注册 `ProtossStaticDefence(photon_cannons_per_base=2, shield_batteries_per_base=1)`，`_should_build_defense`（`defend=yes` 手动 / >6 分钟自动）。steer_vocab 加 `defend` 字段。
- **F3 微操 6 项**（`stalker_offensive.py`）：①blink 帧先 `AttackTarget` ②够不着改 `PathUnitToTarget` 追击（原 StutterUnitBack 后撤是 bug）③全队集火同一 target ④进攻型 blink（残血/高价值 caster 贴脸）⑤blink 躲技能（检测 HIGHTEMPLAR/INFESTOR 等）⑥射程点杀保持阵型。门限改 `@dataclass` 字段，默认 `focus=weakest`。

## 开局流程（每次跑局前必做）

启动前检查清单（每次跑局前必做）：

1. **血条设置**：确认 `~/Library/Application Support/Blizzard/StarCraft II/Variables.txt` 里
   `displayunitstatus=Damaged`（不是就改过来再启动；客户端有时会被局内操作改回别的值）。
2. **请示司令**：用结构化提问逐项确认五项（AskUserQuestion，每项给选项），按选项组装环境变量启动。
   **提问顺序固定：流派 → 难度 → 风格 → 种族 → 地图**（风格紧跟难度问）。
   提问工具每题限 4 个选项，**难度和风格必须列全，用两段问法**：
   - 难度（**严格按 Hard→Cheat 升序列**：Hard / Harder / VeryHard / CheatVision /
     CheatMoney / CheatInsane）：第 1 题 `Hard / Harder / VeryHard / Cheat 档`，
     选 Cheat 档再问第 2 题 `CheatVision / CheatMoney / CheatInsane`；
     司令想要更低难度走 Other 自填。
   - 风格（5 种 + 随机列全）：第 1 题 `Macro / Rush / Timing / 其他`，
     选其他再问第 2 题 `Power / Air / 随机(RandomBuild)`。

| 项 | 环境变量 | 选项 |
|---|---|---|
| 流派 | `BUILD` | `tempest`（最强，认证至 CheatInsane）/ `carrier`（认证至 VeryHard）/ `stalker`（攻坚中，0 胜率） |
| 难度 | `DIFF` | Hard / Harder / VeryHard / CheatVision / CheatMoney / CheatInsane（更低档 VeryEasy~MediumHard 不常问，司令自填） |
| 对手风格 | `AI_BUILD` | Macro / Rush / Timing / Power / Air / RandomBuild（随机） |
| 对手种族 | `OPPONENT_RACE` | Terran / Zerg / Protoss / Random |
| 地图 | `MAP` | 随机（**排除 HonorgroundsLE**）/ AbyssalReefLE（baseline 固定图）/ BelShirVestigeLE / CactusValleyLE（4 人混战图）/ NewkirkPrecinctTE / PaladinoTerminalLE / ProximaStationLE（⚠️ HonorgroundsLE 会崩 PlacementManager，勿选） |

示例：`REALTIME=False BUILD=carrier MAP=AbyssalReefLE DIFF=Medium OPPONENT_RACE=Random AI_BUILD=Macro poetry run python run.py`（验证走 headless；观战/排查才用 `REALTIME=True`）

## 对局后检查（每次对局结束必做，司令指令 2026-07-23）

1. **idle 建造农民检查（O19）**：每局结束后检查日志/快照，确认是否有农民
   **>3s 不干活干等建造**（等钱、钉点、无指令）。bench 走 retro 检测器
   （`idle_builder` 标签）；观战局手动查 state 快照。
   发现 → 记 battle-log 并优化建造顺序与拉农民建造的 timing。
   （阈值 1s→3s：o19 复验数据实证 1-2s 短等是贴 0 花钱风格常态噪声，
   3s 仍 < O11 watchdog 6s 撤回线，真钉点必曝光——司令 2026-07-24 拍板。）
2. 其余 retro 标签照旧（supply_block / one_base / overrun / trickle / bank / stall）。

## 约束 / 踩过的坑
- **升级改动走 `flows.yml` 的 flow.upgrades**（神族生产已不读 `DESIRED_UPGRADES`，该常量已删）；`army_composition.yml` 的 protoss.upgrades 仍被 `tests/test_army_config.py::test_shipped_protoss_upgrades_unchanged` 锁（T/Z 路径还在读它）；flows.yml 的 tempest/stalker 块被 `tests/test_flow_config.py` 的 shipped 测试冻结。
- **spawn 比例和必须 ≈ 1.0**——`flows.yml` 与 `army_composition.yml` 同一约束（加载时各自校验）。
- **ares-sc2 是本地包**——`import ares` 需 `sys.path` 加 `ares-sc2/src`（`run.py:14-16`）；离线编译检查也要加。
- **headless `websocket 超时`/SC2 启动崩溃**——SC2 更新中 / 冷启动慢会导致；用 REALTIME 或等 SC2 ready。~~headless 本环境不稳，优先 REALTIME~~（已更新：司令 2026-08-05 指示后续验证走 headless，当前 headless 默认 `REALTIME=False`）。
- **headless + 双车道并行验证（司令 2026-08-05 最终口径）**——后续正式 bench 默认 `REALTIME=False`（headless），并同时开两条 lane 跑不同组合/对照，最大化迭代速度。O180 曾在 `ares-bot/bench.py` 加启动前清理、进程树级 SC2 检测、崩溃/卡死检测与自动重试；单车道串行仅作为双车道临时不稳时的降级，或观战/快速冒烟场景使用。若双车道出现 SC2 进程卡死/崩溃/残留进程冲突，先 `pkill -9 -x SC2` 清理，再重启双车道；反复出现时降级单车道并排查端口/实例隔离。
- **bench 启动前清理残留 SC2 进程（O180）**——之前中断/卡死的 SC2 会占端口/资源，导致新实例启动即崩溃（`Blizzard Error Report ID: 00000000...`）。`ares-bot/bench.py` 启动时 `_cleanup_stale_sc2()` 会杀掉存活 >5 分钟的残留进程；单局内用 `_sc2_pid_for(run.py_pid)` 精确跟踪本局 SC2，新增启动检测（60s 未出现则放弃）、SC2 进程存活检测（崩溃立即放弃）、状态快照停滞检测（90s 无新 snapshot 判定卡死并杀进程）。
- **SC2 补丁日首发失败**（2026-07-18 实证）：当天补丁（如 Base97563）后 SC2 二进制能起进程但**不开 websocket、不出窗口、静默退出**，新旧 build 都一样 → 不是 bot 问题，去 Battle.net 让它完成更新 / 「扫描和修复」，确认手动能进游戏后再跑 bench。排查手法：直启二进制 `-listen 127.0.0.1 -port <p>` + `lsof -iTCP:<p> -sTCP:LISTEN`；多实例互斥会互相踢，先 `pkill -9 -x SC2` 再测。
- **idle 农民**：ares 框架层 `BuildStructure`/`TechUp` 不查 `can_afford`（bot 层加守卫根治：BuildStructure 注册点 + 升级前置建筑全走 `_build_core_structure`）。**TechUp 已加 can_afford 守卫（2026-07-23 修复）**：在 `ares-sc2/src/ares/behaviors/macro/tech_up.py` 两处添加 `can_afford` 检查（第 128 行和第 180 行），防止农民被钉在建造点等钱（Forge 建造实证：两个农民等钱造 forge）。**O19 派工守卫（2026-07-24）**：`dispatch_viable(矿, 收入/秒, 走位时间, 造价)` 到位可负担才派——F2 防御塔注册点（治 PHOTONCANNON 钉点 9-21 次/局）和 E3k 开矿预走位收窄（治 NEXUS 干等；攒钱预留语义不变）；**二轮（o19fix 复验）**：收入高时守卫恒真 →「派工→钱被抽干→钉 6s→O11 撤→又派」循环，加 `redispatch_cooled_down`（O11 撤回后 15s 冷却，F2 门读取）；**idle_builder 检测阈值 1s→3s**（复验实证 1-2s 短等是存款贴 0 风格下的常态噪声，3s 仍 < O11 6s 撤回线）；ares build runner 开局序列派工仍无守卫（框架层不改，O11 watchdog 兜底）。另有 `main._handle_idle_workers` 每 1 游戏秒兜底清扫（跳过侦查/司令接管/采集中的农民）；tracker 里钉点 >6s 且买不起的建造工人会被拆 tracker 撤回（O11 watchdog，例外=人口紧急态水晶、基地建筑 TOWNHALL_TYPES、**rush_active 期间全部**——E4c 实证：rush 矿紧时撤回循环会让塔永远起不来）。**气矿优先级最高（O13）**：`_ensure_expansion_gas` 每帧在追加产能/滚雪球之前跑，每个就绪基地双气满采，在建气矿 45s 不落地拆 tracker 重派。**司令接管**靠的是 PERSISTENT_BUILDER role + `release_from_build_tracker` 摘除 ares building_tracker（BuildingManager 无视 role，只换 role 抢不回单位，O2 实证）。
- **bot 局小地图点击"失灵"**（2026-07-19 结案）：四层叠加——①窗口非键窗时点击被当"激活"吞掉（先点主画面）；②AI 投降弹窗是模态框挡全部输入（gg 聊天型 bench 自动点 Yes；静默型手动点）；③全速模拟下离散点击被间歇性丢弃；④**主因:并行车道新局开窗每几分钟抢一次键窗,观看窗口被降级,点击被当激活吞掉(开窗期失灵、安静期好使)**。**观察方案:`sc2cam <left|right|top|bottom|center>`(~/.kimi-code/bin/,合成点击切镜头,可靠),或边缘平移(可在游戏内调低滚动速度)**。判别手法：手动开一局 vs AI 能点 = bot 局特有。
- **warpgate 必须自己变形**：`SpawnController.execute` 在 WARPGATERESEARCH 完成后**停产等 gateway 变形**（`return False`），而 ares 没有变形行为——不自己下 `MORPH_WARPGATE` 就永久停产（`production_manager._morph_gateways` 根治）。
- **多兵种 SpawnController 必开 freeflow**：配比是**上限**不是目标——精确配比点全兵种都 ≥ 目标 → 全停产（配比死锁）；且 freeflow 下**首优先兵种若永远可负担会饿死其他兵种**（C5a 实证：zealot p0 → 0 追猎）。单兵种流派靠 `over_produce_on_low_tech` 豁免不用开。freeflow 的镜像坑：p0 **买不起**就 fall-through 喂饱 p1（O5 实证：风暴吃光气攒不出航母）→ carrier 用 `save_up` 憋气机制（`production_plans.save_up_spawn`）截断。
- **carrier 动态多矿（E2）**：`auto_expand` 配 `max_bases` 走动态模式——爆仓（农民 ≥ `when_workers`×基地数）或前线优势（我方 army supply ≥ 敌可见 + `advantage_supply`，**E4b 起敌可见必须先 >0**：0 可见不是优势是未知，迷雾藏兵曾致假优势裸奔+预留停产）逐矿 +1，rush 期间不开；`expansion_cannons` 让 `ProtossStaticDefence` 塔数动态（`min + 敌可见作战单位//4`，封顶 `max`，每帧重算）；星门追加有气体闸门（目标 = min(cap, 满采气基地数 + 1)，满采=该基地 2 个 ready assimilator；+1 因气有存款可爆兵、风暴耗气更慢——司令 2026-07-21 口径）。旧式 `auto_expand {at,to,when_workers}`（stalker）不受影响。
- **carrier 侦查决策闭环（O9+E7）→ 集结纪律（E8）→ 策略 pivot（E10）**：t≈170s 评 `scout_verdict`（早出兵建筑≥2 或早期**作战**敌兵≥6→rush；否则 greedy 维持贪打法；P1 起作战单位口径=`is_combat_type`，排除 OVERLORD/OVERSEER/OVERLORDTRANSPORT 侦查运输，QUEEN 保留——旧口径 Zerg Macro overlord 铺开必误判 rush），rush/unknown 直接置 `_rush_active` 复用响应包并撤回 SCOUTING 农民。E7（O16 断链修复）：verdict 时机走 `scout_verdict_timing`——无情报但探机还在路上→宽限到 230s；探机死/被 O4 提前撤回且非 rush→**补派一次**（仅一次，rush 中不补派）；硬底线仍无情报→才按「尽力未送达」保守 rush。E8（O17/O18）：结论存 `production_manager.verdict`，combat_manager 的 C3a 阈值每帧过 `rally_min_for_verdict`——greedy 减半、rush 收紧到 max(×2, 6)、unknown/None 维持；司令 stance 让位不动。E10（策略 pivot，spawn 层）：verdict=greedy → 舰队成型前风暴主 C（`pivot_primary_id`/`tempest_primary_spawn`，priority 对调 proportion 保留），`carrier_transition_ready`（时间 600s 或风暴×10）一次性转回航母终结；rush/unknown/未判定 → 不 pivot（保守默认）。**P2 产能解放（仅 pivot 生效）**：追加星门豁免矿>400 门槛（`extra_production_mineral_gate`）、气体闸门 +2（`stargate_gas_gate_bonus`，单矿 2→3）、chrono 主 C 认 TEMPEST（`chrono_primary_id`）；非 pivot 三处全走默认值。只挂 carrier，tempest/stalker 基线不动。
- **rush_active 六连动（E3b/E3d）**：①不注册 UpgradeController（研究让位，E3-R1）；②`spawn_target` 切回主基（不前线折跃进敌群）；③`_should_build_defense` 立即铺塔（不等敌兵压 40 格，`rush_triggers_defense`，臂 B `rush_cannons:false` 除外）；④暂停科技链/造农民/追加产能/滚雪球/前线塔，升级建筑只保 FORGE（E3d 矿饥荒实证）；⑤`shield_batteries_per_base=0`（电池要核心，`_tech_required` 会阻塞整条塔链）；⑥敌兵>叉子数时追加 gateway（`rush_needs_gateway`，单兵营 28s 一叉是瓶颈）。
- **基地被打掉后重建（O20，2026-07-23 修复；2026-07-24 Macro 修正）**：当"当前基地数 < 目标基地数"时（如 2 矿被打剩 1 矿），触发类似 E3k 的攒钱预留模式 —— 暂停 SpawnController（**造农民已于 2026-07-24 解除截断**：o19b-macro 五局实证，丢矿后重建模式锁 100-300s，掐农民=掐重建经济来源，农民放血零补员恶性循环；rush 的 E3d 让位与 E3k 短预留保留），优先重建 Nexus。触发条件：`base_rebuild_active(current_bases, peak_bases, target_bases, can_afford_nexus, rush_active)`（峰值门：开局 1<max_bases 不触发），目标基地数来自 `auto_expand.max_bases`。相关代码：`production_plans.py:base_rebuild_active`，`production_manager.py:update()` 头部计算 `_base_rebuild` 标志位，截断点集成（SpawnController/ExpansionController）。**另：Macro 局塔重建限流（同日）**：`cannon_target_capped`——矿 < 舰队矿价且非 rush 时 expansion_cannons 目标压回 min（塔矿出血≈7 艘航母/局实证），rush 期不限。**E9 中局威胁响应（同日二轮，carrier）**：`threat_response_active`（敌可见 supply ≥ max(10, 我方×1.5) 激活、< max(6, 我方×1.0) 滞回解除）——激活时塔目标=ec.max（覆盖限流）、save_up 不截地面防御兵种（`threat_ground_exemption`）；开矿阻断走 `expansion_blocked`（B1：rush 恒停、非 pivot 按 threat 停、**pivot 模式改「敌压家 40 格」才停**——threat 在 Macro 局常驻曾致二矿开不出）；与 rush 同时激活按 rush 走。
- **基地清零重建（O15）**：`townhalls==0` 时 MacroPlan 只留 AutoSupply（研究/出兵/开销块全停，攒钱 400 重建，优先级 > save_up）；主矿干则 `ExpansionController(to_count=1)` 找新矿；Q5 判负豁免条件=有工人且场上还有矿且**存款 ≥400**（`nexus_rebuild_viable`，E4 实证：0 基地=零收入，存款不够就是死局，豁免会空转垃圾时间）。
- **农民被抄转移（E6）**：`main.update_worker_evacuation` 每帧跑——敌地面 ≥4 进某基地 Nexus 15 格视为被抄；有就绪塔（距 Nexus ≤9）且敌 <6+4×塔数则不撤（塔罩得住），**敌 ≥6+4×塔数=塔被压垮照撤**（bench 实证：22 狗+9 蟑螂波 ~20s 拆光塔再屠农，塔覆盖≠安全），无塔即撤；撤离农民挂 `CONTROL_GROUP_ONE` role（脱离 Mining/派工/idle 清扫）撤向最近有塔基地，敌 <2（滞回）或基地丢后归 GATHERING 回采。判据纯函数在 `production_plans`（`should_evacuate_workers`/`evacuation_clear`/`pick_evacuation_base`）。rush 期**主基**不新增撤离（六连动不变），**分矿不受 rush 门**（bench 实证 rush_active 从首接敌续过中段波，全局 rush 门=E6 死代码）；跳过 building_tracker/司令接管农民。
- **开矿攒钱预留（E3k）**：动态开矿触发即把 `ExpansionController(prioritize=True)` 插在 plan 的 UC 之前（欠费也先派工人走位）；触发但买不起时不注册 SpawnController + 暂停造农民 + UC 让位（优先级：Nexus > 研究 > 出兵）；rush 不开矿、O15 重建优先。⚠️ ExpansionController 千万别放 plan 尾部（UC prioritize 会饿死它，E3k 实证）；扩张钉点工人已在 O11 watchdog 豁免（TOWNHALL_TYPES）。
- **分矿塔与 Nexus 同步（E3l）**：`_should_build_defense` 在有 Nexus 在建或 ≥2 基地时即启动（`defense_syncs_with_nexus`）——分矿塔防不再等落地+6 分钟线，裸奔窗口从 30-100s 压到塔建造时间本身。
- **save_up 不截反空军（E3c）**：`save_up_spawn(exempt=)`——pivot `anti_air_units` 永不截断（保命防空不是副 C），否则敌爆空军时零混编团灭。截断判据是 `resource_gap = max(气缺口, 矿缺口) ≤ save_up`（E3h：只看气会在矿瓶颈局把副 C 锁死）。
- **舰队成型前地面保底（E3e/E3f）**：carrier `pre_fleet: {id, cap, per_enemy, max}`——舰队主 C 出生前 spawn 混入保底兵种（矿耗，priority 压最低），上限随敌可见兵力伸缩 `clamp(cap, 敌兵×per_enemy, max)`，主 C 上线自动退出；保底兵种走 save_up exempt；rush 叉子覆盖优先于保底。**保底阶段地面兵默认守家**（E3g `floor_army_defends_home`，无令不进攻防 trickle，主 C 上线恢复）。
- **steer 一次性 vs 粘性**：`build`/`expand`/`scout` 一次性（重下 no-op，要 `clear` 再下）；其余粘性。`clear` 清**全部**字段（无单 key clear）。

## 验证
```bash
cd ares-bot
# 编译（两流派都测，含 2026-07-23 新增 base_rebuild_active）
BUILD=carrier poetry run python -c "import sys; sys.path[:0]=['ares-sc2/src/ares','ares-sc2/src','ares-sc2']; from bot.managers import production_manager; from bot.production_plans import base_rebuild_active; print('OK')"
# 测试(unittest,无需 pytest;86 例)
poetry run python -m unittest discover -s tests
# 跑局
REALTIME=False BUILD=stalker DIFF=Medium OPPONENT_RACE=Random poetry run python run.py
```
跑局看：兵营>1、bot 日志有 `Researching ...`、`state.army` 含 STALKER+ZEALOT、开局农民不骤减、防御塔/blink 微操。

## carrier vs Zerg 优化（2026-07-26 实机迭代；HEAD E10 单矿 Defeat → 多轮改）

carrier vs Zerg Harder/Macro 是对局劣势（Zerg 双矿爆兵 vs carrier 慢）。HEAD(E10) 全程单矿 Defeat，多轮迭代修复（详记 battle-log O21-O33）：

### 已改（scout/macro/combat）
- **scout**：Bug1 探机撤回回家不死（`home_mineral`）+ Bug2 clear+scout 重派（`_scout_ts` 时间戳）+ O22 探机遇敌逃跑（`_SCOUT_FLEE_RADIUS=8`）+ O27 手动造气 BUILD 长倒计时（`player_yield_for_ability` 30s）+ O28 set target= 清图（validate 空值放行）。
- **macro**：O21 建造干等先采矿（grace 开局 1s/中段 6s/TOWNHALL 30s）+ O26 3 矿气矿（去全局 assimilator 守卫 + 距离 15）+ O29 E9 停开矿扩散（`expansion_blocked` 非 pivot 走 `enemy_near_home` + 首扩 `bases<=1` 放行）+ O30 `first_expand_at` 时间触发 + `when_workers` 16 + **O32 vs Zerg 不 pivot**（`should_pivot_tempest` 否决 Zerg —— 航母主 C 龟缩，不烧舰队链矿给 Nexus）+ **O33 叉减量**（pre_fleet cap 3/per_enemy 0.3/max 8）+ `first_expand_at` 150。
- **combat**：O24 启用 carrier_offensive（放机后拉开 AA 射程外 + `_AA_BUFFER` 4 + 残血撤 15 格）+ O25 航母优先级（`carrier_target_priority` 辅助>对空威胁>杂兵）+ 航母 engage 被推家锚点 `ref=敌重心`（主动找敌放机，治"憋家不战斗"）+ O31 塔堵口（`placement_strategy` closest_to 优先 + `ProtossStaticDefence.closest_to_override=defensive_rally_point`）+ O23 航母出击阈值（`carrier_rally_against_aa`：航母<3 + 敌防空→守家攒兵）。
- **O213 carrier macro/combat 补丁**：
  - power/macro 风格单基地且无 Nexus pending 时 FB 让位二矿（`production_manager.py`），治 O212 败局 FB 抢 300 矿导致二矿 466s 才落。
  - carrier 流加 `rally_min_army: 16`（`flows.yml`），兵力不足 16 时守家攒兵，降低 trickle 分批送死。
  - idle_builder 硬顶细化：FORGE/TOWNHALL 保留 30s，其余结构（含 FB/后续 Gateway/科技建筑）降到 20s，更快释放农民回矿。
- **O214 Zerg Timing 二矿资金窗补丁**：
  - O189 强制开二矿对 Zerg Timing 降到 `t≥180 / 矿≥100`（Rush 维持 210/150）。
  - 扩张预留期间 O131 死锁保险丝延长到 120s/400minerals（打断线 200），避免防御过早抽干 Nexus 400 矿。
  - `_expand_holding` 且舰队 <4 时，F2 炮塔注册 buffer 从 30 提到 75，保护二矿/首舰资金。

### 待改（carrier vs Zerg combat 难点，Explore 诊断）
- **问题① 航母被推家没 engage（矿区待着不防守，司令两轮指出）**：根因锚点 `ref=home` 远离敌。已改 ref=敌重心（rec7 改善 macro 起），但 **rec8 仍矿区待着**（单矿航母 1 兵少守不住 + engage 改条件可能没满足/残血撤退干扰）。**深查**：被推家 attack_target=home 是否触发（floor primary<3/rush/defend）+ engage 改 ref=敌重心是否生效（attack_target.distance_to(start)<20 + near 非空）+ 残血撤退（<40% 走 retreat_ref 不走敌重心）+ O24 AA retreat（Hydralisk air_range 6 后撤 10 格 > engage 9.5 横跳）。可能要：被推家航母强制 attack 最近敌（不只锚点）+ 残血阈值降/被推家不撤。

> **元指示（司令 2026-07-26）**：后续所有司令在聊天框发的优化建议，**全部落地本文件（CLAUDE.md）**，优化流派/bot 时重点参考。

## 当前迭代强制验证模式（司令 2026-08-05 最终口径，O198 再次确认）

> **2026-08-05 21:07 追加确认**：当前正在跑的 O197 双车道 bench 已满足 headless + 双车道并行；下局及后续所有正式 bench 继续强制本模式。本节作为项目记忆，每次迭代前重读。
> **2026-08-05 22:43 再次确认（司令）**：下局对战及后续所有正式 bench 必须按 **headless（REALTIME=False）** 跑，并同时开 **双车道 SC2 并行**；已作为项目记忆写入本节。
> **2026-08-05 23:11 司令再次确认**：当前正在跑的 O201 及后续所有正式 bench 继续强制 **headless + 双车道 SC2 并行**；`ares-bot/bench.py` 已同步修正顶部注释。单车道仅作为双车道临时故障、headless 不稳或观战排查时的降级。

- **下局及后续所有正式 bench 必须同时满足**：
  1. **headless**：`REALTIME=False`（非观战/非排查场景）。`bench.py` 默认 `--realtime` 未置位即注入 `REALTIME=0`，无需额外参数。
  2. **双车道并行**：同一时刻开两条 lane 跑不同组合或对照，最大化迭代速度；单车道仅作为双车道临时故障时的降级或观战排查。
- 启动前必须调用 `_cleanup_stale_sc2()` / `pkill -9 -x SC2` 清理残留进程；单局内精确跟踪本局 SC2 PID，检测 60s 未启动 / 崩溃 / 90s 无 snapshot 更新即判定卡死并杀进程重试。
- 若双车道反复崩溃/卡死，先杀进程再重启；仍不稳时临时降级 `REALTIME=True` 单车道观战排查，但需记录并继续修复稳定性，而不是长期停留单车道。
- **窗口可见性兜底**：`bench.py` 每局启动后调用 `_hide_sc2_windows()` 隐藏 SC2 窗口；若因系统事件/用户点击重新显窗，不影响「headless=无人工输入、REALTIME=False 后台加速」的本质。排查需要观战时可手动显窗。
- **问题② 持续侦查不足**：Probe scout 一次性不补（`_handle_scout`）+ Oracle `one_off` 死了不补。改：vs Zerg 循环 scout（60-75s 自动重派）+ Oracle 维持 1 架。**司令指示**：叉子配合先知探路+牵制（不全程 floor 守家）。
- **问题③ 塔防御不足/晚**：6 分钟自动塔偏晚（roach all-in 5:00）+ 反应式（敌到 40 格才建）。改：vs Zerg 自动塔提前 240s（`_should_build_defense`）+ scout 驱动塔 + threat 阈值降（`max(8,own×1.2)`）。**司令指示**：防御主要靠光子塔（不靠叉堆）。

### 司令核心指示（2026-07-26）
- **侦查是最重要的优化方向**（防 rush 一波）：前期做好侦查，**先知 + 叉叉兵要和敌方主力部队接触**（持续了解敌我兵力），供主基地/分矿**建造足够光子塔 + 护盾电池**做防御判断。即"侦查接触敌 → 了解兵力 → 造塔防御"闭环。
- **分矿防御模型**（塔性价比 > 兵）：分矿 Nexus 建好 → **立刻落地水晶** → 水晶好 → **补 3 个光子塔**（最低防御）→ 侦查驱动逐步增加。塔围绕**地形入口**集结（兵营 gateway 顶前面堵口，塔密集后方），不让敌直冲推平主基。防御塔同等金钱守家打出比兵更多伤害。
- **分矿堵口方案**（司令 2026-07-26）：分矿 ramp 前**排一个兵营（gateway）堵口**，**后排放若干光子塔密集防守**（塔射程覆盖 gateway —— 敌打 gateway 时塔集火）。gateway 顶前 + 塔后排 = wall-in 堵口防御。expansion_cannons min:3（min 5 挤矿 macro 差,实证 rec11 vs rec10/Lane2）。
- **headless + 双车道并行验证**（司令 2026-08-05 最终口径）：后续正式 bench 统一走 **headless 双车道并行**（同时开两条 lane 跑不同组合/对照），最大化迭代速度；`bench.py` 保留启动清理、SC2 进程树跟踪、崩溃/卡死检测与自动重试。单车道串行仅作为双车道临时不稳时的降级，或观战/快速冒烟场景使用。O192 追加：bench 启动前必须 `pkill -9 -x SC2` 清理残留进程，避免端口/实例冲突；对局内 townhalls==0 且无法重建时主动 `leave()`，杜绝 SC2 残局不判负导致的 bench 空转。
- **被攻击矿区农民撤离**（司令 2026-07-26）：被攻击的矿区农民应跑回主基或其他安全基地，不在被攻击基地继续采矿。E6 机制（`update_worker_evacuation`）已有，触发条件敌地面 ≥4 进 Nexus 15 格 → 可能阈值太高/覆盖不全，需调。
- **叉叉兵减量**（防御靠塔，叉配合先知侦查+牵制）→ 省矿给 2 矿 + 航母尽早成型。
- **2 矿更早**（10 分钟 2 矿没开 = 经济死，敌方 3 矿碾压单矿）。
- **航母尽早成型** + 被推家该 engage 防御（不憋家）。
- **验证模式：headless + 双车道并行**（司令 2026-08-05 最终口径）。后续所有正式 bench 默认 `REALTIME=False`，并同时开两条 lane 跑不同组合/对照，最大化迭代速度。双车道出现 SC2 卡死/崩溃/残留冲突时，先清理再重启；仍不稳时临时降级 `REALTIME=True` 单车道或观战排查。
