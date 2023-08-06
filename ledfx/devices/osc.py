import logging
import time

import numpy as np
import voluptuous as vol
from pythonosc.udp_client import SimpleUDPClient
from pythonosc.osc_message_builder import OscMessageBuilder

from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class OSCRealtimeDevice(NetworkedDevice):
    """Generic UDP Realtime device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "port",
                description="Port of the OSC server",
                default=9000,
            ): vol.All(int, vol.Range(min=1, max=65535)),
            vol.Required(
                "universe",
                description="Universe of the DMX device",
                default=0,
            ): vol.All(int, vol.Range(min=0)),
            vol.Required(
                "starting_addr",
                description="Starting address of the DMX device",
                default=0,
            ): vol.All(int, vol.Range(min=0)),
            vol.Required(
                "pixel_count",
                description="Amount of channels where every pixel consists of 3 channels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "OSC"
        self.last_frame = np.full((config['pixel_count'], 3), -1)
        self.last_frame_sent_time = 0

    def activate(self):
        self._device = SimpleUDPClient(self.destination, self._config["port"])
        _LOGGER.debug(
            f"{self._device_type} sender for {self._config['name']} started."
        )
        super().activate()

    def deactivate(self):
        super().deactivate()
        _LOGGER.debug(
            f"{self._device_type} sender for {self._config['name']} stopped."
        )
        self._device = None

    def flush(self, data):
        if np.array_equal(data, self.last_frame): return
        colors = [[int(r), int(g), int(b)] for r, g, b in data]
        for i in range(self._config['pixel_count']):
          r, g, b = colors[i % len(colors)]
          send_data_r = OscMessageBuilder('/{u}/dmx/{a}'.format(u=self._config['universe'], a=self._config['starting_addr']+(i*3)+0))
          send_data_r.add_arg(r/255)
          send_data_g = OscMessageBuilder('/{u}/dmx/{a}'.format(u=self._config['universe'], a=self._config['starting_addr']+(i*3)+1))
          send_data_g.add_arg(g/255)
          send_data_b = OscMessageBuilder('/{u}/dmx/{a}'.format(u=self._config['universe'], a=self._config['starting_addr']+(i*3)+2))
          send_data_b.add_arg(b/255)
          try:
              self._device.send(send_data_r.build())
              self._device.send(send_data_g.build())
              self._device.send(send_data_b.build())
          except AttributeError:
              self.activate()
        self.last_frame = np.copy(data)

