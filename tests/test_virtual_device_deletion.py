"""
Regression tests for the virtual zero-segments startup crash bug.

Root cause: when a device is deleted, non-auto-generated virtuals that
lose all segments survived in config.  On restart,
Virtuals.create_from_config() tried to restore their effect via
set_effect(), which raised ValueError.  The except clauses only caught
RuntimeError and vol.MultipleInvalid.

These tests verify:
1. Device deletion destroys user-created virtuals left with zero segments
2. Auto-generated virtual deletion still works
3. Startup restore with poisoned config does not crash
4. Mixed valid/invalid virtuals during startup
5. Scene cleanup when virtuals are removed
6. Defensive behavior for empty-segment virtuals
"""

import logging
import threading
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from ledfx.devices import Device
from ledfx.virtuals import Virtuals

# ---------------------------------------------------------------------------
# Helpers / Dummies
# ---------------------------------------------------------------------------


class _DummyEvents:
    def __init__(self):
        self._listeners = {}

    def fire_event(self, *_, **__):
        pass

    def add_listener(self, callback, event_type):
        self._listeners[event_type] = callback


class _DummyDevice:
    """Minimal device mock for segment and deletion tests."""

    def __init__(self, device_id, pixel_count=100):
        self._id = device_id
        self._config = {
            "name": device_id,
            "pixel_count": pixel_count,
            "refresh_rate": 60,
            "icon_name": "mdi:led-strip",
            "center_offset": 0,
        }
        self._segments = []
        self._active = False
        self._online = True
        self._pixels = None
        self._ledfx = None
        self.lock = threading.Lock()

    @property
    def id(self):
        return self._id

    @property
    def name(self):
        return self._config["name"]

    @property
    def pixel_count(self):
        return self._config["pixel_count"]

    @property
    def max_refresh_rate(self):
        return self._config["refresh_rate"]

    @property
    def config(self):
        return self._config

    def is_active(self):
        return self._active

    def activate(self):
        self._active = True
        self._pixels = np.zeros((self.pixel_count, 3))

    def deactivate(self):
        self._active = False
        self._pixels = None

    def add_segments_batch(self, virtual_id, segments, force=False):
        for start, end in segments:
            self._segments.append((virtual_id, start, end))

    def clear_virtual_segments(self, virtual_id):
        self._segments = [s for s in self._segments if s[0] != virtual_id]

    def invalidate_cached_props(self):
        pass

    def _cleanup_virtual_from_scenes(self, virtual_id):
        """Reuse the real Device helper so remove_from_virtuals works."""
        Device._cleanup_virtual_from_scenes(self, virtual_id)

    async def remove_from_virtuals(self):
        """Delegate to the real Device implementation logic we're testing."""
        # This is called recursively for is_device virtuals.  In our
        # test dummies the device itself doesn't hold virtual refs, so
        # the real function on the Device under test is what matters.
        pass


class _DummyDevices:
    """Dict-like device registry."""

    def __init__(self, devices=None):
        self._objects = {}
        if devices:
            for d in devices:
                self._objects[d.id] = d

    def get(self, device_id, default=None):
        return self._objects.get(device_id, default)

    def values(self):
        return self._objects.values()

    def destroy(self, device_id):
        del self._objects[device_id]

    def create(self, *args, **kwargs):
        pass


class _DummyEffects:
    """Minimal effects registry that can create mock effects."""

    def __init__(self):
        self._objects = {}

    def create(self, ledfx=None, type=None, config=None):
        effect = MagicMock()
        effect.type = type
        effect.config = config or {}
        effect.is_active = True
        effect.name = type
        effect.id = f"{type}-1"
        effect.logsec = None
        effect._active = True
        effect.pixels = None
        effect.activate = MagicMock()
        effect._deactivate = MagicMock()
        effect.get_pixels = MagicMock(return_value=None)
        self._objects[effect.id] = effect
        return effect

    def destroy(self, effect_id):
        self._objects.pop(effect_id, None)

    def get(self, *args):
        return self._objects.get(*args)


def _make_ledfx(devices=None, scenes=None):
    """Build a minimal LedFx-like object wired up for testing."""
    ledfx = MagicMock()
    ledfx.config_dir = ""
    ledfx.config = {
        "scenes": scenes or {},
        "virtuals": [],
        "devices": [],
        "global_brightness": 1.0,
        "global_transitions": False,
        "flush_on_deactivate": False,
    }
    ledfx.events = _DummyEvents()
    ledfx.devices = _DummyDevices(devices or [])
    ledfx.effects = _DummyEffects()

    # Create a fresh Virtuals instance bound to this ledfx
    Virtuals._instance = None
    virtuals = Virtuals(ledfx)
    ledfx.virtuals = virtuals

    return ledfx


