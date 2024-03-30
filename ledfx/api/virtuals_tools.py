import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.color import parse_color, validate_color
from ledfx.config import save_config
from ledfx.virtuals import update_effect_config

_LOGGER = logging.getLogger(__name__)

TOOLS = [
    "force_color",
    "calibration",
    "highlight",
    "oneshot",
    "copy",
    "add_words",
    "del_words",
    "new_words",
    "focus_words",
]


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
                except (ValueError, RuntimeError) as msg:
                    continue

                update_effect_config(
                    self._ledfx.config, dest_virtual_id, effect
                )
                updated += 1

            if updated > 0:
                save_config(
                    config=self._ledfx.config,
                    config_dir=self._ledfx.config_dir,
                )
            else:
                return await self.invalid_request(
                    "Virtual copy failed, no valid targets"
                )

        if tool == "new_words":
            _LOGGER.info(
                f"new words: {virtual.name} effect is {virtual.active_effect.name}"
            )
            if virtual.active_effect.name != "Texter":
                return await self.invalid_request(
                    "Virtual new_words failed, active effect is not texter2d"
                )

            words = data.get("words")

            if words is None:
                return await self.invalid_request(
                    "Required attribute for new_words, words was not provided"
                )

            if type(words) is not str or len(words) < 1:
                return await self.invalid_request(
                    "new_words words parameter must be a string with at least one character"
                )

            result = virtual.active_effect.add_words(words, True)

            if result is not None:
                return await self.invalid_request(
                    f"new_words failed: {result}"
                )

        if tool == "add_words":
            _LOGGER.info(
                f"add words: {virtual.name} effect is {virtual.active_effect.name}"
            )
            if virtual.active_effect.name != "Texter":
                return await self.invalid_request(
                    "Virtual add_words failed, active effect is not texter2d"
                )

            words = data.get("words")

            if words is None:
                return await self.invalid_request(
                    "Required attribute for add_words, words was not provided"
                )

            if type(words) is not str or len(words) < 1:
                return await self.invalid_request(
                    "add_words words parameter must be a string with at least one character"
                )

            result = virtual.active_effect.add_words(words, False)

            if result is not None:
                return await self.invalid_request(
                    f"add_words failed: {result}"
                )

        if tool == "del_words":
            _LOGGER.info(
                f"del words: {virtual.name} effect is {virtual.active_effect.name}"
            )
            if virtual.active_effect.name != "Texter":
                return await self.invalid_request(
                    "Virtual del_words failed, active effect is not texter"
                )

            count = data.get("count")

            if count is None:
                return await self.invalid_request(
                    "Required attribute for del_words, count was not provided"
                )

            if type(count) is not int or count < 1:
                return await self.invalid_request(
                    "del_words count parameter must be an integer greater than 0"
                )

            result = virtual.active_effect.del_words(count)

            if result is not None:
                return await self.invalid_request(
                    f"del_words failed: {result}"
                )

        if tool == "focus_words":
            _LOGGER.info(
                f"focus words: {virtual.name} effect is {virtual.active_effect.name}"
            )
            if virtual.active_effect.name != "Texter":
                return await self.invalid_request(
                    "Virtual focus_words failed, active effect is not texter"
                )

            index = data.get("index")

            if index is None:
                return await self.invalid_request(
                    "Required attribute for focus_words, index was not provided"
                )

            if type(index) is not int or index < 0:
                return await self.invalid_request(
                    "focus_words index parameter must be an integer 0 or greater"
                )

            result = virtual.active_effect.focus_words(index)

            if result is not None:
                return await self.invalid_request(
                    f"focus_words failed: {result}"
                )

        effect_response = {}
        effect_response["tool"] = tool

        response = {"status": "success", "tool": tool}
        return await self.bare_request_success(response)
