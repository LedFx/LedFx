"""API endpoint for updating and deleting an individual Sendspin server configuration."""

import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


def _sendspin_available():
    from ledfx.sendspin import SENDSPIN_AVAILABLE

    return SENDSPIN_AVAILABLE


def _validate_server_url(url: str) -> bool:
    return url.startswith("ws://") or url.startswith("wss://")


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
            return await self.invalid_request(f"Server '{server_id}' not found.")

        if "server_url" in data:
            if not _validate_server_url(data["server_url"]):
                return await self.invalid_request(
                    "server_url must start with ws:// or wss://"
                )
            servers[server_id]["server_url"] = data["server_url"]

        if "client_name" in data:
            servers[server_id]["client_name"] = data["client_name"]

        save_config(self._ledfx.config, self._ledfx.config_dir)
        self._ledfx._load_sendspin_servers()

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

        servers = self._ledfx.config.get("sendspin_servers", {})
        if server_id not in servers:
            return await self.invalid_request(f"Server '{server_id}' not found.")

        del servers[server_id]

        save_config(self._ledfx.config, self._ledfx.config_dir)
        self._ledfx._load_sendspin_servers()

        return await self.request_success(
            type="success",
            message=f"Sendspin server '{server_id}' removed.",
        )
