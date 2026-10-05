"""Actual adapter boundaries retain session ownership and validate before I/O."""

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from ledfx_senders import HueSender, NanoleafSender

from ledfx.devices import packets
from ledfx.devices.govee import Govee
from ledfx.devices.hue import HueDevice
from ledfx.devices.nanoleaf import NanoleafDevice
from ledfx.devices.zengee import ZenggeDevice


def govee_device(sock: MagicMock) -> Govee:
    device = Govee(
        MagicMock(),
        Govee.Config.model_validate(
            {"name": "test", "ip_address": "127.0.0.1", "pixel_count": 1}
        ),
    )
    device.udp_server = sock
    return device


def hue_device(sender: HueSender) -> HueDevice:
    device = HueDevice(
        MagicMock(),
        HueDevice.Config.model_validate(
            {
                "name": "test",
                "ip_address": "127.0.0.1",
                "group_name": "test",
                "entertainment_id": "00000000-0000-0000-0000-000000000000",
                "channel_ids": [7],
            }
        ),
    )
    device._sender = sender
    return device


def test_adalight_compatibility_wrapper_corrects_inclusive_count() -> None:
    packet = packets.build_adalight_packet(np.array([[1, 2, 3]]), "RGB")
    assert isinstance(packet, bytes)
    assert packet == b"Ada\0\0\x55\1\2\3"


def test_govee_invalid_frame_never_reaches_shared_socket() -> None:
    sink = MagicMock()
    device = govee_device(sink)
    with pytest.raises(ValueError):
        device.flush(np.array([[1, 2, np.nan]]))
    sink.sendto.assert_not_called()
    sink.send.assert_not_called()


def test_hue_native_validation_preserves_nonfinite_error_precedence() -> None:
    sender = HueSender(
        destination="127.0.0.1",
        psk_identity=b"opaque",
        client_key=b"key",
        entertainment_id="00000000-0000-0000-0000-000000000000",
        channel_ids=(7,),
    )
    device = hue_device(sender)
    try:
        with pytest.raises(OverflowError):
            device.flush(np.array([[256, np.inf, 0]]))
        assert device._sender is sender
        assert not sender.connected
    finally:
        sender.close()


def test_hue_flush_passes_array_to_owned_sender() -> None:
    sender = MagicMock(spec=HueSender)
    device = hue_device(sender)
    frame = np.array([[17, 34, 51]])
    device.flush(frame)
    sender.send.assert_called_once()
    assert sender.send.call_args.args[0] is frame
    assert device._sender is sender
    with pytest.raises(TypeError, match="numpy"):
        device.flush(bytes([1, 2, 3]))  # pyrefly: ignore[bad-argument-type]


def test_zengge_converts_only_first_pixel() -> None:
    class FirstPixelOnly:
        def astype(self, dtype: object) -> np.ndarray:
            raise AssertionError("whole-frame conversion")

        def __getitem__(self, index: int) -> np.ndarray:
            assert index == 0
            return np.array([257.9, -1.9, 17.2])

    frame = FirstPixelOnly()
    device = object.__new__(ZenggeDevice)
    device.bulb = MagicMock()
    device.flush(frame)
    device.bulb.setRgb.assert_called_once_with(1, 255, 17)


def test_nanoleaf_udp_uses_native_sender_and_rejects_short_frame() -> None:
    native = NanoleafSender._test_sender(
        destination="127.0.0.1", port=60222, version=1, panel_ids=(7, 9), mode="capture"
    )
    config = NanoleafDevice.Config.model_validate(
        {
            "name": "test",
            "ip_address": "127.0.0.1",
            "model": "NL22",
            "pixel_layout": [{"panelId": 7}, {"panelId": 9}],
            "pixel_count": 2,
        }
    )
    device = NanoleafDevice(SimpleNamespace(), config)
    device._sender = native
    device.flush(np.array([[17, 34, 51], [68, 85, 102]]))
    assert native._engine.captures()[0][0] == bytes.fromhex(
        "020701112233000109014455660001"
    )
    with pytest.raises(ValueError):
        device.flush(np.array([[1, 2, 3]]))
    assert len(native._engine.captures()) == 1
    native.close()


def test_nanoleaf_failed_replacement_preserves_live_sender() -> None:
    config = NanoleafDevice.Config.model_validate(
        {
            "name": "test",
            "ip_address": "127.0.0.1",
            "model": "NL22",
            "pixel_layout": [{"panelId": 7}],
            "pixel_count": 1,
        }
    )
    core = MagicMock()
    core.virtuals = dict[str, object]()
    device = NanoleafDevice(core, config)
    original = NanoleafSender._test_sender(
        destination="127.0.0.1", port=60222, version=1, panel_ids=(7,), mode="capture"
    )
    device._sender = original
    device._destination = "127.0.0.1"
    with (
        patch(
            "ledfx.devices.nanoleaf.requests.put",
            return_value=SimpleNamespace(status_code=200),
        ),
        pytest.raises(ValueError),
    ):
        device.update_config(
            {"pixel_layout": [{"panelId": 7}, {"panelId": 7}], "pixel_count": 2}
        )
    assert device._sender is original and not original.closed
    assert device.config.as_dict()["pixel_count"] == 1
    original.close()


