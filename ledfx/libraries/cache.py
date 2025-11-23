"""Image caching system for LedFx."""

import hashlib
import json
import logging
import os
from datetime import datetime
from typing import Optional

_LOGGER = logging.getLogger(__name__)


class ImageCache:
    """
    Manages cached images from remote URLs.

    Cache Policy:
    - No automatic expiration (cache and keep)
    - No TTL-based refresh
    - LRU eviction when size/count limits exceeded
    - Explicit refresh/clear only via API
    """

    def __init__(
        self,
        config_dir: str,
        max_size_mb: int = 500,
        max_items: int = 500,
    ):
        """
        Initialize image cache.

        Args:
            config_dir: LedFx configuration directory
            max_size_mb: Maximum cache size in megabytes (default 500)
            max_items: Maximum number of cached items (default 500)
        """
        self.cache_dir = os.path.join(config_dir, "cache", "images")
        os.makedirs(self.cache_dir, exist_ok=True)
        self.metadata_file = os.path.join(self.cache_dir, "metadata.json")
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_items = max_items
        self.metadata = self._load_metadata()

    def _load_metadata(self) -> dict:
        """Load cache metadata from disk."""
        if os.path.exists(self.metadata_file):
            try:
                with open(self.metadata_file) as f:
                    return json.load(f)
            except Exception as e:
                _LOGGER.warning(f"Failed to load cache metadata: {e}")
                return {"cache_entries": {}, "total_size": 0, "total_count": 0}
        return {"cache_entries": {}, "total_size": 0, "total_count": 0}

    def _save_metadata(self):
        """Save cache metadata to disk."""
        try:
            with open(self.metadata_file, "w") as f:
                json.dump(self.metadata, f, indent=2)
        except Exception as e:
            _LOGGER.error(f"Failed to save cache metadata: {e}")

    def _generate_cache_key(self, url: str) -> str:
        """Generate cache key from URL using SHA-256 hash."""
        return hashlib.sha256(url.encode("utf-8")).hexdigest()

    def _get_cache_path(self, cache_key: str, extension: str = ".jpg") -> str:
        """Get filesystem path for cached image."""
        return os.path.join(self.cache_dir, f"{cache_key}{extension}")

    def get(self, url: str) -> Optional[str]:
        """
        Get cached image if available (no expiration check).

        Args:
            url: The URL to retrieve from cache

        Returns:
            Path to cached file or None if not cached
        """
        cache_key = self._generate_cache_key(url)
        entry = self.metadata["cache_entries"].get(cache_key)

        if entry:
            cache_path = self._get_cache_path(cache_key, entry["extension"])
            if os.path.exists(cache_path):
                # Update access tracking
                entry["last_accessed"] = datetime.utcnow().isoformat()
                entry["access_count"] = entry.get("access_count", 0) + 1
                self._save_metadata()
                _LOGGER.debug(f"Cache hit for {url}")
                return cache_path

        _LOGGER.debug(f"Cache miss for {url}")
        return None

    def put(
        self,
        url: str,
        data: bytes,
        content_type: str,
        etag: Optional[str] = None,
        last_modified: Optional[str] = None,
    ):
        """
        Store image in cache.

        Args:
            url: The URL of the image
            data: Image data bytes
            content_type: MIME type of the image
            etag: Optional ETag header from server
            last_modified: Optional Last-Modified header from server
        """
        cache_key = self._generate_cache_key(url)

        # Determine extension from content type
        extension_map = {
            "image/gif": ".gif",
            "image/png": ".png",
            "image/jpeg": ".jpg",
            "image/webp": ".webp",
            "image/bmp": ".bmp",
            "image/tiff": ".tiff",
            "image/x-icon": ".ico",
        }
        extension = extension_map.get(content_type, ".jpg")

        cache_path = self._get_cache_path(cache_key, extension)

        # Write file
        try:
            with open(cache_path, "wb") as f:
                f.write(data)
        except Exception as e:
            _LOGGER.error(f"Failed to write cache file {cache_path}: {e}")
            return

        # Update metadata
        now = datetime.utcnow().isoformat()

        # Remove old entry size if updating
        if cache_key in self.metadata["cache_entries"]:
            old_size = self.metadata["cache_entries"][cache_key]["file_size"]
            self.metadata["total_size"] -= old_size
            self.metadata["total_count"] -= 1

        entry = {
            "url": url,
            "cached_at": now,
            "last_accessed": now,
            "access_count": 1,
            "file_size": len(data),
            "etag": etag,
            "last_modified": last_modified,
            "content_type": content_type,
            "extension": extension,
        }

        self.metadata["cache_entries"][cache_key] = entry
        self.metadata["total_size"] += len(data)
        self.metadata["total_count"] += 1

        self._save_metadata()
        self._enforce_limits()

        _LOGGER.info(f"Cached image from {url} ({len(data)} bytes)")

    def _enforce_limits(self):
        """Evict LRU entries if cache exceeds size or count limits."""
        evicted = False
        while (
            self.metadata["total_size"] > self.max_size_bytes
            or self.metadata["total_count"] > self.max_items
        ):
            if not self.metadata["cache_entries"]:
                break

            # Find LRU entry (least recently accessed, lowest access count as tiebreaker)
            lru_key = min(
                self.metadata["cache_entries"].items(),
                key=lambda x: (
                    x[1]["last_accessed"],
                    x[1].get("access_count", 0),
                ),
            )[0]

            _LOGGER.info(
                f"Evicting LRU cache entry: {self.metadata['cache_entries'][lru_key]['url']}"
            )
            self._delete(lru_key)
            evicted = True

        # Persist metadata changes after eviction
        if evicted:
            self._save_metadata()

    def _delete(self, cache_key: str):
        """Remove entry from cache by cache key."""
        if cache_key in self.metadata["cache_entries"]:
            entry = self.metadata["cache_entries"][cache_key]
            cache_path = self._get_cache_path(cache_key, entry["extension"])

            if os.path.exists(cache_path):
                try:
                    os.remove(cache_path)
                except Exception as e:
                    _LOGGER.warning(
                        f"Failed to delete cache file {cache_path}: {e}"
                    )

            self.metadata["total_size"] -= entry["file_size"]
            self.metadata["total_count"] -= 1
            del self.metadata["cache_entries"][cache_key]

    def delete(self, url: str) -> bool:
        """
        Remove specific URL from cache.

        Args:
            url: The URL to remove

        Returns:
            True if entry was deleted, False if not found
        """
        cache_key = self._generate_cache_key(url)
        if cache_key in self.metadata["cache_entries"]:
            _LOGGER.info(f"Deleting cached image: {url}")
            self._delete(cache_key)
            self._save_metadata()
            return True
        return False

    def clear(self) -> dict:
        """
        Clear entire cache.

        Returns:
            Dict with cleared_count and freed_bytes
        """
        cleared_count = len(self.metadata["cache_entries"])
        freed_bytes = self.metadata["total_size"]

        for cache_key in list(self.metadata["cache_entries"].keys()):
            self._delete(cache_key)

        self._save_metadata()
        _LOGGER.info(
            f"Cleared entire cache: {cleared_count} items, {freed_bytes} bytes"
        )

        return {"cleared_count": cleared_count, "freed_bytes": freed_bytes}

    def get_stats(self) -> dict:
        """
        Get cache statistics.

        Returns:
            Dict with cache statistics including entries
        """
        entries = [
            {
                "url": entry["url"],
                "cached_at": entry["cached_at"],
                "last_accessed": entry["last_accessed"],
                "access_count": entry.get("access_count", 0),
                "file_size": entry["file_size"],
                "content_type": entry.get("content_type", "unknown"),
            }
            for entry in self.metadata["cache_entries"].values()
        ]

        # Sort by access_count descending
        entries.sort(key=lambda x: x["access_count"], reverse=True)

        return {
            "total_size": self.metadata["total_size"],
            "total_count": self.metadata["total_count"],
            "max_size": self.max_size_bytes,
            "max_count": self.max_items,
            "entries": entries,
        }

    def get_cache_headers(self, url: str) -> Optional[dict]:
        """
        Get stored ETag and Last-Modified headers for conditional requests.

        Args:
            url: The URL to get headers for

        Returns:
            Dict with etag and last_modified or None if not cached
        """
        cache_key = self._generate_cache_key(url)
        entry = self.metadata["cache_entries"].get(cache_key)

        if entry:
            return {
                "etag": entry.get("etag"),
                "last_modified": entry.get("last_modified"),
            }
        return None
