"""Tests for the request Origin policy and the CORS headers built from it."""

import re
import socket
from pathlib import Path
from types import SimpleNamespace

import aiohttp
import pytest
import requests
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ledfx.api.origin_policy import (
    STATE_CHANGING_GETS,
    is_host_allowed,
    is_origin_allowed,
    origin_middleware,
)
from ledfx.configuration.models import LedFxConfig
from tests.test_utilities.consts import BASE_PORT

HOST = "ledfx.example.com:8888"


@pytest.mark.parametrize(
    ("origin", "host"),
    [
        # same origin, including the SSL port and a TLS-terminating proxy
        ("http://ledfx.example.com:8888", HOST),
        ("HTTP://LedFx.Example.com:8888", HOST),
        ("https://ledfx.example.com:8889", "ledfx.example.com:8889"),
        ("https://ledfx.example.com", "ledfx.example.com"),
        ("http://ledfx.example.com", "LEDFX.example.com"),
        # local hosts, any port
        ("http://localhost:3000", HOST),
        ("https://localhost:8889", HOST),
        ("http://127.0.0.1:8888", HOST),
        ("http://10.1.2.3:8888", HOST),
        ("http://172.16.0.1", HOST),
        ("http://192.168.1.5:8888", HOST),
        ("http://100.64.1.1:8888", HOST),
        ("http://169.254.10.10", HOST),
        ("http://[::1]:8888", HOST),
        ("http://[fd00::1]:8888", HOST),
        ("http://[fe80::1]", HOST),
        ("http://[::ffff:192.168.1.1]:8888", HOST),
        ("http://ledfx.local:8888", HOST),
        ("https://LedFx.Local:8889", HOST),
        ("http://ledfx.local.:8888", HOST),
        ("http://raspberrypi:8888", HOST),
        ("http://ledfx.home.arpa", HOST),
        ("http://ledfx.lan:8888", HOST),
        ("http://ledfx.home", HOST),
        ("http://ledfx.localdomain", HOST),
        ("http://ledfx.fritz.box:8888", HOST),
        ("http://ledfx.internal", HOST),
        ("http://app.localhost:5173", HOST),
        # hosted frontends
        ("https://ledfx.stream", HOST),
        ("https://yeonv.github.io", HOST),
        # Electron desktop client WebSocket
        ("file://", HOST),
    ],
)
def test_allowed(origin, host):
    assert is_origin_allowed(origin, host)


@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://ledfx.example.com:9999",
        "https://ledfx.example.com",
        "http://8.8.8.8",
        "http://172.32.0.1",
        "http://[2001:4860::8888]",
        "http://[::ffff:8.8.8.8]",
        "http://localhost.evil.example",
        "http://ledfx.local.evil.example",
        "http://ledfx.lan.evil.example",
        "http://evil-fritz.box",
        "http://evil.box",
        "http://ledfx.stream",
        "https://ledfx.stream:8443",
        "https://my.ledfx.app",
        "https://studio.ledfx.stream",
        "null",
        # malformed or not a serialized origin
        "",
        "localhost",
        "http://",
        "http://.",
        "ftp://localhost",
        "http://localhost:99999",
        "http://[::1",
        "http://user@localhost",
        "http://evil.example\\@localhost",
        "http://localhost/",
        "http://localhost:3000/path",
        "http://localhost?x=1",
        "http://localhost#x",
    ],
)
def test_denied(origin):
    assert not is_origin_allowed(origin, HOST)


def test_allowed_origins_extras():
    extras = ["https://Dash.example.com/", "http://proxy.example:8080"]
    assert is_origin_allowed("https://dash.example.com", HOST, extras)
    assert is_origin_allowed("http://proxy.example:8080", HOST, extras)
    assert not is_origin_allowed("http://proxy.example", HOST, extras)
    assert not is_origin_allowed("https://evil.example", HOST, extras)


def test_allowed_origins_wildcard_allows_everything():
    for origin in ("https://evil.example", "null", "garbage"):
        assert is_origin_allowed(origin, HOST, ["*"])


def test_null_origin_needs_setting():
    assert not is_origin_allowed("null", HOST)
    assert is_origin_allowed("null", HOST, allow_null=True)
    assert is_origin_allowed("NULL", HOST, allow_null=True)


@pytest.mark.parametrize(
    "host",
    [
        "127.0.0.1:8888",
        "192.168.1.5",
        "8.8.8.8:8888",
        "[::1]:8888",
        "[2001:db8::1]",
        "localhost:8888",
        "LocalHost",
        "ledfx.local",
        "LedFx.Local.:8889",
        "raspberrypi:8888",
        "ledfx.home.arpa",
        "ledfx.lan:8888",
        "ledfx.home",
        "ledfx.localdomain",
        "LedFx.Fritz.Box",
        "ledfx.internal",
        "app.localhost:5173",
        "mybox.example.org:8888",
    ],
)
def test_host_allowed(host):
    assert is_host_allowed(host, own_names={"mybox.example.org"})


