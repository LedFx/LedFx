"""Factory function for creating platform-specific monitors."""

import asyncio
import logging
import sys
from typing import Optional

from ._base import AudioDeviceMonitor


def create_monitor(
    *,
    loop: Optional[asyncio.AbstractEventLoop] = None,
    debounce_ms: int = 200,
    logger: Optional[logging.Logger] = None,
) -> Optional[AudioDeviceMonitor]:
    """Create a platform-appropriate audio device change monitor.
    
    Args:
        loop: Event loop for callback scheduling. If None, attempts to get running loop.
        debounce_ms: Milliseconds to wait before invoking callback after last change.
        logger: Logger instance. If None, creates default logger.
    
    Returns:
        Platform-specific monitor instance, or None if platform unsupported.
    
    Example:
        >>> monitor = create_monitor(loop=asyncio.get_event_loop())
        >>> if monitor:
        ...     monitor.start(lambda: print("Devices changed!"))
    """
    _logger = logger or logging.getLogger(__name__)
    
    # Lazy import platform-specific monitors to avoid dependency issues
    if sys.platform == "win32":
        try:
            from ._platform.windows import WindowsAudioDeviceMonitor
            return WindowsAudioDeviceMonitor(loop=loop, debounce_ms=debounce_ms, logger=_logger)
        except ImportError as e:
            _logger.warning(
                f"Windows audio monitoring unavailable: {e}. "
                "Install with: uv pip install 'audio-hotplug[windows]'"
            )
            return None
    
    elif sys.platform == "darwin":
        try:
            from ._platform.macos import MacOSAudioDeviceMonitor
            return MacOSAudioDeviceMonitor(loop=loop, debounce_ms=debounce_ms, logger=_logger)
        except ImportError as e:
            _logger.warning(
                f"macOS audio monitoring unavailable: {e}. "
                "Install with: uv pip install 'audio-hotplug[macos]'"
            )
            return None
    
    elif sys.platform.startswith("linux"):
        try:
            from ._platform.linux import LinuxAudioDeviceMonitor
            return LinuxAudioDeviceMonitor(loop=loop, debounce_ms=debounce_ms, logger=_logger)
        except ImportError as e:
            _logger.warning(
                f"Linux audio monitoring unavailable: {e}. "
                "Install with: uv pip install 'audio-hotplug[linux]'"
            )
            return None
    
    else:
        _logger.warning(f"Audio device monitoring not supported on platform: {sys.platform}")
        return None
