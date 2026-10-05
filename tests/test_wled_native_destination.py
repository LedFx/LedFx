"""WLED parent publication must retarget its immutable native child sender."""

import asyncio
import socket
import threading
from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from ledfx_senders import E131Sender
from ledfx_senders.e131 import ChannelLayout

from ledfx.devices.wled import WLEDDevice


def parent(mode: str) -> WLEDDevice:
    core = MagicMock()
    core.virtuals = dict[str, object]()
    device = WLEDDevice(
        core,
        WLEDDevice.Config.model_validate(
            {
                "name": "parent",
                "ip_address": "fixture.local",
                "pixel_count": 1,
                "sync_mode": mode,
            }
        ),
    )
    device._destination = "127.0.0.1"
    device._virtuals_objs = []
    return device


@pytest.mark.parametrize("mode", ["UDP", "DDP", "E131"])
async def test_parent_dns_replaces_sender_before_unlocked_callback(mode: str) -> None:
    device = parent(mode)
    with ExitStack() as stack:
        old_target = stack.enter_context(
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        )
        new_target = stack.enter_context(
            socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        )
        old_target.bind(("127.0.0.1", 0))
        port = old_target.getsockname()[1]
        new_target.bind(("127.0.0.2", port))
        old_target.settimeout(1)
        new_target.settimeout(1)
        if mode == "E131":

            def sender(
                layout: ChannelLayout,
                *,
                destination: str,
                source_name: str,
                priority: int,
            ) -> E131Sender:
                return E131Sender._test_sender(
                    layout,
                    destination=destination,
                    source_name=source_name,
                    priority=priority,
                    mode="socket",
                    override_destination=f"{destination}:{port}",
                )

            stack.enter_context(
                patch("ledfx.devices.e131.E131Sender", side_effect=sender)
            )
        else:
            device.device_configs[mode]["port"] = port
        device.activate()
        child = device.subdevice
        assert child is not None
        old = child._sender
        assert old is not None
        device.flush(np.ones((1, 3)))
        old_target.recvfrom(65535)

        def callback() -> None:
            assert device._destination == child._destination == "127.0.0.2"
            assert old.closed and child._sender is not old
            with ThreadPoolExecutor(max_workers=1) as pool:
                for lock in [device.device_lock, child.device_lock]:
                    assert pool.submit(lock.acquire, True, 1).result(timeout=2)
                    pool.submit(lock.release).result(timeout=2)

        with patch("ledfx.devices.resolve_destination", return_value="127.0.0.2"):
            await device.resolve_address(callback)
        device.flush(np.full((1, 3), 2))
        assert new_target.recvfrom(65535)[0]
        device.deactivate()


@pytest.mark.parametrize("mode", ["UDP", "DDP", "E131"])
async def test_parent_failed_candidate_keeps_endpoint_and_sender(mode: str) -> None:
    device = parent(mode)
    device.activate()
    child = device.subdevice
    assert child is not None
    old = child._sender
    assert old is not None
    callback = MagicMock()
    with (
        patch("ledfx.devices.resolve_destination", return_value="127.0.0.2"),
        patch.object(child, "activate", side_effect=OSError("candidate failed")),
        pytest.raises(OSError),
    ):
        await device.resolve_address(callback)
    assert device._destination == child._destination == "127.0.0.1"
    assert child._sender is old and not old.closed
    callback.assert_not_called()
    device.deactivate()


@pytest.mark.parametrize("mode", ["UDP", "DDP", "E131"])
@pytest.mark.parametrize("change", ["deactivate", "replace"])
async def test_parent_stale_dns_cannot_publish_to_changed_lifecycle(
    mode: str, change: str
) -> None:
    device = parent(mode)
    device.activate()
    child = device.subdevice
    assert child is not None
    entered, release = asyncio.Event(), asyncio.Event()

    async def resolve(*args: object) -> str:
        entered.set()
        await release.wait()
        return "127.0.0.2"

    callback = MagicMock()
    with patch("ledfx.devices.resolve_destination", side_effect=resolve):
        pending = asyncio.create_task(device.resolve_address(callback))
        await entered.wait()
        if change == "deactivate":
            device.deactivate()
        else:
            device.update_config({"name": "replaced"})
            assert device.subdevice is not child
        release.set()
        await pending
    assert device._destination == "127.0.0.1"
    callback.assert_not_called()
    if change == "deactivate":
        assert child._sender is None
    else:
        assert device.subdevice is not None
        assert device.subdevice._destination == "127.0.0.1"
    device.deactivate()


@pytest.mark.parametrize("mode", ["UDP", "DDP", "E131"])
def test_parent_failed_reconfiguration_keeps_live_child(mode: str) -> None:
    device = parent(mode)
    device.activate()
    child = device.subdevice
    assert child is not None
    old = child._sender
    with (
        patch.object(type(child), "activate", side_effect=OSError("candidate failed")),
        pytest.raises(OSError),
    ):
        device.update_config({"pixel_count": 2})
    assert device.pixel_count == 1 and device.subdevice is child
    assert old is not None and child._sender is old and not old.closed
    assert device._destination == child._destination == "127.0.0.1"
    device.deactivate()


def test_parent_virtual_callbacks_run_outside_publication_lock() -> None:
    device = parent("UDP")
    device.activate()
    callback = MagicMock()
    callback.is_device = device.id
    device._ledfx.virtuals = {"v": callback}

    def check(*args: object) -> None:
        with ThreadPoolExecutor(max_workers=1) as pool:
            assert pool.submit(device.device_lock.acquire, True, 1).result(timeout=2)
            pool.submit(device.device_lock.release).result(timeout=2)

    callback.update_segments.side_effect = check
    device.update_config({"name": "renamed"})
    callback.update_segments.assert_called_once()
    device.deactivate()


@pytest.mark.parametrize("mode", ["UDP", "DDP", "E131"])
@pytest.mark.parametrize("operation", ["deactivate", "replace"])
def test_parent_replacement_waits_for_owned_flush(mode: str, operation: str) -> None:
    device = parent(mode)
    device.activate()
    child = device.subdevice
    assert child is not None
    old = child._sender
    assert old is not None
    entered, release, finished = threading.Event(), threading.Event(), threading.Event()

    def send(*args: object, **kwargs: object) -> None:
        entered.set()
        assert release.wait(3)

    def replace() -> None:
        if operation == "deactivate":
            device.deactivate()
        else:
            device.update_config({"name": "replacement"})
        finished.set()

    with (
        patch.object(old, "send", side_effect=send),
        ThreadPoolExecutor(max_workers=2) as pool,
    ):
        sending = pool.submit(device.flush, np.ones((1, 3)))
        assert entered.wait(1)
        replacing = pool.submit(replace)
        assert not finished.wait(0.05)
        release.set()
        sending.result(timeout=2)
        replacing.result(timeout=2)
    assert old.closed and finished.is_set()
    device.deactivate()
