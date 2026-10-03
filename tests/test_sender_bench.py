"""Sender characterization must reject lost, corrupt and partial delivery."""

import socket
from pathlib import Path
from typing import cast

import numpy as np
import pytest

from tools.effect_profile_report import summarize_stacks
from tools.sender_bench import (
    PacketMatcher,
    Sink,
    frame_pair,
    parse_args,
    skip_reason,
    summarize,
)
from tools.sender_bench_protocols import SPECS, check_payload, make_sender


@pytest.mark.parametrize("name", list(SPECS))
def test_real_sender_payloads_match_dense_and_sparse_inputs(name: str) -> None:
    sink = Sink()
    sender = make_sender(name, 60, sink)
    frames = frame_pair(60, "sparse")
    previous = None
    for frame in (frames[0], frames[1], frames[0]):
        sink.capture = []
        sender.flush(frame)
        assert sink.capture
        check_payload(name, sink.capture, frame, previous)
        with pytest.raises(AssertionError):
            check_payload(name, sink.capture, (frame + 1) % 256, previous)
        previous = frame


@pytest.mark.parametrize(
    "name,count", [("ddp", 481), ("artnet", 171), ("e131", 171), ("udp-dnrgb", 490)]
)
def test_multi_packet_delivery_requires_every_packet(name: str, count: int) -> None:
    sink = Sink()
    sender = make_sender(name, count, sink)
    frame = frame_pair(count, "dense")[0]
    sender.flush(frame)
    packets = sink.capture
    assert packets is not None and len(packets) > 1
    check_payload(name, packets, frame, None)
    matcher = PacketMatcher(name, [packets])
    for packet in packets[1:]:
        matcher.feed(packet)
    assert matcher.complete == 0
    for packet in packets:
        matcher.feed(packet)
    assert matcher.complete == 1
    matcher.feed(packets[0][:-1])
    assert matcher.invalid == 1


def test_ddp_mixed_sequences_never_count_as_complete_frame() -> None:
    sink = Sink()
    make_sender("ddp", 481, sink).flush(frame_pair(481, "dense")[0])
    assert sink.capture is not None
    packets = sink.capture
    matcher = PacketMatcher("ddp", [packets])
    matcher.feed(packets[0])
    changed = bytearray(packets[1])
    changed[1] += 1
    matcher.feed(bytes(changed))
    assert matcher.complete == 0


def test_partial_keepalive_is_distinct_from_full_frame() -> None:
    frames = [[b"a", b"b"], [b"a"]]
    matcher = PacketMatcher("udp-dnrgb", frames, {1})
    matcher.feed(b"a")
    assert matcher.complete == 0 and matcher.keepalive_sets == 0
    # A partial matching variant must not discard the still-viable full one.
    matcher.feed(b"b")
    assert matcher.complete == 1 and matcher.keepalive_sets == 0
    matcher.feed(b"a")
    matcher.finish()
    assert matcher.complete == 1 and matcher.keepalive_sets == 1


def test_sink_records_short_tcp_writes_and_remaps_destinations() -> None:
    calls = []

    class Socket:
        def send(self, data: bytes) -> int:
            return 2

        def sendto(self, data: bytes, address: tuple[str, int]) -> int:
            calls.append(address)
            return len(data)

    sink = Sink()
    sink.capture = None
    sink.sock = cast(socket.socket, Socket())
    sink.transport = "tcp"
    assert sink.send(b"abcde") == 2
    assert sink.short_writes == 1
    sink.transport = "udp"
    sink.address = ("127.0.0.1", 12345)
    sink.sendto(b"abc", ("192.0.2.1", 9999))
    assert calls == [("127.0.0.1", 12345)]


def test_protocol_limits_and_budget_skips_are_explicit() -> None:
    assert skip_reason("udp-dnrgb", 65537, "encode", 10000)
    assert skip_reason("openrgb", 65536, "encode", 10000)
    assert skip_reason("adalight", 60, "loopback", 10000)
    assert skip_reason("osc-three", 500000, "loopback", 10000)
    assert skip_reason("ddp", 500000, "loopback", 10000) is None


@pytest.mark.parametrize(
    "options",
    [
        ["--seconds", "nan"],
        ["--fps", "inf"],
        ["--pixels", "0"],
        ["--senders", "bogus"],
        ["--patterns", "bogus"],
        ["--bind", "192.0.2.1"],
        ["--bind", "::1"],
        ["--repeats", "0"],
    ],
)
def test_invalid_arguments_fail_before_running(
    options: list[str], tmp_path: Path
) -> None:
    with pytest.raises(SystemExit):
        parse_args(["--output", str(tmp_path / "results.jsonl"), *options])


def test_sparse_input_changes_only_one_percent_of_pixels() -> None:
    a, b = frame_pair(1000, "sparse")
    assert np.count_nonzero(np.any(a != b, axis=1)) == 10
    np.testing.assert_array_equal(
        frame_pair(60, "static")[0], frame_pair(60, "static")[1]
    )


def test_summaries_keep_profiled_runs_separate_and_ignore_skips() -> None:
    case = {
        "sender": "ddp",
        "pixels": 60,
        "pattern": "dense",
        "mode": "encode",
        "requested_fps": 0,
        "profiled": False,
    }
    rows = [
        case | {"status": "ok", "flush_fps": 100},
        case | {"status": "skipped", "reason": "fixture unavailable"},
        case | {"status": "ok", "profiled": "cpu", "flush_fps": 50},
    ]
    summary = summarize(rows)
    assert len(summary) == 2
    assert summary[0]["metrics"]["flush_fps"]["median"] == 100
    assert summary[0]["issues"] == ["fixture unavailable"]
    assert summary[1]["profiled"] == "cpu"


def test_sender_sampling_excludes_preflight_and_import_stacks() -> None:
    report = summarize_stacks(
        [
            "sender_bench.py:run_case:1;importlib.py:import_module:1 100",
            "sender_bench.py:run_case:1;sender_bench.py:measure_flushes:1;ddp.py:DDPDevice.flush:1 20",
        ],
        ("measure_flushes",),
    )
    assert report["active_samples"] == 20
    assert report["top_self"][0]["frame"] == "ddp.py:DDPDevice.flush"
