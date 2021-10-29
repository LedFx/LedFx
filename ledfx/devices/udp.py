import logging
import socket

import numpy as np
import voluptuous as vol

from ledfx.devices import NetworkedDevice, packets

_LOGGER = logging.getLogger(__name__)

SUPPORTED_PACKETS = [
    "DRGB",
    "WARLS",
    "DRGBW",
    "DNRGB",
    "adaptive_smallest"
]

class UDPDevice(NetworkedDevice):
    """Generic UDP device support"""

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name", description="Friendly name for the device"
            ): str,
            vol.Required(
                "port",
                description="Port for the UDP device",
                default=21324,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Required(
                "pixel_count",
                description="Number of individual pixels",
                default=1,
            ): vol.All(vol.Coerce(int), vol.Range(min=1)),
            vol.Required(
                "udp_packet_type",
                description="RGB packet encoding",
                default="DRGB",
            ): vol.In(list(SUPPORTED_PACKETS)),
            vol.Optional(
                "timeout",
                description="Seconds to wait after the last received packet to yield device control",
                default=1,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=255)),
        }
    )

    def activate(self):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        _LOGGER.info(f"UDP sender for {self.config['name']} started.")
        super().activate()

    def deactivate(self):
        super().deactivate()
        _LOGGER.info(f"UDP sender for {self.config['name']} stopped.")
        self._sock = None

    last_frame = None

    def flush(self, data):
        try:
            UDPDevice.send_out(
                self._sock,
                self.destination,
                self._config["port"],
                data,
                self.last_frame,
                self._config.get("udp_packet_type"),
                self._config.get("timeout"),
            )
            self.last_frame = np.copy(data)
        except AttributeError:
            self.activate()

    @staticmethod
    def send_out(
        sock,
        dest,
        port,
        data,
        last_frame,
        udp_packet_type,
        timeout=1,
    ):
        frame_size = len(data)

        if udp_packet_type == "DRGB" and frame_size <= 490:
            udpData = packets.build_drgb_packet(data, timeout)
            sock.sendto(bytes(udpData),(dest, port))

        elif udp_packet_type == "WARLS" and frame_size <= 255:
            udpData = packets.build_warls_packet(data, timeout, last_frame)
            sock.sendto(bytes(udpData),(dest, port))

        elif udp_packet_type == "DRGBW" and frame_size <= 367:
            udpData = packets.build_drgbw_packet(data, timeout)
            sock.sendto(bytes(udpData),(dest, port))

        elif udp_packet_type == "DNRGB":
            number_of_packets = int(np.ceil(frame_size / 489))
            for i in range(number_of_packets):
                start_index = i * 489
                end_index = start_index + 489
                udpData = packets.build_dnrgb_packet(data[start_index:end_index], timeout, start_index)
                sock.sendto(bytes(udpData),(dest, port))

        elif udp_packet_type == "adaptive_smallest" and frame_size <= 255:
            if last_frame is not None:
                # compare potential size of WARLS packet to DRGB packet
                if np.count_nonzero(np.any(data!=last_frame, axis=1)) * 4 < len(data) * 3:
                    udpData = packets.build_warls_packet(data, timeout, last_frame)
                    sock.sendto(bytes(udpData),(dest, port))
                    return
            udpData = packets.build_drgb_packet(data, timeout)
            sock.sendto(bytes(udpData),(dest, port))

        else:
            _LOGGER.warning(
                "UDP packet is configured incorrectly (check the pixel count vs the max size): https://kno.wled.ge/interfaces/udp-realtime/"
            )
            if frame_size <= 490: # DRGB
                udpData = packets.build_drgb_packet(data, timeout)
                sock.sendto(bytes(udpData),(dest, port))
            else:   #DNRGB
                number_of_packets = int(np.ceil(frame_size / 489))
                for i in range(number_of_packets):
                    start_index = i * 489
                    end_index = start_index + 489
                    udpData = packets.build_dnrgb_packet(data[start_index:end_index], timeout, start_index)
                    sock.sendto(bytes(udpData),(dest, port))


