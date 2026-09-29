import logging
from json import JSONDecodeError
from typing import Annotated

from aiohttp import web
from pydantic import AfterValidator, BaseModel, ConfigDict, Field

from ledfx.api import RestEndpoint
from ledfx.color import parse_color, validate_color
from ledfx.effects.oneshots.oneshot import Flash

_LOGGER = logging.getLogger(__name__)

TOOLS = ["force_color", "calibration", "highlight", "oneshot", "copy"]


class OneshotRequest(BaseModel):
    """POST body for the oneshot tool. Times are in milliseconds."""

    # An infinite fade never expires and turns the pixels to NaN.
    model_config = ConfigDict(allow_inf_nan=False)

    color: Annotated[str | list[int], AfterValidator(validate_color)] = "white"
    ramp: float = Field(0, ge=0)
    hold: float = Field(0, ge=0)
    fade: float = Field(0, ge=0)
    # Values outside 0-1 are clamped, as they always were.
    brightness: float = 1

    def flash(self) -> Flash:
        brightness = min(1, max(0, self.brightness))
        return Flash(
            parse_color(self.color), self.ramp, self.hold, self.fade, brightness
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

    async def get(self, virtual_id) -> web.Response:
        """
        Get the tools specified for a virtual ID.

        Parameters:
        - virtual_id: The ID of the virtual.

        Returns:
        - web.Response: The response containing the tools for the virtual ID.
        """
        return await self.request_success("info", f"Available tools: {TOOLS}")

    async def post(self, virtual_id, request) -> web.Response:
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
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        tool = data.get("tool")
        if refused := await refuse_post_tool(self, tool, TOOLS):
            return refused

        oneshot = OneshotRequest.model_validate(data)
        if virtual.add_oneshot(oneshot.flash()) is False:
            return await self.invalid_request("oneshot failed")

        response = {"status": "success", "tool": tool}
        return await self.bare_request_success(response)

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
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

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
                rgb = parse_color(validate_color(color))
            except ValueError as e:
                return await self.invalid_request(str(e))
            virtual.force_frame(rgb)

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
                return await self.invalid_request("start and end must be integers")

            hl_error = virtual.set_highlight(state, device, start, end, flip)
            if hl_error is not None:
                return await self.invalid_request(f"highlight error: {hl_error}")

        if tool == "oneshot":
            result = False
            for oneshot in virtual.oneshots:
                if isinstance(oneshot, Flash):
                    oneshot.active = False
                    result = True  # return True if there was at least one oneshot Flash to disable

            if result is False:
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
            updated = 0
            if virtual.active_effect is None:
                return await self.invalid_request(
                    "Virtual copy failed, no active effect on source virtual"
                )

            for dest_virtual_id in target:
                dest_virtual = self._ledfx.virtuals.get(dest_virtual_id)
                if dest_virtual is None:
                    continue

                try:
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=virtual.active_effect.type,
                        config=virtual.active_effect.config,
                    )

                    dest_virtual.set_effect(effect)
                except (ValueError, RuntimeError):
                    continue

                dest_virtual.update_effect_config(effect)
                updated += 1

            if updated > 0:
                self._ledfx.config_store.request_save()
            else:
                return await self.invalid_request(
                    "Virtual copy failed, no valid targets"
                )

        effect_response = {}
        effect_response["tool"] = tool

        response = {"status": "success", "tool": tool}
        return await self.bare_request_success(response)
