"""The audio process: framing, the worker's commands, and a real spawned
process whose results must equal in-process analysis exactly."""

import socket
import threading
import time

import pytest

from ledfx.audio_process import client as client_module
from ledfx.audio_process import protocol
from ledfx.audio_process.client import AudioProcessClient, AudioProcessError
from ledfx.audio_process.worker import AudioWorker
from ledfx.configuration.models import AudioConfig
from ledfx.effects.audio_analyzer import AudioAnalyzer, SnapshotView
from tests.test_audio_analyzer import (
    FakeClock,
    analyzer_values,
    assert_same,
    make_signal,
    make_source,
)

# -- protocol -------------------------------------------------------------


def roundtrip(message):
    a, b = socket.socketpair()
    try:
        protocol.send(a, message)
        return protocol.recv(b)
    finally:
        a.close()
        b.close()


def test_protocol_roundtrip_with_nested_blobs():
    message = {
        "t": "snapshot",
        "s": {
            "x": 1.5,
            "flags": [True, False],
            "melbanks": [b"\x00\x01", b""],
            "n": None,
        },
        "data": bytearray(b"abc"),
    }
    got = roundtrip(message)
    assert got["s"]["melbanks"] == [b"\x00\x01", b""]
    assert got["data"] == b"abc"
    assert got["s"]["x"] == 1.5
    assert got["s"]["flags"] == [True, False]
    assert got["s"]["n"] is None


def test_protocol_rejects_dangling_blob_reference():
    a, b = socket.socketpair()
    try:
        header = b'{"x":{"__blob__":3}}'
        body = protocol._LEN.pack(len(header)) + header + protocol._LEN.pack(0)
        a.sendall(protocol._LEN.pack(len(body)) + body)
        with pytest.raises(protocol.ProtocolError):
            protocol.recv(b)
    finally:
        a.close()
        b.close()


def test_protocol_rejects_a_body_that_does_not_match_its_fields():
    header = b'{"x":1}'
    body = protocol._LEN.pack(len(header)) + header + protocol._LEN.pack(1)
    with pytest.raises(protocol.ProtocolError):
        protocol.decode(body)  # announces one blob, carries none
    with pytest.raises(protocol.ProtocolError):
        protocol.decode(body[:-4] + protocol._LEN.pack(0) + b"extra")


class CountingSocket:
    def __init__(self, sock):
        self._sock = sock
        self.reads = 0

    def recv_into(self, *args):
        self.reads += 1
        return self._sock.recv_into(*args)


def test_protocol_reads_a_whole_snapshot_in_two_reads():
    """Every socket read gives up the interpreter lock, and in a busy LedFx
    getting it back costs up to a switch interval, so reads per message are
    what a snapshot costs the reader there."""
    a, b = socket.socketpair()
    try:
        protocol.send(a, {"t": "snapshot", "s": base_snapshot()})
        counting = CountingSocket(b)
        got = protocol.recv(counting)
        assert got["t"] == "snapshot"
        assert len(got["s"]["melbanks"]) > 0
        assert counting.reads == 2
    finally:
        a.close()
        b.close()


def test_protocol_reports_closed_peer():
    a, b = socket.socketpair()
    a.close()
    with pytest.raises(ConnectionError):
        protocol.recv(b)
    b.close()


# -- snapshot -------------------------------------------------------------


def test_snapshot_view_carries_every_result_exactly():
    clock = FakeClock()
    config = AudioConfig.model_validate({}).model_dump()
    src = make_source(config)
    an = AudioAnalyzer(*src._analyzer_args())
    for block in make_signal()[:200]:
        clock.tick()
        if an.process(block):
            view = SnapshotView(roundtrip({"s": an.snapshot()})["s"])
            assert_same(analyzer_values(an), analyzer_values(view), "snapshot")


# -- worker commands (in a thread, fake audio module) ------------------------


