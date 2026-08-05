---
name: sc2-defeat-autopsy
description: SC2 bot bench 跑局后的败局尸检与根因分析——从 run.log / state_*.json 快照重建时间线,按「败因签名库」归类根因,区分机制bug/策略相克/单局方差,给出最小修复方向。触发场景:bench 跑局出现败局、用户说「分析败因」「尸检这局」「为什么输了」「迭代优化」,或 N=5 系列巡检查到新败局时。
---

# 败局尸检 —— 从日志到根因到最小修复

目标:把每局败仗变成一条可归类的根因(机制 bug / 策略相克 / 方差),而不是凭感觉调参。
铁律(血泪教训,违反=白干):

1. **单局胜利是方差,N≥5 才配叫结论**;单局败局只能提供「假设」,不能提供「结论」。
2. **数据优先于理论**:O72-O81 五轮「合理修复」把 N=5 从 2-3 打到 0-5。每个局部都对的改动组合起来可以是负资产。
3. **修复只落在证据链完整的机制 bug 上**;「看起来能优化」一律不动。
4. 改动 = 纯函数判据(`bot/production_plans.py`)+ 单测 + 全套单测绿 + bench 实局验证,四件缺一不可。

---

## 一、数据在哪(ares-bot/ 下)

```
bench/<tag>/game_XX/run.log        # 全文日志;结果行: Result for player 1 - CodeAgentSC2: Victory/Defeat
bench/<tag>/game_XX/state_*.json   # 每 ~4 游戏秒一个快照,文件名=游戏秒(如 state_000831.7.json)
bench/<tag>/summary.json           # bench 汇总(tail 输出)
```

state 快照字段:`time / minerals / vespene / supply / workers / bases / army / structures / upgrades / enemies[] / events[] / order`。
`events[]` 是带时间戳的事件流(丢矿/农民骤减/E6抄家/E9威胁/F2诊断/idle_builder…),**尸检先扫它**。

## 二、五步尸检法(按序做,别跳步)

**第 1 步 · 定性**:胜负 + 死亡时刻(最后一个快照的游戏秒)+ 终局敌我兵力。
速败(<300s)看中早期链;长局(>900s)看决战与舰队曲线。

**第 2 步 · 时间线重建**:抽 workers / bases / army / structures / minerals / vespene 曲线
(每 100 游戏秒一行足够)。用这段现成脚本(改 GAME 路径):

```bash
python3 - <<'EOF'
import json, glob
GAME = 'ares-bot/bench/<tag>/game_XX'
files = sorted(glob.glob(f'{GAME}/state_*.json'), key=lambda p: float(p.split('state_')[1][:-5]))
for f in files:
    t = float(f.split('state_')[1][:-5])
    if int(t) % 100 > 30: continue
    s = json.load(open(f))
    print(int(t), 'bases:', s.get('bases'), 'workers:', s.get('workers'),
          'min:', s.get('minerals'), 'gas:', s.get('vespene'),
          'army:', s.get('army'), 'structures:', s.get('structures'))
EOF
```

**第 3 步 · 事件链**:合并所有快照的 events 去重按时间排(脚本同上,遍历 `events[]` 用 `(t,msg)` 去重)。
重点事件:`E7:侦查未送达` `E9:敌压境威胁响应` `E6:基地被抄` `丢失基地` `农民骤减`
`idle_builder:...干等(等钱造X)` `F2:注册防御` / `F2:每基地(塔,晶)` `O71:二次侦查结论`。

**第 4 步 · 对签名**(见下「败因签名库」):先查最常见的死锁类(有东西该建没建/该出没出),
再查节奏类(成型晚于波次),最后才考虑操作类。

**第 5 步 · 定级**:
- **机制 bug**:有明确「该发生没发生」的指纹(建筑缺失/产能闲置/静默失败)→ 值得修,写假设→最小修复。
- **策略相克**:机制都对,数值/节奏物理上打不过(如舰队临界质量恒晚于波次)→ 记豁免候选或换 build,不调参。
- **方差**:机制都对、节奏也对,胜负手是随机性(侦查成败/波次构成)→ 不动,累计样本。

## 三、败因签名库(全部来自实局尸检,按危害排序)

### A. 死锁类(该建的没建,最值钱)

