"""The MQTT scene set activates through Scenes, not its own copy of the logic."""

import logging
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from ledfx.configuration.models import Scene
from ledfx.errors import SafeMode
from ledfx.integrations.mqtt import MQTT
from tests.test_utilities.fake_ledfx import fake_ledfx


def test_mqtt_scene_set_routes_through_scenes_activate(
    caplog: pytest.LogCaptureFixture,
) -> None:
    ledfx = fake_ledfx()
    ledfx.config.scenes["plain"] = Scene.model_validate({"name": "Plain"})
    ledfx.scenes = MagicMock()
    integration = object.__new__(MQTT)
    integration._active = False
    integration._client = None
    integration._ledfx = ledfx
    integration._config = SimpleNamespace(topic="led")

    integration._handle_message(SimpleNamespace(topic="led/SCENE", payload=b"plain"))
    ledfx.scenes.activate.assert_called_once_with("plain")

    ledfx.scenes.activate.side_effect = SafeMode("read-only")
    with caplog.at_level(logging.DEBUG):
        integration._handle_message(
            SimpleNamespace(topic="led/SCENE", payload=b"plain")
        )
    scene_logs = [r for r in caplog.records if "not activated" in r.getMessage()]
    assert [r.levelno for r in scene_logs] == [logging.DEBUG]
