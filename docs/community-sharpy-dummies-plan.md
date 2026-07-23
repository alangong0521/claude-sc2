# 社区调研:sharpy-sc2 dummies 流派编目与 flows.yml 落地草案

- 调研日期:2026-07-23
- 来源仓库:https://github.com/DrInfy/sharpy-sc2(`git clone --depth 1`,克隆于 2026-07-23,HEAD 未记录具体 commit hash——浅克隆后未读 git 元数据,遵守不做 git 操作的约定)
- 本地路径:`/Users/calla/work/sc2-community/sharpy-sc2/`
- 对照格式:`/Users/calla/work/claude-sc2/ares-bot/flows.yml`(tempest/stalker/carrier/dt 四块)
- 所有"sharpy 源码事实"均引自上述仓库文件路径;凡未在代码中验证的点已显式标注"未验证/推断"。

## 0. 总览

`dummies/` 共 44 个 bot 文件(不含各目录 `__init__.py`,不含 `run.py`):

| 目录 | 文件数 | 说明 |
|---|---|---|
| `dummies/protoss/` | 12 | 10 个核心流派 + 1 弱版运营(silver)+ 1 随机调度 |
| `dummies/terran/` | 11 | 人族流派(本次仅登记名称,非神族重点) |
| `dummies/zerg/` | 12 | 虫族流派(同上) |
| `dummies/debug/` | 9 | 调试/沙盒 bot,非流派 |

`dummies/protoss/protoss_random.py:3-25` 用 `random.randint(0,9)` 在 10 个核心流派间等概率随机——即官方认定的 protoss 流派清单就是这 10 个。

## 1. 编目表(神族,全部 12 个)

来源均为 `https://github.com/DrInfy/sharpy-sc2/blob/develop/dummies/protoss/<file>`。

