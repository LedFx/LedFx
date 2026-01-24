import asyncio
import logging

import numpy as np
import voluptuous as vol
from lifx import (
    HSBK,
    Animator,
    CeilingLight,
    HevLight,
    InfraredLight,
    LifxError,
    Light,
    MatrixLight,
    MultiZoneLight,
    find_by_ip,
)
from lifx.exceptions import LifxTimeoutError
from lifx.protocol import packets

from ledfx.devices import NetworkedDevice, fps_validator
from ledfx.utils import async_fire_and_forget

_LOGGER = logging.getLogger(__name__)


# Max refresh rate for single bulbs (prevents strobing)
MAX_FPS_LIGHT = 20

# Map lifx-async device types to internal type identifiers
LIFX_TYPE_MAP = {
    "Light": "light",
    "HevLight": "light",
    "InfraredLight": "light",
    "MultiZoneLight": "strip",
    "MatrixLight": "matrix",
    "CeilingLight": "matrix",
    "Device": "light",  # Fallback
}

# Map class names to lifx-async device classes for direct instantiation
LIFX_CLASS_MAP = {
    "MatrixLight": MatrixLight,
    "CeilingLight": CeilingLight,
    "MultiZoneLight": MultiZoneLight,
    "Light": Light,
    "HevLight": HevLight,
    "InfraredLight": InfraredLight,
}


def numpy_rgb_to_hsbk(rgb_array: np.ndarray, kelvin: int = 3500) -> list:
    """Convert NumPy RGB array to protocol-ready HSBK list.

    Args:
        rgb_array: Shape (N, 3) with RGB values 0-255
        kelvin: Color temperature

    Returns:
        List of (hue, sat, bright, kelvin) tuples for send_frame()
    """
    rgb_norm = rgb_array.astype(np.float32) / 255.0
    r, g, b = rgb_norm[:, 0], rgb_norm[:, 1], rgb_norm[:, 2]

    maxc = np.maximum(np.maximum(r, g), b)
    minc = np.minimum(np.minimum(r, g), b)
    delta = maxc - minc

    v = maxc  # Brightness
    s = np.zeros_like(maxc)
    np.divide(delta, maxc, out=s, where=maxc > 0)  # Saturation

    h = np.zeros_like(r)
    mask = delta > 0

    red_max = mask & (maxc == r)
    h[red_max] = ((g[red_max] - b[red_max]) / delta[red_max]) % 6

    green_max = mask & (maxc == g)
    h[green_max] = (b[green_max] - r[green_max]) / delta[green_max] + 2

    blue_max = mask & (maxc == b)
    h[blue_max] = (r[blue_max] - g[blue_max]) / delta[blue_max] + 4

    h = h / 6  # Normalize to 0-1

    hue_proto = (h * 65535).astype(np.uint16)
    sat_proto = (s * 65535).astype(np.uint16)
    bright_proto = (v * 65535).astype(np.uint16)

    return [
        (int(hue_proto[i]), int(sat_proto[i]), int(bright_proto[i]), kelvin)
        for i in range(len(rgb_array))
    ]


