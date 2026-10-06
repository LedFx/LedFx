import io
import logging

import numpy as np
import xled
from ledfx_senders.encoders import RGBGather
from pydantic import Field

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class TwinklySquaresDevice(NetworkedDevice):
    """Twinkly Squares device support"""

    class Config(NetworkedDevice.Config):
        panel_count: int = Field(
            1,
            description="Number of 8x8 Twinkly Squares panels",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "TwinklySquares"
        self.ctrl = None
        self._gather: RGBGather | None = None
        self._set_config_values(pixel_count=64 * self.config.panel_count)

    def config_updated(self, config):
        self._set_config_values(pixel_count=64 * self.config.panel_count)
        return super().config_updated(config)

    def flush(self, data):
        gather = self._gather
        if gather is None:
            raise RuntimeError("Twinkly layout is not active")
        frame = gather.encode(data)
        # the xled lib supports large packets with version 3, but not persistent sockets
        self.ctrl.set_rt_frame_socket(io.BytesIO(frame), version=3)

    def activate(self):
        with self._output_lock:
            self.ctrl = xled.HighControlInterface(self.config.ip_address)
            try:
                self.ctrl.turn_on()
                self.ctrl.set_brightness(100)
                self.ctrl.set_mode("rt")
                info = self.ctrl.get_device_info()
                _LOGGER.debug(
                    "Twinkly Squares device %s info: %s", self.name, info.data
                )
            except Exception as e:  # noqa: BLE001
                _LOGGER.warning(
                    "Failed to activate Twinkly Squares device %s: %s",
                    self.name,
                    e,
                )
                self.ctrl = None
                self._gather = None
                self.set_offline()
                return
            self.leds = info["number_of_led"]
            layout = self.ctrl.get_led_layout()
            cords = layout["coordinates"]
            coords_xy = np.array([[c["x"], c["y"]] for c in cords], dtype=np.float32)

            # Calculate actual grid dimensions from coordinate distribution
            x01_temp = (coords_xy[:, 0] + 1.0) * 0.5
            y01_temp = (coords_xy[:, 1] + 1.0) * 0.5
            actual_width = len(np.unique(np.round(x01_temp * 1000)))
            actual_height = len(np.unique(np.round(y01_temp * 1000)))
            _LOGGER.info(
                "Twinkly grid: %sx%s = %s LEDs",
                actual_width,
                actual_height,
                actual_width * actual_height,
            )

            # Cache the matrix dimensions for virtual configuration
            self.matrix_width = actual_width
            self.matrix_height = actual_height

            self.perm = self.build_twinkly_perm(
                coords_xy, actual_width, actual_height, flip_y=True
            )

            self._gather = RGBGather(tuple(int(index) for index in self.perm))

            config_changed = False

            # Update pixel count if different
            if getattr(self.config, "pixel_count") != self.leds:  # noqa: B009 - stored extra, not a declared field
                self._set_config_values(pixel_count=self.leds)
                config_changed = True

            # Update associated virtuals with the detected matrix height
            for virtual in self._ledfx.virtuals.values():
                if virtual.is_device == self.id:
                    if virtual.config.rows != self.matrix_height:
                        _LOGGER.info(
                            "Updating virtual %s rows from %s to %s",
                            virtual.id,
                            virtual.config.rows,
                            self.matrix_height,
                        )
                        virtual.update_config({"rows": self.matrix_height})
                        config_changed = True
                    break  # Only one virtual can be is_device for this device

            # Save config only once if anything changed
            if config_changed:
                self._ledfx.config_store.request_save()

            super().activate()

    def deactivate(self):
        with self._output_lock:
            if self.ctrl:
                self.ctrl.set_mode("movie")
            self.ctrl = None
            self._gather = None
            return super().deactivate()

    def build_twinkly_perm(self, coords_xy, width, height, flip_y=True):
        N = coords_xy.shape[0]

        # Find actual min/max of coordinates (don't assume -1 to 1)
        x_min, x_max = coords_xy[:, 0].min(), coords_xy[:, 0].max()
        y_min, y_max = coords_xy[:, 1].min(), coords_xy[:, 1].max()

        # Normalize to [0,1] based on actual range
        x01 = (coords_xy[:, 0] - x_min) / (x_max - x_min)
        y01 = (coords_xy[:, 1] - y_min) / (y_max - y_min)

        if flip_y:
            y01 = 1.0 - y01

        # Determine row,column integer positions
        cols = np.clip(np.rint(x01 * (width - 1)).astype(np.int32), 0, width - 1)
        rows = np.clip(np.rint(y01 * (height - 1)).astype(np.int32), 0, height - 1)

        # Row-major linear index (matching your incoming frame order)
        raster_idx = rows * width + cols

        # Sanity check: unique mapping
        unique_indices = np.unique(raster_idx)
        if unique_indices.size != N:
            from collections import Counter

            counts = Counter(raster_idx)
            collisions = {idx: count for idx, count in counts.items() if count > 1}
            _LOGGER.warning(
                "LED layout collision: %s duplicates found", len(collisions)
            )
            raise ValueError("LED layout collision – need resolution adjustment")

        return raster_idx.astype(np.int64)
