"""DT(黑暗圣堂)专属 combat class —— 被反隐照到就撤。

调研来源(社区 bot,见 docs/community-tactics-research.md §2.4):
- Sharky DarkTemplarMicroController:未被发现时关闭一切规避(隐身走位是负收益),
  被发现且盾不满才后跳出敌射程;ares 有现成接口 `mediator.get_is_detected(unit)`
  (unit_memory_manager.py:558),我们此前没用 —— DT 被雷达/OB/炮台照到照样站撸,
  隐刀价值归零。
- 我们没研究 Shadow Stride(DT blink),所以撤退走 KeepUnitSafe 网格安全点,
  不做 blink 后跳;未发现时完全复用 GenericOffensive(站撸/压点逻辑不变)。

只影响 DARKTEMPLAR(army_composition.yml 里 combat=dt_offensive),
carrier/tempest 流派不产 DT,零行为变更。
"""
from dataclasses import dataclass

from ares.behaviors.combat import CombatManeuver
from ares.behaviors.combat.individual import AMove, KeepUnitSafe
from sc2.unit import Unit
from sc2.units import Units

from bot.combat.generic_offensive import GenericOffensive


@dataclass
class DtOffensive(GenericOffensive):
    """DT 指挥:未被侦测 → 通用进攻逻辑;被侦测且盾不满 → 撤到网格安全点。

    「盾不满」条件照抄 Sharky:满盾 DT 即使被照到也值得换输出(盾就是拿来扛的),
    盾掉了隐身又没有,继续站撸就是白送。
    """

    def execute(self, units: Units, **kwargs) -> None:
        retreat: list[Unit] = []
        fight: list[Unit] = []
        for unit in units:
            try:
                detected = self.mediator.get_is_detected(unit)
            except Exception:
                detected = False  # 接口拿不到就不当被发现(保持通用逻辑)
            if detected and unit.shield_percentage < 1.0:
                retreat.append(unit)
            else:
                fight.append(unit)

        for unit in retreat:
            maneuver_plan: CombatManeuver = CombatManeuver()
            grid = self._maybe_grid(unit)
            if grid is not None:
                maneuver_plan.add(KeepUnitSafe(unit, grid))
            else:
                maneuver_plan.add(AMove(unit, self.ai.start_location))
            self.ai.register_behavior(maneuver_plan)

        if fight:
            super().execute(Units(fight, self.ai), **kwargs)
