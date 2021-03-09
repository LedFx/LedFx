import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class GraphicsQualityEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/graphics_quality"

    async def get(self) -> web.Response:
        """Get graphics quality setting"""

        response = {
            "graphics_quality": self._ledfx.config.get("graphics_quality")
        }

        return web.json_response(data=response, status=200)

    async def put(self, request) -> web.Response:
        """Set graphics quality setting"""
        data = await request.json()
        graphics_quality = data.get("graphics_quality")

        if graphics_quality is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "graphics_quality" was not provided',
            }
            return web.json_response(data=response, status=500)

        if graphics_quality not in ["low", "medium", "high", "ultra"]:
            response = {
                "status": "failed",
                "reason": "Invalid graphics_quality [{}]".format(
                    graphics_quality
                ),
            }
            return web.json_response(data=response, status=500)

        # Update and save config
        self._ledfx.config["graphics_quality"] = graphics_quality

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        # reopen all websockets with new graphics settings

        response = {"status": "success"}
        return web.json_response(data=response, status=200)
