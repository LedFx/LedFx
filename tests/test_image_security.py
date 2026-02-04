"""
Test cases for image security validation features.

Tests file type validation (extension, MIME type, PIL format) and size limits.
"""

import io
import os
from unittest.mock import MagicMock, patch

from PIL import Image

from ledfx.utilities.security_utils import is_allowed_image_extension
from ledfx.utils import init_image_cache, open_gif, open_image
from tests.test_utilities.naughty_strings import (
    naughty_filenames,
    naughty_paths,
    naughty_urls,
)


class TestIntegrationOpenImage:
    """Integration tests for open_image function."""

    def test_valid_local_png(self, tmp_path):
        """Test opening valid local PNG file."""
        # Initialize cache to set config_dir for path validation
        init_image_cache(str(tmp_path))

        img = Image.new("RGB", (100, 100), color="green")
        img_path = os.path.join(tmp_path, "test.png")
        img.save(img_path, "PNG")

        result = open_image(str(img_path))
        assert result is not None
        assert isinstance(result, Image.Image)

    def test_invalid_extension_rejected(self, tmp_path):
        """Test that file with invalid extension is rejected."""
        # Initialize cache to set config_dir for path validation
        init_image_cache(str(tmp_path))

        txt_file = os.path.join(tmp_path, "file.txt")
        with open(txt_file, "w") as f:
            f.write("not an image")

        result = open_image(str(txt_file))
        assert result is None

    def test_nonexistent_file(self, tmp_path):
        """Test that nonexistent file returns None."""
        # Initialize cache to set config_dir for path validation
        init_image_cache(str(tmp_path))

        result = open_image(os.path.join(tmp_path, "nonexistent.png"))
        assert result is None

    @patch("ledfx.utils.validate_url_safety")
    @patch("ledfx.utils.build_browser_request")
    @patch("urllib.request.urlopen")
    def test_valid_remote_image(
        self, mock_urlopen, mock_build_request, mock_validate_url
    ):
        """Test downloading valid remote image."""
        # Mock URL validation to pass
        mock_validate_url.return_value = (True, None)

        # Create a small valid PNG in memory
        img = Image.new("RGB", (10, 10), color="red")
        img_bytes = io.BytesIO()
        img.save(img_bytes, "PNG")
        img_data = img_bytes.getvalue()

        # Mock the browser request builder
        mock_build_request.return_value = MagicMock()

        mock_response = MagicMock()
        # Fix headers.get to accept default parameter
        headers_dict = {
            "Content-Length": str(len(img_data)),
            "ETag": "abc123",
            "Last-Modified": "Mon, 01 Jan 2024 00:00:00 GMT",
            "Content-Type": "image/png",
        }
        mock_response.headers.get = lambda key, default=None: headers_dict.get(
            key, default
        )
        mock_response.read.return_value = img_data
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_urlopen.return_value = mock_response

        result = open_image("https://example.com/test.png")
        assert result is not None
        assert isinstance(result, Image.Image)

    def test_invalid_url_extension_rejected(self):
        """Test that URL with invalid extension is rejected."""
        result = open_image("https://example.com/file.txt")
        assert result is None

    @patch("ledfx.utils.validate_url_safety")
    @patch("ledfx.utils.build_browser_request")
    @patch("urllib.request.urlopen")
    def test_extensionless_remote_url_success(
        self, mock_urlopen, mock_build_request, mock_validate_url
    ):
        """Test that remote URLs without extensions work (relies on Content-Type header)."""
        # Mock URL validation to pass
        mock_validate_url.return_value = (True, None)

        # Create a small valid PNG in memory
        img = Image.new("RGB", (10, 10), color="blue")
        img_bytes = io.BytesIO()
        img.save(img_bytes, "PNG")
        img_data = img_bytes.getvalue()

        # Mock the browser request builder
        mock_build_request.return_value = MagicMock()

        mock_response = MagicMock()
        headers_dict = {
            "Content-Length": str(len(img_data)),
            "ETag": "xyz789",
            "Last-Modified": "Tue, 02 Jan 2024 00:00:00 GMT",
            "Content-Type": "image/png",
        }
        mock_response.headers.get = lambda key, default=None: headers_dict.get(
            key, default
        )
        mock_response.read.return_value = img_data
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_urlopen.return_value = mock_response

        # Test with CDN-style URL without extension (validated via Content-Type header)
        result = open_image("https://cdn.example.com/image/abc123def456")
        assert result is not None
        assert isinstance(result, Image.Image)


