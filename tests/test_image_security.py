"""
Test cases for image security validation features.

Tests file type validation (extension, MIME type, PIL format) and size limits.
"""

import io
import os
from unittest.mock import MagicMock, patch

from PIL import Image

# Import validation functions
from ledfx.utils import (
    init_image_cache,
    is_allowed_image_extension,
    open_gif,
    open_image,
    validate_image_mime_type,
    validate_pil_image,
)


class TestFileExtensionValidation:
    """Test file extension allowlist validation."""

    def test_valid_extensions(self):
        """Test that allowed extensions pass validation."""
        valid_files = [
            "image.gif",
            "photo.png",
            "picture.jpg",
            "graphic.jpeg",
            "animation.webp",
            "bitmap.bmp",
            "document.tiff",
            "icon.ico",
        ]
        for filename in valid_files:
            assert is_allowed_image_extension(
                filename
            ), f"{filename} should be allowed"

    def test_invalid_extensions(self):
        """Test that disallowed extensions fail validation."""
        invalid_files = [
            "file.txt",
            "document.pdf",
            "script.py",
            "config.json",
            "data.xml",
            "executable.exe",
            "archive.zip",
            "video.mp4",
        ]
        for filename in invalid_files:
            assert not is_allowed_image_extension(
                filename
            ), f"{filename} should be rejected"

    def test_case_insensitive(self):
        """Test that extension checking is case-insensitive."""
        assert is_allowed_image_extension("image.GIF")
        assert is_allowed_image_extension("photo.PNG")
        assert is_allowed_image_extension("picture.JPG")

    def test_no_extension(self):
        """Test that files without extension are rejected."""
        assert not is_allowed_image_extension("filename")
        assert not is_allowed_image_extension("path/to/filename")


class TestMimeTypeValidation:
    """Test MIME type validation."""

    def test_valid_png(self, tmp_path):
        """Test valid PNG file passes MIME validation."""
        # Create a small valid PNG
        img = Image.new("RGB", (10, 10), color="red")
        img_path = os.path.join(tmp_path, "test.png")
        img.save(img_path, "PNG")

        assert validate_image_mime_type(str(img_path))

    def test_valid_jpeg(self, tmp_path):
        """Test valid JPEG file passes MIME validation."""
        img = Image.new("RGB", (10, 10), color="blue")
        img_path = os.path.join(tmp_path, "test.jpg")
        img.save(img_path, "JPEG")

        assert validate_image_mime_type(str(img_path))

    def test_invalid_text_file(self, tmp_path):
        """Test that text file fails MIME validation."""
        txt_path = os.path.join(tmp_path, "test.txt")
        with open(txt_path, "w") as f:
            f.write("This is not an image")

        assert not validate_image_mime_type(str(txt_path))

    def test_spoofed_extension(self, tmp_path):
        """Test that text file with .png extension fails MIME validation."""
        fake_png = os.path.join(tmp_path, "fake.png")
        with open(fake_png, "w") as f:
            f.write("This is actually text")

        assert not validate_image_mime_type(str(fake_png))


class TestPilImageValidation:
    """Test PIL image format and dimension validation."""

    def test_valid_formats(self):
        """Test that allowed PIL formats pass validation."""
        valid_formats = ["PNG", "JPEG", "GIF", "WEBP", "BMP"]
        for fmt in valid_formats:
            img = Image.new("RGB", (100, 100))
            img.format = fmt
            assert validate_pil_image(img), f"{fmt} should be allowed"

    def test_invalid_format(self):
        """Test that unsupported PIL format fails validation."""
        img = Image.new("RGB", (100, 100))
        img.format = "INVALID"
        assert not validate_pil_image(img)

    def test_dimensions_within_limits(self):
        """Test that images within dimension limits pass."""
        img = Image.new("RGB", (4096, 4096))
        img.format = "PNG"
        assert validate_pil_image(img)

    def test_dimensions_exceed_limits(self):
        """Test that oversized images fail validation."""
        img = Image.new("RGB", (5000, 5000))
        img.format = "PNG"
        assert not validate_pil_image(img)

    def test_decompression_bomb_protection(self):
        """Test protection against decompression bombs."""
        # Image with pixel count exceeding limit
        img = Image.new("RGB", (4097, 4097))  # Just over 4096*4096
        img.format = "PNG"
        assert not validate_pil_image(img)


class TestFileSizeLimits:
    """Test file size limit enforcement."""

    @patch("urllib.request.urlopen")
    def test_remote_content_length_too_large(self, mock_urlopen):
        """Test that remote images with large Content-Length are rejected."""
        mock_response = MagicMock()
        mock_response.headers.get.return_value = str(
            11 * 1024 * 1024
        )  # 11MB > 10MB limit
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = open_image("https://example.com/large.jpg")
        assert result is None

    @patch("urllib.request.urlopen")
    def test_remote_download_exceeds_limit(self, mock_urlopen):
        """Test that remote downloads exceeding 10MB during read are rejected."""
        mock_response = MagicMock()
        mock_response.headers.get.return_value = (
            None  # No Content-Length header
        )
        # Simulate reading more than 10MB
        mock_response.read.return_value = b"x" * (11 * 1024 * 1024)
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        result = open_image("https://example.com/sneaky.jpg")
        assert result is None

    def test_local_file_too_large(self, tmp_path):
        """Test that local files exceeding 10MB are rejected."""
        large_file = os.path.join(tmp_path, "large.png")
        # Create file larger than 10MB
        with open(large_file, "wb") as f:
            f.write(b"x" * (11 * 1024 * 1024))

        result = open_image(str(large_file))
        assert result is None


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

    @patch("ledfx.utils.build_browser_request")
    @patch("urllib.request.urlopen")
    def test_valid_remote_image(self, mock_urlopen, mock_build_request):
        """Test downloading valid remote image."""
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

