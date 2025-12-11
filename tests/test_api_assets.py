"""
Test cases for asset management API endpoints.

Tests upload, download, deletion, and listing of assets via REST API.

Note: These tests run against the live LedFx instance started by conftest.py
"""

import io
import os

import pytest
import requests
from PIL import Image

from tests.test_utilities.consts import BASE_PORT
from tests.test_utilities.naughty_strings import naughty_paths

# Test URLs - Use 127.0.0.1 instead of localhost to avoid Windows DNS resolution delay (~2s per request)
ASSETS_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/assets"
ASSETS_DOWNLOAD_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/assets/download"
ASSETS_THUMBNAIL_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/assets/thumbnail"


@pytest.fixture
def sample_png_bytes():
    """Generate sample PNG image bytes."""
    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, "PNG")
    return img_bytes.getvalue()


@pytest.fixture
def sample_jpeg_bytes():
    """Generate sample JPEG image bytes."""
    img = Image.new("RGB", (100, 100), color="blue")
    img_bytes = io.BytesIO()
    img.save(img_bytes, "JPEG")
    return img_bytes.getvalue()


@pytest.fixture
def sample_animated_gif_bytes():
    """Generate sample animated GIF image bytes (3 frames)."""
    frames = []
    # Create 3 frames with different colors
    for color in ["red", "green", "blue"]:
        img = Image.new("RGB", (100, 100), color=color)
        frames.append(img)

    # Save as animated GIF
    img_bytes = io.BytesIO()
    frames[0].save(
        img_bytes,
        format="GIF",
        save_all=True,
        append_images=frames[1:],
        duration=100,  # 100ms per frame
        loop=0,
    )
    return img_bytes.getvalue()


