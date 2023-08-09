import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.devices.launchpad import find_launchpad

_LOGGER = logging.getLogger(__name__)


class FindLaunchpadDevicesEndpoint(RestEndpoint):
    """REST end-point for detecting and reporting Launchpad device"""

    ENDPOINT_PATH = "/api/find_launchpad"

    async def get(self, request) -> web.Response:
        """Check for launchpad present"""

        try:
            found = find_launchpad()
        except Exception as e:
            _LOGGER.error(f"Error in checking for launchpad: {e}")
            response = {"status": "error", "error": str(e)}
            return web.json_response(data=response, status=500)

        if found is None:
            _LOGGER.error("No launchpad found")
            response = {
                "status": "ok",
                "payload": {"type": "info", "message": "No launchpad found"},
            }
            return web.json_response(data=response, status=200)

        _LOGGER.info(f"Found launchpad: {found}")
        response = {"status": "success", "device": found}
        return web.json_response(data=response, status=200)
