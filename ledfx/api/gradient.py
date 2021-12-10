import logging

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class GradientEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/gradients"

    async def get(self) -> web.Response:
        """
        Get LedFx gradients.
        """
        response = dict(
            zip(("builtin", "user"), self._ledfx.gradients.get_all())
        )

        return web.json_response(data=response, status=200)

    async def delete(self, request) -> web.Response:
        """
        Deletes a user defined gradient
        Request body is a string of the gradient key to delete
        eg. "my_cool_gradient"
        """

        key = await request.json()

        del self._ledfx.gradients[key]

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": f"Deleted gradient {key}",
            },
        }

        return web.json_response(data=response, status=200)

    async def post(self, request) -> web.Response:
        """
        Creates or updates existing gradient.
        eg. {"my_cool_gradient": "linear_gradient(...)"}
        """

        gradients = await request.json()

        for key, val in gradients.items():
            self._ledfx.gradients[key] = val

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": f"Saved gradient{'s' if len(gradients) > 1 else ''}",
            },
        }

        return web.json_response(data=response, status=200)
