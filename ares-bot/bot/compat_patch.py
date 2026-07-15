"""兼容补丁：让老 burnysc2 的 id 枚举容忍"未知 id"。

背景：本机 SC2 客户端比 pinned 的 burnysc2 数据表新，某些地图（尤其 4 人图
CactusValleyLE）里含有老枚举不认识的单位类型（如 id 2009 =
XelNagaTowerRangeIndicatorDummy）。解析地图时 `UnitTypeId(2009)` 抛 ValueError，
导致 bot 在 initialize_first_step 直接投降（"Resigning due to previous error"）。

修法：给相关 id 枚举装 `_missing_`——遇到未知 id 回落到该枚举的 0 值
（UnitTypeId.NOTAUNIT 等）而不是抛异常。只影响"库按整数值解析未知 id"这条路径；
我们代码里都是按名字访问（UnitID.TEMPEST），不受影响，也不会掩盖自己的笔误。

用法：run.py 里 `import bot.compat_patch` 一次即可（导入即打补丁）。
"""
import importlib

from loguru import logger

# (模块, 枚举类名)——都是 burnysc2 生成的 id 枚举，新版客户端最可能出现未知值的几个
_TARGETS = [
    ("sc2.ids.unit_typeid", "UnitTypeId"),
    ("sc2.ids.ability_id", "AbilityId"),
    ("sc2.ids.upgrade_id", "UpgradeId"),
    ("sc2.ids.buff_id", "BuffId"),
    ("sc2.ids.effect_id", "EffectId"),
]


def _patch_id_enums() -> list[str]:
    """给各 id 枚举装上"未知 id 回落到 0 值"的 _missing_（治 UnitTypeId(2009) 之类 ValueError）。"""
    patched: list[str] = []
    for module_name, cls_name in _TARGETS:
        try:
            enum_cls = getattr(importlib.import_module(module_name), cls_name)
        except (ImportError, AttributeError):
            continue
        zero_member = enum_cls._value2member_map_.get(0)
        if zero_member is None:
            continue  # 没有 0 值成员就不动它（避免猜错回落目标）
        # 默认参数 _z 绑定当前枚举的 0 值成员，避免闭包晚绑定
        enum_cls._missing_ = classmethod(lambda cls, value, _z=zero_member: _z)
        patched.append(cls_name)
    return patched


def _patch_unit_orders() -> bool:
    """治 unit.orders 里 `game_data.abilities[ability_id]` 的 KeyError（治 4135 之类）。

    game_data 建技能字典时会丢弃"不在 AbilityId 枚举里"的技能 id；新版客户端的单位
    指令若用到这种未知技能 id，解析 orders 时就 KeyError 崩。这里让 orders 跳过
    burnysc2 不认识的技能——那条指令对框架逻辑不可见（本来也识别不了），既不崩也不误判。
    """
    try:
        from sc2.unit import Unit, UnitOrder
    except (ImportError, AttributeError):
        return False

    def orders(self):  # 覆盖原 cached_property
        abilities = self._bot_object.game_data.abilities
        return [
            UnitOrder.from_proto(o, self._bot_object)
            for o in self._proto.orders
            if o.ability_id in abilities
        ]

    Unit.orders = property(orders)
    return True


def install() -> None:
    """打全部兼容补丁。幂等，可重复调用。"""
    enums = _patch_id_enums()
    orders_ok = _patch_unit_orders()
    logger.info(
        f"compat_patch: 枚举容忍未知id={enums}；unit.orders跳过未知技能={orders_ok}"
    )


install()
