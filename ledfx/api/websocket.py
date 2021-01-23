import asyncio
import json
import logging
from concurrent import futures

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.events import Event

_LOGGER = logging.getLogger(__name__)
MAX_PENDING_MESSAGES = 1024

BASE_MESSAGE_SCHEMA = vol.Schema(
    {
        vol.Required("id"): vol.Coerce(int),
        vol.Required("type"): str,
    },
    extra=vol.ALLOW_EXTRA,
)

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


class WebsocketEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/websocket"

    async def get(self, request) -> web.Response:
        try:
            return await WebsocketConnection(self._ledfx).handle(request)
        except ConnectionResetError:
            _LOGGER.debug(
                "Connection Reset Error on Websocket Connection - retrying."
            )


class WebsocketConnection:
    def __init__(self, ledfx):
        self._ledfx = ledfx
        self._socket = None
        self._listeners = {}
        self._receiver_task = None
        self._sender_task = None
        self._sender_queue = asyncio.Queue(
            maxsize=MAX_PENDING_MESSAGES, loop=ledfx.loop
        )

    def close(self):
        """Closes the websocket connection"""
        if self._receiver_task:
            self._receiver_task.cancel()
        if self._sender_task:
            self._sender_task.cancel()

    def clear_subscriptions(self):
        for func in self._listeners.values():
            func()

    def send(self, message):
        """Sends a message to the websocket connection"""

        try:
            self._sender_queue.put_nowait(message)
        except asyncio.QueueFull:
            _LOGGER.error(
                "Client sender queue size exceeded {}".format(
                    MAX_PENDING_MESSAGES
                )
            )
            self.close()

    def send_error(self, id, message):
        """Sends an error string to the websocket connection"""

        return self.send(
            {
                "id": id,
                "success": False,
                "error": {"message": message},
            }
        )

    def send_event(self, id, event):
        """Sends an event notification to the websocket connection"""

        return self.send({"id": id, "type": "event", **event.to_dict()})

    async def _sender(self):
        """Async write loop to pull from the queue and send"""

        _LOGGER.info("Starting sender")
        while not self._socket.closed:
            message = await self._sender_queue.get()
            if message is None:
                break

            try:
                _LOGGER.debug("Sending websocket message")
                await self._socket.send_json(message, dumps=json.dumps)
            except TypeError as err:
                _LOGGER.error(
                    "Unable to serialize to JSON: %s\n%s",
                    err,
                    message,
                )

        _LOGGER.info("Stopping sender")

    async def handle(self, request):
        """Handle the websocket connection"""

        socket = self._socket = web.WebSocketResponse()
        await socket.prepare(request)
        _LOGGER.info("Websocket connected.")

        self._receiver_task = asyncio.current_task(loop=self._ledfx.loop)
        self._sender_task = self._ledfx.loop.create_task(self._sender())

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
                        ("Received unknown command {}").format(message["type"])
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
                _LOGGER.exception("Unexpected TypeError: {}".format(e))

        except (asyncio.CancelledError, futures.CancelledError):
            _LOGGER.info("Connection cancelled")
        # Hopefully get rid of the aiohttp connection reset errors
        except ConnectionResetError:
            _LOGGER.info("Connection reset")

        except Exception as err:
            _LOGGER.exception("Unexpected Exception: %s", err)

        finally:
            remove_listeners()
            self.clear_subscriptions()

            # Gracefully stop the sender ensuring all messages get flushed
            self.send(None)
            await self._sender_task

            # Close the connection
            await socket.close()
            _LOGGER.info("Closed connection")

        return socket

    @websocket_handler("subscribe_event")
    def subscribe_event_handler(self, message):
        def notify_websocket(event):
            self.send_event(message["id"], event)

        _LOGGER.info(
            "Websocket subscribing to event {} with filter {}".format(
                message.get("event_type"), message.get("event_filter")
            )
        )
        self._listeners[message["id"]] = self._ledfx.events.add_listener(
            notify_websocket,
            message.get("event_type"),
            message.get("event_filter", {}),
        )

    @websocket_handler("unsubscribe_event")
    def unsubscribe_event_handler(self, message):

        subscription_id = message["subscription_id"]

        _LOGGER.info(
            "Websocket unsubscribing from event {}".format(
                message.get("event_type")
            )
        )
        if subscription_id in self._listeners:
            self._listeners.pop(subscription_id)()
