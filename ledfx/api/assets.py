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

    async def get(self) -> web.Response:
        """
        List all available assets with metadata.

        Returns:
            Bare JSON response with list of asset metadata objects,
            each containing path, size, modified timestamp, width, and height,
            or error response if listing fails.
        """
        try:
            asset_list = assets.list_assets(self._ledfx.config_dir)
            return await self.bare_request_success({"assets": asset_list})
        except Exception as e:
            _LOGGER.warning(f"Failed to list assets: {e}")
            return await self.internal_error(
                message=f"Failed to list assets: {e}"
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
            allow_overwrite=True,
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

        Supports both query parameter and JSON body for browser compatibility.

        Query Parameters:
            path (optional): Relative path to asset to delete

        Request Body (JSON, fallback):
            path (optional): Relative path to asset to delete

        Returns:
            Success response if asset was deleted,
            or error response if path is invalid or asset doesn't exist.
        """
        # Try query parameter first (preferred for DELETE)
        asset_path = request.query.get("path")

        # Fallback to JSON body if no query parameter
        if not asset_path:
            try:
                data = await request.json()
                asset_path = data.get("path")
            except Exception:
                pass

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
            _LOGGER.warning(f"Failed to delete asset {asset_path}: {e}")
            return await self.internal_error(
                message=f"Failed to delete asset: {e}"
            )
