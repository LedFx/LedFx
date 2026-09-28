"""SSRF guard: embedded IPv4 in IPv6, DNS rebinding and redirects."""

import ipaddress
import socket
import threading
import urllib.error
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from unittest.mock import patch

import pytest

from ledfx.utilities import security_utils
from ledfx.utilities.security_utils import (
    is_blocked_ip,
    safe_urlopen,
    validate_url_safety,
)

BYPASS_VECTORS = [
    "::ffff:127.0.0.1",  # IPv4-mapped loopback
    "::ffff:169.254.169.254",  # IPv4-mapped cloud metadata
    "::127.0.0.1",  # IPv4-compatible
    "64:ff9b::a9fe:a9fe",  # NAT64 -> 169.254.169.254
    "64:ff9b::7f00:1",  # NAT64 -> 127.0.0.1
    "64:ff9b::a00:1",  # NAT64 -> 10.0.0.1
    "64:ff9b:1::a9fe:a9fe",  # NAT64 local-use
    "2002:7f00:1::",  # 6to4 -> 127.0.0.1
    "2002:a9fe:a9fe::",  # 6to4 -> 169.254.169.254
    "2001:0000:4136:e378:8000:63bf:7eff:fffe",  # Teredo -> 127.0.0.1 client
    "100.64.0.1",  # CGNAT
]


@pytest.mark.parametrize("address", BYPASS_VECTORS)
def test_transition_addresses_are_blocked(address: str) -> None:
    assert is_blocked_ip(address)
    host = f"[{address}]" if ":" in address else address
    safe, _ = validate_url_safety(f"http://{host}/image.png")
    assert not safe


@pytest.mark.parametrize(
    "address", ["::ffff:169.254.169.254", "64:ff9b::7f00:1", "2002:7f00:1::"]
)
def test_allow_private_still_blocks_embedded_loopback_and_metadata(
    address: str,
) -> None:
    safe, _ = validate_url_safety(f"http://[{address}]/", allow_private=True)
    assert not safe


def test_public_destinations_remain_allowed() -> None:
    assert not is_blocked_ip("64:ff9b::808:808")  # NAT64 to a public IPv4
    assert not is_blocked_ip("2606:4700:4700::1111")
    assert not is_blocked_ip("8.8.8.8")
    safe, _ = validate_url_safety("http://100.64.0.5/a.png", allow_private=True)
    assert safe


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:
        if self.path.startswith("/redirect?to="):
            self.send_response(302)
            self.send_header("Location", self.path.split("?to=", 1)[1])
            self.end_headers()
            return
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"internal" if ":" in self.server.server_address[0] else b"ok")

    def log_message(self, format: str, *args: object) -> None:
        pass


class _IPv6Server(HTTPServer):
    address_family = socket.AF_INET6


def _serve(server: HTTPServer) -> Iterator[int]:
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield server.server_address[1]
    server.shutdown()
    server.server_close()


@pytest.fixture
def public_port() -> Iterator[int]:
    yield from _serve(HTTPServer(("127.0.0.1", 0), _Handler))


@pytest.fixture
def internal_port() -> Iterator[int]:
    try:
        server = _IPv6Server(("::1", 0), _Handler)
    except OSError:
        pytest.skip("IPv6 loopback unavailable")
    yield from _serve(server)


@pytest.fixture(autouse=True)
def treat_ipv6_loopback_as_internal(request: pytest.FixtureRequest) -> Iterator[None]:
    # The 127.0.0.1 server stands in for a public host; [::1] is "internal".
    if "public_port" not in request.fixturenames:
        yield
        return
    blocked = [ipaddress.ip_network("::1/128")]
    with (
        patch.object(security_utils, "BLOCKED_IP_NETWORKS", blocked),
        patch.object(security_utils, "ALWAYS_BLOCKED_IP_NETWORKS", blocked),
    ):
        yield


def test_safe_urlopen_fetches_allowed_host(public_port: int) -> None:
    with safe_urlopen(f"http://127.0.0.1:{public_port}/a.png", timeout=5) as resp:
        assert resp.read() == b"ok"


def test_redirect_to_internal_host_is_blocked(
    public_port: int, internal_port: int
) -> None:
    target = f"http://[::1]:{internal_port}/a.png"
    url = f"http://127.0.0.1:{public_port}/redirect?to={target}"
    with pytest.raises(urllib.error.URLError, match="blocked"):
        safe_urlopen(url, timeout=5)


def test_redirect_to_non_http_scheme_is_refused(public_port: int) -> None:
    url = f"http://127.0.0.1:{public_port}/redirect?to=ftp://127.0.0.1/a.png"
    with pytest.raises(urllib.error.URLError, match="unknown url type"):
        safe_urlopen(url, timeout=5)


def test_dns_rebinding_cannot_swap_the_validated_address() -> None:
    public = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 80))]
    internal = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", 80))]
    with patch.object(
        security_utils.socket, "getaddrinfo", side_effect=[public, internal]
    ):
        assert validate_url_safety("http://rebind.test/a.png")[0]
        # The fetch resolves again and must refuse, not connect to 127.0.0.1.
        with (
            patch.object(security_utils.socket, "socket") as sock,
            pytest.raises(urllib.error.URLError, match="blocked"),
        ):
            safe_urlopen("http://rebind.test/a.png", timeout=5)
        sock.assert_not_called()
