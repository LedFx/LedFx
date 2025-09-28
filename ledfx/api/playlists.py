"""API handlers for playlists implemented as RestEndpoint classes."""

import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.playlists import PlaylistManager

_LOGGER = logging.getLogger(__name__)


class PlaylistsEndpoint(RestEndpoint):
    """REST endpoint for playlist collection: list, create, control, delete."""

    ENDPOINT_PATH = "/api/playlists"

    async def _ensure_manager(self):
        if not hasattr(self._ledfx, "playlists"):
            self._ledfx.playlists = PlaylistManager(self._ledfx)

    async def get(self) -> web.Response:
        await self._ensure_manager()
        return await self.bare_request_success(
            {"playlists": self._ledfx.playlists.list_playlists()}
        )

    async def post(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        try:
            await self._ensure_manager()
            playlist = await self._ledfx.playlists.create_or_replace(data)
            return await self.request_success(data={"playlist": playlist})
        except Exception as e:
            _LOGGER.exception(e)
            return await self.invalid_request(str(e))

    async def put(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        action = data.get("action")
        pid = data.get("id")

        try:
            await self._ensure_manager()
            if action == "start":
                ok = await self._ledfx.playlists.start(pid)
                if not ok:
                    return await self.invalid_request("Playlist not found")
                return await self.request_success()
            if action == "stop":
                await self._ledfx.playlists.stop()
                return await self.request_success()
            if action == "pause":
                ok = await self._ledfx.playlists.pause()
                return (
                    await self.request_success()
                    if ok
                    else await self.invalid_request("Pause failed")
                )
            if action == "resume":
                ok = await self._ledfx.playlists.resume()
                return (
                    await self.request_success()
                    if ok
                    else await self.invalid_request("Resume failed")
                )
            if action == "next":
                ok = await self._ledfx.playlists.next()
                return (
                    await self.request_success()
                    if ok
                    else await self.invalid_request("Next failed")
                )
            if action == "prev":
                ok = await self._ledfx.playlists.prev()
                return (
                    await self.request_success()
                    if ok
                    else await self.invalid_request("Prev failed")
                )
            if action == "state":
                state = await self._ledfx.playlists.get_state()
                return await self.request_success(data={"state": state})

            return await self.invalid_request("Unknown action")
        except Exception as e:
            _LOGGER.exception(e)
            return await self.internal_error(str(e))

    async def delete(self, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        pid = data.get("id")
        if pid is None:
            return await self.invalid_request("id required")

        await self._ensure_manager()
        ok = await self._ledfx.playlists.delete(pid)
        if ok:
            return await self.request_success(
                message=f"Playlist '{pid}' deleted."
            )
        return await self.invalid_request("Playlist not found")


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
