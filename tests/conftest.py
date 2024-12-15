import subprocess
import time

import pytest

from tests.test_definitions.all_effects import get_ledfx_effects
from tests.test_definitions.audio_configs import get_ledfx_audio_configs
from tests.test_utilities.consts import BASE_PORT
from tests.test_utilities.test_utils import EnvironmentCleanup


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
    # send LedFx a shutdown signal
    try:
        EnvironmentCleanup.shutdown_ledfx()
    except Exception as e:
        pytest.fail(f"An error occurred while shutting down LedFx: {str(e)}")
    # Wait for LedFx to terminate
    while ledfx.poll() is None:
        time.sleep(0.5)
