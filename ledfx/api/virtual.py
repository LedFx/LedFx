import logging
from json import JSONDecodeError

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.effects import DummyEffect

_LOGGER = logging.getLogger(__name__)


def make_virtual_response(virtual):
    virtual_response = {
        "config": virtual.config,
        "id": virtual.id,
        "is_device": virtual.is_device,
        "auto_generated": virtual.auto_generated,
        "segments": virtual.segments,
        "pixel_count": virtual.pixel_count,
        "active": virtual.active,
        "streaming": virtual.streaming,
        "last_effect": virtual.virtual_cfg.get("last_effect", None),
        "effect": {},
    }
    # Protect from DummyEffect
    if virtual.active_effect and not isinstance(
        virtual.active_effect, DummyEffect
    ):
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
            return await self.invalid_request(
                f"Virtual with ID {virtual_id} not found"
            )

        response = {"status": "success"}
        response[virtual.id] = make_virtual_response(virtual)

        return await self.bare_request_success(response)

    async def put(self, virtual_id, request) -> web.Response:
        """
        Set a virtual to active or inactive
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(
                f"Virtual with ID {virtual_id} not found"
            )

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
        if active:
            if not virtual._active_effect or isinstance(
                virtual.active_effect, DummyEffect
            ):
                last_effect = virtual.virtual_cfg.get("last_effect", None)
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

        virtual.virtual_cfg["active"] = virtual.active

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success", "active": virtual.active}
        return await self.bare_request_success(response)

    async def post(self, virtual_id, request) -> web.Response:
        """
        Update a virtual's segments configuration
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            return await self.invalid_request(
                f"Virtual with ID {virtual_id} not found"
            )

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
            error_message = (
                f"Unable to set virtual segments {virtual_segments}: {msg}"
            )
            _LOGGER.warning(error_message)
            virtual.update_segments(old_segments)
            return await self.internal_error(error_message, "error")

        virtual.virtual_cfg["segments"] = virtual.segments

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

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
            return await self.invalid_request(
                f"Virtual with ID {virtual_id} not found"
            )

        virtual.clear_effect()
        device_id = virtual.is_device
        device = self._ledfx.devices.get(device_id)
        if device is not None:
            await device.remove_from_virtuals()
            self._ledfx.devices.destroy(device_id)

            # Update and save the configuration
            self._ledfx.config["devices"] = [
                _device
                for _device in self._ledfx.config["devices"]
                if _device["id"] != device_id
            ]

        # cleanup this virtual from any scenes
        ledfx_scenes = self._ledfx.config["scenes"].copy()
        for scene_id, scene_config in ledfx_scenes.items():
            self._ledfx.config["scenes"][scene_id]["virtuals"] = {
                _virtual_id: effect
                for _virtual_id, effect in scene_config["virtuals"].items()
                if _virtual_id != virtual_id
            }

        self._ledfx.virtuals.destroy(virtual_id)

        # Update and save the configuration
        self._ledfx.config["virtuals"] = [
            virtual
            for virtual in self._ledfx.config["virtuals"]
            if virtual["id"] != virtual_id
        ]
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )
        return await self.request_success()
