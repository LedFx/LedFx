"""
Windows SMTC (System Media Transport Controls) provider.

Uses winrt-windows-media-control to read active media sessions on Windows.
Event-driven: subscribes to session and media property change events.
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable
from typing import Callable

from ledfx.nowplaying.models import NowPlayingTrack

_LOGGER = logging.getLogger(__name__)

_AVAILABLE = False
_UNAVAILABLE_REASON = ""

try:
    from winrt.windows.media.control import (
        GlobalSystemMediaTransportControlsSessionManager,
    )

    _AVAILABLE = True
except ImportError:
    _UNAVAILABLE_REASON = "winrt-windows-media-control package not installed"


def is_available() -> bool:
    return _AVAILABLE


def unavailable_reason() -> str:
    return _UNAVAILABLE_REASON


class WindowsSMTCProvider:
    """Reads current media session info via Windows SMTC events."""

    PROVIDER_NAME = "windows_smtc"

    def __init__(self):
        self._callback: Callable[[NowPlayingTrack], Awaitable[None]] | None = (
            None
        )
        self._loop: asyncio.AbstractEventLoop | None = None
        self._stopped = False
        self._manager = None
        self._current_session = None
        self._session_changed_token = None
        self._media_props_token = None
        self._playback_token = None

    async def start(
        self,
        callback: Callable[[NowPlayingTrack], Awaitable[None]],
    ) -> None:
        if not _AVAILABLE:
            raise RuntimeError(
                f"Windows SMTC provider unavailable: {_UNAVAILABLE_REASON}"
            )
        self._callback = callback
        self._stopped = False
        self._loop = asyncio.get_running_loop()

        self._manager = (
            await GlobalSystemMediaTransportControlsSessionManager.request_async()
        )

        # Subscribe to session changes (e.g. user switches media app)
        self._session_changed_token = (
            self._manager.add_current_session_changed(
                lambda mgr, args: self._schedule_read()
            )
        )

        # Attach to the current session immediately
        await self._attach_current_session()

        # Fire an initial read so the manager gets the current state
        await self._read_and_notify()

        _LOGGER.info("Windows SMTC provider started (event-driven)")

    async def stop(self) -> None:
        self._stopped = True
        self._detach_session()
        if self._manager and self._session_changed_token is not None:
            self._manager.remove_current_session_changed(
                self._session_changed_token
            )
            self._session_changed_token = None
        self._manager = None
        _LOGGER.info("Windows SMTC provider stopped")

    def _schedule_read(self) -> None:
        """Thread-safe trampoline: schedule a read on the event loop."""
        if self._stopped or self._loop is None:
            return
        self._loop.call_soon_threadsafe(
            lambda: asyncio.ensure_future(self._on_event_fired())
        )

    async def _on_event_fired(self) -> None:
        """Re-attach to the (possibly new) session and read."""
        if self._stopped:
            return
        await self._attach_current_session()
        await self._read_and_notify()

    async def _attach_current_session(self) -> None:
        """Subscribe to property/playback changes on the active session."""
        self._detach_session()
        if self._manager is None:
            return
        session = self._manager.get_current_session()
        if session is None:
            self._current_session = None
            return
        self._current_session = session
        self._media_props_token = session.add_media_properties_changed(
            lambda s, args: self._schedule_read()
        )
        self._playback_token = session.add_playback_info_changed(
            lambda s, args: self._schedule_read()
        )

    def _detach_session(self) -> None:
        """Unsubscribe from the previous session's events."""
        if self._current_session is not None:
            if self._media_props_token is not None:
                self._current_session.remove_media_properties_changed(
                    self._media_props_token
                )
                self._media_props_token = None
            if self._playback_token is not None:
                self._current_session.remove_playback_info_changed(
                    self._playback_token
                )
                self._playback_token = None
        self._current_session = None

    async def _read_and_notify(self) -> None:
        """Read the current session and push to the callback."""
        if self._stopped or self._callback is None:
            return
        try:
            track = await self._read_current_session()
            if track:
                await self._callback(track)
        except Exception:
            _LOGGER.debug("Error reading media session", exc_info=True)

    async def _read_current_session(self) -> NowPlayingTrack | None:
        """Read current media session from Windows SMTC."""
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
        """Get the raw bytes of the last thumbnail stream."""
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
