import logging

import serial.tools.list_ports
from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/comports"

    async def get(self) -> web.Response:
        ports = serial.tools.list_ports.comports()

        available_ports = []

        for p in ports:
            available_ports.append(p.device)

        return web.json_response(data=available_ports, status=200)
