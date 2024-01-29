# Broadly, this will use our internal HTTP APIs to:
# 1. Set Rainbow effect to device ci-test-jig
# 2. Check that the effect is set
# 3. Clear the effect
# 4. Set "Energy" effect to device ci-test-jig
# 5. Check that the effect is set
# 6. Leave the effect set for other tests
from tests.test_utilities.test_utils import APITestCase

effect_tests = {
    "set_rainbow": APITestCase(
        execution_order=1,
        method="POST",
        api_endpoint="/api/virtuals/ci-test-jig/effects",
        expected_return_code=200,
        payload_to_send={"type": "rainbow"},
        expected_response_keys=["status", "effect"],
        expected_response_values=[
            {"status": "success"},
        ],
    ),
    "check_rainbow_set": APITestCase(
        execution_order=2,
        method="GET",
        api_endpoint="/api/virtuals/ci-test-jig/effects",
        expected_return_code=200,
        expected_response_keys=["effect"],
        expected_response_values=[
            {"effect": {"name": "Rainbow", "type": "rainbow"}},
        ],
    ),
    "clear_rainbow": APITestCase(
        execution_order=3,
        method="DELETE",
        api_endpoint="/api/virtuals/ci-test-jig/effects",
        expected_return_code=200,
        expected_response_keys=["status", "effect"],
        expected_response_values=[{"status": "success", "effect": {}}],
    ),
    "set_energy_effect": APITestCase(
        execution_order=4,
        method="POST",
        api_endpoint="/api/virtuals/ci-test-jig/effects",
        expected_return_code=200,
        payload_to_send={"type": "energy"},
        expected_response_keys=["status", "effect"],
        expected_response_values=[
            {"status": "success"},
        ],
    ),
    "check_energy_set": APITestCase(
        execution_order=5,
        method="GET",
        api_endpoint="/api/virtuals/ci-test-jig/effects",
        expected_return_code=200,
        expected_response_keys=["effect"],
        expected_response_values=[
            {"effect": {"name": "Energy", "type": "energy"}},
        ],
    ),
}
