"""
Test cases for image security validation features.

Tests file type validation (extension, MIME type, PIL format) and size limits.
"""

import io
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
        img_path = tmp_path / "test.png"
        img.save(img_path, "PNG")

        assert validate_image_mime_type(str(img_path))

    def test_valid_jpeg(self, tmp_path):
        """Test valid JPEG file passes MIME validation."""
        img = Image.new("RGB", (10, 10), color="blue")
        img_path = tmp_path / "test.jpg"
        img.save(img_path, "JPEG")

        assert validate_image_mime_type(str(img_path))

    def test_invalid_text_file(self, tmp_path):
        """Test that text file fails MIME validation."""
        txt_path = tmp_path / "test.txt"
        txt_path.write_text("This is not an image")

        assert not validate_image_mime_type(str(txt_path))

    def test_spoofed_extension(self, tmp_path):
        """Test that text file with .png extension fails MIME validation."""
        fake_png = tmp_path / "fake.png"
        fake_png.write_text("This is actually text")

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
        large_file = tmp_path / "large.png"
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
        img_path = tmp_path / "test.png"
        img.save(img_path, "PNG")

        result = open_image(str(img_path))
        assert result is not None
        assert isinstance(result, Image.Image)

    def test_invalid_extension_rejected(self, tmp_path):
        """Test that file with invalid extension is rejected."""
        # Initialize cache to set config_dir for path validation
        init_image_cache(str(tmp_path))
        
        txt_file = tmp_path / "file.txt"
        txt_file.write_text("not an image")

        result = open_image(str(txt_file))
        assert result is None

    def test_nonexistent_file(self, tmp_path):
        """Test that nonexistent file returns None."""
        # Initialize cache to set config_dir for path validation
        init_image_cache(str(tmp_path))
        
        result = open_image(str(tmp_path / "nonexistent.png"))
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
        gif_path = tmp_path / "test.gif"
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
        png_path = tmp_path / "single.png"
        img.save(png_path, "PNG")

        result = open_gif(str(png_path))
        assert result is not None
        assert hasattr(result, "n_frames")
        assert result.n_frames == 1


# Test Scenarios Documentation
"""
GOOD SCENARIOS (Should Pass):
1. Valid PNG/JPEG/GIF/WEBP/BMP files with correct extensions
2. Files under 10MB in size
3. Images with dimensions <= 4096x4096 pixels
4. Remote URLs with correct Content-Length headers
5. Files with correct MIME types matching their content

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
"""
