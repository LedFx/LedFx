import logging

import numpy as np
import voluptuous as vol
from lifx import (
    HSBK,
    CeilingLight,
    HevLight,
    InfraredLight,
    LifxError,
    Light,
    MatrixLight,
    MultiZoneLight,
    find_by_ip,
)
from lifx.protocol.protocol_types import MultiZoneApplicationRequest

from ledfx.devices import NetworkedDevice
from ledfx.utils import async_fire_and_forget

_LOGGER = logging.getLogger(__name__)

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

    async def async_initialize(self):
        """Initialize device and auto-detect type during creation."""
        await super().async_initialize()
        await self._detect_device_type()

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
                if isinstance(device, MatrixLight) or isinstance(
                    device, CeilingLight
                ):
                    self._lifx_type = "matrix"
                    self._device_type = "LIFX Matrix"
                    tiles = await device.get_device_chain()

                    if self._process_tile_chain(tiles):
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
                        # Use private _ensure_capabilities() to avoid 3-5 network round-trips
                        # that the async context manager performs. We only need capabilities
                        # to determine whether this multizone supports extended messages,
                        # not full device state.
                        await device._ensure_capabilities()
                    if (
                        device.capabilities
                        and device.capabilities.has_extended_multizone
                    ):
                        self._has_extended = True

                    _LOGGER.info(
                        "LIFX %s: Strip with %d zones",
                        self._config["name"],
                        self._zone_count,
                    )

                elif (
                    isinstance(device, Light)
                    or isinstance(device, HevLight)
                    or isinstance(device, InfraredLight)
                ):
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
        """Return total pixel count based on device type."""
        if self._lifx_type == "matrix":
            return self._total_pixels
        elif self._lifx_type == "strip":
            return self._zone_count
        return self._config.get("pixel_count", 1)

    @property
    def is_matrix(self):
        """Return True if device is a matrix type."""
        return self._lifx_type == "matrix"

    @property
    def matrix_width(self):
        """Return matrix width in pixels, or 0 if not a matrix."""
        return self._matrix_width if self._lifx_type == "matrix" else 0

    @property
    def matrix_height(self):
        """Return matrix height in pixels, or 0 if not a matrix."""
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

    def _process_tile_chain(self, tiles):
        """Process tile chain data and build permutation mapping.

        Extracts tile metadata, calculates total pixels, and builds the
        permutation array for pixel reordering.

        Args:
            tiles: List of tile objects from device.get_device_chain()

        Returns:
            True if tiles were processed successfully, False if no tiles
        """
        self._tiles = []
        self._total_pixels = 0

        for i, tile in enumerate(tiles):
            tile_pixels = tile.width * tile.height
            self._tiles.append(
                {
                    "index": i,
                    "width": tile.width,
                    "height": tile.height,
                    "pixels": tile_pixels,
                    "offset": self._total_pixels,
                    "user_x": tile.user_x,
                    "user_y": tile.user_y,
                }
            )
            self._total_pixels += tile_pixels

        if self._tiles:
            self._perm = self._build_permutation(tiles)
            return True
        return False

    async def _async_connect(self):
        """Connect to device using saved serial/type for speed."""
        try:
            ip = self._config["ip_address"]
            serial = self._config.get("serial")
            lifx_type = self._config.get("lifx_type")

            # Use saved info for direct instantiation (faster)
            lifx_class = self._config.get("lifx_class")
            if serial and lifx_type and lifx_class:
                # Map class name to class
                class_map = {
                    "MatrixLight": MatrixLight,
                    "CeilingLight": CeilingLight,
                    "MultiZoneLight": MultiZoneLight,
                    "Light": Light,
                    "HevLight": HevLight,
                    "InfraredLight": InfraredLight,
                }
                device_cls = class_map.get(lifx_class, Light)
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
        if isinstance(self._device, MatrixLight) or isinstance(
            self._device, CeilingLight
        ):
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

            if self._process_tile_chain(tiles):
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
            except (LifxError, OSError) as e:
                _LOGGER.warning("LIFX %s: Disconnect error: %s", self.name, e)
            self._device = None
            self._connected = False

    def activate(self):
        """Activate device and initiate async connection."""
        if self._destination is None:
            super().activate()
            return

        super().activate()
        async_fire_and_forget(
            self._async_connect(),
            loop=self._ledfx.loop,
        )

    def deactivate(self):
        """Deactivate device and close connection."""
        if self._device:
            async_fire_and_forget(
                self._async_disconnect(),
                loop=self._ledfx.loop,
            )
        super().deactivate()

    async def _async_flush(self, data):
        """Send pixel data to device based on detected type."""
        if not self._device or not self._connected:
            return

        if self._lifx_type == "matrix":
            await self._flush_matrix(data)
        elif self._lifx_type == "strip":
            await self._flush_strip(data)
        else:
            await self._flush_light(data)

    async def _flush_light(self, data):
        """Send color to single bulb."""
        if not isinstance(self._device, Light):
            return

        try:
            pixels = data.astype(np.dtype("B")).reshape(-1, 3)
            if len(pixels) > 0:
                r, g, b = pixels[0]
                color = HSBK.from_rgb(int(r), int(g), int(b))
                await self._device.set_color(color)
        except (LifxError, OSError) as e:
            _LOGGER.warning(
                "LIFX %s: Light flush error: %s", self._config["name"], e
            )

    async def _flush_strip(self, data):
        """Send zone colors to multizone strip."""
        if (
            not isinstance(self._device, MultiZoneLight)
            or self._device.zone_count is None
        ):
            return

        try:
            pixels = data.astype(np.dtype("B")).reshape(-1, 3)
            colors = []

            for r, g, b in pixels[: self._zone_count]:
                colors.append(HSBK.from_rgb(int(r), int(g), int(b)))

            # Pad if needed
            while len(colors) < self._zone_count:
                colors.append(
                    HSBK(hue=0, saturation=0, brightness=0, kelvin=3500)
                )

            # Use duration=0 for instant updates (real-time LED sync)
            if self._has_extended:
                await self._device.set_extended_color_zones(
                    zone_index=0,
                    colors=colors,
                    duration=0.0,
                    apply=MultiZoneApplicationRequest.APPLY,
                    fast=True,
                )
            else:
                for i, color in enumerate(colors):
                    is_last = i == len(colors) - 1
                    apply = (
                        MultiZoneApplicationRequest.APPLY
                        if is_last
                        else MultiZoneApplicationRequest.NO_APPLY
                    )
                    await self._device.set_color_zones(
                        start=i,
                        end=i,
                        color=color,
                        duration=0.0,
                        apply=apply,
                    )
        except (LifxError, OSError) as e:
            _LOGGER.warning(
                "LIFX %s: Strip flush error: %s", self._config["name"], e
            )

    async def _flush_matrix(self, data):
        """Send pixel data to matrix device using frame buffer."""
        if self._device and (
            isinstance(self._device, MatrixLight)
            or isinstance(self._device, CeilingLight)
        ):
            if not self._tiles or self._perm is None:
                return

            try:
                pixels = data.astype(np.dtype("B")).reshape(-1, 3)

                # Validate pixel count matches permutation expectations
                expected_pixels = len(self._perm)
                if pixels.shape[0] < expected_pixels:
                    _LOGGER.warning(
                        "LIFX %s: Pixel count mismatch: got %d, expected %d",
                        self.name,
                        pixels.shape[0],
                        expected_pixels,
                    )
                    return

                reordered = pixels[self._perm]

                for tile in self._tiles:
                    start = tile["offset"]
                    end = start + tile["pixels"]
                    tile_pixels = reordered[start:end]

                    tile_colors = [
                        HSBK.from_rgb(int(r), int(g), int(b))
                        for r, g, b in tile_pixels
                    ]

                    await self._device.set64(
                        tile_index=tile["index"],
                        length=1,
                        x=0,
                        y=0,
                        width=tile["width"],
                        duration=0,
                        colors=tile_colors,
                    )

            except (LifxError, OSError) as e:
                _LOGGER.warning(
                    "LIFX %s: Matrix flush error: %s", self.name, e
                )

    def flush(self, data):
        """Queue pixel data to be sent to device asynchronously."""
        if self._device and self._connected:
            async_fire_and_forget(
                self._async_flush(data),
                loop=self._ledfx.loop,
            )
