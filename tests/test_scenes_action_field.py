"""Tests for scene action field functionality."""

from unittest.mock import patch

from ledfx.scenes import Scenes


class _DummyEvents:
    def fire_event(self, *_, **__):
        pass


class _DummyVirtual:
    def __init__(self, virtual_id, effect=None):
        self.id = virtual_id
        self.active_effect = effect
        self._cleared = False
        self._set_effect_calls = []

    def clear_effect(self):
        self._cleared = True
        self.active_effect = None

    def set_effect(self, effect):
        self._set_effect_calls.append(effect)
        self.active_effect = effect

    def update_effect_config(self, effect):
        pass


class _DummyEffect:
    def __init__(self, effect_type, config):
        self.type = effect_type
        self.config = config


class _DummyEffects:
    def __init__(self):
        self._created_effects = []

    def create(self, ledfx, type, config):
        effect = _DummyEffect(type, config)
        self._created_effects.append(effect)
        return effect

    def get_class(self, effect_id):
        """Mock get_class for generate_default_config support."""

        # Return a mock effect class with a get_combined_default_schema method
        class MockEffectClass:
            @staticmethod
            def get_combined_default_schema():
                # Return a simple default config
                return {"speed": 1.0, "brightness": 1.0, "color": "#ffffff"}

        return MockEffectClass


class _DummyLedFx:
    def __init__(self, scenes=None, virtuals=None, presets=None):
        self.config_dir = ""
        self.config = {
            "scenes": scenes or {},
            "ledfx_presets": presets or {},
            "user_presets": {},
        }
        self.virtuals = virtuals or {}
        self.events = _DummyEvents()
        self.effects = _DummyEffects()


def _build_scenes_manager(scene_config, virtuals, presets=None):
    dummy_ledfx = _DummyLedFx(
        scenes=scene_config, virtuals=virtuals, presets=presets
    )
    return Scenes(dummy_ledfx), dummy_ledfx


# Test action: ignore
@patch("ledfx.scenes.save_config")
def test_action_ignore_leaves_virtual_unchanged(mock_save):
    """Test that action 'ignore' leaves the virtual unchanged."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {"action": "ignore"},
            },
        }
    }
    initial_effect = _DummyEffect("bars", {"speed": 5})
    virtuals = {
        "v1": _DummyVirtual("v1", initial_effect),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    assert virtuals["v1"].active_effect == initial_effect
    assert virtuals["v1"]._cleared is False


# Test action: stop
@patch("ledfx.scenes.save_config")
def test_action_stop_clears_effect(mock_save):
    """Test that action 'stop' clears the virtual's effect."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {"action": "stop"},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("bars", {"speed": 5})),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    assert virtuals["v1"]._cleared is True
    assert virtuals["v1"].active_effect is None


# Test action: forceblack
@patch("ledfx.scenes.save_config")
def test_action_forceblack_sets_black_single_color(mock_save):
    """Test that action 'forceblack' sets Single Color effect with black."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {"action": "forceblack"},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    assert len(ledfx.effects._created_effects) == 1
    effect = ledfx.effects._created_effects[0]
    assert effect.type == "singleColor"
    assert effect.config == {"color": "#000000"}
    assert virtuals["v1"].active_effect == effect


# Test action: activate with explicit config
@patch("ledfx.scenes.save_config")
def test_action_activate_with_explicit_config(mock_save):
    """Test that action 'activate' applies the specified effect."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "bars",
                    "config": {"speed": 3, "color": "red"},
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    assert len(ledfx.effects._created_effects) == 1
    effect = ledfx.effects._created_effects[0]
    assert effect.type == "bars"
    assert effect.config == {"speed": 3, "color": "red"}
    assert virtuals["v1"].active_effect == effect


# Test action: activate with preset
@patch("ledfx.scenes.save_config")
def test_action_activate_with_preset(mock_save):
    """Test that action 'activate' resolves and applies a preset."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "scroll",
                    "preset": "rainbow-preset",
                },
            },
        }
    }
    presets = {
        "scroll": {
            "rainbow-preset": {
                "name": "Rainbow Preset",
                "config": {"speed": 2, "gradient": "rainbow"},
            }
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals, presets)
    result = manager.activate(scene_id)

    assert result is True
    assert len(ledfx.effects._created_effects) == 1
    effect = ledfx.effects._created_effects[0]
    assert effect.type == "scroll"
    assert effect.config == {"speed": 2, "gradient": "rainbow"}


# Test action: activate with missing preset
@patch("ledfx.scenes.save_config")
def test_action_activate_with_missing_preset_falls_back_to_reset(mock_save):
    """Test that action 'activate' with missing preset falls back to reset preset."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "scroll",
                    "preset": "missing-preset",
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    assert len(ledfx.effects._created_effects) == 1
    effect = ledfx.effects._created_effects[0]
    assert effect.type == "scroll"
    # Should fall back to reset/default config
    assert effect.config == {
        "speed": 1.0,
        "brightness": 1.0,
        "color": "#ffffff",
    }


