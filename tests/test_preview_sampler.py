"""Owned preview samples retain latest RGB data on a monotonic cadence."""

from __future__ import annotations

import asyncio
import base64
import heapq
import threading
from collections import deque
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import numpy as np
import pytest
from numpy.typing import NDArray
from typing_extensions import override

from ledfx.configuration.models import LedFxConfig
from ledfx.configuration.store import ConfigStore
from ledfx.core import LedFxCore
from ledfx.events import BaseConfigUpdateEvent, Event, Events, VisualisationUpdateEvent
from ledfx.preview import OwnedFrame, PreviewSampler, PreviewSettings, SourceKey
from ledfx.utils import pixels_boost, resize_pixels, shape_to_fit_len


class Scheduler:
    """Defer real handles and advance deadlines independently of frame arrivals."""

    def __init__(self) -> None:
        self.now = 1000.0
        self.ready: deque[asyncio.Handle] = deque()
        self.timers: list[tuple[float, int, asyncio.TimerHandle]] = []
        self.wakes = 0
        self._order = 0
        self._loop = asyncio.new_event_loop()

    def time(self) -> float:
        return self.now

    def call_soon_threadsafe(
        self, callback: Callable[..., object], *args: object
    ) -> asyncio.Handle:
        handle = asyncio.Handle(callback, args, self._loop)
        self.ready.append(handle)
        self.wakes += 1
        return handle

    def call_at(
        self, when: float, callback: Callable[..., object], *args: object
    ) -> asyncio.TimerHandle:
        handle = asyncio.TimerHandle(when, callback, args, self._loop)
        self._order += 1
        heapq.heappush(self.timers, (when, self._order, handle))
        return handle

    def drain(self) -> None:
        while self.ready:
            handle = self.ready.popleft()
            if not handle.cancelled():
                handle._run()

    def advance(self, to: float) -> None:
        self.drain()
        while self.timers and self.timers[0][0] <= to:
            when, _, handle = heapq.heappop(self.timers)
            self.now = max(self.now, when)
            if not handle.cancelled():
                handle._run()
            self.drain()
        self.now = to
        self.drain()

    def close(self) -> None:
        self._loop.close()


@dataclass
class Core:
    loop: Scheduler
    events: Events = field(init=False)

    def __post_init__(self) -> None:
        self.events = Events(self)


@dataclass
class Harness:
    core: Core = field(default_factory=lambda: Core(Scheduler()))
    sampler: PreviewSampler = field(init=False)
    delivered: list[VisualisationUpdateEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.sampler = PreviewSampler(
            self.core,
            PreviewSettings(60, 100, 0, "compressed"),
            clock=self.core.loop.time,
        )

    def listen(
        self, event_filter: Mapping[str, object] | None = None
    ) -> Callable[[], None]:
        def collect(event: Event) -> None:
            assert isinstance(event, VisualisationUpdateEvent)
            self.delivered.append(event)

        dispose = self.core.events.add_listener(
            collect, Event.VISUALISATION_UPDATE, event_filter
        )
        self.core.loop.drain()
        return dispose

    def frame(
        self,
        key: SourceKey,
        generation: int,
        sequence: int,
        value: int = 1,
        *,
        rows: int = 1,
        pixels: NDArray[np.generic] | None = None,
    ) -> OwnedFrame:
        owned = np.full((2, 3), value, dtype=np.uint8) if pixels is None else pixels
        return OwnedFrame(
            key,
            generation,
            sequence,
            owned,
            rows,
            len(owned),
            self.sampler.settings_generation,
        )

    def close(self) -> None:
        self.sampler.close()
        self.core.loop.close()


@pytest.fixture
def harness() -> Iterator[Harness]:
    result = Harness()
    yield result
    result.close()


def rgb(event: VisualisationUpdateEvent) -> bytes:
    assert isinstance(event.pixels, str)
    return base64.b64decode(event.pixels)


def test_delayed_loop_encodes_only_newest_owned_frame(harness: Harness) -> None:
    harness.listen({"vis_id": "a"})
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    wakes = harness.core.loop.wakes
    for sequence in range(1000):
        harness.sampler.submit(harness.frame(key, generation, sequence, sequence % 256))
    state = harness.sampler._sources[key]
    assert state.pending is not None and state.pending.sequence == 999
    assert state.scheduled and state.pending.pixels.nbytes == 6
    assert harness.core.loop.wakes == wakes + 1
    assert sum(s.pending is not None for s in harness.sampler._sources.values()) == 1
    harness.core.loop.drain()
    assert len(harness.delivered) == 1
    assert rgb(harness.delivered[0]) == bytes([999 % 256] * 6)


@pytest.mark.parametrize("source_fps", [30, 60, 62, 100, 120])
def test_deadline_grid_rate_over_ten_seconds(harness: Harness, source_fps: int) -> None:
    harness.listen()
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    start = harness.core.loop.time()
    for sequence in range(source_fps * 10):
        harness.core.loop.advance(start + sequence / source_fps)
        harness.sampler.submit(harness.frame(key, generation, sequence, sequence % 256))
        harness.core.loop.drain()
    harness.core.loop.advance(start + 10)
    assert abs(len(harness.delivered) - min(source_fps, 60) * 10) <= 1
    assert rgb(harness.delivered[-1]) == bytes([(source_fps * 10 - 1) % 256] * 6)


def test_final_idle_black_delivered_at_due(harness: Harness) -> None:
    harness.listen()
    key = SourceKey("device", "a")
    generation = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, generation, 0, 200))
    harness.core.loop.drain()
    start = harness.core.loop.time()
    harness.core.loop.advance(start + 0.005)
    harness.sampler.submit(harness.frame(key, generation, 1, 0))
    harness.core.loop.drain()
    assert len(harness.delivered) == 1
    harness.core.loop.advance(start + 1 / 60)
    assert [rgb(event) for event in harness.delivered] == [bytes([200] * 6), bytes(6)]


