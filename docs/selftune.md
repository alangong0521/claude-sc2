# B8 自调参(selftune)—— 档内运行时调参骨架

> 落地：2026-07-23。状态：**骨架已建，未接钩子、未跑局验证**(爬山行为全部标「未验证」)。
> 来源：`docs/community-tactics-research.md` B8 条目(12PoolBot leitwerk + ares DataManager),
> 零依赖自实现(只用标准库 + json,不 import ares/sc2)。
> 代码:`ares-bot/bot/selftune.py`;单测:`ares-bot/tests/test_selftune.py`。

## 1. 这是什么 / 与 promotion.py 的分工

| | promotion.py | bot/selftune.py |
|---|---|---|
| 粒度 | **档位资格**:某流派能不能从 Hard 升 Harder | **档内调参**:当前档位里阈值取多少更优 |
| 时机 | 离线 runner,打 best-of-N 矩阵 | 运行时,每局 on_start/on_end |
| 改什么 | 不改参数,只判定晋级/停档 | 按族微调数值阈值(步长内置) |
| 产出 | `bench/promotion.json` | `bench/selftune-params.json` |

两者互补不冲突:promotion 决定「在哪一档打」,selftune 决定「用哪组参数打」。

## 2. 参数清单(8 个,默认值=代码现行阈值)

| 字段 | 默认 | 步长 | 区间 | 出处 |
|---|---|---|---|---|
| `blink_shield_perc` | 0.25 | 0.05 | 0~0.6 | `bot/combat/stalker_offensive.py:68` |
| `blink_when_swarmed` | 4 | 1 | 2~8 | `bot/combat/stalker_offensive.py:69` |
| `rally_min_army` | 14 | 2 | 0~30 | `flows.yml:85`(stalker 流),消费于 `bot/managers/combat_manager.py:78` |
| `bank_threshold` | 400 | 100 | 0~1000 | `bot/managers/production_manager.py:893`(`minerals > 400` 追加产能) |
| `expand_advantage_supply` | 12 | 2 | 0~30 | `flows.yml:113` `auto_expand.advantage_supply`,消费于 `bot/production_plans.py:130` |
| `attack_maxed_threshold` | 190 | 5 | 150~200 | `bot/levers.py:114` `should_hold_for_trigger(maxed_threshold=190)` |
| `worker_evac_threshold` | 4 | 1 | 2~10 | `bot/production_plans.py:369` `should_evacuate_workers(threshold=4)` |
| `anti_air_trigger` | 3 | 1 | 1~8 | `flows.yml:67` `anti_air_trigger` |

注意:这些是 selftune **建议的取值空间**。当前生产代码仍各自读自己的常量/配置;
要让 ask 的结果真正生效,主 agent 接钩子时需把对应读取点改成吃 `SelfTuneParams`
字段(见 §4「生效面」)。

## 3. ask / tell 语义

```python
from bot.selftune import SelfTuner, TellRecord

tuner = SelfTuner()                       # 默认 bench/selftune-params.json
params = tuner.ask({"enemy_race": "Zerg"}) # → SelfTuneParams(按族条件化)
# ... 打一局,params 的字段喂给各读取点 ...
tuner.tell(TellRecord(flow="stalker", difficulty="Hard", race="Zerg",
                      build="Rush", result="win", game_time=self.time,
                      kill_value=..., loss_value=...))
```

- **ask(context)**:返回 `SelfTuneParams`。取值优先级:dataclass 默认值 ← 静态按族
  覆盖表(`RACE_OVERRIDES`,手工先验,未验证)← 学到的按族 override(落盘在
  checkpoint)。总记录 ≥20 局(`MIN_RECORDS`)后,ask 还会先走一步爬山再取参。
- **tell(record)**:追加一条 `(flow, difficulty, race, build, result, game_time,
  kill_value, loss_value)`,自动补算效率分 `log1p(kill) − log1p(loss)`,落盘。
  写盘失败返回 False,不炸 bot。
- **爬山规则(未验证)**:同族最近 5 局(`WINDOW`)胜率 <40%(`WINRATE_FLOOR`)→
  把轮换到的「被怀疑参数」往**上一步的反方向**走一步(步长见参数表,钳位在区间内),
  然后轮换到下一个参数,避免在单参数上震荡。胜率达标或样本不足则不动。

## 4. 集成方式(主 agent 统一加钩子,本骨架不动现有文件)

- `bot/main.py` `on_start`:`self._selftune = SelfTuner()`;
  `self._tune_params = self._selftune.ask({"enemy_race": self.enemy_race})`。
- `bot/main.py` `on_end`(现被注释,见 `bot-self-tuning-plan.md` §1 头号缺口):
  恢复后调 `self._selftune.tell(TellRecord(...))`,`result` 用 `str(game_result)`
  归一(`win/victory/loss/defeat` 都认,`tie` 不计胜率)。
- **生效面**:ask 出的字段要接到这些读取点才真正调参——
  `StalkerOffensive` 的 `blink_at_shield_perc`/`blink_when_swarmed`、
  combat_manager 的 `_rally_min`、production_manager 的 `minerals > 400`、
  levers 的 `maxed_threshold`、production_plans 的 `threshold`、flows.yml 的
  `auto_expand.advantage_supply`/`anti_air_trigger`。接之前 selftune 只是
  「记录 + 学习」,不改变行为——可以安全先上线攒数据。

## 5. 存储 schema(bench/selftune-params.json,bench/ 已 gitignore)

```json
{
  "schema": 1,
  "records":  [ {"flow": "...", "difficulty": "...", "race": "...", "build": "...",
                 "result": "win", "game_time": 600.0, "kill_value": 3000,
                 "loss_value": 1500, "efficiency": 0.7} ],
  "overrides": { "zerg": {"rally_min_army": 16} },   // 学到的按族覆盖
  "climb":     { "zerg": {"idx": 2, "direction": -1} } // 爬山轮换指针
}
```

容错约定:文件不存在/坏 JSON → 全默认;记录缺字段 → 补默认;未知顶层键 →
load/save 往返原样保留(schema 演进不丢旧 checkpoint)。写盘走临时文件 +
`os.replace`,不留半截文件。

## 6. 已知边界 / 后续

- 爬山是单参数轮换 + 固定步长的最朴素版本,胜率信号方差大(5 局窗口),
  只当初始骨架;有效步长/窗口都要跑局标定(**未验证**)。
- 静态 `RACE_OVERRIDES` 是手工先验,同样未验证。
- 学习效率分目前只落盘、未参与爬山决策(爬山只看胜负);后续可用它做
  「赢了但交换比恶化 → 也算退步」的细化。
- 接钩子前记得先恢复 `on_end`(`main.py:316` 附近,当前注释状态)。
