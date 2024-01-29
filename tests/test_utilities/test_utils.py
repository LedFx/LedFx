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

from tests.test_utilities.consts import SERVER_PATH


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
        sleep_after_test (float, optional): The number of seconds to sleep after the test is complete. Defaults to 0.0. This is useful for tests that require a delay before the next test can be run.
    """

    execution_order: int
    method: Literal["GET", "POST", "PUT", "DELETE"]
    api_endpoint: str
    expected_return_code: int
    payload_to_send: dict[str, Any] = None
    expected_response_keys: list[str] = None
    expected_response_values: list[dict[str, Any]] = None
    sleep_after_test: float = 0


class HTTPSession:
    def __init__(
        self,
        retries=5,
        backoff_factor=0.25,
        status_forcelist=(500, 502, 504),
        allowed_methods=frozenset(
            ["HEAD", "TRACE", "GET", "PUT", "POST", "OPTIONS", "DELETE"]
        ),
    ):
        """
        Initialize the RetrySession object.

        Args:
            retries (int): The maximum number of retries for a request. Default is 5.
            backoff_factor (float): The backoff factor between retries. Default is 0.25.
            status_forcelist (tuple): The HTTP status codes that trigger a retry. Default is (500, 502, 504).
            allowed_methods (frozenset): The set of allowed HTTP methods. Default is {"HEAD", "TRACE", "GET", "PUT", "POST", "OPTIONS", "DELETE"}.
        """
        self.retries = retries
        self.backoff_factor = backoff_factor
        self.status_forcelist = status_forcelist
        self.allowed_methods = allowed_methods
        self.session = self.requests_retry_session()

    def requests_retry_session(self):
        """
        Creates a session object with retry functionality for making HTTP requests.

        Returns:
            requests.Session: A session object with retry functionality.
        """
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
        """
        Sends a test API request to the specified URL using the specified HTTP method.

        Args:
            url (str): The URL to send the request to.
            method (str): The HTTP method to use for the request (GET, POST, PUT, DELETE).
            payload (Optional[Union[str, dict]], optional): The payload to include in the request. Defaults to None.

        Returns:
            requests.Response: The response object containing the server's response to the request.

        Raises:
            ValueError: If an invalid HTTP method is provided.

        """
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
        """
        Shuts down the LedFx server by sending a POST request to the power endpoint
        and waits for the server to stop responding.

        Returns:
            None
        """
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
    def cleanup_test_config_folder():
        """
        Cleans up the test configuration folder by removing it if it exists.

        This function checks if the 'debug_config' folder exists and attempts to remove it.
        If the folder cannot be removed, it waits for a short period of time and retries.
        The function will make up to 10 attempts before giving up.

        The delay -> retry is used as LedFx can take a bit of time to shut down and release the

        Raises:
            Any exception that occurs during the removal of the folder.

        """
        current_dir = os.getcwd()
        ci_test_dir = os.path.join(current_dir, "debug_config")

        # If the directory doesn't exist, return immediately
        if not os.path.exists(ci_test_dir):
            return

        for idx in range(10):
            try:
                shutil.rmtree(ci_test_dir)
                break
            except Exception as e:
                time.sleep(idx / 10)
        else:
            pytest.fail("Unable to remove the test config folder.")

    @staticmethod
    def ledfx_is_alive():
        """
        Checks to see if LedFx is running by sending a GET request to the schema endpoint.

        Returns:
            bool: True if LedFx is running, False otherwise.
        """
        try:
            response = requests.get(
                f"http://{SERVER_PATH}/api/info", timeout=1
            )
            if response.status_code == 200:
                # LedFx has returned a response, so it is running, but likely still hydrating the schema
                # We will wait until it is fully hydrated
                while True:
                    old_schema = requests.get(
                        f"http://{SERVER_PATH}/api/schema", timeout=1
                    )
                    time.sleep(0.1)
                    new_schema = requests.get(
                        f"http://{SERVER_PATH}/api/schema", timeout=1
                    )
                    if old_schema.json() == new_schema.json():
                        break
                time.sleep(2)
                return True
        except requests.exceptions.ConnectionError:
            pass
        return False


class SystemInfo:
    @staticmethod
    def calc_available_fps():
        """
        Calculate the available frames per second (fps) based on the system's clock resolution.
        Note: This comes from the ledfx/utils.py file

        Returns:
            dict: A dictionary where the keys represent the fps and the values represent the corresponding tick value.
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
