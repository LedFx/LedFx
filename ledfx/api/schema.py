from ledfx.api import RestEndpoint
from aiohttp import web
from ledfx.api.utils import convertToJsonSchema
import logging
import json

_LOGGER = logging.getLogger(__name__)

class SchemaEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/schema"

    async def get(self) -> web.Response:
        response = {
            'devices': {},
            'effects': {}
        }

        # Generate all the device schema
        for device_type, device in self._ledfx.devices.classes().items():
            response['devices'][device_type] = {
                'schema': convertToJsonSchema(device.schema()),
                'id': device_type
            }

        # Generate all the effect schema
        for effect_type, effect in self._ledfx.effects.classes().items():
            response['effects'][effect_type] = {
                'schema': convertToJsonSchema(effect.schema()),
                'id': effect_type,
                'name': effect.NAME
            }

        return web.json_response(data=response, status=200)