| # | 文件 | Bot 名(代码内字符串) | 流派 | 建造链关键点 | 核心战术 | 适用对局 |
|---|---|---|---|---|---|---|
| 1 | `gate4.py` | "The Sharp Four" | 4-gate blink 追猎 | 14 水晶/16 BG/17 双气/19 第 2 BG;BY 好后先出 2 使徒(only_once),升折跃;BY 就绪下暮光议会,议会就绪升 blink(ChronoTech 加速);BY 存在即补到 4 BG(`gate4.py:55-88`) | blink 完成 90% 即出门(`Step(TechReady(BLINKTECH, 0.9), attack)`,`gate4.py:96`),PlanZoneAttack(6) 且关闭优势判断(attack_on_advantage=False,`gate4.py:45`) | 一波 all-in,对三族通用;sharpy 经典 PvT/PvZ 压制流派(风格定位为 all-in,不扩张——代码中无 Expand) |
| 2 | `macro_stalkers.py` | "Sharp Spiders" | 运营追猎 | 14 水晶/16 气 1/BG/20 二矿(`Expand(2)`)/BY/21 气 2;升折跃;农民 22→(2 矿后)44;7 BG + 3~4 气(`macro_stalkers.py:26-48`) | 4 BG 就绪即进攻(`Step(UnitReady(GATEWAY,4), PlanZoneAttack(4))`,`macro_stalkers.py:57`),无 blink/无科技纯靠产能 | 两矿运营一波,适合对抗中期兵力薄的运营型对手;无反隐/无空军,怕隐刀和空军(推断,代码无对策) |
| 3 | `dark_templar_rush.py` | "Sharp Shadows" | DT rush | 14 水晶/16 气 1/16 BG/双气;BY→暮光→黑暗圣坛(`dark_templar_rush.py:17-20`);升 blink + 冲锋;黑坛就绪后优先出 4 DT(priority=True),之前靠 1 叉+追猎过渡;主矿低矿时才开二矿(`dark_templar_rush.py:31`) | 专用 `DarkTemplarAttack()` 战术(sharpy.plans.tactics.protoss,`dark_templar_rush.py:103`);PlanZoneAttack(20) 且 retreat_multiplier=0.5 偏 all-in(`dark_templar_rush.py:93-94`) | 对无反隐的对手(尤其 TvP 渡鸦/扫描前、ZvP 眼虫前)白打农民;对面出反隐后靠 blink 追猎+冲锋叉续命 |
| 4 | `robo.py` | "Sharp Robots" | 机械台不朽 | 14 水晶/16 气 1/BG/20 二矿/BY/21 气 2;先出 2 追猎防身;BY 就绪下暮光,随后机械台;暮光就绪升冲锋;不朽 chrono 加速(`ChronoUnit(IMMORTAL, ROBOTICSFACILITY)`,`robo.py:34`);机械台产出序列:不朽 1→OB 1→不朽至 20(`robo.py:69-73`);5 分钟开三矿,后补第 2 机械台 | 3 不朽就绪即进攻(`Step(UnitReady(IMMORTAL,3), attack)`,`robo.py:92`),不朽+叉(100 上限叉子) | 克重甲地面:TvP 打坦克/机械化、PvP 打追猎不朽对拼;OB 保证不怕隐刀。怕空军(地面阵容,推断) |
| 5 | `one_base_tempests.py` | "One Base Tempest" | 单矿暴风舰(龟缩) | 14 水晶/15 BG/**同时下锻炉**/双气;BY 后星门→舰队航标;暴风舰 chrono;航标存在补第 2 星门(`one_base_tempests.py:22-42`);`DefensiveCannons(4, 2, 0)` 主矿 4 塔(`one_base_tempests.py:43`) | 首艘暴风舰出生即进攻(`Step(UnitExists(TEMPEST,1), attack)`,`one_base_tempests.py:51`),单矿塔防龟缩憋舰队 | 单矿 all-in 型天空体;经济极脆,靠塔防过渡。与我们 tempest 流同源但激进得多(我们不铺 4 塔、走多矿) |
| 6 | `voidray.py` | "Sharp Rays" | 运营虚空舰 | 14 水晶/16 气 1/BG/20 BY/21 二矿/22 气 2;先 2 追猎;暮光议会(冲锋+使徒攻速两个升级都点,`voidray.py:65-66`);星门虚空 chrono;地面按 6 叉/10 使徒阶梯补;5 分钟三矿,后补第 2 星门(`voidray.py:69-83`) | 3 虚空就绪进攻(`voidray.py:93`),虚空主力+叉使徒地面 | 两矿运营空军流;虚空对重甲加成,打机械化/蟑螂好;怕维京/凤凰/腐化(推断) |
| 7 | `adept_allin.py` | "Sharp Shades" | 使徒 all-in / 幻象骚扰 | 水晶→14 农民→BG→16→气 1→17→第 2 BG→20;BY 好后 2 使徒(only_once)→折跃→纯使徒 100;BY 存在且矿>200 补到 4 BG;气<25 且矿>200 时改刷叉(`adept_allin.py:43-79`) | **DoubleAdeptScout(number)** 双使徒幻象骚扰(`adept_allin.py:89`,number=random 10~15);使徒 >10 才进攻(`TheAttack._should_attack`,`adept_allin.py:25-26`) | 单矿~一波;使徒幻象白嫖农民,对 Z(无女王外对空)/T(无导弹塔)效果好;对 P 追猎乏力(推断) |
| 8 | `cannon_rush.py` | "Sharp Cannon" | 塔 rush(三变体) | 13 农民水晶后开 rush;`ProxyCannoneer` 派两农民沿"敌二矿→斜坡→主矿"路径递进铺水晶+光子塔(`cannon_rush.py:22-189`);三变体由 `select_build_index` 选:cannon_rush(骑脸)/cannon_contain(封二矿)/cannon_expand(塔护自开二矿)(`cannon_rush.py:201-217`);rush 失败判定:死 3 农民或 4 分钟(`cannon_rush.py:208-210`) | 塔阵推进;失败/超时后转追猎+blink+锻炉全攻防的运营 backup(`cannon_rush.py:231-260`) | 对 Z 变体不同(塔位布局按敌族分支,`cannon_rush.py:51-56`);天梯心理战流派;对会防的玩家易血亏,所以 sharpy 自带完备转运营后路 |
| 9 | `proxy_zealot_rush.py` | "Sharp Knives" | 野兵营叉 rush | 17 农民停农,1 水晶后 ProxySolver 在地图中心偏敌 25 格处规划 1 水晶+4 BG 野点矩阵(`proxy_zealot_rush.py:26-93`);chrono 叉子;PlanZoneAttack(7)、retreat_multiplier=0.3 极激进(`proxy_zealot_rush.py:163-164`) | 野 4BG 刷叉骑脸;**Supply 50 后整个 proxy 计划被 skip,切换 backup**:开二矿转虚空+追猎+使徒运营(`proxy_zealot_rush.py:237,166-217`) | 对 P 专用墙(`WallType.ProtossMainProtoss`,`proxy_zealot_rush.py:162`);rush 和运营双阶段设计值得借鉴 |
| 10 | `disruptor.py` | "Sharp Spheres" | 干扰者(炸球) | 2BG→双气→BY→机械台→折跃→机械研究所;机械台 chrono 序列:不朽 1→OB 1→炸球 1;首炸出生后开二矿、补 4 气;炸球至 4,之后纯追猎;二矿后 6 BG(`disruptor.py:43-66`) | 首炸球出生即进攻(`Step(UnitExists(DISRUPTOR), PlanZoneAttack())`,`disruptor.py:79`);有 `PlanWorkerOnlyDefense` 防农民 rush(`disruptor.py:76`) | 炸球克聚团地面(枪兵/小狗/叉);对操作敏感的爆发型流派 |
| 11 | `protoss_silver.py` | "Silver Protoss" | 弱版运营追猎(降难度陪练) | 与 macro_stalkers 几乎同构,但 `game_step=20` 降帧、用 `WeakDefense/WeakAttack(30)` 替代标准战术(`protoss_silver.py:21-22,61-65`) | 白银水平陪练 bot | 不作流派参考;可作我方新流派的跑局对手 |
| 12 | `protoss_random.py` | — | 随机调度器 | 等概率抽上表 1~10(`protoss_random.py:3-25`) | — | 思路可参考:我们未来做多流派随机时同款结构 |

