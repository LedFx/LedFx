"""
Security tests for path traversal and SSRF vulnerabilities
"""

import ipaddress
import socket
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ledfx.utils import (
    BLOCKED_IP_RANGES,
    get_allowed_image_dirs,
    open_gif,
    open_image,
    validate_file_path,
    validate_url,
)


class TestPathTraversalPrevention:
    """Test path traversal attack prevention"""

    def test_validate_file_path_allows_valid_path(self, tmp_path):
        """Test that valid paths in allowed directories are accepted"""
        # Create a test file
        test_file = tmp_path / "test_image.png"
        test_file.write_text("test")

        # Validate with explicit allowed directory
        result = validate_file_path(str(test_file), [tmp_path])
        assert result == test_file.resolve()

    def test_validate_file_path_blocks_parent_traversal(self, tmp_path):
        """Test that ../ path traversal is blocked"""
        # Create a test file outside the allowed directory
        outside_dir = tmp_path.parent
        outside_file = outside_dir / "outside.png"
        outside_file.write_text("outside")

        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        # Try to access file outside allowed directory using ../
        traversal_path = allowed_dir / ".." / "outside.png"

        with pytest.raises(ValueError, match="not in allowed directories"):
            validate_file_path(str(traversal_path), [allowed_dir])

    def test_validate_file_path_blocks_absolute_path(self, tmp_path):
        """Test that absolute paths outside allowed dirs are blocked"""
        # Create file outside allowed directory
        outside_file = Path("/tmp/test_outside.png")
        try:
            outside_file.write_text("test")

            allowed_dir = tmp_path / "allowed"
            allowed_dir.mkdir()

            with pytest.raises(
                ValueError, match="not in allowed directories"
            ):
                validate_file_path("/tmp/test_outside.png", [allowed_dir])
        finally:
            if outside_file.exists():
                outside_file.unlink()

    def test_validate_file_path_blocks_nonexistent_file(self, tmp_path):
        """Test that non-existent files are rejected"""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        with pytest.raises(ValueError, match="not a file or does not exist"):
            validate_file_path(
                str(allowed_dir / "nonexistent.png"), [allowed_dir]
            )

    def test_validate_file_path_blocks_directory(self, tmp_path):
        """Test that directories are rejected (only files allowed)"""
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()

        with pytest.raises(ValueError, match="not a file or does not exist"):
            validate_file_path(str(allowed_dir), [tmp_path])

    def test_validate_file_path_follows_symlinks_safely(self, tmp_path):
        """Test that symlinks are resolved and validated"""
        # Create a file inside allowed directory
        allowed_dir = tmp_path / "allowed"
        allowed_dir.mkdir()
        real_file = allowed_dir / "real.png"
        real_file.write_text("test")

        # Create symlink to it
        link_file = allowed_dir / "link.png"
        link_file.symlink_to(real_file)

        # Should work - symlink points to file in allowed dir
        result = validate_file_path(str(link_file), [allowed_dir])
        assert result == real_file.resolve()


class TestSSRFPrevention:
    """Test SSRF (Server-Side Request Forgery) prevention"""

    def test_validate_url_allows_https(self):
        """Test that valid HTTPS URLs are allowed"""
        # Use a public domain that resolves to non-private IP
        with patch("socket.gethostbyname", return_value="8.8.8.8"):
            result = validate_url("https://example.com/image.png")
            assert result == "https://example.com/image.png"

    def test_validate_url_allows_http(self):
        """Test that valid HTTP URLs are allowed"""
        with patch("socket.gethostbyname", return_value="1.1.1.1"):
            result = validate_url("http://example.com/image.png")
            assert result == "http://example.com/image.png"

    def test_validate_url_blocks_localhost(self):
        """Test that localhost/127.0.0.1 is blocked"""
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            with pytest.raises(ValueError, match="blocked IP range"):
                validate_url("http://localhost/admin")

    def test_validate_url_blocks_private_10(self):
        """Test that 10.0.0.0/8 private range is blocked"""
        with patch("socket.gethostbyname", return_value="10.0.0.1"):
            with pytest.raises(ValueError, match="blocked IP range"):
                validate_url("http://internal.server/api")

    def test_validate_url_blocks_private_172(self):
        """Test that 172.16.0.0/12 private range is blocked"""
        with patch("socket.gethostbyname", return_value="172.16.0.1"):
            with pytest.raises(ValueError, match="blocked IP range"):
                validate_url("http://172.16.0.1/data")

    def test_validate_url_blocks_private_192(self):
        """Test that 192.168.0.0/16 private range is blocked"""
        with patch("socket.gethostbyname", return_value="192.168.1.1"):
            with pytest.raises(ValueError, match="blocked IP range"):
                validate_url("http://192.168.1.1/router")

    def test_validate_url_blocks_aws_metadata(self):
        """Test that AWS metadata endpoint is blocked"""
        with patch("socket.gethostbyname", return_value="169.254.169.254"):
            with pytest.raises(ValueError, match="blocked IP range"):
                validate_url("http://169.254.169.254/latest/meta-data/")

    def test_validate_url_blocks_ipv6_loopback(self):
        """Test that IPv6 loopback is blocked"""
        with patch("socket.gethostbyname", return_value="::1"):
            with pytest.raises(ValueError, match="blocked IP range"):
                validate_url("http://[::1]/admin")

    def test_validate_url_blocks_ftp(self):
        """Test that non-HTTP schemes are blocked"""
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_url("ftp://example.com/file.txt")

    def test_validate_url_blocks_file_scheme(self):
        """Test that file:// scheme is blocked"""
        with pytest.raises(ValueError, match="Invalid URL scheme"):
            validate_url("file:///etc/passwd")

    def test_validate_url_blocks_no_hostname(self):
        """Test that URLs without hostname are blocked"""
        with pytest.raises(ValueError, match="must have a hostname"):
            validate_url("http:///path")

    def test_validate_url_blocks_unresolvable_hostname(self):
        """Test that URLs with unresolvable hostnames are blocked"""
        with patch(
            "socket.gethostbyname", side_effect=socket.gaierror("Not found")
        ):
            with pytest.raises(ValueError, match="Cannot resolve hostname"):
                validate_url("http://this-domain-does-not-exist-xyz123.com/")


