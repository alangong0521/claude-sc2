# 社区 bot 战术调研与合并记录(2026-07-23)

调研范围:ares-sc2 框架(vendor v3.9.6 = 上游最新)、Sharky(sharkbot,C#)、
sharpy-sc2(SharpenedEdge 框架)、h3nnn4n Tapioca(blink 追猎 all-in)、
QueenBot(AresSC2 官方)、12PoolBot(phantomsc2,含 leitwerk 自调参库)。

**澄清**:`BruceBot` 查无此神族 bot(同名只有人族大河 bot prevosta/BruceBot);
"blink 追猎出名"的印象对应 sharkbot / SharpenedEdge / Tapioca。
`Aristaeus (P)` 在 ares 官方 bot 列表里但源码 404(私有仓),机制与 ares 框架同源,不构成信息缺口。
`MicroMachine` 是人族 bot,不是神族。

---

## 已合并(2026-07-23,commit 见 git log)

### 1. 护盾电池主动充能 —— `bot/shield_battery.py`(新增)+ `bot/main.py` 每帧调用
来源:[Sharky ShieldBatteryManager.cs](https://github.com/sharknice/Sharky/blob/master/Sharky/Managers/Protoss/ShieldBatteryManager.cs)
- 此前 `ProtossStaticDefence` 只建电池;**SC2 电池充能不是自动施法,没人点就是废铁**。
- 规则:半径 7.125(6+1.125);目标盾 < 上限-5;按 DPS 降序、盾量升序选;
  防重复充能(跳过电池 Orders 已锁定目标);能量 <20 不充;电池在奶不打扰(防抖)。
- 纯增量:无电池/无残盾单位零指令,全流派防守受益。单测 `tests/test_shield_battery.py`。

### 2. DT 被反隐照到就撤 —— `bot/combat/dt_offensive.py`(新增,combat=dt_offensive)
来源:[Sharky DarkTemplarMicroController.cs](https://github.com/sharknice/Sharky/blob/master/Sharky/MicroControllers/Protoss/DarkTemplarMicroController.cs)
- `mediator.get_is_detected(unit)`(unit_memory_manager.py:558,此前没用):
  被侦测且盾不满 → `KeepUnitSafe` 撤到网格安全点;未被发现 → 关闭规避(隐身走位是负收益),
  完全复用 GenericOffensive。没研究 Shadow Stride,不做 blink 后跳。
- 只影响 DARKTEMPLAR,carrier/tempest 零变更。

### 3. 断电自动补水晶 —— `bot/main.py` 注册 `RestorePower()`(带 can_afford 守卫)
来源:ares 自带 `behaviors/macro/restore_power.py`(此前只 Terran 路径经 ProductionController 间接用)。
- 供电水晶被拆 → 产兵建筑断电 → 产能永久停摆的黑洞,现在自动补。
- 守卫防 O11 钉点(RestorePower 自身无 can_afford 检查,与 ProtossStaticDefence 同类风险)。

---

## Backlog —— **已于 2026-07-24 全部落地**(B1-B9 司令指令提前合并;B10 为放弃项不落地)。
下面保留原始方案备查;实现细节见各文件注释与 commit 记录。
B8 selftune 已接 main.py ask/tell(记录先行,参数消费点未接,见 docs/selftune.md §4)。
BruceBot 衍生项见 docs/bc-flow-plan.md。

### B1. Stalker blink 三改(来源:Sharky StalkerMicroController + sharpy micro_stalkers + h3nnn4n)
目标文件:`bot/combat/stalker_offensive.py`
- 后跳盾阈值 25% → 10~15%(社区两家 12.5%/5%;blink 是 10s CD 稀缺资源,盾厚时用走位风筝);
- 新增「被超射程单位瞄准直接后跳」(Sharky AvoidTargetedDamage:坦克/地刺锁定不看盾量);
- blink 前查 `FUNGALGROWTH` buff(真菌锁 blink,点了浪费);
- 后跳落点校验:落点 influence 必须低于当前位置(sharpy find_weak_influence_ground_blink);
- Cyclone LOCKON 特判:立刻 blink 出 15+ 格。
- h3nnn4n 实测:blink 追猎微操对 Zerg 收益最大(蟑螂射程 4<6 且重甲加成),对 Terran 最差(坦克阵) → 对 T 应考虑转型而非硬撸。

### B2. 集火静态优先级表(来源:sharpy micro_stalkers high_priority 字典)
- 架起坦克 10/感染 10/HT 10/巨像 10/地刺 9/隐刀 9/不朽 9;**电池/炮塔只有 1(不浪费输出打建筑)**;
- 与 `levers.pick_focus_key` 的 weakest 加权合成,离线可单测(lever 层惯例)。

### B3. can_win_fight 接战刹车(来源:ares CombatSimManager + QueenBot combat_queens + 12PoolBot micro.py)
- `mediator.can_win_fight(own, enemy)` 返回 LOSS_* 时全军撤而非压上;只当"一票否决",不当进攻触发器
  (官方警告:模拟器不含微操/施法,农民要过滤);
- 治 bench 信号 `trickle`(兵力反复崩落 = 逐个上去送)和 `overrun`;
- 12PoolBot 加分项:APM 预算分频指令(`iteration % interval == tag % interval`),大兵团不卡帧。

### B4. 防守三角补齐(来源:sharpy PlanHeatDefender + Sharky DefenseSquadTask)
- 防守集结点 = 主坡口顶端下 4 格(而非基地中心),改 `_front_point`/defend 目标点;
- 防御性折跃:被 rush 时把 spawn_target 切到被攻击的基地(参数化现成,一行);
- rush 应激清单(QueenBot 全套):停气、扩张 max_pending=0、取消在建建筑换现金 —— pivot 目前只转防,经济侧联动待补。

### B5. DT 骚扰升级(来源:Sharky DarkTemplarHarassTask + sharpy dt_attack)
- DT 独立 role(不混 ATTACKING 大部队),目标=矿线农民(MineralLineLocation)而非基地中心;
- 三条换矿规则:矿点无敌 → 换;有反隐且战力劣势且盾不满 → 换;找不到绕反隐路径 → 换(最实用);
- sharpy 编配:1 只纯杀农民 + 1 只 A 主力;DT rush 链同时升 blink+冲锋。

### B6. Squad 化群体指挥(来源:ares group behaviors + SquadManager 教程,收益最大工作量最大)
- `mediator.get_squads(role=ATTACKING, squad_radius=9.0)` + `AMoveGroup`/`StutterGroupBack/Forward`;
- 治"行军散队、局部少打多";GenericOffensive 改成按 squad 指挥,tempest 个体风筝不动。

### B7. 运营侧(来源:QueenBot/12PoolBot,多数框架现成)
- MacroPlan 优先级队列:AutoSupply 第一(治 supply_block)→ 造兵 → 产能 → 升级 → 扩张;
- ProductionController `add_production_at_bank=(400,400)` 存款超阈值自动补兵营(治 bank,Protoss 专用);
- 扩张动态 max_pending:rush 时 0、矿>1250 时 3~4(治 one_base),check_location_is_safe 过滤危险矿点;
- 收入/花费守恒式:目标产能花费速率 ≈ 0.83×收入速率(bank 和 stall 是同一不等式两端)。

### B8. 自调参(来源:12PoolBot leitwerk + ares DataManager)
- leitwerk:dataclass 声明连续参数,`ask(context={enemy_race})` 按族采样,`tell((胜负, 交换比))`
  局间进化 —— 就是 bot-self-tuning-plan.md "optimize"阶段的现成轮子;
- ares DataManager `UseData: True`:按 opponent_id 记历史,赢了沿用开局输了轮换(需 protoss_builds.yml 多开局);
- 与 promotion.py 关系:promotion 是档位资格考试(离线),leitwerk/DataManager 是运行时在线调参,互补不冲突。

### B9. Warp Prism(来源:Sharky WarpPrismMicroController + sharpy micro_warp_prism,F1 完整方案)
- 相位折跃:满盾+附近无敌+有门快转好才变相位(复用 _front_point);
- 接残血:sharpy 打分式 `score = 射程×(1.1−血量%)×战力−1`,只接盾空+武器冷却中;
  zealot 规则:盾在/有敌在射程不接(契合我们 zealot 抗线、prism 只救追猎的混编);
- 建议在 B1~B5 稳定后做。

### B10. 已知但放弃
- 整体替换 ProductionController(会丢 E2 gas 闸门等自写调参);
- PlacePredictiveAoE(ares 源码自标 WIP);
- SpeedMining/mineral_boost(O7 人机共驾主动关闭,保持关闭);
- 护盾电池 Overcharge 无视能量充能(框架无支持,自写成本高)。

---

## 关键来源索引
- ares-sc2(vendor 一致 v3.9.6): https://github.com/AresSC2/ares-sc2
- Sharky(sharkbot): https://github.com/sharknice/Sharky (MicroControllers/Protoss/, Managers/Protoss/)
- sharpy-sc2: https://github.com/DrInfy/sharpy-sc2 (sharpy/combat/protoss/, dummies/protoss/)
- h3nnn4n stalker micro: https://h3nnn4n.me/post/sc2-stalker-micro/
- QueenBot: https://github.com/AresSC2/QueenBot (macro_manager/worker_defence_manager/queen_role_controller)
- 12PoolBot: https://github.com/phantomsc2/12PoolBot (strategy.py/micro.py)
- leitwerk: https://github.com/phantomsc2/leitwerk
- ProBots 2023 S1 名单: https://liquipedia.net/starcraft2/ESChamp_ProBots/2023/1
