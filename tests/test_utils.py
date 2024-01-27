import os
import shutil
import sys
import time
from dataclasses import dataclass
from typing import Any

import numpy as np
import pytest
import requests

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
    method: str in ["GET", "POST", "PUT", "DELETE"]  # noqa: F821
    api_endpoint: str
    expected_return_code: int
    payload_to_send: dict[str, Any] = None
    expected_response_keys: list[str] = None
    expected_response_values: list[dict[str, Any]] = None


def send_test_api_request(url, method, payload):
    headers = {"Content-Type": "application/json"}
    try:
        if method == "GET":
            response = requests.get(url, headers=headers)
        elif method == "POST":
            response = requests.post(url, json=payload, headers=headers)
        elif method == "PUT":
            response = requests.put(url, json=payload, headers=headers)
        elif method == "DELETE":
            response = requests.delete(url, json=payload, headers=headers)
        else:
            raise ValueError(f"Invalid method: {method}")
    except Exception as e:
        pytest.fail(
            f"An error occurred while sending the API request: {str(e)}"
        )
    return response


def clear_config():
    print("Clearing configuration...")
    _ = requests.delete(f"http://{BASE_URL}:{BASE_PORT}/api/config")
    print("Waiting for LedFx to restart...")
    time.sleep(3)
    while True:
        response = requests.get(
            f"http://{BASE_URL}:{BASE_PORT}/api/info", timeout=1
        )
        print("LedFx still isn't awake...")
        time.sleep(1)
        if response.status_code == 200:
            print("LedFx restarted, ready to test.")
            break


def shutdown_ledfx():
    print("Shutting down LedFx...")
    _ = requests.post(f"http://{BASE_URL}:{BASE_PORT}/api/power", json={})
    print("Waiting for LedFx to shutdown...")
    time.sleep(3)
    while True:
        try:
            response = requests.post(
                f"http://{BASE_URL}:{BASE_PORT}/api/info", timeout=1
            )
            print("LedFx still isn't shutdown...")
            time.sleep(1)
            if response.status_code != 200:
                print("LedFx shutdown complete.")
                break
        except requests.exceptions.ConnectionError:
            print("LedFx shutdown complete.")
            break


def calc_available_fps():
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


def get_default_config_directory() -> str:
    """Get the default configuration directory (which also has the log file, which is why we're here"""

    base_dir = (
        os.getenv("APPDATA") if os.name == "nt" else os.path.expanduser("~")
    )
    return os.path.join(base_dir, ".ledfx")


def get_log_file_path():
    """Get the log file from the default configuration directory"""
    log_file = os.path.join(get_default_config_directory(), "LedFx.log")
    return log_file


def move_log_file_to_tests_folder():
    """Move the log file from the default configuration directory to the tests folder"""
    log_file = get_log_file_path()
    current_dir = os.getcwd()
    destination = os.path.join(current_dir, "LedFx.log")
    if os.path.exists(log_file):
        shutil.move(log_file, destination)
