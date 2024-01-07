import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.color import parse_color, validate_color

_LOGGER = logging.getLogger(__name__)
TOOLS = ["force_color", "oneshot"]


class VirtualToolsEndpoint(RestEndpoint):
    """api for all virtual manipulations"""

    ENDPOINT_PATH = "/api/virtuals_tools"

    async def get(self) -> web.Response:
        return await self.request_success("info", f"Available tools: {TOOLS}")

    async def put(self, request: web.Request) -> web.Response:
        """Extensible tools support"""

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
            for virtual_id in self._ledfx.virtuals:
                virtual = self._ledfx.virtuals.get(virtual_id)
                if virtual.is_device == virtual.id:
                    virtual.force_frame(parse_color(validate_color(color)))

        if tool == "oneshot":
            color = data.get("color")
            if color is None:
                return await self.invalid_request(
                    "Required attribute for oneshot, color was not provided"
                )

            ramp = data.get("ramp", 0)
            hold = data.get("hold", 0)
            fade = data.get("fade", 0)

            if ramp == 0 and hold == 0 and fade == 0:
                return await self.invalid_request(
                    "At least one of ramp, hold or fade must be greater than 0"
                )

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
        return await self.bare_request_success(response)
