import logging
import socket
import struct

import numpy as np
from pydantic import Field

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class OpenPixelControl(NetworkedDevice):
    """OpenPixelControl device support"""

    class Config(NetworkedDevice.Config):
        pixel_count: int = Field(
            1,
            description="Number of individual pixels",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        channel: int = Field(
            0,
            description="Channel to send pixel data",
            ge=0,
            le=255,
            json_schema_extra={X_REQUIRED: True},
        )

    config = TypedConfig(Config)

    def activate(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _LOGGER.info("Open Pixel Control sender for %s started.", self.config.name)
        super().activate()

    def deactivate(self):
        super().deactivate()
        _LOGGER.info("Open Pixel Control sender for %s stopped.", self.config.name)
        self._sock = None

    def flush(self, data):
        try:
            OpenPixelControl.send_out(
                self,
                self._sock,
                self.destination,
                7890,
                data,
            )
        except AttributeError:
            self.activate()

    @staticmethod
    def send_out(
        self,  # noqa: PLW0211
        sock,
        dest,
        port,
        data,
    ):
        header = struct.pack(
            ">BBH", self.config.channel, 0, self.config.pixel_count * 3
        )
        pixels = np.asarray(data)
        if pixels.shape != (self.config.pixel_count, 3):
            raise ValueError(
                "OPC data must contain the configured number of RGB pixels"
            )
        finite = np.isfinite(pixels)
        if not finite.all():
            # Preserve int()'s rejection of NaN/inf instead of silently casting
            # them to zero. This exceptional path is outside normal rendering.
            int(pixels.ravel()[np.flatnonzero(~finite)[0]])
        # Clamp before casting, matching min/max/int for finite RGB values.
        message = header + np.clip(pixels, 0, 255).astype(np.uint8).tobytes()
        sock.sendto(
            bytes(message),
            (dest, port),
        )
