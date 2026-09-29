"""Sendspin Now Playing provider.

Receives track metadata from a Sendspin server via the aiosendspin client's
metadata listener and forwards it to the NowPlayingService.

Sendspin sends incremental state updates — fields set to UndefinedField mean
"not included in this message" (retain previous value), while explicit None
means "cleared". The provider accumulates state across messages.
"""

import logging
from typing import TYPE_CHECKING, Protocol

from ledfx.nowplaying.models import TrackMetadata

if TYPE_CHECKING:
    from ledfx.nowplaying.service import NowPlayingService

_LOGGER = logging.getLogger(__name__)

SOURCE_ID = "sendspin"


class LedFxNowPlaying(Protocol):
    # LedFxCore sets now_playing only in async_start, so the attribute may be
    # missing at runtime: read it with getattr(..., None), not directly.
    @property
    def now_playing(self) -> "NowPlayingService | None": ...


class _ServerState(Protocol):
    """Metadata field consumed from a Sendspin server state update."""

    @property
    def metadata(self) -> object: ...


class SendspinNowPlayingProvider:
    """Bridges Sendspin metadata callbacks to the NowPlayingService.

    Created and owned by SendspinAudioStream. Receives ServerStatePayload
    objects from the aiosendspin metadata listener and normalizes them into
    TrackMetadata for the Now Playing Service.

    Accumulates state across incremental updates — only fields explicitly
    sent by the server are updated; UndefinedField values are ignored.

    Args:
        ledfx: LedFxCore instance (.now_playing may be absent or None).
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

    def on_metadata(self, server_state_payload: _ServerState) -> None:
        """Handle a server/state metadata update from aiosendspin.

        Sendspin sends incremental updates. UndefinedField means "not sent"
        (keep previous), None means "explicitly cleared", and a value means
        "updated to this".

        Args:
            server_state_payload: _ServerState from the metadata callback.
        """
        from aiosendspin.models.metadata import SessionUpdateMetadata
        from aiosendspin.models.types import UndefinedField

        metadata = server_state_payload.metadata
        if metadata is None:
            return

        if not isinstance(metadata, SessionUpdateMetadata):
            _LOGGER.debug("Ignoring non-metadata server state update")
            return

        # Omitted fields retain their previous value; explicit None clears it.
        if not isinstance(metadata.title, UndefinedField):
            self._title = metadata.title
        if not isinstance(metadata.artist, UndefinedField):
            self._artist = metadata.artist
        if not isinstance(metadata.album, UndefinedField):
            self._album = metadata.album
        if not isinstance(metadata.artwork_url, UndefinedField):
            self._artwork_url = metadata.artwork_url

        # Build TrackMetadata from accumulated state
        track_metadata = TrackMetadata(
            source_id=SOURCE_ID,
            title=self._title,
            artist=self._artist,
            album=self._album,
            artwork_url=self._artwork_url,
        )

        # Forward to Now Playing Service
        now_playing = getattr(self._ledfx, "now_playing", None)
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
        now_playing = getattr(self._ledfx, "now_playing", None)
        if now_playing is not None:
            now_playing.clear(SOURCE_ID)
        self._last_artwork_url = None
        self._title = None
        self._artist = None
        self._album = None
        self._artwork_url = None
        _LOGGER.info("Sendspin Now Playing provider cleared")
