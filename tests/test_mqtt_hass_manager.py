"""MQTT Home Assistant commands change virtuals only through the Virtuals
manager."""

import inspect
import json
import logging
from collections.abc import Iterator
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import ledfx.integrations.mqtt_hass as hass_module
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import Preset
from ledfx.integrations.mqtt_hass import MQTT_HASS
from ledfx.virtuals import Virtual
from tests.test_utilities.virtuals_core import enter_safe_mode, running_core

BIRD = VirtualIdStr("dj bird")


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    monkeypatch.setattr(hass_module, "extract_ip", lambda: "127.0.0.1")
    yield from running_core(monkeypatch)


@pytest.fixture
def integration(ledfx: MagicMock) -> MQTT_HASS:
    integration = MQTT_HASS.__new__(MQTT_HASS)
    integration._active = False  # Integration.__del__ reads it
    integration._config = SimpleNamespace(topic="ha")
    integration._client = MagicMock()
    integration._ledfx = ledfx
    return integration


def send(integration: MQTT_HASS, target: str, payload: object) -> None:
    integration._handle_message(
        SimpleNamespace(
            topic=f"ha/light/{target}/set", payload=json.dumps(payload).encode()
        )
    )


def running(ledfx: MagicMock, virtual_id: str) -> str | None:
    effect = ledfx.virtuals.get_or_raise(VirtualIdStr(virtual_id)).active_effect
    return effect.type if effect else None


def test_a_colour_sets_the_effect_and_the_state(
    ledfx: MagicMock, integration: MQTT_HASS
) -> None:
    send(integration, "dj bird", {"state": "on", "color": [255, 0, 0]})

    bird = ledfx.virtuals.get_or_raise(BIRD)
    assert running(ledfx, "dj bird") == "singleColor"
    assert bird.active_effect.config.color == "#ff0000"
    assert bird.active is True
    assert bird.entry is not None
    assert bird.entry.active is True
    assert bird.entry.effect is not None
    assert bird.entry.effect.config == {**bird.active_effect.config.as_dict()}
    ledfx.config_store.request_save.assert_called()

    send(integration, "dj bird", {"state": "off", "color": [0, 255, 0]})
    assert bird.active is False


def test_an_effect_is_applied(ledfx: MagicMock, integration: MQTT_HASS) -> None:
    send(integration, "dj bird", {"state": "on", "effect": "rainbow"})
    assert running(ledfx, "dj bird") == "rainbow"


def test_a_system_preset_is_applied(ledfx: MagicMock, integration: MQTT_HASS) -> None:
    send(integration, "dj bird", {"state": "on", "effect": "rainbow"})
    bird = ledfx.virtuals.get_or_raise(BIRD)
    assert bird.active_effect.config.blur != 7.7

    send(integration, "dj bird", {"state": "on", "effect": "cascade"})

    assert running(ledfx, "dj bird") == "rainbow"
    assert bird.active_effect.config.blur == 7.7
    assert bird.active_effect.config.speed == 0.3
    assert bird.entry is not None
    assert bird.entry.effect is not None
    assert bird.entry.effect.config["blur"] == 7.7


def test_a_user_preset_is_applied(ledfx: MagicMock, integration: MQTT_HASS) -> None:
    ledfx.config.user_presets["rainbow"] = {
        "mine": Preset(name="mine", config={"blur": 3.3, "speed": 2.2})
    }
    send(integration, "dj bird", {"state": "on", "effect": "rainbow"})

    send(integration, "dj bird", {"state": "on", "effect": "mine"})

    bird = ledfx.virtuals.get_or_raise(BIRD)
    assert bird.active_effect.config.blur == 3.3
    assert bird.active_effect.config.speed == 2.2


def test_a_refusing_virtual_leaks_no_effect(
    ledfx: MagicMock, integration: MQTT_HASS, caplog: pytest.LogCaptureFixture
) -> None:
    before = len(ledfx.effects.values())

    with caplog.at_level(logging.DEBUG):
        send(integration, "empty", {"state": "on", "color": [255, 0, 0]})
        send(integration, "empty", {"state": "on", "effect": "rainbow"})

    assert len(ledfx.effects.values()) == before
    assert running(ledfx, "empty") is None
    warnings = [
        r
        for r in caplog.records
        if r.name == hass_module.__name__ and r.levelno >= logging.WARNING
    ]
    assert [r.levelno for r in warnings] == [logging.WARNING, logging.WARNING]


