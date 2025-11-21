from ledfx.scenes import Scenes


class _DummyEvents:
    def fire_event(self, *_, **__):
        pass


class _DummyVirtual:
    def __init__(self, virtual_id, effect=None):
        self.id = virtual_id
        self.active_effect = effect


class _DummyEffect:
    def __init__(self, effect_type, config):
        self.type = effect_type
        self.config = config


class _DummyLedFx:
    def __init__(
        self, scenes=None, virtuals=None, presets=None, user_presets=None
    ):
        self.config_dir = ""
        self.config = {
            "scenes": scenes or {},
            "ledfx_presets": presets or {},
            "user_presets": user_presets or {},
        }
        self.virtuals = virtuals or {}
        self.events = _DummyEvents()


def _build_scenes_manager(
    scene_config, virtuals, presets=None, user_presets=None
):
    dummy_ledfx = _DummyLedFx(
        scenes=scene_config,
        virtuals=virtuals,
        presets=presets,
        user_presets=user_presets,
    )
    return Scenes(dummy_ledfx)


def test_scene_is_active_when_effects_match():
    scene_id = "scene-one"
    scenes = {
        scene_id: {
            "name": "Scene One",
            "virtuals": {
                "v1": {"type": "bars", "config": {"speed": 2}},
                "v2": {},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 2})),
        "v2": _DummyVirtual("v2", None),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is True


def test_scene_is_not_active_on_effect_mismatch():
    scene_id = "scene-two"
    scenes = {
        scene_id: {
            "name": "Scene Two",
            "virtuals": {
                "v1": {"type": "bars", "config": {"speed": 2}},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 3})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is False


def test_scene_is_not_active_when_virtual_missing():
    scene_id = "scene-three"
    scenes = {
        scene_id: {
            "name": "Scene Three",
            "virtuals": {
                "ghost": {"type": "sparkle", "config": {"color": "red"}},
            },
        }
    }

    manager = _build_scenes_manager(scenes, virtuals={})

    assert manager.is_active(scene_id) is False


# Tests for action field support in is_active


def test_is_active_with_action_ignore():
    """Test that action=ignore always matches (virtual is skipped)."""
    scene_id = "ignore-scene"
    scenes = {
        scene_id: {
            "name": "Ignore Scene",
            "virtuals": {
                "v1": {"action": "ignore"},
            },
        }
    }
    # Virtual has any effect - should still be active because ignore skips comparison
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 5})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is True


