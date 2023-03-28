import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class NotifyEndpoint(RestEndpoint):
    """REST end-point that exposes a notification api"""

    ENDPOINT_PATH = "/api/notify"

    def __init__(self, ledfx):
        self.icon = ledfx.icon

    async def put(self, request) -> web.Response:
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        title = data.get("title")
        if title is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "title" was not provided',
            }
            return web.json_response(data=response, status=400)

        text = data.get("text")
        if text is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "text" was not provided',
            }
            return web.json_response(data=response, status=400)

        _LOGGER.info(f"notify: {title} --- {text}")
        if self.icon is not None:
            if self.icon.HAS_NOTIFICATION:
                self.icon.notify(f"{title}:\n{text}")

        response = {
            "status": "success",
        }

        return web.json_response(data=response, status=200)