BAD SCENARIOS (Should Fail):
1. Files with disallowed extensions (.txt, .pdf, .exe, etc.)
2. Text files with spoofed image extensions
3. Files exceeding 10MB size limit
4. Images exceeding 4096x4096 pixel dimensions
5. Remote downloads without Content-Length or exceeding size during read
6. Files with incorrect MIME types
7. Images with unsupported PIL formats
8. Nonexistent files
9. URLs with invalid extensions
10. URLs pointing to loopback addresses (127.0.0.0/8, ::1)
11. URLs pointing to private networks (10/8, 172.16/12, 192.168/16, fc00::/7)
12. URLs pointing to link-local addresses (169.254/16, fe80::/10)
13. URLs pointing to cloud metadata endpoints (169.254.169.254)
14. URLs using non-HTTP/HTTPS protocols in remote requests (validated by validate_url_safety)
15. Hostnames that resolve to blocked IP addresses
16. Non-HTTP/HTTPS URL schemes in local file path handling (file://, ftp://, data:, javascript:, etc.)
"""


class TestPathTraversalNaughtyStrings:
    """Test path traversal protection with naughty strings from big-list-of-naughty-strings."""

    def test_path_traversal_attempts(self, tmp_path):
        """Test that various path traversal attempts are blocked."""
        # Initialize cache to set config_dir for path validation
        init_image_cache(str(tmp_path))

        # Path traversal patterns from big-list-of-naughty-strings
        naughty_paths = [
            # Classic path traversal
            "../etc/passwd",
            "../../etc/passwd",
            "../../../etc/passwd",
            "../../../../etc/passwd",
            # With image extension
            "../../../etc/passwd.png",
            "../../etc/shadow.jpg",
            # Windows path traversal
            "..\\..\\..\\Windows\\System32\\config\\SAM",
            "..\\..\\..\\Windows\\System32\\config\\SAM.png",
            # Encoded path traversal
            "%2e%2e%2f%2e%2e%2f%2e%2e%2fetc%2fpasswd",
            "..%2F..%2F..%2Fetc%2Fpasswd",
            # Double encoded
            "%252e%252e%252f%252e%252e%252f%252e%252e%252fetc%252fpasswd",
            # Unicode encoding
            "..%c0%af..%c0%af..%c0%afetc%c0%afpasswd",
            # Various separators
            "....//....//....//etc/passwd",
            "..../..../..../etc/passwd",
            # Null byte injection
            "../../../etc/passwd%00.png",
            "../../../etc/passwd\x00.png",
            # Absolute paths (should be outside allowed dirs)
            "/etc/passwd.png",
            "/etc/shadow.jpg",
            "C:\\Windows\\System32\\config\\SAM.png",
            "/root/.ssh/id_rsa.png",
            # Mixed separators
            "..\\../..\\../etc/passwd",
            "../\\../\\../etc/passwd",
            # Overlong paths
            "." * 1000 + "/etc/passwd.png",
            # Special characters
            "../etc/passwd\n.png",
            "../etc/passwd\r\n.png",
            "../etc/passwd\t.png",
        ]

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
        # URL injection patterns from big-list-of-naughty-strings
        naughty_urls = [
            # Protocol injection
            "http://example.com@127.0.0.1/image.png",
            "http://127.0.0.1@example.com/image.png",
            "http://127.0.0.1%2f@example.com/image.png",
            # Port manipulation
            "http://127.0.0.1:80/image.png",
            "http://127.0.0.1:8080/image.png",
            "http://localhost:80/image.png",
            # IPv6 variants
            "http://[::1]:80/image.png",
            "http://[0:0:0:0:0:0:0:1]/image.png",
            "http://[::ffff:127.0.0.1]/image.png",
            # URL encoding tricks
            "http://127.0.0.1%09/image.png",
            "http://127.0.0.1%0a/image.png",
            "http://127.0.0.1%0d/image.png",
            # Octal representation
            "http://0177.0.0.1/image.png",
            "http://0x7f.0.0.1/image.png",
            # Integer representation
            "http://2130706433/image.png",  # 127.0.0.1 as integer
            # Localhost variations
            "http://localhost/image.png",
            "http://LOCALHOST/image.png",
            "http://127.1/image.png",
        ]

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

        # Special filenames from big-list-of-naughty-strings
        naughty_filenames = [
            # Reserved names on Windows
            "CON.png",
            "PRN.jpg",
            "AUX.gif",
            "NUL.png",
            "COM1.jpg",
            "LPT1.png",
            # NTFS alternate data streams
            "test.png::$DATA",
            "image.jpg:hidden.txt",
            # Long filenames
            "A" * 300 + ".png",
            # Control characters
            "test\x00.png",
            "test\x01\x02\x03.png",
            # Unicode homoglyphs
            "іmage.png",  # Cyrillic і instead of latin i
            "imаge.png",  # Cyrillic а instead of latin a
        ]

        for naughty_filename in naughty_filenames:
            # Create path (most will fail at file system level anyway)
            test_path = os.path.join(tmp_path, naughty_filename)
            result = open_image(test_path)
            # Should fail either due to validation or file not existing
            assert (
                result is None
            ), f"Special filename should be rejected or fail: {naughty_filename}"
