"""API endpoint for listing built-in assets from LEDFX_ASSETS_PATH."""

import logging
import os
from datetime import datetime, timezone

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.assets import _list_assets_from_directory
from ledfx.consts import LEDFX_ASSETS_PATH

_LOGGER = logging.getLogger(__name__)


class AssetsFixedEndpoint(RestEndpoint):
    """
    REST API endpoint for listing built-in assets from LEDFX_ASSETS_PATH.

    Provides metadata for GIFs and images bundled with LedFx installation,
    allowing frontend to discover available built-in assets dynamically.
    """

    ENDPOINT_PATH = "/api/assets_fixed"

    async def get(self) -> web.Response:
        """
        List all built-in assets from LEDFX_ASSETS_PATH/gifs with metadata.

        Returns metadata for all images in the gifs directory and subdirectories,
        including dimensions, format, and animation information.

        Returns:
            Bare JSON response with list of asset metadata objects,
            each containing path, size, modified timestamp, dimensions, format,
            frame count, and animation status, or error response if listing fails.
        """
        try:
            gifs_root = os.path.join(LEDFX_ASSETS_PATH, "gifs")
            assets = _list_assets_from_directory(gifs_root, "built-in assets")
            return await self.bare_request_success({"assets": assets})

        except Exception as e:
            _LOGGER.warning(f"Failed to list built-in assets: {e}")
            return await self.internal_error(
                message=f"Failed to list built-in assets: {e}"
            )
