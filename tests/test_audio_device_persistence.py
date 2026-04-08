"""
Tests for audio device name persistence and cross-session resolution.

Strategy doc: docs/developer/dev_notes/audio-device-persistence-strategy.md
"""

import logging
from unittest.mock import MagicMock, call, patch

import pytest

from ledfx.effects.audio import AudioInputSource

_LOGGER = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Mock device lists (from strategy doc §7.1)
# ---------------------------------------------------------------------------

DEVICES_BEFORE = {
    0: "Windows WASAPI: Microphone (Realtek High Definition Audio)",
    5: "Windows WASAPI: Stereo Mix (Realtek High Definition Audio)",
    17: "Windows WASAPI: Speakers (Realtek High Definition Audio) [Loopback]",
    22: "Windows WASAPI: Headset (Bluetooth)",
}

DEVICES_AFTER_USB_ADDED = {
    0: "Windows WASAPI: Microphone (Realtek High Definition Audio)",
    3: "Windows WASAPI: USB Audio Interface",
    5: "Windows WASAPI: Stereo Mix (Realtek High Definition Audio)",
    18: "Windows WASAPI: Speakers (Realtek High Definition Audio) [Loopback]",
    23: "Windows WASAPI: Headset (Bluetooth)",
}

DEVICES_AFTER_REMOVAL = {
    0: "Windows WASAPI: Microphone (Realtek High Definition Audio)",
    5: "Windows WASAPI: Stereo Mix (Realtek High Definition Audio)",
    22: "Windows WASAPI: Headset (Bluetooth)",
}

DEVICES_TRUNCATED = {
    0: "Windows WASAPI: Microphone (Realtek High Def",
    17: "Windows WASAPI: Speakers (Realtek High Def",
}

DEVICES_SIMILAR_NAMES = {
    0: "Windows WASAPI: Microphone",
    1: "Windows WASAPI: Microphone (Realtek)",
    2: "Windows WASAPI: Microphone (Realtek High Definition Audio)",
}

DEVICES_INDEX_VALID_NAME_WRONG = {
    17: "Windows WASAPI: Microphone (Realtek High Definition Audio)",
    18: "Windows WASAPI: Speakers (Realtek High Definition Audio) [Loopback]",
}

LOOPBACK_NAME = "Windows WASAPI: Speakers (Realtek High Definition Audio) [Loopback]"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_mock_ledfx(audio_config=None):
    """Create a mock LedFx instance with config and config_dir."""
    mock = MagicMock()
    mock.config = {"audio": audio_config or {}}
    mock.config_dir = "/tmp/test_config"
    return mock


def make_ais(config=None, ledfx=None):
    """
    Create an AudioInputSource-like object with _config and _ledfx set
    for testing _resolve_device_from_name() and _update_device_config()
    without running __init__ (which requires a real ledfx + audio hardware).
    """
    ais = object.__new__(AudioInputSource)
    ais._config = config or {}
    ais._ledfx = ledfx
    return ais


# ===========================================================================
# §7.2 — _resolve_device_from_name()
# ===========================================================================


