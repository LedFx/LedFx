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
    # MagicMock()'s default attributes are truthy, so an un-configured
    # `is_dmx_paused()` would look "paused" to `_targets` and silently
    # filter the virtual out. Default every fake virtual to unpaused.
    virtual.is_dmx_paused.return_value = False
    # A real (empty) integrations list so `set_paused`'s `_persist()` can
    # iterate/find this integration's config entry without special-casing
    # MagicMock defaults; `save_config` itself is stubbed out below.
    ledfx.config = {"integrations": []}
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.save_config", lambda **kwargs: None
    )
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


def _base_config(stale_timeout=2.0):
    return {
        "name": "test",
        "description": "test",
        "bind_address": "127.0.0.1",
        "port": 6454,
        "update_fps": 60,
        "stale_timeout": stale_timeout,
        "hold_last_look": False,
    }


def _make_venue_mapped_dmx_input(
    monkeypatch, virtuals_by_id, venue_id="venue-1"
):
    """Build a DMXInput whose single fixture mapping targets a venue (rather
    than a single virtual_id), with a mocked VenueManager, so venue/device
    pause precedence can be exercised without real venue persistence."""
    ledfx = MagicMock()
    ledfx.virtuals.get.side_effect = lambda vid: virtuals_by_id.get(vid)
    ledfx.config = {"integrations": []}
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.save_config", lambda **kwargs: None
    )

    venue_mgr = MagicMock()
    venue_mgr.get.return_value = {"virtual_ids": list(virtuals_by_id.keys())}
    venue_mgr.is_paused.return_value = False
    ledfx.venues = venue_mgr

    for v in virtuals_by_id.values():
        v.is_dmx_paused.return_value = False

    integration = DMXInput(ledfx, _base_config(), False, [])
    mapping = {
        "name": "venue-fixture",
        "type": "fixture",
        "universe": 0,
        "venue_id": venue_id,
        "channels": {"dimmer": 1, "r": 2, "g": 3, "b": 4},
    }
    integration.add_mapping(mapping)
    return integration, venue_mgr


def test_global_pause_releases_wash_immediately_and_resumes(monkeypatch):
    """Global pause instantly releases an engaged wash (no waiting for the
    next stale-stream tick), and stops any further reapplication while
    paused. Unpausing needs no special action — the next `_process()` with
    live DMX still flowing simply re-engages."""
    virtual = MagicMock()
    integration = _make_dmx_input(monkeypatch, virtual)

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )

    integration._on_dmx(0, bytes([0, 0, 0, 0]))
    integration._process()  # primes

    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([255, 255, 0, 0]))
    integration._process()
    assert virtual.set_dmx_wash.called
    assert integration.paused is False

    # Pausing releases the wash immediately.
    integration.set_paused(True)
    virtual.clear_dmx_wash.assert_called_once()
    assert integration.paused is True

    # Live DMX keeps flowing (the listener/loop are unaffected by pause),
    # but nothing gets applied while paused.
    virtual.set_dmx_wash.reset_mock()
    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([128, 100, 100, 100]))
    integration._process()
    virtual.set_dmx_wash.assert_not_called()

    # Unpausing needs no special action: the very next tick re-engages.
    integration.set_paused(False)
    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([255, 10, 20, 30]))
    integration._process()
    virtual.set_dmx_wash.assert_called_with((10, 20, 30), 1.0)