def test_stall_skips_slots_without_catch_up_burst(harness: Harness) -> None:
    harness.listen()
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, generation, 0))
    harness.core.loop.drain()
    for sequence in range(1, 1000):
        harness.sampler.submit(harness.frame(key, generation, sequence, sequence % 256))
    harness.core.loop.now += 100
    harness.core.loop.advance(harness.core.loop.now)
    assert len(harness.delivered) == 2
    assert rgb(harness.delivered[-1]) == bytes([999 % 256] * 6)
    state = harness.sampler._sources[key]
    assert state.deadline is not None and state.deadline > harness.core.loop.time()
    harness.core.loop.advance(harness.core.loop.time() + 1)
    assert len(harness.delivered) == 2


@pytest.mark.parametrize(
    "event_filter",
    [
        {},
        {"vis_id": "a"},
        {"is_device": False},
        {"shape": [1, 2]},
        {"pixels": "AQEBAQEB"},
    ],
)
def test_all_real_registrations_are_conservative_demand(
    harness: Harness, event_filter: dict[str, object]
) -> None:
    harness.listen(event_filter)
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    assert harness.sampler.interested(key, generation)
    harness.sampler.submit(harness.frame(key, generation, 0))
    harness.core.loop.drain()
    assert len(harness.delivered) == 1


@pytest.mark.parametrize(
    "event_filter",
    [None, {"vis_id": "other"}, {"is_device": True}, {"event_type": "other"}],
)
def test_no_or_disjoint_interest_creates_no_slot_or_wake(
    harness: Harness, event_filter: dict[str, object] | None
) -> None:
    if event_filter is not None:
        harness.listen(event_filter)
    # A raw consumer must not turn on preview capture.
    harness.core.events.add_listener(lambda event: None, Event.VIRTUAL_UPDATE)
    harness.core.loop.drain()
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    wakes = harness.core.loop.wakes
    assert not harness.sampler.interested(key, generation)
    harness.sampler.submit(harness.frame(key, generation, 0))
    assert not harness.sampler._sources
    assert harness.core.loop.wakes == wakes


