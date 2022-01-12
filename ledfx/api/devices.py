import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint

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
                "online": device.online,
                "virtuals": device.virtuals,
                "active_virtuals": device.active_virtuals,
            }

        return web.json_response(data=response, status=200)

    async def post(self, request) -> web.Response:
        try:
            data = await request.json()
        except JSONDecodeError:
            response = {
                "status": "failed",
                "reason": "JSON Decoding failed",
            }
            return web.json_response(data=response, status=400)

        device_config = data.get("config")
        if device_config is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "config" was not provided',
            }
            return web.json_response(data=response, status=400)

        device_type = data.get("type")
        if device_type is None:
            response = {
                "status": "failed",
                "reason": 'Required attribute "type" was not provided',
            }
            return web.json_response(data=response, status=400)

        try:
            device = await self._ledfx.devices.add_new_device(
                device_type, device_config
            )
        except ValueError as msg:
            response = {
                "status": "failed",
                "payload": {"type": "error", "reason": str(msg)},
            }
            return web.json_response(data=response, status=202)

        response = {
            "status": "success",
            "payload": {
                "type": "success",
                "reason": f"Created device {device.name}",
            },
            "device": {
                "type": device.type,
                "config": device.config,
                "id": device.id,
                "virtuals": device.virtuals,
            },
        }
        return web.json_response(data=response, status=200)
