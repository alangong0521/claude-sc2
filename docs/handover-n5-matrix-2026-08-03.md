# 工作交接：VeryHard 全矩阵 N=5 显著性验证 + O83-O89(2026-08-03)

> 给下一个 AI 接力用的完整状态快照。读这份 + `docs/baselines.md`(n5m 小节,O83-O89 迭代日志全录)即可开工。
> 上一份交接:`docs/handover-carrier-vh-matrix.md`(O40-O82,VeryHard 15 组单局全穿)。
> 不要重复踩坑:先读「## 五、血泪教训(新增)」。

---

## 一、今天干了什么

把 VeryHard 15 组对阵从「单局全穿」升级到 **N=5 显著性验证**(70 局新跑,Terran Rush 沿用 n5j@O82 的 0-5)。每局败仗按新建的尸检 skill(`.claude/skills/sc2-defeat-autopsy`)做根因分析,机制 bug 证据链完整才改代码——共落地 **O83-O89 七个修复**,全部纯函数判据 + 单测 + 实局验证闭环。单测 **470 全绿**(457 → 470)。

## 二、最终战绩(全部盘读自 `bench/n5m-*/summary.json`)

**11/15 组过线(≥3 胜),合计 42-33(56%)**:

| 对手 | Rush | Timing | Power | Macro | Air |
|---|---|---|---|---|---|
| Zerg | 0-5 ❌ | 2-3 ❌ | 3-2 ✅ | **5-0** ✅ | **5-0** ✅ |
| Terran | 0-5 ❌(n5j) | 1-4 ❌ | 2-3 ❌ | 4-1 ✅ | 4-1 ✅ |
| Protoss | 3-2 ✅ | **5-0** ✅ | 4-1 ✅ | 3-2 ✅ | 3-2 ✅ |

## 三、O83-O89 修复资产(都已落地+单测)

「舰队饥饿」家族一条龙,全部源自尸检实锤:

- **O83** `fleet_gas_starved`(production_plans.py):气≥600+无FB+有就绪星门 → FB 豁免 rush/threat 冻结(n5m-zerg-rush game_03:3 星门 250s 零产出、气烂 2500)
- **O84** 基地重建模式不再冻结 SpawnController(zerg-power game_02:暴风恒 1 艘 265s;与 O56 同构)
- **O85** FB 豁免不再让 `_expand_holding`(terran-timing game_01:拉锯局 Nexus pending 常驻,豁免名存实亡)
- **O86** 舰队饥饿期停追加产能(先 FB 后星门;拦产能用「已有+在建」口径)
- **O87** 舰队饥饿期威胁不拉满 ec.max 塔目标(12-13 塔吃光 FB 矿照样守不住)
- **O88** `prefer_void_rays`(levers.py):暴风优先点杀最近虚空(治虚空潮;**已落地未及实局验证**)
- **O89** `rush_spawn_fleet_escape`:rush 纯叉配方棘轮逃生门(基建齐+气≥800 → 混编;terran-air game_05:4 SG+FB 气 2344 零舰队 124s+)

⚠️ O88/O89 编号曾撞车(失联期并行回合各起了一个),现以 baselines.md 的 O 系列表为准。

## 四、结构性结论(比战绩更重要)

1. **快攻墙 = 全部 4 个败组**:Zerg Rush/Timing、Terran Rush/Timing(+Power 2-3 准墙)。共同主线:t≈500-550 波次恒早于舰队临界质量(t≈700-900)。**build order 级问题,调参无解**——修复方向 = 上份交接的「过渡形态大改」(叉/追猎开、推迟星门、活到 t=700 再转舰队)。
2. **虚空潮相克(N=5 确认)**:Protoss Macro/Power/Air 五局败局全对应 5-13 艘虚空;舰队成型不是问题(峰值 18-20 暴风),是纯兵种相克。O88 已落地,**待 Protoss 系复跑验证**。
3. **机制债已清**:O83-O89 落地后,末 30 局 24-6,无 N≥2 同指纹机制 bug 遗留。

