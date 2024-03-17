import random

import pytest
from test_utilities.test_utils import SERVER_PATH, APITestCase, HTTPSession

CONFIG_KEYS_TO_TEST = [
    "audio",
]


def get_ledfx_audio_configs():
    audio_configs_to_test = {}
    http_session = HTTPSession()
    try:
        response = http_session.send_test_api_request(
            url=f"http://{SERVER_PATH}/api/schema",
            method="GET",
        )
    except Exception as e:
        pytest.fail("Unable to get Schema from LedFx.")
    schema = response.json()
    # drop any keys that are not in config_keys_to_test
    schema = {k: v for k, v in schema.items() if k in CONFIG_KEYS_TO_TEST}

    execution_order = 1  # Start execution order from 1
    # using the returned schema, generate test cases for each
    for config_id, config_details in schema.items():
        # Iterate through each config option in the config details
        for config_option, option_details in config_details["schema"][
            "properties"
        ].items():
            # Check if the config option has an enum
            if "enum" in option_details:
                # Iterate over each value in the enum
                for enum_value in option_details["enum"]:
                    # Set the config
                    set_config_test_case = APITestCase(
                        execution_order=execution_order,
                        method="PUT",
                        api_endpoint="/api/config",
                        expected_return_code=200,
                        payload_to_send={
                            config_id: {config_option: enum_value}
                        },
                        expected_response_keys=["status", "payload"],
                        expected_response_values=[
                            {
                                "status": "success",
                            }
                        ],
                        # Let the config run for a bit before checking its still active
                        sleep_after_test=0.5,
                    )
                    audio_configs_to_test[
                        config_id
                        + "_"
                        + config_option
                        + "_"
                        + str(enum_value)
                        + "_set"
                    ] = set_config_test_case

                    # Increment execution order
                    execution_order += 1
            # Check if the config option has a minimum and maximum
            if "minimum" in option_details and "maximum" in option_details:
                # Generate 10 random tests between the minimum and maximum
                for _ in range(10):
                    random_value = random.uniform(
                        option_details["minimum"], option_details["maximum"]
                    )
                    # Set the config
                    set_config_test_case = APITestCase(
                        execution_order=execution_order,
                        method="PUT",
                        api_endpoint="/api/config",
                        expected_return_code=200,
                        payload_to_send={
                            config_id: {config_option: random_value}
                        },
                        expected_response_keys=["status", "payload"],
                        expected_response_values=[
                            {
                                "status": "success",
                            }
                        ],
                        # Let the config run for a bit before checking its still active
                        sleep_after_test=0.5,
                    )
                    audio_configs_to_test[
                        config_id
                        + "_"
                        + config_option
                        + "_"
                        + str(random_value)
                        + "_set"
                    ] = set_config_test_case

                    # Increment execution order
                    execution_order += 1

    return audio_configs_to_test
