import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class PresetsEndpoint(RestEndpoint):
    """REST end-point for querying and managing presets"""

    ENDPOINT_PATH = "/api/effects/{effect_id}/presets"

    async def get(self, effect_id) -> web.Response:
        """Get all presets for an effect"""

        try:
            self._ledfx.effects.get_class(effect_id)
        except BaseException:
            response = {
                "status": "failed",
                "reason": f"effect {effect_id} does not exist",
            }
            return web.json_response(data=response, status=400)

        if effect_id in self._ledfx.config["ledfx_presets"].keys():
            default = self._ledfx.config["ledfx_presets"][effect_id]
        else:
            default = {}

        if effect_id in self._ledfx.config["user_presets"].keys():
            custom = self._ledfx.config["user_presets"][effect_id]
        else:
            custom = {}

        response = {
            "status": "success",
            "effect": effect_id,
            "default_presets": default,
            "custom_presets": custom,
        }
        return web.json_response(data=response, status=200)

    async def put(self, effect_id, request) -> web.Response:
        """Rename a preset"""
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        preset_id = data.get("preset_id")
        category = data.get("category")
        name = data.get("name")

        if category is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "category" was not provided',
            }
            return web.json_response(data=response, status=400)

        if category not in ["ledfx_presets", "user_presets"]:
            response = {
                "status": "failed",
                "reason": 'Category {} is not "ledfx_presets" or "user_presets"'.format(
                    category
                ),
            }
            return web.json_response(data=response, status=400)

        if effect_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "effect_id" was not provided',
            }
            return web.json_response(data=response, status=400)

        if effect_id not in self._ledfx.config[category].keys():
            response = {
                "status": "failed",
                "reason": "Effect {} does not exist in category {}".format(
                    effect_id, category
                ),
            }
            return web.json_response(data=response, status=400)

        try:
            self._ledfx.effects.get_class(effect_id)
        except BaseException:
            response = {
                "status": "failed",
                "reason": f"effect {effect_id} does not exist",
            }
            return web.json_response(data=response, status=400)

        if preset_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "preset_id" was not provided',
            }
            return web.json_response(data=response, status=400)

        if preset_id not in self._ledfx.config[category][effect_id].keys():
            response = {
                "status": "failed",
                "reason": "Preset {} does not exist for effect {} in category {}".format(
                    preset_id, effect_id, category
                ),
            }
            return web.json_response(data=response, status=400)

        if name is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "name" was not provided',
            }
            return web.json_response(data=response, status=400)

        # Update and save config
        self._ledfx.config[category][effect_id][preset_id]["name"] = name
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success"}
        return web.json_response(data=response, status=200)

    async def delete(self, effect_id, request) -> web.Response:
        """Delete a preset"""
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)
        preset_id = data.get("preset_id")
        category = data.get("category")

        if category is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "category" was not provided',
            }
            return web.json_response(data=response, status=400)

        if category not in ["ledfx_presets", "user_presets"]:
            response = {
                "status": "failed",
                "reason": 'Category {} is not "ledfx_presets" or "user_presets"'.format(
                    category
                ),
            }
            return web.json_response(data=response, status=400)

        if effect_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "effect_id" was not provided',
            }
            return web.json_response(data=response, status=400)

        try:
            self._ledfx.effects.get_class(effect_id)
        except BaseException:
            response = {
                "status": "failed",
                "reason": f"effect {effect_id} does not exist",
            }
            return web.json_response(data=response, status=400)

        if effect_id not in self._ledfx.config[category].keys():
            response = {
                "status": "failed",
                "reason": "Effect {} does not exist in category {}".format(
                    effect_id, category
                ),
            }
            return web.json_response(data=response, status=400)

        if preset_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "preset_id" was not provided',
            }
            return web.json_response(data=response, status=400)

        if preset_id not in self._ledfx.config[category][effect_id].keys():
            response = {
                "status": "failed",
                "reason": "Preset {} does not exist for effect {} in category {}".format(
                    preset_id, effect_id, category
                ),
            }
            return web.json_response(data=response, status=400)

        # Delete the preset from configuration
        del self._ledfx.config[category][effect_id][preset_id]

        # Save the config
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success"}
        return web.json_response(data=response, status=200)
