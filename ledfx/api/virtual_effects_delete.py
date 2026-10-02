from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.configuration.fields import VirtualIdStr


class EffectsEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/virtuals/{virtual_id}/effects/delete"

    async def post(self, virtual_id: str, request: web.Request) -> web.Response:
        """
        Deletes an effect from a virtual from the active effect and the history

        Args:
            virtual_id (str): The ID of the virtual from which to delete
            request (web.Request): The request object containing the effect `type`

        Returns:
            web.Response: The response indicating the success or failure of the deletion.
        """
        if self._ledfx.virtuals.get(virtual_id) is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        effect_type = data.get("type", None)
        if not isinstance(effect_type, str):
            return await self.invalid_request(
                "Required attribute 'type' was not provided"
            )

        self._ledfx.virtuals.delete_effect_history(
            VirtualIdStr(virtual_id), effect_type
        )
        response = {"status": "success"}
        return await self.bare_request_success(response)
