import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.color import parse_color, validate_color

_LOGGER = logging.getLogger(__name__)


class VirtualToolsEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/virtuals/{virtual_id}/tools"

    async def get(self, virtual_id) -> web.Response:
        """
        Get presets for active effect of a virtual
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            response = {
                "status": "failed",
                "reason": f"Virtual with ID {virtual_id} not found",
            }
            return web.json_response(data=response, status=404)

        response = {
            "status": "success",
            "virtual": virtual_id,
            "Data": "Nothing to see, Move along",
        }

        return web.json_response(data=response, status=200)

    async def put(self, virtual_id, request) -> web.Response:
        """Extensible tools support"""
        tools = ["force_color"]

        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            response = {
                "status": "failed",
                "reason": f"Virtual with ID {virtual_id} not found",
            }
            return web.json_response(data=response, status=404)

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

        if tool not in ["force_color"]:
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

            virtual.force_frame(parse_color(validate_color(color)))

        effect_response = {}
        effect_response["tool"] = tool

        response = {"status": "success", "tool": tool}
        return web.json_response(data=response, status=200)
