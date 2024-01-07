import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import async_fire_and_forget, set_name_to_icon

_LOGGER = logging.getLogger(__name__)


def handle_exception(future):
    # Ignore exceptions, these will be raised when a device is found that already exists
    exc = future.exception()


class FindDevicesEndpoint(RestEndpoint):
    """REST end-point for detecting and adding wled devices"""

    ENDPOINT_PATH = "/api/find_devices"

    async def post(self, request: web.Request) -> web.Response:
        """
        Find and add all WLED devices on the LAN.

        Args:
            request (web.Request): The request object containing the `name_to_icon` dict.

        Returns:
            A web.Response object indicating the success of the request.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        # TODO: Pull this out of find_devices - not sure why it's here or what's using it.
        name_to_icon = data.get("name_to_icon")

        if name_to_icon is None:
            return await self.invalid_request(
                'Required attribute "name_to_icon" was not provided'
            )
        set_name_to_icon(name_to_icon)

        async_fire_and_forget(
            self._ledfx.zeroconf.discover_wled_devices(),
            loop=self._ledfx.loop,
            exc_handler=handle_exception,
        )
        return await self.request_success()

    async def get(self) -> web.Response:
        """Handle HTTP GET requests.

        This method is responsible for handling HTTP GET requests.
        Returns:
            web.Response: The response object indicating the success of the request.
        """
        async_fire_and_forget(
            self._ledfx.zeroconf.discover_wled_devices(),
            loop=self._ledfx.loop,
            exc_handler=handle_exception,
        )
        return await self.request_success()
