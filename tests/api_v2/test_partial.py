"""Partial[M] bodies and Patch.apply, including Review Focus 1."""

import json
from typing import Annotated

import pytest
from pydantic import BaseModel, ConfigDict, Field

from ledfx.api.v2.core.binding import BuildError, bind
from ledfx.api.v2.core.partial import (
    Partial,
    Patch,
    PatchValidationError,
    partial_schema,
)
from ledfx.api.v2.core.problem import ProblemError
from ledfx.api.v2.core.router import Router
from ledfx.configuration.fields import EnumSource, FromSource, register_enum_source
from tests.api_v2.conftest import ServeRoutes


def _check_colour(value: object) -> object:
    if value == "mauve":
        raise ValueError("not a live colour")
    return value


register_enum_source(
    "v2_patch_colours", EnumSource(options=list, validate=_check_colour)
)


class Inner(BaseModel):
    model_config = ConfigDict(extra="forbid")
    pixel_count: int = Field(ge=1)
    name: str = "strip"
    colour: Annotated[str, FromSource("v2_patch_colours")] = "red"


class Outer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    config: Inner
    segments: list[int] = Field(default_factory=list)
    note: str | None = None
    required: bool = False  # a field called "required" survives partial_schema


class OpenOuter(BaseModel):
    """A stored model that keeps unknown keys, like the v1 plugin configs."""

    model_config = ConfigDict(extra="allow")
    config: Inner
    note: str | None = None


def _current() -> Outer:
    return Outer(config=Inner(pixel_count=10), segments=[1, 2], note="n")


def _patch(body: object) -> Patch[Outer]:
    return Patch.parse(Outer, json.dumps(body).encode())


def test_null_on_a_non_nullable_nested_field_is_422_and_changes_nothing() -> None:
    """Review Focus 1."""
    current = _current()
    before = current.model_dump()
    with pytest.raises(PatchValidationError) as info:
        _patch({"config": {"pixel_count": None}}).apply(current)
    assert info.value.status == 422
    assert info.value.errors is not None
    assert [e.loc for e in info.value.errors] == [["body", "config", "pixel_count"]]
    assert current.model_dump() == before


def test_changed_holds_leaf_paths() -> None:
    patch = _patch({"config": {"pixel_count": 5, "name": "a"}, "segments": [3]})
    assert patch.changed == frozenset(
        {("config", "pixel_count"), ("config", "name"), ("segments",)}
    )


def test_unknown_keys_are_422_at_any_depth() -> None:
    with pytest.raises(ProblemError) as info:
        _patch({"nope": 1, "config": {"pixel_cnt": 2}})
    assert info.value.status == 422
    assert info.value.errors is not None
    assert sorted(e.loc for e in info.value.errors) == [
        ["body", "config", "pixel_cnt"],
        ["body", "nope"],
    ]


def test_a_non_object_body_is_422_and_bad_json_is_400() -> None:
    with pytest.raises(ProblemError) as info:
        Patch.parse(Outer, b"[1]")
    assert info.value.status == 422
    with pytest.raises(ProblemError) as info:
        Patch.parse(Outer, b"{nope")
    assert (info.value.status, info.value.suffix) == (400, "malformed")


def test_nested_objects_merge_lists_replace_and_null_sets_null() -> None:
    updated = _patch(
        {"config": {"pixel_count": 5}, "segments": [9], "note": None}
    ).apply(_current())
    assert updated == Outer(config=Inner(pixel_count=5), segments=[9], note=None)


def test_apply_validates_strictly() -> None:
    with pytest.raises(PatchValidationError) as info:
        _patch({"config": {"pixel_count": "5"}}).apply(_current())
    assert info.value.errors is not None
    assert info.value.errors[0].type == "int_type"


def test_sourced_fields_are_checked_only_when_changed() -> None:
    # Stored before the colour went away: loading doesn't run the source check.
    stored = Outer.model_validate({"config": {"pixel_count": 3, "colour": "mauve"}})
    assert _patch({"config": {"pixel_count": 4}}).apply(stored).config.colour == "mauve"
    with pytest.raises(PatchValidationError) as info:
        _patch({"config": {"colour": "mauve"}}).apply(_current())
    assert info.value.errors is not None
    assert info.value.errors[0].loc == ["body", "config", "colour"]


def test_an_invalid_unchanged_stored_field_is_a_conflict() -> None:
    stored = Outer.model_construct(
        config=Inner.model_construct(pixel_count=0, name="s", colour="red"),
        segments=[],
        note=None,
    )
    with pytest.raises(PatchValidationError) as info:
        _patch({"note": "x"}).apply(stored)
    assert (info.value.status, info.value.suffix) == (409, "conflict")
    assert info.value.stored_field == "config.pixel_count"
    assert info.value.errors is None


def test_a_stored_key_the_model_lacks_is_a_409_naming_it() -> None:
    stored = OpenOuter.model_validate(
        {"config": {"pixel_count": 3}, "gradient_name": "x"}
    )
    patch = _patch({"note": "y"})
    with pytest.raises(PatchValidationError) as info:
        patch.apply(stored)
    assert info.value.stored_field == "gradient_name"


class _Aliased(BaseModel):
    led_count: int = Field(alias="ledCount")


