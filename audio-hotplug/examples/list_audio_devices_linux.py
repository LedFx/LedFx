"""List current audio devices using pyudev (Linux only).

This script helps verify that pyudev can see audio devices on your system.

Run: uv run python examples/list_audio_devices_linux.py
"""

import sys

sys.path.insert(0, "../src")

try:
    import pyudev
except ImportError:
    print("❌ pyudev not installed. Install with: uv sync")
    sys.exit(1)


def list_audio_devices():
    """List all audio-related devices visible to udev."""
    print("=" * 70)
    print("Audio Devices (via pyudev)")
    print("=" * 70)
    print()

    context = pyudev.Context()
    
    # List all sound subsystem devices
    print("Sound Subsystem Devices:")
    print("-" * 70)
    
    count = 0
    for device in context.list_devices(subsystem="sound"):
        count += 1
        print(f"\n{count}. Device: {device.device_node or 'N/A'}")
        print(f"   System Name: {device.sys_name}")
        print(f"   System Path: {device.sys_path}")
        
        # Show useful properties
        if device.get("ID_MODEL"):
            print(f"   Model: {device.get('ID_MODEL')}")
        if device.get("ID_VENDOR"):
            print(f"   Vendor: {device.get('ID_VENDOR')}")
        if device.get("DEVNAME"):
            print(f"   Device Name: {device.get('DEVNAME')}")
    
    if count == 0:
        print("  (No sound devices found)")
    
    print()
    print("=" * 70)
    print(f"Total audio devices found: {count}")
    print("=" * 70)
    print()
    print("Note: The monitor watches for 'add' and 'remove' events in the")
    print("      'sound' subsystem. Try unplugging a USB audio device to")
    print("      see what disappears from this list.")
    print()


if __name__ == "__main__":
    list_audio_devices()
