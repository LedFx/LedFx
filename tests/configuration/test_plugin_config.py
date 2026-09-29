from typing import Annotated, Literal

import pytest
from pydantic import Field, ValidationError

from ledfx.configuration.fields import (
    X_LEGACY,
    X_OMIT_DEFAULT,
    X_REQUIRED,
    CoercedFloat,
    Color,
    OneOf,
)
from ledfx.configuration.plugin import PluginConfig, TypedConfig


class Demo(PluginConfig):
    speed: CoercedFloat = Field(1.0, description="Speed", ge=0, le=10)
    color: Color = Field("red")
    mode: Literal["a", "b"] = Field("a")
    name: str = Field(json_schema_extra={X_REQUIRED: True})
    advanced: bool | None = Field(
        None, json_schema_extra={X_OMIT_DEFAULT: True, X_LEGACY: {"description": False}}
    )


def test_declared_model_keeps_semantics() -> None:
    cfg = Demo.model_validate({"name": "x", "speed": "2"})
    assert cfg.speed == 2.0 and cfg.color == "#ff0000"
    with pytest.raises(ValidationError):
        Demo.model_validate({"name": "x", "mode": "c"})
    with pytest.raises(ValidationError):
        Demo.model_validate({})


def test_ui_only_keys_are_preserved() -> None:
    # Review Focus 1: frontend stores undeclared keys like gradient_name
    cfg = Demo.model_validate({"name": "x", "gradient_name": "Rainbow"})
    assert cfg.as_dict()["gradient_name"] == "Rainbow"
    assert cfg.model_extra is not None
    assert cfg.model_extra["gradient_name"] == "Rainbow"


def test_as_dict_omits_unset_optional_keys_like_voluptuous() -> None:
    cfg = Demo.model_validate({"name": "x"})
    assert "advanced" not in cfg.as_dict()
    assert cfg.advanced is None


def test_frozen_and_with_values_validates() -> None:
    cfg = Demo.model_validate({"name": "x"})
    with pytest.raises(ValidationError):
        cfg.speed = 5  # pyrefly: ignore[read-only]
    assert cfg.with_values(speed=4).speed == 4.0
    with pytest.raises(ValidationError):
        cfg.with_values(speed=40)


def test_empty_one_of_does_not_crash() -> None:
    class Ports(PluginConfig):
        com_port: Annotated[str, OneOf([])] = Field("")

    assert "enum" in Ports.model_json_schema()["properties"]["com_port"]


def test_typed_config_descriptor_returns_instance_config() -> None:
    class Holder:
        class Config(PluginConfig):
            level: int = 1

        config = TypedConfig(Config)

        def __init__(self) -> None:
            self._config = Holder.Config()

    holder = Holder()
    assert holder.config.level == 1
    assert isinstance(Holder.config, TypedConfig)
    with pytest.raises(AttributeError):
        holder.config = Holder.Config()  # type: ignore[misc]


def test_redeclared_key_moves_to_subclass_position() -> None:
    # The order voluptuous' Schema.extend produced, which the snapshots pin.
    class Base(PluginConfig):
        a: int = 1
        b: int = 2

    class Child(Base):
        a: int = 3
        c: int = 4

    assert list(Child.model_fields) == ["b", "a", "c"]


def test_typed_config_before_init_is_a_missing_attribute() -> None:
    class Holder:
        config = TypedConfig(PluginConfig)

    holder = object.__new__(Holder)
    assert getattr(holder, "config", None) is None
    assert not hasattr(holder, "config")
