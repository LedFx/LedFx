from ledfxcontroller.api import RestEndpoint
from aiohttp import web
from ledfxcontroller.api.utils import (convertToJson )
import logging
import json

_LOGGER = logging.getLogger(__name__)


class EffectsEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/schema/effects"

    async def get(self) -> web.Response:
        response = {
            'status': 'success',
            'effects': {}
        }
        for effect_type, effect in self.ledfx.effects.classes().items():
            response['effects'][effect_type] = {
                'schema': convertToJson(effect.schema()),
                'id': effect_type,
                'name': effect.NAME
            }

        return web.Response(text=json.dumps(response), status=200)
