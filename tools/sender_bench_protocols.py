"""Real LedFx flush adapters and independent payload checks for sender_bench.

Discovery, authentication, hardware and periodic discovery threads are excluded.
All network writes are intercepted by the benchmark's loopback-only transport.
Limits describe this implementation's selected RGB configuration, not products.
"""

import base64
import json
import struct
from dataclasses import dataclass
from types import SimpleNamespace
from typing import Any

import numpy as np


@dataclass(frozen=True)
class SenderSpec:
    module: str
    class_name: str
    transport: str
    max_pixels: int
    note: str
    option: str = ""


SPECS = {
    "ddp": SenderSpec(
        "ddp",
        "DDPDevice",
        "udp",
        1_000_000,
        "480 RGB pixels/datagram; benchmark cap 1M, not protocol limit",
    ),
    "artnet": SenderSpec(
        "artnet",
        "ArtNetDevice",
        "udp",
        32768 * 170,
        "510 channels/universe; ordered universe sets, no atomic frame ID",
    ),
    "e131": SenderSpec(
        "e131",
        "E131Device",
        "udp",
        63998 * 170,
        "510 channels/universe plus sync; sync multicast redirected to loopback; periodic discovery excluded",
    ),
    "opc": SenderSpec(
        "open_pixel_control",
        "OpenPixelControl",
        "udp",
        21834,
        "LedFx currently uses a single UDP datagram, not TCP; IPv4 datagram limit",
    ),
    "openrgb": SenderSpec(
        "openrgb",
        "OpenRGB",
        "tcp",
        65535,
        "16-bit pixel count; direct update only, discovery excluded",
    ),
    "adalight": SenderSpec(
        "adalight",
        "AdalightDevice",
        "serial",
        65535,
        "encoding only; real baud rate and hardware excluded",
    ),
    "nanoleaf": SenderSpec(
        "nanoleaf",
        "NanoleafDevice",
        "udp",
        (65507 - 2) // 8,
        "v2 UDP, synthetic sequential panel IDs; discovery/authentication excluded",
    ),
    "govee": SenderSpec(
        "govee",
        "Govee",
        "udp",
        255,
        "8-bit segment count; JSON/base64 Razer payload; activation excluded",
    ),
    "hue": SenderSpec(
        "hue",
        "HueDevice",
        "dtls",
        256,
        "plaintext encoding only; DTLS, pairing and bridge channel limits excluded",
    ),
}
for _name, _option, _limit in [
    ("drgb", "DRGB", 490),
    ("warls", "WARLS", 255),
    ("drgbw", "DRGBW", 367),
    ("dnrgb", "DNRGB", 65536),
    ("adaptive", "adaptive_smallest", 255),
    ("raw", "RGB (HyperHDR)", 500),
]:
    SPECS["udp-" + _name] = SenderSpec(
        "udp",
        "UDPRealtimeDevice",
        "udp",
        _limit,
        "traffic minimization enabled; no sequence/frame ID",
        _option,
    )
for _name, _option in [
    ("one", "One_Argument"),
    ("three", "Three_Arguments"),
    ("channels", "Three_Addresses"),
    ("all", "All_To_One"),
]:
    SPECS["osc-" + _name] = SenderSpec(
        "osc",
        "OSCServerDevice",
        "udp",
        3851 if _name == "all" else 1_000_000,
        "normalized float32 colors; duplicate frames suppressed; 1M benchmark cap for per-address modes",
        _option,
    )

# These adapters require hardware or an SDK session. Do not time mocked SDK calls
# and present the result as wire throughput.
UNMEASURED = {
    "wled": "Delegates flush to measured DDP, E131 or UDP senders; discovery and WLED firmware capacity excluded.",
    "lifx": "RGB-to-HSBK plus device-specific Animator, or asynchronous single-bulb fallback; scheduling time alone is not delivery time. Needs a separate SDK/device fixture.",
    "twinkly_squares": "Permutation plus xled v3 realtime chunks; xled creates sockets and needs authenticated session/device layout. Needs an SDK fixture.",
    "zengee": "Uses only the first RGB triple and calls flux_led setRgb; not a per-pixel strip transport. SDK/device fixture required.",
    "launchpad": "Model-specific MIDI messages and USB/MIDI transport require hardware coverage.",
    "rpi_ws281x": "Native GPIO/DMA and output-mode conversion require Raspberry Pi hardware.",
    "dummy": "No output transport; use pixel_bench --device dummy for rendering-only baseline.",
    "nanoleaf_tcp": "HTTP request/response path excluded; measured variant is v2 UDP.",
}


