"""The audio process: capture, analysis, and nothing that renders.

It connects back to LedFx, proves it was started by it (token), then follows
commands: configure the analyzer, open or close a capture device, analyse
blocks LedFx forwards from network sources. The device callback only analyses;
a separate thread writes to the socket, so a slow LedFx can never stall the
capture.

Snapshots are pulled, not pushed: one goes out only when LedFx asked for it
with "next". Until then the newest one replaces the older, with the per-block
event flags of the replaced one ORed in, so a reader that is behind gets fresh
values and no lost onset or beat, and never a backlog to work through.
"""

import collections
import logging
import os
import socket
import sys
import threading

import numpy as np

from ledfx.audio_process import protocol
from ledfx.effects.audio_analyzer import AudioAnalyzer

_LOGGER = logging.getLogger(__name__)

EVENT_FLAGS = ("onset", "bpm_beat_now", "volume_beat_now")


class AudioWorker:
    def __init__(self, sock, audio_module):
        self._sock = sock
        self._sd = audio_module
        self._analyzer = None
        self._stream = None
        self._cond = threading.Condition()
        self._replies = collections.deque()
        self._latest = None
        self._wanted = False
        self._running = True
        self._sender = threading.Thread(
            target=self._send_loop, name="AudioWorkerSend", daemon=True
        )

    # -- outgoing ---------------------------------------------------------

    def _next_message(self):
        with self._cond:
            while True:
                if self._replies:
                    return self._replies.popleft()
                if not self._running:
                    return None
                if self._wanted and self._latest is not None:
                    snapshot, self._latest = self._latest, None
                    self._wanted = False
                    return {"t": "snapshot", "s": snapshot}
                self._cond.wait()

    def _send_loop(self):
        while True:
            message = self._next_message()
            if message is None:
                return
            try:
                protocol.send(self._sock, message)
            except OSError:
                self._stop()
                return

    def _post(self, message):
        with self._cond:
            self._replies.append(message)
            self._cond.notify()

    def _offer(self, snapshot):
        with self._cond:
            older = self._latest
            if older is not None:
                for name in EVENT_FLAGS:
                    snapshot[name] = snapshot[name] or older[name]
            self._latest = snapshot
            self._cond.notify()

    def _want(self):
        with self._cond:
            self._wanted = True
            self._cond.notify()

    def _stop(self):
        with self._cond:
            self._running = False
            self._cond.notify()

    def _analyse(self, samples):
        analyzer = self._analyzer
        if analyzer is not None and analyzer.process(samples):
            self._offer(analyzer.snapshot())

    # -- capture ----------------------------------------------------------

    # Parameter names as AudioInputSource's callback has them: the Android
    # sounddevice shim passes them by keyword, PortAudio by position.
    def _callback(self, in_data, frame_count, time_info, status):
        self._analyse(in_data)

    def _resolve_device(self, index, name):
        devices = self._sd.query_devices()
        hostapis = self._sd.query_hostapis()

        def full_name(i):
            device = devices[i]
            return f"{hostapis[device['hostapi']]['name']}: {device['name']}"

        if name and 0 <= index < len(devices) and full_name(index) == name:
            return index
        if name:
            for i in range(len(devices)):
                if devices[i]["max_input_channels"] > 0 and full_name(i) == name:
                    return i
            raise LookupError(f"audio device {name!r} not found in the audio process")
        return index

    def _open(self, msg):
        self._close()
        device = self._resolve_device(msg["device"], msg.get("device_name"))
        kwargs = {
            "samplerate": msg["samplerate"],
            "device": device,
            "callback": self._callback,
            "dtype": np.float32,
            "latency": "low",
            "blocksize": msg["blocksize"],
        }
        if msg.get("channels") is not None:
            kwargs["channels"] = msg["channels"]
        stream = self._sd.InputStream(**kwargs)
        stream.start()
        self._stream = stream
        return device

    def _close(self):
        stream, self._stream = self._stream, None
        if stream is not None:
            try:
                stream.stop()
                stream.close()
            except Exception:
                _LOGGER.warning("Error closing the audio stream", exc_info=True)

    # -- commands ---------------------------------------------------------

    def handle(self, msg):
        kind = msg.get("t")
        if kind == "configure":
            self._analyzer = AudioAnalyzer(
                msg["audio_config"], msg["melbank_configs"], msg["coeffs_type"]
            )
        elif kind == "next":
            self._want()
        elif kind == "block":
            self._analyse(np.frombuffer(msg["data"], dtype=np.float32))
        elif kind == "open":
            try:
                device = self._open(msg)
            except Exception as e:  # noqa: BLE001
                self._post(
                    {
                        "t": "open_failed",
                        "id": msg.get("id"),
                        "error": f"{type(e).__name__}: {e}",
                    }
                )
            else:
                self._post({"t": "opened", "id": msg.get("id"), "device": device})
        elif kind == "close":
            self._close()
            self._post({"t": "closed", "id": msg.get("id")})
        elif kind == "quit":
            self._stop()
        else:
            _LOGGER.warning("Unknown command %r", kind)

    def serve(self):
        self._sender.start()
        try:
            while self._running:
                self.handle(protocol.recv(self._sock))
        except (ConnectionError, OSError):
            pass
        finally:
            self._stop()
            self._close()


def main(port, token, audio_module=None):
    """Entry point of the audio process: connect to LedFx on 127.0.0.1:port."""
    logging.basicConfig(level=logging.INFO, stream=sys.stderr)
    if audio_module is None:
        import sounddevice as audio_module
    sock = socket.create_connection(("127.0.0.1", port), timeout=3)
    sock.settimeout(None)
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    protocol.send(sock, {"t": "hello", "token": token, "pid": os.getpid()})
    AudioWorker(sock, audio_module).serve()
    sock.close()


if __name__ == "__main__":
    main(int(sys.argv[1]), sys.argv[2])
