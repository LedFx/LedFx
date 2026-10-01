import asyncio
import ipaddress
import json
import logging
import re
import urllib.error
import urllib.request
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utilities.security_utils import safe_urlopen, validate_url_safety

_LOGGER = logging.getLogger(__name__)

# One DNS label; underscores are tolerated because some LAN names use them.
_LABEL = re.compile(r"^[A-Za-z0-9_]([A-Za-z0-9_-]{0,61}[A-Za-z0-9_])?$")


def is_valid_host(host: object) -> bool:
    """True for a bare IP literal or hostname: no scheme, userinfo, port or path."""
    if not isinstance(host, str) or not host:
        return False
    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass
    name = host.removesuffix(".")
    return len(name) <= 253 and all(_LABEL.match(label) for label in name.split("."))


def _parse_port(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int | str):
        return None
    try:
        port = int(value)
    except ValueError:
        return None
    return port if 1 <= port <= 65535 else None


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

        `ip_address` must be a bare IP or hostname and `port` an integer in
        1-65535. LAN addresses are allowed; loopback, link-local and other
        addresses the SSRF guard always blocks are refused.

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
        if ip is None:
            return await self.invalid_request(
                'Required attribute "ip_address" was not provided'
            )
        if data.get("port") is None:
            return await self.invalid_request(
                'Required attribute "port" was not provided'
            )
        if not is_valid_host(ip):
            return await self.invalid_request(
                '"ip_address" must be an IP address or hostname'
            )
        port = _parse_port(data["port"])
        if port is None:
            return await self.invalid_request(
                '"port" must be an integer between 1 and 65535'
            )

        host = f"[{ip}]" if ":" in ip else ip
        url = f"http://{host}:{port}/api/v1/new"
        loop = asyncio.get_running_loop()
        executor = self._ledfx.thread_executor
        # Resolving a .local name can take seconds; keep it off the event loop.
        safe, reason = await loop.run_in_executor(
            executor, validate_url_safety, url, True
        )
        if not safe:
            return await self.invalid_request(f"Refusing Nanoleaf address: {reason}")

        _LOGGER.info("Getting Nanoleaf token from %s:%s", ip, port)

        def fetch() -> bytes:
            req = urllib.request.Request(url, data=b"", method="POST")
            with safe_urlopen(req, timeout=3, allow_private=True) as response:
                return response.read()

        pairing_hint = "Nanoleaf did not return a token: is it in pairing mode?"
        try:
            body = await loop.run_in_executor(executor, fetch)
            if not body:
                _LOGGER.warning(pairing_hint)
                return await self.internal_error(pairing_hint, "error")
            token = json.loads(body)
        except urllib.error.HTTPError:
            # Nanoleaf answers 403 when it is not in pairing mode.
            _LOGGER.warning(pairing_hint)
            return await self.internal_error(pairing_hint, "error")
        except (OSError, ValueError) as msg:
            error_message = f"Error getting Nanoleaf token from {ip}:{port}: {msg}"
            _LOGGER.warning(error_message)
            return await self.internal_error(error_message, "error")
        return await self.bare_request_success(token)
