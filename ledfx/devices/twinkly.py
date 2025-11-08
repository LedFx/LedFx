import io
import logging

import numpy as np
import voluptuous as vol
import xled
from xled.control import REALTIME_UDP_PORT_NUMBER
from xled.udp_client import UDPClient

from ledfx.config import save_config
from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)

# TODO: can we identify the virtual for this device at activate and correct its rows configuration if wrong.


class TwinklyDevice(NetworkedDevice):
    """Generic twinkly device support, not specialised"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "Twinkly"
        self.ctrl = None
        self.udp_client = None

    def flush(self, data):
        # data is a numpy array of shape (pixel_count, 3) with RGB values as floats in 0-255 range
        # Twinkly expects RGB bytes in sequence: R1 G1 B1 R2 G2 B2 ...

        pixel_data = data.astype(np.uint8)
        reodered = pixel_data[self.perm]
        frame = reodered.tobytes()
        self.ctrl.set_rt_frame_socket(io.BytesIO(frame), version=3)

    def activate(self):
        self.ctrl = xled.HighControlInterface(self._config["ip_address"])
        self.ctrl.turn_on()
        self.ctrl.set_brightness(100)
        self.ctrl.set_mode("rt")
        self.udp_client = UDPClient(
            port=REALTIME_UDP_PORT_NUMBER,
            destination_host=self.config["ip_address"],
        )
        info = self.ctrl.get_device_info()
        _LOGGER.debug(f"Twinkly device {self.name} info: %s", info.data)
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

        self.perm = self.build_twinkly_perm(
            coords_xy, actual_width, actual_height, flip_y=True
        )

        if self._config["pixel_count"] != self.leds:
            self._config["pixel_count"] = self.leds
            # force a config save
            save_config(
                config=self._ledfx.config,
                config_dir=self._ledfx.config_dir,
            )

        super().activate()

    def deactivate(self):
        if self.udp_client:
            self.udp_client.close()
        if self.ctrl:
            self.ctrl.set_mode("movie")
        self.ctrl = None
        self.udp_client = None
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
