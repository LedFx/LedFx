"""DMX Input bridge integration.

Listens for incoming Art-Net DMX (e.g. from SoundSwitch outputting Art-Net to
127.0.0.1 in parallel with its USB-DMX output) and maps DMX channels onto LedFx
actions:

  * **trigger**  — a button / static-look channel toggles a venue color-override
    pad (edge-detected with hysteresis).
  * **color**    — an RGB fixture recolors a target virtual live, while the
    effect keeps animating.
  * **fixture**  — a dimmer + RGB turn a virtual into a dumb DMX wash fixture
    (solid color × brightness), so an LED run can be programmed in
    SoundSwitch alongside real wash fixtures. The wash is engaged
    unconditionally as soon as its universe is receiving data, and tracks
    live dimmer/RGB continuously (dimmer 0 = solid black, no threshold gate);
    it is only released back to the running effect when the DMX stream
    itself goes stale or the mapping is deactivated.

The incoming Art-Net "signal" is just DMX; no reverse engineering of SoundSwitch
internals is required. SoundSwitch is configured to mirror its USB universe to
Art-Net on the loopback interface.

Mappings are persisted in the integration ``data`` blob (mirroring the QLC+
integration pattern) as a list of dicts. See ``MAPPING_SCHEMA`` for the shape.
"""

import asyncio
import logging
import os
import random
import socket
import struct
import time

import voluptuous as vol

from ledfx.config import save_config
from ledfx.integrations import Integration
from ledfx.venues import VenueManager

_LOGGER = logging.getLogger(__name__)

ARTNET_ID = b"Art-Net\x00"
OPCODE_ARTDMX = 0x5000
OPCODE_ARTPOLL = 0x2000
OPCODE_ARTPOLLREPLY = 0x2100  # other nodes announcing themselves; just noise
ARTNET_MIN_PROTO = 14
ARTNET_PORT = 6454

# TEMP DEBUG ONLY — set LEDFX_DMX_TRACE=1 to log every UDP datagram this
# listener receives (source, opcode, raw bytes) plus per-universe DMX values
# at ~2Hz, for tracing a SoundSwitch → LedFx Art-Net handshake. Not meant to
# be committed/merged; strip before opening/updating the PR.
_TRACE = os.environ.get("LEDFX_DMX_TRACE") == "1"
_trace_last_log: dict[int, float] = {}
_trace_last_nomatch_log: dict[int, float] = {}


def _best_local_ip(bind_address: str) -> str:
    """Return the best routable local IP to advertise in ArtPollReply.

    When bound to 0.0.0.0 we probe the routing table via a throw-away UDP
    socket so we report the IP that remote hosts can actually reach us on.
    """
    if bind_address and bind_address != "0.0.0.0":
        return bind_address
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"


