"""Abstract base class for audio device monitors."""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Awaitable
from typing import Callable, Optional, Union

Callback = Union[Callable[[], None], Callable[[], Awaitable[None]]]


class AudioDeviceMonitor(ABC):
    """Abstract base class for platform-specific audio device monitors.

    Monitors system audio device changes (add/remove/state changes) and
    invokes a user callback when changes are detected.
    """

    def __init__(
        self,
        loop: Optional[asyncio.AbstractEventLoop] = None,
        debounce_ms: int = 200,
        logger: Optional[logging.Logger] = None,
    ):
        """Initialize the monitor.

        Args:
            loop: Event loop for callback scheduling. If None, attempts to get running loop.
            debounce_ms: Milliseconds to wait before invoking callback after last change.
            logger: Logger instance. If None, creates a logger for this class.
        """
        self._loop = loop
        self._debounce_ms = debounce_ms
        self._logger = logger or logging.getLogger(self.__class__.__name__)
        self._callback: Optional[Callback] = None
        self._running = False

    @abstractmethod
    def start(self, on_change: Callback) -> None:
        """Start monitoring for device changes.

        Args:
            on_change: Callback to invoke when device changes detected.
                      Can be sync or async function.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """Stop monitoring. Safe to call multiple times."""
        pass

    def _notify(self, callback: Callback) -> None:
        """Schedule callback on the event loop thread safely.

        Args:
            callback: The callback to invoke.
        """
        if not callback:
            return

        loop = self._loop
        if loop is None:
            try:
                loop = asyncio.get_running_loop()
            except RuntimeError:
                # No running loop, call sync callback directly
                if asyncio.iscoroutinefunction(callback):
                    self._logger.error(
                        "Async callback provided but no event loop available"
                    )
                    return
                try:
                    callback()
                except Exception as e:
                    self._logger.error(
                        f"Error in callback: {e}", exc_info=True
                    )
                return

        # Schedule on loop thread
        if asyncio.iscoroutinefunction(callback):
            asyncio.run_coroutine_threadsafe(
                self._safe_async_callback(callback), loop
            )
        else:
            loop.call_soon_threadsafe(self._safe_sync_callback, callback)

    def _safe_sync_callback(self, callback: Callable[[], None]) -> None:
        """Wrap sync callback with error handling."""
        try:
            callback()
        except Exception as e:
            self._logger.error(f"Error in sync callback: {e}", exc_info=True)

    async def _safe_async_callback(
        self, callback: Callable[[], Awaitable[None]]
    ) -> None:
        """Wrap async callback with error handling."""
        try:
            await callback()
        except Exception as e:
            self._logger.error(f"Error in async callback: {e}", exc_info=True)
