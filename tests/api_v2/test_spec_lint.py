"""Spec lint: closed request schemas, no empty schemas, bounded inputs, Problem errors.

Response schemas stay open on purpose: new response fields are additive.

Runs over the spec built with every plugin registry loaded, so later layers'
routes and plugin variants are linted as they land.
"""

from collections.abc import Iterator
from functools import cache
from pathlib import Path

import openapi_spec_validator
import pytest

from ledfx.api.v2.core.registry import build_standalone_spec
from ledfx.configuration.jsonshape import as_dict, as_list

ALLOWLIST_PATH = Path(__file__).with_name("open_schema_allowlist.txt")
PROBLEM_REF = "#/components/schemas/Problem"
_ANNOTATIONS = frozenset(
    {
        "title",
        "description",
        "default",
        "examples",
        "deprecated",
        "readOnly",
        "writeOnly",
        "$comment",
    }
)
# JSON Schema 2020-12 applicators: one subschema, a list, or a map of them.
_ONE = (
    "items",
    "additionalProperties",
    "not",
    "if",
    "then",
    "else",
    "contains",
    "propertyNames",
    "unevaluatedItems",
    "unevaluatedProperties",
)
_MANY = ("anyOf", "oneOf", "allOf", "prefixItems")
_NAMED = ("properties", "patternProperties", "$defs", "dependentSchemas")
_METHODS = ("get", "put", "post", "delete", "patch")

Found = tuple[str, dict[str, object]]  # (JSON pointer, schema)


