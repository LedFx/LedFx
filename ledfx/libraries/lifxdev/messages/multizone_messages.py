#!/usr/bin/env pythom3

"""MultiZone messages

https://lan.developer.lifx.com/docs/multizone-messages
"""

from __future__ import annotations

import enum
from typing import Any

from ledfx.libraries.lifxdev.messages import packet


class ApplicationRequest(enum.Enum):
    NO_APPLY = 0
    APPLY = 1
    APPLY_ONLY = 2


@packet.set_message_type(510)
class SetExtendedColorZones(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("duration", packet.LifxType.u32, 1),
        ("apply", packet.LifxType.u8, 1),
        ("index", packet.LifxType.u16, 1),
        ("colors_count", packet.LifxType.u8, 1),
        ("colors", packet.Hsbk(), 82),
    ]

    def set_value(self, name: str, value: Any, index: int | None = None):
        """The apply register must be an ApplicationRequest type"""
        if name.lower() == "apply":
            if isinstance(value, str):
                value = ApplicationRequest[value].value
            elif isinstance(value, ApplicationRequest):
                value = value.value
            elif isinstance(value, int):
                if value not in [ar.value for ar in ApplicationRequest]:
                    raise ValueError(f"Invalid application request: {value}")
        super().set_value(name, value, index)


@packet.set_message_type(511)
class GetExtendedColorZones(packet.LifxMessage):
    pass


@packet.set_message_type(512)
class StateExtendedColorZones(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("count", packet.LifxType.u16, 1),
        ("index", packet.LifxType.u16, 1),
        ("colors_count", packet.LifxType.u8, 1),
        ("colors", packet.Hsbk(), 82),
    ]


# TODO The above API is for the newer firmware. Add support for the older firmware message types
