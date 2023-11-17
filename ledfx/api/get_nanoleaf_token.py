import logging
from json import JSONDecodeError

import requests
from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class GetNanoleadTokenEndpoint(RestEndpoint):
    """REST end-point for requesting auth token from Nanoleaf
    Ensure that the Nanoleaf controller is in pairing mode
    Long press the power button on the controller for 5-7 seconds
    White LEDs will scan back and forth to indicate pairing mode"""

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
            response = requests.post(f"http://{ip}:{port}/api/v1/new",
                                     timeout=(3,3))
            if response.text == "":
                msg = f"{ip}:{port}: Ensure Nanoleaf controller is in pairing mode"
                _LOGGER.error(msg)
                raise ValueError(msg)
            data = response.json()
        except requests.exceptions.RequestException as e:
            msg = f"{ip}:{port}: exception {str(e)}"
            _LOGGER.error(msg)
            raise ValueError(msg)

        return web.json_response(data=data, status=200)