class TestBlockedIPRanges:
    """Test that all expected IP ranges are blocked"""

    def test_blocked_ranges_complete(self):
        """Test that all necessary ranges are in BLOCKED_IP_RANGES"""
        expected_ranges = [
            "127.0.0.0/8",  # Loopback
            "10.0.0.0/8",  # Private
            "172.16.0.0/12",  # Private
            "192.168.0.0/16",  # Private
            "169.254.0.0/16",  # Link-local
            "::1/128",  # IPv6 loopback
            "fc00::/7",  # IPv6 private
            "fe80::/10",  # IPv6 link-local
        ]

        blocked_range_strs = [
            str(net) for net in BLOCKED_IP_RANGES
        ]

        for expected in expected_ranges:
            assert (
                expected in blocked_range_strs
            ), f"Missing blocked range: {expected}"

    def test_specific_ips_are_blocked(self):
        """Test that specific dangerous IPs are in blocked ranges"""
        dangerous_ips = [
            "127.0.0.1",  # Localhost
            "127.0.0.2",  # Also localhost
            "10.0.0.1",  # Private
            "10.255.255.255",  # Private
            "172.16.0.1",  # Private
            "172.31.255.255",  # Private
            "192.168.0.1",  # Private
            "192.168.255.255",  # Private
            "169.254.169.254",  # AWS metadata
        ]

        for ip_str in dangerous_ips:
            ip = ipaddress.ip_address(ip_str)
            is_blocked = any(
                ip in blocked_range for blocked_range in BLOCKED_IP_RANGES
            )
            assert is_blocked, f"IP {ip_str} should be blocked but isn't"


class TestOpenImageSecurity:
    """Test that open_image enforces security"""

    def test_open_image_blocks_path_traversal(self, tmp_path):
        """Test that open_image blocks directory traversal"""
        # Mock get_allowed_image_dirs to return our test directory
        with patch(
            "ledfx.utils.get_allowed_image_dirs", return_value=[tmp_path]
        ):
            # Try to traverse up
            result = open_image("../../etc/passwd")
            # Should return None due to validation failure
            assert result is None

    def test_open_image_blocks_ssrf(self):
        """Test that open_image blocks SSRF attempts"""
        # Try to access localhost
        with patch("socket.gethostbyname", return_value="127.0.0.1"):
            result = open_image("http://localhost/admin")
            # Should return None due to validation failure
            assert result is None


class TestOpenGifSecurity:
    """Test that open_gif enforces security"""

    def test_open_gif_blocks_path_traversal(self, tmp_path):
        """Test that open_gif blocks directory traversal"""
        with patch(
            "ledfx.utils.get_allowed_image_dirs", return_value=[tmp_path]
        ):
            result = open_gif("../../../etc/passwd")
            # Should return None due to validation failure
            assert result is None

    def test_open_gif_blocks_ssrf(self):
        """Test that open_gif blocks SSRF attempts"""
        with patch("socket.gethostbyname", return_value="192.168.1.1"):
            result = open_gif("http://192.168.1.1/router")
            # Should return None due to validation failure
            assert result is None


class TestAllowedDirectories:
    """Test allowed directory configuration"""

    def test_get_allowed_image_dirs_creates_config_dir(self, tmp_path):
        """Test that config images directory is created if it doesn't exist"""
        with patch(
            "ledfx.utils.get_default_config_directory",
            return_value=str(tmp_path),
        ):
            allowed_dirs = get_allowed_image_dirs()

            # Should create images subdirectory
            images_dir = tmp_path / "images"
            assert images_dir.exists()
            assert images_dir.is_dir()
            assert images_dir in allowed_dirs
