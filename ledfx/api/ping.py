import logging

from aiohttp import web
from icmplib import async_ping

from ledfx.api import RestEndpoint
from ledfx.utils import resolve_destination

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/ping/{device_id}"

    async def get(self, device_id) -> web.Response:
        """
        Retrieves ping statistics for a specific device.

        Args:
            device_id (str): The ID of the device.

        Returns:
            web.Response: The response containing ping statistics.
        """
        device = self._ledfx.devices.get(device_id)

        if device is None:
            return await self.invalid_request(
                f"Device {device_id} was not found"
            )

        ping_target = await resolve_destination(
            self._ledfx.loop,
            self._ledfx.thread_executor,
            device.config["ip_address"],
        )
        ping = await async_ping(
            address=ping_target,
            count=10,
            privileged=False,
            timeout=0.500,
        )
        response = {
            "max_ping": ping.max_rtt,
            "avg_ping": ping.avg_rtt,
            "min_ping": ping.min_rtt,
            "packetlosspercent": ping.packet_loss,
        }
        return await self.bare_request_success(response)
