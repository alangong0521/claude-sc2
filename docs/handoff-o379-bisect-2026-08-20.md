# 工作交接:carrier 流 VeryHard 攻坚(o379+bisect 判决快照,2026-08-20)

> **本文件取代 `docs/handoff-o378-status-2026-08-20.md`**(后者保留作历史档)。
> 给下一个 AI 接力用的完整状态快照。读这份 + `docs/battle-log.md`(10900 行全量迭代日志)即可开工。
> 先读「## 五、血泪教训」和「## 二、bisect 判决」,不要重复踩坑、不要回滚。

---

## 一、项目与目标

`~/work/claude-sc2` —— SC2 神族 bot(vendored ares-sc2 框架)+ bench 自调优回路。
目标(司令定):**carrier 流打穿 VeryHard 电脑的 Zerg 和 Terran 的 Rush/Timing/Power
三风格,每组合 N=5 标准(5 局 ≥3 胜)**。

本体在 `ares-bot/`:`bot/managers/production_manager.py`(生产/防御/科技钉点,~11k 行)、
`bot/managers/combat_manager.py`(O302 推进/出击闸)、`bot/production_plans.py`(纯函数判据库,
~6.6k 行)、`bench.py`(跑局器)、`tests/`(**856 单测全绿**)。

## 二、当前验证状态(2026-08-20)

### 六组合战绩矩阵(VeryHard @ AbyssalReefLE)

| 组合 | 状态 | 备注 |
|---|---|---|
| Zerg Power | ✓ **打穿 5/6** | o361a+o362b |
| Zerg Rush | ✓ **打穿 3/5**(o368b+o369b);**此后 0/9 但 bisect 判非回退**(见下) | 真实胜率 ~20-40% 高方差 |
| Zerg Timing | **封存 0/30** | 结构性量级差(敌波 520s 到脸时配方需 72 农只有 45) |
| Terran Power | **封存 3/24** | 连续四轮 0/3,死因迁出被修机制,剩余病灶是双 lane 共病 |
| Terran Rush | **首测 0/3** | 见「四、Terran Rush 发现」 |
| Terran Timing | 未开战 | 排期中 |

### bisect 判决(本阶段最重大结论,2026-08-20)

Zerg Rush 在 o376b(2/3)后连续 0/9,两尸检疑代码回退。git worktree 同协议复跑判决:

- **bis376(0faca8e = o376b 胜局态)复跑 0/3**(终局编成 TEMPEST×3)
- **bis378(a5e8f10 = O378 态)复跑 1/3**(终局编成 TEMPEST×11+CARRIER×3+VOIDRAY×4)
- **判决:非代码回退——胜率为方差主导**。o376b 的 2/3 是有利签不是更好的代码;
  O377/O378/O379 的机制修复(腐化硬闸/虚空帽/门修透/在场口径)都是净改进,**一律保留,不回滚**。
- 与历史 bisect(o336 态复跑也 1/6)同结论:峰值和低谷都是噪声摆。
- **方法论纪律:判升降一律两轮累计+滚动窗口;谈回滚必须先 bisect 复跑验证**。

### 胜局配方(有 10+ 局实证)

速二矿(132-250s)→ 70+ 农 5-6 矿 → SG ~250-450s → FB(舰队航标)400-550s
→ 舰队(暴风+航母)15-29 → O302 连续先手压制(每 30s 一推)→ 滚雪球终结。
指标:农峰 ≥67、FB ≤550s、舰队峰值 ≥18、O302 ≥10 次。

### o379 轮新事实(Zerg Rush 0/9 的形态)

- 败因形态从「拖进腐化窗口舰队被全歼」(死于 1175-2239s)切换为「**舰队根本没成型就被
  地面波推平**」(死于 766-1075s);农峰 71→31-45、舰队峰 23-25→1-8、O302 ×10-11→0-1。
