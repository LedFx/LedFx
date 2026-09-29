"""
Host and Origin checks for browser requests to the HTTP server, and the CORS
headers that go with them.

Every request must address LedFx by a name it knows: an IP address, a local
name, the machine's own host name, the configured bind host, or an entry in
the ``allowed_hosts`` core config key. Any other name gets a 403. This covers
clients without browser headers too: over plain HTTP to a LAN address,
browsers send no Sec-Fetch-* headers and no Origin on same-origin GETs, so a
page served from a name that resolves to LedFx cannot be told apart from a
script.

Requests that carry an Origin are accepted when the origin is the server
itself, a host on the local network, one of the hosted LedFx frontends, or
listed in the ``allowed_origins`` core config key. State-changing requests
(unsafe methods, WebSocket upgrades, and the GET routes in
``STATE_CHANGING_GETS``) from any other origin get a 403. Other GETs are still
served, but without CORS headers, so the calling page cannot read them.
"""

import ipaddress
import logging
import socket
from urllib.parse import urlsplit

from aiohttp import hdrs, web

_LOGGER = logging.getLogger(__name__)

HOSTED_ORIGINS = frozenset({"https://ledfx.stream", "https://yeonv.github.io"})

# The Electron desktop client loads its UI from file:// and sends this Origin
# on WebSocket handshakes (its fetch/XHR requests carry no Origin at all).
# Browsers serialize file pages as "null", so web content cannot send it.
ELECTRON_FILE_ORIGIN = "file://"

LOCAL_NETWORKS = tuple(
    ipaddress.ip_network(net)
    for net in (
        "127.0.0.0/8",
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
        "100.64.0.0/10",
        "169.254.0.0/16",
        "::1/128",
        "fc00::/7",
        "fe80::/10",
    )
)
# Names that public DNS does not serve to others: special-use and private-use
# names, common router domains (.lan, .home, .localdomain) and the FRITZ!Box
# domain (fritz.box belongs to AVM). A dotless name is a LAN host name.
LOCAL_SUFFIXES = (
    ".local",
    ".localhost",
    ".home.arpa",
    ".internal",
    ".lan",
    ".home",
    ".localdomain",
    ".fritz.box",
)

UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})

# GET routes that change state or reach out to other hosts. The origin check
# treats them like POST. Keep this list in line with the API.
STATE_CHANGING_GETS = frozenset(
    {
        "/api/find_devices",  # starts WLED discovery, adds the devices found
        "/api/find_lifx",  # scans the network; add=true adds the devices found
        "/api/virtuals/{virtual_id}/fallback",  # fires the fallback effect
        "/api/sendspin/discover",  # mDNS scan of up to 30 s
        "/api/find_openrgb",  # connects to the local OpenRGB server
        "/api/ping/{device_id}",  # sends pings to a device
    }
)
CORS_METHODS = "GET, PUT, POST, DELETE"

_reported_origins: set[str] = set()


def _split_origin(origin: str) -> tuple[str, int | None] | None:
    """Return (host, port) for a serialized http(s) origin, else None."""
    try:
        parts = urlsplit(origin)
        port = parts.port
    except ValueError:
        return None
    host = (parts.hostname or "").rstrip(".")
    if (
        parts.scheme not in ("http", "https")
        or not host
        or parts.path
        or parts.query
        or parts.fragment
        or "@" in parts.netloc
    ):
        return None
    return host, port


def _is_local_name(host: str) -> bool:
    return "." not in host or host.endswith(LOCAL_SUFFIXES)


def _host_name(value: str) -> str | None:
    """Host name (lowercase, no port or trailing dot) of a Host value or URL."""
    value = value.strip().lower().rstrip("/")
    split = _split_origin(value if "://" in value else f"http://{value}")
    return split[0] if split else None


def _is_local_host(host: str) -> bool:
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return _is_local_name(host)
    if ip.version == 6 and ip.ipv4_mapped:
        ip = ip.ipv4_mapped
    return any(ip in net for net in LOCAL_NETWORKS)


def is_origin_allowed(
    origin: str, host: str, allowed_origins=(), allow_null: bool = False
) -> bool:
    """
    Decide whether a request carrying ``origin`` may use the API.

    ``host`` is the request's Host header. The origin counts as the server's
    own when host and port match it; the scheme is not compared, so a proxy
    that terminates TLS in front of LedFx still matches.
    """
    origin = origin.strip().lower()
    extras = {entry.strip().rstrip("/").lower() for entry in allowed_origins}
    if "*" in extras or origin in extras:
        return True
    if origin == "null":
        return allow_null
    if origin == ELECTRON_FILE_ORIGIN or origin in HOSTED_ORIGINS:
        return True
    split = _split_origin(origin)
    if split is None:
        return False
    if _is_local_host(split[0]):
        return True
    own = _split_origin(f"http://{host.lower()}")
    return own is not None and own == split


