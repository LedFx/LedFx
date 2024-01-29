import pytest
from test_utilities.test_utils import SERVER_PATH, APITestCase, HTTPSession


def get_ledfx_effects():
    effects_to_test = {}
    http_session = HTTPSession()
    try:
        response = http_session.send_test_api_request(
            url=f"http://{SERVER_PATH}/api/schema",
            method="GET",
        )
    except Exception as e:
        pytest.fail("Unable to get Schema from LedFx.")
    schema = response.json()
    execution_order = 1  # Start execution order from 1
    for effect_id, effect_details in schema["effects"].items():
        # Set the effect
        set_effect_test_case = APITestCase(
            execution_order=execution_order,
            method="POST",
            api_endpoint="/api/virtuals/ci-test-jig/effects",
            expected_return_code=200,
            payload_to_send={"type": effect_id},
            expected_response_keys=["status", "effect"],
            expected_response_values=[
                {"status": "success"},
            ],
            # Let the effect run for a bit before checking its still active
            sleep_after_test=0.1,
        )
        effects_to_test[effect_id + "_set"] = set_effect_test_case

        # Increment execution order for the check operation
        execution_order += 1

        # Check the effect was set
        check_effect_test_case = APITestCase(
            execution_order=execution_order,
            method="GET",
            api_endpoint="/api/virtuals/ci-test-jig/effects",
            expected_return_code=200,
            expected_response_keys=["effect"],
            expected_response_values=[
                {
                    "effect": {
                        "name": effect_details["name"],
                        "type": effect_id,
                    }
                },
            ],
        )
        effects_to_test[effect_id + "_check"] = check_effect_test_case

        # Increment execution order for the next effect
        execution_order += 1

    return effects_to_test
