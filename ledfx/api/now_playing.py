import logging

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class NowPlayingEndpoint(RestEndpoint):
    """GET /api/now-playing — current now-playing state."""

    ENDPOINT_PATH = "/api/now-playing"

    async def get(self) -> web.Response:
        if not hasattr(self._ledfx, "now_playing"):
            return await self.bare_request_success(
                {"status": "unavailable", "message": "Now-playing subsystem not initialized"}
            )

        return await self.bare_request_success(
            self._ledfx.now_playing.state.to_dict()
        )
