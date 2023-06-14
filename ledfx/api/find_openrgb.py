import logging

from aiohttp import web
from openrgb import OpenRGBClient

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class FindOpenRGBDevicesEndpoint(RestEndpoint):
    """REST end-point for detecting and reporting OpenRGB devices
    optional params for server and port"""

    ENDPOINT_PATH = "/api/find_openrgb"

    async def get(self, request) -> web.Response:
        """Check for an openrgb server and report devices"""

        if "server" in request.query.keys():
            server = request.query["server"]
        else:
            server = "127.0.0.1"

        if "port" in request.query.keys():
            port = int(request.query["port"])
        else:
            port = 6742

        try:
            client = OpenRGBClient(address=server, port=port)
        except Exception as e:
            _LOGGER.error(f"Failed to connect to OpenRGB server: {e}")
            response = {"status": "error", "error": str(e)}
            return web.json_response(data=response, status=500)

        devices = []
        for device in client.devices:
            devices.append(
                {
                    "name": device.name,
                    "type": device.type,
                    "id": device.id,
                    "leds": len(device.leds),
                }
            )

        response = {"status": "success", "devices": devices}
        return web.json_response(data=response, status=200)
