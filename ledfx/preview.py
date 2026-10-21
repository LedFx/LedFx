"""Sample the newest frame per preview source and encode it on one loop tick."""

from __future__ import annotations

import asyncio
import logging
import threading
from typing import Protocol

import numpy as np
import pybase64
from numpy.typing import NDArray

from ledfx.configuration.models import LedFxConfig
from ledfx.configuration.paths import Transmission
from ledfx.events import Event, Events, VisualisationUpdateEvent
from ledfx.utils import pixels_boost, resize_pixels, shape_to_fit_len

_LOGGER = logging.getLogger(__name__)

_Key = tuple[bool, str]


class _PreviewHost(Protocol):
    @property
    def loop(self) -> asyncio.AbstractEventLoop: ...

    @property
    def events(self) -> Events: ...

    @property
    def config(self) -> LedFxConfig: ...


class PreviewSampler:
    """Turn producer frames into ``visualisation_update`` events at the preview rate.

    Producers ask ``wants`` before copying a frame and hand the copy to
    ``submit`` from any thread. Only the newest frame per source is kept. The
    loop encodes due frames on one tick at ``visualisation_fps``, reading the
    preview config live. Timer handles are created only on the loop.
    """

    def __init__(self, ledfx: _PreviewHost) -> None:
        self._ledfx = ledfx
        self._lock = threading.Lock()
        self._pending: dict[_Key, tuple[NDArray[np.generic], int]] = {}
        self._due: dict[_Key, float] = {}
        self._scheduled = False
        self._closed = False
        # Loop-only: (last report time, failures since) per exception class.
        self._errors: dict[str, tuple[float, int]] = {}

    def wants(self, is_device: bool, source_id: str) -> bool:
        """Whether a ``visualisation_update`` subscriber could match this source."""
        return not self._closed and self._ledfx.events.may_have_listeners(
            Event.VISUALISATION_UPDATE, {"is_device": is_device, "vis_id": source_id}
        )

    def submit(
        self, is_device: bool, source_id: str, pixels: NDArray[np.generic], rows: int
    ) -> None:
        """Keep ``pixels`` (a private copy the caller gives up) as the newest frame."""
        if not self.wants(is_device, source_id):
            return
        with self._lock:
            if self._closed:
                return
            self._pending[(is_device, source_id)] = (pixels, rows)
            wake = not self._scheduled
            self._scheduled = True
        if wake:
            self._ledfx.loop.call_soon_threadsafe(self._tick)

    def forget(self, is_device: bool, source_id: str) -> None:
        """Drop a deleted source's pending frame and schedule."""
        with self._lock:
            self._pending.pop((is_device, source_id), None)
            self._due.pop((is_device, source_id), None)

    def close(self) -> None:
        with self._lock:
            self._closed = True
            self._pending.clear()
            self._due.clear()

    def _tick(self) -> None:
        # shortcut: a new source submitted while a timer is armed waits for that timer (at most one interval); wake per key if first-frame latency matters.
        now = self._ledfx.loop.time()
        interval = 1 / self._ledfx.config.visualisation_fps
        ready: list[tuple[_Key, NDArray[np.generic], int]] = []
        with self._lock:
            for key in list(self._pending):
                due = self._due.get(key, now)
                if due <= now:
                    ready.append((key, *self._pending.pop(key)))
                    # Advance the schedule, not the arrival time, so a 62 Hz
                    # source keeps 60 Hz, and skip slots missed while idle.
                    self._due[key] = now + interval - (now - due) % interval
            for key, due in list(self._due.items()):
                if due <= now and key not in self._pending:
                    del self._due[key]
            next_due = min((self._due[key] for key in self._pending), default=None)
            self._scheduled = next_due is not None
        # Arm before encoding so a failing frame cannot stall later previews.
        if next_due is not None:
            self._ledfx.loop.call_at(next_due, self._tick)
        for (is_device, source_id), pixels, rows in ready:
            if not self.wants(is_device, source_id):
                continue
            try:
                event = self._encode(is_device, source_id, pixels, rows)
            except Exception as error:  # noqa: BLE001 - one bad source must not starve the rest
                self._report_error(source_id, error, now)
                continue
            self._ledfx.events.fire_event(event)

    def _report_error(self, source_id: str, exc: Exception, now: float) -> None:
        """Log at most once per second per exception class, like Events listeners."""
        category = type(exc).__name__
        last_report, count = self._errors.get(category, (None, 0))
        count += 1
        if last_report is not None and now - last_report < 1.0:
            self._errors[category] = (last_report, count)
            return
        self._errors[category] = (now, 0)
        _LOGGER.error(
            "Preview for %s failed to encode (%d errors since last report)",
            source_id,
            count,
            exc_info=exc,
        )

    def _encode(
        self, is_device: bool, source_id: str, pixels: NDArray[np.generic], rows: int
    ) -> VisualisationUpdateEvent:
        config = self._ledfx.config
        rows = max(1, rows)
        pixels_len = len(pixels)
        shape = (rows, int(pixels_len / rows))

        if pixels_len > config.visualisation_maxlen:
            new_shape, pixels_len = shape_to_fit_len(
                config.visualisation_maxlen, shape, pixels_len
            )
            pixels = resize_pixels(pixels[:pixels_len], shape, new_shape)
            shape = new_shape

        if config.ui_brightness_boost != 0:
            pixels = pixels_boost(pixels, config.ui_brightness_boost, 100)

        encoded: str | list[list[int]]
        if config.transmission_mode == Transmission.BASE64_COMPRESSED:
            b_arr = pixels.astype(np.uint8, copy=False).tobytes()
            encoded = pybase64.b64encode(b_arr).decode("ASCII")
        else:
            encoded = pixels.astype(np.uint8).T.tolist()

        return VisualisationUpdateEvent(is_device, source_id, encoded, shape)
