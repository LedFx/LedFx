import logging
from json import JSONDecodeError

from aiohttp import web
from pydantic import ValidationError

from ledfx.api import RestEndpoint
from ledfx.integrations.dmx_input import compute_dmx_mapped
from ledfx.venues import venue_payload

_LOGGER = logging.getLogger(__name__)


class VenueEndpoint(RestEndpoint):
    """REST end-point for a single venue: read, update, delete, manage members."""

    ENDPOINT_PATH = "/api/venues/{venue_id}"

    async def get(self, venue_id: str) -> web.Response:
        """Get a venue by ID."""
        mgr = self._ledfx.venues
        cfg = mgr.get(venue_id)
        if cfg is None:
            return await self.invalid_request(f"Venue '{venue_id}' not found")
        _, dmx_mapped_venue_ids = compute_dmx_mapped(self._ledfx)
        return await self.bare_request_success(
            {
                "venue": {
                    **venue_payload(venue_id, cfg),
                    "dmx_mapped": venue_id in dmx_mapped_venue_ids,
                }
            }
        )

    async def put(self, venue_id: str, request: web.Request) -> web.Response:
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

        mgr = self._ledfx.venues

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
                    data={"venue": venue_payload(venue_id, venue)},
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
                    data={"venue": venue_payload(venue_id, venue)},
                )

            else:
                # Generic config update (name, color_pads)
                venue = mgr.update(venue_id, data)
                return await self.request_success(
                    type="success",
                    message=f"Updated venue '{venue_id}'",
                    data={"venue": venue_payload(venue_id, venue)},
                )

        except KeyError as e:
            return await self.invalid_request(str(e))
        except ValidationError as err:
            return await self.validation_error(err)
        except ValueError as e:
            return await self.invalid_request(str(e))
        except Exception as e:  # noqa: BLE001 - reported to the client, as before
            _LOGGER.warning("Venue update error: %s", e)
            return await self.invalid_request(str(e))

    async def delete(self, venue_id: str) -> web.Response:
        """Delete a venue."""
        mgr = self._ledfx.venues
        ok = mgr.delete(venue_id)
        if not ok:
            return await self.invalid_request(f"Venue '{venue_id}' not found")
        return await self.request_success(
            type="success", message=f"Deleted venue '{venue_id}'"
        )
