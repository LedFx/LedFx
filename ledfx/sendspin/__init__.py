"""Sendspin audio source integration for LedFx.

This module provides integration with Sendspin synchronized multi-room audio servers.

Requirements:
    - Python 3.12+ (aiosendspin dependency)
    - Running Sendspin server

For Python < 3.12, the module will gracefully no-op and Sendspin won't appear
as an available audio source.
"""

import sys

# Only expose Sendspin functionality on Python 3.12+
if sys.version_info >= (3, 12):
    try:
        from ledfx.sendspin.stream import SendspinAudioStream # noqa: F401

        __all__ = ["SendspinAudioStream"]
        SENDSPIN_AVAILABLE = True
    except ImportError:
        # aiosendspin not available
        SENDSPIN_AVAILABLE = False
        __all__ = []
else:
    SENDSPIN_AVAILABLE = False
    __all__ = []
