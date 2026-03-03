"""
Cross-platform audio device change monitoring.

Listens for OS-level audio device add/remove events and fires LedFx events.
"""

import asyncio
import logging
import sys
import threading
from abc import ABC, abstractmethod

_LOGGER = logging.getLogger(__name__)


class AudioDeviceMonitor(ABC):
    """Abstract base class for platform-specific audio device monitors."""

    def __init__(self, ledfx_instance, loop):
        self._ledfx = ledfx_instance
        self._loop = loop
        self._running = False
        self._monitor_thread = None

    @abstractmethod
    def start_monitoring(self):
        """Start monitoring for device changes."""
        pass

    @abstractmethod
    def stop_monitoring(self):
        """Stop monitoring for device changes."""
        pass

    def _fire_device_list_changed_event(self):
        """Fire event when device list changes - must be called from monitor thread."""
        if self._loop and self._ledfx:
            # Schedule the event on the main loop from the monitor thread
            asyncio.run_coroutine_threadsafe(
                self._async_fire_device_list_changed_event(), self._loop
            )

    async def _async_fire_device_list_changed_event(self):
        """Fire the device list changed event (async)."""
        from ledfx.events import AudioDeviceListChangedEvent

        _LOGGER.info("Audio device list changed - firing event")
        self._ledfx.events.fire_event(AudioDeviceListChangedEvent())


class WindowsAudioDeviceMonitor(AudioDeviceMonitor):
    """Windows audio device monitor using Core Audio API."""

    def start_monitoring(self):
        """Start monitoring using IMMNotificationClient."""
        try:
            from ctypes import POINTER

            import comtypes
            from comtypes import COMMETHOD, GUID
            from pycaw.constants import CLSID_MMDeviceEnumerator
            from pycaw.pycaw import IMMDeviceEnumerator

            _LOGGER.info("Starting Windows audio device monitor")

            # Define IMMNotificationClient interface for comtypes
            class IMMNotificationClient(comtypes.IUnknown):
                _iid_ = GUID("{7991EEC9-7E89-4D85-8390-6C703CEC60C0}")
                _methods_ = [
                    COMMETHOD(
                        [],
                        comtypes.HRESULT,
                        "OnDeviceStateChanged",
                        (["in"], comtypes.c_wchar_p, "pwstrDeviceId"),
                        (["in"], comtypes.c_ulong, "dwNewState"),
                    ),
                    COMMETHOD(
                        [],
                        comtypes.HRESULT,
                        "OnDeviceAdded",
                        (["in"], comtypes.c_wchar_p, "pwstrDeviceId"),
                    ),
                    COMMETHOD(
                        [],
                        comtypes.HRESULT,
                        "OnDeviceRemoved",
                        (["in"], comtypes.c_wchar_p, "pwstrDeviceId"),
                    ),
                    COMMETHOD(
                        [],
                        comtypes.HRESULT,
                        "OnDefaultDeviceChanged",
                        (["in"], comtypes.c_int, "flow"),
                        (["in"], comtypes.c_int, "role"),
                        (["in"], comtypes.c_wchar_p, "pwstrDefaultDeviceId"),
                    ),
                    COMMETHOD(
                        [],
                        comtypes.HRESULT,
                        "OnPropertyValueChanged",
                        (["in"], comtypes.c_wchar_p, "pwstrDeviceId"),
                        (["in"], POINTER(comtypes.c_int), "key"),
                    ),
                ]

            # Create concrete implementation
            class DeviceNotificationClient(comtypes.COMObject):
                _com_interfaces_ = [IMMNotificationClient]

                def __init__(self, callback):
                    super().__init__()
                    self.callback = callback

                def IMMNotificationClient_OnDeviceAdded(self, pwstrDeviceId):
                    _LOGGER.debug(f"Device added: {pwstrDeviceId}")
                    self.callback()
                    return 0

                def IMMNotificationClient_OnDeviceRemoved(self, pwstrDeviceId):
                    _LOGGER.debug(f"Device removed: {pwstrDeviceId}")
                    self.callback()
                    return 0

                def IMMNotificationClient_OnDeviceStateChanged(
                    self, pwstrDeviceId, dwNewState
                ):
                    _LOGGER.debug(
                        f"Device state changed: {pwstrDeviceId} state={dwNewState}"
                    )
                    self.callback()
                    return 0

                def IMMNotificationClient_OnDefaultDeviceChanged(
                    self, flow, role, pwstrDefaultDeviceId
                ):
                    _LOGGER.debug(
                        f"Default device changed: {pwstrDefaultDeviceId}"
                    )
                    # Don't fire event for default device change, only for list changes
                    return 0

                def IMMNotificationClient_OnPropertyValueChanged(
                    self, pwstrDeviceId, key
                ):
                    # Properties changing doesn't mean the device list changed
                    return 0

            # Register for notifications (must run on separate thread to avoid blocking)
            def monitor_thread():
                comtypes.CoInitialize()
                try:
                    device_enumerator = comtypes.CoCreateInstance(
                        CLSID_MMDeviceEnumerator,
                        IMMDeviceEnumerator,
                        comtypes.CLSCTX_INPROC_SERVER,
                    )

                    # Create notification client in this thread (COM apartment threading)
                    self._notification_client = DeviceNotificationClient(
                        self._fire_device_list_changed_event
                    )

                    device_enumerator.RegisterEndpointNotificationCallback(
                        self._notification_client
                    )
                    self._device_enumerator = device_enumerator
                    _LOGGER.info("Windows audio device monitor started")

                    # Keep thread alive - COM callbacks are event-driven by Windows
                    # We just wait here until stop_monitoring() is called
                    self._stop_event.wait()

                finally:
                    try:
                        if hasattr(self, "_device_enumerator") and hasattr(
                            self, "_notification_client"
                        ):
                            self._device_enumerator.UnregisterEndpointNotificationCallback(
                                self._notification_client
                            )
                    except Exception:
                        pass
                    comtypes.CoUninitialize()

            # Initialize state before starting thread to avoid race conditions
            self._stop_event = threading.Event()
            self._running = True
            
            self._monitor_thread = threading.Thread(
                target=monitor_thread, daemon=True, name="AudioDeviceMonitor"
            )
            self._monitor_thread.start()

        except ImportError:
            _LOGGER.warning(
                "pycaw not available - cannot monitor Windows audio device changes. "
                "Install with: pip install pycaw"
            )
        except Exception as e:
            _LOGGER.error(
                f"Failed to start Windows audio device monitor: {e}",
                exc_info=True,
            )

    def stop_monitoring(self):
        """Stop monitoring."""
        self._running = False
        if hasattr(self, "_stop_event"):
            self._stop_event.set()  # Wake up the waiting thread
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        _LOGGER.info("Windows audio device monitor stopped")


