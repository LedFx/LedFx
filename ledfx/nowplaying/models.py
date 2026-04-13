from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class NowPlayingTrack:
    """Normalized track metadata from any provider."""

    provider: str
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    art_url: str | None = None
    duration: float | None = None
    position: float | None = None
    is_playing: bool | None = None
    player_name: str | None = None
    source_id: str | None = None
    raw: dict[str, Any] | None = None

    def signature(self) -> str:
        """Stable identity for dedupe. Changes only on meaningful track change."""
        parts = [
            self.provider or "",
            self.player_name or "",
            self.title or "",
            self.artist or "",
            self.album or "",
        ]
        return hashlib.md5("|".join(parts).encode()).hexdigest()

    def art_signature(self) -> str:
        """Identity for art URL dedupe."""
        return hashlib.md5((self.art_url or "").encode()).hexdigest()

    def to_dict(self) -> dict:
        return {
            "provider": self.provider,
            "title": self.title,
            "artist": self.artist,
            "album": self.album,
            "art_url": self.art_url,
            "duration": self.duration,
            "position": self.position,
            "is_playing": self.is_playing,
            "player_name": self.player_name,
            "source_id": self.source_id,
        }


@dataclass(slots=True)
class NowPlayingState:
    """Current state of the now-playing subsystem."""

    enabled: bool = False
    status: str = "disabled"  # disabled, idle, starting, running, degraded, error
    provider_name: str | None = None
    active_track: NowPlayingTrack | None = None
    active_art_url: str | None = None
    active_art_cache_key: str | None = None
    active_palette_id: str | None = None
    active_gradient: str | None = None
    palette_applied: bool = False
    last_update_ts: float | None = None
    last_track_signature: str | None = None
    last_art_signature: str | None = None
    last_error: str | None = None

    def to_dict(self) -> dict:
        return {
            "enabled": self.enabled,
            "status": self.status,
            "provider_name": self.provider_name,
            "active_track": self.active_track.to_dict() if self.active_track else None,
            "active_art_url": self.active_art_url,
            "active_art_cache_key": self.active_art_cache_key,
            "active_palette_id": self.active_palette_id,
            "active_gradient": self.active_gradient,
            "palette_applied": self.palette_applied,
            "last_update_ts": self.last_update_ts,
            "last_track_signature": self.last_track_signature,
            "last_error": self.last_error,
        }