### 人族/虫族(仅登记,未深入)

- terran(`dummies/terran/`):banshees "Rusty Screams"、battle_cruisers "Flying Rust"、bio "Rusty Infantry"、cyclones "Rusty Locks"、marine_rush、one_base_turtle、rusty "Old Rusty"、safe_tvt_raven、terran_silver_bio、two_base_tanks、terran_random。
- zerg(`dummies/zerg/`):lings(Ling Flood/Ling Expand Speed)、lurkers "Blunt Lurkers"、macro_roach "200 roach"、macro_zerg_v2 "Macro zerg"、mutalisk "Blunt Flies"、roach_burrow "Blunt Burrow"、roach_hydra、twelve_pool、worker_rush、zerg_random、zerg_silver。

## 2. flows.yml 候选流派落地草案

格式对照 `ares-bot/flows.yml` 现有四块。以下草案均为**首次落地建议值**,兵种配比/阈值未经跑局验证(标注"待跑局")。sharpy 的 `PlanZoneAttack(N)` 语义=N 个单位才进攻,映射到我们的 `rally_min_army`;sharpy 的 chrono 目标映射 `chrono.targets`。

### 2.1 四门类 blink 追猎(gate4 → 新流派 `gate4_blink`)

sharpy 要点:blink 90% 即出门、4 BG、BY 先 2 使徒再升折跃、纯追猎。我们 flows.yml 没有"固定 4 BG 上限"的表达,用 extra_production 的 cap=4 近似。

```yaml
  # 4-gate blink 追猎(sharpy gate4.py 移植):blink 好即一波,无扩张
  gate4_blink:
    spawn:
      STALKER: {proportion: 1.0, priority: 0}
    core_structures: [GATEWAY, CYBERNETICSCORE, TWILIGHTCOUNCIL]
    upgrades:
      - WARPGATERESEARCH
      - BLINKTECH
    extra_production: {id: GATEWAY, cap: 4, base: 1}   # sharpy 固定 4BG,不随基地数涨
    chrono: {targets: [TWILIGHTCOUNCIL], when: always}  # sharpy ChronoTech 全程加速 blink
    one_off: [ADEPT]          # sharpy BY 好后先出 2 使徒骚扰;one_off 只支持 1 个,待跑局看是否改源码
    rally_min_army: 10        # sharpy PlanZoneAttack(6) + attack_on_advantage=False;取 10 防分批送
    freeflow: true
    pivot:                    # 与 dt 同款反空军兜底
      anti_air_units: []      # 追猎本身对空,无需混入
      rush_zealots: 2
    # 注意:本流派不开 auto_expand —— sharpy 原版就是无扩张一波
```

