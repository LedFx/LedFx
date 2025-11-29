"""API endpoints for asset management."""

import logging

from aiohttp import web

from ledfx import assets
from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class AssetsEndpoint(RestEndpoint):
    """
    REST API endpoint for asset management.

    Provides secure upload, download, deletion, and listing of image assets
    stored under .ledfx/assets directory.
    """

    ENDPOINT_PATH = "/api/assets"

    async def get(self, request: web.Request) -> web.Response:
        """
        List all assets or retrieve a specific asset file.

        Query Parameters:
            path (optional): Relative path to specific asset. If omitted, lists all assets.

        Returns:
            - Without path: JSON list of all assets
            - With path: Binary image file with appropriate content-type
            - Error response if path is invalid or asset not found
        """
        asset_path = request.query.get("path")

        if not asset_path:
            # List all assets
            try:
                asset_list = assets.list_assets(self._ledfx.config_dir)
                return await self.bare_request_success({"assets": asset_list})
            except Exception as e:
                _LOGGER.error(f"Failed to list assets: {e}")
                return await self.internal_error(
                    message=f"Failed to list assets: {e}"
                )

        # Get specific asset
        try:
            exists, abs_path, error = assets.get_asset_path(
                self._ledfx.config_dir, asset_path
            )

            if not exists:
                return await self.invalid_request(
                    message=error or f"Asset not found: {asset_path}",
                    type="error",
                    resp_code=404,
                )

            # Determine content type from extension
            content_type = self._get_content_type(abs_path)

            # Stream the file
            return web.FileResponse(
                path=abs_path,
                headers={"Content-Type": content_type},
            )

        except Exception as e:
            _LOGGER.error(f"Failed to retrieve asset {asset_path}: {e}")
            return await self.internal_error(
                message=f"Failed to retrieve asset: {e}"
            )

    async def post(self, request: web.Request) -> web.Response:
        """
        Upload a new asset.

        Expects multipart/form-data with:
            - file: The image file to upload
            - path: Relative path where the asset should be stored

        Returns:
            Success response with normalized asset path,
            or error response if validation fails or path is invalid.
        """
        file_data = None
        asset_path = None

        # Read multipart data
        reader = await request.multipart()
        while True:
            part = await reader.next()
            if part is None:
                break

            if part.name == "file":
                file_data = await part.read(decode=False)
            elif part.name == "path":
                asset_path = (await part.read(decode=True)).decode("utf-8")

        if not file_data or not asset_path:
            return await self.invalid_request(
                message="Missing file or path",
                type="error",
            )

        # Save the asset
        success, abs_path, error = assets.save_asset(
            self._ledfx.config_dir,
            asset_path,
            file_data,
            allow_overwrite=False,
        )

        if not success:
            return await self.invalid_request(
                message=error or "Failed to save asset",
                type="error",
            )

        return await self.request_success(
            type="success",
            message=f"Asset uploaded: {asset_path}",
            data={"path": asset_path},
        )

    async def delete(self, request: web.Request) -> web.Response:
        """
        Delete an asset.

        Query Parameters:
            path (required): Relative path to asset to delete

        Returns:
            Success response if asset was deleted,
            or error response if path is invalid or asset doesn't exist.
        """
        asset_path = request.query.get("path")

        if not asset_path:
            return await self.invalid_request(
                message="No path provided for deletion",
                type="error",
            )

        try:
            success, error = assets.delete_asset(
                self._ledfx.config_dir, asset_path
            )

            if not success:
                return await self.invalid_request(
                    message=error or f"Failed to delete asset: {asset_path}",
                    type="error",
                )

            return await self.request_success(
                type="success",
                message=f"Asset deleted: {asset_path}",
                data={"deleted": True, "path": asset_path},
            )

        except Exception as e:
            _LOGGER.error(f"Failed to delete asset {asset_path}: {e}")
            return await self.internal_error(
                message=f"Failed to delete asset: {e}"
            )

    def _get_content_type(self, file_path: str) -> str:
        """
        Determine content type from file extension.

        Args:
            file_path: Path to the file

        Returns:
            MIME type string
        """
        import os

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
