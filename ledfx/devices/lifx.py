import logging

import numpy as np
import voluptuous as vol
from lifx import (
    HSBK,
    CeilingLight,
    Colors,
    HevLight,
    InfraredLight,
    LifxError,
    Light,
    MatrixLight,
    MultiZoneLight,
    find_by_ip,
)
from lifx.protocol import packets
from lifx.protocol.protocol_types import (
    MultiZoneApplicationRequest,
    TileBufferRect,
)

from ledfx.devices import NetworkedDevice, fps_validator
from ledfx.utils import async_fire_and_forget

_LOGGER = logging.getLogger(__name__)


# Black/off color for padding and clearing zones
BLACK = Colors.OFF.to_protocol()

# Max refresh rates by device type (prevents strobing on single bulbs)
MAX_FPS_LIGHT = 40  # Single bulbs strobe visibly at higher rates
MAX_FPS_MULTIZONE = 60  # Strips/matrices handle higher rates better

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


class LifxDevice(NetworkedDevice):
    """Unified LIFX device with auto-detection.

    Automatically detects device type (bulb, strip, or matrix) on connection
    and configures itself appropriately. Users only need to provide an IP.

    For Ceiling lights, creates sub-virtuals for downlight (matrix) and
    uplight (single light) zones, similar to WLED segments.
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
            vol.Optional(
                "create_segments",
                description="Auto-create virtuals for Ceiling uplight/downlight",
                default=True,
            ): bool,
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
        self._frame_buffers = 2  # Default, updated from device
        self._current_fb = (
            1  # Rotating framebuffer index (1 to _frame_buffers-1)
        )

        # Ceiling-specific
        self._is_ceiling = False

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
                # Check for CeilingLight first (it's a subclass of MatrixLight)
                if isinstance(device, CeilingLight):
                    self._is_ceiling = True
                    self._uplight_zone = device.uplight_zone
                    self._downlight_pixel_count = device.downlight_zone_count
                    self._lifx_type = "matrix"
                    self._device_type = "LIFX Ceiling"

                    tiles = await device.get_device_chain()
                    self._total_pixels = 0
                    self._tiles = []
                    min_frame_buffers = 50  # Start high, find minimum

                    for i, tile in enumerate(tiles):
                        tile_pixels = tile.width * tile.height
                        # Get framebuffer count from tile
                        fb_count = getattr(tile, "supported_frame_buffers", 2)
                        min_frame_buffers = min(min_frame_buffers, fb_count)
                        self._tiles.append(
                            {
                                "index": i,
                                "width": tile.width,
                                "height": tile.height,
                                "pixels": tile_pixels,
                                "offset": self._total_pixels,
                                "user_x": tile.user_x,
                                "user_y": tile.user_y,
                                "frame_buffers": fb_count,
                            }
                        )
                        self._total_pixels += tile_pixels

                    if self._tiles:
                        self._frame_buffers = min_frame_buffers
                        self._perm = self._build_permutation(tiles)
                        # Total pixels includes both downlight and uplight
                        self._config["pixel_count"] = self._total_pixels
                        self._config["matrix_width"] = self._matrix_width
                        self._config["matrix_height"] = self._matrix_height
                        _LOGGER.info(
                            "LIFX %s: Ceiling %dx%d (%d downlight + 1 uplight, %d frame buffers)",
                            self._config["name"],
                            self._matrix_width,
                            self._matrix_height,
                            self._downlight_pixel_count,
                            self._frame_buffers,
                        )

                elif isinstance(device, MatrixLight):
                    self._lifx_type = "matrix"
                    self._device_type = "LIFX Matrix"
                    tiles = await device.get_device_chain()
                    self._total_pixels = 0
                    self._tiles = []
                    min_frame_buffers = 50

                    for i, tile in enumerate(tiles):
                        tile_pixels = tile.width * tile.height
                        fb_count = getattr(tile, "supported_frame_buffers", 2)
                        min_frame_buffers = min(min_frame_buffers, fb_count)
                        self._tiles.append(
                            {
                                "index": i,
                                "width": tile.width,
                                "height": tile.height,
                                "pixels": tile_pixels,
                                "offset": self._total_pixels,
                                "user_x": tile.user_x,
                                "user_y": tile.user_y,
                                "frame_buffers": fb_count,
                            }
                        )
                        self._total_pixels += tile_pixels

                    if self._tiles:
                        self._frame_buffers = min_frame_buffers
                        self._perm = self._build_permutation(tiles)
                        self._config["pixel_count"] = self._total_pixels
                        self._config["matrix_width"] = self._matrix_width
                        self._config["matrix_height"] = self._matrix_height
                        _LOGGER.info(
                            "LIFX %s: Matrix %dx%d (%d pixels, %d frame buffers)",
                            self._config["name"],
                            self._matrix_width,
                            self._matrix_height,
                            self._total_pixels,
                            self._frame_buffers,
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

    async def add_postamble(self):
        """Create sub-virtuals for Ceiling lights (like WLED segments)."""
        if not self._is_ceiling:
            return

        if not (
            self._config.get("create_segments", True)
            or self._ledfx.config.get("create_segments", False)
        ):
            return

        _LOGGER.debug("Creating sub-virtuals for LIFX Ceiling %s", self.name)

        # Create downlight virtual (matrix)
        # Downlight uses pixels 0 to (uplight_zone - 1)
        downlight_rows = self._matrix_height
        self.sub_v(
            "Downlight",
            None,
            [[0, self._downlight_pixel_count - 1]],
            downlight_rows,
        )

        # Create uplight virtual (single light)
        # Uplight uses just the uplight zone
        self.sub_v(
            "Uplight",
            None,
            [[self._uplight_zone, self._uplight_zone]],
            1,
        )

        _LOGGER.info(
            "LIFX %s: Created Downlight (%d pixels) and Uplight (1 pixel) virtuals",
            self.name,
            self._downlight_pixel_count,
        )

    def _get_ceiling_zone_activity(self):
        """Check which Ceiling sub-virtuals have active effects.

        Returns tuple of (downlight_active, uplight_active).
        """
        if not self._is_ceiling:
            return (False, False)

        downlight_active = False
        uplight_active = False

        # Check sub-virtuals for active effects
        # Virtual IDs are generated from name, not id, and lowercased
        downlight_id = f"{self.id}-downlight"
        uplight_id = f"{self.id}-uplight"
        downlight_virtual = self._ledfx.virtuals.get(downlight_id)
        uplight_virtual = self._ledfx.virtuals.get(uplight_id)

        _LOGGER.debug(
            "LIFX %s: Zone check - downlight_id=%s (found=%s, effect=%s), "
            "uplight_id=%s (found=%s, effect=%s)",
            self.name,
            downlight_id,
            downlight_virtual is not None,
            downlight_virtual.active_effect if downlight_virtual else None,
            uplight_id,
            uplight_virtual is not None,
            uplight_virtual.active_effect if uplight_virtual else None,
        )

        if downlight_virtual and downlight_virtual.active_effect is not None:
            downlight_active = True
        if uplight_virtual and uplight_virtual.active_effect is not None:
            uplight_active = True

        return (downlight_active, uplight_active)

    async def _clear_ceiling_zone(self, zone: str):
        """Clear a specific Ceiling zone to black using Set64 packet(s).

        For larger Ceilings (128 zones), may require multiple packets.

        Args:
            zone: Either "downlight" or "uplight"
        """
        if not self._device or not self._is_ceiling:
            return

        if not isinstance(self._device, CeilingLight):
            return

        try:
            uplight_zone = self._device.uplight_zone
            # Determine tile dimensions from first tile
            if not self._tiles:
                return
            tile = self._tiles[0]
            tile_width = tile["width"]

            if zone == "downlight":
                # Clear zones 0 to uplight_zone-1
                num_zones = uplight_zone
                colors = [BLACK] * min(64, num_zones)

                # First packet (zones 0-63)
                rect = TileBufferRect(fb_index=0, x=0, y=0, width=tile_width)
                packet = packets.Tile.Set64(
                    tile_index=0,
                    length=1,
                    rect=rect,
                    duration=0,
                    colors=colors,
                )
                await self._device.connection.send_packet(packet)

                # Second packet if needed (zones 64-126 for 128-zone Ceiling)
                if num_zones > 64:
                    remaining = num_zones - 64
                    colors2 = [BLACK] * remaining
                    rows_offset = 64 // tile_width  # 4 rows for 16-wide tile
                    rect2 = TileBufferRect(
                        fb_index=0, x=0, y=rows_offset, width=tile_width
                    )
                    packet2 = packets.Tile.Set64(
                        tile_index=0,
                        length=1,
                        rect=rect2,
                        duration=0,
                        colors=colors2,
                    )
                    await self._device.connection.send_packet(packet2)

                _LOGGER.debug(
                    "LIFX %s: Cleared %d downlight zones to black",
                    self.name,
                    num_zones,
                )

            elif zone == "uplight":
                # Clear just the uplight zone (zone 63 or 127)
                # Calculate position in tile
                uplight_y = uplight_zone // tile_width
                uplight_x = uplight_zone % tile_width
                colors = [BLACK]
                rect = TileBufferRect(
                    fb_index=0, x=uplight_x, y=uplight_y, width=1
                )
                packet = packets.Tile.Set64(
                    tile_index=0,
                    length=1,
                    rect=rect,
                    duration=0,
                    colors=colors,
                )
                await self._device.connection.send_packet(packet)
                _LOGGER.debug("LIFX %s: Cleared uplight to black", self.name)

        except (LifxError, OSError) as e:
            _LOGGER.debug("LIFX %s: Clear zone error: %s", self.name, e)

    async def _clear_inactive_ceiling_zones(self):
        """Clear any Ceiling zones that don't have active effects."""
        if not self._is_ceiling:
            return

        downlight_active, uplight_active = self._get_ceiling_zone_activity()

        _LOGGER.debug(
            "LIFX %s: Clearing inactive zones - downlight_active=%s, uplight_active=%s",
            self.name,
            downlight_active,
            uplight_active,
        )

        if not downlight_active:
            await self._clear_ceiling_zone("downlight")
        if not uplight_active:
            await self._clear_ceiling_zone("uplight")

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

            # Clear inactive Ceiling zones to black
            if self._is_ceiling:
                await self._clear_inactive_ceiling_zones()

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

            # Check if this is a Ceiling
            if isinstance(self._device, CeilingLight):
                self._is_ceiling = True
                self._device_type = "LIFX Ceiling"

            # Use saved config if available (from async_initialize)
            if self._tiles and self._perm is not None:
                self._matrix_width = self._config.get("matrix_width", 0)
                self._matrix_height = self._config.get("matrix_height", 0)
                _LOGGER.info(
                    "LIFX %s: Using saved matrix config %dx%d (%d pixels, %d frame buffers)",
                    self._config["name"],
                    self._matrix_width,
                    self._matrix_height,
                    self._total_pixels,
                    self._frame_buffers,
                )
                return

            # Otherwise query the device
            tiles = await self._device.get_device_chain()
            self._tiles = []
            self._total_pixels = 0
            min_frame_buffers = 50

            for i, tile in enumerate(tiles):
                tile_pixels = tile.width * tile.height
                # Get framebuffer count from tile
                fb_count = getattr(tile, "supported_frame_buffers", 2)
                min_frame_buffers = min(min_frame_buffers, fb_count)
                self._tiles.append(
                    {
                        "index": i,
                        "width": tile.width,
                        "height": tile.height,
                        "pixels": tile_pixels,
                        "offset": self._total_pixels,
                        "user_x": tile.user_x,
                        "user_y": tile.user_y,
                        "frame_buffers": fb_count,
                    }
                )
                self._total_pixels += tile_pixels

            if self._tiles:
                self._frame_buffers = min_frame_buffers
                self._perm = self._build_permutation(tiles)
                tile_info = ", ".join(
                    f"Tile {t['index']}: {t['width']}x{t['height']} "
                    f"@({t['user_x']},{t['user_y']})"
                    for t in self._tiles
                )
                _LOGGER.info(
                    "LIFX %s: Matrix %dx%d (%d pixels, %d frame buffers) [%s]",
                    self._config["name"],
                    self._matrix_width,
                    self._matrix_height,
                    self._total_pixels,
                    self._frame_buffers,
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
            "LIFX %s: Activating with config refresh_rate=%s, "
            "max_refresh_rate=%s",
            self.name,
            self._config.get("refresh_rate"),
            self.max_refresh_rate,
        )
        async_fire_and_forget(
            self._async_connect(),
            loop=self._ledfx.loop,
        )

    def deactivate(self):
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

    @property
    def effective_refresh_rate(self):
        """Get refresh rate capped by device type."""
        max_fps = (
            MAX_FPS_LIGHT if self._lifx_type == "light" else MAX_FPS_MULTIZONE
        )

        # Use virtual's rate if available, otherwise device's configured rate
        if self.priority_virtual:
            rate = self.priority_virtual.refresh_rate
        else:
            rate = self.max_refresh_rate

        return min(rate, max_fps)

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

    async def _flush_strip(self, data):
        """Send zone colors to multizone strip - fire and forget, no ack."""
        if (
            not isinstance(self._device, MultiZoneLight)
            or self._device.zone_count is None
        ):
            return

        try:
            pixels = data.astype(np.dtype("B")).reshape(-1, 3)
            colors = []

            for r, g, b in pixels[: self._zone_count]:
                colors.append(
                    HSBK.from_rgb(int(r), int(g), int(b)).to_protocol()
                )

            # Pad if needed
            while len(colors) < self._zone_count:
                colors.append(BLACK)

            duration = self.frame_duration_ms
            if self._has_extended:
                packet = packets.MultiZone.SetExtendedColorZones(
                    duration=duration,
                    apply=MultiZoneApplicationRequest.APPLY,
                    index=0,
                    colors_count=len(colors),
                    colors=colors,
                )
                await self._device.connection.send_packet(packet)
            else:
                for i, color in enumerate(colors):
                    is_last = i == len(colors) - 1
                    apply = (
                        MultiZoneApplicationRequest.APPLY
                        if is_last
                        else MultiZoneApplicationRequest.NO_APPLY
                    )
                    packet = packets.MultiZone.SetColorZones(
                        start_index=i,
                        end_index=i,
                        color=color,
                        duration=duration,
                        apply=apply,
                    )
                    await self._device.connection.send_packet(packet)
        except (LifxError, OSError) as e:
            _LOGGER.warning(
                "LIFX %s: Strip flush error: %s", self._config["name"], e
            )

    async def _flush_matrix(self, data):
        """Send pixel data to matrix device using rotating framebuffers.

        For smooth animation without tearing or buffer conflicts:
        1. Write all Set64 packets to current off-screen buffer with duration=0
        2. Use CopyFrameBuffer to copy to visible buffer (fb_index=0) with duration
        3. Rotate to next off-screen buffer for next frame

        By rotating through available framebuffers (1 to N-1), we avoid
        overwriting a buffer that's still being copied from.
        """
        if not self._device or not (
            isinstance(self._device, MatrixLight)
            or isinstance(self._device, CeilingLight)
        ):
            return

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
            duration = self.frame_duration_ms

            # Use current rotating framebuffer (1 to _frame_buffers-1)
            fb_index = self._current_fb

            for tile in self._tiles:
                start = tile["offset"]
                end = start + tile["pixels"]
                tile_pixels = reordered[start:end]
                tile_width = tile["width"]
                tile_height = tile["height"]
                total_pixels = tile["pixels"]

                tile_colors = [
                    HSBK.from_rgb(int(r), int(g), int(b)).to_protocol()
                    for r, g, b in tile_pixels
                ]

                # Write all Set64 packets to off-screen buffer
                pixels_per_packet = 64
                colors_sent = 0
                y_offset = 0

                while colors_sent < total_pixels:
                    chunk_size = min(
                        pixels_per_packet, total_pixels - colors_sent
                    )
                    chunk_colors = tile_colors[
                        colors_sent : colors_sent + chunk_size
                    ]
                    rows_in_chunk = chunk_size // tile_width

                    rect = TileBufferRect(
                        fb_index=fb_index,
                        x=0,
                        y=y_offset,
                        width=tile_width,
                    )
                    packet = packets.Tile.Set64(
                        tile_index=tile["index"],
                        length=1,
                        rect=rect,
                        duration=0,  # Instant write to off-screen buffer
                        colors=chunk_colors,
                    )
                    await self._device.connection.send_packet(packet)

                    colors_sent += chunk_size
                    y_offset += rows_in_chunk

                # Copy from off-screen to visible (fb_index=0)
                copy_packet = packets.Tile.CopyFrameBuffer(
                    tile_index=tile["index"],
                    length=1,
                    src_fb_index=fb_index,
                    dst_fb_index=0,
                    src_x=0,
                    src_y=0,
                    dst_x=0,
                    dst_y=0,
                    width=tile_width,
                    height=tile_height,
                    duration=duration,
                )
                await self._device.connection.send_packet(copy_packet)

            # Rotate to next framebuffer (1 to _frame_buffers-1, avoiding 0)
            max_fb = self._frame_buffers - 1
            if max_fb > 0:
                self._current_fb = (self._current_fb % max_fb) + 1

        except (LifxError, OSError) as e:
            _LOGGER.warning("LIFX %s: Matrix flush error: %s", self.name, e)

    def flush(self, data):
        if self._device and self._connected:
            async_fire_and_forget(
                self._async_flush(data),
                loop=self._ledfx.loop,
            )
