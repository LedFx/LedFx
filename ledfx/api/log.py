import asyncio
import json
import logging
import threading
import time
from concurrent import futures
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.events import Event

_LOGGER = logging.getLogger(__name__)
LOG_HISTORY_MAXLEN = 30

# constants for POST log support
# Configurable TTL for rate limiter entries (seconds) tracking IP sources
RATE_LIMIT_TTL_SECONDS = 1800  # 30 minutes default
MAX_LEN = 200  # max log message length
RATE_LIMIT_SECONDS = 1  # seconds between allowed posts per IP source


class LogEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/log"

    def __init__(self, ledfx):
        self.logwebsocket = LogWebsocket(ledfx, ledfx.logqueue)

        # In-memory rate limit: {ip: last_post_time}
        self._rate_limit = {}
        self._rate_limit_lock = threading.Lock()

    async def post(self, request: web.Request) -> web.Response:
        """
        Accepts log messages from the frontend, with per-IP rate limiting.
        The rate limiter is thread-safe and prunes entries older than RATE_LIMIT_TTL_SECONDS
        on each access.
        """

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        text = data.get("text", "")
        if not isinstance(text, str):
            return await self.invalid_request("Text must be an ASCII string.")

        # Sanitize: printable ASCII only (32-126), strip, max length
        sanitized = "".join([c for c in text.strip() if 32 <= ord(c) < 127])
        if len(sanitized) > MAX_LEN:
            sanitized = sanitized[:MAX_LEN]

        if not sanitized:
            return await self.invalid_request(
                "Text must contain ASCII characters."
            )

        peer_ip = request.remote or "unknown"
        now = time.time()

        # Thread-safe rate limiting and TTL-based cleanup
        with self._rate_limit_lock:
            # Prune expired entries
            expired = [
                ip
                for ip, ts in self._rate_limit.items()
                if now - ts > RATE_LIMIT_TTL_SECONDS
            ]
            for ip in expired:
                del self._rate_limit[ip]

            last = self._rate_limit.get(peer_ip, 0)
            if now - last < RATE_LIMIT_SECONDS:
                return await self.invalid_request(
                    "Rate limit exceeded. Try again later.", type="warning"
                )
            self._rate_limit[peer_ip] = now

        _LOGGER.info(f"Frontend log: {sanitized}")
        return await self.bare_request_success({"status": "success"})

    async def get(self, request: web.Request) -> web.Response:
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

    async def handle(self, request: web.Request):
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
