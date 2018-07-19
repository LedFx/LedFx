from ledfxcontroller.api import RestEndpoint
from aiohttp import web
import logging
import json

_LOGGER = logging.getLogger(__name__)

class EffectsEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/effects"

    async def get(self) -> web.Response:
        response = { 'status' : 'success' , 'effects' : self.ledfx.effects.types() }
        return web.Response(text=json.dumps(response), status=200)
