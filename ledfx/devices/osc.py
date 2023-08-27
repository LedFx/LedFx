import logging

import numpy as np
import voluptuous as vol
from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.udp_client import SimpleUDPClient

from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class OSCServerDevice(NetworkedDevice):
    """OSC Server 'device' support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "port",
                description="Port of the OSC server",
                default=9000,
            ): vol.All(int, vol.Range(min=1, max=65535)),
            vol.Required(
                "pixel_count",
                description="The amount of channels OR if address_type == Three_addresses then this is the amount of RGB subsequent addresses (set to 3 if your addresses are defined like R,G,B,R,G,B)",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
            vol.Required(
                "send_type",
                description="One_Argument -> <addr> [R, G, B]; Three_Arguments -> <addr> R G B; Three_Addresses -> <addr> R, <addr+1> G, <addr+2> B; All_To_One -> <addr> [[R, G, B], [R, G, B], [R, G, B]]",
                default="One_Argument",
            ): vol.All(
                str,
                vol.In(
                    [
                        "One_Argument",
                        "Three_Arguments",
                        "Three_Addresses",
                        "All_To_One",
                    ]
                ),
            ),
            vol.Required(
                "starting_addr",
                description="Starting address/id of the OSC device",
                default=0,
            ): vol.All(int, vol.Range(min=0)),
            vol.Required(
                "path",
                description="The OSC Path to send to - Placeholders: {address} -> this will start at the starting_addr and count up",
                default="/0/dmx/{address}",
            ): vol.All(str),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self.last_frame = np.full((config["pixel_count"], 3), -1)

    def config_updated(self, config):
        self.last_frame = np.full((config["pixel_count"], 3), -1)
        self.deactivate()
        self.activate()

    def activate(self):
        self._client = SimpleUDPClient(self.destination, self._config["port"])
        _LOGGER.debug(
            f"{self._device_type} sender for {self._config['name']} started."
        )
        super().activate()

    def deactivate(self):
        super().deactivate()
        _LOGGER.debug(
            f"{self._device_type} sender for {self._config['name']} stopped."
        )
        if "_client" in dir(self):
            self._client._sock.close()
            self._client = None

    def flush(self, data):
        if np.array_equal(data, self.last_frame):
            return

        if data.size != self._config["pixel_count"] * 3:
            raise Exception(
                f"Invalid buffer size. {data.size} != {self._config['pixel_count'] * 3}"
            )

        # Get the config values to variables
        starting_addr = self._config["starting_addr"]

        # Convert data to rgb tuple
        colors = [(int(r), int(g), int(b)) for r, g, b in data]

        # Create array for messages
        messages = []

        # Go though all the pixels
        for i in range(self._config["pixel_count"]):
            # Get the rgb values from the colors array
            r, g, b = colors[i % len(colors)]
            if self._config["send_type"] == "One_Argument":
                send_data = OscMessageBuilder(
                    self.__generate_path(address=starting_addr + i)
                )
                send_data.add_arg([r / 255, g / 255, b / 255])
                messages.append(send_data)
            elif self._config["send_type"] == "Three_Arguments":
                # this one needs editing + saving the device after EVERY restart (atm) for some reason
                send_data = OscMessageBuilder(
                    self.__generate_path(address=starting_addr + i)
                )
                send_data.add_arg(r / 255)
                send_data.add_arg(g / 255)
                send_data.add_arg(b / 255)
                messages.append(send_data)
            elif self._config["send_type"] == "Three_Addresses":
                send_data_r = OscMessageBuilder(
                    self.__generate_path(address=starting_addr + (i * 3))
                )
                send_data_r.add_arg(r / 255)
                send_data_g = OscMessageBuilder(
                    self.__generate_path(address=starting_addr + (i * 3) + 1)
                )
                send_data_g.add_arg(g / 255)
                send_data_b = OscMessageBuilder(
                    self.__generate_path(address=starting_addr + (i * 3) + 2)
                )
                send_data_b.add_arg(b / 255)
                messages.append(send_data_r)
                messages.append(send_data_g)
                messages.append(send_data_b)
            elif self._config["send_type"] == "All_To_One":
                if len(messages) == 0:
                    send_data = OscMessageBuilder(
                        self.__generate_path(address=starting_addr)
                    )
                    send_data.add_arg([r / 255, g / 255, b / 255])
                    messages.append(send_data)
                else:
                    send_data = messages[0]
                    send_data.add_arg([r / 255, g / 255, b / 255])
                    messages[0] = send_data

        for message in messages:
            try:
                self._client.send(message.build())
            except AttributeError:
                self.activate()
                continue

        self.last_frame = np.copy(data)

    def __generate_path(self, path=None, address=None):
        path = self._config["path"] if path is None else path
        address = (
            self._config["starting_address"] if address is None else address
        )

        return path.format(address=address)
