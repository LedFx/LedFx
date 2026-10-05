"""Startup failures must fail CLI/packaging checks, while normal exits stay clean."""

import argparse
from unittest.mock import Mock

import pytest

from ledfx import __main__ as cli
from ledfx.core import LedFxCore


@pytest.fixture
def cli_args(monkeypatch: pytest.MonkeyPatch) -> argparse.Namespace:
    args = argparse.Namespace(
        config="unused",
        host="127.0.0.1",
        port=0,
        port_s=0,
        ci_smoke_test=False,
        clear_config=False,
        clear_effects=False,
        offline_mode=True,
        open_ui=False,
        pause_all=False,
        dump_schemas=None,
        dump_openapi=None,
        loglevel=0,
        sentry_test=False,
        tray=False,
        no_tray=True,
    )
    monkeypatch.setattr(cli, "parse_args", lambda: args)
    return args


@pytest.mark.parametrize(
    "codes,smoke,expected",
    [
        ([1], False, 1),
        ([2], False, 0),
        ([3], False, 0),
        ([5], True, 0),
        ([5], False, 5),
        ([4, 5], True, 0),
        ([4, 1], False, 1),
        ([None], False, 1),
    ],
)
def test_entry_point_preserves_shutdown_and_restart(
    cli_args: argparse.Namespace,
    monkeypatch: pytest.MonkeyPatch,
    codes: list[int | None],
    smoke: bool,
    expected: int,
):
    cli_args.ci_smoke_test = smoke
    core = Mock()
    core.start.side_effect = codes
    factory = Mock(return_value=core)
    monkeypatch.setattr(cli, "LedFxCore", factory)
    assert cli.entry_point() == expected
    assert factory.call_count == len(codes)


def test_console_main_returns_startup_failure(
    cli_args: argparse.Namespace, monkeypatch: pytest.MonkeyPatch
):
    for name in ("ensure_config_directory", "load_logger"):
        monkeypatch.setattr(cli.config_helpers, name, Mock())
    for name in ("setup_logging", "read_ledfx_dotenv", "check_optional_dependencies"):
        monkeypatch.setattr(cli, name, Mock())
    monkeypatch.setattr(cli, "have_psutil", False)
    monkeypatch.setattr(cli, "currently_frozen", lambda: False)
    monkeypatch.setattr(cli, "_LOGGER", Mock(isEnabledFor=Mock(return_value=False)))
    monkeypatch.setattr(cli, "entry_point", Mock(return_value=1))
    assert cli.main() == 1


def test_tray_entry_point_still_stops_icon(
    cli_args: argparse.Namespace, monkeypatch: pytest.MonkeyPatch
):
    core = Mock()
    core.start.return_value = 3
    monkeypatch.setattr(cli, "LedFxCore", Mock(return_value=core))
    icon = Mock()
    assert cli.entry_point(icon) == 0
    assert icon.visible
    icon.stop.assert_called_once()


@pytest.mark.parametrize(
    "cancelled,error",
    [(False, RuntimeError("native startup failed")), (False, None), (True, None)],
)
def test_startup_exception_causes_failed_shutdown(
    cancelled: bool, error: RuntimeError | None
):
    core = Mock()
    task = Mock()
    task.cancelled.return_value = cancelled
    task.exception.return_value = error
    LedFxCore._startup_done(core, task)
    if error is not None and not cancelled:
        core.stop.assert_called_once_with(1)
        assert core.loop_exception_handler.call_args.args[1]["exception"] is error
    else:
        core.stop.assert_not_called()


def test_failing_startup_stops_event_loop(monkeypatch: pytest.MonkeyPatch):
    import asyncio

    core = object.__new__(LedFxCore)
    core.loop = asyncio.new_event_loop()
    core.exit_code = None

    async def fail_start(open_ui: bool, pause_all: bool):
        raise RuntimeError("native startup check failed")

    async def stop(exit_code: int):
        core.exit_code = exit_code
        core.loop.stop()

    monkeypatch.setattr(core, "async_start", fail_start)
    monkeypatch.setattr(core, "async_stop", stop)
    watchdog = core.loop.call_later(2, core.loop.stop)
    try:
        assert core.start() == 1
    finally:
        watchdog.cancel()
        core.loop.close()
