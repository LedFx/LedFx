import logging
import random

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class EffectsEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/devices/{device_id}/effects"

    async def get(self, device_id) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        # Get the active effect
        response = {"effect": {}}
        if device.active_effect:
            effect_response = {}
            effect_response["config"] = device.active_effect.config
            effect_response["name"] = device.active_effect.name
            effect_response["type"] = device.active_effect.type
            response = {"effect": effect_response}

        return web.json_response(data=response, status=200)

    async def put(self, device_id, request) -> web.Response:
        """Update the config of the active effect of a device"""
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        if not device.active_effect:
            response = {
                "status": "failed",
                "reason": "Device {} has no active effect to update config".format(
                    device_id
                ),
            }
            return web.json_response(data=response, status=500)

        data = await request.json()
        effect_config = data.get("config")
        effect_type = data.get("type")
        if effect_config is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "config" was not provided',
            }
            return web.json_response(data=response, status=500)

        if effect_config == "RANDOMIZE":
            # Parse and break down schema for effect, in order to generate
            # acceptable random values
            effect_config = {}
            effect_type = device.active_effect.type
            effect = self._ledfx.effects.get_class(effect_type)
            schema = effect.schema().schema
            for setting in schema.keys():
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

        # Create the effect and add it to the device
        effect = self._ledfx.effects.create(
            ledfx=self._ledfx, type=effect_type, config=effect_config
        )
        device.set_effect(effect)

        # Update and save the configuration
        for device in self._ledfx.config["devices"]:
            if device["id"] == device_id:
                # if not ('effect' in device):
                device["effect"] = {}
                device["effect"]["type"] = effect_type
                device["effect"]["config"] = effect_config
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

    async def post(self, device_id, request) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        data = await request.json()
        effect_type = data.get("type")
        if effect_type is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "type" was not provided',
            }
            return web.json_response(data=response, status=500)

        effect_config = data.get("config")
        if effect_config is None:
            effect_config = {}

        # Create the effect and add it to the device
        effect = self._ledfx.effects.create(
            ledfx=self._ledfx, type=effect_type, config=effect_config
        )
        device.set_effect(effect)

        # Update and save the configuration
        for device in self._ledfx.config["devices"]:
            if device["id"] == device_id:
                # if not ('effect' in device):
                device["effect"] = {}
                device["effect"]["type"] = effect_type
                device["effect"]["config"] = effect_config
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

    async def delete(self, device_id) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        # Clear the effect
        device.clear_effect()

        for device in self._ledfx.config["devices"]:
            if device["id"] == device_id:
                if "effect" in device:
                    del device["effect"]
                    break
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success", "effect": {}}
        return web.json_response(data=response, status=200)
