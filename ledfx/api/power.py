import logging
from json import JSONDecodeError
from typing import ClassVar

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)

# Longest delay, in seconds, a shutdown or restart may be scheduled for.
MAX_POWER_TIMEOUT = 3600


class InfoEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/power"

    exit_codes: ClassVar[dict[str, int]] = {"shutdown": 3, "restart": 4}

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

        if action not in self.exit_codes:
            return await self.invalid_request(
                f"Action {action} not in {list(self.exit_codes.keys())}"
            )

        # bool is an int subclass, so rule it out first.
        if (
            isinstance(timeout, bool)
            or not isinstance(timeout, int)
            or not 0 <= timeout <= MAX_POWER_TIMEOUT
        ):
            return await self.invalid_request(
                f"Timeout must be a whole number of seconds from 0 to {MAX_POWER_TIMEOUT}"
            )

        self._ledfx.loop.call_later(timeout, self._ledfx.stop, self.exit_codes[action])
        return await self.request_success()
