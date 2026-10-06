"""Sample owned source frames before scheduling expensive preview delivery."""

from __future__ import annotations

import asyncio
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, Protocol

import numpy as np
import pybase64
from numpy.typing import NDArray

from ledfx.configuration.paths import Transmission
from ledfx.events import Event, Events, VisualisationUpdateEvent
from ledfx.utils import pixels_boost, resize_pixels, shape_to_fit_len


@dataclass(frozen=True)
class SourceKey:
    kind: Literal["device", "virtual"]
    id: str


@dataclass(frozen=True)
class OwnedFrame:
    """An RGB snapshot transferred by its producer; observers share it read-only."""

    key: SourceKey
    source_generation: int
    sequence: int
    pixels: NDArray[np.generic]
    rows: int
    pixel_count: int
    settings_generation: int


@dataclass(frozen=True)
class PreviewSettings:
    fps: int
    maxlen: int
    boost: float
    transmission_mode: Literal["compressed", "uncompressed"]

    def __post_init__(self) -> None:
        if self.fps <= 0 or self.maxlen <= 0:
            raise ValueError("preview fps and maximum length must be positive")


@dataclass
class _SampleState:
    generation: int
    pending: OwnedFrame | None = None
    deadline: float | None = None
    handle: asyncio.Handle | None = None
    scheduled: bool = False
    encoding: bool = False
    last_sequence: int = -1


class _PreviewLoop(Protocol):
    def call_soon_threadsafe(
        self, callback: Callable[..., object], *args: object
    ) -> asyncio.Handle: ...

    def call_at(
        self, when: float, callback: Callable[..., object], *args: object
    ) -> asyncio.TimerHandle: ...

    def time(self) -> float: ...


class _PreviewHost(Protocol):
    @property
    def loop(self) -> _PreviewLoop: ...

    @property
    def events(self) -> Events: ...