def test_encoded_filter_matching_fans_out_one_shared_encode(harness: Harness) -> None:
    harness.listen({"vis_id": "a", "pixels": "CQkJCQkJ", "shape": [1, 2]})
    harness.listen({"vis_id": "a", "pixels": "CQkJCQkJ"})
    harness.listen({"vis_id": "a", "shape": [2, 1]})
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, generation, 0, 9))
    harness.core.loop.drain()
    assert len(harness.delivered) == 2
    assert harness.delivered[0] is harness.delivered[1]
    assert rgb(harness.delivered[0]) == bytes([9] * 6)


def test_owned_capture_survives_producer_mutation(harness: Harness) -> None:
    harness.listen()
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    producer = np.arange(6, dtype=np.uint8).reshape(2, 3)
    captured = producer.copy()  # Ownership belongs to the producer capture boundary.
    harness.sampler.submit(harness.frame(key, generation, 0, pixels=captured))
    pending = harness.sampler._sources[key].pending
    assert pending is not None and pending.pixels is captured
    producer[:] = 255
    harness.core.loop.drain()
    assert rgb(harness.delivered[0]) == bytes(range(6))


def test_same_id_kinds_keep_separate_cadence(harness: Harness) -> None:
    harness.listen()
    device = SourceKey("device", "a")
    virtual = SourceKey("virtual", "a")
    dg = harness.sampler.allocate_source_generation(device)
    vg = harness.sampler.allocate_source_generation(virtual)
    harness.sampler.submit(harness.frame(device, dg, 0, 10))
    harness.core.loop.drain()
    harness.core.loop.now += 0.005
    harness.sampler.submit(harness.frame(virtual, vg, 0, 20))
    harness.core.loop.drain()
    assert [(event.is_device, rgb(event)) for event in harness.delivered] == [
        (True, bytes([10] * 6)),
        (False, bytes([20] * 6)),
    ]
    assert (
        harness.sampler._sources[device].deadline
        != harness.sampler._sources[virtual].deadline
    )


def test_last_interest_removal_releases_pending_timer_without_new_frame(
    harness: Harness,
) -> None:
    dispose = harness.listen({"vis_id": "a"})
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, generation, 0))
    harness.core.loop.drain()
    harness.sampler.submit(harness.frame(key, generation, 1, 2))
    harness.core.loop.drain()
    handle = harness.sampler._sources[key].handle
    assert handle is not None
    dispose()
    harness.core.loop.drain()
    assert not harness.sampler._sources and handle.cancelled()
    harness.listen({"vis_id": "a"})
    assert harness.sampler.interested(key, generation)
    harness.core.loop.advance(harness.core.loop.time() + 1)
    assert len(harness.delivered) == 1
    harness.sampler.submit(harness.frame(key, generation, 2, 3))
    harness.core.loop.drain()
    assert rgb(harness.delivered[-1]) == bytes([3] * 6)


def test_global_source_generations_reject_recreated_and_reordered_frames(
    harness: Harness,
) -> None:
    harness.listen()
    key = SourceKey("virtual", "a")
    old = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, old, 0, 10))
    harness.sampler.invalidate_source(key)
    other = harness.sampler.allocate_source_generation(SourceKey("device", "other"))
    new = harness.sampler.allocate_source_generation(key)
    assert old < other < new
    assert not harness.sampler.interested(key, old)
    harness.sampler.submit(harness.frame(key, old, 100, 11))
    harness.sampler.submit(harness.frame(key, new, 5, 12))
    harness.sampler.submit(harness.frame(key, new, 4, 13))
    harness.core.loop.drain()
    assert [rgb(event) for event in harness.delivered] == [bytes([12] * 6)]
    # Layout changes allocate again while preserving the actual source lifetime.
    layout = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, new, 6, 14))
    harness.sampler.submit(harness.frame(key, layout, 0, 15))
    harness.core.loop.drain()
    assert rgb(harness.delivered[-1]) == bytes([15] * 6)


