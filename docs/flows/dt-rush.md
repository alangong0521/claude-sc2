# 流派方案 · 隐刀（DT rush / DT 转运营）

> 优先级 S 级 · 预计改动量：中
> 社区出处：SpawningTool "Fake DT drop into tempest rush into two base blink"；
> 内置 AI 反隐弱是社区共识，DT 是对 AI 效果最夸张的兵种之一。

## 流派定位

隐身奇袭流：twilight→dark shrine 速出黑暗圣堂，靠隐身白打对面农民/基地。
对本 bot 的三重契合：

- **隐身单位 a-move 就是完全体**——DT 没有需要微操的技能，0-APM 零损耗。
- **和暴风舰流直接衔接**：假隐刀真暴风舰（对面补反隐/防空投资 → 我们转天空），
  一个流派的钱骗对面两条线的防。
- **参谋长的敌情分析多一出好戏**：核心决策是「对面有没有反隐」——正好是
  `enemies[]` 敌情分栏 + `events[]` 已经能看见的信息（RAVEN/OBSERVER/导弹塔/眼虫）。

- 节奏：农民开局 → gateway→cyber→twilight→dark shrine → 隐刀摸农民/拆基地 →
  对面有反隐就转运营（开矿/转暴风舰），没有就杀穿。
- 死穴：反隐（渡鸦、侦测器、眼虫、导弹塔/孢子爬虫、轨道扫描）+ 前期一波 rush。

## 前置依赖

- P0（流派配置化）。科技链走 flow 块的 `core_structures`：
  `GATEWAY → CYBERNETICSCORE → TWILIGHTCOUNCIL → DARKSHRINE`。
- 无 P0 临时做法：`is_dt_flow` 分支，科技链同上。

## 改动清单

1. **spawn 配方**：`DARKTEMPLAR proportion 1.0 priority 0`（纯隐刀起步；
   混编 ZEALOT 当肉可后续调）。SpawnController 已支持 protoss warp-in，
   dark shrine 造好后 DT 经 gateway/warpgate 入场。
2. **科技链**：见上。`DARKSHRINE` 引擎枚举已实测存在；`build=darkshrine` 经
   `resolve_build_name` passthrough 也能手动点（不在 BUILDABLE，但放行）。
3. **combat class**：先用 `combat: default`（隐身 a-move）。后续可写 `dt_offensive`：
   - `focus=workers` 优先摸农民；
   - 避开可见的反隐单位/建筑（`enemy_near` 里有 RAVEN/MISSILETURRET/SPORECRAWLER 就换目标）；
   - 被扫描/被点亮时撤（`unit.is_cloaked` 或 buff 判定）。
   独立排期，不阻塞首版。
4. **升级**：无关键升级；可空或挂地面攻击（`PROTOSSGROUNDWEAPONSLEVEL1`）。
5. **转型衔接**：档案里写明「对面出反隐 → 转暴风舰」——P1（局中切 flow）落地后
   可直接 `flow=tempest`；落地前由参谋长用现有杠杆模拟（`build=stargate` + 停 DT 产）。
6. **build_meta.md**：新增 `DTRush` 档案段，死穴=反隐清单，转型路径写进「典型胜利路径」。
7. **army_composition.yml**：DARKTEMPLAR 已登记（proportion=0），flow 块引用即可。

## 验证

- 无头：`REALTIME=False BUILD=dt poetry run python run.py` 对 Hard 各打 3 局
  （对手 Random，按种族分别看胜率——虫族眼虫早、人族扫描晚，胜率预期不同）。
- 实机：看三点——① DT 是否绕开有反隐的方向；② AI 被隐刀摸农民时的反应（补不补塔）；
  ③ 对面出反隐后参谋长转运营的路径是否顺（这是观赏重点）。
- 顺手验：`events[]` 里「发现 RAVEN/MISSILETURRET」等首见事件是否足够参谋长做反隐判断，
  不够就补事件类型（这是小改动，别忍）。

## 风险与调优点

- DT 走路进场慢，warp prism 空投是进阶版——投放逻辑接近 `medivac_transport`，
  独立排期（v2 做空投隐刀）。
- 对面如果是快攻 AI build（Rush），DT 未出家门先破——开局 `scout=on` 确认不 rush 是关键，
  写进档案「空窗期」。
- `default` 微操下 DT 可能集火建筑不摸农民，跑局后决定 `dt_offensive` 的优先级。

## 跑局调优记录

（实施时填）
