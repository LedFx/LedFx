"""Wire compatibility of optimized E1.31/OSC frame conversion."""

from types import SimpleNamespace

import numpy as np
import pytest
from numpy.typing import NDArray
from pythonosc.osc_message_builder import OscMessageBuilder

from ledfx.devices.e131 import E131Device
from ledfx.devices.osc import OSCServerDevice
from tests.native_sender_helpers import capture_packets, configure_capture, make_device

OSC_MODES = ["One_Argument", "Three_Arguments", "Three_Addresses", "All_To_One"]


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


@pytest.mark.parametrize("mode", OSC_MODES)
@pytest.mark.parametrize("dtype", ["float32", "float64", "int16", "uint8"])
@pytest.mark.parametrize("count", [1, 17, 171])
def test_osc_wire_equivalence_and_duplicate_suppression(
    mode: str, dtype: str, count: int
) -> None:
    sender = make_device(
        OSCServerDevice,
        count,
        send_type=mode,
        path="/lights/{address:04d}/rgb",
        starting_addr=97,
    )
    rng = np.random.default_rng(2060)
    data = rng.uniform(-25, 300, (count * 2, 3)).astype(dtype)[::2, ::-1]
    original = data.copy()
    for frame in (data, data + 1, data):
        before = len(capture_packets(sender))
        sender.flush(frame)
        assert capture_packets(sender)[before:] == legacy_osc(
            frame, sender.config.send_type, sender.config.path, 97
        )
        before = len(capture_packets(sender))
        sender.flush(frame.copy())
        assert len(capture_packets(sender)) == before
    np.testing.assert_array_equal(data, original)


@pytest.mark.parametrize(
    "size,offset,count",
    [(510, 0, 171), (512, 509, 171), (128, 7, 90), (510, 510, 1), (510, 1027, 2)],
)
@pytest.mark.parametrize("dtype", ["float32", "float64", "int16", "uint8"])
def test_e131_channels_offsets_and_untouched_slots(
    size: int, offset: int, count: int, dtype: str
) -> None:
    from ledfx_senders import E131Sender

    device = E131Device(
        SimpleNamespace(),
        E131Device.config_model().model_validate(
            {
                "name": "test",
                "ip_address": "127.0.0.1",
                "pixel_count": count,
                "universe": 42,
                "universe_size": size,
                "channel_offset": offset,
            }
        ),
    )
    sender = E131Sender._test_sender(
        device._layout(), mode="capture", destination="127.0.0.1", source_name="test"
    )
    device._sender = sender
    data = (
        np.random.default_rng(2060)
        .uniform(0, 256, (count * 2, 3))
        .astype(dtype)[::2, ::-1]
    )
    expected = np.zeros((len(sender.layout.universes), 512), dtype="uint8")
    for index, value in enumerate(data.astype(int).ravel()):
        universe, slot = divmod(offset + index, size)
        expected[universe, slot] = value
    device.flush(data)
    packets = [packet for packet, _ in sender._engine.captures()[:-1]]
    np.testing.assert_array_equal([list(packet[126:]) for packet in packets], expected)
    sender.close()


@pytest.mark.parametrize("mode", OSC_MODES)
def test_osc_headers_follow_configuration_changes(mode: str) -> None:
    sender = make_device(OSCServerDevice, 2, send_type=mode)
    sender.flush(np.zeros((2, 3)))
    sender._set_config_values(path="/new/{address}", starting_addr=600)
    configure_capture(sender)
    data = np.ones((2, 3))
    sender.flush(data)
    assert capture_packets(sender) == legacy_osc(
        data, sender.config.send_type, "/new/{address}", 600
    )


@pytest.mark.parametrize("offset", [0, 509, 510, 1027])
def test_e131_real_packets_preserve_layout_and_library_validation(offset: int) -> None:
    from ledfx_senders import E131Sender

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
    sender = E131Sender._test_sender(
        device._layout(), mode="capture", destination="127.0.0.1", source_name="test"
    )
    device._sender = sender
    frame = np.random.default_rng(2060).uniform(0, 256, (count, 3))
    device.flush(frame)
    packets = [packet for packet, _ in sender._engine.captures()[:-1]]
    expected = np.zeros((len(sender.layout.universes), 512), dtype="uint8")
    for index, value in enumerate(frame.astype(int).ravel()):
        universe, slot = divmod(offset + index, 510)
        expected[universe, slot] = value
    for i, packet in enumerate(packets):
        assert int.from_bytes(packet[113:115], "big") == 42 + i
        assert packet[126:] == expected[i].tobytes()
    before = sender._engine.captures()
    frame[0, 0] = 256
    with pytest.raises(ValueError):
        device.flush(frame)
    assert sender._engine.captures() == before
    sender.close()