def make_sender(name: str, pixels: int, sink: Any) -> Any:
    """Initialize flush state without touching discovery, hardware or remote hosts."""
    import importlib

    spec = SPECS[name]
    cls = getattr(
        importlib.import_module("ledfx.devices." + spec.module), spec.class_name
    )
    config = {
        "name": "sender-benchmark",
        "ip_address": "127.0.0.1",
        "pixel_count": pixels,
        "port": 4048,
    }
    if name.startswith("udp-"):
        config["udp_packet_type"] = spec.option
    if name.startswith("osc-"):
        config.update(send_type=spec.option, path="/bench/{address}")
    if name == "nanoleaf":
        config.update(
            model="NL29", pixel_layout=[{"panelId": i} for i in range(pixels)]
        )
    if name == "hue":
        config.update(
            group_name="benchmark",
            entertainment_id="00000000-0000-0000-0000-000000000000",
        )
    typed = cls.config_model().model_validate(config)
    if name == "hue":
        # __init__ pairs with a bridge; only measure the plaintext flush kernel.
        device = object.__new__(cls)
        device._config = typed
    else:
        device = cls(SimpleNamespace(), typed)
    device._destination = "127.0.0.1"
    device._sock = sink
    if name == "artnet":
        from stupidArtnet import StupidArtnet

        device._artnet = StupidArtnet("127.0.0.1", packet_size=510, broadcast=False)
        device._artnet.socket_client.close()
        device._artnet.socket_client = sink
    elif name == "e131":
        import sacn

        device._sacn = sacn.sACNsender(
            bind_port=0, source_name="benchmark", universeDiscovery=False
        )
        device._sacn._sender_handler.socket._socket.close()
        device._sacn._sender_handler.socket._socket = sink
        device._sacn.manual_flush = True
        for universe in range(1, device.config.universe_end + 1):
            device._sacn.activate_output(universe)
            device._sacn[universe].destination = "127.0.0.1"
    elif name.startswith("osc-"):
        from pythonosc.udp_client import SimpleUDPClient

        device._client = SimpleUDPClient("127.0.0.1", 9000)
        device._client._sock.close()
        device._client._sock = sink
    elif name == "adalight":
        device.serial = sink
    elif name == "openrgb":
        device.openrgb_device = SimpleNamespace(id=0, comms=SimpleNamespace(sock=sink))
    elif name == "govee":
        device.udp_server = sink
    return device


def canonical_packet(name: str, data: bytes) -> bytes:
    """Mask only sequence counters; every payload/header byte remains checked."""
    packet = bytearray(data)
    if name == "ddp":
        packet[1] = 0
    elif name == "artnet":
        packet[12] = 0
    elif name == "e131":
        packet[111 if len(packet) > 49 else 44] = 0
    return bytes(packet)


