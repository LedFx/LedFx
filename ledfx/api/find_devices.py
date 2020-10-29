from ledfx.config import save_config
from ledfx.api import RestEndpoint
from ledfx.utils import generate_id
from aiohttp import web
import logging
import json

_LOGGER = logging.getLogger(__name__)

class FindDevicesEndpoint(RestEndpoint):
    """REST end-point for detecting and adding wled devices"""

    ENDPOINT_PATH = "/api/find_devices"

    async def post(self) -> web.Response:
        """ Find and add all WLED devices on the LAN """
        print("HOWDY")
        self._ledfx.devices.find_wled_devices()

        response = { 'status' : 'success' }
        return web.json_response(data=response, status=200)