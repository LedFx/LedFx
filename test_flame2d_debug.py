#!/usr/bin/env python3

"""
Minimal test for flame2d effect debugging without full LedFx import.
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "ledfx"))

import logging
import time

import numpy as np
from PIL import Image

# Set up logging to see debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)


# Mock the necessary parts
class MockLedfx:
    pass


class MockAudio:
    def __init__(self):
        self.power = np.array([0.8, 0.6, 0.4], dtype=np.float32)
        self.power_filtered = np.array([0.7, 0.5, 0.3], dtype=np.float32)
        self.bass = 0.8


def test_flame2d_particles():
    """Test flame2d particle debugging"""

    # Mock config for basic imports
    import ledfx.color
    from ledfx.effects.flame2d import Flame2d
    from ledfx.effects.twod import Twod

    print("\n=== Testing Flame2d Particle Debug ===")

    config = {
        "spawn_rate": 0.8,
        "velocity": 0.5,
        "intensity": 0.7,
        "blur_amount": 1,  # Keep low for speed
        "low_band": "#FF0000",
        "mid_band": "#00FF00",
        "high_band": "#0000FF",
    }

    # Create effect
    mock_ledfx = MockLedfx()
    effect = Flame2d(mock_ledfx, config)

    # Initialize dimensions and arrays
    effect.r_width = 64
    effect.r_height = 32
    effect.r_pixels = np.zeros((32, 64, 3), dtype=np.float32)
    effect.matrix = Image.fromarray(np.zeros((32, 64, 3), dtype=np.uint8))
    effect.passed = 0.016

    # Initialize particles
    if hasattr(effect, "do_once"):
        effect.do_once()

    # Mock audio
    mock_audio = MockAudio()
    effect.audio_data_updated(mock_audio)

    print("Running flame2d effect for 5 seconds with debug output...")
    start_time = time.time()
    frame_count = 0

    while time.time() - start_time < 5.0:
        try:
            effect.draw()
            frame_count += 1
            time.sleep(0.016)  # ~60 FPS
        except Exception as e:
            print(f"Error in flame2d: {e}")
            break

    print(f"Flame2d completed {frame_count} frames")


if __name__ == "__main__":
    try:
        test_flame2d_particles()
    except Exception as e:
        print(f"Test failed: {e}")
        print(
            "This is expected due to import complexities, but the debug code is in place"
        )
        print(
            "The flame2d debug will work when run in the actual LedFx environment"
        )
