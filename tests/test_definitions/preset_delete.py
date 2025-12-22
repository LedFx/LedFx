# Test the new RESTful DELETE endpoint for effect presets
# This uses path parameters instead of JSON body for better REST compliance
# Tests are self-contained: create device (auto-creates virtual), test delete, cleanup
from tests.test_utilities.test_utils import APITestCase

preset_delete_tests = {
    "create_test_device": APITestCase(
        execution_order=1,
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "dummy",
            "config": {
                "name": "preset-test-device",
                "pixel_count": 100,
            },
        },
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
    ),
    "set_effect_for_preset_test": APITestCase(
        execution_order=2,
        method="POST",
        api_endpoint="/api/virtuals/preset-test-device/effects",
        expected_return_code=200,
        payload_to_send={
            "type": "rainbow",
            "config": {"speed": 1.0},
        },
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
    ),
    "create_user_preset_for_delete": APITestCase(
        execution_order=3,
        method="POST",
        api_endpoint="/api/virtuals/preset-test-device/presets",
        expected_return_code=200,
        payload_to_send={
            "name": "test-preset-to-delete",
            "category": "user_presets",
        },
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
    ),
    "delete_user_preset_restful_success": APITestCase(
        execution_order=4,
        method="DELETE",
        api_endpoint="/api/effects/rainbow/presets/test-preset-to-delete",
        expected_return_code=200,
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
    ),
    "delete_nonexistent_preset": APITestCase(
        execution_order=5,
        method="DELETE",
        api_endpoint="/api/effects/rainbow/presets/nonexistent_preset",
        expected_return_code=200,
        expected_response_keys=["status"],
        expected_response_values=[{"status": "failed"}],
    ),
    "delete_preset_invalid_effect": APITestCase(
        execution_order=6,
        method="DELETE",
        api_endpoint="/api/effects/invalid_effect/presets/some_preset",
        expected_return_code=200,
        expected_response_keys=["status"],
        expected_response_values=[{"status": "failed"}],
    ),
    "cleanup_test_device": APITestCase(
        execution_order=7,
        method="DELETE",
        api_endpoint="/api/devices/preset-test-device",
        expected_return_code=200,
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
    ),
}
