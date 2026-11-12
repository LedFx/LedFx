"""transmission_mode: changeable without a restart, and the binary_rgb frame."""

import struct

import pytest

from ledfx.api.websocket import binary_vis_frame
from ledfx.configuration.models import RESTART_FIELDS, LedFxConfig


def test_changing_it_needs_no_restart():
    assert "transmission_mode" not in RESTART_FIELDS


def test_compressed_stays_the_default():
    assert LedFxConfig().transmission_mode == "compressed"


def test_binary_rgb_is_accepted():
    assert LedFxConfig(transmission_mode="binary_rgb").transmission_mode == "binary_rgb"


def test_binary_frame_layout():
    pixels = bytes(range(12))
    frame = binary_vis_frame(
        {"id": 7, "pixels": pixels, "shape": (2, 2), "is_device": True}
    )
    assert struct.unpack("<BBBBIHH", frame[:12]) == (0x4C, 1, 1, 3, 7, 2, 2)
    assert frame[12:] == pixels


def test_oversized_dimension_raises_struct_error():
    with pytest.raises(struct.error):
        binary_vis_frame({"id": 1, "pixels": b"\0" * 3, "shape": (1, 70000)})
