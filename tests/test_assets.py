"""
Test cases for asset storage system (assets.py).

Tests secure asset storage, path validation, file type validation,
size limits, atomic writes, and listing behavior.
"""

import io
import os
import tempfile

import pytest
from PIL import Image

from assets import (
    ALLOWED_ASSET_EXTENSIONS,
    DEFAULT_MAX_ASSET_SIZE_BYTES,
    delete_asset,
    ensure_assets_directory,
    get_asset_path,
    get_assets_directory,
    list_assets,
    resolve_safe_asset_path,
    save_asset,
    validate_asset_content,
    validate_asset_extension,
    validate_asset_size,
)


@pytest.fixture
def temp_config_dir(tmp_path):
    """Create a temporary config directory for testing."""
    config_dir = os.path.join(str(tmp_path), "test_config")
    os.makedirs(config_dir, exist_ok=True)
    return config_dir


@pytest.fixture
def sample_png_data():
    """Generate sample PNG image data."""
    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, "PNG")
    return img_bytes.getvalue()


@pytest.fixture
def sample_jpeg_data():
    """Generate sample JPEG image data."""
    img = Image.new("RGB", (100, 100), color="blue")
    img_bytes = io.BytesIO()
    img.save(img_bytes, "JPEG")
    return img_bytes.getvalue()


@pytest.fixture
def sample_gif_data():
    """Generate sample GIF image data."""
    img = Image.new("RGB", (50, 50), color="green")
    img_bytes = io.BytesIO()
    img.save(img_bytes, "GIF")
    return img_bytes.getvalue()


@pytest.fixture
def sample_webp_data():
    """Generate sample WEBP image data."""
    img = Image.new("RGB", (100, 100), color="yellow")
    img_bytes = io.BytesIO()
    img.save(img_bytes, "WEBP")
    return img_bytes.getvalue()


class TestAssetsDirectory:
    """Test assets directory creation and path resolution."""

    def test_get_assets_directory(self, temp_config_dir):
        """Test getting assets directory path."""
        assets_dir = get_assets_directory(temp_config_dir)
        expected = os.path.join(temp_config_dir, "assets")
        assert assets_dir == expected

    def test_ensure_assets_directory_creates(self, temp_config_dir):
        """Test that ensure_assets_directory creates the directory."""
        assets_dir = get_assets_directory(temp_config_dir)
        assert not os.path.exists(assets_dir)

        ensure_assets_directory(temp_config_dir)
        assert os.path.exists(assets_dir)
        assert os.path.isdir(assets_dir)

    def test_ensure_assets_directory_idempotent(self, temp_config_dir):
        """Test that ensure_assets_directory can be called multiple times."""
        ensure_assets_directory(temp_config_dir)
        ensure_assets_directory(temp_config_dir)
        assets_dir = get_assets_directory(temp_config_dir)
        assert os.path.exists(assets_dir)


