"""API handlers for playlists implemented as RestEndpoint classes."""

import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.playlists import PlaylistManager

_LOGGER = logging.getLogger(__name__)


class PlaylistEndpoint(RestEndpoint):
    """REST endpoint for single playlist retrieval."""

    ENDPOINT_PATH = "/api/playlists/{id}"

    async def get(self, id) -> web.Response:
        if not hasattr(self._ledfx, "playlists"):
            self._ledfx.playlists = PlaylistManager(self._ledfx)
        p = self._ledfx.playlists.get_playlist(id)
        if not p:
            return await self.invalid_request("Playlist not found")

        return await self.request_success(data={"playlist": p})
