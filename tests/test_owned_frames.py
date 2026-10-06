"""Real physical snapshots and precise demanded logical source views."""

from __future__ import annotations

import asyncio
import base64
import threading
from _thread import LockType
from collections.abc import Callable, Iterator
from unittest.mock import MagicMock

import numpy as np
import pytest
from numpy.typing import NDArray
from typing_extensions import override

from ledfx.configuration.models import VirtualConfig, replace_model
from ledfx.devices import Device, Devices
from ledfx.devices.ddp import DDPDevice
from ledfx.devices.dummy import DummyDevice
from ledfx.devices.e131 import E131Device
from ledfx.devices.launchpad import LaunchpadDevice
from ledfx.devices.lifx import LifxDevice
from ledfx.devices.nanoleaf import NanoleafDevice
from ledfx.devices.utils.rgbw_conversion import OutputMode
from ledfx.devices.wled import WLEDDevice
from ledfx.effects import DummyEffect
from ledfx.effects.oneshots.oneshot import Flash
from ledfx.effects.temporal import TemporalEffect
from ledfx.events import (
    DeviceUpdateEvent,
    Event,
    Events,
    VirtualUpdateEvent,
    VisualisationUpdateEvent,
)
from ledfx.preview import OwnedFrame, PreviewSampler, PreviewSettings, SourceKey
from ledfx.virtuals import Virtual
from tests.test_preview_sampler import Scheduler
from tests.test_utilities.virtuals_core import add_virtual, cfg, running_core

_TEMPORAL_THREAD = TemporalEffect.thread_function
_RENDER_THREAD = Virtual.thread_function


class CapturingDevice(DummyDevice):
    @override
    def __init__(self, ledfx: MagicMock, config: int = 50) -> None:
        super().__init__(ledfx, self.Config(name="physical", pixel_count=config))
        self._id = "physical"
        self.sent: list[NDArray[np.generic]] = []

    @override
    def flush(self, data: NDArray[np.generic]) -> None:
        self.sent.append(data)


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    def no_effect_thread(effect: TemporalEffect) -> None:
        return

    monkeypatch.setattr(TemporalEffect, "thread_function", no_effect_thread)
    for core in running_core(monkeypatch):
        yield core
        for device in core.devices.values():
            device.deactivate()
        if isinstance(core.preview_sampler, PreviewSampler):
            core.preview_sampler.close()
        if isinstance(core.loop, Scheduler):
            core.loop.close()


class OwnedScheduler(Scheduler):
    def call_later(
        self, delay: float, callback: Callable[..., object], *args: object
    ) -> asyncio.TimerHandle:
        return self.call_at(self.now + delay, callback, *args)


def install_sampler(ledfx: MagicMock) -> Scheduler:
    loop = OwnedScheduler()
    ledfx.loop = loop
    ledfx.events = Events(ledfx)
    ledfx.preview_sampler = PreviewSampler(
        ledfx, PreviewSettings(60, 100, 0, "compressed"), clock=loop.time
    )
    return loop


def test_assemble_zero_offset_never_borrows_device_buffer(ledfx: MagicMock) -> None:
    device = CapturingDevice(ledfx, 4)
    device.activate()
    device._pixels = np.arange(12).reshape(4, 3)
    frame = device.assemble_frame()
    device._pixels[:] = 0
    np.testing.assert_array_equal(frame, np.arange(12).reshape(4, 3))
    assert not np.shares_memory(frame, device._pixels)


class HoldingDevice(CapturingDevice):
    @override
    def __init__(self, ledfx: MagicMock, config: int = 50) -> None:
        super().__init__(ledfx, config)
        self.entered = threading.Event()
        self.release = threading.Event()

    @override
    def flush(self, data: NDArray[np.generic]) -> None:
        super().flush(data)
        if len(self.sent) == 1:
            self.entered.set()
            assert self.release.wait(5), "held sender was not released"


def add_physical(ledfx: MagicMock, *, hold: bool = False) -> CapturingDevice:
    device = HoldingDevice(ledfx) if hold else CapturingDevice(ledfx)
    ledfx.devices._objects[device.id] = device
    device.activate()
    return device


def attach(
    ledfx: MagicMock,
    virtual_id: str,
    start: int,
    end: int,
    *,
    invert: bool = False,
    primary: bool = False,
) -> Virtual:
    virtual = add_virtual(
        ledfx,
        virtual_id,
        virtual_id,
        [["physical", start, end, invert]],
        is_device="physical" if primary else False,
    )
    virtual._active = True
    virtual.activate_segments(virtual.segments)
    return virtual


def collect_previews(
    ledfx: MagicMock, **filters: object
) -> list[VisualisationUpdateEvent]:
    delivered: list[VisualisationUpdateEvent] = []

    def collect(event: Event) -> None:
        assert isinstance(event, VisualisationUpdateEvent)
        delivered.append(event)

    ledfx.events.add_listener(collect, Event.VISUALISATION_UPDATE, filters)
    return delivered


def decoded(event: VisualisationUpdateEvent) -> NDArray[np.uint8]:
    assert isinstance(event.pixels, str)
    return np.frombuffer(base64.b64decode(event.pixels), dtype=np.uint8).reshape(-1, 3)


