"""Sendspin audio stream implementation for LedFx.

This module implements the audio stream interface expected by LedFx's AudioInputSource,
receiving audio from a Sendspin server and converting it to LedFx's expected format.
"""

import asyncio
import logging
import threading
from typing import Callable, Optional

import numpy as np

try:
    from aiosendspin.client import AudioFormat, PCMFormat, SendspinClient
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


class SendspinAudioStream:
    """
    Audio stream that receives Sendspin audio chunks and feeds LedFx.

    Implements the same interface as WebAudioStream to work with LedFx's
    AudioInputSource system.

    Args:
        config: Configuration dict with server_url, client_name, etc.
        callback: LedFx's _audio_sample_callback(data, frame_count, time_info, status)
    """

    def __init__(self, config: dict, callback: Callable):
        if SendspinClient is None:
            raise ImportError(
                "aiosendspin not available (requires Python 3.12+)"
            )

        self.config = config
        self.callback = callback
        self._active = False
        self._client: Optional[SendspinClient] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread: Optional[threading.Thread] = None

        _LOGGER.info(
            "Sendspin stream initialized for server: %s",
            config.get("server_url", "unknown"),
        )

    def _audio_chunk_handler(
        self, timestamp: int, chunk_data: bytes, audio_format: AudioFormat
    ):
        """
        Called by aiosendspin when audio chunk arrives.

        Args:
            timestamp: Server timestamp in microseconds
            chunk_data: Raw audio bytes from Sendspin
            audio_format: Audio format description for this chunk
        """
        if not self._active:
            return

        try:
            # Convert to float32 mono (matching LedFx expectations)
            audio_float32 = self._convert_to_float32_mono(
                chunk_data, audio_format
            )

            # Call LedFx's callback
            self.callback(audio_float32, len(audio_float32), None, None)

        except Exception as e:
            _LOGGER.error("Error processing audio chunk: %s", e, exc_info=True)

    def _convert_to_float32_mono(
        self, data: bytes, audio_format: AudioFormat
    ) -> np.ndarray:
        """
        Convert Sendspin audio to LedFx format (float32 mono).

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

        elif codec in (AudioCodec.FLAC, AudioCodec.OPUS):
            # These codecs are decoded by aiosendspin before reaching us
            # If we get here, treat as PCM
            _LOGGER.warning(
                "Received compressed %s data, attempting PCM decode", codec
            )
            # Assume int16 for compressed formats
            audio = np.frombuffer(data, dtype=np.int16)
            audio_float = audio.astype(np.float32) / 32768.0
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

    @staticmethod
    def _unpack_int24(data: bytes) -> np.ndarray:
        """
        Unpack 24-bit little-endian signed integers.

        Args:
            data: Bytes containing packed 24-bit samples

        Returns:
            numpy array of int32 values
        """
        num_samples = len(data) // 3
        samples = np.zeros(num_samples, dtype=np.int32)

        for i in range(num_samples):
            # Extract 3 bytes
            b0, b1, b2 = data[i * 3 : (i + 1) * 3]
            # Combine into int32 (sign-extend from 24-bit)
            value = b0 | (b1 << 8) | (b2 << 16)
            if value & 0x800000:  # Check sign bit
                value |= 0xFF000000  # Sign extend
            samples[i] = np.int32(value)

        return samples

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

        if self._loop and self._loop.is_running():
            self._loop.call_soon_threadsafe(self._loop.stop)

        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5.0)

        _LOGGER.info("Sendspin stream closed")

    def _run_client(self):
        """Background thread running asyncio event loop."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)

        try:
            self._loop.run_until_complete(self._connect_and_receive())
        except Exception as e:
            _LOGGER.error(
                "Sendspin client error: %s", e, exc_info=True
            )
        finally:
            self._loop.close()

    async def _connect_and_receive(self):
        """Connect to Sendspin server and start receiving audio."""
        server_url = self.config.get("server_url")
        client_name = self.config.get("client_name", "LedFx")
        sample_rate = self.config.get("sample_rate", 48000)
        buffer_capacity = self.config.get("buffer_capacity", 1000000)

        _LOGGER.info(
            "Connecting to Sendspin server: %s as '%s'",
            server_url,
            client_name,
        )

        try:
            # Build supported format list
            supported_formats = [
                SupportedAudioFormat(
                    codec=AudioCodec.PCM,
                    channels=2,
                    sample_rate=sample_rate,
                    bit_depth=16,
                ),
            ]

            player_support = ClientHelloPlayerSupport(
                supported_formats=supported_formats,
                buffer_capacity=buffer_capacity,
                supported_commands=[
                    PlayerCommand.VOLUME,
                    PlayerCommand.MUTE,
                ],
            )

            # Create Sendspin client
            self._client = SendspinClient(
                client_id=f"ledfx-{id(self)}",
                client_name=client_name,
                roles=[Roles.PLAYER],
                player_support=player_support,
            )

            # Register event handlers
            self._client.add_audio_chunk_listener(self._audio_chunk_handler)
            self._client.add_stream_start_listener(self._stream_start_handler)

            # Connect to server
            await self._client.connect(server_url)

            _LOGGER.info("Connected to Sendspin server successfully")

            # Keep connection alive
            while self._active:
                await asyncio.sleep(0.1)

        except Exception as e:
            _LOGGER.error(
                "Failed to connect to Sendspin server: %s",
                e,
                exc_info=True,
            )
            raise
        finally:
            if self._client:
                try:
                    await self._client.disconnect()
                except Exception:
                    pass
