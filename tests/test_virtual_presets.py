import pytest

from ledfx.api.virtual_presets import VirtualPresetsEndpoint


class _DummyEffect:
    def __init__(self, effect_type, config):
        self.type = effect_type
        self.config = config


class _DummyVirtual:
    def __init__(self, virtual_id, effect=None):
        self.id = virtual_id
        self.active_effect = effect


class _DummyLedFx:
    def __init__(self, config=None, virtuals=None):
        self.config = config or {}
        self.virtuals = virtuals or {}


@pytest.fixture
def preset_endpoint():
    """Create a VirtualPresetsEndpoint instance for testing"""
    endpoint = VirtualPresetsEndpoint(None)
    endpoint._ledfx = _DummyLedFx()
    return endpoint


def test_add_active_flags_matching_preset(preset_endpoint):
    """Test that matching preset gets active=True"""
    presets = {
        "preset1": {
            "name": "Preset One",
            "config": {"speed": 2, "color": "red"},
        },
        "preset2": {
            "name": "Preset Two",
            "config": {"speed": 3, "color": "blue"},
        },
    }
    active_config = {"speed": 2, "color": "red"}

    result = preset_endpoint._add_active_flags(presets, active_config)

    assert result["preset1"]["active"] is True
    assert result["preset2"]["active"] is False
    # Verify original data is preserved
    assert result["preset1"]["name"] == "Preset One"
    assert result["preset1"]["config"] == {"speed": 2, "color": "red"}


def test_add_active_flags_no_matching_preset(preset_endpoint):
    """Test that no preset gets active=True when none match"""
    presets = {
        "preset1": {
            "name": "Preset One",
            "config": {"speed": 2, "color": "red"},
        },
        "preset2": {
            "name": "Preset Two",
            "config": {"speed": 3, "color": "blue"},
        },
    }
    active_config = {"speed": 5, "color": "green"}

    result = preset_endpoint._add_active_flags(presets, active_config)

    assert result["preset1"]["active"] is False
    assert result["preset2"]["active"] is False


def test_add_active_flags_empty_presets(preset_endpoint):
    """Test handling of empty presets dictionary"""
    presets = {}
    active_config = {"speed": 2}

    result = preset_endpoint._add_active_flags(presets, active_config)

    assert result == {}


def test_add_active_flags_exact_match_required(preset_endpoint):
    """Test that only exact config matches are marked active"""
    presets = {
        "preset1": {
            "name": "Preset One",
            "config": {"speed": 2, "color": "red"},
        },
        "preset2": {
            "name": "Preset Two",
            # Missing 'color' key - should not match
            "config": {"speed": 2},
        },
    }
    active_config = {"speed": 2, "color": "red"}

    result = preset_endpoint._add_active_flags(presets, active_config)

    assert result["preset1"]["active"] is True
    assert result["preset2"]["active"] is False


def test_add_active_flags_handles_empty_configs(preset_endpoint):
    """Test handling of empty configs"""
    presets = {
        "preset1": {
            "name": "Empty Preset",
            "config": {},
        },
    }
    active_config = {}

    result = preset_endpoint._add_active_flags(presets, active_config)

    assert result["preset1"]["active"] is True


def test_add_active_flags_preserves_all_preset_data(preset_endpoint):
    """Test that all preset data is preserved in the result"""
    presets = {
        "preset1": {
            "name": "Test Preset",
            "config": {"speed": 2},
            "custom_field": "custom_value",
            "another_field": 123,
        },
    }
    active_config = {"speed": 2}

    result = preset_endpoint._add_active_flags(presets, active_config)

    assert result["preset1"]["name"] == "Test Preset"
    assert result["preset1"]["config"] == {"speed": 2}
    assert result["preset1"]["custom_field"] == "custom_value"
    assert result["preset1"]["another_field"] == 123
    assert result["preset1"]["active"] is True


def test_add_active_flags_case_sensitivity(preset_endpoint):
    """Test that config comparison is case-sensitive"""
    presets = {
        "preset1": {
            "name": "Preset One",
            "config": {"Color": "Red"},  # Uppercase C
        },
    }
    active_config = {"color": "Red"}  # Lowercase c

    result = preset_endpoint._add_active_flags(presets, active_config)

    # Should not match due to case difference in key
    assert result["preset1"]["active"] is False


