"""Regression tests for v1 REST API bugs: each endpoint either does what its
success response says, or answers with its usual failure response."""

import asyncio
import copy
import json
import threading
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ledfx.api import RestEndpoint
from ledfx.api.assets_download import AssetsDownloadEndpoint
from ledfx.api.assets_thumbnail import AssetsThumbnailEndpoint
from ledfx.api.cache_images_refresh import CacheRefreshEndpoint
from ledfx.api.check_for_updates import CheckLedFxUpdatesEndPoint
from ledfx.api.colors import ColorEndpoint
from ledfx.api.colors_delete import ColorDeleteEndpoint
from ledfx.api.device import DeviceEndpoint
from ledfx.api.find_lifx import FindLifxEndpoint
from ledfx.api.find_openrgb import FindOpenRGBDevicesEndpoint
from ledfx.api.get_gif_frames import GetGifFramesEndpoint
from ledfx.api.integration_qlc import QLCEndpoint
from ledfx.api.integration_spotify import QLCEndpoint as SpotifyEndpoint
from ledfx.api.integrations import IntegrationsEndpoint
from ledfx.api.power import MAX_POWER_TIMEOUT
from ledfx.api.power import InfoEndpoint as PowerEndpoint
from ledfx.api.preset_delete import PresetDeleteEndpoint
from ledfx.api.presets import PresetsEndpoint
from ledfx.api.scenes import MAX_SCENE_DELAY, ScenesEndpoint
from ledfx.api.scenes_id import SceneEndpoint as ScenesIdEndpoint
from ledfx.api.virtual_tools import VirtualToolsEndpoint
from ledfx.api.virtuals_tools import VirtualsToolsEndpoint
from ledfx.color import (
    LEDFX_COLORS,
    LEDFX_GRADIENTS,
    parse_color,
    parse_gradient,
    validate_color,
    validate_gradient,
)
from ledfx.integrations.spotify import Spotify
from ledfx.presets import ledfx_presets
from ledfx.scenes import Scenes
from ledfx.utils import UserDefaultCollection
from ledfx.virtuals import Virtuals
from tests.test_api_validation_responses import _call, _reason, _request
from tests.test_utilities.fake_ledfx import fake_ledfx


async def test_unknown_device_is_named_in_the_reason() -> None:
    ledfx = fake_ledfx()
    ledfx.devices.get.return_value = None
    status, body = await _call(DeviceEndpoint(ledfx), "GET", device_id="nope")
    assert status == 200
    assert body["status"] == "failed"
    assert _reason(body) == "Device nope was not found"


PRESET_CALLS: list[
    tuple[type[RestEndpoint], str, dict[str, str] | None, dict[str, str]]
] = [
    (PresetsEndpoint, "GET", None, {}),
    (
        PresetsEndpoint,
        "PUT",
        {"preset_id": "p", "category": "user_presets", "name": "n"},
        {},
    ),
    (PresetsEndpoint, "DELETE", {"preset_id": "p", "category": "user_presets"}, {}),
    (PresetDeleteEndpoint, "DELETE", {}, {"preset_id": "p"}),
]


@pytest.mark.parametrize(("endpoint", "method", "body", "extra"), PRESET_CALLS)
async def test_unknown_effect_type_is_an_invalid_request(
    endpoint: type[RestEndpoint],
    method: str,
    body: dict[str, str],
    extra: dict[str, str],
) -> None:
    ledfx = fake_ledfx()
    ledfx.effects.get_class.side_effect = KeyError("nope")
    status, reply = await _call(
        endpoint(ledfx), method, body, effect_id="nope", **extra
    )
    assert status == 200
    assert _reason(reply) == "Effect nope does not exist"


