"""
Helper functions for E2E tests.

Utility functions for screenshot handling and test workflows.
"""

import time

from PIL import Image
from playwright.sync_api import Page


def crop_to_720p(image_path: str):
    """
    Crop image to 1280x720 from the top.

    Args:
        image_path: Path to the image file
    """
    img = Image.open(image_path)
    width, height = img.size

    # If image is taller than 720, crop from top
    if height > 720:
        img_cropped = img.crop((0, 0, 1280, 720))
        img_cropped.save(image_path)
        print(f"  ✂️  Cropped from {width}x{height} to 1280x720")


def wait_with_screenshots(page: Page, seconds: int, prefix: str):
    """
    Wait for specified seconds, taking a screenshot every second.

    Args:
        page: Playwright page instance
        seconds: Number of seconds to wait
        prefix: Prefix for screenshot filenames
    """
    for i in range(seconds):
        time.sleep(1)
        screenshot_path = f"tests/e2e/screenshots/{prefix}_{i+1}s.png"
        page.screenshot(path=screenshot_path, full_page=True)
        crop_to_720p(screenshot_path)
        print(f"📸 {prefix} at {i+1}s")
