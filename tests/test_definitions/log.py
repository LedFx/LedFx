from tests.test_utilities.test_utils import APITestCase

log_api_tests = {
    "post_ascii_log": APITestCase(
        execution_order=1,
        method="POST",
        api_endpoint="/api/log",
        expected_return_code=200,
        payload_to_send={"text": "Hello from test!"},
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
        sleep_after_test=1.1,
    ),
    "post_non_ascii_log": APITestCase(
        execution_order=2,
        method="POST",
        api_endpoint="/api/log",
        expected_return_code=200,
        payload_to_send={"text": "Héllo 世界!"},
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
        sleep_after_test=1.1,
    ),
    "post_too_long_log": APITestCase(
        execution_order=3,
        method="POST",
        api_endpoint="/api/log",
        expected_return_code=200,
        payload_to_send={"text": "A" * 300},
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
        # No sleep, so the next test triggers rate limit
    ),
    "post_rate_limited_log": APITestCase(
        execution_order=4,
        method="POST",
        api_endpoint="/api/log",
        expected_return_code=200,
        payload_to_send={"text": "This should be rate limited."},
        expected_response_keys=["status"],
        expected_response_values=[{"status": "failed"}],
        sleep_after_test=1.1,
    ),
    "post_empty_log": APITestCase(
        execution_order=5,
        method="POST",
        api_endpoint="/api/log",
        expected_return_code=200,
        payload_to_send={"text": "   "},
        expected_response_keys=["status"],
        expected_response_values=[{"status": "failed"}],
        sleep_after_test=1.1,
    ),
}