@pytest.mark.parametrize(("endpoint", "method", "body", "extra"), PRESET_CALLS)
async def test_preset_lookup_does_not_swallow_cancellation(
    endpoint: type[RestEndpoint],
    method: str,
    body: dict[str, str],
    extra: dict[str, str],
) -> None:
    ledfx = fake_ledfx()
    ledfx.effects.get_class.side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await _call(endpoint(ledfx), method, body, effect_id="e", **extra)


@pytest.mark.parametrize(
    ("method", "body"),
    [
        ("PUT", {"category": "ledfx_presets", "name": "renamed"}),
        ("DELETE", {"category": "ledfx_presets"}),
    ],
)
async def test_built_in_presets_are_read_only(
    method: str, body: dict[str, str]
) -> None:
    ledfx = fake_ledfx()
    effect_id = next(iter(ledfx_presets))
    preset_id = next(iter(ledfx_presets[effect_id]))
    before = copy.deepcopy(ledfx_presets[effect_id])
    try:
        status, reply = await _call(
            PresetsEndpoint(ledfx),
            method,
            {**body, "preset_id": preset_id},
            effect_id=effect_id,
        )
        assert status == 200
        assert reply["status"] == "failed"
        assert _reason(reply) == "Built-in LedFx presets are read-only"
        assert ledfx_presets[effect_id] == before
        ledfx.config_store.request_save.assert_not_called()
    finally:
        ledfx_presets[effect_id].clear()
        ledfx_presets[effect_id].update(before)


def _with_colors() -> MagicMock:
    ledfx = fake_ledfx({"user_colors": {"mine": "#010203"}})
    ledfx.colors = UserDefaultCollection(
        ledfx,
        "Colors",
        LEDFX_COLORS,
        ledfx.config.user_colors,
        validate_color,
        parse_color,
    )
    ledfx.gradients = UserDefaultCollection(
        ledfx,
        "Gradients",
        LEDFX_GRADIENTS,
        ledfx.config.user_gradients,
        validate_gradient,
        parse_gradient,
    )
    return ledfx


BUILTIN_COLOR = next(iter(LEDFX_COLORS))


@pytest.mark.parametrize(
    ("name", "reason"),
    [
        (BUILTIN_COLOR, f"Cannot delete built-in color or gradient: {BUILTIN_COLOR}"),
        ("ghost", "Color or gradient ghost not found"),
    ],
)
async def test_colors_list_delete_reports_what_it_could_not_delete(
    name: str, reason: str
) -> None:
    ledfx = _with_colors()
    status, reply = await _call(ColorEndpoint(ledfx), "DELETE", ["mine", name])
    assert status == 200
    assert reply["status"] == "failed"
    assert _reason(reply) == reason
    # Nothing is deleted when any name is refused.
    assert ledfx.config.user_colors == {"mine": "#010203"}


async def test_colors_list_delete_refuses_a_user_entry_shadowing_a_built_in() -> None:
    # Only an old config can hold this; POST refuses built-in names.
    ledfx = _with_colors()
    ledfx.config.user_colors[BUILTIN_COLOR] = "#000000"
    before = dict(ledfx.config.user_colors)
    status, reply = await _call(ColorEndpoint(ledfx), "DELETE", ["mine", BUILTIN_COLOR])
    assert status == 200
    assert reply["status"] == "failed"
    assert _reason(reply) == (
        f"Cannot delete built-in color or gradient: {BUILTIN_COLOR}"
    )
    assert ledfx.config.user_colors == before


async def test_colors_single_delete_of_a_built_in_fails() -> None:
    ledfx = _with_colors()
    status, reply = await _call(
        ColorDeleteEndpoint(ledfx), "DELETE", {}, color_id=BUILTIN_COLOR
    )
    assert status == 200
    assert reply["status"] == "failed"
    assert "built-in color" in _reason(reply)
    assert BUILTIN_COLOR in LEDFX_COLORS


