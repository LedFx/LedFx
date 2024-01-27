import subprocess

import pytest

from tests.test_definitions.devices import device_tests
from tests.test_definitions.effects import effect_tests
from tests.test_definitions.proof_of_life import proof_of_life_tests
from tests.test_utils import SERVER_PATH, EnvironmentCleanup, HTTPSession

# Create a dictionary that contains all the tests - this will be used to dynamically create the test functions as we add more
all_tests = {
    "proof_of_life_tests": proof_of_life_tests,
    "device_tests": device_tests,
    "effect_tests": effect_tests,
}
# Create a list that contains the order in which we want to run the test groups
test_order = ["proof_of_life_tests", "device_tests", "effect_tests"]


@pytest.fixture
def http_session():
    # Create a new HTTPSession for each test
    return HTTPSession()


@pytest.fixture(scope="module", autouse=True)
def setup_and_teardown():
    EnvironmentCleanup.cleanup_test_config_folder(),
    # Start LedFx as a subprocess
    ledfx = subprocess.Popen(
        ["poetry", "run", "ledfx", "--offline", "-c", "debug_config", "-vv"]
    )
    # Run tests
    yield
    # Use the API to shut down LedFx
    EnvironmentCleanup.shutdown_ledfx()
    # Terminate the program
    ledfx.terminate()
    ledfx.wait()


def make_test(test_type, test_name, test_case, order):
    @pytest.mark.order(order)
    def test_run_api_call(http_session):
        # Reminder, the api_endpoint contains a leading slash
        url = f"http://{SERVER_PATH}{test_case.api_endpoint}"
        # check to see if we need to send a payload
        payload = (
            test_case.payload_to_send if test_case.payload_to_send else None
        )
        response = HTTPSession.send_test_api_request(
            self=http_session,
            url=url,
            method=test_case.method,
            payload=payload,
        )
        assert (
            response.status_code == test_case.expected_return_code
        ), f"Expected status code {test_case.expected_return_code}, but got {response.status_code}"
        if test_case.expected_response_keys:
            missing_keys = [
                key
                for key in test_case.expected_response_keys
                if key not in response.json()
            ]
            assert (
                not missing_keys
            ), f"Missing expected keys in response: {missing_keys}"
        if test_case.expected_response_values:
            response_dict = response.json()
            for expected_dict in test_case.expected_response_values:
                for key, value in expected_dict.items():
                    # Check if the key exists in the response and is a dictionary
                    if key in response_dict and isinstance(
                        response_dict[key], dict
                    ):
                        # Check if the expected dictionary is a subset of the response dictionary
                        assert (
                            value.items() <= response_dict[key].items()
                        ), f"Expected {key} to contain {value}, but got {response_dict.get(key)}"
                    else:
                        assert (
                            key in response_dict
                            and response_dict[key] == value
                        ), f"Expected {key} to be {value}, but got {response_dict.get(key)}"

    test_run_api_call.__name__ = f"test_{test_type}_{test_name}"
    return test_run_api_call


for i, test_type in enumerate(test_order):
    tests = all_tests[test_type]
    # Sort the tests by execution_order
    sorted_tests = sorted(
        tests.items(), key=lambda test: test[1].execution_order
    )
    for j, (test_name, test_case) in enumerate(sorted_tests):
        order = i * 100 + j
        globals()[f"test_{test_type}_{test_name}"] = make_test(
            test_type, test_name, test_case, order
        )

if __name__ == "__main__":
    pytest.main()
