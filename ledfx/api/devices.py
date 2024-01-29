import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)


class DevicesEndpoint(RestEndpoint):
    """REST end-point for querying and managing devices"""

    ENDPOINT_PATH = "/api/devices"

    async def get(self) -> web.Response:
        """
        Retrieves information about all devices.

        Returns:
            web.Response: The response containing the device information.
        """
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
        return await self.bare_request_success(response)

    async def post(self, request: web.Request) -> web.Response:
        """
        Handle POST request to create a new device.

        Args:
            request (web.Request): The incoming request object that contains the device `config` and `type`

        Returns:
            web.Response: The response containing the result of the request.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        device_config = data.get("config")
        device_type = data.get("type")

        missing_attributes = []
        if device_config is None:
            missing_attributes.append("device_config")
        if device_type is None:
            missing_attributes.append("device_type")

        if missing_attributes:
            return await self.invalid_request(
                f'Required attributes {", ".join(missing_attributes)} were not provided'
            )
        try:
            device = await self._ledfx.devices.add_new_device(
                device_type, device_config
            )
        except ValueError as msg:
            error_message = f"Error creating device: {msg}"
            _LOGGER.warning(error_message)
            return await self.internal_error(error_message)

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

        if device.type == "wled":
            nodes = await device.wled.get_nodes()
            if "nodes" in nodes:
                response["nodes"] = nodes["nodes"]

        return await self.bare_request_success(response)
