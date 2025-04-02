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

    async def post(self, request: web.Request) -> web.Response:
        """
        Uses the specified virtual tool on all virtuals.

        Args:
            request (web.Request): The request object containing the `tool` to use.

        Returns:
            web.Response: The HTTP response object.
        """

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

        if tool == "oneshot":
            color = parse_color(validate_color(data.get("color", "white")))
            ramp = data.get("ramp", 0)
            hold = data.get("hold", 0)
            fade = data.get("fade", 0)
            brightness = min(1, max(0, data.get("brightness", 1)))

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
            # Disable all oneshot Flash if put request is sent.
            result = False
            for virtual_id in self._ledfx.virtuals:
                virtual = self._ledfx.virtuals.get(virtual_id)
                if virtual is not None:
                    for oneshot in virtual.oneshots:
                        if type(oneshot) == Flash:
                            oneshot.active = False
                            result = True  # return True if there was at least one oneshot Flash to disable

            if result is False:
                return await self.invalid_request("oneshot was not found")

        effect_response = {}
        effect_response["tool"] = tool

        response = {"status": "success", "tool": tool}
        return await self.bare_request_success(response)
