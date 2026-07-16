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

## 怎么加一个新兵种(用户问的重点)

**改一个 yaml 就能让 bot 造 + 指挥新兵种**,不用动 Python(前提:该兵种用现成 combat class)。

1. 编辑 `ares-bot/army_composition.yml`,在 `units:` 下加一项:
   ```yaml
     - id: STALKER            # 引擎枚举名(sc2 UnitTypeId),全大写
       proportion: 0.4        # 目标占比(所有 proportion 之和 ≤ 1.0)
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
