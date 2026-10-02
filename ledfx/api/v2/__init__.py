"""LedFx API v2: typed handlers on aiohttp, served under /api/v2."""

from ledfx.api.v2.core.app import mount_v2
from ledfx.api.v2.core.binding import LedFxDep
from ledfx.api.v2.core.partial import Partial, Patch
from ledfx.api.v2.core.router import Binary, Router, register

__all__ = [
    "Binary",
    "LedFxDep",
    "Partial",
    "Patch",
    "Router",
    "mount_v2",
    "register",
]
