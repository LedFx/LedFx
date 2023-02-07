import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class EffectsEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/effects"

    async def get(self) -> web.Response:
        response = {"status": "success", "effects": {}}
        for virtual in self._ledfx.virtuals.values():
            if virtual.active_effect:
                response["effects"][virtual.id] = {
                    "effect_type": virtual.active_effect.type,
                    "effect_config": virtual.active_effect.config,
                }
        return web.json_response(data=response, status=200)

    async def put(self, request) -> web.Response:
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        action = data.get("action")
        if action is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "action" was not provided',
            }
            return web.json_response(data=response, status=400)

        if action not in ["clear_all_effects"]:
            response = {
                "status": "failed",
                "reason": f'Invalid action "{action}"',
            }
            return web.json_response(data=response, status=400)

        # Clear all effects on all devices
        if action == "clear_all_effects":
            self._ledfx.virtuals.clear_all_effects()
            response = {
                "status": "success",
                "payload": {
                    "type": "info",
                    "message": "Cleared all effects on all devices",
                },
            }
            return web.json_response(data=response, status=200)
