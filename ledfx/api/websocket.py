import asyncio
import binascii
import json
import logging
import struct
import uuid
from concurrent import futures

import numpy as np
import pybase64
import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.dedupequeue import VisDeduplicateQ
from ledfx.events import ClientConnectedEvent, ClientDisconnectedEvent, Event
from ledfx.utils import empty_queue

_LOGGER = logging.getLogger(__name__)
MAX_PENDING_MESSAGES = 256
MAX_VAL = 32767

BASE_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("id"): vol.Coerce(int),
        vol.Required("type"): str,
    },
    extra=vol.ALLOW_EXTRA,
)
# Not all events are able to be subscribed to by the websocket
# This dict show the events that are not subscribable and what event should be used instead
NON_SUBSCRIBABLE_EVENTS = {
    "device_update": "Use visualisation_update instead",
}

# TODO: Have a more well defined registration and a more componetized solution.
# Could do something like have Device actually provide the handler for Device
# related functionality. This would allow easy access to internal workings and
# events.
websocket_handlers = {}


def websocket_handler(type):
    def function(func):
        websocket_handlers[type] = func
        return func

    return function


WEB_AUDIO_CLIENTS = set()
ACTIVE_AUDIO_STREAM = None


class WebsocketEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/websocket"

    async def get(self, request) -> web.Response:
        try:
            return await WebsocketConnection(self._ledfx).handle(request)
        except ConnectionResetError:
            _LOGGER.debug("Connection Reset Error on Websocket Connection.")
            return self.internal_error("Connection Reset Error.")


