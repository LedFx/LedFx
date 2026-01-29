"""
Playwright configuration for LedFx E2E tests.

This configuration sets up Playwright for testing the LedFx web interface.
Tests run against a local LedFx instance started by the test suite.
"""

import os

from tests.test_utilities.consts import BASE_PORT

# Base URL for the LedFx web interface
BASE_URL = os.getenv("LEDFX_TEST_URL", f"http://localhost:{BASE_PORT}")

# Timeout settings (in milliseconds)
TIMEOUT = 30000  # 30 seconds
NAVIGATION_TIMEOUT = 30000  # 30 seconds

# Browser settings
HEADLESS = os.getenv("HEADLESS", "true").lower() == "true"
SLOW_MO = int(os.getenv("SLOW_MO", "0"))  # Slow down by N ms

# Screenshot settings
SCREENSHOT_ON_FAILURE = True
SCREENSHOT_PATH = "tests/e2e/screenshots"

# Video settings
VIDEO_ENABLED = os.getenv("VIDEO", "true").lower() == "true"
VIDEO_PATH = "tests/e2e/videos"

# Trace settings
TRACE_ENABLED = os.getenv(
    "TRACE", "on"
)  # 'on', 'off', 'retain-on-failure', 'on-first-retry'
TRACE_PATH = "tests/e2e/traces"

# Viewport settings
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 720

# Browser configuration for pytest-playwright
PLAYWRIGHT_CONFIG = {
    "base_url": BASE_URL,
    "timeout": TIMEOUT,
    "headless": HEADLESS,
    "slow_mo": SLOW_MO,
    "viewport": {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
    "screenshot": {
        "mode": "on" if SCREENSHOT_ON_FAILURE else "off",
        "full_page": True,
    },
    "video": {
        "mode": "on" if VIDEO_ENABLED else "off",
        "size": {"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT},
    },
    "trace": TRACE_ENABLED,
}

# Test paths
TEST_PATHS = ["tests/e2e"]

# Browsers to test on
BROWSERS = [
    "chromium"
]  # Can add 'firefox', 'webkit' for cross-browser testing
