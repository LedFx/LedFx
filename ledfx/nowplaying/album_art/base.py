"""Base class for album-art providers."""

from abc import ABC, abstractmethod

from ledfx.nowplaying.models import TrackMetadata


class AlbumArtProvider(ABC):
    """Asynchronously resolve album art from track metadata.

    Implementations should be stateless where possible.  All network
    failures must be caught internally and returned as ``None``.
    """

    @abstractmethod
    async def resolve(self, metadata: TrackMetadata) -> bytes | None:
        """Return raw image bytes for the given track, or None if not found.

        Args:
            metadata: Normalized track metadata from any now-playing source.

        Returns:
            Raw image bytes (JPEG, PNG, etc.) or None if the provider
            could not find artwork.
        """
        ...
