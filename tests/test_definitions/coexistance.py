from tests.test_utilities.test_utils import APITestCase

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
    "cleanup_osc_1": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-osc-1",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "cleanup_osc_2": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-osc-2",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "create_ddp_device_1": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "ddp",
            "config": {
                "pixel_count": 10,
                "port": 4048,
                "name": "test_ddp_1",
                "ip_address": "1.2.3.4",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "payload": {
                    "type": "success",
                    "reason": "Created device test_ddp_1",
                },
            },
            # we are just happy it was created, we don't care about the device details
        ],
    ),
    # Try to create DDP device on e131 port, should fail
    "create_ddp_device_2_on_e131_port_bad": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "ddp",
            "config": {
                "pixel_count": 10,
                "port": 5568,
                "name": "test_ddp_2",
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
    # Try to create DDP device on default port, should fail
    "create_ddp_device_3_on_default_bad": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "ddp",
            "config": {
                "pixel_count": 10,
                "port": 4048,
                "name": "test_ddp_3",
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
    # Try to create DDP device on default port, but differe IP should pass
    "create_ddp_device_4_on_default_new_ip_good": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "ddp",
            "config": {
                "pixel_count": 10,
                "port": 4048,
                "name": "test_ddp_4",
                "ip_address": "1.2.3.5",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "payload": {
                    "type": "success",
                    "reason": "Created device test_ddp_4",
                },
            },
            # we are just happy it was created, we don't care about the device details
        ],
    ),
    # Try to create DDP devuce on some other port, should succeed
    "create_ddp_device_5_on_default_good": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "ddp",
            "config": {
                "pixel_count": 10,
                "port": 4049,
                "name": "test_ddp_5",
                "ip_address": "1.2.3.4",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "payload": {
                    "type": "success",
                    "reason": "Created device test_ddp_5",
                },
            },
            # we are just happy it was created, we don't care about the device details
        ],
    ),
    # Create UDP device on default, should allow due to seperate port definition
    "create_udp_device_1_default_good": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "udp",
            "config": {
                "pixel_count": 1,
                "port": 21324,
                "name": "test_udp_1",
                "ip_address": "1.2.3.4",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "payload": {
                    "type": "success",
                    "reason": "Created device test_udp_1",
                },
            },
            # we are just happy it was created, we don't care about the device details
        ],
    ),
    # Create UDP device on same port as DDP, should fail due to port conflict
    "create_udp_device_2_on_ddp_port_bad": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "udp",
            "config": {
                "pixel_count": 1,
                "port": 4048,
                "name": "test_udp_2",
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
    "cleanup_ddp_1": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-ddp-1",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "cleanup_ddp_4": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-ddp-4",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "cleanup_ddp_5": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-ddp-5",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "cleanup_udp_1": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/devices/test-udp-1",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
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
