import logging

from zeroconf import ServiceStateChange, Zeroconf
from zeroconf.asyncio import (
    AsyncServiceBrowser,
    AsyncServiceInfo,
    AsyncZeroconf,
)

from ledfx.events import Event
from ledfx.utils import async_fire_and_forget

_LOGGER = logging.getLogger(__name__)


class ZeroConfRunner:
    """
    Class responsible for handling zeroconf, WLED discovery and WLED device registration.

    Attributes:
        aiobrowser: The async service browser for zeroconf.
        aiozc: The async zeroconf instance.
        _ledfx: The ledfx instance.

    Methods:
        on_service_state_change: Callback function for service state change.
        async_on_service_state_change: Asynchronous function for handling WLED service state change.
        add_wled_device: Asynchronous function for adding discovered WLED devices to config.
        discover_wled_devices: Asynchronous function for discovering WLED devices.
        async_close: Asynchronous function for closing zeroconf listener.
    """

    def __init__(self, ledfx):
        self.aiobrowser = None
        self.aiozc = None
        self._ledfx = ledfx

        def on_shutdown(e):
            async_fire_and_forget(self.async_close(), self._ledfx.loop)

        self._ledfx.events.add_listener(on_shutdown, Event.LEDFX_SHUTDOWN)

    def on_service_state_change(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ):
        """
        Callback function for service state change.

        Args:
            zeroconf (Zeroconf): The zeroconf instance.
            service_type (str): The service type.
            name (str): The service name.
            state_change (ServiceStateChange): The state change event.
        """
        # Schedule the coroutine to be run on the event loop
        async_fire_and_forget(
            self.async_on_service_state_change(
                zeroconf=zeroconf,
                service_type=service_type,
                name=name,
                state_change=state_change,
            ),
            self._ledfx.loop,
        )

    async def async_on_service_state_change(
        self,
        zeroconf: Zeroconf,
        service_type: str,
        name: str,
        state_change: ServiceStateChange,
    ):
        """
        Asynchronous function for handling service state change.

        Args:
            zeroconf (Zeroconf): The zeroconf instance.
            service_type (str): The service type.
            name (str): The service name.
            state_change (ServiceStateChange): The state change event.
        """
        _LOGGER.debug(
            f"Service {name} of type {service_type} state changed: {state_change}"
        )
        if state_change is not ServiceStateChange.Added:
            return

        async_fire_and_forget(
            self.add_wled_device(zeroconf, service_type, name),
            self._ledfx.loop,
        )

    async def add_wled_device(
        self, zeroconf: Zeroconf, service_type: str, name: str
    ) -> None:
        """
        Asynchronous function for feeding discovered WLED devices to add_new_device.

        Duplicate detection is handled within add_new_device.

        Args:
            zeroconf (Zeroconf): The zeroconf instance.
            service_type (str): The service type.
            name (str): The service name.
        """
        info = AsyncServiceInfo(service_type, name)
        await info.async_request(zeroconf, 3000)
        if info:
            hostname = str(info.server).rstrip(".")
            _LOGGER.info(f"Found WLED device: {hostname}")

            device_type = "wled"
            device_config = {"ip_address": hostname}

            def handle_exception(future):
                # Ignore exceptions, these will be raised when a device is found that already exists
                exc = future.exception()

            async_fire_and_forget(
                self._ledfx.devices.add_new_device(device_type, device_config),
                loop=self._ledfx.loop,
                exc_handler=handle_exception,
            )

    async def discover_wled_devices(self) -> None:
        """
        Asynchronous function for discovering WLED devices.
        """
        self.aiozc = AsyncZeroconf()
        services = ["_wled._tcp.local."]
        _LOGGER.info("Browsing for WLED devices...")
        self.aiobrowser = AsyncServiceBrowser(
            self.aiozc.zeroconf,
            services,
            handlers=[self.on_service_state_change],
        )

    async def async_close(self) -> None:
        """
        Asynchronous function for closing zeroconf listener.
        """
        # If aiobrowser exists, then aiozc must also exist.
        if self.aiobrowser:
            _LOGGER.info("Closing zeroconf listener.")
            await self.aiobrowser.async_cancel()
            await self.aiozc.async_close()
            _LOGGER.info("Zeroconf closed.")