@pytest.mark.parametrize("mode", ["compressed", "uncompressed"])
def test_reconfigure_discards_old_frames_and_uses_complete_new_settings(
    harness: Harness, mode: Literal["compressed", "uncompressed"]
) -> None:
    harness.listen()
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    old_frame = harness.frame(key, generation, 0, 20)
    harness.sampler.submit(old_frame)
    old_settings = harness.sampler.settings_generation
    harness.sampler.reconfigure(PreviewSettings(30, 1, 0.5, mode))
    assert harness.sampler.settings_generation > old_settings
    assert not harness.sampler._sources
    harness.sampler.submit(old_frame)
    pixels = np.array([[2, 10, 200], [20, 50, 100]], dtype=np.uint8)
    harness.sampler.submit(harness.frame(key, generation, 1, pixels=pixels))
    harness.core.loop.drain()
    assert len(harness.delivered) == 1
    event = harness.delivered[0]
    expected = pixels_boost(resize_pixels(pixels, (1, 2), (1, 1)), 0.5, 100).astype(
        np.uint8
    )
    assert event.shape == (1, 1)
    if mode == "compressed":
        assert rgb(event) == expected.tobytes()
    else:
        assert event.pixels == expected.T.tolist()


@pytest.mark.parametrize(
    "rows,count,maxlen", [(0, 7, 100), (3, 7, 100), (3, 7, 4), (1, 12, 5), (2, 12, 6)]
)
@pytest.mark.parametrize("mode", ["compressed", "uncompressed"])
def test_geometry_rgb_and_boost_match_existing_transform_math(
    harness: Harness,
    rows: int,
    count: int,
    maxlen: int,
    mode: Literal["compressed", "uncompressed"],
) -> None:
    harness.listen()
    harness.sampler.reconfigure(PreviewSettings(60, maxlen, 0.3, mode))
    key = SourceKey("device", "a")
    generation = harness.sampler.allocate_source_generation(key)
    pixels = np.arange(count * 6, dtype=np.float64).reshape(count * 2, 3)[::2]
    before = pixels.copy()
    harness.sampler.submit(harness.frame(key, generation, 0, rows=rows, pixels=pixels))
    harness.core.loop.drain()
    expected = pixels
    shape = (max(1, rows), int(count / max(1, rows)))
    if count > maxlen:
        new_shape, usable = shape_to_fit_len(maxlen, shape, count)
        expected = resize_pixels(pixels[:usable], shape, new_shape)
        shape = new_shape
    expected = pixels_boost(expected, 0.3, 100).astype(np.uint8)
    assert harness.delivered[0].shape == shape
    if mode == "compressed":
        assert rgb(harness.delivered[0]) == expected.tobytes()
    else:
        assert harness.delivered[0].pixels == expected.T.tolist()
    np.testing.assert_array_equal(pixels, before)


class BlockingSampler(PreviewSampler):
    def __init__(self, core: Core) -> None:
        super().__init__(
            core, PreviewSettings(60, 100, 0, "compressed"), clock=core.loop.time
        )
        self.entered = threading.Event()
        self.release = threading.Event()

    @override
    def _encode(
        self, frame: OwnedFrame, settings: PreviewSettings
    ) -> VisualisationUpdateEvent:
        self.entered.set()
        assert self.release.wait(5), (
            "racing producer did not complete outside sampler mutex"
        )
        return super()._encode(frame, settings)


@pytest.mark.parametrize(
    "action", ["submit", "settings", "invalidate", "recreate", "unsubscribe", "close"]
)
def test_worker_races_during_encoding_do_not_lock_or_stale_deliver(
    harness: Harness, action: str
) -> None:
    harness.sampler.close()
    sampler = BlockingSampler(harness.core)
    harness.sampler = sampler
    dispose = harness.listen()
    key = SourceKey("virtual", "a")
    generation = sampler.allocate_source_generation(key)
    sampler.submit(harness.frame(key, generation, 0, 7))
    failures: list[Exception] = []

    def race() -> None:
        try:
            assert sampler.entered.wait(5)
            if action == "submit":
                sampler.submit(harness.frame(key, generation, 1, 8))
            elif action == "settings":
                sampler.reconfigure(PreviewSettings(30, 100, 0.5, "uncompressed"))
            elif action == "invalidate":
                sampler.invalidate_source(key)
            elif action == "recreate":
                sampler.invalidate_source(key)
                new = sampler.allocate_source_generation(key)
                sampler.submit(harness.frame(key, new, 0, 9))
            elif action == "unsubscribe":
                dispose()
            else:
                sampler.close()
        except Exception as error:  # noqa: BLE001 - report worker failure to the owner thread
            failures.append(error)
        finally:
            sampler.release.set()

    worker = threading.Thread(target=race)
    worker.start()
    harness.core.loop.drain()
    worker.join(5)
    assert not worker.is_alive() and not failures
    if action == "submit":
        assert [rgb(event) for event in harness.delivered] == [bytes([7] * 6)]
        harness.core.loop.advance(harness.core.loop.time() + 1 / 60)
        assert [rgb(event) for event in harness.delivered] == [
            bytes([7] * 6),
            bytes([8] * 6),
        ]
    elif action == "recreate":
        assert [rgb(event) for event in harness.delivered] == [bytes([9] * 6)]
    else:
        assert not harness.delivered


