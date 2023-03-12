import logging
import os
from json import JSONDecodeError

from aiohttp import web
from notifypy import Notify

from ledfx.api import RestEndpoint
from ledfx.utils import currently_frozen

_LOGGER = logging.getLogger(__name__)


class DeviceStatusEndpoint(RestEndpoint):
    """REST end-point that exposes a notification api"""

    ENDPOINT_PATH = "/api/notify"

    def __init__(self, ledfx):
        self.icon = ledfx.icon
        print(self.icon)

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
        else:
            if currently_frozen():
                current_directory = os.path.dirname(__file__)
                icon_location = os.path.join(current_directory, "tray.png")
            else:
                current_directory = os.path.dirname(__file__)
                icon_location = os.path.join(
                    current_directory,
                    "tray.png",  # sadly cant reach ../../icons/tray.png
                )

            notification = Notify()
            notification.application_name = "LedFx"
            notification.title = title
            notification.message = text
            notification.icon = icon_location
            notification.send(block=False)

        response = {
            "status": "success",
        }

        return web.json_response(data=response, status=200)
