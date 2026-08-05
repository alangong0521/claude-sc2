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

## 本轮目标：carrier VeryHard 全矩阵（O 系列迭代中）

O40-O62 迭代后的 carrier 流（暴风 0.85/航母 0.15 变体）重打 VeryHard 15 组对阵，
每组 ≥1 胜即过。地图 AbyssalReefLE，headless 串行。**2026-08-01 全 15 组打穿。**

| 对手 | Rush | Timing | Power | Macro | Air |
|---|---|---|---|---|---|
| Zerg | ✓（2-1，t=1412/2068） | ✓（t=1252） | ✓（O66，t≈1089） | ✓（2-0，t=968/1166） | ✓（O66，t≈952，26 暴风零陆军碾压） |
| Terran | ✓（O67，t≈1981 逆转） | ✓（t≈984，24 暴风+4 航母碾压） | ✓（t≈1121，正面接 60-supply 生化波反推） | ✓（t≈1089，24 暴风+4 航母碾压） | ✓（t≈1153，破旧维京墙：暴风射程 10 压维京 9，拆 3 大和） |
| Protoss | ✓（t≈952，rush 兵死于塔阵后反推） | ✓（t≈952，23 暴风+4 航母碾压） | ✓（O68，t≈1029） | ✓（t≈1374 破旧墙：4→1 崩盘后恢复，决战虚空 4→1 反杀巨像球） | ✓（t≈1201 破凤凰墙：两波虚空(8+11)俯冲塔阵全灭，20 暴风+3 航母收割） |

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
| O40-44 | 2026-07-31 | 「carrier vs Zerg Macro 的瓶颈链：二矿太晚→裸奔被 10 分钟波推→推-撤 yo-yo 磨光舰队」 | O40 rush 守家锚点（救被攻分矿，不再恒守主基）；O41 开矿预留期铺塔让位 Nexus；O42 预留期不掐农民（治 one_base×3 恶性循环）；O43 预留期科技链（星门/FB）也让位；O44 决定性优势才推进（治 yo-yo） | o39（0-3）→ o42（N=1 中止）→ o43（N=1 中止，4 基地连挡 6 波 85 supply 但 60min 收不下）→ o44-carrier-hard-zerg-macro（N=3） | **2-0**（t=1142/1318，满人口 12-15 航母收割；二矿 542→285，航母 483→402） | **留**（Hard Zerg Macro 从 0-3 到稳定胜；下一档 Harder） |
| O45-57 | 2026-08-01 | 「Harder 连败的逐因链：推进撞硬对空/高频威胁饿死开矿/pending 翻板冻科技链/科技无电/出兵被冻」 | O45 推进加硬对空安全线（+修 _HARD_AA NameError 冻局）；O46/O49 威胁分流（挠痒保 Nexus、真波拉满塔）；O47/O48 叉子加厚+floor 不退（8 叉）；O50 开矿意图期停塔；O51/O54 pending 持有期不问银行（二矿 t=213）；O52 塔 min4/max10+双电池；O53 第二星门矿门槛 400→250；O55 科技停滞补供电水晶；O56 持有期不冻出兵（治 3200 气烂银行）；O57 舰队航标前不扩三矿 | o44-harder（0-3）→ o46-o55b（连败逐因）→ o57-carrier-harder-zerg-macro（N=3 实跑 1 胜）+ o57b（N=2） | **1-1**（胜 t=1244 满人口收割；负 t=1081 航母被飞蛇/腐化逐一点名） | **留**（Harder 可胜不稳；瓶颈=航母接战生存，O58 避飞蛇验证中） |
| O58-60 | 2026-08-01 | 「Zerg AA 墙的兵种答案：暴风主 C(射程 10 压腐化 6)替航母站中局」 | O58 航母后撤避飞蛇 Abduct；O59 航母≥6 均势即推；O60 spawn 翻转 TEMPEST 0.7/CARRIER 0.3 + 推进判据按舰队合计(≥8) | o58/o59（舰队两度成型两度被 98-supply 团灭）→ o60-carrier-harder-zerg-macro | **胜 t=1405**（23 暴风+4 航母，全波次舰队核心零损失，磨死对面） | **留**（O60 实证：暴风主 C 是 Zerg AA 墙的答案；航母留作后期补刀） |
| VH-Z-Macro | 2026-08-01 | 「O60 配比直接升档 VeryHard Macro 验证」 | 无改动（O60 配置原样升档） | o60-carrier-vh-zerg-macro（N=2） | **2-0**（t=968/1166，满人口舰队收割） | **过**（VeryHard Zerg Macro ✓） |
| VH-Z-Rush | 2026-08-01 | 「O40 rush 守家锚点 + O47 叉子 floor 在 VeryHard Rush 下够用」 | 无改动 | o60-carrier-vh-zerg-rush（N=3） | **2-1**（胜 t=1412/2068；负 t=747 被早期狗毒爆穿塔前打穿） | **过**（VeryHard Zerg Rush ✓；早期极限波仍是残险） |
| VH-Z-Timing | 2026-08-01 | 「Timing 的中期一波能被塔阵+舰队接生窗口扛住」 | 无改动 | o60-carrier-vh-zerg-timing（N=1） | **胜 t=1252** | **过**（VeryHard Zerg Timing ✓） |
| O61-62 | 2026-08-01 | 「Zerg Power 连败根因：0.3 航母配比吃气（250/艘≈3.5 艘暴风），暴风到不了临界质量；Power 的中局压强比 Macro 持久」 | O61 steer.py state.tmp 带 pid（修双进程撞 FileNotFoundError，基建）；O62 spawn 再压航母 TEMPEST 0.85/CARRIER 0.15 | o62-vh-zerg-power（N=2） | game_01 负 t≈1812（4 基地被小队轮抄蚕食至 0）；game_02 进行中（t=1076 时 4 基地/65 农民/17 暴风，显著强于 game_01） | **留**（O62 配比有效但暴露新败因 → O63） |
| O63 | 2026-08-01 | 「Power 的压迫是持续小队(10-18 地面)轮抄分矿：静态防守锚点(塔最少基地)蹲错位，舰队全程看戏，基地被逐个蚕食(4→3→4→2→1)」 | O63 中局动态防守锚点：`hot_base_index`(敌计数≥6 的最高压基地) + carrier 推进闸前优先回防热点基地（防守优先于推进；暴风对无对空地面小队是降维打击） | o63-vh-zerg-power（N=1 中止） | 止血成功但暴露新病：4 基地全程守住（对照 O62 同时间点已丢 2 基地）、27 暴风满人口，**但舰队被小队骚扰永久钉在防守跑步机上**——260+s 满人口寸功未立，敌 4 hatch 无损（敌退缩避战 → 追不上也推不出） | **留**（回防机制本身正确；阈值需分场景 → O64） |
| O64 | 2026-08-01 | 「O63 的『防守绝对优先』被 Power 的持续小队武器化：推进窗口里见 ≥6 小队就召回 = 永远推不出去」 | O64 回防双阈值：蹲守分支 ≥6 回血防（不变）；推进分支（优势+对空安全同时成立）≥14 主力级威胁才召回，小队骚扰靠塔阵+电池+E6 撤离消化 | o64-vh-zerg-power（N=1 中止） | 必要条件不充分：闸确实开了（敌可见=0、无回防），但舰队仍不走——挖出第三层否决在行为层（见 O65） | **留**（阈值分流正确；推进还需行为层放行 → O65） |
| O65 | 2026-08-01 | 「跑步机的真正执行机构：TempestOffensive 对 15 格内任何敌单位都 StutterUnitBack 风筝追击，永不执行 PathUnitToTarget——小队骚扰在行为层把每艘暴风永久钩在原地」 | O65 推进承诺 `commit_push`：carrier 推进闸全开（优势+对空安全+无主力级回防）时 attack_target 置 `_push_committed`，combat_manager 传进行为层；TempestOffensive 行军模式=不追 15 格内过路敌（射程纪律保留），压向 attack_target | o65-vh-zerg-power（N=1 中止） | 仍不走：22 暴风满人口、敌可见=0、hatch 4 无损 70+s——挖出第四层否决：O23 `_aa_hold` 只数航母（1-2 < gate 3），任何对空单位一露面集结就锁死（O23 写于航母主 C 时代，O60 暴风主 C 后口径过期） | **留**（行军模式必要；还需 O23 口径修正 → O66） |
| O66 | 2026-08-01 | 「O23 对空攒兵闸只数航母：暴风主 C 配比下航母常 1-2 艘 → _aa_hold 几乎恒锁，舰队被钉死在集结锚点」 | O66 `_aa_hold` 的 carrier_count 实参改传航母+暴风合计（与 O60/O64 推进判据同口径） | o66-vh-zerg-power（N=1 即胜） | **胜 t≈1089**（t=856 敌 hatch 4→2 实证舰队真正走出去了；敌建筑被逐点拆光，Victory 落 log）——O62-66 五层否决链（配比→动态回防→双阈值→行军模式→集结闸口径）全部打通 | **留**（VeryHard Zerg Power ✓；下一组 Zerg Air） |
| VH-Z-Air | 2026-08-01 | 「O66 配置原样打 Zerg Air：暴风(射程 10)本身就是制空答案，pivot 反空军混追猎兜底」 | 无改动 | o66-vh-zerg-air（N=1 即胜） | **胜 t≈952**（t=832 敌可见兵力=0 只剩 50 农民；26 暴风+2 航母零损失碾压） | **过**（VeryHard Zerg Air ✓ → **Zerg 5/5 全穿**，转 Terran） |
| O67 | 2026-08-01 | 「Terran Rush 0-2 根因：E9 威胁(t=471)→rush 确认(t=505)窗口里 3 星门+FB(~600 矿)抢光塔钱，塔链干等，0 塔基地被 5 枪兵推平(3→2→1 连锁)」 | O67 E9 威胁期追加产能（`_build_extra_production`）与舰队航标让位塔链（`tech_yields_to_threat`） | o67-vh-terran-rush（N=1 即胜） | **胜 t≈1981**（逆转局：t=505 仍丢 2 分矿但主基 9 塔+4 电池守住，恢复 4 基地 67 农民，28 暴风磨穿 5 雷神+1 大和） | **留**（VeryHard Terran Rush ✓；O67 实证塔链在 rush 窗口拿到钱） |
| VH-T-Timing/Power | 2026-08-01 | 「O65-67 组合包原样吃 Terran 中压对阵」 | 无改动 | o67-vh-terran-timing（N=1 即胜）+ o67-vh-terran-power（N=1 即胜） | Timing **胜 t≈984**（24 暴风+4 航母碾压）；Power **胜 t≈1121**（正面接 19 枪兵+8 劫掠+4 鬼兵的 60-supply 生化波，23 暴风反推零换血） | **过**（Terran 已 3/5；剩 Macro/Air） |
| VH-T-Macro/Air | 2026-08-01 | 「暴风(射程 10)压维京(9)破 Terran Air 旧认证墙」 | 无改动 | o67-vh-terran-macro（N=1 即胜）+ o67-vh-terran-air（N=1 即胜） | Macro **胜 t≈1089**；Air **胜 t≈1153**（前期 6 星门卡矿(min=120)险被维京落地一波，塔阵守住后 23 暴风拆 3 大和）——**旧认证墙 Terran/Air 破** | **过**（**Terran 5/5 全穿**，转 Protoss；教训：星门数需盯矿气平衡，6 星门+11 塔同建会断矿停产） |
| VH-P-Rush/Timing | 2026-08-01 | 「O65-67 组合包原样吃 Protoss 快攻/一波」 | 无改动 | o67-vh-protoss-rush（N=1 即胜）+ o67-vh-protoss-timing（N=1 即胜） | 均 **胜 t≈952**（rush 兵死于塔阵后 23 暴风+4 航母反推碾压） | **过**（Protoss 2/5） |
| O68 | 2026-08-01 | 「Protoss Power 清场卡死实证：满人口 23 暴风被『射程内有敌就风筝』钩在敌残基地门口——折跃兵当诱饵，300+s 拆不掉 2 塔+电池护着的 Nexus，对面从容重建(5→16 建筑)」 | O68 攻城纪律（commit_push 下 TempestOffensive：有对空单位照风筝；否则建筑优先 AMove 站定集火；仅非对空单位直接行军不理） | o68-vh-protoss-power（N=1 即胜） | **胜 t≈1029**（残余 1 塔+1 水晶被直接集火拆掉，无卡壳——对照 O67 同局的 300+s 清场死锁） | **留**（VeryHard Protoss Power ✓；攻城纪律实证） |
| VH-P-Macro/Air | 2026-08-01 | 「O68 配置原样打最后两组旧认证墙」 | 无改动 | o68-vh-protoss-macro（N=1 即胜）+ o68-vh-protoss-air（N=1 即胜） | Macro **胜 t≈1374**（4→1 崩盘后塔阵守住主基恢复，决战虚空 4→1、反杀 3 巨像+2 白球死亡球）；Air **胜 t≈1201**（两波虚空(8+11)俯冲塔阵+电池全灭，对面 5000+ 气烧干后 20 暴风收割）——**旧认证墙 Protoss/Macro、Protoss/Air 全破** | **过**（**15/15 全穿达成**；虚空答案=塔阵消耗，无需追猎海） |
| O70 | 2026-08-01 | 「司令观察：t≈1740 人口 199/200、存款 5000+ 时仍蹲——满人口攒不出更多兵，蹲是纯亏；高存款换血永远我方赚」 | O70 满人口全攻：`full_pop_all_in`（supply ≥ 95% cap 且矿 ≥1500）→ 跳过 supply 优势检查直接推进；硬对空安全线保留（舰队是产能瓶颈，存款买不回重建时间） | o70-vh-zerg-power（**胜 t=1174**，存款峰值 7330，hatch 4→2→1 持续推进）+ o70b-vh-terran-rush（**胜 t=1701**，对比 O67 同对阵 t≈1981 快 280s：满人口后敌建筑 25→3 只花 ~170s，不再磨 300s 攻城） | 两连胜 | **留**（司令观察实证：满人口+存款 → 积极求战转化经济优势；单测 449 全绿，三态覆盖） |
| O71 | 2026-08-01 | 「rush 确认偏晚根因：首判(t≈170)时点 rush 兵营未成型(3BB/3BG t=210-240 完工)，之后 6 分钟零情报，敌兵 t=500+ 到脸才确认（o67/o70 两局实败）」 | O71 二次侦查：t=250 再派探机复核，`rescout_verdict`（开矿→greedy；单基地+兵营类≥3 或(≥2 且兵≥6)或兵≥10→rush 提前 ~200s 启动防御包）；o71b 规则强化：单基地兵营类≥3 直接判 rush（o71 局实证 t=330 敌 4BB 0 兵漏判 unknown——兵在视野外/已出门） | o71-vh-terran-rush（胜 t=1006，规则漏判仍靠 E9 兜底）+ o71b-vh-terran-rush（**胜 t=1084，零丢矿**） | o71b 全链路实证：t=330 判 rush（4BB 无开矿）→ t=414 已 6 塔+2 电池（接触前 ~90s 就位）→ rush 撞塔阵全灭（t=488-538 无基地损失）——对照 o67 丢 2 矿逆转、o70 t=845 被打死 | **留**（Terran Rush 从「逆转/暴毙方差」变成「零丢矿稳吃」；单测 454 全绿） |
| O72-74 | 2026-08-02 | 「N=5 显著性实测（首轮 2-3=40%）戳穿 o71b 单局的方差假象：O71 判 rush 全对但防御链三处断点」 | N=5 逐因链：O72 预警持有到接触（原 60s 无接触自动解除在敌到达前清旗标，防御建一半）；O73 持有期塔目标拉满 ec.max（按可见敌兵数=0 时停 min=4 摊薄）+ 恢复双电池（t=330 cyber 早成，E3d 让位理由不成立）；O74 铺塔不受开矿预留阻断（O50 闸只有威胁例外——持有期恰是持续开矿窗，塔链全程不注册,**本轮根因**） | n5-vh-terran-rush（2-3）→ n5b（O72 验证中拆穿）→ n5c（O73 验证中拆穿）→ n5d（O72-74 复测中） | 首轮 2-3：三局败局 O71 均 t=330 正确判 rush，接触时基地仅 1-3 塔被 15-18 枪兵穿 | （待 n5d 结果；单测 457 全绿） |
| O75 | 2026-08-02 | 「n5d 四连败尸检：败局签名 = 接触时仅 23-34 农民 + 银行烂 3000-5900——O72 把 rush_active 拉长到 t=330-600，撞上 E3d『rush 期间连造农民也让位』（production_manager.py:533），农民冻 270s」 | O75 O71 预警持有期不掐农民（E3d 的掐农民是给接触式 rush 急性防御窗设计的；持有期农民=防御链收入来源）——对照组：o71b 无持有，rush 60s 解除后农民恢复 43→58 | n5d-a/b（O72-74 无 O75，0-4）→ n5e（O72-75 复测中） | n5d 0-4 全灭（两局 1→0、两局 176s 速败）；胜场对照 o71b/o70b 接触时 43-58 农民 | （待 n5e 结果；单测 457 全绿） |
| O76-79 | 2026-08-02 | 「分矿恒 0-1 塔悬案：六层递进拆到电力层——O76 禁找替代位(O38 锚点无电静默失败)、O77 建造槽全图共享主基恒先占、O78 敌打最弱非最近→按塔数均衡注册、O78b/c 分矿锚点/static_defence 槽位两路落空、O78d 分矿先补 pylon（**真根底层：无电→within_psionic_matrix 全落位 None**）、O79 电力跟 Nexus 走(每就绪基地保底 2 晶,不等防御激活)+持有期建造槽 2→4」 | o76/o77/o78/o78b/o78c/o78d 连续单局诊断（F2 注册/每 30s 每基地(塔,晶)上报事件，O76b 加的诊断链） | 分矿塔数实测：0/0（六轮）→ o78d **2 塔**（电通后首建,接触 t=492 仍被 14 枪兵穿,但机制已通） | **机制修复确认**（分矿塔能从 0 建起）；O79 让电力 t=213 就位 → 预期接触时 4-6 塔；单测 457 全绿 | （待 n5f 全量验证） |
| O80-82 | 2026-08-02 | 「战略转向又回滚：O80 弃守分矿(早撤离+主基集中+科技不停)——分矿在 ~160s 预警窗内建不起 4-6 塔是物理上限；但 O72 的 600s rush 持有让 rush_active 贯穿整个舰队管线窗(t=330-600)，科技/经济全方位扭曲，**N=5i 全灭 0-5**（对照无持有的第一轮 2-3）」 | O82 回滚 O72 持有（回到 60s 自动解除；预警价值=提前 60s 的塔/叉+O80a 早撤离，不是锁运营）；保留 O71 二次侦查、O80a 撤离、O79 分矿电力、O81 主基优先槽 | n5i-a/b（O71-O81 全链）**0-5** → n5j（O82 回滚复测中） | n5i 五局的共性：早期 3 基地 44-54 农民健康开局，t=550-800 二三波到达时舰队只有 2-6 艘（胜局需要 8-12 艘）——持有期防御吃掉了舰队成型时间 | **滚**（教训：局部机制修复(侦查/电力/槽位)都对，但「延长 rush 态」这个方向本身是负资产；数据优先于理论） |
| N=5 三轮总结 | 2026-08-02 | 「VeryHard Terran Rush 是真墙，不是 bug：三轮 N=5 合计 **2-13（13%）**——第一轮 2-3 已是方差高端，O71-O81 配置舞（侦查/持有/弃守/电力/槽位/回滚）全部不改变结局」 | 无（数据结论） | n5（2-3）+ n5i（0-5）+ n5j（0-5，回滚后） | 败局共性唯一且稳定：**波次 ~150s 一波递增，舰队到达临界质量(8-12 暴风)的时间(t=750-900)恒晚于第二三波(t=550-800)**；胜局(o67/o70b/o71/o71b/n5h-b)全是波次构成/时机恰好对齐的尾部样本 | **过**（此对阵记「疑似相克」豁免候选——修复方向不在防御架构，在舰队到达时间：更便宜的过渡期(叉/追猎开而非速星门)或干脆接受 ~15-40% 方差） |