def test_callbacks_can_take_sampler_and_bus_mutexes(harness: Harness) -> None:
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    checks: list[bool] = []

    def consumer(event: Event) -> None:
        checks.append(harness.sampler.interested(key, generation))
        harness.sampler.reconfigure(PreviewSettings(60, 100, 0, "compressed"))
        dispose()

    dispose = harness.core.events.add_listener(consumer, Event.VISUALISATION_UPDATE)
    harness.sampler.submit(harness.frame(key, generation, 0))
    harness.core.loop.drain()
    assert checks == [True]


def test_close_is_idempotent_releases_lifetimes_and_observer(harness: Harness) -> None:
    harness.listen()
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, generation, 0))
    handle = harness.sampler._sources[key].handle
    harness.sampler.close()
    harness.sampler.close()
    assert not harness.sampler._sources and not harness.sampler._live_generations
    assert handle is not None and handle.cancelled()
    assert not harness.sampler.interested(key, generation)
    harness.sampler.submit(harness.frame(key, generation, 1))
    harness.core.loop.drain()
    assert not harness.delivered and not harness.core.events._registration_observers


async def test_actual_loop_delayed_thousand_frames_encodes_latest_rgb() -> None:
    @dataclass
    class AsyncCore:
        loop: asyncio.AbstractEventLoop
        events: Events = field(init=False)

        def __post_init__(self) -> None:
            self.events = Events(self)

    core = AsyncCore(asyncio.get_running_loop())
    sampler = PreviewSampler(core, PreviewSettings(60, 100, 0, "compressed"))
    delivered: list[VisualisationUpdateEvent] = []

    def collect(event: Event) -> None:
        assert isinstance(event, VisualisationUpdateEvent)
        delivered.append(event)

    core.events.add_listener(collect, Event.VISUALISATION_UPDATE, {"vis_id": "a"})
    key = SourceKey("virtual", "a")
    generation = sampler.allocate_source_generation(key)
    try:
        for sequence in range(1000):
            sampler.submit(
                OwnedFrame(
                    key,
                    generation,
                    sequence,
                    np.full((2, 3), sequence % 256, dtype=np.uint8),
                    1,
                    2,
                    sampler.settings_generation,
                )
            )
        pending = sampler._sources[key].pending
        assert pending is not None and pending.sequence == 999
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert len(delivered) == 1 and rgb(delivered[0]) == bytes([999 % 256] * 6)
    finally:
        sampler.close()


