import logging

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class ColorDeleteEndpoint(RestEndpoint):
    """REST end-point for deleting user colors or gradients"""

    ENDPOINT_PATH = "/api/colors/{color_id}"

    async def delete(self, color_id) -> web.Response:
        """Delete a user color or gradient.

        Args:
            color_id (str): The ID of the color or gradient to delete.

        Returns:
            web.Response: The HTTP response object.
        """
        # Try to delete from colors first
        if color_id in self._ledfx.colors:
            try:
                del self._ledfx.colors[color_id]
                return await self.request_success(
                    "success", f"Deleted color {color_id}"
                )
            except Exception as e:
                error_message = f"Failed to delete color {color_id}: {str(e)}"
                _LOGGER.warning(error_message)
                return await self.invalid_request(error_message)

        # Try to delete from gradients
        if color_id in self._ledfx.gradients:
            try:
                del self._ledfx.gradients[color_id]
                return await self.request_success(
                    "success", f"Deleted gradient {color_id}"
                )
            except Exception as e:
                error_message = (
                    f"Failed to delete gradient {color_id}: {str(e)}"
                )
                _LOGGER.warning(error_message)
                return await self.invalid_request(error_message)

        # Color/gradient not found
        error_message = f"Color or gradient {color_id} not found"
        _LOGGER.warning(error_message)
        return await self.invalid_request(error_message)
