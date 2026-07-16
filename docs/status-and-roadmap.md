# 优化落地状态 + 排期

> 本轮目标:离线(不开 SC2)能做的全做掉,做不了的(需跑局验证)写清楚排期。
> 所有改动都过 `python3 -m unittest`(44 例,0 依赖游戏)+ `py_compile` 语法校验。

## 已落地(离线可验,已验)

| 项 | 内容 | 验证方式 |
|---|---|---|
| **A1** | `gen_skill_vocab.py`:从 `steer_vocab.py` 生成 SKILL.md 词表段(标记内),`--check` 防漂移 | `gen_skill_vocab.py --check` ✅ |
| **A2** | SKILL.md 铁律 2 加「下令 checklist」(set→校验→show→别阻塞轮询) | 文档 |
| **A3** | 「一次性 vs 粘性」提到铁律层 + 词表尾说明 | 文档 |
| **A4** | `steer_cli set` 校验 key/value,非法报错不写盘(exit 2);`validate` 只读校验 | CLI 实测 ✅ |
| **A5** | `focus=closest` 真正实现(按 origin 距离挑),不再退化成默认 | `test_levers` ✅ |
| **A6** | build 别名对齐:`vocab` 列别名;两套别名表加交叉注释;`levers.resolve_build_name` 归一 | `test_levers` ✅ |
| **A7** | 纯逻辑抽 `bot/levers.py`(6 函数)+ `steer_vocab` 校验函数,manager 复用 | `test_levers`(28) ✅ |
| **A8** | 流派知识挪 `ares-bot/build_meta.md`,SKILL.md 改为引用它 | 文档 |
| **C1** | `STEER_RECORD=<dir>` 录制 state 快照 + `tests/fixtures/` 样本 + 回放测试骨架 | `test_state_fixture` ✅ |
| **C2** | `steer_cli set --dry-run` 只校验不写盘(离线可跑,无需 bot) | CLI 实测 ✅ |
| **C3** | `docs/lever-map.md` 操纵杆→动作完整映射图落盘 | 文档 |
| **兵种配置化** | `army_composition.yml` + `bot/army_config.py`;Production/Combat 从它读,不再硬编码 TEMPEST | `test_army_config`(12) ✅ |
| **多兵种指挥** | `CombatManager` 按 army_config 逐兵种分派 combat class;新增 `generic_offensive.py` 通用作战 | `py_compile` ✅,**交战手感待跑局** |

新增测试:`test_levers`(28)+`test_army_config`(12)+`test_state_fixture`(4)= **44 例全绿**。

## 待排期(必须开 SC2 跑局才能验)

这些**代码可以改,但改得好不好只有跑局知道**。建议排在「哪天能开游戏」的窗口一起做。

| # | 项 | 为什么必须跑局 | 优先级 |
|---|---|---|---|
| **B0** | `generic_offensive.py` 交战手感(风筝距离/集火/寻路)逐兵种调 | 通用作战已能动,但阵型/走位好不好要看实战 | 高(多兵种前置) |
| B1 | 数值平衡:开二矿时机、暴风舰攒几艘压上、`when_maxed=190` 阈值 | 战术决策,不跑=猜 | 高 |
| B2 | `_enemy_near_their_base` 的 25 距离、`when_enemy_away` 灵敏度 | 地图尺度相关 | 中 |
| B3 | oracle `ORACLE_WEAPON_COOLDOWN=5`、`oracle_harass_active` 的 25 aa_dps | 实战节奏 | 中 |
| B4 | `_backdoor` 绕后启发式 | 地图/局势 | 低 |
| B5 | `_build_extra_stargates` 的 `minerals>400`、封顶 6 | 经济曲线 | 低 |
| B6 | 参谋提议质量(威胁判断/建议是否合理) | 需真实 state 喂 LLM;可用 C1 fixture 半离线逼近 | 高 |
| B7 | 新兵种的科技/升级链(`DESIRED_UPGRADES` 仍是暴风舰专属) | 换主力兵种要配套改升级,需实测科技顺序 | 中 |

### 跑局时的验证清单(照着做)
1. `poetry install`(首次,慢)。
2. 冒烟:`REALTIME=False poetry run python run.py` 能跑完一局出胜负。
3. 录 fixture:`STEER_RECORD=$PWD/tests/fixtures/rec1 REALTIME=False poetry run python run.py`,
   之后 `STEER_REPLAY_DIR=$PWD/tests/fixtures/rec1 python3 -m unittest tests.test_state_fixture` 回放。
