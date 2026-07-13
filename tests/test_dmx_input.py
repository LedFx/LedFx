"""Tests for the DMX Input (Art-Net) integration parser and mapping logic."""

import struct
from unittest.mock import MagicMock

from ledfx.integrations.dmx_input import DMXInput, _channel, parse_artdmx


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


def _make_dmx_input(monkeypatch, virtual, stale_timeout=2.0):
    """Build a DMXInput with a fake ledfx/virtual, bypassing all networking.

    Driving `_on_dmx` / `_process` directly (instead of real UDP sockets)
    keeps this test fast and deterministic, and avoids Windows-specific
    asyncio Proactor event-loop UDP delivery jitter that made an end-to-end
    loopback Art-Net harness flaky in manual testing.
    """
    ledfx = MagicMock()
    ledfx.virtuals.get.return_value = virtual
    config = {
        "name": "test",
        "description": "test",
        "bind_address": "127.0.0.1",
        "port": 6454,
        "update_fps": 60,
        "stale_timeout": stale_timeout,
        "hold_last_look": False,
    }
    integration = DMXInput(ledfx, config, False, [])
    mapping = {
        "name": "fixture-under-test",
        "type": "fixture",
        "universe": 0,
        "virtual_id": "virtual-1",
        "channels": {"dimmer": 1, "r": 2, "g": 3, "b": 4},
    }
    integration.add_mapping(mapping)
    return integration


def test_fixture_wash_has_no_threshold_gate(monkeypatch):
    """Wash engages unconditionally once data arrives, tracks live dimmer/RGB
    with no on/off threshold, and dimmer=0 renders black instead of
    reverting to the underlying effect (regression test for the flash bug
    caused by the old threshold gate)."""
    virtual = MagicMock()
    integration = _make_dmx_input(monkeypatch, virtual)

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )

    # First packet only primes the baseline; no wash yet.
    integration._on_dmx(0, bytes([0, 0, 0, 0]))
    integration._process()
    assert virtual.set_dmx_wash.call_count == 0

    # Second packet: dimmer=255, red. Wash must engage immediately (no
    # threshold to cross).
    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([255, 255, 0, 0]))
    integration._process()
    virtual.set_dmx_wash.assert_called_with((255, 0, 0), 1.0)

    # Third packet: dimmer=1 (a low-but-nonzero value some consoles send for
    # "off") should NOT be gated to zero/off — no threshold logic at all.
    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([1, 255, 0, 0]))
    integration._process()
    virtual.set_dmx_wash.assert_called_with((255, 0, 0), 1 / 255.0)

    # Fourth packet: dimmer=0 must render solid black via the dimmer math,
    # while the wash stays *engaged* (no revert/flash back to the effect).
    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([0, 255, 0, 0]))
    integration._process()
    virtual.set_dmx_wash.assert_called_with((255, 0, 0), 0.0)
    virtual.clear_dmx_wash.assert_not_called()


def test_fixture_wash_releases_only_on_stale_stream(monkeypatch):
    """The wash is only released when the DMX stream actually goes stale
    (no packets for stale_timeout seconds), never due to a low/zero dimmer
    value."""
    virtual = MagicMock()
    integration = _make_dmx_input(monkeypatch, virtual, stale_timeout=2.0)

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )

    integration._on_dmx(0, bytes([0, 0, 0, 0]))
    integration._process()  # primes

    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([0, 255, 0, 0]))  # dimmer=0, engages
    integration._process()
    assert virtual.set_dmx_wash.called
    virtual.clear_dmx_wash.assert_not_called()

    # Simulate the stream continuing to be silent (SoundSwitch closed/quit)
    # well past stale_timeout — this is the *only* path that should release.
    fake_time[0] += 3.0
    integration._process()
    virtual.clear_dmx_wash.assert_called_once()


