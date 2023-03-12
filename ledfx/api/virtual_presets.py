import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class VirtualPresetsEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/virtuals/{virtual_id}/presets"

    async def get(self, virtual_id) -> web.Response:
        """
        Get presets for active effect of a virtual
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            response = {
                "status": "failed",
                "reason": f"Virtual with ID {virtual_id} not found",
            }
            return web.json_response(data=response, status=404)

        if not virtual.active_effect:
            response = {
                "status": "failed",
                "reason": f"Virtual {virtual_id} has no active effect",
            }
            return web.json_response(data=response, status=400)

        effect_id = virtual.active_effect.type

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
            "virtual": virtual_id,
            "effect": effect_id,
            "default_presets": default,
            "custom_presets": custom,
        }

        return web.json_response(data=response, status=200)

    def update_effect_config(self, virtual_id, effect):
        # Store as both the active effect to protect existing code, and one of effects
        virtual = next(
            (
                item
                for item in self._ledfx.config["virtuals"]
                if item["id"] == virtual_id
            ),
            None,
        )
        if virtual:
            if not ("effects" in virtual):
                virtual["effects"] = {}
            virtual["effects"][effect.type] = {}
            virtual["effects"][effect.type]["type"] = effect.type
            virtual["effects"][effect.type]["config"] = effect.config
            if not ("effect" in virtual):
                virtual["effect"] = {}
            virtual["effect"]["type"] = effect.type
            virtual["effect"]["config"] = effect.config

    async def put(self, virtual_id, request) -> web.Response:
        """Set active effect of virtual to a preset"""
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            response = {
                "status": "failed",
                "reason": f"Virtual with ID {virtual_id} not found",
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
        category = data.get("category")
        effect_id = data.get("effect_id")
        preset_id = data.get("preset_id")

        if category is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "category" was not provided',
            }
            return web.json_response(data=response, status=400)

        if category not in ["default_presets", "custom_presets"]:
            response = {
                "status": "failed",
                "reason": f'Category {category} is not "ledfx_presets" or "user_presets"',
            }
            return web.json_response(data=response, status=400)

        if category == "default_presets":
            category = "ledfx_presets"
        else:
            category = "user_presets"

        if effect_id is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "effect_id" was not provided',
            }
            return web.json_response(data=response, status=400)

        if effect_id not in self._ledfx.config[category].keys():
            response = {
                "status": "failed",
                "reason": f"Effect {effect_id} does not exist in category {category}",
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

        # Create the effect and add it to the virtual
        effect_config = self._ledfx.config[category][effect_id][preset_id][
            "config"
        ]
        effect = self._ledfx.effects.create(
            ledfx=self._ledfx, type=effect_id, config=effect_config
        )
        try:
            virtual.set_effect(effect)
        except (ValueError, RuntimeError) as msg:
            response = {
                "status": "failed",
                "payload": {"type": "warning", "reason": str(msg)},
            }
            return web.json_response(data=response, status=202)

        self.update_effect_config(virtual_id, effect)

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

    async def post(self, virtual_id, request) -> web.Response:
        """save configuration of active virtual effect as a custom preset"""
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            response = {
                "status": "failed",
                "reason": f"Virtual with ID {virtual_id} not found",
            }
            return web.json_response(data=response, status=404)

        if not virtual.active_effect:
            response = {
                "status": "failed",
                "reason": f"Virtual {virtual_id} has no active effect",
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
        preset_name = data.get("name")
        if preset_name is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "preset_name" was not provided',
            }
            return web.json_response(data=response, status=400)

        preset_id = generate_id(preset_name)
        effect_id = virtual.active_effect.type

        # If no presets for the effect, create a dict to store them
        if effect_id not in self._ledfx.config["user_presets"].keys():
            self._ledfx.config["user_presets"][effect_id] = {}

        # Update the preset if it already exists, else create it
        self._ledfx.config["user_presets"][effect_id][preset_id] = {}
        self._ledfx.config["user_presets"][effect_id][preset_id][
            "name"
        ] = preset_name
        self._ledfx.config["user_presets"][effect_id][preset_id][
            "config"
        ] = virtual.active_effect.config

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {
            "status": "success",
            "preset": {
                "id": preset_id,
                "name": preset_name,
                "config": virtual.active_effect.config,
            },
        }
        return web.json_response(data=response, status=200)

    async def delete(self, virtual_id) -> web.Response:
        """clear effect of a virtual"""
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            response = {
                "status": "failed",
                "reason": f"Virtual with ID {virtual_id} not found",
            }
            return web.json_response(data=response, status=404)

        # Clear the effect
        virtual.clear_effect()

        for virtual in self._ledfx.config["virtuals"]:
            if virtual["id"] == virtual_id:
                if "effect" in virtual:
                    del virtual["effect"]
                    break
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success", "effect": {}}
        return web.json_response(data=response, status=200)
