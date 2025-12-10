"""
Test cases for thumbnail caching functionality.

Tests that thumbnails are properly cached with parameter-specific keys
and that cache operations work correctly with thumbnail variants.
"""

import os
from unittest.mock import patch

import pytest

from ledfx.libraries.cache import ImageCache


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_dir = os.path.join(str(tmp_path), "test_cache")
    os.makedirs(cache_dir, exist_ok=True)
    return cache_dir


@pytest.fixture
def cache(temp_cache_dir):
    """Create an ImageCache instance for testing."""
    return ImageCache(temp_cache_dir, max_size_mb=1, max_items=10)


@pytest.fixture
def sample_thumbnail_data():
    """Generate sample thumbnail data."""
    return b"fake_thumbnail_data_png_128x128"


class TestThumbnailCaching:
    """Test thumbnail caching with parameterized keys."""

    def test_cache_key_with_params(self, cache):
        """Test cache key generation includes parameters."""
        url = "asset://test.png"
        params = {"size": 128, "dimension": "max", "animated": True}

        key1 = cache._generate_cache_key(url, params)
        key2 = cache._generate_cache_key(url, params)
        key3 = cache._generate_cache_key(url, None)

        # Same URL and params should generate same key
        assert key1 == key2

        # Same URL but no params should generate different key
        assert key1 != key3

    def test_cache_key_different_params(self, cache):
        """Test different parameters generate different cache keys."""
        url = "asset://test.png"
        params1 = {"size": 128, "dimension": "max", "animated": True}
        params2 = {"size": 256, "dimension": "max", "animated": True}
        params3 = {"size": 128, "dimension": "width", "animated": True}
        params4 = {"size": 128, "dimension": "max", "animated": False}

        key1 = cache._generate_cache_key(url, params1)
        key2 = cache._generate_cache_key(url, params2)
        key3 = cache._generate_cache_key(url, params3)
        key4 = cache._generate_cache_key(url, params4)

        # All different params should generate different keys
        assert key1 != key2  # Different size
        assert key1 != key3  # Different dimension
        assert key1 != key4  # Different animated
        assert key2 != key3
        assert key2 != key4
        assert key3 != key4

    def test_put_and_get_with_params(self, cache, sample_thumbnail_data):
        """Test storing and retrieving thumbnails with parameters."""
        url = "asset://test.png"
        params = {"size": 128, "dimension": "max", "animated": True}

        cache.put(url, sample_thumbnail_data, "image/png", params=params)

        # Should retrieve with same params
        cached_path = cache.get(url, params)
        assert cached_path is not None
        assert os.path.exists(cached_path)

        # Verify data
        with open(cached_path, "rb") as f:
            assert f.read() == sample_thumbnail_data

    def test_get_with_different_params_misses(
        self, cache, sample_thumbnail_data
    ):
        """Test cache miss when retrieving with different parameters."""
        url = "asset://test.png"
        params1 = {"size": 128, "dimension": "max", "animated": True}
        params2 = {"size": 256, "dimension": "max", "animated": True}

        cache.put(url, sample_thumbnail_data, "image/png", params=params1)

        # Should hit with same params
        assert cache.get(url, params1) is not None

        # Should miss with different params
        assert cache.get(url, params2) is None

    def test_multiple_thumbnail_variants(self, cache):
        """Test caching multiple thumbnail variants of same asset."""
        url = "asset://test.png"
        data1 = b"thumbnail_128px"
        data2 = b"thumbnail_256px"
        data3 = b"thumbnail_64px"

        params1 = {"size": 128, "dimension": "max", "animated": True}
        params2 = {"size": 256, "dimension": "max", "animated": True}
        params3 = {"size": 64, "dimension": "max", "animated": True}

        # Cache three different sizes
        cache.put(url, data1, "image/png", params=params1)
        cache.put(url, data2, "image/png", params=params2)
        cache.put(url, data3, "image/png", params=params3)

        # All three should be retrievable independently
        path1 = cache.get(url, params1)
        path2 = cache.get(url, params2)
        path3 = cache.get(url, params3)

        assert path1 is not None
        assert path2 is not None
        assert path3 is not None

        # Verify data
        with open(path1, "rb") as f:
            assert f.read() == data1
        with open(path2, "rb") as f:
            assert f.read() == data2
        with open(path3, "rb") as f:
            assert f.read() == data3

    def test_delete_specific_variant(self, cache):
        """Test deleting a specific thumbnail variant."""
        url = "asset://test.png"
        data1 = b"thumbnail_128px"
        data2 = b"thumbnail_256px"

        params1 = {"size": 128, "dimension": "max", "animated": True}
        params2 = {"size": 256, "dimension": "max", "animated": True}

        # Cache two variants
        cache.put(url, data1, "image/png", params=params1)
        cache.put(url, data2, "image/png", params=params2)

        # Delete one variant
        deleted = cache.delete(url, params1)
        assert deleted is True

        # First should be gone, second should remain
        assert cache.get(url, params1) is None
        assert cache.get(url, params2) is not None

    def test_delete_all_for_url(self, cache):
        """Test deleting all thumbnail variants for a URL."""
        url = "asset://test.png"
        data1 = b"thumbnail_128px"
        data2 = b"thumbnail_256px"
        data3 = b"thumbnail_64px"

        params1 = {"size": 128, "dimension": "max", "animated": True}
        params2 = {"size": 256, "dimension": "max", "animated": True}
        params3 = {"size": 64, "dimension": "max", "animated": True}

        # Cache three variants
        cache.put(url, data1, "image/png", params=params1)
        cache.put(url, data2, "image/png", params=params2)
        cache.put(url, data3, "image/png", params=params3)

        # Delete all variants
        cleared_count = cache.delete_all_for_url(url)
        assert cleared_count == 3

        # All should be gone
        assert cache.get(url, params1) is None
        assert cache.get(url, params2) is None
        assert cache.get(url, params3) is None

    def test_delete_all_for_url_with_different_urls(self, cache):
        """Test delete_all_for_url only deletes matching URL."""
        url1 = "asset://test1.png"
        url2 = "asset://test2.png"
        data = b"thumbnail_data"

        params1 = {"size": 128, "dimension": "max", "animated": True}
        params2 = {"size": 256, "dimension": "max", "animated": True}

        # Cache variants for two different URLs
        cache.put(url1, data, "image/png", params=params1)
        cache.put(url1, data, "image/png", params=params2)
        cache.put(url2, data, "image/png", params=params1)

        # Delete all variants of url1
        cleared_count = cache.delete_all_for_url(url1)
        assert cleared_count == 2

        # url1 variants should be gone
        assert cache.get(url1, params1) is None
        assert cache.get(url1, params2) is None

        # url2 should remain
        assert cache.get(url2, params1) is not None

    def test_metadata_stores_params(self, cache, sample_thumbnail_data):
        """Test that metadata correctly stores params."""
        url = "asset://test.png"
        params = {"size": 128, "dimension": "max", "animated": True}

        cache.put(url, sample_thumbnail_data, "image/png", params=params)

        cache_key = cache._generate_cache_key(url, params)
        entry = cache.metadata["cache_entries"][cache_key]

        assert entry["params"] == params
        assert entry["url"] == url

    def test_lru_eviction_with_params(self, cache):
        """Test LRU eviction works with parameterized cache keys."""
        # Create cache with very small limits (set high size limit to test item limit)
        small_cache = ImageCache(cache.cache_dir, max_size_mb=10, max_items=3)

        url = "asset://test.png"
        data = b"x" * 100  # Small data

        # Add 4 entries (exceeds max_items=3)
        params1 = {"size": 64, "dimension": "max", "animated": True}
        params2 = {"size": 128, "dimension": "max", "animated": True}
        params3 = {"size": 256, "dimension": "max", "animated": True}
        params4 = {"size": 512, "dimension": "max", "animated": True}

        small_cache.put(url, data, "image/png", params=params1)
        small_cache.put(url, data, "image/png", params=params2)
        small_cache.put(url, data, "image/png", params=params3)
        small_cache.put(url, data, "image/png", params=params4)

        # Should have evicted LRU entry (params1)
        assert small_cache.metadata["total_count"] == 3
        assert small_cache.get(url, params1) is None
        assert small_cache.get(url, params2) is not None
        assert small_cache.get(url, params3) is not None
        assert small_cache.get(url, params4) is not None

    def test_get_cache_headers_with_params(self, cache, sample_thumbnail_data):
        """Test get_cache_headers works with parameters."""
        url = "asset://test.png"
        params = {"size": 128, "dimension": "max", "animated": True}
        etag = "test-etag"
        last_modified = "Wed, 21 Oct 2015 07:28:00 GMT"

        cache.put(
            url,
            sample_thumbnail_data,
            "image/png",
            etag=etag,
            last_modified=last_modified,
            params=params,
        )

        headers = cache.get_cache_headers(url, params)
        assert headers is not None
        assert headers["etag"] == etag
        assert headers["last_modified"] == last_modified

        # Different params should return None
        different_params = {"size": 256, "dimension": "max", "animated": True}
        assert cache.get_cache_headers(url, different_params) is None
