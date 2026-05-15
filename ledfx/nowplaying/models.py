"""Data models for the Now Playing Service."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class TrackMetadata:
    """Normalized track metadata from any provider."""

    source_id: str

    title: Optional[str] = None
    artist: Optional[str] = None
    album: Optional[str] = None

    duration: Optional[float] = None
    position: Optional[float] = None

    track_id: Optional[str] = None

    artwork_url: Optional[str] = None
    artwork_hash: Optional[str] = None

    updated_at: Optional[float] = None

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
            "duration": self.duration,
            "position": self.position,
            "track_id": self.track_id,
            "artwork_url": self.artwork_url,
            "artwork_hash": self.artwork_hash,
            "updated_at": self.updated_at,
        }


@dataclass
class ArtworkReference:
    """Reference to cached artwork and its extracted gradients."""

    source_id: str

    url: Optional[str] = None
    cache_key: Optional[str] = None

    content_type: Optional[str] = None
    hash: Optional[str] = None

    width: Optional[int] = None
    height: Optional[int] = None

    gradients: Optional[dict] = None

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

    active_source_id: Optional[str] = None

    metadata: Optional[TrackMetadata] = None
    artwork: Optional[ArtworkReference] = None

    selected_gradient_variant: str = "led_punchy"
    current_gradient: Optional[str] = None

    updated_at: Optional[float] = None

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
