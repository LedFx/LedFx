"""Render and compare the per-plugin model JSON Schema snapshot."""

import functools
import importlib
import json
import logging
import os
import pkgutil

from pydantic.json_schema import JsonSchemaValue

from ledfx.utils import BaseRegistry

_LOGGER = logging.getLogger(__name__)

MODEL_SNAPSHOT = os.path.join(
    os.path.dirname(__file__), "snapshots", "plugin_models.json"
)


@functools.cache
def _registry_by_kind() -> dict[str, list[tuple[str, type[BaseRegistry]]]]:
    out: dict[str, list[tuple[str, type[BaseRegistry]]]] = {}
    for kind, package, base_name in (
        ("effects", "ledfx.effects", "Effect"),
        ("devices", "ledfx.devices", "Device"),
        ("integrations", "ledfx.integrations", "Integration"),
    ):
        module = importlib.import_module(package)
        for _, name, _ in pkgutil.iter_modules(module.__path__, package + "."):
            try:
                importlib.import_module(name)
            except ModuleNotFoundError as err:
                # Some modules are platform-specific; say which were skipped.
                _LOGGER.warning("registry: skipped %s (%s)", name, err)
        out[kind] = sorted(getattr(module, base_name).registry().items())
    return out


def _registry_classes() -> list[tuple[str, type[BaseRegistry]]]:
    return [p for plugins in _registry_by_kind().values() for p in plugins]


def _normalise(schema: JsonSchemaValue) -> JsonSchemaValue:
    schema = json.loads(json.dumps(schema))
    schema.pop("title", None)  # class name: auto "<type>" vs source "Config"
    for prop in schema.get("properties", {}).values():
        if prop.get("x-ledfx-legacy-source") == "fps":  # rates depend on the clock
            for key in ("default", "examples"):
                if key in prop:
                    prop[key] = "<fps>"
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
