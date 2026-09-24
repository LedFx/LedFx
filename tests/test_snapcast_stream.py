"""Tests for SnapcastAudioStream against an in-process fake snapserver.

The fake server's clock runs SERVER_CLOCK_OFFSET seconds ahead of the local
monotonic clock, so these tests also prove that the client's time sync maps
server timestamps back onto local time correctly.
"""

import asyncio
import struct
import threading
import time
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ledfx.snapcast import protocol
from ledfx.snapcast.protocol import MessageType
from ledfx.snapcast.stream import SnapcastAudioStream

try:
    import pyflac
except (ImportError, OSError):
    pyflac = None

RATE = 48000
SERVER_CLOCK_OFFSET = 100.0
BUFFER_MS = 300
TONE_SECONDS = 0.4
CHUNK_SECONDS = 0.02


def server_now():
    return time.monotonic() + SERVER_CLOCK_OFFSET


def _blob(data: bytes) -> bytes:
    return struct.pack("<I", len(data)) + data


def tone(seconds=TONE_SECONDS, amplitude=0.5):
    """Stereo int16 440 Hz tone, shape (samples, 2)."""
    t = np.arange(int(seconds * RATE)) / RATE
    mono = (amplitude * np.sin(2 * np.pi * 440 * t) * 32767).astype(np.int16)
    return np.stack([mono, mono], axis=1)


def wav_header(channels=2, bits=16):
    align = channels * bits // 8
    fmt = struct.pack("<HHIIHH", 1, channels, RATE, RATE * align, align, bits)
    return (
        b"RIFF"
        + struct.pack("<I", 36)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", 16)
        + fmt
        + b"data"
        + struct.pack("<I", 0)
    )


def pcm_stream(samples):
    """Split interleaved int16 audio into (duration, bytes) wire chunks."""
    per_chunk = int(CHUNK_SECONDS * RATE)
    return [
        (len(block) / RATE, block.tobytes())
        for block in (
            samples[i : i + per_chunk]
            for i in range(0, len(samples), per_chunk)
        )
    ]


def flac_stream(samples):
    """Encode audio with pyflac; return (codec header, wire chunks)."""
    header = bytearray()
    chunks = []

    def on_write(data, num_bytes, num_samples, frame):
        if num_samples == 0:
            header.extend(data)
        else:
            chunks.append((num_samples / RATE, bytes(data)))

    encoder = pyflac.StreamEncoder(
        sample_rate=RATE, write_callback=on_write, blocksize=960
    )
    encoder.process(samples)
    encoder.finish()
    return bytes(header), chunks


