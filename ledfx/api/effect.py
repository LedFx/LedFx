import logging

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class EffectEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/effects/{effect_id}"

    async def get(self, effect_id) -> web.Response:
        """
        Retrieve the schema of a specific effect.

        Args:
            effect_id (str): The ID of the effect to retrieve the schema for.

        Returns:
            web.Response: The HTTP response containing the schema of the effect.
        """
        if effect_id is None:
            return await self.invalid_request(
                "Required attribute 'effect_id' was not provided"
            )
        effect = self._ledfx.effects.get_class(effect_id)
        if effect is None:
            return await self.invalid_request(f"{effect_id} was not found")

        response = {"schema": str(effect.schema())}
        return await self.bare_request_success(response)