class TestAssetsAPIList:
    """Test GET /api/assets - listing assets."""

    def test_list_assets(self):
        """Test listing assets with metadata."""
        resp = requests.get(ASSETS_API_URL, timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "assets" in data
        assert isinstance(data["assets"], list)

        # If there are any assets, verify metadata structure
        if len(data["assets"]) > 0:
            asset = data["assets"][0]
            assert "path" in asset
            assert "size" in asset
            assert "modified" in asset
            assert "width" in asset
            assert "height" in asset
            assert isinstance(asset["size"], int)
            assert isinstance(asset["width"], int)
            assert isinstance(asset["height"], int)


class TestAssetsAPIUpload:
    """Test POST /api/assets - uploading assets."""

    def test_upload_valid_png(self, sample_png_bytes):
        """Test uploading a valid PNG asset."""
        files = {
            "file": ("icon.png", io.BytesIO(sample_png_bytes), "image/png")
        }
        data = {"path": "test_icon.png"}

        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "success"
        assert result["data"]["path"] == "test_icon.png"

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "test_icon.png"}, timeout=5
        )

    def test_upload_invalid_extension(self, sample_png_bytes):
        """Test that invalid file extension is rejected."""
        files = {
            "file": ("file.txt", io.BytesIO(sample_png_bytes), "text/plain")
        }
        data = {"path": "file.txt"}

        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "not allowed" in result["payload"]["reason"].lower()

    def test_upload_fake_image(self):
        """Test that fake image content is rejected."""
        fake_data = b"This is not an image"
        files = {"file": ("fake.png", io.BytesIO(fake_data), "image/png")}
        data = {"path": "fake.png"}

        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "not a valid image" in result["payload"]["reason"].lower()

    def test_upload_path_traversal_rejected(self, sample_png_bytes):
        """Test that path traversal attempts are rejected.

        Tests all 207 path traversal patterns from the big-list-of-naughty-strings.
        With the DNS fix (using 127.0.0.1), this completes in ~30s instead of ~15min.
        """
        for naughty_path in naughty_paths:
            files = {
                "file": ("evil.png", io.BytesIO(sample_png_bytes), "image/png")
            }
            data = {"path": naughty_path}

            resp = requests.post(
                ASSETS_API_URL, files=files, data=data, timeout=5
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["status"] == "failed"
            reason = result["payload"]["reason"].lower()
            assert (
                "traversal" in reason
                or "outside" in reason
                or "not allowed" in reason
                or "not a valid image" in reason
                or "invalid" in reason
                or "failed to create" in reason
                or "cannot find the path" in reason
            ), f"Path traversal attempt should fail: {naughty_path} (got: {reason})"


class TestAssetsAPIDownload:
    """Test POST /api/assets/download - downloading assets."""

    def test_download_existing_asset(self, sample_png_bytes):
        """Test downloading an existing asset."""
        # Upload first
        files = {
            "file": ("download.png", io.BytesIO(sample_png_bytes), "image/png")
        }
        data = {"path": "test_download.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Download
        resp = requests.post(
            ASSETS_DOWNLOAD_API_URL,
            json={"path": "test_download.png"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"
        assert resp.content == sample_png_bytes

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "test_download.png"}, timeout=5
        )

    def test_download_nonexistent_asset(self):
        """Test that downloading non-existent asset returns error."""
        resp = requests.post(
            ASSETS_DOWNLOAD_API_URL,
            json={"path": "nonexistent.png"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "not found" in result["payload"]["reason"].lower()

    def test_download_builtin_asset(self):
        """Test downloading a built-in asset using builtin:// prefix."""
        # Get list of built-in assets
        resp = requests.get(
            f"http://127.0.0.1:{BASE_PORT}/api/assets_fixed", timeout=5
        )
        assert resp.status_code == 200
        builtin_assets = resp.json().get("assets", [])

        if not builtin_assets:
            pytest.skip("No built-in assets available for testing")

        # Download first built-in asset with builtin:// prefix
        builtin_asset = builtin_assets[0]
        builtin_path = f"builtin://{builtin_asset['path']}"

        resp = requests.post(
            ASSETS_DOWNLOAD_API_URL,
            json={"path": builtin_path},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        # Content-Type should match the actual file type
        assert "image/" in resp.headers["Content-Type"]
        # Should get binary data
        assert len(resp.content) > 0

    def test_download_builtin_nonexistent(self):
        """Test that downloading non-existent built-in asset returns error."""
        resp = requests.post(
            ASSETS_DOWNLOAD_API_URL,
            json={"path": "builtin://nonexistent.gif"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "not found" in result["payload"]["reason"].lower()

    def test_download_get_existing_asset(self, sample_png_bytes):
        """Test downloading an existing asset via GET request."""
        # Upload first
        files = {
            "file": ("download.png", io.BytesIO(sample_png_bytes), "image/png")
        }
        data = {"path": "test_download_get.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Download via GET
        resp = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": "test_download_get.png"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"
        assert resp.content == sample_png_bytes

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "test_download_get.png"}, timeout=5
        )

    def test_download_get_nonexistent_asset(self):
        """Test that downloading non-existent asset via GET returns error."""
        resp = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": "nonexistent_get.png"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "not found" in result["payload"]["reason"].lower()

    def test_download_get_builtin_asset(self):
        """Test downloading a built-in asset via GET using builtin:// prefix."""
        # Get list of built-in assets
        resp = requests.get(
            f"http://127.0.0.1:{BASE_PORT}/api/assets_fixed", timeout=5
        )
        assert resp.status_code == 200
        builtin_assets = resp.json().get("assets", [])

        if not builtin_assets:
            pytest.skip("No built-in assets available for testing")

        # Download first built-in asset with builtin:// prefix
        builtin_asset = builtin_assets[0]
        builtin_path = f"builtin://{builtin_asset['path']}"

        resp = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": builtin_path},
            timeout=5,
        )
        assert resp.status_code == 200
        # Content-Type should match the actual file type
        assert "image/" in resp.headers["Content-Type"]
        # Should get binary data
        assert len(resp.content) > 0

    def test_download_get_missing_path_parameter(self):
        """Test that GET without path parameter returns error."""
        resp = requests.get(ASSETS_DOWNLOAD_API_URL, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "path" in result["payload"]["reason"].lower()

    def test_download_post_path_traversal_rejected(self):
        """Test that POST download rejects path traversal attempts."""
        resp = requests.post(
            ASSETS_DOWNLOAD_API_URL,
            json={"path": "../../../etc/passwd"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"

    def test_download_get_path_traversal_rejected(self):
        """Test that GET download rejects path traversal attempts."""
        resp = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": "../../../etc/passwd"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"

    def test_download_post_absolute_path_rejected(self):
        """Test that POST download rejects absolute paths."""
        resp = requests.post(
            ASSETS_DOWNLOAD_API_URL,
            json={"path": "/etc/passwd"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"

    def test_download_get_absolute_path_rejected(self):
        """Test that GET download rejects absolute paths."""
        resp = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": "/etc/passwd"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"

    def test_download_builtin_path_traversal_rejected(self):
        """Test that builtin:// prefix also rejects path traversal."""
        resp = requests.post(
            ASSETS_DOWNLOAD_API_URL,
            json={"path": "builtin://../../../etc/passwd"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"


class TestAssetsAPIDelete:
    """Test DELETE /api/assets - deleting assets."""

    def test_delete_existing_asset(self, sample_png_bytes):
        """Test deleting an existing asset."""
        # Upload first
        files = {
            "file": ("todelete.png", io.BytesIO(sample_png_bytes), "image/png")
        }
        data = {"path": "test_delete.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Delete
        resp = requests.delete(
            ASSETS_API_URL, params={"path": "test_delete.png"}, timeout=5
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "success"
        assert result["data"]["deleted"] is True

        # Verify it's gone
        resp = requests.post(
            ASSETS_DOWNLOAD_API_URL,
            json={"path": "test_delete.png"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"

    def test_delete_nonexistent_asset(self):
        """Test that deleting non-existent asset returns error."""
        resp = requests.delete(
            ASSETS_API_URL, params={"path": "nonexistent.png"}, timeout=5
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "not found" in result["payload"]["reason"].lower()

    def test_delete_with_json_body(self, sample_png_bytes):
        """Test that DELETE also works with JSON body (fallback for some browsers)."""
        # Upload first
        files = {
            "file": ("jsontest.png", io.BytesIO(sample_png_bytes), "image/png")
        }
        data = {"path": "test_delete_json.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Delete using JSON body instead of query param
        resp = requests.delete(
            ASSETS_API_URL,
            json={"path": "test_delete_json.png"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "success"
        assert result["data"]["deleted"] is True

        # Verify it's gone
        resp = requests.post(
            ASSETS_DOWNLOAD_API_URL,
            json={"path": "test_delete_json.png"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"


class TestAssetsAPIIntegration:
    """Integration tests for full upload → list → download → delete cycle."""

    def test_full_lifecycle(self, sample_png_bytes):
        """Test complete asset lifecycle: upload → list → download → delete."""
        asset_path = "lifecycle_test.png"

        # 1. Upload
        files = {
            "file": ("test.png", io.BytesIO(sample_png_bytes), "image/png")
        }
        data = {"path": asset_path}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "success"

        # 2. List - verify it's in the list with metadata
        resp = requests.get(ASSETS_API_URL, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        asset_paths = [asset["path"] for asset in result["assets"]]
        assert asset_path in asset_paths
        # Find the asset and verify metadata
        asset_metadata = next(
            a for a in result["assets"] if a["path"] == asset_path
        )
        assert "size" in asset_metadata
        assert "modified" in asset_metadata
        assert "width" in asset_metadata
        assert "height" in asset_metadata

        # 3. Download - verify content
        resp = requests.post(
            ASSETS_DOWNLOAD_API_URL,
            json={"path": asset_path},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.content == sample_png_bytes

        # 4. Delete
        resp = requests.delete(
            ASSETS_API_URL, params={"path": asset_path}, timeout=5
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "success"

        # 5. List - verify it's gone
        resp = requests.get(ASSETS_API_URL, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        asset_paths = [asset["path"] for asset in result["assets"]]
        assert asset_path not in asset_paths


class TestAssetsAPIThumbnail:
    """Test POST /api/assets/thumbnail - generating thumbnails."""

    def test_thumbnail_default_size(self, sample_png_bytes):
        """Test generating thumbnail with default size (128px)."""
        # Upload asset first
        files = {
            "file": (
                "thumb_test.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "test_thumbnail.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Get thumbnail
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "test_thumbnail.png"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"

        # Verify it's a valid PNG and size is correct
        img = Image.open(io.BytesIO(resp.content))
        assert img.format == "PNG"
        assert max(img.size) <= 128
        assert img.size[0] <= 128 and img.size[1] <= 128

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "test_thumbnail.png"}, timeout=5
        )

    def test_thumbnail_custom_size(self, sample_png_bytes):
        """Test generating thumbnail with custom size."""
        # Upload asset first
        files = {
            "file": (
                "thumb_custom.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "test_thumbnail_custom.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Get 64px thumbnail
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "test_thumbnail_custom.png", "size": 64},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"

        # Verify size
        img = Image.open(io.BytesIO(resp.content))
        assert max(img.size) <= 64

        # Cleanup
        requests.delete(
            ASSETS_API_URL,
            params={"path": "test_thumbnail_custom.png"},
            timeout=5,
        )

    def test_thumbnail_size_limits(self, sample_png_bytes):
        """Test that out-of-range thumbnail sizes return a validation error."""
        # Upload asset first
        files = {
            "file": (
                "thumb_limits.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "test_thumbnail_limits.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Test size too small
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "test_thumbnail_limits.png", "size": 10},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "between" in result["payload"]["reason"].lower()

        # Test size too large
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "test_thumbnail_limits.png", "size": 1000},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "between" in result["payload"]["reason"].lower()

        # Cleanup
        requests.delete(
            ASSETS_API_URL,
            params={"path": "test_thumbnail_limits.png"},
            timeout=5,
        )

    def test_thumbnail_nonexistent_asset(self):
        """Test that requesting thumbnail of non-existent asset returns error."""
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "nonexistent_thumbnail.png"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "not found" in result["payload"]["reason"].lower()

    def test_thumbnail_missing_path(self):
        """Test that missing path parameter returns error."""
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "path" in result["payload"]["reason"].lower()

    def test_thumbnail_jpeg_source(self, sample_jpeg_bytes):
        """Test generating PNG thumbnail from JPEG source."""
        # Upload JPEG asset
        files = {
            "file": (
                "thumb_jpeg.jpg",
                io.BytesIO(sample_jpeg_bytes),
                "image/jpeg",
            )
        }
        data = {"path": "test_thumbnail.jpg"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Get thumbnail
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "test_thumbnail.jpg"},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"

        # Verify it's PNG (not JPEG)
        img = Image.open(io.BytesIO(resp.content))
        assert img.format == "PNG"

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "test_thumbnail.jpg"}, timeout=5
        )

    def test_thumbnail_dimension_width(self, sample_png_bytes):
        """Test generating thumbnail with fixed width dimension."""
        # Upload asset first
        files = {
            "file": (
                "thumb_width.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "test_dimension_width.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Get thumbnail with width=200
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={
                "path": "test_dimension_width.png",
                "size": 200,
                "dimension": "width",
            },
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"

        # Verify width is exactly 200
        img = Image.open(io.BytesIO(resp.content))
        assert img.format == "PNG"
        assert img.size[0] == 200  # width should be exactly 200

        # Cleanup
        requests.delete(
            ASSETS_API_URL,
            params={"path": "test_dimension_width.png"},
            timeout=5,
        )

    def test_thumbnail_dimension_height(self, sample_png_bytes):
        """Test generating thumbnail with fixed height dimension."""
        # Upload asset first
        files = {
            "file": (
                "thumb_height.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "test_dimension_height.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Get thumbnail with height=150
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={
                "path": "test_dimension_height.png",
                "size": 150,
                "dimension": "height",
            },
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"

        # Verify height is exactly 150
        img = Image.open(io.BytesIO(resp.content))
        assert img.format == "PNG"
        assert img.size[1] == 150  # height should be exactly 150

        # Cleanup
        requests.delete(
            ASSETS_API_URL,
            params={"path": "test_dimension_height.png"},
            timeout=5,
        )

    def test_thumbnail_dimension_max(self, sample_png_bytes):
        """Test generating thumbnail with max dimension (default behavior)."""
        # Upload asset first
        files = {
            "file": (
                "thumb_max.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "test_dimension_max.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Get thumbnail with dimension=max
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={
                "path": "test_dimension_max.png",
                "size": 200,
                "dimension": "max",
            },
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"

        # Verify longest dimension is at most 200
        img = Image.open(io.BytesIO(resp.content))
        assert img.format == "PNG"
        assert max(img.size) <= 200

        # Cleanup
        requests.delete(
            ASSETS_API_URL,
            params={"path": "test_dimension_max.png"},
            timeout=5,
        )

    def test_thumbnail_dimension_invalid(self, sample_png_bytes):
        """Test that invalid dimension parameter returns error."""
        # Upload asset first
        files = {
            "file": (
                "thumb_invalid.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "test_dimension_invalid.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Try to get thumbnail with invalid dimension
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={
                "path": "test_dimension_invalid.png",
                "size": 128,
                "dimension": "invalid",
            },
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "max" in result["payload"]["reason"].lower()
        assert "width" in result["payload"]["reason"].lower()
        assert "height" in result["payload"]["reason"].lower()

        # Cleanup
        requests.delete(
            ASSETS_API_URL,
            params={"path": "test_dimension_invalid.png"},
            timeout=5,
        )

    def test_thumbnail_animated_gif_default(self, sample_animated_gif_bytes):
        """Test generating animated WebP thumbnail from GIF (default animated=true)."""
        # Upload animated GIF asset
        files = {
            "file": (
                "animated.gif",
                io.BytesIO(sample_animated_gif_bytes),
                "image/gif",
            )
        }
        data = {"path": "test_animated.gif"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Get thumbnail (default animated=true)
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "test_animated.gif", "size": 64},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/webp"

        # Verify it's an animated WebP
        img = Image.open(io.BytesIO(resp.content))
        assert img.format == "WEBP"
        assert getattr(img, "is_animated", False) is True
        assert getattr(img, "n_frames", 1) == 3  # Should have 3 frames

        # Verify dimensions are correct for first frame
        assert max(img.size) <= 64

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "test_animated.gif"}, timeout=5
        )

    def test_thumbnail_animated_gif_explicit_true(
        self, sample_animated_gif_bytes
    ):
        """Test generating animated WebP thumbnail with explicit animated=true."""
        # Upload animated GIF asset
        files = {
            "file": (
                "animated2.gif",
                io.BytesIO(sample_animated_gif_bytes),
                "image/gif",
            )
        }
        data = {"path": "test_animated2.gif"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Get thumbnail with explicit animated=true
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "test_animated2.gif", "size": 64, "animated": True},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/webp"

        # Verify it's an animated WebP
        img = Image.open(io.BytesIO(resp.content))
        assert img.format == "WEBP"
        assert getattr(img, "is_animated", False) is True
        assert getattr(img, "n_frames", 1) == 3

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "test_animated2.gif"}, timeout=5
        )

    def test_thumbnail_animated_gif_static(self, sample_animated_gif_bytes):
        """Test generating static PNG thumbnail from GIF with animated=false."""
        # Upload animated GIF asset
        files = {
            "file": (
                "animated_static.gif",
                io.BytesIO(sample_animated_gif_bytes),
                "image/gif",
            )
        }
        data = {"path": "test_animated_static.gif"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Get thumbnail with animated=false
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={
                "path": "test_animated_static.gif",
                "size": 64,
                "animated": False,
            },
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"

        # Verify it's a static PNG (first frame only)
        img = Image.open(io.BytesIO(resp.content))
        assert img.format == "PNG"
        # PNG should not have is_animated or should be False
        assert getattr(img, "is_animated", False) is False
        assert max(img.size) <= 64

        # Cleanup
        requests.delete(
            ASSETS_API_URL,
            params={"path": "test_animated_static.gif"},
            timeout=5,
        )

    def test_thumbnail_animated_string_parameter(
        self, sample_animated_gif_bytes
    ):
        """Test that animated parameter accepts string values like 'true'/'false'."""
        # Upload animated GIF asset
        files = {
            "file": (
                "animated_string.gif",
                io.BytesIO(sample_animated_gif_bytes),
                "image/gif",
            )
        }
        data = {"path": "test_animated_string.gif"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Test with string "false"
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={
                "path": "test_animated_string.gif",
                "size": 64,
                "animated": "false",
            },
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"

        # Test with string "true"
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={
                "path": "test_animated_string.gif",
                "size": 64,
                "animated": "true",
            },
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/webp"

        # Cleanup
        requests.delete(
            ASSETS_API_URL,
            params={"path": "test_animated_string.gif"},
            timeout=5,
        )

    def test_thumbnail_builtin_animated(self):
        """Test generating animated thumbnail from builtin animated asset."""
        # Test with a known builtin animated GIF (skull.gif exists in ledfx_assets)
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "builtin://skull.gif", "size": 64, "animated": True},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/webp"

        # Verify it's an animated WebP
        img = Image.open(io.BytesIO(resp.content))
        assert img.format == "WEBP"
        assert max(img.size) <= 64

    def test_thumbnail_builtin_static(self):
        """Test generating static PNG from builtin animated asset with animated=false."""
        # Test with a known builtin animated GIF
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={
                "path": "builtin://skull.gif",
                "size": 64,
                "animated": False,
            },
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"

        # Verify it's a static PNG
        img = Image.open(io.BytesIO(resp.content))
        assert img.format == "PNG"
        assert max(img.size) <= 64


class TestAssetsAPIAnimationMetadata:
    """Test GET /api/assets - animation metadata in asset listings."""

    def test_list_assets_includes_animation_metadata(self):
        """Test that listed assets include format, n_frames, and is_animated."""
        resp = requests.get(ASSETS_API_URL, timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "assets" in data

        # If there are assets, verify animation metadata fields
        if len(data["assets"]) > 0:
            asset = data["assets"][0]
            assert "format" in asset
            assert "n_frames" in asset
            assert "is_animated" in asset
            assert isinstance(asset["format"], str)
            assert isinstance(asset["n_frames"], int)
            assert isinstance(asset["is_animated"], bool)
            assert asset["n_frames"] >= 1

    def test_static_image_metadata(self, sample_png_bytes):
        """Test that static images report is_animated=False and n_frames=1."""
        # Upload static PNG
        files = {
            "file": (
                "static_meta.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "test_static_meta.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # List assets and find uploaded one
        resp = requests.get(ASSETS_API_URL, timeout=5)
        data = resp.json()
        assets = [
            a for a in data["assets"] if a["path"] == "test_static_meta.png"
        ]

        assert len(assets) == 1
        asset = assets[0]
        assert asset["format"] == "PNG"
        assert asset["n_frames"] == 1
        assert asset["is_animated"] is False

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "test_static_meta.png"}, timeout=5
        )


class TestAssetsFixedAPI:
    """Test GET /api/assets_fixed - listing built-in assets."""

    def test_assets_fixed_endpoint_exists(self):
        """Test that /api/assets_fixed endpoint is accessible."""
        resp = requests.get(
            f"http://127.0.0.1:{BASE_PORT}/api/assets_fixed", timeout=5
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "assets" in data
        assert isinstance(data["assets"], list)

    def test_assets_fixed_metadata_structure(self):
        """Test that built-in assets have correct metadata structure."""
        resp = requests.get(
            f"http://127.0.0.1:{BASE_PORT}/api/assets_fixed", timeout=5
        )
        assert resp.status_code == 200
        data = resp.json()

        # If there are built-in assets, verify structure
        if len(data["assets"]) > 0:
            asset = data["assets"][0]
            assert "path" in asset
            assert "size" in asset
            assert "modified" in asset
            assert "width" in asset
            assert "height" in asset
            assert "format" in asset
            assert "n_frames" in asset
            assert "is_animated" in asset

            # Verify types
            assert isinstance(asset["path"], str)
            assert isinstance(asset["size"], int)
            assert isinstance(asset["modified"], str)  # ISO timestamp string
            assert isinstance(asset["width"], int)
            assert isinstance(asset["height"], int)
            assert isinstance(asset["format"], str)
            assert isinstance(asset["n_frames"], int)
            assert isinstance(asset["is_animated"], bool)

    def test_assets_fixed_paths_relative(self):
        """Test that built-in asset paths are relative to gifs directory."""
        resp = requests.get(
            f"http://127.0.0.1:{BASE_PORT}/api/assets_fixed", timeout=5
        )
        assert resp.status_code == 200
        data = resp.json()

        for asset in data["assets"]:
            path = asset["path"]
            # Paths should be relative, not absolute
            assert not os.path.isabs(path)
            # Paths should not contain .. traversal
            assert ".." not in path


class TestAssetsThumbnailBuiltinSupport:
    """Test POST /api/assets/thumbnail - built-in asset support with builtin:// prefix."""

    def test_thumbnail_builtin_asset(self):
        """Test generating thumbnail for built-in asset using builtin:// prefix."""
        # First, get list of built-in assets
        resp = requests.get(
            f"http://127.0.0.1:{BASE_PORT}/api/assets_fixed", timeout=5
        )
        assert resp.status_code == 200
        data = resp.json()

        if len(data["assets"]) == 0:
            pytest.skip("No built-in assets available for testing")

        # Use first built-in asset with builtin:// prefix
        builtin_asset = data["assets"][0]
        asset_path = f"builtin://{builtin_asset['path']}"

        # Request thumbnail
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": asset_path, "size": 64},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )

        assert resp.status_code == 200
        # Built-in assets may be animated (WebP) or static (PNG)
        assert resp.headers["Content-Type"] in ("image/png", "image/webp")
        assert len(resp.content) > 0

        # Verify it's a valid image
        img = Image.open(io.BytesIO(resp.content))
        assert img.format in ("PNG", "WEBP")
        assert img.width <= 64
        assert img.height <= 64

    def test_thumbnail_user_vs_builtin_separation(self, sample_png_bytes):
        """Test that user and built-in assets are clearly separated with prefix."""
        # Get a built-in asset name
        resp = requests.get(
            f"http://127.0.0.1:{BASE_PORT}/api/assets_fixed", timeout=5
        )
        data = resp.json()

        if len(data["assets"]) == 0:
            pytest.skip("No built-in assets available for testing")

        builtin_asset_name = os.path.basename(data["assets"][0]["path"])

        # Upload user asset with same name
        files = {
            "file": (
                builtin_asset_name,
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        upload_data = {"path": builtin_asset_name}
        resp = requests.post(
            ASSETS_API_URL, files=files, data=upload_data, timeout=5
        )
        assert resp.status_code == 200

        # Request thumbnail WITHOUT prefix - should get user asset
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": builtin_asset_name, "size": 64},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200

        # Request thumbnail WITH builtin:// prefix - should get built-in asset
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": f"builtin://{builtin_asset_name}", "size": 64},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": builtin_asset_name}, timeout=5
        )

    def test_thumbnail_builtin_nested_path(self):
        """Test generating thumbnail for nested built-in asset path with builtin:// prefix."""
        # Get list of built-in assets to find nested ones
        resp = requests.get(
            f"http://127.0.0.1:{BASE_PORT}/api/assets_fixed", timeout=5
        )
        assert resp.status_code == 200
        data = resp.json()

        # Find asset with nested path (contains /)
        nested_assets = [
            a for a in data["assets"] if "/" in a["path"] or "\\" in a["path"]
        ]

        if len(nested_assets) == 0:
            pytest.skip("No nested built-in assets available for testing")

        # Request thumbnail for nested path with builtin:// prefix
        nested_path = f"builtin://{nested_assets[0]['path']}"
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": nested_path, "size": 64},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )

        assert resp.status_code == 200
        # Built-in assets may be animated (WebP) or static (PNG)
        assert resp.headers["Content-Type"] in ("image/png", "image/webp")

    def test_thumbnail_builtin_nonexistent(self):
        """Test that requesting thumbnail for non-existent built-in asset returns error."""
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "builtin://nonexistent_builtin.gif", "size": 64},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )

        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "not found" in result["payload"]["reason"].lower()
