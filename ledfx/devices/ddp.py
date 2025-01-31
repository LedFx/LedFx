import logging
import struct
from socket import socket
from typing import Union

import numpy as np
import voluptuous as vol
from numpy import ndarray

from ledfx.devices import UDPDevice
from ledfx.events import DevicesUpdatedEvent

_LOGGER = logging.getLogger(__name__)


class DDPDevice(UDPDevice):
    """DDP device support"""

    # PORT = 4048
    HEADER_LEN = 0x0A
    # DDP_ID_VIRTUAL     = 1
    # DDP_ID_CONFIG      = 250
    # DDP_ID_STATUS      = 251

    MAX_PIXELS = 480
    MAX_DATALEN = MAX_PIXELS * 3  # fits nicely in an ethernet packet

    VER = 0xC0  # version mask
    VER1 = 0x40  # version=1
    PUSH = 0x01
    QUERY = 0x02
    REPLY = 0x04
    STORAGE = 0x08
    TIME = 0x10
    DATATYPE = 0x01
    SOURCE = 0x01
    TIMEOUT = 1

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
                default=1,
            ): vol.All(int, vol.Range(min=1)),
            vol.Required(
                "port",
                description="Port for the UDP device",
                default=4048,
            ): vol.All(int, vol.Range(min=1, max=65535)),
            vol.Optional(
                "stuff_to_32",
                description="Test Only: stuff the data only to 32 pixels.",
                default=False,
            ): bool,
            vol.Optional(
                "pixel_to_32",
                description="Test Only: stuff to 32 pixels",
                default=False,
            ): bool,
            vol.Optional(
                "dump",
                description="dump packets",
                default=False,
            ): bool,
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        self._device_type = "DDP"
        self.frame_count = 0
        self.connection_warning = False
        self.destination_port = self._config["port"]

    def flush(self, data: ndarray) -> None:
        """
        Flushes LED data to the DDP device.

        Args:
            data (ndarray): The LED data to be flushed.

        Raises:
            AttributeError: If an attribute error occurs during the flush.
            OSError: If an OS error occurs during the flush.
        """
        
        self.frame_count += 1
        try:
            data2 = data.copy()

            if self.config.get("pixel_to_32", False):
                if len(data2) < (32 * 3):
                    pixel_val = [0xFF, 0x00, 0xFF]
                    for _ in range(32 - len(data2)):
                        data2 = np.append(data2, pixel_val) 

            DDPDevice.send_out(
                self._sock,
                self.destination,
                self.destination_port,
                data2,
                self.frame_count,
                self.config.get("stuff_to_32", False),
                self.config.get("pixel_to_32", False),
                self.config.get("dump", False),
            )

            if self.connection_warning:
                # If we have reconnected, log it, come back online, and fire an event to the frontend
                _LOGGER.info(f"DDP connection to {self.name} re-established.")
                self.connection_warning = False
                self._online = True
                self._ledfx.events.fire_event(DevicesUpdatedEvent(self.id))
        except AttributeError:
            self.activate()
        except OSError as e:
            # print warning only once until it clears
            if not self.connection_warning:
                # If we have lost connection, log it, go offline, and fire an event to the frontend
                _LOGGER.warning(f"Error in DDP connection to {self.name}: {e}")
                self.connection_warning = True
                self._online = False
                self._ledfx.events.fire_event(DevicesUpdatedEvent(self.id))

    @staticmethod
    def send_out(
        sock: socket, dest: str, port: int, data: ndarray, frame_count: int, stuff: bool, pixels: bool, dump: bool
    ) -> None:
        """
        Sends out data packets over a socket using the DDP protocol.

        Args:
            sock (socket): The socket to send the packet over.
            dest (str): The destination IP address.
            port (int): The destination port number.
            data (ndarray): The data to be sent in the packet.
            frame_count(int): The count of frames.

        Returns:
        None
        """
        sequence = frame_count % 15 + 1
        byteData = memoryview(data.astype(np.uint8).ravel())
        packets, remainder = divmod(len(byteData), DDPDevice.MAX_DATALEN)
        if remainder == 0:
            packets -= 1  # divmod returns 1 when len(byteData) fits evenly in DDPDevice.MAX_DATALEN

        for i in range(packets + 1):
            data_start = i * DDPDevice.MAX_DATALEN
            data_end = data_start + DDPDevice.MAX_DATALEN
            DDPDevice.send_packet(
                sock,
                dest,
                port,
                sequence,
                i,
                byteData[data_start:data_end],
                i == packets,
                stuff,
                pixels,
                dump
            )

    @staticmethod
    def send_packet(
        sock: socket,
        dest: str,
        port: int,
        sequence: int,
        packet_count: int,
        data: Union[bytes, memoryview],
        last: bool,
        stuff: bool,
        pixels: bool,
        dump: bool
    ) -> None:
        """
        Sends a DDP packet over a socket to a specified destination.

        Args:
            sock (socket): The socket to send the packet over.
            dest (str): The destination IP address.
            port (int): The destination port number.
            sequence (int): The sequence number of the packet.
            packet_count (int): The total number of packets.
            data (bytes or memoryview): The data to be sent in the packet.
            last (bool): Indicates if this is the last packet in the sequence.

        Returns:
            None
        """
        bytes_length = len(data)
        header = struct.pack(
            "!BBBBLH",
            DDPDevice.VER1 | (DDPDevice.PUSH if last else 0),
            sequence,
            DDPDevice.DATATYPE,
            DDPDevice.SOURCE,
            packet_count * DDPDevice.MAX_DATALEN,
            bytes_length,
        )
        udpData = header + bytes(data)

        if stuff:
            udpData = udpData + b"\x55" * (32 * 3 - len(data))
        
        if dump:
            if stuff:
                st = "S"
            else:
                st = "."

            if pixels:
                px = "P"
            else:
                px = "."

            # debug the content of updData as hex bytes with 16 bytes to a line
            # First 12 bytes on a single line
            if len(udpData) > 0:
                first_chunk = udpData[:10].hex(' ')
                _LOGGER.error(f"{st}{px}: {first_chunk}")

            # Remaining bytes in chunks of 24 bytes per line
            for i in range(10, len(udpData), 24):
                hex_chunk = udpData[i : i + 24].hex(" ")
                _LOGGER.error(f"{int((i-10)/3):02d}: {hex_chunk}")
            _LOGGER.error("end")

        sock.sendto(
            udpData,
            (dest, port),
        )
