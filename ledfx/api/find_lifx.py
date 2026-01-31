import asyncio
import ipaddress
import logging
import random
from json import JSONDecodeError

from aiohttp import web
from lifx import LifxError, discover_mdns, find_by_ip
from lifx.network import UdpTransport, create_message, parse_message
from lifx.protocol import packets

from ledfx.api import RestEndpoint

_LOGGER = logging.getLogger(__name__)

# Fallback defaults (used if config values are missing)
DEFAULT_DISCOVERY_TIMEOUT = 30
DEFAULT_BROADCAST_ADDRESS = "255.255.255.255"

# Number of broadcast packets to send (handles packet loss on large networks)
UDP_BROADCAST_COUNT = 3
# Delay between broadcast packets (seconds)
UDP_BROADCAST_DELAY = 0.3
# LIFX UDP port
LIFX_UDP_PORT = 56700

# Valid discovery methods
DISCOVERY_METHODS = ("udp", "mdns", "both")

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

    def _find_existing_lifx_by_serial(self, serial):
        """Check if a LIFX device already exists by serial number."""
        for existing in self._ledfx.devices.values():
            if (
                existing.type == "lifx"
                and existing.config.get("serial") == serial
            ):
                return existing
        return None

    async def _process_discovered_device(self, device, auto_add, seen_serials):
        """
        Process a discovered LIFX device and optionally add it.

        Args:
            device: The lifx-async device object
            auto_add: Whether to automatically add the device
            seen_serials: Set of already-seen serial numbers (for deduplication)

        Returns:
            Device info dict, or None if device was already seen
        """
        # Skip if we've already seen this device (for "both" method)
        if device.serial in seen_serials:
            await device.close()
            return None
        seen_serials.add(device.serial)

        lifx_class = type(device).__name__
        category = LIFX_CATEGORY_MAP.get(lifx_class, "light")

        try:
            label = await device.get_label()
        except (LifxError, OSError):
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
            existing = self._find_existing_lifx_by_serial(device.serial)
            if existing:
                device_info["added"] = False
                device_info["existing_name"] = existing.name
                _LOGGER.debug(
                    "LIFX %s (%s) already exists as %s",
                    label,
                    device.serial,
                    existing.name,
                )
            else:
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
                except (LifxError, OSError, ValueError) as e:
                    _LOGGER.warning("LIFX add failed for %s: %s", label, e)

        _LOGGER.info(
            "LIFX discovered: %s (%s) at %s -> %s",
            label,
            device.serial,
            device.ip,
            category,
        )

        await device.close()
        return device_info

    async def _discover_udp(
        self, timeout, broadcast_address, auto_add, seen_serials
    ):
        """
        Discover LIFX devices via UDP broadcast.

        Sends multiple broadcast packets upfront to handle packet loss on large
        networks, then listens for responses for the full timeout duration.
        LIFX devices have a response cooldown, so subsequent broadcasts to the
        same device won't yield additional responses - hence we blast packets
        at the start rather than spacing them out.

        Args:
            timeout: Discovery timeout in seconds
            broadcast_address: UDP broadcast address
            auto_add: Whether to automatically add devices
            seen_serials: Set of already-seen serial numbers

        Returns:
            List of discovered device info dicts
        """
        devices = []

        # Generate a random source ID for this discovery session
        source_id = random.randint(2, 0xFFFFFFFF)

        # Create GetService broadcast packet
        get_service = packets.Device.GetService()
        message = create_message(
            get_service,
            source=source_id,
            target=b"\x00\x00\x00\x00\x00\x00\x00\x00",  # Broadcast target
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

                # Listen for responses for the full timeout
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

                        # Parse the response
                        header, _payload = parse_message(data)

                        # Extract serial from header target field
                        serial = header.target.hex()

                        # Skip if already seen
                        if serial in seen_serials:
                            continue

                        ip = addr[0]

                        _LOGGER.debug(
                            "LIFX UDP response from %s (serial=%s)",
                            ip,
                            serial,
                        )

                        # Use find_by_ip to get full device info
                        try:
                            device = await find_by_ip(ip=ip)
                            if device:
                                device_info = (
                                    await self._process_discovered_device(
                                        device, auto_add, seen_serials
                                    )
                                )
                                if device_info:
                                    device_info["discovery_method"] = "udp"
                                    devices.append(device_info)
                                    seen_serials.add(serial)
                            else:
                                seen_serials.add(serial)
                        except (LifxError, OSError) as e:
                            seen_serials.add(serial)
                            _LOGGER.debug(
                                "LIFX UDP: couldn't get device info for %s: %s",
                                ip,
                                e,
                            )

                    except LifxError:
                        # Timeout on receive, continue loop to check overall timeout
                        pass

                _LOGGER.info(
                    "LIFX UDP discovery completed: %d responses, %d devices found",
                    response_count,
                    len(devices),
                )

        except (LifxError, OSError) as e:
            _LOGGER.warning("LIFX UDP discovery error: %s", e)

        return devices

    async def _discover_mdns(self, timeout, auto_add, seen_serials):
        """
        Discover LIFX devices via mDNS/DNS-SD.

        Args:
            timeout: Discovery timeout in seconds
            auto_add: Whether to automatically add devices
            seen_serials: Set of already-seen serial numbers

        Returns:
            List of discovered device info dicts
        """
        devices = []
        try:
            async for device in discover_mdns(timeout=timeout):
                device_info = await self._process_discovered_device(
                    device, auto_add, seen_serials
                )
                if device_info:
                    device_info["discovery_method"] = "mdns"
                    devices.append(device_info)
        except asyncio.TimeoutError:
            _LOGGER.info(
                "LIFX mDNS discovery completed (timeout): found %d devices",
                len(devices),
            )
        except (LifxError, OSError) as e:
            _LOGGER.warning("LIFX mDNS discovery error: %s", e)
        return devices

    async def get(self, request: web.Request) -> web.Response:
        """
        Discover all LIFX devices on the local network.

        Query parameters:
            method (optional): Discovery method - "udp" (default), "mdns", or "both"
            discovery_timeout (optional): How long to wait for replies (seconds)
            broadcast_address (optional): UDP broadcast address for discovery
                                          (e.g., "192.168.1.255")
            add (optional): If "true", automatically add discovered devices

        Returns:
            {
                "status": "success",
                "method": "udp",
                "devices": [
                    {
                        "device_type": "lifx",
                        "category": "matrix",
                        "lifx_type": "CeilingLight",
                        "label": "Living Room",
                        "serial": "d073d5xxxxxx",
                        "ip": "192.168.1.100",
                        "added": true,
                        "discovery_method": "udp"
                    },
                    ...
                ]
            }
        """
        method = request.query.get("method", "udp").lower()
        if method not in DISCOVERY_METHODS:
            _LOGGER.warning("Invalid discovery method: %s", method)
            return await self.invalid_request(
                f"Invalid discovery method '{method}'. Must be one of: {', '.join(DISCOVERY_METHODS)}"
            )

        # Read fresh values from global config (allows frontend to update before discovery)
        config_timeout = self._ledfx.config.get(
            "lifx_discovery_timeout", DEFAULT_DISCOVERY_TIMEOUT
        )
        config_broadcast = self._ledfx.config.get(
            "lifx_broadcast_address", DEFAULT_BROADCAST_ADDRESS
        )
        _LOGGER.debug(
            "LIFX config values: timeout=%s, broadcast=%s",
            config_timeout,
            config_broadcast,
        )

        try:
            discovery_timeout = float(
                request.query.get("discovery_timeout", config_timeout)
            )
            if not (0 < discovery_timeout <= 300):
                _LOGGER.warning(
                    "Invalid discovery_timeout value: %s", discovery_timeout
                )
                return await self.invalid_request(
                    "Invalid discovery_timeout: must be greater than 0 and at most 300 seconds"
                )
        except (ValueError, TypeError):
            _LOGGER.warning(
                "Invalid discovery_timeout: non-numeric value: %s",
                request.query.get("discovery_timeout"),
            )
            return await self.invalid_request(
                "Invalid discovery_timeout: must be a numeric value"
            )

        broadcast_address = request.query.get(
            "broadcast_address", config_broadcast
        )
        try:
            ipaddress.IPv4Address(broadcast_address)
        except ipaddress.AddressValueError:
            _LOGGER.warning("Invalid broadcast_address: %s", broadcast_address)
            return await self.invalid_request(
                f"Invalid broadcast_address: {broadcast_address}"
            )

        auto_add = request.query.get("add", "").lower() == "true"

        _LOGGER.info(
            "LIFX discovery starting: method=%s, timeout=%.0fs, "
            "broadcast_address=%s, auto_add=%s",
            method,
            discovery_timeout,
            broadcast_address,
            auto_add,
        )

        devices = []
        seen_serials: set[str] = set()

        if method in ("mdns", "both"):
            mdns_devices = await self._discover_mdns(
                discovery_timeout, auto_add, seen_serials
            )
            devices.extend(mdns_devices)
            _LOGGER.info(
                "LIFX mDNS discovery found %d devices", len(mdns_devices)
            )

        if method in ("udp", "both"):
            udp_devices = await self._discover_udp(
                discovery_timeout, broadcast_address, auto_add, seen_serials
            )
            devices.extend(udp_devices)
            _LOGGER.info(
                "LIFX UDP discovery found %d devices", len(udp_devices)
            )

        return await self.bare_request_success(
            {
                "method": method,
                "devices": devices,
            }
        )

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
        try:
            data = await request.json()
        except JSONDecodeError:
            _LOGGER.warning("Failed to decode JSON in LIFX POST request")
            return await self.json_decode_error()

        if not isinstance(data, dict):
            _LOGGER.warning("LIFX POST request JSON body is not an object")
            return await self.invalid_request(
                "JSON body must be an object"
            )

        ip_address = data.get("ip_address")

        if not ip_address:
            _LOGGER.warning("Missing required ip_address in LIFX POST request")
            return await self.invalid_request(
                'Required attribute "ip_address" was not provided'
            )

        try:
            ipaddress.IPv4Address(ip_address)
        except ipaddress.AddressValueError:
            _LOGGER.warning("Invalid IPv4 address: %s", ip_address)
            return await self.invalid_request(
                "Invalid ip_address: must be a valid IPv4 address"
            )

        try:
            device = await find_by_ip(ip=ip_address)

            if device is None:
                _LOGGER.warning("No LIFX device found at %s", ip_address)
                return await self.invalid_request(
                    f"No LIFX device found at {ip_address}"
                )

            # Use context manager to ensure cleanup and auto-populate label
            async with device:
                lifx_type = type(device).__name__
                category = LIFX_CATEGORY_MAP.get(lifx_type, "light")
                label = device.label or "Unknown"
                serial = device.serial
                ip = device.ip

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

        except (LifxError, OSError) as e:
            _LOGGER.warning(
                "LIFX discovery failed for %s: %s",
                ip_address,
                e,
            )
            return await self.invalid_request(
                f"Failed to detect LIFX device at {ip_address}: {e}"
            )
