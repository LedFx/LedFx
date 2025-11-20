"""
Test cases for image cache implementation.

Tests cache operations: hit/miss, LRU eviction, refresh, clear, persistence, metadata tracking.
"""

import io
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from ledfx.libraries.cache import ImageCache
from ledfx.utils import get_image_cache, init_image_cache, open_gif, open_image


@pytest.fixture
def temp_cache_dir(tmp_path):
    """Create a temporary cache directory."""
    cache_dir = tmp_path / "test_cache"
    cache_dir.mkdir()
    return str(cache_dir)


@pytest.fixture
def cache(temp_cache_dir):
    """Create an ImageCache instance for testing."""
    return ImageCache(temp_cache_dir, max_size_mb=1, max_items=5)


@pytest.fixture
def sample_image_data():
    """Generate sample image data."""
    img = Image.new("RGB", (100, 100), color="red")
    img_bytes = io.BytesIO()
    img.save(img_bytes, "PNG")
    return img_bytes.getvalue()


class TestCacheBasicOperations:
    """Test basic cache operations."""

    def test_cache_initialization(self, temp_cache_dir):
        """Test cache initializes correctly."""
        cache = ImageCache(temp_cache_dir, max_size_mb=10, max_items=100)
        assert cache.max_size_bytes == 10 * 1024 * 1024
        assert cache.max_items == 100
        assert cache.metadata["total_size"] == 0
        assert cache.metadata["total_count"] == 0

    def test_cache_directory_created(self, temp_cache_dir):
        """Test cache directory is created if it doesn't exist."""
        # Create cache - this should create the directory
        cache = ImageCache(temp_cache_dir, max_size_mb=10, max_items=100)
        cache_dir = Path(temp_cache_dir) / "cache" / "images"
        assert cache_dir.exists()

    def test_cache_miss(self, cache):
        """Test cache miss returns None."""
        result = cache.get("https://example.com/notcached.png")
        assert result is None

    def test_cache_put_and_get(self, cache, sample_image_data):
        """Test putting and getting an image from cache."""
        url = "https://example.com/test.png"
        cache.put(url, sample_image_data, "image/png")

        cached_path = cache.get(url)
        assert cached_path is not None
        assert cached_path.exists()

        # Verify cached file contains correct data
        with open(cached_path, "rb") as f:
            assert f.read() == sample_image_data

    def test_metadata_tracking(self, cache, sample_image_data):
        """Test metadata is tracked correctly."""
        url = "https://example.com/test.png"
        cache.put(url, sample_image_data, "image/png")

        entry_key = cache._generate_cache_key(url)
        assert entry_key in cache.metadata["cache_entries"]

        entry = cache.metadata["cache_entries"][entry_key]
        assert entry["url"] == url
        assert entry["file_size"] == len(sample_image_data)
        assert entry["content_type"] == "image/png"
        assert "cached_at" in entry
        assert "last_accessed" in entry
        assert entry["access_count"] == 1


class TestCacheAccessTracking:
    """Test cache access tracking."""

    def test_access_count_increments(self, cache, sample_image_data):
        """Test access_count increments on each cache hit."""
        url = "https://example.com/test.png"
        cache.put(url, sample_image_data, "image/png")

        # Access multiple times
        for i in range(5):
            cache.get(url)

        entry_key = cache._generate_cache_key(url)
        entry = cache.metadata["cache_entries"][entry_key]
        assert entry["access_count"] == 6  # 1 from put + 5 gets

    def test_last_accessed_updates(self, cache, sample_image_data):
        """Test last_accessed timestamp updates on cache hit."""
        import time

        url = "https://example.com/test.png"
        cache.put(url, sample_image_data, "image/png")

        entry_key = cache._generate_cache_key(url)
        first_access = cache.metadata["cache_entries"][entry_key][
            "last_accessed"
        ]

        time.sleep(0.01)  # Small delay
        cache.get(url)

        second_access = cache.metadata["cache_entries"][entry_key][
            "last_accessed"
        ]
        assert second_access > first_access


