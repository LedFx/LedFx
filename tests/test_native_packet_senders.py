"""Real LedFx adapter lifecycle plus independent local UDP wire checks."""

import asyncio
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from functools import partial
from typing import TypeVar
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from ledfx_senders import (
    DDPSender,
    OPCSender,
    OSCSender,
    UDPRealtimeSender,
)

from ledfx.devices import Device
from ledfx.devices.ddp import DDPDevice
from ledfx.devices.native_packet import NativePacketDevice
from ledfx.devices.open_pixel_control import OpenPixelControl
from ledfx.devices.osc import OSCServerDevice
from ledfx.devices.udp import UDPRealtimeDevice
from ledfx.devices.wled import WLEDDevice

TDevice = TypeVar(
    "TDevice", bound=DDPDevice | OpenPixelControl | OSCServerDevice | UDPRealtimeDevice
)


def device(cls: type[TDevice]) -> TDevice:
    core = MagicMock()
    core.virtuals = dict[str, object]()
    d = cls(
        core,
        cls.config_model().model_validate(
            {"name": "test", "ip_address": "127.0.0.1", "pixel_count": 1}
        ),
    )
    d._destination = "127.0.0.1"
    d._virtuals_objs = []
    return d


def make_capture(
    d: DDPDevice | OpenPixelControl | OSCServerDevice | UDPRealtimeDevice,
    destination: str,
):
    if isinstance(d, DDPDevice):
        return DDPSender._test_sender(
            d.pixel_count * 3,
            destination="127.0.0.1",
            mode="capture",
            destination_id=d.config.destination_id,
            port=d.config.port,
        )
    if isinstance(d, OSCServerDevice):
        return OSCSender._test_sender(
            destination=destination,
            pixel_count=d.pixel_count,
            path=d.config.path,
            send_type=d.config.send_type,
            starting_addr=d.config.starting_addr,
            mode="capture",
        )
    if isinstance(d, UDPRealtimeDevice):
        return UDPRealtimeSender._test_sender(
            destination=destination,
            pixel_count=d.pixel_count,
            packet_type=d.config.udp_packet_type,
            timeout=d.config.timeout,
            minimise_traffic=d.config.minimise_traffic,
            keepalive_interval=d._keepalive_interval(),
            mode="capture",
        )
    return OPCSender._test_sender(
        d.pixel_count, destination="127.0.0.1", mode="capture", channel=d.config.channel
    )


@pytest.mark.parametrize(
    "cls", [DDPDevice, OpenPixelControl, OSCServerDevice, UDPRealtimeDevice]
)
def test_transactional_replacement_and_close(
    cls: type[DDPDevice]
    | type[OpenPixelControl]
    | type[OSCServerDevice]
    | type[UDPRealtimeDevice],
) -> None:
    d = device(cls)
    with patch.object(d, "_make_sender", side_effect=partial(make_capture, d)):
        d.activate()
        old = d._sender
        assert old is not None
        assert old is not None and not hasattr(d, "_sock")
        d.flush(np.ones((1, 3)))
        d.update_config({"name": "renamed"})
        assert d._sender is old
        d.update_config({"pixel_count": 481})
        current = d._sender
        assert current is not None
        assert old.closed and current is not old
        assert d._pixels is not None
        assert d._pixels.shape == (481, 3)
        d.flush(np.ones((481, 3)))
        with (
            patch.object(d, "_make_sender", side_effect=OSError("bind failed")),
            pytest.raises(OSError),
        ):
            d.update_config({"pixel_count": 2})
        assert d._sender is current and not current.closed and d.pixel_count == 481
        d.deactivate()
        assert current.closed and d._sender is None
        d.deactivate()


@pytest.mark.parametrize(
    "cls", [DDPDevice, OpenPixelControl, OSCServerDevice, UDPRealtimeDevice]
)
def test_configuration_validation_preserves_live_sender(
    cls: type[DDPDevice]
    | type[OpenPixelControl]
    | type[OSCServerDevice]
    | type[UDPRealtimeDevice],
) -> None:
    d = device(cls)
    with patch.object(d, "_make_sender", side_effect=partial(make_capture, d)):
        d.activate()
        old = d._sender
        assert old is not None
        with pytest.raises(ValueError):
            d.update_config(
                {"pixel_count": 21835 if cls is OpenPixelControl else 2**32}
            )
        assert d._sender is old and not old.closed and d.pixel_count == 1
        d.deactivate()


@pytest.mark.parametrize(
    "cls", [DDPDevice, OpenPixelControl, OSCServerDevice, UDPRealtimeDevice]
)
async def test_pending_resolution_cannot_resurrect(
    cls: type[DDPDevice]
    | type[OpenPixelControl]
    | type[OSCServerDevice]
    | type[UDPRealtimeDevice],
) -> None:
    d = device(cls)
    d._destination = None
    d._ledfx.loop = asyncio.get_running_loop()
    entered, release = asyncio.Event(), asyncio.Event()

    async def resolve(*args: object) -> str:
        entered.set()
        await release.wait()
        return "127.0.0.1"

    with patch("ledfx.devices.native_packet.resolve_destination", side_effect=resolve):
        d.activate()
        await entered.wait()
        d.deactivate()
        release.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
    assert d._sender is None and d._destination is None and not d.is_active()