## 五、血泪教训(新增,逐条对照)

1. **agent 汇报不可作为数据源**:本次中途发生过一次凭记忆汇报导致的假 15 组汇总(虚构了 8 组未跑对阵的战绩),全量对盘才发现更正。**一切战绩以 `bench/<tag>/summary.json` 盘读为准**,baselines.md 已留数据纪律备注。
2. **后台任务会「lost」但进程不死**:会话重启后 task 句柄丢失(lost 通知),bench 进程仍在跑。**巡检一律读 bench 目录,别依赖任务通知**;cron 任务在会话恢复后可能把已删除的旧任务带回来,删完用 CronList 复核。
3. **并行/失联回合会撞 O 编号**:本次 O86、O88 各撞一次。动手前 `grep -n "O8[0-9]" bot/ docs/baselines.md` 确认最新编号。
4. **bench 每局起新进程 = 系列中途改代码会混入后续局**。这不是污染是特性:修复的实局验证直接搭车,但汇报战绩时要标注代码版本分界。
5. **「舰队饥饿」是一个家族,不是一个 bug**:冻结门(O83)→holding 守卫(O85)→追加产能(O86)→塔目标(O87)→纯叉棘轮(O89),每层修完下一层才暴露。只修一层会说「怎么还不行」。
6. ** fingerprint ②(FB 过门但买不起)最终不立项**:N=4 复现,但矿全流向生存开销(重建/保塔/保底叉),砍生存开销风险大于收益。区分「钱去了哪」比「钱不够」重要。

## 六、待办(按推荐排序)

1. **O88 实局验证**:Protoss 系三组(Macro/Power/Air)各跑 N=3-5,看虚空优先点杀能否翻转虚空潮局。命令同下,tag 建议 `o88-vh-protoss-*`。
2. **【待用户决策】快攻四墙记豁免**:Zerg/Terran Rush 数据已齐(0-5/0-5),Zerg Timing 2-3、Terran Timing 1-4、Terran Power 2-3 同族。要攻就是过渡形态大改(build order 级,非调参)。
3. **险胜组 N=10 坐实**:Protoss Macro/Air、Zerg Power(3-2 组),项目门槛 N=10 ≥7。
4. **CheatVision 升档**:15 组 N=5 底盘已清,具备升档条件;注意 Rush 类在更高难度只会更凶。
5. **待复现指纹**:O55 电力停滞 fired 但 stall 持续 >100s(zerg-timing game_04、protoss-rush game_04,均 N=1-2,暂不够立项)。

## 七、跑局操作约定(沿用+新增)

- bench 命令、杀局卫生、双通道、代理坑、单测命令:同上份交接,全部仍然有效。
- **新增**:巡检自动化可用 cron(每 13 分钟读 bench 目录汇报),跑完务必删除并 CronList 复核(教训#2)。
- **新增**:尸检流程已沉淀为 skill(`.claude/skills/sc2-defeat-autopsy/SKILL.md`):五步尸检法 + 败因签名库(O83-O89 指纹全录,含鉴别方法)。败局分析直接按它来,新指纹记得回填。

## 八、关键文件索引

- `docs/baselines.md` —— n5m 小节:O83-O89 每轮的假设/改动/实证/结论 + 15 组战绩表
- `.claude/skills/sc2-defeat-autopsy/SKILL.md` —— 尸检 skill(五步法+签名库)
- `ares-bot/bot/production_plans.py` —— O83/O86/O87/O89 纯判据(`fleet_gas_starved` 等)
- `ares-bot/bot/levers.py:90` —— O88 `prefer_void_rays`
- `ares-bot/bot/managers/production_manager.py` —— O83-O89 全部接入点(352/424/724/744/764/1342 附近)
- `ares-bot/bench/n5m-*/` —— 70 局快照全集(`game_*/state_*.json` 可复盘)

## 九、环境状态(交接时)

- 无 SC2/bench 残留进程,无遗留 cron
- 单测 470 全绿(含 1 skip)
- `docs/baselines.md` 已同步到 O89 + 15 组 N=5 全表