def _esc(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def _walk(node: dict[str, object], pointer: str) -> Iterator[Found]:
    """node and every schema below it, with JSON pointers."""
    yield pointer, node
    children: list[Found] = []
    for key in _ONE:
        if isinstance(child := node.get(key), dict):
            children.append((f"{pointer}/{key}", as_dict(child)))
    for key in _MANY:
        for i, child in enumerate(as_list(node.get(key))):
            if isinstance(child, dict):
                children.append((f"{pointer}/{key}/{i}", as_dict(child)))
    for key in _NAMED:
        for name, child in as_dict(node.get(key)).items():
            if isinstance(child, dict):
                children.append((f"{pointer}/{key}/{_esc(name)}", as_dict(child)))
    for child_pointer, child in children:
        yield from _walk(child, child_pointer)


def _operations(spec: dict[str, object]) -> Iterator[Found]:
    for path, item in as_dict(spec.get("paths")).items():
        for method, operation in as_dict(item).items():
            if method in _METHODS:
                yield f"/paths/{_esc(path)}/{method}", as_dict(operation)


def _input_roots(spec: dict[str, object]) -> Iterator[Found]:
    for pointer, operation in _operations(spec):
        for i, param in enumerate(as_list(operation.get("parameters"))):
            yield (
                f"{pointer}/parameters/{i}/schema",
                as_dict(as_dict(param).get("schema")),
            )
        content = as_dict(as_dict(operation.get("requestBody")).get("content"))
        for media, entry in content.items():
            schema = as_dict(as_dict(entry).get("schema"))
            yield f"{pointer}/requestBody/content/{_esc(media)}/schema", schema


def _all_roots(spec: dict[str, object]) -> Iterator[Found]:
    yield from _input_roots(spec)
    for pointer, operation in _operations(spec):
        for code, response in as_dict(operation.get("responses")).items():
            for media, entry in as_dict(as_dict(response).get("content")).items():
                if "schema" in as_dict(entry):  # Binary content has no schema
                    schema = as_dict(as_dict(entry).get("schema"))
                    yield (
                        f"{pointer}/responses/{code}/content/{_esc(media)}/schema",
                        schema,
                    )
    for name, schema in _components(spec).items():
        yield f"/components/schemas/{_esc(name)}", as_dict(schema)


def _components(spec: dict[str, object]) -> dict[str, object]:
    return as_dict(as_dict(spec.get("components")).get("schemas"))


def _inputs(spec: dict[str, object]) -> Iterator[Found]:
    """Every request-input schema, following $refs (each component once)."""
    seen: set[str] = set()
    stack = list(_input_roots(spec))
    while stack:
        root, schema = stack.pop()
        for pointer, node in _walk(schema, root):
            ref = node.get("$ref")
            if isinstance(ref, str) and ref not in seen:
                seen.add(ref)
                name = ref.removeprefix("#/components/schemas/")
                target = as_dict(_components(spec).get(name))
                stack.append((f"/components/schemas/{_esc(name)}", target))
            yield pointer, node


def _types(node: dict[str, object]) -> set[object]:
    kind = node.get("type")
    return set(as_list(kind)) if isinstance(kind, list) else {kind}


def _unbounded(node: dict[str, object]) -> str | None:
    if "enum" in node or "const" in node:
        return None
    types, keys = _types(node), node.keys()
    low, high = {"minimum", "exclusiveMinimum"}, {"maximum", "exclusiveMaximum"}
    if types & {"integer", "number"} and not (low & keys and high & keys):
        return "number without a lower and an upper bound"
    if "string" in types and not {"maxLength", "pattern", "format"} & keys:
        return "string without maxLength, pattern, enum, const or format"
    if "array" in types and "maxItems" not in keys:
        return "array without maxItems"
    return None


def lint(spec: dict[str, object], allow: frozenset[str]) -> list[str]:
    """Every rule violation in spec, as 'pointer: reason' lines."""
    found: set[str] = set()
    for root, schema in _all_roots(spec):
        for pointer, node in _walk(schema, root):
            if pointer in allow:
                continue
            if all(key in _ANNOTATIONS or key.startswith("x-") for key in node):
                found.add(f"{pointer}: empty schema")
    for pointer, node in _inputs(spec):
        if pointer in allow:
            continue
        if ("object" in _types(node) or "properties" in node) and node.get(
            "additionalProperties"
        ) is not False:
            found.add(f"{pointer}: open object (additionalProperties is not false)")
        elif why := _unbounded(node):
            found.add(f"{pointer}: {why}")
    for pointer, operation in _operations(spec):
        for code, response in as_dict(operation.get("responses")).items():
            if code.startswith(("4", "5")):
                content = as_dict(as_dict(response).get("content"))
                schema = as_dict(
                    as_dict(content.get("application/problem+json")).get("schema")
                )
                if schema.get("$ref") != PROBLEM_REF:
                    found.add(f"{pointer}/responses/{code}: not a Problem")
    return sorted(found)


def load_allowlist() -> frozenset[str]:
    """Pointers from the allowlist: one 'pointer<TAB>reason' per line, # comments."""
    lines = ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines()
    entries = [line for line in lines if line.strip() and not line.startswith("#")]
    for entry in entries:
        pointer, _, reason = entry.partition("\t")
        assert pointer.startswith("/") and reason.strip(), (
            f"bad allowlist line: {entry!r}"
        )
    return frozenset(entry.partition("\t")[0] for entry in entries)


@cache
def _spec() -> dict[str, object]:
    return build_standalone_spec()


def test_spec_passes_the_lint() -> None:
    assert lint(_spec(), load_allowlist()) == []


def test_spec_is_valid_openapi() -> None:
    openapi_spec_validator.validate(_spec())


def _toy(
    schema: dict[str, object], *, response: dict[str, object] | None = None
) -> dict[str, object]:
    """A one-route spec whose request body is schema."""
    problem = {"application/problem+json": {"schema": {"$ref": PROBLEM_REF}}}
    responses = {"500": response or {"description": "x", "content": problem}}
    body = {"content": {"application/json": {"schema": schema}}}
    return {"paths": {"/t": {"post": {"requestBody": body, "responses": responses}}}}


BODY = "/paths/~1t/post/requestBody/content/application~1json/schema"


@pytest.mark.parametrize(
    ("schema", "expected"),
    [
        ({"title": "Anything"}, f"{BODY}: empty schema"),
        (
            {"type": "object", "properties": {}},
            f"{BODY}: open object (additionalProperties is not false)",
        ),
        (
            {"type": "integer", "minimum": 0},
            f"{BODY}: number without a lower and an upper bound",
        ),
        (
            {"type": "string"},
            f"{BODY}: string without maxLength, pattern, enum, const or format",
        ),
        (
            {"type": "array", "items": {"type": "boolean"}},
            f"{BODY}: array without maxItems",
        ),
    ],
)
def test_each_rule_fires(schema: dict[str, object], expected: str) -> None:
    assert lint(_toy(schema), frozenset()) == [expected]
    assert lint(_toy(schema), frozenset({BODY})) == []


def test_bounds_are_checked_through_refs() -> None:
    spec = _toy({"$ref": "#/components/schemas/N"})
    spec["components"] = {"schemas": {"N": {"type": "number", "maximum": 1}}}
    assert lint(spec, frozenset()) == [
        "/components/schemas/N: number without a lower and an upper bound"
    ]


def test_bounded_inputs_pass() -> None:
    bounded: dict[str, object] = {"type": "string", "maxLength": 3}
    assert lint(_toy(bounded), frozenset()) == []


def test_error_responses_must_be_problems() -> None:
    spec = _toy({"type": "boolean"}, response={"description": "x"})
    assert lint(spec, frozenset()) == ["/paths/~1t/post/responses/500: not a Problem"]


def test_response_objects_may_stay_open() -> None:
    spec = _toy({"type": "boolean"})
    open_object: dict[str, object] = {"type": "object", "properties": {}}
    responses = as_dict(as_dict(as_dict(spec["paths"])["/t"])["post"])["responses"]
    as_dict(responses)["200"] = {
        "description": "x",
        "content": {"application/json": {"schema": open_object}},
    }
    assert lint(spec, frozenset()) == []
