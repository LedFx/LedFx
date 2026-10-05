"""Domain errors (ledfx.errors), safe mode, and their v1 mapping."""

import copy
import json
import logging
import pickle
from collections.abc import Callable
from pathlib import Path

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from ledfx.api import RestEndpoint
from ledfx.configuration.models import LedFxConfig
from ledfx.configuration.store import ConfigStore
from ledfx.errors import (
    Conflict,
    Invalid,
    LedFxError,
    NotFound,
    SafeMode,
    Unavailable,
    ensure_writable,
)
from tests.test_utilities.fake_ledfx import fake_ledfx


@pytest.mark.parametrize(
    ("error", "status", "problem", "detail"),
    [
        (
            NotFound("Virtual", "dj bird"),
            404,
            "not-found",
            "Virtual 'dj bird' not found",
        ),
        (Conflict("Preset 'x' is built in"), 409, "conflict", "Preset 'x' is built in"),
        (Invalid("bad value"), 422, "validation", "bad value"),
        (Unavailable("Spotify"), 503, "unavailable", "Spotify is not available"),
        (
            SafeMode("config.json is not valid JSON"),
            409,
            "safe-mode",
            "Config changes are disabled in safe mode: config.json is not valid JSON",
        ),
    ],
)
def test_error_status_problem_and_detail(
    error: LedFxError, status: int, problem: str, detail: str
) -> None:
    assert isinstance(error, LedFxError)
    assert (error.status, error.problem, error.detail) == (status, problem, detail)
    assert error.title
    assert str(error) == detail
    assert error.loc == ()


def test_error_keeps_its_location() -> None:
    error = Invalid("must be positive", loc=("config", "pixel_count"))
    assert error.loc == ("config", "pixel_count")


def _pickled(error: LedFxError) -> LedFxError:
    return pickle.loads(pickle.dumps(error))


@pytest.mark.parametrize(
    "error",
    [
        NotFound("Virtual", "dj bird"),
        NotFound("Virtual", "a", "b"),
        Unavailable("Spotify"),
        SafeMode("bad json"),
    ],
)
@pytest.mark.parametrize("clone", [copy.copy, _pickled])
def test_errors_survive_copy_and_pickle(
    error: LedFxError, clone: Callable[[LedFxError], LedFxError]
) -> None:
    again = clone(error)
    assert type(again) is type(error)
    assert str(again) == str(error)
    assert again.__dict__ == error.__dict__


def test_config_store_read_only_follows_error(tmp_path: Path) -> None:
    store = ConfigStore(str(tmp_path), LedFxConfig())
    assert store.read_only is False
    store.error = "config.json is not valid JSON"
    assert store.read_only is True


def test_ensure_writable_passes_outside_safe_mode() -> None:
    ensure_writable(fake_ledfx())


def test_ensure_writable_raises_safe_mode_with_the_store_error() -> None:
    ledfx = fake_ledfx()
    ledfx.config_store.error = "config.json could not be read"
    with pytest.raises(SafeMode) as info:
        ensure_writable(ledfx)
    assert info.value.reason == "config.json could not be read"
    assert info.value.status == 409


@RestEndpoint.no_registration
class _Raises(RestEndpoint):
    """A v1 endpoint whose GET raises the error it is given."""

    def __init__(self, error: Exception) -> None:
        super().__init__(fake_ledfx())
        self.error = error

    async def get(self) -> web.Response:
        raise self.error


async def _v1_call(error: Exception) -> tuple[int, object]:
    response = await _Raises(error).handler(make_mocked_request("GET", "/api/x"))
    assert isinstance(response, web.Response)
    return response.status, json.loads(response.text or "")


async def test_v1_maps_domain_errors_to_invalid_request() -> None:
    status, body = await _v1_call(NotFound("Virtual", "kitchen"))
    assert status == 200
    assert body == {
        "status": "failed",
        "payload": {"type": "error", "reason": "Virtual 'kitchen' not found"},
    }


async def test_v1_maps_safe_mode_to_invalid_request() -> None:
    status, body = await _v1_call(SafeMode("config.json is not valid JSON"))
    assert status == 200
    assert body == {
        "status": "failed",
        "payload": {
            "type": "error",
            "reason": "Config changes are disabled in safe mode: "
            "config.json is not valid JSON",
        },
    }


async def test_v1_other_exceptions_keep_the_202_catch_all() -> None:
    status, body = await _v1_call(RuntimeError("boom"))
    assert status == 202
    assert body == {"status": "failed", "payload": {"type": "error", "reason": "boom"}}


async def test_v1_logs_server_side_domain_errors_but_not_client_ones(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.ERROR, logger="ledfx.api"):
        await _v1_call(NotFound("Virtual", "kitchen"))
        assert caplog.records == []
        status, _ = await _v1_call(LedFxError("disk on fire"))
    assert status == 200
    assert [r.levelno for r in caplog.records] == [logging.ERROR]
    assert "disk on fire" in caplog.text