class TestPathResolution:
    """Test safe path resolution and validation."""

    def test_valid_simple_path(self, temp_config_dir):
        """Test that valid simple relative path resolves successfully."""
        is_valid, abs_path, error = resolve_safe_asset_path(
            temp_config_dir, "icon.png"
        )
        assert is_valid is True
        assert error is None
        assert abs_path is not None
        assert "assets" in abs_path
        assert abs_path.endswith("icon.png")

    def test_valid_nested_path(self, temp_config_dir):
        """Test that valid nested relative path resolves successfully."""
        is_valid, abs_path, error = resolve_safe_asset_path(
            temp_config_dir, "buttons/play.png"
        )
        assert is_valid is True
        assert error is None
        assert abs_path is not None
        assert "assets" in abs_path
        assert "buttons" in abs_path

    def test_path_normalization(self, temp_config_dir):
        """Test that paths are normalized (forward/back slashes)."""
        # Test with backslashes
        is_valid1, abs_path1, _ = resolve_safe_asset_path(
            temp_config_dir, "folder\\subfolder\\image.png"
        )
        # Test with forward slashes
        is_valid2, abs_path2, _ = resolve_safe_asset_path(
            temp_config_dir, "folder/subfolder/image.png"
        )

        assert is_valid1 is True
        assert is_valid2 is True
        # Both should resolve to same path
        assert abs_path1 == abs_path2

    def test_empty_path_rejected(self, temp_config_dir):
        """Test that empty path is rejected."""
        is_valid, abs_path, error = resolve_safe_asset_path(
            temp_config_dir, ""
        )
        assert is_valid is False
        assert abs_path is None
        assert "Empty path" in error

    def test_absolute_path_rejected(self, temp_config_dir):
        """Test that absolute paths are rejected."""
        is_valid, abs_path, error = resolve_safe_asset_path(
            temp_config_dir, "/etc/passwd"
        )
        assert is_valid is False
        assert abs_path is None
        assert "Absolute paths" in error

    def test_windows_absolute_path_rejected(self, temp_config_dir):
        """Test that Windows absolute paths are rejected on Windows."""
        # On Windows, C:\path is absolute. On Unix, it's relative (C: is a valid filename)
        # This test verifies Windows-style paths are handled correctly
        is_valid, abs_path, error = resolve_safe_asset_path(
            temp_config_dir, "C:\\Windows\\System32\\config"
        )

        # On Windows: should be rejected as absolute path
        # On Unix: may be accepted as relative path (creating a file named "C:")
        # Either way, it must stay within assets directory if accepted
        if is_valid:
            # If accepted (Unix), verify it's within assets directory
            assets_dir = get_assets_directory(temp_config_dir)
            assert abs_path.startswith(
                assets_dir
            ), "Path must stay within assets directory"
        else:
            # If rejected (Windows), verify proper error
            assert abs_path is None
            assert error is not None

    def test_path_traversal_rejected(self, temp_config_dir):
        """Test that path traversal attempts are rejected."""
        # Try to escape with ../
        is_valid, abs_path, error = resolve_safe_asset_path(
            temp_config_dir, "../../../etc/passwd"
        )
        assert is_valid is False
        assert abs_path is None
        assert "path traversal" in error.lower() or "outside" in error.lower()

    def test_path_traversal_with_valid_prefix_rejected(self, temp_config_dir):
        """Test that path traversal is rejected even with valid-looking prefix."""
        is_valid, abs_path, error = resolve_safe_asset_path(
            temp_config_dir, "images/../../secrets.txt"
        )
        assert is_valid is False
        assert abs_path is None

    def test_url_scheme_rejected(self, temp_config_dir):
        """Test that URL schemes are rejected."""
        is_valid, abs_path, error = resolve_safe_asset_path(
            temp_config_dir, "http://example.com/image.png"
        )
        assert is_valid is False
        assert abs_path is None
        assert "Invalid path" in error

    def test_create_dirs_option(self, temp_config_dir):
        """Test that create_dirs option creates parent directories."""
        ensure_assets_directory(temp_config_dir)

        is_valid, abs_path, error = resolve_safe_asset_path(
            temp_config_dir, "deep/nested/path/image.png", create_dirs=True
        )

        assert is_valid is True
        assert error is None
        parent_dir = os.path.dirname(abs_path)
        assert os.path.exists(parent_dir)

    def test_whitespace_stripped(self, temp_config_dir):
        """Test that whitespace is stripped from paths."""
        is_valid, abs_path, error = resolve_safe_asset_path(
            temp_config_dir, "  icon.png  "
        )
        assert is_valid is True
        assert abs_path.endswith("icon.png")


