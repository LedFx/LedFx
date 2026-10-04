import asyncio
import atexit
import faulthandler
import os
import shutil
import signal
import subprocess
import sys
import threading
import time

import pytest
import requests
from lifx_emulator import EmulatedLifxServer
from lifx_emulator.devices import DeviceManager
from lifx_emulator.factories import create_device
from lifx_emulator.repositories import DeviceRepository

from tests.test_definitions.all_effects import get_ledfx_effects
from tests.test_definitions.audio_configs import get_ledfx_audio_configs
from tests.test_utilities.consts import BASE_PORT, SERVER_PATH
from tests.test_utilities.test_utils import TEST_CONFIG_DIR

# The live LedFx child process, and where its stdout and stderr go
ledfx: subprocess.Popen[bytes] | None = None
LEDFX_OUT = os.path.join(TEST_CONFIG_DIR, "ledfx-stdout.log")

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


def _ledfx_diagnostics(problem: str) -> str:
    """Describe a start or teardown problem with the LedFx log tail and our threads."""
    try:
        with open(LEDFX_OUT, encoding="utf-8", errors="replace") as f:
            tail = "".join(f.readlines()[-60:])
    except OSError as e:
        tail = f"(no log: {e})"
    threads = "\n".join(f"  {t!r}" for t in threading.enumerate())
    return (
        f"{problem}\nLedFx config dir: {TEST_CONFIG_DIR}\n"
        f"--- last lines of {LEDFX_OUT} ---\n{tail}\n"
        f"--- threads in the pytest process ---\n{threads}"
    )


def _reap_ledfx(grace: float) -> str | None:
    """Wait up to `grace` s for LedFx to exit, then terminate, then kill.

    Safe to call on any path, any number of times. Returns a problem
    description, or None if LedFx exited on its own in time.
    """
    global ledfx
    proc, ledfx = ledfx, None
    if proc is None or proc.poll() is not None:
        return None
    try:
        proc.wait(grace)
        return None
    except subprocess.TimeoutExpired:
        pass
    proc.terminate()
    try:
        proc.wait(10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
    return (
        f"LedFx (pid {proc.pid}) was still running {grace} s after shutdown; killed it"
    )


def _on_sigterm(signum: int, frame: object) -> None:
    # A SIGTERM to pytest would skip every finally and atexit: kill LedFx
    # first, then die the way SIGTERM normally would.
    _reap_ledfx(0)
    signal.signal(signum, signal.SIG_DFL)
    os.kill(os.getpid(), signum)


atexit.register(_reap_ledfx, 0)  # last resort; a no-op after a clean finish


def _wait_until_ready(proc: subprocess.Popen[bytes], timeout: float = 60) -> None:
    """Poll /api/info until LedFx answers; fail at once if the child dies."""
    deadline = time.monotonic() + timeout
    while True:
        if proc.poll() is not None:
            raise RuntimeError(
                f"LedFx exited with code {proc.returncode} before it was ready"
            )
        try:
            if requests.get(f"http://{SERVER_PATH}/api/info", timeout=2).ok:
                return
        except requests.RequestException:
            pass
        if time.monotonic() > deadline:
            raise RuntimeError(f"LedFx did not answer /api/info within {timeout} s")
        time.sleep(0.1)


def _start_ledfx() -> None:
    global ledfx, all_effects, audio_configs
    # A fixed dir (CI), or a dead run that had our pid, may hold an old config.json.
    # Only clear a dir this harness made, so LEDFX_TEST_CONFIG_DIR=~/.ledfx can't wipe a real config.
    marker = os.path.join(TEST_CONFIG_DIR, ".ledfx-test-dir")
    if (
        os.path.isdir(TEST_CONFIG_DIR)
        and os.listdir(TEST_CONFIG_DIR)
        and not os.path.isfile(marker)
    ):
        raise RuntimeError(
            f"Refusing to clear {TEST_CONFIG_DIR}: not a LedFx test dir "
            "(no .ledfx-test-dir marker)"
        )
    shutil.rmtree(TEST_CONFIG_DIR, ignore_errors=True)
    os.makedirs(TEST_CONFIG_DIR)
    open(marker, "w").close()

    # Start LIFX emulator before LedFx
    _start_lifx_emulator()

    with open(LEDFX_OUT, "wb") as out:
        ledfx = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "ledfx",
                "-p",
                f"{BASE_PORT}",
                "--offline",
                "-c",
                TEST_CONFIG_DIR,
                "-vv",
            ],
            stdout=out,
            stderr=subprocess.STDOUT,
        )
    _wait_until_ready(ledfx)

    # Dynamic import of tests happens here
    # Needs to be done at session start so that the tests are available to pytest
    # This is a hack to get around the fact that pytest doesn't support dynamic imports
    all_effects = get_ledfx_effects()
    audio_configs = get_ledfx_audio_configs()
    # To add another test group, add it here, and then in test_apis.py


def pytest_report_header(config: pytest.Config) -> str:
    return f"live LedFx config and logs: {TEST_CONFIG_DIR}"


def pytest_sessionstart(session: pytest.Session) -> None:
    """Start the LIFX emulator and LedFx, and build the schema-driven test cases.

    If anything here fails, pytest skips pytest_sessionfinish, so this hook
    kills LedFx itself before it gives up.
    """
    signal.signal(signal.SIGTERM, _on_sigterm)
    # Session hooks run outside pytest-timeout: dump every stack if one hangs.
    faulthandler.dump_traceback_later(120)
    try:
        _start_ledfx()
    except BaseException as e:  # incl. pytest.fail(), which pytest would swallow here
        report = _ledfx_diagnostics(f"LedFx test session failed to start: {e!r}")
        _reap_ledfx(0)
        _stop_lifx_emulator()
        if isinstance(e, KeyboardInterrupt):
            raise
        pytest.exit(report, returncode=pytest.ExitCode.INTERNAL_ERROR)
    finally:
        faulthandler.cancel_dump_traceback_later()


def _shutdown_ledfx() -> str | None:
    """Ask LedFx to stop and wait for it to exit. Returns a problem or None."""
    if ledfx is None:
        return None
    if ledfx.poll() is not None:
        return f"LedFx exited early with code {ledfx.returncode}"
    try:
        requests.post(f"http://{SERVER_PATH}/api/power", json={}, timeout=5)
    except requests.RequestException as e:
        return f"POST /api/power failed ({e!r}); {_reap_ledfx(30) or 'LedFx exited'}"
    return _reap_ledfx(30)


def pytest_sessionfinish(session: pytest.Session, exitstatus: int) -> None:
    """Stop LedFx and the LIFX emulator.

    A teardown problem is reported, never raised, and never skips the kill.
    """
    faulthandler.dump_traceback_later(60)
    problem = None
    try:
        problem = _shutdown_ledfx()
    finally:
        _reap_ledfx(0)
        _stop_lifx_emulator()
        faulthandler.cancel_dump_traceback_later()
    if problem:
        print("\n" + _ledfx_diagnostics(problem), file=sys.stderr)
    elif exitstatus == 0 and "LEDFX_TEST_CONFIG_DIR" not in os.environ:
        shutil.rmtree(TEST_CONFIG_DIR, ignore_errors=True)