| 签名指纹 | 根因 | 出处 |
|---|---|---|
| 星门就绪但 200s+ 零空军产出 + 气银行 ≥600 且持续上涨 + 无 FLEETBEACON | rush/threat 冻结门把舰队航标永久饿死(慢性威胁下 O67 急性窗让位变死锁)→ O83 fleet_gas_starved 豁免 | n5m-zerg-rush game_03 |
| 星门/FB 就绪 + 矿气双饱(矿≥1000 气≥2500) + 人口空闲 + 基地在拉锯(丢失/重建循环) + 出兵恒零增长 | 重建基地模式(_base_rebuild)冻结 SpawnController,拉锯局=永久停产 → O84 已修(重建不冻出兵,Nexus 钱由 _expand_holding 门保护)。注意与 supply 卡人口区分:先打 supply 曲线,53/53 是卡人口,73/106 空闲还停产才是本签名 | n5m-zerg-power game_02 |
| rush 确认后星门+FB 就绪、气 ≥800 持续上涨,但舰队零增长,只有叉子在产在死 | E3d 纯叉配方棘轮:叉子即出即死永远填不满 rush_zealots cap → 纯叉永久生效饿死星门 → O89 已修(基建齐+气≥800 开混编逃生门;急性 rush 早期基建未齐不受影响) | n5m-terran-air game_05 |
| O83 已豁免但 FB 仍 100s+ 不落地:气 ≥600、有就绪星门 | 三个变种按序排查:① Nexus pending/重建常驻 → _expand_holding 把豁免跳过(O85 已修:豁免不让 holding);② 矿被 3-4 座追加星门吃光(SG≥3 先于 FB = 产能 > 科技的死钱)→ O86 已修(舰队饥饿期停追加产能);③ 矿恒 <300 且无追加产能 → 威胁期塔目标=ec.max 吃矿(12-13 塔照样守不住,FB 才是翻盘点)→ O87 已修(舰队饥饿期威胁不拉满,走动态式);④ O55 电力停滞事件 fired 但 stall 持续(落位仍静默 None) | n5m-terran-timing game_01; n5m-terran-power game_02; n5m-zerg-timing game_02/04; n5m-protoss-rush game_02 |
| O55「科技X停滞>20s,补供电水晶」事件 fired 但同一建筑 stall 持续 >100s | 电力自救失效:补的水晶在 start_location,但落位搜索可能仍全 None(O38 锚点把水晶锚去坡口/矿区,科技点无电)。单局孤证,待复现 | n5m-zerg-timing game_04 |
| F2:每基地(塔,晶) 分矿晶=0,塔恒 0,无报错 | **无电**:Protoss 建筑不在电网内时落位**静默返回 None**。查建造问题先查电 | O76-O79 悬案 |
| idle_builder 干等(等钱造X) 反复出现 + 同类建筑已多座 | BuildStructure 的 max_on_route 是**全图共享计数**,多基地并发互饿,主基恒先占满 | O81 |
| 分矿塔建不起、主基塔正常 | ProtossStaticDefence 的 static_defence=True 槽位检索在分矿静默失败,用裸 BuildStructure(static_defence=False) | O78b/c |
| warpgate 研究完成后地面兵永久停产 | ares SpawnController 等变形但全框架没人下 MORPH_WARPGATE | B2 baseline |

### B. 节奏类(成型晚于波次)

| 签名指纹 | 根因 | 出处 |
|---|---|---|
| 接触时(t=550-800)舰队 2-6 艘,胜局需要 8-12 艘 | 舰队临界质量恒晚于敌二三波(~150s 一波递增)= 数值相克,非 bug | N=5 三轮 Terran Rush |
| rush_active/threat 长期挂起 + 农民数冻结 + 银行烂 3000+ | 「延长 rush 态」是负资产:防御收益一次性,运营成本复利 | O72/O75 实证 |
| 分矿在 rush 预警窗(~160s)内要守 | < 2晶+4塔建造所需 ~200s,物理上限,正确姿势=主基塔阵+农民早撤 | O76-O80a |

### C. 经济/资源类

| 签名指纹 | 根因 | 出处 |
|---|---|---|
| min<200 且 gas>2000 长期 | 气矿先满但矿被建筑/出兵抢光(或反之),矿气失衡;星门数要盯矿气平衡 | Terran Air 局 6 星门断矿 |
| 满人口 199/200 + 存款 5000+ 还在蹲 | 蹲是纯亏,换血永远我方赚,应全攻(O70 已修,复发即回归) | O70 |
| supply 长期满(如 60/60) | 水晶断供,pylon 链断 | 常见 |

### D. 操作/战斗类(最后才考虑,最难归因)

- 暴风(射程10)压维京(9)/腐化(6),但**虚空棱镜对齐烧装甲暴风极快**——虚空潮的答案是塔阵消耗,不是暴风对拼(O68)。
- 满人口推不出去:暴风追过路敌不拆建筑(O65/68 行军模式+攻城纪律已修,复发即回归)。
- 决战舰队半灭后败:先看是不是推进闸放行条件太松(supply 优势/对空安全线),再看对面克制兵种构成。

## 四、输出格式(给用户汇报)

```
【尸检】<tag>/game_XX:Defeat @ t=<死亡秒>
死因:<一句话>
证据链:<曲线/事件 2-4 条>
归类:机制bug | 策略相克 | 方差
处置:<修复方向(写清改哪个文件哪个判据) | 记豁免 | 不动,累计样本 N=x/y>
```

## 五、修复工作流(只有归类=机制bug 才走)

1. 写假设:「改 X 判据,Y 指纹应消失」。
2. 判据写成 `bot/production_plans.py` 纯函数 + `tests/test_production_plans.py` 单测。
3. `poetry run python -m unittest discover -s tests | grep -E "^(OK|FAILED|Ran)"` 全绿。
4. 实局验证:同对阵再跑 N≥5(或搭进正在跑的系列),指纹消失且胜率不跌才算过。
5. 结果记 `docs/baselines.md` O 系列日志(假设/改动/实证/结论四段)。