def test_venue_pause_stops_mapped_virtuals_from_receiving_washes(monkeypatch):
    """A paused venue must stop a venue-targeted mapping from reapplying to
    any of its member virtuals."""
    v1, v2 = MagicMock(), MagicMock()
    integration, venue_mgr = _make_venue_mapped_dmx_input(
        monkeypatch, {"v1": v1, "v2": v2}
    )

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )

    integration._on_dmx(0, bytes([0, 0, 0, 0]))
    integration._process()  # primes

    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([255, 255, 0, 0]))
    integration._process()
    assert v1.set_dmx_wash.called
    assert v2.set_dmx_wash.called

    # Simulate the venue becoming paused (VenueManager.set_paused itself
    # clears the color-pad override — see test_venues.py — and reports
    # is_paused()=True from then on).
    venue_mgr.is_paused.return_value = True
    v1.set_dmx_wash.reset_mock()
    v2.set_dmx_wash.reset_mock()

    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([128, 10, 10, 10]))
    integration._process()
    v1.set_dmx_wash.assert_not_called()
    v2.set_dmx_wash.assert_not_called()


def test_device_pause_releases_only_that_virtual(monkeypatch):
    """Pausing one virtual (of two sharing a venue-targeted mapping) must
    only stop that one from receiving washes, leaving the other engaged."""
    v1, v2 = MagicMock(), MagicMock()
    integration, _venue_mgr = _make_venue_mapped_dmx_input(
        monkeypatch, {"v1": v1, "v2": v2}
    )

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )

    integration._on_dmx(0, bytes([0, 0, 0, 0]))
    integration._process()  # primes

    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([255, 255, 0, 0]))
    integration._process()
    assert v1.set_dmx_wash.called
    assert v2.set_dmx_wash.called

    # Pause v1 at the device level only.
    v1.is_dmx_paused.return_value = True
    v1.set_dmx_wash.reset_mock()
    v2.set_dmx_wash.reset_mock()

    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([200, 5, 6, 7]))
    integration._process()
    v1.set_dmx_wash.assert_not_called()
    v2.set_dmx_wash.assert_called_with((5, 6, 7), 200 / 255.0)


def test_pause_precedence_global_wins_over_unpaused_venue_and_device(
    monkeypatch,
):
    """Global pause must block dispatch even when the venue and device are
    both unpaused."""
    v1 = MagicMock()
    integration, venue_mgr = _make_venue_mapped_dmx_input(
        monkeypatch, {"v1": v1}
    )
    venue_mgr.is_paused.return_value = False  # venue unpaused
    v1.is_dmx_paused.return_value = False  # device unpaused

    integration.set_paused(True)  # global pause engaged

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )
    integration._on_dmx(0, bytes([0, 0, 0, 0]))
    integration._process()

    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([255, 255, 0, 0]))
    integration._process()
    v1.set_dmx_wash.assert_not_called()


def test_pause_precedence_venue_wins_over_unpaused_device(monkeypatch):
    """A paused venue must block dispatch to a member virtual even when
    that virtual's own device-level pause flag is False."""
    v1 = MagicMock()
    integration, venue_mgr = _make_venue_mapped_dmx_input(
        monkeypatch, {"v1": v1}
    )
    venue_mgr.is_paused.return_value = True  # venue paused
    v1.is_dmx_paused.return_value = False  # device unpaused

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )
    integration._on_dmx(0, bytes([0, 0, 0, 0]))
    integration._process()

    fake_time[0] += 0.05
    integration._on_dmx(0, bytes([255, 255, 0, 0]))
    integration._process()
    v1.set_dmx_wash.assert_not_called()


def test_fixture_wash_default_strobe_probability_renders_every_pulse(
    monkeypatch,
):
    """Default ``strobe_probability`` (1.0, or unset) must render every
    single strobe pulse exactly like today — no regression for anyone who
    never touches the new setting."""
    virtual = MagicMock()
    integration = _make_dmx_input(monkeypatch, virtual)

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )
    # Force every Bernoulli trial to "fail" if it were ever drawn — proves
    # the strobe_probability==1.0 fast-path skips rolling entirely.
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.random.random", lambda: 0.999
    )

    integration._on_dmx(0, bytes([0, 0, 0, 0]))
    integration._process()  # primes

    for _ in range(5):
        fake_time[0] += 0.02
        integration._on_dmx(0, bytes([255, 255, 0, 0]))  # pulse on
        integration._process()
        virtual.set_dmx_wash.assert_called_with((255, 0, 0), 1.0)

        fake_time[0] += 0.02
        integration._on_dmx(0, bytes([0, 255, 0, 0]))  # pulse off
        integration._process()
        virtual.set_dmx_wash.assert_called_with((255, 0, 0), 0.0)


