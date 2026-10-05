"""Tests for the MQTT Home Assistant integration."""

import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ledfx.errors import SafeMode
from ledfx.events import EffectSetEvent
from ledfx.integrations.mqtt_hass import MQTT_HASS


def _integration(effects: dict[str, object]) -> MQTT_HASS:
    integration = MQTT_HASS.__new__(MQTT_HASS)
    integration._active = False  # Integration.__del__ reads it
    integration._config = SimpleNamespace(topic="ledfx")
    integration._ledfx = MagicMock()
    integration._ledfx.effects = effects
    # By the time the listener runs, a scene change has replaced the
    # virtual's active effect with one that has no colour.
    integration._ledfx.virtuals.get.return_value.active_effect = SimpleNamespace(
        config=SimpleNamespace()
    )
    return integration


def _event() -> EffectSetEvent:
    return EffectSetEvent(
        "Single Color", "singleColor", "strip", "singleColor", True, False
    )


def test_single_color_publishes_the_event_effect_colour() -> None:
    effect = SimpleNamespace(config=SimpleNamespace(color="#ff0000"))
    client = MagicMock()

    _integration({"singleColor": effect}).publish_single_color(client, _event())

    topic, payload = client.publish.call_args.args
    assert topic == "ledfx/light/strip/state"
    assert json.loads(payload) == {
        "state": "on",
        "color": [255, 0, 0],
        "effect": "#ff0000",
    }


@pytest.mark.parametrize(
    "effects",
    [{}, {"singleColor": SimpleNamespace(config=SimpleNamespace())}],
    ids=["effect-gone", "no-color"],
)
def test_single_color_skips_effect_without_colour(effects: dict[str, object]) -> None:
    client = MagicMock()

    _integration(effects).publish_single_color(client, _event())

    client.publish.assert_not_called()


@pytest.mark.parametrize(
    "publish", ["publish_virtual_config", "publish_virtual_paused"]
)
def test_virtual_listeners_ignore_a_virtual_deleted_since(publish: str) -> None:
    integration = _integration({})
    integration._ledfx.virtuals.get.return_value = None
    client = MagicMock()

    getattr(integration, publish)("gone", client)

    client.publish.assert_not_called()


def test_the_pause_listener_ignores_a_virtual_deleted_since() -> None:
    from ledfx.events import Event

    integration = _integration({})
    integration._ledfx.virtuals.get.return_value = None
    integration._listeners = []
    client = MagicMock()
    integration._handle_connect(client, 0)
    listener = next(
        call.args[0]
        for call in integration._ledfx.events.add_listener.call_args_list
        if call.args[1] == Event.VIRTUAL_PAUSE
    )
    client.reset_mock()

    listener(SimpleNamespace(virtual_id="gone"))

    client.publish.assert_not_called()


def test_scene_select_in_safe_mode_is_logged_at_debug(
    caplog: pytest.LogCaptureFixture,
) -> None:
    integration = _integration({})
    integration._client = MagicMock()
    integration._ledfx.scenes.activate.side_effect = SafeMode("read-only")
    msg = SimpleNamespace(topic="ha/select/ledfxsceneselect/set", payload=b"party")
    integration._config = SimpleNamespace(topic="ha")

    with caplog.at_level(logging.DEBUG):
        integration._handle_message(msg)

    integration._ledfx.scenes.activate.assert_called_once_with("party")
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING]
    assert any("safe mode" in r.getMessage() for r in caplog.records)
