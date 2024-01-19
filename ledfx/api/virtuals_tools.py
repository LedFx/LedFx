import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.color import parse_color, validate_color

_LOGGER = logging.getLogger(__name__)

TOOLS = ["force_color", "calibration", "highlight", "oneshot"]


class VirtualsToolsEndpoint(RestEndpoint):
    """api for individual virtual tools"""

    ENDPOINT_PATH = "/api/virtuals_tools/{virtual_id}"

    async def get(self, virtual_id) -> web.Response:
        """
        Get the tools specified for a virtual ID.

        Parameters:
        - virtual_id: The ID of the virtual.

        Returns:
        - web.Response: The response containing the tools for the virtual ID.
        """
        return await self.request_success("info", f"Available tools: {TOOLS}")

    async def put(self, virtual_id, request) -> web.Response:
        """
        Uses the specified virtual tool on the virtual.

        Args:
            virtual_id (str): The ID of the virtual.
            request (web.Request): The request object containing the `tool` to use.

        Returns:
            web.Response: The HTTP response object.
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(
                f"Virtual with ID {virtual_id} not found"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        tool = data.get("tool")

        if tool is None:
            return await self.invalid_request(
                'Required attribute "tool" was not provided'
            )

        if tool not in TOOLS:
            return await self.invalid_request(f"Tool {tool} is not in {TOOLS}")

        if tool == "force_color":
            color = data.get("color")
            if color is None:
                return await self.invalid_request(
                    "Required attribute for force_color, color was not provided"
                )

            virtual.force_frame(parse_color(validate_color(color)))

        if tool == "calibration":
            mode = data.get("mode")
            if mode == "on":
                virtual.set_calibration(True)
            elif mode == "off":
                virtual.set_calibration(False)
            else:
                return await self.invalid_request(
                    "Required attribute for calibration, mode:on or mode:off expected"
                )

        if tool == "highlight":
            state = data.get("state", True)
            device = data.get("device")
            start = data.get("start", -1)
            end = data.get("stop", -1)
            flip = data.get("flip", False)

            # test if start and end are integers
            if type(start) is not int or type(end) is not int:
                return await self.invalid_request(
                    "start and end must be integers"
                )

            hl_error = virtual.set_highlight(state, device, start, end, flip)
            if hl_error is not None:
                return await self.invalid_request(
                    f"highlight error: {hl_error}"
                )

        if tool == "oneshot":
            color = data.get("color")
            if color is None:
                return await self.invalid_request(
                    "Required attribute for oneshot, color was not provided"
                )

            ramp = data.get("ramp", 0)
            hold = data.get("hold", 0)
            fade = data.get("fade", 0)

            if sum(ramp, hold, fade) == 0:
                return await self.invalid_request(
                    "At least one of ramp, hold or fade must be greater than 0"
                )

            result = virtual.oneshot(
                parse_color(validate_color(color)), ramp, hold, fade
            )
            if result is False:
                return await self.invalid_request("oneshot failed")

        effect_response = {}
        effect_response["tool"] = tool

        response = {"status": "success", "tool": tool}
        return await self.bare_request_success(response)
