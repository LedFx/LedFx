"""LIFX Mirror support: detection, Front/Back virtuals and the buffer scatter.

The Mirror reports a 4x13 matrix, but its 52 buffer positions hold two
interleaved 25-zone rings plus two unused positions. LedFx drives it as a
50-pixel strip in zone order and scatters each frame into the buffer, so a
zone's colour must land at the buffer position lifx-async's layout gives it.

The end-to-end test swaps the session's emulated Ceiling for a Mirror on
127.0.0.1, so it runs last: after the LIFX API tests in test_apis.py have
deleted the DDP test jig and the Ceiling device that share that address.
"""

import asyncio
import time
from collections.abc import Coroutine, Iterator
from typing import TypeVar
from unittest.mock import MagicMock

import numpy as np
import pytest
import requests
from lifx.products import get_mirror_layout
from lifx_emulator import EmulatedLifxServer
from lifx_emulator.devices import EmulatedLifxDevice
from lifx_emulator.factories import create_device
from lifx_emulator.protocol.protocol_types import LightHsbk

from ledfx.devices.lifx import LifxDevice, numpy_rgb_to_hsbk
from tests import conftest
from tests.test_utilities.consts import SERVER_PATH

MIRROR_PRODUCT_ID = 267  # LIFX Mirror
MIRROR_SERIAL = "d073d9000002"
_layout = get_mirror_layout(MIRROR_PRODUCT_ID)
assert _layout is not None
MIRROR_LAYOUT = _layout
BUFFER_SIZE = 4 * 13
UNUSED_POSITIONS = sorted(
    set(range(BUFFER_SIZE))
    - set(MIRROR_LAYOUT.front_positions)
    - set(MIRROR_LAYOUT.back_positions)
)

API = f"http://{SERVER_PATH}/api"
DEVICE_NAME = "CI LIFX Mirror"
DEVICE_ID = "ci-lifx-mirror"
FRONT_ID = f"{DEVICE_ID}-front"
BACK_ID = f"{DEVICE_ID}-back"

HUE_RED = 0
HUE_BLUE = 43690  # 240 degrees as a LIFX uint16 hue


T = TypeVar("T")


def _on_emulator(coro: Coroutine[object, object, T], timeout: float = 5) -> T:
    """Run a coroutine on the emulator's event loop and wait for it."""
    loop = conftest.lifx_emulator_loop
    assert loop is not None
    return asyncio.run_coroutine_threadsafe(coro, loop).result(timeout)


def _delete_virtual(virtual_id: str) -> None:
    """Delete a virtual (or device) if it exists; a missing one is fine."""
    requests.delete(f"{API}/virtuals/{virtual_id}", timeout=10)


@pytest.fixture
def emulated_mirror() -> Iterator[EmulatedLifxDevice]:
    """Swap the emulator's Ceiling for a Mirror, and put the Ceiling back after."""
    if conftest.lifx_emulator_server is None:
        pytest.skip("LIFX emulator is not running")
    server: EmulatedLifxServer = conftest.lifx_emulator_server

    # Free 127.0.0.1 in LedFx: one device per IP
    for virtual_id in ("ci-test-jig", "ci-lifx-test"):
        _delete_virtual(virtual_id)

    async def swap_in() -> EmulatedLifxDevice:
        await server.remove_device(conftest.LIFX_TEST_SERIAL)
        mirror = create_device(product_id=MIRROR_PRODUCT_ID, serial=MIRROR_SERIAL)
        server.add_device(mirror)
        return mirror

    async def swap_out() -> None:
        await server.remove_device(MIRROR_SERIAL)
        server.add_device(
            create_device(
                product_id=176,
                serial=conftest.LIFX_TEST_SERIAL,
                tile_count=1,
                tile_width=conftest.LIFX_TEST_MATRIX_WIDTH,
                tile_height=conftest.LIFX_TEST_MATRIX_HEIGHT,
            )
        )

    mirror = _on_emulator(swap_in())
    try:
        yield mirror
    finally:
        for virtual_id in (FRONT_ID, BACK_ID, DEVICE_ID):
            _delete_virtual(virtual_id)
        _on_emulator(swap_out())


def _buffer(mirror: EmulatedLifxDevice) -> list[LightHsbk]:
    """The Mirror's visible buffer, in Set64 position order."""
    return list(mirror.state.tile_devices[0]["colors"])


