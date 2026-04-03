"""API endpoint for updating and deleting an individual Sendspin server configuration."""

import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.effects.audio import AudioInputSource

_LOGGER = logging.getLogger(__name__)


def _sendspin_available():
    from ledfx.sendspin import SENDSPIN_AVAILABLE

    return SENDSPIN_AVAILABLE


def _validate_server_url(url: str) -> bool:
    return url.startswith("ws://") or url.startswith("wss://")


def _sync_active_stream(ledfx, server_id: str, *, restart: bool) -> None:
    """Stop (and optionally restart) the audio stream if it is using *server_id*.

    Called after a sendspin server config is updated or deleted so the live
    SendspinAudioStream reflects the new state instead of keeping an obsolete
    connection open.

    Args:
        ledfx: The LedFx core instance.
        server_id: The sendspin server key that was changed/removed.
        restart: If True, re-activate the stream after stopping it (used for
                 PUT when server_url changed); if False just stop it (DELETE).
    """
    audio = getattr(ledfx, "audio", None)
    if audio is None:
        return

    with AudioInputSource._class_lock:
        active_name = AudioInputSource._last_device_name

    if active_name != f"SENDSPIN: {server_id}":
        return

    _LOGGER.info(
        "Sendspin server '%s' changed; stopping active stream.", server_id
    )
    audio.deactivate()

    if restart and AudioInputSource._callbacks:
        _LOGGER.info(
            "Restarting audio stream with updated Sendspin server '%s'.",
            server_id,
        )
        audio.activate()


class SendspinServerEndpoint(RestEndpoint):
    """REST endpoint for updating and deleting an individual Sendspin server."""

    ENDPOINT_PATH = "/api/sendspin/servers/{server_id}"

    async def put(self, server_id: str, request: web.Request) -> web.Response:
        """Update an existing Sendspin server configuration."""
        if not _sendspin_available():
            return await self.invalid_request(
                "Sendspin is not available. Requires Python 3.12+ and aiosendspin package."
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        servers = self._ledfx.config.get("sendspin_servers", {})
        if server_id not in servers:
            return await self.invalid_request(
                f"Server '{server_id}' not found."
            )

        url_changed = False
        if "server_url" in data:
            if not _validate_server_url(data["server_url"]):
                return await self.invalid_request(
                    "server_url must start with ws:// or wss://"
                )
            if servers[server_id].get("server_url") != data["server_url"]:
                url_changed = True
            servers[server_id]["server_url"] = data["server_url"]

        if "client_name" in data:
            servers[server_id]["client_name"] = data["client_name"]

        save_config(self._ledfx.config, self._ledfx.config_dir)
        self._ledfx._load_sendspin_servers()
        _sync_active_stream(self._ledfx, server_id, restart=url_changed)

        return await self.request_success(
            type="success",
            message=f"Sendspin server '{server_id}' updated.",
        )

    async def delete(
        self, server_id: str, request: web.Request
    ) -> web.Response:
        """Remove a Sendspin server configuration."""
        if not _sendspin_available():
            return await self.invalid_request(
                "Sendspin is not available. Requires Python 3.12+ and aiosendspin package."
            )

        servers = self._ledfx.config.get("sendspin_servers", {})
        if server_id not in servers:
            return await self.invalid_request(
                f"Server '{server_id}' not found."
            )

        del servers[server_id]

        save_config(self._ledfx.config, self._ledfx.config_dir)
        self._ledfx._load_sendspin_servers()
        _sync_active_stream(self._ledfx, server_id, restart=False)

        return await self.request_success(
            type="success",
            message=f"Sendspin server '{server_id}' removed.",
        )