def test_two_writers_keep_owned_ordered_untorn_snapshots(ledfx: MagicMock) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx, hold=True)
    assert isinstance(device, HoldingDevice)
    front = attach(ledfx, "front", 0, 24)
    back = attach(ledfx, "back", 25, 49)
    previews = collect_previews(ledfx, is_device=True)
    device.update_pixels(back.id, [(np.full((25, 3), 17), 25, 49)])
    first = threading.Thread(
        target=device.update_pixels,
        args=(front.id, [(np.full((25, 3), 33), 0, 24)]),
    )
    first.start()
    assert device.entered.wait(5)
    # The retained sender snapshot survives a concurrent nonpriority write.
    contributed = threading.Event()

    def contribute() -> None:
        device.update_pixels(back.id, [(np.full((25, 3), 77), 25, 49)])
        contributed.set()

    writer = threading.Thread(target=contribute)
    writer.start()
    assert contributed.wait(5), "nonpriority writer waited for sender IO"
    writer.join(5)
    second = threading.Thread(
        target=device.update_pixels,
        args=(front.id, [(np.full((25, 3), 99), 0, 24)]),
    )
    second.start()
    assert len(device.sent) == 1
    np.testing.assert_array_equal(device.sent[0][:25], np.full((25, 3), 33))
    np.testing.assert_array_equal(device.sent[0][25:], np.full((25, 3), 17))
    device.release.set()
    first.join(5)
    second.join(5)
    assert not first.is_alive() and not second.is_alive()
    assert len(device.sent) == 2
    np.testing.assert_array_equal(device.sent[1][:25], np.full((25, 3), 99))
    np.testing.assert_array_equal(device.sent[1][25:], np.full((25, 3), 77))
    loop.drain()
    assert len(previews) == 1
    np.testing.assert_array_equal(decoded(previews[0]), device.sent[1])


@pytest.mark.parametrize("offset", [0, 3, -4])
def test_physical_primary_rows_offset_raw_and_full_black(
    ledfx: MagicMock,
    offset: int,
) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx)
    virtual = attach(ledfx, "primary-other", 0, 49, primary=True)
    virtual.rows = 5
    device.update_config({"center_offset": offset})
    previews = collect_previews(ledfx, is_device=True, vis_id="physical")
    raw: list[DeviceUpdateEvent] = []

    def collect(event: Event) -> None:
        assert isinstance(event, DeviceUpdateEvent)
        raw.append(event)

    ledfx.events.add_listener(collect, Event.DEVICE_UPDATE, {"device_id": "physical"})
    pixels = np.arange(150).reshape(50, 3)
    device.update_pixels(virtual.id, [(pixels, 0, 49)])
    pixels[:] = 0
    loop.drain()
    expected = np.roll(np.arange(150).reshape(50, 3), offset, axis=0)
    np.testing.assert_array_equal(device.sent[0], expected)
    assert previews[0].shape == (5, 10)
    np.testing.assert_array_equal(decoded(previews[0]), expected)
    assert raw[0].pixels is device.sent[0]
    device.submit_final_black()
    np.testing.assert_array_equal(device.sent[1], np.zeros((50, 3)))
    np.testing.assert_array_equal(device.sent[0], expected)
    loop.advance(loop.now + 1 / 60)
    np.testing.assert_array_equal(decoded(previews[-1]), np.zeros((50, 3)))
    assert len(raw) == 2


def render_once(virtual: Virtual) -> None:
    virtual._render_frame()


@pytest.mark.parametrize("mapping", ["span", "copy"])
@pytest.mark.parametrize("grouping", [1, 3])
def test_real_effect_grouping_logical_and_reversed_physical_rgb(
    ledfx: MagicMock,
    mapping: str,
    grouping: int,
) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 6, invert=True)
    virtual.update_config(
        {
            "grouping": grouping,
            "mapping": mapping,
            "rows": 2,
            "transition_mode": "None",
            "transition_time": 0,
        }
    )
    effect = ledfx.effects.create(
        "singleColor", ledfx=ledfx, config=cfg({"color": "#112233"})
    )
    virtual.set_effect(effect)
    effect.pixels[:] = np.arange(virtual.effective_pixel_count * 3).reshape(-1, 3)
    previews = collect_previews(ledfx)
    # Real get_pixels owns its copy; the temporal thread is disabled so this
    # distinct RGB pattern also tests group truncation and reverse mapping.
    render_once(virtual)
    loop.drain()
    logical = next(e for e in previews if not e.is_device)
    expected = np.repeat(
        np.arange(virtual.effective_pixel_count * 3).reshape(-1, 3),
        grouping,
        axis=0,
    )[:7]
    np.testing.assert_array_equal(decoded(logical), expected)
    # Existing irregular geometry advertises (2, 3) while retaining all seven
    # RGB pixels when below maxlen; preserve that established behavior.
    assert logical.shape == (2, 3)
    physical_expected = expected[::-1]
    if mapping == "copy":
        physical_expected = np.repeat(
            np.arange(virtual.effective_pixel_count * 3).reshape(-1, 3)[::-1],
            grouping,
            axis=0,
        )[:7]
    np.testing.assert_array_equal(device.sent[-1][:7], physical_expected)
    assert logical.vis_id == "logical"


