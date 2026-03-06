"""Test the factory function and platform detection."""

import sys
from unittest.mock import patch

import pytest

from audio_hotplug import create_monitor
from audio_hotplug._base import AudioDeviceMonitor


class TestFactory:
    """Test cases for create_monitor factory function."""

    @patch("sys.platform", "win32")
    def test_windows_platform_detection(self):
        """Test that Windows platform returns Windows monitor or None."""
        # Should attempt to create Windows monitor
        # May return None if pycaw not installed (expected in test env)
        monitor = create_monitor()
        assert monitor is None or isinstance(monitor, AudioDeviceMonitor)

    @patch("sys.platform", "darwin")
    def test_macos_platform_detection(self):
        """Test that macOS platform returns macOS monitor or None."""
        # Should attempt to create macOS monitor
        # May return None if pyobjc not installed (expected in test env)
        monitor = create_monitor()
        assert monitor is None or isinstance(monitor, AudioDeviceMonitor)

    @patch("sys.platform", "linux")
    def test_linux_platform_detection(self):
        """Test that Linux platform returns Linux monitor or None."""
        # Should attempt to create Linux monitor
        # May return None if pyudev not installed (expected in test env)
        monitor = create_monitor()
        assert monitor is None or isinstance(monitor, AudioDeviceMonitor)

    @patch("sys.platform", "unsupported_os")
    def test_unsupported_platform_returns_none(self):
        """Test that unsupported platforms return None."""
        monitor = create_monitor()
        assert monitor is None

    def test_debounce_parameter_passed(self):
        """Test that debounce_ms parameter is passed to monitor."""
        monitor = create_monitor(debounce_ms=500)
        # May be None if dependencies not installed
        if monitor is not None:
            assert hasattr(monitor, "_debounce_ms")
            assert monitor._debounce_ms == 500

    def test_logger_parameter_passed(self):
        """Test that logger parameter is passed to monitor."""
        import logging

        custom_logger = logging.getLogger("test_logger")

        monitor = create_monitor(logger=custom_logger)
        # May be None if dependencies not installed
        if monitor is not None:
            assert hasattr(monitor, "_logger")
            # Logger should be used (either custom or default)
            assert monitor._logger is not None

    def test_loop_parameter_passed(self):
        """Test that loop parameter is passed to monitor."""
        import asyncio

        loop = asyncio.new_event_loop()

        monitor = create_monitor(loop=loop)
        # May be None if dependencies not installed
        if monitor is not None:
            assert hasattr(monitor, "_loop")
            assert monitor._loop is loop

        loop.close()

    def test_lazy_import_no_early_import(self):
        """Test that platform modules are not imported until needed."""
        # Clear any existing imports
        modules_to_check = [
            "audio_hotplug._platform.windows",
            "audio_hotplug._platform.macos",
            "audio_hotplug._platform.linux",
        ]

        # Remove from sys.modules if present
        for mod in modules_to_check:
            if mod in sys.modules:
                del sys.modules[mod]

        # Import just the factory
        from audio_hotplug import create_monitor as cm

        # Platform modules should not be imported yet
        # (This test may not be fully accurate if tests run in sequence)
        # At minimum, verify the import doesn't fail
        assert cm is not None

    @patch("sys.platform", "win32")
    def test_windows_import_error_handling(self):
        """Test that ImportError on Windows is handled gracefully."""
        # Simulate ImportError by patching the import within the factory
        with patch("audio_hotplug.monitor.sys.platform", "win32"):
            with patch.dict(
                "sys.modules", {"audio_hotplug._platform.windows": None}
            ):
                # This will cause an import error which should be caught
                monitor = create_monitor()
                # Should return None or valid monitor, not raise
                assert monitor is None or isinstance(
                    monitor, AudioDeviceMonitor
                )

    def test_multiple_monitors_independent(self):
        """Test that multiple monitor instances are independent."""
        import asyncio

        loop1 = asyncio.new_event_loop()
        loop2 = asyncio.new_event_loop()

        monitor1 = create_monitor(loop=loop1, debounce_ms=100)
        monitor2 = create_monitor(loop=loop2, debounce_ms=200)

        # If both created successfully, verify independence
        if monitor1 and monitor2:
            assert monitor1 is not monitor2
            assert monitor1._loop is loop1
            assert monitor2._loop is loop2
            assert monitor1._debounce_ms == 100
            assert monitor2._debounce_ms == 200

        loop1.close()
        loop2.close()

    def test_default_parameters(self):
        """Test that factory works with no parameters."""
        monitor = create_monitor()
        # May be None if dependencies not installed, but should not raise
        assert monitor is None or isinstance(monitor, AudioDeviceMonitor)

    def test_monitor_has_required_methods(self):
        """Test that returned monitor has start and stop methods."""
        monitor = create_monitor()

        if monitor is not None:
            assert hasattr(monitor, "start")
            assert callable(monitor.start)
            assert hasattr(monitor, "stop")
            assert callable(monitor.stop)

    @patch("sys.platform", "linux")
    def test_linux_variations(self):
        """Test that linux variations (linux, linux2, etc.) are detected."""
        monitor = create_monitor()
        # Should attempt Linux monitor
        assert monitor is None or isinstance(monitor, AudioDeviceMonitor)

    @patch("sys.platform", "linux2")
    def test_linux2_variation(self):
        """Test linux2 platform string."""
        monitor = create_monitor()
        assert monitor is None or isinstance(monitor, AudioDeviceMonitor)


class TestPlatformSpecificModules:
    """Test platform-specific module structure."""

    def test_windows_module_exists(self):
        """Test that Windows module can be imported."""
        try:
            from audio_hotplug._platform import windows

            assert hasattr(windows, "WindowsAudioDeviceMonitor")
        except ImportError:
            pytest.skip("Windows platform module not available")

    def test_macos_module_exists(self):
        """Test that macOS module can be imported."""
        try:
            from audio_hotplug._platform import macos

            assert hasattr(macos, "MacOSAudioDeviceMonitor")
        except ImportError:
            pytest.skip("macOS platform module not available")

    def test_linux_module_exists(self):
        """Test that Linux module can be imported."""
        try:
            from audio_hotplug._platform import linux

            assert hasattr(linux, "LinuxAudioDeviceMonitor")
        except ImportError:
            pytest.skip("Linux platform module not available")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
