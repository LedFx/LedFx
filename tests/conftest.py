import asyncio
import subprocess
import threading
import time

import pytest
from lifx_emulator import EmulatedLifxServer
from lifx_emulator.devices import DeviceManager
from lifx_emulator.factories import create_device
from lifx_emulator.repositories import DeviceRepository

from tests.test_definitions.all_effects import get_ledfx_effects
from tests.test_definitions.audio_configs import get_ledfx_audio_configs
from tests.test_utilities.consts import BASE_PORT
from tests.test_utilities.test_utils import EnvironmentCleanup

# LIFX emulator globals
lifx_emulator_thread = None
lifx_emulator_loop = None
lifx_emulator_server = None

# Test device configuration (deterministic for test assertions)
# Serial is 12 hex chars with prefix (d073d9 = matrix)
# LIFX Ceiling (pid=176, 8x8 = 64 pixels)
LIFX_TEST_SERIAL = "d073d9000001"
LIFX_TEST_MATRIX_WIDTH = 8
LIFX_TEST_MATRIX_HEIGHT = 8


def _run_lifx_emulator():
    """Run LIFX emulator in a background thread with its own event loop."""
    global lifx_emulator_loop, lifx_emulator_server

    lifx_emulator_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(lifx_emulator_loop)

    # Create emulated LIFX Ceiling (8x8 = 64 pixel matrix)
    devices = [
        create_device(
            product_id=176,  # LIFX Ceiling US
            serial=LIFX_TEST_SERIAL,
            tile_count=1,
            tile_width=LIFX_TEST_MATRIX_WIDTH,
            tile_height=LIFX_TEST_MATRIX_HEIGHT,
        ),
    ]

    # Initialize device manager and server
    repository = DeviceRepository()
    manager = DeviceManager(repository)
    lifx_emulator_server = EmulatedLifxServer(
        devices,
        manager,
        bind_address="127.0.0.1",
        port=56700,
        track_activity=False,
    )

    async def run_server():
        await lifx_emulator_server.start()
        # Keep running until stopped
        while True:
            await asyncio.sleep(1)

    try:
        lifx_emulator_loop.run_until_complete(run_server())
    except asyncio.CancelledError:
        pass
    finally:
        lifx_emulator_loop.run_until_complete(lifx_emulator_server.stop())
        lifx_emulator_loop.close()


def _start_lifx_emulator():
    """Start the LIFX emulator in a background thread."""
    global lifx_emulator_thread
    lifx_emulator_thread = threading.Thread(target=_run_lifx_emulator, daemon=True)
    lifx_emulator_thread.start()
    # Wait for emulator to bind to port
    for _ in range(50):  # 5 second timeout
        if lifx_emulator_server and lifx_emulator_server.transport:
            break
        time.sleep(0.1)
    else:
        pytest.fail("LIFX emulator failed to bind to UDP port")


def _stop_lifx_emulator():
    """Stop the LIFX emulator."""
    if lifx_emulator_loop and lifx_emulator_loop.is_running():

        def _cancel_all_tasks():
            for task in asyncio.all_tasks(lifx_emulator_loop):
                task.cancel()

        lifx_emulator_loop.call_soon_threadsafe(_cancel_all_tasks)
    if lifx_emulator_thread:
        lifx_emulator_thread.join(timeout=2)


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

    # Start LIFX emulator before LedFx
    _start_lifx_emulator()

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

    # Stop LIFX emulator
    _stop_lifx_emulator()
