"""shield_battery.pick_restore_target 单测 —— Sharky 规则:DPS 降序、盾量升序、跳过已锁定。"""
from bot.shield_battery import pick_restore_target


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
