from tests.test_utilities.test_utils import APITestCase, SystemInfo

virtual_config_tests = {
    "cleanup_ci-test-device": APITestCase(
        execution_order=1,
        method="DELETE",
        api_endpoint="/api/virtuals/ci-test-jig",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "create_dummy_device": APITestCase(
        execution_order=2,
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "dummy",
            "config": {
                "icon_name": "mdi:led-strip",
                "center_offset": 0,
                "refresh_rate": SystemInfo.default_fps(),
                "pixel_count": 32,
                "name": "test dummy",
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
                        "pixel_count": 32,
                        "name": "test dummy",
                    },
                    "id": "test-dummy",
                    "virtuals": [],
                }
            },
        ],
    ),
    "create_dummy_device_2": APITestCase(
        execution_order=3,
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
    "modify_dummy_device": APITestCase(
        execution_order=4,
        method="PUT",
        api_endpoint="/api/devices/test-dummy",
        expected_return_code=200,
        payload_to_send={
            "type": "dummy",
            "config": {
                "icon_name": "mdi:led-strip",
                "center_offset": 0,
                "refresh_rate": SystemInfo.default_fps(),
                "pixel_count": 64,
                "name": "test dummy",
            },
        },
        expected_response_keys=["status"],
        expected_response_values=[{"status": "success"}],
    ),
    "check_devices": APITestCase(
        execution_order=5,
        method="GET",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={},
        expected_response_keys=["status", "devices"],
        expected_response_values=[
            {"status": "success"},
            {
                "devices": {
                    "test-dummy": {
                        "config": {
                            "icon_name": "mdi:led-strip",
                            "center_offset": 0,
                            "refresh_rate": SystemInfo.default_fps(),
                            "pixel_count": 64,
                            "name": "test dummy",
                        },
                        "id": "test-dummy",
                        "type": "dummy",
                        "online": True,
                        "virtuals": [],
                        "active_virtuals": [],
                    },
                    "test-dummy-2": {
                        "config": {
                            "icon_name": "mdi:led-strip",
                            "center_offset": 0,
                            "refresh_rate": SystemInfo.default_fps(),
                            "pixel_count": 128,
                            "name": "test dummy 2",
                        },
                        "id": "test-dummy-2",
                        "type": "dummy",
                        "online": True,
                        "virtuals": [],
                        "active_virtuals": [],
                    },
                }
            },
        ],
    ),
    "create_first_virtual": APITestCase(
        execution_order=6,
        method="POST",
        api_endpoint="/api/virtuals",
        expected_return_code=200,
        payload_to_send={
            "config": {
                "mapping": "span",
                "grouping": 1,
                "icon_name": "mdi:led-strip-variant",
                "max_brightness": 1,
                "center_offset": 0,
                "preview_only": False,
                "transition_time": 0.4,
                "transition_mode": "Add",
                "frequency_min": 20,
                "frequency_max": 15000,
                "rows": 1,
                "name": "first virt",
            }
        },
        expected_response_keys=["status", "payload", "virtual"],
        expected_response_values=[
            {"status": "success"},
            {
                "virtual": {
                    "config": {
                        "mapping": "span",
                        "grouping": 1,
                        "icon_name": "mdi:led-strip-variant",
                        "max_brightness": 1.0,
                        "center_offset": 0,
                        "preview_only": False,
                        "transition_time": 0.4,
                        "transition_mode": "Add",
                        "frequency_min": 20,
                        "frequency_max": 15000,
                        "rows": 1,
                        "name": "first virt",
                    },
                    "id": "first-virt",
                    "is_device": False,
                    "auto_generated": False,
                }
            },
        ],
    ),
    "modify_first_virtual": APITestCase(
        execution_order=7,
        method="POST",
        api_endpoint="/api/virtuals",
        expected_return_code=200,
        payload_to_send={
            "id": "first-virt",
            "config": {
                "mapping": "span",
                "grouping": 1,
                "icon_name": "mdi:led-strip-variant",
                "max_brightness": 1,
                "center_offset": 0,
                "preview_only": False,
                "transition_time": 0.4,
                "transition_mode": "Add",
                "frequency_min": 20,
                "frequency_max": 15000,
                "rows": 8,
                "name": "first virt",
            },
        },
        expected_response_keys=["status", "payload", "virtual"],
        expected_response_values=[
            {"status": "success"},
            {
                "virtual": {
                    "config": {
                        "mapping": "span",
                        "grouping": 1,
                        "icon_name": "mdi:led-strip-variant",
                        "max_brightness": 1.0,
                        "center_offset": 0,
                        "preview_only": False,
                        "transition_time": 0.4,
                        "transition_mode": "Add",
                        "frequency_min": 20,
                        "frequency_max": 15000,
                        "rows": 8,
                        "name": "first virt",
                    },
                    "id": "first-virt",
                    "is_device": False,
                    "auto_generated": False,
                }
            },
        ],
    ),
    "add_first_segment": APITestCase(
        execution_order=8,
        method="POST",
        api_endpoint="/api/virtuals/first-virt",
        expected_return_code=200,
        payload_to_send={"segments": [["test-dummy", 0, 60, False]]},
        expected_response_keys=["status"],
        expected_response_values=[
            {"status": "success", "segments": [["test-dummy", 0, 60, False]]}
        ],
    ),
    "add_second_segment": APITestCase(
        execution_order=9,
        method="POST",
        api_endpoint="/api/virtuals/first-virt",
        expected_return_code=200,
        payload_to_send={
            "segments": [
                ["test-dummy", 0, 63, False],
                ["test-dummy-2", 70, 127, False],
            ]
        },
        expected_response_keys=["status"],
        expected_response_values=[
            {
                "status": "success",
                "segments": [
                    ["test-dummy", 0, 63, False],
                    ["test-dummy-2", 70, 127, False],
                ],
            }
        ],
    ),
    "delete_dummy_device": APITestCase(
        execution_order=10,
        method="DELETE",
        api_endpoint="/api/virtuals/test-dummy",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
    ),
    "check_segments_after_device_delete": APITestCase(
        execution_order=11,
        method="GET",
        api_endpoint="/api/virtuals",
        expected_return_code=200,
        expected_response_keys=["status", "virtuals"],
        expected_response_values=[
            {"status": "success"},
            {
                "virtuals": {
                    "test-dummy-2": {
                        "config": {
                            "name": "test dummy 2",
                            "icon_name": "mdi:led-strip",
                            "rows": 1,
                            "frequency_max": 15000,
                            "center_offset": 0,
                            "transition_time": 0.4,
                            "frequency_min": 20,
                            "transition_mode": "Add",
                            "max_brightness": 1.0,
                            "preview_only": False,
                            "mapping": "span",
                            "grouping": 1,
                        },
                        "id": "test-dummy-2",
                        "is_device": "test-dummy-2",
                        "auto_generated": False,
                        "segments": [["test-dummy-2", 0, 127, False]],
                        "pixel_count": 128,
                        "active": False,
                        "streaming": False,
                        "last_effect": None,
                        "effect": {},
                    },
                    "first-virt": {
                        "config": {
                            "mapping": "span",
                            "grouping": 1,
                            "icon_name": "mdi:led-strip-variant",
                            "max_brightness": 1.0,
                            "center_offset": 0,
                            "preview_only": False,
                            "transition_time": 0.4,
                            "transition_mode": "Add",
                            "frequency_min": 20,
                            "frequency_max": 15000,
                            "rows": 8,
                            "name": "first virt",
                        },
                        "id": "first-virt",
                        "is_device": False,
                        "auto_generated": False,
                        "segments": [["test-dummy-2", 70, 127, False]],
                        "pixel_count": 122,
                        "active": False,
                        "streaming": False,
                        "last_effect": None,
                        "effect": {},
                    },
                }
            },
        ],
    ),
    "set_effect_to_virtual": APITestCase(
        execution_order=12,
        method="POST",
        api_endpoint="/api/virtuals/test-dummy-2/effects",
        expected_return_code=200,
        payload_to_send={"type": "rainbow"},
        expected_response_keys=["status", "effect"],
        expected_response_values=[
            {"status": "success"},
            {
                "effect": {
                    "config": {
                        "background_brightness": 1.0,
                        "background_color": "#000000",
                        "blur": 0.0,
                        "brightness": 1.0,
                        "flip": False,
                        "frequency": 1.0,
                        "mirror": False,
                        "speed": 1.0,
                    },
                    "name": "Rainbow",
                    "type": "rainbow",
                }
            },
        ],
    ),
    "modify_effect_to_virtual": APITestCase(
        execution_order=13,
        method="PUT",
        api_endpoint="/api/virtuals/test-dummy-2/effects",
        expected_return_code=200,
        payload_to_send={
            "type": "rainbow",
            "config": {"flip": True, "mirror": True, "speed": 3.0},
        },
        expected_response_keys=["status", "effect"],
        expected_response_values=[
            {"status": "success"},
            {
                "effect": {
                    "config": {
                        "background_brightness": 1.0,
                        "background_color": "#000000",
                        "blur": 0.0,
                        "brightness": 1.0,
                        "flip": True,
                        "frequency": 1.0,
                        "mirror": True,
                        "speed": 3.0,
                    },
                    "name": "Rainbow",
                    "type": "rainbow",
                }
            },
        ],
    ),
    "delete_effect_from_virtual": APITestCase(
        execution_order=14,
        method="DELETE",
        api_endpoint="/api/virtuals/test-dummy-2/effects",
        expected_return_code=200,
        payload_to_send={},
        expected_response_keys=["status", "effect"],
        expected_response_values=[{"status": "success"}, {"effect": {}}],
    ),
    # need to run this test before delete from effects, or will fail.
    "set_effect_to_last_active": APITestCase(
        execution_order=15,
        method="PUT",
        api_endpoint="/api/virtuals/test-dummy-2",
        expected_return_code=200,
        payload_to_send={"active": True},
        expected_response_keys=["status", "active"],
        expected_response_values=[
            {"status": "success"},
            {"active": True}
        ],
    ),
    "check_effect_is_last_effect": APITestCase(
        execution_order=16,
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
                    },
                    "name": "Rainbow",
                    "type": "rainbow",
                }
            }
        ],
    ),

