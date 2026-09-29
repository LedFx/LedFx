import asyncio
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ledfx.config import create_backup, save_config
from ledfx.configuration.migrations import CURRENT_SCHEMA_VERSION
from ledfx.configuration.models import LedFxConfig
from ledfx.configuration.store import ConfigStore


def test_save_config_shim_without_store_writes_atomically(tmp_path: Path) -> None:
    save_config(LedFxConfig(port=1), str(tmp_path))
    data = json.loads((tmp_path / "config.json").read_text())
    assert data["port"] == 1 and data["configuration_version"] == "2.3.6"
    # New behaviour: the store's envelope, and no temp file left behind.
    assert data["schema_version"] == CURRENT_SCHEMA_VERSION
    assert not [p for p in tmp_path.iterdir() if p.name.endswith(".tmp")]


async def test_save_config_shim_routes_to_registered_store(tmp_path: Path) -> None:
    store = ConfigStore.load(str(tmp_path))
    store.attach_loop(asyncio.get_running_loop())
    store.register()
    try:
        store.data.port = 1111
        save_config(store.data, str(tmp_path))
        assert store._save_handle is not None  # debounced, not written yet
        store.flush_sync()
        assert json.loads((tmp_path / "config.json").read_text())["port"] == 1111
    finally:
        store.unregister()


def test_create_backup_keeps_move_semantics_for_clear_config(tmp_path: Path) -> None:
    save_config(LedFxConfig(port=1), str(tmp_path))
    create_backup(str(tmp_path), "DELETE")
    assert not (tmp_path / "config.json").exists()
    # New behaviour: the collision-proof name, not the old fixed one.
    backups = [
        p.name for p in tmp_path.iterdir() if p.name.startswith("config_backup_DELETE_")
    ]
    assert len(backups) == 1 and backups[0].endswith(".json")


def test_mqtt_on_message_runs_handler_on_loop() -> None:
    # Review Focus 5: the paho thread must not touch config directly. on_connect
    # iterates devices, virtuals and scenes, and runs on every reconnect, so it
    # hops to the loop too.
    from ledfx.integrations.mqtt_hass import MQTT_HASS

    integration = MQTT_HASS.__new__(MQTT_HASS)
    integration._active = False  # Integration.__del__ reads it
    integration._ledfx = MagicMock()
    client, msg = MagicMock(), MagicMock()
    MQTT_HASS.on_message(integration, client, None, msg)
    MQTT_HASS.on_connect(integration, client, None, {}, 0)
    calls = integration._ledfx.loop.call_soon_threadsafe.call_args_list
    assert [c.args for c in calls] == [
        (integration._handle_message, msg),
        (integration._handle_connect, client, 0),
    ]
    client.subscribe.assert_not_called()  # nothing ran on the paho thread


def test_plain_mqtt_callbacks_run_on_loop() -> None:
    from ledfx.integrations.mqtt import MQTT

    integration = MQTT.__new__(MQTT)
    integration._active = False  # Integration.__del__ reads it
    integration._ledfx = MagicMock()
    client, msg = MagicMock(), MagicMock()
    MQTT.on_message(integration, client, None, msg)
    MQTT.on_connect(integration, client, None, {}, 0)
    calls = integration._ledfx.loop.call_soon_threadsafe.call_args_list
    assert calls[0].args == (integration._handle_message, msg)
    assert calls[1].args == (integration._handle_connect, client, 0)


def test_mqtt_callback_after_loop_closed_is_dropped(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # paho 2.1 re-raises callback exceptions, which would kill its thread.
    from ledfx.integrations.mqtt_hass import MQTT_HASS

    integration = MQTT_HASS.__new__(MQTT_HASS)
    integration._active = False  # Integration.__del__ reads it
    integration._ledfx = MagicMock()
    integration._ledfx.loop.call_soon_threadsafe.side_effect = RuntimeError(
        "Event loop is closed"
    )
    with caplog.at_level("DEBUG", logger="ledfx.integrations"):
        MQTT_HASS.on_message(integration, MagicMock(), None, MagicMock())
    assert any("Event loop closed" in r.getMessage() for r in caplog.records)


async def test_shutdown_flush_survives_stop_failure() -> None:
    # Review Focus 4: a failure earlier in async_stop must not lose the
    # debounced save; the store stays registered for late save_config() calls.
    from ledfx.core import LedFxCore

    core = object.__new__(LedFxCore)
    core.loop = MagicMock()
    core.events = MagicMock()
    core.audio_device_monitor = None
    core._smtc_now_playing = None
    core._mpris_now_playing = None
    core.http = MagicMock(stop=AsyncMock(side_effect=RuntimeError("boom")))
    core.thread_executor = MagicMock()
    core.exit_code = None
    core.config_store = MagicMock()

    await core.async_stop(4)

    core.config_store.flush_sync.assert_called_once_with()
    core.config_store.unregister.assert_not_called()
    assert core.exit_code == 1


async def test_shutdown_completes_when_flush_raises() -> None:
    # An unexpected flush error must not skip executor shutdown or loop.stop().
    from ledfx.core import LedFxCore

    core = object.__new__(LedFxCore)
    core.loop = MagicMock()
    core.events = MagicMock()
    core.audio_device_monitor = None
    core._smtc_now_playing = None
    core._mpris_now_playing = None
    core.http = MagicMock(stop=AsyncMock())
    core.thread_executor = MagicMock()
    core.exit_code = None
    core.config_store = MagicMock()
    core.config_store.flush_sync.side_effect = KeyError("boom")

    assert await core.async_stop(4) == 4

    core.thread_executor.shutdown.assert_called_once_with()
    core.loop.stop.assert_called_once_with()
    assert core.exit_code == 4
