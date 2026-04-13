"""
Platform media session provider using winrt (Windows) with polling.

All platform-specific media reading logic is isolated in this single file.
Uses winrt-windows-media-control on Windows to read active media sessions.
Linux/macOS support can be added as additional provider files.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Awaitable
from typing import Callable

from ledfx.nowplaying.models import NowPlayingTrack

_LOGGER = logging.getLogger(__name__)

_PLATFORM_AVAILABLE = False
_UNAVAILABLE_REASON = ""

if sys.platform == "win32":
    try:
        from winrt.windows.media.control import (
            GlobalSystemMediaTransportControlsSessionManager,
        )

        _PLATFORM_AVAILABLE = True
    except ImportError:
        _UNAVAILABLE_REASON = (
            "winrt-windows-media-control package not installed"
        )
elif sys.platform == "linux":
    _UNAVAILABLE_REASON = "Linux MPRIS2 reading not yet implemented"
elif sys.platform == "darwin":
    _UNAVAILABLE_REASON = "macOS media reading not yet implemented"
else:
    _UNAVAILABLE_REASON = f"Unsupported platform: {sys.platform}"


def is_available() -> bool:
    return _PLATFORM_AVAILABLE


def unavailable_reason() -> str:
    return _UNAVAILABLE_REASON


class PlatformMediaProvider:
    """Reads current media session info via platform APIs with polling."""

    PROVIDER_NAME = "platform_media"

    def __init__(self, poll_interval: float = 2.0):
        self._poll_interval = poll_interval
        self._callback: Callable[[NowPlayingTrack], Awaitable[None]] | None = (
            None
        )
        self._task: asyncio.Task | None = None
        self._stopped = False

    async def start(
        self,
        callback: Callable[[NowPlayingTrack], Awaitable[None]],
    ) -> None:
        if not _PLATFORM_AVAILABLE:
            raise RuntimeError(
                f"Platform media provider unavailable: {_UNAVAILABLE_REASON}"
            )
        self._callback = callback
        self._stopped = False
        self._task = asyncio.create_task(self._poll_loop())
        _LOGGER.info(
            "Platform media provider started (poll interval: %.1fs)",
            self._poll_interval,
        )

    async def stop(self) -> None:
        self._stopped = True
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        _LOGGER.info("Platform media provider stopped")

    async def _poll_loop(self) -> None:
        while not self._stopped:
            try:
                track = await self._read_current_session()
                if track and self._callback:
                    await self._callback(track)
            except asyncio.CancelledError:
                return
            except Exception:
                _LOGGER.debug("Error reading media session", exc_info=True)
            await asyncio.sleep(self._poll_interval)

    async def _read_current_session(self) -> NowPlayingTrack | None:
        """Read current media session from Windows SMTC."""
        if sys.platform != "win32":
            return None

        try:
            mgr = (
                await GlobalSystemMediaTransportControlsSessionManager.request_async()
            )
            session = mgr.get_current_session()
            if session is None:
                return None

            info = await session.try_get_media_properties_async()
            timeline = session.get_timeline_properties()
            playback = session.get_playback_info()

            title = info.title if info.title else None
            artist = info.artist if info.artist else None
            album = info.album_title if info.album_title else None
            source = session.source_app_user_model_id or None

            # Resolve thumbnail to a local path or None
            art_url = None
            if info.thumbnail:
                try:
                    stream = await info.thumbnail.open_read_async()
                    art_url = f"winrt-thumbnail://{source or 'unknown'}"
                    # Store stream reference for later fetch
                    self._last_thumbnail_stream = stream
                except Exception:
                    _LOGGER.debug("Failed to open thumbnail stream")
                    self._last_thumbnail_stream = None

            # PlaybackStatus enum: 0=Closed, 1=Opened, 2=Changing, 3=Stopped, 4=Playing, 5=Paused
            is_playing = playback.playback_status == 4

            duration = None
            if timeline.end_time:
                duration = timeline.end_time.total_seconds()

            position = None
            if timeline.position:
                position = timeline.position.total_seconds()

            return NowPlayingTrack(
                provider=self.PROVIDER_NAME,
                title=title,
                artist=artist,
                album=album,
                art_url=art_url,
                duration=duration,
                position=position,
                is_playing=is_playing,
                player_name=source,
                source_id=source,
            )
        except Exception:
            _LOGGER.debug(
                "Failed to read Windows media session", exc_info=True
            )
            return None

    async def get_thumbnail_bytes(self) -> bytes | None:
        """Get the raw bytes of the last thumbnail stream. Call after _read_current_session."""
        stream = getattr(self, "_last_thumbnail_stream", None)
        if stream is None:
            return None
        try:
            from winrt.windows.storage.streams import (
                Buffer,
                InputStreamOptions,
            )

            size = stream.size
            if size == 0 or size > 10 * 1024 * 1024:  # Cap at 10MB
                return None
            buf = Buffer(int(size))
            read_buf = await stream.read_async(
                buf, int(size), InputStreamOptions.NONE
            )
            return bytes(read_buf)
        except Exception:
            _LOGGER.debug("Failed to read thumbnail bytes", exc_info=True)
            return None
