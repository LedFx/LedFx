import logging
from json import JSONDecodeError

import requests
from aiohttp import web

from ledfx.api import RestEndpoint

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

        try:
            response = requests.post(
                f"http://{ip}:{port}/api/v1/new", timeout=(3, 3)
            )
            data = response.json()
        except requests.exceptions.RequestException as e:
            msg = f"{ip}:{port}: exception {str(e)}"
            _LOGGER.error(msg)
            raise ValueError(msg)

        return web.json_response(data=data, status=200)
