#!/usr/bin/env pythom3

"""Tile messages

https://lan.developer.lifx.com/docs/tile-messages
"""

from __future__ import annotations

from ledfx.libraries.lifxdev.messages import packet


class Tile(packet.LifxStruct):
    registers: packet.REGISTER_T = [
        ("accel_meas_x", packet.LifxType.s16, 1),
        ("accel_meas_y", packet.LifxType.s16, 1),
        ("accel_meas_z", packet.LifxType.s16, 1),
        ("reserved_1", packet.LifxType.s16, 1),
        ("user_x", packet.LifxType.f32, 1),
        ("user_y", packet.LifxType.f32, 1),
        ("width", packet.LifxType.u8, 1),
        ("height", packet.LifxType.u8, 1),
        ("reserved_2", packet.LifxType.u8, 1),
        ("device_version_vendor", packet.LifxType.u32, 1),
        ("device_version_product", packet.LifxType.u32, 1),
        ("device_version_version", packet.LifxType.u32, 1),
        ("firmware_build", packet.LifxType.u64, 1),
        ("reserved_3", packet.LifxType.u64, 1),
        ("firmware_version_minor", packet.LifxType.u16, 1),
        ("firmware_version_major", packet.LifxType.u16, 1),
        ("reserved_4", packet.LifxType.u32, 1),
    ]


@packet.set_message_type(701)
class GetDeviceChain(packet.LifxMessage):
    pass


@packet.set_message_type(702)
class StateDeviceChain(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("start_index", packet.LifxType.u8, 1),
        ("tile_devices", Tile(), 16),
        ("total_count", packet.LifxType.u8, 1),
    ]


@packet.set_message_type(703)
class SetUserPosition(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("tile_index", packet.LifxType.u8, 1),
        ("reserved", packet.LifxType.u16, 1),
        ("user_x", packet.LifxType.f32, 1),
        ("user_y", packet.LifxType.f32, 1),
    ]


@packet.set_message_type(707)
class GetTileState64(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("tile_index", packet.LifxType.u8, 1),
        ("length", packet.LifxType.u8, 1),
        ("reserved", packet.LifxType.u8, 1),
        ("x", packet.LifxType.u8, 1),
        ("y", packet.LifxType.u8, 1),
        ("width", packet.LifxType.u8, 1),
    ]


@packet.set_message_type(711)
class StateTileState64(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("tile_index", packet.LifxType.u8, 1),
        ("reserved", packet.LifxType.u8, 1),
        ("x", packet.LifxType.u8, 1),
        ("y", packet.LifxType.u8, 1),
        ("width", packet.LifxType.u8, 1),
        ("colors", packet.Hsbk(), 64),
    ]


@packet.set_message_type(715)
class SetTileState64(packet.LifxMessage):
    registers: packet.REGISTER_T = [
        ("tile_index", packet.LifxType.u8, 1),
        ("length", packet.LifxType.u8, 1),
        ("reserved", packet.LifxType.u8, 1),
        ("x", packet.LifxType.u8, 1),
        ("y", packet.LifxType.u8, 1),
        ("width", packet.LifxType.u8, 1),
        ("duration", packet.LifxType.u32, 1),
        ("colors", packet.Hsbk(), 64),
    ]
