from typing import Annotated, cast

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


def test_coerce_overflow_is_a_validation_error() -> None:
    # int(inf) and float(10**400) raise OverflowError, not ValueError.
    with pytest.raises(ValidationError):
        Sample(count=float("inf"))
    with pytest.raises(ValidationError):
        Sample(ratio=10**400)


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
def audio_source(monkeypatch: pytest.MonkeyPatch) -> None:
    from ledfx.configuration import fields
    from ledfx.effects import audio  # noqa: F401 - registers the real source first

    monkeypatch.setitem(
        fields._ENUM_SOURCES,
        "audio_devices",
        EnumSource(options=lambda: {0: "Default"}, validate=lambda v: 0),
    )


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


def test_runtime_audio_hook_sees_the_coerced_int(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from ledfx.configuration.models import AudioInputConfig
    from ledfx.effects.audio import AudioInputSource

    devices = {1: "One", 4: "Four"}
    monkeypatch.setattr(
        AudioInputSource, "input_devices", staticmethod(lambda: devices)
    )
    monkeypatch.setattr(
        AudioInputSource, "default_device_index", staticmethod(lambda: 1)
    )

    def device(value: object, runtime: bool) -> object:
        context = RUNTIME_CONTEXT if runtime else None
        config = AudioInputConfig.model_validate(
            {"audio_device": value}, context=context
        )
        return config.audio_device

    assert device("4", runtime=True) == 4  # was the default: checked before int()
    # The rest is as before: load keeps the value, runtime falls back to default.
    results = [device(v, rt) for v in (None, 4, 99, True) for rt in (False, True)]
    assert results == [None, 1, 4, 4, 99, 1, 1, 1]


def test_validate_color_takes_only_a_string() -> None:
    from ledfx.color import coerce_color, validate_color

    assert validate_color("red") == "#ff0000"
    with pytest.raises(ValueError, match="Invalid color: "):
        validate_color(cast("str", [1, 2, 3]))
    assert coerce_color([1, 2, 3]) == "#010203"
    assert coerce_color((1, 2, 3)) == "#010203"
    assert coerce_color("red") == "#ff0000"
    for bad in ([1, 2], 5, None, {"a": 1}):
        with pytest.raises(ValueError, match="Invalid color: "):
            coerce_color(bad)


def test_the_color_field_still_loads_a_list() -> None:
    """Old configs and v1 send [r, g, b]; the load path stays lenient."""
    assert Sample.model_validate({"color": [1, 2, 3]}).color == "#010203"


def test_the_v2_color_type_refuses_a_list() -> None:
    from pydantic import TypeAdapter

    from ledfx.api.v2.models.virtuals import ColorStr

    with pytest.raises(ValidationError):
        TypeAdapter(ColorStr).validate_python([1, 2, 3])