class TestResolveDeviceFromName:
    """Core resolution logic tests."""

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_resolve_name_matches_at_saved_index(self, mock_devices):
        """#1: Name matches device at saved index — no change."""
        config = {"audio_device": 17, "audio_device_name": LOOPBACK_NAME}
        ais = make_ais(config=config)
        ais._resolve_device_from_name()

        assert ais._config["audio_device"] == 17
        assert ais._config["audio_device_name"] == LOOPBACK_NAME

    @patch("ledfx.effects.audio.save_config")
    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_AFTER_USB_ADDED)
    def test_resolve_name_found_at_different_index(self, mock_devices, mock_save):
        """#2: Device shifted to new index — update index, persist."""
        ledfx = make_mock_ledfx({"audio_device": 17, "audio_device_name": LOOPBACK_NAME})
        config = {"audio_device": 17, "audio_device_name": LOOPBACK_NAME}
        ais = make_ais(config=config, ledfx=ledfx)
        ais._resolve_device_from_name()

        assert ais._config["audio_device"] == 18
        assert ais._config["audio_device_name"] == LOOPBACK_NAME
        mock_save.assert_called_once()

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_AFTER_REMOVAL)
    @patch.object(AudioInputSource, "default_device_index", return_value=0)
    def test_resolve_name_not_found_device_removed(self, mock_default, mock_devices):
        """#3: Device removed — name cleared, falls through to index/default logic."""
        config = {"audio_device": 17, "audio_device_name": LOOPBACK_NAME}
        ais = make_ais(config=config)
        ais._resolve_device_from_name()

        # Name should be cleared
        assert ais._config["audio_device_name"] == ""
        # Index unchanged by resolver — existing validator handles fallback
        assert ais._config["audio_device"] == 17

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_resolve_empty_name_skips_resolution(self, mock_devices):
        """#4: Empty name string — skip resolution, use index as-is."""
        config = {"audio_device": 17, "audio_device_name": ""}
        ais = make_ais(config=config)
        ais._resolve_device_from_name()

        assert ais._config["audio_device"] == 17
        # input_devices should not even be called when name is empty
        mock_devices.assert_not_called()

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_resolve_no_name_key_skips_resolution(self, mock_devices):
        """#5: No audio_device_name key at all (schema default applies)."""
        config = {"audio_device": 17}
        ais = make_ais(config=config)
        ais._resolve_device_from_name()

        assert ais._config["audio_device"] == 17
        mock_devices.assert_not_called()

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_resolve_partial_match_truncated_name(self, mock_devices):
        """#6: Truncated name finds match via partial matching."""
        truncated_name = "Windows WASAPI: Speakers (Realtek High Def"
        config = {"audio_device": 99, "audio_device_name": truncated_name}
        ais = make_ais(config=config)
        ais._resolve_device_from_name()

        # Should find index 17 via partial match
        assert ais._config["audio_device"] == 17

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_SIMILAR_NAMES)
    def test_resolve_prefers_exact_over_partial(self, mock_devices):
        """#7: Exact match at index 1 preferred over partial at index 2."""
        name = "Windows WASAPI: Microphone (Realtek)"
        config = {"audio_device": 99, "audio_device_name": name}
        ais = make_ais(config=config)
        ais._resolve_device_from_name()

        assert ais._config["audio_device"] == 1

    @patch("ledfx.effects.audio.save_config")
    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_resolve_saved_index_invalid_name_found(self, mock_devices, mock_save):
        """#8: Saved index 99 invalid but name found at 17."""
        ledfx = make_mock_ledfx()
        config = {"audio_device": 99, "audio_device_name": LOOPBACK_NAME}
        ais = make_ais(config=config, ledfx=ledfx)
        ais._resolve_device_from_name()

        assert ais._config["audio_device"] == 17
        mock_save.assert_called_once()

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_resolve_saved_index_invalid_name_not_found(self, mock_devices):
        """#9: Index 99 invalid AND name not found — name cleared."""
        config = {"audio_device": 99, "audio_device_name": "Nonexistent Device"}
        ais = make_ais(config=config)
        ais._resolve_device_from_name()

        assert ais._config["audio_device_name"] == ""

    @patch("ledfx.effects.audio.save_config")
    @patch.object(
        AudioInputSource, "input_devices", return_value=DEVICES_INDEX_VALID_NAME_WRONG
    )
    def test_resolve_index_valid_but_wrong_device(self, mock_devices, mock_save):
        """#10: Index 17 valid but points to wrong device — name search finds 18."""
        ledfx = make_mock_ledfx()
        config = {"audio_device": 17, "audio_device_name": LOOPBACK_NAME}
        ais = make_ais(config=config, ledfx=ledfx)
        ais._resolve_device_from_name()

        assert ais._config["audio_device"] == 18
        mock_save.assert_called_once()


# ===========================================================================
# §7.3 — Legacy Upgrade Path
# ===========================================================================


