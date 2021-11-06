import logging

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class DeviceStatusEndpoint(RestEndpoint):
    """REST end-point that outputs a list of device/virtuals and their status"""

    ENDPOINT_PATH = "/api/device-status"

    async def get(self) -> web.Response:
        response = {"active": [], "inactive": []}
        for virtual in self._ledfx.virtuals.values():
            if virtual.active_effect:
                response["active"].append(virtual.id)
            else:
                response["inactive"].append(virtual.id)
        return web.json_response(data=response, status=200)
