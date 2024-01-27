import logging
from json import JSONDecodeError

from aiohttp import web
from openrgb import OpenRGBClient

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class FindOpenRGBDevicesEndpoint(RestEndpoint):
    """
    REST end-point for detecting and reporting OpenRGB devices.
    """

    ENDPOINT_PATH = "/api/find_openrgb"

    async def get(self) -> web.Response:
        """
        Check for an OpenRGB server at localhost on the default port and report devices if found.

        Returns:
            web.Response: The HTTP response object containing either an error, or a dict of OpenRGB devices at localhost:6742.
        """

        try:
            client = OpenRGBClient(address="127.0.0.1", port=6742)
        except Exception as e:
            error_message = (
                f"Unable to connect to OpenRGB server at localhost:6742, {e}."
            )
            _LOGGER.error(error_message)
            return await self.request_success(
                "warning",
                error_message,
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

    async def post(self, request: web.Request) -> web.Response:
        """
        Check for an OpenRGB server at and report devices if found.

        Args:
            request (web.Request): The incoming request object that contains the `server` (str) and `port` (str or int). Defaults to 127.0.0.1 and 6742 if not provided.

        Returns:
            web.Response: The HTTP response object containing either an error, or a dict of OpenRGB devices on the given server.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            _LOGGER.warning(
                "Unable to decode JSON from OpenRGB request, using default localhost:6742."
            )
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
            error_message = (
                f"Unable to connect to OpenRGB server at {server}:{port}, {e}."
            )
            _LOGGER.error(error_message)
            return await self.request_success(
                "warning",
                error_message,
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
