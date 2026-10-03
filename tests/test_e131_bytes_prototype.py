"""Keep the benchmark-only byte path isolated and compare actual packet bytes."""

import numpy as np
import pytest
from sacn.messages.data_packet import DataPacket

from tools.e131_bytes_prototype import BytesDataPacket, enable_e131_bytes_prototype
from tools.sender_bench import Sink, summarize
from tools.sender_bench_protocols import canonical_packet, make_sender


@pytest.mark.parametrize("length", [0, 1, 127, 510, 511, 512])
def test_bytes_setter_matches_library_packet(length: int) -> None:
    data = bytes(i % 256 for i in range(length))
    original = DataPacket(tuple(range(16)), "test", 32767, tuple(data))
    prototype = BytesDataPacket(tuple(range(16)), "test", 32767)
    prototype.dmxData = data
    assert prototype.dmxData == original.dmxData
    assert prototype.getBytes() == original.getBytes()


@pytest.mark.parametrize("invalid", [bytes(513), (-1,), (256,), (1.5,), ("1",)])
def test_bytes_setter_rejects_invalid_data(invalid: object) -> None:
    packet = BytesDataPacket(tuple(range(16)), "test", 1)
    with pytest.raises(ValueError):
        packet.dmxData = invalid


@pytest.mark.parametrize("count", [1, 171, 1000])
def test_prototype_preserves_wire_bytes_and_is_instance_local(count: int) -> None:
    sink = Sink()
    device = make_sender("e131", count, sink)
    untouched = make_sender("e131", 1, Sink())
    data = np.random.default_rng(50).uniform(0, 256, (count, 3))
    device.flush(data)
    assert sink.capture is not None
    expected = [canonical_packet("e131", p) for p in sink.capture]
    enable_e131_bytes_prototype(device)
    sink.capture = []
    device.flush(data)
    assert [canonical_packet("e131", p) for p in sink.capture] == expected
    assert type(untouched._sacn[1]._packet) is DataPacket
    sink.capture = []
    data[0, 0] = -1
    with pytest.raises(ValueError):
        device.flush(data)
    assert sink.capture == []


def test_prototype_is_never_merged_with_production_summary() -> None:
    common = {"sender": "e131", "pixels": 50000, "status": "ok", "flush_mean_ms": 1}
    rows = [common | {"e131_bytes_prototype": value} for value in (False, True)]
    assert len(summarize(rows)) == 2
