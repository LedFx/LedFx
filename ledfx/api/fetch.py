import logging
from urllib.parse import unquote

import requests
from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/fetch/{url}"

    async def get(self, url) -> web.Response:
        """Fetches data for frontend"""
        try:
            response = requests.get(unquote(url))
            data = response.json()
        except requests.exceptions.RequestException:
            msg = f"{unquote(url)}: Failed to fetch"
            raise ValueError(msg)

        return web.json_response(data=data, status=200)
