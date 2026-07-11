import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class VirtualDMXPauseEndpoint(RestEndpoint):
    """REST end-point for muting DMX Input takeover on a single virtual.

    Pausing blocks every mapping type (fixture wash, color tint, and
    venue-trigger override) from applying to this virtual, and immediately
    releases any currently owned wash/color override. Persists across
    restarts alongside the virtual's other config.

    PUT — set the paused state. Body: ``{"paused": true|false}``.
    """

    ENDPOINT_PATH = "/api/virtuals/{virtual_id}/dmx_pause"

    async def put(self, virtual_id, request: web.Request) -> web.Response:
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(
                f"Virtual with ID {virtual_id} not found"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        paused = data.get("paused")
        if paused is None:
            return await self.invalid_request(
                'Required attribute "paused" was not provided'
            )

        virtual.set_dmx_paused(bool(paused))
        virtual.virtual_cfg["dmx_paused"] = virtual.is_dmx_paused()

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        return await self.request_success(
            type="success",
            message=(
                f"Virtual '{virtual.name}' "
                f"{'DMX-paused' if virtual.is_dmx_paused() else 'DMX-resumed'}"
            ),
            data={"paused": virtual.is_dmx_paused()},
        )
