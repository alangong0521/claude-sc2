# 流派方案 · 兵营一波（4-gate / 3-gate 追猎）

> 优先级 B 级 · 预计改动量：小
> 社区出处：SpawningTool "3 Gate Stalker Opener" 等经典快攻 BO。

## 流派定位

老牌快攻：早 cyber 研 warp gate，3-4 兵营爆追猎/狂热者持续压制。
坦率说定位尴尬：对 Hard 内置 AI，现有宏观流派已稳赢，快攻的价值主要是
**展示流派多样性**和给「rush 对 rush」提供答案。改动小，适合做配置化之后的练手流。

- 节奏：农民开局 → gateway → cyber → **warp gate 研究**（灵魂）→ 补到 3-4 兵营 →
  warp-in 追猎不断压对面二矿/主矿，压死就赢，压不死转运营。
- 死穴：压不动就是亏（兵营投资拖累科技）；对面龟住 + 反打时我们科技落后。

## 前置依赖

- P0（流派配置化）。 stalker 骨架验证后做更顺（追猎微操直接复用）。

## 改动清单

1. **spawn 配方**：`STALKER 1.0 priority 0`（或 `ZEALOT` 版本，跑局对比）。
2. **科技链**：`GATEWAY → CYBERNETICSCORE` + flow 块配 `research_asap: [WARPGATERESEARCH]`
   （cyber 好了立刻研，P0 时给 flow 块留个「最优先升级」口子，复用 `_research_upgrades`
   通道但跳过「等主力在产」的前置判断）。
3. **兵营数量**：`_build_extra_stargates` 泛化成「矿富余追加核心产兵建筑」
   （P0 时把目标建筑做成配置），本流派目标 3-4 个 gateway。
4. **杠杆配合**：档案里建议 `stance=attack target=enemy_natural` 持续压、
   `trigger=now`；压死后 `set target= stance=attack` 清图。现有词表完全够用。
5. **combat class**：STALKER 用 `stalker_offensive`（需先跑局验证），ZEALOT 用 `default`。
6. **build_meta.md**：新增 `FourGate` 档案段——写明「压不死就转运营」的转型路径。

## 验证

- 无头：对 Hard 看平均结束时间（应显著短于宏观流派）和胜率。
- 实机：看 warp gate 研究时机、warp-in 节奏（SpawnController 支持 protoss warp-in，
  但从未在实战中观察过节奏是否跟得上一波流）。

## 风险与调优点

- SpawnController 的 warp-in 节奏若偏慢，一波流威力打折——这是本流派唯一的硬依赖，
  跑局第一课就看它。
- 与 stalker 流差异主要在「早压制 vs 运营」，档案里讲清，别让参谋长把两条流混着介绍。

## 跑局调优记录

（实施时填）
