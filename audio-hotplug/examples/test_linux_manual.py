"""Manual Linux audio device testing script.

This script provides detailed logging and instructions for testing
Linux audio device detection with pyudev.

Run: uv run python examples/test_linux_manual.py

Then:
1. Plug in a USB audio device (headset, webcam with mic, etc.)
2. Unplug the USB audio device
3. Change default audio device in system settings
4. Observe the callback triggers and debouncing behavior
"""

import asyncio
import logging
import sys
from datetime import datetime

sys.path.insert(0, "../src")

from audio_hotplug import create_monitor  # noqa: E402

# Configure detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

_LOGGER = logging.getLogger(__name__)

# Track callback invocations
callback_count = 0
last_callback_time = None


def on_devices_changed():
    """Callback when audio devices change."""
    global callback_count, last_callback_time
    callback_count += 1
    current_time = datetime.now()

    if last_callback_time:
        delta_ms = (current_time - last_callback_time).total_seconds() * 1000
        print(f"\n🔊 Callback #{callback_count} - Delta: {delta_ms:.0f}ms")
    else:
        print(f"\n🔊 Callback #{callback_count} - Initial")

    last_callback_time = current_time
    print(f"   Time: {current_time.strftime('%H:%M:%S.%f')[:-3]}")


async def main():
    """Run the monitor with detailed instructions."""
    loop = asyncio.get_running_loop()

    print("=" * 70)
    print("Linux Audio Device Hot-Plug Test")
    print("=" * 70)
    print()
    print("This test will monitor for audio device changes using pyudev.")
    print()
    print("Test Steps:")
    print("  1. Wait for monitor to start")
    print("  2. Plug in a USB audio device (headset, USB mic, etc.)")
    print("  3. Wait 1 second, then unplug it")
    print("  4. Observe callback behavior and debouncing")
    print()
    print("Expected Behavior:")
    print("  - Callbacks should be debounced (200ms coalescing)")
    print("  - Multiple rapid events should trigger single callback")
    print("  - Each callback should show time delta from previous")
    print()
    print("Press Ctrl+C to stop the test")
    print("=" * 70)
    print()

    monitor = create_monitor(loop=loop, debounce_ms=200)

    if monitor is None:
        print("❌ Audio device monitoring not supported on this platform")
        return

    monitor.start(on_devices_changed)
    print("✅ Monitor started successfully")
    print()
    print("Waiting for audio device changes...")
    print("(Try plugging/unplugging a USB audio device)")
    print()

    try:
        # Run for 2 minutes or until interrupted
        for i in range(120):
            await asyncio.sleep(1)
            if i % 10 == 0 and i > 0:
                print(f"[{i}s elapsed - {callback_count} callbacks so far]")
    except KeyboardInterrupt:
        print("\n" + "=" * 70)
        print("Test Summary:")
        print(f"  Total callbacks: {callback_count}")
        print(f"  Test duration: ~{i}s")
        print("=" * 70)
    finally:
        print("\nStopping monitor...")
        monitor.stop()
        await asyncio.sleep(0.5)  # Let monitor clean up
        print("✅ Monitor stopped cleanly")


if __name__ == "__main__":
    asyncio.run(main())
