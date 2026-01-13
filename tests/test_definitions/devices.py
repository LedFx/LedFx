# Broadly, this will use our internal HTTP APIs to:
# 1. Create a test device called "CI Test Jig"
# 2. Check that the device exists
# 3. Delete the device
# 4. Check that the device no longer exists
# 5. Recreate the device to allow it to be used in other tests
#
# Additional tests for LIFX devices:
# 6. Create a LIFX device
# 7. Check the LIFX device exists
# 8. Delete the LIFX device
# 9. Test find_lifx endpoint validation (missing ip_address)
from tests.test_utilities.test_utils import APITestCase, SystemInfo

device_tests = {
    "create_test_device": APITestCase(
        execution_order=1,
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "ddp",
            "config": {
                "icon_name": "mdi:led-strip",
                "center_offset": 0,
                "refresh_rate": SystemInfo.default_fps(),
                "pixel_count": 100,
                "port": 4048,
                "destination_id": 1,
                "name": "CI Test Jig",
                "ip_address": "127.0.0.1",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "device": {
                    "type": "ddp",
                    "config": {
                        "icon_name": "mdi:led-strip",
                        "center_offset": 0,
                        "refresh_rate": SystemInfo.default_fps(),
                        "pixel_count": 100,
                        "port": 4048,
                        "destination_id": 1,
                        "name": "CI Test Jig",
                        "ip_address": "127.0.0.1",
                    },
                    "id": "ci-test-jig",
                    "virtuals": [],
                }
            },
        ],
    ),
    "check_test_device": APITestCase(
        execution_order=2,
        method="GET",
        api_endpoint="/api/devices",
        expected_return_code=200,
        expected_response_keys=["status", "devices"],
        expected_response_values=[
            {
                "status": "success",
                "devices": {
                    "ci-test-jig": {
                        "config": {
                            "icon_name": "mdi:led-strip",
                            "center_offset": 0,
                            "refresh_rate": SystemInfo.default_fps(),
                            "pixel_count": 100,
                            "port": 4048,
                            "destination_id": 1,
                            "name": "CI Test Jig",
                            "ip_address": "127.0.0.1",
                        },
                        "id": "ci-test-jig",
                        "type": "ddp",
                        "online": True,
                        "virtuals": [],
                        "active_virtuals": [],
                    }
                },
            }
        ],
    ),
    "delete_test_device": APITestCase(
        execution_order=3,
        method="DELETE",
        api_endpoint="/api/virtuals/ci-test-jig",
        expected_return_code=200,
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
        payload_to_send={"name": "CI Test Jig"},
    ),
    "check_test_device_deleted": APITestCase(
        execution_order=4,
        method="GET",
        api_endpoint="/api/devices",
        expected_return_code=200,
        expected_response_keys=["status", "devices"],
        expected_response_values=[{"devices": {}}],
    ),
    "recreate_test_device": APITestCase(
        execution_order=5,
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "ddp",
            "config": {
                "icon_name": "mdi:led-strip",
                "center_offset": 0,
                "refresh_rate": SystemInfo.default_fps(),
                "pixel_count": 100,
                "port": 4048,
                "destination_id": 1,
                "name": "CI Test Jig",
                "ip_address": "127.0.0.1",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "device": {
                    "type": "ddp",
                    "config": {
                        "icon_name": "mdi:led-strip",
                        "center_offset": 0,
                        "refresh_rate": SystemInfo.default_fps(),
                        "pixel_count": 100,
                        "port": 4048,
                        "destination_id": 1,
                        "name": "CI Test Jig",
                        "ip_address": "127.0.0.1",
                    },
                    "id": "ci-test-jig",
                    "virtuals": [],
                }
            },
        ],
    ),
    # LIFX device tests
    # Note: LIFX devices auto-detect type on connect, but without a real device
    # at the IP, it will use defaults. Device shows as online since the IP resolves.
    "create_lifx_device": APITestCase(
        execution_order=6,
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "lifx",
            "config": {
                "icon_name": "mdi:lightbulb",
                "center_offset": 0,
                "refresh_rate": SystemInfo.default_fps(),
                "pixel_count": 1,
                "name": "CI LIFX Test",
                "ip_address": "127.0.0.2",
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
                        "refresh_rate": SystemInfo.default_fps(),
                        "pixel_count": 1,
                        "name": "CI LIFX Test",
                        "ip_address": "127.0.0.2",
                        "create_segments": True,
                    },
                    "id": "ci-lifx-test",
                    "virtuals": [],
                }
            },
        ],
    ),
    "check_lifx_device": APITestCase(
        execution_order=7,
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
                            "refresh_rate": SystemInfo.default_fps(),
                            "pixel_count": 1,
                            "name": "CI LIFX Test",
                            "ip_address": "127.0.0.2",
                            "create_segments": True,
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
        execution_order=8,
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
        execution_order=9,
        method="POST",
        api_endpoint="/api/find_lifx",
        expected_return_code=200,
        payload_to_send={"timeout": 1},
        expected_response_keys=["status"],
        expected_response_values=[{"status": "failed"}],
    ),
}
