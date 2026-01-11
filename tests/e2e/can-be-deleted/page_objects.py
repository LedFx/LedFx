"""
Utility functions and page object models for Playwright E2E tests.

This module provides reusable helpers for common testing patterns
in the LedFx web interface.
"""

from typing import Optional

from playwright.sync_api import Page


class PageHelpers:
    """Helper methods for common page interactions."""

    @staticmethod
    def wait_for_api_call(page: Page, url_pattern: str, timeout: int = 30000):
        """
        Wait for a specific API call to complete.

        Args:
            page: Playwright page instance
            url_pattern: URL pattern to match (regex supported)
            timeout: Maximum wait time in milliseconds

        Returns:
            Response object if successful, None otherwise
        """
        try:
            with page.expect_response(
                lambda response: url_pattern in response.url, timeout=timeout
            ) as response_info:
                return response_info.value
        except Exception:
            return None

    @staticmethod
    def wait_for_no_loading_indicators(page: Page, timeout: int = 10000):
        """
        Wait for all loading indicators to disappear.

        Args:
            page: Playwright page instance
            timeout: Maximum wait time in milliseconds
        """
        # Common loading indicator selectors
        loading_selectors = [
            ".loading",
            ".spinner",
            '[class*="loading"]',
            '[class*="spinner"]',
            '[role="progressbar"]',
        ]

        for selector in loading_selectors:
            try:
                page.wait_for_selector(
                    selector, state="hidden", timeout=timeout
                )
            except Exception:
                continue  # Selector might not exist, that's okay

    @staticmethod
    def screenshot_element(page: Page, selector: str, filename: str):
        """
        Take a screenshot of a specific element.

        Args:
            page: Playwright page instance
            selector: CSS selector for the element
            filename: Output filename for screenshot
        """
        element = page.locator(selector)
        if element.count() > 0:
            element.first.screenshot(path=filename)

    @staticmethod
    def get_console_messages(
        page: Page, message_type: str = "all"
    ) -> list[str]:
        """
        Collect console messages from the page.

        Args:
            page: Playwright page instance
            message_type: Type of messages to collect ("log", "error", "warning", "all")

        Returns:
            List of console message texts
        """
        messages = []

        def handle_console(msg):
            if message_type == "all" or msg.type == message_type:
                messages.append(msg.text)

        page.on("console", handle_console)
        return messages


class DevicePageObject:
    """Page Object Model for device management page."""

    def __init__(self, page: Page, base_url: str):
        """
        Initialize device page object.

        Args:
            page: Playwright page instance
            base_url: Base URL of the application
        """
        self.page = page
        self.base_url = base_url

    def navigate(self):
        """Navigate to the devices page."""
        self.page.goto(f"{self.base_url}/devices")
        self.page.wait_for_load_state("networkidle")

    def click_add_device(self):
        """Click the add device button."""
        add_button = self.page.get_by_role("button", name="Add")
        add_button.click()

    def fill_device_form(
        self, device_type: str, name: str, ip: str, pixel_count: int
    ):
        """
        Fill out the device creation form.

        Args:
            device_type: Type of device (e.g., "wled", "e131")
            name: Device name
            ip: IP address
            pixel_count: Number of pixels
        """
        # This is a template - adjust selectors based on actual UI
        self.page.fill('input[name="name"]', name)
        self.page.fill('input[name="ip"]', ip)
        self.page.fill('input[name="pixel_count"]', str(pixel_count))

    def submit_device_form(self):
        """Submit the device creation form."""
        submit_button = self.page.get_by_role("button", name="Submit")
        submit_button.click()

    def get_device_list(self) -> list[str]:
        """
        Get list of device names.

        Returns:
            List of device names currently displayed
        """
        # This is a template - adjust based on actual UI structure
        devices = self.page.locator('[data-testid="device-item"]')
        return [device.text_content() for device in devices.all()]

    def delete_device(self, device_name: str):
        """
        Delete a device by name.

        Args:
            device_name: Name of the device to delete
        """
        # This is a template - adjust based on actual UI structure
        device = self.page.locator(f'[data-device-name="{device_name}"]')
        delete_button = device.locator('[aria-label="Delete"]')
        delete_button.click()

        # Confirm deletion if there's a dialog
        confirm_button = self.page.get_by_role("button", name="Confirm")
        if confirm_button.is_visible():
            confirm_button.click()


