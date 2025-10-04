import asyncio

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
        self.config = {"playlists": {}}
        self.scenes = DummyScenes()


@pytest.mark.asyncio
async def test_shuffle_per_cycle(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "shuffle1",
        "name": "Shuffle One",
        "mode": "shuffle",
        "items": [
            {"scene_id": "a"},
            {"scene_id": "b"},
            {"scene_id": "c"},
        ],
    }

    await manager.create_or_replace(playlist)
    await manager.start("shuffle1")
    # Give time for first activation
    await asyncio.sleep(0.1)
    state1 = await manager.get_state()
    order1 = state1.get("order")
    assert order1 is not None
    assert sorted(order1) == [0, 1, 2]

    # advance through cycle to force regeneration
    # advance by length to wrap the cycle
    for _ in range(len(order1)):
        await manager.next()
        await asyncio.sleep(0.05)

    state2 = await manager.get_state()
    order2 = state2.get("order")
    assert order2 is not None
    assert sorted(order2) == [0, 1, 2]
    # It's okay if shuffle repeats occasionally, but ensure order is a permutation
    assert len(set(order2)) == 3

    await manager.stop()


@pytest.mark.asyncio
async def test_get_state_includes_timing_fields(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "t1",
        "name": "T1",
        "items": [{"scene_id": "s1", "duration_ms": 700}],
    }

    await manager.create_or_replace(playlist)
    await manager.start("t1")
    await asyncio.sleep(0.05)
    state = await manager.get_state()
    assert "effective_duration_ms" in state
    assert "remaining_ms" in state
    # remaining should be <= effective
    assert state["remaining_ms"] <= state["effective_duration_ms"]
    await manager.stop()


@pytest.mark.asyncio
async def test_pause_sets_remaining_and_resume_uses_it(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "t2",
        "name": "T2",
        "items": [{"scene_id": "sX", "duration_ms": 800}],
    }

    await manager.create_or_replace(playlist)
    await manager.start("t2")
    await asyncio.sleep(0.1)
    await manager.pause()
    state = await manager.get_state()
    assert "remaining_ms" in state
    rem = int(state["remaining_ms"])
    assert rem > 0
    # resume and ensure the item completes (activation list grows)
    before = list(core.scenes.activated)
    await manager.resume()
    await asyncio.sleep((rem / 1000.0) + 0.2)
    after = list(core.scenes.activated)
    assert len(after) >= len(before) + 1
    await manager.stop()