class TestLRUEviction:
    """Test LRU eviction when cache limits exceeded."""

    def test_eviction_by_count_limit(self, cache, sample_image_data):
        """Test LRU eviction when max_items exceeded."""
        # Cache is configured for max 5 items
        urls = [f"https://example.com/image{i}.png" for i in range(6)]

        # Add 6 items (should evict 1)
        for url in urls:
            cache.put(url, sample_image_data, "image/png")

        assert cache.metadata["total_count"] == 5
        # First URL should be evicted (LRU)
        assert cache.get(urls[0]) is None
        # Others should still be cached
        for url in urls[1:]:
            assert cache.get(url) is not None

    def test_eviction_by_size_limit(self, cache):
        """Test LRU eviction when max_size_bytes exceeded."""
        # Create large image data (500KB each)
        large_data = b"x" * (500 * 1024)

        urls = [f"https://example.com/large{i}.png" for i in range(3)]

        # Add 3 x 500KB = 1.5MB (should exceed 1MB limit)
        for url in urls:
            cache.put(url, large_data, "image/png")

        # Should have evicted to stay under limit
        assert cache.metadata["total_size"] <= cache.max_size_bytes

    def test_lru_evicts_least_recently_used(self, cache, sample_image_data):
        """Test that LRU evicts least recently accessed item."""
        import time

        urls = [f"https://example.com/image{i}.png" for i in range(6)]

        # Add 5 items (at limit)
        for url in urls[:5]:
            cache.put(url, sample_image_data, "image/png")
            time.sleep(0.01)

        # Access first item to make it more recent
        cache.get(urls[0])

        # Add 6th item (should evict urls[1], the LRU)
        cache.put(urls[5], sample_image_data, "image/png")

        assert cache.get(urls[0]) is not None  # Should still be cached
        assert cache.get(urls[1]) is None  # Should be evicted


class TestCacheDelete:
    """Test cache deletion operations."""

    def test_delete_specific_url(self, cache, sample_image_data):
        """Test deleting specific URL from cache."""
        url = "https://example.com/test.png"
        cache.put(url, sample_image_data, "image/png")

        assert cache.delete(url) is True
        assert cache.get(url) is None
        assert cache.metadata["total_count"] == 0

    def test_delete_nonexistent_url(self, cache):
        """Test deleting URL not in cache returns False."""
        result = cache.delete("https://example.com/notcached.png")
        assert result is False

    def test_clear_entire_cache(self, cache, sample_image_data):
        """Test clearing entire cache."""
        urls = [f"https://example.com/image{i}.png" for i in range(3)]

        for url in urls:
            cache.put(url, sample_image_data, "image/png")

        result = cache.clear()
        assert result["cleared_count"] == 3
        assert result["freed_bytes"] > 0
        assert cache.metadata["total_count"] == 0
        assert cache.metadata["total_size"] == 0

        for url in urls:
            assert cache.get(url) is None


class TestCachePersistence:
    """Test cache persistence across instances."""

    def test_metadata_persists(self, temp_cache_dir, sample_image_data):
        """Test metadata persists between cache instances."""
        url = "https://example.com/persist.png"

        # Create cache and add item
        cache1 = ImageCache(temp_cache_dir, max_size_mb=1, max_items=5)
        cache1.put(url, sample_image_data, "image/png")
        entry_key = cache1._generate_cache_key(url)
        original_cached_at = cache1.metadata["cache_entries"][entry_key][
            "cached_at"
        ]

        # Create new cache instance (simulates restart)
        cache2 = ImageCache(temp_cache_dir, max_size_mb=1, max_items=5)

        # Should load existing metadata
        assert cache2.metadata["total_count"] == 1
        assert entry_key in cache2.metadata["cache_entries"]
        assert (
            cache2.metadata["cache_entries"][entry_key]["cached_at"]
            == original_cached_at
        )

        # Should be able to retrieve cached file
        cached_path = cache2.get(url)
        assert cached_path is not None


