"""/api/v2 bulk actions and virtual tools over a real Virtuals manager,
and the /virtuals/oneshot route precedence."""

from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest

from ledfx.configuration.fields import VirtualIdStr
from ledfx.effects import DummyEffect
from ledfx.effects.oneshots.oneshot import Flash
from tests.api_v2.virtuals_client import BIRD, Client, V, core_of, expect_problem
from tests.test_utilities.virtuals_core import (
    add_virtual,
    enter_safe_mode,
    running_core,
)


@pytest.fixture
def v2_ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    for core in running_core(monkeypatch):
        # Shares its depth with the collection-wide /virtuals/oneshot.
        add_virtual(core, "oneshot", "oneshot", [["strip", 20, 29, False]])
        yield core


def _running(client: Client, virtual_id: str) -> str:
    effect = (
        core_of(client).virtuals.get_or_raise(VirtualIdStr(virtual_id)).active_effect
    )
    return "" if effect is None or isinstance(effect, DummyEffect) else effect.type


def _flashes(client: Client, virtual_id: str) -> int:
    virtual = core_of(client).virtuals.get_or_raise(VirtualIdStr(virtual_id))
    return sum(isinstance(o, Flash) and o.active for o in virtual.oneshots)


async def _start(client: Client, virtual_id: str, type_id: str = "rainbow") -> None:
    path = f"{V}/{virtual_id.replace(' ', '%20')}/effect"
    resp = await client.put(path, json={"type": type_id})
    assert resp.status == 200, await resp.text()


async def test_clear_effects(v2_client: Client) -> None:
    await _start(v2_client, "dj bird")
    await _start(v2_client, "matrix")
    resp = await v2_client.post(f"{V}/clear-effects", json={"virtual_ids": ["matrix"]})
    assert resp.status == 204
    assert (_running(v2_client, "dj bird"), _running(v2_client, "matrix")) == (
        "rainbow",
        "",
    )
    assert (await v2_client.post(f"{V}/clear-effects", json={})).status == 204
    assert _running(v2_client, "dj bird") == ""


async def test_unknown_ids_are_named(v2_client: Client) -> None:
    resp = await v2_client.post(
        f"{V}/clear-effects",
        json={"virtual_ids": ["dj bird", "ghost", "spook", "ghost"]},
    )
    body = await expect_problem(resp, 404, "not-found")
    assert body["detail"] == "Virtuals not found: 'ghost', 'spook'"
    resp = await v2_client.post(
        f"{V}/apply-config",
        json={"brightness": 0.5, "virtual_ids": ["ghost", "spook", "ghost"]},
    )
    body = await expect_problem(resp, 404, "not-found")
    assert body["detail"] == "Virtuals not found: 'ghost', 'spook'"


async def test_apply_config(v2_client: Client) -> None:
    await _start(v2_client, "dj bird")
    resp = await v2_client.post(f"{V}/apply-config", json={"brightness": 0.5})
    assert resp.status == 200
    assert await resp.json() == {"updated": 1, "skipped": 0}
    effect = await (await v2_client.get(f"{BIRD}/effect")).json()
    assert effect["config"]["brightness"] == 0.5
    await expect_problem(
        await v2_client.post(f"{V}/apply-config", json={}), 422, "validation"
    )


async def test_set_effect_on_virtuals(v2_client: Client) -> None:
    resp = await v2_client.post(
        f"{V}/set-effect",
        json={
            "type": "rainbow",
            "config": {"speed": 2.0},
            "virtual_ids": ["dj bird", "empty"],
        },
    )
    assert resp.status == 200
    assert await resp.json() == {"applied": 1, "blocked": 0, "failed": 1}
    assert _running(v2_client, "dj bird") == "rainbow"
    resp = await v2_client.post(f"{V}/set-effect", json={"type": "gone"})
    body = await expect_problem(resp, 422, "validation")
    assert body["detail"] == "Unknown effect type: gone"
    # "2" passes the manager's lenient create but not strict validation, so
    # only the route's up-front check refuses it.
    resp = await v2_client.post(
        f"{V}/set-effect",
        json={"type": "rainbow", "config": {"speed": "2"}, "virtual_ids": ["mirror"]},
    )
    body = await expect_problem(resp, 422, "validation")
    assert body["errors"][0]["loc"] == ["body", "config", "speed"]
    assert _running(v2_client, "mirror") == ""


