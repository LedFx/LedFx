import asyncio

# import numpy as np
# import importlib
# import pkgutil
import logging

import aiohttp
import voluptuous as vol

# from ledfx.events import Event
from ledfx.integrations import Integration
from ledfx.utils import async_fire_and_forget, resolve_destination

# import time
# import os
# import re

_LOGGER = logging.getLogger(__name__)


class QLC(Integration):
    """QLC+ Integration"""

    beta = False

    _widget_types = ["Button", "Slider", "Audio Triggers"]
    NAME = "QLC+"
    DESCRIPTION = "Web Api Integration for Q Light Controller Plus"

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name",
                description="Name of this integration instance and associated settings",
                default="QLC+",
            ): str,
            vol.Required(
                "description",
                description="Description of this integration",
                default="Web Api Integration for Q Light Controller Plus",
            ): str,
            vol.Required(
                "ip_address",
                description="QLC+ ip address",
                default="127.0.0.1",
            ): str,
            vol.Required(
                "port", description="QLC+ port", default=9999
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
        }
    )

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._config = config
        self._client = None
        self._data = []
        self._listeners = []
        self._connect_task = None

        self.restore_from_data(data)

    def restore_from_data(self, data):
        """Creates the event listeners from saved data"""
        if data is not None:
            try:
                for entry in data:
                    event_type, event_filter, active, qlc_payload = entry
                    self.create_event(
                        event_type, event_filter, active, qlc_payload
                    )
            except ValueError:
                _LOGGER.error("Failed to restore QLC+ settings")

    def get_events(self):
        """Get all events in data:
        [(event_type, event_filter, active, qlc_payload), ...]
        event_type : type of event, str
        event_filter : filter for event, dict eg. {"effect_name": "Scroll"}
        active : whether there is an active listener for this event
        qlc_payload : the payload that is sent when this event is triggered
        """
        return self._data

    def create_event(self, event_type, event_filter, active, qlc_payload):
        """Create or update event listener that sends a qlc payload on a specific event"""
        # If it exists, remove the existing listener and update data
        for idx, entry in enumerate(self._data):
            _event_type, _event_filter, _active, _qlc_payload = entry
            if (_event_type == event_type) and (_event_filter == event_filter):
                self._data[idx] = [
                    event_type,
                    event_filter,
                    active,
                    qlc_payload,
                ]
                # if it was active, remove existing listener
                if _active:
                    self._remove_listener(_event_type, event_filter)
                break
        # If it doesn't already exist, add it as a new entry to data
        else:
            self.data.append([event_type, event_filter, active, qlc_payload])
        # Finally, subscribe to the ledfx event if the listener is now active
        if active:
            self._add_listener(event_type, event_filter, qlc_payload)
        _LOGGER.info(
            f"QLC+ payload linked to event '{event_type}' with filter {event_filter}"
        )

    def delete_event(self, event_type, event_filter):
        """Completely delete event listener and saved payload from data"""
        # remove listener if it exists
        self._remove_listener(event_type, event_filter)
        # remove event and payload from data
        for idx, entry in enumerate(self._data):
            _event_type, _event_filter, _active, _qlc_payload = entry
            if (_event_type == event_type) and (_event_filter == event_filter):
                del self._data[idx]
        _LOGGER.info(
            f"QLC+ payload deleted for event '{event_type}' with filter {event_filter}"
        )

    def toggle_event(self, event_type, event_filter):
        """Toggle a payload linked to event on or off"""
        # Update "active" flag in data
        for idx, entry in enumerate(self._data):
            _event_type, _event_filter, _active, _qlc_payload = entry
            if (_event_type == event_type) and (_event_filter == event_filter):
                # toggle active flag in data
                self._data[idx] = [
                    event_type,
                    event_filter,
                    not _active,
                    _qlc_payload,
                ]
                # Enable/disable listener
                if _active:
                    self._remove_listener(_event_type, event_filter)
                else:
                    # no listener exists, so create it
                    self._add_listener(event_type, event_filter, _qlc_payload)
                # log action
                _LOGGER.info(
                    f"QLC+ payload {'disabled' if _active else 'enabled'} for event '{event_type}' with filter {event_filter}"
                )
                return True  # success
        return False  # failed to find event_type with this event_filter

    def _remove_listener(self, event_type, event_filter):
        """Internal function to remove ledfx events listener if it exists"""
        for idx, entry in enumerate(self._listeners):
            _event_type, _event_filter, listener = entry
            if (_event_type == event_type) and (_event_filter == event_filter):
                # Call the listener function that removes the listener
                listener()
                del self._listeners[idx]
                break

    def _add_listener(self, event_type, event_filter, qlc_payload):
        """Internal function that links payload to send on the specified event"""

        def make_callback(qlc_payload):
            def callback(_):
                _LOGGER.info(
                    f"QLC+ sent payload, triggered by event '{event_type}' with filter {event_filter}"
                )
                async_fire_and_forget(
                    self._send_payload(qlc_payload), loop=self._ledfx.loop
                )

            return callback

        callback = make_callback(qlc_payload)
        listener = self._ledfx.events.add_listener(
            callback, event_type, event_filter
        )
        # store "listener", a function to remove the listener later if needed
        self._listeners.append((event_type, event_filter, listener))

    async def get_widgets(self):
        """Returns a list of widgets as tuples: [(ID, Type, Name),...]"""
        # First get list of widgets (ID, Name)
        widgets = []
        message = "QLC+API|getWidgetsList"
        response = await self._client.query(message)
        widgets_list = response.lstrip(f"{message}|").split("|")
        # Then get the type for each widget (in individual requests bc QLC api be like that)
        for widget_id, widget_name in zip(
            widgets_list[::2], widgets_list[1::2]
        ):
            message = "QLC+API|getWidgetType"
            response = await self._client.query(f"{message}|{widget_id}")
            widget_type = response.lstrip(f"{message}|")
            if widget_type in self._widget_types:
                widgets.append((widget_id, widget_type, widget_name))
        return widgets

    async def _send_payload(self, qlc_payload):
        """Sends payload of {id:value, ...} pairs to QLC"""
        for widget_id, value in qlc_payload.items():
            await self._client.send(f"{int(widget_id)}|{value}")

    async def connect(self):
        resolved_ip = await resolve_destination(
            self._ledfx.loop,
            self._ledfx.thread_executor,
            self._config["ip_address"],
        )
        domain = f"{resolved_ip }:{self._config['port']}"
        url = f"http://{domain}/qlcplusWS"
        if self._client is None:
            self._client = QLCWebsocketClient(url, domain)
        self._cancel_connect()
        self._connect_task = asyncio.create_task(self._client.connect())
        if await self._connect_task:
            await super().connect(f"Connected to QLC+ websocket at {domain}")

    async def disconnect(self):
        self._cancel_connect()
        if self._client is not None:
            # fire and forget bc for some reason close() never returns... -o-
            async_fire_and_forget(
                self._client.disconnect(), loop=self._ledfx.loop
            )
            await super().disconnect("Disconnected from QLC+ websocket")
        else:
            await super().disconnect()

    def _cancel_connect(self):
        if self._connect_task is not None:
            self._connect_task.cancel()
            self._connect_task = None


class QLCWebsocketClient:
    def __init__(self, url, domain):
        super().__init__()
        self.websocket = None
        self.url = url
        self.domain = domain
        self.session = aiohttp.ClientSession()

    async def connect(self):
        """Connect to the WebSocket."""
        while True:
            try:
                self.websocket = await self.session.ws_connect(self.url)
                # self.websocket = await self.ws_connect(self.url)
                return True
            except aiohttp.client_exceptions.ClientConnectorError:
                _LOGGER.info(
                    f"Connection to {self.domain} failed. Retrying in 5s..."
                )
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                return False

    async def disconnect(self):
        if self.websocket is not None:
            await self.websocket.close()

    async def begin(self, callback):
        """Connect and indefinitely read from websocket, returning messages to callback func"""
        await self.connect()
        await self.read(callback)

    async def query(self, message):
        """Send a message, and return the response"""
        await self.send(message)
        result = await self.receive()
        return result.lstrip("QLC+API|")

    async def send(self, message):
        """Send a message to the WebSocket."""
        if self.websocket is None:
            _LOGGER.error("Websocket not yet established")
            return

        await self.websocket.send_str(message)
        # Every call to the logger is a performance hit
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
