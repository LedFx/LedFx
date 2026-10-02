"""/api/v2/virtuals over a real Virtuals manager: strict input, safe mode,
ids and rollback."""

from collections.abc import Iterator
from unittest.mock import MagicMock
from urllib.parse import quote

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ledfx.api.virtuals import VirtualsEndpoint
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import Scene, replace_model
from ledfx.virtuals import Virtual
from tests.api_v2.virtuals_client import BIRD, Client, V, core_of, expect_problem
from tests.test_utilities.virtuals_core import enter_safe_mode, running_core
from tests.v1_golden.harness import build_app


@pytest.fixture
def v2_ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


async def test_list_virtuals(v2_client: Client) -> None:
    resp = await v2_client.get(V)
    assert resp.status == 200
    body = await resp.json()
    assert [v["id"] for v in body] == ["dj bird", "mirror", "empty", "matrix"]
    assert body[0]["segments"] == [
        {"device_id": "strip", "start": 0, "end": 49, "invert": False}
    ]
    assert body[3]["is_device"] == "matrix"


async def test_create_makes_an_id_from_the_name(v2_client: Client) -> None:
    """A non-ASCII name, and a Location the client can follow."""
    resp = await v2_client.post(V, json={"config": {"name": "Küche"}})
    assert resp.status == 201
    body = await resp.json()
    assert body["id"] == "k-che"
    assert body["name"] == "Küche"
    assert resp.headers["Location"] == f"{V}/{quote(body['id'], safe='')}"
    followed = await v2_client.get(resp.headers["Location"])
    assert (await followed.json())["id"] == "k-che"
    again = await v2_client.post(V, json={"config": {"name": "Küche"}})
    assert (await again.json())["id"] == "k-che-1"
    core = core_of(v2_client)
    assert [e.id for e in core.config.virtuals][-2:] == ["k-che", "k-che-1"]
    core.config_store.request_save.assert_called()


async def test_an_id_with_a_space_is_one_path_segment(v2_client: Client) -> None:
    resp = await v2_client.get(BIRD)
    assert resp.status == 200
    assert (await resp.json())["id"] == "dj bird"


async def test_v1_and_v2_make_the_same_id(v2_client: Client) -> None:
    """One name gives one id, whichever API creates it."""
    core = core_of(v2_client)
    async with TestClient(TestServer(build_app(core, (VirtualsEndpoint,)))) as v1:
        created = await v1.post("/api/virtuals", json={"config": {"name": "Küche"}})
        v1_id = (await created.json())["virtual"]["id"]
    assert (await v2_client.delete(f"{V}/{quote(v1_id, safe='')}")).status == 204
    resp = await v2_client.post(V, json={"config": {"name": "Küche"}})
    assert v1_id == (await resp.json())["id"] == "k-che"


async def test_an_unknown_id_is_a_404_problem(v2_client: Client) -> None:
    for method in ("GET", "PATCH", "DELETE"):
        resp = await v2_client.request(method, f"{V}/nope", json={})
        body = await expect_problem(resp, 404, "not-found")
        assert body["detail"] == "Virtual 'nope' not found"


async def test_create_refuses_unknown_and_bad_fields(v2_client: Client) -> None:
    resp = await v2_client.post(V, json={"config": {"name": "A"}, "id": "a"})
    body = await expect_problem(resp, 422, "validation")
    assert body["errors"][0]["loc"] == ["body", "id"]
    resp = await v2_client.post(V, json={"config": {"name": "A", "rows": "2"}})
    body = await expect_problem(resp, 422, "validation")
    assert body["errors"][0]["loc"] == ["body", "config", "rows"]


async def test_patch_changes_only_what_is_sent(v2_client: Client) -> None:
    resp = await v2_client.patch(BIRD, json={"config": {"max_brightness": 0.5}})
    assert resp.status == 200
    body = await resp.json()
    assert body["config"]["max_brightness"] == 0.5
    assert body["config"]["name"] == "dj bird"
    entry = core_of(v2_client).virtuals.get_or_raise(VirtualIdStr("dj bird")).entry
    assert entry.config.max_brightness == 0.5


async def test_patch_segments_and_active(v2_client: Client) -> None:
    segments = [{"device_id": "strip", "start": 0, "end": 24, "invert": True}]
    resp = await v2_client.patch(BIRD, json={"segments": segments, "active": False})
    assert resp.status == 200
    body = await resp.json()
    assert body["segments"] == segments
    assert body["active"] is False


async def test_patch_refuses_an_unknown_device(v2_client: Client) -> None:
    segments = [{"device_id": "ghost", "start": 0, "end": 9}]
    resp = await v2_client.patch(BIRD, json={"segments": segments})
    body = await expect_problem(resp, 422, "validation")
    assert body["errors"][0]["loc"] == ["body", "segments"]


@pytest.mark.parametrize("field", ["pixel_count", "max_brightness"])
async def test_null_for_a_setting_is_422_and_changes_nothing(
    v2_client: Client, field: str
) -> None:
    """pixel_count is not a virtual setting; max_brightness
    is not nullable. Either way the stored config stays as it was."""
    core = core_of(v2_client)
    before = core.config.model_dump()
    resp = await v2_client.patch(BIRD, json={"config": {field: None}})
    body = await expect_problem(resp, 422, "validation")
    assert body["errors"][0]["loc"] == ["body", "config", field]
    assert core.config.model_dump() == before
    core.config_store.request_save.assert_not_called()


