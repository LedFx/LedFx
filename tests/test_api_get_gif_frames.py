"""
Test cases for get_gif_frames API endpoint.

Tests the /api/get_gif_frames endpoint with various path types:
- User assets (plain filenames)
- Built-in assets (builtin:// paths)
- URLs (http/https)
"""

import io

import pytest
import requests
from PIL import Image

from tests.test_utilities.consts import BASE_PORT

# Test URL
GIF_FRAMES_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/get_gif_frames"
ASSETS_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/assets"


@pytest.fixture
def sample_animated_gif_bytes():
    """Generate sample animated GIF image bytes (3 frames)."""
    frames = []
    # Create 3 frames with different colors
    for color in ["red", "green", "blue"]:
        img = Image.new("RGB", (50, 50), color=color)
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


@pytest.mark.order(101)
class TestGetGifFramesAPI:
    """Test GET /api/get_gif_frames endpoint."""

    def test_user_asset_plain_filename(self, sample_animated_gif_bytes):
        """
        Test loading GIF from user assets using plain filename.
        
        This is the most common use case - a user uploads an asset
        and references it by filename only.
        """
        # First, upload a GIF asset
        files = {
            "file": (
                "test_anim.gif",
                io.BytesIO(sample_animated_gif_bytes),
                "image/gif",
            )
        }
        data = {"path": "test_anim.gif"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Now request frames using plain filename
        payload = {"path_url": "test_anim.gif"}
        resp = requests.post(GIF_FRAMES_API_URL, json=payload, timeout=5)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["frame_count"] == 3
        assert len(data["frames"]) == 3
        assert all(isinstance(frame, str) for frame in data["frames"])

    def test_user_asset_with_subfolder(self, sample_animated_gif_bytes):
        """Test loading GIF from user assets subfolder."""
        # Upload to subfolder
        files = {
            "file": (
                "test_sub.gif",
                io.BytesIO(sample_animated_gif_bytes),
                "image/gif",
            )
        }
        data = {"path": "animations/test_sub.gif"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Request with subfolder path
        payload = {"path_url": "animations/test_sub.gif"}
        resp = requests.post(GIF_FRAMES_API_URL, json=payload, timeout=5)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["frame_count"] == 3

    def test_builtin_asset(self):
        """Test loading GIF from built-in assets using builtin:// syntax."""
        # Test with a known built-in asset
        payload = {"path_url": "builtin://catfixed.gif"}
        resp = requests.post(GIF_FRAMES_API_URL, json=payload, timeout=5)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["frame_count"] > 0  # Built-in GIFs should have frames
        assert len(data["frames"]) == data["frame_count"]

    def test_builtin_asset_nested(self):
        """Test loading GIF from built-in assets subfolder."""
        payload = {"path_url": "builtin://pixelart/dj_bird.gif"}
        resp = requests.post(GIF_FRAMES_API_URL, json=payload, timeout=5)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["frame_count"] > 0

    def test_missing_path_url(self):
        """Test error handling when path_url is missing."""
        payload = {}
        resp = requests.post(GIF_FRAMES_API_URL, json=payload, timeout=5)
        
        assert resp.status_code == 200  # API returns 200 with error payload
        data = resp.json()
        assert data["status"] == "failed"
        assert "path_url" in data["payload"]["reason"]

    def test_nonexistent_file(self):
        """Test error handling for non-existent file."""
        payload = {"path_url": "nonexistent_file_12345.gif"}
        resp = requests.post(GIF_FRAMES_API_URL, json=payload, timeout=5)
        
        assert resp.status_code == 200  # API returns 200 with error payload
        data = resp.json()
        assert data["status"] == "failed"
        assert "Failed to open GIF" in data["payload"]["reason"]

    def test_invalid_json(self):
        """Test error handling for invalid JSON."""
        resp = requests.post(
            GIF_FRAMES_API_URL,
            data="not valid json",
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        
        # Invalid JSON returns 400 Bad Request
        assert resp.status_code == 400

    def test_path_traversal_blocked(self):
        """Test that path traversal attempts are blocked."""
        # Try to access file outside assets directory
        payload = {"path_url": "../../../etc/passwd"}
        resp = requests.post(GIF_FRAMES_API_URL, json=payload, timeout=5)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"
        assert "Failed to open GIF" in data["payload"]["reason"]

    def test_absolute_path_blocked(self):
        """Test that absolute paths are handled appropriately."""
        # Absolute paths should be blocked or validated within config dir
        payload = {"path_url": "/etc/passwd"}
        resp = requests.post(GIF_FRAMES_API_URL, json=payload, timeout=5)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "failed"

    def test_single_frame_image(self, sample_animated_gif_bytes):
        """Test that single-frame images are handled correctly."""
        # Create a single-frame PNG
        img = Image.new("RGB", (50, 50), color="yellow")
        img_bytes = io.BytesIO()
        img.save(img_bytes, "PNG")
        
        # Upload as user asset
        files = {
            "file": ("single.png", io.BytesIO(img_bytes.getvalue()), "image/png")
        }
        data = {"path": "single.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Request frames
        payload = {"path_url": "single.png"}
        resp = requests.post(GIF_FRAMES_API_URL, json=payload, timeout=5)
        
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert data["frame_count"] == 1
        assert len(data["frames"]) == 1
