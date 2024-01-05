import logging
from json import JSONDecodeError

import voluptuous
from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class DeviceEndpoint(RestEndpoint):
    """REST end-point for querying and managing devices"""

    ENDPOINT_PATH = "/api/devices/{device_id}"

    async def get(self, device_id) -> web.Response:
        """
        Get the configuration of a device.

        Args:
            device_id (str): The ID of the device.

        Returns:
            web.Response: The response containing the device configuration.
        """
        device = self._ledfx.devices.get(device_id)
        if device is None:
            return await self.invalid_request("{device} was not found")

        response = device.config
        return await self.bare_request_success(response)

    async def put(self, device_id, request) -> web.Response:
        """
        Update the configuration of a device.

        Args:
            device_id (str): The ID of the device.
            request (web.Request): The request object containing device `config`.

        Returns:
            web.Response: The response indicating the success or failure of the update.
        """
        device = self._ledfx.devices.get(device_id)
        if device is None:
            return await self.invalid_request(f"{device} was not found")

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()
        device_config = data.get("config")
        if device_config is None:
            return await self.invalid_request(
                "Required attribute 'config' was not provided"
            )
        _LOGGER.debug(
            f"Updating device {device_id} with config {device_config}"
        )

        try:
            device.update_config(device_config)
        except (voluptuous.Error, ValueError) as msg:
            error_message = f"Error updating device {device_id}: {msg}"
            _LOGGER.warning(error_message)
            return await self.internal_error("error", error_message)
        # Update and save the configuration
        for device in self._ledfx.config["devices"]:
            if device["id"] == device_id:
                device["config"] = device_config
                break
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )
        return await self.request_success()

    async def post(self, device_id, request) -> web.Response:
        """
        Handle POST request for a device.

        Args:
            device_id (str): The ID of the device.
            request (web.Request): The request object. Not currently used.

        Returns:
            web.Response: The response object.
        """
        if device_id is None:
            return await self.invalid_request("No `device_id` provided")
        device = self._ledfx.devices.get(device_id)
        if device is None:
            error_message = f"Device with ID {device_id} not found"
            _LOGGER.info(error_message)
            return await self.invalid_request(error_message)

        try:
            if device.type == "wled":
                await device.resolve_address()

            response = {"status": "success", "virtuals": {}}
            response["paused"] = self._ledfx.virtuals._paused
            for virtual in self._ledfx.virtuals.values():
                response["virtuals"][virtual.id] = {
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
                    response["virtuals"][virtual.id][
                        "effect"
                    ] = effect_response

        except (voluptuous.Error, ValueError) as msg:
            error_message = f"Error creating device {device_id}: {msg}"
            _LOGGER.warning(error_message)
            return await self.internal_error("error", error_message)

        device.activate()
        return await self.bare_request_success(response)

    async def delete(self, device_id) -> web.Response:
        """
        Deletes a device with the specified device_id.

        Args:
            device_id (str): The ID of the device to be deleted.

        Returns:
            web.Response: The response indicating the success or failure of the delete operation.
        """
        if device_id is None:
            return await self.invalid_request("No device ID provided")
        device = self._ledfx.devices.get(device_id)
        if device is None:
            error_message = f"Device with ID {device_id} not found"
            _LOGGER.info(error_message)
            return await self.invalid_request(error_message)

        device.clear_effect()
        await device.remove_from_virtuals()
        self._ledfx.devices.destroy(device_id)

        # Update and save the configuration
        self._ledfx.config["devices"] = [
            device
            for device in self._ledfx.config["devices"]
            if device["id"] != device_id
        ]
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )
        return await self.request_success()
