# Playwright E2E Testing

> **Note:** This file is in the `can-be-deleted` folder and is optional.
> See [docs/developer/playwright_testing.md](../docs/developer/playwright_testing.md) for the comprehensive guide.

Quick start guide for running end-to-end tests with Playwright.

## Setup

1. Install dependencies:
```powershell
uv sync --group dev
```

2. Install Playwright browsers:
```powershell
uv run playwright install chromium
```

## Running Tests

### Basic Usage

```powershell
# Run all E2E tests
uv run pytest tests/e2e -m e2e

# Run specific test file
uv run pytest tests/e2e/test_homepage.py -m e2e

# Run with visible browser (watch tests execute)
$env:HEADLESS="false"; uv run pytest tests/e2e -m e2e

# Run with slow motion (easier to follow)
$env:SLOW_MO="1000"; uv run pytest tests/e2e -m e2e
```

### Debugging

```powershell
# Debug mode with Playwright Inspector
$env:PWDEBUG="1"; uv run pytest tests/e2e/test_homepage.py -m e2e

# View trace from failed test
uv run playwright show-trace tests/e2e/traces/test_name.zip
```

### Test Artifacts

After running tests, check these directories:
- `tests/e2e/screenshots/` - Screenshots captured during tests
- `tests/e2e/traces/` - Detailed execution traces (on failure)
- `tests/e2e/videos/` - Video recordings (if enabled)

## Writing Tests

### Example Test

```python
import pytest
from playwright.sync_api import Page, expect

class TestFeature:
    @pytest.mark.e2e
    def test_something(self, page: Page, ledfx_server):
        """Test description."""
        page.goto("http://localhost:8888")
        page.click("button[aria-label='Add']")
        expect(page.locator(".success-message")).to_be_visible()
```

### Using Test Helpers

```python
from tests.e2e.test_helpers import crop_to_720p, wait_with_screenshots

@pytest.mark.e2e
def test_with_helpers(self, page: Page, ledfx_server):
    page.goto("http://localhost:8888")
    page.screenshot(path="tests/e2e/screenshots/example.png", full_page=True)
    crop_to_720p("tests/e2e/screenshots/example.png")
```

## Test Structure

```
tests/e2e/
├── config.py                  # Configuration
├── conftest.py                # Pytest fixtures
├── test_helpers.py            # Helper functions
└── test_homepage.py           # Navigation test

can-be-deleted/
├── README.md                  # This file (optional)
├── QUICK_REFERENCE.txt        # Quick reference (optional)
├── FULL_REFERENCE.txt         # Complete reference (optional)
├── page_objects.py            # Page Object Models templates (optional)
├── run_e2e_tests.py           # Helper script (optional)
├── pytest_config_example.py   # Config examples (optional)
└── github_workflow_example.py # CI/CD template (optional)
```

## Configuration

Edit `tests/e2e/config.py` to configure:
- Timeouts
- Browser settings
- Screenshot/video/trace options
- Viewport size

Environment variables:
```powershell
$env:LEDFX_TEST_URL="http://localhost:8888"  # Base URL
$env:HEADLESS="true"                          # Headless mode
$env:SLOW_MO="0"                             # Slow motion (ms)
$env:VIDEO="false"                           # Record videos
$env:TRACE="on-first-retry"                  # Trace on failure
```

## Common Issues

**Tests timeout**: Increase `TIMEOUT` in `tests/e2e/config.py`

**Server won't start**: Check if port 8888 is in use:
```powershell
Get-NetTCPConnection -LocalPort 8888
```

**Selectors not found**: Use codegen to find selectors:
```powershell
uv run playwright codegen http://localhost:8888
```

## Documentation

See [docs/developer/playwright_testing.md](../docs/developer/playwright_testing.md) for comprehensive documentation.

## Resources

- [Playwright Documentation](https://playwright.dev/)
- [pytest-playwright](https://github.com/microsoft/playwright-pytest)
- [Best Practices](https://playwright.dev/docs/best-practices)
