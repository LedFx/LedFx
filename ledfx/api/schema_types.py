import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.utils import convertToJsonSchema

_LOGGER = logging.getLogger(__name__)


class SchemaEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/schema/{schema_type}"

    async def get(self, schema_type) -> web.Response:
        response = {}
        if schema_type == "devices":
            # Generate all the device schema
            for (
                device_type,
                device,
            ) in self._ledfx.devices.classes().items():
                response[device_type] = {
                    "schema": convertToJsonSchema(device.schema()),
                    "id": device_type,
                }

            return web.json_response(data=response, status=200)
        elif schema_type == "effects":
            # Generate all the effect schema
            for (
                effect_type,
                effect,
            ) in self._ledfx.effects.classes().items():
                response[effect_type] = {
                    "schema": convertToJsonSchema(effect.schema()),
                    "id": effect_type,
                    "name": effect.NAME,
                }
        elif schema_type == "integrations":
            # Generate all the integrations schema
            for (
                integration_type,
                integration,
            ) in self._ledfx.integrations.classes().items():
                response["integrations"][integration_type] = {
                    "schema": convertToJsonSchema(integration.schema()),
                    "id": integration_type,
                    "name": integration.NAME,
                    "description": integration.DESCRIPTION,
                }

            return web.json_response(data=response, status=200)
        else:
            return web.json_response(data=response, status=200)