class TestCacheStatistics:
    """Test cache statistics retrieval."""

    def test_get_stats(self, cache, sample_image_data):
        """Test getting cache statistics."""
        urls = [f"https://example.com/image{i}.png" for i in range(3)]

        for url in urls:
            cache.put(url, sample_image_data, "image/png")

        stats = cache.get_stats()
        assert stats["total_count"] == 3
        assert stats["total_size"] > 0
        assert stats["max_size"] == cache.max_size_bytes
        assert stats["max_count"] == cache.max_items
        assert len(stats["entries"]) == 3

    def test_stats_entries_sorted_by_access_count(
        self, cache, sample_image_data
    ):
        """Test stats entries are sorted by access_count descending."""
        url1 = "https://example.com/image1.png"
        url2 = "https://example.com/image2.png"

        cache.put(url1, sample_image_data, "image/png")
        cache.put(url2, sample_image_data, "image/png")

        # Access url2 multiple times
        for _ in range(5):
            cache.get(url2)

        stats = cache.get_stats()
        # url2 should be first (highest access_count)
        assert stats["entries"][0]["url"] == url2
        assert (
            stats["entries"][0]["access_count"]
            > stats["entries"][1]["access_count"]
        )


class TestCacheHeaders:
    """Test cache header storage and retrieval."""

    def test_store_etag_and_last_modified(self, cache, sample_image_data):
        """Test storing ETag and Last-Modified headers."""
        url = "https://example.com/test.png"
        cache.put(
            url,
            sample_image_data,
            "image/png",
            etag='"abc123"',
            last_modified="Mon, 01 Jan 2024 00:00:00 GMT",
        )

        headers = cache.get_cache_headers(url)
        assert headers is not None
        assert headers["etag"] == '"abc123"'
        assert headers["last_modified"] == "Mon, 01 Jan 2024 00:00:00 GMT"

    def test_get_headers_for_uncached_url(self, cache):
        """Test getting headers for uncached URL returns None."""
        headers = cache.get_cache_headers("https://example.com/notcached.png")
        assert headers is None


class TestContentTypeExtensionMapping:
    """Test content type to extension mapping."""

    def test_extension_from_content_type(self, cache, sample_image_data):
        """Test correct extension is used based on content type."""
        test_cases = [
            ("image/gif", ".gif"),
            ("image/png", ".png"),
            ("image/jpeg", ".jpg"),
            ("image/webp", ".webp"),
            ("image/bmp", ".bmp"),
            ("image/tiff", ".tiff"),
            ("image/x-icon", ".ico"),
            ("image/unknown", ".jpg"),  # Default fallback
        ]

        for content_type, expected_ext in test_cases:
            url = f"https://example.com/test{expected_ext}"
            cache.put(url, sample_image_data, content_type)

            entry_key = cache._generate_cache_key(url)
            entry = cache.metadata["cache_entries"][entry_key]
            assert (
                entry["extension"] == expected_ext
            ), f"Failed for {content_type}"


# Test Scenarios Documentation
"""
CACHE TEST SCENARIOS:

BASIC OPERATIONS:
1. Cache initialization with correct parameters
2. Cache miss returns None
3. Cache hit returns correct cached file
4. Metadata tracked for all cached items

ACCESS TRACKING:
1. access_count increments on each get()
2. last_accessed timestamp updates on each get()
3. cached_at timestamp set on initial put()

LRU EVICTION:
1. Eviction when max_items exceeded (count limit)
2. Eviction when max_size_bytes exceeded (size limit)
3. Least recently accessed item evicted first
4. Items with higher access_count retained longer

DELETION:
1. Delete specific URL removes from cache
2. Delete nonexistent URL returns False
3. Clear all removes all entries
4. Metadata updated after deletion

PERSISTENCE:
1. Metadata saved to disk after changes
2. Metadata loaded from disk on init
3. Cached files survive restart
4. Access tracking persists across restarts

STATISTICS:
1. get_stats() returns correct totals
2. Entries sorted by access_count descending
3. All entry fields included in stats

HEADERS:
1. ETag and Last-Modified stored
2. Headers retrievable for cached URLs
3. Headers None for uncached URLs

EXTENSION MAPPING:
1. Correct extension from content type
2. Default fallback for unknown types
3. Files saved with correct extension

FALLBACK ON ERROR:
1. Corrupted cached files trigger re-download (open_image)
2. Corrupted cached files trigger re-download (open_gif)
3. Invalid cached files are deleted from cache
4. Fresh download succeeds after cache corruption
"""


