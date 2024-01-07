import logging
from urllib.parse import unquote

import requests
from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


# TODO: Figure out what this is and what uses it and if it's needed
# Worried it's a potential security issue since it can be used as a proxy
# to fetch any URL on the internet or local network without authentication
# and without CORS restrictions (since it's a local API)
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
