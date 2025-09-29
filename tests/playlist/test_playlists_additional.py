import asyncio
import json

import pytest
from aiohttp import web

from ledfx.api.playlists import PlaylistsEndpoint
from ledfx.api.playlists_active import ActivePlaylistEndpoint
from ledfx.playlists import PlaylistManager


class DummyCoreWithEvents:
    def __init__(self, tmpdir):
        self.config_dir = tmpdir
        self.config = {"playlists": {}}
        self.scenes = type(
            "S",
            (),
            {
                "activated": [],
                "activate": lambda self, s: self.activated.append(s),
            },
        )()
        # simple event collector
        self.events = type(
            "E",
            (),
            {"fired": [], "fire_event": lambda self, e: self.fired.append(e)},
        )()


@pytest.mark.asyncio
async def test_events_include_timing_fields(tmp_path):
    core = DummyCoreWithEvents(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "evt1",
        "name": "Evt1",
        "items": [{"scene_id": "s1", "duration_ms": 700}],
    }
    await manager.create_or_replace(playlist)
    await manager.start("evt1")
    await asyncio.sleep(0.05)

    # ensure we recorded events and that at least one has effective_duration_ms
    fired = list(core.events.fired)
    assert len(fired) > 0
    assert any(hasattr(ev, "effective_duration_ms") for ev in fired)
    # pause should produce a paused event with remaining_ms
    await manager.pause()
    await asyncio.sleep(0.01)
    assert any(hasattr(ev, "remaining_ms") for ev in core.events.fired)
    await manager.stop()


@pytest.mark.asyncio
async def test_delete_emits_stopped_event(tmp_path):
    core = DummyCoreWithEvents(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "del1",
        "name": "Del1",
        "items": [{"scene_id": "x", "duration_ms": 1000}],
    }
    await manager.create_or_replace(playlist)
    await manager.start("del1")
    await asyncio.sleep(0.01)

    # delete should stop and fire a stopped event
    await manager.delete("del1")
    await asyncio.sleep(0.01)
    fired_types = [getattr(e, "event_type", None) for e in core.events.fired]
    assert "playlist_stopped" in fired_types


def make_minimal_ledfx_for_endpoint(tmp_path):
    # minimal object with config used by PlaylistManager
    ledfx = type("L", (), {})()
    ledfx.config = {"playlists": {}}
    ledfx.config_dir = str(tmp_path)
    return ledfx


@pytest.mark.asyncio
async def test_active_endpoint_returns_null_when_inactive(tmp_path):
    ledfx = make_minimal_ledfx_for_endpoint(tmp_path)
    endpoint = ActivePlaylistEndpoint(ledfx)
    resp: web.Response = await endpoint.get()
    body = json.loads(resp.text)
    assert body.get("data") == {"state": None}


@pytest.mark.asyncio
async def test_get_playlists_endpoint_returns_empty_when_no_playlists(
    tmp_path,
):
    """Ensure the collection GET endpoint returns an empty mapping when none exist."""
    ledfx = make_minimal_ledfx_for_endpoint(tmp_path)
    endpoint = PlaylistsEndpoint(ledfx)
    resp: web.Response = await endpoint.get()
    body = json.loads(resp.text)
    # PlaylistsEndpoint.bare_request_success returns the payload directly
    assert body == {"playlists": {}}


@pytest.mark.asyncio
async def test_start_rejects_empty_playlist(tmp_path):
    core = DummyCoreWithEvents(str(tmp_path))
    manager = PlaylistManager(core)

    await manager.create_or_replace(
        {"id": "empty", "name": "Empty", "items": []}
    )
    ok = await manager.start("empty")
    assert ok is False


@pytest.mark.asyncio
async def test_jitter_bounds(tmp_path):
    core = DummyCoreWithEvents(str(tmp_path))
    manager = PlaylistManager(core)

    playlist = {
        "id": "j1",
        "name": "J1",
        "items": [{"scene_id": "s", "duration_ms": 1000}],
        "timing": {
            "jitter": {"enabled": True, "factor_min": 0.5, "factor_max": 2.0}
        },
    }
    await manager.create_or_replace(playlist)
    await manager.start("j1")
    await asyncio.sleep(0.05)
    state = await manager.get_state()
    eff = state.get("effective_duration_ms")
    assert eff is not None
    # should be between 500 (clamp) and 2000 (1k * 2.0)
    assert 500 <= eff <= 2000
    await manager.stop()
