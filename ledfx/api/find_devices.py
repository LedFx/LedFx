import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import async_fire_and_forget

_LOGGER = logging.getLogger(__name__)


class FindDevicesEndpoint(RestEndpoint):
    """REST end-point for detecting and adding wled devices"""

    ENDPOINT_PATH = "/api/find_devices"

    async def post(self) -> web.Response:
        """Find and add all WLED devices on the LAN"""

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
