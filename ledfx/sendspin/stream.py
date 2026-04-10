"""Sendspin audio stream implementation for LedFx.

This module implements the audio stream interface expected by LedFx's AudioInputSource,
receiving audio from a Sendspin server and converting it to LedFx's expected format.
"""

import asyncio
import heapq
import logging
import threading
from typing import Callable, Optional

import numpy as np

from ledfx.sendspin.config import BUFFER_CAPACITY

try:
    import pyflac
except ImportError:
    pyflac = None

try:
    from aiosendspin.client import AudioFormat, SendspinClient
    from aiosendspin.models import AudioCodec, PlayerCommand, Roles
    from aiosendspin.models.player import (
        ClientHelloPlayerSupport,
        SupportedAudioFormat,
    )
except ImportError:
    # Python < 3.12 or aiosendspin not available
    SendspinClient = None
    AudioFormat = None

_LOGGER = logging.getLogger(__name__)

# Maximum samples per sub-chunk delivered to LedFx.
# Large FLAC frames (e.g. 4608 samples = 96ms) are split into pieces
# of this size so the FFT / beat-detection updates at ~60 Hz,
# matching sounddevice's blocksize = device_rate / sample_rate
# (e.g. 44100/60 = 735 for local mic, 48000/60 = 800 for Sendspin).
_SUB_CHUNK_SAMPLES = 800  # ~16.7 ms at 48 kHz → 60 Hz update rate


