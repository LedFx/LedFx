import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

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
            return await self.invalid_request(
                f"Virtual with ID {virtual_id} not found"
            )

        try:
            data = await request.json()
        except JSONDecodeError as e:
            return await self.json_decode_error()
        effect_type = data.get("type", None)
        if effect_type is None:
            return await self.invalid_request(
                "Required attribute 'type' was not provided"
            )

        _LOGGER.info(f"Deleting effect {effect_type} for virtual {virtual_id}")

        # clearing specific effect from history
        virtual_cfg = next(
            (
                v
                for v in self._ledfx.config["virtuals"]
                if v["id"] == virtual_id
            ),
            None,
        )
        if virtual.active_effect and virtual.active_effect.type == effect_type:
            virtual.clear_effect()
            if virtual_cfg:
                virtual_cfg.pop("effect", None)
        if virtual_cfg and "effects" in virtual_cfg:
            virtual_cfg["effects"].pop(effect_type, None)

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success"}
        return await self.bare_request_success(response)