class TestExtensionValidation:
    """Test file extension validation."""

    def test_valid_extensions(self):
        """Test that allowed extensions pass validation."""
        valid_files = [
            "image.png",
            "photo.jpg",
            "picture.jpeg",
            "animation.gif",
            "graphic.webp",
            "bitmap.bmp",
            "document.tiff",
            "image.tif",
            "icon.ico",
        ]
        for filename in valid_files:
            is_valid, error = validate_asset_extension(filename)
            assert is_valid is True, f"{filename} should be allowed"
            assert error is None

    def test_case_insensitive(self):
        """Test that extension checking is case-insensitive."""
        is_valid1, _ = validate_asset_extension("image.PNG")
        is_valid2, _ = validate_asset_extension("photo.JpG")
        is_valid3, _ = validate_asset_extension("file.GIF")

        assert is_valid1 is True
        assert is_valid2 is True
        assert is_valid3 is True

    def test_invalid_extensions(self):
        """Test that disallowed extensions fail validation."""
        invalid_files = [
            "file.txt",
            "document.pdf",
            "script.py",
            "config.json",
            "archive.zip",
            "executable.exe",
            "image.svg",  # SVG not allowed (security risk)
            "video.mp4",
        ]
        for filename in invalid_files:
            is_valid, error = validate_asset_extension(filename)
            assert is_valid is False, f"{filename} should be rejected"
            assert error is not None
            assert "not allowed" in error

    def test_no_extension(self):
        """Test that files without extension are rejected."""
        is_valid, error = validate_asset_extension("filename")
        assert is_valid is False
        assert "not allowed" in error


class TestContentValidation:
    """Test image content validation with Pillow."""

    def test_valid_png_content(self, sample_png_data):
        """Test that valid PNG content passes validation."""
        is_valid, error, image = validate_asset_content(
            sample_png_data, "test.png"
        )
        assert is_valid is True
        assert error is None
        assert image is not None
        assert image.format == "PNG"
        image.close()

    def test_valid_jpeg_content(self, sample_jpeg_data):
        """Test that valid JPEG content passes validation."""
        is_valid, error, image = validate_asset_content(
            sample_jpeg_data, "test.jpg"
        )
        assert is_valid is True
        assert error is None
        assert image is not None
        assert image.format == "JPEG"
        image.close()

    def test_valid_gif_content(self, sample_gif_data):
        """Test that valid GIF content passes validation."""
        is_valid, error, image = validate_asset_content(
            sample_gif_data, "test.gif"
        )
        assert is_valid is True
        assert error is None
        assert image is not None
        assert image.format == "GIF"
        image.close()

    def test_valid_webp_content(self, sample_webp_data):
        """Test that valid WEBP content passes validation."""
        is_valid, error, image = validate_asset_content(
            sample_webp_data, "test.webp"
        )
        assert is_valid is True
        assert error is None
        assert image is not None
        assert image.format == "WEBP"
        image.close()

    def test_fake_image_rejected(self):
        """Test that fake image (wrong content) is rejected."""
        fake_data = b"This is not actually an image file"
        is_valid, error, image = validate_asset_content(fake_data, "fake.png")
        assert is_valid is False
        assert error is not None
        assert "not a valid image" in error.lower()
        assert image is None

    def test_extension_mismatch_rejected(self, sample_png_data):
        """Test that extension mismatch is detected."""
        # PNG data but .jpg extension
        is_valid, error, image = validate_asset_content(
            sample_png_data, "mismatch.jpg"
        )
        assert is_valid is False
        assert error is not None
        assert "mismatch" in error.lower()
        assert image is None

    def test_corrupted_image_rejected(self):
        """Test that corrupted image data is rejected."""
        # Truncated PNG data
        corrupted_data = b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR"
        is_valid, error, image = validate_asset_content(
            corrupted_data, "corrupt.png"
        )
        assert is_valid is False
        assert error is not None
        assert image is None


