"""JSON Schema export for config models, plus the legacy /api/schema shape."""

import logging
from collections.abc import Mapping, Sequence

from pydantic import BaseModel
from pydantic.json_schema import JsonSchemaValue

from ledfx.configuration.fields import (
    BACKEND_ONLY_KEYS,
    X_ENUM_SOURCE,
    X_LEGACY,
    X_OMIT_DEFAULT,
    X_REQUIRED,
    get_enum_source,
)
from ledfx.configuration.jsonshape import as_dict as _obj
from ledfx.configuration.jsonshape import as_list as _items
from ledfx.utils import generate_title

_LOGGER = logging.getLogger(__name__)
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def _source_values(
    name: str,
) -> tuple[list[object] | dict[object, str], list[str] | None]:
    source = get_enum_source(name)
    if source is None:
        _LOGGER.warning("Enum source %r is not registered", name)
        return [], None
    return source.options(), (source.names() if source.names else None)


def _resolve(node: object, resolve: bool) -> object:
    if isinstance(node, dict):
        if not resolve:
            # Build-time export: keep the source name, never bake in this machine's values.
            return {
                k: _resolve(v, resolve)
                for k, v in node.items()
                if k == X_ENUM_SOURCE or k not in BACKEND_ONLY_KEYS
            }
        out = {
            k: _resolve(v, resolve)
            for k, v in node.items()
            if k not in BACKEND_ONLY_KEYS
        }
        if X_ENUM_SOURCE in node:
            options, names = _source_values(str(node[X_ENUM_SOURCE]))
            # An empty enum can't be satisfied: keep only the source name then.
            if options:
                # Nullable field: constrain only the non-null branch so null stays valid.
                target = next(
                    (
                        _obj(b)
                        for b in _items(out.get("anyOf"))
                        if _obj(b).get("type") != "null"
                    ),
                    out,
                )
                target["enum"] = list(options)
                if isinstance(options, dict):
                    out["x-ledfx-enum-names"] = list(options.values())
                elif names is not None:
                    out["x-ledfx-enum-names"] = names
        return out
    if isinstance(node, list):
        return [_resolve(v, resolve) for v in node]
    return node


def export_schema(model: type[BaseModel], *, resolve: bool = True) -> JsonSchemaValue:
    """Draft 2020-12 schema; x-ledfx-* UI hints kept.

    resolve=True (the HTTP API) fills runtime enum sources into `enum`.
    resolve=False (--dump-schemas, for TS generation) keeps `x-ledfx-enum-source`
    instead, so build output never depends on the build machine's hardware.
    """
    return {"$schema": DRAFT, **_obj(_resolve(model.model_json_schema(), resolve))}


# ---- legacy (pre-overhaul convertToJsonSchema) shape --------------------------
_LEGACY_TYPES = {
    "integer": "integer",
    "number": "number",
    "string": "string",
    "boolean": "boolean",
}


def _legacy_source(name: str) -> dict[str, object]:
    options, names = _source_values(name)
    if name == "fps":
        return {"type": "int", "enum": options}
    if name == "audio_devices":
        return {"type": "string", "enum": options}
    out: dict[str, object] = {"type": "string", "enum": options}
    if names is not None:
        out["names"] = names
    return out


def _deref(prop: dict[str, object], defs: Mapping[str, object]) -> dict[str, object]:
    if "$ref" in prop:
        target = _obj(defs[str(prop["$ref"]).rsplit("/", 1)[-1]])
        prop = {**target, **{k: v for k, v in prop.items() if k != "$ref"}}
    if "anyOf" in prop:
        branches = [
            _obj(b) for b in _items(prop["anyOf"]) if _obj(b).get("type") != "null"
        ]
        if len(branches) != 1:
            raise ValueError("unions of several types need an X_LEGACY type override")
        branch = branches[0]
        prop = {**{k: v for k, v in prop.items() if k != "anyOf"}, **branch}
        return _deref(prop, defs)
    return prop


