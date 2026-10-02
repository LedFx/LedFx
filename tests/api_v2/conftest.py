"""Shared fixtures for the v2 API tests."""

from collections.abc import AsyncIterator, Awaitable, Callable
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

from ledfx.api.origin_policy import origin_middleware
from ledfx.api.v2 import mount_v2
from ledfx.api.v2.core import router as router_module
from ledfx.api.v2.core.binding import LEDFX_KEY, bind
from ledfx.api.v2.core.problem import problem_for, problem_response
from ledfx.api.v2.core.router import Router
from tests.test_utilities.fake_ledfx import fake_ledfx

Client = TestClient[web.Request, web.Application]
ServeRoutes = Callable[[Router], Awaitable[Client]]


@web.middleware
async def _problems(
    request: web.Request,
    handler: Callable[[web.Request], Awaitable[web.StreamResponse]],
) -> web.StreamResponse:
    try:
        return await handler(request)
    except web.HTTPException:
        raise
    except Exception as exc:  # noqa: BLE001 - a stand-in for the v2 middleware
        return problem_response(problem_for(exc, "req-test"))


@pytest.fixture
async def serve_routes() -> AsyncIterator[ServeRoutes]:
    """Serve one router's bound routes at their bare paths (no /api/v2, no
    mount_v2), with errors turned into Problems."""
    clients: list[Client] = []

    async def serve(router: Router) -> Client:
        app = web.Application(client_max_size=5 * 1024 * 1024)
        app.middlewares.append(_problems)
        app[LEDFX_KEY] = fake_ledfx()
        for spec in router.routes:
            app.router.add_route(spec.method, spec.path, bind(spec).__call__)
        client = Client(TestServer(app))
        await client.start_server()
        clients.append(client)
        return client

    yield serve
    for client in clients:
        await client.close()


@pytest.fixture
def v2_ledfx() -> MagicMock:
    """The core behind v2_client. Override it in a test module to seed state."""
    return fake_ledfx()


@pytest.fixture
def v2_routers() -> list[Router]:
    """Extra routers v2_client mounts as extensions. Override to add some."""
    return []


@pytest.fixture
async def v2_client(
    v2_ledfx: MagicMock, v2_routers: list[Router], monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[Client]:
    """The real v2 mount (built-in routes + v2_routers) on a bare app, with
    the same body limit and origin middleware as HttpServer."""
    monkeypatch.setattr(router_module, "_EXTENSIONS", list(v2_routers))
    app = web.Application(
        client_max_size=5 * 1024 * 1024, middlewares=[origin_middleware(v2_ledfx)]
    )
    mount_v2(app, v2_ledfx)
    async with Client(TestServer(app)) as client:
        yield client
