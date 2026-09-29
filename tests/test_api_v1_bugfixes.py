"""Regression tests for v1 REST API bugs: each endpoint either does what its
success response says, or answers with its usual failure response."""

from ledfx.api.device import DeviceEndpoint
from tests.test_api_validation_responses import _call, _reason
from tests.test_utilities.fake_ledfx import fake_ledfx


async def test_unknown_device_is_named_in_the_reason() -> None:
    ledfx = fake_ledfx()
    ledfx.devices.get.return_value = None
    status, body = await _call(DeviceEndpoint(ledfx), "GET", device_id="nope")
    assert status == 200
    assert body["status"] == "failed"
    assert _reason(body) == "Device nope was not found"
