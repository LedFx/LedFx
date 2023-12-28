#!/usr/bin/env pythom3

"""Device messages

https://lan.developer.lifx.com/docs/device-messages
"""

from __future__ import annotations

from ledfx.libraries.lifxdev.messages import packet


@packet.set_message_type(2)
class GetService(packet.LifxMessage):
    pass


@packet.set_message_type(3)
class StateService(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("service", packet.LifxType.u8, 1),
        ("port", packet.LifxType.u32, 1),
    ]


@packet.set_message_type(12)
class GetHostInfo(packet.LifxMessage):
    pass


@packet.set_message_type(13)
class StateHostInfo(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("signal", packet.LifxType.f32, 1),
        ("tx", packet.LifxType.u32, 1),
        ("rx", packet.LifxType.u32, 1),
        ("reserved", packet.LifxType.s16, 1),
    ]


@packet.set_message_type(14)
class GetHostFirmware(packet.LifxMessage):
    pass


@packet.set_message_type(15)
class StateHostFirmware(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("build", packet.LifxType.u64, 1),
        ("reserved", packet.LifxType.u64, 1),
        ("version_minor", packet.LifxType.u16, 1),
        ("version_major", packet.LifxType.u16, 1),
    ]


@packet.set_message_type(16)
class GetWifiInfo(packet.LifxMessage):
    pass


@packet.set_message_type(17)
class StateWifiInfo(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("signal", packet.LifxType.f32, 1),
        ("tx", packet.LifxType.u32, 1),
        ("rx", packet.LifxType.u32, 1),
        ("reserved", packet.LifxType.s16, 1),
    ]


@packet.set_message_type(18)
class GetWifiFirmware(packet.LifxMessage):
    pass


@packet.set_message_type(19)
class StateWifiFirmware(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("build", packet.LifxType.u64, 1),
        ("reserved", packet.LifxType.u64, 1),
        ("version_minor", packet.LifxType.u16, 1),
        ("version_major", packet.LifxType.u16, 1),
    ]


@packet.set_message_type(20)
class GetPower(packet.LifxMessage):
    pass


@packet.set_message_type(21)
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


@packet.set_message_type(22)
class StatePower(packet.LifxMessage):
    registers: packet.REGISTER_T = [("level", packet.LifxType.u16, 1)]

    def get_value(self, name: str) -> bool:
        """Get a register value by name."""
        value = super().get_value(name)
        return value > 0


@packet.set_message_type(23)
class GetLabel(packet.LifxMessage):
    pass


@packet.set_message_type(24)
class SetLabel(packet.LifxMessage):
    registers: packet.REGISTER_T = [("label", packet.LifxType.char, 32)]


@packet.set_message_type(25)
class StateLabel(packet.LifxMessage):
    registers: packet.REGISTER_T = [("label", packet.LifxType.char, 32)]


@packet.set_message_type(32)
class GetVersion(packet.LifxMessage):
    pass


@packet.set_message_type(33)
class StateVersion(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("vendor", packet.LifxType.u32, 1),
        ("product", packet.LifxType.u32, 1),
        ("version", packet.LifxType.u32, 1),
    ]


@packet.set_message_type(34)
class GetInfo(packet.LifxMessage):
    pass


@packet.set_message_type(35)
class StateInfo(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("time", packet.LifxType.u64, 1),
        ("uptime", packet.LifxType.u64, 1),
        ("downtime", packet.LifxType.u64, 1),
    ]


@packet.set_message_type(48)
class GetLocation(packet.LifxMessage):
    pass


@packet.set_message_type(49)
class SetLocation(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("location", packet.LifxType.char, 16),
        ("label", packet.LifxType.char, 32),
        ("updated_at", packet.LifxType.u64, 1),
    ]


@packet.set_message_type(50)
class StateLocation(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("location", packet.LifxType.char, 16),
        ("label", packet.LifxType.char, 32),
        ("updated_at", packet.LifxType.u64, 1),
    ]


@packet.set_message_type(51)
class GetGroup(packet.LifxMessage):
    pass


@packet.set_message_type(52)
class SetGroup(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("group", packet.LifxType.char, 16),
        ("label", packet.LifxType.char, 32),
        ("updated_at", packet.LifxType.u64, 1),
    ]


@packet.set_message_type(53)
class StateGroup(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("group", packet.LifxType.char, 16),
        ("label", packet.LifxType.char, 32),
        ("updated_at", packet.LifxType.u64, 1),
    ]


@packet.set_message_type(58)
class EchoRequest(packet.LifxMessage):
    registers: packet.REGISTER_T = [("payload", packet.LifxType.char, 64)]


@packet.set_message_type(59)
class EchoResponse(packet.LifxMessage):
    registers: packet.REGISTER_T = [("payload", packet.LifxType.char, 64)]
