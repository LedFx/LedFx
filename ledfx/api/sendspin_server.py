"""API endpoint for updating and deleting an individual Sendspin server configuration."""

import logging
from json import JSONDecodeError
from typing import Protocol

from aiohttp import web
from pydantic import ValidationError

from ledfx.api import RestEndpoint
from ledfx.configuration.models import SendspinServerConfig
from ledfx.effects.audio import AudioInputSource
from ledfx.sendspin.config import validate_sendspin_server_url

_LOGGER = logging.getLogger(__name__)


class _AudioController(Protocol):
    """Audio source operations used to restart an active Sendspin stream."""

    def activate(self) -> None: ...

    def deactivate(self) -> None: ...


class _LedFxWithAudio(Protocol):
    """LedFx state needed to synchronize a configured Sendspin server."""

    @property
    def audio(self) -> _AudioController | None: ...


def _sendspin_available():
    from ledfx.sendspin import SENDSPIN_AVAILABLE

    return SENDSPIN_AVAILABLE


def _sync_active_stream(
    ledfx: _LedFxWithAudio, server_id: str, *, restart: bool
) -> None:
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
    audio = ledfx.audio
    if audio is None:
        return

    with AudioInputSource._class_lock:
        active_name = AudioInputSource._last_device_name

    if active_name != f"SENDSPIN: {server_id}":
        return

    _LOGGER.info("Sendspin server '%s' changed; stopping active stream.", server_id)
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

        servers = self._ledfx.config.sendspin_servers
        if server_id not in servers:
            return await self.invalid_request(f"Server '{server_id}' not found.")

        update = {}
        if "server_url" in data:
            server_url = data["server_url"]
            if isinstance(server_url, str):
                server_url = server_url.strip()
            valid, reason = validate_sendspin_server_url(server_url)
            if not valid:
                _LOGGER.warning(
                    "PUT /api/sendspin/servers/%s: invalid server_url %r — %s",
                    server_id,
                    server_url,
                    reason,
                )
                return await self.invalid_request(reason)
            update["server_url"] = server_url

        if "client_name" in data:
            update["client_name"] = data["client_name"]

        old = servers[server_id]
        try:
            new = SendspinServerConfig.model_validate({**old.model_dump(), **update})
        except ValidationError as err:
            return await self.validation_error(err)
        servers[server_id] = new
        url_changed = new.server_url != old.server_url

        self._ledfx.config_store.request_save()
        self._ledfx._load_sendspin_servers()
        _sync_active_stream(self._ledfx, server_id, restart=url_changed)

        return await self.request_success(
            type="success",
            message=f"Sendspin server '{server_id}' updated.",
        )

    async def delete(self, server_id: str, request: web.Request) -> web.Response:
        """Remove a Sendspin server configuration."""
        if not _sendspin_available():
            return await self.invalid_request(
                "Sendspin is not available. Requires Python 3.12+ and aiosendspin package."
            )

        servers = self._ledfx.config.sendspin_servers
        if server_id not in servers:
            return await self.invalid_request(f"Server '{server_id}' not found.")

        del servers[server_id]

        self._ledfx.config_store.request_save()
        self._ledfx._load_sendspin_servers()
        _sync_active_stream(self._ledfx, server_id, restart=False)

        return await self.request_success(
            type="success",
            message=f"Sendspin server '{server_id}' removed.",
        )