async def test_colors_post_of_a_built_in_name_fails() -> None:
    ledfx = _with_colors()
    status, reply = await _call(
        ColorEndpoint(ledfx), "POST", {"new": "#ffffff", BUILTIN_COLOR: "#000000"}
    )
    assert status == 200
    assert _reason(reply) == f"Cannot overwrite built-in color: {BUILTIN_COLOR}"
    assert "new" not in ledfx.config.user_colors


async def test_colors_post_of_an_invalid_value_is_an_invalid_request() -> None:
    ledfx = _with_colors()
    status, reply = await _call(ColorEndpoint(ledfx), "POST", {"bad": "not-a-color"})
    assert status == 200
    assert _reason(reply) == "bad is not a valid color or gradient"
    assert "bad" not in ledfx.config.user_gradients


def test_user_default_collection_refuses_to_touch_built_ins() -> None:
    colors = _with_colors().colors
    with pytest.raises(ValueError, match="built-in color"):
        colors[BUILTIN_COLOR] = "#000000"
    with pytest.raises(ValueError, match="built-in color"):
        del colors[BUILTIN_COLOR]
    with pytest.raises(KeyError):
        del colors["ghost"]


@pytest.fixture(autouse=True)
def _restore_virtuals_singleton(monkeypatch: pytest.MonkeyPatch) -> None:
    # _tool_virtual replaces the singleton; this restores it at teardown.
    monkeypatch.setattr(Virtuals, "_instance", Virtuals._instance)


def _tool_virtual() -> tuple[MagicMock, MagicMock]:
    """A fake core whose real Virtuals manager holds one MagicMock virtual, "v1"."""
    ledfx = fake_ledfx()
    virtual = MagicMock(id="v1")
    virtual.add_oneshot.return_value = True
    Virtuals._instance = None
    ledfx.virtuals = Virtuals(ledfx)
    ledfx.virtuals._virtuals["v1"] = virtual
    return ledfx, virtual


async def _tools_post(body: object, one_virtual: bool):
    ledfx, virtual = _tool_virtual()
    if one_virtual:
        reply = await _call(VirtualsToolsEndpoint(ledfx), "POST", body, virtual_id="v1")
    else:
        reply = await _call(VirtualToolsEndpoint(ledfx), "POST", body)
    return *reply, virtual


@pytest.mark.parametrize("one_virtual", [True, False])
@pytest.mark.parametrize("tool", ["force_color", "calibration", "highlight", "copy"])
async def test_tools_post_refuses_tools_it_does_not_run(
    tool: str, one_virtual: bool
) -> None:
    body = {"tool": tool, "color": "red"}
    status, reply, virtual = await _tools_post(body, one_virtual)
    assert status == 200
    assert reply["status"] == "failed"
    assert virtual.method_calls == []


@pytest.mark.parametrize("one_virtual", [True, False])
@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("brightness", "x"),
        ("ramp", "slow"),
        ("hold", -1),
        ("fade", None),
        ("fade", "inf"),
        ("hold", "nan"),
        ("color", "notacolor"),
        ("color", "#1000000"),
    ],
)
async def test_tools_oneshot_rejects_bad_values(
    field: str, value: object, one_virtual: bool
) -> None:
    body = {"tool": "oneshot", field: value}
    status, reply, virtual = await _tools_post(body, one_virtual)
    assert status == 400
    assert [e["loc"] for e in reply["errors"]] == [[field]]
    virtual.add_oneshot.assert_not_called()


@pytest.mark.parametrize("one_virtual", [True, False])
async def test_tools_oneshot_still_clamps_brightness(one_virtual: bool) -> None:
    body = {"tool": "oneshot", "color": "#ffffff", "ramp": 10, "brightness": 5}
    status, reply, virtual = await _tools_post(body, one_virtual)
    assert (status, reply) == (200, {"status": "success", "tool": "oneshot"})
    (flash,), _ = virtual.add_oneshot.call_args
    assert list(flash._color) == [255.0, 255.0, 255.0]


