import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.utils import convertToJsonSchema

_LOGGER = logging.getLogger(__name__)


class SchemaEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/schema"

    async def get(self) -> web.Response:
        response = {
            "devices": {},
            "effects": {},
            "integrations": {},
        }

        # Generate all the device schema
        for (
            device_type,
            device,
        ) in self._ledfx.devices.classes().items():
            response["devices"][device_type] = {
                "schema": convertToJsonSchema(device.schema()),
                "id": device_type,
            }

        # Generate all the effect schema
        for (
            effect_type,
            effect,
        ) in self._ledfx.effects.classes().items():
            response["effects"][effect_type] = {
                "schema": convertToJsonSchema(effect.schema()),
                "id": effect_type,
                "name": effect.NAME,
            }

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
