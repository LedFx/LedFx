import asyncio
import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/power"

    exit_codes = {"shutdown": 3, "restart": 4}

    async def post(self, request: web.Request) -> web.Response:
        """
        Handle POST requests to control LedFx shutdown/restart actions.

        Args:
            request (web.Request): The incoming request object optionally containing `action` and `timeout`.

        Returns:
            web.Response: The response object.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        action = data.get("action")
        timeout = data.get("timeout")

        if action is None:
            action = "shutdown"
        if timeout is None:
            timeout = 0

        if action not in self.exit_codes.keys():
            return await self.invalid_request(
                f"Action {action} not in {list(self.exit_codes.keys())}"
            )

        if timeout < 0 or not isinstance(timeout, int):
            return await self.invalid_request(
                "Timeout must be a positive integer"
            )

        # This is an ugly hack.
        # We probably should have a better way of doing this but o well.
        try:
            return await self.request_success()
        finally:
            await asyncio.sleep(timeout)
            self._ledfx.stop(self.exit_codes[action])
