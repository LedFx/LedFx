from tests.test_utilities.test_utils import APITestCase, SystemInfo

test_count = 1

coexistance_tests = {
    "create_e131_device_1": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "e131",
            "config": {
                "pixel_count": 1,
                "universe": 50,
                "name": "test_e131_1",
                "ip_address": "1.2.3.4",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "payload": {
                    "type": "success",
                    "reason": "Created device test_e131_1",
                },
            },
            # we are just happy it was created, we don't care about the device details
        ],
    ),
    "create_artnet_device_1_with_different_universe_good": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "artnet",
            "config": {
                "pixel_count": 10,
                "universe": 10,
                "port": 6454,
                "ip_address": "1.2.3.4",
                "name": "test artnet_1",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {
                "status": "success",
                "payload": {
                    "type": "success",
                    "reason": "Created device test artnet_1",
                },
                # we are just happy it was created, we don't care about the device details
            }
        ],
    ),
    "cleanup_artnet_1": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-artnet-1",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "create_artnet_device_2_with_same_universe_bad": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "artnet",
            "config": {
                "pixel_count": 10,
                "universe": 50,
                "port": 6454,
                "ip_address": "1.2.3.4",
                "name": "test artnet_2",
            },
        },
        expected_response_keys=["status", "payload"],
        expected_response_values=[
            {
                "status": "failed",
                "payload": {
                    "type": "error",
                },
            }
        ],
    ),
    "cleanup_artnet_1": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-artnet-1",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "cleanup_artnet_2": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-artnet-2",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "create_openrgb_device_1": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "openrgb",
            "config": {
                "openrgb_id": 1,
                "pixel_count": 1,
                "port": 6742,
                "name": "openrgb_1",
                "ip_address": "1.2.3.4",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "payload": {
                    "type": "success",
                    "reason": "Created device openrgb_1",
                },
            },
            # we are just happy it was created, we don't care about the device details
        ],
    ),
    "create_openrgb_device_2_new_id_good": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "openrgb",
            "config": {
                "openrgb_id": 2,
                "pixel_count": 1,
                "port": 6742,
                "name": "openrgb_2",
                "ip_address": "1.2.3.4",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "payload": {
                    "type": "success",
                    "reason": "Created device openrgb_2",
                },
            },
            # we are just happy it was created, we don't care about the device details
        ],
    ),
    "create_openrgb_device_3_same_id_bad": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "openrgb",
            "config": {
                "openrgb_id": 1,
                "pixel_count": 1,
                "port": 6742,
                "name": "openrgb_3",
                "ip_address": "1.2.3.4",
            },
        },
        expected_response_keys=["status", "payload"],
        expected_response_values=[
            {"status": "failed"},
            {
                "payload": {
                    "type": "error",
                },
            },
        ],
    ),
    "cleanup_openrgb_1": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-openrgb-1",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "cleanup_openrgb_2": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-openrgb-2",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "cleanup_openrgb_3": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-openrgb-3",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "create_osc_device_1": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "osc",
            "config": {
                "port": 9000,
                "pixel_count": 1,
                "starting_addr": 0,
                "path": "/0/dmx/light1",
                "ip_address": "1.2.3.4",
                "name": "test_osc_1",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "payload": {
                    "type": "success",
                    "reason": "Created device test_osc_1",
                },
            },
            # we are just happy it was created, we don't care about the device details
        ],
    ),
    "create_osc_device_2_path_good": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "osc",
            "config": {
                "port": 9000,
                "pixel_count": 1,
                "starting_addr": 0,
                "path": "/0/dmx/light2",
                "ip_address": "1.2.3.4",
                "name": "test_osc_2",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "payload": {
                    "type": "success",
                    "reason": "Created device test_osc_2",
                },
            },
            # we are just happy it was created, we don't care about the device details
        ],
    ),
    "create_osc_device_3_path_bad": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "osc",
            "config": {
                "port": 9000,
                "pixel_count": 1,
                "starting_addr": 0,
                "path": "/0/dmx/light1",
                "name": "test_osc3",
                "ip_address": "1.2.3.4",
            },
        },
        expected_response_keys=["status", "payload"],
        expected_response_values=[
            {"status": "failed"},
            {
                "payload": {
                    "type": "error",
                },
            },
        ],
    ),
    # TODO: add test cases for general port seperated
    # TODO: add test cases for general port seperated
    # TODO: add test cases for general port seperated
    # TODO: add test cases for general port seperated
    # TODO: add test cases for general port seperated
    # TODO: add test cases for general port seperated
    "cleanup_e131": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-e131-1",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
}
