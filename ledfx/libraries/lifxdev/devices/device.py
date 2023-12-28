#!/usr/bin/env python3

from __future__ import annotations

import socket
from collections.abc import Callable

from ledfx.libraries.lifxdev.messages import device_messages, packet


class LifxDevice:
    """LIFX device control"""

    def __init__(
        self,
        ip: str,
        *,
        mac_addr: str | None = None,
        port: int = packet.LIFX_PORT,
        buffer_size: int = packet.BUFFER_SIZE,
        timeout: float = packet.TIMEOUT_S,
        verbose: bool = False,
        comm_init: Callable | None = None,
    ):
        """Create a LIFX device from an IP address

        Args:
            ip: (str) IP addess of the device.
            mac_addr: (str) Mac address of the device.
            port: (int) UDP port of the device.
            buffer_size: (int) Buffer size for receiving UDP responses.
            broadcast: (bool) Whether the IP address is a broadcast address.
            verbose: (bool) Use logging.info instead of logging.debug.
            comm_init: (function) This function (no args) creates a socket object.
        """
        if comm_init:
            comm = comm_init()
        else:
            comm = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        comm.settimeout(timeout)
        comm.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        udp_sender = packet.UdpSender(
            mac_addr=mac_addr,
            ip=ip,
            port=port,
            comm=comm,
            buffer_size=buffer_size,
        )
        self._comm = packet.PacketComm(udp_sender, verbose, timeout)
        self._verbose = verbose

    @property
    def ip(self) -> str:
        return self._comm.ip

    def send_msg(
        self,
        payload: packet.LifxMessage,
        *,
        ack_required: bool = False,
        verbose: bool = False,
    ) -> packet.LifxResponse | None:
        """Send a message to a device.

        This can be used to send any LIFX message to the device. Functions
        that send messages to the device will all wrap this function. This
        function can be used when a wrapper for a message is not available.

        Args:
            payload: (packet.LifxMessage) LIFX message to send to a device.
            ack_required: (bool) Require an acknowledgement from the device.
            verbose: (bool) Log messages as info instead of debug.
        """
        response = self.send_recv(
            payload, ack_required=ack_required, verbose=verbose
        )
        if response:
            return response.pop()

    def send_recv(
        self,
        payload: packet.LifxMessage,
        *,
        res_required: bool = False,
        ack_required: bool = False,
        ip: str | None = None,
        port: int | None = None,
        mac_addr: str | None = None,
        comm: socket.socket | None = None,
        retry_recv: bool = False,
        verbose: bool = False,
    ) -> list[packet.LifxResponse] | None:
        """Send a message to a device or broadcast address.

        This can be used to send any LIFX message to the device. Functions
        that send messages to the device will all wrap this function. This
        function can be used when a wrapper for a message is not available.

        Args:
            payload: (packet.LifxMessage) LIFX message to send to a device.
            res_required: (bool) Require a response from the light.
            ack_required: (bool) Require an acknowledgement from the device.
            ip: (str) Override the IP address.
            port: (int) Override the UDP port.
            mac_addr: (str) Override the MAC address.
            comm: (socket) Override the UDP socket.
            retry_recv: (bool) Re-run recv_from until there are no more packets.
            verbose: (bool) Log messages as info instead of debug.
        """
        if res_required and ack_required:
            raise ValueError(
                "Cannot set both res_required and ack_required to True."
            )
        return self._comm.send_recv(
            payload=payload,
            res_required=res_required,
            ack_required=ack_required,
            ip=ip,
            port=port,
            mac_addr=mac_addr,
            comm=comm,
            retry_recv=retry_recv,
            verbose=verbose or self._verbose,
        )

    def get_power(self) -> bool:
        """Return True if the light is powered on."""
        response = self.send_recv(
            device_messages.GetPower(), res_required=True
        )
        assert response is not None
        return response.pop().payload["level"]

    def set_power(
        self, state: bool, *, ack_required=False
    ) -> packet.LifxResponse | None:
        """Set power state on the device"""
        power = device_messages.SetPower(level=state)
        response = self.send_recv(power, ack_required=ack_required)
        if response:
            return response.pop()
