"""
Example pytest configuration additions for Playwright tests.

Add these to your pyproject.toml [tool.pytest.ini_options] section
to properly configure Playwright testing.
"""

# Example configuration to add to pyproject.toml:
"""
[tool.pytest.ini_options]
markers = [
    "e2e: End-to-end tests using Playwright (deselect with '-m \"not e2e\"')",
    "slow: Slow-running tests",
]

# Playwright-specific options
addopts = [
    "--headed",           # Show browser by default (override with --headless)
    "--browser=chromium", # Default browser
]
"""

# Note: The actual configuration should be added to pyproject.toml manually