@pytest.mark.parametrize(
    "cls", [DDPDevice, OpenPixelControl, OSCServerDevice, UDPRealtimeDevice]
)
def test_virtual_callbacks_run_outside_ownership(
    cls: type[DDPDevice]
    | type[OpenPixelControl]
    | type[OSCServerDevice]
    | type[UDPRealtimeDevice],
) -> None:
    d = device(cls)
    callback = MagicMock()
    callback.is_device = d.id
    d._ledfx.virtuals = {"v": callback}

    def check(*args: object) -> None:
        with ThreadPoolExecutor(max_workers=1) as pool:
            acquired = pool.submit(d.device_lock.acquire, True, 1).result(timeout=2)
            assert acquired
            pool.submit(d.device_lock.release).result(timeout=2)

    callback.update_segments.side_effect = check
    d.update_config({"name": "changed"})
    callback.update_segments.assert_called_once()


def test_ddp_offline_and_recovery_events():
    d = device(DDPDevice)
    with patch.object(d, "_make_sender", side_effect=partial(make_capture, d)):
        d.activate()
        sender = d._sender
        with patch.object(sender, "send", side_effect=OSError("UDP failed")):
            d.flush(np.zeros((1, 3)))
            d.flush(np.zeros((1, 3)))
        assert not d.is_online() and d.connection_warning
        assert d._ledfx.events.fire_event.call_count == 1
        d.flush(np.zeros((1, 3)))
        assert d.is_online() and not d.connection_warning
        assert d._ledfx.events.fire_event.call_count == 2
        d.deactivate()


@pytest.mark.parametrize(
    "cls", [DDPDevice, OpenPixelControl, OSCServerDevice, UDPRealtimeDevice]
)
def test_close_waits_for_inflight_send(
    cls: type[DDPDevice]
    | type[OpenPixelControl]
    | type[OSCServerDevice]
    | type[UDPRealtimeDevice],
) -> None:
    d = device(cls)
    entered, release, closed = threading.Event(), threading.Event(), threading.Event()

    def send(_: object, **kwargs: object) -> None:
        entered.set()
        assert release.wait(3)

    with patch.object(d, "_make_sender", side_effect=partial(make_capture, d)):
        d.activate()
        old = d._sender
        assert old is not None
        with (
            patch.object(old, "send", side_effect=send),
            ThreadPoolExecutor(max_workers=2) as pool,
        ):
            inflight = pool.submit(d.flush, np.zeros((1, 3)))
            assert entered.wait(1)

            def close() -> None:
                d.deactivate()
                closed.set()

            closing = pool.submit(close)
            assert not closed.wait(0.05)
            release.set()
            inflight.result(timeout=2)
            closing.result(timeout=2)
        assert old.closed and closed.is_set()


def test_wled_delegates_to_native_ddp_loopback():
    core = MagicMock()
    d = WLEDDevice(
        core,
        WLEDDevice.config_model().model_validate(
            {
                "name": "wled",
                "ip_address": "127.0.0.1",
                "pixel_count": 481,
                "sync_mode": "DDP",
            }
        ),
    )
    d._destination = "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1)
        d.device_configs["DDP"]["port"] = receiver.getsockname()[1]
        d.activate()
        assert isinstance(d.subdevice, DDPDevice)
        assert not hasattr(d.subdevice, "_sock")
        d.flush(np.ones((481, 3)))
        first = receiver.recvfrom(65535)[0]
        final = receiver.recvfrom(65535)[0]
        assert first[:4] == bytes([0x40, 2, 11, 1]) and len(first) == 1450
        assert final[:4] == bytes([0x41, 2, 11, 1]) and final[4:8] == (1440).to_bytes(
            4, "big"
        )
        assert first[10:] + final[10:] == bytes([1]) * 1443
        sender = d.subdevice._sender
        assert sender is not None
        d.deactivate()
        assert sender.closed


def test_shared_base_is_not_registered():
    assert NativePacketDevice not in Device.registry().values()
    assert DDPDevice in Device.registry().values()
    assert OpenPixelControl in Device.registry().values()


def test_wled_udp_uses_native_sender_and_full_static_refresh() -> None:
    core = MagicMock()
    d = WLEDDevice(
        core,
        WLEDDevice.config_model().model_validate(
            {
                "name": "test",
                "ip_address": "127.0.0.1",
                "pixel_count": 978,
                "sync_mode": "UDP",
            }
        ),
    )
    d._destination = "127.0.0.1"
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(1)
        d.device_configs["UDP"]["port"] = receiver.getsockname()[1]
        with patch("ledfx.devices.udp.time.monotonic", return_value=0):
            d.activate()
            assert isinstance(d.subdevice, UDPRealtimeDevice)
            assert not hasattr(d.subdevice, "_sock")
            d.flush(np.ones((978, 3)))
        first = [receiver.recvfrom(65535)[0] for _ in range(2)]
        with patch("ledfx.devices.udp.time.monotonic", return_value=2):
            d.flush(np.ones((978, 3)))
        assert [receiver.recvfrom(65535)[0] for _ in range(2)] == first
        assert [int.from_bytes(p[2:4], "big") for p in first] == [0, 489]
        d.deactivate()


