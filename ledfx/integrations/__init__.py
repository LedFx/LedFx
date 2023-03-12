# from abc import abstractmethod
# import voluptuous as vol
# import numpy as np
# import requests
import logging
from enum import IntEnum

# from ledfx.config import save_config
from ledfx.events import Event
from ledfx.utils import BaseRegistry, RegistryLoader, async_fire_and_forget

# import asyncio

_LOGGER = logging.getLogger(__name__)


class Status(IntEnum):
    DISCONNECTED = 0
    CONNECTED = 1
    DISCONNECTING = 2
    CONNECTING = 3


@BaseRegistry.no_registration
class Integration(BaseRegistry):
    beta = True  # Over ride in child classes to publish

    def __init__(self, ledfx, config, active, data):
        self._ledfx = ledfx
        self._config = config
        self._active = active
        self._data = data
        self._status = Status.DISCONNECTED

    def __del__(self):
        if self._active:
            async_fire_and_forget(self.deactivate(), self._ledfx.loop)

    async def activate(self):
        _LOGGER.info(
            ("Activating {} integration").format(self._config["name"])
        )
        self._active = True
        self._status = Status.CONNECTING
        async_fire_and_forget(self.connect(), self._ledfx.loop)

    async def deactivate(self):
        _LOGGER.info(
            ("Deactivating {} integration").format(self._config["name"])
        )
        self._active = False
        self._status = Status.DISCONNECTING
        async_fire_and_forget(self.disconnect(), self._ledfx.loop)

    async def reconnect(self):
        _LOGGER.info(
            ("Reconnecting {} integration").format(self._config["name"])
        )
        self._status = Status.DISCONNECTING
        await self.disconnect()
        self._status = Status.CONNECTING
        await self.connect()

    async def connect(self, msg=None):
        """
        Establish a connection with the service.
        This method must be overwritten by the integration implementation.
        Be sure to end this function with await super().connect()
        """
        self._status = Status.CONNECTED
        if msg:
            _LOGGER.info(msg)

    async def disconnect(self, msg=None):
        """
        Disconnect from the service.
        This method must be overwritten by the integration implementation.
        Be sure to end this function with await super().disconnect()
        """
        self._status = Status.DISCONNECTED
        if msg:
            _LOGGER.info(msg)

    def on_shutdown(self):
        """
        Integrations should reimplement this if there's anything they need to do on shutdown to close cleanly.
        This method must be overwritten by the integration implementation.
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

            async_fire_and_forget(
                self.close_all_connections(), self._ledfx.loop
            )

        self._ledfx.events.add_listener(on_shutdown, Event.LEDFX_SHUTDOWN)

    def create_from_config(self, config):
        for integration in config:
            name = integration["config"]["name"]
            _LOGGER.debug(f"Loading integration from config: {name}")
            try:
                self._ledfx.integrations.create(
                    id=integration["id"],
                    type=integration["type"],
                    active=integration["active"],
                    config=integration["config"],
                    data=integration["data"],
                    ledfx=self._ledfx,
                )
            except Exception as e:
                _LOGGER.warning(f"Failed to load integration: {e}")

    async def close_all_connections(self):
        for integration in self.values():
            if integration._active:
                await integration.deactivate()

    async def activate_integrations(self):
        for integration in self.values():
            if integration._active:
                await integration.activate()