def check_payload(
    name: str, packets: list[bytes], expected: np.ndarray, previous: np.ndarray | None
) -> None:
    """Decode a complete flush independently and compare RGB values to its input."""
    rgb = expected.astype(np.uint8)
    size = len(rgb)
    decoded = bytearray()
    if name == "ddp":
        offset = 0
        sequence = packets[0][1]
        for i, data in enumerate(packets):
            flags, seq, dtype, dest, start, length = struct.unpack("!BBBBIH", data[:10])
            assert flags == (0x41 if i == len(packets) - 1 else 0x40)
            assert (seq, dtype, dest, start, length) == (
                sequence,
                11,
                1,
                offset,
                len(data) - 10,
            )
            assert length <= 1440
            decoded.extend(data[10:])
            offset += length
    elif name in ("artnet", "e131"):
        universe = 0 if name == "artnet" else 1
        for data in packets:
            if name == "artnet":
                assert data[:12] == b"Art-Net\x00\x00\x50\x00\x0e"
                assert int.from_bytes(data[14:16], "little") == universe
                assert int.from_bytes(data[16:18], "big") == len(data) - 18 == 510
                decoded.extend(data[18:])
            else:
                assert data[4:16] == b"ASC-E1.17\x00\x00\x00"
                if len(data) == 49:
                    assert data[18:22] == b"\x00\x00\x00\x08"
                    continue
                assert int.from_bytes(data[113:115], "big") == universe
                assert int.from_bytes(data[123:125], "big") == len(data) - 125
                assert data[125] == 0
                decoded.extend(
                    data[126:636]
                )  # 510 selected channels; library keeps 512.
            universe += 1
        decoded = decoded[: size * 3]
    elif name.startswith("udp-"):
        result = (
            np.zeros_like(rgb) if previous is None else previous.astype(np.uint8).copy()
        )
        if name == "udp-raw":
            decoded.extend(packets[0])
        else:
            for data in packets:
                kind = data[0]
                assert data[1] == 1
                if kind == 1:
                    records = np.frombuffer(data[2:], dtype=np.uint8).reshape(-1, 4)
                    result[records[:, 0]] = records[:, 1:]
                elif kind == 2:
                    result[:] = np.frombuffer(data[2:], dtype=np.uint8).reshape(-1, 3)
                elif kind == 3:
                    records = np.frombuffer(data[2:], dtype=np.uint8).reshape(-1, 4)
                    assert not records[:, 3].any()
                    result[:] = records[:, :3]
                else:
                    assert kind == 4
                    start = int.from_bytes(data[2:4], "big")
                    colors = np.frombuffer(data[4:], dtype=np.uint8).reshape(-1, 3)
                    result[start : start + len(colors)] = colors
            decoded.extend(result.tobytes())
    elif name == "opc":
        channel, command, length = struct.unpack(">BBH", packets[0][:4])
        assert (channel, command, length) == (0, 0, size * 3)
        decoded.extend(packets[0][4:])
    elif name == "openrgb":
        data = packets[0]
        magic, device, command, length, payload_length, count = struct.unpack(
            "=4sIIIIH", data[:22]
        )
        assert (magic, device, command, length, payload_length, count) == (
            b"ORGB",
            0,
            1050,
            len(data) - 16,
            len(data) - 16,
            size,
        )
        colors = np.frombuffer(data[22:], dtype=np.uint8).reshape(-1, 4)
        assert not colors[:, 3].any()
        decoded.extend(colors[:, :3].tobytes())
    elif name == "adalight":
        data = packets[0]
        assert data[:3] == b"Ada" and int.from_bytes(data[3:5], "big") == size
        assert data[5] == data[3] ^ data[4] ^ 0x55
        decoded.extend(data[6:])
    elif name == "nanoleaf":
        data = packets[0]
        assert int.from_bytes(data[:2], "big") == size
        for i in range(size):
            panel, r, g, b, white, transition = struct.unpack(
                ">HBBBBH", data[2 + i * 8 : 10 + i * 8]
            )
            assert (panel, white, transition) == (i, 0, 0)
            decoded.extend((r, g, b))
    elif name == "govee":
        message = json.loads(packets[0])
        assert message["msg"]["cmd"] == "razer"
        data = base64.b64decode(message["msg"]["data"]["pt"], validate=True)
        assert data[:5] == bytes([0xBB, 0, 0xFA, 0xB0, 0]) and data[5] == size
        assert np.bitwise_xor.reduce(np.frombuffer(data, dtype=np.uint8)) == 0
        decoded.extend(data[6:-1])
    elif name == "hue":
        data = packets[0]
        assert data[:9] == b"HueStream"
        for i in range(size):
            channel, r, rr, g, gg, b, bb = data[52 + i * 7 : 59 + i * 7]
            assert (channel, r, g, b) == (i, rr, gg, bb)
            decoded.extend((r, g, b))
    elif name.startswith("osc-"):
        from pythonosc.osc_message import OscMessage

        values = []
        for i, data in enumerate(packets):
            message = OscMessage(data)
            assert message.address == f"/bench/{0 if name == 'osc-all' else i}"
            for value in message.params:
                values.extend(value if isinstance(value, list) else [value])
        np.testing.assert_allclose(
            np.array(values).reshape(-1, 3), rgb / 255, rtol=0, atol=3e-8
        )
        return
    else:
        raise ValueError(name)
    assert bytes(decoded) == rgb.tobytes(), f"Incorrect RGB payload: {name}"