#/api/effects
                    # "effect": {
                #     "config": {
                #         "background_brightness": 1.0,
                #         "background_color": "#000000",
                #         "blur": 0.0,
                #         "brightness": 1.0,
                #         "flip": True,
                #         "frequency": 1.0,
                #         "mirror": True,
                #         "speed": 3.0,
                #     },
                #     "name": "Rainbow",
                #     "type": "rainbow",
                # }

    "delete_effect_from_effects_from_virtual": APITestCase(
        execution_order=17,
        method="POST",
        api_endpoint="/api/virtuals/test-dummy-2/effects/delete",
        expected_return_code=200,
        payload_to_send={"type": "rainbow"},
        expected_response_keys=["status"],
        expected_response_values=[
            {"status": "success"},
        ],
    ),
    "set_preset_effect_to_virtual": APITestCase(
        execution_order=18,
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
                    },
                    "name": "Rainbow",
                    "type": "rainbow",
                }
            },
        ],
    ),
    "set_user_preset_to_current": APITestCase(
        execution_order=19,
        method="POST",
        api_endpoint="/api/virtuals/test-dummy-2/presets",
        expected_return_code=200,
        payload_to_send={"name": "cheap-trick"},
        expected_response_keys=["status", "preset"],
        expected_response_values=[
            {"status": "success"},
            {
                "status": "success",
                "preset": {
                    "id": "cheap-trick",
                    "name": "cheap-trick",
                    "config": {
                        "background_brightness": 1.0,
                        "background_color": "#000000",
                        "blur": 7.7,
                        "brightness": 1.0,
                        "flip": False,
                        "frequency": 0.32,
                        "mirror": True,
                        "speed": 0.3,
                    },
                },
            },
        ],
    ),
    "set_user_preset_effect_to_virtual": APITestCase(
        execution_order=20,
        method="PUT",
        api_endpoint="/api/virtuals/test-dummy-2/presets",
        expected_return_code=200,
        payload_to_send={
            "category": "user_presets",
            "effect_id": "rainbow",
            "preset_id": "cheap-trick",
        },
        expected_response_keys=["status", "effect"],
        expected_response_values=[
            {"status": "success"},
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
                    },
                    "name": "Rainbow",
                    "type": "rainbow",
                }
            },
        ],
    ),
    "set_effect_to_virtual_with_fallback": APITestCase(
        execution_order=21,
        method="POST",
        api_endpoint="/api/virtuals/test-dummy-2/effects",
        expected_return_code=200,
        payload_to_send={"type": "bar", "fallback": 2.0},
        expected_response_keys=["status", "effect"],
        expected_response_values=[
            {"status": "success"},
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
                    },
                    "name": "Bar",
                    "type": "bar",
                }
            },
        ],
        sleep_after_test=1.0,
    ),
    "get_effect_from_virtual_before_fallback": APITestCase(
        execution_order=22,
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
                    },
                    "name": "Bar",
                    "type": "bar",
                }
            }
        ],
        sleep_after_test=1.0,
    ),
    "get_effect_from_virtual_after_fallack": APITestCase(
        execution_order=23,
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
                    },
                    "name": "Rainbow",
                    "type": "rainbow",
                }
            }
        ],
    ),
    "create_dummy_device_again": APITestCase(
        execution_order=24,
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "dummy",
            "config": {
                "icon_name": "mdi:led-strip",
                "center_offset": 0,
                "refresh_rate": SystemInfo.default_fps(),
                "pixel_count": 32,
                "name": "test dummy",
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
                        "pixel_count": 32,
                        "name": "test dummy",
                    },
                    "id": "test-dummy",
                    "virtuals": [],
                }
            },
        ],
    ),
    "create_dummy_device_3": APITestCase(
        execution_order=25,
        method="POST",
        api_endpoint="/api/devices",
        expected_return_code=200,
        payload_to_send={
            "type": "dummy",
            "config": {
                "icon_name": "mdi:led-strip",
                "center_offset": 0,
                "refresh_rate": SystemInfo.default_fps(),
                "pixel_count": 32,
                "name": "test dummy 3",
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
                        "pixel_count": 32,
                        "name": "test dummy 3",
                    },
                    "id": "test-dummy-3",
                    "virtuals": [],
                }
            },
        ],
    ),
    "set_effect_to_virtual_again": APITestCase(
        execution_order=26,
        method="POST",
        api_endpoint="/api/virtuals/test-dummy-2/effects",
        expected_return_code=200,
        payload_to_send={"type": "rainbow"},
        expected_response_keys=["status", "effect"],
        expected_response_values=[
            {"status": "success"},
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
                    },
                    "name": "Rainbow",
                    "type": "rainbow",
                }
            },
        ],
    ),
    "copy_effects_to_virtuals": APITestCase(
        execution_order=27,
        method="PUT",
        api_endpoint="/api/virtuals_tools/test-dummy-2",
        expected_return_code=200,
        payload_to_send={
            "tool": "copy",
            "target": ["test-dummy", "test-dummy-3"],
        },
        expected_response_keys=["status", "tool"],
        expected_response_values=[
            {"status": "success"},
            {"tool": "copy"},
        ],
    ),
    "get_effect_for_dummy_1": APITestCase(
        execution_order=28,
        method="GET",
        api_endpoint="/api/virtuals/test-dummy/effects",
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
                    },
                    "name": "Rainbow",
                    "type": "rainbow",
                }
            }
        ],
    ),
    "get_effect_for_dummy_2": APITestCase(
        execution_order=29,
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
                    },
                    "name": "Rainbow",
                    "type": "rainbow",
                }
            }
        ],
    ),
    "get_effect_for_dummy_3": APITestCase(
        execution_order=30,
        method="GET",
        api_endpoint="/api/virtuals/test-dummy-3/effects",
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
                    },
                    "name": "Rainbow",
                    "type": "rainbow",
                }
            }
        ],
    ),
    "cleanup_dummy_device": APITestCase(
        execution_order=31,
        method="DELETE",
        api_endpoint="/api/virtuals/test-dummy",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
        sleep_after_test=1.0,
    ),
    "cleanup_dummy_device_2": APITestCase(
        execution_order=32,
        method="DELETE",
        api_endpoint="/api/virtuals/test-dummy-2",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
        sleep_after_test=1.0,
    ),
    "cleanup_dummy_device_3": APITestCase(
        execution_order=33,
        method="DELETE",
        api_endpoint="/api/virtuals/test-dummy-3",
        expected_return_code=200,
        expected_response_keys=[],
        expected_response_values=[],
        payload_to_send={},
        sleep_after_test=1.0,
    ),
}
