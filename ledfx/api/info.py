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
            'url': 'http://placeholder',
            'name': 'LedFx (Placeholder)',
            'version': PROJECT_VERSION
        }

        return web.Response(text=json.dumps(response), status=200)
