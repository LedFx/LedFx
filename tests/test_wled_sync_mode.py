"""WLED.set_sync_mode rejects unknown modes even when asserts are stripped."""

import pytest

from ledfx.utils import WLED


def test_unknown_sync_mode_raises_value_error():
    wled = WLED("192.0.2.1")
    with pytest.raises(ValueError, match="Invalid WLED sync mode 'BOGUS'"):
        wled.set_sync_mode("bogus")


def test_known_sync_mode_sets_the_port():
    wled = WLED("192.0.2.1")
    wled.sync_settings = {"if": {"live": {"port": WLED.SYNC_MODES["DDP"]}}}
    wled.set_sync_mode("e131")
    assert wled.sync_settings["if"]["live"]["port"] == WLED.SYNC_MODES["E131"]
    assert wled.reboot_flag is True
