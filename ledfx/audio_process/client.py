"""LedFx's side of the audio process.

AudioProcessClient starts the worker, accepts its connection only with the
token it was started with, and runs one reader thread that turns each snapshot
into a SnapshotView for AudioAnalysisSource.

The reader runs in the LedFx process and can fall behind like any other thread
there. So it pulls: it asks for the next snapshot as soon as one arrives, and
the worker holds only the newest until then (see worker). At most one snapshot
is ever on its way, so a slow reader gets fewer, never older, results.
"""

import logging
import multiprocessing
import secrets
import socket
import threading

import numpy as np

from ledfx.audio_process import protocol, worker
from ledfx.effects.audio_analyzer import SnapshotView

_LOGGER = logging.getLogger(__name__)

START_TIMEOUT = 10
COMMAND_TIMEOUT = 5


def spawn_process(port, token):
    """Default launcher: a fresh interpreter via multiprocessing's spawn
    context, which every platform supports and which shares no state with
    LedFx. Returns something with terminate() and join()."""
    process = multiprocessing.get_context("spawn").Process(
        target=worker.main, args=(port, token), name="LedFx audio", daemon=True
    )
    process.start()
    return process


_launcher = spawn_process


def set_launcher(launcher):
    """Replace how the worker gets started, e.g. as an Android service.

    `launcher(port, token)` must start something that calls
    ledfx.audio_process.worker.main(port, token), and return an object with
    terminate() and join(timeout), or None if it cannot be stopped from here.
    """
    global _launcher
    _launcher = launcher


class AudioProcessError(OSError):
    """An OSError, so device fallbacks treat it like any failed audio open."""


class AudioProcessClient:
    def __init__(self, on_results, on_disconnect=None):
        self.on_results = on_results
        self.on_disconnect = on_disconnect
        self._sock = None
        self._handle = None
        self._send_lock = threading.Lock()
        self._replies = {}
        self._reply_lock = threading.Lock()
        self._next_id = 0
        self._reader = None
        self.alive = False

    # -- lifecycle --------------------------------------------------------

    def start(self, timeout=START_TIMEOUT):
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            listener.bind(("127.0.0.1", 0))
            listener.listen(4)
            listener.settimeout(timeout)
            port = listener.getsockname()[1]
            token = secrets.token_hex(16)
            self._handle = _launcher(port, token)
            self._sock = self._accept(listener, token)
        finally:
            listener.close()
        self._sock.settimeout(None)
        self._sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        self.alive = True
        self._reader = threading.Thread(
            target=self._read_loop, name="AudioProcessReader", daemon=True
        )
        self._reader.start()
        self._send({"t": "next"})

    @staticmethod
    def _accept(listener, token):
        while True:
            try:
                conn, _ = listener.accept()
            except TimeoutError as e:
                raise AudioProcessError("the audio process did not connect") from e
            conn.settimeout(COMMAND_TIMEOUT)
            try:
                hello = protocol.recv(conn)
            except (OSError, ValueError, protocol.ProtocolError):
                conn.close()
                continue
            if hello.get("t") == "hello" and secrets.compare_digest(
                str(hello.get("token", "")), token
            ):
                _LOGGER.info("Audio process connected (pid %s)", hello.get("pid"))
                return conn
            _LOGGER.warning("Rejected a connection without the audio process token")
            conn.close()

    def stop(self):
        self.alive = False
        if self._sock is not None:
            try:
                self._send({"t": "quit"})
            except OSError:
                pass
            try:
                self._sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            self._sock.close()
        handle, self._handle = self._handle, None
        if handle is not None:
            handle.join(3)
            if getattr(handle, "is_alive", lambda: False)():
                handle.terminate()
        self.alive = False

    # -- commands ---------------------------------------------------------

    def _send(self, message):
        with self._send_lock:
            protocol.send(self._sock, message)

    def _request(self, message, timeout=COMMAND_TIMEOUT):
        with self._reply_lock:
            self._next_id += 1
            request_id = self._next_id
            done = threading.Event()
            self._replies[request_id] = [done, None]
        message["id"] = request_id
        self._send(message)
        if not done.wait(timeout):
            with self._reply_lock:
                self._replies.pop(request_id, None)
            raise AudioProcessError(f"no answer to {message['t']!r}")
        with self._reply_lock:
            return self._replies.pop(request_id)[1]

    def configure(self, audio_config, melbank_configs, coeffs_type):
        self._send(
            {
                "t": "configure",
                "audio_config": audio_config,
                "melbank_configs": melbank_configs,
                "coeffs_type": coeffs_type,
            }
        )

    def open(self, device, device_name, samplerate, blocksize, channels):
        reply = self._request(
            {
                "t": "open",
                "device": device,
                "device_name": device_name,
                "samplerate": samplerate,
                "blocksize": blocksize,
                "channels": channels,
            }
        )
        if reply.get("t") != "opened":
            raise AudioProcessError(reply.get("error", "could not open the device"))
        return reply["device"]

    def close(self):
        self._request({"t": "close"})

    def want(self, groups):
        """Compute only these result groups (AudioAnalyzer.set_wanted)."""
        self._send({"t": "want", "groups": None if groups is None else sorted(groups)})

    def push(self, samples):
        """Analyse a block LedFx received itself (browser or Sendspin audio)."""
        data = np.ascontiguousarray(np.frombuffer(samples, dtype=np.float32)).tobytes()
        self._send({"t": "block", "data": data})

    # -- reading ----------------------------------------------------------

    def _read_loop(self):
        try:
            while True:
                message = protocol.recv(self._sock)
                if message.get("t") != "snapshot":
                    self._reply(message)
                    continue
                # Ask now, so the worker can send the next one while this
                # one is handled; it holds the newest until then.
                self._send({"t": "next"})
                try:
                    self.on_results(SnapshotView(message["s"]))
                except Exception:
                    _LOGGER.exception("Error handling audio results")
        except (ConnectionError, OSError, protocol.ProtocolError, ValueError) as e:
            if self.alive:
                _LOGGER.error("Audio process connection lost: %s", e)
        finally:
            self.alive = False
            if self.on_disconnect is not None:
                self.on_disconnect()

    def _reply(self, message):
        with self._reply_lock:
            slot = self._replies.get(message.get("id"))
            if slot is not None:
                slot[1] = message
                slot[0].set()