def test_add_active_flags_value_type_sensitivity(preset_endpoint):
    """Test that config comparison is type-sensitive"""
    presets = {
        "preset1": {
            "name": "Preset String",
            "config": {"speed": "2"},  # String
        },
        "preset2": {
            "name": "Preset Int",
            "config": {"speed": 2},  # Integer
        },
    }
    active_config = {"speed": 2}  # Integer

    result = preset_endpoint._add_active_flags(presets, active_config)

    assert result["preset1"]["active"] is False
    assert result["preset2"]["active"] is True


def test_add_active_flags_ignores_advanced_key(preset_endpoint):
    """Test that the 'advanced' key is ignored when comparing configs"""
    presets = {
        "preset1": {
            "name": "Preset One",
            "config": {"speed": 2, "color": "red", "advanced": False},
        },
        "preset2": {
            "name": "Preset Two",
            "config": {"speed": 2, "color": "red", "advanced": True},
        },
        "preset3": {
            "name": "Preset Three",
            "config": {"speed": 2, "color": "red"},  # No advanced key
        },
    }
    active_config = {"speed": 2, "color": "red", "advanced": True}

    result = preset_endpoint._add_active_flags(presets, active_config)

    # All presets should be active since 'advanced' is ignored
    assert result["preset1"]["active"] is True
    assert result["preset2"]["active"] is True
    assert result["preset3"]["active"] is True


def test_add_active_flags_advanced_only_in_preset(preset_endpoint):
    """Test when 'advanced' key exists only in preset config"""
    presets = {
        "preset1": {
            "name": "Preset One",
            "config": {"speed": 2, "color": "red", "advanced": False},
        },
    }
    active_config = {"speed": 2, "color": "red"}  # No advanced key

    result = preset_endpoint._add_active_flags(presets, active_config)

    # Should match since 'advanced' is ignored
    assert result["preset1"]["active"] is True


def test_add_active_flags_advanced_only_in_active(preset_endpoint):
    """Test when 'advanced' key exists only in active effect config"""
    presets = {
        "preset1": {
            "name": "Preset One",
            "config": {"speed": 2, "color": "red"},  # No advanced key
        },
    }
    active_config = {"speed": 2, "color": "red", "advanced": True}

    result = preset_endpoint._add_active_flags(presets, active_config)

    # Should match since 'advanced' is ignored
    assert result["preset1"]["active"] is True


def test_add_active_flags_advanced_ignored_but_other_mismatch(preset_endpoint):
    """Test that 'advanced' is ignored but other mismatches are detected"""
    presets = {
        "preset1": {
            "name": "Preset One",
            "config": {"speed": 2, "color": "red", "advanced": False},
        },
        "preset2": {
            "name": "Preset Two",
            "config": {"speed": 3, "color": "red", "advanced": True},
        },
    }
    active_config = {"speed": 2, "color": "red", "advanced": True}

    result = preset_endpoint._add_active_flags(presets, active_config)

    # preset1 should match (speed matches, advanced ignored)
    assert result["preset1"]["active"] is True
    # preset2 should not match (speed differs, even though advanced is ignored)
    assert result["preset2"]["active"] is False


def test_add_active_flags_ignores_diag_key(preset_endpoint):
    """Test that the 'diag' key is ignored when comparing configs"""
    presets = {
        "preset1": {
            "name": "Preset One",
            "config": {"speed": 2, "color": "red", "diag": False},
        },
        "preset2": {
            "name": "Preset Two",
            "config": {"speed": 2, "color": "red", "diag": True},
        },
        "preset3": {
            "name": "Preset Three",
            "config": {"speed": 2, "color": "red"},  # No diag key
        },
    }
    active_config = {"speed": 2, "color": "red", "diag": True}

    result = preset_endpoint._add_active_flags(presets, active_config)

    # All presets should be active since 'diag' is ignored
    assert result["preset1"]["active"] is True
    assert result["preset2"]["active"] is True
    assert result["preset3"]["active"] is True


def test_add_active_flags_ignores_both_advanced_and_diag(preset_endpoint):
    """Test that both 'advanced' and 'diag' keys are ignored simultaneously"""
    presets = {
        "preset1": {
            "name": "Preset One",
            "config": {
                "speed": 2,
                "color": "red",
                "advanced": False,
                "diag": False,
            },
        },
        "preset2": {
            "name": "Preset Two",
            "config": {
                "speed": 2,
                "color": "red",
                "advanced": True,
                "diag": True,
            },
        },
    }
    active_config = {
        "speed": 2,
        "color": "red",
        "advanced": False,
        "diag": True,
    }

    result = preset_endpoint._add_active_flags(presets, active_config)

    # Both should match since advanced and diag are ignored
    assert result["preset1"]["active"] is True
    assert result["preset2"]["active"] is True
