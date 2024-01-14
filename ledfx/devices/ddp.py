import logging
import multiprocessing
import queue
import socket
import struct

import numpy as np
import voluptuous as vol

from ledfx.devices import UDPDevice
from ledfx.events import LedFxShutdownEvent

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
        }
    )

    def __init__(self, ledfx, config):
        """
        Initialize a DDP device.

        Args:
            ledfx (LedFx): The main LedFx instance.
            config (dict): The configuration for the DDP device.
        """
        super().__init__(ledfx, config)
        self._device_type = "DDP"

        self.frame_count = 0
        self.ddp_queue = multiprocessing.Queue()
        self.parent_conn, self.child_conn = multiprocessing.Pipe()
        self.stop_event = multiprocessing.Event()
        self.ddp_sender_process = multiprocessing.Process(
            target=self.process_runner,
            args=(self.ddp_queue, self.child_conn, self.stop_event),
            daemon=False,
        )
        self.ddp_sender_process.start()
        _LOGGER.debug(
            f"{self._device_type} sender subprocess for {self._config['name']} started."
        )

        def on_shutdown(e):
            # Terminate the ddp_sender_process

            self.stop_event.set()
            self.deactivate()

        self._ledfx.events.add_listener(on_shutdown, LedFxShutdownEvent)

    def flush(self, data):
        """
        Add pixel data to the DDP queue for the subprocess to consume.

        Args:
            data: The data to be flushed.

        Raises:
            None

        Returns:
            None
        """
        self.frame_count += 1
        if self.parent_conn.poll():
            e = self.parent_conn.recv()
            _LOGGER.warning(
                f"Error in subprocess sender for {self._config['name']}: {e}"
            )
            self.deactivate()
        elif not self.stop_event.is_set():
            self.ddp_queue.put_nowait(
                (
                    self.destination,
                    self._config["port"],
                    data,
                    self.frame_count,
                )
            )

    def deactivate(self):
        """
        Deactivates the device by terminating the sender subprocess and cleaning up the DDP queue.
        """
        super().deactivate()
        _LOGGER.debug(
            f"Terminating {self._device_type} sender subprocess for {self._config['name']}."
        )
        if self.ddp_sender_process.is_alive():
            self.stop_event.set()
            self.ddp_sender_process.join()
        if self.ddp_queue is not None:
            self.ddp_queue.cancel_join_thread()
            while not self.ddp_queue.empty():
                try:
                    self.ddp_queue.get_nowait()
                except queue.Empty:
                    continue
            self.ddp_queue.close()
            self.ddp_queue = None

    # Begin DDPDevice Subprocess - Everything below here is run in a subprocess

    @staticmethod
    def process_runner(ddp_queue, parent_conn, stop_event):
        """
        Process runner for handling DDPDevice tasks.

        Args:
            ddp_queue (Queue): The queue containing DDPDevice tasks.
            parent_conn (Connection): The connection to the parent process.
            stop_event (Event): The event to signal when to stop processing.

        Returns:
            None

        Raises:
            OSError: If there is an error while sending data through the socket.


            The function uses three nested try: except blocks for error handling
            in different scenarios:

            1. The outer try: except block is used to catch KeyboardInterrupt and return from the function
               if the process is interrupted by the user.

            2. The middle try: except block is used to catch queue.Empty exception that may occur when getting
               tasks from the ddp_queue. If the queue is empty, the function continues to the next iteration
               of the while loop.

            3. The inner try: except block is used to catch any OSError that may occur while sending data
               through the socket. If an OSError occurs, it is sent to the parent process through the parent_conn
               connection and the processing is stopped.

            Note: The function uses a timeout of 25 milliseconds when getting tasks from the ddp_queue to
            avoid blocking indefinitely if there are no tasks available.
        """
        # Outer Try is to catch KeyboardInterrupt from parent process
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                # Stop the process if the stop_event is set
                while not stop_event.is_set():
                    # Middle Try is to catch queue.Empty exception and continue to next iteration
                    try:
                        task = ddp_queue.get(timeout=0.025)
                        destination, port, data, frame_count = task
                        # Inner Try is to catch OSError and send it to parent process
                        try:
                            DDPDevice.send_out(
                                sock, destination, port, data, frame_count
                            )
                        except OSError as e:
                            # Send OSError to parent process
                            parent_conn.send(e)
                            # Stop the process
                            break
                    except queue.Empty:
                        continue
                # exit process if the stop_event is set
                return
        except KeyboardInterrupt:
            ddp_queue = None
            return

    @staticmethod
    def send_out(sock, dest, port, data, frame_count):
        """
        Send out data packets over a socket using the DDP protocol.

        Args:
            sock (socket): The socket to send the data packets.
            dest (str): The destination IP address.
            port (int): The destination port number.
            data (numpy.ndarray): The data to be sent.
            frame_count (int): The current frame count.

        Returns:
            None
        """
        sequence = frame_count % 15 + 1
        byteData = data.astype(np.uint8).flatten().tobytes()
        packets, remainder = divmod(len(byteData), DDPDevice.MAX_DATALEN)
        if remainder == 0:
            packets -= 1  # divmod returns 1 when len(byteData) fits evenly in DDPDevice.MAX_DATALEN

        for i in range(packets + 1):
            data_start = i * DDPDevice.MAX_DATALEN
            data_end = data_start + DDPDevice.MAX_DATALEN
            DDPDevice.send_packet(
                sock, dest, port, sequence, i, byteData[data_start:data_end]
            )

    @staticmethod
    def send_packet(sock, dest, port, sequence, packet_count, data):
        """
        Sends a packet over UDP socket to the specified destination and port.

        Args:
            sock (socket): The UDP socket to send the packet.
            dest (str): The destination IP address.
            port (int): The destination port number.
            sequence (int): The sequence number of the packet.
            packet_count (int): The total number of packets.
            data (bytes): The data to be sent in the packet.

        Returns:
            None
        """
        bytes_length = len(data)
        udpData = bytearray()
        header = struct.pack(
            "!BBBBLH",
            DDPDevice.VER1
            | (
                DDPDevice.VER1
                if (bytes_length == DDPDevice.MAX_DATALEN)
                else DDPDevice.PUSH
            ),
            sequence,
            DDPDevice.DATATYPE,
            DDPDevice.SOURCE,
            packet_count * DDPDevice.MAX_DATALEN,
            bytes_length,
        )

        udpData.extend(header)
        udpData.extend(data)
        sock.sendto(
            bytes(udpData),
            (dest, port),
        )