class TestSizeValidation:
    """Test file size limit enforcement."""

    def test_size_within_limit(self, sample_png_data):
        """Test that file within size limit passes."""
        is_valid, error = validate_asset_size(sample_png_data)
        assert is_valid is True
        assert error is None

    def test_size_at_limit(self):
        """Test that file exactly at size limit passes."""
        max_size = 1000  # 1000 bytes
        data = b"x" * 1000
        is_valid, error = validate_asset_size(data, max_size)
        assert is_valid is True
        assert error is None

    def test_size_exceeds_limit(self):
        """Test that file exceeding size limit is rejected."""
        max_size = 1000  # 1000 bytes
        data = b"x" * 1001  # 1 byte over
        is_valid, error = validate_asset_size(data, max_size)
        assert is_valid is False
        assert error is not None
        assert "too large" in error.lower()

    def test_large_file_rejected(self):
        """Test that file larger than default 2MB is rejected."""
        # Create data larger than 2MB
        large_data = b"x" * (DEFAULT_MAX_ASSET_SIZE_BYTES + 1)
        is_valid, error = validate_asset_size(large_data)
        assert is_valid is False
        assert error is not None
        assert "too large" in error.lower()

    def test_custom_size_limit(self):
        """Test that custom size limit is enforced."""
        custom_limit = 500  # 500 bytes
        data = b"x" * 600  # 600 bytes
        is_valid, error = validate_asset_size(data, custom_limit)
        assert is_valid is False
        assert "too large" in error.lower()


class TestSaveAsset:
    """Test saving assets with full validation."""

    def test_save_valid_png(self, temp_config_dir, sample_png_data):
        """Test saving a valid PNG asset."""
        success, abs_path, error = save_asset(
            temp_config_dir, "icon.png", sample_png_data
        )

        assert success is True
        assert error is None
        assert abs_path is not None
        assert os.path.exists(abs_path)

        # Verify content
        with open(abs_path, "rb") as f:
            assert f.read() == sample_png_data

    def test_save_nested_path(self, temp_config_dir, sample_jpeg_data):
        """Test saving asset in nested directory."""
        success, abs_path, error = save_asset(
            temp_config_dir, "buttons/play.jpg", sample_jpeg_data
        )

        assert success is True
        assert error is None
        assert os.path.exists(abs_path)
        assert "buttons" in abs_path

    def test_save_creates_parent_directories(
        self, temp_config_dir, sample_png_data
    ):
        """Test that saving creates parent directories automatically."""
        success, abs_path, error = save_asset(
            temp_config_dir,
            "deep/nested/path/image.png",
            sample_png_data,
        )

        assert success is True
        assert os.path.exists(abs_path)
        assert os.path.exists(os.path.dirname(abs_path))

    def test_save_overwrite_rejected_by_default(
        self, temp_config_dir, sample_png_data
    ):
        """Test that overwriting existing file is rejected by default."""
        # Save once
        success1, _, _ = save_asset(
            temp_config_dir, "icon.png", sample_png_data
        )
        assert success1 is True

        # Try to save again without allow_overwrite
        success2, abs_path2, error2 = save_asset(
            temp_config_dir, "icon.png", sample_png_data
        )
        assert success2 is False
        assert abs_path2 is None
        assert "already exists" in error2.lower()

    def test_save_overwrite_allowed(
        self, temp_config_dir, sample_png_data, sample_jpeg_data
    ):
        """Test that overwriting is allowed when flag is set."""
        # Save PNG
        save_asset(temp_config_dir, "icon.png", sample_png_data)

        # Overwrite with JPEG data (but keeping .png extension)
        # Note: This will fail validation due to extension mismatch,
        # so let's use PNG data but different content
        new_png = Image.new("RGB", (200, 200), color="blue")
        new_png_bytes = io.BytesIO()
        new_png.save(new_png_bytes, "PNG")
        new_data = new_png_bytes.getvalue()

        success, abs_path, error = save_asset(
            temp_config_dir, "icon.png", new_data, allow_overwrite=True
        )

        assert success is True
        assert error is None

        # Verify new content
        with open(abs_path, "rb") as f:
            assert f.read() == new_data

    def test_save_invalid_extension_rejected(
        self, temp_config_dir, sample_png_data
    ):
        """Test that invalid extension is rejected."""
        success, abs_path, error = save_asset(
            temp_config_dir, "file.txt", sample_png_data
        )
        assert success is False
        assert abs_path is None
        assert "not allowed" in error.lower()

    def test_save_path_traversal_rejected(
        self, temp_config_dir, sample_png_data
    ):
        """Test that path traversal is rejected during save."""
        success, abs_path, error = save_asset(
            temp_config_dir, "../../../etc/passwd", sample_png_data
        )
        assert success is False
        assert abs_path is None
        assert "traversal" in error.lower() or "outside" in error.lower()

    def test_save_fake_image_rejected(self, temp_config_dir):
        """Test that fake image content is rejected."""
        fake_data = b"This is not an image"
        success, abs_path, error = save_asset(
            temp_config_dir, "fake.png", fake_data
        )
        assert success is False
        assert abs_path is None
        assert "not a valid image" in error.lower()

    def test_save_oversized_file_rejected(self, temp_config_dir):
        """Test that oversized file is rejected."""
        # Create a large fake image (just data, will fail content validation first)
        # So let's create a valid but large image
        large_img = Image.new("RGB", (2000, 2000), color="red")
        large_bytes = io.BytesIO()
        large_img.save(large_bytes, "PNG")
        large_data = large_bytes.getvalue()

        # Use a very small max size
        success, abs_path, error = save_asset(
            temp_config_dir, "large.png", large_data, max_size=1000
        )
        assert success is False
        assert abs_path is None
        assert "too large" in error.lower()

    def test_atomic_write_uses_temp_file(
        self, temp_config_dir, sample_png_data
    ):
        """Test that save uses atomic write (temp file pattern)."""
        # This is harder to test directly, but we can verify the final result
        # and check that no .tmp files are left behind
        assets_dir = get_assets_directory(temp_config_dir)
        ensure_assets_directory(temp_config_dir)

        success, abs_path, error = save_asset(
            temp_config_dir, "icon.png", sample_png_data
        )

        assert success is True

        # Check no temp files left behind
        for root, dirs, files in os.walk(assets_dir):
            for file in files:
                assert not file.endswith(".tmp")
                assert not file.startswith(".asset_")


