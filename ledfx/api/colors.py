import logging

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class ColorEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/colors"

    async def get(self) -> web.Response:
        """
        Get LedFx colors and gradients
        """
        response = {
            "colors": dict(
                zip(("builtin", "user"), self._ledfx.colors.get_all())
            ),
            "gradients": dict(
                zip(("builtin", "user"), self._ledfx.gradients.get_all())
            ),
        }

        return web.json_response(data=response, status=200)

    async def delete(self, request) -> web.Response:
        """
        Deletes a user defined color or gradient
        Request body is a string of the color key to delete
        eg. {
            "colors": ["my_red_color"],
        }
        """

        data = await request.json()

        colors = data.get("colors")
        gradients = data.get("gradients")

        for key in colors:
            del self._ledfx.colors[key]

        for key in gradients:
            del self._ledfx.gradients[key]

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": "Deleted",
            },
        }

        return web.json_response(data=response, status=200)

    async def post(self, request) -> web.Response:
        """
        Creates or updates existing colors or gradients.
        eg. {
            "colors: {"my_red_color": "#ffffff"},
            "gradients": {"my_cool_gradient": "lin..."}
        }
        """

        data = await request.json()

        colors = data.get("colors")
        gradients = data.get("gradients")

        for key, val in colors.items():
            self._ledfx.colors[key] = val

        for key, val in gradients.items():
            self._ledfx.gradients[key] = val

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": "Saved",
            },
        }

        return web.json_response(data=response, status=200)
