"""Tests for the MQTT Home Assistant integration."""

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ledfx.events import EffectSetEvent
from ledfx.integrations.mqtt_hass import MQTT_HASS


def _integration(effects: dict[str, object]) -> MQTT_HASS:
    integration = MQTT_HASS.__new__(MQTT_HASS)
    integration._active = False  # Integration.__del__ reads it
    integration._config = {"topic": "ledfx"}
    integration._ledfx = MagicMock()
    integration._ledfx.effects = effects
    # By the time the listener runs, a scene change has replaced the
    # virtual's active effect with one that has no colour.
    integration._ledfx.virtuals.get.return_value.active_effect = SimpleNamespace(
        config={}
    )
    return integration


def _event() -> EffectSetEvent:
    return EffectSetEvent(
        "Single Color", "singleColor", "strip", "singleColor", True, False
    )


def test_single_color_publishes_the_event_effect_colour() -> None:
    effect = SimpleNamespace(config={"color": "#ff0000"})
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
    [{}, {"singleColor": SimpleNamespace(config={})}],
    ids=["effect-gone", "no-color"],
)
def test_single_color_skips_effect_without_colour(effects: dict[str, object]) -> None:
    client = MagicMock()

    _integration(effects).publish_single_color(client, _event())

    client.publish.assert_not_called()
