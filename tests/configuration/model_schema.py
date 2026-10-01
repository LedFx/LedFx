"""Per-plugin model JSON Schema, pinned from layer 9 through layer 12."""

import json
import os

from pydantic.json_schema import JsonSchemaValue

from tests.configuration.test_plugin_parity import _registry_classes

MODEL_SNAPSHOT = os.path.join(
    os.path.dirname(__file__), "snapshots", "plugin_models.json"
)


def _normalise(schema: JsonSchemaValue) -> JsonSchemaValue:
    schema = json.loads(json.dumps(schema))
    schema.pop("title", None)  # class name: auto "<type>" vs source "Config"
    for name, prop in schema.get("properties", {}).items():
        if prop.get("x-ledfx-enum-source") == "fps" and "default" in prop:
            prop["default"] = "<fps>"
        if name == "com_port":
            for key in ("enum", "default"):
                if key in prop:
                    prop[key] = "<com_port>"
    return schema


def render_model_schemas() -> dict[str, JsonSchemaValue]:
    return {
        f"{cls.__module__}:{plugin_type}": _normalise(
            cls.config_model().model_json_schema()
        )
        for plugin_type, cls in _registry_classes()
    }


def write_model_snapshot() -> None:
    with open(MODEL_SNAPSHOT, "w", encoding="utf-8") as file:
        # No sort_keys: property order is part of what the snapshot pins.
        json.dump(render_model_schemas(), file, indent=1)
        file.write("\n")
