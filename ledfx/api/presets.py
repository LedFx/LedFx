import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.configuration.presets import preset_category
from ledfx.presets import ledfx_presets
from ledfx.utils import generate_defaults, inject_missing_default_keys

_LOGGER = logging.getLogger(__name__)


class PresetsEndpoint(RestEndpoint):
    """REST end-point for querying and managing presets"""

    ENDPOINT_PATH = "/api/effects/{effect_id}/presets"

    async def invalid_effect_id(self, effect_id):
        """
        Helper function to handle the case when an invalid effect ID is provided.

        Args:
            effect_id (str): The ID of the effect that does not exist.

        Returns:
            Response: The invalid request response indicating the error message.

        """
        error_message = f"Effect {effect_id} does not exist"
        _LOGGER.warning(error_message)
        return await self.invalid_request(error_message)

    async def get(self, effect_id) -> web.Response:
        """Get all presets for an effect

        Args:
            effect_id (str): The ID of the effect.

        Returns:
            web.Response: The HTTP response containing the presets for the effect.
        """

        try:
            self._ledfx.effects.get_class(effect_id)
        except BaseException:  # noqa: BLE001
            return await self.invalid_effect_id(effect_id)

        default = generate_defaults(ledfx_presets, self._ledfx.effects, effect_id)

        custom = {
            preset_id: preset.model_dump()
            for preset_id, preset in self._ledfx.config.user_presets.get(
                effect_id, {}
            ).items()
        }

        custom = inject_missing_default_keys(custom, default)

        response = {
            "status": "success",
            "effect": effect_id,
            "ledfx_presets": default,
            "user_presets": custom,
        }
        return await self.bare_request_success(response)

    async def put(self, effect_id, request) -> web.Response:
        """Rename a preset

        Args:
            effect_id (str): The ID of the effect.
            request (web.Request): The request containing `preset_id`, `category`, and `name`.

        Returns:
            web.Response: The HTTP response object.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        preset_id = data.get("preset_id")
        category = data.get("category")
        name = data.get("name")

        if category is None:
            return await self.invalid_request(
                'Required attribute "category" was not provided'
            )
        if preset_id is None:
            return await self.invalid_request(
                'Required attribute "preset_id" was not provided'
            )

        if name is None:
            return await self.invalid_request(
                'Required attribute "name" was not provided'
            )

        if category not in ["ledfx_presets", "user_presets"]:
            return await self.invalid_request(
                f'Category {category} is not "ledfx_presets" or "user_presets"'
            )

        try:
            self._ledfx.effects.get_class(effect_id)
        except BaseException:  # noqa: BLE001
            return await self.invalid_effect_id(effect_id)

        presets = preset_category(self._ledfx.config.user_presets, category)
        if preset_id not in presets[effect_id]:
            return await self.invalid_request(
                f"Preset {preset_id} does not exist for effect {effect_id} in category {category}"
            )

        # Update and save config
        if category == "user_presets":
            self._ledfx.config.user_presets[effect_id][preset_id].name = name
        else:
            ledfx_presets[effect_id][preset_id]["name"] = name
        self._ledfx.config_store.request_save()
        return await self.request_success()

    async def delete(self, effect_id, request) -> web.Response:
        """Delete a preset.

        Args:
            effect_id (str): The ID of the effect.
            request (web.Request): The request containing `preset_id` and `category`.

        Returns:
            web.Response: The HTTP response object.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        preset_id = data.get("preset_id")
        category = data.get("category")

        if category is None:
            return await self.invalid_request(
                'Required attribute "category" was not provided'
            )

        if category not in ["ledfx_presets", "user_presets"]:
            return await self.invalid_request(
                f'Category {category} is not "ledfx_presets" or "user_presets"'
            )

        try:
            self._ledfx.effects.get_class(effect_id)
        except BaseException:  # noqa: BLE001
            return await self.invalid_effect_id(effect_id)

        presets = preset_category(self._ledfx.config.user_presets, category)
        if effect_id not in presets:
            return await self.invalid_request(
                f"Effect {effect_id} does not exist in category {category}"
            )

        if preset_id is None:
            return await self.invalid_request(
                'Required attribute "preset_id" was not provided'
            )

        if preset_id not in presets[effect_id]:
            return await self.invalid_request(
                f"Preset {preset_id} does not exist for effect {effect_id} in category {category}"
            )

        # Delete the preset from configuration
        if category == "user_presets":
            del self._ledfx.config.user_presets[effect_id][preset_id]
        else:
            del ledfx_presets[effect_id][preset_id]

        # Save the config
        self._ledfx.config_store.request_save()
        return await self.request_success()