class TestCacheFallbackOnError:
    """Test cache fallback behavior when cached files are corrupted."""

    @patch("ledfx.utils.build_browser_request")
    @patch("urllib.request.urlopen")
    def test_corrupt_cache_fallback_open_image(
        self,
        mock_urlopen,
        mock_build_request,
        sample_image_data,
        tmp_path,
    ):
        """Test that open_image falls back to download if cached file is corrupted."""

        # Initialize global cache
        init_image_cache(str(tmp_path), max_size_mb=1, max_items=5)
        cache = get_image_cache()

        url = "https://example.com/test.png"

        # First, cache a valid image using the global cache
        cache.put(url, sample_image_data, "image/png")
        cache_key = cache._generate_cache_key(url)
        cached_file = cache._get_cache_path(cache_key, ".png")

        # Corrupt the cached file by writing garbage
        with open(cached_file, "wb") as f:
            f.write(b"CORRUPT DATA NOT AN IMAGE")

        # Mock the download for fallback
        mock_build_request.return_value = MagicMock()
        mock_response = MagicMock()
        headers_dict = {
            "Content-Length": str(len(sample_image_data)),
            "Content-Type": "image/png",
        }
        mock_response.headers.get = lambda key, default=None: headers_dict.get(
            key, default
        )
        mock_response.read.return_value = sample_image_data
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_urlopen.return_value = mock_response

        # Try to open - should detect corruption and re-download
        result = open_image(url)

        # Should succeed by downloading fresh copy
        assert result is not None

        # Verify download was attempted (mock was called)
        assert mock_urlopen.called

    @patch("ledfx.utils.build_browser_request")
    @patch("urllib.request.urlopen")
    def test_corrupt_cache_fallback_open_gif(
        self,
        mock_urlopen,
        mock_build_request,
        sample_image_data,
        tmp_path,
    ):
        """Test that open_gif falls back to download if cached file is corrupted."""

        # Initialize global cache
        init_image_cache(str(tmp_path), max_size_mb=1, max_items=5)
        cache = get_image_cache()

        url = "https://example.com/test.gif"

        # First, cache a valid image using the global cache
        cache.put(url, sample_image_data, "image/gif")
        cache_key = cache._generate_cache_key(url)
        cached_file = cache._get_cache_path(cache_key, ".gif")

        # Corrupt the cached file
        with open(cached_file, "wb") as f:
            f.write(b"CORRUPT GIF DATA")

        # Mock the download for fallback
        mock_build_request.return_value = MagicMock()
        mock_response = MagicMock()
        headers_dict = {
            "Content-Length": str(len(sample_image_data)),
            "Content-Type": "image/gif",
        }
        mock_response.headers.get = lambda key, default=None: headers_dict.get(
            key, default
        )
        mock_response.read.return_value = sample_image_data
        mock_response.__enter__.return_value = mock_response
        mock_response.__exit__.return_value = False
        mock_urlopen.return_value = mock_response

        # Try to open - should detect corruption and re-download
        result = open_gif(url)

        # Should succeed by downloading fresh copy
        assert result is not None

        # Verify download was attempted
        assert mock_urlopen.called
