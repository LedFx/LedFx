import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class DMXInputPauseEndpoint(RestEndpoint):
    """REST end-point for globally pausing (muting) a DMX Input integration.

    While paused, the Art-Net UDP listener keeps running and still replies
    to ArtPoll (so SoundSwitch stays "connected"), but no mapping is
    applied to any virtual/venue. The flag persists across restarts.

    PUT — set the paused state. Body: ``{"paused": true|false}``.
    """

    ENDPOINT_PATH = "/api/integrations/dmx_input/{integration_id}/pause"

    def _get_integration(self, integration_id):
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "dmx_input"):
            return None
        return integration

    async def put(self, integration_id, request: web.Request) -> web.Response:
        integration = self._get_integration(integration_id)
        if integration is None:
            return await self.invalid_request(
                f"Integration {integration_id} was not found or is not type dmx_input"
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

        integration.set_paused(bool(paused))

        return await self.request_success(
            type="success",
            message=f"DMX Input {'paused' if integration.paused else 'resumed'}",
            data={"paused": integration.paused},
        )
