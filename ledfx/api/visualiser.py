"""
Visualiser API Endpoint

Provides REST API for controlling the browser-based visualiser settings.
This allows the visualiser to be configured via API, similar to devices.

The visualiser settings are stored in the config and can be:
- Retrieved (GET)
- Updated (PUT)
- Reset to defaults (DELETE)
"""

import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)

# Default visualiser configuration
DEFAULT_VISUALISER_CONFIG = {
    "visualType": "bars3d",
    "sensitivity": 1.0,
    "smoothing": 0.7,
    "audioSource": "backend",
    "autoChange": False,
    "postProcessing": {
        "bloom": {"enabled": False, "threshold": 0.5, "intensity": 0.5, "radius": 4},
        "kaleidoscope": {"enabled": False, "sides": 6, "angle": 0},
        "glitch": {"enabled": False, "amount": 0.5, "speed": 1},
        "rgbShift": {"enabled": False, "amount": 0.01, "angle": 0, "radial": False},
        "led": {"enabled": False, "spacing": 10, "size": 6, "brightness": 1.2, "showGrid": False},
        "vignette": {"enabled": False, "radius": 0.75, "softness": 0.45, "intensity": 0.5},
        "filmGrain": {"enabled": False, "intensity": 0.15, "grainSize": 2, "colored": False},
        "godRays": {"enabled": False, "lightX": 0.5, "lightY": 0.5, "intensity": 0.5, "threshold": 0.5},
    },
    "audioReactors": {},
    "presets": [],
}


class VisualiserEndpoint(RestEndpoint):
    """REST endpoint for querying and managing visualiser settings"""

    ENDPOINT_PATH = "/api/visualiser"

    async def get(self) -> web.Response:
        """
        Get current visualiser configuration

        Returns:
            web.Response: The response containing the visualiser config
        """
        # Get visualiser config from ledfx config, or use defaults
        visualiser_config = self._ledfx.config.get("visualiser", DEFAULT_VISUALISER_CONFIG.copy())

        response = {
            "status": "success",
            "config": visualiser_config,
        }
        return web.json_response(data=response, status=200)

    async def put(self, request: web.Request) -> web.Response:
        """
        Update visualiser configuration

        Args:
            request (web.Request): The request object containing the config updates

        Returns:
            web.Response: The response indicating success or failure
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        new_config = data.get("config")
        if new_config is None:
            return await self.invalid_request(
                'Required attribute "config" was not provided'
            )

        # Get current config or defaults
        current_config = self._ledfx.config.get("visualiser", DEFAULT_VISUALISER_CONFIG.copy())

        # Merge new config with current config (deep merge for nested objects)
        def deep_merge(base, updates):
            result = base.copy()
            for key, value in updates.items():
                if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                    result[key] = deep_merge(result[key], value)
                else:
                    result[key] = value
            return result

        merged_config = deep_merge(current_config, new_config)

        # Update config
        self._ledfx.config["visualiser"] = merged_config

        # Save config to disk
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        _LOGGER.info(f"Updated visualiser config: {merged_config}")

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": "Visualiser config updated",
            },
            "config": merged_config,
        }
        return web.json_response(data=response, status=200)

    async def delete(self) -> web.Response:
        """
        Reset visualiser configuration to defaults

        Returns:
            web.Response: The response indicating success
        """
        # Reset to defaults
        self._ledfx.config["visualiser"] = DEFAULT_VISUALISER_CONFIG.copy()

        # Save config to disk
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        _LOGGER.info("Reset visualiser config to defaults")

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": "Visualiser config reset to defaults",
            },
            "config": DEFAULT_VISUALISER_CONFIG,
        }
        return web.json_response(data=response, status=200)


