import json
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from ledfx.api.config import ConfigEndpoint
from ledfx.api.integration_spotify import QLCEndpoint as SpotifyEndpoint
from ledfx.api.integrations import IntegrationsEndpoint
from ledfx.api.scenes import ScenesEndpoint
from ledfx.configuration.migrations import CURRENT_SCHEMA_VERSION
from ledfx.integrations.spotify import Spotify
from tests.test_utilities.fake_ledfx import fake_ledfx


def _request(method: str, body: object) -> MagicMock:
    request = MagicMock(spec=web.Request, method=method)
    request.json = AsyncMock(return_value=body)
    return request


def _endpoint(
    config: dict[str, object] | None = None,
) -> tuple[ConfigEndpoint, MagicMock]:
    ledfx = fake_ledfx(config)
    ledfx.hosts = ["10.0.0.2"]
    ledfx.audio = None
    return ConfigEndpoint(ledfx), ledfx


async def test_put_unknown_key_is_rejected_with_legacy_snackbar() -> None:
    # invalid_request keeps its legacy 200 + "failed" shape so the snackbar shows it
    endpoint, ledfx = _endpoint()
    response = await endpoint.put(_request("PUT", {"bogus": 1}))
    body = json.loads(response.text or "")
    assert body["status"] == "failed" and "bogus" in body["payload"]["reason"]
    ledfx.config_store.request_save.assert_not_called()


async def test_put_readonly_key_is_rejected() -> None:
    endpoint, _ = _endpoint()
    response = await endpoint.put(_request("PUT", {"instance_id": "x"}))
    body = json.loads(response.text or "")
    assert body["status"] == "failed" and "instance_id" in body["payload"]["reason"]


# Core keys PUT /api/config rejects: everything outside PERMITTED_KEYS["core"],
# except the sections it merges (audio, melbanks, wled_preferences) and
# user_presets, which it replaces whole.
@pytest.mark.parametrize(
    "key",
    [
        "devices",
        "virtuals",
        "scenes",
        "playlists",
        "integrations",
        "user_colors",
        "user_gradients",
        "sendspin_servers",
        "now_playing",
        "image_cache",
        "debug_asyncio",
        "instance_id",
    ],
)
async def test_put_non_permitted_core_key_is_rejected(key: str) -> None:
    endpoint, ledfx = _endpoint()
    response = await endpoint.put(_request("PUT", {key: None}))
    body = json.loads(response.text or "")
    assert body["status"] == "failed" and key in body["payload"]["reason"]
    ledfx.config_store.request_save.assert_not_called()


async def test_put_invalid_value_returns_structured_errors_and_changes_nothing() -> (
    None
):
    endpoint, ledfx = _endpoint()
    response = await endpoint.put(
        _request("PUT", {"global_brightness": 5, "scan_on_startup": True})
    )
    body = json.loads(response.text or "")
    assert response.status == 400
    assert body["errors"][0]["loc"] == ["global_brightness"]
    assert ledfx.config.scan_on_startup is False  # nothing applied


async def test_put_restarts_only_when_a_restart_field_changed() -> None:
    endpoint, ledfx = _endpoint({"port": 8888})
    await endpoint.put(_request("PUT", {"port": 8888, "global_brightness": 0.5}))
    ledfx.loop.call_soon_threadsafe.assert_not_called()
    await endpoint.put(_request("PUT", {"port": 9999}))
    ledfx.loop.call_soon_threadsafe.assert_called_once()


async def test_get_includes_runtime_keys() -> None:
    endpoint, _ = _endpoint()
    request = make_mocked_request("GET", "/api/config")
    body = json.loads((await endpoint.get(request)).text or "")
    assert body["hosts"] == ["10.0.0.2"] and body["configuration_version"] == "2.3.6"
    assert "ledfx_presets" in body


async def test_post_import_is_lenient_and_replaces() -> None:
    endpoint, ledfx = _endpoint()
    ledfx.config_store.replace = AsyncMock()
    response = await endpoint.post(
        _request(
            "POST",
            {"configuration_version": "2.3.6", "port": 1, "visualisation_fps": 999},
        )
    )
    assert response.status == 200
    (imported,), _ = ledfx.config_store.replace.call_args
    assert (
        imported.port == 1 and imported.visualisation_fps == 30
    )  # bad value defaulted
    ledfx.config_store.quarantine.assert_called()


async def test_post_import_rejects_a_newer_schema_version() -> None:
    endpoint, ledfx = _endpoint()
    ledfx.config_store.replace = AsyncMock()
    future = {"schema_version": CURRENT_SCHEMA_VERSION + 1, "port": 1, "new": 1}
    response = await endpoint.post(_request("POST", future))
    body = json.loads(response.text or "")
    assert body["status"] == "failed" and "newer" in body["payload"]["reason"]
    ledfx.config_store.replace.assert_not_called()
    ledfx.config_store.backup.assert_not_called()


