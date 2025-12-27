"""
E2E test for LedFx web interface.

Tests navigation and UI interactions with screenshots.
"""

import re
import time

import pytest
from playwright.sync_api import Page, expect

from tests.e2e.config import BASE_URL
from tests.e2e.test_helpers import crop_to_720p, wait_with_screenshots


class TestLedFx:
    """Test suite for LedFx E2E testing."""

    @pytest.mark.e2e
    def test_navigation_and_about(self, page: Page, ledfx_server):
        """
        Test navigation through the UI and verify About page information.

        This test:
        - Loads the homepage
        - Skips the welcome dialog
        - Navigates to Settings
        - Checks About page
        - Takes screenshots at each step
        """
        # Navigate to LedFx
        page.goto(BASE_URL)
        page.wait_for_load_state("networkidle")
        
        # Screenshot 1: Homepage
        page.screenshot(path="tests/e2e/screenshots/01_homepage.png", full_page=True)
        crop_to_720p("tests/e2e/screenshots/01_homepage.png")
        print("\n📸 Screenshot 1: Homepage")

        # Click Skip button
        page.get_by_role("button", name="Skip").click()
        time.sleep(1)
        page.screenshot(path="tests/e2e/screenshots/02_after_skip.png", full_page=True)
        crop_to_720p("tests/e2e/screenshots/02_after_skip.png")
        print("📸 Screenshot 2: After skip")

        # Navigate to Settings
        page.get_by_role("link", name="Settings").click()
        page.wait_for_load_state("networkidle")
        time.sleep(1)
        page.screenshot(path="tests/e2e/screenshots/03_settings.png", full_page=True)
        crop_to_720p("tests/e2e/screenshots/03_settings.png")
        print("📸 Screenshot 3: Settings page")

        # Click General button
        page.get_by_role("button", name="General").click()
        time.sleep(1)
        page.screenshot(path="tests/e2e/screenshots/04_general.png", full_page=True)
        crop_to_720p("tests/e2e/screenshots/04_general.png")
        print("📸 Screenshot 4: General settings")

        # Click About button
        page.get_by_role("button", name="About").click()
        time.sleep(1)
        page.screenshot(path="tests/e2e/screenshots/05_about.png", full_page=True)
        crop_to_720p("tests/e2e/screenshots/05_about.png")
        print("📸 Screenshot 5: About page")

        # Verify version (2.1.2 or higher, including beta patterns like 2.1.3-b4)
        version_text = page.get_by_label("About LedFx").text_content()
        version_match = re.search(r"(\d+)\.(\d+)\.(\d+)(?:-b\d+)?", version_text)
        assert version_match, f"No version found in: {version_text}"
        major, minor, patch = map(int, version_match.groups())
        assert (major, minor, patch) >= (2, 1, 2), f"Version {version_match.group()} is below minimum 2.1.2"
        print(f"✅ Version check passed: {version_match.group()}")

        print("\n✅ Navigation test completed with 5 screenshots")
