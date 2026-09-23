"""API endpoint for updating and deleting an individual Snapcast server configuration."""

import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.effects.audio import AudioInputSource
from ledfx.snapcast.config import build_server_config

_LOGGER = logging.getLogger(__name__)


def _sync_active_stream(ledfx, server_id: str, *, restart: bool) -> None:
    """Stop (and optionally restart) the audio stream if it is using *server_id*.

    The client identifies itself to the snapserver when it connects, so any
    change to the server config needs a fresh connection to take effect.
    """
    audio = getattr(ledfx, "audio", None)
    if audio is None:
        return

    with AudioInputSource._class_lock:
        active_name = AudioInputSource._last_device_name

    if active_name != f"SNAPCAST: {server_id}":
        return

    _LOGGER.info(
        "Snapcast server '%s' changed; stopping active stream.", server_id
    )
    audio.deactivate()

    if restart and (
        AudioInputSource._callbacks or audio._should_always_keep_active()
    ):
        audio.activate()


class SnapcastServerEndpoint(RestEndpoint):
    """REST endpoint for updating and deleting an individual Snapcast server."""

    ENDPOINT_PATH = "/api/snapcast/servers/{server_id}"

    async def put(self, server_id: str, request: web.Request) -> web.Response:
        """Update an existing Snapcast server configuration."""
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        servers = self._ledfx.config.get("snapcast_servers", {})
        if server_id not in servers:
            return await self.invalid_request(
                f"Server '{server_id}' not found."
            )

        entry, reason = build_server_config(data, servers[server_id])
        if entry is None:
            _LOGGER.warning(
                "PUT /api/snapcast/servers/%s: %s", server_id, reason
            )
            return await self.invalid_request(reason)

        changed = entry != servers[server_id]
        servers[server_id] = entry
        save_config(self._ledfx.config, self._ledfx.config_dir)
        self._ledfx._load_snapcast_servers()
        if changed:
            _sync_active_stream(self._ledfx, server_id, restart=True)

        return await self.request_success(
            type="success",
            message=f"Snapcast server '{server_id}' updated.",
        )

    async def delete(
        self, server_id: str, request: web.Request
    ) -> web.Response:
        """Remove a Snapcast server configuration."""
        servers = self._ledfx.config.get("snapcast_servers", {})
        if server_id not in servers:
            return await self.invalid_request(
                f"Server '{server_id}' not found."
            )

        del servers[server_id]
        save_config(self._ledfx.config, self._ledfx.config_dir)
        self._ledfx._load_snapcast_servers()
        _sync_active_stream(self._ledfx, server_id, restart=False)

        return await self.request_success(
            type="success",
            message=f"Snapcast server '{server_id}' removed.",
        )
