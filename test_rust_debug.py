#!/usr/bin/env python3

"""
Simple test to demonstrate particle count tracking in Rust effects.
"""

import logging
import time

import numpy as np

# Set up logging to see debug messages
logging.basicConfig(
    level=logging.DEBUG, format="%(asctime)s - %(levelname)s - %(message)s"
)

try:
    import ledfx_rust_effects

    print("Successfully imported Rust effects module")
except ImportError as e:
    print(f"Import error: {e}")
    exit(1)


def test_rust_particle_debug():
    """Test Rust flame effect particle debugging"""
    print("\n=== Testing Rust Flame Particle Debug ===")

    # Create test data
    test_image = np.zeros((32, 64, 3), dtype=np.uint8)
    audio_powers = np.array([0.8, 0.6, 0.4], dtype=np.float32)

    print("Running flame effect for 5 seconds with particle count tracking...")
    start_time = time.time()
    last_report = 0.0
    frame_count = 0

    while time.time() - start_time < 5.0:
        # Run flame effect
        try:
            flame_result = ledfx_rust_effects.rusty_flame_process(
                test_image, 0.0, audio_powers, 1.0, 0.016, 0.8, 0.5, 2
            )
            frame_count += 1

            # Report particle counts every 1 second
            current_time = time.time()
            if current_time - last_report >= 1.0:
                try:
                    particle_counts = (
                        ledfx_rust_effects.get_flame_particle_counts()
                    )
                    total_particles = sum(particle_counts)
                    print(
                        f"Frame {frame_count}: RustFlame particles - Low: {particle_counts[0]}, "
                        f"Mid: {particle_counts[1]}, High: {particle_counts[2]}, "
                        f"Total: {total_particles}"
                    )
                    last_report = current_time
                except Exception as e:
                    print(f"Failed to get particle counts: {e}")

            time.sleep(0.016)  # ~60 FPS

        except Exception as e:
            print(f"Error running flame effect: {e}")
            break

    print(f"Completed {frame_count} frames in 5 seconds")

    # Final particle count
    try:
        particle_counts = ledfx_rust_effects.get_flame_particle_counts()
        total_particles = sum(particle_counts)
        print(
            f"\nFinal particle counts - Low: {particle_counts[0]}, "
            f"Mid: {particle_counts[1]}, High: {particle_counts[2]}, "
            f"Total: {total_particles}"
        )
    except Exception as e:
        print(f"Failed to get final particle counts: {e}")


def main():
    print("Testing Rust flame effect particle debug logging...")
    test_rust_particle_debug()
    print("\n=== Debug Test Complete ===")
    print(
        "This demonstrates the particle count tracking that will also work in the rusty2d effect"
    )


if __name__ == "__main__":
    main()
