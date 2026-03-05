"""Windows audio device monitor using Core Audio API (pycaw)."""

import logging
import threading

from .._base import AudioDeviceMonitor, Callback

_LOGGER = logging.getLogger(__name__)


class WindowsAudioDeviceMonitor(AudioDeviceMonitor):
    """Windows audio device monitor using IMMNotificationClient."""

    def start(self, on_change: Callback) -> None:
        """Start monitoring using Core Audio API."""
        # Initialize debouncer with user callback
        self._initialize_debouncer(on_change)

        try:
            from ctypes import POINTER

            import comtypes
            from comtypes import COMMETHOD, GUID
            from pycaw.constants import CLSID_MMDeviceEnumerator
            from pycaw.pycaw import IMMDeviceEnumerator

            self._logger.info("Starting Windows audio device monitor")

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

                def __init__(self, callback, logger):
                    super().__init__()
                    self.callback = callback
                    self.logger = logger

                def IMMNotificationClient_OnDeviceAdded(self, pwstrDeviceId):
                    self.logger.debug(f"Device added: {pwstrDeviceId}")
                    self.callback()
                    return 0

                def IMMNotificationClient_OnDeviceRemoved(self, pwstrDeviceId):
                    self.logger.debug(f"Device removed: {pwstrDeviceId}")
                    self.callback()
                    return 0

                def IMMNotificationClient_OnDeviceStateChanged(
                    self, pwstrDeviceId, dwNewState
                ):
                    self.logger.debug(
                        f"Device state changed: {pwstrDeviceId} state={dwNewState}"
                    )
                    self.callback()
                    return 0

                def IMMNotificationClient_OnDefaultDeviceChanged(
                    self, flow, role, pwstrDefaultDeviceId
                ):
                    self.logger.debug(
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
                    # Trigger debouncer when device changes occur
                    self._notification_client = DeviceNotificationClient(
                        lambda: self._debouncer.trigger(), self._logger
                    )

                    device_enumerator.RegisterEndpointNotificationCallback(
                        self._notification_client
                    )
                    self._device_enumerator = device_enumerator
                    self._logger.info("Windows audio device monitor started")

                    # Keep thread alive - COM callbacks are event-driven by Windows
                    # We just wait here until stop() is called
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

            self._monitor_thread = threading.Thread(
                target=monitor_thread, daemon=True, name="AudioDeviceMonitor"
            )
            self._monitor_thread.start()

        except ImportError as e:
            self._logger.warning(
                f"pycaw not available - cannot monitor Windows audio device changes: {e}. "
                "Install with: uv pip install 'audio-hotplug[windows]'"
            )
            raise
        except Exception as e:
            self._logger.error(
                f"Failed to start Windows audio device monitor: {e}",
                exc_info=True,
            )
            raise

    def stop(self) -> None:
        """Stop monitoring."""
        self._running = False
        if hasattr(self, "_stop_event"):
            self._stop_event.set()  # Wake up the waiting thread
        if self._debouncer:
            self._debouncer.cancel()
