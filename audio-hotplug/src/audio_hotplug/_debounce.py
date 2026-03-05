"""Thread-safe debouncer for coalescing rapid events."""

import threading
from typing import Callable


class Debouncer:
    """Thread-safe debouncer that coalesces rapid triggers into a single callback.
    
    When triggered multiple times within the debounce period, only invokes
    the callback once after the period expires from the last trigger.
    """

    def __init__(self, callback: Callable[[], None], delay_ms: int = 200):
        """Initialize the debouncer.
        
        Args:
            callback: Function to invoke after debounce period.
            delay_ms: Milliseconds to wait after last trigger before invoking callback.
        """
        self._callback = callback
        self._delay_s = delay_ms / 1000.0
        self._timer: threading.Timer | None = None
        self._lock = threading.Lock()

    def trigger(self) -> None:
        """Trigger the debouncer. Resets the debounce timer."""
        with self._lock:
            # Cancel existing timer if any
            if self._timer is not None and self._timer.is_alive():
                self._timer.cancel()
            
            # Start new timer
            self._timer = threading.Timer(self._delay_s, self._invoke_callback)
            self._timer.daemon = True
            self._timer.start()

    def _invoke_callback(self) -> None:
        """Internal: invoke the callback after debounce period."""
        try:
            self._callback()
        except Exception:
            # Callback handles its own error logging
            pass

    def cancel(self) -> None:
        """Cancel any pending callback."""
        with self._lock:
            if self._timer is not None and self._timer.is_alive():
                self._timer.cancel()
            self._timer = None