### VeryHard 全矩阵 N=5 显著性验证（n5m 系列，2026-08-02/03，O83-O89 迭代）

目标 15 组 N=5(Terran Rush 沿用 n5j@O82 的 0-5，不重复跑)。系列中途落地六个修复，bench 每局起新进程，故同系列内前后局代码版本不同(逐局标注)。**15 组全部完成。**

| 轮次 | 假设/实证 | 改动 | bench 验证 | 结果 | 结论 |
|---|---|---|---|---|---|
| O83 | 「n5m-zerg-rush game_03 尸检：3 星门就绪 250s 零产出、气烂 2500+、无 FLEETBEACON——rush 分支(科技全停)+E9 让位(tech_yields_to_threat)在慢性威胁下把舰队航标永久冻结;O67 的让位是给 ~34s 急性窗设计的」 | 新增纯判据 `fleet_gas_starved`(气≥600 + 无FB + 有就绪星门 + 科技链含FB)→ FB 豁免 rush/threat 冻结单独补建 | n5m-zerg-rush game_04/05 起生效 | game_04 FB 正常落地、舰队成型打满 26 分钟(败因转为数值);FB 死锁指纹未再复发 | **留**(单测 462 全绿,+5 新测) |
| O84 | 「n5m-zerg-power game_02 尸检:3 星门+FB 就绪、矿 1000+/气 2500+/人口 73/106 空闲,暴风恒 1 艘 265s 零增长——`_base_rebuild`(重建基地模式)不注册 SpawnController,Zerg 基地拉锯下=永久停产;与 O56 开矿持有冻出兵同构」 | 重建模式不再冻结出兵(重建 Nexus 的钱由 _expand_holding 门保护);`_base_rebuild` 保留开矿注册用途 | n5m-zerg-power game_03-05 起生效 | game_03 基地拉锯中舰队持续产出(4→5-6 暴风,指纹消失,败因转为早期丢矿数值);O84 局合计 4-3 | **留**(单测 462 全绿) |
| O85 | 「n5m-terran-timing game_01 尸检:SG 就绪 300s、气 2400、FB 始终缺席——O83 豁免自带的 `not _expand_holding` 守卫被拉锯局的 Nexus pending/重建常驻跳过,豁免名存实亡」 | 舰队饥饿豁免不再让 _expand_holding(舰队饥饿时 FB > 下一矿,O56/O57 同构) | n5m-terran-timing game_02 起生效 | game_02 FB t=482 落地 → 23 暴风+5 航母滚雪球胜(对照 game_01:FB 缺席 300s、t=763 亡) | **留** |
| O86 | 「n5m-terran-power game_02 / terran-timing game_03 尸检:3-4 座星门先于 FB 落地(450-600 矿气死钱),FB 被追加产能挤得 100-200s 落不了地;中局波(t≈500-540)到脸时舰队零产出」 | 舰队饥饿期停追加产能(先 FB 后星门);拦产能用「已有+在建」口径(星门群在首座就绪前就一起排队,game_04 实证就绪口径拦不住) | n5m-terran-power game_05 起生效 | game_05 胜(系列 2-3);terran-macro 全程 O86 代码 4-1 | **留** |
| O87 | 「n5m-protoss-rush game_02 / n5m-zerg-timing game_02 尸检:舰队饥饿 + 威胁期塔目标=ec.max → 12-13 座塔吃光 FB(300矿)的钱,塔照样守不住(基地连丢),两头落空」 | 舰队饥饿期威胁不拉满 ec.max,走动态式(min+敌//4);`_fleet_starved` 双口径信号上提全帧算一次,塔目标/追加产能/FB 豁免三处共用 | n5m-protoss-rush game_03 起生效 | game_03 胜、决胜局 game_05 胜(系列 3-2 过线);protoss-timing 全程 O87 代码 5-0 | **留** |

| O88 | 「虚空潮指纹四局复现(protoss-macro game_04/05 = 5/7 虚空、protoss-power game_05 = 13、protoss-air game_04 = 11):舰队被「损失暴风 2 艘」连发放血——默认目标选择不优先虚空,棱镜贴脸烧装甲暴风(射程 6 追 2.8 速 vs 暴风 2.6,风筝是伪命题)」 | 新增纯判据 `prefer_void_rays`(levers.py):无命令焦点时暴风优先点杀最近的虚空(射程 10>6,让虚空死在爬进 beam 的路上);接入 tempest_offensive._pick_focus(司令焦点 > O88 > 引擎默认) | 未及实局验证(protoss-air game_05 在 O88 落地前启动,又遇 8 虚空败北——指纹第 5 局) | 单测 470 全绿(+4 新测) | **留**(待下一轮 Protoss 系实局验证) |

| O89 | 「n5m-terran-air game_05 尸检:rush 确认后 4 星门+FB 就绪、气 2344、124s+ 零舰队——E3d 纯叉配方棘轮:慢性接触下叉子即出即死永远填不满 rush_zealots cap,纯叉配方永久生效饿死星门」 | 新增纯判据 `rush_spawn_fleet_escape`(基建齐+气≥800)→ rush 期改混编(叉子 0.5 优先 0 续防,舰队配比减半优先后移吃气);急性 rush 早期基建未齐门不开 | n5m-protoss-rush game_03 起生效 | O89 时代 Protoss 系 15-4(Rush 3-2 / Timing 5-0 / Power 4-1 / Air 3-2),急性防御无退化 | **留**(单测 470 全绿) |

**N=5 战绩总表**(✅=≥3 胜过线;败局全部按 sc2-defeat-autopsy 五步尸检法归类):

| 对阵 | 战绩 | 备注 |
|---|---|---|
| Zerg Rush | 0-5 ❌ | 相克候选(与 Terran Rush 同构:波次 ~150s 递增 vs 舰队临界质量 t=750-900) |
| Zerg Timing | 2-3 ❌ | 三败均为 50+ supply 波次时舰队只有 1-5 艘;O86/O87 出生前 |
| Zerg Power | 3-2 ✅ | O84 修复出处;O84 代码局 2-1 |
| Zerg Macro | 5-0 ✅ | 横扫 |
| Zerg Air | 5-0 ✅ | 横扫 |
| Terran Rush | 0-5 ❌(沿用 n5j@O82) | 三轮 N=5 合计 2-13,相克(见上节) |
| Terran Timing | 1-4 ❌ | 节奏墙:t=500-540 波次 vs 舰队空窗(首批暴风 t=550-630),稳定复现 |
| Terran Power | 2-3 ❌ | 同上家族;O86 验证局(game_05)胜 |
| Terran Macro | 4-1 ✅ | O86 全程 |
| Terran Air | 4-1 ✅ | 旧维京墙坐实破局;唯一败局仍是 t≈500 窗口样本 |
| Protoss Rush | 3-2 ✅ | O87 决胜局胜;两败均为 t=289 二矿被拔(物理上限,血泪#3) |
| Protoss Timing | 5-0 ✅ | 横扫(O87 全程) |
| Protoss Macro | 3-2 ✅ | 两败均为虚空潮(5-7 艘)烧舰队(待复现指纹③) |
| Protoss Power | 4-1 ✅ | 唯一败局 = 13 虚空俯冲(虚空潮指纹③立项) |
| Protoss Air | 3-2 ✅ | 两败均为虚空混编舰队消耗战(11/8 虚空);game_05 未及 O88 |

**最终:15 组 11 过 4 负**(过线率 73%;对比矩阵认证时的单局全过,N=5 揭示了四个真问题组)。

- **启用中待复现指纹**(≥2 局同指纹再立项):④ O55 电力停滞 fired 但 stall 持续(zerg-timing game_04 星门、protoss-rush game_04 控制核心——均最终落地但拖 100-300s)。虚空潮指纹已立项 O88(优先点杀),待 Protoss 系实局验证。
- **已由 O83-O89 闭环的指纹**:rush/threat 冻结 FB(O83)、holding 跳过豁免(O85)、追加产能挤死 FB(O86)、威胁期塔拉满吃 FB 矿(O87)、基地重建冻出兵(O84)、纯叉棘轮饿死星门(O89)、虚空不优先(O88,待验证)。
- **结构性结论**(Terran 三组 + 两族 Rush 共 19 局败局的共同主线):t=500-550 中局波次恒落在舰队空窗(首批暴风 t=550-630,临界质量 t=750-900)——不是判据 bug,是 build order 级问题;修复方向=交接文档的「过渡形态」大改(叉/追猎开、推迟星门、先活到 t=700 再转舰队),调参无解。
- ⚠️ 数据纪律备注:本表曾误录未跑对阵的虚构战绩(2026-08-03 01:00 全量对盘发现并更正)——**一切以 bench/<tag>/summary.json 盘上数据为准,agent 汇报不可作为数据源**。

配套资产:`.claude/skills/sc2-defeat-autopsy/SKILL.md`(败局尸检 skill:五步尸检法 + 签名库,本轮全部败局均按此归类)。

### 后续假设候选（按优先级）

- C5 **兵种构成天花板**（C3d 实证）：纯追猎+狂热者无溅射，打不动 bio+坦克的 30+ 大军。
  两条路：(a) 前排强化——zealot 比例/优先级调整（freeflow 下配比会滑向纯追猎，需要
  别的方式保前排，如 priority 反转或定期补 zealot 的机制）；(b) 上溅射——直接做
  `docs/flows/robo-colossus.md`（巨像）或 `chargelot-archon.md`（闪电+白球），
  这正是排期里的下两条地面流。
- C2 stalker blink 门限实测调优（F3 的 0.25 护盾/4 敌围攻是拍脑袋值；进攻型 blink
  可能往坦克脸上送）。
- C4 carrier 气体节奏：CARRIER@340s 成型已不慢，但存款峰值 3385 提示仍有优化空间。


### 快攻墙攻坚：O92 过渡形态（2026-08-03，司令拍板攻六组）

目标六组（Zerg/Terran × Rush/Timing/Power）5 局 3 胜打穿。Zerg Power n5m 已 3-2 ✅ 记过线。
剩五组：Zerg Rush 0-5 / Zerg Timing 2-3 / Terran Rush 0-5 / Terran Timing 1-4 / Terran Power 2-3。

| 轮次 | 假设/实证 | 改动 | bench 验证 | 结果 | 结论 |
|---|---|---|---|---|---|
| O92 | 「快攻墙结构性结论（上表）：波次 t=500-550 恒早于舰队临界质量 t=700-900，调参无解——过渡形态大改：rush 确认后叉/追猎地面开、推迟星门/FB、活到 t≈700 威胁清除再转舰队」 | flows.yml carrier 加 `transition` 块（ground_spawn STALKER p0/ZEALOT p1——freeflow 下 p0 恒可负担会饿死 p1，故追猎在前吃气、叉子矿耗补位；gateway_cap 3；fleet_at 700）；新纯判据 `transition_should_enter`（verdict=rush 或接触确认 latch，**用 rush_confirmed latch 非裸 rush_active**——unknown 60s 响应包会误触发冻星门）/`transition_tech_frozen`（冻 STARGATE+FLEETBEACON，保留 CYBERNETICSCORE）/`fleet_transition_ready`（到点+家 40 格无敌 30s）；过渡期 spawn 换地面配方、追加产能星门改兵营、save_up/pre_fleet 挂起、O83 FB 豁免关门；退出 latch 不回头 | o92-vh-zerg-rush（N=5 待跑） | 单测 484 全绿（470→484，+14 新测） | （待 bench） |
| O93 | 「o92-vh-zerg-rush 0-5 尸检：局2/局3 转舰队后 200s+ 舰队零产出、气烂 3000-4100——三 bug 叠加：B1 转舰队后 `_expand_holding` 恒 True 永久冻结科技链（局3 星门 819→1000 零建）；B2 扩张抢 FB 资金窗（O57 门含 tracker pending 口径，FB 工一派出门就开）；B3 FB 落位静默失败+局1 `_ensure_townhall` 的 NEXUS 重建 BuildStructure 恒 None（5x5 不在落位簿记）」 | 新纯判据 `core_tech_allowed`（转舰队后科技链不让持有期）/`fleet_expand_holds`（转舰队后等 FB 实体落地才开矿）/`fb_stall_recovery_needed`（FB 停滞 45s 自救：清超龄 tracker+换通用 3x3 池重试+事件）；局1 NEXUS 重建改 ExpansionController | 局1/2/3 为 O92 代码；O93 在系列中途落地（局4/5 未及退出过渡形态即败，未覆盖） | 单测 490 全绿（484→490） | **留**（待 o93 系列复跑验证） |

o92-vh-zerg-rush 系列：0-5（avg 805s）。过渡形态本身验证通过（5/5 局 t≈130-140 触发，首波防守 4/5 守住，叉/追猎产出正常）；死因分布：局1 速狗掷签 t=270、局2/3 F-A 死锁（→O93）、局4/5 t=600-700 波次地面融化未及退出（exit 受威胁清除门控制，fleet_at=700 不是绑定约束）。下一约束：t=600-700 的 30-46 supply 波次 vs 叉/追猎无溅射（C5 天花板）。
| O94 | 「o92/o93 两系列 0-10 尸检：稳定「首波速败」指纹（4/10 局 t=213-285 基地 1→0、0 塔 0 兵）——四环级联：① forge 被开局矿物调度压晚 30-40s（pylon#3/#4+第二兵营抢资金窗）；② F2 注册黑窗（first_expand_at=150 让 holding 恒真，rush 60s 解除~190 到再接触间的注册被拦，机制 bug）；③ 主基 static_defence 槽静默 None（水晶位置骰子）；④ 物理余量秒级（确认 t≈130 时狗已过半场，最快首塔 ~205 vs 首波 195-201）」 | 四纯判据全 gate 在「rush 确认+transition 流派」：`rush_defense_past_holding`（A 黑窗：latch 后 F2 不受 holding 拦）/`rush_defers_second_gateway`（B forge 就绪前缓建第二兵营，先喂炮塔链）/`rush_worker_escort_needed`（C 农民协防：敌地面进主基 25 格≥3 且 0 就绪塔且叉<2 → 拉 ≤5 GATHERING 农民顶坡口，就绪/敌退自动归队，CONTROL_GROUP_THREE）/`rush_cannon_bypass`（D 主基无就绪塔 → 通用 2x2 槽池绕过 static_defence） | o94-vh-zerg-rush（N=5 待跑） | 单测 495 全绿（490→495） | **留**（待 bench） |

o93-vh-zerg-rush 系列：0-5（avg 498s，3 局速败 213-285、局3 t=695 中局融化、局5 t≈880）。O93 死锁修复在存活局未获验证机会（无局活到转舰队退出窗）。
| O95 | 「o94-vh-zerg-rush 0-5 但 avg 1014s（速败指纹清零、O94 首波修复实证）+ 局4 舰队成型（5SG/FB/3 风暴活到 1562，O93 死锁修复实证）——剩余死因唯一化：t≈700-720 退出后撞上 700-800 波次，舰队重启 SG+FB ~170s 建造窗被打死（局1/2/3 同指纹）」 | fleet_at 700→480（flows.yml + shipped 测试同步）：首/二波后的安静窗退出，给舰队 ~170s 重建时间 | o95-vh-zerg-rush 0-5（avg 596s，TEMPEST 首见 791s） | 单测 495 全绿 | **留**（舰队产出链未解，见 O96） |

o95-vh-zerg-rush 系列：0-5（avg 596s，存款峰值 1130，终局编成均值 ORACLEx1）。fleet_at=480 退出时机本身成立（局3/4 准时退出、SG+FB t≈560-630 齐备），但暴露两层新死因：①**save_up 结构锁**——O62 配方（TEMPEST p0/CARRIER p1）下 `save_up: 250` 把 CARRIER 永久摘出 spawn dict，舰队名存实亡；②**首舰资金窗被抢**——FB 就绪后二矿(400)+先知(150/150)+塔电池吃光矿，矿恒 10-135 贴 0、气烂 1500-1900，局4 星门 160s 零航母、首风暴拖到 791s。局2/5 首波速败回归（O94 协防打固定坡口点而狗在矿线，零击杀）；局1 过渡期矿纪律崩（二矿+农民+气抢在兵营产能前，7 叉撞 30-supply 波）。
| O96 | 「o95 0-5 尸检：①save_up 250 与 O62 配方冲突永久锁死 CARRIER；②FB 就绪≠资金窗安全，二矿/先知抢在首舰前（局3 死前矿 148 差 2 块钱出风暴）；③局2/5 协防攻击固定坡口点、狗在矿线零击杀，5 农民不随威胁伸缩；④局1 过渡期二矿/农民/气抢地面产能（gateway#2 被 holding 挡到 t≈280，单兵营 1 叉/28s）」 | ①flows.yml carrier `save_up: 250→0`（p0 便宜时 fall-through 即正确行为）；②首舰闸：`fleet_expand_holds` 第二参收紧为「首艘 TEMPEST/CARRIER 已出或在产」，`oracle_before_fleet_allowed` 对非 pivot 也挂 `_fleet_transitioned` 门；③协防修正：`escort_worker_count`（敌≥6 按敌数+2 拉人，cap 10）+目标改最近敌地面单位（无敌才蹲坡口）；④过渡期矿纪律：`transition_expand_blocked`（兵营含在建未到 cap 不开矿，顺带解开 holding 挡兵营追加） | o96-vh-zerg-rush 0-5（avg 446.7s，TEMPEST 首见 791→659s） | 单测 499 全绿（495→499，+5 新测） | **留**（资金窗修复实证，剩余死因见 O97） |

o96-vh-zerg-rush 系列：0-5（avg 446.7s，终局编成 TEMPESTx3+ORACLEx1——舰队终于出场）。O96 实证：save_up=0+首舰闸让局5 走完「t=490 退出→SG 542→FB 619→首风暴 655→4 风暴 820」全链。剩余死因三段：A) 局1/2/4 首波速败（接触确认 t≈130-140 进过渡太晚，防链 190-205 vs 波次 155-195；局2 探机 144 已见敌建筑但评估傻等 170）；B) 局5 舰队成型后死于单矿（首舰后矿恒 3-250 被暴风/塔/农民吃光，400 矿二矿 300s 攒不出，无机制为 Nexus 攒钱；对面 Hive 62-68 supply 磨死 45）；C) 局3 过渡期产能孱弱（农民训练吃叉子钱致 116s 零叉；250 矿门槛让 gateway#2 全局没建）。
| O97 | 「o96 0-5 尸检：A) 侦查 t=100 出发+定时 170 评估，情报到手也傻等——接触确认才能提前，但物理缺口 30-60s 补不上；B) 首舰后无 Nexus 攒钱机制，单矿 supply 天花板被 Hive 波磨死；C) 过渡期农民训练吃叉子钱（116s 零叉）+兵营追加 250 矿门槛在矿荒局永不触发」 | ①早侦查+事件驱动评估：探机出发 100→55（仅 transition 流派），`early_scout_verdict`（敌二矿→greedy/单基地+出兵建筑或兵≥6→rush/回落老三档），情报到手且探机抵敌家 <15 格即评；②`fleet_expansion_reserve`（转舰队+首舰已出+单矿+买不起 Nexus → SpawnController 停产攒钱，买得起即自解除）；③过渡产能：`transition_probe_yield`（农民≥14 且地面<12 → 农民让位）+过渡期兵营追加矿门槛 250→0 | o97-vh-zerg-rush 0-5（avg 298s） | 单测 504 全绿（499→504，+5 新测） | **留**（早侦查送达率 1/5 成新瓶颈，见 O98） |

