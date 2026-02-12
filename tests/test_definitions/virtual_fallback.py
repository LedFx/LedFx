from tests.test_utilities.test_utils import APITestCase, SystemInfo

test_count = 1

virtual_fallback_tests = {
    # Create dummy device 2 (used for fallback tests)
    "create_dummy_device_2": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "dummy",
            "config": {
                "icon_name": "mdi:led-strip",
                "center_offset": 0,
                "refresh_rate": SystemInfo.default_fps(),
                "pixel_count": 128,
                "name": "test dummy 2",
            },
        },
        expected_response_keys=["status", "payload", "device"],
        expected_response_values=[
            {"status": "success"},
            {
                "device": {
                    "type": "dummy",
                    "config": {
                        "icon_name": "mdi:led-strip",
                        "center_offset": 0,
                        "refresh_rate": SystemInfo.default_fps(),
                        "pixel_count": 128,
                        "name": "test dummy 2",
                    },
                    "id": "test-dummy-2",
                    "virtuals": [],
                }
            },
        ],
    ),
    # Set rainbow effect using built-in preset before fallback
    "set_builtin_rainbow_effect": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="PUT",
        api_endpoint="/api/virtuals/test-dummy-2/presets",
        expected_return_code=200,
        payload_to_send={
            "category": "ledfx_presets",
            "effect_id": "rainbow",
            "preset_id": "cascade",
        },
        expected_response_keys=["status", "effect"],
        expected_response_values=[
            {"status": "success"},
        ],
        sleep_after_test=0.5,
    ),
    # Set effect with fallback (triggers fallback on top of rainbow)
    "set_effect_to_virtual_with_fallback": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="POST",
        api_endpoint="/api/virtuals/test-dummy-2/effects",
        expected_return_code=200,
        payload_to_send={"type": "bar", "fallback": 2.0},
        expected_response_keys=["status", "effect"],
        expected_response_values=[
            {"status": "success"},
        ],
        sleep_after_test=1.0,
    ),
    # Get effect before fallback
    "get_effect_from_virtual_before_fallback": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="GET",
        api_endpoint="/api/virtuals/test-dummy-2/effects",
        expected_return_code=200,
        payload_to_send={},
        expected_response_keys=["effect"],
        expected_response_values=[
            {
                "effect": {
                    "config": {
                        "color_step": 0.125,
                        "gradient": "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(255, 120, 0) 14%, rgb(255, 200, 0) 28%, rgb(0, 255, 0) 42%, rgb(0, 199, 140) 56%, rgb(0, 0, 255) 70%, rgb(128, 0, 128) 84%, rgb(255, 0, 178) 98%)",
                        "mirror": False,
                        "mode": "wipe",
                        "flip": False,
                        "brightness": 1.0,
                        "blur": 0.0,
                        "beat_skip": "none",
                        "skip_every": 1,
                        "beat_offset": 0.0,
                        "ease_method": "ease_out",
                        "gradient_roll": 0.0,
                        "background_color": "#000000",
                        "background_brightness": 1.0,
                        "diag": False,
                    },
                    "name": "Bar",
                    "type": "bar",
                }
            }
        ],
        sleep_after_test=1.4,
    ),
    # Get effect after fallback
    "get_effect_from_virtual_after_fallack": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="GET",
        api_endpoint="/api/virtuals/test-dummy-2/effects",
        expected_return_code=200,
        payload_to_send={},
        expected_response_keys=["effect"],
        expected_response_values=[
            {
                "effect": {
                    "config": {
                        "background_brightness": 1.0,
                        "background_color": "#000000",
                        "blur": 7.7,
                        "brightness": 1.0,
                        "flip": False,
                        "frequency": 0.32,
                        "mirror": True,
                        "speed": 0.3,
                        "diag": False,
                    },
                    "name": "Rainbow",
                    "type": "rainbow",
                }
            }
        ],
    ),
    # Cleanup dummy device 2
    "cleanup_dummy_device_2": APITestCase(
        execution_order=(test_count := test_count + 1),
        method="DELETE",
        api_endpoint="/api/virtuals/test-dummy-2",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
        sleep_after_test=1.0,
    ),
}
