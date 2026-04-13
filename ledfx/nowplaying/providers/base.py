from __future__ import annotations

from collections.abc import Awaitable
from typing import Callable, Protocol

from ledfx.nowplaying.models import NowPlayingTrack


class NowPlayingProvider(Protocol):
    """Minimal contract for now-playing metadata providers."""

    async def start(
        self,
        callback: Callable[[NowPlayingTrack], Awaitable[None]],
    ) -> None:
        """Start the provider, calling *callback* on each track change."""

    async def stop(self) -> None:
        """Stop the provider and release resources."""
