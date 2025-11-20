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
