import logging

import numpy as np
from aiohttp import web
from tcp_latency import measure_latency

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
        output = measure_latency(
            host=ping_target,
            port=80,
            runs=10,
            wait=0.25,
            timeout=0.2,
            human_output=False,
        )

        ping_count = len(output)

        valid_pings = [i for i in output if i is not None]
        valid_ping_count = len(valid_pings)
        if valid_ping_count >= 1:

            max_ping = np.round(np.max(valid_pings), decimals=2)
            min_ping = np.round(np.min(valid_pings), decimals=2)
            avg_ping = np.round(np.average(valid_pings), decimals=2)

            successful_packets = (valid_ping_count / ping_count) * 100
            packetloss = successful_packets - 100
            response = {
                "max_ping": max_ping,
                "avg_ping": avg_ping,
                "min_ping": min_ping,
                "packetlosspercent": float(packetloss),
            }

            return web.json_response(data=response, status=200)
        else:

            response = {"packetlosspercent": float(100)}

            return web.json_response(data=response, status=200)
