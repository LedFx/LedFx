import asyncio
import logging
import os
from pathlib import Path

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class AssetsEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/assets"

    def __init__(self, ledfx):
        super().__init__(ledfx)
        # Define where assets will be stored
        self.assets_dir = Path(self._ledfx.config_dir) / "assets"
        self.assets_dir.mkdir(exist_ok=True)

    async def get(self, request: web.Request) -> web.Response:
        """
        Get list of all assets or a specific asset file

        Parameters:
        - request (web.Request): The request object.

        Returns:
        - web.Response: The response object containing the assets list or file.
        """
        # Check if a specific filename is requested
        filename = request.match_info.get("filename")

        if filename:
            # Serve the actual file
            file_path = self.assets_dir / filename
            if not file_path.exists():
                return await self.invalid_request(
                    f"Asset '{filename}' not found"
                )

            return web.FileResponse(file_path)

        # Return list of all assets
        try:
            assets = []
            for file_path in self.assets_dir.iterdir():
                if file_path.is_file():
                    stat = file_path.stat()
                    assets.append(
                        {
                            "id": file_path.name,
                            "filename": file_path.name,
                            "type": self._get_mime_type(file_path),
                            "size": stat.st_size,
                            "url": f"/api/assets/{file_path.name}",
                            "path": str(file_path),
                        }
                    )

            return await self.bare_request_success({"assets": assets})

        except Exception as msg:
            error_message = f"Error listing assets: {msg}"
            _LOGGER.error(error_message)
            return await self.internal_error(error_message, "error")

    async def post(self, request: web.Request, body) -> web.Response:
        """
        Upload a new asset

        Parameters:
        - request (web.Request): The request object.
        - body: The parsed multipart form data containing the file.

        Returns:
        - web.Response: The response object indicating success or failure.
        """
        try:
            filename = body.get("filename")
            file_type = body.get("type")
            file = body.get("file")

            if not file:
                return await self.invalid_request("No file provided")

            if not filename:
                return await self.invalid_request("No filename provided")

            # Read file content
            file_content = file.file.read()
            file_size = len(file_content)

            # Save file to assets directory
            file_path = self.assets_dir / filename
            with open(file_path, "wb") as f:
                f.write(file_content)

            _LOGGER.info(
                f"Asset saved: filename={filename}, type={file_type}, size={file_size} bytes"
            )

            return await self.request_success(
                type="success",
                message=f"Asset '{filename}' uploaded successfully",
                data={
                    "filename": filename,
                    "type": file_type,
                    "size": file_size,
                    "url": f"/api/assets/{filename}",
                },
            )

        except Exception as msg:
            error_message = f"Error uploading asset: {msg}"
            _LOGGER.error(error_message)
            return await self.internal_error(error_message, "error")

    def _get_mime_type(self, file_path: Path) -> str:
        """
        Get MIME type based on file extension

        Parameters:
        - file_path (Path): The file path to determine the MIME type for.

        Returns:
        - str: The MIME type string.
        """
        ext = file_path.suffix.lower()
        mime_types = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".gif": "image/gif",
            ".webp": "image/webp",
            ".svg": "image/svg+xml",
        }
        return mime_types.get(ext, "application/octet-stream")
