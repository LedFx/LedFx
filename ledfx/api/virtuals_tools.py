import logging
from json import JSONDecodeError
from typing import Annotated

from aiohttp import web
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from ledfx.api import RestEndpoint
from ledfx.color import validate_color
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import Highlight, OneshotParams
from ledfx.errors import Conflict, Invalid

_LOGGER = logging.getLogger(__name__)

TOOLS = ["force_color", "calibration", "highlight", "oneshot", "copy"]


class OneshotRequest(BaseModel):
    """POST body for the oneshot tool. Times are in milliseconds."""

    # An infinite fade never expires and turns the pixels to NaN.
    model_config = ConfigDict(allow_inf_nan=False)

    # validate_color turns a [r, g, b] list into "#rrggbb" too.
    color: Annotated[str | list[int], AfterValidator(validate_color)] = "white"
    ramp: float = Field(0, ge=0)
    hold: float = Field(0, ge=0)
    fade: float = Field(0, ge=0)
    # Values outside 0-1 are clamped, as they always were.
    brightness: float = 1

    def params(self) -> OneshotParams:
        return OneshotParams(
            color=str(self.color),  # a str once validated
            ramp_ms=self.ramp,
            hold_ms=self.hold,
            fade_ms=self.fade,
            brightness=self.brightness,
        )


async def refuse_post_tool(
    endpoint: RestEndpoint, tool: object, tools: list[str]
) -> web.Response | None:
    """The failure response for a POST tool other than oneshot, else None."""
    if tool is None:
        return await endpoint.invalid_request(
            'Required attribute "tool" was not provided'
        )
    if tool not in tools:
        return await endpoint.invalid_request(f"Tool {tool} is not in {tools}")
    if tool != "oneshot":
        return await endpoint.invalid_request(
            f"POST only runs the oneshot tool; use PUT for {tool}"
        )
    return None


class VirtualsToolsEndpoint(RestEndpoint):
    """api for individual virtual tools"""

    ENDPOINT_PATH = "/api/virtuals_tools/{virtual_id}"

    async def get(self, virtual_id: str) -> web.Response:
        """
        Get the tools specified for a virtual ID.

        Parameters:
        - virtual_id: The ID of the virtual.

        Returns:
        - web.Response: The response containing the tools for the virtual ID.
        """
        return await self.request_success("info", f"Available tools: {TOOLS}")

    async def post(self, virtual_id: str, request: web.Request) -> web.Response:
        """
        Uses the specified virtual tool on the virtual.

        Args:
            virtual_id (str): The ID of the virtual.
            request (web.Request): The request object containing the `tool` to use.

        Returns:
            web.Response: The HTTP response object.
        """
        if self._ledfx.virtuals.get(virtual_id) is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        tool = data.get("tool")
        if refused := await refuse_post_tool(self, tool, TOOLS):
            return refused

        oneshot = OneshotRequest.model_validate(data)
        try:
            self._ledfx.virtuals.oneshot(VirtualIdStr(virtual_id), oneshot.params())
        except Conflict:
            return await self.invalid_request("oneshot failed")

        response = {"status": "success", "tool": tool}
        return await self.bare_request_success(response)

    async def put(self, virtual_id: str, request: web.Request) -> web.Response:
        """
        Uses the specified virtual tool on the virtual.

        Args:
            virtual_id (str): The ID of the virtual.
            request (web.Request): The request object containing the `tool` to use.

        Returns:
            web.Response: The HTTP response object.
        """
        if self._ledfx.virtuals.get(virtual_id) is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        tool = data.get("tool")
        virtuals = self._ledfx.virtuals
        vid = VirtualIdStr(virtual_id)

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
                virtuals.force_color(vid, validate_color(color))
            except (ValueError, Invalid) as e:
                return await self.invalid_request(str(e))

        if tool == "calibration":
            mode = data.get("mode")
            if mode in ("on", "off"):
                virtuals.set_calibration(vid, mode == "on")
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
                return await self.invalid_request("start and end must be integers")

            highlight = Highlight(device, start, end, flip) if state else None
            try:
                virtuals.set_highlight(vid, highlight, strict_off=True)
            except (Conflict, Invalid) as err:
                return await self.invalid_request(f"highlight error: {err.detail}")

        # Disable the virtual's oneshot Flashes
        if tool == "oneshot" and not virtuals.clear_oneshots(vid):
            return await self.invalid_request("oneshot was not found")

        if tool == "copy":
            # copy the config of the specified virtual instance to all virtuals listed in the target payload
            target = data.get("target")
            # test if target is none or not a list

            if target is None:
                return await self.invalid_request(
                    "Required attribute for copy, target was not provided"
                )
            if type(target) is not list:
                return await self.invalid_request(
                    "Required attribute for copy, target must be a list"
                )
            try:
                virtuals.copy_effect(vid, [VirtualIdStr(t) for t in target])
            except (Conflict, Invalid) as err:
                return await self.invalid_request(err.detail)

        response = {"status": "success", "tool": tool}
        return await self.bare_request_success(response)
