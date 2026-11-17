"""Device frame composition: owned frames, a leaf frame lock, flush outside it."""

import asyncio
import sys
import threading
from collections.abc import Callable, Iterator
from types import SimpleNamespace

import numpy as np
import pytest
from ledfx_senders.frames import Frame
from typing_extensions import override

from ledfx.devices import Device
from tests import test_hue_native_lifecycle as hue_lifecycle
from tests.test_hue_native_lifecycle import (
    ControlledSender,
    HueFixture,
    idle,
    owned_virtual,
)
from tests.test_utilities.fake_ledfx import fake_ledfx

# Share the native Hue device fixture: pytest collects fixtures by module attribute.
hue_device = hue_lifecycle.hue_device

PIXELS = 4000
HALF = PIXELS // 2


@Device.no_registration
class FrameDevice(Device):
    """A device that records a snapshot of every flushed frame."""

    def __init__(self, pixel_count: int = PIXELS) -> None:
        ledfx = fake_ledfx()
        ledfx.preview_sampler.wants.return_value = False
        ledfx.events.has_listeners.return_value = False
        super().__init__(
            ledfx,
            Device.Config.model_validate(
                {"name": "frames", "pixel_count": pixel_count}
            ),
        )
        # The priority virtual is derived from registered virtuals; pin it.
        self.__dict__["priority_virtual"] = SimpleNamespace(id="a")
        self.flushed: list[np.ndarray] = []

    def flush(self, data: np.ndarray) -> None:
        self.flushed.append(data.copy())


def run(target: Callable[..., object], *args: object) -> threading.Thread:
    thread = threading.Thread(target=target, args=args, daemon=True)
    thread.start()
    return thread


def finish(*threads: threading.Thread) -> None:
    for thread in threads:
        thread.join(5)
        assert not thread.is_alive(), f"{thread.name} did not finish"


@pytest.fixture
def busy_switching() -> Iterator[None]:
    # Switch threads often so races show up within a few hundred iterations.
    interval = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)
    try:
        yield
    finally:
        sys.setswitchinterval(interval)


def test_assemble_zero_offset_never_borrows_device_buffer() -> None:
    device = FrameDevice(pixel_count=4)
    device.activate()
    device.update_pixels("a", [(np.ones((4, 3)), 0, 3)])
    frame = device.assemble_frame()
    assert frame is not None
    frame[:] = 9
    np.testing.assert_array_equal(device.assemble_frame(), np.ones((4, 3)))
    # The flushed frame is not the device buffer either.
    device.update_pixels("a", [(np.zeros((4, 3)), 0, 3)])
    np.testing.assert_array_equal(device.flushed[0], np.ones((4, 3)))


def test_two_writers_never_tear_a_flushed_frame(busy_switching: None) -> None:
    device = FrameDevice()
    device.activate()
    colours = [np.full((HALF, 3), 10.0), np.full((HALF, 3), 200.0)]
    errors: list[Exception] = []

    def write(virtual_id: str, start: int) -> None:
        try:
            for i in range(2000):
                device.update_pixels(
                    virtual_id, [(colours[i % 2], start, start + HALF - 1)]
                )
        except (TypeError, IndexError, ValueError) as error:
            errors.append(error)

    finish(run(write, "a", 0), run(write, "b", HALF))
    assert errors == []
    assert len(device.flushed) == 2000
    for frame in device.flushed:
        for segment in (frame[:HALF], frame[HALF:]):
            assert np.all(segment == segment[0, 0]), "a flushed segment was torn"


