#!/usr/bin/env pythom3

"""Light messages

https://lan.developer.lifx.com/docs/light-messages
"""

from __future__ import annotations

from ledfx.libraries.lifxdev.messages import packet


@packet.set_message_type(101)
class Get(packet.LifxMessage):
    pass


@packet.set_message_type(102)
class SetColor(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("reserved", packet.LifxType.u8, 1),
        ("color", packet.Hsbk(), 1),
        ("duration", packet.LifxType.u32, 1),
    ]


@packet.set_message_type(103)
class SetWaveform(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("reserved", packet.LifxType.u8, 1),
        ("transient", packet.LifxType.u8, 1),
        ("color", packet.Hsbk(), 1),
        ("period", packet.LifxType.u32, 1),
        ("cycles", packet.LifxType.f32, 1),
        ("skew_ratio", packet.LifxType.s16, 1),
        ("waveform", packet.LifxType.u8, 1),
    ]


@packet.set_message_type(107)
class State(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("color", packet.Hsbk(), 1),
        ("reserved_1", packet.LifxType.s16, 1),
        ("power", packet.LifxType.u16, 1),
        ("label", packet.LifxType.char, 32),
        ("reserved_2", packet.LifxType.u64, 1),
    ]


@packet.set_message_type(116)
class GetPower(packet.LifxMessage):
    pass


@packet.set_message_type(117)
class SetPower(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("level", packet.LifxType.u16, 1),
        ("duration", packet.LifxType.u32, 1),
    ]

    def set_value(self, name: str, value: int | bool) -> None:
        """SetPower level can be either 0 or 65535"""
        if name.lower() == "level":
            if isinstance(value, bool):
                value *= 65535
            elif isinstance(value, list) and value[0] not in [0, 65535]:
                raise ValueError("SetPower level must be either 0 or 65535")
            elif not isinstance(value, list) and value not in [0, 65535]:
                raise ValueError("SetPower level must be either 0 or 65535")
        super().set_value(name, value)


@packet.set_message_type(118)
class StatePower(packet.LifxMessage):
    registers: packet.REGISTER_T = [("level", packet.LifxType.u16, 1)]

    def get_value(self, name: str) -> bool:
        """Get a register value by name."""
        value = super().get_value(name)
        return value > 0


@packet.set_message_type(120)
class GetInfrared(packet.LifxMessage):
    pass


@packet.set_message_type(121)
class StateInfrared(packet.LifxMessage):
    registers: packet.REGISTER_T = [("brightness", packet.LifxType.u16, 1)]


@packet.set_message_type(122)
class SetInfrared(packet.LifxMessage):
    registers: packet.REGISTER_T = [("brightness", packet.LifxType.u16, 1)]