class LifxDevice(NetworkedDevice):
    """Unified LIFX device with auto-detection.

    Automatically detects device type (bulb, strip, or matrix) on connection
    and configures itself appropriately. Users only need to provide an IP.
    """

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Optional(
                "pixel_count",
                description="Number of pixels (auto-detected on connect)",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
            vol.Optional(
                "refresh_rate",
                description="Target rate that pixels are sent to the device",
                default=30,
            ): fps_validator,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "LIFX"
        self._device = None  # The lifx-async device object
        self._lifx_type = None  # "light", "strip", or "matrix"
        self._connected = False

        # Strip-specific
        self._zone_count = 1
        self._has_extended = False

        # Matrix-specific
        self._tiles = []
        self._total_pixels = config.get("pixel_count", 1)
        self._matrix_width = 0
        self._matrix_height = 0
        self._perm = None

        # Animation module for matrix/strip (high performance)
        self._animator = None

    async def async_initialize(self):
        """Initialize device and auto-detect type during creation."""
        await super().async_initialize()
        await self._detect_device_type()

        # Update virtual rows for matrix devices after detection
        if self._lifx_type == "matrix" and self._matrix_height > 0:
            self._update_virtual_rows()

    async def _detect_device_type(self):
        """Detect LIFX device type and update config accordingly."""
        try:
            ip = self._config["ip_address"]
            device = await find_by_ip(ip=ip)

            if device is None:
                _LOGGER.warning(
                    "LIFX %s: No device found at %s during detection",
                    self._config["name"],
                    ip,
                )
                return

            async with device:
                # Save serial, class, and type for faster future connections
                self._config["serial"] = device.serial
                lifx_class = type(device).__name__
                self._config["lifx_class"] = lifx_class
                self._lifx_type = LIFX_TYPE_MAP.get(lifx_class, "light")
                self._config["lifx_type"] = self._lifx_type

                _LOGGER.info(
                    "LIFX %s: Detected %s (%s) serial=%s",
                    self._config["name"],
                    lifx_class,
                    self._lifx_type,
                    device.serial,
                )

                # Get device info based on type
                # CeilingLight is a subclass of MatrixLight
                if isinstance(device, MatrixLight):
                    self._lifx_type = "matrix"
                    self._device_type = "LIFX Matrix"
                    tiles = await device.get_device_chain()
                    self._tiles, self._total_pixels = self._collect_tile_info(
                        tiles
                    )

                    if self._tiles:
                        self._perm = self._build_permutation(tiles)
                        self._config["pixel_count"] = self._total_pixels
                        self._config["matrix_width"] = self._matrix_width
                        self._config["matrix_height"] = self._matrix_height
                        _LOGGER.info(
                            "LIFX %s: Matrix %dx%d (%d pixels)",
                            self._config["name"],
                            self._matrix_width,
                            self._matrix_height,
                            self._total_pixels,
                        )
                    else:
                        _LOGGER.warning(
                            "LIFX %s: Matrix device returned no tiles",
                            self._config["name"],
                        )

                elif isinstance(device, MultiZoneLight):
                    self._lifx_type = "strip"
                    self._device_type = "LIFX Strip"
                    self._zone_count = await device.get_zone_count()
                    self._config["pixel_count"] = self._zone_count

                    if not device.capabilities:
                        await device._ensure_capabilities()
                    if (
                        device.capabilities
                        and device.capabilities.has_extended_multizone
                    ):
                        self._has_extended = True

                    _LOGGER.info(
                        "LIFX %s: Strip with %d zones (extended=%s)",
                        self._config["name"],
                        self._zone_count,
                        self._has_extended,
                    )

                elif isinstance(device, (Light, HevLight, InfraredLight)):
                    self._lifx_type = "light"
                    self._device_type = "LIFX Light"
                    self._config["pixel_count"] = 1
                    _LOGGER.info("LIFX %s: Single bulb", self._config["name"])

        except (LifxError, OSError) as e:
            _LOGGER.warning(
                "LIFX %s: Detection failed: %s", self._config["name"], e
            )

    @property
    def pixel_count(self):
        if self._lifx_type == "matrix":
            return self._total_pixels
        elif self._lifx_type == "strip":
            return self._zone_count
        return self._config.get("pixel_count", 1)

    @property
    def is_matrix(self):
        return self._lifx_type == "matrix"

    @property
    def matrix_width(self):
        return self._matrix_width if self._lifx_type == "matrix" else 0

    @property
    def matrix_height(self):
        return self._matrix_height if self._lifx_type == "matrix" else 0

    def _build_permutation(self, tiles):
        """Build permutation array for matrix devices.

        Maps LedFx row-major pixel order to LIFX tile layout using
        tile position data (user_x, user_y).
        """
        coords = []
        for tile in tiles:
            tile_x = int(tile.user_x)
            tile_y = int(tile.user_y)
            for local_idx in range(tile.width * tile.height):
                local_x = local_idx % tile.width
                local_y = local_idx // tile.width
                global_x = tile_x + local_x
                global_y = tile_y + local_y
                coords.append((global_x, global_y))

        coords = np.array(coords, dtype=np.float32)

        x_min, x_max = coords[:, 0].min(), coords[:, 0].max()
        y_min, y_max = coords[:, 1].min(), coords[:, 1].max()
        self._matrix_width = int(x_max - x_min + 1)
        self._matrix_height = int(y_max - y_min + 1)

        cols = (coords[:, 0] - x_min).astype(np.int32)
        rows = (coords[:, 1] - y_min).astype(np.int32)

        raster_idx = rows * self._matrix_width + cols
        return raster_idx.astype(np.int64)

    def _collect_tile_info(self, tiles):
        """Collect tile metadata and compute total pixels.

        Args:
            tiles: List of tile objects from device.get_device_chain()

        Returns:
            Tuple of (tile_list, total_pixels)
        """
        tile_list = []
        total_pixels = 0

        for tile in tiles:
            tile_pixels = tile.width * tile.height
            tile_list.append(
                {
                    "index": tile.tile_index,
                    "width": tile.width,
                    "height": tile.height,
                    "pixels": tile_pixels,
                    "offset": total_pixels,
                    "user_x": tile.user_x,
                    "user_y": tile.user_y,
                }
            )
            total_pixels += tile_pixels

        return tile_list, total_pixels

    async def _create_animator(self):
        """Create Animator for high-performance frame delivery."""
        try:
            ip = self._config["ip_address"]
            serial = self._config.get("serial")

            if self._lifx_type == "matrix":
                lifx_class = self._config.get("lifx_class")
                device_cls = LIFX_CLASS_MAP.get(lifx_class, MatrixLight)

                if serial:
                    self._device = device_cls(serial=serial, ip=ip)
                else:
                    self._device = await device_cls.from_ip(ip)

                await self._device.set_power(True)
                self._animator = await Animator.for_matrix(self._device)

            elif self._lifx_type == "strip":
                if serial:
                    self._device = MultiZoneLight(serial=serial, ip=ip)
                else:
                    self._device = await MultiZoneLight.from_ip(ip)

                await self._device.set_power(True)
                self._animator = await Animator.for_multizone(self._device)

            self._connected = True
            self._online = True

            _LOGGER.info(
                "LIFX %s: Animator ready (%dx%d, %d pixels)",
                self.name,
                self._animator.canvas_width,
                self._animator.canvas_height,
                self._animator.pixel_count,
            )

            # Update virtual rows for matrix devices
            if self._lifx_type == "matrix":
                self._update_virtual_rows()

        except (LifxError, LifxTimeoutError, OSError) as e:
            _LOGGER.warning(
                "LIFX %s: Animator creation failed: %s",
                self.name,
                e,
                exc_info=True,
            )
            self._animator = None
            self._connected = False
            self._online = False

    async def _async_connect(self):
        """Connect to device using saved serial/type for speed."""
        try:
            ip = self._config["ip_address"]
            serial = self._config.get("serial")
            lifx_type = self._config.get("lifx_type")

            # Use saved info for direct instantiation (faster)
            lifx_class = self._config.get("lifx_class")
            if serial and lifx_type and lifx_class:
                device_cls = LIFX_CLASS_MAP.get(lifx_class, Light)
                self._device = device_cls(serial=serial, ip=ip)
                self._lifx_type = lifx_type
                _LOGGER.info(
                    "LIFX %s: Direct connect as %s (%s)",
                    self._config["name"],
                    lifx_class,
                    lifx_type,
                )
            else:
                # Fallback to discovery (slower, 2+ round trips)
                self._device = await find_by_ip(ip=ip)
                if self._device is None:
                    _LOGGER.warning(
                        "LIFX %s: No device found at %s",
                        self._config["name"],
                        ip,
                    )
                    self._connected = False
                    self._online = False
                    return
                lifx_class = type(self._device).__name__
                self._lifx_type = LIFX_TYPE_MAP.get(lifx_class, "light")
                _LOGGER.info(
                    "LIFX %s: Discovery connect as %s (%s)",
                    self._config["name"],
                    lifx_class,
                    self._lifx_type,
                )

            # Ensure capabilities are populated (needed for Ceiling uplight_zone etc.)
            await self._device._ensure_capabilities()

            # Configure based on type
            if self._lifx_type == "matrix":
                await self._setup_matrix()
            elif self._lifx_type == "strip":
                await self._setup_strip()
            else:
                await self._setup_light()

            # Turn on device
            await self._device.set_power(True)
            self._connected = True
            self._online = True

            # Update virtual rows for matrix devices
            if self._lifx_type == "matrix":
                self._update_virtual_rows()

        except (LifxError, OSError) as e:
            _LOGGER.warning(
                "LIFX %s: Connection failed: %s",
                self._config["name"],
                e,
            )
            self._connected = False
            self._online = False

    async def _setup_light(self):
        """Configure for single bulb device."""
        self._device_type = "LIFX Light"
        _LOGGER.info(
            "LIFX %s: Configured as single bulb",
            self._config["name"],
        )

    async def _setup_strip(self):
        """Configure for multizone strip device."""
        if not isinstance(self._device, MultiZoneLight):
            return

        self._device_type = "LIFX Strip"
        self._zone_count = await self._device.get_zone_count()

        # Check for extended multizone capability
        if not self._device.capabilities:
            await self._device._ensure_capabilities()

        if (
            self._device.capabilities
            and self._device.capabilities.has_extended_multizone
        ):
            self._has_extended = True

        _LOGGER.info(
            "LIFX %s: Configured as strip with %d zones (extended=%s)",
            self._config["name"],
            self._zone_count,
            self._has_extended,
        )

    async def _setup_matrix(self):
        """Configure for matrix device (Tile, Ceiling, etc.)."""
        if isinstance(self._device, (MatrixLight, CeilingLight)):
            self._device_type = "LIFX Matrix"

            # Use saved config if available (from async_initialize)
            if self._tiles and self._perm is not None:
                self._matrix_width = self._config.get("matrix_width", 0)
                self._matrix_height = self._config.get("matrix_height", 0)
                _LOGGER.info(
                    "LIFX %s: Using saved matrix config %dx%d (%d pixels)",
                    self._config["name"],
                    self._matrix_width,
                    self._matrix_height,
                    self._total_pixels,
                )
                return

            # Otherwise query the device
            tiles = await self._device.get_device_chain()
            self._tiles, self._total_pixels = self._collect_tile_info(tiles)

            if self._tiles:
                self._perm = self._build_permutation(tiles)
                tile_info = ", ".join(
                    f"Tile {t['index']}: {t['width']}x{t['height']} "
                    f"@({t['user_x']},{t['user_y']})"
                    for t in self._tiles
                )
                _LOGGER.info(
                    "LIFX %s: Matrix %dx%d (%d pixels) [%s]",
                    self._config["name"],
                    self._matrix_width,
                    self._matrix_height,
                    self._total_pixels,
                    tile_info,
                )
            else:
                _LOGGER.warning(
                    "LIFX %s: Matrix device returned no tiles",
                    self._config["name"],
                )

    def _update_virtual_rows(self):
        """Update associated virtual's rows to match matrix height."""
        for virtual in self._ledfx.virtuals.values():
            if virtual.is_device == self.id:
                if virtual.config.get("rows", 1) != self._matrix_height:
                    _LOGGER.info(
                        "Updating virtual %s rows %d -> %d",
                        virtual.id,
                        virtual.config.get("rows", 1),
                        self._matrix_height,
                    )
                    virtual.config = {"rows": self._matrix_height}
                    virtual.virtual_cfg["config"]["rows"] = self._matrix_height
                break

    async def _async_disconnect(self):
        """Disconnect from device."""
        if self._device:
            try:
                await self._device.set_power(False)
            except asyncio.TimeoutError:
                _LOGGER.warning("LIFX %s: Power off timed out", self.name)
            except (LifxError, OSError) as e:
                _LOGGER.warning("LIFX %s: Power off error: %s", self.name, e)
            try:
                await self._device.close()
            except (LifxError, OSError) as e:
                _LOGGER.warning("LIFX %s: Close error: %s", self.name, e)
            self._device = None
            self._connected = False

    def activate(self):
        if self._destination is None:
            super().activate()
            return

        super().activate()
        _LOGGER.debug(
            "LIFX %s: Activating with config refresh_rate=%s, max_refresh_rate=%s",
            self.name,
            self._config.get("refresh_rate"),
            self.max_refresh_rate,
        )

        # Use Animator for matrix/strip (high performance)
        # Keep connection-based for single bulbs
        if self._lifx_type in ("matrix", "strip"):
            async_fire_and_forget(
                self._create_animator(),
                loop=self._ledfx.loop,
            )
        else:
            async_fire_and_forget(
                self._async_connect(),
                loop=self._ledfx.loop,
            )

    def deactivate(self):
        if self._animator:
            self._animator.close()
            self._animator = None
        if self._device:
            async_fire_and_forget(
                self._async_disconnect(),
                loop=self._ledfx.loop,
            )
        super().deactivate()

    async def _async_flush(self, data):
        """Send pixel data to single bulb device."""
        if not self._device or not self._connected:
            return
        await self._flush_light(data)

    @property
    def effective_refresh_rate(self):
        """Get refresh rate capped by device type."""
        # Use virtual's rate if available, otherwise device's configured rate
        if self.priority_virtual:
            rate = self.priority_virtual.refresh_rate
        else:
            rate = self.max_refresh_rate

        # Only cap single bulbs to prevent strobing
        if self._lifx_type == "light":
            return min(rate, MAX_FPS_LIGHT)
        return rate

    @property
    def frame_duration_ms(self):
        """Frame duration in milliseconds for hardware interpolation.

        Subtract 2ms buffer so interpolation completes before next frame arrives.
        """
        return max(1, int(1000 / self.effective_refresh_rate) - 2)

    async def _flush_light(self, data):
        """Send color to single bulb - fire and forget, no ack."""
        if not isinstance(self._device, Light):
            return

        try:
            pixels = data.astype(np.dtype("B")).reshape(-1, 3)
            if len(pixels) > 0:
                r, g, b = pixels[0]
                color = HSBK.from_rgb(int(r), int(g), int(b)).to_protocol()
                packet = packets.Light.SetColor(
                    color=color, duration=self.frame_duration_ms
                )
                await self._device.connection.send_packet(packet)
        except (LifxError, OSError) as e:
            _LOGGER.warning(
                "LIFX %s: Light flush error: %s", self._config["name"], e
            )

    def flush(self, data):
        if self._animator:
            # Animation module (synchronous, high performance)
            try:
                pixels = data.astype(np.dtype("B")).reshape(-1, 3)
                pixel_count = min(len(pixels), self._animator.pixel_count)
                hsbk_data = numpy_rgb_to_hsbk(pixels[:pixel_count])

                # Pad if needed
                while len(hsbk_data) < self._animator.pixel_count:
                    hsbk_data.append((0, 0, 0, 3500))

                self._animator.send_frame(hsbk_data)
            except (LifxError, LifxTimeoutError, OSError, ValueError) as e:
                _LOGGER.warning(
                    "LIFX %s: Frame send error: %s",
                    self.name,
                    e,
                    exc_info=True,
                )

        elif self._device and self._connected:
            # Fallback for single bulbs or Animator failure
            async_fire_and_forget(
                self._async_flush(data),
                loop=self._ledfx.loop,
            )
