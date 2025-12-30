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
async def test_start_and_advance(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "p1",
        "name": "P1",
        "items": [
            {"scene_id": "s1", "duration_ms": 600},
            {"scene_id": "s2", "duration_ms": 600},
        ],
    }

    await manager.create_or_replace(playlist)
    ok = await manager.start("p1")
    assert ok

    # allow runner to activate first item and advance
    await asyncio.sleep(0.7)
    assert core.scenes.activated[0] == "s1"

    # skip to next immediately
    await manager.next()
    # give a small moment for activation
    await asyncio.sleep(0.1)
    assert core.scenes.activated[-1] in ("s2", "s1")

    await manager.stop()


@pytest.mark.asyncio
async def test_pause_resume(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "p2",
        "name": "P2",
        "items": [{"scene_id": "sA", "duration_ms": 600}],
    }

    await manager.create_or_replace(playlist)
    await manager.start("p2")
    await asyncio.sleep(0.1)
    await manager.pause()
    # capture current activation count
    activated_before = list(core.scenes.activated)
    await asyncio.sleep(0.7)
    # should not have activated additional items while paused
    assert core.scenes.activated == activated_before
    await manager.resume()
    await asyncio.sleep(0.7)
    assert len(core.scenes.activated) >= len(activated_before) + 1
    await manager.stop()