class TestIntegrationOpenGif:
    """Integration tests for open_gif function."""

    def test_valid_local_gif(self, tmp_path):
        """Test opening valid local GIF file."""
        # Initialize cache to set config_dir for path validation
        init_image_cache(str(tmp_path))

        img = Image.new("RGB", (50, 50), color="blue")
        gif_path = os.path.join(tmp_path, "test.gif")
        img.save(gif_path, "GIF")

        result = open_gif(str(gif_path))
        assert result is not None
        assert isinstance(result, Image.Image)
        assert hasattr(result, "n_frames")

    def test_single_frame_image_gets_n_frames(self, tmp_path):
        """Test that single-frame images get n_frames attribute."""
        # Initialize cache to set config_dir for path validation
        init_image_cache(str(tmp_path))

        img = Image.new("RGB", (50, 50), color="yellow")
        png_path = os.path.join(tmp_path, "single.png")
        img.save(png_path, "PNG")

        result = open_gif(str(png_path))
        assert result is not None
        assert hasattr(result, "n_frames")
        assert result.n_frames == 1

    @patch("ledfx.utils.validate_url_safety")
    @patch("ledfx.utils.build_browser_request")
    @patch("urllib.request.urlopen")
    def test_extensionless_remote_gif_url_success(
        self, mock_urlopen, mock_build_request, mock_validate_url
    ):
        """Test that remote GIF URLs without extensions work."""
        # Mock URL validation to pass
        mock_validate_url.return_value = (True, None)

        # Create a small valid GIF in memory
        img = Image.new("RGB", (10, 10), color="green")
        img_bytes = io.BytesIO()
        img.save(img_bytes, "GIF")
        img_data = img_bytes.getvalue()

        # Mock the browser request builder
        mock_build_request.return_value = MagicMock()

        mock_response = MagicMock()
        headers_dict = {
            "Content-Length": str(len(img_data)),
            "ETag": "gif123",
            "Last-Modified": "Wed, 03 Jan 2024 00:00:00 GMT",
            "Content-Type": "image/gif",
        }
        mock_response.headers.get = lambda key, default=None: headers_dict.get(
            key, default
        )
        mock_response.read.return_value = img_data
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_urlopen.return_value = mock_response

        # Test with extension-less URL
        result = open_gif("https://example.com/api/animation")
        assert result is not None
        assert isinstance(result, Image.Image)
        assert hasattr(result, "n_frames")
        assert result.n_frames == 1