def test_govee_real_flush_keeps_shared_socket_owner() -> None:
    sink = MagicMock()
    device = govee_device(sink)
    device.flush(np.array([[17, 34, 51]], dtype=np.uint8))
    sink.sendto.assert_called_once_with(
        b'{"msg": {"cmd": "razer", "data": {"pt": "uwD6sAABESIz8A=="}}}',
        ("127.0.0.1", 4003),
    )
    assert device.udp_server is sink


async def test_nanoleaf_dns_failure_stale_result_and_callback_ownership() -> None:
    import asyncio
    import threading

    core = MagicMock()
    core.loop = asyncio.get_running_loop()
    config = NanoleafDevice.Config.model_validate(
        {
            "name": "test",
            "ip_address": "127.0.0.1",
            "model": "NL22",
            "pixel_layout": [{"panelId": 7}],
            "pixel_count": 1,
        }
    )
    device = NanoleafDevice(core, config)
    original = NanoleafSender._test_sender(
        destination="127.0.0.1", port=60222, version=1, panel_ids=(7,), mode="capture"
    )
    device._sender = original
    device._destination = "127.0.0.1"
    device._active = True
    try:
        with (
            patch("ledfx.devices.resolve_destination", return_value="127.0.0.2"),
            patch(
                "ledfx.devices.nanoleaf.resolve_destination",
                return_value="127.0.0.2",
                create=True,
            ),
            patch(
                "ledfx.devices.nanoleaf.NanoleafSender",
                side_effect=OSError("candidate failed"),
            ),
            pytest.raises(OSError, match="candidate failed"),
        ):
            await device.resolve_address()
        assert device._destination == "127.0.0.1"
        assert device._sender is original and not original.closed

        async def stale(*args: object) -> str:
            device.deactivate()
            return "127.0.0.3"

        with (
            patch("ledfx.devices.resolve_destination", side_effect=stale),
            patch(
                "ledfx.devices.nanoleaf.resolve_destination",
                side_effect=stale,
                create=True,
            ),
        ):
            await device.resolve_address()
        assert device._destination == "127.0.0.1"
        assert device._sender is None and original.closed
        finished = threading.Event()

        def callback() -> None:
            def acquire() -> None:
                with device.lock, device.device_lock:
                    finished.set()

            worker = threading.Thread(target=acquire)
            worker.start()
            assert finished.wait(2)
            worker.join(2)

        with (
            patch("ledfx.devices.resolve_destination", return_value="127.0.0.4"),
            patch(
                "ledfx.devices.nanoleaf.resolve_destination",
                return_value="127.0.0.4",
                create=True,
            ),
        ):
            await device.resolve_address(callback)
        assert device._destination == "127.0.0.4" and finished.is_set()
    finally:
        device.deactivate()


def test_nanoleaf_mode_changes_close_only_owned_sessions_and_rollback_rest_failure() -> (
    None
):
    config = NanoleafDevice.Config.model_validate(
        {
            "name": "test",
            "ip_address": "127.0.0.1",
            "model": "NL22",
            "pixel_layout": [{"panelId": 7}],
            "pixel_count": 1,
        }
    )
    core = MagicMock()
    core.virtuals = dict[str, object]()
    device = NanoleafDevice(core, config)
    original = NanoleafSender._test_sender(
        destination="127.0.0.1", port=60222, version=1, panel_ids=(7,), mode="capture"
    )
    unrelated = NanoleafSender._test_sender(
        destination="127.0.0.1", port=60222, version=1, panel_ids=(8,), mode="capture"
    )
    candidates: list[NanoleafSender] = []

    def create(
        *, destination: str, port: int, version: int, panel_ids: tuple[int, ...]
    ) -> NanoleafSender:
        candidate = NanoleafSender._test_sender(
            destination=destination,
            port=port,
            version=version,
            panel_ids=panel_ids,
            mode="capture",
        )
        candidates.append(candidate)
        return candidate

    device._sender = original
    device._destination = "127.0.0.1"
    with (
        patch.object(device, "_virtuals_objs", list[object]()),
        patch("ledfx.devices.nanoleaf.NanoleafSender", side_effect=create),
        patch(
            "ledfx.devices.nanoleaf.requests.put",
            return_value=SimpleNamespace(status_code=200),
        ) as rest,
    ):
        device.update_config({"sync_mode": "TCP"})
        assert original.closed and device._sender is None and not unrelated.closed
        device.flush(np.array([[17, 34, 51]]))
        assert (
            rest.call_args.kwargs["json"]["write"]["animData"] == "1 7 1 17 34 51 0 0"
        )
        rest.return_value = SimpleNamespace(status_code=400)
        with pytest.raises(OSError):
            device.update_config({"sync_mode": "UDP"})
        assert device.config.sync_mode == "TCP" and device._sender is None
        assert candidates[-1].closed and not unrelated.closed
        rest.return_value = SimpleNamespace(status_code=200)
        device.update_config({"sync_mode": "UDP"})
        assert device._sender is candidates[-1] and not candidates[-1].closed
        device.deactivate()
        assert candidates[-1].closed and not unrelated.closed
    unrelated.close()


