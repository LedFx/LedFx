# LIFX device tests using lifx-emulator-core
# The emulator runs a Ceiling matrix device (8x8 = 64 pixels) at 127.0.0.1:56700
# LIFX devices auto-detect type on connect and update config accordingly
#
# These tests run last because the LIFX emulator is bound to 127.0.0.1
# and no coexistence rule exists between LIFX and the DDP test jig.
# The test jig is deleted first to free the IP.
#
# 1. Delete the DDP test jig (frees 127.0.0.1)
# 2. Create a LIFX device
# 3. Check the LIFX device exists
# 4. Delete the LIFX device
# 5. Test find_lifx endpoint validation (missing ip_address)
from tests.test_utilities.test_utils import APITestCase, SystemInfo

_available_fps = SystemInfo.calc_available_fps()
_default_lifx_fps = next(
    (f for f in _available_fps if f >= 30), list(_available_fps)[-1]
)

lifx_tests = {
    # Delete test jig if it still exists (may already be gone from earlier test groups)
    "delete_test_jig": APITestCase(
        execution_order=1,
        method="DELETE",
        api_endpoint="/api/virtuals/ci-test-jig",
        expected_return_code=200,
        expected_response_keys=["status"],
        expected_response_values=[],
        payload_to_send={"name": "CI Test Jig"},
    ),
    "create_lifx_device": APITestCase(
        execution_order=2,
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "lifx",
            "config": {
                "icon_name": "mdi:lightbulb",
                "center_offset": 0,
                "refresh_rate": _default_lifx_fps,
                "pixel_count": 1,
                "name": "CI LIFX Test",
                "ip_address": "127.0.0.1",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "device": {
                    "type": "lifx",
                    "config": {
                        "icon_name": "mdi:lightbulb",
                        "center_offset": 0,
                        "refresh_rate": _default_lifx_fps,
                        # Auto-detected from emulated matrix device
                        "pixel_count": 64,
                        "name": "CI LIFX Test",
                        "ip_address": "127.0.0.1",
                        "serial": "d073d9000001",
                        "lifx_class": "CeilingLight",
                        "lifx_type": "matrix",
                        "matrix_width": 8,
                        "matrix_height": 8,
                    },
                    "id": "ci-lifx-test",
                    "virtuals": [],
                }
            },
        ],
    ),
    "check_lifx_device": APITestCase(
        execution_order=3,
        method="GET",
        api_endpoint="/api/devices",
        expected_return_code=200,
        expected_response_keys=["status", "devices"],
        expected_response_values=[
            {
                "status": "success",
                "devices": {
                    "ci-lifx-test": {
                        "config": {
                            "icon_name": "mdi:lightbulb",
                            "center_offset": 0,
                            "refresh_rate": _default_lifx_fps,
                            "pixel_count": 64,
                            "name": "CI LIFX Test",
                            "ip_address": "127.0.0.1",
                            "serial": "d073d9000001",
                            "lifx_class": "CeilingLight",
                            "lifx_type": "matrix",
                            "matrix_width": 8,
                            "matrix_height": 8,
                        },
                        "id": "ci-lifx-test",
                        "type": "lifx",
                        "online": True,
                        "virtuals": [],
                        "active_virtuals": [],
                    },
                },
            }
        ],
    ),
    "delete_lifx_device": APITestCase(
        execution_order=4,
        method="DELETE",
        api_endpoint="/api/virtuals/ci-lifx-test",
        expected_return_code=200,
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
        payload_to_send={"name": "CI LIFX Test"},
    ),
    # find_lifx endpoint validation tests
    # Send valid JSON without ip_address to test missing field validation
    # Note: Empty {} is falsy and becomes None in test framework, so use non-empty payload
    "find_lifx_missing_ip": APITestCase(
        execution_order=5,
        method="POST",
        api_endpoint="/api/find_lifx",
        expected_return_code=200,
        payload_to_send={"timeout": 1},
        expected_response_keys=["status"],
        expected_response_values=[{"status": "failed"}],
    ),
}
