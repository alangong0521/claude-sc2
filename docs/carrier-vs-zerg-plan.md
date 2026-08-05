# carrier vs Zerg 优化计划（2026-07-26）

标准：**打到 carrier vs Zerg Harder/Macro 赢**，再逐级升档。
验证方式：**串行单车道 headless**（`REALTIME=False` + `STEER_RECORD=<dir>`），双车道不可行（SC2 二进制单实例锁互踢）。

## 现状基线

| 版本 | 结果 | 关键指标 |
|---|---|---|
| HEAD（E10，改前） | Defeat | 全程 **单矿**，无舰队 |
| rec10（综合改，Macro/AbyssalReef） | Defeat | 3 矿 t=667 / 48 农民 t=727 / CARRIER 1+TEMPEST 1 / 气积压 3111 |
| Lane2（综合改，Rush/BelShirVestige） | Defeat | 3 矿 t=607 / **CARRIER 3 + TEMPEST 2 @ t=864** / t=976 起被推丢矿 |
| rec11（塔 min 5 + threshold 2） | Defeat | **比 rec10 差**：t=583 丢分矿，t=615 主基丢（塔挤矿） |

结论：**macro 已解决**（3 矿 + 舰队成型），**守不住 Zerg 大军推**是当前唯一瓶颈；塔数 min 3 优于 min 5（min 5 挤矿）。

已存盘：commit `13a8cc8`（22 files，1209 insertions，单测 391 绿）。

## 计划（按优先级，待司令拍板）

### P1 — E6 农民撤离调参
- **司令原话**：被攻击的矿区农民应跑回主基或其他安全基地，不在被攻击基地继续采矿。
- **根因猜测**：`main.update_worker_evacuation` 触发条件是敌地面 **≥4** 进 Nexus **15 格** —— 阈值偏高（2-3 只狗压矿已经该撤），且需确认每个分矿都被覆盖。
- **改动**：阈值 ≥4 → ≥2；半径 15 → 20；确认 per-townhall 遍历无遗漏；纯函数在 `production_plans.should_evacuate_workers` / `evacuation_clear` / `pick_evacuation_base`，测试同步。
- **验收**：headless 快照里被打分矿的 workers 不再原地归零；总 workers 曲线不出现断崖。

### P2 — 分矿堵口（wall-in）
- **司令原话**：分矿 ramp 前排一个兵营（gateway）堵口，后排放若干光子塔密集防守，塔射程覆盖 gateway（敌打 gateway 时塔集火）。
- **改动**：分矿 ramp 检测（ares `main_ramp` 之外的 expansion ramp）+ `BuildStructure` 走 wall 位置 + 塔 `closest_to_override` 放 gateway 后排（射程 7 内）。
- **约束**：`expansion_cannons.min` 保持 **3**（rec11 实证 min 5 挤矿使 macro 崩）。
- **验收**：分矿 Nexus 落地后 gateway + 3 塔按 ramp 排布；分矿存活时间显著延长。

### P3 — 侦查闭环
- **司令原话**：侦查是最重要的优化方向；先知 + 叉叉兵要和敌方主力部队接触，时刻了解敌我兵力，供主基地/分矿造塔判断。
- **现状**：循环 scout（O34，60s 自动重派）已做；**先知阵亡不补**（`one_off: [ORACLE]`）、**叉叉兵接触侦查未做**。
- **改动**：Oracle 维持 1 架（死了重建）；叉分一小队做接触侦查+牵制（不全程守家）；侦查读到的敌兵力驱动塔数（`expansion_cannons` 动态项 + threat 阈值降到 `max(8, own×1.2)`）。
- **验收**：全局任意时刻有 1 架 Oracle；敌兵力估计非零且随时间更新；塔数随敌兵增长。

### P4 — 航母 engage 改进
- **司令原话**：航母还是在矿区待着，没有防守。
- **现状**：被推家已改为强制路径到敌重心（绕过 `_anchor` 的 AA 降权），但航母仍会被打死。
- **改动**：塔掩护下 engage（往有塔区域拉打）；AA retreat 距离与残血阈值再调；残血不撤到地图深处。
- **验收**：Lane2 的 t=864 CARRIER 3 不再在 t=976 归 1。

### P5 — carrier 对局矩阵
Zerg Harder/Macro Victory → Harder 其他风格 → VeryHard → 换族 → Cheat 档。每档串行 headless 复跑 2 局确认稳定。

## 待办杂项
- 司令观战时需点击左下角小地图切主画面：SC2 客户端窗口问题（bot 不控窗口），用 `sc2cam <left|right|top|bottom|center>` 切镜头，或先点主画面激活再点小地图。
- 所有新的司令建议按元指示继续落 `CLAUDE.md`。
