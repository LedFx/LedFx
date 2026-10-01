import logging
from typing import Literal

import numpy as np
from pydantic import Field
from pythonosc.osc_message_builder import OscMessageBuilder
from pythonosc.udp_client import SimpleUDPClient

from ledfx.configuration.fields import X_REQUIRED
from ledfx.configuration.plugin import TypedConfig
from ledfx.devices import NetworkedDevice

_LOGGER = logging.getLogger(__name__)


class OSCServerDevice(NetworkedDevice):
    """OSC Server 'device' support"""

    class Config(NetworkedDevice.Config):
        port: int = Field(
            9000,
            description="Port of the OSC server",
            ge=1,
            le=65535,
            json_schema_extra={X_REQUIRED: True},
        )
        pixel_count: int = Field(
            1,
            description="The amount of channels OR if address_type == Three_addresses then this is the amount of RGB subsequent addresses (set to 3 if your addresses are defined like R,G,B,R,G,B)",
            ge=1,
            json_schema_extra={X_REQUIRED: True},
        )
        send_type: Literal[
            "One_Argument", "Three_Arguments", "Three_Addresses", "All_To_One"
        ] = Field(
            "One_Argument",
            description="One_Argument -> <addr> [R, G, B]; Three_Arguments -> <addr> R G B; Three_Addresses -> <addr> R, <addr+1> G, <addr+2> B; All_To_One -> <addr> [[R, G, B], [R, G, B], [R, G, B]]",
            json_schema_extra={X_REQUIRED: True},
        )
        starting_addr: int = Field(
            0,
            description="Starting address/id of the OSC device",
            ge=0,
            json_schema_extra={X_REQUIRED: True},
        )
        path: str = Field(
            "/0/dmx/{address}",
            description="The OSC Path to send to - Placeholders: {address} -> this will start at the starting_addr and count up",
            json_schema_extra={X_REQUIRED: True},
        )

    config = TypedConfig(Config)

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "OSC"
        self.last_frame = np.full((config["pixel_count"], 3), -1)

    OUTPUT_KEYS = (
        "ip_address",
        "port",
        "pixel_count",
        "send_type",
        "starting_addr",
        "path",
    )

    def config_updated(self, config):
        if not self._output_changed():
            return
        self.last_frame = np.full((self.config.pixel_count, 3), -1)
        self.deactivate()
        self.activate()
        self._built_settings = self._output_settings()

    def activate(self):
        self._client = SimpleUDPClient(self.destination, self.config.port)
        _LOGGER.debug(
            "%s sender for %s started.",
            self._device_type,
            self.config.name,
        )
        super().activate()

    def deactivate(self):
        super().deactivate()
        _LOGGER.debug(
            "%s sender for %s stopped.",
            self._device_type,
            self.config.name,
        )
        if getattr(self, "_client", None) is not None:
            self._client._sock.close()
            self._client = None

    def flush(self, data):
        if np.array_equal(data, self.last_frame):
            return

        if data.size != self.config.pixel_count * 3:
            raise Exception(  # noqa: TRY002
                f"Invalid buffer size. {data.size} != {self.config.pixel_count * 3}"
            )

        # Get the config values to variables
        starting_addr = self.config.starting_addr

        # Convert data to rgb tuple
        colors = data.astype(int)

        # Create array for messages
        messages = []

        # Go though all the pixels
        for i in range(self.config.pixel_count):
            # Get the rgb values from the colors array
            r, g, b = colors[i % len(colors)]
            if self.config.send_type == "One_Argument":
                send_data = OscMessageBuilder(
                    self.__generate_path(address=starting_addr + i)
                )
                send_data.add_arg([r / 255, g / 255, b / 255])
                messages.append(send_data)
            elif self.config.send_type == "Three_Arguments":
                # this one needs editing + saving the device after EVERY restart (atm) for some reason
                send_data = OscMessageBuilder(
                    self.__generate_path(address=starting_addr + i)
                )
                send_data.add_arg(r / 255)
                send_data.add_arg(g / 255)
                send_data.add_arg(b / 255)
                messages.append(send_data)
            elif self.config.send_type == "Three_Addresses":
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
            elif self.config.send_type == "All_To_One":
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
        path = self.config.path if path is None else path
        address = self.config.starting_addr if address is None else address

        return path.format(address=address)
