"""Validate real ArtDmx headers across Sub-Net/Net address boundaries."""

import socket
import struct
from types import SimpleNamespace
from typing import cast

import numpy as np
import pytest
from stupidArtnet import StupidArtnet

from ledfx.devices.artnet import ArtNetDevice
from tools.sender_bench import Sink


@pytest.mark.parametrize("start", [0, 14, 254, 256, 4094, 32766])
def test_artnet_serializes_full_universe_address_without_clamping(start: int) -> None:
    count = 2 if start == 32766 else 4
    config = ArtNetDevice.config_model().model_validate(
        {
            "name": "address-test",
            "ip_address": "127.0.0.1",
            "pixel_count": count * 170,
            "universe": start,
        }
    )
    device = ArtNetDevice(SimpleNamespace(), config)
    sink = Sink()
    artnet = StupidArtnet("127.0.0.1", universe=start, packet_size=510, broadcast=False)
    artnet.socket_client.close()
    artnet.socket_client = cast(socket.socket, sink)
    device._artnet = artnet
    try:
        data = (np.arange(count * 510).reshape(-1, 3) % 256).astype(float)
        device.flush(data)
        assert sink.capture is not None and len(sink.capture) == count
        addresses = [struct.unpack("<H", packet[14:16])[0] for packet in sink.capture]
        assert addresses == list(range(start, start + count))
        assert (
            b"".join(packet[18:] for packet in sink.capture)
            == data.astype(np.uint8).tobytes()
        )
    finally:
        artnet.close()


@pytest.mark.parametrize(("start", "pixels"), [(32768, 1), (32767, 171)])
def test_artnet_rejects_out_of_range_layout_before_sending(
    start: int, pixels: int
) -> None:
    values = {
        "name": "address-test",
        "ip_address": "127.0.0.1",
        "pixel_count": pixels,
        "universe": start,
    }
    # Preserve the legacy config schema; validate the complete channel span
    # when preparing output, before the first packet can be emitted.
    device = ArtNetDevice(
        SimpleNamespace(), ArtNetDevice.config_model().model_validate(values)
    )
    with pytest.raises(ValueError, match="exceeds universe"):
        device.do_once()