async def test_a_bad_stored_setting_is_a_409_until_fixed(v2_client: Client) -> None:
    virtual = core_of(v2_client).virtuals.get_or_raise(VirtualIdStr("dj bird"))
    virtual._config = replace_model(virtual.config, grouping=5000)  # v2 max 4096
    resp = await v2_client.patch(BIRD, json={"config": {"name": "Bird"}})
    body = await expect_problem(resp, 409, "conflict")
    assert "config.grouping" in body["detail"]
    resp = await v2_client.patch(BIRD, json={"config": {"grouping": 2}})
    assert resp.status == 200


async def test_delete(v2_client: Client) -> None:
    resp = await v2_client.delete(f"{V}/mirror")
    assert resp.status == 204
    assert (await v2_client.get(f"{V}/mirror")).status == 404
    assert "mirror" not in [e.id for e in core_of(v2_client).config.virtuals]


async def test_safe_mode_refuses_changes_but_serves_reads(v2_client: Client) -> None:
    core = core_of(v2_client)
    enter_safe_mode(core)
    before = core.config.model_dump()
    for method, path, body in (
        ("POST", V, {"config": {"name": "New"}}),
        ("PATCH", BIRD, {"config": {"name": "Renamed"}}),
        ("DELETE", BIRD, None),
    ):
        resp = await v2_client.request(method, path, json=body)
        problem = await expect_problem(resp, 409, "safe-mode")
        assert "safe mode" in str(problem["detail"])
    assert core.config.model_dump() == before
    assert (await v2_client.get(V)).status == 200
    assert (await v2_client.get(BIRD)).status == 200


MIRROR = f"{V}/mirror"
MIRROR_PATCH = {
    "segments": [{"device_id": "strip", "start": 0, "end": 4, "invert": True}],
    "config": {"max_brightness": 0.5, "mapping": "copy"},
    "active": True,
}


def _snapshot(core: MagicMock) -> tuple[object, ...]:
    virtual = core.virtuals.get_or_raise(VirtualIdStr("mirror"))
    return (
        virtual.config,
        list(virtual.segments),
        virtual.active,
        virtual.entry.model_dump(),
        core.config.model_dump(),
    )


async def test_a_refused_step_undoes_the_whole_patch(v2_client: Client) -> None:
    """A v2 PATCH is all or nothing: a 4xx means nothing changed. mirror has
    no effect to restore, so active: true is refused after the other steps."""
    core = core_of(v2_client)
    before = _snapshot(core)
    resp = await v2_client.patch(MIRROR, json=MIRROR_PATCH)
    body = await expect_problem(resp, 422, "validation")
    assert body["errors"][0]["loc"] == ["body", "active"]
    assert _snapshot(core) == before
    core.config_store.request_save.assert_not_called()


async def test_a_step_that_commits_then_raises_is_undone(
    v2_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """update_config sets the config, then _reactivate_effect can still fail."""

    def boom(self: Virtual, *args: object, **kwargs: object) -> None:
        raise RuntimeError("boom")

    monkeypatch.setattr(Virtual, "_reactivate_effect", boom)
    core = core_of(v2_client)
    before = _snapshot(core)
    resp = await v2_client.patch(MIRROR, json={"config": {"mapping": "copy"}})
    assert resp.status == 500
    assert _snapshot(core) == before
    core.config_store.request_save.assert_not_called()


async def test_a_step_that_fails_once_is_restored(
    v2_client: Client,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only the first _reactivate_effect fails, so the restore itself runs
    and succeeds."""
    calls: list[int] = []
    reactivate = Virtual._reactivate_effect

    def fail_once(self: Virtual) -> None:
        calls.append(1)
        if len(calls) == 1:
            raise RuntimeError("boom")
        reactivate(self)

    monkeypatch.setattr(Virtual, "_reactivate_effect", fail_once)
    core = core_of(v2_client)
    before = _snapshot(core)
    resp = await v2_client.patch(MIRROR, json={"config": {"mapping": "copy"}})
    assert resp.status == 500
    assert len(calls) == 2
    assert "Could not undo" not in caplog.text
    assert _snapshot(core) == before
    core.config_store.request_save.assert_not_called()


async def test_delete_a_devices_virtual_removes_its_device_and_scene_entry(
    v2_client: Client,
) -> None:
    core = core_of(v2_client)
    core.config.scenes["s"] = Scene.model_validate(
        {"name": "S", "virtuals": {"matrix": {}, "mirror": {}}}
    )
    assert (await v2_client.delete(f"{V}/matrix")).status == 204
    assert core.devices.get("matrix") is None
    assert list(core.config.scenes["s"].virtuals) == ["mirror"]


async def test_the_patch_schema_requires_whole_segments(v2_client: Client) -> None:
    spec = await (await v2_client.get("/api/v2/openapi.json")).json()
    patch = spec["paths"]["/api/v2/virtuals/{virtual_id}"]["patch"]
    body = patch["requestBody"]["content"]["application/json"]["schema"]
    schemas = spec["components"]["schemas"]
    while "$ref" in body:
        body = schemas[body["$ref"].rsplit("/", 1)[1]]
    items = body["properties"]["segments"]["items"]
    segment = schemas[items["$ref"].rsplit("/", 1)[1]]
    assert set(segment["required"]) >= {"device_id", "start", "end"}
