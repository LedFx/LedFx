# Test the new RESTful DELETE endpoint for effect presets
# This uses path parameters instead of JSON body for better REST compliance
# Success test depends on virtual_config_tests creating first-virt (runs before this in CI)
from tests.test_utilities.test_utils import APITestCase

preset_delete_tests = {
    "create_user_preset_for_delete": APITestCase(
        execution_order=1,
        method="POST",
        api_endpoint="/api/virtuals/first-virt/presets",
        expected_return_code=200,
        payload_to_send={
            "preset_name": "test_preset_to_delete",
            "category": "user_presets",
        },
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
    ),
    "delete_user_preset_restful_success": APITestCase(
        execution_order=2,
        method="DELETE",
        api_endpoint="/api/effects/rainbow/presets/test_preset_to_delete",
        expected_return_code=200,
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
    ),
    "delete_nonexistent_preset": APITestCase(
        execution_order=3,
        method="DELETE",
        api_endpoint="/api/effects/rainbow/presets/nonexistent_preset",
        expected_return_code=200,
        expected_response_keys=["status"],
        expected_response_values=[{"status": "failed"}],
    ),
    "delete_preset_invalid_effect": APITestCase(
        execution_order=4,
        method="DELETE",
        api_endpoint="/api/effects/invalid_effect/presets/some_preset",
        expected_return_code=200,
        expected_response_keys=["status"],
        expected_response_values=[{"status": "failed"}],
    ),
}
