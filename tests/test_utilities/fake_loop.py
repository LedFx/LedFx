"""A deterministic stand-in for the asyncio loop's thread-safe scheduling."""

from collections import deque
from collections.abc import Callable


class FakeLoop:
    """Queue callbacks like ``call_soon_threadsafe`` and run them on demand."""

    def __init__(self) -> None:
        # deque append and popleft are atomic, so other threads may schedule.
        self._ready: deque[tuple[Callable[..., object], tuple[object, ...]]] = deque()

    def call_soon_threadsafe(
        self, callback: Callable[..., object], *args: object
    ) -> None:
        self._ready.append((callback, args))

    def run_ready(self) -> int:
        """Run queued callbacks in FIFO order, including ones queued meanwhile."""
        count = 0
        while self._ready:
            callback, args = self._ready.popleft()
            callback(*args)
            count += 1
        return count
