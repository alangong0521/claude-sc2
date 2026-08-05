# 工作交接：carrier 流 VeryHard 全矩阵自调优（2026-08-02）

> 给下一个 AI 接力用的完整状态快照。读这份 + `docs/baselines.md`（迭代日志全录）即可开工。
> 不要重复踩坑：先读「## 六、血泪教训」。

---

## 一、项目是什么

`~/work/claude-sc2` —— SC2 神族 bot（vendored ares-sc2 框架）+ 流派化生产/战斗配置 + bench 自调优回路。
本体在 `ares-bot/`：

- `bot/managers/production_manager.py`：生产/经济/侦查/rush 响应（本工作主战场，O40-O82 迭代都在这里）
- `bot/managers/combat_manager.py`：战斗指挥（推进闸/防守锚点/集结）
- `bot/production_plans.py`：纯逻辑判据库（全部可单测，新判据一律写成纯函数）
- `bot/combat/tempest_offensive.py`：暴风微操（行军模式/攻城纪律）
- `flows.yml`：流派配置（carrier 流 spawn/科技链/塔目标/pivot）
- `bench.py`：自调优跑局器（`--flow/--diff/--race/--ai-build/--map/-n/--tag`）
- `tests/`：457 个单测全绿（`poetry run python -m unittest discover -s tests`）

## 二、当前状态（已验证成果）

### VeryHard 15 组对阵矩阵：全穿 ✅

carrier 流（暴风 0.85/航母 0.15，O40-O70 迭代后）每组 ≥1 胜，全部 headless 实跑：

| 对手 | Rush | Timing | Power | Macro | Air |
|---|---|---|---|---|---|
| Zerg | ✓ 2-1 | ✓ | ✓ | ✓ 2-0 | ✓ |
| Terran | ✓（O67 逆转） | ✓ | ✓ | ✓ | ✓（破维京墙） |
| Protoss | ✓ | ✓ | ✓ | ✓（破旧墙） | ✓（破凤凰墙） |

旧认证墙（Terran/Air 维京、Protoss/Air 凤凰、Protoss/Macro、Zerg/Rush）全破。
**主线目标已完成。** 结果+完整迭代日志（O40-O82 每轮的假设/改动/实证/结论）在 `docs/baselines.md`。

### 关键机制资产（都已落地+单测覆盖）

- **O60/62 暴风主 C**：spawn 配比 TEMPEST 0.85/CARRIER 0.15（暴风射程 10 压腐化/维京/凤凰；航母 250 气/艘吃掉 ~3.5 艘暴风的气）
- **O63/64 动态回防**：敌计数 ≥6 的最高压基地舰队回防；推进窗口 ≥14 主力级才召回（防「防守跑步机」）
- **O65/68 行军模式+攻城纪律**：commit_push 时暴风不追过路敌、优先拆建筑（治「满人口推不出去」）
- **O66 集结闸按舰队计数**（原只数航母，暴风主 C 后口径过期）
- **O67 威胁期科技让位塔链**
- **O70 满人口全攻**：supply ≥95% cap 且矿 ≥1500 → 跳过 supply 优势检查直接压上（硬对空安全线保留）
- **O71 早期二次侦查**：t=250 探机复核，rush 确认 t=500+ → t=330（`rescout_verdict`：开矿→greedy；单基地+兵营类≥3 或(≥2且兵≥6)或兵≥10→rush）
- **O79 分矿电力跟 Nexus 走**（每就绪基地保底 2 晶——「分矿恒 0 塔」的最底层根因：无电时所有塔落位静默返回 None）

## 三、N=5 显著性验证结果（Terran Rush 专项）

| 轮次 | 配置 | 战绩 |
|---|---|---|
| n5 第一轮 | O71 | 2-3（40%） |
| n5i | O71-O81 | 0-5 |
| n5j | O82 回滚持有 | 0-5 |

**结论：VeryHard Terran Rush 是真墙（方差局，非 bug）**。败因唯一且稳定：
舰队临界质量（t=750-900，8-12 暴风）恒晚于对手第二三波（t=550-800，~150s 一波递增）。
当前代码已回到 O82 状态（rush 预警 60s 自动解除，不锁运营）。

**此对阵建议记「疑似相克」豁免（promotion.py 的 ≤2 豁免席位用法）。**

## 四、待办/可选方向（按推荐排序）

1. **【待用户决策】Terran Rush 记豁免** —— 数据已齐（2-13），不值得再投入。
2. **CheatVision 升档** —— 15/15 打完后自然的下一档。风险预告：VeryHard Rush 已是 2-1 险胜，CheatVision 的 rush 更凶；tempest 流曾打到 CheatInsane 12/15 停档（墙在三族 Rush）可作参照。
3. **【大改，非调参】Terran Rush 换过渡形态** —— 若要再攻这堵墙，唯一剩的方向：叉/追猎开、推迟星门，先活到 t=700 再转舰队。这是改 build order 的活，不是调参。
4. **N=10 显著性**（如果要做）：项目判定门槛是 N=10 ≥7 胜（`docs/bot-self-tuning-plan.md` §6）。N=5 证明 Terran Rush 达不到，其他险胜组（Zerg Rush 2-1、Protoss Macro 逆转）若要坐实稳定性可跑。
5. **已知未修的小问题**（不阻塞，都是实证见过的）：
   - Terran Air 局出现 6 星门+11 塔同建导致断矿停产（min=120, gas=2200）——星门数需盯矿气平衡
   - rush 局恢复战的二次扩张时机：恢复后第 3 基地常裸落（塔链没跟上再丢一次）
   - F2 诊断事件（`F2:注册防御`/`F2:每基地(塔,晶)`）还在代码里（O76b 加的），长期跑局会刷事件流，可留可清