def _build_artpollreply(local_ip: str, port: int = ARTNET_PORT) -> bytes:
    """Build a 239-byte ArtPollReply advertising one DMX output port.

    SoundSwitch (and other Art-Net controllers) broadcast ArtPoll to discover
    nodes.  Without this reply LedFx is invisible to them and they report
    "no device found".

    We advertise a single output port on universe 0 (StNode style).  Once
    SoundSwitch selects this node it sends ArtDMX to our IP regardless of
    which universe/channel is active, so no multi-universe advertising is
    needed.
    """
    pkt = bytearray(239)
    pkt[0:8] = ARTNET_ID
    # OpCode 0x2100 – stored little-endian
    pkt[8] = 0x00
    pkt[9] = 0x21
    # IP address (network byte order / big-endian)
    try:
        pkt[10:14] = socket.inet_aton(local_ip)
    except OSError:
        pkt[10:14] = bytes(4)
    # Port – little-endian
    struct.pack_into("<H", pkt, 14, port)
    # VersInfo – firmware version big-endian; just use 1
    struct.pack_into(">H", pkt, 16, 1)
    # NetSwitch / SubSwitch – universe 0
    pkt[18] = 0
    pkt[19] = 0
    # OemHi / Oem – 0x00 0xFF = unknown/experimental
    pkt[20] = 0x00
    pkt[21] = 0xFF
    # ShortName (18 bytes, null-padded)
    short = b"LedFx DMX Input"
    pkt[26 : 26 + len(short)] = short
    # LongName (64 bytes, null-padded)
    long_n = b"LedFx Art-Net DMX Input Bridge"
    pkt[44 : 44 + len(long_n)] = long_n
    # NodeReport (64 bytes)
    report = b"#0001 [0000] LedFx DMX Input active"
    pkt[108 : 108 + len(report)] = report
    # NumPorts – 1
    pkt[172] = 0
    pkt[173] = 1
    # PortTypes[0] – 0x80 = output port (receives DMX from network → LedFx)
    pkt[174] = 0x80
    # GoodOutput[0] – 0x80 = data being transmitted
    pkt[182] = 0x80
    # SwOut[0] – universe 0
    pkt[190] = 0
    # Style – 0x00 = StNode
    pkt[200] = 0x00
    # BindIp – same as our IP
    try:
        pkt[207:211] = socket.inet_aton(local_ip)
    except OSError:
        pkt[207:211] = bytes(4)
    # BindIndex – 1
    pkt[211] = 1
    # Status2 – 0x08 = DHCP capable (harmless flag)
    pkt[212] = 0x08
    return bytes(pkt)


def parse_artdmx(data: bytes):
    """Strictly parse an ArtDMX packet.

    Returns ``(universe, dmx_bytes)`` or ``None`` if the packet is not a valid
    ArtDMX frame. The DMX length field is honored (not assumed to be 512).
    """
    if len(data) < 18:
        return None
    if data[:8] != ARTNET_ID:
        return None
    # OpCode is little-endian; ArtDMX == 0x5000
    opcode = data[8] | (data[9] << 8)
    if opcode != OPCODE_ARTDMX:
        return None
    # Protocol version is big-endian at bytes 10-11
    proto = (data[10] << 8) | data[11]
    if proto < ARTNET_MIN_PROTO:
        return None
    # Port-Address (universe) is little-endian, 15 bits, at bytes 14-15
    universe = (data[14] | (data[15] << 8)) & 0x7FFF
    # Length is big-endian at bytes 16-17
    length = (data[16] << 8) | data[17]
    dmx = data[18 : 18 + length]
    return universe, bytes(dmx)


class _ArtNetProtocol(asyncio.DatagramProtocol):
    """Minimal UDP protocol that forwards parsed ArtDMX frames upstream.

    Also responds to ArtPoll broadcasts so Art-Net controllers (e.g.
    SoundSwitch) can discover LedFx via the standard node-discovery flow
    instead of requiring a manually entered IP address.
    """

    def __init__(self, on_dmx, local_ip: str, port: int = ARTNET_PORT):
        self._on_dmx = on_dmx
        self._reply = _build_artpollreply(local_ip, port)
        self._transport = None

    def connection_made(self, transport):
        self._transport = transport

    def datagram_received(self, data, addr):
        if len(data) < 10 or data[:8] != ARTNET_ID:
            if _TRACE:
                _LOGGER.info(
                    "DMX Input TRACE: non-Art-Net UDP from %s (%d bytes): %s",
                    addr[0],
                    len(data),
                    data[:16].hex(),
                )
            return
        opcode = data[8] | (data[9] << 8)
        if _TRACE and opcode not in (
            OPCODE_ARTPOLL,
            OPCODE_ARTDMX,
            OPCODE_ARTPOLLREPLY,
        ):
            _LOGGER.info(
                "DMX Input TRACE: unhandled Art-Net opcode 0x%04x from %s",
                opcode,
                addr[0],
            )
        if opcode == OPCODE_ARTPOLL:
            # Reply directly to the controller that asked
            if self._transport is not None:
                self._transport.sendto(self._reply, (addr[0], ARTNET_PORT))
                _LOGGER.info("DMX Input: ArtPoll from %s → replied", addr[0])
        elif opcode == OPCODE_ARTDMX:
            parsed = parse_artdmx(data)
            if parsed is None:
                if _TRACE:
                    _LOGGER.info(
                        "DMX Input TRACE: malformed ArtDMX from %s (%d bytes)",
                        addr[0],
                        len(data),
                    )
                return
            universe, dmx = parsed
            if _TRACE:
                now = time.monotonic()
                if now - _trace_last_log.get(universe, 0) > 0.5:
                    _trace_last_log[universe] = now
                    _LOGGER.info(
                        "DMX Input TRACE: ArtDMX from %s universe=%d len=%d "
                        "first10=%s",
                        addr[0],
                        universe,
                        len(dmx),
                        list(dmx[:10]),
                    )
            self._on_dmx(universe, dmx)

    def error_received(self, exc):
        _LOGGER.debug("Art-Net socket error: %s", exc)


