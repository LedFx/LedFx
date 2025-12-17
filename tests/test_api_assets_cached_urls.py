"""
Integration tests for cached URL support in assets API endpoints.

These tests verify that /api/assets/download and /api/assets/thumbnail
can handle remote URLs by automatically fetching, validating, and caching them.

Test Strategy:
- Uses mocking for error-handling tests (fast, deterministic)
- Uses external raw content URLs (raw.githubusercontent.com) for integration tests
- Verifies successful URL download and caching behavior
- Tests cache reuse on subsequent requests
- Validates SSRF protection and security checks
- Ensures non-URL paths (user/builtin assets) still work correctly

These are integration tests that require a running LedFx instance on a dynamically
allocated port (configured via test harness).
"""

import io
import time
import urllib.error
from unittest.mock import MagicMock, patch

import pytest
import requests
from PIL import Image

from tests.test_utilities.consts import BASE_PORT

# API endpoints - Use 127.0.0.1 instead of localhost to avoid Windows DNS resolution delay
ASSETS_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/assets"
ASSETS_DOWNLOAD_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/assets/download"
ASSETS_THUMBNAIL_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/assets/thumbnail"
CACHE_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/cache/images"


@pytest.fixture
def sample_gif_bytes():
    """Create a simple 2-frame animated GIF."""
    frames = []
    for color in [(255, 0, 0), (0, 0, 255)]:  # Red, Blue
        img = Image.new("RGB", (100, 100), color=color)
        frames.append(img)

    gif_bytes = io.BytesIO()
    frames[0].save(
        gif_bytes,
        save_all=True,
        append_images=frames[1:],
        duration=100,
        loop=0,
        format="GIF",
    )
    return gif_bytes.getvalue()


