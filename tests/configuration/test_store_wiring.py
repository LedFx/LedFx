import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

from ledfx.configuration.models import LedFxConfig
from ledfx.configuration.store import ConfigStore, backup_config_file
from ledfx.core import LedFxCore


def test_create_backup_keeps_move_semantics_for_clear_config(tmp_path: Path) -> None:
    ConfigStore(str(tmp_path), LedFxConfig(port=1)).save_now()
    backup_config_file(str(tmp_path), "DELETE", move=True)
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
    # debounced save.
    core = object.__new__(LedFxCore)
    core.loop = MagicMock()
    core.events = MagicMock()
    core.audio_device_monitor = None
    core._smtc_now_playing = None
    core._mpris_now_playing = None
    core.http = MagicMock(stop=AsyncMock(side_effect=RuntimeError("boom")))
    core.devices = MagicMock(async_shutdown_devices=AsyncMock())
    core.thread_executor = MagicMock()
    core.exit_code = None
    core.config_store = MagicMock()

    await core.async_stop(4)

    core.config_store.flush_sync.assert_called_once_with()
    core.devices.async_shutdown_devices.assert_not_awaited()
    core.thread_executor.shutdown.assert_called_once_with()
    core.loop.stop.assert_called_once_with()
    assert core.exit_code == 1


async def test_shutdown_completes_when_flush_raises() -> None:
    # An unexpected flush error must not skip executor shutdown or loop.stop().
    core = object.__new__(LedFxCore)
    core.loop = MagicMock()
    core.events = MagicMock()
    core.audio_device_monitor = None
    core._smtc_now_playing = None
    core._mpris_now_playing = None
    core.http = MagicMock(stop=AsyncMock())
    core.devices = MagicMock(async_shutdown_devices=AsyncMock())
    core.thread_executor = MagicMock()
    core.exit_code = None
    core.config_store = MagicMock()
    core.config_store.flush_sync.side_effect = KeyError("boom")

    assert await core.async_stop(4) == 4

    core.devices.async_shutdown_devices.assert_awaited_once_with()
    core.config_store.flush_sync.assert_called_once_with()
    core.thread_executor.shutdown.assert_called_once_with()
    core.loop.stop.assert_called_once_with()
    assert core.exit_code == 4


def test_shutdown_before_device_registry_is_created(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Device registries are created in async_start, after the core constructor.
    # Startup failure or cancellation can therefore stop a core before this step.
    monkeypatch.setattr(LedFxCore, "setup_logqueue", MagicMock())
    http = MagicMock(stop=AsyncMock())
    monkeypatch.setattr("ledfx.core.HttpServer", MagicMock(return_value=http))
    core = LedFxCore(str(tmp_path), offline_mode=True)
    shutdown = core.thread_executor.shutdown
    shutdown_spy = MagicMock(wraps=shutdown)
    monkeypatch.setattr(core.thread_executor, "shutdown", shutdown_spy)
    try:
        assert not hasattr(core, "devices")
        assert core.loop.run_until_complete(core.async_stop(4)) == 4
        assert core.exit_code == 4
        http.stop.assert_awaited_once_with()
        shutdown_spy.assert_called_once_with()
        assert not core.loop.is_running()
    finally:
        shutdown()
        core.loop.close()
        asyncio.set_event_loop(None)
