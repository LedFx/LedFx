import pytest
import voluptuous as vol
from pydantic import ValidationError

from ledfx.color import validate_color
from ledfx.configuration.plugin import PluginConfig, TypedConfig, vol_to_model

SCHEMA = vol.Schema(
    {
        vol.Optional("speed", description="Speed", default=1.0): vol.All(
            vol.Coerce(float), vol.Range(min=0, max=10)
        ),
        vol.Optional("color", default="red"): validate_color,
        vol.Optional("mode", default="a"): vol.In(["a", "b"]),
        vol.Required("name"): str,
        vol.Optional("advanced", description=False): bool,
    }
)


def test_vol_to_model_keeps_semantics() -> None:
    model = vol_to_model("Demo", SCHEMA)
    cfg = model.model_validate({"name": "x", "speed": "2"})
    assert cfg["speed"] == 2.0 and cfg["color"] == "#ff0000"
    with pytest.raises(ValidationError):
        model.model_validate({"name": "x", "mode": "c"})
    with pytest.raises(ValidationError):
        model.model_validate({})


def test_ui_only_keys_are_preserved() -> None:
    # Review Focus 1: frontend stores undeclared keys like gradient_name
    model = vol_to_model("Demo", SCHEMA)
    cfg = model.model_validate({"name": "x", "gradient_name": "Rainbow"})
    assert cfg.as_dict()["gradient_name"] == "Rainbow"
    assert cfg["gradient_name"] == "Rainbow"


def test_as_dict_omits_unset_optional_keys_like_voluptuous() -> None:
    cfg = vol_to_model("Demo", SCHEMA).model_validate({"name": "x"})
    assert "advanced" not in cfg.as_dict()
    assert "advanced" not in cfg and cfg.get("advanced", 5) == 5
    with pytest.raises(KeyError):
        cfg["advanced"]


def test_mapping_shim_supports_merge_idiom() -> None:
    cfg = vol_to_model("Demo", SCHEMA).model_validate({"name": "x"})
    merged = dict(cfg) | {"speed": 3}  # dict()/** use keys() + __getitem__
    assert merged["speed"] == 3 and merged["name"] == "x"
    assert dict(cfg) == cfg.as_dict()


def test_frozen_and_with_values_validates() -> None:
    cfg = vol_to_model("Demo", SCHEMA).model_validate({"name": "x"})
    with pytest.raises(ValidationError):
        cfg.speed = 5
    assert cfg.with_values(speed=4)["speed"] == 4.0
    with pytest.raises(ValidationError):
        cfg.with_values(speed=40)


def test_empty_in_container_does_not_crash() -> None:
    model = vol_to_model(
        "Ports", vol.Schema({vol.Required("com_port", default=""): vol.In([])})
    )
    assert "enum" in model.model_json_schema()["properties"]["com_port"]


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


def test_redeclared_key_moves_to_subclass_position_like_schema_extend() -> None:
    parent = vol.Schema(
        {vol.Optional("a", default=1): int, vol.Optional("b", default=2): int}
    )
    child = {vol.Optional("a", default=3): int, vol.Optional("c", default=4): int}
    expected = [k.schema for k in parent.extend(child).schema]

    class Base(PluginConfig):
        a: int = 1
        b: int = 2

    class Child(Base):
        a: int = 3
        c: int = 4

    assert list(Child.model_fields) == expected == ["b", "a", "c"]
    assert (
        list(vol_to_model("Auto", vol.Schema(child), (Base,)).model_fields) == expected
    )


def test_typed_config_before_init_is_a_missing_attribute() -> None:
    class Holder:
        config = TypedConfig(PluginConfig)

    holder = object.__new__(Holder)
    assert getattr(holder, "config", None) is None
    assert not hasattr(holder, "config")


def test_extra_keys_named_like_model_attributes_return_stored_values() -> None:
    cfg = vol_to_model("Demo", SCHEMA).model_validate(
        {"name": "x", "keys": "k", "get": "g"}
    )
    assert cfg["keys"] == "k" and cfg.get("get") == "g"
    assert "keys" in cfg and "get" in cfg and "copy" not in cfg
    assert cfg.get("copy", 5) == 5
    merged = dict(cfg)  # same keys() + __getitem__ path as {**cfg}
    assert merged["keys"] == "k" and merged["get"] == "g"
    keys = cfg.keys()
    assert {"keys", "get"} <= set(keys) and all(k in cfg for k in keys)


def test_list_item_constraints_precede_coercion() -> None:
    model = vol_to_model(
        "Items",
        vol.Schema(
            {
                vol.Optional("xs", default=[1]): [
                    vol.All(vol.Coerce(int), vol.Range(min=0, max=9))
                ]
            }
        ),
    )
    items = model.model_json_schema()["properties"]["xs"]["items"]
    assert items["minimum"] == 0 and items["maximum"] == 9
    assert "ge" not in items and "le" not in items
    assert model.model_validate({"xs": ["3", 4.7]})["xs"] == [3, 4]
    with pytest.raises(ValidationError):
        model.model_validate({"xs": [10]})
