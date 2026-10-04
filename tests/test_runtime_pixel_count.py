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
    config = E131Device.schema()(
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

        assert device.config["channel_count"] == 600
        assert device.config["universe_end"] == 2
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
    virtual._ledfx.config = {"global_brightness": 1}
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


def test_shrinking_an_active_device_clears_its_old_segment() -> None:
    # Shrinking resizes the buffer before the old segment is cleared.
    device = _e131(4)
    device._ledfx.config = {"flush_on_deactivate": True}
    Device.activate(device)  # the buffer only; no sACN sender
    device._segments = [["v", 0, 3]]
    device.update_config({"pixel_count": 2})
    device.clear_virtual_segments("v")

    assert device._pixels is not None
    assert device._pixels.shape == (2, 3)


def test_e131_ip_address_change_rebuilds_the_sender() -> None:
    # The old sender keeps its destination; a new address must replace it.
    device = _e131(100)
    with (
        patch("ledfx.devices.e131.sacn.sACNsender") as sender,
        patch("ledfx.devices.NetworkedDevice.activate") as resolve_then_activate,
    ):
        device.activate()
        device.update_config({"ip_address": "10.0.0.2"})

    sender.return_value.stop.assert_called_once()
    assert device._sacn is None
    # Activation resolves the new address, then builds the new sender.
    assert device._destination is None
    assert resolve_then_activate.call_count == 2  # first activate, then this one


def test_e131_layout_ending_on_a_universe_boundary_sends_every_channel() -> None:
    # 170 pixels from channel offset 1 end on index 510: the first channel of
    # the second 510-channel universe.
    device = _e131(170)
    device.update_config({"channel_offset": 1})
    universes: dict[int, MagicMock] = {}

    def universe(u: int) -> MagicMock:
        return universes.setdefault(u, MagicMock(dmx_data=(0,) * 512))

    with patch("ledfx.devices.e131.sacn.sACNsender") as sender:
        sender.return_value.__getitem__.side_effect = universe
        device.activate()
        device.flush(np.full((170, 3), 255))

    assert device.config["universe_end"] == 2
    assert universes[2].dmx_data[0] == 255
