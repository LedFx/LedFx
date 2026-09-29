from typing import Annotated

import pytest
from pydantic import BaseModel, Field, ValidationError

from ledfx.configuration.fields import (
    RUNTIME_CONTEXT,
    X_ENUM_SOURCE,
    X_OMIT_DEFAULT,
    AudioDeviceIndex,
    CoercedFloat,
    CoercedInt,
    Color,
    EnumSource,
    Fps,
    IPv4,
    OneOf,
    coerce,
    fps_validator,
    register_enum_source,
)
from ledfx.configuration.models import LedFxModel, validate_dict
from ledfx.utils import AVAILABLE_FPS


class Sample(LedFxModel):
    count: CoercedInt = Field(3, ge=0, le=10)
    ratio: CoercedFloat = Field(0.5, ge=0, le=1)
    color: Color = "red"
    fps: Fps = 60
    ip: IPv4 = "255.255.255.255"
    mode: Annotated[str, OneOf(["a", "b"])] = "a"
    label: str | None = Field(None, json_schema_extra={X_OMIT_DEFAULT: True})


def test_coerce_matches_voluptuous_truncation() -> None:
    assert Sample(count=1.7).count == 1
    assert Sample(count="4").count == 4
    with pytest.raises(ValidationError):
        Sample(count="abc")


def test_defaults_are_validated_and_normalised() -> None:
    assert Sample().color == "#ff0000"


def test_range_rejects_out_of_bounds() -> None:
    with pytest.raises(ValidationError):
        Sample(ratio=1.5)


def test_fps_clamps_up_to_available_rate() -> None:
    assert Sample(fps=1).fps == fps_validator(1)
    assert fps_validator(10**6) == list(AVAILABLE_FPS)[-1]
    with pytest.raises(ValidationError):
        Sample(fps="60")


def test_ipv4() -> None:
    with pytest.raises(ValidationError):
        Sample(ip="999.1.1.1")


def test_one_of_validates_and_emits_enum() -> None:
    with pytest.raises(ValidationError):
        Sample(mode="c")
    assert Sample.model_json_schema()["properties"]["mode"]["enum"] == ["a", "b"]


def test_one_of_reevaluates_callable_options() -> None:
    options = ["x"]

    class Dyn(LedFxModel):
        v: Annotated[str, OneOf(lambda: options)] = "x"

    options.append("y")
    assert Dyn(v="y").v == "y"
    assert Dyn.model_json_schema()["properties"]["v"]["enum"] == ["x", "y"]


def test_constraints_emit_standard_keywords() -> None:
    class Items(BaseModel):
        values: list[Annotated[int, Field(ge=0, le=5), coerce(int)]] = [1]

    items = Items.model_json_schema()["properties"]["values"]["items"]
    assert items["minimum"] == 0 and items["maximum"] == 5


@pytest.fixture
def audio_source():
    from ledfx.configuration import fields

    previous = fields._ENUM_SOURCES.get("audio_devices")
    register_enum_source(
        "audio_devices",
        EnumSource(options=lambda: {0: "Default"}, validate=lambda v: 0),
    )
    yield
    if previous is None:
        fields._ENUM_SOURCES.pop("audio_devices", None)
    else:
        register_enum_source("audio_devices", previous)


def test_enum_source_hook_runs_only_at_runtime(audio_source: None) -> None:
    class Audio(LedFxModel):
        device: AudioDeviceIndex = None

    assert Audio(device=99).device == 99  # load: stored value untouched
    assert Audio.model_validate({"device": 99}, context=RUNTIME_CONTEXT).device == 0
    assert validate_dict(Audio, {"device": 99}, runtime=True)["device"] == 0
    schema = Audio.model_json_schema()["properties"]["device"]
    assert schema[X_ENUM_SOURCE] == "audio_devices"


def test_unset_optionals_are_dropped_from_every_dump() -> None:
    out = validate_dict(Sample, {})
    assert "label" not in out
    assert "label" not in Sample().model_dump(mode="json")
    assert validate_dict(Sample, {"label": "x"})["label"] == "x"


def test_titles_use_generate_title() -> None:
    assert Sample.model_json_schema()["properties"]["count"]["title"] == "Count"
