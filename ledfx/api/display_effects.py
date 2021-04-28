import logging
import random
from json import JSONDecodeError

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class EffectsEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/displays/{display_id}/effects"

    async def get(self, display_id) -> web.Response:
        """
        Get active effect configuration for a display
        """
        display = self._ledfx.displays.get(display_id)
        if display is None:
            response = {
                "status": "failed",
                "reason": f"Display with ID {display_id} not found",
            }
            return web.json_response(data=response, status=404)

        # Get the active effect
        response = {"effect": {}}
        if display.active_effect:
            effect_response = {}
            effect_response["config"] = display.active_effect.config
            effect_response["name"] = display.active_effect.name
            effect_response["type"] = display.active_effect.type
            response = {"effect": effect_response}

        return web.json_response(data=response, status=200)

    async def put(self, display_id, request) -> web.Response:
        """
        Update the config of the active effect of a display
        """
        display = self._ledfx.displays.get(display_id)
        if display is None:
            response = {
                "status": "failed",
                "reason": f"Display with ID {display_id} not found",
            }
            return web.json_response(data=response, status=404)

        if not display.active_effect:
            response = {
                "status": "failed",
                "reason": f"Display {display_id} has no active effect",
            }
            return web.json_response(data=response, status=400)

        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)
        effect_config = data.get("config")
        effect_type = data.get("type")
        if effect_config is None:
            effect_config = {}
        if effect_config == "RANDOMIZE":
            # Parse and break down schema for effect, in order to generate
            # acceptable random values
            ignore_settings = ["brightness"]
            effect_config = {}
            effect_type = display.active_effect.type
            effect = self._ledfx.effects.get_class(effect_type)
            schema = effect.schema().schema
            for setting in schema.keys():
                if setting in ignore_settings:
                    continue
                # Booleans
                if schema[setting] is bool:
                    val = random.choice([True, False])
                # Lists
                elif isinstance(schema[setting], vol.validators.In):
                    val = random.choice(schema[setting].container)
                # All (assuming coerce(float/int), range(min,max))
                # NOTE: vol.coerce(float/int) does not give enough info for a random value to be generated!
                # *** All effects should give a range! ***
                # This is also important for when sliders will be added, slider
                # needs a start and stop
                elif isinstance(schema[setting], vol.validators.All):
                    for validator in schema[setting].validators:
                        if isinstance(validator, vol.validators.Coerce):
                            coerce_type = validator.type
                        elif isinstance(validator, vol.validators.Range):
                            lower = validator.min
                            upper = validator.max
                    if coerce_type is float:
                        val = random.uniform(lower, upper)
                    elif coerce_type is int:
                        val = random.randint(lower, upper)
                effect_config[setting.schema] = val

        # See if display's active effect type matches this effect type,
        # if so update the effect config
        # otherwise, create a new effect and add it to the display

        # DO NOT DELETE THIS
        # this is nice code to UPDATE the effect config of an active effect
        # this is commented out until frontend sends incremental effect updates
        # so that transitions can now apply on any effect config change.
        # with incremental updates, we can be smart and only apply transition
        # on changes to keys like gradient or colour. but we're gonna wait until
        # frontend incremental updates bc it would make that so much easier

        try:
            # handling an effect update. nested if else and repeated code bleh. ain't a looker ;)
            if (
                display.active_effect
                and display.active_effect.type == effect_type
            ):
                # substring search to match any key containing "color" or "colour"
                # this handles special cases where we want to update an effect and also trigger
                # a transition by creating a new effect.
                if next(
                    (
                        key
                        for key in effect_config.keys()
                        if "color" or "colour" in key
                    ),
                    None,
                ):
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=effect_type,
                        config=display.active_effect.config | effect_config,
                    )
                    display.set_effect(effect)
                else:
                    effect = display.active_effect
                    display.active_effect.update_config(effect_config)

            # handling a new effect
            else:
                effect = self._ledfx.effects.create(
                    ledfx=self._ledfx, type=effect_type, config=effect_config
                )
                display.set_effect(effect)

        except (ValueError, RuntimeError) as msg:
            response = {
                "status": "failed",
                "payload": {"type": "warning", "reason": str(msg)},
            }
            return web.json_response(data=response, status=202)

        # Update and save the configuration
        for display in self._ledfx.config["displays"]:
            if display["id"] == display_id:
                if not ("effect" in display):
                    display["effect"] = {}
                    display["effect"]["type"] = effect.type
                    display["effect"]["config"] = effect.config
                    break

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        effect_response = {}
        effect_response["config"] = effect.config
        effect_response["name"] = effect.name
        effect_response["type"] = effect.type

        response = {"status": "success", "effect": effect_response}
        return web.json_response(data=response, status=200)

    async def post(self, display_id, request) -> web.Response:
        """
        Set the active effect of a display
        """
        display = self._ledfx.displays.get(display_id)
        if display is None:
            response = {
                "status": "failed",
                "reason": f"Display with ID {display_id} not found",
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
        effect_type = data.get("type")
        if effect_type is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "type" was not provided',
            }
            return web.json_response(data=response, status=400)

        effect_config = data.get("config")
        if effect_config is None:
            effect_config = {}

        # Create the effect and add it to the display
        effect = self._ledfx.effects.create(
            ledfx=self._ledfx, type=effect_type, config=effect_config
        )
        try:
            display.set_effect(effect)
        except (ValueError, RuntimeError) as msg:
            response = {
                "status": "failed",
                "payload": {"type": "warning", "reason": str(msg)},
            }
            return web.json_response(data=response, status=202)

        # Update and save the configuration
        for display in self._ledfx.config["displays"]:
            if display["id"] == display_id:
                # if not ('effect' in display):
                display["effect"] = {}
                display["effect"]["type"] = effect_type
                display["effect"]["config"] = effect_config
                break
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        effect_response = {}
        effect_response["config"] = effect.config
        effect_response["name"] = effect.name
        effect_response["type"] = effect.type

        response = {"status": "success", "effect": effect_response}
        return web.json_response(data=response, status=200)

    async def delete(self, display_id) -> web.Response:
        display = self._ledfx.displays.get(display_id)
        if display is None:
            response = {
                "status": "failed",
                "reason": f"Display with ID {display_id} not found",
            }
            return web.json_response(data=response, status=404)

        # Clear the effect
        display.clear_effect()

        for display in self._ledfx.config["displays"]:
            if display["id"] == display_id:
                if "effect" in display:
                    del display["effect"]
                    break
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success", "effect": {}}
        return web.json_response(data=response, status=200)
