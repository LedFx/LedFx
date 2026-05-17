"""Now Playing REST API endpoint."""

import json
import logging

from aiohttp import web
from voluptuous import Invalid

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class NowPlayingEndpoint(RestEndpoint):
    """REST endpoint for Now Playing state and configuration.

    GET /api/now-playing
        Returns the current Now Playing state including metadata,
        artwork reference, gradient information, and full configuration.

    PUT /api/now-playing
        Updates Now Playing configuration (gradient, track_text, album_art).
        Accepts a partial or full configuration dict; unspecified sections
        retain their current values.
    """

    ENDPOINT_PATH = "/api/now-playing"

    async def get(self) -> web.Response:
        """Get current Now Playing state and configuration."""
        np_service = self._ledfx.now_playing
        state = np_service.get_current()
        response = state.to_dict()
        response["config"] = np_service.config
        return await self.bare_request_success(response)

    async def put(self, request: web.Request) -> web.Response:
        """Update Now Playing configuration."""
        try:
            data = await request.json()
        except json.JSONDecodeError:
            return await self.json_decode_error()

        if not isinstance(data, dict):
            return await self.invalid_request(
                "Request body must be a JSON object."
            )

        np_service = self._ledfx.now_playing

        try:
            validated = np_service.update_config(data)
        except Invalid as exc:
            _LOGGER.warning("Invalid now_playing config: %s", exc)
            return await self.invalid_request(str(exc))

        return await self.request_success(
            "success", "Now Playing configuration updated.", validated
        )