def is_host_allowed(host: str, allowed_hosts=(), own_names=frozenset()) -> bool:
    """
    Decide whether a client may address LedFx by ``host`` (the Host header).

    Any IP address and any local name is accepted; other names only when they
    are in ``own_names`` (this machine, the bind host) or ``allowed_hosts``.
    """
    if any(entry.strip() == "*" for entry in allowed_hosts):
        return True
    name = _host_name(host)
    if name is None:
        return False
    try:
        ipaddress.ip_address(name)
        return True
    except ValueError:
        pass
    return (
        _is_local_name(name)
        or name in own_names
        or name in {_host_name(entry) for entry in allowed_hosts}
    )


def _machine_names() -> frozenset[str]:
    names = set()
    for lookup in (socket.gethostname, socket.getfqdn):
        try:
            names.add(_host_name(lookup()))
        except OSError:
            pass
    names.discard(None)
    return frozenset(names)


def _forbidden(reason: str) -> web.Response:
    return web.json_response(
        {"status": "failed", "payload": {"type": "error", "reason": reason}},
        status=403,
    )


def _add_cors_headers(headers, origin: str) -> None:
    headers[hdrs.ACCESS_CONTROL_ALLOW_ORIGIN] = origin
    headers.add(hdrs.VARY, hdrs.ORIGIN)


def _report(key: str, message: str, origin: str) -> None:
    # One log line per origin; bounded because the value comes from the client.
    if key not in _reported_origins and len(_reported_origins) < 100:
        _reported_origins.add(key)
        _LOGGER.warning(message, origin)


def origin_middleware(ledfx):
    """Build the middleware; it reads the LedFx config on every request."""
    machine_names = _machine_names()

    @web.middleware
    async def middleware(request: web.Request, handler):
        headers = request.headers
        origin = headers.get(hdrs.ORIGIN)
        fetch_site = headers.get("Sec-Fetch-Site")
        config = ledfx.config

        # Checked for every request: over plain HTTP a browser sends neither
        # Origin nor Sec-Fetch-Site on a same-origin GET.
        own_names = machine_names | {_host_name(config.host or "")}
        if not is_host_allowed(request.host, config.allowed_hosts, own_names):
            name = _host_name(request.host) or request.host
            _report(
                f"host {name}",
                "Rejected request for host %s. Add it to "
                "allowed_hosts in the LedFx config to allow it.",
                name,
            )
            return _forbidden(
                f"Host not allowed: {name}. "
                "Add it to allowed_hosts in the LedFx config."
            )

        route = getattr(request.match_info.route.resource, "canonical", None)
        state_changing_get = (
            request.method in (hdrs.METH_GET, hdrs.METH_HEAD)
            and route in STATE_CHANGING_GETS
        )

        if origin is None:
            # <img>, links and forms on another site send no Origin on GET.
            # A cors-mode fetch without Origin is the Electron desktop client.
            if (
                state_changing_get
                and fetch_site in ("cross-site", "same-site")
                and headers.get("Sec-Fetch-Mode") != "cors"
            ):
                return _forbidden(f"Cross-site request not allowed: {request.path}")
            return await handler(request)

        allow_null = config.allow_null_origin
        allowed = is_origin_allowed(
            origin, request.host, config.allowed_origins, allow_null
        )
        preflight = (
            request.method == hdrs.METH_OPTIONS
            and hdrs.ACCESS_CONTROL_REQUEST_METHOD in headers
        )

        if not allowed:
            upgrade = headers.get(hdrs.UPGRADE, "").lower() == "websocket"
            if not (
                preflight
                or upgrade
                or state_changing_get
                or request.method in UNSAFE_METHODS
            ):
                return await handler(request)
            _report(
                f"origin {origin}",
                "Rejected request from origin %s. Add it to allowed_origins "
                "in the LedFx config to allow it.",
                origin,
            )
            return _forbidden(
                f"Origin not allowed: {origin}. "
                "Add it to allowed_origins in the LedFx config."
            )

        if allow_null and origin.strip().lower() == "null":
            _report(
                "accepted null",
                "Accepted a request with Origin %s because allow_null_origin is "
                "on. Sandboxed frames on any website send this origin; turn the "
                "setting off once no client needs it.",
                origin,
            )

        if preflight:
            response = web.Response()
            _add_cors_headers(response.headers, origin)
            response.headers[hdrs.ACCESS_CONTROL_ALLOW_METHODS] = CORS_METHODS
            requested = headers.get(hdrs.ACCESS_CONTROL_REQUEST_HEADERS)
            if requested:
                response.headers[hdrs.ACCESS_CONTROL_ALLOW_HEADERS] = requested
            return response

        try:
            response = await handler(request)
        except web.HTTPException as exc:
            _add_cors_headers(exc.headers, origin)
            raise
        if not response.prepared:
            _add_cors_headers(response.headers, origin)
        return response

    return middleware