def _rings_show(buffer: list[LightHsbk]) -> bool:
    """True once the front is red, the back is blue and unused positions are off."""
    front = [buffer[p] for p in MIRROR_LAYOUT.front_positions]
    back = [buffer[p] for p in MIRROR_LAYOUT.back_positions]
    unused = [buffer[p] for p in UNUSED_POSITIONS]
    return (
        all(c.brightness > 0 and c.hue == HUE_RED for c in front)
        and all(c.brightness > 0 and abs(c.hue - HUE_BLUE) <= 1 for c in back)
        and all(c.brightness == 0 for c in unused)
    )


@pytest.mark.order("last")
def test_mirror_end_to_end(emulated_mirror: EmulatedLifxDevice) -> None:
    # Detection: a Mirror is a 50-zone "mirror" device, not a 4x13 matrix
    resp = requests.post(
        f"{API}/devices",
        json={
            "type": "lifx",
            "config": {"name": DEVICE_NAME, "ip_address": "127.0.0.1"},
        },
        timeout=30,
    )
    assert resp.status_code == 200, resp.text
    device = resp.json()["device"]
    assert device["id"] == DEVICE_ID
    config = device["config"]
    assert config["lifx_class"] == "MirrorLight"
    assert config["lifx_type"] == "mirror"
    assert config["serial"] == MIRROR_SERIAL
    assert config["pixel_count"] == MIRROR_LAYOUT.zone_count == 50

    # A 25-pixel strip virtual for each ring
    rings = {
        FRONT_ID: (0, 24),
        BACK_ID: (25, 49),
    }
    for virtual_id, (start, end) in rings.items():
        resp = requests.get(f"{API}/virtuals/{virtual_id}", timeout=10)
        assert resp.status_code == 200, resp.text
        virtual = resp.json()[virtual_id]
        assert virtual["auto_generated"] is True
        assert virtual["pixel_count"] == 25
        assert virtual["segments"] == [[DEVICE_ID, start, end, False]]

    # Scatter: each ring's colour lands at its buffer positions, and the
    # two unused positions stay black
    for virtual_id, color in ((FRONT_ID, "#ff0000"), (BACK_ID, "#0000ff")):
        resp = requests.post(
            f"{API}/virtuals/{virtual_id}/effects",
            json={"type": "singleColor", "config": {"color": color}},
            timeout=10,
        )
        assert resp.status_code == 200, resp.text

    deadline = time.monotonic() + 10
    while not _rings_show(_buffer(emulated_mirror)):
        if time.monotonic() > deadline:
            pytest.fail(
                f"Mirror buffer never showed red/blue rings: {_buffer(emulated_mirror)}"
            )
        time.sleep(0.1)


def _mirror_device_with_animator() -> tuple[LifxDevice, MagicMock]:
    """A connected LifxDevice in Mirror mode, with a mocked Animator."""
    device = object.__new__(LifxDevice)
    device._lifx_type = "mirror"
    device._zone_count = MIRROR_LAYOUT.zone_count
    device._mirror_positions = np.array(
        MIRROR_LAYOUT.front_positions + MIRROR_LAYOUT.back_positions, dtype=np.intp
    )
    animator = MagicMock()
    animator.pixel_count = BUFFER_SIZE
    device._animator = animator
    return device, animator


def test_mirror_flush_scatters_each_zone_to_its_buffer_position():
    device, animator = _mirror_device_with_animator()
    # A distinct colour per zone, so any misplaced zone shows up
    zones = np.array(
        [[(z * 5) % 256, (z * 11 + 7) % 256, (255 - z * 3) % 256] for z in range(50)],
        dtype=float,
    )

    device.flush(zones)

    sent = animator.send_frame.call_args.args[0]
    assert len(sent) == BUFFER_SIZE
    expected = np.zeros((BUFFER_SIZE, 3), dtype=np.uint8)
    positions = device._mirror_positions
    assert positions is not None
    for zone, position in enumerate(positions):
        expected[position] = zones[zone]
    assert sent == numpy_rgb_to_hsbk(expected)
    for position in UNUSED_POSITIONS:
        assert sent[position][2] == 0  # brightness


def test_mirror_flush_with_a_short_frame_leaves_the_rest_black():
    device, animator = _mirror_device_with_animator()
    front_only = np.full((25, 3), 255.0)

    device.flush(front_only)

    sent = animator.send_frame.call_args.args[0]
    assert len(sent) == BUFFER_SIZE
    lit = {p for p, (_, _, brightness, _) in enumerate(sent) if brightness > 0}
    assert lit == set(MIRROR_LAYOUT.front_positions)
