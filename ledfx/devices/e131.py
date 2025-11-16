import logging
import socket
import threading

import numpy as np
import sacn
import voluptuous as vol

from ledfx.devices import NetworkedDevice
from ledfx.utils import check_if_ip_is_broadcast

_LOGGER = logging.getLogger(__name__)


class BroadcastAwareSenderSocket(
    sacn.sending.sender_socket_udp.SenderSocketUDP
):
    """
    Custom sACN socket that automatically enables SO_BROADCAST when
    sending to broadcast addresses. Extends the standard UDP sender socket.
    """

    def __init__(self, listener, bind_address: str, bind_port: int, fps: int):
        super().__init__(listener, bind_address, bind_port, fps)
        self._broadcast_addresses = set()

    def add_broadcast_address(self, address: str):
        """Register an address as a broadcast address"""
        self._broadcast_addresses.add(address)

    def send_unicast(self, data, destination: str) -> None:
        """
        Override send_unicast to enable SO_BROADCAST when sending to
        registered broadcast addresses
        """
        if destination in self._broadcast_addresses:
            # Enable SO_BROADCAST for this send operation
            # Note: Accessing self._socket here is acceptable as we're in a subclass
            # This follows the same pattern as send_multicast and send_broadcast
            # in the parent class
            try:
                self._socket.setsockopt(
                    socket.SOL_SOCKET, socket.SO_BROADCAST, 1
                )
            except OSError as e:
                self._logger.warning(
                    f"Failed to enable SO_BROADCAST for {destination}: {e}"
                )

        # Call parent's send_unicast
        super().send_unicast(data, destination)


class E131Device(NetworkedDevice):
    """E1.31 device support"""

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
                default=1,
            ): vol.All(int, vol.Range(min=1)),
            vol.Optional(
                "universe_size",
                description="Size of each DMX universe",
                default=510,
            ): vol.All(int, vol.Range(min=1)),
            vol.Optional(
                "channel_offset",
                description="Channel offset within the DMX universe",
                default=0,
            ): vol.All(int, vol.Range(min=0)),
            vol.Optional(
                "packet_priority",
                description="Priority given to the sACN packets for this device",
                default=100,
            ): vol.All(int, vol.Range(min=0, max=200)),
        }
    )

    def __init__(self, ledfx, config):
        super().__init__(ledfx, config)
        # Since RGBW data is 4 packets, we can use 512 for RGBW LEDs; 512/4 = 128
        # The 129th pixels data will span into the next universe correctly
        # If it's not, we lose nothing by using a smaller universe size and keeping things easy for the end user (and us!)
        # if self._config["rgbw_led"] is True:
        #     self._config["universe_size"] = 512
        # else:
        #     self._config["universe_size"] = 510
        # Allow for configuring in terms of "pixels" or "channels"

        self._device_type = "e131"
        if "pixel_count" in self._config:
            self._config["channel_count"] = self._config["pixel_count"] * 3
        else:
            self._config["pixel_count"] = self._config["channel_count"] // 3

        span = (
            self._config["channel_offset"] + self._config["channel_count"] - 1
        )
        self._config["universe_end"] = self._config["universe"] + int(
            span / self._config["universe_size"]
        )
        if span % self._config["universe_size"] == 0:
            self._config["universe_end"] -= 1

        self._sacn = None
        self.device_lock = threading.Lock()

    def activate(self):
        with self.device_lock:
            if self._config["ip_address"].lower() == "multicast":
                multicast = True
            else:
                multicast = False

            if self._sacn:
                _LOGGER.warning(
                    f"sACN sender already started for device {self.id}"
                )

            # Check if the provided IP address is a broadcast address
            is_broadcast = False
            custom_socket = None
            if not multicast:
                is_broadcast = check_if_ip_is_broadcast(
                    self._config["ip_address"]
                )
                if is_broadcast:
                    _LOGGER.info(
                        f"Detected broadcast address {self._config['ip_address']} for device {self.config['name']}"
                    )
                    # Create a custom socket that will handle broadcast
                    # We pass this to sACNsender via its public socket parameter
                    custom_socket = BroadcastAwareSenderSocket(
                        listener=None,  # Will be set by sACNsender
                        bind_address="0.0.0.0",
                        bind_port=5568,
                        fps=self._config.get("refresh_rate", 30),
                    )
                    custom_socket.add_broadcast_address(
                        self._config["ip_address"]
                    )

            # Configure sACN and start the dedicated thread to flush the buffer
            # Some variables are immutable and must be called here
            # If we detected a broadcast address, pass our custom socket
            if custom_socket:
                self._sacn = sacn.sACNsender(
                    source_name=self.name, socket=custom_socket
                )
            else:
                self._sacn = sacn.sACNsender(source_name=self.name)

            for universe in range(
                self._config["universe"], self._config["universe_end"] + 1
            ):
                _LOGGER.info(f"sACN activating universe {universe}")
                self._sacn.activate_output(universe)
                self._sacn[universe].priority = self._config["packet_priority"]
                self._sacn[universe].multicast = multicast
                if not multicast:
                    self._sacn[universe].destination = self.destination

            self._sacn.start()
            self._sacn.manual_flush = True

            if is_broadcast:
                _LOGGER.info(
                    f"Enabled broadcast mode for device {self.config['name']}"
                )

            _LOGGER.info(f"sACN sender for {self.config['name']} started.")
            super().activate()

    def deactivate(self):
        super().deactivate()

        if not self._sacn:
            # He's dead, Jim
            # _LOGGER.warning("sACN sender not started.")
            return

        self.flush(np.zeros(self._config["channel_count"]))

        with self.device_lock:
            self._sacn.stop()
            self._sacn = None
            _LOGGER.info(f"sACN sender for {self.config['name']} stopped.")

    def flush(self, data):
        """Flush the data to all the E1.31 channels account for spanning universes"""

        with self.device_lock:
            if self._sacn is not None:
                if data.size != self._config["channel_count"]:
                    raise Exception(
                        f"Invalid buffer size. {data.size} != {self._config['channel_count']}"
                    )

                data = data.flatten()
                current_index = 0
                for universe in range(
                    self._config["universe"], self._config["universe_end"] + 1
                ):
                    # Calculate offset into the provide input buffer for the channel. There are some
                    # cleaner ways this can be done... This is just the quick and dirty
                    universe_start = (
                        universe - self._config["universe"]
                    ) * self._config["universe_size"]
                    universe_end = (
                        universe - self._config["universe"] + 1
                    ) * self._config["universe_size"]

                    dmx_start = (
                        max(universe_start, self._config["channel_offset"])
                        % self._config["universe_size"]
                    )
                    dmx_end = (
                        min(
                            universe_end,
                            self._config["channel_offset"]
                            + self._config["channel_count"],
                        )
                        % self._config["universe_size"]
                    )
                    if dmx_end == 0:
                        dmx_end = self._config["universe_size"]

                    input_start = current_index
                    input_end = current_index + dmx_end - dmx_start
                    current_index = input_end

                    dmx_data = np.array(self._sacn[universe].dmx_data)
                    dmx_data[dmx_start:dmx_end] = data[input_start:input_end]

                    # Because the sACN library checks for data to be of int type, we have to
                    # convert the numpy array into a python list of ints using tolist()
                    self._sacn[universe].dmx_data = dmx_data.tolist()

                self._sacn.flush()
