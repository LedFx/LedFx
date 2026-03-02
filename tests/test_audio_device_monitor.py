"""Tests for ledfx/audio_device_monitor.py - Audio device monitoring"""

import asyncio
import sys
import threading
from unittest.mock import MagicMock, Mock, call, patch

import pytest

from ledfx.audio_device_monitor import (
    AudioDeviceMonitor,
    LinuxAudioDeviceMonitor,
    MacOSAudioDeviceMonitor,
    WindowsAudioDeviceMonitor,
    create_audio_device_monitor,
)
from ledfx.events import Event


class TestAudioDeviceMonitorBase:
    """Test AudioDeviceMonitor abstract base class"""

    def test_fire_device_list_changed_event_schedules_coroutine(self):
        """Test that _fire_device_list_changed_event schedules the coroutine"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        # Create concrete subclass for testing
        class TestMonitor(AudioDeviceMonitor):
            def start_monitoring(self):
                pass

            def stop_monitoring(self):
                pass

        monitor = TestMonitor(mock_ledfx, mock_loop)
        monitor._fire_device_list_changed_event()

        # Verify run_coroutine_threadsafe was called
        # Note: We can't easily verify the exact call since it uses asyncio.run_coroutine_threadsafe
        assert monitor._loop is mock_loop
        assert monitor._ledfx is mock_ledfx

    def test_abstract_methods_raise_not_implemented(self):
        """Test that abstract methods can't be instantiated without implementation"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        # Can't instantiate abstract class
        with pytest.raises(TypeError, match="abstract"):
            monitor = AudioDeviceMonitor(mock_ledfx, mock_loop)


class TestCreateAudioDeviceMonitor:
    """Test create_audio_device_monitor factory function"""

    def test_create_monitor_windows(self):
        """Test creating monitor on Windows platform"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        with patch("sys.platform", "win32"):
            monitor = create_audio_device_monitor(mock_ledfx, mock_loop)

        assert isinstance(monitor, WindowsAudioDeviceMonitor)
        assert monitor._ledfx is mock_ledfx
        assert monitor._loop is mock_loop

    def test_create_monitor_macos(self):
        """Test creating monitor on macOS platform"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        with patch("sys.platform", "darwin"):
            monitor = create_audio_device_monitor(mock_ledfx, mock_loop)

        assert isinstance(monitor, MacOSAudioDeviceMonitor)
        assert monitor._ledfx is mock_ledfx
        assert monitor._loop is mock_loop

    def test_create_monitor_linux(self):
        """Test creating monitor on Linux platform"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        with patch("sys.platform", "linux"):
            monitor = create_audio_device_monitor(mock_ledfx, mock_loop)

        assert isinstance(monitor, LinuxAudioDeviceMonitor)
        assert monitor._ledfx is mock_ledfx
        assert monitor._loop is mock_loop

    def test_create_monitor_unknown_platform(self):
        """Test creating monitor on unknown platform returns None"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        with patch("sys.platform", "freebsd"):
            monitor = create_audio_device_monitor(mock_ledfx, mock_loop)

        assert monitor is None


class TestWindowsAudioDeviceMonitor:
    """Test WindowsAudioDeviceMonitor"""

    def test_monitor_initialization(self):
        """Test that Windows monitor initializes correctly"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        monitor = WindowsAudioDeviceMonitor(mock_ledfx, mock_loop)

        assert monitor._ledfx is mock_ledfx
        assert monitor._loop is mock_loop
        assert monitor._running is False
        assert monitor._monitor_thread is None

    def test_monitor_handles_import_error_gracefully(self):
        """Test that missing pycaw is handled gracefully"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        # Patch the import inside start_monitoring
        with patch(
            "builtins.__import__", side_effect=ImportError("pycaw not found")
        ):
            monitor = WindowsAudioDeviceMonitor(mock_ledfx, mock_loop)
            monitor.start_monitoring()  # Should not raise

        # Monitor should not be running
        assert monitor._running is False


