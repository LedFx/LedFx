import logging
from json import JSONDecodeError
from typing import TYPE_CHECKING

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.venues import VenueManager

if TYPE_CHECKING:
    from ledfx.core import LedFxCore

_LOGGER = logging.getLogger(__name__)


def _ensure_manager(ledfx: "LedFxCore") -> VenueManager:
    if not hasattr(ledfx, "venues"):
        ledfx.venues = VenueManager(ledfx)
    return ledfx.venues


class VenueOverrideEndpoint(RestEndpoint):
    """REST end-point for color override pads on a venue.

    POST  — activate override from a specific pad index.
    DELETE — clear the override (restore running effects).
    """

    ENDPOINT_PATH = "/api/venues/{venue_id}/override"

    async def post(self, venue_id: str, request: web.Request) -> web.Response:
        """Activate a color pad override on all virtuals in the venue.

        Body::

            { "pad_index": int }  # 0-based, row-major
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        pad_index = data.get("pad_index")
        if pad_index is None:
            return await self.invalid_request(
                'Required attribute "pad_index" was not provided'
            )

        try:
            pad_index = int(pad_index)
        except (TypeError, ValueError):
            return await self.invalid_request('"pad_index" must be an integer')

        mgr = _ensure_manager(self._ledfx)
        try:
            mgr.activate_override(venue_id, pad_index)
        except KeyError as e:
            return await self.invalid_request(str(e))
        except IndexError as e:
            return await self.invalid_request(str(e))
        except Exception as e:  # noqa: BLE001 - reported to the client, as before
            _LOGGER.warning("Override activation error: %s", e)
            return await self.invalid_request(str(e))

        return await self.request_success(
            type="success",
            message=f"Color override activated (pad {pad_index}) on venue '{venue_id}'",
        )

    async def delete(self, venue_id: str) -> web.Response:
        """Clear the color override — running effects immediately resume."""
        mgr = _ensure_manager(self._ledfx)
        try:
            mgr.clear_override(venue_id)
        except KeyError as e:
            return await self.invalid_request(str(e))

        return await self.request_success(
            type="success",
            message=f"Color override cleared on venue '{venue_id}'",
        )
