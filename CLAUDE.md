# claude-sc2

SC2 bot（神族 Aristaeus），基于 [ares-sc2](ares-bot/ares-sc2/) 框架。核心模式：**参谋长(LLM / `steer_cli`)下令，bot 执行**——司令(用户)零 APM，靠 steer 命令指挥。

- `ares-bot/bot/`：我们的代码（**改动重点**）
- `ares-bot/ares-sc2/`：ares 框架（本地子包，**尽量不改，用其原语**）
- `steer_cli.py` / `bot/steer_vocab.py`：参谋长指挥 CLI + 命令词表（单一真相源）
- 参谋长玩法见 `.claude/skills/sc2-claude/SKILL.md`；流派档案见 `ares-bot/build_meta.md`

## 流派（BUILD env，开局前锁定）
`BUILD=tempest|stalker|carrier`，**启动参数**，不能局中换。流派配置在 `ares-bot/flows.yml`（spawn/科技链/升级/chrono/追加产能/一次性建造，单一真相源），加载/校验在 `bot/flow_config.py`。
- `run.py` 在 `import bot.main` **之前** setdefault BUILD 并调 `FlowConfig.load` 归一（未知名警告并回退 tempest）；`production_manager` 在 `__init__` 才读，不再模块级锁定。
- 切换：`BUILD=carrier poetry run python run.py`（在 `ares-bot/` 下）。

## 关键架构（改动热点）
- **`bot/managers/production_manager.py`** — Protoss macro 主战场。流派差异已全部进 `flows.yml`（P0 配置化），本文件只剩机制逻辑。`update()` 每帧注册 macro behaviors。**改机制（产能逻辑/防御/前线塔）在这，改流派数值去 `flows.yml`**。
- **`bot/managers/combat_manager.py`** — 战斗分派。`attack_target` property（解析 steer target 成 Point2）+ 按 `army_composition` 的 `by_role("ATTACKING")` 分派 combat class。
- **`bot/combat/stalker_offensive.py`** — 追猎 blink 微操。
- **`bot/steer_vocab.py`** — 命令词表（`FIELDS` + `_FIELD_VALUES`），bot 和 steer_cli 共用，加命令只改这里。

## ares 原语（优先复用，不改框架）
- `UpgradeController(upgrades, base_location)` — 自动 `TechUp` 建科技建筑 + 研究 + 打 `logger.info`。
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

## 约束 / 踩过的坑
- **升级改动走 `flows.yml` 的 flow.upgrades**（神族生产已不读 `DESIRED_UPGRADES`，该常量已删）；`army_composition.yml` 的 protoss.upgrades 仍被 `tests/test_army_config.py::test_shipped_protoss_upgrades_unchanged` 锁（T/Z 路径还在读它）；flows.yml 的 tempest/stalker 块被 `tests/test_flow_config.py` 的 shipped 测试冻结。
- **spawn 比例和必须 ≈ 1.0**——`flows.yml` 与 `army_composition.yml` 同一约束（加载时各自校验）。
- **ares-sc2 是本地包**——`import ares` 需 `sys.path` 加 `ares-sc2/src`（`run.py:14-16`）；离线编译检查也要加。
- **headless `websocket 超时`**——SC2 更新中 / 冷启动慢会导致；用 REALTIME 或等 SC2 ready。headless 本环境不稳，优先 REALTIME。
- **SC2 补丁日首发失败**（2026-07-18 实证）：当天补丁（如 Base97563）后 SC2 二进制能起进程但**不开 websocket、不出窗口、静默退出**，新旧 build 都一样 → 不是 bot 问题，去 Battle.net 让它完成更新 / 「扫描和修复」，确认手动能进游戏后再跑 bench。排查手法：直启二进制 `-listen 127.0.0.1 -port <p>` + `lsof -iTCP:<p> -sTCP:LISTEN`；多实例互斥会互相踢，先 `pkill -9 -x SC2` 再测。
- **idle 农民**：ares 框架层 `BuildStructure.execute` 不查 `can_afford`（bot 层加守卫根治，不改框架）。
- **steer 一次性 vs 粘性**：`build`/`expand`/`scout` 一次性（重下 no-op，要 `clear` 再下）；其余粘性。`clear` 清**全部**字段（无单 key clear）。

## 验证
```bash
cd ares-bot
# 编译（两流派都测）
BUILD=stalker poetry run python -c "import sys; sys.path[:0]=['ares-sc2/src/ares','ares-sc2/src','ares-sc2']; from bot.managers import production_manager; from bot.combat.stalker_offensive import StalkerOffensive; print('OK')"
# 测试(unittest,无需 pytest;86 例)
poetry run python -m unittest discover -s tests
# 跑局
REALTIME=True BUILD=stalker DIFF=Medium OPPONENT_RACE=Random poetry run python run.py
```
跑局看：兵营>1、bot 日志有 `Researching ...`、`state.army` 含 STALKER+ZEALOT、开局农民不骤减、防御塔/blink 微操。