class VirtualPageObject:
    """Page Object Model for virtual LED strips page."""

    def __init__(self, page: Page, base_url: str):
        """
        Initialize virtual page object.

        Args:
            page: Playwright page instance
            base_url: Base URL of the application
        """
        self.page = page
        self.base_url = base_url

    def navigate(self):
        """Navigate to the virtuals page."""
        self.page.goto(f"{self.base_url}/virtuals")
        self.page.wait_for_load_state("networkidle")

    def create_virtual(self, name: str, pixel_count: int):
        """
        Create a new virtual LED strip.

        Args:
            name: Name for the virtual strip
            pixel_count: Number of pixels
        """
        # Click add button
        add_button = self.page.get_by_role("button", name="Add")
        add_button.click()

        # Fill form (adjust selectors based on actual UI)
        self.page.fill('input[name="name"]', name)
        self.page.fill('input[name="pixel_count"]', str(pixel_count))

        # Submit
        submit_button = self.page.get_by_role("button", name="Create")
        submit_button.click()

    def apply_effect(self, virtual_name: str, effect_name: str):
        """
        Apply an effect to a virtual strip.

        Args:
            virtual_name: Name of the virtual strip
            effect_name: Name of the effect to apply
        """
        # This is a template - adjust based on actual UI structure
        virtual = self.page.locator(f'[data-virtual-name="{virtual_name}"]')
        effect_select = virtual.locator('[data-testid="effect-select"]')
        effect_select.click()

        # Select effect from dropdown
        effect_option = self.page.locator(f'[data-effect="{effect_name}"]')
        effect_option.click()

    def set_effect_parameter(self, parameter_name: str, value: str):
        """
        Set an effect parameter value.

        Args:
            parameter_name: Name of the parameter
            value: Value to set
        """
        # This is a template - adjust based on actual UI structure
        param_input = self.page.locator(f'input[name="{parameter_name}"]')
        param_input.fill(value)

    def start_virtual(self, virtual_name: str):
        """
        Start a virtual strip.

        Args:
            virtual_name: Name of the virtual strip
        """
        virtual = self.page.locator(f'[data-virtual-name="{virtual_name}"]')
        play_button = virtual.locator('[aria-label="Play"]')
        play_button.click()

    def stop_virtual(self, virtual_name: str):
        """
        Stop a virtual strip.

        Args:
            virtual_name: Name of the virtual strip
        """
        virtual = self.page.locator(f'[data-virtual-name="{virtual_name}"]')
        stop_button = virtual.locator('[aria-label="Stop"]')
        stop_button.click()


class SettingsPageObject:
    """Page Object Model for settings page."""

    def __init__(self, page: Page, base_url: str):
        """
        Initialize settings page object.

        Args:
            page: Playwright page instance
            base_url: Base URL of the application
        """
        self.page = page
        self.base_url = base_url

    def navigate(self):
        """Navigate to the settings page."""
        self.page.goto(f"{self.base_url}/settings")
        self.page.wait_for_load_state("networkidle")

    def set_audio_device(self, device_name: str):
        """
        Set the audio input device.

        Args:
            device_name: Name of the audio device
        """
        audio_select = self.page.locator('[data-testid="audio-device-select"]')
        audio_select.click()

        device_option = self.page.locator(f'[data-device="{device_name}"]')
        device_option.click()

    def save_settings(self):
        """Save current settings."""
        save_button = self.page.get_by_role("button", name="Save")
        save_button.click()


class AssertionHelpers:
    """Custom assertions for LedFx testing."""

    @staticmethod
    def assert_no_errors_in_console(
        page: Page, allowed_errors: Optional[list[str]] = None
    ):
        """
        Assert that no unexpected errors appear in the console.

        Args:
            page: Playwright page instance
            allowed_errors: List of error patterns to ignore
        """
        console_errors = []

        def handle_error(msg):
            if msg.type == "error":
                console_errors.append(msg.text)

        page.on("console", handle_error)

        # Wait a moment for any errors to appear
        page.wait_for_timeout(1000)

        # Filter out allowed errors
        if allowed_errors:
            unexpected_errors = [
                err
                for err in console_errors
                if not any(allowed in err for allowed in allowed_errors)
            ]
        else:
            unexpected_errors = console_errors

        assert (
            len(unexpected_errors) == 0
        ), f"Unexpected console errors: {unexpected_errors}"

    @staticmethod
    def assert_api_success(response):
        """
        Assert that an API response indicates success.

        Args:
            response: Playwright Response object
        """
        assert (
            response.status >= 200 and response.status < 300
        ), f"API call failed with status {response.status}"

        try:
            body = response.json()
            # LedFx API typically returns {"status": "success"} for successful operations
            if "status" in body:
                assert (
                    body["status"] == "success"
                ), f"API returned status: {body.get('status')}"
        except Exception:
            # Some responses might not be JSON or have status field
            pass