async def test_a_repeated_id_is_applied_once(v2_client: Client) -> None:
    resp = await v2_client.post(
        f"{V}/set-effect", json={"type": "rainbow", "virtual_ids": ["dj bird"] * 5}
    )
    assert await resp.json() == {"applied": 1, "blocked": 0, "failed": 0}


async def test_set_effect_on_an_unknown_virtual_is_a_404(v2_client: Client) -> None:
    resp = await v2_client.post(
        f"{V}/set-effect", json={"type": "rainbow", "virtual_ids": ["dj bird", "ghost"]}
    )
    body = await expect_problem(resp, 404, "not-found")
    assert body["detail"] == "Virtual 'ghost' not found"
    assert _running(v2_client, "dj bird") == ""  # nothing ran before the refusal


async def test_oneshot_on_one_virtual(v2_client: Client) -> None:
    resp = await v2_client.post(
        f"{BIRD}/oneshot", json={"color": "blue", "hold_ms": 500}
    )
    body = await expect_problem(resp, 409, "conflict")
    assert body["detail"] == "Virtual dj bird is not active"
    await _start(v2_client, "dj bird")
    assert (await v2_client.post(f"{BIRD}/oneshot", json={})).status == 204
    assert _flashes(v2_client, "dj bird") == 1
    assert (await v2_client.delete(f"{BIRD}/oneshot")).status == 204
    assert _flashes(v2_client, "dj bird") == 0
    await expect_problem(
        await v2_client.post(f"{V}/nope/oneshot", json={}), 404, "not-found"
    )
    resp = await v2_client.post(f"{BIRD}/oneshot", json={"ramp_ms": 60001})
    body = await expect_problem(resp, 422, "validation")
    assert body["errors"][0]["loc"] == ["body", "ramp_ms"]


async def test_oneshot_on_every_virtual(v2_client: Client) -> None:
    await _start(v2_client, "dj bird")
    assert (await v2_client.post(f"{V}/oneshot", json={"color": "red"})).status == 204
    assert _flashes(v2_client, "dj bird") == 1
    assert (await v2_client.delete(f"{V}/oneshot")).status == 204
    assert _flashes(v2_client, "dj bird") == 0


async def test_the_fixed_oneshot_path_wins_only_where_it_has_the_method(
    v2_client: Client,
) -> None:
    """GET and PATCH /virtuals/oneshot reach the virtual "oneshot"; DELETE
    is the collection-wide action and leaves it in place."""
    resp = await v2_client.get(f"{V}/oneshot")
    assert (resp.status, (await resp.json())["id"]) == (200, "oneshot")
    resp = await v2_client.patch(f"{V}/oneshot", json={"config": {"name": "One"}})
    assert (resp.status, (await resp.json())["name"]) == (200, "One")
    assert (await v2_client.delete(f"{V}/oneshot")).status == 204
    assert (await v2_client.get(f"{V}/oneshot")).status == 200


@pytest.mark.parametrize("name", ["oneshot", "Force Color"])
async def test_a_name_giving_a_reserved_id_is_refused(
    v2_client: Client, name: str
) -> None:
    resp = await v2_client.post(V, json={"config": {"name": name}})
    body = await expect_problem(resp, 422, "validation")
    assert body["errors"][0]["loc"] == ["body", "config", "name"]


async def test_force_color(v2_client: Client) -> None:
    await _start(v2_client, "dj bird")
    assert (
        await v2_client.post(f"{BIRD}/force-color", json={"color": "red"})
    ).status == 204
    frame = (
        core_of(v2_client)
        .virtuals.get_or_raise(VirtualIdStr("dj bird"))
        .assembled_frame
    )
    assert frame[0].tolist() == [255.0, 0.0, 0.0]
    assert (
        await v2_client.post(f"{V}/force-color", json={"color": "blue"})
    ).status == 204
    virtuals = core_of(v2_client).virtuals
    matrix = virtuals.get_or_raise(VirtualIdStr("matrix")).assembled_frame
    assert matrix[0].tolist() == [0.0, 0.0, 255.0]
    # Only a device's own virtual is filled; dj bird keeps its red.
    bird = virtuals.get_or_raise(VirtualIdStr("dj bird")).assembled_frame
    assert bird[0].tolist() == [255.0, 0.0, 0.0]
    resp = await v2_client.post(f"{BIRD}/force-color", json={"color": "notacolor"})
    body = await expect_problem(resp, 422, "validation")
    assert body["errors"][0]["loc"] == ["body", "color"]


