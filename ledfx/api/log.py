import asyncio
import json
import logging
from concurrent import futures

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.events import Event

_LOGGER = logging.getLogger(__name__)
LOG_HISTORY_MAXLEN = 30


class LogEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/log"

    def __init__(self, ledfx):
        self.logwebsocket = LogWebsocket(ledfx, ledfx.logqueue)

    async def get(self, request) -> web.Response:
        return await self.logwebsocket.handle(request)


class LogWebsocket:
    def __init__(self, ledfx, queue):
        self._ledfx = ledfx
        self._sender_queue = queue
        self._socket = None
        self._receiver_task = None
        self._sender_task = None
        self._log_history = []

    def close(self):
        """Closes the websocket connection"""
        if self._receiver_task:
            self._receiver_task.cancel()
        if self._sender_task:
            self._sender_task.cancel()

    def log_append(self, msg):
        self._log_history.append(msg)
        self._log_history = self._log_history[-LOG_HISTORY_MAXLEN:]

    async def send(self, msg):
        await self._socket.send_json(msg.__dict__, dumps=json.dumps)

    async def _sender(self):
        """Async write loop to pull from the queue and send"""

        _LOGGER.info("Starting log sender")
        try:
            # send log history on socket open
            for msg in self._log_history:
                await self.send(msg)

            # keep sending and adding to history while socket open
            while not self._socket.closed:
                msg = await self._sender_queue.get()
                self.log_append(msg)
                await self.send(msg)

        except TypeError as e:
            if self._socket.closed:
                _LOGGER.info("Logging connection closed by client.")
            else:
                _LOGGER.exception(f"Unexpected TypeError: {e}")

        except (asyncio.CancelledError, futures.CancelledError):
            _LOGGER.info("Logging connection cancelled")
        # Hopefully get rid of the aiohttp connection reset errors
        except ConnectionResetError:
            _LOGGER.info("Logging connection reset")

        except Exception as err:
            _LOGGER.exception("Unexpected Exception: %s", err)

        _LOGGER.info("Stopping log sender")

    async def handle(self, request):
        """Handle the websocket connection"""
        # close existing connection and sender if it exists
        self.close()
        if self._socket is not None:
            await self._socket.close()

        socket = self._socket = web.WebSocketResponse()
        await socket.prepare(request)
        _LOGGER.info("Logging websocket opened")

        self._receiver_task = asyncio.current_task(loop=self._ledfx.loop)
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
                _LOGGER.exception(f"Unexpected TypeError: {e}")

        except (asyncio.CancelledError, futures.CancelledError):
            _LOGGER.info("Logging connection cancelled")
        # Hopefully get rid of the aiohttp connection reset errors
        except ConnectionResetError:
            _LOGGER.info("Logging connection reset")

        except Exception as err:
            _LOGGER.exception("Unexpected Exception: %s", err)

        finally:
            remove_listeners()

            # Close the connection
            await socket.close()
            await self._sender_task

            _LOGGER.info("Logging websocket closed")

        return socket
