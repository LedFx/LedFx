import asyncio
import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import async_fire_and_forget

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/shutdown"
    PERMITTED_KEYS = ["timeout"]

    async def get(self) -> web.Response:
        response = {
            "statusText ": "GET not allowed - only PUT",
        }

        return web.json_response(data=response, status=200)

    async def put(self, request) -> web.Response:
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)
        if data is None or data.get("timeout") is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "timeout" was not provided',
            }
            return web.json_response(data=response, status=400)

        for key in data.keys():
            if key not in self.PERMITTED_KEYS:
                response = {
                    "status": "failed",
                    "reason": f"Unknown/forbidden key: '{key}'",
                }
                return web.json_response(data=response, status=400)

        delay_time = int(data.get("timeout"))

        # This is an ugly hack.
        # We probably should have a better way of doing this but o well.
        try:
            return web.json_response(data={"status": "success"}, status=200)
        finally:
            await asyncio.sleep(delay_time)
            async_fire_and_forget(self._ledfx.async_stop(2), self._ledfx.loop)
