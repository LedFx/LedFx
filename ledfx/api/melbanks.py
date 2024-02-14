import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.api.utils import PERMITTED_KEYS, convertToJsonSchema
from ledfx.effects.melbank import Melbank, Melbanks

_LOGGER = logging.getLogger(__name__)


class ScenesEndpoint(RestEndpoint):
    """REST end-point for querying config and schema melbanks"""

    ENDPOINT_PATH = "/api/melbanks"

    async def get(self) -> web.Response:
        """
        Get all melbank configuration and permitted values.

        Returns:
            web.Response: The response containing the scenes.
        """
        data = {}
        data["melbanks"] = {
            "config": self._ledfx.config["melbanks"],
            "schema": {
                **convertToJsonSchema(
                    Melbanks.CONFIG_SCHEMA,
                ),
                **{"permitted_keys": PERMITTED_KEYS["melbanks"]},
            },
        }
        data["melbank_collection"] = {
            "config": self._ledfx.config["melbank_collection"],
            "schema": {
                **convertToJsonSchema(
                    Melbank.CONFIG_SCHEMA,
                ),
                **{"permitted_keys": PERMITTED_KEYS["melbank_collection"]},
            },
        }

        return await self.request_success(type=None, message=None, data=data)
