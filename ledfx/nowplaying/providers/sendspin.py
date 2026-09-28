"""Sendspin Now Playing provider.

Receives track metadata from a Sendspin server via the aiosendspin client's
metadata listener and forwards it to the NowPlayingService.

Sendspin sends incremental state updates — fields set to UndefinedField mean
"not included in this message" (retain previous value), while explicit None
means "cleared". The provider accumulates state across messages.
"""

import logging
from typing import Protocol

from aiosendspin.models.core import ServerStatePayload
from aiosendspin.models.metadata import SessionUpdateMetadata
from aiosendspin.models.types import UndefinedField

from ledfx.nowplaying.models import TrackMetadata

_LOGGER = logging.getLogger(__name__)

SOURCE_ID = "sendspin"


class _NowPlayingService(Protocol):
    """Now Playing operations used to publish Sendspin metadata."""

    def set_metadata(self, source_id: str, metadata: TrackMetadata) -> bool: ...

    def set_artwork_url(self, source_id: str, url: str) -> bool: ...

    def clear_artwork(self, source_id: str) -> None: ...

    def clear(self, source_id: str) -> None: ...


class LedFxNowPlaying(Protocol):
    @property
    def now_playing(self) -> _NowPlayingService | None: ...


class _NotSent:
    """Marker for metadata fields that were omitted by the server."""


class SendspinNowPlayingProvider:
    """Bridges Sendspin metadata callbacks to the NowPlayingService.

    Created and owned by SendspinAudioStream. Receives ServerStatePayload
    objects from the aiosendspin metadata listener and normalizes them into
    TrackMetadata for the Now Playing Service.

    Accumulates state across incremental updates — only fields explicitly
    sent by the server are updated; UndefinedField values are ignored.

    Args:
        ledfx: LedFxCore instance (must have .now_playing attribute).
    """

    def __init__(self, ledfx: LedFxNowPlaying) -> None:
        self._ledfx = ledfx
        self._last_artwork_url: str | None = None
        # Accumulated track state (survives across incremental updates)
        self._title: str | None = None
        self._artist: str | None = None
        self._album: str | None = None
        self._artwork_url: str | None = None
        _LOGGER.info("Sendspin Now Playing provider initialized")

    def on_metadata(self, server_state_payload: ServerStatePayload) -> None:
        """Handle a server/state metadata update from aiosendspin.

        Sendspin sends incremental updates. UndefinedField means "not sent"
        (keep previous), None means "explicitly cleared", and a value means
        "updated to this".

        Args:
            server_state_payload: ServerStatePayload from the metadata callback.
        """
        metadata = server_state_payload.metadata
        if metadata is None:
            return

        if not isinstance(metadata, SessionUpdateMetadata):
            _LOGGER.debug("Ignoring non-metadata server state update")
            return

        # Extract fields: UndefinedField → _NOT_SENT (keep prev), else use value
        def _val(field: str | None | UndefinedField) -> str | None | _NotSent:
            if isinstance(field, UndefinedField):
                return _NotSent()
            return field

        # Update accumulated state only for fields that were actually sent
        title = _val(metadata.title)
        artist = _val(metadata.artist)
        album = _val(metadata.album)
        artwork_url = _val(metadata.artwork_url)

        if not isinstance(title, _NotSent):
            self._title = title
        if not isinstance(artist, _NotSent):
            self._artist = artist
        if not isinstance(album, _NotSent):
            self._album = album
        if not isinstance(artwork_url, _NotSent):
            self._artwork_url = artwork_url

        # Build TrackMetadata from accumulated state
        track_metadata = TrackMetadata(
            source_id=SOURCE_ID,
            title=self._title,
            artist=self._artist,
            album=self._album,
            artwork_url=self._artwork_url,
        )

        # Forward to Now Playing Service
        now_playing = self._ledfx.now_playing
        if now_playing is None:
            return
        now_playing.set_metadata(SOURCE_ID, track_metadata)

        # Handle artwork URL changes
        if (
            self._artwork_url is not None
            and self._artwork_url != self._last_artwork_url
        ):
            self._last_artwork_url = self._artwork_url
            now_playing.set_artwork_url(SOURCE_ID, self._artwork_url)
        elif self._artwork_url is None and self._last_artwork_url is not None:
            # Artwork cleared by server
            self._last_artwork_url = None
            now_playing.clear_artwork(SOURCE_ID)

    def clear(self) -> None:
        """Clear Now Playing state and reset accumulated state."""
        now_playing = self._ledfx.now_playing
        if now_playing is not None:
            now_playing.clear(SOURCE_ID)
        self._last_artwork_url = None
        self._title = None
        self._artist = None
        self._album = None
        self._artwork_url = None
        _LOGGER.info("Sendspin Now Playing provider cleared")