def test_a_bad_colour_is_a_warning_and_changes_nothing(
    ledfx: MagicMock, integration: MQTT_HASS, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        send(integration, "dj bird", {"state": "on", "color": "not a colour"})

    assert running(ledfx, "dj bird") is None
    assert [r.levelno for r in caplog.records] == [logging.WARNING]


def test_safe_mode_changes_nothing_and_logs_at_debug(
    ledfx: MagicMock, integration: MQTT_HASS, caplog: pytest.LogCaptureFixture
) -> None:
    send(integration, "dj bird", {"state": "on", "color": [255, 0, 0]})
    enter_safe_mode(ledfx)
    bird = ledfx.virtuals.get_or_raise(BIRD)
    stored = bird.entry.model_copy(deep=True) if bird.entry else None
    before = bird.config

    with caplog.at_level(logging.DEBUG):
        send(integration, "dj bird", {"state": "off", "color": [0, 0, 255]})
        send(integration, "dj bird", {"state": "on", "effect": "rainbow"})
        for target, value in (
            ("ledfxtransitiontype", "Push"),
            ("ledfxtransitiontime", "2"),
        ):
            integration._handle_message(
                SimpleNamespace(topic=f"ha/number/{target}/set", payload=value.encode())
            )

    assert running(ledfx, "dj bird") == "singleColor"
    assert bird.active_effect.config.color == "#ff0000"
    assert bird.active is True
    assert bird.entry == stored
    assert bird.config == before
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("safe mode" in r.getMessage() for r in caplog.records)


def test_a_transition_applies_to_every_virtual_without_a_leaked_toggle(
    ledfx: MagicMock, integration: MQTT_HASS
) -> None:
    ledfx.config.global_transitions = False

    for target, value in (
        ("ledfxtransitiontype", "Add"),
        ("ledfxtransitiontime", "1.5"),
    ):
        integration._handle_message(
            SimpleNamespace(topic=f"ha/number/{target}/set", payload=value.encode())
        )

    for virtual in ledfx.virtuals.values():
        assert virtual.config.transition_mode == "Add"
        assert virtual.config.transition_time == 1.5
    assert ledfx.config.global_transitions is False


@pytest.mark.parametrize(
    ("target", "payload"),
    [
        ("ledfxtransitiontype", b"Sideways"),
        ("ledfxtransitiontime", b"abc"),
        ("ledfxtransitiontime", b'{"a": 1}'),
    ],
)
def test_a_bad_transition_is_a_warning(
    ledfx: MagicMock,
    integration: MQTT_HASS,
    caplog: pytest.LogCaptureFixture,
    target: str,
    payload: bytes,
) -> None:
    before = {virtual.id: virtual.config for virtual in ledfx.virtuals.values()}

    with caplog.at_level(logging.WARNING):
        integration._handle_message(
            SimpleNamespace(topic=f"ha/number/{target}/set", payload=payload)
        )

    assert {virtual.id: virtual.config for virtual in ledfx.virtuals.values()} == (
        before
    )
    # One warning for the payload, not one per virtual.
    ours = [r for r in caplog.records if r.name == hass_module.__name__]
    assert [r.levelno for r in ours] == [logging.WARNING]


def test_commands_go_through_the_manager(
    ledfx: MagicMock, integration: MQTT_HASS, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A direct Virtual.set_effect or update_config makes the counts differ."""
    direct: dict[str, list[object]] = {"set_effect": [], "update_config": []}

    def spy(name: str):
        original = getattr(Virtual, name)

        def wrapper(virtual: Virtual, *args: object, **kwargs: object) -> object:
            direct[name].append(virtual.id)
            return original(virtual, *args, **kwargs)

        return wrapper

    managed = {
        name: MagicMock(wraps=getattr(ledfx.virtuals, name))
        for name in ("set_effect", "set_active", "set_config")
    }
    for name in direct:
        monkeypatch.setattr(Virtual, name, spy(name))
    for name, mock in managed.items():
        monkeypatch.setattr(ledfx.virtuals, name, mock)

    send(integration, "dj bird", {"state": "on", "color": [255, 0, 0]})
    send(integration, "dj bird", {"state": "on", "effect": "rainbow"})
    integration._handle_message(
        SimpleNamespace(topic="ha/number/ledfxtransitiontime/set", payload=b"1")
    )

    assert managed["set_effect"].call_count == 2
    assert managed["set_active"].call_count == 1
    assert managed["set_config"].call_count == len(ledfx.virtuals.values())
    # Each manager call reaches the virtual once; nothing reaches it directly.
    assert len(direct["set_effect"]) == 2
    assert direct["update_config"] == []


def test_source_has_no_direct_virtual_changes() -> None:
    source = inspect.getsource(hass_module)
    assert "effects.create(" not in source
    assert "update_config(" not in source.replace("audio.update_config(", "")
    assert "virtual.active =" not in source
    assert "global_transitions" not in source
    assert source.count(".set_effect(") == source.count("virtuals.set_effect(")


def test_a_bad_effect_config_is_one_warning_and_changes_nothing(
    ledfx: MagicMock, integration: MQTT_HASS, caplog: pytest.LogCaptureFixture
) -> None:
    before = len(ledfx.effects.values())
    with caplog.at_level(logging.WARNING):
        send(
            integration,
            "dj bird",
            {"state": "on", "effect": "rainbow", "effect_config": 5},
        )

    assert running(ledfx, "dj bird") is None
    assert len(ledfx.effects.values()) == before
    assert [r.levelno for r in caplog.records] == [logging.WARNING]


def test_a_value_error_from_the_manager_is_not_a_refusal(
    ledfx: MagicMock,
    integration: MQTT_HASS,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    monkeypatch.setattr(
        ledfx.virtuals, "set_effect", MagicMock(side_effect=ValueError("boom"))
    )
    with caplog.at_level(logging.WARNING):
        send(integration, "dj bird", {"state": "on", "color": [255, 0, 0]})

    # An unexpected manager error keeps its traceback.
    assert [r.levelno for r in caplog.records] == [logging.ERROR]
    assert caplog.records[0].exc_info is not None


def test_a_colour_list_with_a_non_number_is_one_warning(
    ledfx: MagicMock, integration: MQTT_HASS, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING):
        send(integration, "dj bird", {"state": "on", "color": [None, 1, 2]})

    assert running(ledfx, "dj bird") is None
    assert [r.levelno for r in caplog.records] == [logging.WARNING]


def test_home_assistant_initialized_with_no_virtuals(
    ledfx: MagicMock, integration: MQTT_HASS, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(ledfx.virtuals, "_virtuals", {})
    monkeypatch.setattr(hass_module.AudioInputSource, "input_devices", MagicMock())
    client = MagicMock()
    integration._client = client

    integration._handle_message(
        SimpleNamespace(topic="ledfx/state", payload=b'"HomeAssistant initialized"')
    )

    published = [c.args[0] for c in client.publish.call_args_list]
    assert "ha/switch/ledfxplay/state" in published
    assert "ha/select/ledfxtransitiontype/state" not in published