@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        "evil.example:8888",
        "ledfx.example.com",
        "ledfx.local.evil.example",
        "ledfx.lan.evil.example",
        "evil-fritz.box",
        "evil.box:8888",
        "localhost.evil.example",
        "",
        "user@localhost",
        "localhost:99999",
        "[::1",
    ],
)
def test_host_denied(host):
    assert not is_host_allowed(host, own_names={"mybox.example.org"})


def test_allowed_hosts_extras():
    for entries in (
        ["LEDFX.example.com"],
        ["ledfx.example.com:8080"],
        ["https://ledfx.example.com/"],
        ["ledfx.example.com."],
    ):
        assert is_host_allowed("ledfx.example.com:8888", entries)
    assert not is_host_allowed("evil.example", ["ledfx.example.com"])
    assert is_host_allowed("evil.example", ["*"])


def test_state_changing_gets_are_real_routes():
    paths = set()
    for module in Path("ledfx/api").glob("*.py"):
        paths.update(re.findall(r'ENDPOINT_PATH = "([^"]+)"', module.read_text()))
    assert STATE_CHANGING_GETS <= paths
    assert {
        "/api/find_devices",
        "/api/find_lifx",
        "/api/virtuals/{virtual_id}/fallback",
    } <= STATE_CHANGING_GETS


# --- middleware -------------------------------------------------------------

EVIL = "https://evil.example"
LOCAL = "http://192.168.1.20:8888"


@pytest.fixture
async def client():
    ledfx = SimpleNamespace(config=LedFxConfig())

    async def thing(request):
        return web.json_response({"method": request.method})

    async def websocket(request):
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        await ws.send_str("hello")
        await ws.close()
        return ws

    app = web.Application(middlewares=[origin_middleware(ledfx)])
    for method in ("GET", "PUT", "POST", "DELETE"):
        app.router.add_route(method, "/api/thing", thing)
    app.router.add_get("/api/websocket", websocket)
    app.router.add_get("/api/find_devices", thing)
    app.router.add_get("/api/virtuals/{virtual_id}/fallback", thing)
    async with TestClient(TestServer(app)) as test_client:
        test_client.ledfx = ledfx
        yield test_client


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE", "PATCH"])
async def test_unsafe_method_from_disallowed_origin_is_rejected(client, method):
    resp = await client.request(method, "/api/thing", headers={"Origin": EVIL})
    assert resp.status == 403
    assert await resp.json() == {
        "status": "failed",
        "payload": {
            "type": "error",
            "reason": f"Origin not allowed: {EVIL}. "
            "Add it to allowed_origins in the LedFx config.",
        },
    }
    assert "Access-Control-Allow-Origin" not in resp.headers


@pytest.mark.parametrize("method", ["POST", "PUT", "DELETE"])
async def test_unsafe_method_without_origin_is_allowed(client, method):
    resp = await client.request(method, "/api/thing")
    assert resp.status == 200
    assert "Access-Control-Allow-Origin" not in resp.headers


async def test_unsafe_method_from_allowed_origin_gets_cors_headers(client):
    resp = await client.post("/api/thing", headers={"Origin": LOCAL})
    assert resp.status == 200
    assert resp.headers["Access-Control-Allow-Origin"] == LOCAL
    assert resp.headers["Vary"] == "Origin"
    assert "Access-Control-Allow-Credentials" not in resp.headers


async def test_same_origin_by_host_header(client):
    client.ledfx.config.allowed_hosts = ["ledfx.example.com"]
    headers = {"Host": HOST, "Origin": "http://ledfx.example.com:8888"}
    assert (await client.post("/api/thing", headers=headers)).status == 200
    headers["Origin"] = "http://ledfx.example.com:9999"
    assert (await client.post("/api/thing", headers=headers)).status == 403


async def test_get_from_disallowed_origin_is_served_without_cors(client):
    resp = await client.get("/api/thing", headers={"Origin": EVIL})
    assert resp.status == 200
    assert "Access-Control-Allow-Origin" not in resp.headers


async def test_get_from_allowed_origin_gets_cors(client):
    resp = await client.get("/api/thing", headers={"Origin": LOCAL})
    assert resp.headers["Access-Control-Allow-Origin"] == LOCAL


