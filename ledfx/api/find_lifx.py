import asyncio
import logging
from json import JSONDecodeError

from aiohttp import web

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)

# Default timeout for network discovery (seconds)
DISCOVERY_TIMEOUT = 5

# Map lifx-async device types to internal category names
LIFX_CATEGORY_MAP = {
    "Light": "light",
    "HevLight": "light",
    "InfraredLight": "light",
    "MultiZoneLight": "strip",
    "MatrixLight": "matrix",
    "CeilingLight": "matrix",
    "Device": "light",  # Fallback for unknown types
}


class FindLifxEndpoint(RestEndpoint):
    """REST endpoint for LIFX device discovery and detection.

    GET: Discover all LIFX devices on the local network
    POST: Detect a specific LIFX device by IP address
    """

    ENDPOINT_PATH = "/api/find_lifx"

    async def get(self, request: web.Request) -> web.Response:
        """
        Discover all LIFX devices on the local network.

        Query parameters:
            discovery_timeout (optiona): How long to wait for replies to
                                         the discovery broadcast
            broadcast_address (optional): Broadcast address for discovery
                                          (e.g., "192.168.1.255")
            add (optional): If "true", automatically add discovered devices

        Returns:
            {
                "devices": [
                    {
                        "device_type": "lifx",
                        "category": "matrix",
                        "lifx_type": "CeilingLight",
                        "label": "Living Room",
                        "serial": "d073d5xxxxxx",
                        "ip": "192.168.1.100",
                        "added": true
                    },
                    ...
                ]
            }
        """
        from lifx import discover

        discovery_timeout = float(
            request.query.get("discovery_timeout", DISCOVERY_TIMEOUT)
        )
        broadcast_address = request.query.get(
            "broadcast_address", "255.255.255.255"
        )
        auto_add = request.query.get("add", "").lower() == "true"
        devices = []

        try:
            async for device in discover(
                timeout=discovery_timeout,
                broadcast_address=broadcast_address,
            ):
                lifx_class = type(device).__name__
                category = LIFX_CATEGORY_MAP.get(lifx_class, "light")

                try:
                    label = await device.get_label()
                except Exception:
                    label = f"LIFX {device.serial[-6:]}"

                device_info = {
                    "device_type": "lifx",
                    "category": category,
                    "lifx_type": lifx_class,
                    "label": label,
                    "serial": device.serial,
                    "ip": device.ip,
                    "added": False,
                }

                # Auto-add device if requested
                if auto_add:
                    try:
                        device_config = {
                            "name": label,
                            "ip_address": device.ip,
                            "serial": device.serial,
                        }
                        await self._ledfx.devices.add_new_device(
                            "lifx", device_config
                        )
                        device_info["added"] = True
                        _LOGGER.info(
                            "LIFX added: %s (%s) at %s",
                            label,
                            device.serial,
                            device.ip,
                        )
                    except Exception as e:
                        # Device might already exist
                        _LOGGER.warning("LIFX add failed for %s: %s", label, e)

                devices.append(device_info)

                _LOGGER.info(
                    "LIFX discovered: %s (%s) at %s -> %s",
                    label,
                    device.serial,
                    device.ip,
                    category,
                )

                await device.close()

        except asyncio.TimeoutError:
            _LOGGER.info(
                "LIFX discovery completed (timeout): found %d devices",
                len(devices),
            )
        except Exception as e:
            _LOGGER.warning("LIFX discovery error: %s", e)

        return await self.bare_request_success({"devices": devices})

    async def post(self, request: web.Request) -> web.Response:
        """
        Detect LIFX device type from IP address.

        Request body:
            {
                "ip_address": "192.168.1.100"
            }

        Returns:
            {
                "device_type": "lifx",
                "category": "matrix",
                "lifx_type": "MatrixLight",
                "label": "Living Room",
                "serial": "d073d5xxxxxx",
                "ip": "192.168.1.100"
            }
        """
        from lifx import find_by_ip

        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        ip_address = data.get("ip_address")

        if not ip_address:
            return await self.invalid_request(
                'Required attribute "ip_address" was not provided'
            )

        try:
            device = await find_by_ip(ip=ip_address)

            if device is None:
                return await self.invalid_request(
                    f"No LIFX device found at {ip_address}"
                )

            # Get device info
            lifx_type = type(device).__name__
            category = LIFX_CATEGORY_MAP.get(lifx_type, "light")

            try:
                label = await device.get_label()
            except Exception:
                label = "Unknown"

            serial = device.serial
            ip = device.ip

            # Close the connection
            await device.close()

            response = {
                "device_type": "lifx",
                "category": category,
                "lifx_type": lifx_type,
                "label": label,
                "serial": serial,
                "ip": ip,
            }

            _LOGGER.info(
                "LIFX discovery: %s (%s) at %s -> lifx (%s)",
                label,
                serial,
                ip,
                category,
            )

            return await self.bare_request_success(response)

        except Exception as e:
            _LOGGER.warning(
                "LIFX discovery failed for %s: %s",
                ip_address,
                e,
            )
            return await self.invalid_request(
                f"Failed to detect LIFX device at {ip_address}: {e}"
            )
