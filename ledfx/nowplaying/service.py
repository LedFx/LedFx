"""Now Playing Service implementation.

Centralized service managing current media playback state.
Receives normalized metadata from providers and exposes a single
source of truth for the rest of LedFx.
"""

import logging
import time

from ledfx.events import (
    NowPlayingArtworkChangedEvent,
    NowPlayingClearedEvent,
    NowPlayingMetadataChangedEvent,
    NowPlayingTrackChangedEvent,
)
from ledfx.nowplaying.models import (
    ArtworkReference,
    NowPlayingState,
    TrackMetadata,
)

_LOGGER = logging.getLogger(__name__)


class NowPlayingService:
    """Provider-neutral Now Playing state manager.

    Attributes:
        ledfx: Reference to the LedFxCore instance.
        state: Current NowPlayingState.
    """

    def __init__(self, ledfx):
        self._ledfx = ledfx
        self._state = NowPlayingState()
        _LOGGER.info("Now Playing Service initialized")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def set_metadata(self, source_id: str, metadata: TrackMetadata) -> bool:
        """Update current track metadata from a provider.

        Args:
            source_id: Provider identifier (e.g. "sendspin").
            metadata: Normalized track metadata.

        Returns:
            True if a track change was detected, False otherwise.
        """
        now = time.time()
        metadata.updated_at = now

        # Determine if this is a new track
        track_changed = self._detect_track_change(metadata)

        # Activate source on first metadata or if already active
        if self._state.active_source_id is None:
            self._state.active_source_id = source_id
            _LOGGER.info("Now Playing active source set to: %s", source_id)

        # Only update state if this provider is the active source
        if source_id != self._state.active_source_id:
            _LOGGER.debug(
                "Ignoring metadata from inactive source: %s (active: %s)",
                source_id,
                self._state.active_source_id,
            )
            return False

        self._state.metadata = metadata
        self._state.updated_at = now

        # Fire events
        self._fire_event(
            NowPlayingMetadataChangedEvent(source_id, metadata.to_dict())
        )

        if track_changed:
            _LOGGER.info(
                "Track changed: %s - %s - %s",
                metadata.artist or "Unknown artist",
                metadata.title or "Unknown title",
                metadata.album or "Unknown album",
            )
            self._fire_event(
                NowPlayingTrackChangedEvent(
                    source_id, metadata.title, metadata.artist, metadata.album
                )
            )

        return track_changed

    def set_artwork_url(
        self,
        source_id: str,
        url: str,
        content_type: str = None,
        artwork_hash: str = None,
    ) -> bool:
        """Set artwork reference from a URL.

        Args:
            source_id: Provider identifier.
            url: URL to the artwork image.
            content_type: MIME type of the image.
            artwork_hash: Hash for change detection.

        Returns:
            True if artwork changed, False otherwise.
        """
        if source_id != self._state.active_source_id:
            return False

        # Detect artwork change
        current = self._state.artwork
        if current and current.url == url and current.hash == artwork_hash:
            return False

        self._state.artwork = ArtworkReference(
            source_id=source_id,
            url=url,
            content_type=content_type,
            hash=artwork_hash,
        )
        self._state.updated_at = time.time()

        _LOGGER.info("Artwork URL updated from %s", source_id)
        self._fire_event(
            NowPlayingArtworkChangedEvent(
                source_id, self._state.artwork.to_dict()
            )
        )
        return True

    def set_artwork_bytes(
        self,
        source_id: str,
        data: bytes,
        content_type: str,
        artwork_hash: str = None,
    ) -> bool:
        """Set artwork from raw image bytes.

        The bytes will be routed through the image cache pipeline
        in a later phase. For now, store the reference.

        Args:
            source_id: Provider identifier.
            data: Raw image bytes.
            content_type: MIME type of the image.
            artwork_hash: Hash for change detection. If None, computed from data.

        Returns:
            True if artwork changed, False otherwise.
        """
        import hashlib

        if source_id != self._state.active_source_id:
            return False

        if artwork_hash is None:
            artwork_hash = hashlib.sha256(data).hexdigest()[:16]

        # Detect artwork change
        current = self._state.artwork
        if current and current.hash == artwork_hash:
            return False

        # Synthetic cache key for byte-based artwork
        cache_key = f"now-playing://{source_id}/{artwork_hash}"

        self._state.artwork = ArtworkReference(
            source_id=source_id,
            url=None,
            cache_key=cache_key,
            content_type=content_type,
            hash=artwork_hash,
        )
        self._state.updated_at = time.time()

        _LOGGER.info(
            "Artwork bytes updated from %s (hash: %s)", source_id, artwork_hash
        )
        self._fire_event(
            NowPlayingArtworkChangedEvent(
                source_id, self._state.artwork.to_dict()
            )
        )
        return True

    def clear(self, source_id: str) -> None:
        """Clear state for a provider.

        If the cleared provider is the active source, resets all state.

        Args:
            source_id: Provider identifier to clear.
        """
        if self._state.active_source_id == source_id:
            _LOGGER.info(
                "Clearing Now Playing state for active source: %s", source_id
            )
            self._state = NowPlayingState()
            self._fire_event(NowPlayingClearedEvent(source_id))
        else:
            _LOGGER.debug(
                "Clear requested for inactive source: %s (active: %s)",
                source_id,
                self._state.active_source_id,
            )

    def get_current(self) -> NowPlayingState:
        """Return the current Now Playing state.

        Returns:
            The current NowPlayingState instance.
        """
        return self._state

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _detect_track_change(self, new_metadata: TrackMetadata) -> bool:
        """Compare new metadata against current to detect track changes.

        A track change is detected when the track identity tuple differs.
        Position-only updates are not considered track changes.

        Args:
            new_metadata: Incoming metadata to compare.

        Returns:
            True if the track identity changed.
        """
        current = self._state.metadata
        if current is None:
            return True

        return current.track_identity() != new_metadata.track_identity()

    def _fire_event(self, event) -> None:
        """Fire an event if the events system is available.

        Gracefully no-ops if events is not yet initialized (e.g. during testing).
        """
        if hasattr(self._ledfx, "events"):
            self._ledfx.events.fire_event(event)
