import logging

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class SpecifiedDeviceStatusEndpoint(RestEndpoint):
    """REST end-point for querying specific device/virtuals"""

    ENDPOINT_PATH = "/api/device-status/{virtual_id}"

    async def get(self, virtual_id) -> web.Response:
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return web.json_response(data={"not found": 404}, status=404)
        response = {"active": virtual.active_effect}
        return web.json_response(data=response, status=200)