async def test_missing_route_from_allowed_origin_keeps_cors(client):
    resp = await client.get("/api/missing", headers={"Origin": LOCAL})
    assert resp.status == 404
    assert resp.headers["Access-Control-Allow-Origin"] == LOCAL


async def test_preflight_allowed(client):
    resp = await client.options(
        "/api/thing",
        headers={
            "Origin": LOCAL,
            "Access-Control-Request-Method": "PUT",
            "Access-Control-Request-Headers": "content-type,x-custom",
        },
    )
    assert resp.status == 200
    assert resp.headers["Access-Control-Allow-Origin"] == LOCAL
    assert "PUT" in resp.headers["Access-Control-Allow-Methods"]
    assert resp.headers["Access-Control-Allow-Headers"] == "content-type,x-custom"
    assert "Access-Control-Allow-Credentials" not in resp.headers


async def test_preflight_disallowed(client):
    resp = await client.options(
        "/api/thing",
        headers={"Origin": EVIL, "Access-Control-Request-Method": "PUT"},
    )
    assert resp.status == 403
    assert "Access-Control-Allow-Origin" not in resp.headers


@pytest.mark.parametrize("origin", [None, LOCAL, "file://"])
async def test_websocket_allowed(client, origin):
    headers = {"Origin": origin} if origin else {}
    async with client.ws_connect("/api/websocket", headers=headers) as ws:
        assert await ws.receive_str() == "hello"


@pytest.mark.parametrize("origin", [EVIL, "null"])
async def test_websocket_from_disallowed_origin_is_rejected(client, origin):
    with pytest.raises(aiohttp.WSServerHandshakeError) as err:
        await client.ws_connect("/api/websocket", headers={"Origin": origin})
    assert err.value.status == 403


async def test_config_changes_apply_without_restart(client):
    assert (await client.post("/api/thing", headers={"Origin": EVIL})).status == 403
    client.ledfx.config.allowed_origins = [EVIL]
    assert (await client.post("/api/thing", headers={"Origin": EVIL})).status == 200
    client.ledfx.config.allowed_origins = ["*"]
    resp = await client.put("/api/thing", headers={"Origin": "https://other.example"})
    assert resp.status == 200


async def test_null_origin_setting(client):
    assert (await client.post("/api/thing", headers={"Origin": "null"})).status == 403
    client.ledfx.config.allow_null_origin = True
    resp = await client.post("/api/thing", headers={"Origin": "null"})
    assert resp.status == 200
    assert resp.headers["Access-Control-Allow-Origin"] == "null"


REBIND = {"Host": "evil.example:8888", "Origin": "http://evil.example:8888"}
HOST_REASON = (
    "Host not allowed: evil.example. Add it to allowed_hosts in the LedFx config."
)


async def test_foreign_host_with_same_origin_is_rejected(client):
    resp = await client.post("/api/thing", headers=REBIND)
    assert resp.status == 403
    assert (await resp.json())["payload"]["reason"] == HOST_REASON


@pytest.mark.parametrize(
    "headers",
    [
        {"Host": "evil.example:8888", "Sec-Fetch-Site": "same-origin"},
        {"Host": "evil.example:8888", "Sec-Fetch-Site": "none"},
    ],
)
async def test_foreign_host_browser_get_is_rejected(client, headers):
    resp = await client.get("/api/thing", headers=headers)
    assert resp.status == 403
    assert (await resp.json())["payload"]["reason"] == HOST_REASON


async def test_foreign_host_websocket_is_rejected(client):
    with pytest.raises(aiohttp.WSServerHandshakeError) as err:
        await client.ws_connect("/api/websocket", headers=REBIND)
    assert err.value.status == 403


@pytest.mark.parametrize("method", ["GET", "POST"])
async def test_foreign_host_without_browser_headers_is_rejected(client, method):
    # Over plain HTTP to a LAN address a browser sends no Sec-Fetch-* headers,
    # and a same-origin GET carries no Origin: a page on a rebinding name looks
    # like a script.
    headers = {"Host": "evil.example:8888"}
    resp = await client.request(method, "/api/thing", headers=headers)
    assert resp.status == 403
    assert (await resp.json())["payload"]["reason"] == HOST_REASON


@pytest.mark.parametrize(
    "host", ["192.168.1.200:8888", "[fd00::1]:8888", "ledfx.local", "ledfx"]
)
async def test_local_host_without_browser_headers_is_allowed(client, host):
    assert (await client.post("/api/thing", headers={"Host": host})).status == 200


async def test_script_using_allowed_dns_name(client):
    client.ledfx.config.allowed_hosts = ["ledfx.mydomain.example"]
    headers = {"Host": "ledfx.mydomain.example"}
    assert (await client.post("/api/thing", headers=headers)).status == 200


