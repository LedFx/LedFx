from unittest.mock import MagicMock, patch

import numpy as np
import pytest
from ledfx_senders import E131Sender, Frame
from ledfx_senders.e131 import ChannelLayout

from ledfx.devices.e131 import E131Device


def device() -> E131Device:
    core = MagicMock()
    core.virtuals = dict[str, object]()
    result = E131Device(
        core,
        E131Device.config_model().model_validate(
            {"name": "test", "ip_address": "multicast", "pixel_count": 1}
        ),
    )
    result._virtuals_objs = []
    return result


def capture(
    layout: ChannelLayout, *, destination: str, source_name: str, priority: int = 100
) -> E131Sender:
    return E131Sender._test_sender(
        layout,
        mode="capture",
        destination=destination,
        source_name=source_name,
        priority=priority,
    )


def test_multicast_activation_and_transactional_replacement():
    d = device()
    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        d.activate()
        old = d._sender
        assert old is not None
        assert d._pixels is not None
        assert d.is_active() and d._pixels.shape == (1, 3)
        d.flush(np.ones((1, 3)))
        d.update_config({"pixel_count": 171})
        assert old.closed and d._sender is not old
        d.flush(np.ones((171, 3)))
        current = d._sender
        assert current is not None
        with (
            patch("ledfx.devices.e131.E131Sender", side_effect=OSError("bind failed")),
            pytest.raises(OSError),
        ):
            d.update_config({"pixel_count": 2})
        assert d._sender is current and not current.closed
        assert d.pixel_count == 171
        assert getattr(d.config, "channel_count") == 513  # noqa: B009 - stored extra
        d.deactivate()
        assert current.closed and d._sender is None


@pytest.mark.parametrize(
    "change",
    [
        {"universe": 7},
        {"universe_size": 512},
        {"channel_offset": 513},
        {"packet_priority": 150},
        {"ip_address": "MULTICAST"},
    ],
)
def test_output_changes_replace_sender_and_cid(change: dict[str, object]) -> None:
    d = device()
    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        d.activate()
        old = d._sender
        assert old is not None
        d.flush(np.ones((1, 3)))
        old_cid = old._engine.captures()[0][0][22:38]
        d.update_config(change)
        new = d._sender
        assert new is not None
        assert old.closed and new is not old
        d.flush(np.ones((1, 3)))
        assert new._engine.captures()[0][0][22:38] != old_cid
        d.deactivate()


async def test_unresolved_reconfiguration_and_deactivation_cannot_resurrect():
    import asyncio

    d = device()
    d.update_config({"ip_address": "first.invalid"})
    d._ledfx.loop = asyncio.get_running_loop()
    started = asyncio.Event()
    release = asyncio.Event()

    async def resolve(*args: object) -> str:
        started.set()
        await release.wait()
        return "127.0.0.1"

    with (
        patch("ledfx.devices.e131.resolve_destination", side_effect=resolve),
        patch("ledfx.devices.e131.E131Sender", side_effect=capture) as factory,
    ):
        d.activate()
        await started.wait()
        d.update_config({"pixel_count": 171, "ip_address": "second.invalid"})
        d.deactivate()
        release.set()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert d._sender is None and not d.is_active()
        assert d._destination is None
        factory.assert_not_called()


async def test_unresolved_layout_change_activates_latest_layout():
    import asyncio
    from unittest.mock import AsyncMock

    d = device()
    d.update_config({"ip_address": "test.invalid"})
    d._ledfx.loop = asyncio.get_running_loop()
    with (
        patch(
            "ledfx.devices.e131.resolve_destination",
            new=AsyncMock(return_value="127.0.0.1"),
        ),
        patch("ledfx.devices.e131.E131Sender", side_effect=capture),
    ):
        d.activate()
        d.update_config({"pixel_count": 171})
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert d.is_active()
        assert d._sender is not None
        assert d._sender.layout.channel_count == 513
        assert d._pixels is not None
        assert d._pixels.shape == (171, 3)
        d.deactivate()
        await asyncio.sleep(0)