# Test legacy behavior: empty object
@patch("ledfx.scenes.save_config")
def test_legacy_empty_object_behaves_as_ignore(mock_save):
    """Test that empty object {} behaves as 'ignore' action."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {},
            },
        }
    }
    initial_effect = _DummyEffect("bars", {"speed": 5})
    virtuals = {
        "v1": _DummyVirtual("v1", initial_effect),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    assert virtuals["v1"].active_effect == initial_effect
    assert virtuals["v1"]._cleared is False


# Test legacy behavior: type and config present
@patch("ledfx.scenes.save_config")
def test_legacy_type_config_behaves_as_activate(mock_save):
    """Test that type/config without action behaves as 'activate'."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "type": "energy",
                    "config": {"intensity": 10},
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    assert len(ledfx.effects._created_effects) == 1
    effect = ledfx.effects._created_effects[0]
    assert effect.type == "energy"
    assert effect.config == {"intensity": 10}


# Test mixed actions in one scene
@patch("ledfx.scenes.save_config")
def test_mixed_actions_in_scene(mock_save):
    """Test a scene with multiple virtuals using different actions."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {"action": "ignore"},
                "v2": {"action": "stop"},
                "v3": {"action": "forceblack"},
                "v4": {
                    "action": "activate",
                    "type": "bars",
                    "config": {"speed": 1},
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1", _DummyEffect("existing", {})),
        "v2": _DummyVirtual("v2", _DummyEffect("existing", {})),
        "v3": _DummyVirtual("v3"),
        "v4": _DummyVirtual("v4"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    # v1 should be unchanged
    assert virtuals["v1"].active_effect.type == "existing"
    # v2 should be cleared
    assert virtuals["v2"]._cleared is True
    # v3 should have black single color
    assert virtuals["v3"].active_effect.type == "singleColor"
    assert virtuals["v3"].active_effect.config["color"] == "#000000"
    # v4 should have bars effect
    assert virtuals["v4"].active_effect.type == "bars"
    assert virtuals["v4"].active_effect.config["speed"] == 1


# Test activate with invalid action config
@patch("ledfx.scenes.save_config")
def test_action_activate_without_type_or_config_skips(mock_save):
    """Test that activate without type/config/preset skips the virtual."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    # Missing type, config, and preset
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    assert len(ledfx.effects._created_effects) == 0
    assert virtuals["v1"].active_effect is None


# Test preset resolution from user_presets
@patch("ledfx.scenes.save_config")
def test_preset_resolution_from_user_presets(mock_save):
    """Test that presets are resolved from user_presets as well."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "gradient",
                    "preset": "my-custom-preset",
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
    }

    dummy_ledfx = _DummyLedFx(
        scenes=scenes,
        virtuals=virtuals,
        presets={},
    )
    # Add user preset
    dummy_ledfx.config["user_presets"] = {
        "gradient": {
            "my-custom-preset": {
                "name": "My Custom Preset",
                "config": {"colors": ["red", "blue"]},
            }
        }
    }
    manager = Scenes(dummy_ledfx)
    result = manager.activate(scene_id)

    assert result is True
    assert len(dummy_ledfx.effects._created_effects) == 1
    effect = dummy_ledfx.effects._created_effects[0]
    assert effect.type == "gradient"
    assert effect.config == {"colors": ["red", "blue"]}


# Test virtual missing from system
@patch("ledfx.scenes.save_config")
def test_scene_activation_skips_missing_virtuals(mock_save):
    """Test that scene activation continues when a virtual is missing."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "bars",
                    "config": {"speed": 1},
                },
                "missing-virtual": {"action": "stop"},
                "v2": {"action": "forceblack"},
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
        "v2": _DummyVirtual("v2"),
        # "missing-virtual" not in the system
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    # v1 should have bars effect
    assert virtuals["v1"].active_effect.type == "bars"
    # v2 should have black single color
    assert virtuals["v2"].active_effect.type == "singleColor"
    # No errors should occur from missing virtual


# Test invalid action value
@patch("ledfx.scenes.save_config")
def test_unknown_action_value_treated_as_legacy(mock_save):
    """Test that unknown action values are ignored/skipped and no effect is created."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "unknown_action",  # Invalid action
                    "type": "bars",
                    "config": {"speed": 1},
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    # Should still succeed; unknown action is skipped, no effect should be created
    assert result is True
    assert len(ledfx.effects._created_effects) == 0


# Test scene with no virtuals
@patch("ledfx.scenes.save_config")
def test_scene_with_no_virtuals_activates_successfully(mock_save):
    """Test that a scene with no virtuals can be activated."""
    scene_id = "empty-scene"
    scenes = {
        scene_id: {
            "name": "Empty Scene",
            "virtuals": {},
        }
    }
    virtuals = {}

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    assert len(ledfx.effects._created_effects) == 0


# Test reset preset
@patch("ledfx.scenes.save_config")
def test_action_activate_with_reset_preset(mock_save):
    """Test that the special 'reset' preset generates default config."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "scroll",
                    "preset": "reset",
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    assert len(ledfx.effects._created_effects) == 1
    effect = ledfx.effects._created_effects[0]
    assert effect.type == "scroll"
    # Should have the default config from get_combined_default_schema
    assert effect.config == {
        "speed": 1.0,
        "brightness": 1.0,
        "color": "#ffffff",
    }
