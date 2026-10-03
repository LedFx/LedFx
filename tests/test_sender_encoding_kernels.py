"""Wire compatibility of optimized E1.31/OSC frame conversion."""

import socket
from types import SimpleNamespace
from typing import cast

import numpy as np
import pytest
from numpy.typing import NDArray
from pythonosc.osc_message_builder import OscMessageBuilder

from ledfx.devices.e131 import E131Device
from tools.sender_bench import Sink
from tools.sender_bench_protocols import make_sender


def legacy_osc(
    data: NDArray[np.generic], mode: str, path: str, start: int
) -> list[bytes]:
    messages = []
    for i, color in enumerate(data.astype(int)):
        values = [value / 255 for value in color]
        if mode == "Three_Addresses":
            for channel, value in enumerate(values):
                message = OscMessageBuilder(
                    path.format(address=start + 3 * i + channel)
                )
                message.add_arg(value)
                messages.append(message)
        elif mode == "All_To_One":
            if not messages:
                messages.append(OscMessageBuilder(path.format(address=start)))
            messages[0].add_arg(values)
        else:
            message = OscMessageBuilder(path.format(address=start + i))
            if mode == "One_Argument":
                message.add_arg(values)
            else:
                for value in values:
                    message.add_arg(value)
            messages.append(message)
    return [message.build().dgram for message in messages]


@pytest.mark.parametrize("name", ["osc-one", "osc-three", "osc-channels", "osc-all"])
@pytest.mark.parametrize("dtype", ["float32", "float64", "int16", "uint8"])
@pytest.mark.parametrize("count", [1, 17, 171])
def test_osc_wire_equivalence_and_duplicate_suppression(
    name: str, dtype: str, count: int
) -> None:
    sink = Sink()
    sender = make_sender(name, count, sink)
    sender._set_config_values(path="/lights/{address:04d}/rgb", starting_addr=97)
    rng = np.random.default_rng(2060)
    data = rng.uniform(-25, 300, (count * 2, 3)).astype(dtype)[::2, ::-1]
    original = data.copy()
    for frame in (data, data + 1, data):
        sink.capture = []
        sender.flush(frame)
        assert sink.capture == legacy_osc(
            frame, sender.config.send_type, sender.config.path, 97
        )
        sink.capture = []
        sender.flush(frame.copy())
        assert sink.capture == []
    np.testing.assert_array_equal(data, original)


@pytest.mark.parametrize(
    "size,offset,count",
    [(510, 0, 171), (512, 509, 171), (128, 7, 90), (510, 510, 1), (510, 1027, 2)],
)
@pytest.mark.parametrize("dtype", ["float32", "float64", "int16", "uint8"])
def test_e131_channels_offsets_and_untouched_slots(
    size: int, offset: int, count: int, dtype: str
) -> None:
    config = E131Device.config_model().model_validate(
        {
            "name": "test",
            "ip_address": "127.0.0.1",
            "pixel_count": count,
            "universe": 42,
            "universe_size": size,
            "channel_offset": offset,
        }
    )
    device = E131Device(SimpleNamespace(), config)

    class Outputs(dict[int, SimpleNamespace]):
        def flush(self) -> None:
            pass

    outputs = Outputs(
        {
            u: SimpleNamespace(dmx_data=tuple([19] * 512))
            for u in range(42, 42 + (offset + count * 3 - 1) // size + 1)
        }
    )
    device._sacn = outputs
    data = (
        np.random.default_rng(2060)
        .uniform(0, 256, (count * 2, 3))
        .astype(dtype)[::2, ::-1]
    )
    expected = np.full((len(outputs), 512), 19)
    flat = data.astype(int).ravel()
    for index, value in enumerate(flat):
        universe, slot = divmod(offset + index, size)
        expected[universe, slot] = value
    device.flush(data)
    np.testing.assert_array_equal([o.dmx_data for o in outputs.values()], expected)


@pytest.mark.parametrize("name", ["osc-one", "osc-three", "osc-channels", "osc-all"])
def test_osc_headers_follow_configuration_changes(name: str) -> None:
    sink = Sink()
    sender = make_sender(name, 2, sink)
    sender.flush(np.zeros((2, 3)))
    sender._set_config_values(path="/new/{address}", starting_addr=600)
    data = np.ones((2, 3))
    sink.capture = []
    sender.flush(data)
    assert sink.capture == legacy_osc(
        data, sender.config.send_type, "/new/{address}", 600
    )


@pytest.mark.parametrize("offset", [0, 509, 510, 1027])
def test_e131_real_packets_preserve_layout_and_library_validation(offset: int) -> None:
    import sacn
    from sacn.sending.sender_socket_udp import SenderSocketUDP

    count = 171
    device = E131Device(
        SimpleNamespace(),
        E131Device.config_model().model_validate(
            {
                "name": "test",
                "ip_address": "127.0.0.1",
                "pixel_count": count,
                "universe": 42,
                "universe_size": 510,
                "channel_offset": offset,
            }
        ),
    )
    sender = sacn.sACNsender(bind_port=0, universeDiscovery=False)
    # The concrete transport has a socket; replace it with the capture adapter.
    transport = cast(SenderSocketUDP, sender._sender_handler.socket)
    transport._socket.close()
    sink = Sink()
    transport._socket = cast(socket.socket, sink)
    sender.manual_flush = True
    device._sacn = sender
    universe_count = (offset + count * 3 - 1) // 510 + 1
    for universe in range(42, 42 + universe_count):
        sender.activate_output(universe)
        output = sender[universe]
        assert output is not None
        output.destination = "127.0.0.1"
        output.dmx_data = (19,) * 512
    frame = np.random.default_rng(2060).uniform(0, 256, (count, 3))
    expected = np.full((universe_count, 512), 19)
    for index, value in enumerate(frame.astype(int).ravel()):
        universe, slot = divmod(offset + index, 510)
        expected[universe, slot] = value
    device.flush(frame)
    assert sink.capture is not None
    packets = [packet for packet in sink.capture if len(packet) > 49]
    assert len(packets) == len(expected)
    for i, packet in enumerate(packets):
        assert int.from_bytes(packet[113:115], "big") == 42 + i
        assert packet[126:] == expected[i].astype("uint8").tobytes()
    sink.capture = []
    frame[0, 0] = 256
    with pytest.raises(ValueError, match="valid bytes"):
        device.flush(frame)
    assert sink.capture == []
