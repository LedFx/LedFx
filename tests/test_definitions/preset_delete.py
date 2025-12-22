# Test the new RESTful DELETE endpoint for effect presets
# This uses path parameters instead of JSON body for better REST compliance
# Depends on: device_tests (creates ci-test-jig) and effect_tests (sets energy effect)
from tests.test_utilities.test_utils import APITestCase

preset_delete_tests = {
    "create_user_preset_for_delete": APITestCase(
        execution_order=1,
        method="POST",
        api_endpoint="/api/virtuals/ci-test-jig/presets",
        expected_return_code=200,
        payload_to_send={
            "preset_name": "test_preset_to_delete",
            "category": "user_presets",
        },
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
    ),
    "verify_user_preset_exists": APITestCase(
        execution_order=2,
        method="GET",
        api_endpoint="/api/effects/energy/presets",
        expected_return_code=200,
        expected_response_keys=["status", "effect", "user_presets"],
        expected_response_values=[
            {"status": "success", "effect": "energy"},
        ],
    ),
    "delete_user_preset_restful": APITestCase(
        execution_order=3,
        method="DELETE",
        api_endpoint="/api/effects/energy/presets/test_preset_to_delete",
        expected_return_code=200,
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
    ),
    "verify_user_preset_deleted": APITestCase(
        execution_order=4,
        method="GET",
        api_endpoint="/api/effects/energy/presets",
        expected_return_code=200,
        expected_response_keys=["status", "effect", "user_presets"],
        expected_response_values=[
            {"status": "success", "effect": "energy"},
        ],
    ),
    "delete_nonexistent_preset": APITestCase(
        execution_order=5,
        method="DELETE",
        api_endpoint="/api/effects/energy/presets/nonexistent_preset",
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
}
