"""Regression tests for v1 REST API bugs: each endpoint either does what its
success response says, or answers with its usual failure response."""

import asyncio
import copy
from unittest.mock import MagicMock

import pytest

from ledfx.api import RestEndpoint
from ledfx.api.colors import ColorEndpoint
from ledfx.api.colors_delete import ColorDeleteEndpoint
from ledfx.api.device import DeviceEndpoint
from ledfx.api.preset_delete import PresetDeleteEndpoint
from ledfx.api.presets import PresetsEndpoint
from ledfx.color import (
    LEDFX_COLORS,
    LEDFX_GRADIENTS,
    parse_color,
    parse_gradient,
    validate_color,
    validate_gradient,
)
from ledfx.presets import ledfx_presets
from ledfx.utils import UserDefaultCollection
from tests.test_api_validation_responses import _call, _reason
from tests.test_utilities.fake_ledfx import fake_ledfx


async def test_unknown_device_is_named_in_the_reason() -> None:
    ledfx = fake_ledfx()
    ledfx.devices.get.return_value = None
    status, body = await _call(DeviceEndpoint(ledfx), "GET", device_id="nope")
    assert status == 200
    assert body["status"] == "failed"
    assert _reason(body) == "Device nope was not found"


PRESET_CALLS: list[
    tuple[type[RestEndpoint], str, dict[str, str] | None, dict[str, str]]
] = [
    (PresetsEndpoint, "GET", None, {}),
    (
        PresetsEndpoint,
        "PUT",
        {"preset_id": "p", "category": "user_presets", "name": "n"},
        {},
    ),
    (PresetsEndpoint, "DELETE", {"preset_id": "p", "category": "user_presets"}, {}),
    (PresetDeleteEndpoint, "DELETE", {}, {"preset_id": "p"}),
]


@pytest.mark.parametrize(("endpoint", "method", "body", "extra"), PRESET_CALLS)
async def test_unknown_effect_type_is_an_invalid_request(
    endpoint: type[RestEndpoint],
    method: str,
    body: dict[str, str],
    extra: dict[str, str],
) -> None:
    ledfx = fake_ledfx()
    ledfx.effects.get_class.side_effect = KeyError("nope")
    status, reply = await _call(
        endpoint(ledfx), method, body, effect_id="nope", **extra
    )
    assert status == 200
    assert _reason(reply) == "Effect nope does not exist"


@pytest.mark.parametrize(("endpoint", "method", "body", "extra"), PRESET_CALLS)
async def test_preset_lookup_does_not_swallow_cancellation(
    endpoint: type[RestEndpoint],
    method: str,
    body: dict[str, str],
    extra: dict[str, str],
) -> None:
    ledfx = fake_ledfx()
    ledfx.effects.get_class.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await _call(endpoint(ledfx), method, body, effect_id="e", **extra)


@pytest.mark.parametrize(
    ("method", "body"),
    [
        ("PUT", {"category": "ledfx_presets", "name": "renamed"}),
        ("DELETE", {"category": "ledfx_presets"}),
    ],
)
async def test_built_in_presets_are_read_only(
    method: str, body: dict[str, str]
) -> None:
    ledfx = fake_ledfx()
    effect_id = next(iter(ledfx_presets))
    preset_id = next(iter(ledfx_presets[effect_id]))
    before = copy.deepcopy(ledfx_presets[effect_id])
    try:
        status, reply = await _call(
            PresetsEndpoint(ledfx),
            method,
            {**body, "preset_id": preset_id},
            effect_id=effect_id,
        )
        assert status == 200
        assert reply["status"] == "failed"
        assert _reason(reply) == "Built-in LedFx presets are read-only"
        assert ledfx_presets[effect_id] == before
        ledfx.config_store.request_save.assert_not_called()
    finally:
        ledfx_presets[effect_id].clear()
        ledfx_presets[effect_id].update(before)


def _with_colors() -> MagicMock:
    ledfx = fake_ledfx({"user_colors": {"mine": "#010203"}})
    ledfx.colors = UserDefaultCollection(
        ledfx,
        "Colors",
        LEDFX_COLORS,
        ledfx.config.user_colors,
        validate_color,
        parse_color,
    )
    ledfx.gradients = UserDefaultCollection(
        ledfx,
        "Gradients",
        LEDFX_GRADIENTS,
        ledfx.config.user_gradients,
        validate_gradient,
        parse_gradient,
    )
    return ledfx


BUILTIN_COLOR = next(iter(LEDFX_COLORS))


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        (BUILTIN_COLOR, f"Cannot delete built-in color or gradient: {BUILTIN_COLOR}"),
        ("ghost", "Color or gradient ghost not found"),
    ],
)
async def test_colors_list_delete_reports_what_it_could_not_delete(
    name: str, reason: str
) -> None:
    ledfx = _with_colors()
    status, reply = await _call(ColorEndpoint(ledfx), "DELETE", ["mine", name])
    assert status == 200
    assert reply["status"] == "failed"
    assert _reason(reply) == reason
    # Nothing is deleted when any name is refused.
    assert ledfx.config.user_colors == {"mine": "#010203"}


async def test_colors_list_delete_refuses_a_user_entry_shadowing_a_built_in() -> None:
    # Only an old config can hold this; POST refuses built-in names.
    ledfx = _with_colors()
    ledfx.config.user_colors[BUILTIN_COLOR] = "#000000"
    before = dict(ledfx.config.user_colors)
    status, reply = await _call(ColorEndpoint(ledfx), "DELETE", ["mine", BUILTIN_COLOR])
    assert status == 200
    assert reply["status"] == "failed"
    assert _reason(reply) == (
        f"Cannot delete built-in color or gradient: {BUILTIN_COLOR}"
    )
    assert ledfx.config.user_colors == before


async def test_colors_single_delete_of_a_built_in_fails() -> None:
    ledfx = _with_colors()
    status, reply = await _call(
        ColorDeleteEndpoint(ledfx), "DELETE", {}, color_id=BUILTIN_COLOR
    )
    assert status == 200
    assert reply["status"] == "failed"
    assert "built-in color" in _reason(reply)
    assert BUILTIN_COLOR in LEDFX_COLORS


async def test_colors_post_of_a_built_in_name_fails() -> None:
    ledfx = _with_colors()
    status, reply = await _call(
        ColorEndpoint(ledfx), "POST", {"new": "#ffffff", BUILTIN_COLOR: "#000000"}
    )
    assert status == 200
    assert _reason(reply) == f"Cannot overwrite built-in color: {BUILTIN_COLOR}"
    assert "new" not in ledfx.config.user_colors


async def test_colors_post_of_an_invalid_value_is_an_invalid_request() -> None:
    ledfx = _with_colors()
    status, reply = await _call(ColorEndpoint(ledfx), "POST", {"bad": "not-a-color"})
    assert status == 200
    assert _reason(reply) == "bad is not a valid color or gradient"
    assert "bad" not in ledfx.config.user_gradients


def test_user_default_collection_refuses_to_touch_built_ins() -> None:
    colors = _with_colors().colors
    with pytest.raises(ValueError, match="built-in color"):
        colors[BUILTIN_COLOR] = "#000000"
    with pytest.raises(ValueError, match="built-in color"):
        del colors[BUILTIN_COLOR]
    with pytest.raises(KeyError):
        del colors["ghost"]
