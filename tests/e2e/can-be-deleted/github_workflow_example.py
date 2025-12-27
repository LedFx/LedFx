"""
Example GitHub Actions workflow for running Playwright E2E tests.

Save this as .github/workflows/e2e-tests.yml to enable automated E2E testing.
"""

GITHUB_WORKFLOW = """
name: Playwright E2E Tests

on:
  push:
    branches: [ main, dev ]
  pull_request:
    branches: [ main, dev ]
  workflow_dispatch:  # Allow manual triggering

jobs:
  test-e2e:
    name: Run E2E Tests
    runs-on: ubuntu-latest
    timeout-minutes: 30
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          submodules: recursive  # For frontend submodule
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install uv
        uses: astral-sh/setup-uv@v4
      
      - name: Install Python dependencies
        run: uv sync --group dev
      
      - name: Install Playwright browsers
        run: uv run playwright install chromium --with-deps
      
      - name: Run E2E tests
        env:
          HEADLESS: 'true'
          VIDEO: 'true'
          TRACE: 'on-first-retry'
        run: |
          uv run pytest tests/e2e -m e2e -v --tb=short
      
      - name: Upload test artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: playwright-test-results
          path: |
            tests/e2e/screenshots/
            tests/e2e/videos/
            tests/e2e/traces/
          retention-days: 7
      
      - name: Upload test report
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: pytest-report
          path: pytest-report.html
          retention-days: 7

  test-e2e-cross-browser:
    name: Cross-Browser E2E Tests
    runs-on: ubuntu-latest
    timeout-minutes: 45
    if: github.event_name == 'pull_request'  # Only on PRs
    
    strategy:
      fail-fast: false
      matrix:
        browser: [chromium, firefox, webkit]
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          submodules: recursive
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install uv
        uses: astral-sh/setup-uv@v4
      
      - name: Install Python dependencies
        run: uv sync --group dev
      
      - name: Install Playwright browsers
        run: uv run playwright install ${{ matrix.browser }} --with-deps
      
      - name: Run E2E tests on ${{ matrix.browser }}
        env:
          HEADLESS: 'true'
          BROWSER: ${{ matrix.browser }}
        run: |
          uv run pytest tests/e2e -m e2e --browser=${{ matrix.browser }} -v
      
      - name: Upload artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: ${{ matrix.browser }}-test-results
          path: |
            tests/e2e/screenshots/
            tests/e2e/traces/
          retention-days: 7

  test-e2e-windows:
    name: E2E Tests on Windows
    runs-on: windows-latest
    timeout-minutes: 30
    if: github.event_name == 'pull_request'  # Only on PRs
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
        with:
          submodules: recursive
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Install uv
        uses: astral-sh/setup-uv@v4
      
      - name: Install Python dependencies
        run: uv sync --group dev
      
      - name: Install Playwright browsers
        run: uv run playwright install chromium --with-deps
      
      - name: Run E2E tests
        env:
          HEADLESS: 'true'
        run: |
          uv run pytest tests/e2e -m e2e -v
      
      - name: Upload artifacts on failure
        if: failure()
        uses: actions/upload-artifact@v4
        with:
          name: windows-test-results
          path: |
            tests/e2e/screenshots/
            tests/e2e/traces/
          retention-days: 7
"""

if __name__ == "__main__":
    print("To add this workflow to your repository:")
    print("1. Create directory: .github/workflows/")
    print("2. Save the GITHUB_WORKFLOW content as: .github/workflows/e2e-tests.yml")
    print("3. Commit and push to GitHub")
    print()
    print(GITHUB_WORKFLOW)