async def test_put_rolls_back_every_field_when_a_runtime_update_fails() -> None:
    endpoint, ledfx = _endpoint()
    before = ledfx.config.model_copy(deep=True)
    ledfx.events.fire_event.side_effect = RuntimeError("listener failed")
    response = await endpoint.put(
        _request(
            "PUT", {"global_brightness": 0.5, "melbanks": {"max_frequencies": [8000]}}
        )
    )
    assert response.status == 500
    assert ledfx.config == before
    ledfx.config_store.request_save.assert_not_called()


async def test_scene_rename_reports_the_old_name() -> None:
    ledfx = fake_ledfx({"scenes": {"s1": {"name": "Old"}}})
    body = {"id": "s1", "action": "rename", "name": "New"}
    response = await ScenesEndpoint(ledfx).put(_request("PUT", body))
    reason = json.loads(response.text or "")["payload"]["reason"]
    assert reason == "Renamed Old to New"
    assert ledfx.config.scenes["s1"].name == "New"


async def test_post_import_rejects_a_non_object_body() -> None:
    endpoint, ledfx = _endpoint()
    ledfx.config_store.replace = AsyncMock()
    for body in ([1, 2], "config", None):
        response = await endpoint.post(_request("POST", body))
        payload = json.loads(response.text or "")
        assert response.status == 200 and payload["status"] == "failed"
        assert "not a LedFx config" in payload["payload"]["reason"]
    ledfx.config_store.replace.assert_not_called()


def _spotify_endpoint() -> tuple[SpotifyEndpoint, Spotify, MagicMock]:
    ledfx = fake_ledfx(
        {
            "scenes": {"s1": {"name": "S1"}},
            "integrations": [{"id": "sp", "type": "spotify", "data": {}}],
        }
    )
    spotify = Spotify(ledfx, {"name": "Spotify"}, False, {})
    vars(spotify).update(_id="sp", _type="spotify")  # set by the registry
    ledfx.integrations.get.return_value = spotify
    return SpotifyEndpoint(ledfx), spotify, ledfx


async def test_spotify_trigger_add_and_delete_persist() -> None:
    endpoint, spotify, ledfx = _spotify_endpoint()
    trigger = {
        "scene_id": "s1",
        "song_id": "abc",
        "song_name": "Song",
        "song_position": 1000,
    }
    await endpoint.post("sp", _request("POST", trigger))
    entry = ledfx.config.integrations[0]
    assert entry.data == {"s1": {"abc-1000": ["abc", "Song", 1000]}}
    assert spotify.get_triggers() == {
        "s1": {"name": "S1", "abc-1000": ["abc", "Song", 1000]}
    }
    ledfx.config_store.request_save.assert_called_once()
    await endpoint.delete("sp", _request("DELETE", {"trigger_id": "abc-1000"}))
    assert entry.data == {"s1": {}}
    assert ledfx.config_store.request_save.call_count == 2


async def test_integration_update_keeps_stored_data() -> None:
    ledfx = fake_ledfx(
        {"integrations": [{"id": "sp", "type": "spotify", "data": {"s1": {}}}]}
    )
    ledfx.integrations.get_class.return_value = Spotify
    ledfx.integrations.get.return_value.type = "spotify"
    body = {"id": "sp", "type": "spotify", "config": {"name": "Renamed"}}
    await IntegrationsEndpoint(ledfx).post(_request("POST", body))
    assert ledfx.integrations.create.call_args.kwargs["data"] == {"s1": {}}
    assert ledfx.config.integrations[0].config["name"] == "Renamed"


async def test_invalid_integration_update_keeps_the_running_integration() -> None:
    ledfx = fake_ledfx({"integrations": [{"id": "sp", "type": "spotify"}]})
    ledfx.integrations.get_class.return_value = Spotify
    body = {"id": "sp", "type": "spotify", "config": {"name": ["not", "a", "name"]}}
    response = await IntegrationsEndpoint(ledfx).post(_request("POST", body))
    assert json.loads(response.text or "")["status"] == "failed"
    ledfx.integrations.destroy.assert_not_called()
    ledfx.integrations.create.assert_not_called()


@pytest.mark.parametrize("config", ["abc", 5, [["name", "x"]]])
async def test_non_object_integration_config_is_a_validation_error(
    config: object,
) -> None:
    ledfx = fake_ledfx()
    ledfx.integrations.get_class.return_value = Spotify
    body = {"type": "spotify", "config": config}
    response = await IntegrationsEndpoint(ledfx).post(_request("POST", body))
    assert response.status == 400
    ledfx.integrations.create.assert_not_called()


async def test_new_integration_stores_raw_data_not_display_data() -> None:
    ledfx = fake_ledfx({"scenes": {"s1": {"name": "S1"}}})
    config = Spotify.config_model().model_validate({"name": "Spotify"})
    spotify = Spotify(ledfx, config, False, None)
    vars(spotify).update(_id="sp", _type="spotify")  # set by the registry
    spotify.add_trigger("s1", "abc", "Song", 1000)
    ledfx.integrations.get_class.return_value = Spotify
    ledfx.integrations.create.return_value = spotify
    body = {"type": "spotify", "config": {"name": "Spotify"}}
    await IntegrationsEndpoint(ledfx).post(_request("POST", body))
    assert ledfx.config.integrations[0].data == {
        "s1": {"abc-1000": ["abc", "Song", 1000]}
    }