4. 多兵种冒烟:改 `army_composition.yml` 放开一个 `combat: default` 兵种(如 STALKER),跑一局看它
   是否被造出来且会压向 attack_target;再调 B0。

## 多兵种 / 多种族(ares-sc2 复用 + 现状)

### army_composition.yml 现在是 per-race
顶层三块 `protoss/terran/zerg`,bot 按自己的种族(`ai.race`)选块(`army_config.bot_race_name`
+ `_select_block`,回退 protoss)。`spawn_dict()` 只喂 `proportion>0` 的兵种给 SpawnController;
`proportion=0` = "控制层已就绪但不入产"。**protoss 块的产出仍恰是 `{TEMPEST:1.0}`,与已验证行为逐位一致**。

- Protoss:主力 TEMPEST(1.0)+ ORACLE(骚扰,单独造);备选 STALKER/VOIDRAY/IMMORTAL 已登记
  (proportion=0,场上有就指挥,调 >0 即混编,需对应科技 + 跑局验证)。
- Terran:MARINE/MARAUDER/SIEGETANK/MEDIVAC 组成已写(combat=default)。
- Zerg:ZERGLING/ROACH/HYDRALISK 组成已写(combat=default)。

### ares-sc2 里能直接复用的(已核对 vendored 源码)
| 组件 | 用处 | 种族 |
|---|---|---|
| `SpawnController` | 按 army_comp 造兵,**已支持 Zerg larva/morph、Terran train、Protoss warp-in** | 全 |
| group 战斗行为(`stutter_group_back`/`a_move_group`/`path_group_to_target`) | 队级微操,比逐单位省事,是 generic_offensive 的升级路线 | 全 |
| 个体微操原语(`siege_tank_decision`/`ghost_snipe`/`medivac_heal`/`place_predictive_aoe`/`stutter_unit_back` 等 26 个) | 写专属 combat class 的积木 | 全 |
| `UpgradeController(desired_upgrades=[...])` | **种族无关**的自动研究升级,可替代硬编码的暴风舰专属 `DESIRED_UPGRADES`(解 B7) | 全 |
| `ProductionController` | 按 army_comp 自动补生产建筑 | **仅 Terran/Protoss,不支持 Zerg** |

### 诚实的边界:控制层就绪 ≠ 能打的 T/Z bot
- ✅ **控制 + 造兵层已多种族**:SpawnController(造)+ CombatManager 分派(指挥)对任意种族兵种都通。
- ❌ **科技/生产层仍是 Protoss 专属**:当前 `ProductionManager` 只建 Protoss 结构(pylon/stargate/
  chrono/tempest 链)。要真正 field Terran/Zerg 需:(a)`BOT_RACE` 切成该种族;(b)补该种族科技层
  —— Terran 可接 ares `ProductionController`;**Zerg 不支持 ProductionController**,得靠 build order
  (`zerg_builds.yml` 已有 Standard)或自定义 morph 逻辑。这些**必须跑局**,列为下方排期。

### 多种族排期(需跑局)
| # | 项 | 状态 | 依赖 |
|---|---|---|---|
| M1 | Terran 生产层:用 `ProductionController` 替代 Protoss 专属建筑逻辑 | **🚧 开了头(骨架落地,待跑局)** | 跑局 |
| M2 | Zerg 生产层:build order + larva/morph 自定义(ProductionController 不支持) | 未开始(当前 stub:只维农民+补给) | 跑局 |
| M3 | 升级配置化:`UpgradeController` + army_composition 里加 `upgrades:` 字段(解 B7,种族无关) | **✅ 落地(骨架)** | 跑局验时机 |
| M4 | 专属 combat class:SIEGETANK 架起 / MEDIVAC 治疗(用 ares 原语) | **🚧 开了头(坦克+医疗落地;storm/运兵待做)** | 跑局 |
| M5 | generic_offensive 升级到 group 行为(队级) | 未开始 | 跑局调手感 |

#### M3 已落地(升级配置化,解 B7)
army_composition.yml 每种族块加 `upgrades:` 列表(引擎 UpgradeId 名);`army_config` 解析
(`upgrade_names` 纯逻辑 / `upgrade_ids` 运行时转枚举,认不出静默跳过)。
- Protoss:`_research_upgrades` 改从 `self._army.upgrade_ids() or DESIRED_UPGRADES` 取
  —— protoss 块列**同样 3 项** → **行为逐位不变**,只是可配。
- Terran:`_update_terran` 用 ares `UpgradeController(upgrade_list, base_location)`(种族无关自动 tech-up)。
待跑局:研究时机/顺序。

