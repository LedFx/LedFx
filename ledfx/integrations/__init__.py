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

    _active = False
    _status = None

    def __init__(self, ledfx, config, active):
        self._ledfx = ledfx
        self._config = config
        self._active = active

    def __del__(self):
        if self._active:
            self.deactivate()

    async def activate(self):
        _LOGGER.info(("Activating {} integration").format(self._config["name"]))
        self._active = True
        await self.connect()

    async def deactivate(self):
        _LOGGER.info(("Deactivating {} integration").format(self._config["name"]))
        self._active = False
        await self.disconnect()

    async def reconnect(self):
        _LOGGER.info(("Reconnecting {} integration").format(self._config["name"]))
        await self.disconnect()
        await self.connect()

    async def connect(self):
        pass
        """
        Establish a connection with the service.
        This abstract method must be overwritten by the integration implementation.
        """

    async def disconnect(self):
        pass
        """
        Disconnect from the service.
        This abstract method must be overwritten by the integration implementation.
        """

    def save_data(self):
        return None
        """
        Integrations should reimplement this to return their data that will be saved in config.yaml.
        This abstract method must be overwritten by the integration implementation.
        """

    def on_shutdown(self):
        data = self.save_data()
        self._config["data"] = data

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