async def test_allowed_hosts_config(client):
    client.ledfx.config.allowed_hosts = ["evil.example"]
    assert (await client.post("/api/thing", headers=REBIND)).status == 200
    client.ledfx.config.allowed_hosts = ["*"]
    headers = {"Host": "other.example", "Origin": "http://other.example"}
    assert (await client.post("/api/thing", headers=headers)).status == 200


async def test_own_hostname_and_bind_host_are_allowed(client):
    name = socket.gethostname()
    headers = {"Host": f"{name}:8888", "Sec-Fetch-Site": "same-origin"}
    assert (await client.get("/api/thing", headers=headers)).status == 200
    client.ledfx.config.host = "ledfx-box.example.net"
    headers = {"Host": "ledfx-box.example.net", "Sec-Fetch-Site": "same-origin"}
    assert (await client.get("/api/thing", headers=headers)).status == 200


@pytest.mark.parametrize("path", ["/api/find_devices", "/api/virtuals/strip/fallback"])
async def test_state_changing_get_from_disallowed_origin_is_rejected(client, path):
    resp = await client.get(path, headers={"Origin": EVIL})
    assert resp.status == 403
    resp = await client.get(path, headers={"Origin": LOCAL})
    assert resp.status == 200
    assert resp.headers["Access-Control-Allow-Origin"] == LOCAL


@pytest.mark.parametrize(
    ("headers", "status"),
    [
        # <img>, <link>, navigation from another site: no Origin header
        ({"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors"}, 403),
        ({"Sec-Fetch-Site": "same-site", "Sec-Fetch-Mode": "navigate"}, 403),
        # Electron desktop client fetch from file://: cors mode, no Origin
        ({"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "cors"}, 200),
        # typed into the address bar
        ({"Sec-Fetch-Site": "none", "Sec-Fetch-Mode": "navigate"}, 200),
        ({"Sec-Fetch-Site": "same-origin", "Sec-Fetch-Mode": "cors"}, 200),
        # scripts
        ({}, 200),
    ],
)
async def test_state_changing_get_without_origin(client, headers, status):
    assert (await client.get("/api/find_devices", headers=headers)).status == status


async def test_plain_get_without_origin_from_other_site_is_served(client):
    headers = {"Sec-Fetch-Site": "cross-site", "Sec-Fetch-Mode": "no-cors"}
    assert (await client.get("/api/thing", headers=headers)).status == 200


# --- running LedFx ------------------------------------------------------------

API = f"http://127.0.0.1:{BASE_PORT}/api"


def test_live_server_rejects_disallowed_origin():
    resp = requests.put(f"{API}/config", json={}, headers={"Origin": EVIL})
    assert resp.status_code == 403
    assert "allowed_origins" in resp.json()["payload"]["reason"]


def test_live_server_config_keys():
    config = requests.get(f"{API}/config").json()
    assert config["allowed_origins"] == []
    assert config["allow_null_origin"] is False
    assert config["allowed_hosts"] == []
    permitted = requests.get(f"{API}/schema", json="core").json()["core"]["schema"][
        "permitted_keys"
    ]
    assert {"allowed_origins", "allowed_hosts", "allow_null_origin"} <= set(permitted)

    dash = "https://dash.example"
    try:
        resp = requests.put(f"{API}/config", json={"allowed_origins": [dash]})
        assert resp.json()["payload"]["reason"] == "Configuration Updated"
        resp = requests.put(
            f"{API}/config",
            json={"allowed_origins": [dash]},
            headers={"Origin": dash},
        )
        assert resp.status_code == 200
        assert resp.headers["Access-Control-Allow-Origin"] == dash
    finally:
        requests.put(f"{API}/config", json={"allowed_origins": []})


def test_live_server_rejects_foreign_host():
    resp = requests.get(f"{API}/info", headers=REBIND)
    assert resp.status_code == 403
    assert resp.json()["payload"]["reason"] == HOST_REASON


def test_live_server_gates_state_changing_get():
    resp = requests.get(f"{API}/find_devices", headers={"Origin": EVIL})
    assert resp.status_code == 403


def test_live_server_allowed_hosts():
    try:
        resp = requests.put(f"{API}/config", json={"allowed_hosts": ["evil.example"]})
        assert resp.json()["payload"]["reason"] == "Configuration Updated"
        assert requests.get(f"{API}/info", headers=REBIND).status_code == 200
    finally:
        requests.put(f"{API}/config", json={"allowed_hosts": []})
    assert requests.get(f"{API}/info", headers=REBIND).status_code == 403
