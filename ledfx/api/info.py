import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.consts import PROJECT_VERSION

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/info"

    async def get(self) -> web.Response:
        """
        Get information about the LedFx Controller.

        Returns:
            web.Response: The response containing the controller information.
        """
        response = {
            "url": self._ledfx.http.base_url,
            "name": "LedFx Controller",
            "version": PROJECT_VERSION,
            "developer_mode": self._ledfx.config["dev_mode"],
        }
        return await self.bare_request_success(response)