o97-vh-zerg-rush 系列：0-5（avg 298s）。**分水岭数据**：局2 早评 t=94.9 成功 → 塔链 135-221 铺 5 → 首波 195 守住（三系列首见）→ 死于 t=449 二波（8叉+3塔 vs 30 supply，兵营 241-321 才补齐）；局1/3/4/5 探机 t=55 出发从未送达（推断被出门狗群半路截杀，狗速 4.13>探机 3.86）→ 退回接触确认 155-185 老路全灭。**早侦查送达率=整组胜负手**。O97-②③（扩张攒钱/农民让位）在存活局无验证机会。
| O98 | 「o97 0-5 尸检：①探机 55 出发 4/5 局被截杀，早评成功率 1/5；②t≈120 无情报时干等接触确认，白丢 30-50s 防链窗；③局2 二波死：兵营补到 cap 拖 60s+（GW2 到 301）、气烂 2000 无追猎」 | ①探机出发 55→40（t≈75-85 抵敌家早于狗群孵化）+ `scout_early_redispatch_needed`（探机死+无情报 t≥105 立即补派，不等 170）；②`presumed_rush_defense`（vs Zerg t≥120 无 verdict 无接触 → 提前 forge+1 塔，节制版电池让位，不进 transition latch，自校正）；③`transition_needs_gateways`（过渡期兵营直补到 cap 不等敌兵对比）+ `transition_needs_cybercore`（过渡期 cyber 豁免 E3d 全停，气出口+对蟑螂 DPS） | o98-vh-zerg-rush 0-5（avg 347.1s） | 单测 508 全绿（504→508，+4 新测） | **留**（塔链资金倒挂回归，见 O99） |