class TestSSRFProtection:
    """Test SSRF (Server-Side Request Forgery) protection for URL validation."""

    def test_loopback_ipv4_blocked(self):
        """Test that loopback addresses are blocked."""
        from ledfx.utils import validate_url_safety

        # Test various loopback addresses
        blocked_urls = [
            "http://127.0.0.1/image.jpg",
            "http://127.1.2.3/image.png",
            "http://127.255.255.255/image.gif",
        ]
        for url in blocked_urls:
            is_safe, error_msg = validate_url_safety(url)
            assert not is_safe, f"{url} should be blocked"
            assert "blocked ip" in error_msg.lower()

    def test_private_networks_blocked(self):
        """Test that private network addresses are blocked."""
        from ledfx.utils import validate_url_safety

        blocked_urls = [
            "http://10.0.0.1/image.jpg",
            "http://10.255.255.255/image.png",
            "http://172.16.0.1/image.gif",
            "http://172.31.255.255/image.jpg",
            "http://192.168.1.1/image.png",
            "http://192.168.255.255/image.gif",
        ]
        for url in blocked_urls:
            is_safe, error_msg = validate_url_safety(url)
            assert not is_safe, f"{url} should be blocked"
            assert "blocked ip" in error_msg.lower()

    def test_link_local_blocked(self):
        """Test that link-local addresses are blocked."""
        from ledfx.utils import validate_url_safety

        blocked_urls = [
            "http://169.254.0.1/image.jpg",
            "http://169.254.169.254/image.png",  # AWS metadata
            "http://169.254.170.2/image.gif",  # ECS metadata
        ]
        for url in blocked_urls:
            is_safe, error_msg = validate_url_safety(url)
            assert not is_safe, f"{url} should be blocked"

    def test_metadata_endpoints_blocked(self):
        """Test that cloud metadata endpoints are blocked by hostname."""
        from ledfx.utils import validate_url_safety

        # Direct IP check
        is_safe, error_msg = validate_url_safety(
            "http://169.254.169.254/latest/meta-data/"
        )
        assert not is_safe
        assert "blocked" in error_msg.lower()

    def test_ipv6_loopback_blocked(self):
        """Test that IPv6 loopback is blocked."""
        from ledfx.utils import validate_url_safety

        blocked_urls = [
            "http://[::1]/image.jpg",
            "http://[0:0:0:0:0:0:0:1]/image.png",
        ]
        for url in blocked_urls:
            is_safe, error_msg = validate_url_safety(url)
            assert not is_safe, f"{url} should be blocked"

    def test_ipv6_private_blocked(self):
        """Test that IPv6 private addresses are blocked."""
        from ledfx.utils import validate_url_safety

        blocked_urls = [
            "http://[fc00::1]/image.jpg",
            "http://[fd00::1]/image.png",
            "http://[fe80::1]/image.gif",  # Link-local
        ]
        for url in blocked_urls:
            is_safe, error_msg = validate_url_safety(url)
            assert not is_safe, f"{url} should be blocked"

    def test_invalid_protocols_blocked(self):
        """Test that non-HTTP/HTTPS protocols are blocked."""
        from ledfx.utils import validate_url_safety

        blocked_urls = [
            "file:///etc/passwd",
            "ftp://example.com/image.jpg",
            "gopher://example.com/image.png",
            "data:image/png;base64,abc123",
        ]
        for url in blocked_urls:
            is_safe, error_msg = validate_url_safety(url)
            assert not is_safe, f"{url} should be blocked"
            assert "not allowed" in error_msg.lower()

    @patch("socket.getaddrinfo")
    def test_dns_rebinding_protection(self, mock_getaddrinfo):
        """Test that hostnames resolving to blocked IPs are rejected."""
        from ledfx.utils import validate_url_safety

        # Mock DNS resolution to return a private IP
        mock_getaddrinfo.return_value = [
            (
                2,
                1,
                6,
                "",
                ("192.168.1.1", 80),
            )  # AF_INET, SOCK_STREAM, private IP
        ]

        is_safe, error_msg = validate_url_safety(
            "http://evil.example.com/image.jpg"
        )
        assert not is_safe
        assert "blocked ip" in error_msg.lower()
        assert "192.168.1.1" in error_msg

    @patch("socket.getaddrinfo")
    def test_valid_public_url_allowed(self, mock_getaddrinfo):
        """Test that valid public URLs are allowed."""
        from ledfx.utils import validate_url_safety

        # Mock DNS resolution to return a public IP
        mock_getaddrinfo.return_value = [
            (2, 1, 6, "", ("93.184.216.34", 80))  # example.com IP
        ]

        is_safe, error_msg = validate_url_safety(
            "http://example.com/image.jpg"
        )
        assert is_safe
        assert error_msg == ""

    def test_open_image_blocks_ssrf(self):
        """Test that open_image rejects SSRF attempts."""
        # Test with loopback address
        result = open_image("http://127.0.0.1/image.jpg")
        assert result is None

        # Test with private network
        result = open_image("http://192.168.1.1/image.png")
        assert result is None

        # Test with metadata endpoint
        result = open_image("http://169.254.169.254/image.gif")
        assert result is None

    def test_open_gif_blocks_ssrf(self):
        """Test that open_gif rejects SSRF attempts."""
        # Test with loopback address
        result = open_gif("http://127.0.0.1/animation.gif")
        assert result is None

        # Test with private network
        result = open_gif("http://10.0.0.1/animation.gif")
        assert result is None