落地缺口(如实标注):sharpy 的"blink 90% 出门"是科技进度触发,我们 rally_min_army 是兵力数触发,语义不等价;若跑局发现出门时机不对,需要 ProductionManager 侧支持"科技就绪触发 rally",或调 rally_min_army 数值近似。

### 2.2 DT rush(sharpy dark_templar_rush.py vs 我们已有 `dt`)

对比(sharpy 原版 → 我们现状):

| 维度 | sharpy `dark_templar_rush.py` | 我们 flows.yml `dt` 块 | 差异评估 |
|---|---|---|---|
| 链 | BY→暮光→黑坛;blink+冲锋双科技 | GATEWAY, CYBERNETICSCORE, TWILIGHTCOUNCIL, DARKSHRINE;折跃+地攻 1/2 | sharpy 给 DT 配 blink(跳崖/逃生)和冲锋叉;我们没点 BLINKTECH |
| 兵力 | 黑坛就绪优先 4 DT,之前 1 叉+追猎过渡 | 纯 DT, rally_min_army=4 攒 4 把出门 | 一致(sharpy 也是 4 DT 为阈值) |
| 进攻 | PlanZoneAttack(20) + retreat 0.5 all-in + 专用 DarkTemplarAttack 战术 | rally 后由 CombatManager 接管 | sharpy 有 DT 专属收割战术(打农民优先、避反隐),**未验证**我们 CombatManager 对 DT 有无特化,值得查 |
| 退路 | 主矿低矿才开二矿 + 转 blink 追猎/冲锋叉 | auto_expand at:300 转两矿 | 思路一致 |

建议改进项(可并入 dt 块的增量,不算新流派):

```yaml
    upgrades:
      - WARPGATERESEARCH
      - BLINKTECH            # 新增:sharpy DT 流标配,跳崖白打+逃生,升级在暮光议会(链内已有)
      - CHARGE               # 新增:转型后叉子有用;顺序放 BLINKTECH 后
      - PROTOSSGROUNDWEAPONSLEVEL1
      - PROTOSSGROUNDWEAPONSLEVEL2
```

### 2.3 运营追猎(macro_stalkers → 新流派 `macro_stalker`)

sharpy 要点:20 农二矿、44 农两矿饱和、7 BG、4 BG 就绪即进攻。与我们已有 `stalker` 块(纯 blink 骨架,rally 14、150 秒二矿)是近亲——**建议不新增,而是给 stalker 块加一个免 blink 变体或直接用 stalker 块对比跑局**。若坚持单列:

```yaml
  # 运营追猎(sharpy macro_stalkers.py 移植):两矿 7BG 纯产能压制,不点 blink
  macro_stalker:
    spawn:
      STALKER: {proportion: 1.0, priority: 0}
    core_structures: [GATEWAY, CYBERNETICSCORE]     # 不要暮光,气体全留给追猎
    upgrades:
      - WARPGATERESEARCH
      - PROTOSSGROUNDWEAPONSLEVEL1
      - PROTOSSGROUNDARMORSLEVEL1
    extra_production: {id: GATEWAY, cap: 7, base: 2}
    chrono: {targets: [GATEWAY], when: always}
    one_off: []
    rally_min_army: 12          # sharpy 4BG 就绪进攻≈8~12 追猎,待跑局
    auto_expand: {at: 120, to: 2, when_workers: 20}   # sharpy 20 农开二矿,150→120 提前
    freeflow: true
```

### 2.4 机械台不朽(robo.py → 新流派 `robo_immortal`)

sharpy 要点:不朽 chrono、不朽 1→OB 1→不朽至 20、冲锋叉当地面、3 不朽进攻、5 分钟三矿。OB 在 flows.yml 无现成表达,用 one_off 近似。

