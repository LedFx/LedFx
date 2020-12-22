from ledfx.utils import BaseRegistry, RegistryLoader, generate_id, async_fire_and_forget
from ledfx.config import save_config
from ledfx.events import DeviceUpdateEvent, Event
from abc import abstractmethod
import voluptuous as vol
import numpy as np
import requests
import logging
import asyncio

_LOGGER = logging.getLogger(__name__)


@BaseRegistry.no_registration
class Integration(BaseRegistry):

    # STATUS REFERENCE
    # 0: disconnected
    # 1: connected
    # 2: disconnecting
    # 3: connecting

    def __init__(self, ledfx, config, active, data):
        self._ledfx = ledfx
        self._config = config
        self._active = active
        self._data = data
        self._status = 0

    def __del__(self):
        if self._active:
            self.deactivate()

    async def activate(self):
        _LOGGER.info(("Activating {} integration").format(self._config["name"]))
        self._active = True
        self._status = 3
        await self.connect()
        self._status = 1

    async def deactivate(self):
        _LOGGER.info(("Deactivating {} integration").format(self._config["name"]))
        self._active = False
        self._status = 2
        await self.disconnect()
        self._status = 0

    async def reconnect(self):
        _LOGGER.info(("Reconnecting {} integration").format(self._config["name"]))
        self._status = 2
        await self.disconnect()
        self._status = 3
        await self.connect()
        self._status = 1

    async def connect(self):
        """
        Establish a connection with the service.
        This abstract method must be overwritten by the integration implementation.
        """
        pass

    async def disconnect(self):
        """
        Disconnect from the service.
        This abstract method must be overwritten by the integration implementation.
        """
        pass

    def on_shutdown(self):
        """
        Integrations should reimplement this if there's anything they need to do on shutdown to close cleanly.
        This abstract method must be overwritten by the integration implementation.
        """
        pass

    @property
    def name(self):
        return self._config["name"]

    @property
    def description(self):
        return self._config["description"]

    @property
    def status(self):
        return self._status

    @property
    def active(self):
        return self._active

    @property
    def data(self):
        return self._data


class Integrations(RegistryLoader):
    """Thin wrapper around the integration registry that manages integrations"""

    PACKAGE_NAME = "ledfx.integrations"

    def __init__(self, ledfx):
        super().__init__(ledfx, Integration, self.PACKAGE_NAME)

        def on_shutdown(e):
            for integration in self.values():
                integration.on_shutdown()
            # TODO Make sure program lets this finish before closing!
            async_fire_and_forget(self.close_all_connections(), self._ledfx.loop)

        def notify_shutdown(e):
            self.notify_shutdown()

        self._ledfx.events.add_listener(on_shutdown, Event.LEDFX_SHUTDOWN)

    def create_from_config(self, config):
        for integration in config:
            _LOGGER.info("Loading integration from config: {}".format(integration))
            self._ledfx.integrations.create(
                id=integration["id"],
                type=integration["type"],
                active=integration["active"],
                config=integration["config"],
                data=integration["data"],
                ledfx=self._ledfx,
            )

    async def close_all_connections(self):
        for integration in self.values():
            await integration.deactivate()

    async def activate_integrations(self):
        for integration in self.values():
            if integration._active:
                await integration.activate()