def test_twinkly_activation_caches_gather_and_preserves_xled_owner() -> None:
    from ledfx.devices import NetworkedDevice
    from ledfx.devices.twinkly_squares import TwinklySquaresDevice

    core = MagicMock()
    core.virtuals = dict[str, object]()
    device = TwinklySquaresDevice(
        core,
        TwinklySquaresDevice.Config.model_validate(
            {"name": "test", "ip_address": "127.0.0.1", "panel_count": 1}
        ),
    )
    ctrl = MagicMock()
    info = MagicMock()
    info.__getitem__.return_value = 4
    ctrl.get_device_info.return_value = info
    ctrl.get_led_layout.return_value = {
        "coordinates": [
            {"x": 1, "y": 1},
            {"x": -1, "y": -1},
            {"x": -1, "y": 1},
            {"x": 1, "y": -1},
        ]
    }
    with (
        patch(
            "ledfx.devices.twinkly_squares.xled.HighControlInterface", return_value=ctrl
        ),
        patch.object(NetworkedDevice, "activate"),
    ):
        device.activate()
    gather = device._gather
    frame = np.array([[1, 2, 3], [4, 5, 6], [257, -1, 17], [10, 11, 12]])
    device.flush(frame)
    received = ctrl.set_rt_frame_socket.call_args
    assert received.kwargs == {"version": 3}
    assert received.args[0].getvalue() == bytes(
        [4, 5, 6, 1, 255, 17, 1, 2, 3, 10, 11, 12]
    )
    device.flush(frame)
    assert device._gather is gather
    assert device.ctrl is ctrl
    with pytest.raises(ValueError):
        device.flush(np.full((4, 3), np.nan))
    assert ctrl.set_rt_frame_socket.call_count == 2
    with patch.object(NetworkedDevice, "deactivate"):
        device.deactivate()
    ctrl.set_mode.assert_called_with("movie")
    assert device.ctrl is None and device._gather is None


@pytest.mark.parametrize("status", [302, 401, 403, 500])
@pytest.mark.parametrize("replacement", ["config", "dns"])
async def test_nanoleaf_rejected_rest_never_replaces_healthy_session(
    status: int, replacement: str
) -> None:
    import asyncio

    core = MagicMock()
    core.loop = asyncio.get_running_loop()
    core.virtuals = dict[str, object]()
    config = NanoleafDevice.Config.model_validate(
        {
            "name": "test",
            "ip_address": "127.0.0.1",
            "model": "NL22",
            "pixel_layout": [{"panelId": 7}],
            "pixel_count": 1,
        }
    )
    device = NanoleafDevice(core, config)
    original = NanoleafSender._test_sender(
        destination="127.0.0.1", port=60222, version=1, panel_ids=(7,), mode="capture"
    )
    candidate = NanoleafSender._test_sender(
        destination="127.0.0.2", port=60222, version=1, panel_ids=(7,), mode="capture"
    )
    device._sender, device._destination, device._online = original, "127.0.0.1", True
    generation = device._generation
    try:
        with (
            patch.object(device, "_virtuals_objs", list[object]()),
            patch("ledfx.devices.nanoleaf.NanoleafSender", return_value=candidate),
            patch(
                "ledfx.devices.nanoleaf.requests.put",
                return_value=SimpleNamespace(status_code=status),
            ),
            patch(
                "ledfx.devices.nanoleaf.resolve_destination", return_value="127.0.0.2"
            ),
            pytest.raises(OSError, match="activation"),
        ):
            if replacement == "config":
                device.update_config({"ip_address": "127.0.0.2"})
            else:
                await device.resolve_address()
        assert candidate.closed and not original.closed
        assert device._sender is original and device._destination == "127.0.0.1"
        assert device.config.ip_address == "127.0.0.1" and device._online
        assert device._generation == generation
        device.flush(np.array([[17, 34, 51]]))
        assert original._engine.captures()[0][0] == bytes.fromhex("0107011122330001")
    finally:
        original.close()
        candidate.close()
