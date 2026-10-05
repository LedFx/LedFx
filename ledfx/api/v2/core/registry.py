"""Build the v2 spec without a running core (``--dump-openapi`` and the tests)."""

from aiohttp import web

from ledfx.api.v2.core.app import OPENAPI_KEY, mount_v2
from ledfx.devices import Device
from ledfx.effects import Effect
from ledfx.integrations import Integration
from ledfx.utils import RegistryLoader


def load_plugin_registries() -> None:
    """Import every effect, device and integration module, as core startup does.

    RegistryLoader logs and skips a module whose optional dependency is missing,
    so outside the canonical environment the spec is a subset of the committed one.
    """
    for cls, package in (
        (Effect, "ledfx.effects"),
        (Device, "ledfx.devices"),
        (Integration, "ledfx.integrations"),
    ):
        RegistryLoader(None, cls, package)


def build_standalone_spec() -> dict[str, object]:
    """The v2 OpenAPI document, built the way HttpServer.start() builds it."""
    load_plugin_registries()
    app = web.Application()
    mount_v2(app, None)
    return app[OPENAPI_KEY].spec
