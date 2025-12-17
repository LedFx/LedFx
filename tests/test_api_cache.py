"""
Integration tests for cache API endpoints.

Tests cache management APIs: statistics retrieval, cache refresh, and cache clearing.
"""

import io

import pytest
import requests
from PIL import Image

from tests.test_utilities.consts import BASE_PORT

# Test URLs - Use 127.0.0.1 instead of localhost to avoid Windows DNS resolution delay
CACHE_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/cache/images"
CACHE_REFRESH_API_URL = (
    f"http://127.0.0.1:{BASE_PORT}/api/cache/images/refresh"
)
ASSETS_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/assets"
ASSETS_THUMBNAIL_API_URL = f"http://127.0.0.1:{BASE_PORT}/api/assets/thumbnail"


@pytest.fixture
def sample_png_bytes():
    """Generate sample PNG image bytes."""
    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, "PNG")
    return img_bytes.getvalue()


@pytest.mark.order(100)
class TestCacheRefreshAPI:
    """Test the cache refresh endpoint."""

    def test_refresh_single_entry(self, sample_png_bytes):
        """Test refreshing a single cache entry."""
        # Upload an asset
        files = {
            "file": (
                "refresh_test.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "refresh_test.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Generate thumbnail to populate cache
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "refresh_test.png", "size": 64},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200

        # Refresh the cache entry (single variant)
        resp = requests.post(
            CACHE_REFRESH_API_URL,
            json={"url": "asset://refresh_test.png", "all_variants": False},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        # Bare response returns data directly (no status/payload wrapping)
        assert "refreshed" in result
        assert isinstance(result["refreshed"], bool)

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "refresh_test.png"}, timeout=5
        )

    def test_refresh_all_variants(self, sample_png_bytes):
        """Test refreshing all cache variants for a URL."""
        # Upload an asset
        files = {
            "file": (
                "refresh_variants.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "refresh_variants.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Generate multiple thumbnail sizes to create variants
        for size in [64, 128, 256]:
            resp = requests.post(
                ASSETS_THUMBNAIL_API_URL,
                json={"path": "refresh_variants.png", "size": size},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            assert resp.status_code == 200

        # Refresh all variants
        resp = requests.post(
            CACHE_REFRESH_API_URL,
            json={"url": "asset://refresh_variants.png", "all_variants": True},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        # Bare response returns data directly (no status/payload wrapping)
        assert "cleared_count" in result
        assert result["cleared_count"] >= 3  # At least 3 variants

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "refresh_variants.png"}, timeout=5
        )

    def test_refresh_missing_url(self):
        """Test that missing URL parameter is rejected."""
        resp = requests.post(
            CACHE_REFRESH_API_URL,
            json={"all_variants": False},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        # Error responses still use status/payload format
        assert result["status"] == "failed"
        assert "url" in result["payload"]["reason"].lower()

    def test_refresh_uncached_url(self):
        """Test refreshing a URL that was never cached."""
        resp = requests.post(
            CACHE_REFRESH_API_URL,
            json={
                "url": "asset://never_existed.png",
                "all_variants": False,
            },
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        # Bare response returns data directly
        assert "refreshed" in result
        assert result["refreshed"] is False  # URL was not cached

    def test_refresh_all_variants_boolean_validation(self):
        """Test that all_variants parameter only accepts boolean values."""
        # Test valid boolean values
        for valid_value in [True, False]:
            resp = requests.post(
                CACHE_REFRESH_API_URL,
                json={
                    "url": "asset://test.png",
                    "all_variants": valid_value,
                },
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            assert resp.status_code == 200
            # Bare response should return data directly
            result = resp.json()
            assert "cleared_count" in result or "refreshed" in result

        # Test invalid types - strings, integers, etc.
        for invalid_value in ["true", "false", "1", "0", 1, 0, {}, [], None]:
            resp = requests.post(
                CACHE_REFRESH_API_URL,
                json={
                    "url": "asset://test.png",
                    "all_variants": invalid_value,
                },
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            assert resp.status_code == 200
            result = resp.json()
            assert result["status"] == "failed"
            assert "invalid" in result["payload"]["reason"].lower()
            assert "boolean" in result["payload"]["reason"].lower()


@pytest.mark.order(101)
class TestCacheDeleteAPI:
    """Test the cache delete endpoint."""

    def test_delete_single_entry(self, sample_png_bytes):
        """Test deleting a single cache entry via DELETE method."""
        # Upload an asset
        files = {
            "file": (
                "delete_test.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "delete_test.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Generate thumbnail to populate cache
        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "delete_test.png", "size": 64},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200

        # Delete the cache entry
        resp = requests.delete(
            CACHE_API_URL,
            params={"url": "asset://delete_test.png"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        # Bare response returns data directly
        assert "deleted" in result
        assert "cleared_count" in result

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "delete_test.png"}, timeout=5
        )

    def test_delete_all_variants(self, sample_png_bytes):
        """Test deleting all cache variants via query parameter."""
        # Upload an asset
        files = {
            "file": (
                "delete_variants.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "delete_variants.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Generate multiple thumbnail sizes
        for size in [64, 128]:
            resp = requests.post(
                ASSETS_THUMBNAIL_API_URL,
                json={"path": "delete_variants.png", "size": size},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            assert resp.status_code == 200

        # Delete all variants using query parameter
        resp = requests.delete(
            CACHE_API_URL,
            params={
                "url": "asset://delete_variants.png",
                "all_variants": "true",
            },
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        # Bare response returns data directly
        assert "cleared_count" in result
        assert result["cleared_count"] >= 2

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "delete_variants.png"}, timeout=5
        )

    def test_delete_query_param_boolean_parsing(self, sample_png_bytes):
        """Test that all_variants query parameter accepts true/false strings."""
        # Upload an asset
        files = {
            "file": (
                "query_bool.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "query_bool.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Generate thumbnails
        for size in [64, 128]:
            resp = requests.post(
                ASSETS_THUMBNAIL_API_URL,
                json={"path": "query_bool.png", "size": size},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            assert resp.status_code == 200

        # Test "true" (case-insensitive) - should delete all variants
        resp = requests.delete(
            CACHE_API_URL,
            params={"url": "asset://query_bool.png", "all_variants": "True"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        # Bare response returns data directly
        assert "cleared_count" in result

        # Re-generate and test "false" - should delete single entry
        for size in [64, 128]:
            resp = requests.post(
                ASSETS_THUMBNAIL_API_URL,
                json={"path": "query_bool.png", "size": size},
                headers={"Content-Type": "application/json"},
                timeout=5,
            )
            assert resp.status_code == 200

        resp = requests.delete(
            CACHE_API_URL,
            params={"url": "asset://query_bool.png", "all_variants": "false"},
            timeout=5,
        )
        assert resp.status_code == 200
        result = resp.json()
        # Bare response returns data directly
        assert "deleted" in result
        assert "cleared_count" in result

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "query_bool.png"}, timeout=5
        )

    def test_clear_entire_cache(self):
        """Test clearing the entire cache by omitting URL parameter."""
        resp = requests.delete(CACHE_API_URL, timeout=5)
        assert resp.status_code == 200
        result = resp.json()
        # Bare response returns cache.clear() data directly
        assert "cleared_count" in result
        assert "freed_bytes" in result


@pytest.mark.order(102)
class TestCacheStatsAPI:
    """Test the cache statistics endpoint."""

    def test_get_stats_structure(self):
        """Test that cache stats have the expected structure."""
        resp = requests.get(CACHE_API_URL, timeout=5)
        assert resp.status_code == 200
        stats = resp.json()

        # Check required fields
        assert "total_size" in stats
        assert "total_count" in stats
        assert "entries" in stats
        assert "cache_policy" in stats

        # Check cache policy structure
        policy = stats["cache_policy"]
        assert "expiration" in policy
        assert "refresh" in policy
        assert "eviction" in policy

    def test_get_stats_excludes_thumbnails(self, sample_png_bytes):
        """Test that thumbnail cache entries are excluded from stats."""
        # Upload an asset and generate thumbnail
        files = {
            "file": (
                "stats_test.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "stats_test.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        resp = requests.post(
            ASSETS_THUMBNAIL_API_URL,
            json={"path": "stats_test.png", "size": 64},
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        assert resp.status_code == 200

        # Get stats
        resp = requests.get(CACHE_API_URL, timeout=5)
        assert resp.status_code == 200
        stats = resp.json()

        # Verify no asset:// URLs in entries
        for entry in stats["entries"]:
            assert not entry["url"].startswith("asset://")

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "stats_test.png"}, timeout=5
        )

    def test_get_stats_includes_image_metadata(self, sample_png_bytes):
        """Test that cache stats include image metadata fields."""
        # Upload an asset that will get cached
        files = {
            "file": (
                "metadata_test.png",
                io.BytesIO(sample_png_bytes),
                "image/png",
            )
        }
        data = {"path": "metadata_test.png"}
        resp = requests.post(ASSETS_API_URL, files=files, data=data, timeout=5)
        assert resp.status_code == 200

        # Download the asset to trigger caching (if remote)
        # Note: User assets may not trigger remote cache, so this test
        # is more relevant for actual remote URLs in production
        resp = requests.get(CACHE_API_URL, timeout=5)
        assert resp.status_code == 200
        stats = resp.json()

        # If we have any cached entries, verify they have metadata
        if stats["entries"]:
            for entry in stats["entries"]:
                # Required fields from caching
                assert "url" in entry
                assert "cached_at" in entry
                assert "last_accessed" in entry
                assert "access_count" in entry
                assert "file_size" in entry
                assert "content_type" in entry

                # New image metadata fields
                assert "width" in entry
                assert "height" in entry
                assert "format" in entry
                assert "n_frames" in entry
                assert "is_animated" in entry

                # Verify types
                assert isinstance(entry["width"], int)
                assert isinstance(entry["height"], int)
                assert isinstance(entry["n_frames"], int)
                assert isinstance(entry["is_animated"], bool)

        # Cleanup
        requests.delete(
            ASSETS_API_URL, params={"path": "metadata_test.png"}, timeout=5
        )
