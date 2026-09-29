"""Render, normalise and compare the legacy GET /api/schema payload.

The snapshot was captured once from the voluptuous-based code and must never
be regenerated: the pydantic models have to reproduce it exactly.
"""

import asyncio
import json
import os
import types

from aiohttp.test_utils import make_mocked_request
from pydantic.json_schema import JsonSchemaValue

SNAPSHOT = os.path.join(os.path.dirname(__file__), "snapshots", "legacy_schema.json")

# Values that depend on the machine (clock resolution, sound cards, serial
# ports, created virtuals) are replaced by placeholders before comparing.
_MACHINE_DEPENDENT_KEYS = ("com_port",)


def fake_ledfx() -> object:
    from ledfx.devices import Device
    from ledfx.effects import Effect
    from ledfx.integrations import Integration
    from ledfx.utils import RegistryLoader

    ledfx = types.SimpleNamespace()
    ledfx.devices = RegistryLoader(ledfx, Device, "ledfx.devices")
    ledfx.effects = RegistryLoader(ledfx, Effect, "ledfx.effects")
    ledfx.integrations = RegistryLoader(ledfx, Integration, "ledfx.integrations")
    return ledfx


def render_legacy_schema() -> JsonSchemaValue:
    from ledfx.api.schema import SchemaEndpoint

    endpoint = SchemaEndpoint(fake_ledfx())
    response = asyncio.run(endpoint.get(make_mocked_request("GET", "/api/schema")))
    return json.loads(response.text or "")


def _normalise_property(name: str, prop: dict[str, object]) -> None:
    placeholder = None
    if prop.get("type") == "int" and "enum" in prop:
        placeholder = "<fps>"
    elif isinstance(prop.get("enum"), dict):
        placeholder = "<audio_devices>"
    elif "names" in prop:
        placeholder = "<virtuals>"
        prop["names"] = placeholder
    elif name in _MACHINE_DEPENDENT_KEYS and "enum" in prop:
        placeholder = f"<{name}>"
    if placeholder is not None:
        prop["enum"] = placeholder
        if "default" in prop:
            prop["default"] = placeholder


def normalise(payload: JsonSchemaValue) -> JsonSchemaValue:
    payload = json.loads(json.dumps(payload))

    def walk(node: object) -> None:
        if isinstance(node, dict):
            for name, prop in (node.get("properties") or {}).items():
                if isinstance(prop, dict):
                    _normalise_property(name, prop)
            for value in node.values():
                walk(value)
        elif isinstance(node, list):
            for value in node:
                walk(value)

    walk(payload)
    return payload


def property_orders(payload: object, path: str = "") -> list[list[str]]:
    orders: list[list[str]] = []
    if isinstance(payload, dict):
        if isinstance(payload.get("properties"), dict):
            orders.append([path, *payload["properties"]])
        for key in sorted(payload):
            orders.extend(property_orders(payload[key], f"{path}/{key}"))
    return orders


def write_snapshot() -> None:
    os.makedirs(os.path.dirname(SNAPSHOT), exist_ok=True)
    with open(SNAPSHOT, "w", encoding="utf-8") as file:
        json.dump(normalise(render_legacy_schema()), file, indent=1)
        file.write("\n")
