# 流派方案 · 航母黄金舰队（Carrier Skytoss）

> 优先级 S 级 · 预计改动量：小（P0 配置化完成后基本只改 yaml + 档案）
> 社区出处：SpawningTool "skytoss smasher carriers"、"CIA into Carriers"；中文社区「黄金舰队」。
> **状态：已落地（2026-07，待跑局验证）** —— `flows.yml` 的 `carrier` 块 + `build_meta.md`
> 档案段已就位，`BUILD=carrier poetry run python run.py` 即可开局；跑局结果回填到末节。

## 流派定位

星门科技的另一条旗舰线：航母主 C、暴风舰副 C 的天空体。航母是**最 a-move 友好的旗舰**
（拦截机自动索敌攻击，无需任何微操），与本 bot 架构完美契合。与暴风舰流**共用整条科技链**
（gateway→cyber→星门→舰队航标），是 P0 配置化之后「几乎白捡」的第二个已验证候选。

- 节奏：农民开局 → 星门 → 舰队航标 → 航母滚雪球（比暴风舰更贵更慢，成型后更硬）。
- 死穴：维京战机、腐化者、风暴战舰对射；成型前空窗期比暴风舰更长、更怕早压。
- 杠杆配合：`stance=defend` + `trigger=when_maxed` 正好覆盖「龟到成型再一波」的打法。

## 前置依赖

- P0（流派配置化）。**若 P0 未做**：可在 `production_manager.py` 仿照 `is_stalker_flow`
  再加一个 `is_carrier_flow` 分支临时落地（spawn 配方 + 升级列表两份常量），但不推荐——
  第三个流派起就该还配置化的债了。

## 改动清单

1. **spawn 配方**（P0 后写在配置里）：
   `CARRIER proportion 0.7 priority 0` + `TEMPEST proportion 0.3 priority 1`（示意，
   跑局后调）；航母优先、暴风舰补射程。ORACLE 维持 `proportion=0` + 一次性建造（可选保留）。
2. **科技链**：完全复用暴风舰流（`CORE_STRUCTURES` + 舰队航标分支），无新增。
   航母前置 = 舰队航标，已在链上。
3. **升级**：复用空系（`TEMPESTGROUNDATTACKUPGRADE` 换成 `PROTOSSAIRWEAPONSLEVEL1/2` 更贴航母，
   跑局对比后定）；配置化后写进 flow 块 `upgrades:`。
4. **combat class**：CARRIER 先用 `combat: default`（generic_offensive，依赖 B0 手感尚可）；
   后续可写 `carrier_offensive`（利用 8+2 射程保持最大距离风筝、优先维修?），独立排期。
5. **chrono**：`_primary_unit_id()` 按配置 priority 自动指向 CARRIER，**无需改代码**。
6. **产能**：`_build_extra_stargates`（封顶 6）直接适用；航母 350/250 极吃气，
   验 `_build_tempest_rush_structures` 的 `2*基地数` 气矿逻辑是否跟得上，不够再调。
7. **build_meta.md**：新增 `CarrierSkytoss` 档案段（codename/core_units/节奏/死穴/空窗期），
   供参谋长开局介绍。
8. **army_composition.yml**：CARRIER 已在 protoss 块登记（proportion=0），配置化后只需在
   flow 块引用，不用动兵种注册。

## 验证

- 无头：`REALTIME=False BUILD=carrier poetry run python run.py` 对 Hard 应稳赢。
- 实机：看三点——① 气够不够（航母卡不卡气）；② 空窗期会不会被 AI 早压打死
  （必要时让参谋长开局就 `stance=defend`）；③ 航母团战拦截机是否正常输出。
- 顺手验：暴风舰副 C 是否仍由 `tempest_offensive` 正确接管（混编分派）。

## 风险与调优点

- 空窗期比暴风舰更长——开局介绍里参谋长必须讲明，建议默认 `trigger=when_maxed`。
- 航母怕的兵种（维京/腐化）恰好是 AI 较少憋的；若实测被克，档案里补「死穴」预警条件。
- `default` 微操下航母可能冲太前，跑局后决定要不要写 `carrier_offensive`。

## 跑局调优记录

（实施时填）