def _make_virtual(
    ledfx, virtual_id, name, segments, is_device=False, auto_generated=False
):
    """Create a Virtual through the Virtuals manager and wire segments."""
    virtual = ledfx.virtuals.create(
        id=virtual_id,
        config={"name": name},
        is_device=is_device,
        auto_generated=auto_generated,
        ledfx=ledfx,
    )
    virtual.virtual_cfg = {
        "id": virtual_id,
        "config": virtual.config,
        "segments": segments,
        "is_device": is_device,
        "auto_generated": auto_generated,
    }
    ledfx.config["virtuals"].append(virtual.virtual_cfg)

    if segments:
        virtual.update_segments(segments)

    return virtual


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _reset_virtuals_singleton():
    """Ensure each test gets a fresh Virtuals singleton and properly
    tears down any resources (threads, timers, scheduled handles) that
    living Virtual instances may have started."""
    Virtuals._instance = None
    yield
    instance = Virtuals._instance
    if instance is not None:
        for virtual in list(instance.values()):
            # Stop the render thread if it was started
            if getattr(virtual, "_active", False):
                virtual._active = False
            if hasattr(virtual, "_thread"):
                virtual._thread.join(timeout=2)
            # Cancel any pending fallback timer
            if getattr(virtual, "fallback_timer", None) is not None:
                virtual.fallback_timer.cancel()
                virtual.fallback_timer = None
            # Cancel any pending clear_handle
            if getattr(virtual, "clear_handle", None) is not None:
                virtual.clear_handle.cancel()
                virtual.clear_handle = None
    Virtuals._instance = None


@pytest.fixture(autouse=True)
def _mock_save_config():
    """Don't actually write to disk during tests."""
    with patch("ledfx.devices.save_config"):
        with patch("ledfx.virtuals.save_config"):
            yield


@pytest.fixture(autouse=True)
def _mock_is_gap_device():
    """Gap devices should return False for our test devices."""
    with patch("ledfx.virtuals.is_gap_device", return_value=False):
        yield


# ---------------------------------------------------------------------------
# Test 1: Device deletion destroys user-created virtual with zero segments
# ---------------------------------------------------------------------------


class TestDeviceDeletionDestroysUserVirtual:
    """Main regression: a non-auto-generated virtual must be destroyed
    when the device it depends on is deleted."""

    @pytest.mark.asyncio
    async def test_user_virtual_destroyed_after_device_removal(self):
        device = _DummyDevice("dev-1", pixel_count=50)
        ledfx = _make_ledfx(devices=[device])
        device._ledfx = ledfx

        virtual = _make_virtual(
            ledfx,
            "v-user",
            "User Virtual",
            segments=[["dev-1", 0, 49, False]],
            auto_generated=False,
        )

        # Simulate setting an effect (just mark it as having one)
        virtual._active_effect = MagicMock()
        virtual._active_effect.id = "eff-1"

        # Bind the method to our dummy device so it runs the real logic
        bound = Device.remove_from_virtuals.__get__(device, type(device))
        await bound()

        # Virtual should be destroyed
        assert ledfx.virtuals.get("v-user") is None
        # Config should not contain the virtual
        assert all(v["id"] != "v-user" for v in ledfx.config["virtuals"])

    @pytest.mark.asyncio
    async def test_config_integrity_after_device_removal(self):
        device = _DummyDevice("dev-1", pixel_count=30)
        ledfx = _make_ledfx(devices=[device])
        device._ledfx = ledfx

        _make_virtual(
            ledfx,
            "v1",
            "Virtual 1",
            segments=[["dev-1", 0, 29, False]],
            auto_generated=False,
        )

        bound = Device.remove_from_virtuals.__get__(device, type(device))
        await bound()

        # No poisoned zero-segment virtual should remain
        for v in ledfx.virtuals.values():
            assert (
                len(v._segments) > 0
            ), f"Virtual {v.id} has zero segments and should have been removed"


# ---------------------------------------------------------------------------
# Test 2: Auto-generated virtual deletion behavior preserved
# ---------------------------------------------------------------------------


