"""API endpoint for discovering Sendspin servers on the local network via mDNS."""

import asyncio
import logging

from aiohttp import web
from zeroconf.asyncio import (
    AsyncServiceBrowser,
    AsyncServiceInfo,
    AsyncZeroconf,
)

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)

# mDNS service type broadcast by Sendspin servers (client-initiated connection path).
# Note: _sendspin._tcp.local. is what CLIENTS advertise for server-initiated connections.
# Servers advertise _sendspin-server._tcp.local. so that clients can discover them.
_SENDSPIN_SERVICE_TYPE = "_sendspin-server._tcp.local."
_DEFAULT_TIMEOUT = 3.0
_MAX_TIMEOUT = 30.0
_MIN_TIMEOUT = 0.1


def _sendspin_available():
    from ledfx.sendspin import SENDSPIN_AVAILABLE

    return SENDSPIN_AVAILABLE


class SendspinDiscoverEndpoint(RestEndpoint):
    """REST endpoint for discovering Sendspin servers on the local network."""

    ENDPOINT_PATH = "/api/sendspin/discover"

    async def get(self, request: web.Request) -> web.Response:
        """
        Scan the local network for Sendspin servers via mDNS.

        Query Parameters:
            timeout (float): Scan duration in seconds. Default 3.0, max 30.0.
        """
        if not _sendspin_available():
            return await self.invalid_request(
                "Sendspin is not available. Requires Python 3.12+ and aiosendspin package."
            )

        try:
            timeout = float(
                request.rel_url.query.get("timeout", _DEFAULT_TIMEOUT)
            )
        except (ValueError, TypeError):
            return await self.invalid_request("timeout must be a number")

        if not (_MIN_TIMEOUT <= timeout <= _MAX_TIMEOUT):
            return await self.invalid_request(
                f"timeout must be between {_MIN_TIMEOUT} and {_MAX_TIMEOUT} seconds"
            )

        discovered = await self._discover(timeout)

        # Annotate with already_configured flag
        configured_urls = {
            cfg.get("server_url")
            for cfg in self._ledfx.config.get("sendspin_servers", {}).values()
        }
        for entry in discovered:
            entry["already_configured"] = (
                entry["server_url"] in configured_urls
            )

        count = len(discovered)
        if count:
            reason = f"Discovery complete. {count} server(s) found."
        else:
            reason = "Discovery complete. No Sendspin servers found on the local network."

        return await self.request_success(
            type="info",
            message=reason,
            data={"servers": discovered},
        )

    async def _discover(self, timeout: float) -> list:
        """Browse mDNS for Sendspin servers and return a list of found entries."""
        import ipaddress

        from zeroconf import ServiceStateChange

        found: list[dict] = []
        found_names: set[str] = set()
        lock = asyncio.Lock()
        pending_tasks: list[asyncio.Task] = []

        aiozc = AsyncZeroconf()
        try:

            async def _handle_service(
                zeroconf, service_type, name, state_change
            ):
                if state_change is not ServiceStateChange.Added:
                    return
                info = AsyncServiceInfo(service_type, name)
                result = await info.async_request(zeroconf, 3000)
                if not result:
                    _LOGGER.debug("mDNS info request timed out for %s", name)
                    return

                addresses = info.parsed_addresses()
                host = None
                for addr in addresses:
                    try:
                        ip = ipaddress.ip_address(addr)
                        if not ip.is_link_local and not ip.is_unspecified:
                            host = addr
                            break
                    except ValueError:
                        continue

                if host is None and addresses:
                    host = addresses[0]

                if host is None:
                    # Fall back to hostname
                    host = (
                        str(info.server).rstrip(".") if info.server else None
                    )

                if host is None:
                    return

                port = info.port or 8927
                # Read WebSocket path from TXT record (spec recommends /sendspin)
                properties = info.decoded_properties or {}
                path = properties.get("path", "/sendspin")
                if not path.startswith("/"):
                    path = "/" + path
                # Bracket IPv6 literals so the URL is valid (e.g. ws://[::1]:8927/…)
                try:
                    if isinstance(
                        ipaddress.ip_address(host), ipaddress.IPv6Address
                    ):
                        url_host = f"[{host}]"
                    else:
                        url_host = host
                except ValueError:
                    url_host = host  # hostname string, no bracketing needed
                server_url = f"ws://{url_host}:{port}{path}"
                service_name = name.replace(f".{service_type}", "").strip(".")

                async with lock:
                    if name not in found_names:
                        found_names.add(name)
                        found.append(
                            {
                                "name": service_name,
                                "server_url": server_url,
                                "host": host,
                                "port": port,
                            }
                        )

            def on_service_state_change(
                zeroconf, service_type, name, state_change
            ):
                task = asyncio.ensure_future(
                    _handle_service(zeroconf, service_type, name, state_change)
                )
                pending_tasks.append(task)

            browser = AsyncServiceBrowser(
                aiozc.zeroconf,
                _SENDSPIN_SERVICE_TYPE,
                handlers=[on_service_state_change],
            )
            try:
                await asyncio.sleep(timeout)
            finally:
                await browser.async_cancel()
                # Wait for any in-flight service info requests before closing zeroconf.
                # Without this, async_close() kills the socket while async_request()
                # is still waiting for a response, causing discovered servers to be lost.
                if pending_tasks:
                    _remaining = min(3.0, timeout)
                    _, still_pending = await asyncio.wait(
                        pending_tasks, timeout=_remaining
                    )
                    for t in still_pending:
                        t.cancel()

        finally:
            await aiozc.async_close()

        return found