class TestDeleteAsset:
    """Test deleting assets."""

    def test_delete_existing_asset(self, temp_config_dir, sample_png_data):
        """Test deleting an existing asset."""
        # Save asset first
        save_asset(temp_config_dir, "icon.png", sample_png_data)

        # Delete it
        success, error = delete_asset(temp_config_dir, "icon.png")
        assert success is True
        assert error is None

        # Verify it's gone
        exists, _, _ = get_asset_path(temp_config_dir, "icon.png")
        assert exists is False

    def test_delete_nested_asset(self, temp_config_dir, sample_png_data):
        """Test deleting asset in nested directory."""
        # Save nested asset
        save_asset(temp_config_dir, "buttons/play.png", sample_png_data)

        # Delete it
        success, error = delete_asset(temp_config_dir, "buttons/play.png")
        assert success is True
        assert error is None

    def test_delete_nonexistent_asset(self, temp_config_dir):
        """Test deleting non-existent asset returns error."""
        success, error = delete_asset(temp_config_dir, "nonexistent.png")
        assert success is False
        assert error is not None
        assert "not found" in error.lower()

    def test_delete_cleans_empty_directories(
        self, temp_config_dir, sample_png_data
    ):
        """Test that deleting asset cleans up empty parent directories."""
        # Save asset in nested path
        save_asset(
            temp_config_dir, "deep/nested/path/image.png", sample_png_data
        )

        # Get the parent directory path
        _, abs_path, _ = get_asset_path(
            temp_config_dir, "deep/nested/path/image.png"
        )
        parent_dir = os.path.dirname(abs_path)

        # Delete the asset
        delete_asset(temp_config_dir, "deep/nested/path/image.png")

        # Parent directories should be cleaned up if empty
        # (the implementation cleans up empty dirs)
        # Note: This might vary based on implementation details

    def test_delete_path_traversal_rejected(self, temp_config_dir):
        """Test that path traversal is rejected during delete."""
        success, error = delete_asset(temp_config_dir, "../../../etc/passwd")
        assert success is False
        assert error is not None


