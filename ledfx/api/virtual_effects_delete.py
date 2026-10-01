import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class EffectsEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/virtuals/{virtual_id}/effects/delete"

    async def post(self, virtual_id, request) -> web.Response:
        """
        Deletes an effect from a virtual from the active effect and the history

        Args:
            virtual_id (str): The ID of the virtual from which to delete
            request (web.Request): The request object containing the effect `type`

        Returns:
            web.Response: The response indicating the success or failure of the deletion.
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
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

        _LOGGER.info(
            "Deleting effect %s for virtual %s from effects",
            effect_type,
            virtual_id,
        )

        # clearing specific effect from history
        try:
            if virtual.active_effect and virtual.active_effect.type == effect_type:
                virtual.clear_effect()
                entry = virtual.entry
                if entry is not None:
                    entry.effect = None
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Error clearing active effect in effects delete: %s", e)

        entry = virtual.entry
        if entry is not None:
            entry.effects.pop(effect_type, None)

        self._ledfx.config_store.request_save()

        response = {"status": "success"}
        return await self.bare_request_success(response)