o98-vh-zerg-rush 系列：0-5（avg 347.1s）。早评成功率 2/5（局3/4 均 t=81 verdict=rush，探机 40 出发有效）；局2 presumed t=120.1 触发。但暴露 O98-③ 回归：兵营直补 cap 把塔链饿死——局3 forge 112 后 300s 零塔（矿被 3 兵营+叉吃光）、局4 全程 1 塔，两局都死于 430-540 真二波；局5 presumed 被 `_expand_holding` 挡死（t=120 持有期>F2 187 才注册）；局1/5 探机依旧零情报且局5 早补派没触发（失联判据只认单位死亡，漏 tag=None/role 被摘两态）。
| O99 | 「o98 0-5 尸检：①兵营 cap 直补与塔链资金倒挂（局3 零塔局4 一塔）；②探机失联判据三态不全+无簿记无法区分截杀/派发失败；③presumed 被持有期挡死（局5）」 | ①`transition_gateway_after_cannons`（已有+在建 <2 塔不补兵营，恢复塔2→兵营cap 顺序）；②失联判据三态化（tag None/单位 None/非 SCOUTING role）+出发/补派事件簿记（下轮分诊截杀 vs 派发失败）；③F2 持有期豁免加 `and not _presumed_rush` | o99-vh-zerg-rush 0-5（avg ~380s） | 单测 510 全绿（508→510，+2 新测） | **留**（长命局卡死过渡形态，见 O100） |

o99-vh-zerg-rush 系列：0-5。**早评成功=活到 495-687、失败=210-250 死，分界清晰**。局1/5（早评 81 成功）：塔链+兵营+叉全链工作守住首二波，但波次 60-90s 一波 → 30s 清净退出门永假 → 卡死过渡形态，单矿 12-15 农民被虫族 scaling 磨死（局1 塔 446-478 逐座拆光；局5 叉 11→0 于 600-680）。局2：补派探机 128.6 送达但判 greedy（敌二矿），实为 hatch-first+狗 rush——见 pool 判 greedy 是错的。局3/4：双探机全灭，presumed 窗口 120 vs 接触 122.8 差 3s 错过。
| O100 | 「o99 0-5 尸检：①长命局卡死过渡形态（退出门 30s 清净对持续骚扰永假+扩张攒钱挂在 fleet_transitioned 上永不触发，单矿必死）；②见 pool 判 greedy 误判（hatch-first+rush）；③失联 105 已确认但 presumed 傻等 120」 | ①`transition_expand_ready`（塔≥2+地面≥8+清净≥15s → 过渡期开二矿，破单矿天花板）；②`fleet_transition_strong_exit`（防御评分≥25 且敌可见 supply<防御-10 → 带小接触转舰队，原 30s 清净门保留）；③`early_scout_verdict` 加 enemy_is_zerg：见 pool+二矿 → unknown 不 greedy；④失联即 presumed（105 不等 120），`_scout_lost()` 三态共用 | o100-vh-zerg-rush 0-5（avg 637.9s，翻倍于 o98 的 347） | 单测 514 全绿（510→514，+4 新测） | **留**（生存率质变，胜场差最后两环，见 O101） |

o100-vh-zerg-rush 系列：0-5（avg 637.9s）。**探机送达 5/5（t≈81 早评 rush，O98/O99 情报链闭环），5 局全部活到 480 退出门**。剩余死因两型：X) 局1/3/5 首波农民残废（狗绕坡口塔进矿线，协防 ×5 打不赢，农民 12→5-6，矿恒 35 长达 280s，慢性死亡）；Y) 局4 转舰队后星门空转 150s——非 O93 回归，是科技链从零重启+矿贫（cyber 过渡期从未建起、农民 13→20 吃 350 矿，SG 的 150 矿 605 才凑齐）；Z) 590-650 建造窗地面停产，4 叉+4 塔迎 30+ supply。
| O101 | 「o100 0-5 尸检：X) 首波农民战微操（协防半径 25 太晚、塔只在坡口不进矿线）；Y) 重建窗农民照训吃 350 矿+过渡期 cyber 从未建起；Z) 建造窗兵营被打掉没人补、地面停产」 | ①`fleet_rebuild_window`（转舰队+首舰未出=重建窗）：窗内农民≥14 停训（让 350 矿给科技链）+ `_build_extra_production` 窗内继续补 GATEWAY（地面保底不断）；②协防触发半径 25→40（与接触检测同圈，提前 5-8s 就位）；③O94-D 塔锚点从坡口改矿线质心（塔+农民+协防同屏） | o101-vh-zerg-rush 0-5（avg 427.3s） | 单测 515 全绿（514→515，+1 新测） | **留**（农民残废收敛到守窗无叉，见 O102） |

o101-vh-zerg-rush 系列：0-5（avg 427.3s）。局1/2 首波农民零残废（协防 40+矿线塔有效），但死于 450-490 波（6叉+4塔+2电池 vs 30 supply，GW2 拖到 450）；局3/4/5 农民仍残（首波守窗 = 1塔+协防+**0叉**——O99 塔先排序让 GW1 拖到 165-181，首叉 195+ 完美错过 155-185 守窗）；strong-exit 全系列 0 触发，根因不是敌情口径而是 **fleet_at=480 时间闸**：局1 清净窗 380-445（敌全图可见 65s 为 0、评分 28 达标）与 480 永不重叠，446 波次先把塔拆光。
| O102 | 「o101 0-5 尸检：①塔先排序误伤 GW1（守窗 0 叉）；②过渡期塔铺到 5-6 吃叉子钱（450 波只有 6 叉）；③strong-exit 被 fleet_at=480 时间闸架空（清净窗 380-445 够不到），敌情口径含王虫是附带瑕疵」 | ①`transition_gateway_allowed`（塔闸只管 GW2/GW3，GW1 与 forge 并行双开，首叉 ~140-155 进守窗）；②`transition_cannon_cap`（过渡期塔 4 封顶，余钱进兵营/叉）；③fleet_at 480→420 + strong-exit 敌情口径改家 40 格+is_combat_type（除王虫） | o102-vh-zerg-rush 0-5（avg 406.2s） | 单测 517 全绿（515→517，+2 新测） | **留**（守窗零叉真凶查明，见 O103） |

o102-vh-zerg-rush 系列：0-5（avg 406.2s）。两型死因：局1/2 活到 579-671 但 420 转舰队后 SG 又空转 183s（cyber+SG+FB 800 矿链，12 农单矿喂不饱双线）；局3/4/5 死于 212-298（守窗零叉/农民残废）。**守窗零叉真凶查明（非 spawn fall-through——ares `tech_ready_for_unit` 行为正常）**：GW1 就绪瞬间 O98-③c cyber 买走 150 + rush_active 60s 自解除后 SHIELDS L1 研究注册（UC prioritize 截断 MacroPlan，SpawnController 整段不执行）——守窗的钱被 cyber+研究买光。另 O100 扩张门（8 叉/15s）全系列 0 触发，单矿鸡生蛋死结实证。
| O103 | 「o102 0-5 尸检：①守窗钱被 cyber+SHIELDS 研究买走（rush_active 60s 自解除 vs 波次 155-185 的时间差）；②扩张门 8 叉/15s 永不触发（鸡生蛋）；③forge 派工被水晶 #3 抢 10s+」 | ①`research_paused_for_rush` 加 transition_active 参（过渡期全程停研究）+ `transition_needs_cybercore` 加地面≥2 闸（先有叉站岗再 cyber）；②`transition_expand_ready` 降阈（地面 8→5、清净 15→12）；③`forge_first_pylon_yield`（rush 确认/presumed 且 forge 无实体且 supply>4 → 水晶让位） | o103-vh-zerg-rush 0-5 | 单测 521 全绿（517→521，+4 新测） | **留**（协防范式证伪，见 O104） |

o103-vh-zerg-rush 系列：0-5。**六系列收敛结论：首波（155-200 的 3-6 狗）农民生亡率是所有败局汇聚点**——协防「主动攻击最近敌」范式证伪（赢战斗也输经济：局1 早评 81 成功、GW1 120 完工、首叉 GW+23s 达标，但 t=164-168 协防送死 8 农民 13→4，收入崩到 3/s 慢性死 587；局2/3/4 同指纹骤减 4-7 于 155-213）。局2 补派探机看到二矿没看到 pool 误判 greedy（主基地内部没看清 ≠ 没 rush）。
| O104 | 「o103 0-5 尸检：①协防 charge 范式送农民（13→4 一局残废）；②1 塔就绪就放协防回矿线=狗继续咬采农民（归队条件太松）；③补派见二矿无 pool 证据判 greedy 误判」 | ①`escort_stance`：有就绪塔→塔下作战（attack 塔位，塔+农民双打），无塔→mineral-walk（穿矿往返甩包围，不下 attack）；②归队条件收紧为 2 塔或叉≥2；③vs Zerg 见二矿一律 unknown 不 greedy（pool 没看见≠没 rush；vs Zerg 本就不 pivot，无损） | o104-vh-zerg-rush 0-5（avg 406.6s） | 单测 522 全绿（521→522，+1 新测） | **留**（退出门打通、扩张门死锁查明，见 O105） |

o104-vh-zerg-rush 系列：0-5（avg 406.6s）。实证：协防新范式有效（局2 首波零农民死亡、16 农稳住）+ strong-exit 两连发（局2 评分32、局5 评分28）。新瓶颈：①扩张门全系列 0 触发——strong-exit 后 `_transition_active` 翻假，过渡扩张分支不评估，O96 首舰闸接力挡 260s，且过渡期无 Nexus 攒钱机制（矿恒 0-170）；②局3 协防 ×1 vs 12 狗——停气农民被摘出 GATHERING，候选池只剩 1；③舰队建造窗（420→680）防御断档，局2 13叉4塔死于 723 波。
| O105 | 「o104 0-5 尸检：①扩张门闸门接力+无攒钱机制双杀；②协防拉人池不含停气农民；③SG 串行+建造窗塔 cap 4 不够」 | ①`fleet_expand_holds` 加防御评分豁免（≥25 即便首舰未出也放行）+ `transition_expand_reserve`（过渡期站稳且买不起 Nexus → 停产攒钱）；②协防拉人池 ∪ 停气农民；③`stargate_double_opener`（重建窗 SG 双开）+ `fleet_rebuild_cannon_cap`（窗内塔 cap 4→6） | o105-vh-zerg-rush 0-5（TEMPEST 首见 863.8s） | 单测 526 全绿（522→526，+4 新测） | **留**（机制触达率假说被否、真因查明，见 O106） |

o105-vh-zerg-rush 系列：0-5。局3 打到 968s（历史最长）：strong-exit 420 → 但 SG 空转 300s（723 才落地）→ FB 840 → 首风暴 960 → 死 936-968。「状态门恒假」系统性假说被逐帧否掉（threat/rush 窗内均不真）；真因：①cyber 落位停滞 135s（主基带电 3x3 槽被塔/兵营占满，O55 自救等钱到 551）；②SG 资金被电池×2+塔重建+叉挤掉（矿恒 5-90）；③462 波把防御评分 29→<25，O105 评分豁免后再不达标。局1/2 首波速骰死 193/201（presumed 105 启动仍差 ~20s）。
| O106 | 「o105 0-5 尸检：①重建窗无科技资金优先级（电池/塔重建/叉挤掉 SG 钱）；②窗内塔 cap 6 实证吃 SG 钱；③速骰局 presumed 105 仍晚 20s」 | ①`fleet_tech_reserve`（重建窗+下一件科技缺失+买不起 → 停产攒钱，cyber→SG→FB 优先链）；②窗内塔 cap 6→4；③失联判定/presumed 105→95（补 20s 给 forge+首塔链） | o106-vh-zerg-rush 0-5（avg 210.7s，大回退） | 单测 528 全绿（526→528，+2 新测） | **留**（回退主因查明=latch 漏洞+greedy 回落，见 O107） |

