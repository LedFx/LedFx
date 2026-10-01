"""Tests for scene action field functionality."""

from unittest.mock import patch

import pytest

import ledfx.scenes as scenes_module
from ledfx.scenes import Scenes
from tests.test_utilities.fake_ledfx import fake_ledfx


@pytest.fixture(autouse=True)
def builtin_presets():
    """An empty built-in preset library per test; _DummyLedFx fills it."""
    with patch.dict("ledfx.scenes.ledfx_presets", clear=True):
        yield


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
        fake = fake_ledfx({"scenes": scenes or {}})
        self.config = fake.config
        self.config_store = fake.config_store
        scenes_module.ledfx_presets.update(presets or {})
        self.virtuals = virtuals or {}
        self.events = _DummyEvents()
        self.effects = _DummyEffects()


def _build_scenes_manager(scene_config, virtuals, presets=None):
    dummy_ledfx = _DummyLedFx(scenes=scene_config, virtuals=virtuals, presets=presets)
    return Scenes(dummy_ledfx), dummy_ledfx


# Test action: ignore
def test_action_ignore_leaves_virtual_unchanged():
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

    manager, ledfx = _build_scenes_manager(scenes, virtuals)  # noqa: RUF059
    result = manager.activate(scene_id)

    assert result is True
    assert virtuals["v1"].active_effect == initial_effect
    assert virtuals["v1"]._cleared is False


# Test action: stop
def test_action_stop_clears_effect():
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

    manager, ledfx = _build_scenes_manager(scenes, virtuals)  # noqa: RUF059
    result = manager.activate(scene_id)

    assert result is True
    assert virtuals["v1"]._cleared is True
    assert virtuals["v1"].active_effect is None


# Test action: forceblack
def test_action_forceblack_sets_black_single_color():
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
def test_action_activate_with_explicit_config():
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
def test_action_activate_with_preset():
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
def test_action_activate_with_missing_preset_falls_back_to_reset():
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
def test_legacy_empty_object_behaves_as_ignore():
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

    manager, ledfx = _build_scenes_manager(scenes, virtuals)  # noqa: RUF059
    result = manager.activate(scene_id)

    assert result is True
    assert virtuals["v1"].active_effect == initial_effect
    assert virtuals["v1"]._cleared is False


