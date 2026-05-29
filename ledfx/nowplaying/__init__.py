"""Now Playing Service for LedFx.

Provides a centralized, provider-neutral source of truth for current media
playback metadata, artwork references, and artwork-derived gradients.

The service receives normalized metadata from providers (Sendspin, Spotify,
MPRIS, etc.) and exposes it to effects, the frontend, and other LedFx
subsystems via internal APIs and events.
"""

from ledfx.nowplaying.service import NowPlayingService

__all__ = ["NowPlayingService"]