o106-vh-zerg-rush 系列：0-5（avg 210.7s，vs o104 的 406s 大回退）。回退主因不在 O106 三刀：**①O92 时代 latch 漏洞被早评暴露**——早评 verdict=rush 只置 `_rush_active` 不置 `_rush_confirmed`，O94 的炮塔绕过/F2 持有期豁免/GW 让位全部 rush_confirmed 门在早评局到接触（t=154）才武装，白丢 70s（局1/2 早评成功却 0 塔死掉）；**②greedy 回落分支漏网**——补派探机只看到主基地 HATCHERY（无 pool 无兵）落进 `scout_verdict` 回落 → greedy → presumed 被关（局3/4/5）；③E3d 老路不过 O99/O102 塔闸，GW2 抢首塔/首叉的钱（局1 矿 230→5）。
| O107 | 「o106 0-5 尸检：①verdict=rush 不置 rush_confirmed（70s 防御真空）；②greedy 回落分支漏网（单基地无 pool → greedy）；③E3d 老路 GW2 无塔闸」 | ①verdict=rush 时置 `_rush_confirmed=True`（情报确认=证实，全机制 t≈81 武装）；②vs Zerg 早评删除全部 greedy 出口（rush/unknown 二选一）；③E3d 老路加 `transition_gateway_allowed` 同闸 | o107-vh-zerg-rush **1-4（首胜！avg 520.1s）** | 单测 529 全绿（528→529，+1 新测） | **留**（首胜突破，见 O108） |

o107-vh-zerg-rush 系列：**1-4，Zerg Rush 组 14 个系列以来首胜**。胜局（局2，1002s）：unknown verdict（greedy 灭绝生效）→ 接触 459 确认 → strong-exit 评分 37 → 25 风暴+4 基地+65 农碾压，全链验证。败局：①局3/5 评分 31/26 达标但被 fleet_at=420 时间闸卡死（清净窗 380-410 敌全图可见=0，波次 413-421 到脸先把防御嚼光——o101 局1 同构问题复现）；②局4 退出即死（420 退出→425 波次接触→E3d rush 全停重新冻结科技链，SG 到死没拍）；③局1 速骰 190 死（presumed 启动时点无簿记，查不清）。
| O108 | 「o107 1-4 尸检：①fleet_at=420 又成闸门（清净窗 380-410 vs 波次 413）；②退出后 E3d rush 全停冻结 SG（退出即死）；③presumed 启动无簿记」 | ①fleet_at 420→400（评分≥25 门保底，再撞就摘 strong 通道的 fleet_at）；②重建窗内 SG/FB 豁免 E3d rush 全停（与 cyber 同待遇）；③presumed 启动事件簿记（下轮可读） | o108-vh-zerg-rush 0-5（avg 890.1s 历史最佳、TEMPEST 首见 612.8s 最早） | 单测 529 全绿（配置值+复用判据） | **留**（rush 防守关已破，死于中局 scaling，见 O109） |

o108-vh-zerg-rush 系列：0-5 但 avg 890s、5 局全长命——rush 防守关已破，死法全部是中局 scaling：局3（1438s 史诗局）转舰队 442 → 二矿 470/502 连掉（分矿水晶落后 Nexus 80-100s，rush 全停块跳过 `_ensure_expansion_pylon`）→ 敌 66 vs 我 43 磨死；舰队期卡人口 ×3（暴风 6 人口/艘，AutoSupply 默认阈值追不上）；SG 恒 2 座 600s+（250 矿门槛在矿恒 0-250 下永不触发+无攒钱机制），终局仅 3 风暴 vs o107 胜局 25。
| O109 | 「o108 0-5 尸检：①舰队期卡人口停产；②SG 爬坡双锁（250 矿门槛+无攒钱）；③分矿水晶被 rush 全停跳过致 0 晶 0 塔连掉」 | ①`fleet_supply_buffer_needed`（supply_left≤8 直接补水晶）；②`fleet_stargate_reserve`（首舰后 SG 未达标→停产攒钱）+首舰后追加产能矿门槛 250→0；③分矿水晶豁免 rush 全停块 | o109-vh-zerg-rush 0-5（avg 529.2s，TEMPEST 零出场） | 单测 531 全绿（529→531，+2 新测） | **留**（非 O109 误伤，FB watchdog 瘫痪查明，见 O110） |

o109-vh-zerg-rush 系列：0-5。回退定性：非 O109 三刀误伤（SG 预留需首舰已出、buffer 水晶仅 100 矿级，舰队未启动它们没机会开火）——主因是落位停滞长尾集中爆发。**FB 链断根因**：FB 买得起但落位/派工静默失败（主基 3x3 槽耗尽），O93 watchdog 把 `can_afford` 编进停滞计时条件——矿在 300 造价上下振荡 → 计时器反复归零 →「连续 45s 买得起」永不成立，watchdog 全程零触发。局2 SG 同型停滞整局。
| O110 | 「o109 0-5 尸检：①FB/SG 落位停滞 + watchdog 被 can_afford 计时条件瘫痪；②strong-exit 踩波前 40s（波次周期 190-210s）；③重建窗塔不重建（矿荒，暂不修）」 | ①`_fb_stall_watchdog`→`_fleet_stall_watchdog` 重写：计时摘 can_afford、监视面扩到 SG、自救加分矿试建、每 sid 独立计时；②strong-exit 加清净≥30s（退出落在波间隙深位）；③观察 | o110-vh-zerg-rush 0-4+1ERROR（avg 296.6s） | 单测 531 全绿（改写 strong-exit 测试，无新类） | **留**（崩溃根因+速骰最后 15s，见 O111） |

o110-vh-zerg-rush 系列：0-4+1ERROR。ERROR 根因：O110 新字典 `_tech_stall_since` 与 O55 同名 float 属性撞车（AttributeError，单测抓不住的运行时炸）。局1/2：presumed 95 准时启动（簿记生效）但 forge ~105 落地仍晚——首塔 ~165 vs 波次 153-160 差最后 10-15s；O107 后 vs Zerg 侦查对首波防御价值已为零（rush/unknown 二选一）。
| O111 | 「o110 尸检：①`_tech_stall_since` 撞名崩溃；②速骰局 forge 晚 10s（农民训练吃 100-150 矿）；③presumed 等失联/95 已无必要」 | ①改名 `_fleet_stall_since`；②`forge_first_probe_yield`（defense_urgent+forge 无实体+农民≥12 → 停训）；③presumed 对 Zerg 无条件 t≥78 启动 | o111-vh-zerg-rush 0-5（avg 509.4s，无崩溃） | 单测 532 全绿（531→532，+1 新测） | **留**（机制链全通，瓶颈=SG/FB 落位，见 O112） |

o111-vh-zerg-rush 系列：0-5。机制链全部按设计触发（presumed 78 ✓ 5/5、早评 rush ✓ 4/5、strong-exit 400-422 ✓ 4/5），唯一瓶颈 = **SG/FB 落位持续失败**（局1 FB 停滞 516 自救失败死 679、局3 FB 507、局4 SG 445+490 两次）——主基带电 3x3 槽被塔/兵营/水晶占满或生产区无电，watchdog 自救（换池/分矿试建）救不回。
| O112 | 「o111 0-5 尸检：SG/FB 落位失败三候选（3x3 物理占满/带电槽为零/其他），现有事件区分不了」 | ①`gateway_yields_tech_slots`（主基 3x3 余量<2 时 GW3+ 让位，给科技留槽）；②`tech_goes_to_expansion`（重建窗 SG/FB 落分矿）+ watchdog 自救链补「就地补水晶开新槽」；③watchdog 事件带各基地 3x3 余量/总量簿记（下轮定性占满 vs 无电） | o112-vh-zerg-rush **1-4**（局4 Victory 2096s，29 风暴+4 基地） | 单测 534 全绿（532→534，+2 新测） | **留**（第二胜，落位定性「无电」型，见 O113） |

o112-vh-zerg-rush 系列：1-4（avg 809.3s）。胜局局4：29 风暴+4 基地+70 农，但 1500-2096 龟缩 500+s 靠虫族耗死（O64 召回阈值 14 的防守跑步机：每波召回，暴风 2.8 速走到半路回家）。落位簿记定性：局2「槽位余 20/总 25」仍停滞——**非占满，是带电槽为零**（水晶全锚坡口/矿线，生产区 3x3 无电）。局1/3 速骰 191-262 死（首塔 vs 波次仍掷硬币）。
| O113 | 「o112 1-4 尸检：①落位失败=无电型（余 20 槽全不带电）；②O64 召回 14 太敏感造防守跑步机（舰队 ≥12 时 15-20 波也召回）；③速骰局 presumed 78 仍差一口气」 | ①`pick_slot_anchor`+`_free_3x3_slots_at`：watchdog 补水晶贴空闲 3x3 槽落（槽位通电）；②`fleet_no_recall_threshold`（舰队≥12 → 召回阈值 14→25，换家比回防快）；③presumed 78→65 | o113-vh-zerg-rush 0-5（avg 461.3s） | 单测 537 全绿（534→537，+3 新测） | **留**（槽位口径不含电力实锤，见 O114） |

o113-vh-zerg-rush 系列：0-5。**SG 落位因果链闭环**：局1 矿 290-535 充足但 SG 六轮自救全失败——watchdog 簿记「余 21/25」是不带电口径（available 不过 psionic matrix），真实带电空闲=0；贴槽水晶通电后槽被塔/兵营抢走（21→4 实证），SG 永远排不上。局3：presumed 65 准时但 F2 注册被 dispatch_viable（矿+5s 收入≥150）拖到 110.7，45s 全丢；局4：spawn (38,122) 第三次复现「有 forge 仍 0 塔」，地图级落位问题嫌疑。
| O114 | 「o113 0-5 尸检：①槽位余量口径不含电力（假空闲 20）；②通电槽被塔/兵营抢（无科技硬预留）；③F2 dispatch_viable 守卫拖 45s+spawn(38,122) 塔落位疑案」 | ①`_slot_counts_at`（带电空闲/空闲/总三值，cy_pylon_matrix_covers 过滤）全口径统一；②带电口径生效后 `gateway_yields_tech_slots` 真触发（3x3 消费者只有兵营/科技）；③`f2_dispatch_guard_bypassed`（0 塔紧急时跳过收入守卫）+首塔停滞 2x2 三值簿记 | o114-vh-zerg-rush 0-5（avg 561.5s） | 单测 538 全绿（537→538，+1 新测） | **留**（落位链已通，死于爬坡死锁，见 O115） |

o114-vh-zerg-rush 系列：0-5。落位问题大体解决（局3 链全通：contact 430→strong-exit 579→FB 683）。两个新死锁查明：①**SG 爬坡死锁**——O101-Z 重建窗恒产 GATEWAY，关窗条件=首舰出场，首舰需 FB+产出 → SG2 被判据性排除（「首舰没出→不产 SG→爬坡断档」）；②**O106 科技预留死锁**——FB 被拆后 `_next_tech` 恒缺、预留恒开、SpawnController 永久暂停，地面回填连坐（工人 30→0 一兵未补）。分矿 482 失守=水晶 0→2 花 85-115s（工人走进被抄区被杀）。
| O115 | 「o114 0-5 尸检：①重建窗兵营劫持致 SG 爬坡死锁；②科技预留在 FB 被拆后永久锁死地面回填；③分矿供电落后 Nexus 85-115s」 | ①`rebuild_extra_production_id`（FB 已拍且 SG<3 → 追加 SG 否则 GW）+双开门 300/200→200/150；②`fleet_tech_reserve` 加 `tech_stalled` 参（watchdog 开火过→预留解除）；③分矿水晶供电目标扩到在建 Nexus 落点（与 Nexus 并行建） | o115-vh-zerg-rush 0-5（avg 585.8s，TEMPEST 811.6s） | 单测 540 全绿（538→540，+2 新测） | **留**（派工静默失败取证，见 O116） |

o115-vh-zerg-rush 系列：0-5。**「没电/没槽」假说被否定**：局3 首塔停滞时「带电余 9、空闲余 22」、局5 SG 停滞时「带电余 7」——钱够槽够电够，建造请求静默落空，真凶在派工链路（选工/落位请求/工人死路上），主嫌 `no_worker`（协防≤10+停气 6+建造占用把 GATHERING 池抽干）。
| O116 | 「o115 0-5 尸检：派工静默失败四分类不明（没注册/没位置/没工人/工人死路上）」 | ①`_dispatch_structure()`（落位→选工→下单三段，返回失败环节）替换首塔 bypass 与 watchdog 重试，事件带失败环节+池余量；②`builder_borrow_ok`（GATHERING 空→从停气池借最近农民，摘台账防回气循环拽走） | o116-vh-zerg-rush 0-5（avg 546.5s） | 单测 541 全绿（540→541，+1 新测） | **留**（取证命中：停气棘轮+O11 循环，见 O117） |

