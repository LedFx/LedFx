import logging
from json import JSONDecodeError

import voluptuous as vol
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class DisplayEndpoint(RestEndpoint):
    """REST end-point for querying and managing displays"""

    ENDPOINT_PATH = "/api/displays/{display_id}"

    async def get(self, display_id) -> web.Response:
        """
        Get a display's full config
        """
        display = self._ledfx.displays.get(display_id)
        if display is None:
            response = {
                "status": "failed",
                "reason": f"Display with ID {display_id} not found",
            }
            return web.json_response(data=response, status=404)

        response = {"status": "success"}
        response[display.id] = {
            "config": display.config,
            "id": display.id,
            "is_device": display.is_device,
            "segments": display.segments,
            "pixel_count": display.pixel_count,
            "active": display.active,
            "effect": {},
        }
        if display.active_effect:
            effect_response = {}
            effect_response["config"] = display.active_effect.config
            effect_response["name"] = display.active_effect.name
            effect_response["type"] = display.active_effect.type
            response[display.id]["effect"] = effect_response

        return web.json_response(data=response, status=200)

    async def put(self, display_id, request) -> web.Response:
        """
        Set a display to active or inactive
        """
        display = self._ledfx.displays.get(display_id)
        if display is None:
            response = {
                "status": "failed",
                "reason": f"Display with ID {display_id} not found",
            }
            return web.json_response(data=response, status=404)

        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=500)
        active = data.get("active")
        if active is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "active" was not provided',
            }
            return web.json_response(data=response, status=500)

        # Update the display's configuration
        try:
            display.active = active
        except ValueError as msg:
            response = {
                "status": "failed",
                "payload": {"type": "warning", "reason": str(msg)},
            }
            return web.json_response(data=response, status=202)

        # Update ledfx's config
        for idx, item in enumerate(self._ledfx.config["displays"]):
            if item["id"] == display.id:
                item["active"] = display.active
                self._ledfx.config["displays"][idx] = item
                break

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success", "active": display.active}
        return web.json_response(data=response, status=200)

    async def post(self, display_id, request) -> web.Response:
        """
        Update a display's segments configuration
        """
        display = self._ledfx.displays.get(display_id)
        if display is None:
            response = {
                "status": "failed",
                "reason": f"Display with ID {display_id} not found",
            }
            return web.json_response(data=response, status=404)

        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=500)
        display_segments = data.get("segments")
        if display_segments is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "segments" was not provided',
            }
            return web.json_response(data=response, status=500)

        # Update the display's configuration
        old_segments = display.segments
        try:
            display.update_segments(display_segments)
        except (ValueError, vol.MultipleInvalid, vol.Invalid) as msg:
            response = {
                "status": "failed",
                "payload": {"type": "error", "message": str(msg)},
            }
            display.update_segments(old_segments)
            return web.json_response(data=response, status=202)

        # Update ledfx's config
        for idx, item in enumerate(self._ledfx.config["displays"]):
            if item["id"] == display.id:
                item["segments"] = display.segments
                self._ledfx.config["displays"][idx] = item
                break

        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success", "segments": display.segments}
        return web.json_response(data=response, status=200)

    async def delete(self, display_id) -> web.Response:
        """
        Remove a display with this display id
        """
        display = self._ledfx.displays.get(display_id)
        if display is None:
            response = {
                "status": "failed",
                "reason": f"Display with ID {display_id} not found",
            }
            return web.json_response(data=response, status=404)

        display.clear_effect()
        device_id = display.is_device
        if self._ledfx.devices.get(device_id) is not None:
            self._ledfx.devices.destroy(device_id)

            # Update and save the configuration
            self._ledfx.config["devices"] = [
                device
                for device in self._ledfx.config["devices"]
                if device["id"] != device_id
            ]

        self._ledfx.displays.destroy(display_id)

        # Update and save the configuration
        self._ledfx.config["displays"] = [
            display
            for display in self._ledfx.config["displays"]
            if display["id"] != display_id
        ]
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success"}
        return web.json_response(data=response, status=200)