class _Wraps(BaseModel):
    inner: _Aliased | None = None


def test_partial_of_an_aliased_model_is_a_build_error() -> None:
    router = Router(tag="t")

    @router.patch("/x")
    async def patch_x(body: Partial[_Aliased]) -> int:
        return 1

    @router.patch("/y")
    async def patch_y(body: Partial[_Wraps]) -> int:  # alias one level down
        return 1

    for spec in router.routes:
        with pytest.raises(
            BuildError, match=r"can't take aliases \(_Aliased\.led_count"
        ):
            bind(spec)


def test_partial_schema_has_no_required_anywhere() -> None:
    schema = partial_schema(Outer)
    text = json.dumps(schema)
    assert '"required": [' not in text
    defs, properties = schema["$defs"], schema["properties"]
    assert isinstance(defs, dict) and "Inner" in defs
    assert isinstance(properties, dict) and "required" in properties
    assert Outer.model_json_schema()["required"] == ["config"]


async def test_a_patch_route_gets_a_patch(serve_routes: ServeRoutes) -> None:
    router = Router(tag="t")

    @router.patch("/things/{thing_id}")
    async def patch_thing(thing_id: int, body: Partial[Outer]) -> Outer:
        return body.apply(_current())

    route = bind(router.routes[0])
    assert route.body_is_patch
    assert route.patch_model is Outer
    assert route.body_type is Outer
    assert route.body_adapter is None

    client = await serve_routes(router)
    response = await client.patch("/things/1", json={"config": {"name": "b"}})
    assert response.status == 200
    assert (await response.json())["config"] == {
        "pixel_count": 10,
        "name": "b",
        "colour": "red",
    }
    response = await client.patch("/things/x", json={"bogus": 1})
    assert response.status == 422
    assert sorted(e["loc"] for e in (await response.json())["errors"]) == [
        ["body", "bogus"],
        ["path", "thing_id"],
    ]
    response = await client.patch("/things/1", json={"config": {"pixel_count": 0}})
    assert response.status == 422
    response = await client.patch(
        "/things/1", data=b"{", headers={"Content-Type": "application/json"}
    )
    assert response.status == 400


async def test_a_stored_field_conflict_is_a_409_problem(
    serve_routes: ServeRoutes,
) -> None:
    router = Router(tag="t")

    @router.patch("/broken")
    async def patch_broken(body: Partial[Outer]) -> Outer:
        stored = Outer.model_construct(
            config=Inner.model_construct(pixel_count=0, name="s", colour="red"),
            segments=[],
            note=None,
        )
        return body.apply(stored)

    client = await serve_routes(router)
    response = await client.patch("/broken", json={"note": "x"})
    assert response.status == 409
    problem = await response.json()
    assert problem["type"] == "urn:ledfx:problem:conflict"
    assert "config.pixel_count" in problem["detail"]


class MaybeNested(BaseModel):
    model_config = ConfigDict(extra="forbid")
    nested: Inner | None = None


def test_a_partial_object_over_a_stored_none_is_a_422() -> None:
    current = MaybeNested()
    patch = Patch.parse(MaybeNested, b'{"nested": {"name": "a"}}')
    with pytest.raises(PatchValidationError) as info:
        patch.apply(current)
    assert info.value.status == 422
    assert info.value.errors is not None
    assert [e.loc for e in info.value.errors] == [["body", "nested", "pixel_count"]]
    assert current.nested is None


@pytest.mark.parametrize("constant", [b"NaN", b"Infinity", b"-Infinity"])
def test_non_finite_numbers_are_400_malformed(constant: bytes) -> None:
    with pytest.raises(ProblemError) as info:
        Patch.parse(Outer, b'{"segments": [' + constant + b"]}")
    assert (info.value.status, info.value.suffix) == (400, "malformed")


def test_deeply_nested_json_is_400_malformed() -> None:
    with pytest.raises(ProblemError) as info:
        Patch.parse(Outer, b"[" * 100_000 + b"]" * 100_000)
    assert (info.value.status, info.value.suffix) == (400, "malformed")


class Item(BaseModel):
    model_config = ConfigDict(extra="forbid")
    a: int
    b: int = 0


class Holder(BaseModel):
    model_config = ConfigDict(extra="forbid")
    one: Item
    many: list[Item] = []


def test_partial_schema_keeps_required_for_array_items() -> None:
    schema = partial_schema(Holder)
    defs, props = schema["$defs"], schema["properties"]
    assert isinstance(defs, dict) and isinstance(props, dict)
    # Item merges as an object (stripped) and replaces as an array item (whole).
    assert "required" not in defs["Item"]
    assert props["many"]["items"] == {"$ref": "#/$defs/Item__item"}
    assert defs["Item__item"]["required"] == ["a"]
    assert "required" not in schema


def test_partial_schema_item_only_def_keeps_its_name() -> None:
    class OnlyMany(BaseModel):
        many: list[Item] = []

    schema = partial_schema(OnlyMany)
    defs, props = schema["$defs"], schema["properties"]
    assert isinstance(defs, dict) and isinstance(props, dict)
    assert props["many"]["items"] == {"$ref": "#/$defs/Item"}
    assert defs["Item"]["required"] == ["a"]
