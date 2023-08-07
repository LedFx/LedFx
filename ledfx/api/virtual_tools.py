import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.color import parse_color, validate_color

_LOGGER = logging.getLogger(__name__)


class VirtualToolsEndpoint(RestEndpoint):
    """api for all virtual manipulations"""

    ENDPOINT_PATH = "/api/virtuals_tools"

    async def get(self) -> web.Response:
        """
        No current tools implemented
        """
        response = {
            "status": "success",
            "Data": "No current tools supported",
        }

        return web.json_response(data=response, status=200)

    async def put(self, request) -> web.Response:
        """Extensible tools support"""
        tools = ["force_color", "oneshot"]

        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        tool = data.get("tool")

        if tool is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "tool" was not provided',
            }
            return web.json_response(data=response, status=400)

        if tool not in tools:
            response = {
                "status": "failed",
                "reason": f"Category {tool} is not in {tools}",
            }
            return web.json_response(data=response, status=400)

        if tool == "force_color":
            color = data.get("color")
            if color is None:
                response = {
                    "status": "failed",
                    "reason": "Required attribute for force_color, color was not provided",
                }
                return web.json_response(data=response, status=400)

            for virtual_id in self._ledfx.virtuals:
                virtual = self._ledfx.virtuals.get(virtual_id)
                if virtual.is_device == virtual.id:
                    virtual.force_frame(parse_color(validate_color(color)))

        if tool == "oneshot":
            color = data.get("color")
            if color is None:
                response = {
                    "status": "failed",
                    "reason": "Required attribute for oneshot, color was not provided",
                }
                return web.json_response(data=response, status=400)

            ramp = data.get("ramp", 0)
            hold = data.get("hold", 0)
            fade = data.get("fade", 0)

            if ramp == 0 and hold == 0 and fade == 0:
                response = {
                    "status": "failed",
                    "reason": "At least one of ramp, hold or fade must be greater than 0",
                }
                return web.json_response(data=response, status=400)

            # iterate through all virtuals and apply oneshot
            for virtual_id in self._ledfx.virtuals:
                virtual = self._ledfx.virtuals.get(virtual_id)
                if virtual is not None:
                    virtual.oneshot(
                        parse_color(validate_color(color)), ramp, hold, fade
                    )

        effect_response = {}
        effect_response["tool"] = tool

        response = {"status": "success", "tool": tool}
        return web.json_response(data=response, status=200)
