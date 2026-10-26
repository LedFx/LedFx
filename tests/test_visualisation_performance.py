"""Virtuals and devices preview through the core-owned sampler."""

import base64
from collections.abc import Iterator
from typing import cast
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ledfx.core import LedFxCore
from ledfx.devices import Device, Devices
from ledfx.events import (
    BaseConfigUpdateEvent,
    Event,
    Events,
    VisualisationUpdateEvent,
)
from ledfx.preview import PreviewSampler
from ledfx.virtuals import Virtual, Virtuals
from tests.test_utilities.fake_ledfx import fake_ledfx
from tests.test_utilities.fake_loop import FakeLoop


@pytest.fixture
def ledfx() -> Iterator[MagicMock]:
    core = fake_ledfx()
    core.loop = FakeLoop()
    core.events = Events(core)
    core.devices.get.return_value = None
    LedFxCore.setup_visualisation_events(cast(LedFxCore, core))
    Virtuals._instance = None
    core.virtuals = Virtuals(core)
    yield core
    Virtuals._instance = None


def watch(ledfx: MagicMock) -> list[VisualisationUpdateEvent]:
    received: list[VisualisationUpdateEvent] = []
    ledfx.events.add_listener(received.append, Event.VISUALISATION_UPDATE)
    return received


def make_virtual(ledfx: MagicMock, pixel_count: int = 10) -> Virtual:
    virtual = ledfx.virtuals.create(id="strip", config={"name": "strip"}, ledfx=ledfx)
    virtual.update_segments([["gap-a", 0, pixel_count - 1, False]])
    return virtual


def make_device(ledfx: MagicMock) -> tuple[Devices, Device]:
    devices = Devices(ledfx)
    device = devices.create(
        id="lamp", type="dummy", config={"name": "lamp", "pixel_count": 4}, ledfx=ledfx
    )
    assert isinstance(device, Device)
    # No public way to elect a priority virtual without starting a renderer.
    device.__dict__["priority_virtual"] = MagicMock(id="strip")
    device.activate()
    return devices, device


def rgb(event: VisualisationUpdateEvent) -> bytes:
    return base64.b64decode(cast(str, event.pixels))


def test_core_owns_sampler_and_registers_no_raw_listeners(ledfx: MagicMock):
    sampler = ledfx.preview_sampler
    assert isinstance(sampler, PreviewSampler)
    assert not ledfx.events.has_listeners(Event.VIRTUAL_UPDATE)
    assert not ledfx.events.has_listeners(Event.DEVICE_UPDATE)

    # Preview config is read when encoding; changing it keeps the sampler.
    LedFxCore.handle_base_configuration_update(
        cast(LedFxCore, ledfx), BaseConfigUpdateEvent({"visualisation_fps": 60})
    )
    assert ledfx.preview_sampler is sampler
    assert not ledfx.events.has_listeners(Event.VIRTUAL_UPDATE)


def test_virtual_preview_is_an_owned_copy(ledfx: MagicMock):
    virtual = make_virtual(ledfx)
    received = watch(ledfx)

    virtual.force_frame((10, 20, 30))
    frame = virtual.assembled_frame
    assert frame is not None
    frame[:] = 0  # the renderer reuses its buffer
    ledfx.loop.run_ready()

    assert [event.shape for event in received] == [(1, 10)]
    assert rgb(received[0]) == bytes([10, 20, 30] * 10)


def test_device_preview_copy_precedes_flush(ledfx: MagicMock):
    _, device = make_device(ledfx)
    received = watch(ledfx)

    def zeroing_flush(data: np.ndarray) -> None:
        data[:] = 0  # some senders convert the frame in place

    with patch.object(device, "flush", side_effect=zeroing_flush) as flush:
        device.update_pixels("strip", [(np.full((4, 3), 200.0), 0, 3)])
    ledfx.loop.run_ready()

    flush.assert_called_once()
    assert [(event.is_device, event.vis_id) for event in received] == [(True, "lamp")]
    assert rgb(received[0]) == bytes([200] * 12)


def test_deleted_virtual_preview_is_forgotten(ledfx: MagicMock):
    virtual = make_virtual(ledfx)
    received = watch(ledfx)

    virtual.force_frame((10, 20, 30))
    ledfx.virtuals.destroy("strip")
    ledfx.loop.run_ready()

    assert received == []


def test_deleted_device_preview_is_forgotten(ledfx: MagicMock):
    devices, device = make_device(ledfx)
    received = watch(ledfx)

    device.update_pixels("strip", [(np.full((4, 3), 200.0), 0, 3)])
    devices.destroy("lamp")
    ledfx.loop.run_ready()

    assert received == []
