from __future__ import annotations

from typing import Awaitable, Callable, Protocol

from ledfx.nowplaying.models import NowPlayingTrack


class NowPlayingProvider(Protocol):
    """Minimal contract for now-playing metadata providers."""

    async def start(
        self,
        callback: Callable[[NowPlayingTrack], Awaitable[None]],
    ) -> None: ...

    async def stop(self) -> None: ...
