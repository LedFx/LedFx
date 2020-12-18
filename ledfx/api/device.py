import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config

_LOGGER = logging.getLogger(__name__)


class DeviceEndpoint(RestEndpoint):
    """REST end-point for querying and managing devices"""

    ENDPOINT_PATH = "/api/devices/{device_id}"

    async def get(self, device_id) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        response = device.config
        return web.json_response(data=response, status=200)

    async def put(self, device_id, request) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        data = await request.json()
        device_config = data.get("config")
        if device_config is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "config" was not provided',
            }
            return web.json_response(data=response, status=500)

        # TODO: Support dynamic device configuration updates. For now
        # remove the device and re-create it
        _LOGGER.info(
            ("Updating device {} with config {}").format(
                device_id, device_config
            )
        )
        self._ledfx.devices.destroy(device_id)

        device = self._ledfx.devices.create(
            id=device_id,
            type=device_config.get("type"),
            config=device_config,
            ledfx=self._ledfx,
        )

        # Update and save the configuration
        for device in self._ledfx.config["devices"]:
            if device["id"] == device_id:
                device["config"] = device_config
                break
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {"status": "success"}
        return web.json_response(data=response, status=200)

    async def delete(self, device_id) -> web.Response:
        device = self._ledfx.devices.get(device_id)
        if device is None:
            response = {"not found": 404}
            return web.json_response(data=response, status=404)

        device.clear_effect()
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

        response = {"status": "success"}
        return web.json_response(data=response, status=200)
