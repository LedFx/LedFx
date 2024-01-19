import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.color import validate_color

_LOGGER = logging.getLogger(__name__)


class ColorEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/colors"

    async def get(self) -> web.Response:
        """
        Get LedFx colors and gradients

        Returns:
            web.Response: The response containing the colors and gradients.
        """
        response = {
            "colors": dict(
                zip(("builtin", "user"), self._ledfx.colors.get_all())
            ),
            "gradients": dict(
                zip(("builtin", "user"), self._ledfx.gradients.get_all())
            ),
        }
        return await self.bare_request_success(response)

    async def delete(self, request: web.Request) -> web.Response:
        """
        Deletes a user defined color or gradient
        Request body is a string of the color key to delete
        eg. ["my_red_color"]

        Parameters:
        - request (web.Request): The HTTP request object

        Returns:
        - web.Response: The HTTP response object
        """

        data = await request.json()

        for key in data:
            del self._ledfx.colors[key]
            del self._ledfx.gradients[key]
        return await self.request_success("success", "Deleted {key}")

    async def post(self, request: web.Request) -> web.Response:
        """
        Creates or updates existing colors or gradients.

        Parameters:
        - request (web.Request): The request containing the color or gradient to create or update.

        Returns:
        - web.Response: The HTTP response object.

        Example:
        ```
        {
            "my_red_color": "#ffffff"
        }
        ```
        or
        ```
        {
            "my_cool_gradient": "lin..."
        }
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        if data is None:
            return await self.invalid_request(
                "Required attribute was not provided"
            )

        # TODO: Handle instances where neither color nor gradient is provided
        for key, val in data.items():
            try:
                is_color = validate_color(val)
            except ValueError:
                is_color = False
            if is_color:
                self._ledfx.colors[key] = val
            else:
                self._ledfx.gradients[key] = val

        return await self.request_success("success", "Saved {key}")
