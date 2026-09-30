"""Router declaration, pkgutil discovery and the extension hook."""

from pathlib import Path

import pytest

from ledfx.api.v2.core import router as router_module
from ledfx.api.v2.core.router import Binary, Router, discover_routers, register
from ledfx.errors import NotFound


async def _handler() -> None:
    return None


def test_decorator_records_the_route_and_returns_the_function() -> None:
    router = Router(tag="things")
    decorated = router.post(
        "/things",
        status=201,
        responses={200: Binary("image/png")},
        errors=[NotFound],
    )(_handler)
    assert decorated is _handler
    [spec] = router.routes
    assert (spec.method, spec.path, spec.tag, spec.status) == (
        "POST",
        "/things",
        "things",
        201,
    )
    assert spec.handler is _handler
    assert spec.responses == {200: Binary("image/png")}
    assert spec.errors == (NotFound,)


def test_each_method_decorator() -> None:
    router = Router(tag="t")
    router.get("/a")(_handler)
    router.put("/a")(_handler)
    router.patch("/a")(_handler)
    router.delete("/a", status=204)(_handler)
    assert [r.method for r in router.routes] == ["GET", "PUT", "PATCH", "DELETE"]
    assert router.routes[0].status == 200
    assert router.routes[0].responses == {}


@pytest.mark.parametrize("path", ["things", "/api", "/api/v2/things", ""])
def test_bad_paths_are_refused(path: str) -> None:
    with pytest.raises(ValueError, match="must start with /"):
        Router(tag="t").get(path)


def test_apiary_is_not_the_api_prefix() -> None:
    Router(tag="t").get("/apiary")(_handler)


def _write_package(root: Path, name: str, modules: dict[str, str]) -> None:
    package = root / name
    package.mkdir()
    (package / "__init__.py").write_text("")
    for module, source in modules.items():
        (package / f"{module}.py").write_text(source)


_MODULE = """
from ledfx.api.v2.core.router import Router
router = Router(tag={tag!r})
"""


def test_discovery_imports_modules_in_name_order(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_package(
        tmp_path,
        "v2routes_order",
        {
            "zeta": _MODULE.format(tag="zeta"),
            "alpha": _MODULE.format(tag="alpha"),
            "many": "from ledfx.api.v2.core.router import Router\n"
            "routers = [Router(tag='m1'), Router(tag='m2'), 'not a router']\n",
            "helpers": "VALUE = 1\n",
        },
    )
    monkeypatch.syspath_prepend(str(tmp_path))
    monkeypatch.setattr(router_module, "_EXTENSIONS", [])
    builtins, extensions = discover_routers("v2routes_order")
    assert [r.tag for r in builtins] == ["alpha", "m1", "m2", "zeta"]
    assert extensions == []


def test_register_adds_an_extension(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(router_module, "_EXTENSIONS", [])
    extra = Router(tag="extra")
    register(extra)
    _, extensions = discover_routers()
    assert extensions == [extra]


def test_a_broken_builtin_module_raises(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _write_package(tmp_path, "v2routes_broken", {"bad": "raise RuntimeError('x')\n"})
    monkeypatch.syspath_prepend(str(tmp_path))
    with pytest.raises(RuntimeError):
        discover_routers("v2routes_broken")
