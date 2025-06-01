import time

import pytest

# Remember to import the test groups here if you add a new one
from tests.conftest import all_effects, audio_configs
from tests.test_definitions.coexistance import coexistance_tests
from tests.test_definitions.devices import device_tests
from tests.test_definitions.effects import effect_tests
from tests.test_definitions.proof_of_life import proof_of_life_tests
from tests.test_definitions.virtual_config import virtual_config_tests
from tests.test_utilities.consts import SERVER_PATH
from tests.test_utilities.test_utils import HTTPSession


@pytest.fixture
def http_session():
    # Create a new HTTPSession for each test
    return HTTPSession()


@pytest.fixture(scope="session", autouse=True)
def setup_and_teardown(request):
    yield


# Define a list of all test groups
# Remember to add any new test groups here
test_groups = [
    ("proof_of_life_tests", proof_of_life_tests),
    ("device_tests", device_tests),
    ("effect_tests", effect_tests),
    ("all_effects", all_effects),
    ("audio_configs", audio_configs),
    ("virtual_config_tests", virtual_config_tests),
    ("coexistance_tests", coexistance_tests),
]

# Define a list of all test cases
test_cases = []
for group_name, group in test_groups:
    for name, case in sorted(
        group.items(), key=lambda item: item[1].execution_order
    ):
        test_cases.append((group_name, name, case))


# Parametrize the test function
@pytest.mark.parametrize("group_name,test_name,case", test_cases)
def test_api(group_name, test_name, case, http_session):
    # Run the test case
    url = f"http://{SERVER_PATH}{case.api_endpoint}"
    payload = case.payload_to_send if case.payload_to_send else None
    response = HTTPSession.send_test_api_request(
        self=http_session,
        url=url,
        method=case.method,
        payload=payload,
    )
    assert (
        response.status_code == case.expected_return_code
    ), f"Expected status code {case.expected_return_code}, but got {response.status_code}"
    if case.expected_response_keys:
        missing_keys = [
            key
            for key in case.expected_response_keys
            if key not in response.json()
        ]
        assert (
            not missing_keys
        ), f"Missing expected keys in response: {missing_keys}"
    if case.expected_response_values:
        response_dict = response.json()
        for expected_dict in case.expected_response_values:
            for key, value in expected_dict.items():
                if key in response_dict and isinstance(
                    response_dict[key], dict
                ):
                    try:
                        assert value.items() <= response_dict[key].items()
                    except AssertionError as exc:
                        error_detail = find_first_error(
                            value, response_dict[key]
                        )
                        msg = (
                            f"Expected {key} to contain \n{value}, "
                            f"\n but got \n{response_dict.get(key)}. "
                            f"\n\nDetail: {error_detail}"
                        )
                        raise AssertionError(msg) from exc
                else:
                    try:
                        assert (
                            key in response_dict
                            and response_dict[key] == value
                        )
                    except AssertionError as exc:
                        error_detail = find_first_error(
                            value, response_dict.get(key)
                        )
                        msg = (
                            f"Expected {key} to be \n{value}, "
                            f"\n but got \n{response_dict.get(key)}. "
                            f"\n\nDetail: {error_detail}"
                        )
                        raise AssertionError(msg) from exc
    if case.sleep_after_test:
        time.sleep(case.sleep_after_test)


def find_first_error(expect, got, path=""):
    """
    Find the first error in the expected and actual values, including the key path.
    """
    if isinstance(expect, dict) and isinstance(got, dict):
        for key in expect:
            current_path = f"{path}.{key}" if path else key
            if key not in got:
                return f"Key '{current_path}' not found in actual response"
            error = find_first_error(expect[key], got[key], current_path)
            if error:
                return error
        return None
    elif expect != got:
        return f"At '{path}': expected '{expect}', but got '{got}'"
    return None


if __name__ == "__main__":
    pytest.main()
