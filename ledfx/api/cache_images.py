"""API endpoints for image cache management."""

import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import get_image_cache

_LOGGER = logging.getLogger(__name__)


class CacheImagesEndpoint(RestEndpoint):
    """
    REST API endpoint for image cache statistics and management.

    Cache Policy:
    - Images cached indefinitely (no automatic expiration)
    - No TTL-based refresh
    - LRU eviction when size/count limits exceeded
    - Explicit refresh/clear only via API
    """

    ENDPOINT_PATH = "/api/cache/images"

    async def get(self) -> web.Response:
        """
        Get cache statistics and entries.

        Returns:
            JSON with cache stats including total size, count, and all cached entries

        Example Response:
            {
                "total_size": 52428800,
                "total_count": 45,
                "max_size": 524288000,
                "max_count": 500,
                "cache_policy": {
                    "expiration": "none",
                    "refresh": "explicit only",
                    "eviction": "LRU when limits exceeded"
                },
                "entries": [
                    {
                        "url": "https://example.com/image.gif",
                        "cached_at": "2024-01-15T10:30:00Z",
                        "last_accessed": "2024-01-20T14:20:00Z",
                        "access_count": 42,
                        "file_size": 524288,
                        "content_type": "image/gif"
                    }
                ]
            }
        """
        cache = get_image_cache()

        if not cache:
            return await self.invalid_request(
                message="Image cache not initialized",
                type="error",
            )

        stats = cache.get_stats()
        stats["cache_policy"] = {
            "expiration": "none",
            "refresh": "explicit only",
            "eviction": "LRU when limits exceeded",
        }

        return await self.bare_request_success(stats)

    async def delete(self, request: web.Request) -> web.Response:
        """
        Clear cache for specific URL or entire cache.

        Query Parameters:
            url (optional): Specific URL to clear from cache

        Returns:
            JSON with cleared_count and freed_bytes

        Examples:
            DELETE /api/cache/images?url=https://example.com/image.gif
            DELETE /api/cache/images  (clears entire cache)

        Example Response:
            {
                "status": "success",
                "cleared_count": 1,
                "freed_bytes": 524288
            }
        """
        cache = get_image_cache()

        if not cache:
            return await self.invalid_request(
                message="Image cache not initialized",
                type="error",
            )

        url = request.query.get("url")

        if url:
            # Clear specific URL
            deleted = cache.delete(url)
            if deleted:
                return await self.request_success(
                    type="success",
                    message=f"Cleared cache for URL: {url}",
                    data={"cleared_count": 1},
                )
            else:
                return await self.invalid_request(
                    message=f"URL not found in cache: {url}",
                    type="warning",
                )
        else:
            # Clear entire cache
            result = cache.clear()
            return await self.request_success(
                type="success",
                message="Entire cache cleared",
                data=result,
            )
