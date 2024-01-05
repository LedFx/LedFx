import logging
from json import JSONDecodeError

import requests
from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class GetNanoleadTokenEndpoint(RestEndpoint):
    """
    REST end-point for requesting auth token from Nanoleaf
    Ensure that the Nanoleaf controller is in pairing mode
    Long press the power button on the controller for 5-7 seconds
    White LEDs will scan back and forth to indicate pairing mode
    """

    ENDPOINT_PATH = "/api/get_nanoleaf_token"

    async def post(self, request: web.Request) -> web.Response:
        """
        Handle POST request to retrieve Nanoleaf token.

        Args:
            request (web.Request): The incoming request object containing `ip_address` and `port`.

        Returns:
            web.Response: The response object.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        ip = data.get("ip_address")
        port = data.get("port")

        if ip is None:
            return await self.invalid_request(
                'Required attribute "ip_address" was not provided'
            )
        if port is None:
            return await self.invalid_request(
                'Required attribute "port" was not provided'
            )

        _LOGGER.info(f"Getting Nanoleaf token from {ip}:{port}")

        try:
            response = requests.post(
                f"http://{ip}:{port}/api/v1/new", timeout=(3, 3)
            )
            # TODO: See if we can just check the response is None - no nanoleaf to test with
            if response.text == "":
                error_message = (
                    "Nanoleaf did not return a token: is it in pairing mode?"
                )
                _LOGGER.warning(error_message)
                return await self.internal_error("error", error_message)
            data = response.json()
        except requests.exceptions.RequestException as msg:
            error_message = (
                f"Error getting Nanoleaf token from {ip}:{port}: {msg}"
            )
            _LOGGER.warning(error_message)
            return await self.internal_error("error", error_message)
        return await self.bare_request_success(data)
