"""API handlers for playlists implemented as RestEndpoint classes."""

import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.playlists import PlaylistManager

_LOGGER = logging.getLogger(__name__)


class ActivePlaylistEndpoint(RestEndpoint):
    """REST endpoint for reporting runtime state of playlists."""

    ENDPOINT_PATH = "/api/playlists/active"

    async def get(self) -> web.Response:
        if not hasattr(self._ledfx, "playlists"):
            self._ledfx.playlists = PlaylistManager(self._ledfx)
        # If there is no active playlist, return state: null to match docs
        if not self._ledfx.playlists._active_playlist_id:
            return await self.request_success(data={"state": None})
        state = await self._ledfx.playlists.get_state()
        return await self.request_success(data={"state": state})