def _channel(dmx: bytes, ch: int) -> int:
    """Return the value of 1-based DMX channel *ch* (0 if out of range)."""
    idx = ch - 1
    if 0 <= idx < len(dmx):
        return dmx[idx]
    return 0


def compute_dmx_mapped(ledfx):
    """Cross-reference every ``dmx_input`` integration's mappings to find
    which virtuals and venues are currently targeted by DMX Input.

    Used by the virtuals/venues REST endpoints to compute a ``dmx_mapped``
    flag per item, so the frontend can only render pause controls where DMX
    actually applies.

    Returns:
        (mapped_virtual_ids, mapped_venue_ids): a tuple of sets. A venue is
        included if any mapping targets it directly by ``venue_id``, or if
        it owns a virtual targeted directly by ``virtual_id``. A virtual is
        included if any mapping targets it directly, or targets a venue it
        belongs to.
    """
    mapped_virtual_ids = set()
    mapped_venue_ids = set()

    integrations = getattr(ledfx, "integrations", None)
    if integrations is not None:
        for integration in integrations.values():
            if getattr(integration, "type", None) != "dmx_input":
                continue
            get_mappings = getattr(integration, "get_mappings", None)
            if get_mappings is None:
                continue
            for mapping in get_mappings():
                vid = mapping.get("virtual_id")
                if vid:
                    mapped_virtual_ids.add(vid)
                venue_id = mapping.get("venue_id")
                if venue_id:
                    mapped_venue_ids.add(venue_id)

    # Expand venue-targeted mappings to their member virtuals, and mark a
    # venue as mapped if it owns a directly-targeted virtual.
    venues = getattr(ledfx, "venues", None)
    if venues is not None:
        for venue_id, cfg in venues.list_venues().items():
            virtual_ids = cfg.get("virtual_ids", [])
            if venue_id in mapped_venue_ids:
                mapped_virtual_ids.update(virtual_ids)
            elif mapped_virtual_ids.intersection(virtual_ids):
                mapped_venue_ids.add(venue_id)

    return mapped_virtual_ids, mapped_venue_ids


