import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.v1_compat import v1_color
from ledfx.api.virtuals_tools import OneshotRequest, refuse_post_tool

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
        if refused := await refuse_post_tool(self, tool, TOOLS):
            return refused

        oneshot = OneshotRequest.model_validate(data)
        self._ledfx.virtuals.oneshot(None, oneshot.params())

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
            try:
                # Every device's own virtual
                # v1-compat: a colour may be an [r, g, b] list.
                self._ledfx.virtuals.force_color(None, v1_color(color))
            except ValueError as e:
                return await self.invalid_request(str(e))

        # Disable every virtual's oneshot Flashes
        if tool == "oneshot" and not self._ledfx.virtuals.clear_oneshots(None):
            return await self.invalid_request("oneshot was not found")

        response = {"status": "success", "tool": tool}
        return await self.bare_request_success(response)