@pytest.mark.parametrize("one_virtual", [True, False])
@pytest.mark.parametrize(
    ("color", "reason"),
    [("notacolor", "Invalid color: notacolor"), ("#1000000", "Invalid color: 1000000")],
)
async def test_tools_force_color_with_a_bad_color_is_an_invalid_request(
    one_virtual: bool, color: str, reason: str
) -> None:
    ledfx, virtual = _tool_virtual()
    body = {"tool": "force_color", "color": color}
    if one_virtual:
        status, reply = await _call(
            VirtualsToolsEndpoint(ledfx), "PUT", body, virtual_id="v1"
        )
    else:
        virtual.is_device = virtual.id = "v1"
        status, reply = await _call(VirtualToolsEndpoint(ledfx), "PUT", body)
    assert status == 200
    assert _reason(reply) == reason
    virtual.force_frame.assert_not_called()


@pytest.mark.parametrize("timeout", ["5", True, -1, 1.5, MAX_POWER_TIMEOUT + 1])
async def test_power_rejects_a_bad_timeout(timeout: object) -> None:
    ledfx = fake_ledfx()
    status, reply = await _call(
        PowerEndpoint(ledfx), "POST", {"action": "restart", "timeout": timeout}
    )
    assert status == 200
    assert _reason(reply) == (
        f"Timeout must be a whole number of seconds from 0 to {MAX_POWER_TIMEOUT}"
    )
    ledfx.loop.call_later.assert_not_called()
    ledfx.stop.assert_not_called()


async def test_power_answers_at_once_and_stops_later() -> None:
    ledfx = fake_ledfx()
    status, reply = await asyncio.wait_for(
        _call(PowerEndpoint(ledfx), "POST", {"action": "restart", "timeout": 5}),
        timeout=1,
    )
    assert (status, reply) == (200, {"status": "success"})
    ledfx.loop.call_later.assert_called_once_with(5, ledfx.stop, 4)
    ledfx.stop.assert_not_called()


def _with_scene() -> MagicMock:
    ledfx = fake_ledfx({"scenes": {"s1": {"name": "S1"}}})
    ledfx.scenes = Scenes(ledfx)
    return ledfx


async def _activate_in(ledfx: MagicMock, delay: object):
    body = {"id": "s1", "action": "activate_in", "ms": delay}
    return await _call(ScenesEndpoint(ledfx), "PUT", body)


@pytest.mark.parametrize("delay", ["soon", True, -1, MAX_SCENE_DELAY + 1])
async def test_scene_delay_must_be_seconds_within_the_cap(delay: object) -> None:
    ledfx = _with_scene()
    status, reply = await _activate_in(ledfx, delay)
    assert status == 200
    assert _reason(reply) == (
        f'"ms" must be a number of seconds from 0 to {MAX_SCENE_DELAY}'
    )
    ledfx.loop.call_later.assert_not_called()


@pytest.mark.parametrize(
    ("method", "body", "extra", "endpoint"),
    [
        ("PUT", {"id": "s1", "action": "deactivate"}, {}, ScenesEndpoint),
        ("PUT", {"id": "s1", "action": "activate"}, {}, ScenesEndpoint),
        ("PUT", {"id": "s1", "action": "activate_in", "ms": 9}, {}, ScenesEndpoint),
        ("DELETE", {"id": "s1"}, {}, ScenesEndpoint),
        ("DELETE", {}, {"scene_id": "s1"}, ScenesIdEndpoint),
    ],
)
async def test_a_pending_scene_activation_can_be_cancelled(
    method: str,
    body: dict[str, object],
    extra: dict[str, str],
    endpoint: type[RestEndpoint],
) -> None:
    ledfx = _with_scene()
    status, reply = await _activate_in(ledfx, 5)
    assert (status, _reason(reply)) == (200, "Scene S1 will activate in 5s")
    (delay, *_), _ = ledfx.loop.call_later.call_args
    assert delay == 5
    pending = ledfx.loop.call_later.return_value

    status, reply = await _call(endpoint(ledfx), method, body, **extra)

    assert reply["status"] == "success"
    pending.cancel.assert_called_once_with()