class TestLocalFileSchemeValidation:
    """Test that non-HTTP/HTTPS URL schemes are rejected for local file paths."""

    def test_file_scheme_rejected_in_open_image(self):
        """Test that file:// URLs are rejected."""
        result = open_image("file:///etc/passwd")
        assert result is None

        result = open_image("file:///C:/Windows/System32/config/SAM")
        assert result is None

    def test_file_scheme_rejected_in_open_gif(self):
        """Test that file:// URLs are rejected."""
        result = open_gif("file:///etc/passwd")
        assert result is None

    def test_ftp_scheme_rejected_in_open_image(self):
        """Test that ftp:// URLs are rejected."""
        result = open_image("ftp://example.com/image.jpg")
        assert result is None

    def test_ftp_scheme_rejected_in_open_gif(self):
        """Test that ftp:// URLs are rejected."""
        result = open_gif("ftp://example.com/image.gif")
        assert result is None

    def test_data_uri_rejected_in_open_image(self):
        """Test that data: URIs are rejected."""
        result = open_image(
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
        )
        assert result is None

    def test_javascript_scheme_rejected(self):
        """Test that javascript: URLs are rejected."""
        result = open_image("javascript:alert('xss')")
        assert result is None

        result = open_gif("javascript:void(0)")
        assert result is None

    def test_other_schemes_rejected(self):
        """Test that various other URL schemes are rejected."""
        schemes = ["gopher", "telnet", "ssh", "sftp", "smb", "ldap"]
        for scheme in schemes:
            result = open_image(f"{scheme}://example.com/image.jpg")
            assert result is None, f"{scheme}:// should be rejected"

            result = open_gif(f"{scheme}://example.com/image.gif")
            assert result is None, f"{scheme}:// should be rejected"


class TestURLParsing:
    """Test URL parsing for extension validation with query strings and fragments."""

    def test_url_with_query_string(self):
        """Test that URLs with query strings are handled correctly."""
        assert is_allowed_image_extension(
            "https://example.com/image.jpg?size=large&quality=high"
        )
        assert is_allowed_image_extension(
            "https://example.com/photo.png?token=abc123"
        )

    def test_url_with_fragment(self):
        """Test that URLs with fragments are handled correctly."""
        assert is_allowed_image_extension(
            "https://example.com/image.gif#section"
        )
        assert is_allowed_image_extension("https://example.com/photo.webp#top")

    def test_url_with_query_and_fragment(self):
        """Test that URLs with both query strings and fragments work."""
        assert is_allowed_image_extension(
            "https://example.com/image.png?v=2#preview"
        )

    def test_url_with_invalid_extension_and_query(self):
        """Test that invalid extensions are still caught with query strings."""
        assert not is_allowed_image_extension(
            "https://example.com/file.txt?type=image"
        )
        assert not is_allowed_image_extension(
            "https://example.com/script.py?download=true"
        )


class TestExtensionlessRemoteURLs:
    """Test that remote URLs without file extensions are allowed (validated via Content-Type header)."""

    def test_http_url_no_extension_allowed(self):
        """Test that HTTP URLs without extension are allowed."""
        assert is_allowed_image_extension("http://example.com/image")
        assert is_allowed_image_extension("http://cdn.example.com/abc123")

    def test_https_url_no_extension_allowed(self):
        """Test that HTTPS URLs without extension are allowed."""
        assert is_allowed_image_extension("https://example.com/image")
        assert is_allowed_image_extension("https://cdn.example.com/image/abc123")

    def test_cdn_urls_without_extension_allowed(self):
        """Test that CDN URLs without extensions are allowed (content validated via HTTP headers)."""
        # CDN-style hash-based URLs without extensions
        assert is_allowed_image_extension(
            "https://cdn.example.com/image/ab67616d0000b273a1b2c3d4e5f6a7b8c9d0e1f2"
        )
        # With query parameters
        assert is_allowed_image_extension(
            "https://images.example/content/ab67616d0000b273?size=large"
        )

    def test_remote_url_with_path_no_extension(self):
        """Test remote URLs with paths but no extension."""
        assert is_allowed_image_extension("https://example.com/api/v1/image")
        assert is_allowed_image_extension(
            "https://example.com/user/123/profile"
        )

    def test_remote_url_no_extension_with_query(self):
        """Test remote URL without extension but with query string."""
        assert is_allowed_image_extension(
            "https://example.com/image?id=123&size=large"
        )

    def test_remote_url_no_extension_with_fragment(self):
        """Test remote URL without extension but with fragment."""
        assert is_allowed_image_extension("https://example.com/image#preview")

    def test_local_file_no_extension_rejected(self):
        """Test that local files without extension are still rejected."""
        assert not is_allowed_image_extension("/path/to/file")
        assert not is_allowed_image_extension("./relative/file")
        assert not is_allowed_image_extension("filename")

    def test_local_file_invalid_extension_rejected(self):
        """Test that local files with invalid extensions are rejected."""
        assert not is_allowed_image_extension("/path/to/file.txt")
        assert not is_allowed_image_extension("./relative/file.pdf")

    def test_remote_url_with_valid_extension_still_works(self):
        """Test that remote URLs with valid extensions still work."""
        assert is_allowed_image_extension("https://example.com/image.png")
        assert is_allowed_image_extension("https://example.com/photo.jpg")
        assert is_allowed_image_extension("https://example.com/anim.gif")

    def test_remote_url_with_invalid_extension_rejected(self):
        """Test that remote URLs with explicitly invalid extensions are rejected."""
        assert not is_allowed_image_extension("https://example.com/file.txt")
        assert not is_allowed_image_extension("https://example.com/doc.pdf")
        assert not is_allowed_image_extension("https://example.com/script.py")