# Test legacy behavior: type and config present
def test_legacy_type_config_behaves_as_activate():
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
def test_mixed_actions_in_scene():
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

    manager, ledfx = _build_scenes_manager(scenes, virtuals)  # noqa: RUF059
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
def test_action_activate_without_type_or_config_skips():
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
def test_preset_resolution_from_user_presets():
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
    dummy_ledfx.config.user_presets = {
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
def test_scene_activation_skips_missing_virtuals():
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

    manager, ledfx = _build_scenes_manager(scenes, virtuals)  # noqa: RUF059
    result = manager.activate(scene_id)

    assert result is True
    # v1 should have bars effect
    assert virtuals["v1"].active_effect.type == "bars"
    # v2 should have black single color
    assert virtuals["v2"].active_effect.type == "singleColor"
    # No errors should occur from missing virtual


# Test invalid action value
def test_unknown_action_value_treated_as_legacy():
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
def test_scene_with_no_virtuals_activates_successfully():
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
def test_action_activate_with_reset_preset():
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


# Test preset fallback behavior when preset doesn't exist
def test_action_activate_preset_fallback_to_default():
    """Test that missing preset falls back to generate_default_config."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "scroll",
                    "preset": "nonexistent-preset",
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
    # Should fall back to default config
    assert effect.config == {
        "speed": 1.0,
        "brightness": 1.0,
        "color": "#ffffff",
    }


# Test user_presets are consulted
def test_action_activate_with_user_preset():
    """Test that user_presets are checked in addition to ledfx_presets."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "gradient",
                    "preset": "my-user-preset",
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
    dummy_ledfx.config.user_presets = {
        "gradient": {
            "my-user-preset": {
                "name": "My User Preset",
                "config": {"colors": ["#ff0000", "#00ff00", "#0000ff"]},
            }
        }
    }
    manager = Scenes(dummy_ledfx)
    result = manager.activate(scene_id)

    assert result is True
    assert len(dummy_ledfx.effects._created_effects) == 1
    effect = dummy_ledfx.effects._created_effects[0]
    assert effect.type == "gradient"
    assert effect.config == {"colors": ["#ff0000", "#00ff00", "#0000ff"]}


# Test ledfx_presets are consulted before user_presets
def test_action_activate_ledfx_presets_priority():
    """Test that ledfx_presets are checked before user_presets."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "scroll",
                    "preset": "rainbow-scroll",
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
        presets={
            "scroll": {
                "rainbow-scroll": {
                    "name": "Rainbow Scroll (System)",
                    "config": {"speed": 2.0, "gradient": "rainbow"},
                }
            }
        },
    )
    # Also add a user preset with same name
    dummy_ledfx.config.user_presets = {
        "scroll": {
            "rainbow-scroll": {
                "name": "Rainbow Scroll (User)",
                "config": {"speed": 5.0, "gradient": "custom"},
            }
        }
    }
    manager = Scenes(dummy_ledfx)
    result = manager.activate(scene_id)

    assert result is True
    assert len(dummy_ledfx.effects._created_effects) == 1
    effect = dummy_ledfx.effects._created_effects[0]
    assert effect.type == "scroll"
    # Should use ledfx_presets, not user_presets
    assert effect.config == {"speed": 2.0, "gradient": "rainbow"}


# Test unknown action values are treated as ignore/skipped
def test_unknown_action_value_is_ignored():
    """Test that unknown action values are skipped (no effect created)."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "unknown_action_type",
                    "type": "bars",
                    "config": {"speed": 1},
                },
                "v2": {
                    "action": "activate",
                    "type": "scroll",
                    "config": {"speed": 2},
                },
            },
        }
    }
    initial_effect_v1 = _DummyEffect("existing", {"speed": 10})
    virtuals = {
        "v1": _DummyVirtual("v1", initial_effect_v1),
        "v2": _DummyVirtual("v2"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    # v1 should be unchanged (unknown action treated as ignore)
    assert virtuals["v1"].active_effect == initial_effect_v1
    assert virtuals["v1"]._cleared is False
    # v2 should have new effect
    assert len(ledfx.effects._created_effects) == 1
    assert virtuals["v2"].active_effect.type == "scroll"


# Test missing type field with activate action
def test_action_activate_missing_type_field():
    """Test that activate action without type field is skipped."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "config": {"speed": 1},
                    # Missing required 'type' field
                },
                "v2": {
                    "action": "activate",
                    "type": "scroll",
                    "config": {"speed": 2},
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
        "v2": _DummyVirtual("v2"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    # v1 should not have an effect created (missing type)
    assert virtuals["v1"].active_effect is None
    # v2 should have effect
    assert len(ledfx.effects._created_effects) == 1
    assert virtuals["v2"].active_effect.type == "scroll"


# Test missing config with activate action (no preset)
def test_action_activate_missing_config_and_preset():
    """Test that activate action without config or preset is skipped."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "scroll",
                    # Missing both 'config' and 'preset'
                },
                "v2": {
                    "action": "activate",
                    "type": "bars",
                    "config": {"speed": 1},
                },
            },
        }
    }
    virtuals = {
        "v1": _DummyVirtual("v1"),
        "v2": _DummyVirtual("v2"),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    # v1 should not have an effect created (missing config/preset)
    assert virtuals["v1"].active_effect is None
    # v2 should have effect
    assert len(ledfx.effects._created_effects) == 1
    assert virtuals["v2"].active_effect.type == "bars"


# Test multiple unknown actions in one scene
def test_multiple_unknown_actions_in_scene():
    """Test scene with multiple unknown action types."""
    scene_id = "test-scene"
    scenes = {
        scene_id: {
            "name": "Test Scene",
            "virtuals": {
                "v1": {"action": "pause"},  # Unknown
                "v2": {"action": "resume"},  # Unknown
                "v3": {
                    "action": "activate",
                    "type": "scroll",
                    "config": {"speed": 1},
                },  # Valid
                "v4": {"action": "mute"},  # Unknown
            },
        }
    }
    initial_v1 = _DummyEffect("existing1", {})
    initial_v2 = _DummyEffect("existing2", {})
    initial_v4 = _DummyEffect("existing4", {})
    virtuals = {
        "v1": _DummyVirtual("v1", initial_v1),
        "v2": _DummyVirtual("v2", initial_v2),
        "v3": _DummyVirtual("v3"),
        "v4": _DummyVirtual("v4", initial_v4),
    }

    manager, ledfx = _build_scenes_manager(scenes, virtuals)
    result = manager.activate(scene_id)

    assert result is True
    # Unknown actions should leave virtuals unchanged
    assert virtuals["v1"].active_effect == initial_v1
    assert virtuals["v2"].active_effect == initial_v2
    assert virtuals["v4"].active_effect == initial_v4
    # Only v3 should have new effect
    assert len(ledfx.effects._created_effects) == 1
    assert virtuals["v3"].active_effect.type == "scroll"
