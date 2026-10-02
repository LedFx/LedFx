"""GET changes nothing.

Every v2 GET route is called with fixture ids, with outbound HTTP blocked. It
must answer 200, leave the config as it was, and call nothing on the core
beyond the read verbs in READ_CALLS (so a destroy, create, save, event or
device write fails it). A new GET route whose path has a parameter fails here
until its id is added to PATH_PARAM_FIXTURES and the resource is seeded.
"""

import re
import urllib.request
from collections.abc import Awaitable, Callable
from unittest.mock import MagicMock
from urllib.parse import quote

import aiohttp
import pytest
import requests
from aiohttp import web
from aiohttp.test_utils import TestClient
from yarl import URL

from ledfx.api.v2.core.app import BOUND_ROUTES_KEY, V2_PREFIX
from ledfx.api.v2.core.binding import LEDFX_KEY
from ledfx.api.v2.core.registry import load_plugin_registries
from ledfx.api.v2.core.router import RouteSpec, discover_routers

load_plugin_registries()

# Path parameter name -> the id of a resource the test seeds. Empty: no
# built-in GET route has a path parameter yet.
PATH_PARAM_FIXTURES: dict[str, str] = {}

# The only calls a GET may make on the fake core (the last name of each
# recorded call). Anything else (save, fire_event, destroy, create, flush,
# set_effect, ...) fails the test.
READ_CALLS = frozenset(
    {
        "get",
        "values",
        "items",
        "keys",
        "virtual_entry",
        "device_entry",
        "__iter__",
        "__contains__",
        "__len__",
        "__getitem__",
    }
)


def _get_routes() -> list[RouteSpec]:
    builtin, extensions = discover_routers()
    return sorted(
        (
            spec
            for router in (*builtin, *extensions)
            for spec in router.routes
            if spec.method.upper() == "GET"
        ),
        key=lambda spec: spec.path,
    )


GET_ROUTES = _get_routes()


def _fill_path(path: str) -> str:
    """Substitute fixture ids into a route path, percent-encoded."""
    params = re.findall(r"\{([^}:]+)", path)
    missing = [name for name in params if name not in PATH_PARAM_FIXTURES]
    assert not missing, (
        f"GET {path}: no fixture id for {missing}; add it to "
        "PATH_PARAM_FIXTURES and seed the resource in _seed()"
    )
    return re.sub(
        r"\{([^}:]+)(?::[^}]*)?\}",
        lambda m: quote(PATH_PARAM_FIXTURES[m.group(1)], safe=""),
        path,
    )


def _block_outbound(
    monkeypatch: pytest.MonkeyPatch, client: TestClient[web.Request, web.Application]
) -> list[str]:
    """Stub every HTTP client LedFx uses; return the list of blocked calls."""
    blocked: list[str] = []
    real_request: Callable[..., Awaitable[aiohttp.ClientResponse]] = (
        aiohttp.ClientSession._request
    )

    async def aiohttp_request(
        self: aiohttp.ClientSession,
        method: str,
        str_or_url: str | URL,
        **kwargs: object,
    ) -> aiohttp.ClientResponse:
        url = URL(str_or_url)
        if (url.host, url.port) == (client.host, client.port):
            return await real_request(self, method, str_or_url, **kwargs)
        blocked.append(f"aiohttp {method} {url}")
        raise AssertionError(f"GET made an outbound request: {url}")

    def urllib_open(
        self: urllib.request.OpenerDirector,
        fullurl: object,
        *args: object,
        **kwargs: object,
    ) -> object:
        url = getattr(fullurl, "full_url", fullurl)
        blocked.append(f"urllib {url}")
        raise AssertionError(f"GET made an outbound request: {url}")

    def requests_request(
        self: requests.Session, method: str, url: str, *args: object, **kwargs: object
    ) -> requests.Response:
        blocked.append(f"requests {method} {url}")
        raise AssertionError(f"GET made an outbound request: {url}")

    monkeypatch.setattr(aiohttp.ClientSession, "_request", aiohttp_request)
    monkeypatch.setattr(urllib.request.OpenerDirector, "open", urllib_open)
    monkeypatch.setattr(requests.Session, "request", requests_request)
    return blocked


def test_fill_path_requires_a_fixture_for_every_param(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(PATH_PARAM_FIXTURES, "known_id", "a/b")
    assert _fill_path("/things/{known_id}") == "/things/a%2Fb"
    with pytest.raises(AssertionError, match="no fixture id for \\['thing_id'\\]"):
        _fill_path("/things/{thing_id}")


def test_layer_get_routes_are_discovered() -> None:
    # Guards against discovery silently returning nothing, which would leave
    # test_get_is_safe with no cases.
    assert {
        "/system",
        "/openapi.json",
        "/docs",
        "/docs/scalar.standalone.js",
    } <= {spec.path for spec in GET_ROUTES}


async def test_every_get_route_is_covered(
    v2_client: TestClient[web.Request, web.Application],
) -> None:
    mounted = {
        route.spec.path
        for route in v2_client.app[BOUND_ROUTES_KEY]
        if route.spec.method.upper() == "GET"
    }
    assert mounted == {spec.path for spec in GET_ROUTES}


@pytest.mark.parametrize(
    "spec", GET_ROUTES, ids=[spec.handler.__name__ for spec in GET_ROUTES]
)
async def test_get_is_safe(
    spec: RouteSpec,
    v2_client: TestClient[web.Request, web.Application],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = _fill_path(spec.path)
    blocked = _block_outbound(monkeypatch, v2_client)
    core = v2_client.app[LEDFX_KEY]
    assert isinstance(core, MagicMock)  # tests/api_v2/conftest.py: fake_ledfx()
    before = len(core.mock_calls)
    config_before = core.config.model_dump()

    resp = await v2_client.get(V2_PREFIX + path)

    assert not blocked, f"GET {spec.path} reached the network: {blocked}"
    assert resp.status == 200, await resp.text()
    assert core.config.model_dump() == config_before, (
        f"GET {spec.path} changed the config"
    )
    writes = [
        name
        for name, _args, _kwargs in core.mock_calls[before:]
        if name.rsplit(".", 1)[-1] not in READ_CALLS
    ]
    assert not writes, f"GET {spec.path} called non-read methods: {writes}"
