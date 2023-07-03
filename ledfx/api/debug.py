import logging

from aiohttp import web
from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class DebugEndpoint(RestEndpoint):
    """REST api to trigger debug into log optional params for slicing the content
       devices
       virtuals
       """

    ENDPOINT_PATH = "/api/debug"

    async def get(self, request) -> web.Response:
        debugged = False
        _LOGGER.info(f"Debug api: {request.query.keys()}")
        if "devices" in request.query.keys():
            _LOGGER.info("debug for devices")
            for device in self._ledfx.devices.values():
                device.dump(request.query["devices"])
            debugged = True

        if "virtuals" in request.query.keys():
            _LOGGER.info("debug for virtuals")
            for virtual in self._ledfx.virtuals.values():
                virtual.dump(request.query["virtuals"])

            debugged = True

        if not debugged:
            _LOGGER.error(f"No debug params")
            response = {"status": "error", "error": "No debug params"}
            return web.json_response(data=response, status=500)
        else:
            response = {"status": "success"}
            return web.json_response(data=response, status=200)
