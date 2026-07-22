# bot 流派档案（参谋长开局介绍用）

> 本文件是 bot 流派的"作战知识"单一真相源。`.claude/skills/sc2-claude/SKILL.md`
> 的「这局的流派」段落引用本文件 —— 参谋长按 **$BUILD**（`ares-bot/flows.yml` 里的
> 流派名，默认 tempest）读对应段。换/加流派只改本文件和 flows.yml，不用动 skill。
> 机器可读字段见下方 YAML frontmatter。

---
flows:
  tempest:
    race: Protoss
    codename: Aristaeus
    core_units: [TEMPEST, ORACLE]
    playstyle: 直奔暴风舰(Tempest)天空体 + 先知(Oracle)骚扰
  stalker:
    race: Protoss
    codename: BlinkStalker
    core_units: [STALKER, ZEALOT]
    playstyle: 追猎 blink 混狂热者的地面运营流
  carrier:
    race: Protoss
    codename: Skytoss
    core_units: [CARRIER, TEMPEST]
    playstyle: 航母黄金舰队(航母主 C + 暴风舰副 C)
  dt:
    race: Protoss
    codename: ShadowBlade
    core_units: [DARKTEMPLAR]
    playstyle: 黑暗圣堂速出隐身白打农民,对面出反隐就转型
---

## 流派 tempest（暴风舰天空体 + 先知，已实机验证）

**神族 Protoss**：**直奔暴风舰(Tempest)天空体** + 先知(Oracle)骚扰。（注意：**没有光炮起手**——开局就是造农民 + 一路爬星门科技，前期没有任何拖延/骚扰手段，比较脆。）

### 节奏
农民开局 → Gateway→控制核心→星门(Stargate)→舰队航标科技 → **暴风舰滚雪球**（射程极远，地面兵根本够不着）→ 出一个先知顺路骚扰对面农民。中后期靠暴风舰数量碾压。

### 关键特性
- **死穴 = 凤凰(Phoenix)**：能拉扯放风筝慢速的暴风舰。所以侦查到对面**起星门**，
  立刻向司令预警「他要转空军了」。
- **前期是空窗期**：科技没成型前几乎没战斗力，怕对面早期 rush/压制。开局侦查确认对面不 rush 很关键。

### 典型胜利路径（参考实战）
先知骚扰拖经济 → 开二矿追经济 → 暴风舰够量后压二矿、捅主矿、清图。

## 流派 stalker（追猎 blink 流，骨架待跑局验证）

**神族 Protoss**：追猎(Stalker)为主力 + 狂热者(Zealot)混编的地面运营流。

### 节奏
农民开局 → Gateway→控制核心→议会(Twilight Council)研究 blink → 追猎混狂热者持续给压力。
 blink 用来集火点杀 + 残血后撤保命，追猎数量起来后压制清图。

### 关键特性
- **blink 是灵魂**：有 blink 的追猎能打能跑；blink 冷却期是最脆弱的时候，别硬拼。
- **怕 AOE**：坦克轰炸、毒爆、巨像扫射都让追猎海蒸发——侦查到这类科技要预警。
- **对空不虚**：追猎本身对空，不怕对面空军骚（与暴风舰流互补）。

### 典型胜利路径
blink 好了打一波消耗 → 追猎成型持续压 → 混狂热者顶前排，多线点杀滚雪球。

## 流派 carrier（航母黄金舰队，新流派待跑局验证）

**神族 Protoss**：**航母(Carrier)主 C + 暴风舰(Tempest)副 C** 的天空体，科技链与暴风舰流完全相同。

### 节奏
农民开局 → Gateway→控制核心→星门→舰队航标 → **航母滚雪球**（拦截机自动攻击，射程远、
身板硬）→ 暴风舰补超远点杀。成型比暴风舰更慢更贵，但成型后更难解。

### 关键特性
- **空窗期更长**：航母 350 矿 250 气，憋得比暴风舰久——建议早下 `stance=defend` +
  `trigger=when_maxed`，龟到成型再一波。
- **死穴 = 成规模的对空**：维京战机、腐化者、对面风暴舰对射。侦查到对面爆对空要预警。
- **拦截机免费**：航母只要不死就能持续输出，残血航母记得 `stance=retreat` 拉开保船。

### 典型胜利路径
龟缩防守憋航母（先知顺路骚扰拖时间）→ 开二矿补经济 → 航母 4-5 艘成型压上 → 暴风舰点杀威胁目标 → 清图。

## 流派 dt（隐刀 rush，2026-07-21 落地）

**神族 Protoss**：**黑暗圣堂(Dark Templar)速出**，隐身白打对面农民/基地；对面出反隐就转运营。

### 节奏
农民开局 → Gateway→控制核心→暮光议会(Twilight Council)→黑暗圣所(Dark Shrine) →
**攒 4 把隐刀齐出**（分批送死是 DT 头号死法，rally 到数才出门）→ 摸农民、拆基地。
对面反隐成型 → 转开矿运营混编。

### 关键特性
- **隐身即完全体**：DT 没有要微操的技能，白打看不见的敌人；对面没反隐就是屠杀。
- **死穴 = 反隐**：渡鸦(Raven)、侦测器(Observer)、眼虫(Overseer)、导弹塔/孢子爬虫、
  轨道扫描。侦查到这些立刻预警「他有反隐了，别送」。
- ** rush 窗口短**：Dark Shrine 科技链较长，成型越晚对面反隐越齐——速度就是一切。

### 典型胜利路径
探机确认对面开局 → 速 dark shrine → 4 刀齐出摸主矿农民 → 对面慌补反隐时家里开二矿 →
有反隐就转运营混编，没有就杀穿。

## 当前支持的兵种（army_composition）
见 `army_composition.yml`（兵种注册表，战斗侧分派用）；各流派造兵配方见 `flows.yml`。
