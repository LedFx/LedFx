import logging

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class EffectsEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/virtuals/{virtual_id}/fallback"

    async def get(self, virtual_id) -> web.Response:
        """
        Fires a fallback trigger which will cause a virtual to return to its default effect

        Args:
            virtual_id (str): The ID of the virtual which to fire the fallback trigger

        Returns:
            web.Response: The response indicating the success or failure of the deletion.
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(
                f"Virtual with ID {virtual_id} not found"
            )

        _LOGGER.info(f"Fire fallback for virtual {virtual_id}")

        virtual.fallback_fire_set_with_lock()
        response = {"status": "success"}
        return await self.bare_request_success(response)
