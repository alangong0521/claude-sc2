# Baselines 与迭代日志（自调优回路）

> 数据来源：`bench.py` 系列（`ares-bot/bench/<tag>/summary.json`）。
> 固定变量：地图 `AbyssalReefLE`（后期 `random`）、对手种族固定、AI build 固定、`REALTIME=False`。
> 判定门槛（docs/bot-self-tuning-plan.md §6）：中档 N=10 ≥7 胜为「显著强于骰子」。

## 晋升矩阵全景（2026-07-21 认证天花板）

promotion.py 逐档打穿「3 族 × 5 风格」矩阵，失败重打一轮，仍不过记「疑似相克」豁免 ≤2 个：

**tempest —— 一路杀到最高档 CheatInsane 才停**

| 档位 | 结果 |
|---|---|
| Medium | 14/15（Zerg/Timing 豁免） |
| MediumHard | **15/15 全穿** |
| Hard | 13/15（Zerg/Timing、Protoss/Rush 豁免） |
| Harder | 14/15（Zerg/Rush 豁免） |
| VeryHard | 14/15（Zerg/Rush 豁免） |
| CheatVision | 14/15（Zerg/Rush 豁免） |
| CheatMoney | 13/15（Terran/Macro、Zerg/Rush 豁免） |
| **CheatInsane** | **12/15 停档**，墙 = 三族 Rush（Terran/Zerg/Protoss Rush，重打两轮 0/4） |

**carrier —— 停在 VeryHard**

| 档位 | 结果 |
|---|---|
| Medium | 6/7（中途跳档未补） |
| Hard | **15/15 全穿**（磁盘实证，全 2-0/2-1） |
| Harder | 13/15（Terran/Timing、Zerg/Rush 豁免） |
| **VeryHard** | **11/15 停档**，墙 = Terran/Air（维京）、Zerg/Rush、Protoss/Air（凤凰）、Protoss/Macro |

墙的共性：**Rush（星空体空窗期被快攻打死）+ 对空兵种（维京/凤凰硬 counter）**——
这正是 pivot 迭代（见下方 A1）要破的。

## Baseline（2026-07-19 凌晨，SC2 Base97563）

| 系列 | tag | 战绩 | 胜率 | 平均时长 | 主力成型 | 终局编成(均值) | 备注 |
|---|---|---|---|---|---|---|---|
| tempest vs Hard | b1-tempest-hard-terran | **10-0** | 1.0 | 632s | ORACLE@249s TEMPEST@290s | TEMPEST×10.4 | 官方已验证流，对照组，符合预期 |
| stalker vs Hard | b2-stalker-hard-terran | **0-10** | 0.0 | 661s | ZEALOT@156s STALKER@215s | （全军覆没） | 见下方根因 |
| carrier vs Hard | b3-carrier-hard-terran | **10-0** | 1.0 | 748s | CARRIER@340s TEMPEST@400s | CARRIER×5.6 TEMPEST×3.0 | **新流派首飞即过**，P0 配置化链路实战验证 |

### B2 stalker 0-10 根因（诊断局 b2-diag 实证）

- 现象：前 5 个兵出门送死后，**~340s 起生产完全停摆**（army=0），存款堆到 5000+，
  建筑（3 gateway、6 pylon）和升级（warpgate/blink/攻防盾全研究）全部正常。
- 根因：ares `SpawnController.execute` 开头——**warpgate 研究完成后，只要还有就绪空闲
  gateway 就 `return False` 停产等变形**；而 vendored ares 没有任何 gateway→warpgate
  变形行为，没人变形 = 永久停产。tempest/carrier 不含 WARPGATERESEARCH 所以不踩。
- 快照诊断字段（`structures`/`upgrades`）已加进 `state.json`（本过程产物）。

## 迭代日志

