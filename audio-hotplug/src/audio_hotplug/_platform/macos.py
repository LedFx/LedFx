"""macOS audio device monitor using CoreAudio framework."""

# Implementation will be added in Phase 2
# This is a placeholder to establish the module structure

from .._base import AudioDeviceMonitor, Callback


class MacOSAudioDeviceMonitor(AudioDeviceMonitor):
    """macOS audio device monitor using CoreAudio property listeners."""

    def start(self, on_change: Callback) -> None:
        """Start monitoring using CoreAudio."""
        raise NotImplementedError("macOS monitor implementation pending (Phase 2)")

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
