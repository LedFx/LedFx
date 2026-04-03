"""API endpoint for listing and adding Sendspin server configurations."""

import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.sendspin.config import DEFAULT_CLIENT_NAME
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


def _sendspin_available():
    from ledfx.sendspin import SENDSPIN_AVAILABLE

    return SENDSPIN_AVAILABLE


def _validate_server_url(url: str) -> bool:
    return url.startswith("ws://") or url.startswith("wss://")


class SendspinServersEndpoint(RestEndpoint):
    """REST endpoint for listing and adding Sendspin servers."""

    ENDPOINT_PATH = "/api/sendspin/servers"

    async def get(self, request: web.Request) -> web.Response:
        """Return all configured Sendspin servers."""
        if not _sendspin_available():
            return await self.invalid_request(
                "Sendspin is not available. Requires Python 3.12+ and aiosendspin package."
            )

        servers = self._ledfx.config.get("sendspin_servers", {})
        return await self.bare_request_success({"servers": servers})

    async def post(self, request: web.Request) -> web.Response:
        """Add a new Sendspin server configuration."""
        if not _sendspin_available():
            return await self.invalid_request(
                "Sendspin is not available. Requires Python 3.12+ and aiosendspin package."
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        if "id" not in data:
            return await self.invalid_request(
                "Required key not provided: 'id'"
            )

        if "server_url" not in data:
            return await self.invalid_request(
                "Required key not provided: 'server_url'"
            )

        server_url = data["server_url"]
        if not _validate_server_url(server_url):
            return await self.invalid_request(
                "server_url must start with ws:// or wss://"
            )

        server_id = generate_id(data["id"])
        servers = self._ledfx.config.setdefault("sendspin_servers", {})

        if server_id in servers:
            return await self.invalid_request(
                f"Server '{server_id}' already exists. Use PUT to update."
            )

        entry = {
            "server_url": server_url,
            "client_name": data.get("client_name", DEFAULT_CLIENT_NAME),
        }
        servers[server_id] = entry

        save_config(self._ledfx.config, self._ledfx.config_dir)
        self._ledfx._load_sendspin_servers()

        return await self.request_success(
            type="success",
            message=f"Sendspin server '{server_id}' added.",
        )
