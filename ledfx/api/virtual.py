import logging
from json import JSONDecodeError

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.effects import DummyEffect

_LOGGER = logging.getLogger(__name__)


def make_virtual_response(virtual):
    entry = virtual.entry
    virtual_response = {
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


class VirtualEndpoint(RestEndpoint):
    """REST end-point for querying and managing virtuals"""

    ENDPOINT_PATH = "/api/virtuals/{virtual_id}"

    async def get(self, virtual_id) -> web.Response:
        """
        Get a virtual's full config
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        response = {"status": "success"}
        response[virtual.id] = make_virtual_response(virtual)

        return await self.bare_request_success(response)

    async def put(self, virtual_id, request) -> web.Response:
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
            return await self.invalid_request(
                'Required attribute "active" was not provided'
            )

        # Update the virtual's configuration
        if active and (
            not virtual._active_effect or isinstance(virtual.active_effect, DummyEffect)
        ):
            entry = virtual.entry
            last_effect = entry.last_effect if entry is not None else None
            if last_effect:
                effect_config = virtual.get_effects_config(last_effect)
                if effect_config:
                    effect = self._ledfx.effects.create(
                        ledfx=self._ledfx,
                        type=last_effect,
                        config=effect_config,
                    )
                    virtual.set_effect(effect)
                    virtual.update_effect_config(effect)
        try:
            virtual.active = active
        except ValueError as msg:
            error_message = f"Unable to set virtual {virtual.id} status: {msg}"
            _LOGGER.warning(error_message)
            return await self.internal_error(error_message, "error")

        entry = virtual.entry
        if entry is not None:
            entry.active = virtual.active

        self._ledfx.config_store.request_save()

        response = {"status": "success", "active": virtual.active}
        return await self.bare_request_success(response)

    async def post(self, virtual_id, request) -> web.Response:
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

        # Update the virtual's configuration
        old_segments = virtual.segments
        try:
            virtual.update_segments(virtual_segments)
        except (ValueError, vol.MultipleInvalid, vol.Invalid) as msg:
            error_message = f"Unable to set virtual segments {virtual_segments}: {msg}"
            _LOGGER.warning(error_message)
            virtual.update_segments(old_segments)
            return await self.internal_error(error_message, "error")

        entry = virtual.entry
        if entry is not None:
            entry.segments = virtual.segments

        self._ledfx.config_store.request_save()

        response = {"status": "success", "segments": virtual.segments}
        return await self.bare_request_success(response)

    async def delete(self, virtual_id) -> web.Response:
        """
        Remove a virtual with this virtual id
        Handles deleting the device if the virtual is dedicated to a device
        Removes references to this virtual in any scenes
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(f"Virtual with ID {virtual_id} not found")

        virtual.clear_effect()
        device_id = virtual.is_device
        device = self._ledfx.devices.get(device_id)
        if device is not None:
            await device.remove_from_virtuals()
            # remove_from_virtuals may have already destroyed this device
            if self._ledfx.devices.get(device_id) is not None:
                self._ledfx.devices.destroy(device_id)

            # Update and save the configuration
            self._ledfx.config.devices = [
                _device
                for _device in self._ledfx.config.devices
                if _device.id != device_id
            ]

        # cleanup this virtual from any scenes
        for scene in self._ledfx.config.scenes.values():
            scene.virtuals.pop(virtual_id, None)

        # remove_from_virtuals may have already destroyed this virtual
        if self._ledfx.virtuals.get(virtual_id) is not None:
            self._ledfx.virtuals.destroy(virtual_id)

        # Update and save the configuration
        self._ledfx.config.virtuals = [
            virtual
            for virtual in self._ledfx.config.virtuals
            if virtual.id != virtual_id
        ]
        self._ledfx.config_store.request_save()
        return await self.request_success()
