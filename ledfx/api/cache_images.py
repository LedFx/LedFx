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
            return web.json_response(
                {
                    "status": "error",
                    "message": "Image cache not initialized",
                },
                status=200,
            )

        stats = cache.get_stats()
        stats["cache_policy"] = {
            "expiration": "none",
            "refresh": "explicit only",
            "eviction": "LRU when limits exceeded",
        }

        return web.json_response(stats, status=200)

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
            return web.json_response(
                {
                    "status": "error",
                    "message": "Image cache not initialized",
                },
                status=200,
            )

        url = request.query.get("url")

        if url:
            # Clear specific URL
            deleted = cache.delete(url)
            if deleted:
                return web.json_response(
                    {
                        "status": "success",
                        "message": f"Cleared cache for URL: {url}",
                        "cleared_count": 1,
                    },
                    status=200,
                )
            else:
                return web.json_response(
                    {
                        "status": "error",
                        "message": f"URL not found in cache: {url}",
                        "cleared_count": 0,
                    },
                    status=200,
                )
        else:
            # Clear entire cache
            result = cache.clear()
            return web.json_response(
                {
                    "status": "success",
                    "message": "Entire cache cleared",
                    **result,
                },
                status=200,
            )


class CacheRefreshEndpoint(RestEndpoint):
    """REST API endpoint for explicit cache refresh."""

    ENDPOINT_PATH = "/api/cache/images/refresh"

    async def post(self, body) -> web.Response:
        """
        Clear a cached image to force re-download on next access.

        This endpoint removes the specified URL from the cache, causing the image
        to be re-downloaded from the origin server the next time it is requested
        via open_image() or open_gif().

        Request Body:
            {
                "url": "https://example.com/image.gif"
            }

        Returns:
            JSON with the cleared URL

        Example Response:
            {
                "status": "success",
                "message": "Cache entry cleared. Image will be re-downloaded on next access.",
                "url": "https://example.com/image.gif"
            }
        """
        cache = get_image_cache()

        if not cache:
            return web.json_response(
                {
                    "status": "error",
                    "message": "Image cache not initialized",
                },
                status=200,
            )

        if not body or not isinstance(body, dict):
            return web.json_response(
                {"status": "error", "message": "Invalid JSON in request body"},
                status=200,
            )

        url = body.get("url")
        if not url:
            return web.json_response(
                {
                    "status": "error",
                    "message": "Missing 'url' in request body",
                },
                status=200,
            )

        # Clear the URL from cache to force refresh on next access
        deleted = cache.delete(url)

        if deleted:
            return web.json_response(
                {
                    "status": "success",
                    "message": "Cache entry cleared. Image will be re-downloaded on next access.",
                    "url": url,
                },
                status=200,
            )
        else:
            return web.json_response(
                {
                    "status": "success",
                    "message": "URL was not in cache (no action needed).",
                    "url": url,
                },
                status=200,
            )
