"""OPC's vectorized encoder must retain the scalar sender's RGB semantics."""

import struct

import numpy as np
import pytest

from tools.sender_bench import Sink
from tools.sender_bench_protocols import make_sender


@pytest.mark.parametrize("dtype", ["float32", "float64", "int16", "uint8"])
@pytest.mark.parametrize("count", [1, 17, 1000])
def test_opc_matches_scalar_clamping_and_truncation(dtype: str, count: int) -> None:
    rng = np.random.default_rng(2058)
    data = rng.uniform(-100, 400, (count * 2, 3)).astype(dtype)[::2, ::-1]
    original = data.copy()
    expected = struct.pack(">BBH", 0, 0, count * 3) + bytes(
        min(255, max(0, int(value))) for row in data for value in row
    )
    sink = Sink()
    make_sender("opc", count, sink).flush(data)
    assert sink.capture == [expected]
    np.testing.assert_array_equal(data, original)


@pytest.mark.parametrize("value", [float("nan"), float("inf"), -float("inf")])
def test_opc_rejects_nonfinite_channels_before_sending(value: float) -> None:
    sink = Sink()
    sender = make_sender("opc", 1, sink)
    error = ValueError if np.isnan(value) else OverflowError
    with pytest.raises(error):
        sender.flush(np.array([[0, value, 255]]))
    assert not sink.capture


@pytest.mark.parametrize("shape", [(1, 4), (2, 3), (3,)])
def test_opc_rejects_shape_mismatch_before_sending(shape: tuple[int, ...]) -> None:
    sink = Sink()
    with pytest.raises(ValueError, match="configured number"):
        make_sender("opc", 1, sink).flush(np.zeros(shape))
    assert not sink.capture
