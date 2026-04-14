"""Sendspin audio source integration for LedFx.

This module provides integration with Sendspin synchronized multi-room audio servers.

Requirements:
    - Python 3.12+ (aiosendspin dependency)
    - Running Sendspin server

For Python < 3.12, the module will gracefully no-op and Sendspin won't appear
as an available audio source.
"""

import logging
import sys

_LOGGER = logging.getLogger(__name__)

# Only expose Sendspin functionality on Python 3.12+
if sys.version_info >= (3, 12):
    _LOGGER.debug("[SENDSPIN] Python %s >= 3.12, attempting import", sys.version_info)
    try:
        from ledfx.sendspin.stream import SendspinAudioStream  # noqa: F401

        __all__ = ["SendspinAudioStream"]
        SENDSPIN_AVAILABLE = True
        _LOGGER.debug("[SENDSPIN] Import succeeded, SENDSPIN_AVAILABLE=True")
    except (ImportError, OSError) as _exc:
        # aiosendspin not available, or native library (e.g. libFLAC.dll) failed to load
        SENDSPIN_AVAILABLE = False
        __all__ = []
        _LOGGER.debug("[SENDSPIN] Import failed (%s), SENDSPIN_AVAILABLE=False", _exc)
else:
    SENDSPIN_AVAILABLE = False
    __all__ = []
    _LOGGER.debug("[SENDSPIN] Python %s < 3.12, SENDSPIN_AVAILABLE=False", sys.version_info)
