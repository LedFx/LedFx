import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class PresetDeleteEndpoint(RestEndpoint):
    """REST end-point for deleting user presets"""

    ENDPOINT_PATH = "/api/effects/{effect_id}/presets/{preset_id}"

    async def delete(self, effect_id, preset_id) -> web.Response:
        """Delete a user preset.

        Args:
            effect_id (str): The ID of the effect.
            preset_id (str): The ID of the preset to delete.

        Returns:
            web.Response: The HTTP response object.
        """
        # Validate effect exists
        try:
            self._ledfx.effects.get_class(effect_id)
        except BaseException:
            error_message = f"Effect {effect_id} does not exist"
            _LOGGER.warning(error_message)
            return await self.invalid_request(error_message)

        # Check if effect has any user presets
        if effect_id not in self._ledfx.config["user_presets"].keys():
            return await self.invalid_request(
                f"Effect {effect_id} has no user presets"
            )

        # Check if preset exists
        if preset_id not in self._ledfx.config["user_presets"][effect_id].keys():
            return await self.invalid_request(
                f"Preset {preset_id} does not exist for effect {effect_id} in user presets"
            )

        # Delete the preset from configuration
        try:
            del self._ledfx.config["user_presets"][effect_id][preset_id]
            
            # Save the config
            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )
        except Exception as e:
            error_message = f"Failed to delete preset {preset_id}: {str(e)}"
            _LOGGER.warning(error_message)
            return await self.invalid_request(error_message)
        
        return await self.request_success()
