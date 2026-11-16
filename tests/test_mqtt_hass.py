"""Tests for the MQTT Home Assistant integration."""

import json
import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import ledfx.integrations.mqtt_hass as hass_module
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


def test_connect_subscribes_to_the_home_assistant_status_topic() -> None:
    integration = _integration({})
    integration._listeners = []
    client = MagicMock()

    integration._handle_connect(client, 0)

    subscribed = [call.args[0] for call in client.subscribe.call_args_list]
    assert "ledfx/status" in subscribed


@pytest.fixture
def birth_integration(monkeypatch: pytest.MonkeyPatch) -> MQTT_HASS:
    monkeypatch.setattr(
        hass_module.AudioInputSource,
        "input_devices",
        staticmethod(lambda: {0: "Mic"}),
    )
    integration = _integration({})
    integration._ledfx.config.audio.audio_device = 0
    integration._ledfx.scenes._scenes = {"party": SimpleNamespace()}
    integration._ledfx.scenes.is_active.return_value = True
    return integration


def test_an_online_birth_message_republishes_discovery_and_state(
    birth_integration: MQTT_HASS,
) -> None:
    client = MagicMock()
    birth_integration._client = client

    birth_integration._handle_message(
        SimpleNamespace(topic="ledfx/status", payload=b"online")
    )

    # The republish is scheduled after a short random delay, as Home
    # Assistant's MQTT guide recommends, not sent immediately.
    client.publish.assert_not_called()
    delay, callback, scheduled_client = (
        birth_integration._ledfx.loop.call_later.call_args.args
    )
    assert 0 <= delay <= 10
    callback(scheduled_client)

    published = [(call.args[0], call.args[1]) for call in client.publish.call_args_list]
    topics = [topic for topic, _payload in published]
    # Discovery configs, so Home Assistant recreates the entities
    assert "ledfx/select/ledfxsceneselect/config" in topics
    assert "ledfx/switch/ledfxplay/config" in topics
    # Current state, including the scene selector
    assert ("ledfx/select/ledfxsceneselect/state", "party") in published
    assert "ledfx/switch/ledfxplay/state" in topics
    assert "ledfx/sensor/ledfxpixelsensor/state" in topics

    # The state is scheduled a second time a few seconds later: Home
    # Assistant may still be subscribing when the first copy arrives,
    # and the messages are not retained.
    delay, callback, scheduled_client = (
        birth_integration._ledfx.loop.call_later.call_args.args
    )
    assert delay == 5
    assert callback == birth_integration.publish_state
    callback(scheduled_client)

    published = [(call.args[0], call.args[1]) for call in client.publish.call_args_list]
    assert published.count(("ledfx/select/ledfxsceneselect/state", "party")) == 2
    assert [t for t, _p in published].count("ledfx/select/ledfxsceneselect/config") == 1


def test_an_offline_birth_message_republishes_nothing(
    birth_integration: MQTT_HASS,
) -> None:
    client = MagicMock()
    birth_integration._client = client

    birth_integration._handle_message(
        SimpleNamespace(topic="ledfx/status", payload=b"offline")
    )

    birth_integration._ledfx.loop.call_later.assert_not_called()
    client.publish.assert_not_called()
