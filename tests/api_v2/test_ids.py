"""Typed ids: NewType bases on the shared aliases, constrained v2 aliases."""

import json
import uuid

import pytest
from pydantic import TypeAdapter, ValidationError

from ledfx.api.v2.models.ids import (
    DeviceIdParam,
    JobIdParam,
    VirtualIdParam,
)
from ledfx.configuration.fields import (
    X_ENUM_SOURCE,
    DeviceId,
    PlaylistId,
    SceneId,
    SceneIdStr,
    VirtualId,
    VirtualIdStr,
)
from ledfx.utils import generate_id

ID_PARAMS = [
    VirtualIdParam,
    DeviceIdParam,
]
UNUSUAL_IDS = ["dj bird", "Rainbow-lr", "bass_only", "Küche", "x" * 128]


@pytest.mark.parametrize("param", ID_PARAMS)
@pytest.mark.parametrize("value", UNUSUAL_IDS)
def test_v2_ids_accept_opaque_strings(param: object, value: str) -> None:
    adapter = TypeAdapter[str](param)
    assert adapter.validate_python(value) == value
    assert adapter.validate_json(json.dumps(value), strict=True) == value


@pytest.mark.parametrize("param", ID_PARAMS)
@pytest.mark.parametrize("value", ["", "x" * 129])
def test_v2_ids_reject_empty_and_overlong(param: object, value: str) -> None:
    with pytest.raises(ValidationError):
        TypeAdapter[str](param).validate_python(value)


@pytest.mark.parametrize(
    ("param", "source"),
    [
        (VirtualIdParam, "virtuals"),
        (DeviceIdParam, "devices"),
    ],
)
def test_v2_ids_keep_the_enum_source_marker(param: object, source: str) -> None:
    schema = TypeAdapter[str](param).json_schema()
    assert schema[X_ENUM_SOURCE] == source
    assert (schema["minLength"], schema["maxLength"]) == (1, 128)
    assert "pattern" not in schema


@pytest.mark.parametrize("alias", [VirtualId, DeviceId, SceneId, PlaylistId])
def test_shared_aliases_stay_unconstrained(alias: object) -> None:
    adapter = TypeAdapter[str](alias)
    assert adapter.validate_python("") == ""  # stored configs keep "" defaults
    schema = adapter.json_schema()
    assert schema["type"] == "string"
    assert "minLength" not in schema and "maxLength" not in schema


def test_job_id_is_a_uuid_string() -> None:
    adapter = TypeAdapter[str](JobIdParam)
    job_id = str(uuid.uuid4())
    assert adapter.validate_python(job_id) == job_id
    for bad in [
        "not-a-job",
        "-" * 36,
        "0" * 36,
        "AAAAAAAA-AAAA-4AAA-AAAA-AAAAAAAAAAAA",
    ]:
        with pytest.raises(ValidationError):
            adapter.validate_python(bad)


def test_generate_id_examples() -> None:
    assert generate_id("Küche") == "k-che"
    assert generate_id("DJ Bird") == "dj-bird"


def _virtual_only(virtual_id: VirtualIdStr) -> str:
    return virtual_id


def test_newtype_ids_are_plain_strings_at_runtime() -> None:
    virtual_id = VirtualIdStr("a")
    assert virtual_id == "a"
    assert type(virtual_id) is str
    # Type-checked by pyrefly: a VirtualIdStr is accepted where one is required.
    assert _virtual_only(virtual_id) == "a"


def test_newtype_ids_are_distinct_to_the_type_checker() -> None:
    # pyrefly fails on an unused ignore, so this ignore proves that a scene id
    # is rejected where a virtual id is required.
    assert _virtual_only(SceneIdStr("a")) == "a"  # pyrefly: ignore[bad-argument-type]
