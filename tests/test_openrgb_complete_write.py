"""Large OpenRGB TCP packets must not silently lose their unwritten suffix."""

import socket
from typing import cast

import numpy as np
import pytest

from ledfx.devices.openrgb import OpenRGB
from ledfx.devices.packets import build_openrgb_packet


class ShortWriter:
    def __init__(self) -> None:
        self.received = bytearray()
        self.calls = 0

    def send(self, data: bytes) -> int:
        self.calls += 1
        size = min(997, len(data))
        self.received.extend(data[:size])
        return size

    def sendall(self, data: bytes) -> None:
        while data:
            data = data[self.send(data) :]


def test_openrgb_sends_complete_50k_frame_on_partial_transport() -> None:
    writer = ShortWriter()
    frame = np.random.default_rng(50).uniform(0, 256, (50000, 3))
    OpenRGB.send_out(cast(socket.socket, writer), frame, 3)
    assert writer.calls > 1
    assert writer.received == build_openrgb_packet(frame, 3)


def test_openrgb_preserves_transport_errors() -> None:
    class Broken:
        def sendall(self, data: bytes) -> None:
            raise BrokenPipeError("disconnected")

    with pytest.raises(BrokenPipeError, match="disconnected"):
        OpenRGB.send_out(cast(socket.socket, Broken()), np.zeros((1, 3)), 3)
