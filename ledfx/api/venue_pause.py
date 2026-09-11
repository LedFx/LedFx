import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.venues import VenueManager

_LOGGER = logging.getLogger(__name__)


def _ensure_manager(ledfx) -> VenueManager:
    if not hasattr(ledfx, "venues"):
        ledfx.venues = VenueManager(ledfx)
    return ledfx.venues


class VenuePauseEndpoint(RestEndpoint):
    """REST end-point for muting DMX Input takeover on a venue.

    Pausing also clears any active color-pad override on the venue,
    since both represent "this venue's manual takeover" to the operator.

    PUT — set the paused state. Body: ``{"paused": true|false}``.
    """

    ENDPOINT_PATH = "/api/venues/{venue_id}/pause"

    async def put(self, venue_id, request: web.Request) -> web.Response:
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        paused = data.get("paused")
        if paused is None:
            return await self.invalid_request(
                'Required attribute "paused" was not provided'
            )

        mgr = _ensure_manager(self._ledfx)
        try:
            venue = mgr.set_paused(venue_id, bool(paused))
        except KeyError as e:
            return await self.invalid_request(str(e))

        return await self.request_success(
            type="success",
            message=f"Venue '{venue_id}' {'paused' if venue['paused'] else 'resumed'}",
            data={"venue": venue},
        )