o116-vh-zerg-rush 系列：0-5。O116 取证一发命中两案：**①停气棘轮（支配性）**——`_rush_gas_stop` 台账单向（只在 rush 翻假归还），慢性骚扰下 rush_active 长期 latch，Mining 补人→每帧摘→只进不出，局3 停气池 38/采集池 0 经济停摆；**②taken 型停滞=O11 钉点撤回+F2 重派冷却 21s 循环**（E4c 豁免只看 rush_active，presumed/早评窗未置位）；③no_placement 偶发（贴槽水晶与目标槽距离或超电力半径，未死证）。
| O117 | 「o116 0-5 尸检：①停气台账棘轮只进不出；②O11 撤回+15s 冷却的 21s 循环卡住首塔/科技派工；③贴槽水晶电力半径存疑」 | ①`rush_gas_stop_window`（停气限定急性窗 45s，窗后/解除自动回气回采；其他流派 inf 旧语义）；②`builder_release_exempt`（defense_urgent=rush∪过渡∪presumed，O11 豁免改走它）；③观察 | o117-vh-zerg-rush **1-4**（局5 Victory：28 风暴+4 基地+70 农） | 单测 543 全绿（541→543，+2 新测） | **留**（停气修复实证，速败三局同指纹，见 O118） |

o117-vh-zerg-rush 系列：1-4。停气棘轮修复实证（停气池=0、采集池正常）。三局速败（死 190-202）同指纹：presumed 65 ✓、F2 注册 65 ✓、forge ~95 就绪 → **60s 静默 → 派工=taken 到死**——工人被入侵狗群杀路上/被拽走后，tracker 要等 45s watchdog 周期才回收，首塔窗（95→150）只有 55s，一个死工人吃掉大半。
| O118 | 「o117 1-4 尸检：①taken 回收 45s 太慢（首塔窗 55s）；②presumed→forge 延迟 60-104s=PSD 水晶+GW1 抢 forge 资金窗（局1 水晶#2/#3、局3 水晶+GW1 连抢）；③首塔落点在入侵路径上+协防穿矿目标穿过狗群」 | ①`tracker_entry_stale`（工人死/闲置>10s 立即清 tracker 重派）；②`_presumed_defense_chain`（presumed 窗 forge/首塔绕开 PSD 直派）+`forge_before_first_gateway`（GW1 让位 forge）；③`cannon_safe_anchor`（首塔退 2.5 格）+`pick_walk_patch`（协防穿矿目标改「离威胁最远」矿簇） | o118-vh-zerg-rush 0-5（avg 511.5s，速骰局 3/5→1/5） | 单测 547 全绿（543→545→547） | **留**（前半场已稳，单矿退出=死亡判决，见 O119） |

o118-vh-zerg-rush 系列：0-5。O118 实证：速骰局从 3/5 降到 1/5、strong-exit 3/5——前半场已稳。死因唯一化：**单矿退出=死亡判决**（局5 典型：400 退出时 6叉4塔12农单矿 → 440-480 波 25-35 supply → 塔 4→1 叉清零 → 死 543；三个胜局全是 3-4 基地局）。过渡期扩张 0 触发根因=波间隙 8-12s 切碎清净窗（要 12s）。
| O119 | 「o118 0-5 尸检：①单矿退出必死（12 农产出在 440+ 波次前物理不够）；②扩张清净窗 12s 超波间隙实测 8-12s；③退出时地面太薄（6叉 无下限）」 | ①`fleet_exit_allowed`（bases≥2 或 Nexus 在建才退，t>600 单矿放行兜底）；②`transition_expand_ready` 降阈（4叉/8s）；③退出加地面 supply≥14 下限（不够自校正补够再退） | o119-vh-zerg-rush 0-5（avg 408.0s） | 单测 549 全绿（547→549，+2 新测） | **留**（退出闸全挡死、GW2 资金排队查明，见 O120） |

o119-vh-zerg-rush 系列：0-5。退出经济门 5 局全挡（bases≥2/地面≥14 从未同时满足）→ 全死在过渡期 491-820。GW2 卡死根因=**资金排队**（非门拦）：2 塔 237 就位后塔#3/电池×2/塔#4/叉子连续吃矿，矿恒 0-145，GW2 的 150 矿 220s 没轮上；叉产能锁死 1/30s，460 波 6 叉 vs 19 supply。
| O120 | 「o119 0-5 尸检：①GW2 资金排队 220s（塔/电池/叉连续吃矿无人给兵营攒钱）；②电池超载从没用过；③过渡期电池 0-1 座无续航」 | ①`transition_gateway_reserve`（2 塔+兵营<cap+买不起 → 停产攒 GW）；②`should_overcharge`+`overcharge_with_batteries`（敌进 15 格给盾量最低友军挂超载）；③`transition_battery_floor`（过渡期电池 ≥2） | o120-vh-zerg-rush 0-5（avg 641.6s，TEMPEST 743.3s） | 单测 551 全绿（549→551，+2 新测） | **留**（死因唯一化=舰队 150s 空窗，见 O121） |

o120-vh-zerg-rush 系列：0-5。退出质量改善（O119 地面下限让 strong-exit 延到 497-600、评分 32-33），但死因唯一化=**舰队 150s 空窗**：退出后 SG→FB→首舰 ~190s，波次 exit+60s 到脸时仅 0-1 风暴，终局编成 1 艘。超载零触发根因=`not s.orders` 过滤（波次中电池在平奶就被跳过）+能量门 50 偏紧。
| O121 | 「o120 0-5 尸检：①舰队 150s 空窗（0-1 风暴迎 30 supply 波）；②超载被 orders 过滤+能量门卡死；③退出时 SG 未拍=空窗再 +60s」 | ①`rebuild_window_spawn`（重建窗 VOIDRAY p0 填窗，37s 成型不需 FB，FB 就绪后暴风自然挤占）；②超载去 orders 过滤+能量 50→45+触发簿记；③`transition_stargate_allowed`（评分≥25 过渡期解冻 SG）+`fleet_exit_allowed` 加 SG 已拍前提 | o121b-vh-zerg-rush 0-5（avg 460.3s） | 单测 554 全绿（551→554，+3 新测） | **留**（超载实证，虚空被预留连坐，见 O122） |

o121b-vh-zerg-rush 系列：0-5。超载实证（局1 触发 ×4）。虚空 0 艘之谜查明：O106 科技预留在「FB 缺+矿<300」时恒开 → SpawnController 整段暂停 → 虚空被连坐（watchdog 45s 才解除，波次 exit+39s 就到）；SG 产线配方层无断点。局1：strong-exit 632（评分55）→ 671 波（3 矿虫族 40+ supply）穿双矿。
| O122 | 「o121b 0-5 尸检：①科技预留连坐虚空填窗；②单矿中骰局必死（三胜局全是慢骰安心扩张）；③超载目标选择未验」 | ①`fleet_tech_reserve` 加虚空优先参（有虚空在产/已出才许为 FB 停产）；②`transition_expand_after_first_wave`（见过且清除一波+塔≥2+地面≥4 即开二矿，不看清净秒数）+`_saw_wave` latch；③`pick_overcharge_target`（残盾塔优先）+超载事件带目标名 | o122-vh-zerg-rush 0-5（avg 337.2s，回退） | 单测 556 全绿（554→556，+2 新测） | **留**（塔链物理极限判定，转叉海 A/B，见 O123） |

o122-vh-zerg-rush 系列：0-5（4/5 速败 198-238 回归）。塔链打最快骰物理极限确认：presumed 65 → 攒 150 矿需 ~100-110 → forge 125-141 → 首塔 175-185 vs 波次 154-190，硬币无解。30 轮迭代的结构性结论：**塔/forge/落位链贡献 ~60% bug 面**（落位失败、电力口径、派工静默、资金排队），叉子不需要其中任何一项；三胜局地面核心都是叉/追猎海。
| O123 | 「o122 0-5 尸检+战略转向：①塔链最快骰无解+bug 面集中；②超载挂 PYLON；③叉≥4 后协防仍送农民」 | **叉海 A/B**：①`transition_cannon_cap` 4→2 + `transition_gateway_reserve` 反转常态预留（GW<cap 持续攒，兵营链最优先）——目标 t=250 叉 8-10、t=450 叉 16-20+追猎 3-4；②超载白名单（PHOTONCANNON/NEXUS/战斗单位）；③协防归队线 2→4 叉 | o123-vh-zerg-rush（N=5 跑局中） | 单测 558 全绿（556→558，+2 新测） | **留**（待 bench，A/B 判读：t=250/450 叉数+440 波战损比） |

o121 首跑局1 ERROR：`rebuild_window_spawn`/`transition_stargate_allowed` 两个新判据忘了 import（NameError，agent 编译检查口径没盖到运行时 import 链）——已补 import、按 CLAUDE.md 验证命令双流派编译+554 全绿，重跑为 o121b-vh-zerg-rush。教训入档：新判据落地后必须跑 CLAUDE.md 验证节的 import 检查而不是仅编译单文件。

o123-vh-zerg-rush 系列（叉海 A/B 首跑）：0-5（avg 311.2s，首叉 303s 更晚）。翻车根因：①常态预留自伤——为 GW2/GW3 攒钱时 SpawnController 整段暂停，GW1 空转 76s（为不存在的兵营攒钱、让现役兵营空转）；②气矿早建吃 150×2 矿（叉海不需要气，gas 烂 468-588）。
| O124 | 「o123 0-5 尸检：①预留饿死现役兵营；②过渡期气矿吃叉子钱；③首叉无冲刺机制」 | ①`transition_gateway_reserve` 加 `zealot_producible` 参（有空闲 GW+矿≥100 → 不预留先产叉）；②`transition_pauses_gas`（过渡期不建新气矿）；③`first_zealot_sprint`（rush 确认+GW 就绪+首叉未出+矿<100 → 水晶/农民全停） | o124-vh-zerg-rush（N=5 跑局中） | 单测 561 全绿（558→561，+3 新测） | **留**（待 bench） |

o124-vh-zerg-rush 系列：0-5（avg 481.6s，VOIDRAY 首见 679s——虚空填窗实证出厂）。但首叉仍 337.5s：盘出三段延迟=O79 分矿保底水晶吃 200 矿（不在 AutoSupply 让位覆盖内）+ GW1/forge 互抢 + 无 chrono。
| O125 | 「o124 0-5 尸检：①首叉 337s（O79 水晶+互抢+无 chrono 三段延迟）；②O118 forge 优先是塔链残留与叉海冲突」 | ①`forge_first_probe_yield` min_workers 12→11；②`chrono_first_zealot`（rush 窗 chrono 给在产兵营，首叉 27→19s）；③`gateway_before_forge` 取代 `forge_before_first_gateway`（叉海顺序反转：先 GW1 后 forge，预期首叉 ~140-145） | o125-vh-zerg-rush（N=5 跑局中） | 单测 563 全绿（561→563，+3 新测） | **留**（待 bench） |

o125-vh-zerg-rush 系列：0-5。首叉仍晚——但真凶修正：快照 GATEWAY 是在建口径（GW1 117 开工 163 才完工），零叉是「兵营还没好」+完工瞬间 forge/GW2 抢矿（163 完工时矿 45）。预留闸全部为假，`zealot_producible` 豁免的前提（就绪空闲 GW）不满足。
| O126 | 「o125 0-5 尸检：①GW2/forge 与首叉资金撞车（GW2 在 GW1 完工前抢矿）；②六道预留闸各自为战无仲裁」 | ①`spawn_pause_reason` 仲裁器单点决策（叉子保底凌驾一切预留：空闲GW+矿≥100+需要地面 → 必产）+暂停原因事件簿记（30s 节流）；②`gateway_chain_after_first_zealot`（GW2+ 等首叉在产） | o126-vh-zerg-rush（N=5 跑局中） | 单测 567 全绿（563→567，+4 新测） | **留**（待 bench） |

o126 首跑两局 ERROR：`gateway_chain_after_first_zealot` 接入点的 `_gw_have` 局部变量漏定义（NameError，import 级编译检查抓不住函数体内的未定义名——第二次同类事故）。已补定义（GW+WARPGATE 已有+在建口径），567 全绿，重跑为 o126b-vh-zerg-rush。教训更新：新接线点除 import 检查外，需要跑一次真实对局烟测（bench 单局）才算落地。

o126b-vh-zerg-rush 系列：0-5（仲裁器簿记立功：`产兵暂停=gw_reserve(矿30,地面0)` 直接指认 GW2 攒钱抢首叉；GW1 开工 120 仍晚=O79 分矿保底水晶偷 200 矿）。forge/GW 顺序算术终裁：forge 优先（75 拍→塔 140-145）才能打 154 波，GW 优先（叉 155-165）必败——O118 方向对、O125 反转为误。
| O127 | 「o126b 0-5 尸检：①forge 优先方向对但没能在 75-80 开拍（O79 水晶偷窗）；②gw_reserve 先于首叉；③首塔 29s 建造窗无协防掩护」 | ①恢复 `forge_before_first_gateway`+O79 水晶纳入让位（forge ≤80 开拍）；②仲裁器加首叉参（首叉未出 GW 链预留不暂停）；③`escort_stance` 加 cannon_pending（塔在建即回撤守建造点） | o127-vh-zerg-rush（N=5 跑局中） | 单测 568 全绿（567→568）；烟测 1 局 0 错误（首塔 dispatched 148.8 系列最早） | **留**（待 bench） |

