"""
Test cases for asset management API endpoints.

Tests upload, download, deletion, and listing of assets via REST API.

Note: These tests run against the live LedFx instance started by conftest.py
"""

import io

import pytest
import requests
from PIL import Image

from tests.test_utilities.consts import BASE_PORT

# Test URLs
ASSETS_API_URL = f"http://localhost:{BASE_PORT}/api/assets"
ASSETS_DOWNLOAD_API_URL = f"http://localhost:{BASE_PORT}/api/assets/download"
ASSETS_THUMBNAIL_API_URL = f"http://localhost:{BASE_PORT}/api/assets/thumbnail"


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


class TestAssetsAPIList:
    """Test GET /api/assets - listing assets."""

    def test_list_assets(self):
        """Test listing assets."""
        resp = requests.get(ASSETS_API_URL, timeout=5)
        assert resp.status_code == 200
        data = resp.json()
        assert "assets" in data
        assert isinstance(data["assets"], list)


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
        """Test that path traversal attempts are rejected."""
        files = {
            "file": ("evil.png", io.BytesIO(sample_png_bytes), "image/png")
        }
        data = {"path": "../../../etc/passwd"}

        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert (
            "traversal" in result["payload"]["reason"].lower()
            or "outside" in result["payload"]["reason"].lower()
        )


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

        # 2. List - verify it's in the list
        resp = requests.get(ASSETS_API_URL, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert asset_path in result["assets"]

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
        assert asset_path not in result["assets"]


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
        """Test that thumbnail size is clamped to valid range."""
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
