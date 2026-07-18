# 流派方案 · 提速叉白球（Chargelot Archon / Storm）

> 优先级 A 级 · 预计改动量：中大（要新写「合球」行为）
> 社区出处：TL.net "chargelot archon" 后期标准地面组合；
> SpawningTool "Creature - 2 oracle 8 gate archon charge attack"。

## 流派定位

神族后期地面标准答案：冲锋狂热者贴脸 + 高阶圣堂闪电aoe + 多余高模两两合成执政官（白球）
当肉盾。对生化、对地面海都有压制力，是给 bot 的**第二条地面路线**（比巨像便宜、成型快）。

- 节奏：农民开局 → gateway 海 → cyber → twilight（研究冲锋 CHARGE）→
  圣堂档案馆（TEMPLARARCHIVE）→ 高模放完闪电合白球，叉子海平推。
- 死穴：空军（全家对空靠电弧……白球对空射程短，本质还是怕空军，需要追猎/凤凰补）、
  EMP（幽灵一炮清空高模能量和白球护盾）、劫掠者风筝叉子。
- 观赏点：闪电落点 + 合球时机，是参谋长解说素材最多的一条流派。

## 前置依赖

- P0（流派配置化）。
- **新行为「合球」**（本方案的大头，见改动 3）。
- `templar_caster` 骨架（放灵能风暴）已在仓库，未跑局验证——本流派顺带验证它。

## 改动清单

1. **spawn 配方**（示意）：`ZEALOT 0.6 priority 0` + `HIGHTEMPLAR 0.4 priority 1`。
   高模攒能量期间叉子先顶。
2. **科技链**（flow 块 `core_structures`）：
   `GATEWAY → CYBERNETICSCORE → TWILIGHTCOUNCIL → TEMPLARARCHIVE`。
   多兵营（gateway 海）走 `_build_extra_stargates` 同款的「矿富余追加」逻辑
   （泛化成追加 gateway，P0 时可配）。
3. **新行为：合球（merge archon）**
   - 引擎里合球 = 选中 2 个高模放 merge 技能（`AbilityId` 枚举运行时核对，照仓库惯例
     getattr 兜底）；ares **没有现成原语**，要自写一个 behavior/manager 逻辑：
     能量低于阈值（如 <50，放不出闪电了）的高模两两配对 → 放 merge → 产物 ARCHON
     归 ATTACKING role（`on_unit_created` 已会给非农民单位指派）。
   - 建议落点：`bot/behaviors/merge_archon.py` + 在 CombatManager 或独立小 manager 里每帧检查。
   - ARCHON 的指挥走 `combat: default`（yml 已登记）。
4. **combat class**：ZEALOT 用 `default`（冲锋是被动技能，a-move 即可）；
   HIGHTEMPLAR 用 `templar_caster`（骨架，跑局调风暴落点/能量阈值）。
5. **升级**：`CHARGE`（twilight 研究，流派灵魂）+ `PROTOSSGROUNDWEAPONSLEVEL1/2` +
   `PROTOSSGROUNDARMORSLEVEL1`。写进 flow 块 `upgrades:`，CHARGE 排首位。
6. **build_meta.md**：新增 `ChargelotArchon` 档案段（死穴 EMP 要写清——发现对面
   幽灵军校/幽灵就预警「高模别扎堆」）。

## 验证

- 无头：对 Hard Terran 生化（AIBuild=Macro/Rush）几局看胜率。
- 实机：看四点——① CHARGE 是否及时研究；② 高模闪电放不放得出来、落点如何；
  ③ 空能高模有没有被两两合球（不是满 energy 也合）；④ 白球是否归队参战。
- 顺手验：`templar_caster` 的 ability id 兜底是否真的对得上（对不上就静默不放——
  这次必须确认技能放出来了）。

## 风险与调优点

- 合球是全新行为，配对/施法/打断的边界情况不少（配对中途一个死了、被打断能量返还等），
  实现时先写最朴素版本（两两在同帧直接放技能），跑局再补健壮性。
- 叉子海怕 aoe（坦克/巨像/毒爆），对这类 AI 局胜率预期放低，档案里写明。
- 对空短板——档案「死穴」里写明，参谋长应建议混编或转型。

## 跑局调优记录

（实施时填）
