import logging

from aiohttp import web

from ledfx.api import RestEndpoint
from ledfx.config import save_config
from ledfx.utils import generate_id

_LOGGER = logging.getLogger(__name__)


class DevicesEndpoint(RestEndpoint):
    """REST end-point for querying and managing devices"""

    ENDPOINT_PATH = "/api/devices"

    async def get(self) -> web.Response:
        response = {"status": "success", "devices": {}}
        for device in self._ledfx.devices.values():
            response["devices"][device.id] = {
                "config": device.config,
                "id": device.id,
                "type": device.type,
                "effect": {},
            }
            if device.active_effect:
                effect_response = {}
                effect_response["config"] = device.active_effect.config
                effect_response["name"] = device.active_effect.name
                effect_response["type"] = device.active_effect.type
                response["devices"][device.id]["effect"] = effect_response

        return web.json_response(data=response, status=200)

    async def post(self, request) -> web.Response:
        data = await request.json()

        device_config = data.get("config")
        if device_config is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "config" was not provided',
            }
            return web.json_response(data=response, status=500)

        device_type = data.get("type")
        if device_type is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "type" was not provided',
            }
            return web.json_response(data=response, status=500)

        device_id = generate_id(device_config.get("name"))
        # Remove the device it if already exist?

        # Create the device
        _LOGGER.info(
            "Adding device of type {} with config {}".format(
                device_type, device_config
            )
        )
        device = self._ledfx.devices.create(
            id=device_id,
            type=device_type,
            config=device_config,
            ledfx=self._ledfx,
        )

        # Update and save the configuration
        self._ledfx.config["devices"].append(
            {
                "id": device.id,
                "type": device.type,
                "config": device.config,
            }
        )
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

        response = {
            "status": "success",
            "device": {
                "type": device.type,
                "config": device.config,
                "id": device.id,
            },
        }
        return web.json_response(data=response, status=200)
