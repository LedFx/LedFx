"""Tests for the DMX Input (Art-Net) integration parser and mapping logic."""

import struct

from ledfx.integrations.dmx_input import _channel, parse_artdmx


def _build_artdmx(universe: int, dmx: bytes, sequence: int = 1) -> bytes:
    """Build a spec-compliant ArtDMX packet for testing."""
    length = len(dmx)
    header = b"Art-Net\x00"
    header += struct.pack("<H", 0x5000)  # OpCode little-endian
    header += struct.pack(">H", 14)  # ProtVer big-endian
    header += bytes([sequence, 0])  # Sequence, Physical
    header += struct.pack("<H", universe & 0x7FFF)  # Port-Address LE
    header += struct.pack(">H", length)  # Length big-endian
    return header + dmx


def test_parse_valid_artdmx():
    dmx = bytes([0, 200, 50] + [0] * 9)
    pkt = _build_artdmx(7, dmx)
    result = parse_artdmx(pkt)
    assert result is not None
    universe, data = result
    assert universe == 7
    assert data == dmx


def test_parse_respects_length_field():
    dmx = bytes([10, 20, 30, 40])
    pkt = _build_artdmx(0, dmx)
    universe, data = parse_artdmx(pkt)
    assert len(data) == 4
    assert data == dmx


def test_parse_rejects_non_artnet():
    assert parse_artdmx(b"NOT-ARTNET-DATA-AT-ALL") is None


def test_parse_rejects_wrong_opcode():
    pkt = bytearray(_build_artdmx(0, bytes([1, 2, 3])))
    pkt[8:10] = struct.pack("<H", 0x2000)  # ArtPoll, not ArtDMX
    assert parse_artdmx(bytes(pkt)) is None


def test_parse_rejects_short_packet():
    assert parse_artdmx(b"Art-Net\x00\x00\x50") is None


def test_parse_high_universe():
    pkt = _build_artdmx(300, bytes([1, 2, 3]))
    universe, _ = parse_artdmx(pkt)
    assert universe == 300


def test_channel_is_one_based():
    dmx = bytes([11, 22, 33])
    assert _channel(dmx, 1) == 11
    assert _channel(dmx, 2) == 22
    assert _channel(dmx, 3) == 33


def test_channel_out_of_range_returns_zero():
    dmx = bytes([5, 6])
    assert _channel(dmx, 99) == 0
    assert _channel(dmx, 0) == 0
