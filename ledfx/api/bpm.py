import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint

# from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)

""" Work In Progress """


class BPMEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/audio/bpm"

    _audio = None

    async def get(self) -> web.Response:
        """Doesn't have any defined bahiour yet"""
        response = {"status": "success"}
        return web.json_response(data=response, status=200)

    async def put(self, request) -> web.Response:
        """Set LedFx's internal BPM data"""
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        _LOGGER.info(data)

        response = {"status": "success"}
        return web.json_response(data=response, status=200)
