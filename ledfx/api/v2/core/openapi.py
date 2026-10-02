"""Build the OpenAPI 3.1 document for /api/v2 from the bound route table."""

import inspect
import json
import re
from collections.abc import Iterable, Sequence
from http import HTTPStatus

from pydantic import BaseModel, TypeAdapter
from pydantic.json_schema import (
    GenerateJsonSchema,
    JsonSchemaMode,
    JsonSchemaValue,
)
from pydantic_core import core_schema, to_jsonable_python
from typing_extensions import override

from ledfx.api.v2.core.app import V2_PREFIX
from ledfx.api.v2.core.binding import BoundRoute, BuildError
from ledfx.api.v2.core.partial import partial_schema
from ledfx.api.v2.core.problem import Problem
from ledfx.configuration.jsonshape import as_dict
from ledfx.configuration.schema import strip_backend_keys

OPENAPI_VERSION = "3.1.0"
_REF = "#/components/schemas/{model}"
_PROBLEM_REF = "#/components/schemas/Problem"
_PLACEHOLDER = re.compile(r"{([^}/]+)}")
_MUTATING = frozenset({"POST", "PUT", "PATCH", "DELETE"})
_NO_CONTENT = frozenset({204, 304})  # RFC 9110: these statuses never carry content
# Core-schema node types that become named components. A tuple, not a set:
# some nodes' "type" values are dicts, which a set lookup cannot hash.
_NAMED = ("model", "dataclass", "typed-dict", "enum")

_Input = tuple[str, JsonSchemaMode, TypeAdapter[object]]
_REF_PREFIX = "#/components/schemas/"


class _OpenResponses(GenerateJsonSchema):
    """Response schemas stay open: a client that validates a response must not
    reject a field added later. Request schemas stay closed."""

    def _open(self, schema: JsonSchemaValue) -> JsonSchemaValue:
        if self.mode == "serialization" and schema.get("additionalProperties") is False:
            del schema["additionalProperties"]
        return schema

    @override
    def model_schema(self, schema: core_schema.ModelSchema) -> JsonSchemaValue:
        return self._open(super().model_schema(schema))

    @override
    def dataclass_schema(self, schema: core_schema.DataclassSchema) -> JsonSchemaValue:
        return self._open(super().dataclass_schema(schema))

    @override
    def typed_dict_schema(self, schema: core_schema.TypedDictSchema) -> JsonSchemaValue:
        return self._open(super().typed_dict_schema(schema))


def build_openapi(routes: Sequence[BoundRoute], *, version: str) -> dict[str, object]:
    """The OpenAPI document for routes, deterministic for a given route table."""
    inputs: list[_Input] = [("problem", "serialization", TypeAdapter[object](Problem))]
    for route in routes:
        op = route.operation_id
        if route.params_model is not None:
            for name, field in route.params_model.model_fields.items():
                adapter = TypeAdapter[object](field.rebuild_annotation())
                inputs.append((f"param:{op}:{name}", "validation", adapter))
        if route.body_adapter is not None and not route.body_is_patch:
            inputs.append((f"body:{op}", "validation", route.body_adapter))
        if route.patch_model is not None:
            # Built here so the name check below sees a PATCH body's models too.
            patch = TypeAdapter[object](route.patch_model)
            inputs.append((f"patch:{op}", "validation", patch))
        if route.return_adapter is not None:
            inputs.append((f"return:{op}", "serialization", route.return_adapter))
    schemas, defs = TypeAdapter.json_schemas(
        inputs, ref_template=_REF, schema_generator=_OpenResponses
    )
    # After json_schemas, which builds every adapter: one over a defer_build
    # model holds a mock core_schema (not a dict) until then.
    _check_component_names(adapter for _, _, adapter in inputs)
    components: dict[str, JsonSchemaValue] = dict(defs.get("$defs", {}))

    paths: dict[str, dict[str, object]] = {}
    for route in routes:
        path = V2_PREFIX + route.spec.path
        paths.setdefault(path, {})[route.spec.method.lower()] = _operation(
            route, schemas, components
        )
    spec: dict[str, object] = {
        "openapi": OPENAPI_VERSION,
        "info": {
            "title": "LedFx API",
            "version": version,
            "description": "Clients must ignore unknown fields in responses:"
            " new response fields are additive. Requests are strict.",
        },
        "tags": [{"name": tag} for tag in sorted({r.spec.tag for r in routes})],
        "paths": paths,
        "components": {"schemas": components},
    }
    return as_dict(strip_backend_keys(spec))