def test_stale_maintenance_start_cannot_cancel_replacement():
    d = device()
    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        d.activate()
        old, generation = d._sender, d._generation
        d.update_config({"pixel_count": 2})
        current = d._sender
        assert current is not None
        task = MagicMock()
        with patch.object(d, "_maintenance_task", task):
            d._start_maintenance(old, generation)
            assert d._maintenance_task is task
            task.cancel.assert_not_called()
        d.deactivate()


async def test_maintenance_awaits_executor_and_stale_work_keeps_old_identity():
    import asyncio
    import threading
    from concurrent.futures import ThreadPoolExecutor

    d = device()
    d._ledfx.loop = asyncio.get_running_loop()
    with (
        ThreadPoolExecutor(max_workers=2) as executor,
        patch("ledfx.devices.e131.E131Sender", side_effect=capture),
    ):
        d._ledfx.thread_executor = executor
        d.activate()
        old = d._sender
        assert old is not None
        started, release = threading.Event(), threading.Event()
        calls = []

        def service(now: float | None = None) -> None:
            calls.append(old)
            started.set()
            assert release.wait(3)
            old_service()

        old_service = old.service
        old.service = service
        await asyncio.wait_for(asyncio.to_thread(started.wait), 2)
        await asyncio.sleep(0.3)
        assert calls == [old]
        d.update_config({"pixel_count": 2})
        new = d._sender
        assert new is not None
        assert old.closed and not new.closed
        with patch.object(new, "service", wraps=new.service) as new_service:
            await asyncio.sleep(0.3)
            new_service.assert_not_called()
        release.set()
        await asyncio.sleep(0)
        assert calls == [old]
        d.deactivate()
        await asyncio.sleep(0)


def test_flush_config_deactivate_contention_preserves_ownership():
    import threading
    from concurrent.futures import ThreadPoolExecutor

    d = device()
    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        d.activate()
        old = d._sender
        assert old is not None
        started, release = threading.Event(), threading.Event()
        send = old.send

        def blocked_send(frame: Frame) -> None:
            started.set()
            assert release.wait(3)
            send(frame)

        old.send = blocked_send
        with ThreadPoolExecutor(max_workers=3) as executor:
            flushing = executor.submit(d.flush, np.ones((1, 3)))
            assert started.wait(2)
            updating = executor.submit(d.update_config, {"pixel_count": 2})
            stopping = executor.submit(d.deactivate)
            assert d._sender is old and not old.closed
            release.set()
            for future in (flushing, updating, stopping):
                future.result(timeout=3)
        assert old.closed and d._sender is None and not d.is_active()


@pytest.mark.parametrize("kind", [bytes, bytearray, memoryview])
def test_byte_frames_and_stale_frame_drop(
    kind: type[bytes] | type[bytearray] | type[memoryview],
) -> None:
    d = device()
    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        d.activate()
        sender = d._sender
        assert sender is not None
        d.flush(kind(bytes([10, 20, 30])))
        assert sender._engine.captures()[0][0][126:129] == bytes([10, 20, 30])
        count = len(sender._engine.captures())
        d.flush(kind(bytes(6)))
        assert len(sender._engine.captures()) == count
        d.deactivate()


def test_real_adapter_loopback_captures_all_control_destinations():
    import socket

    d = device()
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as receiver:
        receiver.bind(("127.0.0.1", 0))
        receiver.settimeout(2)
        destination = f"127.0.0.1:{receiver.getsockname()[1]}"

        def socket_sender(
            layout: ChannelLayout,
            *,
            destination: str,
            source_name: str,
            priority: int = 100,
        ) -> E131Sender:
            return E131Sender._test_sender(
                layout,
                destination=destination,
                source_name=source_name,
                priority=priority,
                mode="socket",
                override_destination=override,
            )

        override = destination
        with patch("ledfx.devices.e131.E131Sender", side_effect=socket_sender):
            d.activate()
            d.flush(bytes([9, 8, 7]))
            data = receiver.recv(2048)
            sync = receiver.recv(2048)
            assert data[126:129] == bytes([9, 8, 7])
            assert len(sync) == 49
            assert d._sender is not None
            d._sender.service()
            assert len(receiver.recv(2048)) == 122
            d.deactivate()
            assert not d.is_active()


