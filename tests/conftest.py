import subprocess
import time

import pytest

from tests.test_definitions.all_effects import get_ledfx_effects
from tests.test_definitions.audio_configs import get_ledfx_audio_configs
from tests.test_utilities.consts import BASE_PORT
from tests.test_utilities.test_utils import EnvironmentCleanup

# Track whether LedFx was started
_ledfx_started = False
ledfx = None

# Initialize globals for effect/audio test data
all_effects = {}
audio_configs = {}


def _requires_ledfx_server(session) -> bool:
    """
    Check if any collected tests require the LedFx server.

    This function determines whether to start the LedFx server subprocess
    based on the test paths specified. Unit tests (like test_multifft)
    don't need the server, while integration tests (like test_apis) do.

    Note: A more robust solution would use pytest markers (e.g., @pytest.mark.integration)
    to explicitly tag tests that need the server. This heuristic approach is used
    to avoid modifying all existing integration tests.

    Returns:
        True if tests require the LedFx server, False otherwise.
    """
    # Known unit test directories that don't need LedFx server
    unit_test_dirs = ["test_multifft"]

    if session.config.args:
        # Check if ANY specified path explicitly targets a unit test directory
        # Note: "tests" from addopts is the base directory, so we look for more specific paths
        specific_unit_test_path = False
        has_other_test_path = False

        for arg in session.config.args:
            arg_str = str(arg)
            # Skip option arguments (like --verbose, --ignore)
            if arg_str.startswith("-"):
                continue
            # Skip the generic "tests" base directory (from addopts)
            if arg_str == "tests":
                continue
            # Check if this path targets a unit test directory
            if any(unit_dir in arg_str for unit_dir in unit_test_dirs):
                specific_unit_test_path = True
            else:
                has_other_test_path = True

        # Only skip LedFx if we're specifically targeting unit tests
        # and not also running other tests
        if specific_unit_test_path and not has_other_test_path:
            return False

    return True


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
    global _ledfx_started, ledfx, all_effects, audio_configs

    # Skip LedFx startup for unit tests that don't need it
    if not _requires_ledfx_server(session):
        return

    EnvironmentCleanup.cleanup_test_config_folder()
    # Start LedFx as a subprocess
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
        _ledfx_started = True
    except Exception as e:
        pytest.fail(f"An error occurred while starting LedFx: {str(e)}")

    time.sleep(
        2
    )  # Wait for 2 seconds for the server to start and schema to be generated

    # Dynamic import of tests happens here
    # Needs to be done at session start so that the tests are available to pytest
    # This is a hack to get around the fact that pytest doesn't support dynamic imports
    all_effects = get_ledfx_effects()
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
    # Only try to shut down LedFx if it was started
    if not _ledfx_started:
        return

    # send LedFx a shutdown signal
    try:
        EnvironmentCleanup.shutdown_ledfx()
    except Exception as e:
        pytest.fail(f"An error occurred while shutting down LedFx: {str(e)}")
    # Wait for LedFx to terminate
    while ledfx.poll() is None:
        time.sleep(0.5)
