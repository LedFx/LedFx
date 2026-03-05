"""Linux audio device monitor using udev."""

import logging
import threading

from .._base import AudioDeviceMonitor, Callback

_LOGGER = logging.getLogger(__name__)


class LinuxAudioDeviceMonitor(AudioDeviceMonitor):
    """Linux audio device monitor using pyudev."""

    def start(self, on_change: Callback) -> None:
        """Start monitoring using pyudev."""
        # Initialize debouncer with user callback
        self._initialize_debouncer(on_change)

        try:
            import pyudev

            self._logger.info("Starting Linux audio device monitor")

            context = pyudev.Context()
            monitor = pyudev.Monitor.from_netlink(context)
            monitor.filter_by(subsystem="sound")

            def monitor_thread():
                self._logger.info("Linux audio device monitor started")

                try:
                    # Use timeout to allow periodic checking of _running flag
                    while self._running:
                        device = monitor.poll(timeout=1.0)
                        if device is None:
                            # Timeout - no event, loop again to check _running
                            continue

                        if not self._running:
                            break

                        if device.action in ("add", "remove"):
                            self._logger.debug(
                                f"Sound device {device.action}: {device.device_node}"
                            )
                            self._debouncer.trigger()

                except Exception as e:
                    self._logger.error(
                        f"Error in Linux audio device monitor: {e}",
                        exc_info=True,
                    )

            self._monitor_thread = threading.Thread(
                target=monitor_thread, daemon=True, name="AudioDeviceMonitor"
            )
            self._monitor_thread.start()

        except ImportError as e:
            self._logger.warning(
                f"pyudev not available: {e}. "
                "Install with: uv pip install 'audio-hotplug[linux]'"
            )
            raise
        except Exception as e:
            self._logger.error(
                f"Failed to start Linux audio device monitor: {e}",
                exc_info=True,
            )
            raise

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False

        if hasattr(self, "_monitor_thread") and self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
            self._logger.info("Linux audio device monitor stopped")

        if self._debouncer:
            self._debouncer.cancel()
