"""Regressions for changing a device's pixel count while LedFx runs."""

from unittest.mock import MagicMock, patch

import numpy as np

from ledfx.devices.e131 import E131Device


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
