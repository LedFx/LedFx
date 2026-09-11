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


class VenueEndpoint(RestEndpoint):
    """REST end-point for a single venue: read, update, delete, manage members."""

    ENDPOINT_PATH = "/api/venues/{venue_id}"

    async def get(self, venue_id) -> web.Response:
        """Get a venue by ID."""
        mgr = _ensure_manager(self._ledfx)
        cfg = mgr.get(venue_id)
        if cfg is None:
            return await self.invalid_request(f"Venue '{venue_id}' not found")
        _, dmx_mapped_venue_ids = compute_dmx_mapped(self._ledfx)
        return await self.bare_request_success(
            {
                "venue": {
                    "id": venue_id,
                    **cfg,
                    "dmx_mapped": venue_id in dmx_mapped_venue_ids,
                }
            }
        )

    async def put(self, venue_id, request: web.Request) -> web.Response:
        """Update venue name, grid dimensions, or manage virtual membership.

        Supported body variants:

        Update name / grid::

            { "name": "...", "color_pads": { "rows": N, "cols": M } }

        Add a virtual::

            { "action": "add_virtual", "virtual_id": "..." }

        Remove a virtual::

            { "action": "remove_virtual", "virtual_id": "..." }
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        mgr = _ensure_manager(self._ledfx)

        action = data.get("action")

        try:
            if action == "add_virtual":
                virtual_id = data.get("virtual_id")
                if not virtual_id:
                    return await self.invalid_request(
                        '"virtual_id" required for add_virtual'
                    )
                venue = mgr.add_virtual(venue_id, virtual_id)
                return await self.request_success(
                    type="success",
                    message=f"Added virtual '{virtual_id}' to venue '{venue_id}'",
                    data={"venue": venue},
                )

            elif action == "remove_virtual":
                virtual_id = data.get("virtual_id")
                if not virtual_id:
                    return await self.invalid_request(
                        '"virtual_id" required for remove_virtual'
                    )
                venue = mgr.remove_virtual(venue_id, virtual_id)
                return await self.request_success(
                    type="success",
                    message=f"Removed virtual '{virtual_id}' from venue '{venue_id}'",
                    data={"venue": venue},
                )

            else:
                # Generic config update (name, color_pads)
                venue = mgr.update(venue_id, data)
                return await self.request_success(
                    type="success",
                    message=f"Updated venue '{venue_id}'",
                    data={"venue": venue},
                )

        except KeyError as e:
            return await self.invalid_request(str(e))
        except ValueError as e:
            return await self.invalid_request(str(e))
        except Exception as e:
            _LOGGER.warning("Venue update error: %s", e)
            return await self.invalid_request(str(e))

    async def delete(self, venue_id) -> web.Response:
        """Delete a venue."""
        mgr = _ensure_manager(self._ledfx)
        ok = mgr.delete(venue_id)
        if not ok:
            return await self.invalid_request(f"Venue '{venue_id}' not found")
        return await self.request_success(
            type="success", message=f"Deleted venue '{venue_id}'"
        )
