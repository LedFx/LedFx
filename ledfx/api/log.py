import asyncio
import json
import logging
from concurrent import futures

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.events import Event

_LOGGER = logging.getLogger(__name__)


class LogEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/log"

    async def get(self, request) -> web.Response:
        return await LogWebsocket(self._ledfx, self._ledfx.logqueue).handle(
            request
        )


class LogWebsocket:
    def __init__(self, ledfx, queue):
        self._ledfx = ledfx
        self._sender_queue = queue
        self._socket = None
        self._sender_task = None

    def close(self):
        """Closes the websocket connection"""
        if self._sender_task:
            self._sender_task.cancel()

    def send(self, message):
        """Sends a message to the websocket connection"""

        try:
            self._sender_queue.put_nowait(message)
        except asyncio.QueueFull:
            self._sender_queue.get()
            self._sender_queue.put_nowait(message)

    async def _sender(self):
        """Async write loop to pull from the queue and send"""

        _LOGGER.debug("Starting log sender")
        while not self._socket.closed:
            message = await self._sender_queue.get()
            if message == "END":
                break

            try:
                await self._socket.send_json(
                    message.__dict__, dumps=json.dumps
                )

            except TypeError as e:
                if self._socket.closed:
                    _LOGGER.info("Logging connection closed by client.")
                else:
                    _LOGGER.exception("Unexpected TypeError: {}".format(e))

            except (asyncio.CancelledError, futures.CancelledError):
                _LOGGER.info("Logging connection cancelled")
            # Hopefully get rid of the aiohttp connection reset errors
            except ConnectionResetError:
                _LOGGER.info("Logging connection reset")

            except Exception as err:
                _LOGGER.exception("Unexpected Exception: %s", err)

        _LOGGER.debug("Stopping log sender")

    async def handle(self, request):
        """Handle the websocket connection"""

        socket = self._socket = web.WebSocketResponse()
        await socket.prepare(request)
        _LOGGER.info("Logging websocket opened")

        self._sender_task = self._ledfx.loop.create_task(self._sender())

        def shutdown_handler(e):
            self.close()

        remove_listeners = self._ledfx.events.add_listener(
            shutdown_handler, Event.LEDFX_SHUTDOWN
        )

        try:
            while await socket.receive_json():
                # ignore any incoming messages
                pass

        except TypeError as e:
            if socket.closed:
                _LOGGER.info("Logging connection closed by client.")
            else:
                _LOGGER.exception("Unexpected TypeError: {}".format(e))

        except (asyncio.CancelledError, futures.CancelledError):
            _LOGGER.info("Logging connection cancelled")
        # Hopefully get rid of the aiohttp connection reset errors
        except ConnectionResetError:
            _LOGGER.info("Logging connection reset")

        except Exception as err:
            _LOGGER.exception("Unexpected Exception: %s", err)

        finally:
            remove_listeners()
            # Gracefully stop the sender ensuring all messages get flushed
            self.send("END")
            await self._sender_task

            # Close the connection
            await socket.close()
            _LOGGER.info("Logging websocket closed")

        return socket
