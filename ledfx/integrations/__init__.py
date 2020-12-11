from ledfx.utils import BaseRegistry, RegistryLoader, generate_id
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

    def activate(self):
        _LOGGER.info(("Activating {} integration").format(self._config["name"]))
        self._active = True
        self.connect()

    def deactivate(self):
        _LOGGER.info(("Deactivating {} integration").format(self._config["name"]))
        self._active = False
        self.disconnect()

    def reconnect(self):
        _LOGGER.info(("Reconnecting {} integration").format(self._config["name"]))
        self.disconnect()
        self.connect()

    @abstractmethod
    def connect(self):
        """
        Establish a connection with the service.
        This abstract method must be overwritten by the integration implementation.
        """

    @abstractmethod
    def disconnect(self):
        """
        Disconnect from the service.
        This abstract method must be overwritten by the integration implementation.
        """

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

        def close_connections(e):
            self.close_all_connections()

        self._ledfx.events.add_listener(close_connections, Event.LEDFX_SHUTDOWN)

    def create_from_config(self, config):
        for integration in config:
            _LOGGER.info("Loading integration from config: {}".format(integration))
            self._ledfx.integrations.create(
                id=integration["id"],
                type=integration["type"],
                active=integration["active"],
                config=integration["config"],
                ledfx=self._ledfx,
            )

    def close_all_connections(self):
        for integration in self.values():
            integration.deactivate()
