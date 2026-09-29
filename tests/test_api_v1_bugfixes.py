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
from ledfx.api.power import MAX_POWER_TIMEOUT
from ledfx.api.power import InfoEndpoint as PowerEndpoint
from ledfx.api.preset_delete import PresetDeleteEndpoint
from ledfx.api.presets import PresetsEndpoint
from ledfx.api.virtual_tools import VirtualToolsEndpoint
from ledfx.api.virtuals_tools import VirtualsToolsEndpoint
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


def _tool_virtual() -> tuple[MagicMock, MagicMock]:
    ledfx = fake_ledfx()
    virtual = MagicMock()
    virtual.add_oneshot.return_value = True
    ledfx.virtuals.get.return_value = virtual
    ledfx.virtuals.__iter__.return_value = iter(["v1"])
    return ledfx, virtual


async def _tools_post(body: object, one_virtual: bool):
    ledfx, virtual = _tool_virtual()
    if one_virtual:
        reply = await _call(VirtualsToolsEndpoint(ledfx), "POST", body, virtual_id="v1")
    else:
        reply = await _call(VirtualToolsEndpoint(ledfx), "POST", body)
    return *reply, virtual


@pytest.mark.parametrize("one_virtual", [True, False])
@pytest.mark.parametrize("tool", ["force_color", "calibration", "highlight", "copy"])
async def test_tools_post_refuses_tools_it_does_not_run(
    tool: str, one_virtual: bool
) -> None:
    body = {"tool": tool, "color": "red"}
    status, reply, virtual = await _tools_post(body, one_virtual)
    assert status == 200
    assert reply["status"] == "failed"
    assert virtual.method_calls == []


@pytest.mark.parametrize("one_virtual", [True, False])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("brightness", "x"),
        ("ramp", "slow"),
        ("hold", -1),
        ("fade", None),
        ("fade", "inf"),
        ("hold", "nan"),
        ("color", "notacolor"),
    ],
)
async def test_tools_oneshot_rejects_bad_values(
    field: str, value: object, one_virtual: bool
) -> None:
    body = {"tool": "oneshot", field: value}
    status, reply, virtual = await _tools_post(body, one_virtual)
    assert status == 400
    assert [e["loc"] for e in reply["errors"]] == [[field]]
    virtual.add_oneshot.assert_not_called()


@pytest.mark.parametrize("one_virtual", [True, False])
async def test_tools_oneshot_still_clamps_brightness(one_virtual: bool) -> None:
    body = {"tool": "oneshot", "color": "#ffffff", "ramp": 10, "brightness": 5}
    status, reply, virtual = await _tools_post(body, one_virtual)
    assert (status, reply) == (200, {"status": "success", "tool": "oneshot"})
    (flash,), _ = virtual.add_oneshot.call_args
    assert list(flash._color) == [255.0, 255.0, 255.0]


@pytest.mark.parametrize("one_virtual", [True, False])
async def test_tools_force_color_with_a_bad_color_is_an_invalid_request(
    one_virtual: bool,
) -> None:
    ledfx, virtual = _tool_virtual()
    body = {"tool": "force_color", "color": "notacolor"}
    if one_virtual:
        status, reply = await _call(
            VirtualsToolsEndpoint(ledfx), "PUT", body, virtual_id="v1"
        )
    else:
        virtual.is_device = virtual.id = "v1"
        status, reply = await _call(VirtualToolsEndpoint(ledfx), "PUT", body)
    assert status == 200
    assert _reason(reply) == "Invalid color: notacolor"
    virtual.force_frame.assert_not_called()


@pytest.mark.parametrize("timeout", ["5", True, -1, 1.5, MAX_POWER_TIMEOUT + 1])
async def test_power_rejects_a_bad_timeout(timeout: object) -> None:
    ledfx = fake_ledfx()
    status, reply = await _call(
        PowerEndpoint(ledfx), "POST", {"action": "restart", "timeout": timeout}
    )
    assert status == 200
    assert _reason(reply) == (
        f"Timeout must be a whole number of seconds from 0 to {MAX_POWER_TIMEOUT}"
    )
    ledfx.loop.call_later.assert_not_called()
    ledfx.stop.assert_not_called()


async def test_power_answers_at_once_and_stops_later() -> None:
    ledfx = fake_ledfx()
    status, reply = await asyncio.wait_for(
        _call(PowerEndpoint(ledfx), "POST", {"action": "restart", "timeout": 5}),
        timeout=1,
    )
    assert (status, reply) == (200, {"status": "success"})
    ledfx.loop.call_later.assert_called_once_with(5, ledfx.stop, 4)
    ledfx.stop.assert_not_called()
