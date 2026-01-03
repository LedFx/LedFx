import subprocess
import time

import pytest

from tests.test_definitions.all_effects import get_ledfx_effects
from tests.test_definitions.audio_configs import get_ledfx_audio_configs
from tests.test_utilities.consts import BASE_PORT
from tests.test_utilities.test_utils import EnvironmentCleanup

# Initialize globals as empty dicts so they can be imported by test_apis.py at module load time
# They will be populated in pytest_sessionstart when the LedFx server starts
all_effects = {}
audio_configs = {}


def pytest_sessionstart(session):
    """
    Function to start LedFx as a subprocess and initialize necessary variables.
    It is called once at the start of the pytest session, before any tests are run.
    We use this function to start LedFx as a subprocess and initialize the all_effects variable.
    These are then exported as global variables so that they can be used by the tests.
    Args:
        session: The pytest session object.

    Returns:
        None
    """
    # Skip this startup logic for E2E tests - they handle their own server startup
    # Two detection methods needed:
    # 1. Marker-based command line: pytest -m e2e (checks markexpr)
    # 2. Path-based: pytest tests/e2e/ (checks if ALL args are e2e paths)
    selected_items = session.config.option.markexpr
    test_args = session.config.args

    # Only skip if running e2e marker OR if ALL test paths are e2e tests
    # This prevents skipping when VS Code passes mixed paths during discovery
    if selected_items and "e2e" in selected_items:
        return

    # Check if we're only running e2e tests (not mixed with other tests)
    if test_args and all("e2e" in str(arg) for arg in test_args):
        return

    EnvironmentCleanup.cleanup_test_config_folder()
    # Start LedFx as a subprocess
    global ledfx
    try:
        ledfx = subprocess.Popen(
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
    except Exception as e:
        pytest.fail(f"An error occurred while starting LedFx: {str(e)}")

    time.sleep(
        2
    )  # Wait for 2 seconds for the server to start and schema to be generated

    # Dynamic import of tests happens here
    # Needs to be done at session start so that the tests are available to pytest
    # This is a hack to get around the fact that pytest doesn't support dynamic imports
    global all_effects
    all_effects = get_ledfx_effects()
    global audio_configs
    audio_configs = get_ledfx_audio_configs()
    # To add another test group, add it here, and then in test_apis.py


def pytest_sessionfinish(session, exitstatus):
    """
    Function to terminate the ledfx subprocess.
    It is called once at the end of the pytest session, after all tests are run.
    Args:
        session: The pytest session object.
        exitstatus: The exit status of the pytest session.

    Returns:
        None
    """
    # Skip this cleanup logic for E2E tests - they handle their own server cleanup
    # Detect e2e tests via marker (pytest -m e2e) or if ALL paths are e2e tests
    selected_items = session.config.option.markexpr
    test_args = session.config.args

    if selected_items and "e2e" in selected_items:
        return

    if test_args and all("e2e" in str(arg) for arg in test_args):
        return

    # send LedFx a shutdown signal
    try:
        EnvironmentCleanup.shutdown_ledfx()
    except Exception as e:
        pytest.fail(f"An error occurred while shutting down LedFx: {str(e)}")
    # Wait for LedFx to terminate
    while ledfx.poll() is None:
        time.sleep(0.5)
