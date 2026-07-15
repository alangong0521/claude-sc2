# 当前 bot 流派档案（参谋长开局介绍用）

> 本文件是 bot 当前 build 的"作战知识"单一真相源。`.claude/skills/canmou/SKILL.md`
> 的「这局的流派」段落从本文件生成/引用 —— 换 build 只改这里,不用动 skill。
> 机器可读字段见下方 YAML frontmatter(steer_cli / 校验工具可读)。

---
build_id: TempestRush
race: Protoss
codename: Aristaeus
core_units: [TEMPEST, ORACLE]
playstyle: 直奔暴风舰(Tempest)天空体 + 先知(Oracle)骚扰
---

## 一句话
**神族 Protoss**：**直奔暴风舰(Tempest)天空体** + 先知(Oracle)骚扰。

## 节奏
农民开局 → Gateway→控制核心→星门(Stargate)→舰队航标科技 → **暴风舰滚雪球**
（射程极远，地面兵根本够不着）→ 出一个先知顺路骚扰对面农民。中后期靠暴风舰数量碾压。

## 关键特性
- **没有光炮起手**：开局就是造农民 + 一路爬星门科技，前期没有任何拖延/骚扰手段，比较脆。
- **死穴 = 凤凰(Phoenix)**：能拉扯放风筝慢速的暴风舰。所以侦查到对面**起星门**，
  立刻向司令预警「他要转空军了」。
- **前期是空窗期**：科技没成型前几乎没战斗力，怕对面早期 rush/压制。开局侦查确认
  对面不 rush 很关键。

## 典型胜利路径（参考实战）
先知骚扰拖经济 → 开二矿追经济 → 暴风舰够量后压二矿、捅主矿、清图。

## 当前支持的兵种（army_composition）
见 `army_composition.yml`。默认主力 = 暴风舰；可配置多兵种混编。