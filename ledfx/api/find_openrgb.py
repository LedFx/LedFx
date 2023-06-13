import logging

from aiohttp import web
from openrgb import OpenRGBClient

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class FindOpenRGBDevicesEndpoint(RestEndpoint):
    """REST end-point for detecting and reporting OpenRGB devices"""

    ENDPOINT_PATH = "/api/find_openrgb"

    async def post(self) -> web.Response:
        """Check for an openrgb server and report devices"""
        try:
            client = OpenRGBClient()
        except Exception as e:
            _LOGGER.error(f"Failed to connect to OpenRGB server: {e}")
            response = {"status": "error", "error": str(e)}
            return web.json_response(data=response, status=500)

        print(client.devices)

        devices = []
        for device in client.devices:
            devices.append(
                {
                    "name": device.name,
                    "type": device.type,
                }
            )
        response = {"status": "success", "devices": devices}
        return web.json_response(data=response, status=200)
