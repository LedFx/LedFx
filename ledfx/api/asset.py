import logging
import os
from pathlib import Path
from urllib.parse import unquote

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class AssetEndpoint(RestEndpoint):
    """REST end-point for querying and managing individual assets"""

    ENDPOINT_PATH = "/api/assets/{filename}"

    def __init__(self, ledfx):
        super().__init__(ledfx)
        # Define where assets are stored
        self.assets_dir = Path(self._ledfx.config_dir) / "assets"
        self.assets_dir.mkdir(exist_ok=True)

    async def delete(self, filename) -> web.Response:
        """
        Delete an asset with this filename

        Parameters:
        - filename: The URI-encoded filename of the asset.

        Returns:
        - web.Response: Success or error response.
        """
        # Decode URI-encoded filename
        decoded_filename = unquote(filename)
        file_path = self.assets_dir / decoded_filename
        
        if not file_path.exists():
            return await self.invalid_request(
                f"Asset with filename '{decoded_filename}' not found"
            )
        
        try:
            # Delete the file
            os.remove(file_path)
            
            _LOGGER.info(f"Asset deleted: {decoded_filename}")
            
            return await self.request_success(
                type="success",
                message=f"Asset '{decoded_filename}' deleted successfully"
            )
            
        except Exception as msg:
            error_message = f"Unable to delete asset {decoded_filename}: {msg}"
            _LOGGER.warning(error_message)
            return await self.internal_error(error_message, "error")

