"""GET /api/schemas[/{kind}]: standard JSON Schema for config models."""

from aiohttp import web
from pydantic.json_schema import JsonSchemaValue

from ledfx.api import RestEndpoint
from ledfx.api.jsonutil import dumps
from ledfx.configuration.models import (
    AudioConfig,
    LedFxConfig,
    MelbankConfig,
    MelbanksConfig,
    VirtualConfig,
    WledPreferences,
)
from ledfx.configuration.schema import export_schema


def build_schemas(ledfx: object) -> dict[str, JsonSchemaValue]:
    """All exported schemas: core kinds plus one entry per plugin type."""
    from ledfx.devices import Device
    from ledfx.effects import Effect
    from ledfx.integrations import Integration
    from ledfx.utils import RegistryLoader

    ex = export_schema
    out: dict[str, JsonSchemaValue] = {
        "audio": {"schema": ex(AudioConfig)},
        "melbanks": {"schema": ex(MelbanksConfig)},
        "melbank_collection": {"schema": ex(MelbankConfig)},
        "wled_preferences": {"schema": ex(WledPreferences)},
        "virtuals": {"schema": ex(VirtualConfig)},
        "core": {"schema": ex(LedFxConfig)},
    }
    # Sorted: registry order follows import order, which differs in a running server.
    devices = sorted(RegistryLoader(ledfx, Device, "ledfx.devices").classes().items())
    out["devices"] = {t: {"schema": ex(c.config_model()), "id": t} for t, c in devices}
    integrations = sorted(
        RegistryLoader(ledfx, Integration, "ledfx.integrations").classes().items()
    )
    out["integrations"] = {
        t: {
            "schema": ex(c.config_model()),
            "id": t,
            "name": c.NAME,
            "description": c.DESCRIPTION,
            "beta": c.beta,
        }
        for t, c in integrations
    }
    effects: JsonSchemaValue = {}
    for t, c in sorted(
        RegistryLoader(ledfx, Effect, "ledfx.effects").classes().items()
    ):
        entry: JsonSchemaValue = {
            "schema": ex(c.config_model()),
            "id": t,
            "name": c.NAME,
            "category": c.CATEGORY,
            "uses_melbank_range": c.USES_MELBANK_RANGE,
        }
        for attr, key in (
            ("HIDDEN_KEYS", "hidden_keys"),
            ("ADVANCED_KEYS", "advanced_keys"),
            ("PERMITTED_KEYS", "permitted_keys"),
        ):
            if getattr(c, attr):
                entry[key] = getattr(c, attr)
        effects[t] = entry
    out["effects"] = effects
    return out


class SchemasEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/schemas"

    async def get(self, request: web.Request) -> web.Response:
        return web.json_response(
            data=build_schemas(self._ledfx), status=200, dumps=dumps
        )
