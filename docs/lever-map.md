# 操纵杆 → bot 动作 映射图

> 参谋长(LLM)写 `orders.json` 的每个字段,最终落到 bot 哪段代码、变成什么动作。
> 改 bot 行为或扩词表前先看这张图。**页内结论与源码冲突时以源码为准。**

## 数据通道

```
LLM 参谋长 ──steer_cli set k=v──▶ orders.json (粘性,原子写)
                                     │ MyBot.on_step 每 4 游戏秒 read_order()
                                     ▼
                            MyBot.steer_order (dict)
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        ▼                            ▼                            ▼
  CombatManager              ProductionManager           OracleManager
  (主力进攻单位)             (造兵/运营/建筑)             (先知骚扰)
```

- bot 每 `_STEER_EVERY = 4.0` 游戏秒发布一次 `state.json`、读一次 `orders.json`(`main.py`)。
- 命令**粘性**:写了一直生效,直到改它或 `clear`。
- 兵种不再硬编码:`CombatManager` / `ProductionManager` 从 `army_composition.yml` 读该指挥/该造哪些兵(见 `bot/army_config.py`)。

## 每个操纵杆的落点

| 操纵杆 | 取值 | 消费者 | 落到什么动作 | 代码位置 |
|---|---|---|---|---|
| **stance** | attack/defend/retreat/hold | CombatManager | defend/retreat→回家集结；hold→`update()` 直接 return 全军不动；attack→走 attack_target | `combat_manager.py` `attack_target`/`update` |
| **target** | enemy_main/natural/third/fourth/backdoor/map_center/home | CombatManager `_resolve_steer_target` | 语义目标→Point2。enemy_natural/third/fourth 查**已知敌方城镇厅**(`levers.pick_known_base`)，没探到返回 None 不硬冲空地 | `combat_manager.py` + `bot/levers.py` |
| **focus** | weakest/closest/workers/&lt;兵种名&gt; | combat class `_pick_focus`→`levers.pick_focus_key` | 射程内选目标：weakest=血+盾最少；workers=挑农民；closest=离本单位最近(需 origin)；兵种名=精确点名 | `tempest_offensive.py`/`generic_offensive.py` + `bot/levers.py` |
| **maneuver** | ambush/hold_position | combat class | 附近有敌但没进射程时**不追击**，继续蹲向目标点等敌进射程 | `tempest_offensive.py`/`generic_offensive.py` |
| **trigger** | now/when_maxed/when_enemy_away | CombatManager.update→`levers.should_hold_for_trigger` | when_maxed→supply&lt;190 不动；when_enemy_away→敌主力在家就不动 | `combat_manager.py` + `bot/levers.py` |
| **harass** | on/off | OracleManager | off→把 HARASSING 的 oracle 转成 SCOUTING 待命 | `oracle_manager.py` |
| **expand** | yes/no | ProductionManager `_handle_manual_build` | = build=nexus 别名，一次性开一矿 | `production_manager.py` |
| **build** | nexus/assimilator/stargate/... +别名 | ProductionManager `_handle_manual_build`→`_resolve_buildable`→`levers.resolve_build_name` | 一次性锁定"当前数+1"为目标，造到即停；nexus 走 ExpansionController，assimilator 走 _build_gas，其余走 BuildStructure | `production_manager.py` + `bot/levers.py` |
| **scout** | on/off | MyBot `_handle_scout` | on→派一个 probe 去焦点敌主基，摸到就撤回采矿，死了不补 | `main.py` |
| **enemy** | E1/E2/E3/E4 | MyBot `focused_enemy_start`→`levers.resolve_enemy_slot` | 所有 enemy_* 目标/侦察/骚扰相对它解析；1v1 无效 | `main.py` + `bot/levers.py` |
| **note** | 自由文本 | 无人消费 | 只给人看，不进 bot 逻辑 | — |

## 三个关键设计细节

1. **"粘性 vs 一次性"双模式**（见 `levers.ONE_SHOT_FIELDS`）:
   - 粘性:stance/target/focus/maneuver/harass/trigger/enemy —— 一直生效。
   - 一次性锁定:build/expand/scout —— 靠 `_build_key/_build_target`、`_scout_done` 状态锁,造到/派过即停。**重下同值是 no-op**,想再来必须先 `clear`。

2. **target 的安全回退**:`_resolve_steer_target` 对 enemy_natural/third/fourth 查**实际探到的**敌方城镇厅,没探到返回 None,`attack_target` 回退默认追敌 —— 防"硬冲空地"。

3. **人机共驾让权**:`_handle_player_control` 用 `is_selected` + `state.actions` 双信号判断司令在微操,让权 3 秒,超时自动收回。`raw_affects_selection=False` 是关键开关。

## 纯逻辑抽离(可离线单测)

以下"给定输入算输出"的纯函数抽到 `bot/levers.py`,由 `tests/test_levers.py` 覆盖(28 例,不起游戏):
`resolve_enemy_slot` / `pick_known_base` / `pick_focus_key` / `resolve_build_name` /
`should_hold_for_trigger` / `is_one_shot`。词表校验在 `bot/steer_vocab.py`(`validate_field`/`validate_order`)。