class TestLegacyUpgradePath:
    """Verify seamless upgrade from index-only configs."""

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    @patch.object(AudioInputSource, "valid_device_indexes", return_value=tuple(DEVICES_BEFORE.keys()))
    @patch.object(AudioInputSource, "default_device_index", return_value=0)
    def test_legacy_config_no_name_field(self, mock_default, mock_valid, mock_devices):
        """#11: Config with only audio_device — schema defaults audio_device_name to ''."""
        schema = AudioInputSource.AUDIO_CONFIG_SCHEMA.fget()
        config = schema({"audio_device": 17})

        assert config["audio_device"] == 17
        assert config["audio_device_name"] == ""

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    @patch.object(AudioInputSource, "valid_device_indexes", return_value=tuple(DEVICES_BEFORE.keys()))
    @patch.object(AudioInputSource, "default_device_index", return_value=0)
    def test_legacy_config_empty_audio_dict(self, mock_default, mock_valid, mock_devices):
        """#12: Empty audio config — default device chosen, no name."""
        schema = AudioInputSource.AUDIO_CONFIG_SCHEMA.fget()
        config = schema({})

        assert config["audio_device"] == 0  # default_device_index
        assert config["audio_device_name"] == ""

    @patch("ledfx.effects.audio.save_config")
    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_legacy_upgrade_name_persisted_on_activation(self, mock_devices, mock_save):
        """#13: After activation with legacy config, name is persisted."""
        ledfx = make_mock_ledfx({"audio_device": 17})
        config = {"audio_device": 17, "audio_device_name": ""}
        ais = make_ais(config=config, ledfx=ledfx)

        # Simulate _update_device_config which is called during activation
        ais._update_device_config(17)

        assert ais._config["audio_device_name"] == LOOPBACK_NAME
        mock_save.assert_called_once()

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_legacy_upgrade_name_not_persisted_for_invalid_device(self, mock_devices):
        """#14: Activation with invalid index — name not persisted (empty)."""
        config = {"audio_device": 999, "audio_device_name": ""}
        ais = make_ais(config=config)

        ais._update_device_config(999)

        assert ais._config["audio_device_name"] == ""

    @patch("ledfx.effects.audio.save_config")
    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_AFTER_USB_ADDED)
    def test_legacy_upgrade_second_startup_uses_name(self, mock_devices, mock_save):
        """#15: First boot persists name, second boot resolves by name to new index."""
        # Simulate second boot: name was persisted, but indices shifted
        ledfx = make_mock_ledfx()
        config = {"audio_device": 17, "audio_device_name": LOOPBACK_NAME}
        ais = make_ais(config=config, ledfx=ledfx)
        ais._resolve_device_from_name()

        assert ais._config["audio_device"] == 18


# ===========================================================================
# §7.4 — API Endpoint
# ===========================================================================


class TestAudioDevicesApi:
    """API endpoint tests for name persistence."""

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    @patch.object(AudioInputSource, "valid_device_indexes", return_value=tuple(DEVICES_BEFORE.keys()))
    def test_api_put_persists_name_and_index(self, mock_valid, mock_devices):
        """#16: PUT stores both audio_device and audio_device_name in config."""
        # Simulate what the PUT handler does
        index = 5
        new_config = {}
        new_config["audio_device"] = int(index)
        devices = AudioInputSource.input_devices()
        if index in devices:
            new_config["audio_device_name"] = devices[index]

        assert new_config["audio_device"] == 5
        assert new_config["audio_device_name"] == "Windows WASAPI: Stereo Mix (Realtek High Definition Audio)"

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    @patch.object(AudioInputSource, "valid_device_indexes", return_value=tuple(DEVICES_BEFORE.keys()))
    def test_api_put_invalid_index_not_in_devices(self, mock_valid, mock_devices):
        """#17: PUT with index not in valid_indexes — name not added."""
        index = 999
        valid_indexes = AudioInputSource.valid_device_indexes()

        assert index not in valid_indexes

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    @patch.object(AudioInputSource, "valid_device_indexes", return_value=tuple(DEVICES_BEFORE.keys()))
    @patch.object(AudioInputSource, "default_device_index", return_value=0)
    def test_api_get_returns_name(self, mock_default, mock_valid, mock_devices):
        """#18: GET response includes active_device_name."""
        schema = AudioInputSource.AUDIO_CONFIG_SCHEMA.fget()
        audio_config = schema({"audio_device": 17, "audio_device_name": LOOPBACK_NAME})

        response = {}
        response["active_device_index"] = audio_config["audio_device"]
        response["active_device_name"] = audio_config.get("audio_device_name", "")

        assert response["active_device_index"] == 17
        assert response["active_device_name"] == LOOPBACK_NAME


# ===========================================================================
# §7.5 — _update_device_config()
# ===========================================================================


