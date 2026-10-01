import copy
import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.integrations.dmx_input import DMXInput, DMXMapping
from ledfx.venues import VenueManager

_LOGGER = logging.getLogger(__name__)


class DMXInputEndpoint(RestEndpoint):
    """REST end-point for managing a DMX Input integration's channel mappings.

    GET    — list mappings plus live DMX, venues and virtuals (for the editor).
    POST   — add a new mapping or update an existing one (by ``index``).
    DELETE — remove a mapping by ``index``.
    """

    ENDPOINT_PATH = "/api/integrations/dmx_input/{integration_id}"

    def _get_integration(self, integration_id: str) -> DMXInput | None:
        integration = self._ledfx.integrations.get(integration_id)
        if (integration is None) or (integration.type != "dmx_input"):
            return None
        return integration

    def _persist(self, integration: DMXInput) -> None:
        for entry in self._ledfx.config.integrations:
            if entry.id == integration.id:
                entry.data = copy.deepcopy(integration.data)
                break
        self._ledfx.config_store.request_save()

    async def get(self, integration_id: str) -> web.Response:
        integration = self._get_integration(integration_id)
        if integration is None:
            return await self.invalid_request(
                f"Integration {integration_id} was not found or is not type dmx_input"
            )

        if not hasattr(self._ledfx, "venues"):
            self._ledfx.venues = VenueManager(self._ledfx)
        venues = {
            vid: venue.model_dump()
            for vid, venue in self._ledfx.venues.list_venues().items()
        }

        virtuals = {v.id: v.name for v in self._ledfx.virtuals.values()}

        response = {
            "mappings": integration.get_mappings(),
            "live_dmx": integration.get_live_dmx(),
            "venues": venues,
            "virtuals": virtuals,
        }
        return await self.bare_request_success(response)

    async def post(self, integration_id: str, request: web.Request) -> web.Response:
        integration = self._get_integration(integration_id)
        if integration is None:
            return await self.invalid_request(
                f"Integration {integration_id} was not found or is not type dmx_input"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        # Mappings are stored as sent (the editor keeps its own extra keys).
        mapping: DMXMapping | None = data.get("mapping")
        if mapping is None or not isinstance(mapping, dict):
            return await self.invalid_request(
                'Required attribute "mapping" (object) was not provided'
            )

        index = data.get("index")
        mappings = integration.get_mappings()
        if index is None:
            integration.add_mapping(mapping)
        else:
            try:
                index = int(index)
            except (TypeError, ValueError):
                return await self.invalid_request('"index" must be an integer')
            if index < 0 or index >= len(mappings):
                return await self.invalid_request(f"Mapping index {index} out of range")
            mappings[index] = mapping

        self._persist(integration)
        return await self.request_success(type="success", message="DMX mapping saved")

    async def delete(self, integration_id: str, request: web.Request) -> web.Response:
        integration = self._get_integration(integration_id)
        if integration is None:
            return await self.invalid_request(
                f"Integration {integration_id} was not found or is not type dmx_input"
            )

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        index = data.get("index")
        if index is None:
            return await self.invalid_request(
                'Required attribute "index" was not provided'
            )
        try:
            index = int(index)
        except (TypeError, ValueError):
            return await self.invalid_request('"index" must be an integer')
        if index < 0 or index >= len(integration.get_mappings()):
            return await self.invalid_request(f"Mapping index {index} out of range")

        integration.delete_mapping(index)
        self._persist(integration)
        return await self.request_success(type="success", message="DMX mapping deleted")
