"""Snapcast audio stream implementation for LedFx.

Connects to a snapserver as a regular Snapcast client and feeds the received
audio to LedFx's AudioInputSource.  Audio is released to LedFx at the moment
the snapserver schedules it to be played, so visualisation stays in sync with
the speakers of the other clients in the same group.
"""

import asyncio
import collections
import logging
import platform
import socket
import statistics
import threading
from typing import Callable

import numpy as np

from ledfx.consts import PROJECT_VERSION
from ledfx.events import AudioSourceErrorEvent
from ledfx.snapcast import protocol
from ledfx.snapcast.config import DEFAULT_CLIENT_NAME, DEFAULT_PORT
from ledfx.snapcast.protocol import MessageType

try:
    import pyflac
except (ImportError, OSError):
    pyflac = None

_LOGGER = logging.getLogger(__name__)

# Audio is delivered to LedFx in blocks of sample_rate / 60 samples so the
# FFT / beat detection runs at ~60 Hz, the same as a local input device.
_BLOCKS_PER_SECOND = 60


class SnapcastAudioStream:
    """
    Audio stream that receives audio from a snapserver and feeds LedFx.

    Implements the same interface as WebAudioStream / SendspinAudioStream
    (start / stop / close) to work with LedFx's AudioInputSource system.

    Args:
        config: Configuration dict with host, port and client_name.
        callback: LedFx's _audio_sample_callback(data, frame_count, time_info, status)
        instance_id: Persistent LedFx installation UUID.  Used to form a
            stable client ID so the snapserver remembers this client's name,
            group, volume and latency across restarts.
        ledfx: LedFx core instance, used to report errors to the frontend.
        name: Server id, used to name this source in error reports.
    """

    CONNECT_TIMEOUT = 5.0
    # Snapserver answers a time sync request every second, so a connection
    # with no traffic for this long is dead.
    READ_TIMEOUT = 10.0
    MAX_BACKOFF = 30.0
    # Time sync: a quick burst to converge, then one request per second
    TIME_SYNC_BURST = 10
    TIME_SYNC_BURST_INTERVAL = 0.1
    TIME_SYNC_INTERVAL = 1.0
    TIME_SYNC_SAMPLES = 50
    # Consecutive chunks further apart than this are a stream discontinuity
    MAX_CHUNK_GAP = 0.5
    # Audio released later than this is stale and dropped
    MAX_LATE = 0.1
    # Feed silence once no audio has been due for this long, so effects
    # settle when the stream is idle or muted instead of freezing
    SILENCE_AFTER = 0.25
    DEFAULT_SAMPLE_RATE = 48000

    def __init__(
        self,
        config: dict,
        callback: Callable,
        instance_id: str = "",
        ledfx=None,
        name: str = "",
    ):
        self.config = config
        self._device_name = f"SNAPCAST: {name}" if name else "SNAPCAST"
        self.callback = callback
        self._ledfx = ledfx
        self._client_id = f"ledfx-{instance_id[:8] or socket.gethostname()}"

        self._active = False
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._main_task: asyncio.Task | None = None
        self._writer: asyncio.StreamWriter | None = None
        self._msg_id = 0

        # Server settings (updated by ServerSettings messages)
        self._buffer_ms = 1000
        self._latency_ms = 0
        self._muted = False

        # Clock sync: server clock minus local clock, in seconds
        self._offsets = collections.deque(maxlen=self.TIME_SYNC_SAMPLES)
        self._offset: float | None = None

        # Stream format (from CodecHeader)
        self._codec: str | None = None
        self._codec_header = b""
        self._format: protocol.PcmFormat | None = None
        self._last_chunk_ts: float | None = None

        # FLAC decoding runs on pyflac's own thread, so decoded blocks are
        # timestamped by counting samples from an anchor chunk rather than
        # by matching them to the chunk they came from.
        self._flac_decoder = None
        self._flac_anchor_ts = 0.0
        self._flac_samples = 0

        # Decoded audio waiting to be released: (local play time, samples)
        self._pending = collections.deque()
        self._pending_lock = threading.Lock()
        self._leftover = np.array([], dtype=np.float32)
        self._leftover_ts = 0.0

        _LOGGER.info(
            "Snapcast stream initialized for server %s:%s (id=%s)",
            config.get("host", "unknown"),
            config.get("port", DEFAULT_PORT),
            id(self),
        )

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def start(self):
        """Start receiving audio from the snapserver."""
        if self._active:
            _LOGGER.warning("Snapcast stream already active")
            return
        self._active = True
        self._thread = threading.Thread(
            target=self._run, daemon=True, name="SnapcastAudioThread"
        )
        self._thread.start()

    def stop(self):
        """Stop receiving audio. Safe to call multiple times."""
        if not self._active:
            return
        self._active = False
        loop, task = self._loop, self._main_task
        if loop is not None and task is not None and loop.is_running():
            try:
                loop.call_soon_threadsafe(task.cancel)
            except RuntimeError:
                pass  # loop closed in the meantime

    def close(self):
        """Stop and wait for the background thread to exit."""
        self.stop()
        if self._thread is not None and self._thread.is_alive():
            self._thread.join(timeout=5.0)
            if self._thread.is_alive():
                _LOGGER.error(
                    "Snapcast thread did not exit within 5 s (id=%s)", id(self)
                )
        self._finish_flac_decoder()
        _LOGGER.info("Snapcast stream closed (id=%s)", id(self))

    # ------------------------------------------------------------------
    # Connection handling
    # ------------------------------------------------------------------

    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._main_task = self._loop.create_task(self._reconnect_loop())
            # stop() may have been called before the task existed
            if not self._active:
                self._main_task.cancel()
            self._loop.run_until_complete(self._main_task)
        except asyncio.CancelledError:
            pass
        except Exception as exc:
            _LOGGER.error("Snapcast client error: %s", exc, exc_info=True)
        finally:
            self._main_task = None
            self._loop.close()

    async def _reconnect_loop(self):
        backoff = 1.0
        while self._active:
            host = self.config.get("host")
            port = self.config.get("port", DEFAULT_PORT)
            try:
                await self._connect_and_receive(host, port)
                backoff = 1.0
            except asyncio.CancelledError:
                raise
            except (OSError, asyncio.TimeoutError) as exc:
                _LOGGER.warning(
                    "Snapcast connection to %s:%s lost, retrying in %.0fs: %s",
                    host,
                    port,
                    backoff,
                    exc or type(exc).__name__,
                )
            except protocol.ProtocolError as exc:
                _LOGGER.warning(
                    "Snapcast protocol error from %s:%s, reconnecting in "
                    "%.0fs: %s",
                    host,
                    port,
                    backoff,
                    exc,
                )
            if not self._active:
                break
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, self.MAX_BACKOFF)

    async def _connect_and_receive(self, host, port):
        _LOGGER.info(
            "Connecting to snapserver %s:%s as '%s' (client id %s)",
            host,
            port,
            self.config.get("client_name", DEFAULT_CLIENT_NAME),
            self._client_id,
        )
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), self.CONNECT_TIMEOUT
        )
        self._writer = writer
        self._reset_stream_state()
        tasks = []
        try:
            self._send(
                MessageType.HELLO,
                protocol.encode_hello(
                    client_id=self._client_id,
                    host_name=self.config.get(
                        "client_name", DEFAULT_CLIENT_NAME
                    ),
                    version=PROJECT_VERSION,
                    os_name=platform.system(),
                    arch=platform.machine(),
                ),
            )
            tasks.append(asyncio.ensure_future(self._time_sync_loop()))
            tasks.append(asyncio.ensure_future(self._playback_scheduler()))
            _LOGGER.info("Connected to snapserver %s:%s", host, port)

            while self._active:
                raw = await asyncio.wait_for(
                    reader.readexactly(protocol.HEADER_SIZE),
                    self.READ_TIMEOUT,
                )
                header = protocol.decode_header(raw)
                header.received = self._loop.time()
                payload = await asyncio.wait_for(
                    reader.readexactly(header.size), self.READ_TIMEOUT
                )
                self._handle_message(header, payload)
        except asyncio.IncompleteReadError as exc:
            raise ConnectionResetError(
                "snapserver closed the connection"
            ) from exc
        finally:
            for task in tasks:
                task.cancel()
            await asyncio.gather(*tasks, return_exceptions=True)
            self._writer = None
            writer.close()
            try:
                await writer.wait_closed()
            except Exception:
                pass
            self._finish_flac_decoder()

    def _send(self, msg_type, payload, refers_to=0):
        if self._writer is None:
            return
        self._msg_id = (self._msg_id + 1) & 0xFFFF
        self._writer.write(
            protocol.encode_message(
                msg_type,
                payload,
                msg_id=self._msg_id,
                refers_to=refers_to,
                sent=self._loop.time(),
            )
        )

    async def _time_sync_loop(self):
        for _ in range(self.TIME_SYNC_BURST):
            self._send(MessageType.TIME, protocol.encode_time())
            await asyncio.sleep(self.TIME_SYNC_BURST_INTERVAL)
        while True:
            self._send(MessageType.TIME, protocol.encode_time())
            await asyncio.sleep(self.TIME_SYNC_INTERVAL)

    def _reset_stream_state(self):
        self._offsets.clear()
        self._offset = None
        self._codec = None
        self._format = None
        self._last_chunk_ts = None
        self._clear_pending()

    def _clear_pending(self):
        with self._pending_lock:
            self._pending.clear()
            self._leftover = np.array([], dtype=np.float32)

    # ------------------------------------------------------------------
    # Message handling
    # ------------------------------------------------------------------

    def _handle_message(self, header, payload):
        if header.type == MessageType.WIRE_CHUNK:
            self._on_wire_chunk(*protocol.decode_wire_chunk(payload))
        elif header.type == MessageType.TIME:
            self._on_time(header, protocol.decode_time(payload))
        elif header.type == MessageType.CODEC_HEADER:
            self._on_codec_header(*protocol.decode_codec_header(payload))
        elif header.type == MessageType.SERVER_SETTINGS:
            self._on_server_settings(protocol.decode_json(payload))
        else:
            _LOGGER.debug("Ignoring snapcast message type %s", header.type)

    def _on_time(self, header, latency):
        # latency = server receive - client send (c2s transit + offset)
        # s2c     = client receive - server send (s2c transit - offset)
        # With symmetric transit, (c2s - s2c) / 2 is the clock offset.
        s2c = header.received - header.sent
        self._offsets.append((latency - s2c) / 2)
        self._offset = statistics.median(self._offsets)

    def _on_server_settings(self, settings):
        self._buffer_ms = int(settings.get("bufferMs", self._buffer_ms))
        self._latency_ms = int(settings.get("latency", self._latency_ms))
        muted = bool(settings.get("muted", False))
        if muted and not self._muted:
            self._clear_pending()
        self._muted = muted
        _LOGGER.info(
            "Snapcast server settings: buffer=%dms latency=%dms muted=%s",
            self._buffer_ms,
            self._latency_ms,
            self._muted,
        )

    def _on_codec_header(self, codec, header):
        self._finish_flac_decoder()
        self._clear_pending()
        self._codec = codec
        self._codec_header = header
        self._format = None
        self._last_chunk_ts = None
        try:
            if codec == "pcm":
                self._format = protocol.parse_wav_header(header)
            elif codec == "flac":
                if pyflac is None:
                    self._report_error(
                        "snapcast_codec_unavailable",
                        "The snapserver stream uses FLAC, but pyFLAC is not "
                        "installed. Install pyFLAC or set the stream codec to "
                        "pcm.",
                    )
                    return
                self._format = protocol.parse_flac_header(header)
            else:
                self._report_error(
                    "snapcast_codec_unsupported",
                    f"The snapserver stream uses the '{codec}' codec, which "
                    "LedFx does not support. Set the stream codec to flac or "
                    "pcm in snapserver.conf.",
                )
                return
        except protocol.ProtocolError as exc:
            self._report_error(
                "snapcast_codec_invalid",
                f"Could not read the snapserver '{codec}' stream header: {exc}",
            )
            return
        _LOGGER.info(
            "Snapcast stream format: %s %dHz %dbit %dch",
            codec,
            self._format.sample_rate,
            self._format.bit_depth,
            self._format.channels,
        )

    def _on_wire_chunk(self, timestamp, data):
        if self._format is None or self._muted:
            return

        # A jump in the stream (server restarted it, or it resumed after
        # being idle) invalidates the FLAC sample-count timeline.
        last = self._last_chunk_ts
        self._last_chunk_ts = timestamp
        discontinuity = last is not None and not (
            0 <= timestamp - last <= self.MAX_CHUNK_GAP
        )

        if self._codec == "pcm":
            if discontinuity:
                self._clear_pending()
            self._schedule(self._decode_pcm(data), timestamp)
            return

        if discontinuity:
            self._finish_flac_decoder()
            self._clear_pending()
        if self._flac_decoder is None:
            self._init_flac_decoder(timestamp)
        self._flac_decoder.process(data)

    # ------------------------------------------------------------------
    # Decoding
    # ------------------------------------------------------------------

    def _decode_pcm(self, data):
        fmt = self._format
        if fmt.bit_depth == 16:
            audio = np.frombuffer(data, dtype="<i2").astype(np.float32)
        elif fmt.bit_depth == 24:
            raw = np.frombuffer(data, dtype=np.uint8).reshape(-1, 3)
            audio = (
                raw[:, 0].astype(np.int32)
                | (raw[:, 1].astype(np.int32) << 8)
                | (raw[:, 2].astype(np.int8).astype(np.int32) << 16)
            ).astype(np.float32)
        elif fmt.bit_depth == 32:
            audio = np.frombuffer(data, dtype="<i4").astype(np.float32)
        else:
            raise protocol.ProtocolError(
                f"unsupported pcm bit depth {fmt.bit_depth}"
            )
        audio /= float(1 << (fmt.bit_depth - 1))
        return self._to_mono(audio, fmt.channels)

    @staticmethod
    def _to_mono(audio, channels):
        if channels > 1:
            usable = len(audio) - len(audio) % channels
            audio = audio[:usable].reshape(-1, channels).mean(axis=1)
        return audio.astype(np.float32, copy=False)

    def _init_flac_decoder(self, anchor_ts):
        self._flac_anchor_ts = anchor_ts
        self._flac_samples = 0
        self._flac_decoder = pyflac.StreamDecoder(
            write_callback=self._flac_write_callback
        )
        self._flac_decoder.process(self._codec_header)

    def _finish_flac_decoder(self):
        decoder, self._flac_decoder = self._flac_decoder, None
        if decoder is None:
            return
        try:
            decoder.finish()
        except Exception as exc:
            _LOGGER.debug("FLAC decoder finish failed: %s", exc)

    def _flac_write_callback(
        self, audio, sample_rate, num_channels, num_samples
    ):
        """Called by pyflac on its decoder thread for each decoded frame."""
        try:
            timestamp = self._flac_anchor_ts + self._flac_samples / sample_rate
            self._flac_samples += num_samples
            scale = float(1 << (self._format.bit_depth - 1))
            mono = self._to_mono(
                audio.reshape(-1).astype(np.float32) / scale, num_channels
            )
            self._schedule(mono, timestamp)
        except Exception as exc:
            _LOGGER.error("Error in snapcast FLAC callback: %s", exc)

    # ------------------------------------------------------------------
    # Playback scheduling
    # ------------------------------------------------------------------

    def _play_delay(self):
        return (self._buffer_ms - self._latency_ms) / 1000

    def _schedule(self, samples, server_ts):
        """Split decoded mono audio into LedFx-sized blocks and queue each
        one for release at its local play time."""
        offset = self._offset
        if offset is None or self._format is None:
            return  # clock not synced yet; audio cannot be placed in time
        rate = self._format.sample_rate
        block = rate // _BLOCKS_PER_SECOND
        play_time = server_ts + self._play_delay() - offset

        with self._pending_lock:
            if len(self._leftover):
                samples = np.concatenate([self._leftover, samples])
                play_time = self._leftover_ts
            n_blocks = len(samples) // block
            for i in range(n_blocks):
                self._pending.append(
                    (
                        play_time + i * block / rate,
                        samples[i * block : (i + 1) * block],
                    )
                )
            self._leftover = samples[n_blocks * block :].copy()
            self._leftover_ts = play_time + n_blocks * block / rate

    async def _playback_scheduler(self):
        """Release queued audio to LedFx at its play time, and feed silence
        when nothing is playing."""
        last_release = self._loop.time()
        silence_next = 0.0
        while True:
            now = self._loop.time()
            due = None
            with self._pending_lock:
                while self._pending and self._pending[0][0] <= now:
                    play_time, samples = self._pending.popleft()
                    if now - play_time <= self.MAX_LATE:
                        due = samples
                        break
                next_time = self._pending[0][0] if self._pending else None

            if due is not None:
                self._deliver(due)
                last_release = now
                continue

            if (
                now - last_release >= self.SILENCE_AFTER
                and now >= silence_next
            ):
                rate = (
                    self._format.sample_rate
                    if self._format
                    else self.DEFAULT_SAMPLE_RATE
                )
                self._deliver(
                    np.zeros(rate // _BLOCKS_PER_SECOND, dtype=np.float32)
                )
                silence_next = now + 1 / _BLOCKS_PER_SECOND

            wait = 0.005
            if next_time is not None:
                wait = min(wait, max(0.0, next_time - now))
            await asyncio.sleep(wait)

    def _deliver(self, samples):
        try:
            self.callback(samples, len(samples), None, None)
        except Exception as exc:
            _LOGGER.error(
                "Error in LedFx audio callback: %s", exc, exc_info=True
            )

    def _report_error(self, error_type, message):
        _LOGGER.error("Snapcast: %s", message)
        if self._ledfx is not None:
            self._ledfx.events.fire_event(
                AudioSourceErrorEvent(
                    error_type=error_type,
                    message=message,
                    device_name=self._device_name,
                )
            )
