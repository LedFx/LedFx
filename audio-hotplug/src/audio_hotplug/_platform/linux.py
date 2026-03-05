"""Linux audio device monitor using udev."""

# Implementation will be added in Phase 2
# This is a placeholder to establish the module structure

from .._base import AudioDeviceMonitor, Callback


class LinuxAudioDeviceMonitor(AudioDeviceMonitor):
    """Linux audio device monitor using pyudev."""

    def start(self, on_change: Callback) -> None:
        """Start monitoring using pyudev."""
        raise NotImplementedError("Linux monitor implementation pending (Phase 2)")

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
