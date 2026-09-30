"""Domain errors (ledfx.errors), safe mode, and their v1 mapping."""

import copy
import pickle
from collections.abc import Callable
from pathlib import Path

import pytest

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
    [NotFound("Virtual", "dj bird"), Unavailable("Spotify"), SafeMode("bad json")],
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
