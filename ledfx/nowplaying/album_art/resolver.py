"""Album-art resolver — orchestrates album-art provider lookups.

Triggered by track changes.  Runs lookups asynchronously so metadata
updates are never blocked.  Keeps only the last normalized track key to
avoid duplicate lookups for the same track.
"""

import asyncio
import hashlib
import logging

from ledfx.nowplaying.album_art.base import AlbumArtProvider
from ledfx.nowplaying.models import TrackMetadata

_LOGGER = logging.getLogger(__name__)

# Content-type sniffing for raw bytes returned by providers
_MAGIC = [
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
]


def _detect_content_type(data: bytes) -> str:
    for magic, ct in _MAGIC:
        if data[: len(magic)] == magic:
            return ct
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return "image/jpeg"


class AlbumArtResolver:
    """Orchestrator that resolves album art from an ordered list of providers.

    Args:
        providers: Ordered list of :class:`AlbumArtProvider` instances.
        service: The :class:`~ledfx.nowplaying.service.NowPlayingService`
            instance to deliver resolved artwork to.
    """

    def __init__(self, providers: list[AlbumArtProvider], service):
        self._providers = providers
        self._service = service
        self._last_key: tuple | None = None
        self._resolve_task: asyncio.Task | None = None

    def on_track_changed(self, metadata: TrackMetadata) -> None:
        """Called when a track change is detected.

        If the normalized key differs from the last lookup, schedules an
        async artwork resolution without blocking the caller.

        Args:
            metadata: The new track metadata.
        """
        key = self._normalize_key(metadata)
        if key == self._last_key:
            return

        self._last_key = key

        # Cancel any in-flight lookup for the previous track.
        if self._resolve_task is not None and not self._resolve_task.done():
            self._resolve_task.cancel()
            self._resolve_task = None

        # If the source already supplies an artwork URL, the service will
        # download it directly — MusicBrainz is only a fallback for sources
        # that provide no artwork (e.g. SMTC without thumbnail).
        if metadata.artwork_url:
            _LOGGER.debug(
                "AlbumArtResolver: artwork URL provided by source, skipping lookup"
            )
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            _LOGGER.warning(
                "AlbumArtResolver: no running event loop, skipping lookup"
            )
            return

        self._resolve_task = asyncio.ensure_future(
            self._resolve(metadata), loop=loop
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_key(metadata: TrackMetadata) -> tuple:
        return (
            (metadata.artist or "").strip().lower(),
            (metadata.title or "").strip().lower(),
            (metadata.album or "").strip().lower(),
        )

    def cancel_pending(self) -> None:
        """Cancel any in-flight provider lookup (e.g. source supplied artwork)."""
        if self._resolve_task is not None and not self._resolve_task.done():
            self._resolve_task.cancel()
            _LOGGER.debug(
                "AlbumArtResolver: pending lookup cancelled (source artwork)"
            )
        self._resolve_task = None

    async def _resolve(self, metadata: TrackMetadata) -> None:
        key = self._normalize_key(metadata)
        try:
            for provider in self._providers:
                try:
                    data = await provider.resolve(metadata)
                except Exception as exc:
                    _LOGGER.warning(
                        "AlbumArtResolver: provider %s raised: %s",
                        type(provider).__name__,
                        exc,
                    )
                    continue

                if data:
                    # Discard if the track changed while we were fetching.
                    if self._last_key != key:
                        _LOGGER.debug(
                            "AlbumArtResolver: stale result discarded (track "
                            "changed during fetch)"
                        )
                        return
                    content_type = _detect_content_type(data)
                    artwork_hash = hashlib.sha256(data).hexdigest()[:16]
                    try:
                        self._service.set_artwork_resolved(
                            data, content_type, artwork_hash=artwork_hash
                        )
                    except Exception as exc:
                        _LOGGER.warning(
                            "AlbumArtResolver: failed to deliver artwork: %s",
                            exc,
                        )
                    return

            _LOGGER.debug(
                "AlbumArtResolver: no artwork found for %r - %r",
                metadata.artist,
                metadata.title,
            )
        finally:
            self._resolve_task = None
