"""LIFX matrix devices get a 2D virtual as soon as they are added.

The session's emulated Ceiling (8x8) answers on 127.0.0.1. Detection runs in
async_initialize, before the device's virtual exists, so the virtual must take
its rows from the detected matrix height rather than waiting for a connect.

Runs after the LIFX API tests in test_apis.py and before test_lifx_mirror.py,
which both free 127.0.0.1 the same way.
"""

import requests

from tests import conftest
from tests.test_utilities.consts import SERVER_PATH

API = f"http://{SERVER_PATH}/api"
DEVICE_NAME = "CI LIFX Matrix"
DEVICE_ID = "ci-lifx-matrix"


def _delete_virtual(virtual_id: str) -> None:
    """Delete a virtual (or device) if it exists; a missing one is fine."""
    requests.delete(f"{API}/virtuals/{virtual_id}", timeout=10)


def test_new_matrix_device_virtual_has_matrix_rows() -> None:
    # Free 127.0.0.1 in LedFx: one device per IP
    for virtual_id in ("ci-test-jig", "ci-lifx-test", DEVICE_ID):
        _delete_virtual(virtual_id)

    response = requests.post(
        f"{API}/devices",
        json={
            "type": "lifx",
            "config": {
                "name": DEVICE_NAME,
                "ip_address": "127.0.0.1",
                "port": conftest.lifx_emulator_port,
            },
        },
        timeout=30,
    ).json()
    try:
        assert response["status"] == "success", response
        assert (
            response["device"]["config"]["matrix_height"]
            == conftest.LIFX_TEST_MATRIX_HEIGHT
        )

        virtual = requests.get(f"{API}/virtuals/{DEVICE_ID}", timeout=10).json()
        assert virtual[DEVICE_ID]["config"]["rows"] == conftest.LIFX_TEST_MATRIX_HEIGHT
    finally:
        _delete_virtual(DEVICE_ID)
