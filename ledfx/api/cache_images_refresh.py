"""API endpoint for refreshing cached images."""

import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import get_image_cache

_LOGGER = logging.getLogger(__name__)


class CacheRefreshEndpoint(RestEndpoint):
    """REST API endpoint for explicit cache refresh."""

    ENDPOINT_PATH = "/api/cache/images/refresh"

    async def post(self, request: web.Request) -> web.Response:
        """
        Clear a cached image to force re-download on next access.

        Removes the specified URL from cache. Next request will re-download
        from origin server and cache the fresh copy.

        Request Body:
            url (required): URL to clear from cache
            all_variants (optional): If true, clears all cache entries for that URL
                                    (including thumbnails with different params)

        Returns:
            Success response with URL and cleared_count (type: success if cached, info if not cached),
            or error response if request invalid or cache not initialized.
        """
        cache = get_image_cache()

        if not cache:
            return await self.invalid_request(
                message="Image cache not initialized",
                type="error",
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        url = data.get("url")
        if not url:
            return await self.invalid_request(
                message="Missing 'url' in request body",
                type="error",
            )

        all_variants = data.get("all_variants", False)
        if not isinstance(all_variants, bool):
            return await self.invalid_request(
                message="Invalid 'all_variants' parameter. Must be a boolean (true or false).",
                type="error",
            )

        if all_variants:
            # Clear all variants (useful for asset thumbnails)
            cleared_count = cache.delete_all_for_url(url)
            return await self.bare_request_success(
                {"cleared_count": cleared_count}
            )

        # Clear the URL from cache to force refresh on next access
        deleted = cache.delete(url)
        return await self.bare_request_success({"deleted": deleted})
