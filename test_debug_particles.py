#!/usr/bin/env python3

"""
Test script to demonstrate particle debug logging for both flame2d and rusty2d effects.
"""

import logging
import time

import numpy as np
from PIL import Image

# Set up logging to see debug messages
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

# Import effects
try:
    from ledfx.effects.flame2d import Flame2d
    from ledfx.effects.rusty2d import Rusty2d

    print("Successfully imported both effects")
except ImportError as e:
    print(f"Import error: {e}")
    exit(1)


class MockLedFx:
    """Mock LedFx object for testing"""

    pass


class MockAudio:
    """Mock audio data"""

    def __init__(self):
        self.power = np.array([0.8, 0.6, 0.4], dtype=np.float32)
        self.power_filtered = np.array([0.7, 0.5, 0.3], dtype=np.float32)
        self.bass = 0.8


def test_effect_debug(effect_class, effect_name, config):
    """Test an effect and show debug output"""
    print(f"\n=== Testing {effect_name} ===")

    # Create effect instance
    mock_ledfx = MockLedFx()
    effect = effect_class(mock_ledfx, config)

    # Set up effect dimensions
    effect.r_width = 64
    effect.r_height = 32
    effect.r_pixels = np.zeros((32, 64, 3), dtype=np.float32)
    effect.matrix = Image.fromarray(np.zeros((32, 64, 3), dtype=np.uint8))

    # Mock audio data
    mock_audio = MockAudio()
    effect.audio_data_updated(mock_audio)

    print(f"Running {effect_name} for 3 seconds with debug output...")
    start_time = time.time()
    frame_count = 0

    while time.time() - start_time < 3.0:
        # Update time for effect
        effect.passed = 0.016  # ~60 FPS

        # Run the effect
        try:
            effect.draw()
            frame_count += 1
            time.sleep(0.016)  # Simulate 60 FPS
        except Exception as e:
            print(f"Error in {effect_name}: {e}")
            break

    print(f"{effect_name} completed {frame_count} frames in 3 seconds")


def main():
    print("Testing particle debug logging for flame effects...")

    # Test configurations
    flame2d_config = {
        "spawn_rate": 0.8,
        "velocity": 0.5,
        "intensity": 0.7,
        "blur_amount": 2,
        "low_band": "#FF0000",
        "mid_band": "#00FF00",
        "high_band": "#0000FF",
    }

    rusty2d_config = {
        "effect_type": "flame",
        "spawn_rate": 0.8,
        "velocity": 0.5,
        "intensity": 0.7,
        "blur_amount": 2,
        "low_band": "#FF0000",
        "mid_band": "#00FF00",
        "high_band": "#0000FF",
    }

    # Test Python flame2d effect
    test_effect_debug(Flame2d, "Flame2d (Python)", flame2d_config)

    # Test Rust rusty2d effect
    test_effect_debug(Rusty2d, "Rusty2d (Rust)", rusty2d_config)

    print("\n=== Debug Test Complete ===")
    print(
        "Check the debug output above for particle count reports every 1 second"
    )


if __name__ == "__main__":
    main()
