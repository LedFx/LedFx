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
        if not action:
            return await self.invalid_request("action required")

        try:
            await self._ensure_manager()

            # Playlist Selection Actions (require id)
            if action == "start":
                pid = data.get("id")
                if not pid:
                    return await self.invalid_request(
                        "id required for start action"
                    )
                ok = await self._ledfx.playlists.start(pid)
                if not ok:
                    return await self.invalid_request(
                        f"Playlist {pid} not found or empty"
                    )
                return await self.request_success(
                    type="success", message=f"Playlist '{pid}' started"
                )

            # Active Playlist Controls (no id required, operate on active playlist)
            elif action == "stop":
                await self._ledfx.playlists.stop()
                return await self.request_success(
                    type="success", message="Active playlist stopped"
                )
            elif action == "pause":
                ok = await self._ledfx.playlists.pause()
                return (
                    await self.request_success(
                        type="success", message="Active playlist paused"
                    )
                    if ok
                    else await self.invalid_request(
                        "No active playlist to pause"
                    )
                )
            elif action == "resume":
                ok = await self._ledfx.playlists.resume()
                return (
                    await self.request_success(
                        type="success", message="Active playlist resumed"
                    )
                    if ok
                    else await self.invalid_request(
                        "No active playlist to resume"
                    )
                )
            elif action == "next":
                ok = await self._ledfx.playlists.next()
                return (
                    await self.request_success(
                        type="success",
                        message="Advanced to next scene in playlist",
                    )
                    if ok
                    else await self.invalid_request(
                        "No active playlist for next"
                    )
                )
            elif action == "prev":
                ok = await self._ledfx.playlists.prev()
                return (
                    await self.request_success(
                        type="success",
                        message="Moved to previous scene in playlist",
                    )
                    if ok
                    else await self.invalid_request(
                        "No active playlist for prev"
                    )
                )
            elif action == "state":
                state = await self._ledfx.playlists.get_state()
                return await self.request_success(data={"state": state})
            else:
                return await self.invalid_request(f"Unknown action: {action}")

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
                type="success", message=f"Playlist '{pid}' deleted."
            )
        return await self.invalid_request("Playlist not found")