- 直接链条:O145 农民停滞 → rush 锁要等「舰队成型」(O204)才解 → 舰队要 FB →
  FB 要 300/200 → 矿被塔/叉吸血 + O364 停气校验环泄漏(气进矿饿)→ 死锁。
- O379 机制本身生效:腐化硬闸零违规(但出击 0-1 次/局,几乎没被压测)、虚空帽咬死(峰 ≤2)。

## 三、Terran Rush 首测发现(o379b,0/3)

- **敌形态:不是早而弱,是晚而重的死亡球**——首个非 SCV 敌军 502-538s 才可见(零骚扰),
  首波 21-37 supply 枪兵+劫掠+坦克架射,此后每 150-200s 一波逐波加重(33→41→74→104);
  坦克/解放者射程白嫖塔,维京专猎舰队,寡妇雷批量屠农。
- **opener 错配 300s**:78.8s 凭「1 座兵营」判 rush 进 Zerg 式锻炉塔+叉应急形态,
  塔立好后空站 300s、叉子对 MM+坦克白给;260s 二次侦查报「兵=0」但 rush 锁没解除。
- **方向已被自己数据验证**:g1 二矿 229s 是唯一攒出 62 农+9 塔的局——
  「利用 500s 无骚扰窗早开二矿」。
- 与 Zerg Rush 差异:Zerg 首波 200-300s 渐进压;Terran 首波晚 200s+、零接触、一波成团。

## 四、方法协议(司令拍板,必须遵守)

1. **双 lane 并行**,每轮 2 lane × 3 局(headless 加速无窗口)。启动前:`pkill -9 -x SC2` +
   代理关(`scutil --proxy`) + Battle.net Agent 在(**单机版不更新 SC2**)。
2. **每局结束立即尸检**,≥3 优化点落地下轮验证(在 CLAUDE.md)。
   工具:`cd ares-bot && poetry run python scripts/autopsy_summary.py bench/<tag>/game_XX`。
3. **判读强制两轮累计+滚动窗口;回滚判决必须先 bisect 复跑**(git worktree,
   记得 `cp ares-sc2/sc2_helper/sc2_helper.cpython-312-darwin.so` + `poetry install --no-root`)。
4. **落地纪律**:纯函数+单测;**实例属性一律 `__init__` 初始化**;import 冒烟
   `poetry run python -c "import sys; sys.path[:0]=['ares-sc2/src/ares','ares-sc2/src','ares-sc2']; import bot.main"`。
5. 每轮 commit+push(develop);push 偶发 SSL 错误,后台重试循环必成。
6. 监视器:`while pgrep -f "bench.py --flow carrier"; do sleep 60; done` 后台 task,不轮询。

## 五、血泪教训(每条都烧过整轮样本)

1. **协议矩阵门死(犯过两次!)**:`_ai_build == "timing"` 把 rush lane 关门外。
   防线:`tests/test_production_plans.py::test_protocol_matrix_reachability`。
2. **阈值改动必须对照胜局配方参数**:O374-④b fleet 8、O376-⑤ floor 6 都是单点数据过矫,
   删掉有胜局实证的参数(fleet=5 首推),各烧一轮。
3. **「修好了」必须有事件级证据**:O377-④ 注释写「在场口径」代码没传参 = 假修复,
   幻影舰队(报 5 实 2)出门捐掉。
4. **实例属性未初始化**:三次 AttributeError 各烧一轮。`__init__` 初始化 + 全目录扫描。
5. **暂停型预留体系(O106 全局资金冻结)已证伪**;可用的是单建筑窄域基金窗
   (FB latch/破产分支,带超时+threat 豁免+健康监控)。
6. **已证伪勿再试**(完整清单在 battle-log 开头):ZT 全程墙链、O283 口袋推广、全量 F2 冻结、
   O310 农民 cap、O312 A 案、O317 forge 先于墙、forge 落位分矿(O344-①)。
