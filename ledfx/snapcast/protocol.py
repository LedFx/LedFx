"""Snapcast binary stream protocol (client side).

Snapcast clients talk to snapserver over TCP (default port 1704).  Every
message starts with a fixed 26-byte little-endian header followed by a
type-specific payload:

    uint16 type        MessageType
    uint16 id          sender-assigned message id
    uint16 refersTo    id of the message this one answers (Time replies)
    int32  sent.sec    sender clock when the message was sent
    int32  sent.usec
    int32  recv.sec    receiver clock when the message was received
    int32  recv.usec   (filled in by the receiver)
    uint32 size        payload size in bytes

Strings and blobs inside payloads are length-prefixed with a uint32.

Reference: https://github.com/badaix/snapcast/blob/develop/doc/binary_protocol.md
"""

import json
import struct
from dataclasses import dataclass
from enum import IntEnum

HEADER = struct.Struct("<HHHiiiiI")
HEADER_SIZE = HEADER.size  # 26

# Protocol version advertised in Hello, matching snapclient 0.27+
SNAPSTREAM_PROTOCOL_VERSION = 2

# Hard upper bound on a single payload.  Real messages are a few KB at most;
# anything larger means we are out of sync with the stream or talking to
# something that is not a snapserver.
MAX_PAYLOAD_SIZE = 16 * 1024 * 1024

_U32 = struct.Struct("<I")
_TV = struct.Struct("<ii")


class MessageType(IntEnum):
    BASE = 0
    CODEC_HEADER = 1
    WIRE_CHUNK = 2
    SERVER_SETTINGS = 3
    TIME = 4
    HELLO = 5
    STREAM_TAGS = 6
    CLIENT_INFO = 7


class ProtocolError(Exception):
    """Raised when data received from the server cannot be parsed."""


@dataclass
class Header:
    type: int
    id: int
    refers_to: int
    sent: float  # seconds
    received: float  # seconds
    size: int


@dataclass
class PcmFormat:
    sample_rate: int
    bit_depth: int
    channels: int