class MacOSAudioDeviceMonitor(AudioDeviceMonitor):
    """macOS audio device monitor using CoreAudio."""

    def start_monitoring(self):
        """Start monitoring using CoreAudio property listeners."""
        try:
            from CoreAudio import (
                AudioObjectAddPropertyListener,
                AudioObjectPropertyAddress,
                kAudioHardwarePropertyDevices,
                kAudioObjectPropertyElementMaster,
                kAudioObjectPropertyScopeGlobal,
                kAudioObjectSystemObject,
            )

            _LOGGER.info("Starting macOS audio device monitor")

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
                _LOGGER.debug("macOS audio device list changed")
                self._fire_device_list_changed_event()
                return 0  # Return success

            # Register listener
            AudioObjectAddPropertyListener(
                kAudioObjectSystemObject,
                property_address,
                device_list_changed_callback,
                None,
            )

            self._running = True
            self._property_address = property_address
            self._callback = device_list_changed_callback
            _LOGGER.info("macOS audio device monitor started")

        except ImportError:
            _LOGGER.warning(
                "pyobjc-framework-CoreAudio not available - cannot monitor macOS audio device changes. "
                "Install with: pip install pyobjc-framework-CoreAudio"
            )
        except Exception as e:
            _LOGGER.error(
                f"Failed to start macOS audio device monitor: {e}",
                exc_info=True,
            )

    def stop_monitoring(self):
        """Stop monitoring."""
        if self._running and hasattr(self, "_property_address"):
            try:
                from CoreAudio import (
                    AudioObjectRemovePropertyListener,
                    kAudioObjectSystemObject,
                )

                AudioObjectRemovePropertyListener(
                    kAudioObjectSystemObject,
                    self._property_address,
                    self._callback,
                    None,
                )
            except Exception:
                pass
        self._running = False
        _LOGGER.info("macOS audio device monitor stopped")


class LinuxAudioDeviceMonitor(AudioDeviceMonitor):
    """Linux audio device monitor using udev."""

    def start_monitoring(self):
        """Start monitoring using pyudev."""
        try:
            import pyudev

            _LOGGER.info("Starting Linux audio device monitor")

            context = pyudev.Context()
            monitor = pyudev.Monitor.from_netlink(context)
            monitor.filter_by(subsystem="sound")

            def monitor_thread():
                _LOGGER.info("Linux audio device monitor started")

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
                            _LOGGER.debug(
                                f"Sound device {device.action}: {device.device_node}"
                            )
                            self._fire_device_list_changed_event()

                except Exception as e:
                    _LOGGER.error(
                        f"Error in Linux audio device monitor: {e}",
                        exc_info=True,
                    )

            # Initialize state before starting thread to avoid race conditions
            self._running = True
            
            self._monitor_thread = threading.Thread(
                target=monitor_thread, daemon=True, name="AudioDeviceMonitor"
            )
            self._monitor_thread.start()

        except ImportError:
            _LOGGER.warning(
                "pyudev not available - cannot monitor Linux audio device changes. "
                "Install with: pip install pyudev"
            )
        except Exception as e:
            _LOGGER.error(
                f"Failed to start Linux audio device monitor: {e}",
                exc_info=True,
            )

    def stop_monitoring(self):
        """Stop monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)
        _LOGGER.info("Linux audio device monitor stopped")


def create_audio_device_monitor(ledfx_instance, loop):
    """
    Factory function to create the appropriate audio device monitor for the current platform.

    Args:
        ledfx_instance: LedFx core instance
        loop: asyncio event loop

    Returns:
        Platform-specific AudioDeviceMonitor instance, or None if platform unsupported
    """
    if sys.platform == "win32":
        return WindowsAudioDeviceMonitor(ledfx_instance, loop)
    elif sys.platform == "darwin":
        return MacOSAudioDeviceMonitor(ledfx_instance, loop)
    elif sys.platform.startswith("linux"):
        return LinuxAudioDeviceMonitor(ledfx_instance, loop)
    else:
        _LOGGER.warning(
            f"Audio device monitoring not supported on platform: {sys.platform}"
        )
        return None