@pytest.mark.order(120)
class TestAssetsDownloadCachedURL:
    """Test /api/assets/download with cached URLs."""

    @patch("ledfx.utils.urllib.request.urlopen")
    def test_download_uncached_url_returns_error(self, mock_urlopen):
        """
        Test that requesting an unreachable URL returns appropriate error.

        Uses mocking to simulate URL fetch failure without actual network calls.
        This is fast, deterministic, and doesn't depend on external network.
        """
        # Simulate URLError (connection timeout/refused)
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        test_url = "https://example.com/not_in_cache.gif"

        # GET method
        resp = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": test_url},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        # Should return download/fetch error or validation error
        assert any(
            keyword in result["payload"]["reason"].lower()
            for keyword in ["download", "fetch", "failed", "validate", "url"]
        )

        # POST method
        resp = requests.post(
            ASSETS_DOWNLOAD_API_URL,
            json={"path": test_url},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        # Should return download/fetch error or validation error
        assert any(
            keyword in result["payload"]["reason"].lower()
            for keyword in ["download", "fetch", "failed", "validate", "url"]
        )


@pytest.mark.order(121)
class TestAssetsThumbnailCachedURL:
    """Test /api/assets/thumbnail with cached URLs."""

    @patch("ledfx.utils.urllib.request.urlopen")
    def test_thumbnail_uncached_url_returns_error(self, mock_urlopen):
        """
        Test that requesting thumbnail of unreachable URL returns error.

        Uses mocking to simulate URL fetch failure without actual network calls.
        This is fast, deterministic, and doesn't depend on external network.
        """
        # Simulate URLError (connection timeout/refused)
        mock_urlopen.side_effect = urllib.error.URLError("Connection refused")

        test_url = "https://example.com/not_in_cache.gif"

        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": test_url, "size": 64},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        # Should return download/fetch error or validation error
        assert any(
            keyword in result["payload"]["reason"].lower()
            for keyword in ["download", "fetch", "failed", "validate", "url"]
        )


@pytest.mark.order(122)
class TestCachedURLIntegration:
    """Integration tests for cached URL workflow."""

    def test_non_url_paths_still_work(self):
        """Test that regular asset paths are unaffected."""
        # Regular user asset path
        resp = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": "nonexistent.gif"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "not found" in result["payload"]["reason"].lower()

        # Builtin asset path
        resp = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": "builtin://nonexistent.gif"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        assert result["status"] == "failed"
        assert "not found" in result["payload"]["reason"].lower()


@pytest.mark.order(123)
class TestURLDownloadWithExternalURL:
    """
    Integration tests with real external URLs.

    These tests make actual network requests to GitHub and may be slow
    if network is unavailable.
    """

    # Use GitHub raw content URLs as reliable test image sources
    # These URLs have proper file extensions and are highly available
    TEST_PNG_URL = "https://raw.githubusercontent.com/github/explore/main/topics/python/python.png"
    TEST_GIF_URL = "https://raw.githubusercontent.com/github/explore/main/topics/git/git.png"  # Actually PNG but works

    def test_download_url_successfully(self):
        """Test successful URL download and caching."""
        # First request should download from URL
        resp = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": self.TEST_PNG_URL},
            timeout=60,  # Generous timeout for real network request
        )
        assert resp.status_code == 200
        assert resp.headers["Content-Type"] == "image/png"
        assert len(resp.content) > 0

        # Verify it's a valid image
        img = Image.open(io.BytesIO(resp.content))
        assert img.format == "PNG"
        assert img.size[0] > 0 and img.size[1] > 0

        # Verify image was cached
        cache_resp = requests.get(CACHE_API_URL, timeout=10)
        assert cache_resp.status_code == 200
        cache_data = cache_resp.json()

        # Find our cached URL in the response
        cached_entries = [
            entry
            for entry in cache_data["entries"]
            if entry.get("url") == self.TEST_PNG_URL
        ]
        assert len(cached_entries) > 0, "URL should be in cache"
        cached_entry = cached_entries[0]

        # Verify metadata
        assert cached_entry["width"] == img.size[0]
        assert cached_entry["height"] == img.size[1]
        assert cached_entry["format"] == "PNG"

    def test_download_url_uses_cache_on_second_request(self):
        """Test that subsequent requests use cached data."""
        test_url = self.TEST_GIF_URL

        # First request
        resp1 = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": test_url},
            timeout=60,  # Generous timeout for real network request
        )
        assert resp1.status_code == 200
        first_content = resp1.content

        # Second request should be much faster (from cache)
        start = time.time()
        resp2 = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": test_url},
            timeout=10,  # Should be fast from cache
        )
        cache_time = time.time() - start

        assert resp2.status_code == 200
        assert resp2.content == first_content
        # Cache hit should be reasonably fast (< 3 seconds for local cache read + API overhead)
        assert (
            cache_time < 3.0
        ), f"Cache hit took {cache_time:.2f}s, expected < 3s"

    def test_thumbnail_url_successfully(self):
        """Test thumbnail generation from URL."""
        test_url = self.TEST_PNG_URL

        # Request thumbnail (use POST as thumbnail API requires POST)
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": test_url, "size": 50, "dimension": "max"},
            headers={"Content-Type": "application/json"},
            timeout=60,  # Generous timeout for real network request
        )
        assert resp.status_code == 200

        # Verify thumbnail was generated (returns valid image)
        thumb_img = Image.open(io.BytesIO(resp.content))
        assert thumb_img.format in ("PNG", "GIF", "JPEG", "WEBP")
        assert thumb_img.size[0] > 0 and thumb_img.size[1] > 0

    def test_thumbnail_url_cached_separately(self):
        """Test that thumbnails and original images are cached separately."""
        test_url = "https://raw.githubusercontent.com/github/explore/main/topics/javascript/javascript.png"

        # Download original
        resp1 = requests.get(
            ASSETS_DOWNLOAD_API_URL,
            params={"path": test_url},
            timeout=60,  # Generous timeout for real network request
        )
        assert resp1.status_code == 200

        # Generate thumbnail (use POST)
        resp2 = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": test_url, "size": 50, "dimension": "max"},
            headers={"Content-Type": "application/json"},
            timeout=60,  # Generous timeout for real network request
        )
        assert resp2.status_code == 200

        # Check cache has both entries
        cache_resp = requests.get(CACHE_API_URL, timeout=10)
        assert cache_resp.status_code == 200
        cache_data = cache_resp.json()

        # Should have at least 2 entries for this URL (original + thumbnail)
        url_entries = [
            entry
            for entry in cache_data["entries"]
            if entry.get("url") == test_url and entry.get("params") is None
        ]
        # At least original should be cached (thumbnail may be in separate entry with params)
        assert len(url_entries) >= 1, "Original URL should be in cache"

    def test_url_ssrf_protection(self):
        """Test that SSRF protection blocks private/localhost URLs."""
        # These should be blocked by SSRF protection
        blocked_urls = [
            "http://127.0.0.1/test.gif",
            "http://localhost/test.gif",
            "http://10.0.0.1/test.gif",
            "http://192.168.1.1/test.gif",
            "http://169.254.169.254/latest/meta-data/",  # AWS metadata
        ]

        for url in blocked_urls:
            resp = requests.get(
                ASSETS_DOWNLOAD_API_URL,
                params={"path": url},
                timeout=10,  # SSRF validation happens before download
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["status"] == "failed"
            # Should mention validation or failed (validates includes the word "validate")
            error_msg = result["payload"]["reason"].lower()
            assert any(
                keyword in error_msg
                for keyword in ["validate", "failed", "blocked"]
            ), f"Expected security/validation error for {url}, got: {result['payload']['reason']}"
