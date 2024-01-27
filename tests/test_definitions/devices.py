# Broadly, this will use our internal HTTP APIs to:
# 1. Create a test device called "CI Test Jig"
# 2. Check that the device exists
# 3. Delete the device
# 4. Check that the device no longer exists
# 5. Recreate the device to allow it to be used in other tests
from tests.test_utils import APITestCase

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
                "refresh_rate": 62,
                "pixel_count": 100,
                "port": 4048,
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
                        "refresh_rate": 62,
                        "pixel_count": 100,
                        "port": 4048,
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
                            "refresh_rate": 62,
                            "pixel_count": 100,
                            "port": 4048,
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
                "refresh_rate": 62,
                "pixel_count": 100,
                "port": 4048,
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
                        "refresh_rate": 62,
                        "pixel_count": 100,
                        "port": 4048,
                        "name": "CI Test Jig",
                        "ip_address": "127.0.0.1",
                    },
                    "id": "ci-test-jig",
                    "virtuals": [],
                }
            },
        ],
    ),
}