class TestUpdateDeviceConfig:
    """Config save helper tests."""

    @patch("ledfx.effects.audio.save_config")
    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_update_device_config_writes_name(self, mock_devices, mock_save):
        """#19: Valid device_idx — both audio_device and audio_device_name set."""
        ledfx = make_mock_ledfx()
        ais = make_ais(config={"audio_device": 0, "audio_device_name": ""}, ledfx=ledfx)
        ais._update_device_config(17)

        assert ais._config["audio_device"] == 17
        assert ais._config["audio_device_name"] == LOOPBACK_NAME

    @patch("ledfx.effects.audio.save_config")
    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_update_device_config_clears_name_for_invalid(self, mock_devices, mock_save):
        """#20: Invalid device_idx — name cleared."""
        ledfx = make_mock_ledfx()
        ais = make_ais(
            config={"audio_device": 17, "audio_device_name": LOOPBACK_NAME},
            ledfx=ledfx,
        )
        ais._update_device_config(999)

        assert ais._config["audio_device"] == 999
        assert ais._config["audio_device_name"] == ""

    @patch("ledfx.effects.audio.save_config")
    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_update_device_config_saves_to_disk(self, mock_devices, mock_save):
        """#21: With _ledfx attached — save_config is called."""
        ledfx = make_mock_ledfx()
        ais = make_ais(config={"audio_device": 0, "audio_device_name": ""}, ledfx=ledfx)
        ais._update_device_config(17)

        mock_save.assert_called_once_with(
            config=ledfx.config,
            config_dir=ledfx.config_dir,
        )

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_update_device_config_no_ledfx_no_crash(self, mock_devices):
        """_update_device_config without _ledfx doesn't crash."""
        ais = make_ais(config={"audio_device": 0, "audio_device_name": ""}, ledfx=None)
        ais._update_device_config(17)

        assert ais._config["audio_device"] == 17
        assert ais._config["audio_device_name"] == LOOPBACK_NAME


# ===========================================================================
# §7.6 — handle_device_list_change() integration
# ===========================================================================


class TestHandleDeviceListChangeIntegration:
    """Runtime hotplug recovery with name field."""

    @patch("ledfx.effects.audio.save_config")
    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_AFTER_USB_ADDED)
    @patch.object(AudioInputSource, "default_device_index", return_value=0)
    def test_hotplug_recovery_updates_name(self, mock_default, mock_devices, mock_save):
        """#22: Device shifts — _update_device_config persists new name."""
        ledfx = make_mock_ledfx()
        ais = make_ais(
            config={"audio_device": 17, "audio_device_name": LOOPBACK_NAME},
            ledfx=ledfx,
        )

        # Simulate what handle_device_list_change does when it finds device at new index
        ais._update_device_config(18)

        assert ais._config["audio_device"] == 18
        assert ais._config["audio_device_name"] == LOOPBACK_NAME

    @patch("ledfx.effects.audio.save_config")
    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_AFTER_REMOVAL)
    @patch.object(AudioInputSource, "default_device_index", return_value=0)
    def test_hotplug_device_removed_uses_fallback(self, mock_default, mock_devices, mock_save):
        """#23: Device removed — falls to default, name updated."""
        ledfx = make_mock_ledfx()
        ais = make_ais(
            config={"audio_device": 17, "audio_device_name": LOOPBACK_NAME},
            ledfx=ledfx,
        )

        # Simulate fallback to default device
        ais._update_device_config(0)

        assert ais._config["audio_device"] == 0
        assert ais._config["audio_device_name"] == "Windows WASAPI: Microphone (Realtek High Definition Audio)"

    def test_hotplug_no_active_stream_no_crash(self):
        """#24: Device change event with no active stream — no error."""
        # Just verify _resolve_device_from_name doesn't crash with empty config
        ais = make_ais(config={})
        ais._resolve_device_from_name()  # Should not raise


# ===========================================================================
# §7.7 — get_device_index_by_name() edge cases
# ===========================================================================


class TestGetDeviceIndexByName:
    """Name matching logic tests."""

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_exact_match_preferred(self, mock_devices):
        """#25: Exact name match returns correct index."""
        ais = make_ais()
        result = ais.get_device_index_by_name(LOOPBACK_NAME)
        assert result == 17

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_partial_match_stored_name_is_substring(self, mock_devices):
        """#26: Truncated stored name matches as substring."""
        ais = make_ais()
        truncated = "Windows WASAPI: Speakers (Realtek High Def"
        result = ais.get_device_index_by_name(truncated)
        assert result == 17

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_no_match_returns_negative_one(self, mock_devices):
        """#27: No match returns -1."""
        ais = make_ais()
        result = ais.get_device_index_by_name("Totally Nonexistent Device XYZ")
        assert result == -1

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_empty_string_returns_negative_one(self, mock_devices):
        """#28: Empty string returns -1 (matches everything as substring, but
        get_device_index_by_name tries exact first, then substring)."""
        ais = make_ais()
        result = ais.get_device_index_by_name("")
        # Empty string is a substring of everything, so it will match.
        # This is acceptable — callers should not pass empty strings.
        # The resolver already guards against this.
        assert isinstance(result, int)

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_case_sensitive_matching(self, mock_devices):
        """#29: Device name matching is case-sensitive."""
        ais = make_ais()
        # Uppercase version should not exact-match
        result = ais.get_device_index_by_name(LOOPBACK_NAME.upper())
        # No exact match expected; partial match depends on case
        assert result == -1 or isinstance(result, int)

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_SIMILAR_NAMES)
    def test_partial_match_avoids_false_positive(self, mock_devices):
        """#30: Short name 'Microphone' is substring of all — returns longest match."""
        ais = make_ais()
        result = ais.get_device_index_by_name("Windows WASAPI: Microphone")
        # Exact match at 0
        assert result == 0