class PreviewSampler:
    """Keep one pending frame and wake/timer for each interested live source.

    Producers own capture and call submit from any thread. Only the owner loop
    drains and encodes. Source lifetimes, settings and registration revisions
    remain independent. Encoding and delivery claims never hold the mutex.
    """

    def __init__(
        self,
        ledfx: _PreviewHost,
        settings: PreviewSettings,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ledfx = ledfx
        self._settings = settings
        self._clock = clock
        self._lock = threading.Lock()
        self._closed = False
        self._settings_generation = 0
        self._source_generation = 0
        self._live_generations: dict[SourceKey, int] = {}
        self._sources: dict[SourceKey, _SampleState] = {}
        self._registration_revision = 0
        self._dispose_observer = ledfx.events.add_registration_observer(
            self._registrations_changed
        )

    @property
    def settings_generation(self) -> int:
        with self._lock:
            return self._settings_generation

    def allocate_source_generation(self, key: SourceKey) -> int:
        """Publish a new source/layout lifetime, never reusing a historical ID."""
        with self._lock:
            if self._closed:
                raise RuntimeError("preview sampler is closed")
            self._source_generation += 1
            generation = self._source_generation
            self._live_generations[key] = generation
            state = self._sources.pop(key, None)
        self._cancel(state)
        return generation

    def interested(self, key: SourceKey, source_generation: int) -> bool:
        with self._lock:
            if self._closed or self._live_generations.get(key) != source_generation:
                return False
        demand = self._ledfx.events.may_have_listeners(
            Event.VISUALISATION_UPDATE,
            {
                "event_type": Event.VISUALISATION_UPDATE,
                "is_device": key.kind == "device",
                "vis_id": key.id,
            },
        )
        with self._lock:
            return (
                demand
                and not self._closed
                and self._live_generations.get(key) == source_generation
            )

    def submit(self, frame: OwnedFrame) -> None:
        if not self.interested(frame.key, frame.source_generation):
            return
        with self._lock:
            if (
                self._closed
                or frame.settings_generation != self._settings_generation
                or self._live_generations.get(frame.key) != frame.source_generation
            ):
                return
            state = self._sources.get(frame.key)
            if state is None:
                state = _SampleState(frame.source_generation)
                self._sources[frame.key] = state
            if frame.sequence <= state.last_sequence:
                return
            state.last_sequence = frame.sequence
            state.pending = frame
            arm = not state.scheduled and not state.encoding
            if arm:
                state.scheduled = True
        if arm:
            self._arm(frame.key, state)

    def _arm(
        self, key: SourceKey, state: _SampleState, deadline: float | None = None
    ) -> None:
        # Scheduling is outside the mutex. A loop can run a threadsafe wake
        # before this thread receives its handle, so do not install that spent
        # handle over the timer/drain that the callback has already established.
        started = False

        def wake() -> None:
            nonlocal started
            with self._lock:
                started = True
                if self._sources.get(key) is not state or not state.scheduled:
                    return
            self._wake_source(key, state)

        if deadline is None:
            handle = self._ledfx.loop.call_soon_threadsafe(wake)
        else:
            # call_at uses the event-loop clock; the injectable sampler clock
            # can have a different epoch, including on supported Python loops.
            delay = max(0.0, deadline - self._clock())
            handle = self._ledfx.loop.call_at(self._ledfx.loop.time() + delay, wake)
        with self._lock:
            install = (
                not started and self._sources.get(key) is state and state.scheduled
            )
            if install:
                state.handle = handle
        if not install:
            handle.cancel()

    def _wake(self, key: SourceKey) -> None:
        with self._lock:
            state = self._sources.get(key)
        if state is not None:
            self._wake_source(key, state)

    def _wake_source(self, key: SourceKey, state: _SampleState) -> None:
        now = self._clock()
        with self._lock:
            if self._sources.get(key) is not state or state.encoding:
                return
            state.handle = None
            # Keep the scheduling reservation until it becomes a timer or an
            # encoding claim. A racing submit only replaces the pending frame.
            if state.pending is None:
                state.scheduled = False
                return
            generation = state.generation
        if not self.interested(key, generation):
            self._remove_state(key, state)
            return
        with self._lock:
            if self._sources.get(key) is not state:
                return
            deadline = state.deadline
            later = deadline is not None and now < deadline
            if later:
                state.scheduled = True
        if later:
            self._arm(key, state, deadline)
        else:
            self._drain_source(key, state)

    def _drain(self, key: SourceKey) -> None:
        with self._lock:
            state = self._sources.get(key)
        if state is not None:
            self._drain_source(key, state)

    def _drain_source(self, key: SourceKey, state: _SampleState) -> None:
        now = self._clock()
        with self._lock:
            if (
                self._sources.get(key) is not state
                or state.pending is None
                or state.encoding
            ):
                return
            frame = state.pending
            state.pending = None
            state.scheduled = False
            state.encoding = True
            settings = self._settings
            settings_generation = self._settings_generation
            due = state.deadline if state.deadline is not None else now
            interval = 1 / settings.fps
            state.deadline = now + interval - (now - due) % interval
        try:
            if not self.interested(key, frame.source_generation):
                self._remove_state(key, state)
                return
            event = self._encode(frame, settings)
            demand = self.interested(key, frame.source_generation)
            with self._lock:
                claimed = (
                    demand
                    and not self._closed
                    and self._sources.get(key) is state
                    and self._live_generations.get(key) == frame.source_generation
                    and self._settings_generation == settings_generation
                    and frame.settings_generation == settings_generation
                )
                # This is the delivery start claim. Invalidation after this
                # boundary may finish this publication, just as an already
                # claimed bus callback may finish after its token is disposed.
            if claimed:
                self._ledfx.events.fire_event(event)
        finally:
            with self._lock:
                current = self._sources.get(key) is state
                state.encoding = False
                arm = current and state.pending is not None and not state.scheduled
                deadline = state.deadline
                if arm:
                    state.scheduled = True
            if arm:
                self._arm(key, state, deadline)

    def _encode(
        self, frame: OwnedFrame, settings: PreviewSettings
    ) -> VisualisationUpdateEvent:
        rows = max(1, frame.rows)
        pixels = frame.pixels
        pixel_count = frame.pixel_count
        shape = (rows, int(pixel_count / rows))
        if pixel_count > settings.maxlen:
            new_shape, pixel_count = shape_to_fit_len(
                settings.maxlen, shape, pixel_count
            )
            pixels = resize_pixels(pixels[:pixel_count], shape, new_shape)
            shape = new_shape
        if settings.boost != 0:
            pixels = pixels_boost(pixels, settings.boost, 100)
        encoded: str | list[list[int]]
        if settings.transmission_mode == Transmission.BASE64_COMPRESSED:
            encoded = pybase64.b64encode(
                pixels.astype(np.uint8, copy=False).tobytes()
            ).decode("ASCII")
        else:
            encoded = pixels.astype(np.uint8, copy=False).T.tolist()
        return VisualisationUpdateEvent(
            frame.key.kind == "device", frame.key.id, encoded, shape
        )

    def _remove_state(self, key: SourceKey, state: _SampleState) -> None:
        with self._lock:
            if self._sources.get(key) is not state:
                return
            self._sources.pop(key)
        self._cancel(state)

    @staticmethod
    def _cancel(state: _SampleState | None) -> None:
        if state is not None and state.handle is not None:
            state.handle.cancel()

    def _registrations_changed(self, event_type: str, revision: int) -> None:
        if event_type != Event.VISUALISATION_UPDATE:
            return
        with self._lock:
            if self._closed or revision <= self._registration_revision:
                return
            self._registration_revision = revision
            sources = tuple(self._sources.items())
        for key, state in sources:
            if not self.interested(key, state.generation):
                self._remove_state(key, state)

    def invalidate_source(self, key: SourceKey) -> None:
        with self._lock:
            self._live_generations.pop(key, None)
            state = self._sources.pop(key, None)
        self._cancel(state)

    def reconfigure(self, settings: PreviewSettings) -> None:
        with self._lock:
            if self._closed:
                return
            self._settings = settings
            self._settings_generation += 1
            states = tuple(self._sources.values())
            self._sources.clear()
        for state in states:
            self._cancel(state)

    def close(self) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            states = tuple(self._sources.values())
            self._sources.clear()
            self._live_generations.clear()
        self._dispose_observer()
        for state in states:
            self._cancel(state)