class DMXInput(Integration):
    """Bridge incoming Art-Net DMX onto LedFx venue overrides and virtuals."""

    beta = False

    NAME = "DMX Input"
    DESCRIPTION = (
        "Control LedFx from a DMX source (e.g. SoundSwitch via Art-Net): "
        "venue color overrides, live color passthrough, and DMX wash fixtures."
    )

    CONFIG_SCHEMA = vol.Schema(
        {
            vol.Required(
                "name",
                description="Name of this integration instance",
                default="DMX Input",
            ): str,
            vol.Required(
                "description",
                description="Description of this integration",
                default="Art-Net DMX input bridge",
            ): str,
            vol.Required(
                "bind_address",
                description="Local address to listen on. Use 0.0.0.0 to accept Art-Net "
                "from any machine on the network (e.g. SoundSwitch on a separate PC). "
                "Use 127.0.0.1 to accept only from the same machine.",
                default="0.0.0.0",
            ): str,
            vol.Required(
                "port",
                description="Art-Net UDP port",
                default=6454,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=65535)),
            vol.Optional(
                "update_fps",
                description="How often incoming DMX is applied to LedFx",
                default=60,
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=120)),
            vol.Optional(
                "stale_timeout",
                description="Seconds without DMX before owned overrides are "
                "released (0 disables)",
                default=2.0,
            ): vol.All(vol.Coerce(float), vol.Range(min=0.0, max=60.0)),
            vol.Optional(
                "hold_last_look",
                description="Keep the last look when the DMX stream stops "
                "instead of releasing it",
                default=False,
            ): bool,
        }
    )

    def __init__(self, ledfx, config, active, data):
        super().__init__(ledfx, config, active, data)

        self._ledfx = ledfx
        self._config = config
        # `data` is the integration's persisted state. Historically this was
        # just the list of channel mappings; it is now a dict of
        # ``{"mappings": [...], "paused": bool}`` so the global pause flag
        # can survive restarts alongside the mappings. Old-format (bare
        # list) configs are transparently migrated on load.
        if isinstance(data, dict):
            self._data = data.get("mappings", [])
            self._paused = bool(data.get("paused", False))
        else:
            self._data = data if isinstance(data, list) else []
            self._paused = False

        self._transport = None
        self._protocol = None
        self._update_task = None

        # Latest DMX state per universe and when it last arrived
        self._latest_dmx: dict[int, bytes] = {}
        self._last_packet_time: dict[int, float] = {}
        self._seen_universe: set[int] = set()

        # Per-mapping runtime state, keyed by mapping index
        self._mapping_state: dict[int, dict] = {}

        # Ownership: which mapping index currently owns each venue override
        self._venue_override_owner: dict[str, int] = {}
        # Virtuals we currently hold in wash / color-passthrough mode
        self._owned_washes: set[str] = set()
        self._owned_color: set[str] = set()

    # ------------------------------------------------------------------
    # Mapping management (persisted in self._data)
    # ------------------------------------------------------------------

    @property
    def data(self):
        """Persisted state: mapping list plus the global pause flag."""
        return {"mappings": self._data, "paused": self._paused}

    def get_mappings(self):
        return self._data

    def add_mapping(self, mapping: dict):
        self._data.append(mapping)

    def delete_mapping(self, index: int):
        if 0 <= index < len(self._data):
            del self._data[index]
            self._mapping_state.pop(index, None)

    def get_live_dmx(self) -> dict:
        """Return the latest DMX values per universe (for monitor / learn UI)."""
        return {
            str(universe): list(dmx)
            for universe, dmx in self._latest_dmx.items()
        }

    @property
    def paused(self) -> bool:
        return self._paused

    def set_paused(self, paused: bool):
        """Globally mute (or unmute) this integration's DMX takeover.

        The Art-Net UDP listener keeps running and still replies to
        ArtPoll (so SoundSwitch stays "connected") — pausing only stops
        mapping dispatch. Pausing releases every mapping's currently owned
        wash/color override/venue-trigger immediately, so all target
        virtuals revert right away instead of waiting for the next
        stale-stream timeout. Unpausing needs no special action: the next
        DMX tick re-engages mappings naturally.
        """
        self._paused = bool(paused)
        if self._paused:
            self._release_all()
        self._persist()

    def _persist(self):
        """Save this integration's persisted state (mirrors the API's
        ``_persist`` helper in ``ledfx.api.integration_dmx_input``), so
        toggling pause is instant and durable without triggering a
        reconnect (unlike a ``CONFIG_SCHEMA`` change)."""
        for integration in self._ledfx.config.get("integrations", []):
            if integration["id"] == self.id:
                integration["data"] = self.data
                break
        save_config(
            config=self._ledfx.config,
            config_dir=self._ledfx.config_dir,
        )

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(self):
        bind = self._config["bind_address"]
        port = self._config["port"]
        local_ip = _best_local_ip(bind)
        try:
            (
                self._transport,
                self._protocol,
            ) = await self._ledfx.loop.create_datagram_endpoint(
                lambda: _ArtNetProtocol(self._on_dmx, local_ip, port),
                local_addr=(bind, port),
                allow_broadcast=True,
            )
        except OSError as e:
            _LOGGER.error(
                "DMX Input: failed to bind Art-Net listener on %s:%s (%s). "
                "Is another Art-Net node or LedFx Art-Net output using the port?",
                bind,
                port,
                e,
            )
            await super().disconnect()
            return

        self._update_task = self._ledfx.loop.create_task(self._update_loop())
        await super().connect(
            f"DMX Input listening for Art-Net on {local_ip}:{port} "
            f"(bind {bind}) — ArtPoll discovery enabled"
        )

    async def disconnect(self):
        if self._update_task is not None:
            self._update_task.cancel()
            self._update_task = None
        if self._transport is not None:
            self._transport.close()
            self._transport = None
            self._protocol = None
        # Release everything this integration owns
        self._release_all()
        await super().disconnect("DMX Input stopped")

    def on_shutdown(self):
        self._release_all()

    # ------------------------------------------------------------------
    # Art-Net intake (runs on the loop thread, kept tiny)
    # ------------------------------------------------------------------

    def _on_dmx(self, universe: int, dmx: bytes):
        self._latest_dmx[universe] = dmx
        self._last_packet_time[universe] = time.monotonic()

    # ------------------------------------------------------------------
    # Coalesced processing loop
    # ------------------------------------------------------------------

    async def _update_loop(self):
        try:
            while True:
                interval = 1.0 / max(1, self._config.get("update_fps", 60))
                await asyncio.sleep(interval)
                try:
                    self._process()
                except Exception as e:  # never let the loop die
                    _LOGGER.warning("DMX Input processing error: %s", e)
        except asyncio.CancelledError:
            pass

    def _process(self):
        # Global pause: the UDP listener and update loop keep running (so
        # ArtPoll replies and DMX intake are unaffected and SoundSwitch
        # stays "connected"), but no mapping is dispatched — nothing is
        # applied to any virtual/venue while paused.
        if self._paused:
            return

        now = time.monotonic()
        stale_timeout = self._config.get("stale_timeout", 2.0)
        hold = self._config.get("hold_last_look", False)

        for idx, mapping in enumerate(self._data):
            if not mapping.get("active", True):
                continue

            universe = int(mapping.get("universe", 0))
            dmx = self._latest_dmx.get(universe)
            if dmx is None:
                if _TRACE and self._latest_dmx:
                    if now - _trace_last_nomatch_log.get(idx, 0) > 2.0:
                        _trace_last_nomatch_log[idx] = now
                        _LOGGER.info(
                            "DMX Input TRACE: mapping '%s' wants universe %d "
                            "but only received universe(s) %s so far — check "
                            "SoundSwitch's universe setting matches the "
                            "mapping.",
                            mapping.get("name", idx),
                            universe,
                            sorted(self._latest_dmx.keys()),
                        )
                continue

            # On the first packet for a universe, prime baselines so a channel
            # that is already high at startup does not spuriously fire.
            if universe not in self._seen_universe:
                self._seen_universe.add(universe)
                self._prime_mapping(idx, mapping, dmx)
                continue

            # Stale-stream handling: release owned looks if the source stopped.
            age = now - self._last_packet_time.get(universe, 0)
            if stale_timeout > 0 and not hold and age > stale_timeout:
                self._release_mapping(idx, mapping)
                continue

            mtype = mapping.get("type")

            # If this mapping's type was edited in place at runtime (same
            # index, e.g. "fixture" -> "color" via the UI), release whatever
            # the *previous* type owned (wash takeover, color override,
            # triggered venue pad) before dispatching to the new type's
            # handler. Without this, e.g. a virtual's DMX wash takeover
            # (which wins render priority over a color override) would stay
            # engaged forever with its last stale value, since nothing else
            # ever calls clear_dmx_wash() for it once the mapping stops
            # being processed as "fixture" — the LED appears permanently
            # frozen on the last wash frame even though a new color override
            # is being applied underneath it.
            prev_state = self._mapping_state.get(idx)
            prev_type = prev_state.get("_active_type") if prev_state else None
            if prev_type is not None and prev_type != mtype:
                self._release_mapping(idx, mapping, mtype=prev_type)
            # Record unconditionally (creating the state dict on the very
            # first cycle if needed) so a type change is detected even if
            # this is the mapping's first-ever processed cycle immediately
            # followed by a type edit before the next cycle.
            self._mapping_state.setdefault(idx, {})["_active_type"] = mtype

            if mtype == "trigger":
                self._process_trigger(idx, mapping, dmx)
            elif mtype == "color":
                self._process_color(idx, mapping, dmx)
            elif mtype == "fixture":
                self._process_fixture(idx, mapping, dmx)

    # ------------------------------------------------------------------
    # Per-type handlers
    # ------------------------------------------------------------------

    def _prime_mapping(self, idx, mapping, dmx):
        """Record an initial 'off' baseline so startup does not auto-fire."""
        state = self._mapping_state.setdefault(
            idx, {"triggered": False, "last_color": None, "wash_on": False}
        )
        # Seed the active type so the first real _process() cycle after
        # priming has a baseline to detect an in-place type change against.
        state.setdefault("_active_type", mapping.get("type"))

    def _process_trigger(self, idx, mapping, dmx):
        # Use setdefault on the specific key, not just the container: if this
        # index previously held state for a *different* mapping type (e.g.
        # the mapping's type was edited in place from "color"/"fixture" to
        # "trigger" without restarting), the dict already exists but lacks
        # this handler's key — a plain setdefault(idx, {...}) would silently
        # leave it missing and this handler would KeyError forever.
        state = self._mapping_state.setdefault(idx, {})
        state.setdefault("triggered", False)
        ch = int(mapping.get("channels", [1])[0])
        value = _channel(dmx, ch)
        on_t = int(mapping.get("on_threshold", 128))
        off_t = int(mapping.get("off_threshold", 96))
        venue_id = mapping.get("venue_id")
        pad_index = mapping.get("pad_index")
        if venue_id is None or pad_index is None:
            return

        if self._venues().is_paused(venue_id):
            # Venue paused: stop tracking edges and drop ownership until
            # unpaused (the venue's own pause already cleared its override).
            state["triggered"] = False
            self._venue_override_owner.pop(venue_id, None)
            return

        if state["triggered"]:
            if value <= off_t:
                state["triggered"] = False
                # Only clear if we still own this venue's override
                if self._venue_override_owner.get(venue_id) == idx:
                    self._clear_venue_pad(venue_id)
                    self._venue_override_owner.pop(venue_id, None)
        else:
            if value >= on_t:
                state["triggered"] = True
                try:
                    self._activate_venue_pad(venue_id, int(pad_index))
                    self._venue_override_owner[venue_id] = idx
                    _LOGGER.info(
                        "DMX Input: trigger '%s' activated override pad %s on venue '%s'",
                        mapping.get("name", idx),
                        pad_index,
                        venue_id,
                    )
                except Exception as e:
                    _LOGGER.warning("DMX Input activate_override: %s", e)

    def _process_color(self, idx, mapping, dmx):
        # See _process_trigger for why we setdefault the key, not just the
        # container dict — guards against a mapping's type having been
        # changed in place at runtime.
        state = self._mapping_state.setdefault(idx, {})
        state.setdefault("last_color", None)
        chans = mapping.get("channels", [1, 2, 3])
        r = _channel(dmx, int(chans[0]))
        g = _channel(dmx, int(chans[1]))
        b = _channel(dmx, int(chans[2]))
        rgb = (r, g, b)
        if rgb == state["last_color"]:
            return
        state["last_color"] = rgb
        hex_color = f"#{r:02x}{g:02x}{b:02x}"
        for v in self._targets(mapping):
            try:
                v.set_color_override(hex_color)
                self._owned_color.add(v.id)
            except Exception as e:
                _LOGGER.warning("DMX Input set_color_override: %s", e)

    def _process_fixture(self, idx, mapping, dmx):
        """Drive a virtual as a continuous DMX wash fixture.

        As soon as this mapping's universe is receiving data, the target
        virtual(s) are engaged as a wash fixture and driven continuously by
        the live dimmer/RGB values on every packet — a dimmer of 0 naturally
        renders solid black (rgb * 0). There is no on/off threshold gate:
        the wash is engaged unconditionally while the DMX stream is live, and
        only released back to the running effect via the stale-stream
        timeout (SoundSwitch stops sending entirely) or the mapping being
        deactivated/removed, handled by ``_release_mapping``. This avoids a
        bright "flash" of the underlying effect whenever the operator dims a
        fixture down to (near) zero.

        Optional ``strobe_probability`` (0.0-1.0, default 1.0): real DMX
        fixtures each strobe on their own independent onboard oscillator, so
        multiple real fixtures visibly drift out of sync with each other even
        when fed identical DMX — whereas LedFx mirrors the incoming dimmer
        frame-perfectly, looking artificially "locked". Setting this below
        1.0 draws one Bernoulli trial per detected strobe *pulse* (edge-
        detected: dimmer rising from 0), forcing that pulse to render black
        instead of firing with probability ``1 - strobe_probability``. The
        default of 1.0 renders every pulse (today's exact behaviour, no
        regression for anyone who leaves the setting untouched).
        """
        state = self._mapping_state.setdefault(idx, {})
        # See _process_trigger for why we setdefault the key, not just the
        # container dict — guards against a mapping's type having been
        # changed in place at runtime.
        state.setdefault("wash_on", False)
        state.setdefault("strobe_pulse_on", False)
        state.setdefault("strobe_pulse_render", True)
        chans = mapping.get("channels", {})
        # channels may be a dict {dimmer,r,g,b} or a 4-list in that order
        # (a legacy "mode" key, if still present in old saved mappings, is
        # ignored — the fixture wash is no longer gated by a threshold).
        if isinstance(chans, dict):
            dim_ch = int(chans.get("dimmer", 1))
            r_ch = int(chans.get("r", 2))
            g_ch = int(chans.get("g", 3))
            b_ch = int(chans.get("b", 4))
        else:
            dim_ch, r_ch, g_ch, b_ch = (list(chans) + [1, 2, 3, 4])[:4]

        targets = list(self._targets(mapping))
        dimmer = _channel(dmx, dim_ch) / 255.0
        rgb = (
            _channel(dmx, r_ch),
            _channel(dmx, g_ch),
            _channel(dmx, b_ch),
        )

        strobe_probability = float(mapping.get("strobe_probability", 1.0))
        strobe_probability = max(0.0, min(1.0, strobe_probability))
        if strobe_probability < 1.0:
            pulse_on = dimmer > 0.0
            if pulse_on and not state["strobe_pulse_on"]:
                # Rising edge of a new strobe pulse — roll once and hold the
                # decision until the pulse's falling edge, so a single
                # intended flash isn't chopped into flicker by re-rolling
                # every frame.
                state["strobe_pulse_render"] = (
                    random.random() < strobe_probability
                )
            state["strobe_pulse_on"] = pulse_on
            if pulse_on and not state["strobe_pulse_render"]:
                dimmer = 0.0

        if not state["wash_on"]:
            state["wash_on"] = True
            _LOGGER.info(
                "DMX Input: fixture '%s' wash ENGAGED on %d virtual(s)",
                mapping.get("name", idx),
                len(targets),
            )

        for v in targets:
            try:
                v.set_dmx_wash(rgb, dimmer)
                self._owned_washes.add(v.id)
            except Exception as e:
                _LOGGER.warning("DMX Input set_dmx_wash: %s", e)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _venues(self) -> VenueManager:
        if not hasattr(self._ledfx, "venues"):
            self._ledfx.venues = VenueManager(self._ledfx)
        return self._ledfx.venues

    def _targets(self, mapping):
        """Yield target virtuals for a color/fixture mapping.

        A mapping targets either a single ``virtual_id`` or every virtual in a
        ``venue_id``. Applies global -> venue -> device pause precedence:
        a globally paused integration yields nothing at all, a paused venue
        yields nothing for venue-targeted mappings, and an individually
        paused virtual is skipped regardless of how it was targeted. Actual
        release of any override this virtual currently owns happens the
        instant the relevant pause flag is set (see ``set_paused`` here,
        ``VenueManager.set_paused``, and ``Virtual.set_dmx_paused``) — this
        is only responsible for not re-engaging a paused target.
        """
        if self._paused:
            return

        vid = mapping.get("virtual_id")
        if vid:
            v = self._ledfx.virtuals.get(vid)
            if v is not None and not v.is_dmx_paused():
                yield v
            return
        venue_id = mapping.get("venue_id")
        if venue_id:
            if self._venues().is_paused(venue_id):
                return
            cfg = self._venues().get(venue_id)
            if not cfg:
                return
            for v_id in cfg.get("virtual_ids", []):
                v = self._ledfx.virtuals.get(v_id)
                if v is not None and not v.is_dmx_paused():
                    yield v

    def _activate_venue_pad(self, venue_id, pad_index):
        """Apply a venue color pad, honoring per-device DMX pause.

        Mirrors ``VenueManager.activate_override`` but routes virtual
        selection through ``_targets`` so a device-paused virtual in the
        venue is skipped even though the trigger targets the whole venue.
        """
        cfg = self._venues().get(venue_id)
        if not cfg:
            raise KeyError(f"Venue '{venue_id}' not found")

        pads = cfg["color_pads"]["pads"]
        if pad_index < 0 or pad_index >= len(pads):
            raise IndexError(
                f"Pad index {pad_index} out of range (0-{len(pads) - 1})"
            )

        pad = pads[pad_index]
        color_or_gradient = pad.get("gradient") or pad.get("color", "#ffffff")

        for v in self._targets({"venue_id": venue_id}):
            v.set_color_override(color_or_gradient)

    def _clear_venue_pad(self, venue_id):
        try:
            self._venues().clear_override(venue_id)
        except Exception as e:
            _LOGGER.warning("DMX Input clear_override: %s", e)

    def _release_mapping(self, idx, mapping, mtype=None):
        """Release whatever a single mapping currently owns.

        Args:
            mtype: release ownership for this type instead of the mapping's
                current ``type``. Used when a mapping's type was edited in
                place at runtime — we must release what the *previous* type
                owned (e.g. a fixture wash takeover), not what the new type
                would own, since the new type hasn't engaged anything yet.
        """
        state = self._mapping_state.get(idx)
        if not state:
            return
        if mtype is None:
            mtype = mapping.get("type")
        if mtype == "trigger" and state.get("triggered"):
            state["triggered"] = False
            venue_id = mapping.get("venue_id")
            if venue_id and self._venue_override_owner.get(venue_id) == idx:
                self._clear_venue_pad(venue_id)
                self._venue_override_owner.pop(venue_id, None)
        elif mtype == "color" and state.get("last_color") is not None:
            state["last_color"] = None
            for v in self._targets(mapping):
                try:
                    v.clear_color_override()
                except Exception:
                    pass
                self._owned_color.discard(v.id)
        elif mtype == "fixture" and state.get("wash_on"):
            state["wash_on"] = False
            _LOGGER.info(
                "DMX Input: fixture '%s' wash RELEASED (stale/deactivated)",
                mapping.get("name", idx),
            )
            for v in self._targets(mapping):
                try:
                    v.clear_dmx_wash()
                except Exception:
                    pass
                self._owned_washes.discard(v.id)

    def _release_all(self):
        """Release every override / takeover this integration owns."""
        for venue_id in list(self._venue_override_owner.keys()):
            try:
                self._venues().clear_override(venue_id)
            except Exception:
                pass
        self._venue_override_owner.clear()

        for vid in list(self._owned_color):
            v = self._ledfx.virtuals.get(vid)
            if v is not None:
                try:
                    v.clear_color_override()
                except Exception:
                    pass
        self._owned_color.clear()

        for vid in list(self._owned_washes):
            v = self._ledfx.virtuals.get(vid)
            if v is not None:
                try:
                    v.clear_dmx_wash()
                except Exception:
                    pass
        self._owned_washes.clear()

        self._mapping_state.clear()