async def test_a_pending_scene_activation_runs_once() -> None:
    ledfx = _with_scene()
    ledfx.loop = asyncio.get_running_loop()
    ledfx.scenes.activate = MagicMock(return_value=True)
    await _activate_in(ledfx, 0)
    await asyncio.sleep(0.01)
    ledfx.scenes.activate.assert_called_once_with("s1")
    assert not ledfx.scenes._pending


async def _find_lifx(ledfx: MagicMock, query: dict[str, str]):
    request = _request("GET")
    request.has_body = False
    request.query = query
    request.match_info = dict[str, str]()
    response = await asyncio.wait_for(FindLifxEndpoint(ledfx).handler(request), 2)
    return response.status, json.loads(response.text or "")


async def test_find_lifx_both_runs_mdns_and_udp_together() -> None:
    udp_started = asyncio.Event()

    async def mdns(*_):
        await udp_started.wait()  # would never finish if udp ran after it
        return [{"serial": "m"}]

    async def udp(*_):
        udp_started.set()
        return [{"serial": "u"}]

    with (
        patch.object(FindLifxEndpoint, "_discover_mdns", side_effect=mdns),
        patch.object(FindLifxEndpoint, "_discover_udp", side_effect=udp),
    ):
        status, reply = await _find_lifx(
            fake_ledfx(), {"method": "both", "discovery_timeout": "1"}
        )
    assert status == 200
    assert reply == {"method": "both", "devices": [{"serial": "m"}, {"serial": "u"}]}


async def test_find_lifx_caps_the_total_time() -> None:
    mdns_cancelled = asyncio.Event()

    async def mdns(*_):
        try:
            await asyncio.Event().wait()
        finally:
            mdns_cancelled.set()

    async def udp(*_):
        return [{"serial": "u"}]

    with (
        patch.object(FindLifxEndpoint, "_discover_mdns", side_effect=mdns),
        patch.object(FindLifxEndpoint, "_discover_udp", side_effect=udp),
        patch("ledfx.api.find_lifx.DISCOVERY_GRACE", 0),
    ):
        status, reply = await _find_lifx(
            fake_ledfx(), {"method": "both", "discovery_timeout": "0.05"}
        )
    assert status == 200
    assert reply["devices"] == [{"serial": "u"}]
    assert mdns_cancelled.is_set()


async def test_find_lifx_keeps_other_scan_results_when_one_fails() -> None:
    async def mdns(*_):
        raise RuntimeError("add_new_device blew up")

    async def udp(*_):
        return [{"serial": "u"}]

    with (
        patch.object(FindLifxEndpoint, "_discover_mdns", side_effect=mdns),
        patch.object(FindLifxEndpoint, "_discover_udp", side_effect=udp),
    ):
        status, reply = await _find_lifx(
            fake_ledfx(), {"method": "both", "discovery_timeout": "1"}
        )
    assert status == 200
    assert reply["devices"] == [{"serial": "u"}]


@pytest.mark.parametrize("step", ["get_label", "add_new_device"])
async def test_find_lifx_closes_a_device_when_its_scan_is_cancelled(step: str) -> None:
    ledfx = fake_ledfx()
    device = MagicMock(serial="d073d5000001", ip="10.0.0.9")
    device.get_label = AsyncMock(return_value="Lamp")
    device.close = AsyncMock()
    ledfx.devices.add_new_device = AsyncMock()
    getattr(
        device if step == "get_label" else ledfx.devices, step
    ).side_effect = asyncio.CancelledError
    with pytest.raises(asyncio.CancelledError):
        await FindLifxEndpoint(ledfx)._process_discovered_device(device, True, set())
    device.close.assert_awaited_once()