class TestAutoGeneratedVirtualDeletion:
    @pytest.mark.asyncio
    async def test_auto_generated_virtual_destroyed(self):
        device = _DummyDevice("dev-1", pixel_count=50)
        ledfx = _make_ledfx(devices=[device])
        device._ledfx = ledfx

        _make_virtual(
            ledfx,
            "v-auto",
            "Auto Virtual",
            segments=[["dev-1", 0, 49, False]],
            auto_generated=True,
        )

        bound = Device.remove_from_virtuals.__get__(device, type(device))
        await bound()

        assert ledfx.virtuals.get("v-auto") is None

    @pytest.mark.asyncio
    async def test_partial_segment_removal_keeps_virtual(self):
        """If a virtual has segments on two devices and only one is removed,
        the virtual should survive with the remaining segments."""
        dev1 = _DummyDevice("dev-1", pixel_count=50)
        dev2 = _DummyDevice("dev-2", pixel_count=50)
        ledfx = _make_ledfx(devices=[dev1, dev2])
        dev1._ledfx = ledfx
        dev2._ledfx = ledfx

        virtual = _make_virtual(
            ledfx,
            "v-multi",
            "Multi Virtual",
            segments=[["dev-1", 0, 49, False], ["dev-2", 0, 49, False]],
            auto_generated=False,
        )

        bound = Device.remove_from_virtuals.__get__(dev1, type(dev1))
        await bound()

        # Virtual should survive with dev-2 segments only
        surviving = ledfx.virtuals.get("v-multi")
        assert surviving is not None
        assert len(surviving._segments) == 1
        assert surviving._segments[0][0] == "dev-2"


# ---------------------------------------------------------------------------
# Test 3: Startup restore with poisoned config does not crash
# ---------------------------------------------------------------------------


class TestStartupRestoreWithPoisonedConfig:
    def test_zero_segments_virtual_with_effect_does_not_crash(self):
        """A virtual with zero segments and an effect in config should
        not crash create_from_config()."""
        ledfx = _make_ledfx()

        poisoned_config = [
            {
                "id": "v-poison",
                "config": {"name": "Poisoned Virtual"},
                "segments": [],
                "is_device": False,
                "auto_generated": False,
                "effect": {
                    "type": "singleColor",
                    "config": {"color": "#ff0000"},
                },
            },
        ]

        # This must not raise
        ledfx.virtuals.create_from_config(poisoned_config)

        # Virtual is created but should have no active effect
        virtual = ledfx.virtuals.get("v-poison")
        assert virtual is not None
        assert virtual._active_effect is None

    def test_no_segments_key_with_effect_does_not_crash(self):
        """A virtual config with no 'segments' key at all should not crash."""
        ledfx = _make_ledfx()

        config = [
            {
                "id": "v-noseg",
                "config": {"name": "No Segments Virtual"},
                "is_device": False,
                "auto_generated": False,
                "effect": {
                    "type": "singleColor",
                    "config": {},
                },
            },
        ]

        ledfx.virtuals.create_from_config(config)
        virtual = ledfx.virtuals.get("v-noseg")
        assert virtual is not None
        assert virtual._active_effect is None


# ---------------------------------------------------------------------------
# Test 4: Mixed valid and invalid virtuals during startup
# ---------------------------------------------------------------------------


class TestMixedValidInvalidStartup:
    def test_bad_virtual_does_not_prevent_good_virtual_restore(self):
        """One bad virtual must not prevent valid virtuals from restoring."""
        device = _DummyDevice("dev-1", pixel_count=50)
        ledfx = _make_ledfx(devices=[device])

        config = [
            # Bad virtual: has effect but no segments
            {
                "id": "v-bad",
                "config": {"name": "Bad Virtual"},
                "segments": [],
                "is_device": False,
                "auto_generated": False,
                "effect": {
                    "type": "singleColor",
                    "config": {},
                },
            },
            # Good virtual: has segments and effect
            {
                "id": "v-good",
                "config": {"name": "Good Virtual"},
                "segments": [["dev-1", 0, 49, False]],
                "is_device": False,
                "auto_generated": False,
                "effect": {
                    "type": "singleColor",
                    "config": {},
                },
            },
        ]

        ledfx.virtuals.create_from_config(config)

        # Bad virtual created but has no effect
        bad = ledfx.virtuals.get("v-bad")
        assert bad is not None
        assert bad._active_effect is None

        # Good virtual created and has effect set
        good = ledfx.virtuals.get("v-good")
        assert good is not None
        assert good._active_effect is not None


# ---------------------------------------------------------------------------
# Test 5: Scene cleanup when virtual removed due to segment loss
# ---------------------------------------------------------------------------


