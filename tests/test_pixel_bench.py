"""The benchmark must reject corrupt streams and compare like workloads."""

import base64
import struct
import sys

import pytest

from tools.pixel_bench import DDPReceiver, compare_baseline, parse_args, validate_frame


def test_sampling_requires_supported_python_and_no_cprofile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "version_info", (3, 12))
    with pytest.raises(SystemExit):
        parse_args(["--sampling", "cpu"])
    monkeypatch.setattr(sys, "version_info", (3, 15))
    with pytest.raises(SystemExit):
        parse_args(["--sampling", "cpu", "--profile"])
    assert parse_args(["--sampling", "gil", "--loops", "standard"]).sampling == "gil"


def packet(
    offset: int, payload: bytes, *, push: bool = False, sequence: int = 1
) -> bytes:
    return (
        struct.pack(">BBBBIH", 0x40 | push, sequence, 0x0B, 1, offset, len(payload))
        + payload
    )


def test_ddp_requires_all_rgb_bytes_in_order() -> None:
    receiver = DDPReceiver(4)
    receiver.feed(packet(0, b"abcdef"))
    receiver.feed(packet(6, b"ghijkl", push=True))
    assert receiver.counts[2:] == [1, 1, 0]


def test_ddp_push_does_not_hide_a_missing_middle_packet() -> None:
    receiver = DDPReceiver(4)
    receiver.feed(packet(0, b"abc"))
    receiver.feed(packet(9, b"jkl", push=True))
    assert receiver.counts[2:] == [1, 0, 0]
    receiver.feed(packet(0, b"abcdefghijkl", push=True, sequence=2))
    assert receiver.counts[2:] == [2, 1, 0]


def test_ddp_does_not_join_different_frame_sequences() -> None:
    receiver = DDPReceiver(4)
    receiver.feed(packet(0, b"abcdef", sequence=1))
    receiver.feed(packet(6, b"ghijkl", push=True, sequence=2))
    assert receiver.counts[3] == 0


@pytest.mark.parametrize(
    "data", [b"short", packet(0, b"abcdef")[:-1], packet(9, b"abcdef")]
)
def test_ddp_rejects_malformed_packets(data: bytes) -> None:
    receiver = DDPReceiver(4)
    receiver.feed(data)
    assert receiver.counts[4] == 1


def test_websocket_validation_counts_actual_rgb_bytes() -> None:
    encoded = base64.b64encode(b"abcdef").decode("ascii")
    assert validate_frame({"shape": [1, 2], "pixels": encoded}, 2) == [1, 2]
    with pytest.raises(ValueError, match="Truncated"):
        validate_frame({"shape": [1, 2], "pixels": encoded[:-4]}, 2)
    with pytest.raises(ValueError, match="shape"):
        validate_frame({"shape": [1, 1], "pixels": encoded}, 2)
    with pytest.raises(ValueError):
        validate_frame({"shape": [1, 2], "pixels": "!!!!!!!!"}, 2)


def test_baseline_uses_medians_and_rejects_unmatched_scenarios() -> None:
    baseline = [
        {
            "loop": "standard",
            "platform": "linux",
            "python": "3.12",
            "device": "ddp",
            "pixels": 500000,
            "refresh_rate": 60,
            "preview_fps": 60,
            "effect_speed": 6,
            "stream": "full",
            "profiled": False,
            "assemble": {"fps": fps},
            "effect": {"fps": fps},
            "ws_fps": fps,
            "ws_changed_fps": fps,
            "ddp_complete_fps": fps,
            "server_cpu_pct": 100,
            "rss_mb": 200,
        }
        for fps in (60.0, 60.0, 1.0)
    ]
    current = [{**baseline[0], "ws_fps": 40.0}]
    failures = compare_baseline(current, baseline, 0.1)
    assert len(failures) == 1
    assert "ws_fps" in failures[0]
    assert compare_baseline(baseline, baseline, 0.1) == []
    assert (
        "no matching"
        in compare_baseline([{**baseline[0], "profiled": True}], baseline, 0.1)[0]
    )


@pytest.mark.parametrize(
    "arguments",
    [
        ["--pixels", "0"],
        ["--seconds", "-1"],
        ["--seconds", "nan"],
        ["--warmup", "-1"],
        ["--repeats", "0"],
        ["--streams", "typo"],
        ["--loops", "typo"],
        ["--max-regression", "1"],
    ],
)
def test_invalid_benchmark_parameters_fail_early(arguments: list[str]) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--loops", "standard", *arguments])
