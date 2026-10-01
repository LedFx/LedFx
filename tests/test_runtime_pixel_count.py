"""Regressions for changing a device's pixel count while LedFx runs."""

from unittest.mock import MagicMock, patch

import numpy as np

from ledfx.devices import Device
from ledfx.devices.e131 import E131Device
from ledfx.transitions import Transitions
from ledfx.virtuals import Virtual


def _e131(pixel_count: int) -> E131Device:
    ledfx = MagicMock()
    ledfx.virtuals = dict[str, object]()
    config = E131Device.config_model().model_validate(
        {"name": "e131", "ip_address": "10.0.0.1", "pixel_count": pixel_count}
    )
    device = E131Device(ledfx, config)
    device._destination = "10.0.0.1"
    device._virtuals_objs = []
    return device


def test_e131_pixel_count_change_resizes_channels() -> None:
    # LEDFX-V2-REL-1PN / 3MD: channel_count stayed at the old size, so every
    # flush raised "Invalid buffer size".
    device = _e131(100)
    with patch("ledfx.devices.e131.sacn.sACNsender") as sender:
        sender.return_value.__getitem__.return_value.dmx_data = (0,) * 512
        device.activate()
        device.update_config({"pixel_count": 200})

        assert getattr(device.config, "channel_count") == 600  # noqa: B009
        assert getattr(device.config, "universe_end") == 2  # noqa: B009
        # The sender restarts so the second universe is activated.
        assert sender.call_count == 2
        sender.return_value.activate_output.assert_called_with(2)
        device.flush(np.zeros((200, 3)))


def test_pixel_count_change_resizes_device_buffer() -> None:
    # LEDFX-V2-REL-1WD: _pixels kept its old length, so clearing a segment
    # sized for the new count raised a broadcast error.
    device = _e131(1)
    Device.activate(device)  # the buffer only; no sACN sender
    device.update_config({"pixel_count": 4})

    assert device._pixels is not None
    assert device._pixels.shape == (4, 3)
    device._segments = [["v", 0, 3]]
    device.clear_virtual_segments("v")


def test_transition_follows_effective_pixel_count() -> None:
    # LEDFX-V2-REL-4SD: the dissolve mask kept the old length after the
    # effective pixel count changed, so every transition frame raised.
    virtual = object.__new__(Virtual)
    virtual._ledfx = MagicMock()
    virtual._ledfx.config.global_brightness = 1
    virtual._config = {"center_offset": 0, "max_brightness": 1}
    virtual._active_effect = MagicMock()
    virtual._active_effect.get_pixels.return_value = np.zeros((1, 3))
    virtual._transition_effect = MagicMock(is_active=True)
    virtual._transition_effect.get_pixels.return_value = np.zeros((1, 3))
    virtual.transitions = Transitions(2)
    virtual.frame_transitions = virtual.transitions["Dissolve"]
    virtual.transition_frame_counter = 0
    virtual.transition_frame_total = 10

    virtual.assemble_frame()
    assert virtual.transitions.pixel_count == 1
