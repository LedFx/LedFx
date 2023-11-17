import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import async_fire_and_forget, set_name_to_icon

_LOGGER = logging.getLogger(__name__)


class GetNanoleadTokenEndpoint(RestEndpoint):
    """REST end-point for detecting and adding wled devices"""

    ENDPOINT_PATH = "/api/getNanoleafToken"

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

        ip = data.get("ip_address")
        port = data.get("port")
        _LOGGER.info(f"Get Nanoleaf Token from {ip}:{port}")
        # TODO: Get Nanoleaf Token from IP and Port
        # TODO: Replace with actual token
        response = {"status": "success", "auth_token": "1337Blade"}
        return web.json_response(data=response, status=200)
