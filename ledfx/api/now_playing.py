"""Now Playing REST API endpoint."""

import logging

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class NowPlayingEndpoint(RestEndpoint):
    """REST endpoint for querying current Now Playing state.

    GET /api/now-playing
        Returns the current Now Playing state including metadata,
        artwork reference, and gradient information.
    """

    ENDPOINT_PATH = "/api/now-playing"

    async def get(self) -> web.Response:
        """Get current Now Playing state."""
        state = self._ledfx.now_playing.get_current()
        return await self.bare_request_success(state.to_dict())
