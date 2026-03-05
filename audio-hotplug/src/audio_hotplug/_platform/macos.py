"""macOS audio device monitor using CoreAudio framework."""

import logging

from .._base import AudioDeviceMonitor, Callback

_LOGGER = logging.getLogger(__name__)


class MacOSAudioDeviceMonitor(AudioDeviceMonitor):
    """macOS audio device monitor using CoreAudio property listeners."""

    def start(self, on_change: Callback) -> None:
        """Start monitoring using CoreAudio property listeners."""
        # Initialize debouncer with user callback
        self._initialize_debouncer(on_change)

        try:
            from CoreAudio import (
                AudioObjectAddPropertyListener,
                AudioObjectPropertyAddress,
                kAudioHardwarePropertyDevices,
                kAudioObjectPropertyElementMaster,
                kAudioObjectPropertyScopeGlobal,
                kAudioObjectSystemObject,
            )

            self._logger.info("Starting macOS audio device monitor")

            # Create property address for device list
            property_address = AudioObjectPropertyAddress(
                kAudioHardwarePropertyDevices,
                kAudioObjectPropertyScopeGlobal,
                kAudioObjectPropertyElementMaster,
            )

            # Callback function for property changes
            def device_list_changed_callback(
                obj_id, num_addresses, addresses, client_data
            ):
                self._logger.debug("macOS audio device list changed")
                self._debouncer.trigger()
                return 0  # Return success

            # Register listener
            AudioObjectAddPropertyListener(
                kAudioObjectSystemObject,
                property_address,
                device_list_changed_callback,
                None,
            )

            self._property_address = property_address
            self._callback_ref = device_list_changed_callback
            self._logger.info("macOS audio device monitor started")

        except ImportError as e:
            self._logger.warning(
                f"pyobjc-framework-CoreAudio not available: {e}. "
                "Install with: uv pip install 'audio-hotplug[macos]'"
            )
            raise
        except Exception as e:
            self._logger.error(
                f"Failed to start macOS audio device monitor: {e}",
                exc_info=True,
            )
            raise

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False

        if hasattr(self, "_property_address") and hasattr(self, "_callback_ref"):
            try:
                from CoreAudio import (
                    AudioObjectRemovePropertyListener,
                    kAudioObjectSystemObject,
                )

                AudioObjectRemovePropertyListener(
                    kAudioObjectSystemObject,
                    self._property_address,
                    self._callback_ref,
                    None,
                )
                self._logger.info("macOS audio device monitor stopped")
            except Exception as e:
                self._logger.warning(
                    f"Error stopping macOS monitor: {e}", exc_info=True
                )

        if self._debouncer:
            self._debouncer.cancel()
