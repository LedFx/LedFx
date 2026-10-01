import logging
from json import JSONDecodeError

from aiohttp import web
from pydantic import ValidationError

from ledfx.api import RestEndpoint
from ledfx.integrations.dmx_input import compute_dmx_mapped
from ledfx.venues import venue_payload

_LOGGER = logging.getLogger(__name__)


class VenuesEndpoint(RestEndpoint):
    """REST end-point for querying and managing venues (collection)."""

    ENDPOINT_PATH = "/api/venues"

    async def get(self) -> web.Response:
        """List all venues."""
        mgr = self._ledfx.venues
        venues = mgr.list_venues()
        _, dmx_mapped_venue_ids = compute_dmx_mapped(self._ledfx)
        result = [
            {**venue_payload(vid, cfg), "dmx_mapped": vid in dmx_mapped_venue_ids}
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

        try:
            mgr = self._ledfx.venues
            venue_id, venue = mgr.create(
                name=name, rows=data.get("rows", 4), cols=data.get("cols", 4)
            )
        except ValidationError as err:
            return await self.validation_error(err)
        except Exception as e:  # noqa: BLE001 - reported to the client, as before
            _LOGGER.warning("Failed to create venue: %s", e)
            return await self.invalid_request(str(e))

        return await self.request_success(
            type="success",
            message=f"Created venue '{name}'",
            data={"venue": venue_payload(venue_id, venue)},
        )
