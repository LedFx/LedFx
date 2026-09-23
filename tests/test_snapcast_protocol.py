"""Unit tests for the Snapcast binary protocol helpers."""

import json
import struct

import pytest

from ledfx.snapcast import protocol
from ledfx.snapcast.protocol import MessageType, ProtocolError


def _blob(data: bytes) -> bytes:
    return struct.pack("<I", len(data)) + data


def _wav_header(sample_rate=48000, bits=16, channels=2) -> bytes:
    block_align = channels * bits // 8
    fmt = struct.pack(
        "<HHIIHH",
        1,
        channels,
        sample_rate,
        sample_rate * block_align,
        block_align,
        bits,
    )
    return (
        b"RIFF"
        + struct.pack("<I", 36)
        + b"WAVE"
        + b"fmt "
        + struct.pack("<I", len(fmt))
        + fmt
        + b"data"
        + struct.pack("<I", 0)
    )


def _flac_header(sample_rate=44100, bits=24, channels=2) -> bytes:
    packed = (
        (sample_rate << 44)
        | ((channels - 1) << 41)
        | ((bits - 1) << 36)
        | 123456  # total samples
    )
    streaminfo = (
        struct.pack(">HH", 4096, 4096)
        + b"\x00" * 6  # min/max frame size
        + struct.pack(">Q", packed)
        + b"\x00" * 16  # MD5
    )
    return b"fLaC" + bytes([0x80, 0, 0, len(streaminfo)]) + streaminfo


class TestTimeValues:
    @pytest.mark.parametrize("seconds", [0.0, 1.5, 11973.086150, 2.9999999])
    def test_round_trip(self, seconds):
        sec, usec = protocol.to_tv(seconds)
        assert 0 <= usec < 1_000_000
        assert protocol.from_tv(sec, usec) == pytest.approx(seconds, abs=1e-6)

    def test_negative(self):
        sec, usec = protocol.to_tv(-0.25)
        assert (sec, usec) == (-1, 750000)
        assert protocol.from_tv(sec, usec) == pytest.approx(-0.25)


class TestHeader:
    def test_encode_decode(self):
        msg = protocol.encode_message(
            MessageType.TIME, b"12345678", msg_id=7, refers_to=3, sent=10.5
        )
        assert len(msg) == protocol.HEADER_SIZE + 8
        header = protocol.decode_header(msg[: protocol.HEADER_SIZE])
        assert header.type == MessageType.TIME
        assert header.id == 7
        assert header.refers_to == 3
        assert header.sent == pytest.approx(10.5)
        assert header.received == 0
        assert header.size == 8

    def test_matches_snapclient_layout(self):
        """Byte layout captured from snapclient 0.27's first Time message."""
        raw = bytes.fromhex(
            "0400"  # type = Time
            "0300"  # id = 3
            "0000"  # refersTo
            "c52e0000d5500100"  # sent = 11973 s, 86229 us
            "c52e000067500100"  # received = 11973 s, 86119 us
            "08000000"  # size
        )
        header = protocol.decode_header(raw)
        assert header.type == MessageType.TIME
        assert header.id == 3
        assert header.sent == pytest.approx(11973.086229)
        assert header.received == pytest.approx(11973.086119)
        assert header.size == 8
        # and encoding produces the same bytes (received is receiver-filled)
        assert (
            protocol.encode_message(
                MessageType.TIME, b"", msg_id=3, sent=11973.086229
            )[:14]
            == raw[:14]
        )

    def test_rejects_wrong_length(self):
        with pytest.raises(ProtocolError):
            protocol.decode_header(b"\x00" * 10)

    def test_rejects_oversized_payload(self):
        raw = protocol.HEADER.pack(2, 0, 0, 0, 0, 0, 0, 1 << 30)
        with pytest.raises(ProtocolError):
            protocol.decode_header(raw)


class TestPayloads:
    def test_hello(self):
        payload = protocol.encode_hello(
            client_id="ledfx-abcd1234",
            host_name="Living Room LEDs",
            version="2.1.0",
            os_name="Linux",
            arch="x86_64",
        )
        (length,) = struct.unpack_from("<I", payload)
        hello = json.loads(payload[4:])
        assert length == len(payload) - 4
        assert hello["ID"] == "ledfx-abcd1234"
        assert hello["HostName"] == "Living Room LEDs"
        assert hello["SnapStreamProtocolVersion"] == 2
        # Every key snapclient sends, so the server treats us the same way
        assert set(hello) == {
            "Arch",
            "ClientName",
            "HostName",
            "ID",
            "Instance",
            "MAC",
            "OS",
            "SnapStreamProtocolVersion",
            "Version",
        }

    def test_server_settings(self):
        payload = _blob(b'{"bufferMs":1000,"latency":20,"muted":false}')
        assert protocol.decode_json(payload) == {
            "bufferMs": 1000,
            "latency": 20,
            "muted": False,
        }

    @pytest.mark.parametrize(
        "payload", [b"\x05\x00", _blob(b"not json"), _blob(b"[1, 2]")]
    )
    def test_bad_json(self, payload):
        with pytest.raises(ProtocolError):
            protocol.decode_json(payload)

    def test_codec_header(self):
        payload = _blob(b"flac") + _blob(b"fLaC-header")
        assert protocol.decode_codec_header(payload) == (
            "flac",
            b"fLaC-header",
        )

    def test_wire_chunk(self):
        payload = struct.pack("<ii", 100, 250000) + _blob(b"audio")
        timestamp, data = protocol.decode_wire_chunk(payload)
        assert timestamp == pytest.approx(100.25)
        assert data == b"audio"

    def test_truncated_wire_chunk(self):
        payload = struct.pack("<ii", 100, 0) + struct.pack("<I", 50) + b"x"
        with pytest.raises(ProtocolError):
            protocol.decode_wire_chunk(payload)

    def test_time(self):
        payload = protocol.encode_time(1.25)
        assert protocol.decode_time(payload) == pytest.approx(1.25)


class TestFormats:
    def test_wav_header(self):
        fmt = protocol.parse_wav_header(_wav_header(44100, 24, 2))
        assert fmt == protocol.PcmFormat(44100, 24, 2)

    def test_wav_header_invalid(self):
        with pytest.raises(ProtocolError):
            protocol.parse_wav_header(b"OggS" + b"\x00" * 40)

    def test_flac_header(self):
        fmt = protocol.parse_flac_header(_flac_header(44100, 24, 2))
        assert fmt == protocol.PcmFormat(44100, 24, 2)

    def test_flac_header_invalid(self):
        with pytest.raises(ProtocolError):
            protocol.parse_flac_header(b"fLaC")
