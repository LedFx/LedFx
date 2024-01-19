import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.devices.launchpad import find_launchpad

_LOGGER = logging.getLogger(__name__)


class FindLaunchpadDevicesEndpoint(RestEndpoint):
    """REST end-point for detecting and reporting Launchpad device"""

    ENDPOINT_PATH = "/api/find_launchpad"

    async def get(self) -> web.Response:
        """
        Check for launchpad present

        Returns:
            web.Response: The response containing the information about the launchpad.
        """
        try:
            found = find_launchpad()
        except Exception as msg:
            error_message = f"Error checking for launchpad: {msg}"
            _LOGGER.warning(error_message)
            return await self.internal_error("error", error_message)

        if found is None:
            _LOGGER.warning("No launchpad found")
            return await self.request_success("info", "No launchpad found")

        _LOGGER.info(f"Found launchpad: {found}")
        return await self.request_success("info", "Found launchpad")
