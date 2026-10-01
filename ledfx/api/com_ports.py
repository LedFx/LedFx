import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.devices import available_com_ports

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/comports"

    async def get(self) -> web.Response:
        """
        Get the list of available COM ports.

        Returns:
            web.Response: The response containing the list of available COM ports.
        """
        # The ports only: "" (no port) is a com_port value, not a port.
        return await self.bare_request_success([p for p in available_com_ports() if p])