def test_mirror_front_back_and_physical_are_distinct_rgb_views(
    ledfx: MagicMock,
) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx)
    front = attach(ledfx, "mirror-front", 0, 24)
    back = attach(ledfx, "mirror-back", 25, 49, invert=True)
    previews = collect_previews(ledfx)
    front_pixels = np.arange(75).reshape(25, 3)
    back_pixels = np.arange(75, 150).reshape(25, 3)
    back.flush(back_pixels)
    back._submit_preview_frame(back_pixels, owned=False)
    front.flush(front_pixels)
    front._submit_preview_frame(front_pixels, owned=False)
    front_pixels[:] = 0
    back_pixels[:] = 0
    loop.drain()
    by_source = {(e.is_device, e.vis_id): decoded(e) for e in previews}
    np.testing.assert_array_equal(
        by_source[False, front.id], np.arange(75).reshape(25, 3)
    )
    np.testing.assert_array_equal(
        by_source[False, back.id], np.arange(75, 150).reshape(25, 3)
    )
    np.testing.assert_array_equal(
        by_source[True, device.id],
        np.concatenate(
            (np.arange(75).reshape(25, 3), np.arange(75, 150).reshape(25, 3)[::-1])
        ),
    )


@pytest.mark.parametrize("demand", ["none", "disjoint", "raw"])
def test_virtual_demand_gates_extra_projection_copy_and_scheduling(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    demand: str,
) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    virtual.update_config({"preview_only": True, "grouping": 2})
    frames: list[VirtualUpdateEvent] = []

    def collect(event: Event) -> None:
        assert isinstance(event, VirtualUpdateEvent)
        frames.append(event)

    if demand == "raw":
        ledfx.events.add_listener(
            collect, Event.VIRTUAL_UPDATE, {"virtual_id": "logical"}
        )
    elif demand == "disjoint":
        collect_previews(ledfx, is_device=False, vis_id="other")
    calls: list[int] = []
    project = virtual._effective_to_physical_pixels

    def counted(
        pixels: NDArray[np.generic], pixel_count: int | None = None
    ) -> NDArray[np.generic]:
        calls.append(len(pixels))
        return project(pixels, pixel_count)

    monkeypatch.setattr(virtual, "_effective_to_physical_pixels", counted)
    wakes = loop.wakes
    pixels = np.arange(75).reshape(25, 3)
    virtual._submit_preview_frame(pixels, owned=False)
    pixels[:] = 0
    assert len(calls) == (1 if demand == "raw" else 0)
    assert loop.wakes - wakes == (1 if demand == "raw" else 0)
    loop.drain()
    assert device.sent == []
    if frames:
        np.testing.assert_array_equal(
            frames[0].pixels, np.repeat(np.arange(75).reshape(25, 3), 2, axis=0)
        )


