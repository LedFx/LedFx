import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.consts import PROJECT_VERSION

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/info"

    async def get(self) -> web.Response:
        response = {
            "url": self._ledfx.http.base_url,
            "name": "LedFx Controller",
            "version": PROJECT_VERSION,
            "debug_mode": True,
        }

        return web.json_response(data=response, status=200)
