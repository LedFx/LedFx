"""Routers: typed handlers declared per family, discovered with pkgutil."""

import importlib
import pkgutil
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import TypeVar

from ledfx.errors import LedFxError

ROUTES_PACKAGE = "ledfx.api.v2.routes"

F = TypeVar("F", bound=Callable[..., Awaitable[object]])


@dataclass(frozen=True)
class Binary:
    """A non-JSON response: the handler returns a web.StreamResponse."""

    media_type: str


@dataclass(frozen=True)
class RouteSpec:
    method: str
    path: str
    handler: Callable[..., Awaitable[object]]
    tag: str
    status: int
    responses: Mapping[int, Binary]
    errors: tuple[type[LedFxError], ...]
    in_schema: bool = True


class Router:
    def __init__(self, tag: str) -> None:
        self.tag = tag
        self.routes: list[RouteSpec] = []

    def _route(
        self,
        method: str,
        path: str,
        status: int,
        responses: Mapping[int, Binary] | None,
        errors: Sequence[type[LedFxError]],
        in_schema: bool = True,
    ) -> Callable[[F], F]:
        # Paths are relative to /api/v2; "/api..." means the prefix was repeated.
        if not path.startswith("/") or path == "/api" or path.startswith("/api/"):
            raise ValueError(f"v2 path {path!r} must start with / and not /api")

        def decorator(fn: F) -> F:
            self.routes.append(
                RouteSpec(
                    method=method,
                    path=path,
                    handler=fn,
                    tag=self.tag,
                    status=status,
                    responses=dict(responses or {}),
                    errors=tuple(errors),
                    in_schema=in_schema,
                )
            )
            return fn

        return decorator

    def get(
        self,
        path: str,
        *,
        status: int = 200,
        responses: Mapping[int, Binary] | None = None,
        errors: Sequence[type[LedFxError]] = (),
        in_schema: bool = True,
    ) -> Callable[[F], F]:
        return self._route("GET", path, status, responses, errors, in_schema)

    def post(
        self,
        path: str,
        *,
        status: int = 200,
        responses: Mapping[int, Binary] | None = None,
        errors: Sequence[type[LedFxError]] = (),
    ) -> Callable[[F], F]:
        return self._route("POST", path, status, responses, errors)

    def put(
        self,
        path: str,
        *,
        status: int = 200,
        responses: Mapping[int, Binary] | None = None,
        errors: Sequence[type[LedFxError]] = (),
    ) -> Callable[[F], F]:
        return self._route("PUT", path, status, responses, errors)

    def patch(
        self,
        path: str,
        *,
        status: int = 200,
        responses: Mapping[int, Binary] | None = None,
        errors: Sequence[type[LedFxError]] = (),
    ) -> Callable[[F], F]:
        return self._route("PATCH", path, status, responses, errors)

    def delete(
        self,
        path: str,
        *,
        status: int = 200,
        responses: Mapping[int, Binary] | None = None,
        errors: Sequence[type[LedFxError]] = (),
    ) -> Callable[[F], F]:
        return self._route("DELETE", path, status, responses, errors)


_EXTENSIONS: list[Router] = []


def register(router: Router) -> None:
    """Add a router from outside ledfx.api.v2.routes; call before the app is
    built (HttpServer.start)."""
    _EXTENSIONS.append(router)


def discover_routers(
    package: str = ROUTES_PACKAGE,
) -> tuple[list[Router], list[Router]]:
    """(built-in routers from package's modules in name order, extensions)."""
    root = importlib.import_module(package)
    builtins: list[Router] = []
    modules = sorted(
        pkgutil.iter_modules(root.__path__, package + "."), key=lambda m: m.name
    )
    for info in modules:
        module = importlib.import_module(info.name)
        found = getattr(module, "router", None)
        if isinstance(found, Router):
            builtins.append(found)
        many = getattr(module, "routers", None)
        if isinstance(many, list):
            builtins.extend(r for r in many if isinstance(r, Router))
    return builtins, list(_EXTENSIONS)
