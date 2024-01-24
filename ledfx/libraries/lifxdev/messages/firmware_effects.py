#!/usr/bin/env pythom3

"""Firmware effects

https://lan.developer.lifx.com/docs/firmware-effects
"""

from __future__ import annotations

import enum
from typing import Any

from ledfx.libraries.lifxdev.messages import packet


class MultiZoneEffectType(enum.Enum):
    OFF = 0
    MOVE = 1


class TileEffectType(enum.Enum):
    OFF = 0
    RESERVED = 1
    MORPH = 2
    FLAME = 3


@packet.set_message_type(507)
class GetMultiZoneEffect(packet.LifxMessage):
    pass


@packet.set_message_type(508)
class SetMultiZoneEffect(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("instanceid", packet.LifxType.u32, 1),
        ("type", packet.LifxType.u8, 1),
        ("reserved_1", packet.LifxType.u16, 1),
        ("speed", packet.LifxType.u32, 1),
        ("duration", packet.LifxType.u64, 1),
        ("reserved_2", packet.LifxType.u32, 1),
        ("reserved_3", packet.LifxType.u32, 1),
        ("parameters", packet.LifxType.u32, 8),
    ]

    def set_value(self, name: str, value: Any):
        """The apply register must be an ApplicationRequest type"""
        if name.lower() == "type":
            if isinstance(value, str):
                value = MultiZoneEffectType[value].value
            elif isinstance(value, MultiZoneEffectType):
                value = value.value
            elif isinstance(value, int):
                if value not in [ar.value for ar in MultiZoneEffectType]:
                    raise ValueError(f"Invalid MultiZoneType: {value}")
        super().set_value(name, value)


@packet.set_message_type(509)
class StateMultiZoneEffect(SetMultiZoneEffect):
    pass


@packet.set_message_type(718)
class GetTileEffect(packet.LifxMessage):
    pass


@packet.set_message_type(719)
class SetTileEffect(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("reserved_1", packet.LifxType.u8, 1),
        ("reserved_2", packet.LifxType.u8, 1),
        ("instanceid", packet.LifxType.u32, 1),
        ("type", packet.LifxType.u8, 1),
        ("speed", packet.LifxType.u32, 1),
        ("duration", packet.LifxType.u64, 1),
        ("reserved_3", packet.LifxType.u32, 1),
        ("reserved_4", packet.LifxType.u32, 1),
        ("parameters", packet.LifxType.u32, 8),
        ("palette_count", packet.LifxType.u8, 1),
        ("palette", packet.Hsbk(), 16),
    ]

    def set_value(self, name: str, value: Any):
        """The apply register must be an ApplicationRequest type"""
        if name.lower() == "type":
            if isinstance(value, str):
                value = TileEffectType[value].value
            elif isinstance(value, TileEffectType):
                value = value.value
            elif isinstance(value, int):
                if value not in [ar.value for ar in TileEffectType]:
                    raise ValueError(f"Invalid TileType: {value}")
        super().set_value(name, value)


@packet.set_message_type(720)
class StateTileEffect(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("reserved_1", packet.LifxType.u8, 1),
        ("instanceid", packet.LifxType.u32, 1),
        ("type", packet.LifxType.u8, 1),
        ("speed", packet.LifxType.u32, 1),
        ("duration", packet.LifxType.u64, 1),
        ("reserved_2", packet.LifxType.u32, 1),
        ("reserved_3", packet.LifxType.u32, 1),
        ("parameters", packet.LifxType.u32, 8),
        ("palette_count", packet.LifxType.u8, 1),
        ("palette", packet.Hsbk(), 16),
    ]
