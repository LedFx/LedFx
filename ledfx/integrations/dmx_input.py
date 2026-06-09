"""DMX Input bridge integration.

Listens for incoming Art-Net DMX (e.g. from SoundSwitch outputting Art-Net to
127.0.0.1 in parallel with its USB-DMX output) and maps DMX channels onto LedFx
actions:

  * **trigger**  — a button / static-look channel toggles a venue color-override
    pad (edge-detected with hysteresis).
  * **color**    — an RGB fixture recolors a target virtual live, while the
    effect keeps animating.
  * **fixture**  — a mode-toggle + dimmer + RGB turn a virtual into a dumb DMX
    wash fixture (solid color × brightness), so an LED run can be programmed in
    SoundSwitch alongside real wash fixtures. Toggling off reveals the effect.

The incoming Art-Net "signal" is just DMX; no reverse engineering of SoundSwitch
internals is required. SoundSwitch is configured to mirror its USB universe to
Art-Net on the loopback interface.

Mappings are persisted in the integration ``data`` blob (mirroring the QLC+
integration pattern) as a list of dicts. See ``MAPPING_SCHEMA`` for the shape.
"""

import asyncio
import logging
import socket
import struct
import time

import voluptuous as vol

from ledfx.integrations import Integration
from ledfx.venues import VenueManager

_LOGGER = logging.getLogger(__name__)

ARTNET_ID = b"Art-Net\x00"
OPCODE_ARTDMX = 0x5000
OPCODE_ARTPOLL = 0x2000
ARTNET_MIN_PROTO = 14
ARTNET_PORT = 6454


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
            return
        opcode = data[8] | (data[9] << 8)
        if opcode == OPCODE_ARTPOLL:
            # Reply directly to the controller that asked
            if self._transport is not None:
                self._transport.sendto(self._reply, (addr[0], ARTNET_PORT))
                _LOGGER.debug("DMX Input: ArtPoll from %s → replied", addr[0])
        elif opcode == OPCODE_ARTDMX:
            parsed = parse_artdmx(data)
            if parsed is not None:
                self._on_dmx(parsed[0], parsed[1])

    def error_received(self, exc):
        _LOGGER.debug("Art-Net socket error: %s", exc)