def test_mapping_type_changed_in_place_does_not_crash(monkeypatch):
    """Regression test: editing a mapping's ``type`` in place (same list
    index) at runtime — e.g. via the mapping editor UI, without restarting
    the backend — must not leave stale per-index runtime state that crashes
    the new type's handler.

    Root cause this guards against: each ``_process_*`` handler used to do
    ``self._mapping_state.setdefault(idx, {<its own default key>: ...})``.
    ``setdefault`` only inserts when the *index* is entirely absent from the
    dict — if a different handler already created an entry at that index
    (from the mapping's previous type), the new handler's key was never
    added, and later direct indexing like ``state["wash_on"]`` raised a
    ``KeyError`` on every processing cycle, silently swallowed by
    ``_update_loop``'s catch-all and logged as a warning — so the new
    mapping type appeared to simply do nothing.

    ``_prime_mapping`` seeds all three handlers' keys unconditionally, so
    this bug only manifests once a mapping's universe has already been
    "seen" (SoundSwitch has already been streaming for a while) *before*
    the type edit happens — priming is per-universe, not per-mapping, so an
    existing (previously-seen) universe never re-primes an edited mapping.
    That's the realistic, common case: you edit a mapping's type while DMX
    is already live, not at the very first packet after a cold start.
    """
    virtual = MagicMock()
    integration = _make_dmx_input(monkeypatch, virtual)

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )

    # Simulate the DMX stream having already been live for a while: universe
    # 0 is already "seen", so priming will never run again for it.
    integration._seen_universe.add(0)
    integration._last_packet_time[0] = fake_time[0]

    # Configure the mapping as "color" and process one packet — since the
    # universe is already seen, _process_color creates _mapping_state[0]
    # itself, containing *only* the color handler's key.
    integration._data[0]["type"] = "color"
    integration._data[0]["channels"] = [2, 3, 4]
    integration._on_dmx(0, bytes([0, 10, 20, 30]))
    integration._process()
    assert virtual.set_color_override.called
    assert integration._mapping_state[0] == {
        "last_color": (10, 20, 30),
        "_active_type": "color",
    }

    # Now edit the *same* mapping index's type to "fixture" at runtime,
    # without restarting/re-priming — this is exactly what the frontend's
    # mapping editor does when you change a mapping's type via PUT.
    integration._data[0]["type"] = "fixture"
    integration._data[0]["channels"] = {"dimmer": 1, "r": 2, "g": 3, "b": 4}

    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([255, 255, 0, 0]))
    integration._process()  # must not raise / silently no-op

    virtual.set_dmx_wash.assert_called_with((255, 0, 0), 1.0)


def test_mapping_type_changed_fixture_to_color_releases_wash(monkeypatch):
    """Regression test for the "frozen frame" bug: switching a mapping from
    "fixture" (wash) to "color" (live RGB) in place at runtime, while DMX is
    live, must release the old wash takeover — not just start applying the
    new color override underneath it.

    Root cause this guards against: ``_release_mapping`` was only ever
    called by ``_process`` on the stale-stream/deactivation path, using
    ``mapping.get("type")`` — i.e. the mapping's *current* type. Editing a
    mapping's type in place never went through that path at all, so nothing
    ever called ``clear_dmx_wash()`` for the virtual's stale fixture-wash
    takeover. Since ``Virtual.thread_function``'s render loop gives DMX wash
    render priority over a color override (wash is checked first), the
    virtual would keep painting the wash's last (now frozen/stale) RGB
    value forever, even though a brand new color override was also being
    applied every cycle underneath it — the LED appears completely frozen,
    with no exception anywhere (this is not a crash, so nothing appears in
    the log), even though the color override is "correct" from the DMX
    Input integration's point of view.
    """
    virtual = MagicMock()
    integration = _make_dmx_input(monkeypatch, virtual)

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )

    # Engage the fixture wash first (mapping starts as "fixture", per
    # _make_dmx_input's default config).
    integration._on_dmx(0, bytes([0, 0, 0, 0]))
    integration._process()  # primes

    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([255, 255, 0, 0]))
    integration._process()
    virtual.set_dmx_wash.assert_called_with((255, 0, 0), 1.0)
    virtual.clear_dmx_wash.assert_not_called()

    # Now edit the *same* mapping index's type to "color" at runtime — e.g.
    # via the mapping editor UI — without going through any stale/removal
    # path.
    integration._data[0]["type"] = "color"
    integration._data[0]["channels"] = [2, 3, 4]

    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([0, 10, 20, 30]))
    integration._process()

    # The stale wash takeover must be released so the new color override
    # actually becomes visible instead of being silently masked by it.
    virtual.clear_dmx_wash.assert_called_once()
    virtual.set_color_override.assert_called_with("#0a141e")