```yaml
  # 机械台不朽(sharpy robo.py 移植):不朽主力+冲锋叉,克重甲地面
  robo_immortal:
    spawn:
      IMMORTAL: {proportion: 0.4, priority: 0}
      ZEALOT: {proportion: 0.6, priority: 1}
    core_structures: [GATEWAY, CYBERNETICSCORE, TWILIGHTCOUNCIL, ROBOTICSFACILITY]
    upgrades:
      - WARPGATERESEARCH
      - CHARGE
      - PROTOSSGROUNDWEAPONSLEVEL1
    extra_production: {id: ROBOTICSFACILITY, cap: 2, base: 1}   # sharpy 后期补第 2 机械台
    chrono: {targets: [ROBOTICSFACILITY], when: always}          # sharpy 全程 chrono 不朽
    one_off: [OBSERVER]      # sharpy 第 2 个机械台单位就是 OB(反隐兜底);one_off 机制复用
    rally_min_army: 8        # sharpy 3 不朽进攻;3 不朽+5 叉≈8 单位,待跑局
    auto_expand: {at: 150, to: 2, when_workers: 20}   # sharpy 20 农二矿;5 分钟三矿用动态模式待跑局再定
    freeflow: true
    pivot:
      anti_air_units: [STALKER]   # sharpy 原版开局也先出 2 追猎;纯不朽+叉怕空军,必须保这个 pivot
      anti_air_proportion: 0.3
      anti_air_trigger: 3
      rush_zealots: 4
```

### 2.5 天空体(sharpy one_base_tempests.py / voidray.py vs 我们 tempest/carrier)

- `one_base_tempests` 与我们 `tempest` 块科技链完全一致(星门→舰队航标),差异在 sharpy 单矿+4 塔龟缩+首舰即攻。我们已有 E2 动态开矿+expansion_cannons,覆盖面更全,**不建议移植单矿版**,但 sharpy 的"首艘暴风舰出生即进攻"比我们纯 rally 阈值更激进,可作为 tempest 块 rally 参数跑局对照。
- `voidray.py` 的"虚空+阶梯式叉/使徒地面+双科技(冲锋+使徒攻速)"是多兵种混编范例。若未来开 `voidray` 流派:

```yaml
  # 运营虚空(sharpy voidray.py 移植,优先级低,草案未跑局)
  voidray:
    spawn:
      VOIDRAY: {proportion: 0.5, priority: 0}
      ZEALOT: {proportion: 0.3, priority: 1}
      ADEPT: {proportion: 0.2, priority: 2}
    core_structures: [GATEWAY, CYBERNETICSCORE, TWILIGHTCOUNCIL, STARGATE]
    upgrades:
      - WARPGATERESEARCH
      - CHARGE
      - ADEPTPIERCINGATTACK
    extra_production: {id: STARGATE, cap: 2, base: 1}
    chrono: {targets: [STARGATE], when: primary_pending}   # sharpy chrono 虚空
    one_off: []
    rally_min_army: 6          # sharpy 3 虚空进攻
    auto_expand: {at: 150, to: 2, when_workers: 20}
    freeflow: true
    save_up: 150               # 虚空 150 气,p0 占比落后时憋气(对照 O5 注释公式:150-50=100,取 150 更稳)
```

### 2.6 使徒骚扰(adept_allin.py → 新流派 `adept_shade`)

sharpy 核心价值不在建造链而在 `DoubleAdeptScout`(双使徒幻象进家杀农民)——这是**战斗侧战术**,flows.yml 是生产侧单一真相源,装不下它。草案只落生产侧,骚扰行为需要 CombatManager/战术层配合(**未验证我们有无等价物,需查 ares-bot 战术注册表**)。

```yaml
  # 使徒一波(sharpy adept_allin.py 移植,生产侧):4BG 纯使徒,缺气刷叉
  adept_shade:
    spawn:
      ADEPT: {proportion: 0.8, priority: 0}
      ZEALOT: {proportion: 0.2, priority: 1}   # sharpy:气<25 且矿>200 时刷叉兜底
    core_structures: [GATEWAY, CYBERNETICSCORE]
    upgrades:
      - WARPGATERESEARCH
      - ADEPTPIERCINGATTACK     # sharpy voidray 流点了;adept_allin 未点,可选,待跑局
    extra_production: {id: GATEWAY, cap: 4, base: 1}
    chrono: {targets: [CYBERNETICSCORE], when: always}   # sharpy ChronoAnyTech
    one_off: []
    rally_min_army: 11         # sharpy 使徒>10 才进攻(TheAttack._should_attack)
    freeflow: true
    # 无 auto_expand:sharpy 原版单矿一波
```