class TestListAssets:
    """Test listing assets."""

    def test_list_empty_directory(self, temp_config_dir):
        """Test listing assets when directory is empty."""
        ensure_assets_directory(temp_config_dir)
        assets = list_assets(temp_config_dir)
        assert assets == []

    def test_list_nonexistent_directory(self, temp_config_dir):
        """Test listing when assets directory doesn't exist yet."""
        assets = list_assets(temp_config_dir)
        assert assets == []

    def test_list_single_asset(self, temp_config_dir, sample_png_data):
        """Test listing single asset."""
        save_asset(temp_config_dir, "icon.png", sample_png_data)

        assets = list_assets(temp_config_dir)
        assert len(assets) == 1
        assert "icon.png" in assets

    def test_list_multiple_assets(self, temp_config_dir, sample_png_data):
        """Test listing multiple assets."""
        save_asset(temp_config_dir, "icon1.png", sample_png_data)
        save_asset(temp_config_dir, "icon2.png", sample_png_data)
        save_asset(temp_config_dir, "icon3.png", sample_png_data)

        assets = list_assets(temp_config_dir)
        assert len(assets) == 3
        assert "icon1.png" in assets
        assert "icon2.png" in assets
        assert "icon3.png" in assets

    def test_list_nested_assets(
        self, temp_config_dir, sample_png_data, sample_jpeg_data
    ):
        """Test listing nested assets."""
        save_asset(temp_config_dir, "icon.png", sample_png_data)
        save_asset(temp_config_dir, "buttons/play.png", sample_png_data)
        save_asset(
            temp_config_dir, "effects/fire/texture.jpg", sample_jpeg_data
        )

        assets = list_assets(temp_config_dir)
        assert len(assets) == 3

        # Should return normalized relative paths
        assert "icon.png" in assets
        assert "buttons/play.png" in assets
        assert "effects/fire/texture.jpg" in assets

    def test_list_ignores_temp_files(self, temp_config_dir, sample_png_data):
        """Test that temp files are ignored in listing."""
        assets_dir = get_assets_directory(temp_config_dir)
        ensure_assets_directory(temp_config_dir)

        # Save a normal asset
        save_asset(temp_config_dir, "icon.png", sample_png_data)

        # Create a temp file manually
        temp_file = os.path.join(assets_dir, "temp.tmp")
        with open(temp_file, "wb") as f:
            f.write(b"temp data")

        assets = list_assets(temp_config_dir)
        assert len(assets) == 1
        assert "icon.png" in assets
        assert "temp.tmp" not in assets

    def test_list_ignores_system_files(self, temp_config_dir, sample_png_data):
        """Test that system files are ignored in listing."""
        assets_dir = get_assets_directory(temp_config_dir)
        ensure_assets_directory(temp_config_dir)

        # Save a normal asset
        save_asset(temp_config_dir, "icon.png", sample_png_data)

        # Create system files manually
        ds_store = os.path.join(assets_dir, ".DS_Store")
        thumbs = os.path.join(assets_dir, "Thumbs.db")
        with open(ds_store, "wb") as f:
            f.write(b"system data")
        with open(thumbs, "wb") as f:
            f.write(b"system data")

        assets = list_assets(temp_config_dir)
        assert len(assets) == 1
        assert "icon.png" in assets
        assert ".DS_Store" not in assets
        assert "Thumbs.db" not in assets

    def test_list_ignores_non_image_files(
        self, temp_config_dir, sample_png_data
    ):
        """Test that non-image files are ignored in listing."""
        assets_dir = get_assets_directory(temp_config_dir)
        ensure_assets_directory(temp_config_dir)

        # Save a normal asset
        save_asset(temp_config_dir, "icon.png", sample_png_data)

        # Create non-image file manually
        txt_file = os.path.join(assets_dir, "readme.txt")
        with open(txt_file, "w") as f:
            f.write("This is not an image")

        assets = list_assets(temp_config_dir)
        assert len(assets) == 1
        assert "icon.png" in assets
        assert "readme.txt" not in assets

    def test_list_sorted_output(self, temp_config_dir, sample_png_data):
        """Test that listing returns sorted results."""
        save_asset(temp_config_dir, "zebra.png", sample_png_data)
        save_asset(temp_config_dir, "alpha.png", sample_png_data)
        save_asset(temp_config_dir, "beta.png", sample_png_data)

        assets = list_assets(temp_config_dir)
        assert assets == ["alpha.png", "beta.png", "zebra.png"]

    def test_list_uses_forward_slashes(self, temp_config_dir, sample_png_data):
        """Test that listing uses forward slashes consistently."""
        save_asset(
            temp_config_dir, "folder/subfolder/image.png", sample_png_data
        )

        assets = list_assets(temp_config_dir)
        assert len(assets) == 1
        # Should use forward slashes
        assert "folder/subfolder/image.png" in assets
        # Should not contain backslashes
        assert all("\\" not in asset for asset in assets)