class FakeStream:
    def __init__(self, **kwargs):
        self.kwargs = kwargs
        self.started = False

    def start(self):
        self.started = True

    def stop(self):
        self.started = False

    def close(self):
        pass


class FakeSounddevice:
    def __init__(self):
        self.opened = []

    def query_hostapis(self):
        return [{"name": "MME"}, {"name": "Windows WASAPI"}]

    def query_devices(self):
        return [
            {"name": "Speakers", "hostapi": 0, "max_input_channels": 0},
            {"name": "Microphone", "hostapi": 1, "max_input_channels": 1},
            {"name": "Line In", "hostapi": 1, "max_input_channels": 2},
        ]

    def InputStream(self, **kwargs):
        stream = FakeStream(**kwargs)
        self.opened.append(stream)
        return stream


def worker_pair():
    a, b = socket.socketpair()
    sd = FakeSounddevice()
    w = AudioWorker(b, sd)
    t = threading.Thread(target=w.serve, daemon=True)
    t.start()
    return a, sd, t


def test_worker_opens_device_by_name_when_index_drifted():
    a, sd, t = worker_pair()
    protocol.send(
        a,
        {
            "t": "open",
            "id": 1,
            "device": 1,
            "device_name": "Windows WASAPI: Line In",
            "samplerate": 48000,
            "blocksize": 800,
            "channels": 1,
        },
    )
    reply = protocol.recv(a)
    assert reply == {"t": "opened", "id": 1, "device": 2}
    assert sd.opened[0].kwargs["device"] == 2
    assert sd.opened[0].started
    protocol.send(a, {"t": "quit"})
    a.close()
    t.join(3)


def test_worker_refuses_unknown_device_instead_of_another():
    a, sd, t = worker_pair()
    protocol.send(
        a,
        {
            "t": "open",
            "id": 7,
            "device": 1,
            "device_name": "Windows WASAPI: Gone",
            "samplerate": 48000,
            "blocksize": 800,
            "channels": 1,
        },
    )
    reply = protocol.recv(a)
    assert reply["t"] == "open_failed"
    assert reply["id"] == 7
    assert "Gone" in reply["error"]
    assert sd.opened == []
    a.close()
    t.join(3)


# -- token ----------------------------------------------------------------


def test_client_rejects_a_connection_without_the_token(monkeypatch):
    """Something else connects first; only the real worker is accepted."""
    started = {}

    def launcher(port, token):
        def connect():
            intruder = socket.create_connection(("127.0.0.1", port))
            protocol.send(intruder, {"t": "hello", "token": "wrong"})
            started["intruder"] = intruder
            real = socket.create_connection(("127.0.0.1", port))
            protocol.send(real, {"t": "hello", "token": token})
            started["real"] = real

        threading.Thread(target=connect, daemon=True).start()

    monkeypatch.setattr(client_module, "_launcher", launcher)
    c = AudioProcessClient(lambda view: None)
    c.start(timeout=5)
    try:
        assert c.alive
        # The intruder was closed by the client.
        started["intruder"].settimeout(3)
        assert started["intruder"].recv(1) == b""
    finally:
        c.stop()
        started["real"].close()


def test_client_gives_up_when_nothing_connects(monkeypatch):
    monkeypatch.setattr(client_module, "_launcher", lambda port, token: None)
    c = AudioProcessClient(lambda view: None)
    with pytest.raises(AudioProcessError):
        c.start(timeout=0.5)


# -- a real audio process -------------------------------------------------------