o127-vh-zerg-rush 系列：0-5（avg 351.7s）。取证决定性：首塔派工=tech_not_ready 从 81 刷到 167——forge 100s 迟到的三段偷钱=①手动链窗口太窄（rush_active 置位即退出，PSD 水晶 92/108 连偷 200）+②③b 兵营链无 forge 顺序闸（GW1 t=122 抢）+③forge 137 才开工。spawn(38,122) 塔位无电第四次复现。
| O128 | 「o127 0-5 尸检：①手动链窗太窄+PSD 水晶+③b 无闸（forge 100s 三段偷钱）；②塔位区无电（四局累犯）；③taken 循环=工人反复死路上（回收机制已在）」 | ①手动链窗口扩到「首塔落地才交还 F2」+③b 加 forge 顺序闸；②`tower_zone_pylon_needed`（forge 拍下即派塔位供电水晶，供电+开位一石二鸟）；③不加新机制（塔位供电+矿线深位联合覆盖） | o128-vh-zerg-rush（N=5 跑局中） | 单测 569 全绿（568→569） | **留**（待 bench） |

o128 首跑两局 ERROR：`tower_zone_pylon_needed` 又没 import（第三次同类事故）。已补+固化了 AST 判据 import 检查脚本 `ares-bot/scripts/check_judge_imports.py`（判据名×import 清单对比，挡函数体内 NameError），烟测 1 局 0 错误，重跑为 o128b-vh-zerg-rush。**后续所有 O 系列落地必须过此脚本+1 局烟测。**

o128b-vh-zerg-rush 系列：0-5。水晶 68/92/108/137 连拍 4 根（400 矿）+GW 125 插队 → forge 又 165——逐路径让位修 6 轮修不完，打法证伪。
| O129 | 「o128b 0-5 尸检：逐路径让位打法证伪（水晶四路径漏不完）」 | **冲刺总闸** `defense_sprint_active`（presumed/rush 起到 forge+首塔+首叉链完成前）：probe/水晶（≤1 应急除外）/GW2+/气矿/研究/F2 单点统掐；链序硬编码 forge→首塔→GW1→首叉 | o129-vh-zerg-rush（N=5 跑局中） | 单测 572 全绿（569→572，+3 新测）；烟测 forge 117/首塔 152.7（0 错误） | **留**（待 bench） |

o129-vh-zerg-rush 系列：**1-4（第四胜，局2 Victory 26 风暴；avg 925.3s）**。速骰清零（5 局全活过 450）。新死因=冲刺死亡螺旋：GW1 在建被拆→链永远差一环→sprint 永真→探针永冻→2-3 农民局死 484-892（局3 矿恒 65）。
| O130 | 「o129 1-4 尸检：①sprint 无逃逸阀（链断=全局锁死）；②协防把农民全拉空（14→2-3）；③第二塔 no_placement 复发（锚点判定与电力覆盖几何不一致，下轮候选）」 | ①sprint 加 120s 强制退出+`sprint_blocks_probes`（农民<8 豁免总闸）；②`escort_pull_cap`（任何时刻留 6 采矿）；③观察 | o130-vh-zerg-rush（N=5 跑局中） | 单测 575 全绿（572→575，+3 新测）；烟测 0 错误 | **留**（待 bench） |

o130-vh-zerg-rush 系列：0-5（avg 420.7s）。仲裁器簿记指认支配性死因：**暂停型预留死锁变体**——gw_reserve 暂停产兵攒钱，但 F2 塔不在仲裁器管辖照建照吃（矿恒 15-95 永远攒不到 150），局2 从 297 刷到 568+、局5 从 243 刷到 610；O119 退出经济门从未满足，无人能转舰队。
| O131 | 「o130 0-5 尸检：①预留只停兵不停塔=永久暂停；②暂停型预留在赤贫局是死锁发生器；③无保险丝」 | ①F2 塔注册纳入预留管辖；②gw_reserve 暂停型→排队型（`tower_yields_gateway_chain`，SpawnController 永不停）；③`reserve_deadlock_break` 保险丝（预留>60s 且矿<150 强制解除+事件） | o131-vh-zerg-rush（N=5 跑局中） | 单测 577 全绿（575→577，+2 新测）；烟测 0 错误（首版保险丝 UnboundLocalError 被烟测当场抓到） | **留**（待 bench） |

o131-vh-zerg-rush 系列：0-5（avg 628.2s，one_base×5）。队列化后死锁消失但扩张在 rush 压力下仍零成功，O119 经济门与之互锁（无二矿不准退舰队；退不出去就磨死）。**战术决定：改进已跨组可迁移，先收其他五组（n5m 旧码已 2-3/1-4/2-3），Zerg Rush 留到最后回头攻坚。** 开 o131-vh-zerg-timing。

o131-vh-zerg-timing 系列：0-5（avg 634.7s）。**O119 退出经济门定性为系统性败笔**：上线后 0 胜（rush 压力下扩张从不成功→无人转舰队→全磨死），四胜全部发生在它之前。timing 局1：11 叉守到 542、580 波 27 supply 穿、全程未转舰队。
| O132 | 「o131 两系列 0-10 尸检：①退出经济门掐死舰队路（0 胜 vs 此前 4 胜）；②塔 cap 2 太薄（timing 波穿防）；③塔闸吃实时口径（塔被打掉后兵营链永锁）」 | ①`fleet_exit_allowed` 三选一（bases≥2 / 地面≥20 / 评分≥35），死线 600→540；②塔 cap 2→3；③塔口径改峰值 latch（`_cannons_peak`，塔被拆不再回头锁兵营） | o132-vh-zerg-timing（N=5 跑局中） | 单测 577 全绿；烟测 0 错误 | **留**（待 bench） |

o132-vh-zerg-timing 系列：**1-4（第五胜，局3 Victory 28 风暴+4 基地；TEMPEST 首见 554.5s）**。四败同指纹：timing 波 273-289 到脸、323-384 死——局1/2/5 verdict=unknown 等接触才进过渡（零防御接波）；局4 早进过渡但 289 波时规模不够。O71 二次侦查 250 才派，看到兵时波已出门。
| O133 | 「o132 1-4 尸检：①二次侦查太晚（250 派出，timing 波 273-289 到脸）；②unknown=零防御等接触；③过渡 240+ 防御规模无冲刺」 | ①二次侦查 250→195/截止 330→260，判 rush 即置 rush_confirmed+进过渡；②vs Zerg unknown 且 t≥200 按 presumed 级拉 2 塔；③t≥240+过渡 active 非 greedy → GW3+塔3+电池1 冲刺 | o133-vh-zerg-timing（N=5 跑局中） | 单测 580 全绿（577→580，+3 新测）；烟测 0 错误 | **留**（待 bench） |

o133-vh-zerg-timing 系列：0-5（avg 482.5s）。支配性死因=**非过渡局地面兵力真空**：局2 铁证——二矿 300、农民 39（经济好），但 t=542 仅 1 叉+2 兵营；525 波 25+ supply 到脸 1 叉应战，39 农民 60s 死光。carrier 标准路径 500 前零地面产出，任何 mid-game push 都是死刑（跨组通用洞，Terran 组同构）。
| O134 | 「o133 0-5 尸检：①非过渡局 500 前地面零产出（39 农 1 叉迎 25 supply 波）；②地面 floor 资金位；③525 波级电池/超载覆盖」 | ①carrier 标准路径加地面 floor（2GW 叉/追猎，t≤300 达 10-14 supply，舰队链不打断）；②复用现有配方 floor 语义；③超载覆盖校 | o134-vh-zerg-timing（N=5 跑局中） | 单测 582 全绿（580→582，+2 新测）；烟测 0 错误 | **留**（待 bench） |

o134-vh-zerg-timing 系列：0-5（avg 609.7s）。地面 floor 进了配方但产不出（局1：42 农 2 矿 2GW 就绪，t=542 仅 3 叉——兵营空转）。**暂停型预留体系整体证伪**：六道预留闸 40 轮出 6 次死锁变体，攒钱期间建筑侧照吃，兵营空转。
| O135 | 「o134 0-5 尸检：预留暂停产兵的语义整体错误」 | **产出永不暂停**：SpawnController 注册与五道预留闸脱钩（语义反转——攒钱暂停的是建筑注册不是产兵）；仅 rebuild_nexus（基地清零应急）保留停产权；保险丝改防建筑永久冻结镜像死锁 | o135-vh-zerg-timing（N=5 跑局中） | 单测 580 全绿（582→580，-4 旧预留用例 +2 新）；烟测 0 错误 | **留**（待 bench） |

o135-vh-zerg-timing 系列：0-5（avg 570.1s）。兵营仍晚（GW1 ~390）——**反应式调度的资金纪律到头了**：没有一个机制保证「GW 在 t≈100 一定开建」。转硬编码 OpeningBuildOrder（'12 gateway' 起手，落地 ~137）。
| O136 | 「o135 0-5 尸检：①反应式调度证伪（GW 落地时点漂移 120-390）；②速骰硬币差 1-2s 榨不出水；③需要结构性解」 | ①protoss_builds.yml OpeningBuildOrder 硬编码 '12 gateway'；②③坡口墙：ares Ramp.protoss_wall_buildings 取墙槽，rush/presumed 后 GW+forge 落墙位封主坡，叉子墙后 hold，协防肉身填缝到墙死 | o136-vh-zerg-rush（N=5 跑局中） | 单测 583 全绿（580→583，+3 新测）；烟测 0 错误（墙武装事件✓） | **留**（待 bench） |

o136b-vh-zerg-rush 系列：0-5（avg 231.5s，大回退）。墙逻辑卡死 forge/GW 派工（墙派工无 can_afford 守卫工人驻车干等 90s+ + 墙链每帧 return 挡死原链），局1 慢骰也 0 防具死 223。
| O137 | 「o136b 0-5 尸检：墙派工无守卫+挡死原链」 | ①墙派工 15s 未开工回落普通槽+O116 四分类取证；②墙派工失败两次全局关墙 latch；③烟测核墙成型 | o137-vh-zerg-rush（N=5 跑局中） | 单测 585 全绿（583→585，+2 新测）；烟测 0 错误（墙链仍偏慢：GW 156 才派工，下轮候选提速） | **留**（待 bench；若再 0 胜则关墙回 o135 基线） |

o136b/o137 两系列 0-10：坡口墙实验整体证伪（墙派工拖累防链），O138 关墙回滚（`_WALL_ENABLED=False`，代码留档）；'12 gateway' 硬编码开局保留。**双通道实证可行**（两 SC2 实例并行 100s+ 无互踢），CLAUDE.md「双车道不可行」条目已修正。
| O138 | 关墙回滚 | `_WALL_ENABLED=False`（墙链/墙后站位/堵缝全关，o135 行为恢复） | — | 单测 585 绿；烟测 0 错误 | **留** |
| O139 | 「司令观察：前期农民钉建造点干等钱不采矿（每系列 idle_builder×5）」 | ①手动派工链接入 `dispatch_viable`+10s 冷却（此前只 F2 有守卫）；②O11 撤回前移到「钉点>3s 且缺口>5s 收入」；③开局序列/AutoSupply 路径观察 | o139-vh-zerg-rush（N=5 跑局中，双通道 lane A） | 单测 586 绿（585→586，+1 新测）；烟测 0 错误（干等事件仍有 18 起——ares 原生路径残余，下轮看） | **留**（待 bench） |

o139-vh-terran-rush/timing 双系列：0-5/0-5（avg 556.9/593.3s）。**退出门死锁实锤**：局2 评分 35/地面 26 全达标但 SG=0——`fleet_exit_allowed` 要 SG 已拍，而 SG 要解冻（评分≥25）+150 矿（单矿恒 25-75）→「SG 已拍才准退、SG 要退才解冻」循环。电池 floor 失效=PSD 无 can_afford 守卫，电池工驻车↔撤回死循环 280s 零落地。
| O140 | 「o139 双系列 0-10 尸检：①退出门 SG 前提死锁；②电池驻车循环；③叉停 12=单矿资金天花板」 | ①SG 前提改「已拍或评分≥35」；②transition 电池改手动派工（dispatch_viable+冷却）；③退出解锁后矿自然攒向 SG→FB（floor 退配方） | o140-terran-rush/zerg-rush（双通道跑局中） | 单测 586 绿；烟测 0 错误 | **留**（待 bench） |

o140 双系列：0-5/0-5（zerg-rush avg 232.4 / terran-rush 560.6）。'12 gateway' 开局与 presumed forge 链抢同一笔 150 矿（runner 与 bot 层管辖冲突），forge 又 140+。
| O141 | 「o140 尸检：runner/bot 开局管辖冲突」 | OpeningBuildOrder 实测调优两轮：'13 supply/14 forge/15 gateway' + 摘 chrono@nexus + presumed 65→55 + 水晶卡人口也让位 forge + chrono_forge_first（33→23s）；runner/bot 共用 tracker 不双建（代码级确认） | o141-zerg-rush/terran-timing（双通道跑局中） | 单测 587 绿（586→587）；3 局烟测 forge 116-129/首塔 157-173（0 错误） | **留**（待 bench） |