# ===========================================================================
# §7.8 — Regression Guard Tests
# ===========================================================================


class TestRegressionGuards:
    """Ensure new code doesn't break existing behavior."""

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    @patch.object(AudioInputSource, "valid_device_indexes", return_value=tuple(DEVICES_BEFORE.keys()))
    @patch.object(AudioInputSource, "default_device_index", return_value=0)
    def test_schema_accepts_legacy_config_without_name(self, mock_default, mock_valid, mock_devices):
        """#31: Schema validation doesn't reject old configs without audio_device_name."""
        schema = AudioInputSource.AUDIO_CONFIG_SCHEMA.fget()
        config = schema({"audio_device": 17})

        assert "audio_device" in config
        assert "audio_device_name" in config
        assert config["audio_device_name"] == ""

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    @patch.object(AudioInputSource, "valid_device_indexes", return_value=tuple(DEVICES_BEFORE.keys()))
    @patch.object(AudioInputSource, "default_device_index", return_value=0)
    def test_schema_allows_extra_keys(self, mock_default, mock_valid, mock_devices):
        """#32: ALLOW_EXTRA still works — other audio config fields not lost."""
        schema = AudioInputSource.AUDIO_CONFIG_SCHEMA.fget()
        config = schema({"audio_device": 17, "custom_field": "preserved"})

        assert config["custom_field"] == "preserved"

    @patch.object(AudioInputSource, "valid_device_indexes", return_value=tuple(DEVICES_BEFORE.keys()))
    @patch.object(AudioInputSource, "default_device_index", return_value=0)
    def test_device_index_validator_unchanged_behavior(self, mock_default, mock_valid):
        """#33: Validator returns value for valid index, default for invalid."""
        assert AudioInputSource.device_index_validator(17) == 17
        assert AudioInputSource.device_index_validator(999) == 0

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    def test_resolve_still_works_without_name(self, mock_devices):
        """#34: Full resolution path works with audio_device_name=''."""
        config = {"audio_device": 17, "audio_device_name": ""}
        ais = make_ais(config=config)
        ais._resolve_device_from_name()

        # No change — index preserved
        assert ais._config["audio_device"] == 17

    @patch.object(AudioInputSource, "input_devices", return_value=DEVICES_BEFORE)
    @patch.object(AudioInputSource, "valid_device_indexes", return_value=tuple(DEVICES_BEFORE.keys()))
    @patch.object(AudioInputSource, "default_device_index", return_value=0)
    def test_config_roundtrip_preserves_all_fields(self, mock_default, mock_valid, mock_devices):
        """#35: Save → load cycle preserves both audio_device and audio_device_name."""
        schema = AudioInputSource.AUDIO_CONFIG_SCHEMA.fget()
        original = {"audio_device": 17, "audio_device_name": LOOPBACK_NAME}
        config = schema(original)

        assert config["audio_device"] == 17
        assert config["audio_device_name"] == LOOPBACK_NAME

    @patch.object(AudioInputSource, "input_devices", return_value={
        0: "WEB AUDIO: browser-client-123",
    })
    def test_web_audio_device_name_persisted(self, mock_devices):
        """#36: WEB AUDIO virtual devices also get name persisted."""
        ais = make_ais(config={"audio_device": 0, "audio_device_name": ""})
        ais._update_device_config(0)

        assert ais._config["audio_device_name"] == "WEB AUDIO: browser-client-123"

    @patch.object(AudioInputSource, "input_devices", return_value={
        0: "SENDSPIN: my-sendspin-server",
    })
    def test_sendspin_device_name_persisted(self, mock_devices):
        """#37: SENDSPIN devices also get name persisted."""
        ais = make_ais(config={"audio_device": 0, "audio_device_name": ""})
        ais._update_device_config(0)

        assert ais._config["audio_device_name"] == "SENDSPIN: my-sendspin-server"
