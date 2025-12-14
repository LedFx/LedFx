"""API endpoint for downloading individual assets."""

import logging
import os

from aiohttp import web

from ledfx import assets
from ledfx.api import RestEndpoint
from ledfx.utils import get_image_cache, open_image

_LOGGER = logging.getLogger(__name__)


class AssetsDownloadEndpoint(RestEndpoint):
    """
    REST API endpoint for downloading individual assets.

    Supports user-uploaded assets, built-in assets, and remote URLs:
    - User assets: "icons/led.png" (no prefix)
    - Built-in assets: "builtin://skull.gif" (builtin:// prefix)
    - Remote URLs: "https://example.com/image.gif" (automatically fetched and cached)

    Supports both GET and POST methods:
    - GET: /api/assets/download?path=icons/led.png (browser-friendly)
    - POST: JSON body with {"path": "icons/led.png"} (programmatic use)

    Remote URLs are validated (SSRF protection, size limits, content validation),
    fetched if not cached, and cached for future requests.
    """

    ENDPOINT_PATH = "/api/assets/download"

    async def get(self, request: web.Request) -> web.Response:
        """
        Download a specific asset file via GET request.

        Query Parameters:
            path (required): Asset identifier
                - User assets: "icons/led.png" (no prefix)
                - Built-in assets: "builtin://skull.gif" (builtin:// prefix)
                - Cached URLs: "https://example.com/image.gif" (http:// or https://)

        Returns:
            Binary image file with appropriate Content-Type header,
            or error response if path is invalid or asset not found.
        """
        asset_path = request.query.get("path")

        if not asset_path:
            return await self.invalid_request(
                message='Required query parameter "path" was not provided',
                type="error",
            )

        return await self._download(request, asset_path)

    async def post(self, request: web.Request) -> web.Response:
        """
        Download a specific asset file via POST request.

        Request Body (JSON):
            path (required): Asset identifier
                - User assets: "icons/led.png" (no prefix)
                - Built-in assets: "builtin://skull.gif" (builtin:// prefix)
                - Cached URLs: "https://example.com/image.gif" (http:// or https://)

        Returns:
            Binary image file with appropriate Content-Type header,
            or error response if path is invalid or asset not found.
        """
        try:
            data = await request.json()
        except Exception:
            return await self.json_decode_error()

        asset_path = data.get("path")

        if not asset_path:
            return await self.invalid_request(
                message='Required attribute "path" was not provided',
                type="error",
            )

        return await self._download(request, asset_path)

    async def _download(
        self, request: web.Request, asset_path: str
    ) -> web.Response:
        """
        Internal helper to download an asset given its path.

        Args:
            request: The aiohttp request object
            asset_path: Relative path to the asset (may include builtin:// prefix or HTTP/HTTPS URL)

        Returns:
            Binary file response or JSON error response
        """
        # Check if path is a remote URL (fetch and cache with validation)
        if asset_path.startswith(("http://", "https://")):
            # open_image handles URL validation, download, and caching
            try:
                image = open_image(
                    asset_path, config_dir=self._ledfx.config_dir
                )
                if not image:
                    return await self.invalid_request(
                        message=f"Failed to download or validate URL: {asset_path}",
                        type="error",
                    )

                # Get cached path after successful download
                cache = get_image_cache()
                if not cache:
                    return await self.invalid_request(
                        message="Image cache not initialized",
                        type="error",
                    )

                abs_path = cache.get(asset_path)
                if not abs_path:
                    return await self.invalid_request(
                        message=f"Failed to cache URL: {asset_path}",
                        type="error",
                    )
            except Exception as e:
                _LOGGER.warning(f"Failed to fetch URL {asset_path}: {e}")
                return await self.invalid_request(
                    message=f"Failed to fetch URL: {e}",
                    type="error",
                )
        else:
            # Get the asset path (checks both user assets and built-in assets)
            try:
                exists, abs_path, error = assets.get_asset_or_builtin_path(
                    self._ledfx.config_dir, asset_path
                )

                if not exists:
                    return await self.invalid_request(
                        message=error or f"Asset not found: {asset_path}",
                        type="error",
                    )
            except Exception as e:
                _LOGGER.warning(f"Failed to retrieve asset {asset_path}: {e}")
                return await self.internal_error(
                    message=f"Failed to retrieve asset: {e}"
                )

        # Determine content type from extension
        content_type = _get_content_type(abs_path)

        # Stream the file
        return web.FileResponse(
            path=abs_path,
            headers={"Content-Type": content_type},
        )


def _get_content_type(file_path: str) -> str:
    """
    Determine content type from file extension.

    Args:
        file_path: Path to the file

    Returns:
        MIME type string
    """
    ext = os.path.splitext(file_path)[1].lower()

    content_types = {
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
        ".gif": "image/gif",
        ".webp": "image/webp",
        ".bmp": "image/bmp",
        ".tiff": "image/tiff",
        ".tif": "image/tiff",
        ".ico": "image/x-icon",
    }

    return content_types.get(ext, "application/octet-stream")
