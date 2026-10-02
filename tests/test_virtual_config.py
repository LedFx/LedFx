"""Virtual.config is a frozen VirtualConfig; changes go through update_config."""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from pydantic import ValidationError

from ledfx.configuration.models import VirtualConfig
from ledfx.effects.melbank import FrequencyRange
from ledfx.virtuals import Virtual
from tests.test_utilities.virtuals_core import running_core


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


def _bird(ledfx: MagicMock) -> Virtual:
    virtual = ledfx.virtuals.get("dj bird")
    assert isinstance(virtual, Virtual)
    return virtual


def test_config_is_the_stored_frozen_model(ledfx: MagicMock) -> None:
    virtual = _bird(ledfx)
    assert isinstance(virtual.config, VirtualConfig)
    entry = virtual.entry
    assert entry is not None and entry.config is virtual.config
    with pytest.raises(ValidationError, match="frozen"):
        field = "name"  # by name: a literal assignment is a static error
        setattr(virtual.config, field, "renamed")


def test_update_config_replaces_the_model(ledfx: MagicMock) -> None:
    virtual = _bird(ledfx)
    old = virtual.config
    virtual.update_config({"max_brightness": 0.5})
    assert virtual.config is not old
    assert (old.max_brightness, virtual.config.max_brightness) == (1.0, 0.5)


def test_update_config_validates_before_changing_anything(ledfx: MagicMock) -> None:
    virtual = _bird(ledfx)
    old = virtual.config
    with pytest.raises(ValidationError):
        virtual.update_config({"max_brightness": 5})
    assert virtual.config is old


def test_a_reversed_frequency_range_is_swapped(ledfx: MagicMock) -> None:
    virtual = _bird(ledfx)
    virtual.update_config({"frequency_min": 500, "frequency_max": 100})
    assert (virtual.config.frequency_min, virtual.config.frequency_max) == (100, 500)
    assert virtual.frequency_range == FrequencyRange(100, 500)


def test_a_one_row_virtual_does_not_rotate(ledfx: MagicMock) -> None:
    virtual = _bird(ledfx)
    virtual.update_config({"rotate": 2})
    assert virtual.config.rotate == 0
    virtual.update_config({"rows": 5, "rotate": 2})
    assert virtual.config.rotate == 2


def test_rows_setter_keeps_at_least_one_row(ledfx: MagicMock) -> None:
    virtual = _bird(ledfx)
    virtual.rows = 0
    assert virtual.config.rows == 1


def test_global_transitions_are_shared_and_stored(ledfx: MagicMock) -> None:
    ledfx.config.global_transitions = True
    _bird(ledfx).update_config({"transition_time": 1.5})
    mirror = ledfx.virtuals.get("mirror")
    assert mirror.config.transition_time == 1.5
    assert mirror.entry.config is mirror.config


def test_update_config_keeps_the_entry_in_sync(ledfx: MagicMock) -> None:
    virtual = _bird(ledfx)
    virtual.update_config({"max_brightness": 0.5})
    entry = virtual.entry
    assert entry is not None and entry.config is virtual.config


def test_rows_setter_keeps_the_entry_in_sync(ledfx: MagicMock) -> None:
    virtual = _bird(ledfx)
    virtual.rows = 4
    entry = virtual.entry
    assert entry is not None and entry.config is virtual.config
    assert entry.config.rows == 4


@pytest.mark.parametrize(
    ("pair", "expected"),
    [((15000, 15000), (14999, 15000)), ((100, 100), (100, 101))],
)
def test_a_zero_width_frequency_range_is_widened(
    ledfx: MagicMock, pair: tuple[int, int], expected: tuple[int, int]
) -> None:
    virtual = _bird(ledfx)
    virtual.update_config({"frequency_min": pair[0], "frequency_max": pair[1]})
    assert (virtual.config.frequency_min, virtual.config.frequency_max) == expected
    assert virtual.frequency_range == FrequencyRange(*expected)
