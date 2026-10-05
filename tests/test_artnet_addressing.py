"""Validate native ArtDmx headers across Sub-Net/Net address boundaries."""

import struct
from unittest.mock import MagicMock

import numpy as np
import pytest
from ledfx_senders import ArtNetSender

from ledfx.devices.artnet import ArtNetDevice
from tests.native_sender_helpers import capture_packets, make_device


@pytest.mark.parametrize("start", [0, 14, 254, 256, 4094, 32766])
def test_artnet_serializes_full_universe_address_without_clamping(start: int) -> None:
    count = 2 if start == 32766 else 4
    device = make_device(ArtNetDevice, count * 170, universe=start)
    data = (np.arange(count * 510).reshape(-1, 3) % 256).astype(float)
    device.flush(data)
    packets = capture_packets(device)
    assert len(packets) == count
    assert [struct.unpack("<H", p[14:16])[0] for p in packets] == list(
        range(start, start + count)
    )
    assert b"".join(p[18:] for p in packets) == data.astype(np.uint8).tobytes()
    assert isinstance(device._sender, ArtNetSender)
    device._sender.close(False)


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
    with pytest.raises(ValueError, match="universe"):
        ArtNetDevice(MagicMock(), ArtNetDevice.Config.model_validate(values))
