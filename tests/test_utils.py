import os
import shutil
import sys
import time
from dataclasses import dataclass
from typing import Any, Literal, Optional, Union

import numpy as np
import pytest
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

BASE_URL = "127.0.0.1"
BASE_PORT = 8888


@dataclass
class APITestCase:
    """
    Represents a test case for the test runner.

    Attributes:
        execution_order (int): The order in which the test case should be executed. This order is within the test type/grouping, not the overall order of the tests.
        method (str): The HTTP method to be used for the API request.
        api_endpoint (str): The endpoint of the API to be tested, including the leading slash.
        expected_return_code (int): The expected return code of the API response.
        payload_to_send (Dict[str, Any], optional): The payload to be sent with the API request.
        expected_response_keys (List[str], optional): The expected keys in the API response payload. You don't need to specify the entire payload, just the keys you want to check.
        expected_payload_values (List[Dict[str, Any]], optional): The expected values in the API response payload. You don't need to specify the entire payload, just the key:values you want to check.
    """

    execution_order: int
    method: Literal["GET", "POST", "PUT", "DELETE"]
    api_endpoint: str
    expected_return_code: int
    payload_to_send: dict[str, Any] = None
    expected_response_keys: list[str] = None
    expected_response_values: list[dict[str, Any]] = None


def send_test_api_request(
    url, method, payload: Optional[Union[str, dict]] = None, retries=5
):
    """
    Sends a test API request to the specified URL using the specified HTTP method.

    Args:
        url (str): The URL to send the request to.
        method (str): The HTTP method to use for the request (e.g., "GET", "POST", "PUT", "DELETE").
        payload (Optional[Union[str, dict]]): The payload to include in the request (optional).
        retries (int): The number of times to retry the request in case of failure (default is 5).

    Returns:
        requests.Response: The response object containing the server's response to the request.

    Raises:
        ValueError: If an invalid HTTP method is provided.

    """
    headers = {"Content-Type": "application/json"}
    session = requests_retry_session(retries=retries)

    try:
        if method == "GET":
            response = session.get(url, headers=headers)
        elif method == "POST":
            response = session.post(url, json=payload, headers=headers)
        elif method == "PUT":
            response = session.put(url, json=payload, headers=headers)
        elif method == "DELETE":
            response = session.delete(url, json=payload, headers=headers)
        else:
            raise ValueError(f"Invalid method: {method}")
    except Exception as e:
        pytest.fail(
            f"An error occurred while sending the API request: {str(e)}"
        )

    return response


def requests_retry_session(
    retries=5,
    backoff_factor=0.5,
    status_forcelist=(500, 502, 504),
    allowed_methods=frozenset(
        ["HEAD", "TRACE", "GET", "PUT", "POST", "OPTIONS", "DELETE"]
    ),
    session=None,
):
    """
    Creates a session object with retry functionality for making HTTP requests.

    Args:
        retries (int): The number of times to retry the request in case of failure. Default is 5.
        backoff_factor (float): The backoff factor for exponential backoff between retries. Default is 0.5.
        status_forcelist (tuple): The HTTP status codes that should trigger a retry. Default is (500, 502, 504).
        allowed_methods (frozenset): The set of allowed HTTP methods. Default is {'HEAD', 'TRACE', 'GET', 'PUT', 'POST', 'OPTIONS', 'DELETE'}.
        session (requests.Session): An existing session object to use. If not provided, a new session will be created.

    Returns:
        requests.Session: The session object with retry functionality.

    """
    session = session or requests.Session()
    retry = Retry(
        total=None,
        read=retries,
        connect=retries,
        backoff_factor=backoff_factor,
        status_forcelist=status_forcelist,
        allowed_methods=allowed_methods,
        raise_on_status=False,
        other=retries,
    )
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    return session


def shutdown_ledfx():
    """
    Sends a POST request to the LeDFx server to shut it down and waits until the server is no longer accessible.

    Returns:
        None
    """
    _ = requests_retry_session().post(
        f"http://{BASE_URL}:{BASE_PORT}/api/power", json={}
    )
    while True:
        try:
            response = requests.get(
                f"http://{BASE_URL}:{BASE_PORT}/api/info", timeout=1
            )

            if response.status_code != 200:
                break
            time.sleep(0.5)
        except requests.exceptions.ConnectionError:
            break
    # Wait 1s for the logs to be written to the file and the file to be closed
    time.sleep(1)


def calc_available_fps():
    """
    Calculate the available frames per second (fps) based on the system's clock resolution.

    Returns:
        dict: A dictionary where the keys represent the fps and the values represent the corresponding multiplier.
    """
    if (
        sys.version_info[0] == 3 and sys.version_info[1] >= 11
    ) or sys.version_info[0] >= 4:
        clock_source = "perf_counter"
    else:
        clock_source = "monotonic"

    sleep_res = time.get_clock_info(clock_source).resolution

    if sleep_res < 0.001:
        mult = int(0.001 / sleep_res)
    else:
        mult = 1

    max_fps_target = 126
    min_fps_target = 10

    max_fps_ticks = np.ceil((1 / max_fps_target) / (sleep_res * mult)).astype(
        int
    )
    min_fps_ticks = np.ceil((1 / min_fps_target) / (sleep_res * mult)).astype(
        int
    )
    tick_range = reversed(range(max_fps_ticks, min_fps_ticks))
    return {int(1 / (sleep_res * mult * i)): i * mult for i in tick_range}


def copy_log_file_to_tests_folder():
    """
    Moves the log file from the 'debug_config' folder to the current directory.

    This function checks if the log file exists in the 'debug_config' folder and
    then moves it to the current directory.

    """
    current_dir = os.getcwd()
    ledfx_log_file = os.path.join(os.getcwd(), "debug_config", "LedFx.log")
    destination = os.path.join(current_dir, "LedFx.log")
    if os.path.exists(ledfx_log_file):
        shutil.copyfile(ledfx_log_file, destination)


def cleanup_test_config_folder():
    """
    Deletes the debug_config folder and everything in it.

    This function removes the 'debug_config' folder and all its contents from the current working directory.
    If the folder does not exist, no action is taken.

    Uses a retry loop to ensure that the folder is deleted - useful for rapid test cycles.
    """
    current_dir = os.getcwd()
    ci_test_dir = os.path.join(current_dir, "debug_config")

    for _ in range(10):
        if os.path.exists(ci_test_dir):
            try:
                shutil.rmtree(ci_test_dir)
                break  # If the directory was successfully deleted, break the loop
            except Exception as e:
                pass  # If the directory couldn't be deleted, try again
        time.sleep(0.1)  # Wait for 100ms before the next attempt