@pytest.mark.parametrize(
    "setting",
    [
        "visualisation_fps",
        "visualisation_maxlen",
        "ui_brightness_boost",
        "transmission_mode",
    ],
)
async def test_core_setup_and_config_updates_own_sampler_without_raw_listeners(
    tmp_path: Path, setting: str
) -> None:
    core = object.__new__(LedFxCore)
    core.loop = asyncio.get_running_loop()
    core.config_store = ConfigStore(str(tmp_path), LedFxConfig())
    core.events = Events(core)
    core.preview_sampler = PreviewSampler(
        core,
        PreviewSettings(
            core.config.visualisation_fps,
            core.config.visualisation_maxlen,
            core.config.ui_brightness_boost,
            core.config.transmission_mode,
        ),
    )
    sampler = core.preview_sampler
    assert not core.events.has_listeners(Event.DEVICE_UPDATE)
    assert not core.events.has_listeners(Event.VIRTUAL_UPDATE)
    delivered: list[VisualisationUpdateEvent] = []

    def collect(event: Event) -> None:
        assert isinstance(event, VisualisationUpdateEvent)
        delivered.append(event)

    core.events.add_listener(collect, Event.VISUALISATION_UPDATE)
    key = SourceKey("virtual", "a")
    generation = sampler.allocate_source_generation(key)
    old_settings = sampler.settings_generation
    sampler.submit(
        OwnedFrame(
            key, generation, 0, np.full((2, 3), 10, dtype=np.uint8), 1, 2, old_settings
        )
    )
    if setting == "visualisation_fps":
        core.config.visualisation_fps = 30
    elif setting == "visualisation_maxlen":
        core.config.visualisation_maxlen = 5
    elif setting == "ui_brightness_boost":
        core.config.ui_brightness_boost = 0.5
    else:
        core.config.transmission_mode = "uncompressed"
    core.handle_base_configuration_update(
        BaseConfigUpdateEvent({setting: getattr(core.config, setting)})
    )
    assert core.preview_sampler is sampler
    assert sampler.settings_generation == old_settings + 1
    assert sampler.interested(key, generation)
    assert not sampler._sources
    pixels = np.tile(np.array([[2, 10, 200], [20, 50, 100]], dtype=np.uint8), (6, 1))
    sampler.submit(
        OwnedFrame(
            key, generation, 1, pixels, 1, len(pixels), sampler.settings_generation
        )
    )
    try:
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert len(delivered) == 1
        expected = pixels
        if setting == "visualisation_maxlen":
            expected = resize_pixels(expected, (1, 12), (1, 5))
        if setting == "ui_brightness_boost":
            expected = pixels_boost(expected, 0.5, 100).astype(np.uint8)
        if setting == "transmission_mode":
            assert delivered[0].pixels == expected.T.tolist()
        else:
            assert rgb(delivered[0]) == expected.tobytes()
        before = sampler.settings_generation
        before = sampler.settings_generation
        core.setup_visualisation_events()  # Remains callable for external tools.
        assert core.preview_sampler is sampler
        assert sampler.settings_generation == before + 1
        assert not core.events.has_listeners(Event.DEVICE_UPDATE)
        assert not core.events.has_listeners(Event.VIRTUAL_UPDATE)
    finally:
        sampler.close()


class HeldScheduler(Scheduler):
    """Let the owner loop run a producer wake before its handle is returned."""

    def __init__(self) -> None:
        super().__init__()
        self.hold_next = False
        self.enqueued = threading.Event()
        self.release_return = threading.Event()

    @override
    def call_soon_threadsafe(
        self, callback: Callable[..., object], *args: object
    ) -> asyncio.Handle:
        handle = super().call_soon_threadsafe(callback, *args)
        if self.hold_next:
            self.hold_next = False
            self.enqueued.set()
            assert self.release_return.wait(5)
        return handle


@pytest.mark.parametrize("recreate", [False, True])
def test_wake_runs_before_handle_return_without_overwriting_next_due_timer(
    recreate: bool,
) -> None:
    scheduler = HeldScheduler()
    harness = Harness(Core(scheduler))
    harness.listen()
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)

    def submit_next(event: Event) -> None:
        assert isinstance(event, VisualisationUpdateEvent)
        if rgb(event) == bytes([7] * 6):
            harness.sampler.submit(harness.frame(key, generation, 1, 8))

    harness.core.events.add_listener(submit_next, Event.VISUALISATION_UPDATE)
    scheduler.drain()
    failures: list[Exception] = []

    def produce() -> None:
        try:
            harness.sampler.submit(
                harness.frame(key, generation, 0, 6 if recreate else 7)
            )
        except Exception as error:  # noqa: BLE001 - forward the worker failure
            failures.append(error)

    scheduler.hold_next = True
    worker = threading.Thread(target=produce)
    worker.start()
    try:
        assert scheduler.enqueued.wait(5)
        if recreate:
            harness.sampler.invalidate_source(key)
            generation = harness.sampler.allocate_source_generation(key)
            harness.sampler.submit(harness.frame(key, generation, 0, 7))
        scheduler.drain()
        timer = harness.sampler._sources[key].handle
        assert isinstance(timer, asyncio.TimerHandle)
        scheduler.release_return.set()
        worker.join(5)
        assert not worker.is_alive() and not failures
        assert harness.sampler._sources[key].handle is timer
        assert not timer.cancelled()
        scheduler.advance(scheduler.time() + 1 / 60)
        assert [rgb(event) for event in harness.delivered] == [
            bytes([7] * 6),
            bytes([8] * 6),
        ]
    finally:
        scheduler.release_return.set()
        worker.join(5)
        harness.close()


