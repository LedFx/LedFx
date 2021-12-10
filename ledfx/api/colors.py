import logging

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class ColorEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/colors"

    async def get(self) -> web.Response:
        """
        Get LedFx colors.
        """
        response = dict(zip(("builtin", "user"), self._ledfx.colors.get_all()))

        return web.json_response(data=response, status=200)

    async def delete(self, request) -> web.Response:
        """
        Deletes a user defined color
        Request body is a string of the color key to delete
        eg. "my_red_color"
        """

        key = await request.json()

        del self._ledfx.colors[key]

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": f"Deleted color {key}",
            },
        }

        return web.json_response(data=response, status=200)

    async def post(self, request) -> web.Response:
        """
        Creates or updates existing color.
        eg. {"my_red_color": "#ffffff"}
        """

        colors = await request.json()

        for key, val in colors.items():
            self._ledfx.colors[key] = val

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": f"Saved color{'s' if len(colors) > 1 else ''}",
            },
        }

        return web.json_response(data=response, status=200)
