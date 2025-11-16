"""
Unit tests for E131 device broadcast address detection
"""

import socket
import unittest
from unittest.mock import MagicMock, Mock, patch

from ledfx.devices.e131 import E131Device


class TestE131BroadcastDetection(unittest.TestCase):
    """Test E131 device broadcast address detection"""

    def setUp(self):
        """Set up test fixtures"""
        self.ledfx_mock = MagicMock()
        self.ledfx_mock.dev_enabled = MagicMock(return_value=False)
        self.ledfx_mock.config = {}
        self.ledfx_mock.loop = MagicMock()

        self.base_config = {
            "name": "Test E131 Device",
            "ip_address": "192.168.1.255",
            "pixel_count": 100,
            "universe": 1,
            "universe_size": 510,
            "channel_offset": 0,
            "packet_priority": 100,
            "refresh_rate": 30,
        }

    @patch("ledfx.devices.e131.check_if_ip_is_broadcast")
    @patch("ledfx.devices.e131.sacn")
    def test_broadcast_address_detection_enabled(
        self, mock_sacn, mock_check_broadcast
    ):
        """Test that SO_BROADCAST is enabled when broadcast address is detected"""
        # Setup
        mock_check_broadcast.return_value = True

        # Create mock sender with proper structure
        mock_sender = MagicMock()
        mock_socket = Mock()
        mock_sender._sender_handler.socket._socket = mock_socket
        mock_sacn.sACNsender.return_value = mock_sender

        # Create device and initialize destination
        device = E131Device(self.ledfx_mock, self.base_config)
        device._destination = "192.168.1.255"
        device.activate()

        # Verify broadcast check was called
        mock_check_broadcast.assert_called_once_with("192.168.1.255")

        # Verify SO_BROADCAST socket option was set
        mock_socket.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET, socket.SO_BROADCAST, 1
        )

    @patch("ledfx.devices.e131.check_if_ip_is_broadcast")
    @patch("ledfx.devices.e131.sacn")
    def test_broadcast_address_detection_disabled(
        self, mock_sacn, mock_check_broadcast
    ):
        """Test that SO_BROADCAST is not enabled for non-broadcast addresses"""
        # Setup
        mock_check_broadcast.return_value = False

        # Create mock sender with proper structure
        mock_sender = MagicMock()
        mock_socket = Mock()
        mock_sender._sender_handler.socket._socket = mock_socket
        mock_sacn.sACNsender.return_value = mock_sender

        # Create device with regular IP and activate
        config = self.base_config.copy()
        config["ip_address"] = "192.168.1.100"
        device = E131Device(self.ledfx_mock, config)
        device._destination = "192.168.1.100"
        device.activate()

        # Verify broadcast check was called
        mock_check_broadcast.assert_called_once_with("192.168.1.100")

        # Verify SO_BROADCAST socket option was NOT set
        mock_socket.setsockopt.assert_not_called()

    @patch("ledfx.devices.e131.check_if_ip_is_broadcast")
    @patch("ledfx.devices.e131.sacn")
    def test_multicast_mode_skips_broadcast_check(
        self, mock_sacn, mock_check_broadcast
    ):
        """Test that broadcast check is skipped when using multicast mode"""
        # Setup
        # Create mock sender with proper structure
        mock_sender = MagicMock()
        mock_socket = Mock()
        mock_sender._sender_handler.socket._socket = mock_socket
        mock_sacn.sACNsender.return_value = mock_sender

        # Create device with multicast and activate
        config = self.base_config.copy()
        config["ip_address"] = "multicast"
        device = E131Device(self.ledfx_mock, config)
        device._destination = "multicast"
        device.activate()

        # Verify broadcast check was NOT called
        mock_check_broadcast.assert_not_called()

        # Verify SO_BROADCAST socket option was NOT set
        mock_socket.setsockopt.assert_not_called()

    @patch("ledfx.devices.e131.check_if_ip_is_broadcast")
    @patch("ledfx.devices.e131.sacn")
    def test_broadcast_socket_option_error_handling(
        self, mock_sacn, mock_check_broadcast
    ):
        """Test that socket option errors are handled gracefully"""
        # Setup
        mock_check_broadcast.return_value = True

        # Create mock sender with proper structure
        mock_sender = MagicMock()
        mock_socket = Mock()
        mock_socket.setsockopt.side_effect = OSError("Socket error")
        mock_sender._sender_handler.socket._socket = mock_socket
        mock_sacn.sACNsender.return_value = mock_sender

        # Create device and activate - should not raise exception
        device = E131Device(self.ledfx_mock, self.base_config)
        device._destination = "192.168.1.255"
        device.activate()

        # Verify broadcast check was called
        mock_check_broadcast.assert_called_once_with("192.168.1.255")

        # Verify SO_BROADCAST socket option was attempted
        mock_socket.setsockopt.assert_called_once_with(
            socket.SOL_SOCKET, socket.SO_BROADCAST, 1
        )


if __name__ == "__main__":
    unittest.main()
