import asyncio
import random

import pytest

from ledfx.playlists import PlaylistManager


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


@pytest.mark.asyncio
async def test_sequence_start_overrides_prior_shuffle(tmp_path):
    """Start with sequence should produce identity order even after a prior shuffle."""
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "mseq",
        "name": "ModeSeq",
        "mode": "shuffle",
        "items": [
            {"scene_id": "a"},
            {"scene_id": "b"},
            {"scene_id": "c"},
        ],
    }

    await manager.create_or_replace(playlist)

    # start shuffled first to create a shuffled order
    await manager.start("mseq", mode="shuffle")
    await asyncio.sleep(0.05)
    state_shuf = await manager.get_state()
    order_shuf = state_shuf.get("order")
    assert order_shuf is not None
    assert sorted(order_shuf) == [0, 1, 2]

    # now start in sequence; this must regenerate an identity order
    await manager.start("mseq", mode="sequence")
    await asyncio.sleep(0.05)
    state_seq = await manager.get_state()
    order_seq = state_seq.get("order")
    assert order_seq == [0, 1, 2]

    await manager.stop()


@pytest.mark.asyncio
async def test_shuffle_start_overrides_prior_sequence(tmp_path):
    """Start with shuffle should produce a valid shuffled permutation even when playlist default is sequence."""
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "mshuf",
        "name": "ModeShuf",
        "mode": "sequence",
        "items": [
            {"scene_id": "x"},
            {"scene_id": "y"},
            {"scene_id": "z"},
            {"scene_id": "w"},
        ],
    }

    await manager.create_or_replace(playlist)

    # Ensure deterministic shuffle for the test
    random.seed(42)
    await manager.start("mshuf", mode="shuffle")
    await asyncio.sleep(0.05)
    state = await manager.get_state()
    assert state.get("mode") == "shuffle"
    order = state.get("order")
    assert order is not None
    assert sorted(order) == [0, 1, 2, 3]
    # ensure it's a permutation
    assert len(set(order)) == 4

    await manager.stop()


@pytest.mark.asyncio
async def test_configured_mode_is_used_when_no_override(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "mconf",
        "name": "ModeConf",
        "mode": "shuffle",
        "items": [{"scene_id": "1"}, {"scene_id": "2"}, {"scene_id": "3"}],
    }

    await manager.create_or_replace(playlist)
    await manager.start("mconf")
    await asyncio.sleep(0.05)
    state = await manager.get_state()
    assert state.get("mode") == "shuffle"
    order = state.get("order")
    assert order is not None
    assert sorted(order) == [0, 1, 2]

    await manager.stop()
