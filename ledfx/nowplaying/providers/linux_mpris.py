"""
Linux MPRIS2 provider (stub).

Future implementation will use D-Bus to read MPRIS2 media session data.
Currently reports as unavailable.
"""

from __future__ import annotations

import logging
from collections.abc import Awaitable
from typing import Callable

from ledfx.nowplaying.models import NowPlayingTrack

_LOGGER = logging.getLogger(__name__)

_AVAILABLE = False
_UNAVAILABLE_REASON = "Linux MPRIS2 reading not yet implemented"


def is_available() -> bool:
    return _AVAILABLE


def unavailable_reason() -> str:
    return _UNAVAILABLE_REASON


class LinuxMPRISProvider:
    """Stub provider for Linux MPRIS2 media sessions."""

    PROVIDER_NAME = "linux_mpris"

    def __init__(self):
        pass

    async def start(
        self,
        callback: Callable[[NowPlayingTrack], Awaitable[None]],
    ) -> None:
        raise RuntimeError(
            f"Linux MPRIS provider unavailable: {_UNAVAILABLE_REASON}"
        )

    async def stop(self) -> None:
        pass