7. **自救水晶治不了 placement 几何死槽**(O356 实证):no_placement=不可放置时补电无用,
   走 O357 死槽换锚/O378 水晶环带降级。
8. **单一轮 0/3 或 2/3 都不能作为回归/改进证据**(o376b 态复跑 0/3、O378 态复跑 1/3 实证);
   判升降要两轮累计+bisect。

## 六、后续要做的事(按优先级,给下一棒)

### 立即(下一轮的代码任务,O380)
1. **拆 rush 锁-经济死锁**(两 lane 共病,最高优先):O204 解锁条件从「舰队成型」降级为
   「防御评分达标」(O203 已有口径)或加硬时间盒;农民下限保护(wrk<40 时产农不可被
   任何 hold/yield 拦截)。证据:o379a 农峰 31-45 vs 配方 71。
2. **修 O364 停气泄漏**:停气校验环泄漏复拽反复出现(10s 增速 19-97),停气做成
   **硬切换**(抽干采气农民)而非校验环。这是 FB 资金断链的直接推手。
3. **新矿首塔 fund-first**:Nexus 开工同帧预留 150 矿+钉塔派工(复用 FB latch 攒钱通道);
   首塔瓶颈是等钱(每局 idle_builder 等钱造塔 ×4-13)不是锚点。验收:新矿 90s 内 ≥1 塔。
4. **Terran lane rush 锁降级**:260s 二次侦查「兵=0、无接触」时解除 O92 应急形态,
   二矿提前到 ~200s,早期塔/叉钱转农+SG(利用 500s 无骚扰窗,o379b g1 实证)。
5. **防「永不出击」**:t>900 且舰队<阈且防守评分达标时,给一次豁命推/换家窗
   (o379 后出击 0-1 次/局,推引擎实质沉默)。

### 短期
6. **Terran Rush 继续攻**(opener 适配落地后复跑 3 局);Terran Timing 之后开。
7. Zerg Rush 不专门修——bisect 已判方差主导,共享修复(上述 1-3)落地后顺带复跑确认水位。
8. 双 lane 建议:lane1 Zerg Rush(验证 1-3)、lane2 Terran Rush(验证 4)。

### 中期/判决点
9. Terran Rush 若 opener 适配+共享修复后仍 0/3 两轮,按同款规则封存,转 Terran Timing。
10. 打穿任何组合达 5 局 3 胜后,按司令规则暂停交验收。
11. 可选扩展:Protoss 三风格、Macro/Air 风格(Air=制空硬碰硬最难签)。

### 工程债(不阻塞,顺手修)
- O379-③ 覆盖不全(O365 重试入口绕过判据);跳扇形后锚点仍 no_placement(落点引擎本身有病)
- O324 build runner 步#5 卡死(88s 处 >45s)
- O365「买得起=False」疑似 can_afford bug(矿2170/气443 买不起航母,查 supply_left)
- 塔硬顶在途穿透;o377b g2 扩张闸(478s 后无 NEXUS 钉点手里 535 矿)
- O307 撤开矿抖动

## 七、环境与运维

- bench 一律在 `ares-bot/` 子目录跑;双 lane 用「先 cd 再两个 nohup」写法(每个 `&` 分段丢 cwd)。
- worktree bisect:`git worktree add /tmp/bisect-<sha> <sha>` →
  `cp ares-bot/ares-sc2/sc2_helper/sc2_helper.cpython-312-darwin.so <wt>/ares-bot/ares-sc2/sc2_helper/`
  → `cd <wt>/ares-bot && poetry install --no-root` → import 冒烟。用完 `git worktree remove`。
- 录像:bench 带 `--replay` 存 `bench/<tag>/game_XX/`;解析 `scripts/replay_bases.py`。
- SC2 卡死:`pkill -9 -x SC2`;Battle.net Agent 不在则 `open -a "/Users/Shared/Battle.net/Agent/Agent.app"`。
- git:develop 分支;HEAD ≈ c60343f(o379 记账后,最新以远端为准)。