class SendspinAudioStream:
    """
    Audio stream that receives Sendspin audio chunks and feeds LedFx.

    Implements the same interface as WebAudioStream to work with LedFx's
    AudioInputSource system.

    Args:
        config: Configuration dict with server_url, client_name, etc.
        callback: LedFx's _audio_sample_callback(data, frame_count, time_info, status)
        server_id: Stable identifier for this server config entry, used to
            generate a persistent client_id across reconnections (spec requirement).
    """

    def __init__(self, config: dict, callback: Callable, server_id: str = ""):
        if SendspinClient is None:
            raise ImportError(
                "aiosendspin not available (requires Python 3.12+)"
            )

        self.config = config
        self.callback = callback
        self._server_id = server_id
        self._active = False
        self._client: Optional[SendspinClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

        # Timestamp-sorted playback buffer: heap of (play_time_us, seq, audio)
        self._chunk_buffer: list[tuple[int, int, np.ndarray]] = []
        self._chunk_seq = 0
        self._buffer_lock = threading.Lock()
        self._scheduler_task: Optional[asyncio.Task] = None

        # FLAC decoder (persistent across chunks within a stream).
        # Recreated on _stream_start_handler; None until first FLAC chunk.
        self._flac_decoder = None  # pyflac.StreamDecoder instance
        self._flac_bit_depth: int = 16  # bit depth negotiated with server
        self._flac_fmt_logged: bool = False
        # Timing context for the pyFLAC write callback.
        # These are set immediately before each decoder.process() call so
        # the callback can stamp every decoded PCM block with the correct
        # play timestamp, even when one compressed chunk yields multiple
        # callback invocations.
        self._flac_pending_play_time_us: int = 0
        self._flac_pending_sample_rate: int = 48000
        self._flac_pending_samples_emitted: int = 0

        # Leftover samples from previous frame, carried over so every
        # callback receives exactly _SUB_CHUNK_SAMPLES samples.
        self._leftover = np.array([], dtype=np.float32)
        self._leftover_ts = 0  # play-time (us) of leftover samples

        _LOGGER.info(
            "Sendspin stream initialized for server: %s",
            config.get("server_url", "unknown"),
        )

    def _audio_chunk_handler(
        self, timestamp: int, chunk_data: bytes, audio_format: AudioFormat
    ):
        """
        Called by aiosendspin when an audio chunk arrives.

        Converts the audio to float32 mono and inserts it into a
        timestamp-sorted buffer.  The scheduler loop releases chunks
        to LedFx at the correct play time so visualisation stays in
        sync with speakers playing the same stream.

        Args:
            timestamp: Server timestamp in microseconds (raw, not offset-adjusted)
            chunk_data: Raw audio bytes from Sendspin
            audio_format: Audio format description for this chunk
        """
        if not self._active or self._client is None:
            return

        try:
            play_time_us = self._client.compute_play_time(timestamp)
            sample_rate = audio_format.pcm_format.sample_rate

            if audio_format.codec == AudioCodec.FLAC:
                # pyFLAC path: decoded PCM is delivered to
                # _flac_write_callback which calls _schedule_mono_samples
                # directly.  Set the timing context before process() so the
                # callback can timestamp each decoded PCM block correctly,
                # even when one compressed chunk produces multiple blocks.
                if self._flac_decoder is None:
                    self._init_flac_decoder(audio_format)
                self._flac_pending_play_time_us = play_time_us
                self._flac_pending_sample_rate = sample_rate
                self._flac_pending_samples_emitted = 0
                self._flac_decoder.process(chunk_data)
            else:
                # PCM path: decode synchronously then schedule.
                audio_float32 = self._convert_to_float32_mono(
                    chunk_data, audio_format
                )
                self._schedule_mono_samples(audio_float32, play_time_us, sample_rate)

        except Exception as e:
            _LOGGER.error("Error processing audio chunk: %s", e, exc_info=True)

    def _schedule_mono_samples(
        self,
        samples: np.ndarray,
        play_time_us: int,
        sample_rate: int,
    ) -> None:
        """
        Schedule decoded mono float32 samples into the heap playback buffer.

        Extracted so both the PCM path and the callback-driven FLAC backend
        (Stage 2) share identical leftover-handling and scheduling logic
        without duplication.  Keeping the scheduling in one place also means
        the FLAC backend can be purely callback-driven (pyFLAC fires this
        from within process()) without any duplicate heap/leftover state.

        Args:
            samples:      Mono float32 numpy array of decoded audio.
            play_time_us: Intended play time (µs) for the first sample in
                          *samples*.  Ignored when leftover samples from the
                          previous chunk are prepended – in that case the
                          leftover's saved timestamp is used as the base.
            sample_rate:  Sample rate of *samples* in Hz.
        """
        sub_duration_us = int(_SUB_CHUNK_SAMPLES / sample_rate * 1_000_000)
        now_us = int(self._loop.time() * 1_000_000)

        # Prepend any leftover samples from the previous frame and use
        # the leftover's original timestamp as the base so carryover
        # samples keep their scheduled play time.
        if len(self._leftover) > 0:
            samples = np.concatenate([self._leftover, samples])
            base_ts = self._leftover_ts
            self._leftover = np.array([], dtype=np.float32)
        else:
            base_ts = play_time_us

        total_samples = len(samples)
        n_full = total_samples // _SUB_CHUNK_SAMPLES
        remainder = total_samples % _SUB_CHUNK_SAMPLES

        # Per-sub-chunk late check: drop only sub-chunks whose play time
        # is already in the past instead of discarding the entire packet.
        if n_full > 0:
            with self._buffer_lock:
                for i in range(n_full):
                    sub_play = base_ts + i * sub_duration_us
                    if sub_play < now_us:
                        continue
                    start = i * _SUB_CHUNK_SAMPLES
                    end = start + _SUB_CHUNK_SAMPLES
                    self._chunk_seq += 1
                    heapq.heappush(
                        self._chunk_buffer,
                        (
                            sub_play,
                            self._chunk_seq,
                            samples[start:end].copy(),
                        ),
                    )

        # Save leftover samples with their scheduled play time.
        if remainder > 0:
            self._leftover = samples[n_full * _SUB_CHUNK_SAMPLES :].copy()
            self._leftover_ts = base_ts + n_full * sub_duration_us

    def _convert_to_float32_mono(
        self, data: bytes, audio_format: AudioFormat
    ) -> np.ndarray:
        """
        Convert Sendspin PCM audio to LedFx format (float32 mono).

        FLAC chunks are no longer routed here – they go directly through
        the pyFLAC decoder in _audio_chunk_handler.

        Args:
            data: Raw audio bytes
            audio_format: Audio format information from Sendspin

        Returns:
            numpy array of float32 mono audio samples
        """
        codec = audio_format.codec
        pcm = audio_format.pcm_format
        bit_depth = pcm.bit_depth
        channels = pcm.channels

        # Handle PCM (most common)
        if codec == AudioCodec.PCM:
            if bit_depth == 16:
                # int16 PCM
                audio = np.frombuffer(data, dtype=np.int16)
                audio_float = audio.astype(np.float32) / 32768.0
            elif bit_depth == 24:
                # 24-bit packed as 3 bytes per sample
                audio = self._unpack_int24(data)
                audio_float = audio.astype(np.float32) / 8388608.0
            elif bit_depth == 32:
                # int32 PCM
                audio = np.frombuffer(data, dtype=np.int32)
                audio_float = audio.astype(np.float32) / 2147483648.0
            else:
                raise ValueError(f"Unsupported bit depth: {bit_depth}")

        else:
            raise ValueError(f"Unsupported codec: {codec}")

        # Convert stereo to mono if needed
        if channels == 2:
            # Reshape to (samples, 2) and average across channels
            audio_float = np.mean(audio_float.reshape(-1, 2), axis=1)
        elif channels > 2:
            # Multi-channel: take first channel
            audio_float = audio_float[::channels]

        return audio_float.astype(np.float32)

    def _init_flac_decoder(self, audio_format: AudioFormat) -> None:
        """
        Create a new persistent pyFLAC StreamDecoder for this stream.

        Feeds the FLAC stream header (STREAMINFO + metadata blocks) to the
        decoder immediately so subsequent audio-frame process() calls can be
        decoded without requiring the decoder to resync from scratch.
        """
        if pyflac is None:
            raise ImportError(
                "pyFLAC is required for FLAC decoding but is not installed. "
                "Install it with: uv add 'pyflac>=2.2.0'"
            )
        pcm = audio_format.pcm_format
        self._flac_bit_depth = pcm.bit_depth

        decoder = pyflac.StreamDecoder(
            write_callback=self._flac_write_callback,
        )
        self._flac_decoder = decoder

        # Prime the decoder with the FLAC stream header (fLaC marker +
        # STREAMINFO block) that Sendspin sends ahead of audio frames.
        codec_header = audio_format.codec_header
        if codec_header:
            if codec_header[:4] != b"fLaC":
                # Reconstruct a minimal valid FLAC stream header from the
                # raw STREAMINFO bytes supplied by the server.
                # FLAC metadata block header: 1 byte (type | last-flag) +
                # 3-byte big-endian block length.
                hdr_len = len(codec_header)
                block_hdr = bytes(
                    [
                        0x80,  # type=STREAMINFO (0), last-metadata-block flag
                        (hdr_len >> 16) & 0xFF,
                        (hdr_len >> 8) & 0xFF,
                        hdr_len & 0xFF,
                    ]
                )
                codec_header = b"fLaC" + block_hdr + codec_header
            # Header contains only metadata — no audio expected.
            # Initialise pending timing state to safe defaults.
            self._flac_pending_play_time_us = 0
            self._flac_pending_sample_rate = pcm.sample_rate
            self._flac_pending_samples_emitted = 0
            try:
                decoder.process(codec_header)
            except Exception as e:
                _LOGGER.warning(
                    "pyFLAC: ignoring error while processing stream header: %s", e
                )

        _LOGGER.info(
            "FLAC decoder (pyFLAC) initialized: %dHz %dch %dbit",
            pcm.sample_rate,
            pcm.channels,
            pcm.bit_depth,
        )

    def _flac_write_callback(
        self,
        audio: np.ndarray,
        sample_rate: int,
        num_channels: int,
        num_samples: int,
    ) -> None:
        """
        pyFLAC write callback – called synchronously during process().

        ``audio`` is a NumPy array of shape ``(num_samples, num_channels)``
        with dtype ``int16`` (or matching the source bit depth).  Sample
        values are scaled to the source bit depth range
        (e.g. 16-bit FLAC yields values in ``[-32768, 32767]``).

        Timing: ``_flac_pending_play_time_us`` is the play timestamp of the
        first sample in the current compressed chunk.  Each callback
        invocation advances the base timestamp by the number of mono samples
        already emitted for that chunk so multiple FLAC frames within one
        compressed chunk are stamped correctly.
        """
        try:
            if not self._flac_fmt_logged:
                _LOGGER.info(
                    "pyFLAC first block: dtype=%s shape=%s rate=%d "
                    "channels=%d num_samples=%d",
                    audio.dtype,
                    audio.shape,
                    sample_rate,
                    num_channels,
                    num_samples,
                )
                self._flac_fmt_logged = True

            # Advance the base timestamp by however many mono samples have
            # already been emitted for this compressed chunk.
            current_play_time_us = self._flac_pending_play_time_us + int(
                self._flac_pending_samples_emitted / sample_rate * 1_000_000
            )

            # Normalise to float32 in approximately [-1.0, 1.0].
            # pyFLAC delivers int32 with values in the range of the source
            # bit depth; divide by 2^(bit_depth-1).
            scale = float(1 << (self._flac_bit_depth - 1))

            # pyFLAC delivers shape (num_samples, num_channels) – row-per-sample.
            # Average across channels (axis=1) to downmix to mono.
            if num_channels >= 2:
                mono = np.mean(audio.astype(np.float32), axis=1) / scale
            else:
                mono = audio.flatten().astype(np.float32) / scale

            self._schedule_mono_samples(mono, current_play_time_us, sample_rate)
            self._flac_pending_samples_emitted += num_samples

        except Exception as e:
            _LOGGER.error(
                "Error in pyFLAC write callback: %s", e, exc_info=True
            )

    @staticmethod
    def _unpack_int24(data: bytes) -> np.ndarray:
        """
        Unpack 24-bit little-endian signed integers.

        Args:
            data: Bytes containing packed 24-bit samples

        Returns:
            numpy array of int32 values
        """
        # Reshape to (n_samples, 3) for vectorized processing
        raw = np.frombuffer(data, dtype=np.uint8)
        raw = raw[: len(raw) - len(raw) % 3].reshape(-1, 3)
        # Combine bytes: little-endian 24-bit
        samples = (
            raw[:, 0].astype(np.int32)
            | (raw[:, 1].astype(np.int32) << 8)
            | (raw[:, 2].astype(np.int32) << 16)
        )
        # Sign-extend from 24-bit
        samples = np.where(samples & 0x800000, samples | 0xFF000000, samples)
        return samples.astype(np.int32)

    def _stream_start_handler(self, stream_start_msg):
        """
        Called when stream starts.

        Args:
            stream_start_msg: StreamStartMessage from Sendspin
        """
        player = stream_start_msg.payload.player
        if player:
            _LOGGER.info(
                "Sendspin stream started: %s %dHz %dbit %dch",
                player.codec.value,
                player.sample_rate,
                player.bit_depth,
                player.channels,
            )
        else:
            _LOGGER.info("Sendspin stream started (no player info)")

        # Reset pyFLAC decoder on new stream (format may have changed).
        # Call finish() to free libFLAC resources before discarding the instance.
        if self._flac_decoder is not None:
            try:
                self._flac_decoder.finish()
            except Exception as e:
                _LOGGER.warning(
                    "Error finishing FLAC decoder on stream reset: %s", e
                )
            self._flac_decoder = None
        self._flac_fmt_logged = False
        self._flac_pending_play_time_us = 0
        self._flac_pending_sample_rate = 48000
        self._flac_pending_samples_emitted = 0
        self._leftover = np.array([], dtype=np.float32)
        self._leftover_ts = 0

    def _stream_clear_handler(self, roles):
        """Called on stream/clear (e.g. seek). Flush the playback buffer."""
        self._leftover = np.array([], dtype=np.float32)
        self._leftover_ts = 0
        with self._buffer_lock:
            self._chunk_buffer.clear()
        _LOGGER.debug(
            "Playback buffer cleared (stream/clear, roles=%s)", roles
        )

    async def _playback_scheduler(self):
        """Release buffered chunks to LedFx at their scheduled play time."""
        while self._active:
            chunk = None
            with self._buffer_lock:
                if self._chunk_buffer:
                    play_time_us = self._chunk_buffer[0][0]
                    now_us = int(self._loop.time() * 1_000_000)
                    if play_time_us <= now_us:
                        _, _, chunk = heapq.heappop(self._chunk_buffer)

            if chunk is not None:
                try:
                    self.callback(chunk, len(chunk), None, None)
                except Exception as e:
                    _LOGGER.error(
                        "Error in LedFx audio callback: %s", e, exc_info=True
                    )
                # Check immediately for more ready chunks
                continue

            # Nothing ready — sleep briefly before re-checking.
            # 5 ms keeps CPU negligible while limiting scheduling jitter
            # to well within acceptable limits for LED visualisation.
            await asyncio.sleep(0.005)

    def start(self):
        """Start receiving audio from Sendspin server."""
        if self._active:
            _LOGGER.warning("Sendspin stream already active")
            return

        _LOGGER.info("Starting Sendspin stream...")
        self._active = True

        # Start background thread with asyncio event loop
        self._thread = threading.Thread(
            target=self._run_client, daemon=True, name="SendspinAudioThread"
        )
        self._thread.start()

    def stop(self):
        """Stop receiving audio."""
        if not self._active:
            return

        _LOGGER.info("Stopping Sendspin stream...")
        self._active = False

        if self._client and self._loop:
            # Schedule disconnect in the event loop
            asyncio.run_coroutine_threadsafe(
                self._client.disconnect(), self._loop
            )

    def close(self):
        """Clean shutdown of the stream."""
        self.stop()

        # Give the thread up to 5 s to finish the scheduled disconnect cleanly
        # before force-stopping the loop.  Calling loop.stop() immediately would
        # abort the run_coroutine_threadsafe(disconnect()) future before it
        # completes and produce "event loop stopped before Future completed".
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        if self._thread and self._thread.is_alive():
            # Thread did not finish in time; force-stop the loop so the thread
            # can exit and then wait briefly for cleanup.
            _LOGGER.warning(
                "Sendspin thread did not exit within 5 s; force-stopping event loop"
            )
            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
            self._thread.join(timeout=2.0)

        # Clean up pyFLAC decoder once the stream thread has fully stopped.
        if self._flac_decoder is not None:
            try:
                self._flac_decoder.finish()
            except Exception:
                pass
            self._flac_decoder = None

        _LOGGER.info("Sendspin stream closed")

    def _run_client(self):
        """Background thread running asyncio event loop with reconnect."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._reconnect_loop())
        except Exception as e:
            _LOGGER.error("Sendspin client error: %s", e, exc_info=True)
        finally:
            self._loop.close()

    async def _reconnect_loop(self):
        """Reconnect to Sendspin server with exponential backoff."""
        backoff = 1.0
        max_backoff = 30.0
        while self._active:
            try:
                await self._connect_and_receive()
                backoff = 1.0  # reset on clean exit
            except Exception as e:
                if not self._active:
                    break
                _LOGGER.warning(
                    "Sendspin connection lost, retrying in %.0fs: %s",
                    backoff,
                    e,
                )
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, max_backoff)

    async def _connect_and_receive(self):
        """Connect to Sendspin server and start receiving audio."""
        server_url = self.config.get("server_url")
        client_name = self.config.get("client_name", "LedFx")
        sample_rate = self.config.get("sample_rate", 48000)
        buffer_capacity = BUFFER_CAPACITY

        _LOGGER.info(
            "Connecting to Sendspin server: %s as '%s'",
            server_url,
            client_name,
        )

        try:
            # Build supported format list — prefer FLAC (lower bandwidth)
            # then fall back to PCM. Server picks the first mutually supported.
            # Request mono since LedFx downmixes to mono anyway.
            supported_formats = []
            if pyflac is not None:
                supported_formats.append(
                    SupportedAudioFormat(
                        codec=AudioCodec.FLAC,
                        channels=1,
                        sample_rate=sample_rate,
                        bit_depth=16,
                    ),
                )
            supported_formats.append(
                SupportedAudioFormat(
                    codec=AudioCodec.PCM,
                    channels=1,
                    sample_rate=sample_rate,
                    bit_depth=16,
                ),
            )

            player_support = ClientHelloPlayerSupport(
                supported_formats=supported_formats,
                buffer_capacity=buffer_capacity,
                supported_commands=[
                    PlayerCommand.VOLUME,
                    PlayerCommand.MUTE,
                ],
            )

            # Create Sendspin client
            # client_id must be persistent across reconnections so the server
            # can associate this client with previous sessions (spec requirement).
            client_id = (
                f"ledfx-{self._server_id}"
                if self._server_id
                else f"ledfx-{id(self)}"
            )
            self._client = SendspinClient(
                client_id=client_id,
                client_name=client_name,
                roles=[Roles.PLAYER],
                player_support=player_support,
            )

            # Register event handlers
            self._client.add_audio_chunk_listener(self._audio_chunk_handler)
            self._client.add_stream_start_listener(self._stream_start_handler)
            self._client.add_stream_clear_listener(self._stream_clear_handler)

            # Connect to server
            await self._client.connect(server_url)

            _LOGGER.info("Connected to Sendspin server successfully")

            # Start the playback scheduler that drains the buffer at the
            # correct timestamps.
            self._scheduler_task = asyncio.ensure_future(
                self._playback_scheduler()
            )

            # Keep connection alive
            while self._active:
                await asyncio.sleep(0.1)

        except Exception as e:
            _LOGGER.warning("Sendspin connection attempt failed: %s", e)
            raise
        finally:
            if self._scheduler_task and not self._scheduler_task.done():
                self._scheduler_task.cancel()
                try:
                    await self._scheduler_task
                except asyncio.CancelledError:
                    pass
            self._scheduler_task = None

            with self._buffer_lock:
                self._chunk_buffer.clear()

            if self._client:
                try:
                    await self._client.disconnect()
                except Exception as e:
                    _LOGGER.warning(
                        "Sendspin disconnect failed during teardown: %s",
                        e,
                        exc_info=True,
                    )
            self._client = None
