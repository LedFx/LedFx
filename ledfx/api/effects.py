import logging

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class EffectsEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/effects"

    async def get(self) -> web.Response:
        response = {}
        for device in self._ledfx.devices.values():
            if device.active_effect:
                response[
                    device.active_effect.type
                ] = device.active_effect.config

        return web.json_response(data=response, status=200)
