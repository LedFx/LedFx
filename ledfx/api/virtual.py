import logging
from json import JSONDecodeError

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class VirtualEndpoint(RestEndpoint):
    """REST end-point for querying and managing virtuals"""

    ENDPOINT_PATH = "/api/virtuals/{virtual_id}"

    async def get(self, virtual_id) -> web.Response:
        """
        Get a virtual's full config
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            response = {
                "status": "failed",
                "reason": f"Virtual with ID {virtual_id} not found",
            }
            return web.json_response(data=response, status=404)

        response = {"status": "success"}
        response[virtual.id] = {
            "config": virtual.config,
            "id": virtual.id,
            "is_device": virtual.is_device,
            "auto_generated": virtual.auto_generated,
            "segments": virtual.segments,
            "pixel_count": virtual.pixel_count,
            "active": virtual.active,
            "effect": {},
        }
        if virtual.active_effect:
            effect_response = {}
            effect_response["config"] = virtual.active_effect.config
            effect_response["name"] = virtual.active_effect.name
            effect_response["type"] = virtual.active_effect.type
            response[virtual.id]["effect"] = effect_response

        return web.json_response(data=response, status=200)

    async def put(self, virtual_id, request) -> web.Response:
        """
        Set a virtual to active or inactive
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            response = {
                "status": "failed",
                "reason": f"Virtual with ID {virtual_id} not found",
            }
            return web.json_response(data=response, status=404)

        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)
        active = data.get("active")
        if active is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "active" was not provided',
            }
            return web.json_response(data=response, status=400)

        # Update the virtual's configuration
        try:
            virtual.active = active
        except ValueError as msg:
            response = {
                "status": "failed",
                "payload": {"type": "warning", "reason": str(msg)},
            }
            return web.json_response(data=response, status=202)

        # Update ledfx's config
        for idx, item in enumerate(self._ledfx.config["virtuals"]):
            if item["id"] == virtual.id:
                item["active"] = virtual.active
                self._ledfx.config["virtuals"][idx] = item
                break

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success", "active": virtual.active}
        return web.json_response(data=response, status=200)

    async def post(self, virtual_id, request) -> web.Response:
        """
        Update a virtual's segments configuration
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            response = {
                "status": "failed",
                "reason": f"Virtual with ID {virtual_id} not found",
            }
            return web.json_response(data=response, status=404)

        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)
        virtual_segments = data.get("segments")
        if virtual_segments is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "segments" was not provided',
            }
            return web.json_response(data=response, status=400)

        # Update the virtual's configuration
        old_segments = virtual.segments
        try:
            virtual.update_segments(virtual_segments)
        except (ValueError, vol.MultipleInvalid, vol.Invalid) as msg:
            response = {
                "status": "failed",
                "payload": {"type": "error", "message": str(msg)},
            }
            virtual.update_segments(old_segments)
            return web.json_response(data=response, status=202)

        # Update ledfx's config
        for idx, item in enumerate(self._ledfx.config["virtuals"]):
            if item["id"] == virtual.id:
                item["segments"] = virtual.segments
                self._ledfx.config["virtuals"][idx] = item
                break

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success", "segments": virtual.segments}
        return web.json_response(data=response, status=200)

    async def delete(self, virtual_id) -> web.Response:
        """
        Remove a virtual with this virtual id
        Handles deleting the device if the virtual is dedicated to a device
        Removes references to this virtual in any scenes
        """
        virtual = self._ledfx.virtuals.get(virtual_id)
        if virtual is None:
            response = {
                "status": "failed",
                "reason": f"Virtual with ID {virtual_id} not found",
            }
            return web.json_response(data=response, status=404)

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

        response = {"status": "success"}
        return web.json_response(data=response, status=200)
