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
                "displays": device.displays,
            }

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

        # Generate display configuration for the device
        _LOGGER.info(f"Creating a display for device {device.name}")
        display_name = f"{device.name}"
        display_id = generate_id(display_name)
        display_config = {
            "name": display_name,
            "icon_name": device_config["icon_name"],
        }
        segments = [[device.id, 0, device_config["pixel_count"] - 1, False]]

        # create the display
        display = self._ledfx.displays.create(
            id=display_id,
            config=display_config,
            ledfx=self._ledfx,
            is_device=device.id,
        )

        # create the device as a single segment on the display
        display.update_segments(segments)

        # Update the configuration
        self._ledfx.config["displays"].append(
            {
                "id": display.id,
                "config": display.config,
                "segments": display.segments,
                "is_device": device.id,
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
                "displays": device.displays,
            },
        }
        return web.json_response(data=response, status=200)
