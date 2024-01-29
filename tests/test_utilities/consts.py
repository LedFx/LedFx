import random
from http.server import HTTPServer, SimpleHTTPRequestHandler

import pytest


class PortPicker:
    @staticmethod
    def pick_port(max_tries=10):
        for _ in range(max_tries):
            port = random.randint(4000, 10000)
            try:
                server = HTTPServer(
                    ("localhost", port), SimpleHTTPRequestHandler
                )
                server.server_close()
                return port
            except OSError:
                continue
        pytest.fail(f"Could not find an open port after {max_tries} tries.")


global BASE_URL
global BASE_PORT
global SERVER_PATH
BASE_URL = "127.0.0.1"
BASE_PORT = PortPicker.pick_port()
SERVER_PATH = f"{BASE_URL}:{BASE_PORT}"