def _legacy_value(
    prop: dict[str, object], defs: Mapping[str, object]
) -> dict[str, object]:
    prop = _deref(prop, defs)
    out: dict[str, object] = {}
    if X_ENUM_SOURCE in prop:
        out.update(_legacy_source(str(prop[X_ENUM_SOURCE])))
    elif prop.get("format") in ("color", "gradient"):
        out.update({"type": "color", "gradient": prop["format"] == "gradient"})
    elif "enum" in prop or "const" in prop:
        out.update({"type": "string", "enum": prop.get("enum", [prop.get("const")])})
    elif "properties" in prop:
        return _legacy_object(prop, defs)
    elif prop.get("type") == "array":
        items = _obj(prop.get("items"))
        out["type"] = "list" if items else "array"
        if items:
            out["validators"] = [_legacy_value(items, defs)]
    elif prop.get("type") == "object":
        out["type"] = "dict"
    elif str(prop.get("type")) in _LEGACY_TYPES:
        out["type"] = _LEGACY_TYPES[str(prop.get("type"))]
    if prop.get("format") == "ipv4":
        out["format"] = "ipv4"
    for src, dst in (
        ("minimum", "minimum"),
        ("maximum", "maximum"),
        ("exclusiveMinimum", "minimum"),
        ("exclusiveMaximum", "maximum"),
        ("minLength", "minLength"),
        ("maxLength", "maxLength"),
    ):
        if src in prop:
            out[dst] = prop[src]
    return out


def _legacy_object(
    schema: Mapping[str, object],
    defs: Mapping[str, object],
    order: Sequence[str] | None = None,
    extra_properties: Mapping[str, dict[str, object]] | None = None,
    model: type[BaseModel] | None = None,
) -> dict[str, object]:
    properties: dict[str, object] = {}
    required: list[str] = []
    pydantic_required = set(_items(schema.get("required")))
    for name, raw_prop in _obj(schema.get("properties")).items():
        raw = _obj(raw_prop)
        overrides = dict(_obj(raw.get(X_LEGACY)))
        if overrides.pop("omit", False):
            continue  # field did not exist in the pre-overhaul schema
        if "type" in overrides:
            prop: dict[str, object] = {"type": overrides.pop("type")}
        else:
            try:
                prop = _legacy_value(raw, defs)
            except ValueError as exc:
                raise ValueError(f"{schema.get('title')}.{name}: {exc}") from exc
        prop["title"] = generate_title(name)
        if "description" in raw:
            prop["description"] = raw["description"]
        if not raw.get(X_OMIT_DEFAULT):
            if "default" in raw:
                prop["default"] = raw["default"]
            elif model is not None and name not in pydantic_required:
                # default_factory fields: pydantic's schema omits the value
                info = model.model_fields.get(name)
                if info is not None and not info.is_required():
                    prop["default"] = info.get_default(call_default_factory=True)
        prop.update(overrides)
        if raw.get(X_REQUIRED) or name in pydantic_required:
            required.append(name)
        properties[name] = prop
    for name, prop in (extra_properties or {}).items():
        properties[name] = prop
    if order is not None:
        ranked = {name: i for i, name in enumerate(order)}
        properties = dict(
            sorted(properties.items(), key=lambda kv: ranked.get(kv[0], len(ranked)))
        )
        required.sort(key=lambda name: ranked.get(name, len(ranked)))
    out: dict[str, object] = {"properties": properties}
    if required:
        out["required"] = required
    return out


def legacy_schema(
    model: type[BaseModel],
    order: Sequence[str] | None = None,
    extra_properties: Mapping[str, dict[str, object]] | None = None,
) -> JsonSchemaValue:
    """The pre-overhaul /api/schema shape for model (see convertToJsonSchema)."""
    schema = model.model_json_schema()
    return _legacy_object(
        schema, schema.get("$defs", {}), order, extra_properties, model
    )
