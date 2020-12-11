from ledfx.utils import RegistryLoader, async_fire_and_forget
from ledfx.events import Event
from ledfx.integrations import Integration
import aiohttp
import asyncio
import voluptuous as vol
import numpy as np
import importlib
import pkgutil
import logging
import time
import os
import re

_LOGGER = logging.getLogger(__name__)


class QLC(Integration):
    """QLC+ Integration"""

    _status = None

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name", description="Name of this integration", default="QLC+"
            ): str,
            vol.Required(
                "description",
                description="Description of this integration",
                default="Web Api Integration for Q Light Controller Plus",
            ): str,
            vol.Required(
                "ip_address", description="QLC+ ip address", default="127.0.0.1"
            ): str,
            vol.Required("port", description="QLC+ port", default=9999): vol.All(
                vol.Coerce(int), vol.Range(min=1, max=65535)
            ),
        }
    )

    def __init__(self, ledfx, config, active):
        super().__init__(ledfx, config, active)

        self._ledfx = ledfx
        self._config = config
        self.client = None

        # def send_payload(e):
        #     print(f"Heard event {e}")

        # self._ledfx.events.add_listener(
        #     send_payload, Event.SCENE_SET)

        if active:
            self.activate()

    def handle_message(self, message):
        print(f"NEW MESSAGE: {message}")

    def connect(self):
        domain = f"{self._config['ip_address']}:{str(self._config['port'])}"
        url = f"http://{domain}/qlcplusWS"
        self.client = WebsocketClient(url, domain)
        async_fire_and_forget(self.client.begin(self.handle_message), self._ledfx.loop)

    def disconnect(self):
        if self.client is not None:
            async_fire_and_forget(self.client.disconnect(), self._ledfx.loop)


class WebsocketClient(aiohttp.ClientSession):
    def __init__(self, url, domain):
        super().__init__()
        self.websocket = None
        self.url = url
        self.domain = domain

    async def connect(self):
        """Connect to the WebSocket."""
        while True:
            try:
                self.websocket = await self.ws_connect(self.url)
                _LOGGER.info(f"Connected websocket to {self.domain}")
                return
            except aiohttp.client_exceptions.ClientConnectorError:
                _LOGGER.info(f"Connection to {self.domain} failed. Retrying in 5s...")
                await asyncio.sleep(5)

    async def disconnect(self):
        if self.websocket is not None:
            return await self.websocket.close()

    async def begin(self, callback):
        await self.connect()
        await self.read(callback)

    async def send(self, message):
        """Send a message to the WebSocket."""
        if self.websocket is None:
            _LOGGER.error("Websocket not yet established")
            return

        self.websocket.send_str(message)
        _LOGGER.info(f"Sent message {message} to {self.domain}")

    async def receive(self):
        """Receive one message from the WebSocket."""
        if self.websocket is None:
            _LOGGER.error("Websocket not yet established")
            return

        return (await self.websocket.receive()).data

    async def read(self, callback):
        """Read messages from the WebSocket."""
        if self.websocket is None:
            _LOGGER.error("Websocket not yet established")
            return

        while await self.websocket.receive():
            message = await self.receive()
            if message.type == aiohttp.WSMsgType.TEXT:
                self.callback(message)
            elif message.type == aiohttp.WSMsgType.CLOSED:
                break
            elif message.type == aiohttp.WSMsgType.ERROR:
                break
