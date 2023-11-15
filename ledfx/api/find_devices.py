import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import async_fire_and_forget, set_name_to_icon

_LOGGER = logging.getLogger(__name__)


class FindDevicesEndpoint(RestEndpoint):
    """REST end-point for detecting and adding wled devices"""

    ENDPOINT_PATH = "/api/find_devices"

    async def post(self, request) -> web.Response:
        """Find and add all WLED devices on the LAN"""
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        set_name_to_icon(data.get("name_to_icon"))

        def handle_exception(future):
            # Ignore exceptions, these will be raised when a device is found that already exists
            exc = future.exception()

        async_fire_and_forget(
            self._ledfx.devices.find_wled_devices(),
            loop=self._ledfx.loop,
            exc_handler=handle_exception,
        )

        response = {"status": "success"}
        return web.json_response(data=response, status=200)