def test_fixture_wash_strobe_probability_suppresses_failed_pulses(
    monkeypatch,
):
    """With strobe_probability < 1.0, a pulse whose single Bernoulli trial
    "fails" must render fully black (dimmer forced to 0) for that pulse's
    entire duration, while a pulse that "succeeds" renders normally — and
    the decision must be drawn once per rising edge, not re-rolled every
    frame within the same pulse."""
    virtual = MagicMock()
    integration = _make_dmx_input(monkeypatch, virtual)
    integration._data[0]["strobe_probability"] = 0.5

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )

    integration._on_dmx(0, bytes([0, 0, 0, 0]))
    integration._process()  # primes

    # First pulse: rig the trial to "fail" (0.9 >= 0.5).
    rolls = iter([0.9, 0.1])
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.random.random", lambda: next(rolls)
    )

    fake_time[0] += 0.02
    integration._on_dmx(0, bytes([255, 255, 0, 0]))  # rising edge, rolls 0.9
    integration._process()
    virtual.set_dmx_wash.assert_called_with((255, 0, 0), 0.0)

    # Still within the same pulse (dimmer still nonzero) — must stay
    # suppressed without re-rolling, even though the next roll (0.1) would
    # have succeeded.
    fake_time[0] += 0.02
    integration._on_dmx(0, bytes([200, 255, 0, 0]))
    integration._process()
    virtual.set_dmx_wash.assert_called_with((255, 0, 0), 0.0)

    # Falling edge — pulse ends.
    fake_time[0] += 0.02
    integration._on_dmx(0, bytes([0, 255, 0, 0]))
    integration._process()
    virtual.set_dmx_wash.assert_called_with((255, 0, 0), 0.0)

    # Second pulse: rolls 0.1 (succeeds, 0.1 < 0.5) — must render normally.
    fake_time[0] += 0.02
    integration._on_dmx(0, bytes([255, 255, 0, 0]))  # rising edge, rolls 0.1
    integration._process()
    virtual.set_dmx_wash.assert_called_with((255, 0, 0), 1.0)


def test_mapping_type_cache_field_round_trips_untouched(monkeypatch):
    """An arbitrary ``_type_field_cache`` key (used by the frontend mapping
    editor to remember each type's last-entered field values across type
    switches, per-mapping) must survive add_mapping/get_mappings untouched,
    and must never be interpreted by any of the ``_process_*`` handlers —
    it is pure frontend-managed UI state that happens to round-trip through
    the backend's unvalidated mapping dicts."""
    virtual = MagicMock()
    integration = _make_dmx_input(monkeypatch, virtual)
    integration._data[0]["_type_field_cache"] = {
        "color": {"channels": [5, 6, 7]},
        "trigger": {"on_threshold": 200, "off_threshold": 150},
    }

    fake_time = [1000.0]
    monkeypatch.setattr(
        "ledfx.integrations.dmx_input.time.monotonic", lambda: fake_time[0]
    )

    integration._on_dmx(0, bytes([0, 0, 0, 0]))
    integration._process()  # primes
    fake_time[0] += 0.02
    integration._on_dmx(0, bytes([255, 255, 0, 0]))
    integration._process()  # normal fixture-wash processing, unaffected

    mappings = integration.get_mappings()
    assert mappings[0]["_type_field_cache"] == {
        "color": {"channels": [5, 6, 7]},
        "trigger": {"on_threshold": 200, "off_threshold": 150},
    }
    virtual.set_dmx_wash.assert_called_with((255, 0, 0), 1.0)