class FakeSnapserver:
    """Minimal snapserver: answers Hello and Time, then streams chunks in
    real time with server-clock timestamps."""

    def __init__(
        self,
        codec,
        codec_header,
        chunks,
        muted=False,
        drop_connection=False,
        settings=None,
    ):
        self.codec = codec
        self.codec_header = codec_header
        self.chunks = chunks
        self.muted = muted
        self.drop_connection = drop_connection
        self.settings = settings
        self.hellos = []
        self.first_chunk_local_time = None
        self._ready = threading.Event()
        self._handlers = set()

    def __enter__(self):
        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        assert self._ready.wait(5)
        return self

    def __exit__(self, *exc):
        self._loop.call_soon_threadsafe(self._stopping.set)
        self._thread.join(5)

    def _run(self):
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._serve())
        self._loop.close()

    async def _serve(self):
        self._stopping = asyncio.Event()
        server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = server.sockets[0].getsockname()[1]
        self._ready.set()
        await self._stopping.wait()
        server.close()
        for task in self._handlers:
            task.cancel()
        await asyncio.gather(*self._handlers, return_exceptions=True)
        await server.wait_closed()

    def _send(self, writer, msg_type, payload, refers_to=0):
        writer.write(
            protocol.encode_message(
                msg_type, payload, refers_to=refers_to, sent=server_now()
            )
        )

    async def _read(self, reader):
        header = protocol.decode_header(
            await reader.readexactly(protocol.HEADER_SIZE)
        )
        header.received = server_now()
        return header, await reader.readexactly(header.size)

    async def _handle(self, reader, writer):
        self._handlers.add(asyncio.current_task())
        try:
            await self._converse(reader, writer)
        except (asyncio.IncompleteReadError, ConnectionError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except (ConnectionError, asyncio.CancelledError):
                pass

    async def _converse(self, reader, writer):
        header, payload = await self._read(reader)
        assert header.type == MessageType.HELLO
        self.hellos.append(protocol.decode_json(payload))
        if self.drop_connection:
            return

        settings = self.settings or {
            "bufferMs": BUFFER_MS,
            "latency": 0,
            "muted": self.muted,
        }
        self._send(
            writer, MessageType.SERVER_SETTINGS, protocol.encode_json(settings)
        )
        self._send(
            writer,
            MessageType.CODEC_HEADER,
            _blob(self.codec.encode()) + _blob(self.codec_header),
        )
        streaming = asyncio.ensure_future(self._stream_chunks(writer))
        try:
            while True:
                header, payload = await self._read(reader)
                if header.type == MessageType.TIME:
                    latency = header.received - header.sent
                    self._send(
                        writer,
                        MessageType.TIME,
                        protocol.encode_time(latency),
                        refers_to=header.id,
                    )
        finally:
            streaming.cancel()

    async def _stream_chunks(self, writer):
        # Give the client's time sync burst a moment, like a real server
        # whose stream is already running when the client joins.
        await asyncio.sleep(0.2)
        start_local = time.monotonic()
        self.first_chunk_local_time = start_local
        ts = start_local + SERVER_CLOCK_OFFSET
        elapsed = 0.0
        for duration, data in self.chunks:
            self._send(
                writer,
                MessageType.WIRE_CHUNK,
                struct.pack("<ii", *protocol.to_tv(ts)) + _blob(data),
            )
            ts += duration
            elapsed += duration
            await asyncio.sleep(
                max(0, start_local + elapsed - time.monotonic())
            )


class Recorder:
    def __init__(self):
        self.calls = []

    def __call__(self, data, frame_count, time_info, status):
        assert frame_count == len(data)
        self.calls.append(
            (time.monotonic(), len(data), float(np.sqrt(np.mean(data**2))))
        )

    def loud(self):
        return [c for c in self.calls if c[2] > 0.3]


def run_stream(server, seconds, ledfx=None):
    recorder = Recorder()
    stream = SnapcastAudioStream(
        {"host": "127.0.0.1", "port": server.port, "client_name": "Test LEDs"},
        recorder,
        instance_id="abcdef123456",
        ledfx=ledfx,
        name="test-server",
    )
    stream.start()
    try:
        time.sleep(seconds)
    finally:
        stream.close()
    return stream, recorder


def assert_tone_in_sync(server, stream, recorder):
    assert stream._offset == pytest.approx(SERVER_CLOCK_OFFSET, abs=0.005)
    loud = recorder.loud()
    # 0.4 s of tone at 60 blocks/s, allowing for block boundaries
    assert 20 <= len(loud) <= 26
    assert {c[1] for c in loud} == {RATE // 60}
    # Released when the snapserver schedules it to play: bufferMs after it
    # was timestamped
    expected = server.first_chunk_local_time + BUFFER_MS / 1000
    assert loud[0][0] == pytest.approx(expected, abs=0.05)
    assert loud[-1][0] == pytest.approx(expected + TONE_SECONDS, abs=0.06)


class TestSnapcastStream:
    def test_hello_identifies_client(self):
        with FakeSnapserver("pcm", wav_header(), []) as server:
            run_stream(server, 0.3)
        assert server.hellos[0]["ID"] == "ledfx-abcdef12"
        assert server.hellos[0]["HostName"] == "Test LEDs"
        assert server.hellos[0]["ClientName"] == "LedFx"

    def test_pcm_audio_delivered_in_sync(self):
        chunks = pcm_stream(tone())
        with FakeSnapserver("pcm", wav_header(), chunks) as server:
            stream, recorder = run_stream(server, 1.2)
        assert_tone_in_sync(server, stream, recorder)
        assert max(c[2] for c in recorder.calls) == pytest.approx(
            0.5 / np.sqrt(2), abs=0.01
        )

    @pytest.mark.skipif(pyflac is None, reason="pyFLAC not installed")
    def test_flac_audio_delivered_in_sync(self):
        header, chunks = flac_stream(tone())
        with FakeSnapserver("flac", header, chunks) as server:
            stream, recorder = run_stream(server, 1.2)
        assert stream._format == protocol.PcmFormat(RATE, 16, 2)
        assert_tone_in_sync(server, stream, recorder)

    def test_silence_when_muted(self):
        chunks = pcm_stream(tone())
        with FakeSnapserver("pcm", wav_header(), chunks, muted=True) as server:
            _, recorder = run_stream(server, 1.2)
        assert recorder.loud() == []
        # silence keeps flowing at ~60 Hz so effects settle rather than freeze
        assert len(recorder.calls) > 40
        assert all(c[2] == 0 for c in recorder.calls)

    def test_silence_rate_with_coarse_timer(self):
        """Windows timers resolve asyncio.sleep to ~15.6 ms ticks; silence
        must still be delivered at ~60 blocks per second."""
        real_sleep = asyncio.sleep
        tick = 0.0156

        async def coarse_sleep(delay, *args, **kwargs):
            ticks = max(1, -(-delay // tick)) if delay > 0 else 0
            await real_sleep(ticks * tick, *args, **kwargs)

        stream_asyncio = SimpleNamespace(
            **{n: getattr(asyncio, n) for n in dir(asyncio) if n[0] != "_"}
        )
        stream_asyncio.sleep = coarse_sleep
        chunks = pcm_stream(tone())
        with FakeSnapserver("pcm", wav_header(), chunks, muted=True) as server:
            with patch("ledfx.snapcast.stream.asyncio", stream_asyncio):
                _, recorder = run_stream(server, 1.2)
        silent = [c for c in recorder.calls if c[2] == 0]
        span = silent[-1][0] - silent[0][0]
        assert len(silent) / span == pytest.approx(60, abs=6)

    def test_reconnects_after_malformed_settings(self):
        bad_settings = {"bufferMs": "not a number", "latency": 0}
        with FakeSnapserver(
            "pcm", wav_header(), [], settings=bad_settings
        ) as server:
            run_stream(server, 1.5)
        assert len(server.hellos) >= 2

    def test_recovers_from_unexpected_error(self):
        """An unexpected exception must not end the client thread."""
        with FakeSnapserver("pcm", wav_header(), []) as server:
            with patch.object(
                SnapcastAudioStream,
                "_on_codec_header",
                side_effect=RuntimeError("boom"),
            ):
                run_stream(server, 1.5)
        assert len(server.hellos) >= 2

    def test_partial_frame_is_dropped(self):
        stream = SnapcastAudioStream({"host": "x"}, lambda *a: None)
        stream._on_codec_header("pcm", wav_header(channels=2))
        frames = np.array([[16384, 16384]], dtype="<i2").tobytes()
        mono = stream._decode_pcm(frames + b"\x01\x02\x03")
        assert mono == pytest.approx([0.5])

    def test_unsupported_codec_reports_error(self):
        ledfx = SimpleNamespace(events=MagicMock())
        with FakeSnapserver("opus", b"OPUS", []) as server:
            run_stream(server, 0.3, ledfx=ledfx)
        event = ledfx.events.fire_event.call_args.args[0]
        assert event.error_type == "snapcast_codec_unsupported"
        assert event.device_name == "SNAPCAST: test-server"
        assert "opus" in event.message

    def test_reconnects_after_disconnect(self):
        with FakeSnapserver(
            "pcm", wav_header(), [], drop_connection=True
        ) as server:
            run_stream(server, 1.5)
        assert len(server.hellos) >= 2

    def test_close_without_server(self):
        stream = SnapcastAudioStream(
            {"host": "127.0.0.1", "port": 1}, lambda *a: None
        )
        stream.start()
        time.sleep(0.2)
        started = time.monotonic()
        stream.close()
        assert time.monotonic() - started < 1
        assert not stream._thread.is_alive()


class TestTiming:
    """Handler-level checks that don't need a network connection."""

    def make_stream(self):
        stream = SnapcastAudioStream({"host": "x"}, lambda *a: None)
        stream._on_codec_header("pcm", wav_header(channels=1))
        return stream

    def test_clock_offset_from_time_reply(self):
        stream = self.make_stream()
        # Client sent at local 10.0; server (clock +100) received at 110.01
        # and replied at 110.02; client received at local 10.03.
        header = protocol.Header(
            type=MessageType.TIME,
            id=1,
            refers_to=1,
            sent=110.02,
            received=10.03,
            size=8,
        )
        stream._on_time(header, latency=110.01 - 10.0)
        assert stream._offset == pytest.approx(100.0)

    def test_offset_uses_median(self):
        stream = self.make_stream()
        for sample in (1.0, 1.0, 50.0):
            header = protocol.Header(MessageType.TIME, 1, 1, 0.0, 0.0, 8)
            stream._on_time(header, latency=2 * sample)
        assert stream._offset == pytest.approx(1.0)

    def test_blocks_scheduled_at_play_time(self):
        stream = self.make_stream()
        stream._offset = 100.0
        stream._on_server_settings({"bufferMs": 1000, "latency": 200})
        samples = np.zeros(RATE // 60 * 3 + 10, dtype=np.float32)
        stream._schedule(samples, server_ts=150.0)
        times = [t for t, _ in stream._pending]
        # server 150.0 + (1000 - 200) ms buffer -> local 50.8
        assert times == pytest.approx([50.8, 50.8 + 1 / 60, 50.8 + 2 / 60])
        assert len(stream._leftover) == 10

    def test_discontinuity_drops_pending_audio(self):
        stream = self.make_stream()
        stream._offset = 0.0
        block = np.zeros(RATE // 60, dtype="<i2").tobytes()
        stream._on_wire_chunk(10.0, block)
        assert len(stream._pending) == 1
        stream._on_wire_chunk(20.0, block)  # stream jumped 10 s
        assert [t for t, _ in stream._pending] == pytest.approx([21.0])

    @pytest.mark.parametrize(
        "settings", [{"bufferMs": "abc"}, {"latency": None}]
    )
    def test_invalid_settings_are_a_protocol_error(self, settings):
        stream = self.make_stream()
        with pytest.raises(protocol.ProtocolError):
            stream._on_server_settings(settings)
        assert stream._buffer_ms == 1000

    def test_mute_clears_pending_audio(self):
        stream = self.make_stream()
        stream._offset = 0.0
        stream._on_wire_chunk(10.0, np.zeros(RATE, dtype="<i2").tobytes())
        assert stream._pending
        stream._on_server_settings({"muted": True})
        assert not stream._pending
        stream._on_wire_chunk(11.0, np.zeros(RATE, dtype="<i2").tobytes())
        assert not stream._pending

    def test_pcm_downmix(self):
        stream = SnapcastAudioStream({"host": "x"}, lambda *a: None)
        stream._on_codec_header("pcm", wav_header(channels=2))
        frames = np.array([[16384, -16384], [16384, 16384]], dtype="<i2")
        mono = stream._decode_pcm(frames.tobytes())
        assert mono == pytest.approx([0.0, 0.5])
