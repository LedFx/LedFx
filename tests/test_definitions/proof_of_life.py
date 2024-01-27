from tests.test_utils import APITestCase

proof_of_life_tests = {
    "quick_health_check": APITestCase(
        execution_order=1,
        method="GET",
        api_endpoint="/api/info",
        expected_return_code=200,
        expected_response_keys=["url", "name", "version", "developer_mode"],
    ),
    "get_audio_devices": APITestCase(
        execution_order=2,
        method="GET",
        api_endpoint="/api/audio/devices",
        expected_return_code=200,
        expected_response_keys=["active_device_index", "devices"],
    ),
    "color_endpoint": APITestCase(
        execution_order=3,
        method="GET",
        api_endpoint="/api/colors",
        expected_return_code=200,
        expected_response_keys=["colors", "gradients"],
    ),
    "config_endpoint": APITestCase(
        execution_order=4,
        method="GET",
        api_endpoint="/api/config",
        expected_return_code=200,
    ),
    "effects_endpoint_empty": APITestCase(
        execution_order=5,
        method="GET",
        api_endpoint="/api/effects",
        expected_return_code=200,
        expected_response_keys=["status", "effects"],
    ),
    "devices_endpoint_empty": APITestCase(
        execution_order=6,
        method="GET",
        api_endpoint="/api/devices",
        expected_return_code=200,
        expected_response_keys=["status", "devices"],
    ),
    "find_devices_get": APITestCase(
        execution_order=7,
        method="GET",
        api_endpoint="/api/find_devices",
        expected_return_code=200,
        expected_response_keys=["status"],
    ),
    "find_devices_post": APITestCase(
        execution_order=8,
        method="POST",
        api_endpoint="/api/find_devices",
        expected_return_code=200,
        expected_response_keys=["status"],
        payload_to_send={"name_to_icon": {"test": "test"}},
    ),
    "scenes_list_empty": APITestCase(
        execution_order=9,
        method="GET",
        api_endpoint="/api/scenes",
        expected_return_code=200,
        expected_response_keys=["status", "scenes"],
    ),
}
