import os
import platform
import subprocess
import sys
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
    default_audio_device_setup()
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


"""
Pytest startup hook to configure default audio device for Windows CI runs.

It only runs when tests are executed on GitHub
Actions Windows runners to avoid changing developer environments.

Behavior:
- If running on GitHub Actions and platform is Windows, try to select a
  WDM-KS device containing 'CABLE Output' and set it as the default input
  device via sounddevice. Diagnostics are written to stderr.
- All errors are caught and reported to stderr; failure is non-fatal.
"""


def _should_run_on_ci_windows() -> bool:
    # Run only on GitHub Actions Windows runners
    # - GITHUB_ACTIONS is 'true' on GitHub Actions
    # - platform.system() == 'Windows' on Windows runners
    return (
        os.environ.get("GITHUB_ACTIONS", "") == "true"
        and platform.system() == "Windows"
    )


def default_audio_device_setup():

    if _should_run_on_ci_windows():
        try:
            import sounddevice as sd

            # Query available devices and host APIs
            devs = sd.query_devices()
            hostapis = sd.query_hostapis()

            def host_name(d):
                return hostapis[d["hostapi"]]["name"]

            # Find WDM-KS devices with 'CABLE Output' in the name
            candidates = [
                i
                for i, d in enumerate(devs)
                if d.get("max_input_channels", 0) > 0
                and "CABLE Output" in d.get("name", "")
                and host_name(d).startswith("Windows WDM-KS")
            ]

            if candidates:
                idx = candidates[0]
                try:
                    # Set as input device only
                    sd.default.device = (idx, None)
                except Exception:
                    # Fallback to setting for both input/output
                    sd.default.device = idx

                sys.stdout.write(
                    f"[conftest] WDM-KS input -> #{idx}: {devs[idx]['name']}\n"
                )
            else:
                sys.stdout.write(
                    "[conftest] No WDM-KS 'CABLE Output' found.\n"
                )

        except Exception as e:
            sys.stdout.write(f"[conftest] skip: {e}\n")
