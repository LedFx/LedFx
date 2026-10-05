"""The native OPC adapter retains scalar RGB conversion semantics."""

import struct

import numpy as np
import pytest

from ledfx.devices.open_pixel_control import OpenPixelControl
from tests.native_sender_helpers import capture_packets, make_device


@pytest.mark.parametrize("dtype", ["float32", "float64", "int16", "uint8"])
@pytest.mark.parametrize("count", [1, 17, 1000])
def test_opc_matches_scalar_clamping_and_truncation(dtype: str, count: int) -> None:
    rng = np.random.default_rng(2058)
    data = rng.uniform(-100, 400, (count * 2, 3)).astype(dtype)[::2, ::-1]
    original = data.copy()
    expected = struct.pack(">BBH", 0, 0, count * 3) + bytes(
        min(255, max(0, int(value))) for row in data for value in row
    )
    sender = make_device(OpenPixelControl, count)
    sender.flush(data)
    assert capture_packets(sender) == [expected]
    np.testing.assert_array_equal(data, original)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_opc_rejects_nonfinite_channels_before_sending(value: float) -> None:
    sender = make_device(OpenPixelControl, 1)
    error = ValueError if np.isnan(value) else OverflowError
    with pytest.raises(error):
        sender.flush(np.array([[0, value, 255]]))
    assert not capture_packets(sender)


@pytest.mark.parametrize("shape", [(1, 4), (2, 3), (3,)])
def test_opc_rejects_shape_mismatch_before_sending(shape: tuple[int, ...]) -> None:
    sender = make_device(OpenPixelControl, 1)
    with pytest.raises(ValueError, match="configured number"):
        sender.flush(np.zeros(shape))
    assert not capture_packets(sender)