def test_deactivate_during_writes_never_raises(busy_switching: None) -> None:
    device = FrameDevice()
    device.activate()
    stop, progress = threading.Event(), threading.Event()
    errors: list[Exception] = []
    # Many small segments widen the window between the active check and writes.
    pixel = np.ones((1, 3))
    ranges = [(pixel, i, i) for i in range(1000)]
    scatter = [(pixel, np.array([i])) for i in range(1000)]

    def write() -> None:
        try:
            while not stop.is_set():
                device.update_pixels("a", ranges)
                device.update_pixels("a", scatter)
                progress.set()
        except (TypeError, IndexError, ValueError) as error:
            errors.append(error)
        finally:
            progress.set()  # never leave the toggling thread waiting

    writer = run(write)
    try:
        for _ in range(500):
            device.deactivate()
            # Let a whole write run while inactive, including one already past
            # the active check.
            progress.clear()
            assert progress.wait(5)
            device.activate()
            if errors:
                break
    finally:
        stop.set()
        finish(writer)
    assert errors == []


@Device.no_registration
class SenderLockDevice(FrameDevice):
    """A device whose sender lock is held around Device.deactivate, as Hue does."""

    def __init__(self) -> None:
        super().__init__(pixel_count=4)
        self.sender_lock = threading.Lock()
        self.in_flush = threading.Event()
        self.release_flush = threading.Event()
        self.holding_sender = threading.Event()

    @override
    def flush(self, data: np.ndarray) -> None:
        self.in_flush.set()
        assert self.release_flush.wait(5)
        with self.sender_lock:
            super().flush(data)

    @override
    def deactivate(self) -> None:
        with self.sender_lock:
            self.holding_sender.set()
            Device.deactivate(self)


def test_sender_lock_then_deactivate_during_blocked_flush() -> None:
    device = SenderLockDevice()
    device.activate()
    flusher = run(device.update_pixels, "a", [(np.ones((4, 3)), 0, 3)])
    assert device.in_flush.wait(5)
    deactivator = run(device.deactivate)
    try:
        assert device.holding_sender.wait(5)
        # Device.deactivate must not wait for the flush to return.
        finish(deactivator)
    finally:
        device.release_flush.set()
    finish(flusher)
    assert not device.is_active()
    assert len(device.flushed) == 1


async def test_hue_deactivate_during_blocked_flush_completes(
    hue_device: HueFixture, monkeypatch: pytest.MonkeyPatch
) -> None:
    sender = ControlledSender()
    hue_device.senders.append(sender)
    owned_virtual(hue_device, monkeypatch)
    await idle(hue_device)
    assert hue_device.is_active()
    in_send, release_send = threading.Event(), threading.Event()
    send = sender.send

    def blocking_send(frame: Frame) -> None:
        in_send.set()
        assert release_send.wait(5)
        send(frame)

    monkeypatch.setattr(sender, "send", blocking_send)
    flusher = run(hue_device.update_pixels, "owner", [(np.ones((2, 3)), 0, 1)])
    assert await asyncio.to_thread(in_send.wait, 5)
    deactivator = run(hue_device.deactivate)
    try:
        await asyncio.to_thread(deactivator.join, 5)
        assert not deactivator.is_alive(), "Hue deactivate waited on the flush"
    finally:
        release_send.set()
    await asyncio.to_thread(flusher.join, 5)
    assert not flusher.is_alive()
    await idle(hue_device)
    assert not hue_device.is_active()
    assert len(sender.sent) == 1


@Device.no_registration
class SlowActivateDevice(FrameDevice):
    """A device whose activate does blocking IO before the base activate."""

    def __init__(self) -> None:
        super().__init__(pixel_count=4)
        self.in_io = threading.Event()
        self.release_io = threading.Event()

    @override
    def activate(self) -> None:
        self.in_io.set()
        assert self.release_io.wait(5)
        super().activate()


def test_activate_io_holds_no_base_lock() -> None:
    device = SlowActivateDevice()
    device.release_io.set()
    device.activate()
    device.release_io.clear()
    device.in_io.clear()
    activator = run(device.activate)
    try:
        assert device.in_io.wait(5)
        writer = run(device.update_pixels, "a", [(np.ones((4, 3)), 0, 3)])
        finish(writer)
    finally:
        device.release_io.set()
    finish(activator)
    assert len(device.flushed) == 1
