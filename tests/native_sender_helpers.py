"""Small native capture fixtures for application adapter contracts."""

from typing import TypeVar
from unittest.mock import MagicMock

from ledfx_senders import ArtNetSender, OPCSender, OSCSender

from ledfx.devices.artnet import ArtNetDevice
from ledfx.devices.native_packet import NativePacketDevice
from ledfx.devices.open_pixel_control import OpenPixelControl
from ledfx.devices.osc import OSCServerDevice
from ledfx.utils import extract_uint8_seq

TDevice = TypeVar("TDevice", bound=NativePacketDevice)


def make_device(cls: type[TDevice], pixels: int, **settings: object) -> TDevice:
    core = MagicMock()
    core.virtuals = dict[str, object]()
    device = cls(
        core,
        cls.Config.model_validate(
            {
                "name": "test",
                "ip_address": "127.0.0.1",
                "pixel_count": pixels,
                **settings,
            }
        ),
    )
    device._destination = "127.0.0.1"
    device._virtuals_objs = []
    configure_capture(device)
    return device


def configure_capture(device: NativePacketDevice) -> None:
    old = device._sender
    if isinstance(device, ArtNetDevice):
        device._sender = ArtNetSender._test_sender(
            destination="127.0.0.1",
            port=device.config.port,
            universe=device.config.universe,
            packet_size=device.config.packet_size,
            even_packet_size=device.config.even_packet_size,
            dmx_start_address=device.config.dmx_start_address,
            pixel_count=device.config.pixel_count,
            pixels_per_device=device.config.pixels_per_device,
            pre_amble=bytes(extract_uint8_seq(device.config.pre_amble)),
            post_amble=bytes(extract_uint8_seq(device.config.post_amble)),
            rgb_order=device.config.rgb_order,
            white_mode=device.config.white_mode,
            broadcast=False,
            mode="capture",
        )
    elif isinstance(device, OpenPixelControl):
        device._sender = OPCSender._test_sender(
            device.config.pixel_count,
            destination="127.0.0.1",
            channel=device.config.channel,
            mode="capture",
        )
    elif isinstance(device, OSCServerDevice):
        device._sender = OSCSender._test_sender(
            destination="127.0.0.1",
            port=device.config.port,
            pixel_count=device.config.pixel_count,
            path=device.config.path,
            starting_addr=device.config.starting_addr,
            send_type=device.config.send_type,
            mode="capture",
        )
    else:
        raise TypeError("unsupported capture device")
    if old is not None:
        if isinstance(old, ArtNetSender):
            old.close(False)
        else:
            old.close()


def capture_packets(device: NativePacketDevice) -> list[bytes]:
    sender = device._sender
    assert sender is not None
    return [packet for packet, _ in sender._engine.captures()]
