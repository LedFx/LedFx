import logging

import numpy as np
import voluptuous as vol
from stupidArtnet import StupidArtnet
from ledfx.utils import (
    clip_at_limit,
    extract_uint8_seq,
)

from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class ArtNetDevice(NetworkedDevice):
    """Art-Net device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
            vol.Optional(
                "universe",
                description="DMX universe for the device",
                default=0,
            ): vol.All(int, vol.Range(min=0)),
            vol.Optional(
                "packet_size",
                description="Size of each DMX universe",
                default=510,
            ): vol.All(int, vol.Range(min=1, max=512)),
            vol.Optional(
                "pre_amble",
                description="Channel bytes to insert before the RGB data",
                default="",
            ): str,
            vol.Optional(
                "post_amble",
                description="Channel bytes to insert after the RGB bata",
                default="",
            ): str,
            vol.Optional(
                "even_packet_size",
                description="Whether to use even packet size",
                default=True,
            ): bool,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._artnet = None
        self.config_use(config)

    def config_updated(self, config):
        self.config_use(config)
        self.deactivate()
        self.activate()

    def config_use(self, config):
        # get the preamble string, stip it and convert to np.arry of unint8
        self.pre_amble = np.array(extract_uint8_seq(config.get("pre_amble", "")), dtype=np.uint8)
        self.post_amble = np.array(extract_uint8_seq(config.get("post_amble", "")), dtype=np.uint8)
        # This assumes RGB - for RGBW devices this isn't gonna work.
        # TODO: Fix this when/if we ever want to move to RGBW outputs for devices
        # warning magic number 3 for RGB
        self.channel_count = self.pre_amble.size + (
            self._config["pixel_count"] * 3 ) + self.post_amble.size
        self.packet_size = self._config["packet_size"]
        self.universe_count = (
            self.channel_count + self.packet_size - 1
        ) // self.packet_size

    def activate(self):
        if self._artnet:
            _LOGGER.warning(
                f"Art-Net sender already started for device {self.config['name']}"
            )
        self._artnet = StupidArtnet(
            target_ip=self._config["ip_address"],
            universe=self._config["universe"],
            packet_size=self.packet_size,
            fps=self._config["refresh_rate"],
            even_packet_size=self._config["even_packet_size"],
            broadcast=False,
        )
        # Don't use start for stupidArtnet - we handle fps locally, and it spawns hundreds of threads

        _LOGGER.info(f"Art-Net sender for {self.config['name']} started.")
        super().activate()

    def deactivate(self):
        super().deactivate()
        if not self._artnet:
            return

        self._artnet.blackout()
        self._artnet.close()
        self._artnet = None
        _LOGGER.info(f"Art-Net sender for {self.config['name']} stopped.")

    def flush(self, data):
        with self.lock:
            """Flush the data to all the Art-Net channels"""
            if not self._artnet:
                self.activate()

            data = data.flatten()
            data = np.concatenate((self.pre_amble, data, self.post_amble))
            # TODO: Handle the data transformation outside of the loop and just use loop to set universe and send packets
            for i in range(self.universe_count):
                start = i * self.packet_size
                end = start + self.packet_size
                packet = np.zeros(self.packet_size, dtype=np.uint8)
                packet[: min(self.packet_size, self.channel_count - start)] = (
                    data[start:end]
                )
                self._artnet.set_universe(i + self._config["universe"])
                self._artnet.set(packet)
                self._artnet.show()
