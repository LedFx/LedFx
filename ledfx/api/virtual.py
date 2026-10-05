import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import Segment
from ledfx.effects import DummyEffect
from ledfx.errors import Conflict, Invalid
from ledfx.virtuals import Virtual

_LOGGER = logging.getLogger(__name__)


def make_virtual_response(virtual: Virtual) -> dict[str, object]:
    entry = virtual.entry
    virtual_response: dict[str, object] = {
        "config": virtual.config,
        "id": virtual.id,
        "is_device": virtual.is_device,
        "auto_generated": virtual.auto_generated,
        "segments": virtual.segments,
        "pixel_count": virtual.pixel_count,
        "active": virtual.active,
        "streaming": virtual.streaming,
        "last_effect": entry.last_effect if entry is not None else None,
        "effect": {},
    }
    # Protect from DummyEffect
    if virtual.active_effect and not isinstance(virtual.active_effect, DummyEffect):
        effect_response = {
            "config": virtual.active_effect.config,
            "name": virtual.active_effect.name,
            "type": virtual.active_effect.type,
        }
        virtual_response["effect"] = effect_response

    return virtual_response


def _v1_segments(virtual: Virtual, value: object) -> list[Segment]:
    """v1-compat: the manager refuses segments outside a device's pixels; v1
    clamped them and answered success, so clamp here. Raises ValueError with
    v1's text."""
    if isinstance(value, (list, tuple)):
        return [
            Segment._make(
                virtual.validate_segment(
                    list(item) if isinstance(item, (list, tuple)) else item
                )
            )
            for item in value
        ]
    raise ValueError(f"Invalid segments: {value}, should be a list of segments")


class VirtualEndpoint(RestEndpoint):
    """REST end-point for querying and managing virtuals"""

    ENDPOINT_PATH = "/api/virtuals/{virtual_id}"

    async def get(self, virtual_id: str) -> web.Response:
        """
        Get a virtual's full config
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        response: dict[str, object] = {"status": "success"}
        response[virtual.id] = make_virtual_response(virtual)

        return await self.bare_request_success(response)

    async def put(self, virtual_id: str, request: web.Request) -> web.Response:
        """
        Set a virtual to active or inactive
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        active = data.get("active")
        if active is None:
            # PUT only toggles; a config update is POST /api/virtuals with the id.
            return await self.invalid_request(
                'Required attribute "active" was not provided. '
                "To change the config, POST it to /api/virtuals with the virtual's id"
            )
        if not isinstance(active, bool):
            return await self.invalid_request('"active" must be true or false')

        try:
            virtual = self._ledfx.virtuals.set_active(VirtualIdStr(virtual_id), active)
        except Conflict as err:
            # v1-compat: v1 words the refusal as a status failure and shows the
            # underlying error's text (the stale-config case has a cleaner v2 detail).
            error_message = (
                f"Unable to set virtual {virtual.id} status: {err.__cause__ or err}"
            )
            _LOGGER.warning(error_message)
            return await self.invalid_request(error_message)

        response = {"status": "success", "active": virtual.active}
        return await self.bare_request_success(response)

    async def post(self, virtual_id: str, request: web.Request) -> web.Response:
        """
        Update a virtual's segments configuration
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        virtual_segments = data.get("segments")
        if virtual_segments is None:
            return await self.invalid_request(
                'Required attribute "segments" was not provided'
            )

        try:
            virtual = self._ledfx.virtuals.set_segments(
                VirtualIdStr(virtual_id), _v1_segments(virtual, virtual_segments)
            )
        except (ValueError, Invalid) as err:
            detail = err.detail if isinstance(err, Invalid) else str(err)
            error_message = (
                f"Unable to set virtual segments {virtual_segments}: {detail}"
            )
            _LOGGER.warning(error_message)
            return await self.invalid_request(error_message)

        response = {"status": "success", "segments": virtual.segments}
        return await self.bare_request_success(response)

    async def delete(self, virtual_id: str) -> web.Response:
        """
        Remove a virtual with this virtual id
        Handles deleting the device if the virtual is dedicated to a device
        Removes references to this virtual in any scenes
        """
        if self._ledfx.virtuals.get(virtual_id) is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        self._ledfx.virtuals.remove(VirtualIdStr(virtual_id))
        return await self.request_success()
