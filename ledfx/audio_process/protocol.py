"""Message framing between LedFx and its audio process.

A message is a dict of JSON-compatible values plus bytes. On the wire:

    4 bytes  big-endian length of everything that follows
    4 bytes  length of the JSON header
    header   UTF-8 JSON; every bytes value is replaced by {"__blob__": i}
    4 bytes  number of blobs
    blobs    the bytes values in order, each prefixed with its 4-byte length

The leading total length lets the reader take a whole message in two socket
reads and split it in memory. Every blocking read gives up the interpreter
lock, and in a busy LedFx process getting it back costs up to a switch
interval each time, so a read per field made one snapshot cost tens of ms.

JSON plus raw bytes rather than pickle: anything on the machine can connect to
a loopback port, and unpickling what it sends would run its code.
"""

import json
import struct

_LEN = struct.Struct(">I")
# A snapshot is a few KB and an audio block well under 100 KB.
MAX_FRAME = 16 * 1024 * 1024


class ProtocolError(Exception):
    pass


def _strip_blobs(value, blobs):
    if isinstance(value, (bytes, bytearray, memoryview)):
        blobs.append(bytes(value))
        return {"__blob__": len(blobs) - 1}
    if isinstance(value, dict):
        return {k: _strip_blobs(v, blobs) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_strip_blobs(v, blobs) for v in value]
    return value


def _restore_blobs(value, blobs):
    if isinstance(value, dict):
        if set(value) == {"__blob__"}:
            index = value["__blob__"]
            if not isinstance(index, int) or not 0 <= index < len(blobs):
                raise ProtocolError(f"bad blob reference {index!r}")
            return blobs[index]
        return {k: _restore_blobs(v, blobs) for k, v in value.items()}
    if isinstance(value, list):
        return [_restore_blobs(v, blobs) for v in value]
    return value


def encode(message):
    blobs = []
    header = json.dumps(_strip_blobs(message, blobs), separators=(",", ":")).encode()
    parts = [_LEN.pack(len(header)), header, _LEN.pack(len(blobs))]
    for blob in blobs:
        parts.append(_LEN.pack(len(blob)))
        parts.append(blob)
    body = b"".join(parts)
    return _LEN.pack(len(body)) + body


def _recv_exact(sock, size):
    if size > MAX_FRAME:
        raise ProtocolError(f"frame of {size} bytes exceeds {MAX_FRAME}")
    buf = bytearray(size)
    view = memoryview(buf)
    got = 0
    while got < size:
        n = sock.recv_into(view[got:], size - got)
        if n == 0:
            raise ConnectionError("peer closed the connection")
        got += n
    return bytes(buf)


class _Cursor:
    def __init__(self, body):
        self._body = body
        self._at = 0

    def take(self, size):
        end = self._at + size
        if end > len(self._body):
            raise ProtocolError("message shorter than its fields")
        chunk = self._body[self._at : end]
        self._at = end
        return chunk

    def length(self):
        return _LEN.unpack(self.take(_LEN.size))[0]

    def done(self):
        return self._at == len(self._body)


def decode(body):
    cursor = _Cursor(body)
    header = json.loads(cursor.take(cursor.length()))
    blobs = [cursor.take(cursor.length()) for _ in range(cursor.length())]
    if not cursor.done():
        raise ProtocolError("message longer than its fields")
    return _restore_blobs(header, blobs)


def recv(sock):
    """Read one message. Raises ConnectionError when the peer has gone."""
    (size,) = _LEN.unpack(_recv_exact(sock, _LEN.size))
    return decode(_recv_exact(sock, size))


def send(sock, message):
    sock.sendall(encode(message))
