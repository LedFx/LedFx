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
            Bare response with cache operation results:
            - url + all_variants="true": {"cleared_count": int}
            - url + all_variants="false": {"deleted": bool, "cleared_count": int}
            - no url (clear all): {"cleared_count": int, "freed_bytes": int}

            Error responses use standard format with status/payload for validation errors.
        """
        cache = get_image_cache()

        if not cache:
            return await self.invalid_request(
                message="Image cache not initialized",
                type="error",
            )

        url = request.query.get("url")
        # Query params are always strings - accept "true"/"false" (case-insensitive)
        all_variants = (
            request.query.get("all_variants", "false").lower() == "true"
        )

        if url:
            if all_variants:
                # Clear all entries for this URL (all thumbnail variants)
                cleared_count = cache.delete_all_for_url(url)
                return await self.bare_request_success(
                    {"cleared_count": cleared_count}
                )
            else:
                # Clear specific URL (without params)
                deleted = cache.delete(url)
                return await self.bare_request_success(
                    {"deleted": deleted, "cleared_count": 1 if deleted else 0}
                )
        else:
            # Clear entire cache
            result = cache.clear()
            return await self.bare_request_success(result)
