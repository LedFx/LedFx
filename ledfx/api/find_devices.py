import asyncio
import logging
import random
from json import JSONDecodeError

from aiohttp import web
from lifx import LifxError, discover_mdns, find_by_ip
from lifx.network import UdpTransport, create_message, parse_message
from lifx.protocol import packets

from ledfx.api import RestEndpoint
from ledfx.utils import async_fire_and_forget, set_name_to_icon

_LOGGER = logging.getLogger(__name__)

# Fallback defaults for LIFX discovery (used if config values are missing)
DEFAULT_LIFX_TIMEOUT = 30
DEFAULT_LIFX_BROADCAST = "255.255.255.255"

# Number of broadcast packets to send (handles packet loss on large networks)
UDP_BROADCAST_COUNT = 3
# Delay between broadcast packets (seconds)
UDP_BROADCAST_DELAY = 0.3
# LIFX UDP port
LIFX_UDP_PORT = 56700

# Map lifx-async device types to internal category names
LIFX_CATEGORY_MAP = {
    "Light": "light",
    "HevLight": "light",
    "InfraredLight": "light",
    "MultiZoneLight": "strip",
    "MatrixLight": "matrix",
    "CeilingLight": "matrix",
    "Device": "light",
}

# Supported device types for discovery
SUPPORTED_DEVICE_TYPES = ("wled", "lifx")


def handle_exception(future):
    # Ignore exceptions, these will be raised when a device is found that already exists
    future.exception()


