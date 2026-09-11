import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.integrations.dmx_input import compute_dmx_mapped
from ledfx.venues import VenueManager

_LOGGER = logging.getLogger(__name__)


def _ensure_manager(ledfx) -> VenueManager:
    if not hasattr(ledfx, "venues"):
        ledfx.venues = VenueManager(ledfx)
    return ledfx.venues


class VenuesEndpoint(RestEndpoint):
    """REST end-point for querying and managing venues (collection)."""

    ENDPOINT_PATH = "/api/venues"

    async def get(self) -> web.Response:
        """List all venues."""
        mgr = _ensure_manager(self._ledfx)
        venues = mgr.list_venues()
        _, dmx_mapped_venue_ids = compute_dmx_mapped(self._ledfx)
        result = [
            {"id": vid, **cfg, "dmx_mapped": vid in dmx_mapped_venue_ids}
            for vid, cfg in venues.items()
        ]
        return await self.bare_request_success({"venues": result})

    async def post(self, request: web.Request) -> web.Response:
        """Create a new venue.

        Body: ``{ "name": str, "rows": int (optional, default 4), "cols": int (optional, default 4) }``
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        name = data.get("name")
        if not name:
            return await self.invalid_request(
                'Required attribute "name" was not provided'
            )

        rows = int(data.get("rows", 4))
        cols = int(data.get("cols", 4))
        if rows < 1 or cols < 1:
            return await self.invalid_request(
                '"rows" and "cols" must be positive integers'
            )

        try:
            mgr = _ensure_manager(self._ledfx)
            venue = mgr.create(name=name, rows=rows, cols=cols)
        except Exception as e:
            _LOGGER.warning("Failed to create venue: %s", e)
            return await self.invalid_request(str(e))

        return await self.request_success(
            type="success",
            message=f"Created venue '{name}'",
            data={"venue": venue},
        )
