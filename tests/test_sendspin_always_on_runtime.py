"""Runtime behavior tests for Sendspin always-on startup paths."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from ledfx.api.config import ConfigEndpoint
from ledfx.config import CORE_CONFIG_SCHEMA
from ledfx.core import LedFxCore
from ledfx.effects.audio import AudioInputSource
from ledfx.sendspin.config import eager_start


def test_sendspin_always_on_default_true():
    config = CORE_CONFIG_SCHEMA({})
    assert config["sendspin_always_on"] is True


def test_audio_should_keep_active_for_sendspin_name_even_if_index_invalid():
    ais = object.__new__(AudioInputSource)
    ais._ledfx = SimpleNamespace(config={"sendspin_always_on": True})
    ais._config = {
        "audio_device": 999,
        "audio_device_name": "SENDSPIN: living-room",
    }

    assert ais._should_always_keep_active() is True


def test_handle_base_configuration_update_reconciles_when_enabled():
    core = object.__new__(LedFxCore)
    core.audio = None
    core.config = {"sendspin_always_on": True}

    with patch("ledfx.core.sendspin_eager_start") as mock_eager_start:
        core.handle_base_configuration_update(
            SimpleNamespace(config={"sendspin_always_on": True})
        )

    mock_eager_start.assert_called_once_with(core)


def test_eager_start_reuses_existing_audio_instance():
    ledfx = SimpleNamespace(
        config={
            "sendspin_always_on": True,
            "audio": {
                "audio_device": 0,
                "audio_device_name": "SENDSPIN: living-room",
            },
        },
        audio=MagicMock(),
    )

    with (
        patch(
            "ledfx.effects.audio.AudioInputSource.query_devices",
            return_value=({},),
        ),
        patch(
            "ledfx.effects.audio.AudioInputSource.query_hostapis",
            return_value=({},),
        ),
    ):
        eager_start(ledfx)

    ledfx.audio.update_config.assert_called_once_with(ledfx.config["audio"])


def test_reconcile_sendspin_always_on_runtime_deactivates_when_disabled():
    core = object.__new__(LedFxCore)
    core.config = {"sendspin_always_on": False}
    core.audio = MagicMock()

    with patch("ledfx.core.sendspin_eager_start") as mock_eager_start:
        core.reconcile_sendspin_always_on_runtime("unit_test")

    mock_eager_start.assert_not_called()
    core.audio.check_and_deactivate.assert_called_once_with()


@patch.object(
    AudioInputSource,
    "input_devices",
    return_value={0: "SENDSPIN: living-room"},
)
def test_config_update_audio_triggers_core_sendspin_reconcile(_mock_devices):
    ledfx = SimpleNamespace(
        config={
            "audio": {
                "audio_device": 0,
                "audio_device_name": "",
            },
            "melbanks": {},
            "wled_preferences": {},
            "sendspin_always_on": True,
        },
        audio=None,
        reconcile_sendspin_always_on_runtime=MagicMock(),
        events=SimpleNamespace(fire_event=MagicMock()),
    )

    endpoint = object.__new__(ConfigEndpoint)
    endpoint._ledfx = ledfx

    endpoint.update_config({"audio": {"audio_device": 0}})

    ledfx.reconcile_sendspin_always_on_runtime.assert_called_once_with(
        "audio_config_updated"
    )
