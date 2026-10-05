"""Art-Net adapter ownership and transactional replacement."""

import threading
from contextlib import AbstractContextManager
from unittest.mock import MagicMock, patch

import numpy as np
from ledfx_senders import ArtNetSender

from ledfx.devices.artnet import ArtNetDevice
from tests.native_sender_helpers import capture_packets, make_device


def test_busy_artnet_skips_without_layout_or_sender_mutation() -> None:
    device = make_device(ArtNetDevice, 4)
    original = device._sender
    for lock in [device.lock, device.device_lock]:
        entered, release = threading.Event(), threading.Event()

        def holder(
            owned: AbstractContextManager[object] = lock,
            started: threading.Event = entered,
            finish: threading.Event = release,
        ) -> None:
            with owned:
                started.set()
                assert finish.wait(3)

        worker = threading.Thread(target=holder)
        worker.start()
        assert entered.wait(3)
        try:
            device.flush(np.ones((4, 3)))
            assert device._sender is original
            assert capture_packets(device) == []
        finally:
            release.set()
            worker.join(3)
        assert not worker.is_alive()
    device.flush(np.ones((4, 3)))
    assert len(capture_packets(device)) == 1
    assert isinstance(device._sender, ArtNetSender)
    device._sender.close(False)


def test_artnet_callback_can_take_ownership_after_config_publication() -> None:
    ledfx = MagicMock()
    device = ArtNetDevice(
        ledfx,
        ArtNetDevice.Config.model_validate(
            {"name": "test", "ip_address": "127.0.0.1", "pixel_count": 4}
        ),
    )
    virtual = MagicMock()
    virtual.is_device = device.id
    ledfx.virtuals = {"test": virtual}
    done = threading.Event()

    def callback(*args: object) -> None:
        def owner() -> None:
            with device.lock, device.device_lock:
                done.set()

        worker = threading.Thread(target=owner)
        worker.start()
        assert done.wait(2)
        worker.join(2)

    virtual.update_segments.side_effect = callback
    with patch.object(device, "_virtuals_objs", list[object]()):
        device.update_config({"name": "new name"})
    assert done.is_set()


async def test_artnet_dns_transaction_success_stale_and_failure() -> None:
    """Use real native constructors; only inject the failed candidate call."""
    import asyncio
    from concurrent.futures import ThreadPoolExecutor

    import pytest

    core = MagicMock()
    core.loop = asyncio.get_running_loop()
    device = ArtNetDevice(
        core,
        ArtNetDevice.Config.model_validate(
            {"name": "dns", "ip_address": "127.0.0.1", "pixel_count": 4}
        ),
    )
    device._destination = "127.0.0.1"
    device.activate()
    old = device._sender
    old_generation = device._generation
    old_online = device._online
    try:
        with (
            patch(
                "ledfx.devices.native_packet.resolve_destination",
                return_value="127.0.0.2",
            ),
            patch.object(
                device, "_make_sender", side_effect=OSError("candidate failed")
            ),
            pytest.raises(OSError, match="candidate failed"),
        ):
            await device.resolve_address()
        assert device._destination == "127.0.0.1"
        assert device._online == old_online
        assert device._sender is old and old is not None and not old.closed
        assert device._generation == old_generation
        callback = MagicMock()

        def check_published() -> None:
            def take_lock() -> None:
                with device.device_lock:
                    assert device._destination == "127.0.0.2"

            with ThreadPoolExecutor(1) as pool:
                pool.submit(take_lock).result(timeout=2)

        callback.side_effect = check_published
        with patch(
            "ledfx.devices.native_packet.resolve_destination", return_value="127.0.0.2"
        ):
            await device.resolve_address(callback)
        assert old.closed and device._sender is not old
        callback.assert_called_once()
        current = device._sender
        with (
            patch(
                "ledfx.devices.native_packet.resolve_destination",
                return_value="127.0.0.3",
            ),
            patch.object(device, "_make_sender") as construct,
        ):
            await device._resolve(device.config.ip_address, old_generation, callback)
        construct.assert_not_called()
        assert device._destination == "127.0.0.2" and device._sender is current
        callback.assert_called_once()
    finally:
        if device._sender is not None:
            assert isinstance(device._sender, ArtNetSender)
            device._sender.close(False)
        device._sender = None
        device.deactivate()
