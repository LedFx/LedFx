"""Windows audio device monitor using Core Audio API (pycaw)."""

# Implementation will be added in Phase 2
# This is a placeholder to establish the module structure

import threading

from .._base import AudioDeviceMonitor, Callback


class WindowsAudioDeviceMonitor(AudioDeviceMonitor):
    """Windows audio device monitor using IMMNotificationClient."""

    def start(self, on_change: Callback) -> None:
        """Start monitoring using Core Audio API."""
        raise NotImplementedError(
            "Windows monitor implementation pending (Phase 2)"
        )

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