## 五、跑局操作约定（重要，别踩坑）

- **bench 命令**（`ares-bot/` 下）：
  `poetry run python bench.py --flow carrier --diff <难度> --race <Zerg|Terran|Protoss> --ai-build <Rush|Timing|Power|Macro|Air> --map AbyssalReefLE -n <局数> --tag <系列名>`
  一律后台启动（`run_in_background=true` + `disable_timeout=true`）。
- **结果读法**：`bench/<tag>/game_*/run.log` 里 `Result for player 1 - CodeAgentSC2: Victory/Defeat`；快照 `game_*/state_*.json`（t/bases/workers/army/structures/enemies/events）；汇总 `bench/<tag>/summary.json`（bench 自己 tail 输出）。
- **杀局卫生**：`kill $(pgrep -f "bench.py --flow") ; pkill -f "run.py" ; pkill -x SC2`，`pgrep -x SC2` 归零再开新局。**注意 `pkill -f` 只杀 shell 包装会留孤儿 bench 进程**（踩过：必须用 `kill $(pgrep -f bench.py)` 杀 PID）。
- **双实例可行**：python-sc2 自动 `pick_unused_port()`，两路 bench 并行（3+2 拆 tag）实证可用；本机 10 核 16GB 每局 ~2 核 3GB。
- **代理坑**：手动起 `run.py` 要 `env -u HTTP_PROXY -u HTTPS_PROXY NO_PROXY=127.0.0.1,localhost`；bench.py 自己会剥。
- **单测**：`poetry run python -m unittest discover -s tests | grep -E "^(OK|FAILED|Ran)"`，当前 **457 个全绿**（含 1 skip）。改动后必跑。
- 本机 Python 3.14 不被 poetry 项目支持（>=3.11,<3.13），poetry 会自动选 3.12，别手动 `python3` 跑 bot。

## 六、血泪教训（接手的 AI 请逐条对照）

1. **数据优先于理论**：O72-O81 五轮「合理修复」把 N=5 从 2-3 打到 0-5。每个局部都对的改动，组合起来可以是负资产（600s rush 持有把舰队管线窗全毁了）。单局胜利是方差，N≥5 才配叫结论。
2. **「延长 rush 态」是负资产**：rush_active 每多挂一秒，科技链/农民/出兵就多停一秒；防御的收益是一次性的（塔落地），运营的成本是复利的（舰队晚一分钟）。
3. **分矿在 rush 预警窗内不可守**：~160s 窗 < 2 晶+4 塔建造所需 ~200s，物理上限，别试图补（O76-O79 六层全修完也只能到 2 塔）。正确姿势：主基坡口塔阵 + 分矿农民早撤（O80a）。
4. **Protoss 建筑必须「有电」**：`within_psionic_matrix` 下无电区域的所有落位**静默返回 None**，不报错不告警（悬案排查花了 6 轮）。查建造问题先查电。
5. **BuildStructure 的 max_on_route 是全图共享计数**：多基地并发建塔会互相饿死（主基恒先占满），排序按主基优先（O81）。
6. **ProtossStaticDefence 的 static_defence=True 槽位检索**在分矿会静默失败，分矿防御直接用裸 `BuildStructure(static_defence=False, find_alternative=True)` 更稳。
7. **满人口 199/200 + 5000 存款时别再攒**：蹲是纯亏，换血永远我方赚（O70 的司令观察）。
8. **暴风 vs 虚空/雷神**：暴风(射程 10)压维京(9)/腐化(6)，但虚空棱镜对齐烧装甲暴风贼快——虚空潮的答案是塔阵消耗（两波虚空俯冲塔阵全灭），不是暴风对拼。

## 七、关键文件索引

- `docs/baselines.md` —— 一切迭代的全录（矩阵 + O 系列日志 + N=5 三轮），先读它
- `ares-bot/flows.yml` —— carrier 流全部配置（spawn 配比/塔目标/pivot/开矿）
- `ares-bot/bot/managers/production_manager.py:852` —— `_update_rush_state`（rush 检测/60s 解除）
- `ares-bot/bot/managers/production_manager.py:894` —— `_rescout`（O71 二次侦查）
- `ares-bot/bot/managers/combat_manager.py:305` —— carrier 推进闸（O44/45/59/60/63/64/65/70 全在这）
- `ares-bot/bot/combat/tempest_offensive.py` —— 暴风行军/攻城（O65/68）
- `ares-bot/bench/` —— 所有历史系列快照（`<tag>/game_*/state_*.json` 可复盘）

## 八、环境状态（交接时）

- 无 SC2/bench 残留进程
- 单测 457 全绿
- `docs/baselines.md` 已同步到 O82 + N=5 三轮总结
