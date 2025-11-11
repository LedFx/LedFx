import asyncio
import random

import pytest

from ledfx.playlists import PlaylistManager


class DummyScenes:
    def __init__(self):
        self.activated = []

    def activate(self, scene_id):
        self.activated.append(scene_id)


class DummyCore:
    def __init__(self, tmpdir):
        self.config_dir = tmpdir
        self.config = {"playlists": {}, "scenes": {}}
        self.scenes = type(
            "S",
            (),
            {
                "scenes": {},
                "activated": [],
                "activate": lambda self, s: self.activated.append(s),
            },
        )()
        self.scenes = DummyScenes()


@pytest.mark.asyncio
async def test_runtime_timing_override_applies(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "rt1",
        "name": "RT1",
        "items": [{"scene_id": "s", "duration_ms": 1000}],
        # configured timing disabled — we'll provide runtime override
        "timing": {"jitter": {"enabled": False}},
    }

    await manager.create_or_replace(playlist)

    # deterministic sampling
    random.seed(1)
    timing_override = {
        "jitter": {"enabled": True, "factor_min": 1.2, "factor_max": 1.5}
    }
    await manager.start("rt1", timing=timing_override)
    await asyncio.sleep(0.05)
    state = await manager.get_state()
    eff = state.get("effective_duration_ms")
    assert eff is not None
    # effective should be between 1000*min and 1000*max (and at least 500)
    assert 1200 <= eff <= 1500
    await manager.stop()


@pytest.mark.asyncio
async def test_runtime_timing_override_preserved_across_pause_resume(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "rt2",
        "name": "RT2",
        "items": [{"scene_id": "sX", "duration_ms": 1000}],
    }

    await manager.create_or_replace(playlist)

    # deterministic sampling
    random.seed(7)
    timing_override = {
        "jitter": {"enabled": True, "factor_min": 1.0, "factor_max": 1.7}
    }
    await manager.start("rt2", timing=timing_override)
    await asyncio.sleep(0.05)

    state_before = await manager.get_state()
    eff_before = state_before.get("effective_duration_ms")
    assert eff_before is not None

    await manager.pause()
    await asyncio.sleep(0.01)
    state_paused = await manager.get_state()
    eff_paused = state_paused.get("effective_duration_ms")
    assert eff_paused == eff_before

    await manager.resume()
    await asyncio.sleep(0.01)
    state_after = await manager.get_state()
    eff_after = state_after.get("effective_duration_ms")
    # effective duration should remain the same (preserved sample)
    assert eff_after == eff_before

    await manager.stop()


@pytest.mark.asyncio
async def test_configured_timing_used_when_no_override(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "rt3",
        "name": "RT3",
        "items": [{"scene_id": "sY", "duration_ms": 1000}],
        "timing": {
            "jitter": {"enabled": True, "factor_min": 0.8, "factor_max": 1.2}
        },
    }

    await manager.create_or_replace(playlist)
    random.seed(3)
    await manager.start("rt3")
    await asyncio.sleep(0.05)
    state = await manager.get_state()
    eff = state.get("effective_duration_ms")
    assert eff is not None
    assert 800 <= eff <= 1200
    await manager.stop()
