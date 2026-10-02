"""A fake core running the real Virtuals and Effects managers.

Devices are small fakes. Tests that activate a virtual disable its render
thread (``no_render``) so nothing races the responses they record, and call
``stop_virtuals()`` afterwards to join effect threads and cancel timers.
"""

import threading
from collections.abc import Iterator, Mapping
from typing import cast
from unittest.mock import MagicMock

import pytest

from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import VirtualEntry
from ledfx.configuration.plugin import PluginConfig
from ledfx.devices import Device
from ledfx.effects import Effects
from ledfx.effects.oneshots.oneshot import Flash
from ledfx.utils import build_user_collections
from ledfx.virtuals import Virtual, Virtuals
from tests.test_utilities.fake_ledfx import fake_ledfx


class FakeDevice:
    """Enough of a Device for virtuals: segments, activation, pixel writes."""

    type = "fake"

    def __init__(self, ledfx: MagicMock, device_id: str, pixel_count: int) -> None:
        self._ledfx = ledfx
        self.id = device_id
        self.name = device_id
        self.pixel_count = pixel_count
        self.max_refresh_rate = 60
        self.lock = threading.Lock()
        self._active = False
        self.segments: list[tuple[str, int, int]] = []
        self.frames = 0

    def is_active(self) -> bool:
        return self._active

    def activate(self) -> None:
        self._active = True

    def deactivate(self) -> None:
        self._active = False

    def add_segments_batch(
        self, virtual_id: str, segments: list[tuple[int, int]], force: bool = False
    ) -> None:
        self.segments += [(virtual_id, start, end) for start, end in segments]

    def clear_virtual_segments(self, virtual_id: str) -> None:
        self.segments = [s for s in self.segments if s[0] != virtual_id]

    def update_pixels(self, virtual_id: str, data: object) -> None:
        self.frames += 1

    def _cleanup_virtual_from_scenes(self, virtual_id: str) -> None:
        Device._cleanup_virtual_from_scenes(cast("Device", self), virtual_id)

    def remove_from_virtuals(self) -> None:
        Device.remove_from_virtuals(cast("Device", self))


class FakeDevices:
    """The device registry's lookups over FakeDevices."""

    def __init__(self, *devices: FakeDevice) -> None:
        self._objects = {device.id: device for device in devices}

    def get(self, device_id: str, default: object = None) -> object:
        return self._objects.get(device_id, default)

    def values(self) -> list[FakeDevice]:
        return list(self._objects.values())

    def destroy(self, device_id: str) -> None:
        del self._objects[device_id]


def install_virtuals(ledfx: MagicMock) -> MagicMock:
    """Give a fake_ledfx() core devices "strip" (50 px) and "matrix" (64 px),
    colors, gradients and the real Effects and Virtuals managers."""
    ledfx.devices = FakeDevices(
        FakeDevice(ledfx, "strip", 50), FakeDevice(ledfx, "matrix", 64)
    )
    ledfx.effects = Effects(ledfx)
    ledfx.colors, ledfx.gradients = build_user_collections(ledfx)
    Virtuals._instance = None
    ledfx.virtuals = Virtuals(ledfx)
    return ledfx


def add_virtual(
    ledfx: MagicMock,
    virtual_id: str,
    name: str,
    segments: list[list[object]],
    *,
    is_device: str | bool = False,
    effect: Mapping[str, object] | None = None,
    effects: Mapping[str, Mapping[str, object]] | None = None,
) -> Virtual:
    """Add a virtual the way a config load does (its entry, then the object).

    effect/effects are stored entries ({"type": ..., "config": ...}); a stored
    effect of a registered type starts running."""
    entry = VirtualEntry.model_validate(
        {
            "id": virtual_id,
            "config": {"name": name},
            "segments": segments,
            "is_device": is_device,
            "effect": effect,
            "effects": effects or {},
        }
    )
    ledfx.config.virtuals.append(entry)
    ledfx.virtuals.create_from_config([entry])
    virtual = ledfx.virtuals.get(virtual_id)
    assert virtual is not None
    return virtual


def seed_standard(ledfx: MagicMock) -> None:
    """The virtuals most tests share:
    - "dj bird": all of strip (an id with a space);
    - "mirror": the first 10 px of strip (streams while dj bird runs);
    - "empty": no segments;
    - "matrix": the matrix device's own virtual."""
    add_virtual(ledfx, "dj bird", "dj bird", [["strip", 0, 49, False]])
    add_virtual(ledfx, "mirror", "Mirror", [["strip", 0, 9, False]])
    add_virtual(ledfx, "empty", "Empty", [])
    add_virtual(
        ledfx, "matrix", "matrix", [["matrix", 0, 63, False]], is_device="matrix"
    )


def enter_safe_mode(ledfx: MagicMock) -> None:
    ledfx.config_store.error = "config.json is not valid JSON"


def no_render(virtual: Virtual) -> None:
    """Stands in for Virtual.thread_function: no frames, no races."""


def stop_virtuals(ledfx: MagicMock) -> None:
    """Cancel fallback timers and join every effect thread, including those of
    effects whose virtual was deleted mid-transition."""
    for virtual in list(ledfx.virtuals.values()):
        virtual._active = False
        if virtual.fallback_timer is not None:
            virtual.fallback_timer.cancel()
    for effect in list(ledfx.effects.values()):
        if effect.is_active:
            effect._deactivate()
    Virtuals._instance = None


def running_core(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    """Fixture body: a core with seed_standard() virtuals and no render threads.

    Use as ``yield from running_core(monkeypatch)`` in a module's fixture."""
    monkeypatch.setattr(Virtual, "thread_function", no_render)
    ledfx = install_virtuals(fake_ledfx())
    seed_standard(ledfx)
    yield ledfx
    stop_virtuals(ledfx)


def cfg(values: Mapping[str, object]) -> PluginConfig:
    """Effect settings as the manager takes them."""
    return PluginConfig.model_validate(values)


def entry_ids(ledfx: MagicMock) -> list[str]:
    """The ids of the stored virtual entries."""
    return [entry.id for entry in ledfx.config.virtuals]


def flashes(ledfx: MagicMock, virtual_id: str) -> list[Flash]:
    """The flashes running on a virtual."""
    virtual = ledfx.virtuals.get_or_raise(VirtualIdStr(virtual_id))
    return [o for o in virtual.oneshots if isinstance(o, Flash) and o.active]