| # | 日期 | 假设 | 改动 | 系列 | 结果 | 结论 |
|---|---|---|---|---|---|---|
| C1 | 2026-07-19 | 「让 gateway 变形为 warpgate 后，stalker 生产不再停摆，胜率从 0/10 显著提升」 | `production_manager._morph_gateways()`：研究完成后对就绪空闲 gateway 下 `MORPH_WARPGATE` | c1-warpgate-fix-smoke（N=4） | 0-4，但机制层完全修复：t≈321s gateway 全变 warpgate，生产全程不断，存款峰值 5100→565 | **留**（停摆根因消除；胜率未动 → 暴露第二败因，见 C3） |
| C3a | 2026-07-19 | 「集结阈值让兵力攒到 8 再出门，减少分批送死」 | flows.yml `rally_min_army: 8`（仅 stalker）+ `combat_manager` 集结逻辑（司令 stance 优先） | c3a-rally-smoke（N=4） | 0-4，集结生效（289s 攒到 7-9 才接战），但 8 个兵打不过对方 17-25 的波次；全程单矿 | **留**（机制成立，绑约束移到经济，见 C3b） |
| C3b | 2026-07-19 | 「地面流到点自动开二矿，经济撑起消耗战」 | flows.yml `auto_expand: {at: 210, to: 2}`（仅 stalker）+ `production_manager._auto_expand` | c3b-expand-smoke（N=4） | 0-4，但局面质变：281s 二矿、42 农民、兵力反复到 13、时长 661→1125s；输给对方后期 40-60 大军的波次消耗 | **留**（经济约束消除；绑约束移到「中后期决战质量」） |
| C3c | 2026-07-19 | 「集结阈值 8→14，减少中期失血，攒到能打赢的体量再接战」 | flows.yml stalker `rally_min_army: 14` | c3c-rally14-smoke（N=4） | 0-4；兵力卡在 10 永远到不了 14——诊断出**第二根停产因**：SpawnController 配比死锁（7:3 精确配比点双方都 ≥ 目标 → 全停产），存款又堆到 4045 | **留 14**（阈值本身无辜，死锁由 C3d 解） |
| C3d | 2026-07-19 | 「freeflow 解除配比死锁，产能不再卡在配比点，兵力上限由经济决定」 | flows.yml stalker `freeflow: true` + `SpawnController(freeflow_mode=...)` 配置化 | c3d-freeflow-smoke（N=4） | 0-4，但兵力破死锁：10→15→17→**21**（643s），打上真正的团战；配比滑向纯追猎（无前排）；输给 31-38 大军的决战质量 | **留**（第二个停产根因消除；绑约束移到「兵种构成天花板」——纯追猎+狂热者无溅射，打不动 bio+坦克） |
| C5a | 2026-07-19 | 「spawn 优先级反转（zealot p0）让狂热者先出，保住前排吸收伤害，追猎少死」 | flows.yml stalker spawn 优先级反转（ZEALOT p0 / STALKER p1） | c5a-zealot-prio（N=4） | 0-4，且机制反噬：狂热者永远可负担 → 占满全部折跃位，**全程 0 追猎**（气堆到 4190 没用）；21 纯狂热者被坦克风筝团灭 | **滚**（已回滚优先级；教训：freeflow 下首优先兵种若永远可负担会饿死其他兵种） |
| C2 | 2026-07-19 | 「关掉进攻型 blink（_BLINK_KILL_HP 80→0）后追猎不贴脸送，交换比改善」 | `stalker_offensive.py` `_BLINK_KILL_HP` 80→0（caster 切后排保留） | c2-blinkoff（N=4） | 0-4，但指标全面改善：时长 958→1054s、存款峰值 1410→1030、trickle ×4→×2、兵力峰值 20-28 | **留**（送死减少；胜率未动 → 构成天花板锤实：纯追猎/狂热者无溅射，调参救不了，正路是 robo-colossus / chargelot-archon 的溅射） |
| Q2 | 2026-07-19 | 「闲置农民清扫后无命令农民 ≤ 极个别(远途建造中)」 | `main._handle_idle_workers()`：每 2 游戏秒扫 `workers.idle`（跳过侦查/司令接管），派回最近矿脉 + 归 GATHERING | （待 smoke） | （机制已落地，B4 后续局即生效） | （待填） |
| Q3 | 2026-07-19 | 「爆仓前尽早开二矿（农民 ≥18 或 150s，先到先触发）」 | flows.yml stalker `auto_expand: {at: 150, to: 2, when_workers: 18}` + `AutoExpand.when_workers` | （待 smoke） | （机制已落地） | （待填） |
| Q4 | 2026-07-19 | 「基地被打爆到 0 且有矿区价值时自动重建，全局至少 1 基地」 | `production_manager._ensure_townhall()`：0 基地 + 出生点有矿 + 无敌军压场 → 重建（全流派） | （待 smoke） | （机制已落地） | （待填） |
| A1 | 2026-07-21 | 「pivot 自适应（早侦查/rush 响应包=叉子顶+铺塔+守家/反空军混追猎）能破 Rush 墙和对空墙」 | flows.yml `pivot:` 块 + `_early_scout/_update_rush_state/_effective_spawn` + combat 守家联动 | pivot3-tempest-ci-zerg-rush（N=3）+ pivot3-carrier-vh-protoss-air（N=3） | tempest **1-2**（此前两轮 0/4，首胜 cheat-rush：先出 4 叉顶住再天空体滚雪球）；carrier **3-0 全穿**（此前 0/4，反空军混编直接拆墙） | **留**（两堵墙均破；其余墙组合按 promotion 续打验证） |

### 后续假设候选（按优先级）

- C5 **兵种构成天花板**（C3d 实证）：纯追猎+狂热者无溅射，打不动 bio+坦克的 30+ 大军。
  两条路：(a) 前排强化——zealot 比例/优先级调整（freeflow 下配比会滑向纯追猎，需要
  别的方式保前排，如 priority 反转或定期补 zealot 的机制）；(b) 上溅射——直接做
  `docs/flows/robo-colossus.md`（巨像）或 `chargelot-archon.md`（闪电+白球），
  这正是排期里的下两条地面流。
- C2 stalker blink 门限实测调优（F3 的 0.25 护盾/4 敌围攻是拍脑袋值；进攻型 blink
  可能往坦克脸上送）。
- C4 carrier 气体节奏：CARRIER@340s 成型已不慢，但存款峰值 3385 提示仍有优化空间。