@pytest.mark.parametrize("cls", [OSCServerDevice, UDPRealtimeDevice])
async def test_native_stateful_resolved_destination_change(
    cls: type[OSCServerDevice] | type[UDPRealtimeDevice],
) -> None:
    d = device(cls)
    with patch.object(d, "_make_sender", side_effect=partial(make_capture, d)):
        d.activate()
        old = d._sender
        with patch(
            "ledfx.devices.native_packet.resolve_destination", return_value="127.0.0.2"
        ):
            await d.resolve_address()
        assert old is not None and old.closed and d._sender is not old
        assert d._destination == "127.0.0.2"
        d.deactivate()


@pytest.mark.parametrize(
    "mode", ["One_Argument", "Three_Arguments", "Three_Addresses", "All_To_One"]
)
def test_osc_validation_closes_public_sender_without_publishing(mode: str) -> None:
    d = device(OSCServerDevice)
    d._config = d.config.model_copy(update={"send_type": mode})
    public_factory = d._make_sender
    probes: list[OSCSender] = []

    def make_probe(destination: str) -> OSCSender:
        probe = public_factory(destination)
        probes.append(probe)
        return probe

    with (
        patch.object(d, "_make_sender", side_effect=make_probe),
        patch.object(OSCSender, "_test_sender", side_effect=AssertionError("test API")),
    ):
        d._validate_configuration()
    assert len(probes) == 1 and probes[0].closed
    assert d._sender is None and not d._requested


@pytest.mark.parametrize("path", ["missing-leading-slash", "/invalid\0path"])
def test_osc_invalid_native_path_preserves_live_sender(path: str) -> None:
    d = device(OSCServerDevice)
    d.activate()
    live = d._sender
    assert live is not None
    try:
        with pytest.raises(ValueError):
            d.update_config({"path": path})
        assert d._sender is live and not live.closed
        assert d.config.path == "/0/dmx/{address}"
    finally:
        d.deactivate()
    assert live.closed


def test_osc_output_paths_and_refresh_rate_reconfigure_native() -> None:
    d = device(OSCServerDevice)
    with patch.object(d, "_make_sender", side_effect=partial(make_capture, d)):
        d.activate()
        old = d._sender
        d.update_config({"path": "/new/{address:04d}", "starting_addr": 17})
        assert old is not None and old.closed
        d.flush(np.zeros((1, 3)))
        assert d._sender is not None
        assert d._sender._engine.captures()[0][0].startswith(b"/new/0017\0")
        d.deactivate()
    u = device(UDPRealtimeDevice)
    with patch.object(u, "_make_sender", side_effect=partial(make_capture, u)):
        u.activate()
        old = u._sender
        u.update_config({"refresh_rate": 30})
        assert old is not None and old.closed
        assert u._keepalive_interval() == 14 / 30
        u.deactivate()


@pytest.mark.parametrize(
    "change", [{"port": 9001}, {"path": "/other/{address}"}, {"starting_addr": 1}]
)
def test_actual_osc_coexistence_rules(change: dict[str, object]) -> None:
    from ledfx.devices import Devices

    registry = object.__new__(Devices)
    existing = device(OSCServerDevice)
    vars(existing)["_type"] = "osc"  # RegistryLoader sets this creation metadata.
    config = existing.config.model_dump()
    with pytest.raises(ValueError, match="Shares IP, Port, Path"):
        registry.run_device_ip_tests("osc", config, existing)
    config.update(change)
    registry.run_device_ip_tests("osc", config, existing)


@pytest.mark.parametrize(
    "cls", [DDPDevice, OpenPixelControl, OSCServerDevice, UDPRealtimeDevice]
)
async def test_resolved_candidate_failure_preserves_published_state(
    cls: type[TDevice],
) -> None:
    d = device(cls)
    with patch.object(d, "_make_sender", side_effect=partial(make_capture, d)):
        d.activate()
    old, generation, online = d._sender, d._generation, d._online
    callback = MagicMock()
    try:
        with (
            patch(
                "ledfx.devices.native_packet.resolve_destination",
                return_value="127.0.0.2",
            ),
            patch.object(d, "_make_sender", side_effect=OSError("candidate failed")),
            pytest.raises(OSError, match="candidate failed"),
        ):
            await d.resolve_address(callback)
        assert d._destination == "127.0.0.1" and d._online == online
        assert d._sender is old and old is not None and not old.closed
        assert d._generation == generation
        callback.assert_not_called()
    finally:
        d.deactivate()
