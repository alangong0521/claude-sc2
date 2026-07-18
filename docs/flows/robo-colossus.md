# 流派方案 · 机械化地面流（Robo：不朽 + 巨像）

> 优先级 A 级 · 预计改动量：中
> 社区出处：SpawningTool proxy robo / adept-immortal all-in 等机械研究所流；
> 巨像地面推是神族对地面部队的经典答案。

## 流派定位

**战略价值最大的一条**：给 bot 第一条地面流派，全家不再怕凤凰（暴风舰流的死穴）。
机械研究所链：不朽者前排 + 巨像后排扫射 + 追猎/狂热者填线。
巨像跨悬崖行走是被动、扫射是普攻，a-move 友好；不朽对重甲也是普攻型。

- 节奏：农民开局 → gateway→cyber→robo（机械研究所）→robo bay（机械湾）→
  不朽/巨像混编推进，追猎补对空。
- 死穴：空军（巨像只能对地，对空全押在追猎比例上）、不朽者怕被围、巨像怕维京/腐化者点杀。
- 顺带收益：robo 也出**侦测器（OBSERVER）**，把反隐能力补进体系（DT 流的镜子）。

## 前置依赖

- P0（流派配置化）。
- **B0（`generic_offensive` 跑局调手感）**——巨像/不朽初期都走 `combat: default`，
  通用微操不过关这条流派就不成立，所以排在 DT 之后。
- 无 P0 临时做法：`is_robo_flow` 分支 + 新科技链常量。

## 改动清单

1. **spawn 配方**（示意，跑局调）：
   `IMMORTAL 0.3 priority 1` + `COLOSSUS 0.3 priority 0` + `STALKER 0.4 priority 2`（对空）。
   `OBSERVER` 登记 `proportion=0` + 一次性造 1-2 只（仿 oracle 的一次性建造模式，
   生产侧加个小逻辑或在 flow 块配 `one_off: [OBSERVER]`）。
2. **科技链**（flow 块 `core_structures`）：
   `GATEWAY → CYBERNETICSCORE → ROBOTICSFACILITY → ROBOTICSBAY`（巨像前置）。
   巨像射程升级 `EXTENDEDTHERMALLANCE`（robo bay 研究）写进 flow 块 `upgrades:` 首位——
   这是巨像的灵魂升级。
3. **生产建筑**：robo/robo bay 由科技链逻辑自动建；不朽/巨像从 robo 产出，
   ares `ProductionController` 支持 Protoss，可自动补第二个 robo。
4. **combat class**：首版全部 `default`；后续可写 `colossus_offensive`
   （保持最大扫射距离风筝、利用跨地形站位躲近战），独立排期。
   STALKER 已有 `stalker_offensive`（骨架验证后可直接用）。
5. **升级**：`EXTENDEDTHERMALLANCE` + 地面攻防（`PROTOSSGROUNDWEAPONSLEVEL1/2` 等）。
6. **build_meta.md**：新增 `RoboColossus` 档案段——强调「不再怕凤凰」「对空靠追猎比例」。
7. **army_composition.yml**：IMMORTAL/COLOSSUS/OBSERVER 均已登记，flow 块引用即可。

## 验证

- 无头：对 Hard Zerg（蟑螂海被巨像完克，胜率应显著高于对 Terran）+ Hard Terran 各几局。
- 实机：看四点——① 气体分配（巨像 200 气/不朽 100 气，气链是否卡）；② 巨像扫射站位
  （default 微操会不会冲脸）；③ 追猎比例够不够防空；④ 侦测器有没有跟着部队走。
- 顺手验：`EXTENDEDTHERMALLANCE` 升级是否在产巨像后自动研究（M3 升级配置化链路）。

## 风险与调优点

- 气体压力是三条科技链里最大的——可能需要把 `gas_target` 的 `per_base` 从 2 调到更早满采，
  或在 flow 块支持覆写气矿节奏（P0 时留个口子）。
- 巨像被点杀很伤，`default` 微操不管后排保护——跑局后评估 `colossus_offensive` 优先级。
- 对空完全押在追猎比例上，比例不对会被虚空/女妖白打，跑局调 spawn 配比。

## 跑局调优记录

（实施时填）