async def test_calibration_and_highlight(v2_client: Client) -> None:
    highlight = {"device_id": "strip", "start": 0, "end": 9}
    bird = core_of(v2_client).virtuals.get_or_raise(VirtualIdStr("dj bird"))
    body = await expect_problem(
        await v2_client.put(f"{BIRD}/highlight", json=highlight), 409, "conflict"
    )
    assert "not in calibration mode" in str(body["detail"])
    assert (
        await v2_client.put(f"{BIRD}/calibration", json={"enabled": True})
    ).status == 204
    assert (await v2_client.put(f"{BIRD}/highlight", json=highlight)).status == 204
    resp = await v2_client.put(
        f"{BIRD}/highlight", json={**highlight, "device_id": "ghost"}
    )
    body = await expect_problem(resp, 422, "validation")
    assert body["detail"] == "Device ghost not found"
    assert body["errors"][0]["loc"] == ["body", "device_id"]
    resp = await v2_client.put(f"{BIRD}/highlight", json={**highlight, "end": 99})
    body = await expect_problem(resp, 422, "validation")
    assert body["detail"] == "start and end must be less than 50"
    assert body["errors"][0]["loc"] == ["body", "end"]
    assert (await v2_client.delete(f"{BIRD}/highlight")).status == 204
    assert not bird._hl_state
    # A refused PUT changes nothing: the cleared highlight stays off.
    resp = await v2_client.put(
        f"{BIRD}/highlight", json={**highlight, "device_id": "ghost"}
    )
    await expect_problem(resp, 422, "validation")
    assert not bird._hl_state
    # DELETE is idempotent, and turning calibration off forgets the highlight.
    assert (await v2_client.put(f"{BIRD}/highlight", json=highlight)).status == 204
    assert bird._hl_state
    assert (
        await v2_client.put(f"{BIRD}/calibration", json={"enabled": False})
    ).status == 204
    assert not bird._hl_state
    assert (await v2_client.delete(f"{BIRD}/highlight")).status == 204
    assert (
        await v2_client.put(f"{BIRD}/calibration", json={"enabled": True})
    ).status == 204
    assert not bird._hl_state


async def test_copy_effect(v2_client: Client) -> None:
    resp = await v2_client.post(f"{BIRD}/copy-effect", json={"targets": ["mirror"]})
    await expect_problem(resp, 409, "conflict")
    await _start(v2_client, "dj bird")
    resp = await v2_client.post(f"{BIRD}/copy-effect", json={"targets": ["mirror"]})
    assert resp.status == 204
    assert _running(v2_client, "mirror") == "rainbow"
    # An unknown target is a 404 and nothing is copied, even to the known ones.
    resp = await v2_client.post(
        f"{BIRD}/copy-effect", json={"targets": ["matrix", "ghost"]}
    )
    await expect_problem(resp, 404, "not-found")
    assert _running(v2_client, "matrix") == ""
    # A target that refuses is a state conflict; one that takes it is enough.
    resp = await v2_client.post(f"{BIRD}/copy-effect", json={"targets": ["empty"]})
    body = await expect_problem(resp, 409, "conflict")
    assert "errors" not in body
    resp = await v2_client.post(
        f"{BIRD}/copy-effect", json={"targets": ["empty", "mirror"]}
    )
    assert resp.status == 204


async def test_safe_mode(v2_client: Client) -> None:
    """Saved changes are refused; runtime tools still work."""
    await _start(v2_client, "dj bird")
    core = core_of(v2_client)
    enter_safe_mode(core)
    before = core.config.model_dump()
    saved: list[tuple[str, dict[str, object]]] = [
        (f"{V}/apply-config", {"brightness": 0.5}),
        (f"{V}/set-effect", {"type": "singleColor"}),
        (f"{BIRD}/copy-effect", {"targets": ["mirror"]}),
    ]
    for path, body in saved:
        await expect_problem(await v2_client.post(path, json=body), 409, "safe-mode")
    assert core.config.model_dump() == before
    runtime: list[tuple[str, str, dict[str, object] | None]] = [
        ("POST", f"{BIRD}/oneshot", {}),
        ("DELETE", f"{V}/oneshot", None),
        ("POST", f"{V}/force-color", {"color": "red"}),
        ("PUT", f"{BIRD}/calibration", {"enabled": True}),
        ("DELETE", f"{BIRD}/highlight", None),
        ("POST", f"{V}/clear-effects", {}),
    ]
    for method, path, body in runtime:
        resp = await v2_client.request(method, path, json=body)
        assert resp.status == 204, (method, path, await resp.text())
    assert core.config.model_dump() == before
