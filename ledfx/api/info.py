from ledfx.api import RestEndpoint
from ledfx.consts import PROJECT_VERSION
from aiohttp import web
import logging
import json

_LOGGER = logging.getLogger(__name__)

class InfoEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/info"

    async def get(self) -> web.Response:
        response = {
            'url': self._ledfx.base_url,
            'name': 'LedFx Controller',
            'version': PROJECT_VERSION,
            'debug_mode': True
        }

        return web.Response(text=json.dumps(response), status=200)
