# Playwright End-to-End Testing Guide

This guide covers end-to-end (E2E) testing for the LedFx web interface using Playwright.

## Table of Contents

- [Overview](#overview)
- [Setup](#setup)
- [Running Tests](#running-tests)
- [Writing Tests](#writing-tests)
- [Test Structure](#test-structure)
- [Best Practices](#best-practices)
- [Debugging](#debugging)
- [CI/CD Integration](#cicd-integration)

## Overview

LedFx uses [Playwright](https://playwright.dev/) for end-to-end browser testing. Playwright provides:

- **Cross-browser testing**: Chromium, Firefox, and WebKit
- **Auto-wait**: Automatically waits for elements to be ready
- **Network interception**: Mock or monitor API calls
- **Screenshots & videos**: Capture test failures
- **Traces**: Detailed debugging information

### Current Tests

The project includes a complete working example:
- **Navigation test** (`test_homepage.py`): Full UI navigation flow with screenshots
  - Homepage loading
  - Welcome dialog interaction
  - Settings navigation
  - About page verification
  - Version checking

## Setup

### Prerequisites

- Python 3.10 or higher
- uv package manager
- Node.js (for Playwright browsers)

### Installation

1. **Install dependencies** with the dev group:

```powershell
uv sync --group dev
```

2. **Install Playwright browsers**:

```powershell
uv run playwright install chromium
```

For all browsers (optional):

```powershell
uv run playwright install
```

3. **Verify installation**:

```powershell
uv run playwright --version
```

### Project Structure

```
tests/
└── e2e/                           # E2E test directory
    ├── __init__.py                # Package marker
    ├── config.py                  # Playwright configuration
    ├── conftest.py                # Pytest fixtures
    ├── test_helpers.py            # Helper functions (crop_to_720p, etc.)
    ├── test_homepage.py           # Navigation test example
    ├── screenshots/               # Screenshots (created during tests)
    ├── videos/                    # Videos (when enabled)
    ├── traces/                    # Traces (on failure)
    └── can-be-deleted/            # Optional files (templates & examples)
        ├── README.md              # Quick start guide (optional)
        ├── QUICK_REFERENCE.txt    # Minimal quick reference (optional)
        ├── FULL_REFERENCE.txt     # Complete command reference (optional)
        ├── page_objects.py        # Page Object Models templates (optional)
        ├── run_e2e_tests.py       # Helper script (optional)
        ├── pytest_config_example.py   # Configuration examples (optional)
        └── github_workflow_example.py # CI/CD template (optional)
```

## Running Tests

### Run All E2E Tests

```powershell
uv run pytest tests/e2e -m e2e
```

### Run Specific Test File

```powershell
uv run pytest tests/e2e/test_homepage.py -m e2e
```

### Run Specific Test

```powershell
uv run pytest tests/e2e/test_homepage.py::TestLedFx::test_navigation_and_about -m e2e
```

### Run with Headed Browser (Watch Tests Run)

```powershell
$env:HEADLESS="false"; uv run pytest tests/e2e -m e2e
```

### Run with Slow Motion (Easier to Follow)

```powershell
$env:SLOW_MO="500"; uv run pytest tests/e2e -m e2e
```

### Run with Video Recording

```powershell
$env:VIDEO="true"; uv run pytest tests/e2e -m e2e
```

### Run with Verbose Output

```powershell
uv run pytest tests/e2e -m e2e -v
```

### Run Tests in Parallel (Faster)

```powershell
uv run pytest tests/e2e -m e2e -n auto
```

## Writing Tests

### Basic Test Structure

```python
import pytest
from playwright.sync_api import Page, expect

class TestFeature:
    @pytest.mark.e2e
    def test_something(self, page: Page, ledfx_server):
        """Test description."""
        # Navigate to page
        page.goto("http://localhost:8888")

        # Interact with elements
        page.click("button[aria-label='Add']")

        # Assert expectations
        expect(page.locator(".success-message")).to_be_visible()
```

### Using Test Helpers

The project includes helper functions for common test operations:

```python
from tests.e2e.test_helpers import crop_to_720p, wait_with_screenshots
from tests.e2e.config import BASE_URL

@pytest.mark.e2e
def test_with_helpers(self, page: Page, ledfx_server):
    """Test using helper functions."""
    # Navigate and interact
    page.goto(BASE_URL)
    page.get_by_role("button", name="Skip").click()

    # Take and crop screenshot
    page.screenshot(path="tests/e2e/screenshots/example.png", full_page=True)
    crop_to_720p("tests/e2e/screenshots/example.png")

    # Wait with screenshots for debugging
    wait_with_screenshots(page, ".settings-page", "settings_loaded")
```

### Page Objects (Available for Future Tests)

Page objects are available in `page_objects.py` for when you add more tests:

```python
from tests.e2e.page_objects import DevicePageObject

@pytest.mark.e2e
def test_add_device(self, page: Page, ledfx_server):
    """Test adding a new device."""
    device_page = DevicePageObject(page, "http://localhost:8888")
    device_page.navigate()
    # ... use page object methods
```

### Waiting for Elements

Playwright has built-in auto-waiting, but you can be explicit:

```python
# Wait for element to be visible
page.wait_for_selector(".device-list", state="visible")

# Wait for API call
with page.expect_response(lambda r: "/api/devices" in r.url):
    page.click("button[aria-label='Refresh']")

# Wait for navigation
with page.expect_navigation():
    page.click("a[href='/settings']")
```

### Interacting with Elements

```python
# Click
page.click("button.submit")
page.get_by_role("button", name="Submit").click()

# Fill input
page.fill("input[name='device-name']", "My Device")

# Select option
page.select_option("select[name='device-type']", "wled")

# Upload file
page.set_input_files("input[type='file']", "path/to/file.gif")

# Hover
page.hover(".tooltip-trigger")

# Check/uncheck
page.check("input[type='checkbox']")
page.uncheck("input[type='checkbox']")
```

### Assertions

Use Playwright's `expect` for better error messages:

```python
from playwright.sync_api import expect

# Visibility
expect(page.locator(".success-message")).to_be_visible()
expect(page.locator(".loading")).to_be_hidden()

# Text content
expect(page.locator("h1")).to_have_text("LedFx Dashboard")
expect(page.locator(".error")).to_contain_text("Invalid")

# Attributes
expect(page.locator("input")).to_have_attribute("disabled", "")
expect(page.locator("input")).to_have_value("100")

# Count
expect(page.locator(".device-item")).to_have_count(3)

# URL
expect(page).to_have_url("http://localhost:8888/devices")
expect(page).to_have_title("LedFx")
```

### Network Interception

```python
# Monitor requests
def handle_request(request):
    if "/api/devices" in request.url:
        print(f"Device API called: {request.method}")

page.on("request", handle_request)

# Mock responses
def handle_route(route):
    if "/api/devices" in route.request.url:
        route.fulfill(
            status=200,
            body='{"devices": []}',
            headers={"Content-Type": "application/json"}
        )
    else:
        route.continue_()

page.route("**/api/**", handle_route)
```

### Taking Screenshots

```python
# Full page screenshot
page.screenshot(path="screenshot.png", full_page=True)

# Element screenshot
page.locator(".dashboard").screenshot(path="dashboard.png")
```

## Test Structure

### Fixtures (conftest.py)

Key fixtures available to all tests:

- **`ledfx_server`**: Starts LedFx server (session scope)
- **`browser`**: Playwright browser instance (session scope)
- **`context`**: Browser context with tracing (function scope)
- **`page`**: Page instance with auto-screenshot on failure (function scope)

### Test Organization

Organize tests by feature/page:

```python
class TestDeviceManagement:
    """Tests for device management features."""

    @pytest.mark.e2e
    def test_add_device(self, page, ledfx_server):
        """Test adding a device."""
        pass

    @pytest.mark.e2e
    def test_edit_device(self, page, ledfx_server):
        """Test editing a device."""
        pass

    @pytest.mark.e2e
    def test_delete_device(self, page, ledfx_server):
        """Test deleting a device."""
        pass
```

### Marking Tests

Use pytest marks for test categorization:

```python
@pytest.mark.e2e              # E2E test
@pytest.mark.slow             # Long-running test
@pytest.mark.skip             # Skip test
@pytest.mark.skipif           # Conditional skip
@pytest.mark.xfail            # Expected to fail
```

## Best Practices

### 1. Use Meaningful Selectors

Prefer semantic selectors over CSS classes:

```python
# Good
page.get_by_role("button", name="Submit")
page.get_by_label("Device Name")
page.get_by_text("Success!")

# Avoid
page.locator(".btn-primary-123")
page.locator("div > div > button")
```

### 2. Add Test IDs for Reliability

In your React/Vue components, add data-testid attributes:

```jsx
<button data-testid="add-device-btn">Add Device</button>
```

Then use in tests:

```python
page.locator('[data-testid="add-device-btn"]').click()
```

### 3. Keep Tests Independent

Each test should be able to run independently:

```python
# Good - self-contained
def test_add_device(self, page, ledfx_server):
    device_page = DevicePageObject(page, BASE_URL)
    device_page.navigate()
    device_page.click_add_device()
    # ... complete test

# Bad - depends on previous test state
def test_edit_device(self, page, ledfx_server):
    # Assumes device already exists from previous test
    page.click(".device-item:first-child")
```

### 4. Use Helper Functions and Page Objects

Use the provided helper functions:

```python
from tests.e2e.test_helpers import crop_to_720p

# Crop screenshots to 720p for consistent sizing
page.screenshot(path="screenshot.png", full_page=True)
crop_to_720p("screenshot.png")
```

Create page objects for complex pages when adding new tests:

```python
class DevicePageObject:
    def __init__(self, page, base_url):
        self.page = page
        self.base_url = base_url

    def navigate(self):
        self.page.goto(f"{self.base_url}/devices")

    def add_device(self, name, ip):
        # Encapsulate complex interactions
        pass
```

### 5. Handle Async Operations

Wait for async operations to complete:

```python
# Wait for API call
with page.expect_response(lambda r: "/api/devices" in r.url):
    page.click("button.refresh")

# Wait for element
page.wait_for_selector(".device-list")

# Wait for loading to disappear
page.wait_for_selector(".loading", state="hidden")
```

### 6. Clean Up Test Data

Use fixtures to clean up after tests:

```python
@pytest.fixture
def test_device(page, ledfx_server):
    """Create and cleanup test device."""
    # Setup
    device_page = DevicePageObject(page, BASE_URL)
    device_page.create_device("Test Device", "192.168.1.100", 100)

    yield "Test Device"

    # Teardown
    device_page.delete_device("Test Device")
```

## Debugging

### View Trace in Playwright Inspector

When a test fails, a trace file is saved to `tests/e2e/traces/`:

```powershell
uv run playwright show-trace tests/e2e/traces/test_name.zip
```

This opens an interactive viewer showing:
- Network requests
- Screenshots at each step
- Console logs
- DOM snapshots

### Debug Mode

Run tests in debug mode with Playwright Inspector:

```powershell
$env:PWDEBUG="1"; uv run pytest tests/e2e/test_homepage.py::TestLedFx::test_navigation_and_about -m e2e
```

This allows you to:
- Step through test execution
- Inspect elements
- Try selectors in console
- View network activity

### Screenshots

Failed tests automatically capture screenshots in `tests/e2e/screenshots/`.

Manually capture screenshots in tests:

```python
page.screenshot(path="debug.png", full_page=True)
page.locator(".problem-element").screenshot(path="element.png")
```

### Console Logs

Capture and print console messages:

```python
def test_with_console_logging(page, ledfx_server):
    page.on("console", lambda msg: print(f"Console: {msg.text}"))
    page.goto(BASE_URL)
    # Console messages will be printed to test output
```

### Slow Motion

Slow down test execution to see what's happening:

```powershell
$env:SLOW_MO="1000"; uv run pytest tests/e2e -m e2e
```

## CI/CD Integration

### GitHub Actions Example

```yaml
name: E2E Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install uv
        uses: astral-sh/setup-uv@v4

      - name: Install dependencies
        run: uv sync --group dev

      - name: Install Playwright browsers
        run: uv run playwright install chromium --with-deps

      - name: Run E2E tests
        run: uv run pytest tests/e2e -m e2e

      - name: Upload test artifacts
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: test-results
          path: |
            tests/e2e/screenshots/
            tests/e2e/traces/
```

### Environment Variables

Configure tests via environment variables:

```powershell
$env:LEDFX_TEST_URL="http://localhost:8888"
$env:HEADLESS="true"
$env:SLOW_MO="0"
$env:VIDEO="false"
$env:TRACE="on-first-retry"
```

## Troubleshooting

### Tests Timeout

Increase timeout in [tests/e2e/config.py](../../tests/e2e/config.py):

```python
TIMEOUT = 60000  # 60 seconds
```

### Server Won't Start

Check if port 8888 is already in use:

```powershell
Get-NetTCPConnection -LocalPort 8888
```

### Selectors Not Found

Use Playwright's codegen to find reliable selectors:

```powershell
uv run playwright codegen http://localhost:8888
```

### Browser Won't Close

Ensure proper cleanup in fixtures or manually kill:

```powershell
Get-Process | Where-Object {$_.ProcessName -like "*playwright*"} | Stop-Process
```

## Additional Resources

- [Playwright Documentation](https://playwright.dev/)
- [pytest-playwright Plugin](https://github.com/microsoft/playwright-pytest)
- [Best Practices](https://playwright.dev/docs/best-practices)
- [Selectors Guide](https://playwright.dev/docs/selectors)
- [LedFx API Documentation](../apis/)

## Examples and References

### Essential Files
- [test_homepage.py](../../tests/e2e/test_homepage.py) - Complete navigation test with screenshots
  - Shows how to interact with UI elements
  - Demonstrates screenshot capture and cropping
  - Includes version verification
  - Uses Playwright's role-based selectors
- [test_helpers.py](../../tests/e2e/test_helpers.py) - Helper functions
  - `crop_to_720p()` - Screenshot cropping
  - `wait_with_screenshots()` - Wait with visual feedback
- [config.py](../../tests/e2e/config.py) - Configuration settings
- [conftest.py](../../tests/e2e/conftest.py) - Pytest fixtures

### Optional Templates (in tests/e2e/can-be-deleted/)
- [README.md](../../tests/e2e/can-be-deleted/README.md) - Quick start guide
- [QUICK_REFERENCE.txt](../../tests/e2e/can-be-deleted/QUICK_REFERENCE.txt) - Essential commands
- [FULL_REFERENCE.txt](../../tests/e2e/can-be-deleted/FULL_REFERENCE.txt) - Complete command reference
- [page_objects.py](../../tests/e2e/can-be-deleted/page_objects.py) - Page Object Models templates
- [run_e2e_tests.py](../../tests/e2e/can-be-deleted/run_e2e_tests.py) - Helper script
- [pytest_config_example.py](../../tests/e2e/can-be-deleted/pytest_config_example.py) - Configuration examples
- [github_workflow_example.py](../../tests/e2e/can-be-deleted/github_workflow_example.py) - CI/CD workflow template
