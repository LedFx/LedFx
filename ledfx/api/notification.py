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

    async def put(self, request: web.Request) -> web.Response:
        """
        Handle the PUT request for notifications.

        Args:
            request (web.Request): The request object containing the notification `title` and `text`.

        Returns:
            web.Response: The response object.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        title = data.get("title")
        if title is None:
            return await self.invalid_request(
                'Required attribute "title" was not provided'
            )

        text = data.get("text")
        if text is None:
            return await self.invalid_request(
                'Required attribute "text" was not provided'
            )

        _LOGGER.info(f"notify: {title} --- {text}")
        if self.icon is not None:
            if self.icon.HAS_NOTIFICATION:
                self.icon.notify(f"{title}:\n{text}")
        return await self.request_success()
