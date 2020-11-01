from ledfx.config import save_config
from ledfx.api import RestEndpoint
from ledfx.utils import generate_id, async_fire_and_forget
from aiohttp import web
import logging
import json

_LOGGER = logging.getLogger(__name__)

class FindDevicesEndpoint(RestEndpoint):
    """REST end-point for detecting and adding wled devices"""

    ENDPOINT_PATH = "/api/find_devices"

    async def post(self) -> web.Response:
        """ Find and add all WLED devices on the LAN """
        async_fire_and_forget(self._ledfx.devices.find_wled_devices(), self._ledfx.loop)

        response = { 'status' : 'success' }
        return web.json_response(data=response, status=200)