def test_sampler_clock_epoch_is_translated_to_owner_loop_deadlines(
    harness: Harness,
) -> None:
    harness.sampler.close()
    harness.sampler = PreviewSampler(
        harness.core,
        PreviewSettings(60, 100, 0, "compressed"),
        clock=lambda: harness.core.loop.time() + 500,
    )
    harness.listen()
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, generation, 0, 7))
    harness.core.loop.drain()
    harness.sampler.submit(harness.frame(key, generation, 1, 8))
    harness.core.loop.drain()
    harness.core.loop.advance(harness.core.loop.time() + 1 / 60)
    assert [rgb(event) for event in harness.delivered] == [
        bytes([7] * 6),
        bytes([8] * 6),
    ]


def test_reconfigure_cancels_due_timer_and_next_frame_is_immediately_eligible(
    harness: Harness,
) -> None:
    harness.listen()
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, generation, 0, 7))
    harness.core.loop.drain()
    stale = harness.frame(key, generation, 1, 8)
    harness.sampler.submit(stale)
    harness.core.loop.drain()
    timer = harness.sampler._sources[key].handle
    assert isinstance(timer, asyncio.TimerHandle)
    harness.sampler.reconfigure(PreviewSettings(30, 100, 0, "compressed"))
    assert timer.cancelled() and not harness.sampler._sources
    harness.sampler.submit(stale)
    harness.sampler.submit(harness.frame(key, generation, 2, 9))
    harness.core.loop.drain()
    harness.core.loop.advance(harness.core.loop.time() + 1)
    assert [rgb(event) for event in harness.delivered] == [
        bytes([7] * 6),
        bytes([9] * 6),
    ]


def test_submit_during_wake_to_timer_handoff_keeps_one_pending_handle(
    harness: Harness, monkeypatch: pytest.MonkeyPatch
) -> None:
    harness.listen()
    key = SourceKey("virtual", "a")
    generation = harness.sampler.allocate_source_generation(key)
    harness.sampler.submit(harness.frame(key, generation, 0, 7))
    harness.core.loop.drain()
    harness.core.loop.advance(harness.core.loop.time() + 0.005)
    harness.sampler.submit(harness.frame(key, generation, 1, 8))
    wakes = harness.core.loop.wakes
    entered = threading.Event()
    finished = threading.Event()
    owner = threading.current_thread()
    original = harness.sampler.interested
    block_once = True
    failures: list[Exception] = []

    def interested(source: SourceKey, source_generation: int) -> bool:
        nonlocal block_once
        if threading.current_thread() is owner and block_once:
            block_once = False
            entered.set()
            assert finished.wait(5), "wake admission held the sampler mutex"
        return original(source, source_generation)

    monkeypatch.setattr(harness.sampler, "interested", interested)

    def produce() -> None:
        try:
            assert entered.wait(5)
            harness.sampler.submit(harness.frame(key, generation, 2, 9))
        except Exception as error:  # noqa: BLE001 - forward the worker failure
            failures.append(error)
        finally:
            finished.set()

    worker = threading.Thread(target=produce)
    worker.start()
    harness.core.loop.drain()
    worker.join(5)
    assert not worker.is_alive() and not failures
    assert harness.core.loop.wakes == wakes
    assert sum(not timer.cancelled() for _, _, timer in harness.core.loop.timers) == 1
    harness.core.loop.advance(harness.core.loop.time() + 1 / 60)
    assert [rgb(event) for event in harness.delivered] == [
        bytes([7] * 6),
        bytes([9] * 6),
    ]
