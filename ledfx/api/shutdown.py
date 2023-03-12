import asyncio
import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/power"

    exit_codes = {"shutdown": 3, "restart": 4}

    async def post(self, request) -> web.Response:
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        action = data.get("action")
        timeout = data.get("timeout")

        if action is None:
            action = "shutdown"
        if timeout is None:
            timeout = 0

        if action not in self.exit_codes.keys():
            response = {
                "status": "failed",
                "reason": f"Action {action} not in {list(self.exit_codes.keys())}",
            }
            return web.json_response(data=response, status=400)

        if timeout < 0:
            response = {
                "status": "failed",
                "reason": f"Invalid timeout: {timeout}. Timeout is integer?",
            }
            return web.json_response(data=response, status=400)

        # This is an ugly hack.
        # We probably should have a better way of doing this but o well.
        try:
            return web.json_response(data={"status": "success"}, status=200)
        finally:
            await asyncio.sleep(timeout)
            self._ledfx.stop(self.exit_codes[action])