def test_deactivate_after_loop_close_still_releases_sender():
    d = device()
    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        d.activate()
        sender = d._sender
        assert sender is not None
        d._ledfx.loop.call_soon_threadsafe.side_effect = RuntimeError(
            "Event loop is closed"
        )
        d.deactivate()
        assert sender.closed and d._sender is None and not d.is_active()


async def test_resolution_failure_marks_current_device_offline():
    from unittest.mock import AsyncMock

    d = device()
    d.update_config({"ip_address": "invalid.example"})
    with patch(
        "ledfx.devices.e131.resolve_destination",
        new=AsyncMock(side_effect=ValueError("DNS failed")),
    ):
        await d.resolve_address()
    assert not d.is_online() and d._destination is None


def test_attached_virtual_render_and_config_callbacks_do_not_invert_locks():
    import threading
    from concurrent.futures import ThreadPoolExecutor
    from types import TracebackType

    from ledfx.configuration.models import VirtualConfig
    from ledfx.virtuals import Virtual

    d = device()
    d.__dict__["_id"] = "device"
    virtual = Virtual(d._ledfx, VirtualConfig.model_validate({"name": "attached"}))
    virtual.__dict__["_id"] = "attached"
    virtual.is_device = d.id
    virtual._segments = [[d.id, 0, 0, False]]
    d._ledfx.devices.get.return_value = d
    d._ledfx.config_store.virtual_entry.return_value = None
    d._ledfx.virtuals = MagicMock()
    d._ledfx.virtuals.__iter__.return_value = (virtual.id,)
    d._ledfx.virtuals.get.return_value = virtual
    rendering, callback = threading.Event(), threading.Event()

    class BoundedLock:
        def __init__(self) -> None:
            self.lock = threading.Lock()

        def __enter__(self) -> None:
            assert self.lock.acquire(timeout=2), "configuration/render lock cycle"

        def __exit__(
            self,
            exc_type: type[BaseException] | None,
            exc: BaseException | None,
            traceback: TracebackType | None,
        ) -> None:
            self.lock.release()

    lock = BoundedLock()
    original_update = virtual.update_segments

    def update(segments: list[list[object]]) -> None:
        callback.set()
        original_update(segments)

    def render() -> None:
        with lock:
            rendering.set()
            assert callback.wait(2)
            d.flush(bytes(3))

    with (
        patch.object(virtual, "lock", lock),
        patch.object(virtual, "update_segments", side_effect=update),
        patch("ledfx.devices.e131.E131Sender", side_effect=capture),
        ThreadPoolExecutor(max_workers=2) as executor,
    ):
        d.activate()
        rendered = executor.submit(render)
        assert rendering.wait(2)
        configured = executor.submit(d.update_config, {"pixel_count": 2})
        configured.result(timeout=4)
        rendered.result(timeout=4)
        assert virtual.segments == [[d.id, 0, 1, False]]
        d.deactivate()


