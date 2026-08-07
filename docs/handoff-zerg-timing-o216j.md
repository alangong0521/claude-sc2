# Handoff — Zerg Timing 攻坚状态（唯一未打穿组合）

> 日期：2026-08-06 ｜ 代码版本：O251 ｜ 状态：**5/6 组合已打穿，Zerg Timing 累计 3 胜未打穿（单 lane 需 3/5）**
> 接手先读：`docs/battle-log.md` 末尾（O216-O251 全部迭代记录）+ `CLAUDE.md` bench 纪律。

## 1. 六组合总进度

| 组合 | 状态 |
|---|---|
| Zerg Rush | ✅ O211 打穿 |
| Zerg Power | ✅ o244z lane1 3-0 |
| Terran Rush | ✅ o241t lane2 3-2 |
| Terran Timing | ✅ o242t lane2 3-2（后补至 3-2） |
| Terran Power | ✅ o243t lane1 5-0 |
| **Zerg Timing** | **3 胜（o224-g05 / o229-g03 / o249-g03），未打穿** |

## 2. Zerg Timing 当前路线（O248-O251，相对胜率最高的代码）

- **不强制/禁止 transition**（O248/O249b）：直爬 cyber→SG→FB，首舰 374-510s（原 550-620s）。
- **舰队先行**（O247/O250）：未见首舰 + t<620 不开二矿（含 _spend_bank 滚雪球通道）。
- **产能链**：O218/O249 追加 SG（首舰后气 ≥400）+ O228/O229 SG/FB 钉点派工 + O239/O240 航母攒钱点舰。
- **防守**：O216i 防御优先门 + O220/O221 无防基地强注册 + O246 追猎核（舰队<8 时 cap2=12）+ O217 残敌清剿 + O219 全军协防 + O245 不朽者（机械台+直产）。
- **经济**：O222 硬饱和开矿 + O251 硬饱和钉点 Nexus（最新）。

## 3. 最好局剖面（仍败）

- 舰队 9 / 3 基地 / 67 农民 / 1227s（o248b-g02）
- 舰队 7 / 3 基地 / SG 4 / 57 农民 / 1317s（o250b-g04）
- 胜局剖面（o249-g03）：4 基地 / 66 农民 / SG 5 / 5 暴风+9 追猎+2 不朽 / 1316s

## 4. 已知未解（按优先级）

1. **终局 attrition**：舰队 6-9 在 900-1300s 被 Zerg 80-100 supply 连续波磨光；航母 350 矿门常因矿恒 <350 出不来。
2. **三/四矿转化率**：O251 刚落地（钉点 Nexus），样本不足；二矿→三矿是胜负分水岭（胜局 4 矿 vs 败局 2 矿）。
3. **早期存款淤积**：281-394s 矿 1015-1670 无出口（O247 封扩张 + 探机/科技链饱和），需要观察 O251 是否消化。
4. **SC2 崩溃率**：每 lane ~1 局崩溃重试（bench 自动兜底）。

## 5. 操作手册

- bench：`cd ares-bot && poetry run python bench.py --flow carrier --diff VeryHard --race Zerg --map AbyssalReefLE --ai-build Timing -n 5 --tag <tag>`（双 lane 错峰 25s，headless 默认）。
- 尸检：`poetry run python scripts/autopsy_summary.py bench/<tag>/game_XX`。
- 验证：`python3 -m py_compile ...` + `poetry run python -m unittest discover -s tests`（当前 652 例）。
- PaladinoTerminalLE 在 Zerg Timing 累计 0/60+，当前只用 AbyssalReefLE 双 lane 出样（改图请先核司令意图）。

## 6. 候选下一杠杆（未实施）

- **先手骚扰压运营**（oracle/voidray 狙 overlord/农民，拖慢 Zerg 90-supply 成型）——唯一未试过的战略维度。
- **航母 350 矿门**：攒钱空窗期塔/探机照抽，与 O245e 同型；可评估 O228 式「星门驻点等钱产航母」是否可行（产线指令不受 can_afford 帧判影响的可行性需验证）。
- **飞蛇/腐化对策**：舰队后撤线/散开站位（tempest_offensive 参数）。