o141 双系列：0-5/0-5（zerg-rush avg 315.5/terran-timing 655.7）。**环形死锁实锤**：runner 开局 '14 forge' 要等 supply≥14，probes 被 sprint 冻结永远到不了 14，forge 不建 sprint 不结束——矿堆 670 什么都不建（o141-zerg-rush 局3）。
| O142 | 「o141 尸检：runner supply 触发 × bot 农民冻结互锁成环」 | OpeningBuildOrder 回退为只有农民+水晶（forge/GW/塔全部归 presumed/防御链管，bot 层时序不受 supply 触发约束） | o142-zerg-rush/zerg-timing（双通道跑局中） | 单测 587 绿；烟测活到 702s（此前 198-317） | **留**（待 bench） |

o142 双系列：0-5/0-5。**strong-exit 自 o133 以来归零**——叠加门死锁：`fleet_exit_allowed` 在 strong-exit（评分+清净30s）之上又叠经济三选一/SG/地面三门；o129 局5 评分 41 单矿无 SG 不退、o142-timing 局5 评分 29 被「34<35」卡死。
| O143 | 「o142 尸检：退出门叠加死锁（评分达标也退不出）」 | 评分 ≥25 直接放行（低防局仍走原三门防裸奔） | o143-zerg-rush/terran-rush（双通道跑局中） | 单测 587 绿；烟测 0 错误 | **留**（待 bench） |

o143 双系列：0-5/0-5（zerg-rush 322.4 / terran-rush 585.0）。退出门修复未见胜场——回归源继续二分。
| O144 | 「o133 以来零胜回归二分：嫌疑=O133 过度防御两刀+O134 floor 误伤运营局」 | ①`unknown_verdict_defense` 关断（unknown 不再拉 presumed 级防御，省 400 矿）；②`transition_timing_sprint` 关断（删 t≥240 无差别冲刺）；③`ground_floor_active`（仅 rush_confirmed/敌可见≥4 才激活 floor） | o144-zerg-rush/zerg-timing（双通道跑局中） | 单测 588 绿（587→588，+1 新测）；烟测 0 错误 | **留**（待 bench） |

o144 双系列：0-5/0-5。strong-exit 恢复触发（O143 实证 评分25 放行 ✓），但死于舰队窗：局3 退出 400 → SG 600 → FB 643 → 波 700 穿（1 虚空迎战）。**农民恒 12-13 长达 240s（矿 280 躺着）+ 二矿零开**——单矿 12 农的穷局撑不起舰队链。
| O145 | 「o144 尸检：①农民 12-13 卡死（闸静态全假，疑 rush_active 粘连）；②舰队期扩张预留带 first_fleet_seen 前提（首舰前不攒钱，科技链吃光 Nexus 400）」 | ①O145 九项读数取证事件（rush/hold/yield/sprint/矿/supply/闲置基地/过渡/转舰队，30s 节流）；②`fleet_expansion_reserve` 加评分≥25 豁免（首舰前可为二矿攒钱）+预留激活时科技链让位 Nexus 基金 | o145-zerg-rush/terran-power（双通道跑局中） | 单测 588 绿；烟测 0 错误 | **留**（待 bench） |

o145 双系列：0-5/0-5（14 连零胜）。**元诊断**：胜局时代退出形态=13-15叉+4塔+15-20农，现局=7-8叉+3塔+12农——刹车家族（O97-C/O111/O125/O129）每个省 50 矿换几秒，叠加把 400s 收入腰斩，「为最快骰优化把中盘饿死」。
| O146 | 「o145 尸检：农民被长期压 12（持续型刹车条件）」 | ①`probe_floor_needed`（t≤350 非急性窗农民<16 必产，绕过一切刹车）；②刹车家族窗口化（`transition_probe_yield` 加 acute 参、forge 让位加 200s 截止）；③目标形态 16农/13叉/3塔@300 | o146-vh-zerg-rush（跑局中，terran-power lane 并行） | 单测 591 绿（588→591，+3 新测）；烟测 0 错误 | **留**（待 bench） |

o146b/o146c 冻结复测：0-5/0-5（avg 272/284）——确认当前构建真胜率 ~0%，o107-o132 时代的 20% 是真回退。**根因定性：O139 钉点治理误伤**——钉点（驻点等钱，钱到秒开工）恰是 forge 准点的关键机制，守卫+早撤回+冷却把 forge 从 ~100 漂回 125-155，且 forge→首塔出现 43s 守卫空档。
| O147 | 「冻结复测确认回退+O139 误伤定性」 | `_dispatch_structure` 加 `critical` 参（forge/首塔/GW1 豁免收入守卫+撤回+冷却，驻点等钱即正义）；forge→首塔同帧衔接 | o147-zerg-rush/terran-power（双通道跑局中） | 单测 592 绿（591→592，+1 新测）；烟测 0 错误 | **留**（待 bench） |

o147 双系列：0-5/0-5（zerg-rush 479.5 / terran-power 0-5 但终局 TEMPESTx10——舰队能成型、打不赢波次）。16 连零胜，宏观链已通，转攻战斗微操层。
| O148 | 「o147 尸检：宏观链通、战斗粗放（叉子开阔地被围杀/伤兵不后拉/防守锚点在基地中心）」 | ①守军锚点改 `_ramp_hold_point`（坡顶内侧 4 格，sharpy 同款）；过渡期地面守坡口不推进；②`hurt_retreat_needed`（盾血<30% 后拉到电池/塔圈奶回再上）；③协防分工与超载目标验证在跑无需改；附带修 O146 农民下限与 forge 竞速互抢（sprint 并入急性窗） | o148-zerg-rush/terran-timing（双通道跑局中） | 单测 593 绿（592→593，+1 新测）；烟测 0 错误 | **留**（待 bench） |

o148 双系列：0-5/0-5（zerg-rush 456.0 / terran-timing 730.7 航母 570s 出厂）。O145 取证实证：农民停滞=yield+矿 0（赤贫非闸 bug）；元诊断收敛：**二矿存活率=胜率**（五胜局全 3-4 基地，败局全 1-2）。
| O149 | 「o148 尸检：二矿从不存活——清净窗判据在持续波次下永不满足、塔慢于 Nexus、守军只守主基」 | ①`transition_expand_at_210`（过渡+过波+t≥210 强开二矿，不等站稳门）；②`_expansion_predefense`（Nexus 在途即同帧预派供电晶+2塔+1电池，塔 29s 先于 Nexus 71s 落地）；③`two_base_guard_point`（双矿时 rally 改两矿连线中点） | o149-zerg-rush/terran-power（双通道跑局中） | 单测 595 绿（593→595，+2 新测）；烟测 0 错误 | **留**（待 bench） |

o149 双系列+校准：terran-power **1-4（第六胜）**；zerg-power 0-5（**基线回退实锤**：n5m 旧码 3-2 → 现 0-5）。尸检：greedy 局接触误入过渡（`transition_should_enter` 只查 latch 不看时点/verdict）+转舰队后重进过渡自残。
| O150 | 「o149 尸检：①greedy 局接触误入过渡（500s 波次误判 rush）；②转舰队后可重进过渡；③presumed 对 Zerg Macro 白拍 forge」 | ①`transition_should_enter` 加接触时限（≤360 才许接触进入，verdict=rush 不受限）；②加 `fleet_transitioned` 硬关断（单程化）；③`cancel_presumed_forge`（greedy 且 t≤110 取消在建 forge 退 75%） | o150-zerg-power/zerg-rush（双通道跑局中） | 单测 597 绿（595→597，+2 新测）；烟测 0 错误 | **留**（待 bench） |

o150 复校：zerg-power **1-4（第七胜，macro 局恢复）**；zerg-rush 0-5（avg 396.3）。新靶：macro 局二矿拖到 546 裸开 16s 被拆——扩张门 ~250 就开但钱被塔/叉/科技链吃光；`_expansion_predefense` 挂在 F2 闸内被 `_expand_holding` 按成死代码。
| O151 | 「o150 尸检：①rush latch 压住扩张预留（非急性窗也禁攒钱）；②分矿预防御被 holding 闸死；③macro 局新矿裸奔」 | ①`rush_blocks_reserve`（rush latch 但家无敌=非急性 → 允许攒钱）；②预防御调用点移出 F2 闸+Nexus 未开工不预派；③macro 局新矿=2塔1电池预派+双矿中点接应 | o151-zerg-power/terran-power（双通道跑局中） | 单测 598 绿（597→598，+1 新测）；烟测 0 错误 | **留**（待 bench） |

o151 双系列：**zerg-power 2-3（第八/九胜，差一局过线）**；terran-power 0-5（avg 821.7，航母 570 出厂）。败局分水岭=风暴数（胜局 20-27 vs 败局峰值 3-7）+分矿波次无人接应。
| O152 | 「o151 尸检：①局1 型非零扩张是舰队爬坡慢（SG 峰值 3 vs 胜局 27 艘）；②分矿波次守军死蹲中点；③SG 预留要首舰已出（爬坡与首舰互等）」 | ①`carrier_sg_bonus`（carrier +1，双矿四气 SG 目标 3→4）+SG 预留前提放宽到「FB 在链」+气体闸计在途气矿；②分矿威胁 ≥3 时守军锚点直指分矿（不再死蹲中点）；③（并入①） | o152-zerg-power/terran-power（双通道跑局中） | 单测 599 绿（598→599，+1 新测）；烟测 0 错误 | **留**（待 bench） |

o152 双系列：zerg-power 0-5（o151 的 2-3 回退）、terran-power 1-4（第十胜）。责任分配：O152 三刀均非主凶（①无消费方中性、②轻微、③只作用过渡局而败局全是非过渡局）——大头是骰子方差+「greedy 局 229 小股接触误入过渡烧 170s 舰队链」（O150 时限 360 内的残留陷阱）。
| O153 | 「o152 回退评估」 | 按证只修一刀：`main_defense_first`（主基 25 格敌≥3 时守军不接应分矿）；下轮候选：greedy 判决后小股接触不置 rush_confirmed | o153-zerg-power/terran-power（双通道跑局中） | 单测 600 绿（599→600，+1 新测）；烟测 0 错误 | **留**（待 bench） |

o153 双系列：0-5/0-5。**greedy 接触陷阱实锤**（局1：verdict=greedy → t=237 接触 → 过渡进入冻舰队链；O150 的 360s 时限没拦住）；rush latch 在 greedy 局闪烁掐农民。
| O154 | 「o153 尸检：greedy 局接触误入过渡+rush latch 闪烁」 | ①`transition_should_enter` 加 greedy 一票否决（接触不进过渡，骚扰归 E9 威胁包）；②`rush_contact_arms`（greedy 后接触不置 rush latch）；③E9 兜底验证在跑 | o154-zerg-power/zerg-timing（双通道跑局中） | 单测 602 绿（600→602，+2 新测）；烟测 0 错误 | **留**（待 bench） |

o154 双系列：**zerg-power 1-4 / zerg-timing 1-4**。greedy 接触问题已修好（无过渡误入），但胜率未提升；暴露新主因：**carrier 流整局不出航母**——终局编成 17-28 TEMPEST / 0 CARRIER。根因：O62 配方 TEMPEST p0/CARRIER p1 + save_up=0，freeflow 下便宜且永远可负担的 TEMPEST 把 CARRIER 永久截断。次要问题：idle_builder 五局全中（最多 ×34）、overrun 频繁。
| O155 | 「o154 尸检：①carrier 流不出航母（TEMPEST p0/CARRIER p1 + save_up=0 永久截断）；②idle_builder 严重；③overrun/舰队爬坡慢」 | ①`carrier_quota_active`/`carrier_quota_spawn`：舰队成型且舰队总数 ≥12、航母 <4 艘时，spawn 主次对调成 CARRIER p0/TEMPEST p1，并开动态 save_up=250 憋出航母；②③列入后续候选（先验证①的胜负手效果） | o155-vh-zerg-power（5 局在跑） | 单测 614 绿（602→614，+12 新测）；烟测未出结果（2 次均超时，但游戏正常未崩溃） | **留**（待 bench） |

o155-vh-zerg-power bench 在 game_01  defeat / game_02 败势中 lost（后台任务 bash-1f38qf0m 丢失，进程残留已清）。尸检：舰队峰值 11 艘暴风，**未到 O155 阈值 12，航母配额从未触发**，终局 0 航母；idle_builder 仍刷屏（AutoSupply 被 O11 撤回后每帧重派新工）；中盘 3 矿后基地守不住经济崩盘。
| O156 | 「o155 尸检：①配额阈值 12 太高（VeryHard Power 等不到 12 艘就被推平）；②AutoSupply 撤回无冷却致 idle_builder 刷屏；③中盘经济崩盘待验证」 | ①`carrier_quota_active` 默认 `fleet_min` 12→8，加 fallback（暴风 ≥6 且 0 航母时强制触发）；②AutoSupply 注册前加 `redispatch_cooled_down` 守卫（非人口紧急时 10s 内不重派）；③先靠航母提前成型验证对中盘影响 | o156-vh-zerg-power（5 局在跑） | 单测 615 绿（614→615，+1 新测）；烟测未跑 | **留**（待 bench） |
