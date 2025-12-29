"""
Visualiser Presets API Endpoint

Provides REST API for managing visualiser presets.
"""

import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)

# Default visualiser configuration (shared with visualiser.py)
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


class VisualiserPresetsEndpoint(RestEndpoint):
    """REST endpoint for managing visualiser presets"""

    ENDPOINT_PATH = "/api/visualiser/presets"

    async def get(self) -> web.Response:
        """
        Get all visualiser presets

        Returns:
            web.Response: The response containing all presets
        """
        visualiser_config = self._ledfx.config.get("visualiser", DEFAULT_VISUALISER_CONFIG.copy())
        presets = visualiser_config.get("presets", [])

        response = {
            "status": "success",
            "presets": presets,
        }
        return web.json_response(data=response, status=200)

    async def post(self, request: web.Request) -> web.Response:
        """
        Save a new visualiser preset

        Args:
            request (web.Request): The request object containing the preset

        Returns:
            web.Response: The response indicating success or failure
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        preset = data.get("preset")
        if preset is None:
            return await self.invalid_request(
                'Required attribute "preset" was not provided'
            )

        name = preset.get("name")
        if not name:
            return await self.invalid_request(
                'Preset must have a "name" attribute'
            )

        # Get current config
        visualiser_config = self._ledfx.config.get("visualiser", DEFAULT_VISUALISER_CONFIG.copy())
        presets = visualiser_config.get("presets", [])

        # Check if preset with same name exists
        existing_index = next((i for i, p in enumerate(presets) if p.get("name") == name), None)

        if existing_index is not None:
            # Update existing preset
            presets[existing_index] = preset
            _LOGGER.info(f"Updated visualiser preset: {name}")
        else:
            # Add new preset
            presets.append(preset)
            _LOGGER.info(f"Created visualiser preset: {name}")

        visualiser_config["presets"] = presets
        self._ledfx.config["visualiser"] = visualiser_config

        # Save config to disk
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": f"Saved preset: {name}",
            },
            "preset": preset,
        }
        return web.json_response(data=response, status=200)

    async def delete(self, request: web.Request) -> web.Response:
        """
        Delete a visualiser preset

        Args:
            request (web.Request): The request object containing the preset name

        Returns:
            web.Response: The response indicating success or failure
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        name = data.get("name")
        if not name:
            return await self.invalid_request(
                'Required attribute "name" was not provided'
            )

        # Get current config
        visualiser_config = self._ledfx.config.get("visualiser", DEFAULT_VISUALISER_CONFIG.copy())
        presets = visualiser_config.get("presets", [])

        # Find and remove preset
        original_length = len(presets)
        presets = [p for p in presets if p.get("name") != name]

        if len(presets) == original_length:
            return await self.invalid_request(f"Preset '{name}' not found")

        visualiser_config["presets"] = presets
        self._ledfx.config["visualiser"] = visualiser_config

        # Save config to disk
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        _LOGGER.info(f"Deleted visualiser preset: {name}")

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": f"Deleted preset: {name}",
            },
        }
        return web.json_response(data=response, status=200)
