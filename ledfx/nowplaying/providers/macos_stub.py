"""
macOS now-playing provider (stub).

Future implementation may use NSAppleScript or MediaRemote framework.
Currently reports as unavailable.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable
from typing import Callable

from ledfx.nowplaying.models import NowPlayingTrack

_LOGGER = logging.getLogger(__name__)

_AVAILABLE = False
_UNAVAILABLE_REASON = "macOS media reading not yet implemented"


def is_available() -> bool:
    return _AVAILABLE


def unavailable_reason() -> str:
    return _UNAVAILABLE_REASON


class MacOSNowPlayingProvider:
    """Stub provider for macOS now-playing sessions."""

    PROVIDER_NAME = "macos_nowplaying"

    def __init__(self, poll_interval: float = 2.0):
        self._poll_interval = poll_interval

    async def start(
        self,
        callback: Callable[[NowPlayingTrack], Awaitable[None]],
    ) -> None:
        raise RuntimeError(
            f"macOS provider unavailable: {_UNAVAILABLE_REASON}"
        )

    async def stop(self) -> None:
        pass
