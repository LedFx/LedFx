"""Mount /api/v2 on the main app: routes and the error middleware. CORS and
origin checks come from the server's origin middleware."""

import hashlib
import json
import logging
from collections.abc import Awaitable, Callable
from functools import cached_property
from typing import TYPE_CHECKING

from aiohttp import web

from ledfx.api import origin_policy
from ledfx.api.v2.core.binding import (
    LEDFX_KEY,
    BoundRoute,
    bind,
    check_unique,
    link_locations,
)
from ledfx.api.v2.core.problem import (
    ProblemError,
    new_instance,
    problem_for,
    problem_headers,
    problem_response,
)
from ledfx.api.v2.core.router import discover_routers

if TYPE_CHECKING:
    from ledfx.core import LedFxCore

_LOGGER = logging.getLogger(__name__)

V2_PREFIX = "/api/v2"
# The contract version (info.version in the spec), not the LedFx release: bump it
# by hand when the contract changes (minor for additions, major for breaks).
API_VERSION = "2.0.0"
BOUND_ROUTES_KEY: web.AppKey[list[BoundRoute]] = web.AppKey("v2_bound_routes")
OPENAPI_KEY: web.AppKey["OpenApiDoc"] = web.AppKey("v2_openapi")

Handler = Callable[[web.Request], Awaitable[web.StreamResponse]]


class OpenApiDoc:
    """The spec, built on first read (a build costs ~0.5 s with every route):
    the dict, its compact key-sorted JSON (what GET /openapi.json serves) and
    the sha256 hex of that JSON (the ETag), each computed once."""

    def __init__(self, routes: list[BoundRoute]) -> None:
        self._routes = routes

    @cached_property
    def spec(self) -> dict[str, object]:
        # Imported here: openapi.py imports V2_PREFIX from this module.
        from ledfx.api.v2.core.openapi import mounted_spec

        return mounted_spec(self._routes, version=API_VERSION)

    @cached_property
    def body(self) -> bytes:
        return json.dumps(self.spec, sort_keys=True, separators=(",", ":")).encode()

    @cached_property
    def digest(self) -> str:
        return hashlib.sha256(self.body).hexdigest()


def mount_v2(app: web.Application, ledfx: "LedFxCore | None") -> None:
    """Bind every router and add its routes under /api/v2. Call before the
    app is frozen (HttpServer.start), after the plugin registries load.
    ledfx is None only for building the spec (--dump-openapi): no handler runs."""
    # Imported here: openapi.py imports V2_PREFIX from this module.
    from ledfx.api.v2.core.openapi import (
        build_openapi,
        check_builtins,
        check_extension,
    )

    builtins, extensions = discover_routers()
    routes = [bind(spec) for router in builtins for spec in router.routes]
    check_unique(routes)  # a broken built-in router stops LedFx starting
    # Built-ins first: their clash is a startup error, not an extension's fault.
    n_builtin = len(routes)
    if extensions:
        check_builtins(routes, version=API_VERSION)  # cached per process
    for router in extensions:
        try:
            extra = [bind(spec) for spec in router.routes]
            check_unique([*routes, *extra])
            # A component-name clash is an app-build failure too:
            # a trial build finds it, so the extension is skipped, not fatal.
            if len(routes) == n_builtin:  # the cheap check against the built-ins
                check_extension(routes, extra, version=API_VERSION)
            else:  # a second extension also has to fit the first
                build_openapi([*routes, *extra], version=API_VERSION)
        except Exception:  # LedFx starts without the extension
            _LOGGER.exception("Skipping v2 extension router %r", router.tag)
            continue
        routes.extend(extra)
    link_locations(routes)

    by_path: dict[str, list[BoundRoute]] = {}
    for route in routes:
        by_path.setdefault(route.spec.path, []).append(route)
    for path, group in by_path.items():
        resource = app.router.add_resource(V2_PREFIX + path)
        for route in group:
            resource.add_route(route.spec.method, route.__call__)
            if route.spec.method == "GET":  # like router.add_get: HEAD, no body
                resource.add_route("HEAD", route.__call__)

    if ledfx is not None:
        app[LEDFX_KEY] = ledfx
    app[BOUND_ROUTES_KEY] = routes
    app[OPENAPI_KEY] = OpenApiDoc(routes)
    app.middlewares.append(error_middleware)
    origin_policy.ORIGIN_REFUSAL = _origin_refusal


def _is_v2(path: str) -> bool:
    return path == V2_PREFIX or path.startswith(V2_PREFIX + "/")


def _origin_refusal(request: web.Request, reason: str) -> web.Response | None:
    """The origin middleware runs outside error_middleware, so its refusals
    under /api/v2 are turned into Problems here."""
    if not _is_v2(request.path):
        return None
    exc = ProblemError(403, "forbidden", "Forbidden", reason)
    return problem_response(problem_for(exc, new_instance()))


@web.middleware
async def error_middleware(
    request: web.Request, handler: Handler
) -> web.StreamResponse:
    """Every error under /api/v2 becomes a Problem; other paths are untouched."""
    if not _is_v2(request.path):
        return await handler(request)
    try:
        return await handler(request)
    except web.HTTPException as exc:
        if exc.status < 400:  # redirects and 304s are answers, not errors
            raise
        return _problem(request, exc)
    except Exception as exc:  # noqa: BLE001 - anything else is a 500
        return _problem(request, exc)


def _problem(request: web.Request, exc: Exception) -> web.Response:
    instance = new_instance()
    problem = problem_for(exc, instance)
    if problem.status >= 500:
        _LOGGER.error(
            "v2 %s %s failed [%s]", request.method, request.path, instance, exc_info=exc
        )
    return problem_response(problem, problem_headers(exc))
