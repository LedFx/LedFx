import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.color import parse_color, validate_color
from ledfx.effects.oneshots.oneshot import Flash

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
            color = parse_color(validate_color(data.get("color", "white")))
            ramp = data.get("ramp", 0)
            hold = data.get("hold", 0)
            fade = data.get("fade", 0)
            brightness = data.get("brightness", 1)

            # if all values are zero, we will now just ensure any current
            # oneshot are cancelled

            # iterate through all virtuals and apply oneshot
            for virtual_id in self._ledfx.virtuals:
                virtual = self._ledfx.virtuals.get(virtual_id)
                if virtual is not None:
                    virtual.add_oneshot(
                        Flash(color, ramp, hold, fade, brightness)
                    )

        effect_response = {}
        effect_response["tool"] = tool

        response = {"status": "success", "tool": tool}
        return await self.bare_request_success(response)