# Test Scenarios Documentation
"""
GOOD SCENARIOS (Should Pass):
1. Valid PNG/JPEG/GIF/WEBP/BMP files with correct extensions
2. Files under 10MB in size
3. Images with dimensions <= 4096x4096 pixels
4. Remote URLs with correct Content-Length headers
5. Files with correct MIME types matching their content
6. URLs pointing to public IP addresses
7. URLs with query strings and fragments
8. Remote URLs (http/https) without file extensions (validated via Content-Type header)

BAD SCENARIOS (Should Fail):
1. Files with disallowed extensions (.txt, .pdf, .exe, etc.)
2. Text files with spoofed image extensions
3. Files exceeding 10MB size limit
4. Images exceeding 4096x4096 pixel dimensions
5. Remote downloads without Content-Length or exceeding size during read
6. Files with incorrect MIME types
7. Images with unsupported PIL formats
8. Nonexistent files
9. Remote URLs with explicitly invalid extensions (.txt, .pdf, etc.)
10. Local files without extensions or with invalid extensions
11. URLs pointing to loopback addresses (127.0.0.0/8, ::1)
12. URLs pointing to private networks (10/8, 172.16/12, 192.168/16, fc00::/7)
13. URLs pointing to link-local addresses (169.254/16, fe80::/10)
14. URLs pointing to cloud metadata endpoints (169.254.169.254)
15. URLs using non-HTTP/HTTPS protocols in remote requests (validated by validate_url_safety)
16. Hostnames that resolve to blocked IP addresses
17. Non-HTTP/HTTPS URL schemes in local file path handling (file://, ftp://, data:, javascript:, etc.)
"""


class TestPathTraversalNaughtyStrings:
    """Test path traversal protection with naughty strings from big-list-of-naughty-strings."""

    def test_path_traversal_attempts(self, tmp_path):
        """Test that various path traversal attempts are blocked."""
        # Initialize cache to set config_dir for path validation
        init_image_cache(str(tmp_path))

        # Use shared path traversal patterns

        for naughty_path in naughty_paths:
            result = open_image(naughty_path)
            assert (
                result is None
            ), f"Path traversal attempt should fail: {naughty_path}"

            result = open_gif(naughty_path)
            assert (
                result is None
            ), f"Path traversal attempt should fail: {naughty_path}"

    def test_url_injection_attempts(self):
        """Test that URL injection attempts are blocked."""
        # Use shared URL injection patterns
        for naughty_url in naughty_urls:
            result = open_image(naughty_url)
            # Should be blocked by SSRF protection or URL validation
            assert (
                result is None
            ), f"URL injection attempt should fail: {naughty_url}"

            result = open_gif(naughty_url)
            assert (
                result is None
            ), f"URL injection attempt should fail: {naughty_url}"

    def test_special_filename_attacks(self, tmp_path):
        """Test that special filename attacks are blocked."""
        # Initialize cache to set config_dir for path validation
        init_image_cache(str(tmp_path))

        # Use shared special filename patterns
        for naughty_filename in naughty_filenames:
            # Create path (most will fail at file system level anyway)
            test_path = os.path.join(tmp_path, naughty_filename)
            result = open_image(test_path)
            # Should fail either due to validation or file not existing
            assert (
                result is None
            ), f"Special filename should be rejected or fail: {naughty_filename}"
