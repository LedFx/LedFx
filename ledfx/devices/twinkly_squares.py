import io
import logging

import numpy as np
import voluptuous as vol
import xled

from ledfx.config import save_config
from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class TwinklySquaresDevice(NetworkedDevice):
    """Twinkly Squares device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "panel_count",
                description="Number of 8x8 Twinkly Squares panels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "TwinklySquares"
        self.ctrl = None
        self.config["pixel_count"] = 64 * self._config["panel_count"]

    def config_updated(self, config):
        self.config["pixel_count"] = 64 * self._config["panel_count"]
        return super().config_updated(config)

    def flush(self, data):
        pixel_data = data.astype(np.uint8)
        # do the magic or reordering the whole frame according to the precalculated perm mapping
        reodered = pixel_data[self.perm]
        frame = reodered.tobytes()
        # the xled lib supports large packets with version 3, but not persistent sockets
        self.ctrl.set_rt_frame_socket(io.BytesIO(frame), version=3)

    def activate(self):
        self.ctrl = xled.HighControlInterface(self._config["ip_address"])
        try:
            self.ctrl.turn_on()
            self.ctrl.set_brightness(100)
            self.ctrl.set_mode("rt")
            info = self.ctrl.get_device_info()
            _LOGGER.debug(
                f"Twinkly Squares device {self.name} info: %s", info.data
            )
        except Exception as e:
            _LOGGER.error(
                f"Failed to activate Twinkly Squares device {self.name}: {e}"
            )
            self.ctrl = None
            self.set_offline()
            return
        self.leds = info["number_of_led"]
        layout = self.ctrl.get_led_layout()
        cords = layout["coordinates"]
        coords_xy = np.array(
            [[c["x"], c["y"]] for c in cords], dtype=np.float32
        )
        N = coords_xy.shape[0]

        # Calculate actual grid dimensions from coordinate distribution
        x01_temp = (coords_xy[:, 0] + 1.0) * 0.5
        y01_temp = (coords_xy[:, 1] + 1.0) * 0.5
        actual_width = len(np.unique(np.round(x01_temp * 1000)))
        actual_height = len(np.unique(np.round(y01_temp * 1000)))
        _LOGGER.info(
            f"Twinkly grid: {actual_width}×{actual_height} = {actual_width * actual_height} LEDs"
        )

        # Cache the matrix dimensions for virtual configuration
        self.matrix_width = actual_width
        self.matrix_height = actual_height

        self.perm = self.build_twinkly_perm(
            coords_xy, actual_width, actual_height, flip_y=True
        )

        config_changed = False

        # Update pixel count if different
        if self._config["pixel_count"] != self.leds:
            self._config["pixel_count"] = self.leds
            config_changed = True

        # Update associated virtuals with the detected matrix height
        for virtual in self._ledfx.virtuals.values():
            if virtual.is_device == self.id:
                if virtual.config.get("rows", 1) != self.matrix_height:
                    _LOGGER.info(
                        f"Updating virtual {virtual.id} rows from {virtual.config.get('rows', 1)} to {self.matrix_height}"
                    )
                    virtual.config = {"rows": self.matrix_height}
                    virtual.virtual_cfg["config"]["rows"] = self.matrix_height
                    config_changed = True
                break  # Only one virtual can be is_device for this device

        # Save config only once if anything changed
        if config_changed:
            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )

        super().activate()

    def deactivate(self):
        if self.ctrl:
            self.ctrl.set_mode("movie")
        self.ctrl = None
        return super().deactivate()

    def build_twinkly_perm(self, coords_xy, width, height, flip_y=True):
        N = coords_xy.shape[0]
        assert width * height == N

        # Find actual min/max of coordinates (don't assume -1 to 1)
        x_min, x_max = coords_xy[:, 0].min(), coords_xy[:, 0].max()
        y_min, y_max = coords_xy[:, 1].min(), coords_xy[:, 1].max()

        # Normalize to [0,1] based on actual range
        x01 = (coords_xy[:, 0] - x_min) / (x_max - x_min)
        y01 = (coords_xy[:, 1] - y_min) / (y_max - y_min)

        if flip_y:
            y01 = 1.0 - y01

        # Determine row,column integer positions
        cols = np.clip(
            np.rint(x01 * (width - 1)).astype(np.int32), 0, width - 1
        )
        rows = np.clip(
            np.rint(y01 * (height - 1)).astype(np.int32), 0, height - 1
        )

        # Row-major linear index (matching your incoming frame order)
        raster_idx = rows * width + cols

        # Sanity check: unique mapping
        unique_indices = np.unique(raster_idx)
        if unique_indices.size != N:
            from collections import Counter

            counts = Counter(raster_idx)
            collisions = {
                idx: count for idx, count in counts.items() if count > 1
            }
            _LOGGER.error(
                f"LED layout collision: {len(collisions)} duplicates found"
            )
            raise ValueError(
                "LED layout collision – need resolution adjustment"
            )

        return raster_idx.astype(np.int64)
