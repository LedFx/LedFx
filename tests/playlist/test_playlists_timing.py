import asyncio

import pytest

from ledfx.playlists import PlaylistManager


class DummyScenes:
    def __init__(self):
        self.activated = []

    def activate(self, scene_id, save_config_after=True):
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
async def test_shuffle_regenerates_on_natural_cycle_completion(tmp_path):
    """Test that shuffle generates a new random order after completing a full
    cycle via natural timer progression (not manual next/prev)."""
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "shuffle2",
        "name": "Shuffle Two",
        "mode": "shuffle",
        "items": [
            {"scene_id": "a", "duration_ms": 500},
            {"scene_id": "b", "duration_ms": 500},
            {"scene_id": "c", "duration_ms": 500},
            {"scene_id": "d", "duration_ms": 500},
        ],
    }

    await manager.create_or_replace(playlist)
    await manager.start("shuffle2")
    await asyncio.sleep(0.05)
    state1 = await manager.get_state()
    order1 = state1.get("order")
    assert order1 is not None
    assert sorted(order1) == [0, 1, 2, 3]

    # Wait for one complete cycle (4 items × 500ms + buffer)
    await asyncio.sleep(2.2)

    # Get order after natural cycle completion
    state2 = await manager.get_state()
    order2 = state2.get("order")
    assert order2 is not None
    assert sorted(order2) == [0, 1, 2, 3]

    # With 4! = 24 possible permutations, verify we got a different order
    # In extremely rare cases (<5%) this might fail, but it's very unlikely
    # We run this multiple cycles to increase confidence
    orders_seen = [tuple(order1), tuple(order2)]

    # Wait for 2 more cycles
    for _ in range(2):
        await asyncio.sleep(2.2)
        state = await manager.get_state()
        order = state.get("order")
        assert order is not None
        orders_seen.append(tuple(order))

    # With 4 samples from 24 permutations, we should see at least 2 different orders
    unique_orders = set(orders_seen)
    assert (
        len(unique_orders) >= 2
    ), f"Expected shuffle to generate different orders but got: {orders_seen}"

    await manager.stop()


@pytest.mark.asyncio
async def test_next_regenerates_shuffle_on_wrap(tmp_path):
    """Test that calling next() regenerates shuffle order when wrapping from
    last item back to first."""
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "shuffle3",
        "name": "Shuffle Three",
        "mode": "shuffle",
        "items": [
            {"scene_id": "a", "duration_ms": 500},
            {"scene_id": "b", "duration_ms": 500},
            {"scene_id": "c", "duration_ms": 500},
            {"scene_id": "d", "duration_ms": 500},
        ],
    }

    await manager.create_or_replace(playlist)
    await manager.start("shuffle3")
    await asyncio.sleep(0.05)
    state1 = await manager.get_state()
    order1 = state1.get("order")
    assert order1 is not None

    # Manually advance through all items using next()
    for _ in range(len(order1)):
        await manager.next()
        await asyncio.sleep(0.05)

    # After wrapping, we should have a new shuffle order
    state2 = await manager.get_state()
    order2 = state2.get("order")
    assert order2 is not None
    assert sorted(order2) == [0, 1, 2, 3]

    # Collect multiple samples to verify regeneration
    orders_seen = [tuple(order1), tuple(order2)]
    for _ in range(2):
        for _ in range(len(order2)):
            await manager.next()
            await asyncio.sleep(0.05)
        state = await manager.get_state()
        order = state.get("order")
        assert order is not None
        orders_seen.append(tuple(order))

    # With 4! = 24 permutations and 4 samples, should see at least 2 different
    unique_orders = set(orders_seen)
    assert (
        len(unique_orders) >= 2
    ), f"Expected next() to generate different shuffle orders but got: {orders_seen}"

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
