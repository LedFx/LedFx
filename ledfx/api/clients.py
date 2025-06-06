import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.websocket import WebsocketConnection

_LOGGER = logging.getLogger(__name__)


class ClientEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/clients"

    async def get(self) -> web.Response:
        """
        Get the list of client IPs

        Returns:
            web.Response: The response containing the list of client IPs
        """

        clients = WebsocketConnection.get_all_client_ips()

        return await self.bare_request_success(clients)
    