def to_tv(seconds: float) -> tuple[int, int]:
    """Split a time in seconds into the (sec, usec) pair used on the wire."""
    sec = int(seconds // 1)
    usec = int(round((seconds - sec) * 1_000_000))
    if usec >= 1_000_000:
        sec += 1
        usec -= 1_000_000
    return sec, usec


def from_tv(sec: int, usec: int) -> float:
    return sec + usec / 1_000_000


def encode_message(
    msg_type: int,
    payload: bytes,
    msg_id: int = 0,
    refers_to: int = 0,
    sent: float = 0.0,
) -> bytes:
    """Build a complete wire message (header + payload)."""
    sent_sec, sent_usec = to_tv(sent)
    header = HEADER.pack(
        msg_type,
        msg_id & 0xFFFF,
        refers_to & 0xFFFF,
        sent_sec,
        sent_usec,
        0,
        0,
        len(payload),
    )
    return header + payload


def decode_header(data: bytes) -> Header:
    if len(data) != HEADER_SIZE:
        raise ProtocolError(
            f"header must be {HEADER_SIZE} bytes, got {len(data)}"
        )
    msg_type, msg_id, refers_to, ss, su, rs, ru, size = HEADER.unpack(data)
    if size > MAX_PAYLOAD_SIZE:
        raise ProtocolError(f"payload size {size} exceeds limit")
    return Header(
        type=msg_type,
        id=msg_id,
        refers_to=refers_to,
        sent=from_tv(ss, su),
        received=from_tv(rs, ru),
        size=size,
    )


def _read_blob(payload: bytes, offset: int) -> tuple[bytes, int]:
    """Read a uint32 length-prefixed blob starting at *offset*."""
    if offset + 4 > len(payload):
        raise ProtocolError("truncated length prefix")
    (length,) = _U32.unpack_from(payload, offset)
    start = offset + 4
    end = start + length
    if end > len(payload):
        raise ProtocolError("truncated payload")
    return payload[start:end], end


def encode_json(data: dict) -> bytes:
    raw = json.dumps(data, separators=(",", ":")).encode("utf-8")
    return _U32.pack(len(raw)) + raw


def decode_json(payload: bytes) -> dict:
    raw, _ = _read_blob(payload, 0)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ProtocolError(f"invalid JSON payload: {exc}") from exc
    if not isinstance(value, dict):
        raise ProtocolError("JSON payload is not an object")
    return value


def encode_hello(
    client_id: str,
    host_name: str,
    version: str,
    os_name: str = "",
    arch: str = "",
    instance: int = 1,
) -> bytes:
    """Build the Hello payload a client sends right after connecting.

    Snapserver identifies clients by ``ID`` (persisting their name, group,
    volume and latency against it) and shows ``HostName`` in its UIs.
    """
    return encode_json(
        {
            "Arch": arch,
            "ClientName": "LedFx",
            "HostName": host_name,
            "ID": client_id,
            "Instance": instance,
            "MAC": "00:00:00:00:00:00",
            "OS": os_name,
            "SnapStreamProtocolVersion": SNAPSTREAM_PROTOCOL_VERSION,
            "Version": version,
        }
    )


def decode_codec_header(payload: bytes) -> tuple[str, bytes]:
    """Return (codec name, codec-specific header) from a CodecHeader payload."""
    codec, offset = _read_blob(payload, 0)
    header, _ = _read_blob(payload, offset)
    return codec.decode("ascii", errors="replace"), header


def decode_wire_chunk(payload: bytes) -> tuple[float, bytes]:
    """Return (server timestamp in seconds, encoded audio) from a WireChunk."""
    if len(payload) < _TV.size:
        raise ProtocolError("truncated wire chunk")
    sec, usec = _TV.unpack_from(payload, 0)
    data, _ = _read_blob(payload, _TV.size)
    return from_tv(sec, usec), data


def encode_time(latency: float = 0.0) -> bytes:
    return _TV.pack(*to_tv(latency))


def decode_time(payload: bytes) -> float:
    """Return the ``latency`` field of a Time message in seconds.

    In a server reply this is the server receive time minus the client send
    time of the request, i.e. client->server transit plus clock offset.
    """
    if len(payload) < _TV.size:
        raise ProtocolError("truncated time message")
    return from_tv(*_TV.unpack_from(payload, 0))


def parse_wav_header(header: bytes) -> PcmFormat:
    """Extract the PCM format from the RIFF header sent for the pcm codec."""
    if len(header) < 12 or header[:4] != b"RIFF" or header[8:12] != b"WAVE":
        raise ProtocolError("pcm codec header is not a RIFF/WAVE header")
    offset = 12
    while offset + 8 <= len(header):
        chunk_id = header[offset : offset + 4]
        (chunk_size,) = _U32.unpack_from(header, offset + 4)
        body = offset + 8
        if chunk_id == b"fmt ":
            if body + 16 > len(header):
                break
            _, channels, sample_rate, _, _, bit_depth = struct.unpack_from(
                "<HHIIHH", header, body
            )
            return PcmFormat(sample_rate, bit_depth, channels)
        offset = body + chunk_size + (chunk_size & 1)
    raise ProtocolError("pcm codec header has no fmt chunk")


def parse_flac_header(header: bytes) -> PcmFormat:
    """Extract the PCM format from the STREAMINFO block of a FLAC header."""
    # "fLaC" + metadata block header (4 bytes) + STREAMINFO (34 bytes)
    if len(header) < 42 or header[:4] != b"fLaC":
        raise ProtocolError("flac codec header has no STREAMINFO")
    if header[4] & 0x7F != 0:
        raise ProtocolError("first flac metadata block is not STREAMINFO")
    # Bytes 10..17 of STREAMINFO hold sample rate (20 bits), channels-1
    # (3 bits), bits per sample-1 (5 bits) and total samples (36 bits).
    (packed,) = struct.unpack_from(">Q", header, 8 + 10)
    sample_rate = packed >> 44
    channels = ((packed >> 41) & 0x7) + 1
    bit_depth = ((packed >> 36) & 0x1F) + 1
    return PcmFormat(sample_rate, bit_depth, channels)
