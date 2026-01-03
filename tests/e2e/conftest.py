"""
Pytest fixtures and configuration for Playwright E2E tests.

This module provides shared fixtures and utilities for end-to-end testing
of the LedFx web interface using Playwright.
"""

import glob
import os
import subprocess
import time
from collections.abc import Generator

import pytest
from PIL import Image
from playwright.sync_api import Browser, BrowserContext, Page, Playwright

from tests.e2e.config import (
    BASE_URL,
    BROWSERS,
    PLAYWRIGHT_CONFIG,
    SCREENSHOT_PATH,
    TRACE_PATH,
    VIDEO_PATH,
)
from tests.test_utilities.consts import BASE_PORT
from tests.test_utilities.test_utils import EnvironmentCleanup



def convert_webm_to_mp4(webm_path: str, mp4_path: str):
    """
    Convert WebM video to MP4 using ffmpeg for VS Code compatibility.

    Args:
        webm_path: Path to WebM video file
        mp4_path: Output path for MP4 file
    """
    try:
        # Use ffmpeg to convert webm to mp4 with H.264 codec
        subprocess.run(
            [
                "ffmpeg",
                "-i",
                webm_path,
                "-c:v",
                "libx264",  # H.264 codec for wide compatibility
                "-preset",
                "fast",  # Faster encoding
                "-crf",
                "23",  # Quality (lower is better, 23 is default)
                "-pix_fmt",
                "yuv420p",  # Pixel format for compatibility
                "-y",  # Overwrite output file if it exists
                mp4_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            check=True,
        )
        print(f"  🎥 Created MP4: {os.path.basename(mp4_path)}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        # ffmpeg not available or conversion failed
        return False


@pytest.fixture(scope="function")
def ledfx_server(request) -> Generator[subprocess.Popen, None, None]:
    """
    Start LedFx server for E2E tests.

    This fixture starts a LedFx instance in a subprocess before running
    E2E tests and tears it down after all tests complete.

    Yields:
        subprocess.Popen: The LedFx server process
    """
    # Clean up any existing test configuration
    EnvironmentCleanup.cleanup_test_config_folder()

    # Start LedFx server
    process = subprocess.Popen(
        [
            "uv",
            "run",
            "ledfx",
            "-p",
            f"{BASE_PORT}",
            "--offline",
            "-c",
            "debug_config",
            "-vv",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    # Wait for server to start
    time.sleep(5)

    # Verify server is running
    if process.poll() is not None:
        pytest.fail("Failed to start LedFx server")

    yield process

    # Teardown: Stop the server
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()

    # Wait for Windows to release file handles
    time.sleep(1)

    # Cleanup test configuration
    EnvironmentCleanup.cleanup_test_config_folder()


@pytest.fixture(scope="session")
def browser_type_launch_args():
    """Configure browser launch arguments."""
    return {
        "headless": PLAYWRIGHT_CONFIG["headless"],
        "slow_mo": PLAYWRIGHT_CONFIG["slow_mo"],
    }


@pytest.fixture(scope="session")
def browser_context_args():
    """Configure browser context arguments."""
    return {
        "viewport": PLAYWRIGHT_CONFIG["viewport"],
        "base_url": BASE_URL,
        "ignore_https_errors": True,
    }


@pytest.fixture(scope="function")
def context(
    browser: Browser,
    browser_context_args: dict,
    request: pytest.FixtureRequest,
) -> Generator[BrowserContext, None, None]:
    """
    Create a new browser context for each test.

    This fixture provides test isolation by creating a fresh browser
    context with tracing and video recording enabled.

    Args:
        browser: Playwright browser instance
        browser_context_args: Browser context configuration
        request: Pytest request object for test metadata

    Yields:
        BrowserContext: Isolated browser context
    """
    # Create output directories
    os.makedirs(SCREENSHOT_PATH, exist_ok=True)
    os.makedirs(VIDEO_PATH, exist_ok=True)
    os.makedirs(TRACE_PATH, exist_ok=True)

    # Create context with video recording
    context = browser.new_context(
        **browser_context_args,
        record_video_dir=(
            VIDEO_PATH if PLAYWRIGHT_CONFIG["video"]["mode"] == "on" else None
        ),
    )

    # Start tracing
    trace_mode = PLAYWRIGHT_CONFIG["trace"]
    if trace_mode in ["on", "retain-on-failure", "on-first-retry"]:
        context.tracing.start(screenshots=True, snapshots=True, sources=True)

    yield context

    # Stop tracing and save on failure
    if trace_mode in ["on", "retain-on-failure", "on-first-retry"]:
        if request.node.rep_call.failed or trace_mode == "on":
            trace_file = os.path.join(
                TRACE_PATH,
                f"{request.node.name}.zip",
            )
            context.tracing.stop(path=trace_file)
        else:
            context.tracing.stop()

    # Close context and process videos
    context.close()

    # Convert WebM videos to GIF if video recording is enabled
    if PLAYWRIGHT_CONFIG["video"]["mode"] == "on":
        # Get the video file for this context (find the most recent one)
        video_files = glob.glob(os.path.join(VIDEO_PATH, "*.webm"))
        if video_files:
            # Sort by modification time to get the most recent
            latest_video = max(video_files, key=os.path.getmtime)

            # Rename to test name
            new_video_name = f"{request.node.name}.webm"
            new_video_path = os.path.join(VIDEO_PATH, new_video_name)

            # Rename the video file (os.replace overwrites if exists)
            if latest_video != new_video_path:
                os.replace(latest_video, new_video_path)
                print(f"  🎬 Renamed video to: {new_video_name}")

            # Create MP4 version for VS Code compatibility
            mp4_file = new_video_path.replace(".webm", ".mp4")
            convert_webm_to_mp4(new_video_path, mp4_file)


@pytest.fixture(scope="function")
def page(
    context: BrowserContext, request: pytest.FixtureRequest
) -> Generator[Page, None, None]:
    """
    Create a new page for each test.

    This fixture provides a fresh page instance with automatic screenshot
    capture on test failure.

    Args:
        context: Browser context
        request: Pytest request object for test metadata

    Yields:
        Page: Playwright page instance
    """
    page = context.new_page()

    # Set default timeout
    page.set_default_timeout(PLAYWRIGHT_CONFIG["timeout"])

    yield page

    # Screenshot on failure
    if (
        request.node.rep_call.failed
        and PLAYWRIGHT_CONFIG["screenshot"]["mode"] == "on"
    ):
        screenshot_file = os.path.join(
            SCREENSHOT_PATH,
            f"{request.node.name}.png",
        )
        page.screenshot(
            path=screenshot_file,
            full_page=PLAYWRIGHT_CONFIG["screenshot"]["full_page"],
        )

    page.close()


@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Hook to capture test results for screenshot/trace decisions.

    This hook allows fixtures to access test result status to determine
    whether to save screenshots or traces on failure.
    """
    outcome = yield
    rep = outcome.get_result()
    setattr(item, f"rep_{rep.when}", rep)
