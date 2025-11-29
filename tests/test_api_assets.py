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
        files = {"file": ("icon.png", io.BytesIO(sample_png_bytes), "image/png")}
        data = {"path": "test_icon.png"}

        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "success"
        assert result["data"]["path"] == "test_icon.png"

        # Cleanup
        requests.delete(ASSETS_API_URL, params={"path": "test_icon.png"}, timeout=5)

    def test_upload_invalid_extension(self, sample_png_bytes):
        """Test that invalid file extension is rejected."""
        files = {"file": ("file.txt", io.BytesIO(sample_png_bytes), "text/plain")}
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
        files = {"file": ("evil.png", io.BytesIO(sample_png_bytes), "image/png")}
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
    """Test GET /api/assets?path=... - downloading assets."""

    def test_download_existing_asset(self, sample_png_bytes):
        """Test downloading an existing asset."""
        # Upload first
        files = {"file": ("download.png", io.BytesIO(sample_png_bytes), "image/png")}
        data = {"path": "test_download.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Download
        resp = requests.get(ASSETS_API_URL, params={"path": "test_download.png"}, timeout=5)
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"
        assert resp.content == sample_png_bytes

        # Cleanup
        requests.delete(ASSETS_API_URL, params={"path": "test_download.png"}, timeout=5)

    def test_download_nonexistent_asset(self):
        """Test that downloading non-existent asset returns 404."""
        resp = requests.get(ASSETS_API_URL, params={"path": "nonexistent.png"}, timeout=5)
        assert resp.status_code == 404
        result = resp.json()
        assert result["status"] == "failed"
        assert "not found" in result["payload"]["reason"].lower()


class TestAssetsAPIDelete:
    """Test DELETE /api/assets?path=... - deleting assets."""

    def test_delete_existing_asset(self, sample_png_bytes):
        """Test deleting an existing asset."""
        # Upload first
        files = {"file": ("todelete.png", io.BytesIO(sample_png_bytes), "image/png")}
        data = {"path": "test_delete.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Delete
        resp = requests.delete(ASSETS_API_URL, params={"path": "test_delete.png"}, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "success"
        assert result["data"]["deleted"] is True

        # Verify it's gone
        resp = requests.get(ASSETS_API_URL, params={"path": "test_delete.png"}, timeout=5)
        assert resp.status_code == 404

    def test_delete_nonexistent_asset(self):
        """Test that deleting non-existent asset returns error."""
        resp = requests.delete(ASSETS_API_URL, params={"path": "nonexistent.png"}, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "not found" in result["payload"]["reason"].lower()


class TestAssetsAPIIntegration:
    """Integration tests for full upload → list → download → delete cycle."""

    def test_full_lifecycle(self, sample_png_bytes):
        """Test complete asset lifecycle: upload → list → download → delete."""
        asset_path = "lifecycle_test.png"

        # 1. Upload
        files = {"file": ("test.png", io.BytesIO(sample_png_bytes), "image/png")}
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
        resp = requests.get(ASSETS_API_URL, params={"path": asset_path}, timeout=5)
        assert resp.status_code == 200
        assert resp.content == sample_png_bytes

        # 4. Delete
        resp = requests.delete(ASSETS_API_URL, params={"path": asset_path}, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "success"

        # 5. List - verify it's gone
        resp = requests.get(ASSETS_API_URL, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        assert asset_path not in result["assets"]
