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
            Bare JSON response with cache stats (total_size, total_count, entries)
            or error response if cache not initialized.
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
            url (optional): Specific URL to clear. If omitted, clears entire cache.
            all_variants (optional): If "true" and url provided, clears all cache entries
                                    for that URL (including thumbnails with different params).

        Returns:
            Success response with cleared_count (and freed_bytes for full clear),
            or error response if URL not found or cache not initialized.
        """
        cache = get_image_cache()

        if not cache:
            return await self.invalid_request(
                message="Image cache not initialized",
                type="error",
            )

        url = request.query.get("url")
        all_variants = request.query.get("all_variants", "false").lower() in (
            "true",
            "1",
            "yes",
        )

        if url:
            if all_variants:
                # Clear all entries for this URL (all thumbnail variants)
                cleared_count = cache.delete_all_for_url(url)
                if cleared_count > 0:
                    return await self.request_success(
                        type="success",
                        message=f"Cleared {cleared_count} cache entries for URL: {url}",
                        data={"cleared_count": cleared_count},
                    )
                else:
                    return await self.invalid_request(
                        message=f"URL not found in cache: {url}",
                        type="warning",
                    )
            else:
                # Clear specific URL (without params)
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