class WebsocketConnection:
    ip_uid_map = {}
    map_lock = asyncio.Lock()

    def __init__(self, ledfx):
        self._ledfx = ledfx
        self._socket = None
        self._listeners = {}
        self._receiver_task = None
        self._sender_task = None
        self._sender_queue = VisDeduplicateQ(maxsize=MAX_PENDING_MESSAGES)
        self.client_ip = None
        self.uid = None

    def close(self):
        """
        Closes the websocket connection.

        This method cancels the receiver and sender tasks, if they exist, to close the websocket connection.
        """
        if self._receiver_task:
            self._receiver_task.cancel()
        if self._sender_task:
            self._sender_task.cancel()

    def clear_subscriptions(self):
        """
        Clears all the subscriptions by calling the registered listener functions.
        """
        for func in self._listeners.values():
            func()

    @classmethod
    async def get_all_clients(cls):
        async with cls.map_lock:
            return cls.ip_uid_map.copy()

    def send(self, message):
        """Sends a message to the websocket connection

        Args:
            message (str): The message to be sent
        """

        # If the queue is full, dump it and start again
        if self._sender_queue.qsize() == MAX_PENDING_MESSAGES:
            empty_queue(self._sender_queue)

        try:
            self._sender_queue.put_nowait(message)
        except asyncio.QueueFull:
            _LOGGER.error(
                f"Client sender queue size exceeded {MAX_PENDING_MESSAGES}"
            )
            self.close()

    def send_error(self, id, message):
        """Sends an error string to the websocket connection.

        Args:
            id (int): The ID of the error message.
            message (str): The error message to be sent.


        """

        return self.send(
            {
                "id": id,
                "success": False,
                "error": {"message": message},
            }
        )

    def send_event(self, id, event):
        """
        Sends an event notification to the websocket connection.

        Args:
            id (str): The ID of the event.
            event (Event): The event object to be sent.

        """

        return self.send({"id": id, "type": "event", **event.to_dict()})

    async def _sender(self):
        """
        Async write loop to pull from the queue and send

        This method is an asynchronous write loop that pulls messages from the sender queue and sends them over the websocket connection.
        It continuously checks for new messages in the queue until the websocket connection is closed.
        If there is an error serializing the message to JSON, it logs an error message.
        If the websocket connection is closed by the client, it logs a message and breaks the loop.
        """
        _LOGGER.info("Starting websocket sender")
        while not self._socket.closed:
            message = await self._sender_queue.get()
            try:
                # _LOGGER.debug("Sending websocket message")
                await self._socket.send_json(message, dumps=json.dumps)
            except TypeError as err:
                _LOGGER.error(
                    "Unable to serialize to JSON: %s\n%s",
                    err,
                    message,
                )
            except ConnectionResetError:
                _LOGGER.info("Websocket connection closed by the client.")
                break

        _LOGGER.info("Stopped websocket sender.")

    async def handle(self, request):
        """Handle the websocket connection"""

        self.client_ip = request.remote

        async with WebsocketConnection.map_lock:
            self.uid = str(uuid.uuid4())
            WebsocketConnection.ip_uid_map[self.uid] = self.client_ip

        socket = self._socket = web.WebSocketResponse(
            protocols=("http", "https", "ws", "wss")
        )

        # print(request.protocol)
        # print(socket._protocols)
        # headers = request.headers
        # from aiohttp import hdrs
        # protocol = None
        # print(headers)
        # print("SEC_WEBSOCKET_PROTOCOL", hdrs.SEC_WEBSOCKET_PROTOCOL)
        # print(hdrs.SEC_WEBSOCKET_PROTOCOL in headers)
        # if hdrs.SEC_WEBSOCKET_PROTOCOL in headers:
        #     req_protocols = [
        #         str(proto.strip())
        #         for proto in headers[hdrs.SEC_WEBSOCKET_PROTOCOL].split(",")
        #     ]
        #     print("req",req_protocols)
        #     for proto in req_protocols:
        #         if proto in socket._protocols:
        #             protocol = proto
        #             break
        #     else:
        #         # No overlap found: Return no protocol as per spec
        #         _LOGGER.warning(
        #             "Client protocols %r don’t overlap server-known ones %r",
        #             req_protocols,
        #             socket._protocols,
        #         )
        # print(protocol)
        # print(socket.can_prepare(request))
        # print(socket._protocols)
        # print(socket.ws_protocol)

        await socket.prepare(request)

        _LOGGER.info("Websocket connected.")

        # Send UID to the client
        await self._socket.send_json(
            {"event_type": "client_id", "client_id": self.uid}
        )

        self._receiver_task = asyncio.current_task(loop=self._ledfx.loop)
        self._sender_task = self._ledfx.loop.create_task(self._sender())

        self._ledfx.events.fire_event(
            ClientConnectedEvent(self.uid, self.client_ip)
        )

        def shutdown_handler(e):
            self.close()

        remove_listeners = self._ledfx.events.add_listener(
            shutdown_handler, Event.LEDFX_SHUTDOWN
        )

        try:
            message = await socket.receive_json()
            while message:
                message = BASE_MESSAGE_SCHEMA(message)

                if message["type"] in websocket_handlers:
                    websocket_handlers[message["type"]](self, message)
                else:
                    _LOGGER.error(
                        f"Received unknown command {message['type']}"
                    )
                    self.send_error(message["id"], "Unknown command type.")

                message = await socket.receive_json()

        except (vol.Invalid, ValueError):
            _LOGGER.info("Invalid message format.")
            self.send_error(message["id"], "Invalid message format.")

        except TypeError as e:
            if socket.closed:
                _LOGGER.info("Connection closed by client.")
            else:
                _LOGGER.exception(f"Unexpected TypeError: {e}")

        except (asyncio.CancelledError, futures.CancelledError):
            _LOGGER.info("Connection cancelled")
        # Hopefully get rid of the aiohttp connection reset errors
        except ConnectionResetError:
            _LOGGER.info("Connection reset")

        except Exception as err:
            _LOGGER.exception("Unexpected Exception: %s", err)

        finally:
            async with WebsocketConnection.map_lock:
                if self.uid in WebsocketConnection.ip_uid_map:
                    del WebsocketConnection.ip_uid_map[self.uid]
            remove_listeners()
            self.clear_subscriptions()

            # Gracefully stop the sender ensuring all messages get flushed
            self.send(None)
            await self._sender_task

            # Close the connection
            await socket.close()
            _LOGGER.info("Closed connection")

            self._ledfx.events.fire_event(
                ClientDisconnectedEvent(self.uid, self.client_ip)
            )

        return socket

    @websocket_handler("subscribe_event")
    def subscribe_event_handler(self, message):
        def notify_websocket(event):
            self.send_event(message["id"], event)

        # Some events are not subscribable - send an error message if the user tries to subscribe to one with a hint on what to use instead
        if message.get("event_type") in NON_SUBSCRIBABLE_EVENTS.keys():
            msg = f"Websocket cannot subscribe to {message.get('event_type')} events - use {NON_SUBSCRIBABLE_EVENTS[message.get('event_type')]} instead"
            _LOGGER.warning(f"{msg}.")
            self.send_error(message["id"], msg)
            return

        _LOGGER.debug(f"  sub Q: {hex(id(self))} {str(message)[:80]}")
        _LOGGER.debug(
            f"Websocket subscribing to event {message.get('event_type')} with filter {message.get('event_filter')}"
        )
        self._listeners[message["id"]] = self._ledfx.events.add_listener(
            notify_websocket,
            message.get("event_type"),
            message.get("event_filter", {}),
        )

    @websocket_handler("unsubscribe_event")
    def unsubscribe_event_handler(self, message):
        _LOGGER.debug(f"unsub Q: {hex(id(self))} {str(message)[:80]}")
        subscription_id = message["id"]

        _LOGGER.debug(f"Websocket unsubscribing event id {subscription_id}")
        if subscription_id in self._listeners:
            self._listeners.pop(subscription_id)()
        else:
            _LOGGER.warning(
                f"Unsubscibe unknown subscription ID {subscription_id}"
            )

    @websocket_handler("audio_stream_start")
    def audio_stream_start_handler(self, message):
        client = message.get("client")

        if client in WEB_AUDIO_CLIENTS:
            _LOGGER.warning(f"Web audio client {client} already exists")
            return

        _LOGGER.info(f"Web audio stream opened by client {client}")
        WEB_AUDIO_CLIENTS.add(client)

    @websocket_handler("audio_stream_stop")
    def audio_stream_stop_handler(self, message):
        client = message.get("client")
        _LOGGER.info(f"Web audio stream closed by client {client}")
        WEB_AUDIO_CLIENTS.discard(client)

    @websocket_handler("audio_stream_config")
    def audio_stream_config_handler(self, message):
        _LOGGER.info(
            f"WebAudioConfig from {message.get('client')}: {message.get('data')}"
        )

    @websocket_handler("audio_stream_data")
    def audio_stream_data_handler(self, message):
        # _LOGGER.info(
        #     "Websocket: {} incoming from {} with type {}".format(
        #         message.get("event_type"),
        #         message.get("client"),
        #         type(message.get("data")),
        #     )
        # )

        if not ACTIVE_AUDIO_STREAM:
            return

        client = message.get("client")

        if ACTIVE_AUDIO_STREAM.client != client:
            return
        ACTIVE_AUDIO_STREAM.data = np.fromiter(
            message.get("data").values(), dtype=np.float32
        )

    @websocket_handler("audio_stream_data_v2")
    def audio_stream_data_base64_handler(self, message):
        # Max value for signed 16-bit values.
        if not ACTIVE_AUDIO_STREAM:
            return

        client = message.get("client")

        if ACTIVE_AUDIO_STREAM.client != client:
            return
        try:
            decoded = pybase64.b64decode(message.get("data"))
        except binascii.Error:
            _LOGGER.info("Incorrect base64 padding.")
        except Exception as err:
            _LOGGER.exception(
                "Unexpected Exception in base64 decoding: %s", err
            )
        else:
            fmt = "<%dh" % (len(decoded) // 2)
            data = list(struct.unpack(fmt, decoded))
            # Minimum value is -32768 for signed, so that's why if the number is negative,
            # it is divided by 32768 when converting to float.
            data = np.array(
                [d / MAX_VAL if d >= 0 else d / (MAX_VAL + 1) for d in data],
                dtype=np.float32,
            )
            ACTIVE_AUDIO_STREAM.data = data


class WebAudioStream:
    def __init__(self, client: str, callback: callable):
        self.client = client
        self.callback = callback
        self._data = None
        self._active = False

    def start(self):
        self._active = True

    def stop(self):
        self._active = False

    def close(self):
        self._active = False

    @property
    def data(self, x):
        return self._data

    @data.setter
    def data(self, x):
        self._data = x
        if self._active:
            try:
                self.callback(self._data, None, None, None)
            except Exception as e:
                _LOGGER.error(e)
