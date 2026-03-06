"""Example: Simple monitor that prints when devices change.

Run this example to manually test audio device detection:
    uv run python examples/monitor_print.py

Then plug/unplug audio devices to see the output.
"""

import asyncio
import logging
import sys

# Add src to path for local development
sys.path.insert(0, "../src")

from audio_hotplug import create_monitor  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


def on_devices_changed():
    """Callback when audio devices change."""
    print("🔊 Audio devices changed!")


async def main():
    """Run the monitor."""
    loop = asyncio.get_running_loop()

    print("Starting audio device monitor...")
    print("Plug or unplug audio devices to see detection in action.")
    print("Press Ctrl+C to stop.\n")

    monitor = create_monitor(loop=loop, debounce_ms=200)

    if monitor is None:
        print("❌ Audio device monitoring not supported on this platform")
        return

    monitor.start(on_devices_changed)
    print("✅ Monitor started. Waiting for device changes...\n")

    try:
        # Run forever
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        print("\n\nStopping monitor...")
        monitor.stop()
        print("✅ Monitor stopped")


if __name__ == "__main__":
    asyncio.run(main())
