"""Regression tests for v1 REST API bugs: each endpoint either does what its
success response says, or answers with its usual failure response."""

import asyncio
import copy

import pytest

from ledfx.api import RestEndpoint
from ledfx.api.device import DeviceEndpoint
from ledfx.api.preset_delete import PresetDeleteEndpoint
from ledfx.api.presets import PresetsEndpoint
from ledfx.presets import ledfx_presets
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
