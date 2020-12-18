import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class DevicePresetsEndpoint(RestEndpoint):

    ENDPOINT_PATH = "/api/devices/{device_id}/presets"

    async def get(self, device_id) -> web.Response:
        """get presets for active effect of a device"""
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        if not device.active_effect:
            response = {
                "status": "failed",
                "reason": "Device {} has no active effect".format(device),
            }
            return web.json_response(data=response, status=500)

        effect_id = device.active_effect.type

        if effect_id in self._ledfx.config["default_presets"].keys():
            default = self._ledfx.config["default_presets"][effect_id]
        else:
            default = {}

        if effect_id in self._ledfx.config["custom_presets"].keys():
            custom = self._ledfx.config["custom_presets"][effect_id]
        else:
            custom = {}

        response = {
            "status": "success",
            "device": device_id,
            "effect": effect_id,
            "default_presets": default,
            "custom_presets": custom,
        }

        return web.json_response(data=response, status=200)

    async def put(self, device_id, request) -> web.Response:
        """set active effect of device to a preset"""
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        data = await request.json()
        category = data.get("category")
        effect_id = data.get("effect_id")
        preset_id = data.get("preset_id")

        if category is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "category" was not provided',
            }
            return web.json_response(data=response, status=500)

        if category not in ["default_presets", "custom_presets"]:
            response = {
                "status": "failed",
                "reason": 'Category {} is not "default_presets" or "custom_presets"'.format(
                    category
                ),
            }
            return web.json_response(data=response, status=500)

        if effect_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "effect_id" was not provided',
            }
            return web.json_response(data=response, status=500)

        if effect_id not in self._ledfx.config[category].keys():
            response = {
                "status": "failed",
                "reason": "Effect {} does not exist in category {}".format(
                    effect_id, category
                ),
            }
            return web.json_response(data=response, status=500)

        if preset_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "preset_id" was not provided',
            }
            return web.json_response(data=response, status=500)

        if preset_id not in self._ledfx.config[category][effect_id].keys():
            response = {
                "status": "failed",
                "reason": "Preset {} does not exist for effect {} in category {}".format(
                    preset_id, effect_id, category
                ),
            }
            return web.json_response(data=response, status=500)

        # Create the effect and add it to the device
        effect_config = self._ledfx.config[category][effect_id][preset_id][
            "config"
        ]
        effect = self._ledfx.effects.create(
            ledfx=self._ledfx, type=effect_id, config=effect_config
        )
        device.set_effect(effect)

        # Update and save the configuration
        for device in self._ledfx.config["devices"]:
            if device["id"] == device_id:
                # if not ('effect' in device):
                device["effect"] = {}
                device["effect"]["type"] = effect_id
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
        """save configuration of active device effect as a custom preset"""
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        if not device.active_effect:
            response = {
                "status": "failed",
                "reason": "device {} has no active effect".format(device_id),
            }
            return web.json_response(data=response, status=404)

        data = await request.json()
        preset_name = data.get("name")
        if preset_name is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "preset_name" was not provided',
            }
            return web.json_response(data=response, status=500)

        preset_id = generate_id(preset_name)
        effect_id = device.active_effect.type

        # If no presets for the effect, create a dict to store them
        if effect_id not in self._ledfx.config["custom_presets"].keys():
            self._ledfx.config["custom_presets"][effect_id] = {}

        # Update the preset if it already exists, else create it
        self._ledfx.config["custom_presets"][effect_id][preset_id] = {}
        self._ledfx.config["custom_presets"][effect_id][preset_id][
            "name"
        ] = preset_name
        self._ledfx.config["custom_presets"][effect_id][preset_id][
            "config"
        ] = device.active_effect.config

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {
            "status": "success",
            "preset": {
                "id": preset_id,
                "name": preset_name,
                "config": device.active_effect.config,
            },
        }
        return web.json_response(data=response, status=200)

    async def delete(self, device_id) -> web.Response:
        """clear effect of a device"""
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