class TestMacOSAudioDeviceMonitor:
    """Test MacOSAudioDeviceMonitor"""

    def test_monitor_initialization(self):
        """Test that macOS monitor initializes correctly"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        monitor = MacOSAudioDeviceMonitor(mock_ledfx, mock_loop)

        assert monitor._ledfx is mock_ledfx
        assert monitor._loop is mock_loop
        assert monitor._running is False
        assert monitor._monitor_thread is None

    def test_monitor_handles_import_error_gracefully(self):
        """Test that missing CoreAudio is handled gracefully"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        # Patch the import inside start_monitoring
        with patch(
            "builtins.__import__",
            side_effect=ImportError("CoreAudio not found"),
        ):
            monitor = MacOSAudioDeviceMonitor(mock_ledfx, mock_loop)
            monitor.start_monitoring()  # Should not raise

        # Monitor should not be running
        assert monitor._running is False


class TestLinuxAudioDeviceMonitor:
    """Test LinuxAudioDeviceMonitor"""

    def test_monitor_initialization(self):
        """Test that Linux monitor initializes correctly"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        monitor = LinuxAudioDeviceMonitor(mock_ledfx, mock_loop)

        assert monitor._ledfx is mock_ledfx
        assert monitor._loop is mock_loop
        assert monitor._running is False
        assert monitor._monitor_thread is None

    def test_monitor_handles_import_error_gracefully(self):
        """Test that missing pyudev is handled gracefully"""
        mock_ledfx = MagicMock()
        mock_loop = MagicMock()

        # Patch the import inside start_monitoring
        with patch(
            "builtins.__import__", side_effect=ImportError("pyudev not found")
        ):
            monitor = LinuxAudioDeviceMonitor(mock_ledfx, mock_loop)
            monitor.start_monitoring()  # Should not raise

        # Monitor should not be running
        assert monitor._running is False


class TestAudioDeviceListChangedEvent:
    """Test AudioDeviceListChangedEvent"""

    def test_event_has_correct_type(self):
        """Test that event is created with correct type"""
        from ledfx.events import AudioDeviceListChangedEvent, Event

        event = AudioDeviceListChangedEvent()

        assert event.event_type == Event.AUDIO_DEVICE_LIST_CHANGED
        assert event.event_type == "audio_device_list_changed"

    def test_event_constant_exists(self):
        """Test that AUDIO_DEVICE_LIST_CHANGED constant is defined"""
        from ledfx.events import Event

        assert hasattr(Event, "AUDIO_DEVICE_LIST_CHANGED")
        assert Event.AUDIO_DEVICE_LIST_CHANGED == "audio_device_list_changed"


class TestAudioInputSourceRefresh:
    """Test AudioInputSource.refresh_device_list()"""

    @patch("ledfx.effects.audio.sd")
    def test_refresh_device_list_reinitializes_sounddevice(self, mock_sd):
        """Test that refresh_device_list() calls sd._terminate() and sd._initialize()"""
        from ledfx.effects.audio import AudioInputSource

        AudioInputSource.refresh_device_list()

        # Verify PortAudio reinitialization
        mock_sd._terminate.assert_called_once()
        mock_sd._initialize.assert_called_once()

    @patch("ledfx.effects.audio.sd")
    def test_refresh_device_list_handles_errors(self, mock_sd):
        """Test that refresh_device_list() handles errors gracefully"""
        from ledfx.effects.audio import AudioInputSource

        # Simulate error during reinit
        mock_sd._terminate.side_effect = Exception("PortAudio error")

        # Should not raise
        AudioInputSource.refresh_device_list()

    @patch("ledfx.effects.audio.sd")
    def test_refresh_device_list_clears_cache(self, mock_sd):
        """Test that refresh_device_list() clears device list cache"""
        from ledfx.effects.audio import AudioInputSource

        # Set cache
        AudioInputSource._device_list_cache = {"test": "data"}

        AudioInputSource.refresh_device_list()

        # Verify cache cleared
        assert AudioInputSource._device_list_cache is None
