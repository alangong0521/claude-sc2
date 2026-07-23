# 憋大招流派计划(BruceBot 调研落地,2026-07-24)

来源:[prevosta/BruceBot](https://github.com/prevosta/BruceBot)(ares 模板 fork,Terran 单流派 BcPush 直跳大和)。
完整调研结论见本文;机制出处均标注 BruceBot 源文件。时间点为作者注释,**未实测**。

## BruceBot 套路拆解

**建造链**(terran_builds.yml):兵营堵口(墙 ~01:40)→ 双气极早 → Factory →
**Starport 野在敌方四矿方向隐蔽点**(ProxyBuilder,按图离线算坐标缓存 data/map_info.json)
→ Factory 科技挂 1 坦克(~02:50)→ Orbital → FusionCore → Starport 科技挂 →
首艘大和 ~04:30 → 第 2 艘 + 导弹塔×2 → **然后才第一次扩张**。

**"憋"期防守(总成本 <400 矿)**:①坡口建筑学(兵营居中+补给站×2,ControlSupplyDepot 自动升降);
②1 枪兵哨位(PicketDefence 按 climber_grid 算可攀入侵点布哨);③1 坦克架坡顶(贴脸自动收);
④前 2:15 反 cheese:检测敌前置建筑 → 拉 3~9 农民编队反拆(优先拆快造好的)+ 停气。

**大河六级行为链**(combat/BattleCruiser.py,逐船每帧按序,命中即停):
1. **Repair**:<100% 血且 10 格有空闲 SCV → 船找工人;<25% 血 → 战术跳跃回家
2. **Yamato**:只点对空高威胁(维京/腐化/虚空/航母/防空塔),排序键 =(未点名, 建筑, 能对空, 血+盾)
3. **Support**:家里被入侵 >3 或墙血 <10% 且离家 >20 → 战术跳跃传回坡口
4. **KiteBack**:15 格内敌对空 DPS 合计 >25 才退(**DPS 阈值,不是单位数**)
5. **Attack**:默认目标 = 农民(经济打击)
6. **Patrol**:8 航点巡逻敌主矿/二矿矿线,切入贴地图空气边缘绕开防空,<40% 血直接回家

**机制亮点**:逐单位优先级链骨架;DPS 求和做退/战决策;`ready_to_upgrade` ≥2 艘才开升级(防卡钱);
RepairController 全局派维修(钱少自动缩编);RebuildDestroyStructure 被拆原地重建;扩张选离敌我最远矿点。

## 方案 A:terran BC 流(新流派,工作量大)

照抄 BcPush 翻译成 flows.yml:链 SUPPLYDEPOT→REFINERY→BARRACKS(坡口)→REFINERY→FACTORY→
STARPORT→FACTORYTECHLAB→SIEGETANK×1→ORBITAL→FUSIONCORE→STARPORTTECHLAB→BATTLECRUISER;
spawn BATTLECRUISER 1.0;升级门控 ≥2 艘才开 YAMATOCANNON→武器/护甲。
⚠️ 我们 terran 块是 M1 骨架,生产层未跑局验证,需先打通基础生产。从 Hard 起测,
重点盯 stall(双气早+单矿易卡气)和 one_base(扩张晚)。

## 方案 B:改进 carrier 流(工作量小,直击 VeryHard Terran/Air 0-3 痛点)

1. **TempestFocusFire**:carrier 流里 30% 配比的风暴舰承担"大和炮"角色——只对 can_attack_air
   空军(维京/腐化/凤凰)集火,射程 14 白打维京;目标排序抄 yamato_priority。
2. **航母群 DPS 阈值撤退**:15 格内敌对空 DPS > 阈值 → 整队撤电池圈(替代 per-unit 风筝)。
3. **残血航母回电池**:<40% 血单体撤最近电池(复用 bot/shield_battery.py)= 神族版 Repair+跳跃闭环。
4. **矿线巡逻 posture**:默认目标农民、切入贴地图边缘(抄 BattleCruiserPatrol),维京要追就离正面。
5. **升级门控**:≥2 艘航母才开 L2+ 升级(防 stall,抄 ready_to_upgrade)。

验证:直接 promotion.py 跑 carrier × Terran/Air × VeryHard,先确认 0-3 破零;盯 trickle 信号。

## 可直接进 backlog 的通用机制
- 反 cannon-rush:拉 3~9 农民编队反拆前置建筑(优先拆快造好的)——我们 pivot 只有转防没有反拆。
- 静态防守位置预注册(RampBuilder 把防空塔改写进标记位)——治炮塔乱放。
- DPS 求和撤退阈值——可进 bench.py 信号体系。
- RebuildDestroyStructure 被拆原地重建——与 O15 重建逻辑互补。
