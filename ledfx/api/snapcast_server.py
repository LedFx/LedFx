"""API endpoint for updating and deleting an individual Snapcast server configuration."""

import logging
from json import JSONDecodeError
from typing import Protocol

from aiohttp import web
from pydantic import ValidationError

from ledfx.api import RestEndpoint
from ledfx.configuration.models import SnapcastServerConfig
from ledfx.effects.audio import AudioInputSource
from ledfx.snapcast.config import build_server_config

_LOGGER = logging.getLogger(__name__)


class _AudioController(Protocol):
    """Audio source operations used to restart an active Snapcast stream."""

    def activate(self) -> None: ...

    def deactivate(self) -> None: ...

    def _should_always_keep_active(self) -> bool: ...


class _LedFxWithAudio(Protocol):
    """LedFx state needed to synchronize a configured Snapcast server."""

    @property
    def audio(self) -> _AudioController | None: ...


def _sync_active_stream(
    ledfx: _LedFxWithAudio, server_id: str, *, restart: bool
) -> None:
    """Stop (and optionally restart) the audio stream if it is using *server_id*.

    The client identifies itself to the snapserver when it connects, so any
    change to the server config needs a fresh connection to take effect.
    """
    audio = ledfx.audio
    if audio is None:
        return

    with AudioInputSource._class_lock:
        active_name = AudioInputSource._last_device_name

    if active_name != f"SNAPCAST: {server_id}":
        return

    _LOGGER.info("Snapcast server '%s' changed; stopping active stream.", server_id)
    audio.deactivate()

    if restart and (AudioInputSource._callbacks or audio._should_always_keep_active()):
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

        servers = self._ledfx.config.snapcast_servers
        if server_id not in servers:
            return await self.invalid_request(f"Server '{server_id}' not found.")

        old = servers[server_id]
        entry, reason = build_server_config(data, old.model_dump())
        if entry is None:
            _LOGGER.warning("PUT /api/snapcast/servers/%s: %s", server_id, reason)
            return await self.invalid_request(reason)

        try:
            new = SnapcastServerConfig.model_validate(entry)
        except ValidationError as err:
            return await self.validation_error(err)
        changed = new != old
        servers[server_id] = new
        self._ledfx.config_store.request_save()
        self._ledfx._load_snapcast_servers()
        if changed:
            _sync_active_stream(self._ledfx, server_id, restart=True)

        return await self.request_success(
            type="success",
            message=f"Snapcast server '{server_id}' updated.",
        )

    async def delete(self, server_id: str, request: web.Request) -> web.Response:
        """Remove a Snapcast server configuration."""
        servers = self._ledfx.config.snapcast_servers
        if server_id not in servers:
            return await self.invalid_request(f"Server '{server_id}' not found.")

        del servers[server_id]
        self._ledfx.config_store.request_save()
        self._ledfx._load_snapcast_servers()
        _sync_active_stream(self._ledfx, server_id, restart=False)

        return await self.request_success(
            type="success",
            message=f"Snapcast server '{server_id}' removed.",
        )
