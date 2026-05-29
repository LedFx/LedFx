"""SMTC (System Media Transport Controls) Now Playing provider.

Windows-only. Uses WinRT events to react to media session changes.
Track metadata (title, artist, album) is forwarded to NowPlayingService.
Artwork is NOT fetched here; that is handled by the album-art resolver.
"""

import asyncio
import logging
import sys

from ledfx.nowplaying.models import TrackMetadata

_LOGGER = logging.getLogger(__name__)

SOURCE_ID = "smtc"


class SMTCNowPlayingProvider:
    def __init__(self, ledfx):
        self._ledfx = ledfx
        self._loop = None
        self._manager = None
        self._manager_token = None
        self._session = None
        self._session_tokens = []
        self._init_task = None
        self._last_title = None
        self._last_artist = None
        self._last_album = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self):
        if sys.platform != "win32":
            return
        if self._init_task is not None:
            return
        self._loop = asyncio.get_running_loop()
        self._init_task = asyncio.ensure_future(self._initialize())

    def stop(self):
        if self._init_task is not None:
            self._init_task.cancel()
            self._init_task = None
        if self._manager is not None and self._manager_token is not None:
            try:
                self._manager.remove_current_session_changed(
                    self._manager_token
                )
            except Exception:
                pass
        self._manager_token = None
        self._manager = None
        self._detach_session_events()
        self._last_title = None
        self._last_artist = None
        self._last_album = None

    def clear(self):
        """Explicitly reset this provider's state and notify the service."""
        self._last_title = None
        self._last_artist = None
        self._last_album = None
        now_playing = getattr(self._ledfx, "now_playing", None)
        if now_playing is not None:
            now_playing.clear(SOURCE_ID)

    # ------------------------------------------------------------------
    # Initialisation
    # ------------------------------------------------------------------

    async def _initialize(self):
        try:
            from winrt.windows.media.control import (
                GlobalSystemMediaTransportControlsSessionManager as MediaManager,
            )
        except ImportError:
            return

        try:
            manager = await MediaManager.request_async()
        except Exception:
            _LOGGER.exception("SMTC: failed to acquire MediaManager")
            return

        self._manager = manager
        self._manager_token = manager.add_current_session_changed(
            self._on_session_changed
        )
        await self._attach_to_session(manager.get_current_session())

    # ------------------------------------------------------------------
    # WinRT event callbacks (called from WinRT thread pool)
    # ------------------------------------------------------------------

    def _on_session_changed(self, manager, args):
        """Fires when the active media session changes."""
        if self._loop is None:
            return
        session = manager.get_current_session()
        asyncio.run_coroutine_threadsafe(
            self._attach_to_session(session), self._loop
        )

    def _on_media_properties_changed(self, session, args):
        """Fires when track title/artist/album changes."""
        if self._loop is None:
            return
        asyncio.run_coroutine_threadsafe(
            self._fetch_and_push_metadata(), self._loop
        )

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    async def _attach_to_session(self, session):
        self._detach_session_events()
        if session is None:
            self._maybe_clear()
            return
        self._session = session
        tok = session.add_media_properties_changed(
            self._on_media_properties_changed
        )
        self._session_tokens = [(session.remove_media_properties_changed, tok)]
        await self._fetch_and_push_metadata()

    def _detach_session_events(self):
        for remove_fn, token in self._session_tokens:
            try:
                remove_fn(token)
            except Exception:
                pass
        self._session_tokens = []
        self._session = None

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    async def _fetch_and_push_metadata(self):
        if self._session is None:
            return
        try:
            props = await self._session.try_get_media_properties_async()
        except Exception:
            _LOGGER.warning("SMTC: failed to fetch media properties")
            return

        if props is None:
            self._maybe_clear()
            return

        title = props.title or None
        artist = props.artist or None
        album = props.album_title or None

        self._last_title = title
        self._last_artist = artist
        self._last_album = album

        now_playing = getattr(self._ledfx, "now_playing", None)
        if now_playing is None:
            return

        now_playing.set_metadata(
            SOURCE_ID,
            TrackMetadata(
                source_id=SOURCE_ID,
                title=title,
                artist=artist,
                album=album,
            ),
        )

    def _maybe_clear(self):
        if (
            self._last_title is None
            and self._last_artist is None
            and self._last_album is None
        ):
            return
        now_playing = getattr(self._ledfx, "now_playing", None)
        if now_playing is not None:
            now_playing.clear(SOURCE_ID)
        self._last_title = None
        self._last_artist = None
        self._last_album = None
