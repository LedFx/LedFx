"""API endpoint for listing and adding Snapcast server configurations."""

import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.snapcast.config import build_server_config
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class SnapcastServersEndpoint(RestEndpoint):
    """REST endpoint for listing and adding Snapcast servers."""

    ENDPOINT_PATH = "/api/snapcast/servers"

    async def get(self, request: web.Request) -> web.Response:
        """Return all configured Snapcast servers."""
        servers = self._ledfx.config.get("snapcast_servers", {})
        return await self.bare_request_success({"servers": servers})

    async def post(self, request: web.Request) -> web.Response:
        """Add a new Snapcast server configuration."""
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        if "id" not in data:
            return await self.invalid_request(
                "Required key not provided: 'id'"
            )

        entry, reason = build_server_config(data)
        if entry is None:
            _LOGGER.warning("POST /api/snapcast/servers: %s", reason)
            return await self.invalid_request(reason)

        server_id = generate_id(data["id"])
        servers = self._ledfx.config.setdefault("snapcast_servers", {})
        if server_id in servers:
            return await self.invalid_request(
                f"Server '{server_id}' already exists. Use PUT to update."
            )

        servers[server_id] = entry
        save_config(self._ledfx.config, self._ledfx.config_dir)
        self._ledfx._load_snapcast_servers()

        return await self.request_success(
            type="success",
            message=f"Snapcast server '{server_id}' added.",
        )