async def test_live_dns_replacement_retargets_wire_and_releases_callback_lock() -> None:
    from concurrent.futures import ThreadPoolExecutor

    d = device()
    d.update_config({"ip_address": "fixture.local"})
    d._destination = "127.0.0.1"
    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        d.activate()
        old = d._sender
        assert old is not None and d._pixels is not None
        d._pixels[:] = [17, 34, 51]
        pixels = d._pixels

        def callback() -> None:
            def acquire_and_check() -> None:
                assert d.device_lock.acquire(timeout=1), "callback retains ownership"
                try:
                    assert d._destination == "127.0.0.2"
                    assert d._sender is not old and old.closed
                finally:
                    d.device_lock.release()

            with ThreadPoolExecutor(max_workers=1) as executor:
                executor.submit(acquire_and_check).result(timeout=2)

        completed = MagicMock(side_effect=callback)
        try:
            with patch(
                "ledfx.devices.e131.resolve_destination", return_value="127.0.0.2"
            ):
                await d.resolve_address(completed)
            completed.assert_called_once()
            current = d._sender
            assert current is not None
            assert d._pixels is pixels
            np.testing.assert_array_equal(pixels, [[17, 34, 51]])
            d.flush(pixels)
            packet, destination = current._engine.captures()[0]
            assert destination == "127.0.0.2:5568"
            assert packet[126:129] == bytes([17, 34, 51])
        finally:
            d.deactivate()


@pytest.mark.parametrize("resolver", ["public", "scheduled"])
async def test_dns_failed_candidate_keeps_live_sender_and_metadata(
    resolver: str,
) -> None:
    d = device()
    d.update_config({"ip_address": "fixture.local"})
    d._destination = "127.0.0.1"
    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        d.activate()
    old = d._sender
    assert old is not None
    generation = d._generation
    d._online = False
    completed = MagicMock()
    try:
        with (
            patch("ledfx.devices.e131.resolve_destination", return_value="127.0.0.2"),
            patch(
                "ledfx.devices.e131.E131Sender", side_effect=OSError("candidate failed")
            ),
            pytest.raises(OSError, match="candidate failed"),
        ):
            if resolver == "public":
                await d.resolve_address(completed)
            else:
                await d._resolve(d.config.ip_address, generation, completed)
        completed.assert_not_called()
        assert d._destination == "127.0.0.1" and not d._online
        assert d._sender is old and not old.closed and d.is_active()
        assert d._generation == generation
        d.flush(bytes([17, 34, 51]))
        assert old._engine.captures()[0][1] == "127.0.0.1:5568"
    finally:
        d.deactivate()


async def test_unchanged_dns_preserves_live_sender_and_frame_buffer() -> None:
    d = device()
    d.update_config({"ip_address": "fixture.local"})
    d._destination = "127.0.0.1"
    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        d.activate()
    old, pixels, generation = d._sender, d._pixels, d._generation
    assert old is not None
    try:
        with (
            patch("ledfx.devices.e131.resolve_destination", return_value="127.0.0.1"),
            patch("ledfx.devices.e131.E131Sender") as constructor,
        ):
            await d.resolve_address()
        constructor.assert_not_called()
        assert d._sender is old and not old.closed
        assert d._pixels is pixels and d._generation == generation
    finally:
        d.deactivate()


async def test_inactive_dns_only_caches_endpoint_until_activation() -> None:
    d = device()
    d.update_config({"ip_address": "fixture.local"})
    with (
        patch("ledfx.devices.e131.resolve_destination", return_value="127.0.0.2"),
        patch("ledfx.devices.e131.E131Sender") as constructor,
    ):
        await d.resolve_address()
    constructor.assert_not_called()
    assert d._destination == "127.0.0.2" and d.is_online()
    assert not d.is_active() and d._sender is None and not d._requested


async def test_public_dns_stale_completion_cannot_resurrect_deactivated_sender() -> (
    None
):
    d = device()
    d.update_config({"ip_address": "fixture.local"})
    d._destination = "127.0.0.1"
    with patch("ledfx.devices.e131.E131Sender", side_effect=capture):
        d.activate()
    old = d._sender
    assert old is not None

    async def resolve(*args: object) -> str:
        d.deactivate()
        return "127.0.0.2"

    completed = MagicMock()
    with (
        patch("ledfx.devices.e131.resolve_destination", side_effect=resolve),
        patch("ledfx.devices.e131.E131Sender") as constructor,
    ):
        await d.resolve_address(completed)
    constructor.assert_not_called()
    completed.assert_not_called()
    assert d._destination == "127.0.0.1" and d._sender is None
    assert old.closed and not d.is_active()
