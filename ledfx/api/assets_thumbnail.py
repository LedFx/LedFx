"""API endpoint for generating asset thumbnails."""

import io
import logging

from aiohttp import web
from PIL import Image

from ledfx import assets
from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)

# Default and limits for thumbnail size
DEFAULT_THUMBNAIL_SIZE = 128
MIN_THUMBNAIL_SIZE = 16
MAX_THUMBNAIL_SIZE = 512


class AssetsThumbnailEndpoint(RestEndpoint):
    """
    REST API endpoint for generating asset thumbnails on-demand.

    Generates PNG thumbnails with configurable size, maintaining aspect ratio.
    """

    ENDPOINT_PATH = "/api/assets/thumbnail"

    async def post(self, request: web.Request) -> web.Response:
        """
        Generate and return a thumbnail of an asset.

        Request Body (JSON):
            path (required): Relative path to the asset
            size (optional): Dimension size in pixels (default 128, range 16-512)
            dimension (optional): Which dimension to apply size to (default "max")
                - "max": Apply to longest axis (default)
                - "width": Apply to width, scale height proportionally
                - "height": Apply to height, scale width proportionally

        Returns:
            PNG image data with Content-Type: image/png header,
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

        # Get and validate size parameter
        size = data.get("size", DEFAULT_THUMBNAIL_SIZE)
        try:
            size = int(size)
            if size < MIN_THUMBNAIL_SIZE or size > MAX_THUMBNAIL_SIZE:
                return await self.invalid_request(
                    message=f"Size must be between {MIN_THUMBNAIL_SIZE} and {MAX_THUMBNAIL_SIZE} pixels",
                    type="error",
                )
        except (ValueError, TypeError):
            return await self.invalid_request(
                message="Size must be an integer",
                type="error",
            )

        # Get and validate dimension parameter
        dimension = data.get("dimension", "max")
        if dimension not in ("max", "width", "height"):
            return await self.invalid_request(
                message='Dimension must be "max", "width", or "height"',
                type="error",
            )

        try:
            # Get the asset path
            exists, abs_path, error = assets.get_asset_path(
                self._ledfx.config_dir, asset_path
            )

            if not exists:
                return await self.invalid_request(
                    message=error or f"Asset not found: {asset_path}",
                    type="error",
                )

            # Open and generate thumbnail
            try:
                with Image.open(abs_path) as img:
                    # Convert to RGB if necessary (handles RGBA, P, etc.)
                    if img.mode not in ("RGB", "L"):
                        img = img.convert("RGB")

                    # Calculate thumbnail dimensions based on dimension parameter
                    width, height = img.size

                    if dimension == "width":
                        # Fix width, scale height proportionally
                        new_width = size
                        new_height = int(height * (size / width))
                    elif dimension == "height":
                        # Fix height, scale width proportionally
                        new_height = size
                        new_width = int(width * (size / height))
                    else:  # dimension == "max"
                        # Use thumbnail() which applies size to longest axis
                        img.thumbnail((size, size), Image.Resampling.LANCZOS)
                        new_width, new_height = img.size

                    # Resize if we calculated specific dimensions
                    if dimension in ("width", "height"):
                        img = img.resize(
                            (new_width, new_height), Image.Resampling.LANCZOS
                        )

                    # Save to bytes buffer as PNG
                    buffer = io.BytesIO()
                    img.save(buffer, format="PNG", optimize=True)
                    buffer.seek(0)

                    return web.Response(
                        body=buffer.read(),
                        headers={"Content-Type": "image/png"},
                    )

            except Exception as e:
                _LOGGER.error(
                    f"Failed to generate thumbnail for {asset_path}: {e}"
                )
                return await self.internal_error(
                    message=f"Failed to generate thumbnail: {e}"
                )

        except Exception as e:
            _LOGGER.error(f"Failed to process thumbnail request: {e}")
            return await self.internal_error(
                message=f"Failed to process request: {e}"
            )
