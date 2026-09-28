"""Data models for the Now Playing Service."""

from dataclasses import dataclass


@dataclass
class TrackMetadata:
    """Normalized track metadata from any provider."""

    source_id: str

    title: str | None = None
    artist: str | None = None
    album: str | None = None

    track_id: str | None = None

    artwork_url: str | None = None
    artwork_hash: str | None = None

    updated_at: float | None = None

    def track_identity(self) -> tuple:
        """Return a tuple representing the track identity for change detection.

        A change in any of these fields indicates a new track.
        """
        return (self.title, self.artist, self.album, self.track_id)

    def to_dict(self) -> dict:
        """Serialize to a plain dict for API responses."""
        return {
            "source_id": self.source_id,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "track_id": self.track_id,
            "artwork_url": self.artwork_url,
            "artwork_hash": self.artwork_hash,
            "updated_at": self.updated_at,
        }


@dataclass
class ArtworkReference:
    """Reference to cached artwork and its extracted gradients."""

    source_id: str

    url: str | None = None
    cache_key: str | None = None

    content_type: str | None = None
    hash: str | None = None

    width: int | None = None
    height: int | None = None

    gradients: dict | None = None

    def to_dict(self) -> dict:
        """Serialize to a plain dict for API responses."""
        return {
            "source_id": self.source_id,
            "url": self.url,
            "cache_key": self.cache_key,
            "content_type": self.content_type,
            "hash": self.hash,
            "width": self.width,
            "height": self.height,
            "gradients": self.gradients,
        }


@dataclass
class NowPlayingState:
    """Complete current state of the Now Playing Service."""

    active_source_id: str | None = None

    metadata: TrackMetadata | None = None
    artwork: ArtworkReference | None = None

    selected_gradient_variant: str = "led_punchy"
    current_gradient: str | None = None

    updated_at: float | None = None

    def to_dict(self) -> dict:
        """Serialize to a plain dict for API responses."""
        return {
            "active_source_id": self.active_source_id,
            "metadata": self.metadata.to_dict() if self.metadata else None,
            "artwork": self.artwork.to_dict() if self.artwork else None,
            "selected_gradient_variant": self.selected_gradient_variant,
            "current_gradient": self.current_gradient,
            "updated_at": self.updated_at,
        }