def _operation(
    route: BoundRoute,
    schemas: dict[tuple[str, JsonSchemaMode], JsonSchemaValue],
    components: dict[str, JsonSchemaValue],
) -> dict[str, object]:
    spec, op = route.spec, route.operation_id
    placeholders = _PLACEHOLDER.findall(spec.path)
    operation: dict[str, object] = {"operationId": op, "tags": [spec.tag]}
    summary, _, description = (inspect.getdoc(spec.handler) or "").partition("\n")
    if summary:
        operation["summary"] = summary.strip()
    if description.strip():
        operation["description"] = description.strip()

    parameters: list[dict[str, object]] = []
    if route.params_model is not None:
        for name, field in route.params_model.model_fields.items():
            schema = dict(schemas[(f"param:{op}:{name}", "validation")])
            in_path = name in placeholders
            if not in_path and not field.is_required():
                default = field.get_default(call_default_factory=True)
                schema["default"] = to_jsonable_python(default)
            param: dict[str, object] = {
                "name": name,
                "in": "path" if in_path else "query",
                "required": in_path or field.is_required(),
                "schema": schema,
            }
            if _is_array(schema):
                param["style"], param["explode"] = "form", True
            parameters.append(param)
    if parameters:
        operation["parameters"] = parameters

    body = _request_body(route, schemas, components)
    if body is not None:
        operation["requestBody"] = body

    responses: dict[str, object] = {}
    returns_none = route.return_type is None or route.return_type is type(None)
    if route.return_adapter is not None:
        responses[str(spec.status)] = {
            "description": HTTPStatus(spec.status).phrase,
            "content": {
                "application/json": {
                    "schema": schemas[(f"return:{op}", "serialization")]
                }
            },
        }
    elif returns_none:  # bind() allows -> None only with status 204 or 202
        responses[str(spec.status)] = {"description": HTTPStatus(spec.status).phrase}
    for code, binary in spec.responses.items():
        entry: dict[str, object] = {"description": HTTPStatus(code).phrase}
        if code not in _NO_CONTENT:
            no_schema: dict[str, object] = {}  # Binary: any bytes of that media type
            entry["content"] = {binary.media_type: no_schema}
        responses[str(code)] = entry
    json_body = route.body_param is not None
    # 403: the origin policy answers before any route runs
    problems = {403, 500} | {error.status for error in spec.errors}
    if parameters or json_body:
        problems.add(422)
    if placeholders:
        problems.add(404)
    if spec.method.upper() in _MUTATING:
        problems |= {409, 415}  # 415: any non-JSON body on an unsafe method
    if json_body:
        problems |= {400, 413}  # 413: the body is over the server's size limit
    for code in problems:
        responses[str(code)] = {
            "description": HTTPStatus(code).phrase,
            "content": {"application/problem+json": {"schema": {"$ref": _PROBLEM_REF}}},
        }
    operation["responses"] = responses
    return operation


def _request_body(
    route: BoundRoute,
    schemas: dict[tuple[str, JsonSchemaMode], JsonSchemaValue],
    components: dict[str, JsonSchemaValue],
) -> dict[str, object] | None:
    if route.body_param is None:
        return None
    if route.patch_model is not None:
        schema = _add_partial(route.patch_model, components)
    else:
        schema = schemas[(f"body:{route.operation_id}", "validation")]
    return {"required": True, "content": {"application/json": {"schema": schema}}}


def _add_partial(
    model: type[BaseModel], components: dict[str, JsonSchemaValue]
) -> JsonSchemaValue:
    """Register partial_schema(model) as <Name>Partial.

    A $def the partial schema leaves unchanged reuses the existing component
    (an enum, say); only changed defs, and defs that refer to one, get a
    Partial copy.
    """
    raw = json.loads(json.dumps(partial_schema(model)).replace("#/$defs/", _REF_PREFIX))
    defs: dict[str, JsonSchemaValue] = raw.pop("$defs", {})
    root_name = model.__name__
    if set(raw) == {"$ref"}:  # a recursive model: the root is one of the defs
        root_name = raw["$ref"].removeprefix(_REF_PREFIX)
        raw = defs.pop(root_name)
    defs[root_name] = raw
    changed = {
        name
        for name, value in defs.items()
        if name == root_name or components.get(name) != value
    }
    while grew := {
        name
        for name, value in defs.items()
        if name not in changed
        and any(f'"{_REF_PREFIX}{c}"' in json.dumps(value) for c in changed)
    }:
        changed |= grew
    for name in changed:
        text = json.dumps(defs[name])
        for other in changed:
            text = text.replace(
                f'"{_REF_PREFIX}{other}"', f'"{_REF_PREFIX}{other}Partial"'
            )
        value = json.loads(text)
        if components.setdefault(f"{name}Partial", value) != value:
            raise BuildError(
                f"component name {name + 'Partial'!r} is used by two different schemas"
            )
    return {"$ref": _REF.format(model=f"{root_name}Partial")}


def _is_array(schema: JsonSchemaValue) -> bool:
    branches = [schema, *schema.get("anyOf", [])]
    return any(isinstance(b, dict) and b.get("type") == "array" for b in branches)


def _check_component_names(adapters: Iterable[TypeAdapter[object]]) -> None:
    """pydantic silently renames colliding components, so refuse them."""
    seen: dict[str, type] = {}

    def walk(node: object) -> None:
        if isinstance(node, dict):
            cls = node.get("cls")
            if node.get("type") in _NAMED and isinstance(cls, type):
                other = seen.setdefault(cls.__name__, cls)
                if other is not cls:
                    raise BuildError(
                        f"component name {cls.__name__!r} is used by"
                        f" {_qualname(other)} and {_qualname(cls)}"
                    )
            for value in node.values():
                walk(value)
        elif isinstance(node, (list, tuple)):
            for value in node:
                walk(value)

    for adapter in adapters:
        walk(adapter.core_schema)


def _qualname(cls: type) -> str:
    return f"{cls.__module__}.{cls.__qualname__}"
