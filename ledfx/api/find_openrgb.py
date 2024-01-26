import logging
from json import JSONDecodeError

from aiohttp import web
from openrgb import OpenRGBClient

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class FindOpenRGBDevicesEndpoint(RestEndpoint):
    """REST end-point for detecting and reporting OpenRGB devices
    optional params for server and port"""

    ENDPOINT_PATH = "/api/find_openrgb"

    async def get(self, request: web.Request) -> web.Response:
        """
        Check for an openRGB server and report devices

        Args:
            request (web.Request): The incoming request object that contains the `server` (str) and `port` (str or int). Defaults to 127.0.0.1 and 6742 if not provided.

        Returns:
            web.Response: The HTTP response object.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            data = {}

        server = data.get("server", "127.0.0.1")
        port = data.get("port", "6742")

        try:
            port = int(port)
        except ValueError:
            error_message = f"Unable to convert {port} to int."
            _LOGGER.warning(error_message)
            return await self.invalid_request(error_message)

        try:
            client = OpenRGBClient(address=server, port=port)
        except Exception as e:
            _LOGGER.error(f"Failed to connect to OpenRGB server: {e}")
            return await self.request_success(
                "info", f"No OpenRGB server found at {server}:{port}"
            )

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
        return await self.bare_request_success(response)