class FindDevicesEndpoint(RestEndpoint):
    """REST end-point for detecting and adding devices (WLED, LIFX)"""

    ENDPOINT_PATH = "/api/find_devices"

    def _find_existing_lifx_by_serial(self, serial):
        """Check if a LIFX device already exists by serial number."""
        for existing in self._ledfx.devices.values():
            if (
                existing.type == "lifx"
                and existing.config.get("serial") == serial
            ):
                return existing
        return None

    async def _discover_lifx(self):
        """
        Discover and add LIFX devices via mDNS and UDP broadcast.

        Reads fresh values from global config to pick up any frontend changes.
        """
        # Read fresh values from global config (allows frontend to update before discovery)
        timeout = self._ledfx.config.get(
            "lifx_discovery_timeout", DEFAULT_LIFX_TIMEOUT
        )
        broadcast_address = self._ledfx.config.get(
            "lifx_broadcast_address", DEFAULT_LIFX_BROADCAST
        )
        _LOGGER.debug(
            "LIFX config values: timeout=%s, broadcast=%s",
            timeout,
            broadcast_address,
        )

        _LOGGER.info(
            "LIFX discovery starting: timeout=%.0fs, broadcast_address=%s",
            timeout,
            broadcast_address,
        )

        seen_serials: set[str] = set()
        devices_found = 0

        # mDNS discovery first
        try:
            async for device in discover_mdns(timeout=timeout):
                if await self._process_lifx_device(device, seen_serials):
                    devices_found += 1
        except asyncio.TimeoutError:
            pass
        except (LifxError, OSError) as e:
            _LOGGER.warning("LIFX mDNS discovery error: %s", e)

        _LOGGER.info("LIFX mDNS discovery found %d devices", devices_found)

        # UDP broadcast discovery - send multiple packets upfront for reliability
        udp_found = 0

        # Generate a random source ID for this discovery session
        source_id = random.randint(2, 0xFFFFFFFF)

        # Create GetService broadcast packet
        get_service = packets.Device.GetService()
        message = create_message(
            get_service,
            source=source_id,
            target=b"\x00\x00\x00\x00\x00\x00\x00\x00",
            res_required=True,
        )

        try:
            async with UdpTransport(broadcast=True) as transport:
                broadcast_addr = (broadcast_address, LIFX_UDP_PORT)

                # Send multiple broadcast packets to handle packet loss
                for i in range(UDP_BROADCAST_COUNT):
                    await transport.send(message, broadcast_addr)
                    _LOGGER.info(
                        "LIFX UDP broadcast %d/%d sent to %s:%d",
                        i + 1,
                        UDP_BROADCAST_COUNT,
                        broadcast_address,
                        LIFX_UDP_PORT,
                    )
                    if i < UDP_BROADCAST_COUNT - 1:
                        await asyncio.sleep(UDP_BROADCAST_DELAY)

                # Listen for responses
                _LOGGER.info(
                    "LIFX UDP listening for responses (%.0fs timeout)...",
                    timeout,
                )

                start_time = asyncio.get_event_loop().time()
                response_count = 0

                while True:
                    elapsed = asyncio.get_event_loop().time() - start_time
                    remaining = timeout - elapsed

                    if remaining <= 0:
                        break

                    try:
                        data, addr = await transport.receive(
                            timeout=min(remaining, 1.0)
                        )
                        response_count += 1

                        header, payload = parse_message(data)
                        serial = header.target.hex()

                        if serial in seen_serials:
                            continue

                        ip = addr[0]

                        _LOGGER.debug(
                            "LIFX UDP response from %s (serial=%s)", ip, serial
                        )

                        try:
                            device = await find_by_ip(ip=ip)
                            if device:
                                if await self._process_lifx_device(
                                    device, seen_serials
                                ):
                                    udp_found += 1
                        except (LifxError, OSError) as e:
                            _LOGGER.debug(
                                "LIFX UDP: couldn't get device info for %s: %s",
                                ip,
                                e,
                            )

                    except LifxError:
                        pass  # Timeout on receive

                _LOGGER.info(
                    "LIFX UDP discovery completed: %d responses, %d devices added",
                    response_count,
                    udp_found,
                )

        except (LifxError, OSError) as e:
            _LOGGER.warning("LIFX UDP discovery error: %s", e)

        _LOGGER.info(
            "LIFX discovery completed: %d total devices found",
            devices_found + udp_found,
        )

    async def _process_lifx_device(self, device, seen_serials):
        """
        Process a discovered LIFX device and add it if new.

        Returns True if device was newly added, False otherwise.
        """
        if device.serial in seen_serials:
            await device.close()
            return False
        seen_serials.add(device.serial)

        lifx_class = type(device).__name__
        category = LIFX_CATEGORY_MAP.get(lifx_class, "light")

        try:
            label = await device.get_label()
        except (LifxError, OSError):
            label = f"LIFX {device.serial[-6:]}"

        # Check if device already exists
        existing = self._find_existing_lifx_by_serial(device.serial)
        if existing:
            _LOGGER.debug(
                "LIFX %s (%s) already exists as %s",
                label,
                device.serial,
                existing.name,
            )
            await device.close()
            return False

        # Add the device
        try:
            device_config = {
                "name": label,
                "ip_address": device.ip,
                "serial": device.serial,
            }
            await self._ledfx.devices.add_new_device("lifx", device_config)
            _LOGGER.info(
                "LIFX added: %s (%s) at %s -> %s",
                label,
                device.serial,
                device.ip,
                category,
            )
            await device.close()
            return True
        except (LifxError, OSError, ValueError) as e:
            _LOGGER.warning("LIFX add failed for %s: %s", label, e)
            await device.close()
            return False

    async def post(self, request: web.Request) -> web.Response:
        """
        Find and add devices on the LAN.

        Args:
            request (web.Request): The request object.

        Request body:
            {
                "name_to_icon": {...},  // Required for WLED
                "device_types": ["wled", "lifx"]  // Optional, defaults to ["wled"]
            }

        Returns:
            A web.Response object indicating the success of the request.
        """
        try:
            data = await request.json()
        except JSONDecodeError:
            return await self.json_decode_error()

        # Get device types to discover (default to WLED for backward compat)
        device_types = data.get("device_types", ["wled"])
        if device_types is None:
            device_types = ["wled"]
        elif isinstance(device_types, str):
            device_types = [device_types]
        elif not isinstance(device_types, list):
            return await self.invalid_request(
                f"device_types must be a list or string, not {type(device_types).__name__}. "
                f"Supported types: {SUPPORTED_DEVICE_TYPES}"
            )

        # Validate device types
        invalid_types = [
            t for t in device_types if t not in SUPPORTED_DEVICE_TYPES
        ]
        if invalid_types:
            return await self.invalid_request(
                f"Invalid device type(s): {invalid_types}. "
                f"Supported types: {SUPPORTED_DEVICE_TYPES}"
            )

        # Handle WLED discovery
        if "wled" in device_types:
            name_to_icon = data.get("name_to_icon")
            if name_to_icon is None:
                return await self.invalid_request(
                    'Required attribute "name_to_icon" was not provided for WLED discovery'
                )
            set_name_to_icon(name_to_icon)
            async_fire_and_forget(
                self._ledfx.zeroconf.discover_wled_devices(),
                loop=self._ledfx.loop,
                exc_handler=handle_exception,
            )

        # Handle LIFX discovery
        if "lifx" in device_types:
            async_fire_and_forget(
                self._discover_lifx(),
                loop=self._ledfx.loop,
                exc_handler=handle_exception,
            )

        return await self.request_success()

    async def get(self, request: web.Request) -> web.Response:
        """
        Find and add devices on the LAN via GET request.

        Query parameters:
            device_types (optional): Comma-separated list of device types
                                     (e.g., "wled,lifx"). Defaults to "wled".

        Returns:
            web.Response: The response object indicating the success of the request.
        """
        # Parse device types from query string
        device_types_param = request.query.get("device_types", "wled")
        device_types = [t.strip() for t in device_types_param.split(",")]

        # Validate device types
        invalid_types = [
            t for t in device_types if t not in SUPPORTED_DEVICE_TYPES
        ]
        if invalid_types:
            return await self.invalid_request(
                f"Invalid device type(s): {invalid_types}. "
                f"Supported types: {SUPPORTED_DEVICE_TYPES}"
            )

        # Handle WLED discovery
        if "wled" in device_types:
            async_fire_and_forget(
                self._ledfx.zeroconf.discover_wled_devices(),
                loop=self._ledfx.loop,
                exc_handler=handle_exception,
            )

        # Handle LIFX discovery
        if "lifx" in device_types:
            async_fire_and_forget(
                self._discover_lifx(),
                loop=self._ledfx.loop,
                exc_handler=handle_exception,
            )

        return await self.request_success()