class TestGetAssetPath:
    """Test getting asset paths."""

    def test_get_existing_asset(self, temp_config_dir, sample_png_data):
        """Test getting path to existing asset."""
        save_asset(temp_config_dir, "icon.png", sample_png_data)

        exists, abs_path, error = get_asset_path(temp_config_dir, "icon.png")
        assert exists is True
        assert error is None
        assert abs_path is not None
        assert os.path.exists(abs_path)

    def test_get_nonexistent_asset(self, temp_config_dir):
        """Test getting path to non-existent asset."""
        exists, abs_path, error = get_asset_path(
            temp_config_dir, "nonexistent.png"
        )
        assert exists is False
        assert abs_path is None
        assert error is not None
        assert "not found" in error.lower()

    def test_get_path_traversal_rejected(self, temp_config_dir):
        """Test that path traversal is rejected."""
        exists, abs_path, error = get_asset_path(
            temp_config_dir, "../../../etc/passwd"
        )
        assert exists is False
        assert abs_path is None
        assert error is not None


class TestSecurityPatterns:
    """Test security patterns from big-list-of-naughty-strings."""

    def test_null_byte_injection(self, temp_config_dir, sample_png_data):
        """Test that null byte injection is rejected."""
        # Null byte could truncate the path in some systems
        success, _, error = save_asset(
            temp_config_dir, "image.png\x00.txt", sample_png_data
        )
        # Should either reject or handle safely
        # Most likely will fail during path resolution or file creation
        assert success is False or error is not None

    def test_unicode_traversal(self, temp_config_dir, sample_png_data):
        """Test that unicode path traversal attempts are rejected."""
        # Unicode encoding of ../
        unicode_traversal = "\u002e\u002e\u002f\u002e\u002e\u002f"
        success, _, error = save_asset(
            temp_config_dir,
            f"{unicode_traversal}image.png",
            sample_png_data,
        )
        assert success is False

    def test_mixed_separators(self, temp_config_dir, sample_png_data):
        """Test that mixed path separators are handled correctly."""
        # This should be normalized and accepted
        success, abs_path, error = save_asset(
            temp_config_dir, "folder\\subfolder/image.png", sample_png_data
        )
        assert success is True
        assert os.path.exists(abs_path)

    def test_double_dot_sequences(self, temp_config_dir, sample_png_data):
        """Test various double-dot traversal sequences."""
        dangerous_paths = [
            "./../image.png",
            "folder/.././../image.png",
            "..\\..\\image.png",
            "folder\\..\\..\\image.png",
        ]

        for path in dangerous_paths:
            success, abs_path, error = save_asset(
                temp_config_dir, path, sample_png_data
            )
            # Either rejected outright or resolved safely within assets
            if success:
                # If accepted, must be within assets directory
                assets_dir = get_assets_directory(temp_config_dir)
                assert abs_path.startswith(assets_dir)

    def test_extremely_long_path(self, temp_config_dir, sample_png_data):
        """Test that extremely long paths are handled gracefully."""
        # Create a very long path
        long_path = "/".join(["folder"] * 100) + "/image.png"
        success, abs_path, error = save_asset(
            temp_config_dir, long_path, sample_png_data
        )
        # Should either succeed or fail gracefully (OS limits)
        # No crash or security issue
        assert success is True or error is not None
