"""A deterministic stand-in for the asyncio loop's scheduling and clock."""

import heapq
import itertools
from collections import deque
from collections.abc import Callable


class FakeTimer:
    """The part of ``asyncio.TimerHandle`` that callers use."""

    def __init__(
        self, when: float, callback: Callable[..., object], args: tuple[object, ...]
    ) -> None:
        self.when = when
        self.callback = callback
        self.args = args
        self.cancelled = False

    def cancel(self) -> None:
        self.cancelled = True


class FakeLoop:
    """Queue callbacks like ``call_soon_threadsafe`` and run them on demand.

    ``time()`` moves only when ``advance`` moves it.
    """

    def __init__(self, now: float = 1000.0) -> None:
        # deque append and popleft are atomic, so other threads may schedule.
        self._ready: deque[tuple[Callable[..., object], tuple[object, ...]]] = deque()
        self._now = now
        self._timers: list[tuple[float, int, FakeTimer]] = []
        self._order = itertools.count()

    def time(self) -> float:
        return self._now

    def call_soon_threadsafe(
        self, callback: Callable[..., object], *args: object
    ) -> None:
        self._ready.append((callback, args))

    def call_at(
        self, when: float, callback: Callable[..., object], *args: object
    ) -> FakeTimer:
        timer = FakeTimer(when, callback, args)
        heapq.heappush(self._timers, (when, next(self._order), timer))
        return timer

    @property
    def armed_timers(self) -> list[FakeTimer]:
        """Timers still scheduled and not cancelled."""
        return [timer for _, _, timer in self._timers if not timer.cancelled]

    def run_ready(self) -> int:
        """Run queued callbacks in FIFO order, including ones queued meanwhile."""
        count = 0
        while self._ready:
            callback, args = self._ready.popleft()
            callback(*args)
            count += 1
        return count

    def advance(self, seconds: float) -> None:
        """Move the clock forward, running ready callbacks and due timers in order."""
        end = self._now + seconds
        self.run_ready()
        while self._timers and self._timers[0][0] <= end:
            when, _, timer = heapq.heappop(self._timers)
            self._now = max(self._now, when)
            if not timer.cancelled:
                timer.callback(*timer.args)
            self.run_ready()
        self._now = end