#### M4 开了头(专属 combat class,已落地坦克+医疗)
- `combat=siege_offensive`(`bot/combat/siege_offensive.py`):ares `SiegeTankDecision` 自动架/撤 + AMove 推进。
- `combat=medivac_support`(`bot/combat/medivac_support.py`):ares `MedivacHeal` 治疗跟队。
- 注册进 `CombatManager._combat_dispatch` + `army_config.COMBAT_KINDS`;Terran 的 SIEGETANK/MEDIVAC 已切过去。
**未跑局验证**:架起时机/站位、跟队距离、运兵(pick_up/drop_cargo)、高模 storm(用 `place_predictive_aoe`)是 M4 剩余项。

#### M1 已落地(离线,骨架)
`ProductionManager.update` 按 `ai.race` 分派:Terran → `_update_terran`,Zerg → `_update_zerg_stub`,
Protoss → 原逻辑不变。`_update_terran` 全借 ares 宏行为(不手写建造序):
`AutoSupply`+`BuildWorkers`+`GasBuildingController`+`ProductionController`(人族/神族支持,按 army_comp
自动补 rax/factory/starport)+`SpawnController`+`UpgradeCCs`(升轨道)+ build/expand 杠杆(种族无关)。
农民/气目标抽到 `bot/production_plans.py`(纯逻辑,`test_production_plans` 9 例)。
**M1 待跑局(未验证)**:建造时机、addon(techlab/reactor)管理、开局序(可交 `terran_builds.yml` 的
build runner)、与 M4 的架坦克/运兵专属微操。当前 Terran 能造建筑+出兵+补农民,但手感/平衡未测。

## 怎么加一个新兵种(用户问的重点)

**改一个 yaml 就能让 bot 造 + 指挥新兵种**,不用动 Python(前提:该兵种用现成 combat class)。

1. 编辑 `ares-bot/army_composition.yml`,在**对应种族块**(`protoss:`/`terran:`/`zerg:`)的
   `units:` 下加一项:
   ```yaml
     - id: STALKER            # 引擎枚举名(sc2 UnitTypeId),全大写
       proportion: 0.4        # 目标占比(同块内 >0 之和 ≤ 1.0);0=登记但不入产,只受指挥
       priority: 1            # 造兵优先级(越小越先),0=最高
       role: ATTACKING        # ATTACKING 归 CombatManager 指挥
       combat: default        # 用通用作战(generic_offensive);暴风舰用 tempest_offensive
       notes: 追猎,补对空火力(暴风舰被凤凰克时)
   ```
   同时把主力 `proportion` 调低,让两者之和 ≈ 1.0。
2. 就这样。`ProductionManager` 读它喂 `SpawnController`(自动补生产建筑),`CombatManager`
   读它把该兵种的 ATTACKING 单位交给 `combat: default` → `generic_offensive` 指挥。
3. **验证**:跑一局看它被造出来、会压上、会打(B0/B7 可能要调)。

### 三个边界(加兵种前必读)
- **combat 只有三种**:`tempest_offensive`(暴风舰远射风筝)/ `oracle_harass`(先知,OracleManager 单独管)/
  `default`(通用,`generic_offensive`,**未跑局验证**)。要更精细的兵种微操(如攻城坦克架起、
  不朽护盾)得**新写一个 combat class** 并在 `CombatManager._combat_dispatch` 注册。
- **科技/升级还没配置化**:`DESIRED_UPGRADES`、chrono 逻辑仍偏暴风舰(见 B7)。换**主力**兵种时
  这块要一并改;只是**添**辅助兵种通常不受影响。
- **proportion 校验**:总和 > 1.0 会在加载时报错(`army_config._validate`);oracle 这种 0 占比
  单独存在是允许的。

## 关键文件索引

| 文件 | 作用 |
|---|---|
| `ares-bot/army_composition.yml` | **兵种单一真相源**(造什么/怎么指挥) |
| `ares-bot/bot/army_config.py` | 解析上表,给 Production/Combat 用;纯逻辑可单测 |
| `ares-bot/bot/levers.py` | 操纵杆纯逻辑(目标/焦点/择时/build 归一) |
| `ares-bot/bot/steer_vocab.py` | 词表 + 校验(单一真相源) |
| `ares-bot/bot/combat/generic_offensive.py` | 通用作战(combat=default),**待跑局调** |
| `ares-bot/build_meta.md` | 流派知识(参谋开局介绍读它) |
| `ares-bot/gen_skill_vocab.py` | 从词表生成 SKILL.md 词表段 |
| `docs/lever-map.md` | 操纵杆→动作映射图 |
| `ares-bot/tests/` | 44 例离线单测(不需游戏) |