# Blocking network calls must run off the event loop thread.


def _record_thread(result: object) -> tuple[MagicMock, list[int]]:
    threads: list[int] = []

    def blocking(*_args, **_kwargs):
        threads.append(threading.get_ident())
        return result

    return MagicMock(side_effect=blocking), threads


_URL = "https://example.com/a.gif"


@pytest.mark.parametrize(
    ("target", "result", "endpoint", "method", "body", "reason"),
    [
        (
            "ledfx.api.get_gif_frames.open_gif",
            None,
            GetGifFramesEndpoint,
            "POST",
            {"path_url": _URL},
            f"Failed to open GIF image from: {_URL}",
        ),
        (
            "ledfx.api.assets_download.open_image",
            None,
            AssetsDownloadEndpoint,
            "POST",
            {"path": _URL},
            f"Failed to download or validate URL: {_URL}",
        ),
        (
            "ledfx.utils.open_image",
            None,
            AssetsThumbnailEndpoint,
            "POST",
            {"path": _URL, "force_refresh": True},
            f"Failed to download or validate URL: {_URL}",
        ),
        (
            "ledfx.api.cache_images_refresh.open_image",
            None,
            CacheRefreshEndpoint,
            "POST",
            {"url": _URL},
            f"Failed to refresh URL: {_URL}. Image could not be downloaded.",
        ),
        (
            "ledfx.api.check_for_updates.UpdateChecker.get_release_information",
            False,
            CheckLedFxUpdatesEndPoint,
            "GET",
            None,
            "Unable to check for updates",
        ),
    ],
)
async def test_blocking_calls_run_off_the_loop(
    target: str,
    result: object,
    endpoint: type[RestEndpoint],
    method: str,
    body: dict[str, object] | None,
    reason: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("IS_RELEASE", "true")
    blocking, threads = _record_thread(result)
    with (
        patch(target, blocking),
        patch("ledfx.api.cache_images_refresh.get_image_cache"),
    ):
        _, reply = await _call(endpoint(fake_ledfx()), method, body)
    assert _reason(reply) == reason
    assert threads and threading.get_ident() not in threads


@pytest.mark.parametrize("method", ["GET", "POST"])
async def test_openrgb_connects_off_the_loop(method: str) -> None:
    device = MagicMock(id=0, type=1, leds=[1, 2])
    device.name = "strip"
    client = MagicMock(devices=[device])
    connect, threads = _record_thread(client)
    with patch("ledfx.api.find_openrgb.OpenRGBClient", connect):
        status, reply = await _call(
            FindOpenRGBDevicesEndpoint(fake_ledfx()), method, {}
        )
    assert (status, reply) == (
        200,
        {
            "status": "success",
            "devices": [{"name": "strip", "type": 1, "id": 0, "leds": 2}],
        },
    )
    assert threads and threading.get_ident() not in threads


async def test_openrgb_disconnects_after_listing() -> None:
    client = MagicMock(devices=[])
    with patch("ledfx.api.find_openrgb.OpenRGBClient", return_value=client):
        await _call(FindOpenRGBDevicesEndpoint(fake_ledfx()), "GET")
    client.disconnect.assert_called_once_with()


def _spotify() -> tuple[MagicMock, Spotify]:
    ledfx = fake_ledfx(
        {
            "scenes": {"s1": {"name": "S1"}, "s2": {"name": "S2"}},
            "integrations": [{"id": "sp", "type": "spotify", "data": {}}],
        }
    )
    spotify = Spotify(ledfx, {"name": "Spotify"}, False, {})
    vars(spotify).update(_id="sp", _type="spotify")  # set by the registry
    ledfx.integrations.get.return_value = spotify
    spotify.add_trigger("s1", "abc", "Song", 1000)
    return ledfx, spotify


async def test_spotify_put_moves_a_trigger_to_another_scene() -> None:
    ledfx, spotify = _spotify()
    # What the frontend's edit-trigger sends (storeIntegrationsSpotify.tsx).
    body = {
        "scene_id": "s2",
        "song_id": "abc",
        "song_name": "Song",
        "song_position": 1000,
    }
    status, reply = await _call(
        SpotifyEndpoint(ledfx), "PUT", body, integration_id="sp"
    )
    assert (status, reply) == (200, {"status": "success"})
    assert spotify.triggers == {"s1": {}, "s2": {"abc-1000": ["abc", "Song", 1000]}}
    assert ledfx.config.integrations[0].data == spotify.triggers
    ledfx.config_store.request_save.assert_called_once_with()


@pytest.mark.parametrize(
    ("body", "reason"),
    [
        (
            {"scene_id": "s2", "song_id": "abc", "song_name": "S", "song_position": 5},
            "Trigger abc-5 does not exist",
        ),
        (
            {
                "scene_id": "nope",
                "song_id": "abc",
                "song_name": "S",
                "song_position": 1000,
            },
            "Scene nope does not exist",
        ),
        (
            {"enabled": False},
            "Required attributes scene_id, song_id, song_name, song_position were not provided",
        ),
    ],
)
async def test_spotify_put_refuses_what_it_cannot_do(
    body: dict[str, object], reason: str
) -> None:
    ledfx, spotify = _spotify()
    status, reply = await _call(
        SpotifyEndpoint(ledfx), "PUT", body, integration_id="sp"
    )
    assert (status, _reason(reply)) == (200, reason)
    assert spotify.triggers == {"s1": {"abc-1000": ["abc", "Song", 1000]}}
    ledfx.config_store.request_save.assert_not_called()


async def test_spotify_post_refuses_a_trigger_another_scene_owns() -> None:
    ledfx, spotify = _spotify()
    body = {"scene_id": "s2", "song_id": "abc", "song_name": "S", "song_position": 1000}
    status, reply = await _call(
        SpotifyEndpoint(ledfx), "POST", body, integration_id="sp"
    )
    assert (status, _reason(reply)) == (
        200,
        "Trigger abc-1000 already belongs to scene s1; use PUT to move it",
    )
    assert spotify.triggers == {"s1": {"abc-1000": ["abc", "Song", 1000]}}
    ledfx.config_store.request_save.assert_not_called()


@pytest.mark.parametrize(
    ("endpoint", "kind"), [(SpotifyEndpoint, "spotify"), (QLCEndpoint, "qlc")]
)
@pytest.mark.parametrize("method", ["GET", "PUT", "POST", "DELETE"])
async def test_unknown_integration_is_named_in_the_reason(
    endpoint: type[RestEndpoint], kind: str, method: str
) -> None:
    ledfx = fake_ledfx()
    ledfx.integrations.get.return_value = None
    status, reply = await _call(endpoint(ledfx), method, {}, integration_id="nope")
    assert (status, _reason(reply)) == (
        200,
        f"nope was not found or was not type {kind}",
    )


@pytest.mark.parametrize("was_active", [True, False])
async def test_integration_update_keeps_it_as_active_as_it_was(
    was_active: bool,
) -> None:
    ledfx = fake_ledfx(
        {"integrations": [{"id": "sp", "type": "spotify", "active": was_active}]}
    )
    ledfx.integrations.get_class.return_value = Spotify
    old = MagicMock(type="spotify", active=was_active, deactivate=AsyncMock())
    ledfx.integrations.get.return_value = old
    new = ledfx.integrations.create.return_value
    new.activate = AsyncMock()
    body = {"id": "sp", "type": "spotify", "config": {"name": "Renamed"}}

    _, reply = await _call(IntegrationsEndpoint(ledfx), "POST", body)

    assert reply == {"status": "success"}
    assert old.deactivate.await_count == new.activate.await_count == int(was_active)
    assert ledfx.config.integrations[0].active is was_active