def test_is_active_with_action_stop_matching():
    """Test that action=stop matches when virtual has no effect."""
    scene_id = "stop-scene"
    scenes = {
        scene_id: {
            "name": "Stop Scene",
            "virtuals": {
                "v1": {"action": "stop"},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", None),  # No effect
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is True


def test_is_active_with_action_stop_not_matching():
    """Test that action=stop does not match when virtual has an effect."""
    scene_id = "stop-scene"
    scenes = {
        scene_id: {
            "name": "Stop Scene",
            "virtuals": {
                "v1": {"action": "stop"},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 1})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is False


def test_is_active_with_action_forceblack_matching():
    """Test that action=forceblack matches when virtual has singleColor #000000."""
    scene_id = "black-scene"
    scenes = {
        scene_id: {
            "name": "Black Scene",
            "virtuals": {
                "v1": {"action": "forceblack"},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual(
            "v1", _DummyEffect("singleColor", {"color": "#000000"})
        ),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is True


def test_is_active_with_action_forceblack_wrong_color():
    """Test that action=forceblack does not match with different color."""
    scene_id = "black-scene"
    scenes = {
        scene_id: {
            "name": "Black Scene",
            "virtuals": {
                "v1": {"action": "forceblack"},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual(
            "v1", _DummyEffect("singleColor", {"color": "#ff0000"})
        ),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is False


def test_is_active_with_action_forceblack_wrong_effect_type():
    """Test that action=forceblack does not match with different effect type."""
    scene_id = "black-scene"
    scenes = {
        scene_id: {
            "name": "Black Scene",
            "virtuals": {
                "v1": {"action": "forceblack"},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 1})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is False


def test_is_active_with_action_activate_matching():
    """Test that action=activate matches when effect and config match."""
    scene_id = "activate-scene"
    scenes = {
        scene_id: {
            "name": "Activate Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "bars",
                    "config": {"speed": 2},
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 2})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is True


def test_is_active_with_action_activate_config_mismatch():
    """Test that action=activate does not match when config differs."""
    scene_id = "activate-scene"
    scenes = {
        scene_id: {
            "name": "Activate Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "bars",
                    "config": {"speed": 2},
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 3})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is False


def test_is_active_with_action_activate_type_mismatch():
    """Test that action=activate does not match when effect type differs."""
    scene_id = "activate-scene"
    scenes = {
        scene_id: {
            "name": "Activate Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "bars",
                    "config": {"speed": 2},
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("scroll", {"speed": 2})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is False


def test_is_active_with_action_activate_preset_matching():
    """Test that action=activate with preset matches when resolved config matches."""
    scene_id = "preset-scene"
    scenes = {
        scene_id: {
            "name": "Preset Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "scroll",
                    "preset": "rainbow-scroll",
                },
            },
        }
    }
    presets = {
        "scroll": {
            "rainbow-scroll": {
                "name": "Rainbow Scroll",
                "config": {"speed": 2, "gradient": "rainbow"},
            }
        }
    }
    virtuals = {
        "v1": _DummyVirtual(
            "v1", _DummyEffect("scroll", {"speed": 2, "gradient": "rainbow"})
        ),
    }

    manager = _build_scenes_manager(scenes, virtuals, presets=presets)

    assert manager.is_active(scene_id) is True


def test_is_active_with_action_activate_preset_not_matching():
    """Test that action=activate with preset does not match when config differs."""
    scene_id = "preset-scene"
    scenes = {
        scene_id: {
            "name": "Preset Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "scroll",
                    "preset": "rainbow-scroll",
                },
            },
        }
    }
    presets = {
        "scroll": {
            "rainbow-scroll": {
                "name": "Rainbow Scroll",
                "config": {"speed": 2, "gradient": "rainbow"},
            }
        }
    }
    virtuals = {
        # Different speed
        "v1": _DummyVirtual(
            "v1", _DummyEffect("scroll", {"speed": 3, "gradient": "rainbow"})
        ),
    }

    manager = _build_scenes_manager(scenes, virtuals, presets=presets)

    assert manager.is_active(scene_id) is False


def test_is_active_with_mixed_actions():
    """Test is_active with a scene containing multiple action types."""
    scene_id = "mixed-scene"
    scenes = {
        scene_id: {
            "name": "Mixed Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "bars",
                    "config": {"speed": 1},
                },
                "v2": {"action": "stop"},
                "v3": {"action": "ignore"},
                "v4": {"action": "forceblack"},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 1})),
        "v2": _DummyVirtual("v2", None),  # Stopped
        "v3": _DummyVirtual(
            "v3", _DummyEffect("scroll", {"speed": 99})
        ),  # Ignored, can be anything
        "v4": _DummyVirtual(
            "v4", _DummyEffect("singleColor", {"color": "#000000"})
        ),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is True


def test_is_active_with_mixed_actions_one_mismatch():
    """Test is_active returns False when one virtual in mixed scene doesn't match."""
    scene_id = "mixed-scene"
    scenes = {
        scene_id: {
            "name": "Mixed Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "bars",
                    "config": {"speed": 1},
                },
                "v2": {"action": "stop"},
                "v3": {"action": "ignore"},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 1})),
        "v2": _DummyVirtual(
            "v2", _DummyEffect("scroll", {"speed": 1})
        ),  # Should be stopped!
        "v3": _DummyVirtual("v3", _DummyEffect("anything", {"x": 1})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is False


def test_is_active_legacy_empty_object_with_no_effect():
    """Test legacy format: empty object matches when no effect."""
    scene_id = "legacy-scene"
    scenes = {
        scene_id: {
            "name": "Legacy Scene",
            "virtuals": {
                "v1": {},  # Legacy: empty object means ignore
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", None),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    # Empty object is treated as ignore, so it always matches
    assert manager.is_active(scene_id) is True


def test_is_active_legacy_empty_object_with_effect():
    """Test legacy format: empty object still matches even with effect (ignore behavior)."""
    scene_id = "legacy-scene"
    scenes = {
        scene_id: {
            "name": "Legacy Scene",
            "virtuals": {
                "v1": {},  # Legacy: empty object means ignore
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 1})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    # Empty object is treated as ignore, so it always matches
    assert manager.is_active(scene_id) is True


def test_is_active_legacy_type_config_matching():
    """Test legacy format: type/config without action field matches when effect matches."""
    scene_id = "legacy-scene"
    scenes = {
        scene_id: {
            "name": "Legacy Scene",
            "virtuals": {
                "v1": {
                    "type": "bars",
                    "config": {"speed": 2},
                },  # No action field
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 2})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is True


def test_is_active_legacy_type_config_not_matching():
    """Test legacy format: type/config without action field does not match when config differs."""
    scene_id = "legacy-scene"
    scenes = {
        scene_id: {
            "name": "Legacy Scene",
            "virtuals": {
                "v1": {
                    "type": "bars",
                    "config": {"speed": 2},
                },  # No action field
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 3})),
    }

    manager = _build_scenes_manager(scenes, virtuals)

    assert manager.is_active(scene_id) is False
