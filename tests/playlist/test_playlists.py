import asyncio

import pytest

from ledfx.playlists import PlaylistManager


class DummyCore:
    def __init__(self, tmpdir):
        self.config_dir = tmpdir
        self.config = {"playlists": {}}


@pytest.mark.asyncio
async def test_create_and_list_playlists(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "evening",
        "name": "Evening",
        "items": [{"scene_id": "s1", "duration_ms": 500}, {"scene_id": "s2"}],
    }

    p = await manager.create_or_replace(playlist)
    assert p["id"] == "evening"

    allp = manager.list_playlists()
    assert "evening" in allp

    # ensure persisted in core.config
    assert core.config["playlists"]["evening"]["name"] == "Evening"


@pytest.mark.asyncio
async def test_create_generates_id_when_missing(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {"name": "My Playlist", "items": [{"scene_id": "s1"}]}
    p = await manager.create_or_replace(playlist)
    assert "id" in p
    assert p["id"] in core.config["playlists"]


@pytest.mark.asyncio
async def test_validation_rejects_short_duration(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    bad = {
        "id": "bad",
        "name": "Bad",
        "items": [{"scene_id": "s1", "duration_ms": 100}],
    }
    with pytest.raises(Exception):
        # create_or_replace is async, await it properly
        await manager.create_or_replace(bad)


@pytest.mark.asyncio
async def test_delete_stops_active_playlist(tmp_path):
    core = DummyCore(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "to-delete",
        "name": "To Delete",
        "items": [
            {"scene_id": "s1", "duration_ms": 500},
            {"scene_id": "s2", "duration_ms": 500},
        ],
    }

    await manager.create_or_replace(playlist)

    ok = await manager.start("to-delete")
    assert ok is True
    # give the runner a moment to start
    await asyncio.sleep(0.01)

    # delete should stop the playlist and return True
    deleted = await manager.delete("to-delete")
    assert deleted is True

    # active playlist should be cleared and task should be None
    assert manager._active_playlist_id is None
    assert manager._task is None