@pytest.mark.parametrize(
    "mapping,complex_segments", [("span", False), ("copy", False), ("span", True)]
)
def test_normal_render_transfer_span_projection_reuse_dummy_transition_and_overlays(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    mapping: str,
    complex_segments: bool,
) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    virtual.update_config(
        {
            "transition_mode": "None",
            "transition_time": 0,
            "mapping": mapping,
            "complex_segments": complex_segments,
        }
    )
    previews = collect_previews(ledfx, is_device=False)
    effect = ledfx.effects.create(
        "singleColor", ledfx=ledfx, config=cfg({"color": "#102030"})
    )
    virtual.set_effect(effect)
    effect.effect_loop()
    render_once(virtual)
    sampler = ledfx.preview_sampler
    assert isinstance(sampler, PreviewSampler)
    pending = sampler._sources[SourceKey("virtual", virtual.id)].pending
    assert pending is not None and pending.pixels is virtual.assembled_frame
    loop.drain()
    expected = np.tile((16, 32, 48), (50, 1))
    np.testing.assert_array_equal(decoded(previews[-1]), expected)
    virtual._oneshots = [Flash((0, 0, 255), 0, 100000, 0, 1)]
    render_once(virtual)
    np.testing.assert_array_equal(device.sent[-1], np.tile((0, 0, 255), (50, 1)))
    loop.advance(loop.now + 1 / 60)
    np.testing.assert_array_equal(decoded(previews[-1]), expected)
    virtual.set_calibration(True)
    render_once(virtual)
    loop.advance(loop.now + 1 / 60)
    np.testing.assert_array_equal(decoded(previews[-1]), expected)
    assert not np.array_equal(device.sent[-1], expected)
    virtual._oneshots = []
    virtual.set_calibration(False)
    virtual._transition_effect = effect
    virtual._active_effect = DummyEffect(50)
    virtual.transition_frame_total = 2
    virtual.transition_frame_counter = 0
    virtual.frame_transitions = virtual.transitions["Add"]
    render_once(virtual)
    old_pixels = virtual.assembled_frame
    loop.advance(loop.now + 1 / 60)
    np.testing.assert_array_equal(decoded(previews[-1]), expected // 2)
    render_once(virtual)
    np.testing.assert_array_equal(old_pixels, expected / 2)
    loop.advance(loop.now + 1 / 60)
    np.testing.assert_array_equal(decoded(previews[-1]), np.zeros((50, 3)))


def test_force_preview_only_and_clear_pending_black(ledfx: MagicMock) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    previews = collect_previews(ledfx, is_device=False)
    virtual.force_frame((5, 6, 7))
    loop.drain()
    np.testing.assert_array_equal(decoded(previews[-1]), np.tile((5, 6, 7), (50, 1)))
    virtual.clear_frame()
    assert not virtual.active
    loop.advance(loop.now + 1 / 60)
    np.testing.assert_array_equal(decoded(previews[-1]), np.zeros((50, 3)))
    count = len(device.sent)
    virtual.update_config({"preview_only": True})
    virtual.force_frame((8, 9, 10))
    loop.drain()
    np.testing.assert_array_equal(decoded(previews[-1]), np.tile((8, 9, 10), (50, 1)))
    assert len(device.sent) == count


@pytest.mark.parametrize("action", ["resize", "recreate"])
def test_real_virtual_lifetime_rejects_held_old_encoding(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    loop = install_sampler(ledfx)
    add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    previews = collect_previews(ledfx, is_device=False)
    sampler = ledfx.preview_sampler
    assert isinstance(sampler, PreviewSampler)
    entered, release = threading.Event(), threading.Event()
    encode = sampler._encode

    def held(frame: OwnedFrame, settings: PreviewSettings) -> VisualisationUpdateEvent:
        if frame.source_generation == old:
            entered.set()
            assert release.wait(5)
        return encode(frame, settings)

    old = virtual._source_generation
    monkeypatch.setattr(sampler, "_encode", held)
    virtual.force_frame((1, 2, 3))
    consumer = threading.Thread(target=loop.drain)
    consumer.start()
    assert entered.wait(5)
    if action == "recreate":
        virtual.deactivate()
        ledfx.virtuals.destroy("logical")
        virtual = attach(ledfx, "logical", 0, 24)
    else:
        virtual.update_segments([["physical", 0, 24, False]])
    assert virtual._source_generation > old
    virtual.force_frame((7, 8, 9))
    release.set()
    consumer.join(5)
    assert not consumer.is_alive()
    loop.drain()
    assert len(previews) == 1
    np.testing.assert_array_equal(decoded(previews[0]), np.tile((7, 8, 9), (25, 1)))


def test_mutating_output_mode_owns_its_conversion(ledfx: MagicMock) -> None:
    device = CapturingDevice(ledfx)
    device.activate()
    assert device._pixels is not None
    device._pixels[:] = 37
    frame = device.assemble_frame()
    converted = OutputMode("GRB", "None").apply(frame)
    converted[:] = 0
    np.testing.assert_array_equal(frame, np.full((50, 3), 37))


def test_hardware_without_preview_demand_has_only_required_projection(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    virtual.update_config({"grouping": 2})
    pixels = np.arange(75).reshape(25, 3)
    calls: list[int] = []
    project = virtual._effective_to_physical_pixels

    def counted(
        value: NDArray[np.generic], pixel_count: int | None = None
    ) -> NDArray[np.generic]:
        calls.append(len(value))
        return project(value, pixel_count)

    monkeypatch.setattr(virtual, "_effective_to_physical_pixels", counted)
    virtual.flush(pixels)
    virtual._submit_preview_frame(pixels, owned=False)
    assert calls == [25]
    assert loop.wakes == 0
    expected = np.repeat(np.arange(75).reshape(25, 3), 2, axis=0)
    np.testing.assert_array_equal(device.sent[0], expected)
    pixels[:] = 0
    np.testing.assert_array_equal(device.sent[0], expected)
    assert ledfx.preview_sampler._sources == {}


@pytest.mark.parametrize("action", ["deactivate", "config"])
def test_delayed_physical_publication_rejects_invalidated_capture(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    action: str,
) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    previews = collect_previews(ledfx, is_device=True)
    entered, release = threading.Event(), threading.Event()
    publish = device._publish_captured_frame
    old = device._source_generation

    def held(
        pixels: NDArray[np.generic], rows: int, generation: int, sequence: int
    ) -> None:
        if generation == old:
            entered.set()
            assert release.wait(5)
        publish(pixels, rows, generation, sequence)

    monkeypatch.setattr(device, "_publish_captured_frame", held)
    worker = threading.Thread(
        target=device.update_pixels, args=(virtual.id, [(np.ones((50, 3)), 0, 49)])
    )
    worker.start()
    assert entered.wait(5)
    if action == "deactivate":
        device.deactivate()
    else:
        device.update_config({"center_offset": 1})
        device.update_pixels(virtual.id, [(np.full((50, 3), 7), 0, 49)])
    release.set()
    worker.join(5)
    assert not worker.is_alive()
    loop.drain()
    assert len(previews) == (0 if action == "deactivate" else 1)
    if previews:
        np.testing.assert_array_equal(decoded(previews[0]), np.full((50, 3), 7))


def acquire_from_worker(lock: threading.RLock | LockType) -> bool:
    acquired: list[bool] = []

    def attempt() -> None:
        success = lock.acquire(blocking=False)
        acquired.append(success)
        if success:
            lock.release()

    worker = threading.Thread(target=attempt)
    worker.start()
    worker.join(5)
    assert not worker.is_alive()
    return acquired == [True]


def test_device_config_hook_runs_without_frame_lock(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    device = add_physical(ledfx)
    called: list[bool] = []

    def hook(self: CapturingDevice, config: object) -> None:
        called.append(acquire_from_worker(self._frame_lock))
        assert not acquire_from_worker(self._output_lock)

    monkeypatch.setattr(CapturingDevice, "config_updated", hook)
    device.update_config({"pixel_count": 25})
    assert called == [True]
    assert device._pixels is not None and len(device._pixels) == 25


def test_actual_launchpad_flush_failure_reenters_teardown(ledfx: MagicMock) -> None:
    install_sampler(ledfx)
    device = LaunchpadDevice(ledfx, LaunchpadDevice.Config(name="pad", pixel_count=50))
    device._id = "physical"
    ledfx.devices._objects[device.id] = device
    virtual = add_virtual(ledfx, "logical", "logical", [["physical", 0, 49, False]])
    virtual._active = True
    device.lp = MagicMock()
    device.lp.flush.return_value = False
    Device.activate(device)
    device.add_segments_batch(virtual.id, [(0, 49)])
    worker = threading.Thread(
        target=device.update_pixels, args=(virtual.id, [(np.ones((50, 3)), 0, 49)])
    )
    worker.start()
    worker.join(5)
    assert not worker.is_alive(), "flush -> set_offline -> deactivate deadlocked"
    assert not device.is_active()
    assert device.lp is None


@pytest.mark.parametrize("kind", ["ddp", "e131", "wled", "nanoleaf"])
def test_real_sender_lifecycle_output_device_frame_lock_order(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    kind: str,
) -> None:
    classes: dict[str, type[DDPDevice | E131Device | WLEDDevice | NanoleafDevice]] = {
        "ddp": DDPDevice,
        "e131": E131Device,
        "wled": WLEDDevice,
        "nanoleaf": NanoleafDevice,
    }
    cls = classes[kind]
    device = cls(
        ledfx,
        cls.Config.model_validate(
            {"name": kind, "ip_address": "127.0.0.1", "pixel_count": 50}
        ),
    )
    device._id = kind
    device._destination = "127.0.0.1"
    observations: list[tuple[bool, bool, bool]] = []
    method = {
        "ddp": "_validate_configuration",
        "e131": "_layout",
        "wled": "setup_subdevice",
        "nanoleaf": "_replace_output",
    }[kind]
    original = getattr(device, method)

    def probe() -> object:
        observations.append(
            (
                acquire_from_worker(device._output_lock),
                acquire_from_worker(device.device_lock),
                acquire_from_worker(device._frame_lock),
            )
        )
        if kind == "nanoleaf":
            return None  # no physical Nanoleaf network discovery in this test
        return original()

    monkeypatch.setattr(device, method, probe)
    device.activate()
    device.deactivate()
    assert observations and all(item == (False, False, True) for item in observations)


@pytest.mark.parametrize("kind", ["virtual", "device"])
def test_actual_registry_recreation_allocates_global_source_generation(
    ledfx: MagicMock,
    kind: str,
) -> None:
    install_sampler(ledfx)
    if kind == "virtual":
        first = add_virtual(ledfx, "same", "same", [["strip", 0, 24, False]])
        old = first._source_generation
        ledfx.virtuals.destroy("same")
        successor = add_virtual(ledfx, "same", "same", [["strip", 0, 49, False]])
    else:
        registry = Devices(ledfx)
        first = registry.create(
            "dummy", "same", ledfx=ledfx, config={"name": "same", "pixel_count": 25}
        )
        assert first is not None
        old = first._source_generation
        registry.destroy("same")
        successor = registry.create(
            "dummy", "same", ledfx=ledfx, config={"name": "same", "pixel_count": 50}
        )
        assert successor is not None
    assert successor._source_generation > old > 0
    assert successor.pixel_count == 50


def test_closed_sampler_allows_real_layout_teardown_without_resurrection(
    ledfx: MagicMock,
) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    collect_previews(ledfx)
    virtual.force_frame((1, 2, 3))
    sampler = ledfx.preview_sampler
    assert isinstance(sampler, PreviewSampler)
    counter = sampler._source_generation
    sampler.close()
    virtual.deactivate()
    virtual.update_segments([["physical", 0, 24, False]])
    device.update_config({"pixel_count": 25})
    device.deactivate()
    assert sampler.allocate_source_generation(SourceKey("device", "physical")) == -1
    assert sampler._source_generation == counter
    assert sampler._live_generations == {} and sampler._sources == {}
    assert not sampler.interested(SourceKey("virtual", "logical"), -1)
    loop.drain()


@pytest.mark.parametrize("event_filter", [{}, {"virtual_id": "logical"}])
def test_raw_only_virtual_observers_receive_each_owned_rgb_frame(
    ledfx: MagicMock,
    event_filter: dict[str, object],
) -> None:
    loop = install_sampler(ledfx)
    add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    frames: list[VirtualUpdateEvent] = []

    def collect(event: Event) -> None:
        assert isinstance(event, VirtualUpdateEvent)
        frames.append(event)

    ledfx.events.add_listener(collect, Event.VIRTUAL_UPDATE, event_filter)
    pixels = np.ones((50, 3))
    for value in range(1, 4):
        pixels[:] = value
        virtual._submit_preview_frame(pixels, owned=False)
    pixels[:] = 0
    loop.drain()
    assert len(frames) == 3
    for value, event in enumerate(frames, 1):
        np.testing.assert_array_equal(event.pixels, np.full((50, 3), value))
        assert not np.shares_memory(event.pixels, pixels)
    assert ledfx.preview_sampler._sources == {}


def test_demanded_grouped_span_reuses_hardware_projection(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    loop = install_sampler(ledfx)
    add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    virtual.update_config({"grouping": 3})
    previews = collect_previews(ledfx, is_device=False)
    calls: list[int] = []
    project = virtual._effective_to_physical_pixels

    def counted(
        pixels: NDArray[np.generic], pixel_count: int | None = None
    ) -> NDArray[np.generic]:
        calls.append(len(pixels))
        return project(pixels, pixel_count)

    monkeypatch.setattr(virtual, "_effective_to_physical_pixels", counted)
    virtual.force_frame((12, 34, 56))
    assert calls == [17]
    sampler = ledfx.preview_sampler
    assert isinstance(sampler, PreviewSampler)
    pending = sampler._sources[SourceKey("virtual", virtual.id)].pending
    assert pending is not None and virtual._span_frame is not None
    assert pending.pixels is virtual._span_frame[1]
    loop.drain()
    np.testing.assert_array_equal(decoded(previews[0]), np.tile((12, 34, 56), (50, 1)))


def test_source_allocation_racing_close_never_resurrects_a_live_generation(
    ledfx: MagicMock,
) -> None:
    install_sampler(ledfx)
    sampler = ledfx.preview_sampler
    assert isinstance(sampler, PreviewSampler)
    barrier = threading.Barrier(2)
    generations: list[int] = []
    key = SourceKey("device", "racing")

    def allocate() -> None:
        barrier.wait(5)
        generations.append(sampler.allocate_source_generation(key))

    worker = threading.Thread(target=allocate)
    worker.start()
    barrier.wait(5)
    sampler.close()
    worker.join(5)
    assert not worker.is_alive()
    assert len(generations) == 1
    counter = sampler._source_generation
    assert sampler.allocate_source_generation(key) == -1
    assert sampler._source_generation == counter
    assert sampler._live_generations == {} and sampler._sources == {}
    assert not sampler.interested(key, generations[0])


@pytest.mark.parametrize("preview_only", [False, True])
def test_actual_render_loop_transfers_owned_rgb_and_respects_preview_only(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    preview_only: bool,
) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    virtual.update_config(
        {"preview_only": preview_only, "transition_mode": "None", "transition_time": 0}
    )
    previews = collect_previews(ledfx, is_device=False)
    effect = ledfx.effects.create(
        "singleColor", ledfx=ledfx, config=cfg({"color": "#102030"})
    )
    virtual.set_effect(effect)
    effect.effect_loop()

    def end_loop(delay: float) -> None:
        virtual._active = False

    monkeypatch.setattr("ledfx.virtuals.time.sleep", end_loop)
    _RENDER_THREAD(virtual)
    sampler = ledfx.preview_sampler
    assert isinstance(sampler, PreviewSampler)
    pending = sampler._sources[SourceKey("virtual", virtual.id)].pending
    assert pending is not None and pending.pixels is virtual.assembled_frame
    loop.drain()
    np.testing.assert_array_equal(decoded(previews[0]), np.tile((16, 32, 48), (50, 1)))
    assert len(device.sent) == (0 if preview_only else 1)
    if device.sent:
        np.testing.assert_array_equal(device.sent[0], np.tile((16, 32, 48), (50, 1)))


@pytest.mark.parametrize("change", ["reactivate", "config"])
def test_priority_admission_rejects_generation_changed_before_output_wait(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    install_sampler(ledfx)
    device = add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    checked = threading.Event()
    original = device._write_pixels

    class ObservedPriority:
        @property
        def id(self) -> str:
            checked.set()
            return virtual.id

    monkeypatch.setattr(device, "priority_virtual", ObservedPriority())
    with device._output_lock:
        worker = threading.Thread(
            target=device.update_pixels,
            args=(virtual.id, [(np.full((50, 3), 73), 0, 49)]),
        )
        worker.start()
        assert checked.wait(5)
        if change == "reactivate":
            device.deactivate()
            device.activate()
        else:
            device.update_config({"center_offset": 1})
        monkeypatch.setattr(device, "_write_pixels", original)
    worker.join(5)
    assert not worker.is_alive()
    assert device.sent == []
    assert device._pixels is not None
    np.testing.assert_array_equal(device._pixels, np.zeros((50, 3)))


def test_launchpad_teardown_waits_for_actual_held_flush(ledfx: MagicMock) -> None:
    install_sampler(ledfx)
    device = LaunchpadDevice(ledfx, LaunchpadDevice.Config(name="pad", pixel_count=50))
    device._id = "physical"
    entered, release, closed = threading.Event(), threading.Event(), threading.Event()
    calls: list[NDArray[np.generic]] = []

    class Pad:
        def flush(self, data: NDArray[np.generic], alpha: bool, diag: bool) -> bool:
            calls.append(data)
            if len(calls) == 1:
                entered.set()
                assert release.wait(5)
            return True

        def Close(self) -> None:
            closed.set()

    ledfx.devices._objects[device.id] = device
    virtual = add_virtual(ledfx, "logical", "logical", [["physical", 0, 49, False]])
    virtual._active = True
    device.lp = Pad()
    Device.activate(device)
    device.add_segments_batch(virtual.id, [(0, 49)])
    sender = threading.Thread(
        target=device.update_pixels, args=(virtual.id, [(np.full((50, 3), 73), 0, 49)])
    )
    sender.start()
    assert entered.wait(5)
    stopper = threading.Thread(target=device.deactivate)
    stopper.start()
    closed_during_send = closed.wait(0.1)
    calls_during_send = len(calls)
    release.set()
    sender.join(5)
    stopper.join(5)
    assert not sender.is_alive() and not stopper.is_alive()
    assert not closed_during_send, "pad closed while first flush still owned output"
    assert calls_during_send == 1
    assert closed.is_set() and device.lp is None


@pytest.mark.parametrize("operation", ["clear", "grouping", "transition"])
def test_actual_temporal_worker_join_and_sender_io_release_producing_lock(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    operation: str,
) -> None:
    install_sampler(ledfx)
    device = add_physical(ledfx)
    virtual = attach(ledfx, "logical", 0, 49)
    virtual.update_config({"transition_mode": "None", "transition_time": 0})
    monkeypatch.setattr(TemporalEffect, "thread_function", _TEMPORAL_THREAD)
    effect = ledfx.effects.create(
        "singleColor", ledfx=ledfx, config=cfg({"color": "#102030"})
    )
    virtual.set_effect(effect)
    real_worker = effect._thread
    assert isinstance(real_worker, threading.Thread) and real_worker.is_alive()
    join_observations: list[bool] = []
    io_observations: list[bool] = []
    original_join = threading.Thread.join
    original_flush = device.flush

    def join(thread: threading.Thread, timeout: float | None = None) -> None:
        if thread is real_worker:
            join_observations.append(acquire_from_worker(virtual.lock))
        original_join(thread, timeout)

    def flush(data: NDArray[np.generic]) -> None:
        io_observations.append(acquire_from_worker(virtual.lock))
        original_flush(data)

    monkeypatch.setattr(threading.Thread, "join", join)
    monkeypatch.setattr(device, "flush", flush)
    virtual.force_frame((1, 2, 3))
    if operation == "clear":
        virtual.clear_frame()
    elif operation == "grouping":
        virtual.update_config({"grouping": 2})
    else:
        virtual._transition_effect = effect
        virtual._active_effect = DummyEffect(50)
        virtual.transition_frame_total = 1
        virtual.transition_frame_counter = 0
        virtual.frame_transitions = virtual.transitions["Add"]
        render_once(virtual)
    assert io_observations and all(io_observations)
    assert join_observations and all(join_observations)


def test_lifx_teardown_waits_for_actual_held_animator_send(ledfx: MagicMock) -> None:
    install_sampler(ledfx)
    device = LifxDevice(
        ledfx, LifxDevice.Config(name="lifx", ip_address="127.0.0.1", pixel_count=50)
    )
    device._id = "physical"
    ledfx.devices._objects[device.id] = device
    virtual = add_virtual(ledfx, "logical", "logical", [["physical", 0, 49, False]])
    virtual._active = True
    entered, release, closed = threading.Event(), threading.Event(), threading.Event()

    class Animator:
        pixel_count = 50

        def send_frame(self, data: list[tuple[int, int, int, int]]) -> None:
            entered.set()
            assert release.wait(5)

        def close(self) -> None:
            closed.set()

    device._animator = Animator()
    Device.activate(device)
    device.add_segments_batch(virtual.id, [(0, 49)])
    sender = threading.Thread(
        target=device.update_pixels, args=(virtual.id, [(np.full((50, 3), 73), 0, 49)])
    )
    sender.start()
    assert entered.wait(5)
    stopper = threading.Thread(target=device.deactivate)
    stopper.start()
    closed_during_send = closed.wait(0.1)
    release.set()
    sender.join(5)
    stopper.join(5)
    assert not sender.is_alive() and not stopper.is_alive()
    assert not closed_during_send and closed.is_set()
    assert device._animator is None


@pytest.mark.parametrize("change", ["config", "deactivate"])
def test_registration_rejects_source_superseded_during_forced_callback(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
    change: str,
) -> None:
    install_sampler(ledfx)
    device = add_physical(ledfx)
    owner = attach(ledfx, "owner", 0, 24)
    blocker = attach(ledfx, "blocker", 25, 49)
    callback_locks: list[bool] = []
    stop = blocker.deactivate

    def supersede() -> None:
        callback_locks.append(acquire_from_worker(owner._output_lock))
        callback_locks.append(acquire_from_worker(owner.lock))
        if change == "config":
            owner.update_config({"rows": 2})
        else:
            owner.deactivate()
        stop()

    monkeypatch.setattr(blocker, "deactivate", supersede)
    owner.activate_segments(
        [["physical", 0, 49, False]], source_generation=owner._source_generation
    )
    assert callback_locks == [True, True]
    assert (owner.id, 0, 49) not in device._segments


def test_simultaneous_forced_cross_owner_activation_completes(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_sampler(ledfx)
    device = add_physical(ledfx)
    front = attach(ledfx, "front", 0, 24)
    back = attach(ledfx, "back", 25, 49)
    barrier = threading.Barrier(2)
    observations: list[bool] = []
    originals = {front.id: front.deactivate, back.id: back.deactivate}

    def stop_front() -> None:
        observations.append(acquire_from_worker(back._output_lock))
        barrier.wait(5)
        originals[front.id]()

    def stop_back() -> None:
        observations.append(acquire_from_worker(front._output_lock))
        barrier.wait(5)
        originals[back.id]()

    monkeypatch.setattr(front, "deactivate", stop_front)
    monkeypatch.setattr(back, "deactivate", stop_back)
    workers = [
        threading.Thread(
            target=v.activate_segments,
            args=([["physical", 0, 49, False]],),
            kwargs={"source_generation": v._source_generation},
        )
        for v in (front, back)
    ]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join(5)
    assert all(not worker.is_alive() for worker in workers)
    assert observations == [True, True]
    assert not front.active and not back.active
    assert device._segments == []


@pytest.mark.parametrize("action", ["config", "delete"])
def test_held_virtual_output_leaves_producing_lock_free_and_orders_successor(
    ledfx: MagicMock,
    action: str,
) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx, hold=True)
    assert isinstance(device, HoldingDevice)
    virtual = attach(ledfx, "logical", 0, 49)
    previews = collect_previews(ledfx, is_device=False)
    sender = threading.Thread(target=virtual.force_frame, args=((73, 73, 73),))
    sender.start()
    assert device.entered.wait(5)
    assert acquire_from_worker(virtual.lock)
    completed = threading.Event()

    def change() -> None:
        if action == "config":
            virtual.update_config({"rows": 2, "grouping": 2})
        else:
            ledfx.virtuals.destroy(virtual.id)
        completed.set()

    successor = threading.Thread(target=change)
    successor.start()
    assert not completed.wait(0.1), "successor crossed already-claimed output"
    device.release.set()
    sender.join(5)
    successor.join(5)
    assert not sender.is_alive() and not successor.is_alive()
    loop.drain()
    assert previews == []  # source invalidation beats delayed preview consumption
    np.testing.assert_array_equal(device.sent[0], np.full((50, 3), 73))
    if action == "config":
        virtual.force_frame((7, 8, 9))
        loop.drain()
        assert previews[-1].shape == (2, 25)
        np.testing.assert_array_equal(
            decoded(previews[-1]), np.tile((7, 8, 9), (50, 1))
        )


def test_shared_transition_propagation_releases_source_owner_and_rejects_stale_config(
    ledfx: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    install_sampler(ledfx)
    add_physical(ledfx)
    source = attach(ledfx, "source", 0, 24)
    target = attach(ledfx, "target", 25, 49)
    source.frame_transitions = source.transitions["Add"]
    target.frame_transitions = target.transitions["Add"]
    ledfx.config.global_transitions = True
    propagate = source._share_transition
    observations: list[bool] = []
    before = target.config.transition_mode

    def delayed(config: VirtualConfig) -> None:
        observations.append(acquire_from_worker(source._output_lock))
        source.replace_config(replace_model(source.config, rows=2))
        propagate(config)

    monkeypatch.setattr(source, "_share_transition", delayed)
    source.update_config({"transition_mode": "Push"})
    assert observations == [True]
    assert target.config.transition_mode == before


def test_deleted_virtual_cannot_send_into_same_id_successor(ledfx: MagicMock) -> None:
    loop = install_sampler(ledfx)
    device = add_physical(ledfx)
    old = attach(ledfx, "logical", 0, 49)
    previews = collect_previews(ledfx, is_device=False)
    ledfx.virtuals.destroy(old.id)
    successor = attach(ledfx, "logical", 0, 49)
    successor.force_frame((7, 8, 9))
    count = len(device.sent)
    old.force_frame((73, 73, 73))
    loop.drain()
    assert len(device.sent) == count
    np.testing.assert_array_equal(decoded(previews[-1]), np.tile((7, 8, 9), (50, 1)))