def _channel(dmx: bytes, ch: int) -> int:
    """Return the value of 1-based DMX channel *ch* (0 if out of range)."""
    idx = ch - 1
    if 0 <= idx < len(dmx):
        return dmx[idx]
    return 0


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
        # data is the list of channel mappings
        self._data = data if isinstance(data, list) else []

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
        now = time.monotonic()
        stale_timeout = self._config.get("stale_timeout", 2.0)
        hold = self._config.get("hold_last_look", False)

        for idx, mapping in enumerate(self._data):
            if not mapping.get("active", True):
                continue

            universe = int(mapping.get("universe", 0))
            dmx = self._latest_dmx.get(universe)
            if dmx is None:
                continue

            # On the first packet for a universe, prime baselines so a channel
            # that is already high at startup does not spuriously fire.
            if universe not in self._seen_universe:
                self._seen_universe.add(universe)
                self._prime_mapping(idx, mapping, dmx)
                continue

            # Stale-stream handling: release owned looks if the source stopped.
            if (
                stale_timeout > 0
                and not hold
                and (now - self._last_packet_time.get(universe, 0))
                > stale_timeout
            ):
                self._release_mapping(idx, mapping)
                continue

            mtype = mapping.get("type")
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
        self._mapping_state.setdefault(
            idx, {"triggered": False, "last_color": None, "wash_on": False}
        )

    def _process_trigger(self, idx, mapping, dmx):
        state = self._mapping_state.setdefault(idx, {"triggered": False})
        ch = int(mapping.get("channels", [1])[0])
        value = _channel(dmx, ch)
        on_t = int(mapping.get("on_threshold", 128))
        off_t = int(mapping.get("off_threshold", 96))
        venue_id = mapping.get("venue_id")
        pad_index = mapping.get("pad_index")
        if venue_id is None or pad_index is None:
            return

        mgr = self._venues()
        if state["triggered"]:
            if value <= off_t:
                state["triggered"] = False
                # Only clear if we still own this venue's override
                if self._venue_override_owner.get(venue_id) == idx:
                    try:
                        mgr.clear_override(venue_id)
                    except Exception as e:
                        _LOGGER.warning("DMX Input clear_override: %s", e)
                    self._venue_override_owner.pop(venue_id, None)
        else:
            if value >= on_t:
                state["triggered"] = True
                try:
                    mgr.activate_override(venue_id, int(pad_index))
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
        state = self._mapping_state.setdefault(idx, {"last_color": None})
        chans = mapping.get("channels", [1, 2, 3])
        r = _channel(dmx, int(chans[0]))
        g = _channel(dmx, int(chans[1]))
        b = _channel(dmx, int(chans[2]))
        rgb = (r, g, b)
        if rgb == state["last_color"]:
            return
        state["last_color"] = rgb
        hex_color = "#{:02x}{:02x}{:02x}".format(r, g, b)
        for v in self._targets(mapping):
            try:
                v.set_color_override(hex_color)
                self._owned_color.add(v.id)
            except Exception as e:
                _LOGGER.warning("DMX Input set_color_override: %s", e)

    def _process_fixture(self, idx, mapping, dmx):
        state = self._mapping_state.setdefault(idx, {"wash_on": False})
        chans = mapping.get("channels", {})
        # channels may be a dict {mode,dimmer,r,g,b} or a 5-list in that order
        if isinstance(chans, dict):
            mode_ch = int(chans.get("mode", 1))
            dim_ch = int(chans.get("dimmer", 2))
            r_ch = int(chans.get("r", 3))
            g_ch = int(chans.get("g", 4))
            b_ch = int(chans.get("b", 5))
        else:
            mode_ch, dim_ch, r_ch, g_ch, b_ch = (
                list(chans) + [1, 2, 3, 4, 5]
            )[:5]
        on_t = int(mapping.get("on_threshold", 128))
        off_t = int(mapping.get("off_threshold", 96))
        mode_val = _channel(dmx, mode_ch)

        targets = list(self._targets(mapping))
        if state["wash_on"]:
            if mode_val <= off_t:
                state["wash_on"] = False
                for v in targets:
                    try:
                        v.clear_dmx_wash()
                    except Exception as e:
                        _LOGGER.warning("DMX Input clear_dmx_wash: %s", e)
                    self._owned_washes.discard(v.id)
                _LOGGER.info(
                    "DMX Input: fixture '%s' wash OFF on %d virtual(s)",
                    mapping.get("name", idx),
                    len(targets),
                )
            else:
                dimmer = _channel(dmx, dim_ch) / 255.0
                rgb = (
                    _channel(dmx, r_ch),
                    _channel(dmx, g_ch),
                    _channel(dmx, b_ch),
                )
                for v in targets:
                    try:
                        v.set_dmx_wash(rgb, dimmer)
                    except Exception as e:
                        _LOGGER.warning("DMX Input set_dmx_wash: %s", e)
        else:
            if mode_val >= on_t:
                state["wash_on"] = True
                dimmer = _channel(dmx, dim_ch) / 255.0
                rgb = (
                    _channel(dmx, r_ch),
                    _channel(dmx, g_ch),
                    _channel(dmx, b_ch),
                )
                for v in targets:
                    try:
                        v.set_dmx_wash(rgb, dimmer)
                        self._owned_washes.add(v.id)
                    except Exception as e:
                        _LOGGER.warning("DMX Input set_dmx_wash: %s", e)
                _LOGGER.info(
                    "DMX Input: fixture '%s' wash ON rgb=%s dimmer=%.2f on "
                    "%d virtual(s)",
                    mapping.get("name", idx),
                    rgb,
                    dimmer,
                    len(targets),
                )

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
        ``venue_id``.
        """
        vid = mapping.get("virtual_id")
        if vid:
            v = self._ledfx.virtuals.get(vid)
            if v is not None:
                yield v
            return
        venue_id = mapping.get("venue_id")
        if venue_id:
            cfg = self._venues().get(venue_id)
            if not cfg:
                return
            for v_id in cfg.get("virtual_ids", []):
                v = self._ledfx.virtuals.get(v_id)
                if v is not None:
                    yield v

    def _release_mapping(self, idx, mapping):
        """Release whatever a single mapping currently owns."""
        state = self._mapping_state.get(idx)
        if not state:
            return
        mtype = mapping.get("type")
        if mtype == "trigger" and state.get("triggered"):
            state["triggered"] = False
            venue_id = mapping.get("venue_id")
            if venue_id and self._venue_override_owner.get(venue_id) == idx:
                try:
                    self._venues().clear_override(venue_id)
                except Exception:
                    pass
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
