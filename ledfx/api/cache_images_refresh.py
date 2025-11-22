"""API endpoint for refreshing cached images."""

import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import get_image_cache

_LOGGER = logging.getLogger(__name__)


class CacheRefreshEndpoint(RestEndpoint):
    """REST API endpoint for explicit cache refresh."""

    ENDPOINT_PATH = "/api/cache/images/refresh"

    async def post(self, body) -> web.Response:
        """
        Clear a cached image to force re-download on next access.

        Removes the specified URL from cache. Next request will re-download
        from origin server and cache the fresh copy.

        Request Body:
            url (required): URL to clear from cache

        Returns:
            Success response with URL (type: success if cached, info if not cached),
            or error response if request invalid or cache not initialized.
        """
        cache = get_image_cache()

        if not cache:
            return await self.invalid_request(
                message="Image cache not initialized",
                type="error",
            )

        if not body or not isinstance(body, dict):
            return await self.invalid_request(
                message="Invalid JSON in request body",
                type="error",
            )

        url = body.get("url")
        if not url:
            return await self.invalid_request(
                message="Missing 'url' in request body",
                type="error",
            )

        # Clear the URL from cache to force refresh on next access
        deleted = cache.delete(url)

        if deleted:
            return await self.request_success(
                type="success",
                message="Cache entry cleared. Image will be re-downloaded on next access.",
                data={"url": url},
            )
        else:
            return await self.request_success(
                type="info",
                message="URL was not in cache (no action needed).",
                data={"url": url},
            )
