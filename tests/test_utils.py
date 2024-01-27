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
SERVER_PATH = f"{BASE_URL}:{BASE_PORT}"


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


class HTTPSession:
    def __init__(
        self,
        retries=5,
        backoff_factor=0.5,
        status_forcelist=(500, 502, 504),
        allowed_methods=frozenset(
            ["HEAD", "TRACE", "GET", "PUT", "POST", "OPTIONS", "DELETE"]
        ),
    ):
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.status_forcelist = status_forcelist
        self.allowed_methods = allowed_methods
        self.session = self.requests_retry_session()

    def requests_retry_session(self):
        session = requests.Session()
        retry = Retry(
            total=None,
            read=self.retries,
            connect=self.retries,
            backoff_factor=self.backoff_factor,
            status_forcelist=self.status_forcelist,
            allowed_methods=self.allowed_methods,
            raise_on_status=False,
            other=self.retries,
        )
        adapter = HTTPAdapter(max_retries=retry)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        return session

    def send_test_api_request(
        self, url, method, payload: Optional[Union[str, dict]] = None
    ):
        headers = {"Content-Type": "application/json"}
        try:
            if method == "GET":
                response = self.session.get(url, headers=headers)
            elif method == "POST":
                response = self.session.post(
                    url, json=payload, headers=headers
                )
            elif method == "PUT":
                response = self.session.put(url, json=payload, headers=headers)
            elif method == "DELETE":
                response = self.session.delete(
                    url, json=payload, headers=headers
                )
            else:
                raise ValueError(f"Invalid method: {method}")
        except Exception as e:
            pytest.fail(
                f"An error occurred while sending the API request: {str(e)}"
            )
        return response


class EnvironmentCleanup:
    @staticmethod
    def shutdown_ledfx():
        _ = requests.post(f"http://{SERVER_PATH}/api/power", json={})
        while True:
            try:
                response = requests.get(
                    f"http://{SERVER_PATH}/api/info", timeout=1
                )
                if response.status_code != 200:
                    break
                time.sleep(0.5)
            except requests.exceptions.ConnectionError:
                break
        time.sleep(1)

    @staticmethod
    def copy_log_file_to_tests_folder():
        current_dir = os.getcwd()
        ledfx_log_file = os.path.join(current_dir, "debug_config", "LedFx.log")
        destination = os.path.join(current_dir, "LedFx.log")
        if os.path.exists(ledfx_log_file):
            shutil.copyfile(ledfx_log_file, destination)

    @staticmethod
    def cleanup_test_config_folder():
        current_dir = os.getcwd()
        ci_test_dir = os.path.join(current_dir, "debug_config")
        for _ in range(10):
            if os.path.exists(ci_test_dir):
                try:
                    shutil.rmtree(ci_test_dir)
                    break
                except Exception as e:
                    pass
            time.sleep(0.1)


class SystemInfo:
    @staticmethod
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
        max_fps_ticks = np.ceil(
            (1 / max_fps_target) / (sleep_res * mult)
        ).astype(int)
        min_fps_ticks = np.ceil(
            (1 / min_fps_target) / (sleep_res * mult)
        ).astype(int)
        tick_range = reversed(range(max_fps_ticks, min_fps_ticks))
        return {int(1 / (sleep_res * mult * i)): i * mult for i in tick_range}

    @staticmethod
    def default_fps():
        available_fps = SystemInfo.calc_available_fps()
        default_fps = next(
            (f for f in available_fps if f >= 60), list(available_fps)[-1]
        )
        return default_fps
