import logging

from aiohttp import web
from icmplib import async_ping

from ledfx.api import RestEndpoint
from ledfx.utils import resolve_destination

_LOGGER = logging.getLogger(__name__)


class InfoEndpoint(RestEndpoint):
    ENDPOINT_PATH = "/api/ping/{device_id}"

    async def get(self, device_id) -> web.Response:
        device = self._ledfx.devices.get(device_id)

        if device is None:
            response = {f"{device_id} not found": 404}
            return web.json_response(data=response, status=404)

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

        return web.json_response(data=response, status=200)
