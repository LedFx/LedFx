"""API endpoint for refreshing cached images."""

import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.utils import get_image_cache, open_image

_LOGGER = logging.getLogger(__name__)


class CacheRefreshEndpoint(RestEndpoint):
    """REST API endpoint for explicit cache refresh."""

    ENDPOINT_PATH = "/api/cache/images/refresh"

    async def post(self, request: web.Request) -> web.Response:
        """
        Refresh a cached image by re-downloading from the origin server.

        Removes the specified URL from cache, then immediately re-downloads
        and caches the fresh copy. For local assets, clears cache variants.

        Request Body:
            url (required): URL to refresh (must be http:// or https://)
            all_variants (optional): If true, clears all cache entries for that URL
                                    (including thumbnails with different params)

        Returns:
            Bare response with cache operation results:
            - all_variants=true: {"cleared_count": int} (for local assets/thumbnails)
            - all_variants=false: {"refreshed": bool} (for URLs - true if re-downloaded successfully)

            Error responses use standard format with status/payload for validation errors.
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

        # Check if URL is a remote image (http/https)
        if url.startswith(("http://", "https://")):
            # Delete from cache
            deleted = cache.delete(url)
            
            # Immediately re-download and cache (force_refresh=True bypasses cache check)
            _LOGGER.info(f"Actively refreshing cached URL: {url}")
            image = open_image(url, force_refresh=True, config_dir=self._ledfx.config_dir)
            
            if image:
                # Re-download succeeded, image is now cached
                return await self.bare_request_success({"refreshed": True})
            else:
                # Re-download failed
                return await self.invalid_request(
                    message=f"Failed to refresh URL: {url}. Image could not be downloaded.",
                    type="error"
                )
        else:
            # For local assets (asset:// or builtin://), just clear the cache
            # Can't "refresh" a local file, only clear cached variants
            deleted = cache.delete(url)
            return await self.bare_request_success({"refreshed": deleted})
