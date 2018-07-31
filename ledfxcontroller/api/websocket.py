import json
import logging
import asyncio
from aiohttp import web
import voluptuous as vol
from concurrent import futures
from ledfxcontroller.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)
MAX_PENDING_MESSAGES = 256

BASE_MESSAGE_SCHEMA = vol.Schema({
    vol.Required('id'): vol.Coerce(int),
    vol.Required('type'): str,
}, extra=vol.ALLOW_EXTRA)

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
        return await WebsocketConnection(self.ledfx).handle(request)

class WebsocketConnection:

    def __init__(self, ledfx):
        self.ledfx = ledfx
        self.socket = None

        self.receiver_task = None
        self.sender_task = None
        self.sender_queue = asyncio.Queue(maxsize=MAX_PENDING_MESSAGES, loop=ledfx.loop)

    def close(self):
        """Closes the websocket connection"""

        if self.receiver_task:
            self.receiver_task.cancel()
        if self.sender_task:
            self.sender_task.cancel()

    def send(self, message):
        """Sends a message to the websocket connection"""

        try:
            self.sender_queue.put_nowait(message)
        except asyncio.QueueFull:
            _LOGGER.error('Client sender queue size exceeded {}'.format(
                MAX_PENDING_MESSAGES))
            self.close()

    def send_error(self, id, message):
        """Sends an error string to the websocket connection"""

        return self.send({
            'id': id,
            'success': False,
            'error': {
                'message': message
            }
        })

    async def _sender(self):
        """Async write loop to pull from the queue and send"""

        _LOGGER.info("Starting sender")
        while not self.socket.closed:
            message = await self.sender_queue.get()
            if message is None:
                break

            try:
                _LOGGER.info("Sending websocket message")
                await self.socket.send_json(message, dumps=json.dumps)
            except TypeError as err:
                _LOGGER.error('Unable to serialize to JSON: %s\n%s',
                                err, message)

        _LOGGER.info("Stopping sender")

    async def handle(self, request):
        """Handle the websocket connection"""

        socket = self.socket = web.WebSocketResponse()
        await socket.prepare(request)
        _LOGGER.info("Websocket connected.")

        self.receiver_task = asyncio.Task.current_task(loop=self.ledfx.loop)
        self.sender_task = self.ledfx.loop.create_task(self._sender())

        try:
            message = await socket.receive_json()
            while message:
                message = BASE_MESSAGE_SCHEMA(message)

                if message['type'] in websocket_handlers:
                    websocket_handlers[message['type']](self, message)
                else:
                    _LOGGER.error(('Received unknown command {}').format(message['type']))
                    self.send_error(message['id'], 'Unknown command type.')

                message = await socket.receive_json()

        except (vol.Invalid, ValueError) as e:
            self.send_error(message['id'], 'Invalid message format.')

        except TypeError as e:
            if socket.closed:
                _LOGGER.info('Connection closed by client.')
            else:
                _LOGGER.exception('Unexpected TypeError: {}'.format(e))

        except (asyncio.CancelledError, futures.CancelledError) as e:
            _LOGGER.info("Connection cancelled")

        except Exception as err:
            _LOGGER.exception("Unexpected Exception: %s", err)

        finally:

            # Gracefully stop the sender ensuring all messages get flushed
            self.send(None)
            await self.sender_task

            # Close the connection
            await socket.close()
            _LOGGER.info("Closed connection")

        return socket

import numpy as np

@websocket_handler('get_pixels')
def get_pixels_handler(conn, message):
    device = conn.ledfx.devices.get(message.get('device_id'))
    if device is None:
        conn.send_error(message['id'], 'Device not found.')

    rgb_x = np.arange(0, device.pixel_count).tolist()
    if device.latest_frame is not None:
        pixels = np.copy(device.latest_frame).T
        conn.send({"action": "update_pixels", "rgb_x": rgb_x, "r": pixels[0].tolist(), "g": pixels[1].tolist(), "b": pixels[2].tolist()})
    else:
        pixels = np.zeros((device.pixel_count, 3))
        conn.send({"action": "update_pixels", "rgb_x": rgb_x, "r": pixels[0].tolist(), "g": pixels[1].tolist(), "b": pixels[2].tolist()})
