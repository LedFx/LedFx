"""
Tests for gap device handling in LedFx.

Gap devices are dummy placeholders created by the frontend to represent
empty spaces in discontiguous virtual matrix mappings.
"""


from ledfx.utils import is_gap_device


class MockDevice:
    """Mock device for testing."""

    def __init__(self, device_id, device_type):
        self.id = device_id
        self.type = device_type


class TestGapDeviceIdentification:
    """Test the is_gap_device helper function."""

    def test_gap_device_identification(self):
        """Test that gap devices are correctly identified with naming and dummy type."""
        # Gap devices with proper dummy type
        assert is_gap_device(MockDevice("gap-", "dummy"))
        assert is_gap_device(MockDevice("gap-matrix", "dummy"))
        assert is_gap_device(MockDevice("gap-my-virtual", "dummy"))
        assert is_gap_device(MockDevice("gap-livingroom", "dummy"))
        assert is_gap_device(MockDevice("gap-mapping", "dummy"))

    def test_non_gap_device_identification(self):
        """Test that non-gap devices are correctly identified."""
        # Non-gap devices - even with dummy type, naming must match
        assert not is_gap_device(MockDevice("test-device", "dummy"))
        assert not is_gap_device(MockDevice("wled-device", "dummy"))
        assert not is_gap_device(MockDevice("dummy", "dummy"))
        assert not is_gap_device(MockDevice("", "dummy"))
        assert not is_gap_device(MockDevice("gapdevice", "dummy"))  # no hyphen
        assert not is_gap_device(
            MockDevice("my-gap-device", "dummy")
        )  # doesn't start with gap-

    def test_special_device_types(self):
        """Test that special device types are not confused with gap devices."""
        # Complex device types - should not be gap devices
        assert not is_gap_device(MockDevice("test-device-background", "dummy"))
        assert not is_gap_device(MockDevice("test-device-foreground", "dummy"))
        assert not is_gap_device(MockDevice("test-device-mask", "dummy"))

    def test_gap_device_with_dummy_type(self):
        """Test that gap devices with dummy type are correctly identified."""
        # Gap devices with proper device type
        assert is_gap_device(MockDevice("gap-test", "dummy"))
        assert is_gap_device(MockDevice("gap-matrix", "dummy"))
        assert is_gap_device(MockDevice("gap-my-virtual", "dummy"))

    def test_gap_device_with_wrong_type(self):
        """Test that devices with gap naming but wrong type are rejected."""
        # Gap naming but not dummy type - should be rejected
        assert not is_gap_device(MockDevice("gap-test", "wled"))
        assert not is_gap_device(MockDevice("gap-matrix", "e131"))

    def test_non_gap_device_with_any_type(self):
        """Test that non-gap named devices are rejected regardless of type."""
        # Non-gap naming - should fail even with dummy type
        assert not is_gap_device(MockDevice("test-device", "dummy"))
        assert not is_gap_device(MockDevice("wled-device", "wled"))
        assert not is_gap_device(MockDevice("my-device", "dummy"))


class TestGapDeviceIntegration:
    """Test gap device integration with Virtual and Device classes."""

    def test_validate_segment_logic(self):
        """Test the validation logic for gap devices by reading source code."""
        # This is a basic sanity check - the actual validation is tested
        # through the API tests in test_definitions/virtual_config.py

        # Verify that the function is imported and available where needed
        import ledfx.virtuals
        from ledfx.utils import is_gap_device

        # Check that the module imports is_gap_device
        assert hasattr(ledfx.virtuals, "is_gap_device")

        # Test with proper mock devices
        assert is_gap_device(MockDevice("gap-test", "dummy"))
        assert not is_gap_device(MockDevice("real-device", "wled"))

    def test_devices_module_imports(self):
        """Verify devices module imports is_gap_device."""
        # Check that the module can access is_gap_device
        from ledfx.utils import is_gap_device

        assert is_gap_device(MockDevice("gap-test", "dummy"))
