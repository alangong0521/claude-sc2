"""shield_battery.pick_restore_target 单测 —— Sharky 规则:DPS 降序、盾量升序、跳过已锁定。"""
from bot.shield_battery import (
    overcharge_struct_allowed,
    overcharge_unit_allowed,
    pick_overcharge_target,
    pick_restore_target,
    should_overcharge,
)


class _U:
    def __init__(self, tag, dps_ground=0, dps_air=0, shield=50):
        self.tag = tag
        self.ground_dps = dps_ground
        self.air_dps = dps_air
        self.shield = shield


def test_prefers_higher_dps():
    stalker = _U(1, dps_ground=13, shield=80)
    probe = _U(2, dps_ground=5, shield=10)
    assert pick_restore_target([probe, stalker], set()) is stalker


def test_air_dps_counts():
    phoenix = _U(1, dps_ground=0, dps_air=15)
    zealot = _U(2, dps_ground=8)
    assert pick_restore_target([zealot, phoenix], set()) is phoenix


def test_same_dps_prefers_lower_shield():
    a = _U(1, dps_ground=13, shield=60)
    b = _U(2, dps_ground=13, shield=20)
    assert pick_restore_target([a, b], set()) is b


def test_skips_busy_tags():
    busy_one = _U(1, dps_ground=13)
    other = _U(2, dps_ground=8)
    assert pick_restore_target([busy_one, other], {1}) is other


def test_empty_returns_none():
    assert pick_restore_target([], set()) is None


def test_overcharge_gate():
    # O120-②:敌地面压到电池旁 + 能量 ≥50 → 超载;否则不烧(能量留着奶)
    assert should_overcharge(2, 45.0)
    assert should_overcharge(6, 80.0)
    assert not should_overcharge(2, 44.0)  # O121:能量门 50→45
    assert not should_overcharge(1, 80.0)


def test_overcharge_target_prefers_structures():
    # O122-③:超载塔优先(DPS 续航最值),无残盾塔才给盾%最低单位
    tower = _U(1, shield=20)   # shield_max 默认 50 → 40%
    tower.shield_max = 100
    tower2 = _U(2, shield=10)
    tower2.shield_max = 100
    zealot = _U(3, shield=5)
    zealot.shield_max = 50
    assert pick_overcharge_target([tower, tower2], [zealot]) is tower2
    assert pick_overcharge_target([], [zealot]) is zealot
    assert pick_overcharge_target([], []) is None


def test_overcharge_struct_whitelist():
    # O123-②:超载只挂塔/主基地 —— PYLON 白烧(o122 局3 实证)不再发生
    assert overcharge_struct_allowed("PHOTONCANNON")
    assert overcharge_struct_allowed("NEXUS")
    assert not overcharge_struct_allowed("PYLON")
    assert not overcharge_struct_allowed("GATEWAY")


def test_overcharge_unit_blacklist():
    # O293-③:超载不挂农民(o291a game_01 超载→PROBE 白烧实证),作战单位照挂
    assert not overcharge_unit_allowed("PROBE")
    assert overcharge_unit_allowed("ZEALOT")
    assert overcharge_unit_allowed("STALKER")
    assert overcharge_unit_allowed("CARRIER")
