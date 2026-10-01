"""GET /api/schemas[/{kind}]: standard JSON Schema for config models."""

from aiohttp import web
from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaValue

from ledfx.api import RestEndpoint
from ledfx.configuration.models import (
    AudioConfig,
    MelbankConfig,
    MelbanksConfig,
    VirtualConfig,
    WledPreferences,
)
from ledfx.configuration.schema import export_schema


def build_schemas(ledfx: object, *, resolve: bool = True) -> dict[str, JsonSchemaValue]:
    """All exported schemas. Layers 8 and 9 add core and plugin kinds."""

    def ex(model: type[BaseModel]) -> JsonSchemaValue:
        return export_schema(model, resolve=resolve)

    return {
        "audio": {"schema": ex(AudioConfig)},
        "melbanks": {"schema": ex(MelbanksConfig)},
        "melbank_collection": {"schema": ex(MelbankConfig)},
        "wled_preferences": {"schema": ex(WledPreferences)},
        "virtuals": {"schema": ex(VirtualConfig)},
    }


class SchemasEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/schemas"

    async def get(self, request: web.Request) -> web.Response:
        return web.json_response(data=build_schemas(self._ledfx), status=200)