def test_spawned_process_matches_in_process_analysis_exactly(monkeypatch):
    """Blocks go to a real separate interpreter and come back as results that
    the source's getters expose identically to in-process analysis.

    time.time is not shared with the child, so values that depend on the wall
    clock (bar oscillator, volume beat) are left out here; the in-process
    tests cover them with a fake clock.
    """
    config = AudioConfig.model_validate({}).model_dump()
    blocks = make_signal()[:240]

    local = AudioAnalyzer(*make_source(config)._analyzer_args())
    expected = []
    for block in blocks:
        if local.process(block):
            expected.append(analyzer_values(local))

    src = make_source(config)
    got = []
    arrived = threading.Event()

    def on_results(view):
        src._apply_results(view)
        got.append(clock_free(source_like(src)))
        arrived.set()

    c = AudioProcessClient(on_results)
    c.start()
    try:
        c.configure(*src._analyzer_args())
        for block in blocks:
            arrived.clear()
            before = len(got)
            c.push(block)
            # Wait for this block's result, or for nothing (first block is
            # swallowed by the resampler), before sending the next.
            arrived.wait(2)
            assert len(got) - before in (0, 1)
    finally:
        c.stop()

    assert len(got) == len(expected) > 200
    for i, (e, g) in enumerate(zip(expected, got, strict=True)):
        assert_same(clock_free(e), g, f"block {i}")


CLOCK_DEPENDENT = ("bar_oscillator", "beat_oscillator", "volume_beat_now")


def clock_free(values):
    return {k: v for k, v in values.items() if k not in CLOCK_DEPENDENT}


def source_like(src):
    from tests.test_audio_analyzer import source_values

    return source_values(src)


def base_snapshot():
    an = AudioAnalyzer(
        *make_source(AudioConfig.model_validate({}).model_dump())._analyzer_args()
    )
    for block in make_signal()[:5]:
        an.process(block)
    return an.snapshot()


def nothing_arrives(sock, wait=0.3):
    sock.settimeout(wait)
    try:
        sock.recv(1)
    except TimeoutError:
        return True
    finally:
        sock.settimeout(None)
    return False


def test_worker_sends_only_the_newest_snapshot_when_asked():
    """A reader that is behind gets fresh values and every event, never a
    backlog: unasked snapshots replace each other, flags ORed together."""
    a, b = socket.socketpair()
    w = AudioWorker(b, FakeSounddevice())
    t = threading.Thread(target=w.serve, daemon=True)
    t.start()
    base = base_snapshot()
    w._offer(dict(base, onset=True, bpm_beat_now=False, volume_beat_now=False, pitch=1.0))
    w._offer(dict(base, onset=False, bpm_beat_now=True, volume_beat_now=False, pitch=2.0))
    assert nothing_arrives(a)

    protocol.send(a, {"t": "next"})
    s = protocol.recv(a)["s"]
    assert s["pitch"] == 2.0
    assert (s["onset"], s["bpm_beat_now"], s["volume_beat_now"]) == (True, True, False)

    # Asked once, sent once: the next snapshot waits for the next request.
    w._offer(dict(base, onset=False, bpm_beat_now=False, volume_beat_now=False, pitch=3.0))
    assert nothing_arrives(a)
    protocol.send(a, {"t": "next"})
    s = protocol.recv(a)["s"]
    assert s["pitch"] == 3.0
    assert (s["onset"], s["bpm_beat_now"], s["volume_beat_now"]) == (False, False, False)
    protocol.send(a, {"t": "quit"})
    a.close()
    t.join(3)
    assert not t.is_alive()


def test_reader_asks_for_the_next_snapshot_before_handling_this_one():
    a, b = socket.socketpair()
    handling = threading.Event()
    release = threading.Event()
    seen = []

    def on_results(view):
        seen.append(view)
        handling.set()
        release.wait(3)

    c = AudioProcessClient(on_results)
    c._sock = b
    c.alive = True
    reader = threading.Thread(target=c._read_loop, daemon=True)
    reader.start()
    protocol.send(a, {"t": "snapshot", "s": dict(base_snapshot(), pitch=5.0)})
    # on_results blocks until release; a request sent only after it would
    # miss this timeout.
    a.settimeout(1)
    assert protocol.recv(a) == {"t": "next"}
    a.settimeout(None)
    assert handling.wait(3)
    release.set()
    a.close()
    reader.join(3)
    assert [v.pitch for v in seen] == [5.0]
