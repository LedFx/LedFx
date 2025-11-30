"""API endpoint for downloading individual assets."""

import logging
import os

from aiohttp import web

from ledfx import assets
from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class AssetsDownloadEndpoint(RestEndpoint):
    """
    REST API endpoint for downloading individual assets.

    Separate endpoint for downloading to maintain consistency with cache API pattern
    of using JSON request bodies instead of query parameters.
    """

    ENDPOINT_PATH = "/api/assets/download"

    async def post(self, request: web.Request) -> web.Response:
        """
        Download a specific asset file.

        Request Body (JSON):
            path (required): Relative path to the asset

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

        try:
            exists, abs_path, error = assets.get_asset_path(
                self._ledfx.config_dir, asset_path
            )

            if not exists:
                return await self.invalid_request(
                    message=error or f"Asset not found: {asset_path}",
                    type="error",
                )

            # Determine content type from extension
            content_type = _get_content_type(abs_path)

            # Stream the file
            return web.FileResponse(
                path=abs_path,
                headers={"Content-Type": content_type},
            )

        except Exception as e:
            _LOGGER.warning(f"Failed to retrieve asset {asset_path}: {e}")
            return await self.internal_error(
                message=f"Failed to retrieve asset: {e}"
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