class TestSceneCleanupOnVirtualRemoval:
    @pytest.mark.asyncio
    async def test_scene_references_removed_with_virtual(self):
        device = _DummyDevice("dev-1", pixel_count=50)
        ledfx = _make_ledfx(
            devices=[device],
            scenes={
                "scene-1": {
                    "name": "Test Scene",
                    "virtuals": {
                        "v-del": {"type": "singleColor", "config": {}},
                        "v-keep": {"type": "bars", "config": {}},
                    },
                }
            },
        )
        device._ledfx = ledfx

        _make_virtual(
            ledfx,
            "v-del",
            "To Delete",
            segments=[["dev-1", 0, 49, False]],
            auto_generated=False,
        )

        bound = Device.remove_from_virtuals.__get__(device, type(device))
        await bound()

        # v-del should be removed from the scene
        scene_virtuals = ledfx.config["scenes"]["scene-1"]["virtuals"]
        assert "v-del" not in scene_virtuals
        # v-keep should still be in the scene
        assert "v-keep" in scene_virtuals

    @pytest.mark.asyncio
    async def test_multiple_scenes_cleaned(self):
        device = _DummyDevice("dev-1", pixel_count=50)
        ledfx = _make_ledfx(
            devices=[device],
            scenes={
                "s1": {
                    "name": "Scene 1",
                    "virtuals": {"v1": {"type": "a", "config": {}}},
                },
                "s2": {
                    "name": "Scene 2",
                    "virtuals": {"v1": {"type": "b", "config": {}}},
                },
            },
        )
        device._ledfx = ledfx

        _make_virtual(
            ledfx,
            "v1",
            "Virtual 1",
            segments=[["dev-1", 0, 49, False]],
        )

        bound = Device.remove_from_virtuals.__get__(device, type(device))
        await bound()

        assert "v1" not in ledfx.config["scenes"]["s1"]["virtuals"]
        assert "v1" not in ledfx.config["scenes"]["s2"]["virtuals"]


# ---------------------------------------------------------------------------
# Test 6: Empty-segment virtual defensive behavior
# ---------------------------------------------------------------------------


class TestEmptySegmentDefensiveBehavior:
    def test_set_effect_raises_value_error_for_no_segments(self):
        """set_effect() should raise ValueError when no segments exist."""
        ledfx = _make_ledfx()
        virtual = _make_virtual(
            ledfx,
            "v-empty",
            "Empty",
            segments=[],
        )
        effect = MagicMock()
        with pytest.raises(ValueError, match="Cannot activate"):
            virtual.set_effect(effect)

    def test_activate_raises_runtime_error_for_no_segments(self):
        """activate() should raise RuntimeError when no segments exist."""
        ledfx = _make_ledfx()
        virtual = _make_virtual(
            ledfx,
            "v-empty2",
            "Empty 2",
            segments=[],
        )
        with pytest.raises(RuntimeError, match="Cannot activate"):
            virtual.activate()

    def test_create_from_config_catches_value_error(self):
        """Even if set_effect raises ValueError, startup should not crash."""
        ledfx = _make_ledfx()

        config = [
            {
                "id": "v-err",
                "config": {"name": "Error Virtual"},
                "segments": [],
                "is_device": False,
                "auto_generated": False,
                "effect": {
                    "type": "singleColor",
                    "config": {},
                },
            },
        ]

        # Must not raise
        ledfx.virtuals.create_from_config(config)

        virtual = ledfx.virtuals.get("v-err")
        assert virtual is not None
        # Effect should not be set on a segmentless virtual
        assert virtual._active_effect is None


# ---------------------------------------------------------------------------
# Test 7: Cached property invalidation after segment mutation
# ---------------------------------------------------------------------------


class TestCachedPropertyInvalidation:
    @pytest.mark.asyncio
    async def test_cached_devices_invalidated_after_segment_removal(self):
        """After remove_from_virtuals strips segments, the cached _devices
        property must reflect the new state."""
        dev1 = _DummyDevice("dev-1", pixel_count=50)
        dev2 = _DummyDevice("dev-2", pixel_count=50)
        ledfx = _make_ledfx(devices=[dev1, dev2])
        dev1._ledfx = ledfx

        virtual = _make_virtual(
            ledfx,
            "v-multi",
            "Multi",
            segments=[["dev-1", 0, 49, False], ["dev-2", 0, 49, False]],
        )

        # Prime the cached property
        _ = virtual._devices
        assert len(virtual._devices) == 2

        bound = Device.remove_from_virtuals.__get__(dev1, type(dev1))
        await bound()

        surviving = ledfx.virtuals.get("v-multi")
        assert surviving is not None
        # After invalidation the cached property should only show dev-2
        assert len(surviving._devices) == 1


# ---------------------------------------------------------------------------
# Test 8: Logging verification
# ---------------------------------------------------------------------------


class TestLogging:
    def test_startup_logs_warning_for_poisoned_virtual(self, caplog):
        """create_from_config should log a clear warning when skipping
        effect restore for a zero-segment virtual."""
        ledfx = _make_ledfx()

        config = [
            {
                "id": "v-log",
                "config": {"name": "Log Virtual"},
                "segments": [],
                "is_device": False,
                "auto_generated": False,
                "effect": {
                    "type": "singleColor",
                    "config": {},
                },
            },
        ]

        with caplog.at_level(logging.WARNING, logger="ledfx.virtuals"):
            ledfx.virtuals.create_from_config(config)

        assert any(
            "v-log" in record.message
            and "no device segments" in record.message
            for record in caplog.records
        ), f"Expected warning about v-log, got: {[r.message for r in caplog.records]}"