### 2.7 塔 rush(cannon_rush.py → 建议**暂缓**)

sharpy 塔 rush 的精髓全在 `ProxyCannoneer` 的农民微操:双农民分工(铺水晶/铺塔)、沿敌二矿→斜坡→主矿的递进塔位序列、按敌族分支的塔位、失败判定(死 3 农民/4 分钟)后转完整运营 backup(`cannon_rush.py:22-272`)。这些**没有一条能用 flows.yml 表达**——它是建造位置规划+农民微操,不是生产配比。我们 flows.yml 现有字段(spawn/core_structures/rally/auto_expand)无法承载。若要支持,需要新机制(如 proxy 位置 act),超出"加一块 yaml"的范畴。**结论:登记为长期候选,不进本批 flows.yml。**

同理 `proxy_zealot_rush`(野 4BG 叉)依赖 ProxySolver 建筑网格规划,也超出 yaml 表达能力,但其"Supply 50 后从 rush 切运营 backup"的双阶段思路与我们 pivot 机制同构,可作 pivot 演进参考。

## 3. 建议验证顺序

原则:先落地"纯 yaml 可表达、与已验证块差异最小、能复用现有 pivot/战术"的流派。

1. **`robo_immortal`(2.4)** —— 首推。理由:①链(GATEWAY→BY→暮光→机械台)与 dt 块同构,落地风险最低;②IMMORTAL/OBSERVER 都是常规引擎兵种名,无 FLEETBEACON 那种特判坑;③补上了我们流派池最缺的"地面反重甲+自带反隐(OB)"形态,与 tempest/carrier(空军)、dt(隐身骚扰)、stalker(机动)差异化最大;④sharpy 的 chrono 不朽、不朽→OB→不朽序列都能直接用现有 chrono/one_off 字段表达。
2. **`gate4_blink`(2.1)** —— 第二。与已有 stalker 块只差"固定 4BG+无扩张+暮光提速 blink",适合作为 stalker 块跑局的对照组;唯一风险点是出门触发语义(科技 vs 兵力),跑两局就能看出 rally_min_army 近似够不够用。
3. **dt 块增量升级(2.2)** —— 不算新流派,只是往 dt 的 upgrades 里插 BLINKTECH/CHARGE 两行,改动最小、sharpy 侧证据充分(`dark_templar_rush.py:21-22`),建议在 gate4_blink 之后顺手做。
4. **`adept_shade`(2.6)** —— 第三梯队。生产侧简单,但价值依赖幻象骚扰战术,需先确认战斗侧支持,否则落地就是个"普通使徒一波",泯然众人。
5. **`macro_stalker`(2.3)/`voidray`(2.5)** —— 与现有 stalker/carrier 块重叠度高,作为跑局对照组按需启用,不单独立项。
6. **cannon_rush / proxy_zealot** —— 暂缓,等 flows.yml 之外的机制(proxy 建造规划、农民微操)有立项再说。

## 4. 未验证/存疑清单(诚实声明)

- 浅克隆未记录 HEAD commit;文中行号基于 2026-07-23 克隆时的 develop 分支快照。
- 各草案的 rally_min_army / auto_expand 时间 / 兵种配比均为从 sharpy 语义的人工换算,**未经任何跑局验证**。
- 我方 CombatManager 对 DT、使徒幻象有无兵种特化战术——未查(超出本次调研范围),2.2/2.6 标注处需确认。
- sharpy `ProtossUnit(ADEPT, 2, only_once=True)` 是"恰好 2 个",我们 one_off 语义是"造 1 个即停",2.1 的 one_off: [ADEPT] 只是近似。
- 人族/虫族 dummies 仅登记名称,未读实现;若后续做人/虫族陪练对手选型,需二次调研。
