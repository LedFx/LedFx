from ledfx.utils import RegistryLoader, async_fire_and_forget, async_fire_and_return, async_callback
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
    _widget_types = ["Button", "Slider", "Audio Triggers"]

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

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active)

        self._ledfx = ledfx
        self._config = config
        self._client = None
        self._mappings = {}

        self.restore_from_data(data)

        # def send_payload(e):
        #     print(f"Heard event {e}")

        # self._ledfx.events.add_listener(
        #     send_payload, Event.SCENE_SET)

    def restore_from_data(self, data):
        self._mappings = data

    def save_data(self):
        return self._mappings

    def add_mapping(self, event, filter, *qlc_ids):
        pass

    def add_listener(self, event_type, event_filter, *qlc_ids):
        def make_callback(*qlc_ids):
            def func():
                print(*qlc_ids)
            return func

        self._ledfx.events.add_listener(
            func, event_type, event_filter)

    async def get_widgets(self):
        """ Returns a list of widgets as tuples: [(ID, Type, Name),...] """
        # First get list of widgets (ID, Name)
        widgets = []
        message = "QLC+API|getWidgetsList"
        response = await self._client.query(message)
        widgets_list = response.lstrip(f"{message}|").split("|")
        # Then get the type for each widget (in individual requests bc QLC api be like that)
        for widget_id, widget_name in enumerate(widgets_list[1::2]):
            message = "QLC+API|getWidgetType"
            response = await self._client.query(f"{message}|{widget_id}")
            widget_type = response.lstrip(f"{message}|")
            if widget_type in self._widget_types:
                widgets.append((widget_id, widget_type, widget_name))
        return widgets

    async def handle_scene_set(self):
        pass

    async def connect(self):
        domain = f"{self._config['ip_address']}:{str(self._config['port'])}"
        url = f"http://{domain}/qlcplusWS"
        self._client = QLCWebsocketClient(url, domain)
        await self._client.connect()

    async def disconnect(self):
        if self._client is not None:
            await self._client.disconnect()

class QLCWebsocketClient(aiohttp.ClientSession):
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
                _LOGGER.info(f"Connected to QLC+ websocket at {self.domain}")
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

    async def query(self, message):
        await self.send(message)
        result = await self.receive()
        return result.lstrip("QLC+API|")

    async def send(self, message):
        """Send a message to the WebSocket."""
        if self.websocket is None:
            _LOGGER.error("Websocket not yet established")
            return


        await self.websocket.send_str(message)
        _LOGGER.debug(f"Sent message {message} to {self.domain}")

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
