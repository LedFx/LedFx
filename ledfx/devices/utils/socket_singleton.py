import socket
from threading import Lock


class SocketSingleton:
    """_summary_

    Returns:
        _type_: _description_
    """

    _instances = {}
    _lock = Lock()

    def __new__(cls, recv_port):
        """creates a new singleton socket instance with a bind again the specified port
        Checks if an instance already exists for the specified port and returns it if it does.

        Args:
            recv_port: recieve port number

        Returns: socket instance new or existing
        """
        # Ensure that only one instance is created for each port
        with cls._lock:
            if recv_port not in cls._instances:
                # Create the new instance if it doesn't exist
                instance = super().__new__(cls)
                cls._instances[recv_port] = {
                    "instance": instance,
                    "ref_count": 0,
                }
            # Return the existing instance for the specified port
            return cls._instances[recv_port]["instance"]

    def __init__(self, recv_port):
        """Creates and adds reference count

        Args:
            recv_port: port to bind to
        """
        self.recv_port = recv_port
        self._create_socket()

        # Increment reference count
        SocketSingleton._instances[self.recv_port]["ref_count"] += 1

    def _create_socket(self):
        """Creates a new socket and binds it to the specified port."""
        if not hasattr(self, "udp_server"):
            self.udp_server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.udp_server.bind(("", self.recv_port))

    def close_socket(self):
        """Decrements the reference count and closes the socket if no more references exist."""
        with SocketSingleton._lock:
            if self.recv_port in SocketSingleton._instances:
                SocketSingleton._instances[self.recv_port]["ref_count"] -= 1
                if (
                    SocketSingleton._instances[self.recv_port]["ref_count"]
                    <= 0
                ):
                    # Close the socket and remove the instance
                    self.udp_server.close()
                    del SocketSingleton._instances[self.recv_port]

    def send_data(self, data, address):
        self.udp_server.sendto(data, address)

    def receive_data(self, buffer_size=1024):
        return self.udp_server.recvfrom(buffer_size)

    def settimeout(self, timeout):
        self.udp_server.settimeout(timeout)
