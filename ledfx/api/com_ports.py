import logging

import serial.tools.list_ports
from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/comports"

    async def get(self) -> web.Response:
        """
        Get the list of available COM ports.

        Returns:
            web.Response: The response containing the list of available COM ports.
        """
        ports = serial.tools.list_ports.comports()

        available_ports = []

        for p in ports:
            available_ports.append(p.device)
        return await self.bare_request_success(available_ports)
