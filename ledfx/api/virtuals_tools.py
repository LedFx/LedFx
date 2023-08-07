import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.color import parse_color, validate_color

_LOGGER = logging.getLogger(__name__)


class VirtualsToolsEndpoint(RestEndpoint):
    """api for individual virtual tools"""

    ENDPOINT_PATH = "/api/virtuals_tools/{virtual_id}"

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
            "Data": "No current tools supported",
        }

        return web.json_response(data=response, status=200)

    async def put(self, virtual_id, request) -> web.Response:
        """Extensible tools support"""
        tools = ["force_color", "calibration", "highlight", "oneshot"]

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

            virtual.force_frame(parse_color(validate_color(color)))

        if tool == "calibration":
            mode = data.get("mode")
            if mode == "on":
                virtual.set_calibration(True)
            elif mode == "off":
                virtual.set_calibration(False)
            else:
                response = {
                    "status": "failed",
                    "reason": "calibration mode:on or mode:off expected",
                }
                return web.json_response(data=response, status=400)

        if tool == "highlight":
            state = data.get("state", True)
            device = data.get("device")
            start = data.get("start", -1)
            end = data.get("stop", -1)
            flip = data.get("flip", False)

            # test if start and end are integers
            try:
                start = int(start)
                end = int(end)
            except ValueError:
                response = {
                    "status": "failed",
                    "reason": "start and end must be integers",
                }
                return web.json_response(data=response, status=400)

            hl_error = virtual.set_highlight(state, device, start, end, flip)
            if hl_error is not None:
                response = {
                    "status": "failed",
                    "reason": hl_error,
                }
                return web.json_response(data=response, status=400)

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

            result = virtual.oneshot(
                parse_color(validate_color(color)), ramp, hold, fade
            )
            if result is False:
                response = {
                    "status": "failed",
                    "reason": f"virtual {virtual_id} is not active",
                }
                return web.json_response(data=response, status=400)

        effect_response = {}
        effect_response["tool"] = tool

        response = {"status": "success", "tool": tool}
        return web.json_response(data=response, status=200)
