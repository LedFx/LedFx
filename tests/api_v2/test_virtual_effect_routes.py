"""/api/v2/virtuals/{virtual_id}/effect(s) over a real Virtuals manager,
including stored effects whose type is no longer registered."""

from collections.abc import Iterator, Mapping
from unittest.mock import MagicMock

import pytest
from pydantic import BaseModel

from ledfx.api.v2.routes import virtual_effect
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import EffectEntry, Segment
from tests.api_v2.virtuals_client import (
    BIRD,
    Client,
    EffectJson,
    V,
    core_of,
    expect_problem,
)
from tests.test_utilities.virtuals_core import (
    add_virtual,
    enter_safe_mode,
    running_core,
)

EFFECT = f"{BIRD}/effect"


@pytest.fixture
def v2_ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    for core in running_core(monkeypatch):
        # A stored effect whose plugin is gone.
        add_virtual(
            core,
            "old",
            "Old",
            [["strip", 10, 19, False]],
            effect={"type": "gone", "config": {"x": 1}},
            effects={"gone": {"type": "gone", "config": {"x": 1}}},
        )
        yield core


async def _put(client: Client, body: dict[str, object]) -> EffectJson:
    resp = await client.put(EFFECT, json=body)
    assert resp.status == 200, await resp.text()
    effect: EffectJson = await resp.json()
    return effect


async def test_no_effect_is_null(v2_client: Client) -> None:
    resp = await v2_client.get(EFFECT)
    assert resp.status == 200
    assert await resp.json() is None


async def test_put_starts_an_effect(v2_client: Client) -> None:
    body = await _put(v2_client, {"type": "rainbow", "config": {"speed": 2.0}})
    assert body["type"] == "rainbow"
    assert body["config"]["speed"] == 2.0
    assert await (await v2_client.get(EFFECT)).json() == body
    entry = core_of(v2_client).virtuals.get_or_raise(VirtualIdStr("dj bird")).entry
    assert entry.effect.type == "rainbow"


async def test_put_without_config_restores_the_stored_one(v2_client: Client) -> None:
    await _put(v2_client, {"type": "rainbow", "config": {"speed": 2.0}})
    await _put(v2_client, {"type": "singleColor"})
    body = await _put(v2_client, {"type": "rainbow"})
    assert body["config"]["speed"] == 2.0


@pytest.mark.parametrize(
    ("config", "field"),
    [({"speed": "fast"}, "speed"), ({"not_a_setting": 1}, "not_a_setting")],
)
async def test_put_checks_the_config_against_the_type(
    v2_client: Client, config: dict[str, object], field: str
) -> None:
    resp = await v2_client.put(EFFECT, json={"type": "rainbow", "config": config})
    body = await expect_problem(resp, 422, "validation")
    assert body["errors"][0]["loc"] == ["body", "config", field]


async def test_put_refusals_are_conflicts(v2_client: Client) -> None:
    resp = await v2_client.put(f"{V}/empty/effect", json={"type": "rainbow"})
    body = await expect_problem(resp, 409, "conflict")
    assert "no configured device segments" in str(body["detail"])
    core = core_of(v2_client)
    core.virtuals.set_segments(
        VirtualIdStr("dj bird"),
        [Segment("strip", 0, 49, False), Segment("matrix", 0, 63, False)],
    )
    await _put(v2_client, {"type": "rainbow"})
    resp = await v2_client.put(
        f"{V}/matrix/effect", json={"type": "singleColor", "fallback_s": 5}
    )
    body = await expect_problem(resp, 409, "conflict")
    assert body["detail"] == "Virtual matrix is being streamed to"


async def test_put_with_a_stale_stored_config_is_a_409(v2_client: Client) -> None:
    core = core_of(v2_client)
    entry = core.virtuals.get_or_raise(VirtualIdStr("dj bird")).entry
    assert entry is not None
    entry.effects["rainbow"] = EffectEntry(type="rainbow", config={"speed": "x"})
    known = len(list(core.effects))
    resp = await v2_client.put(EFFECT, json={"type": "rainbow"})
    body = await expect_problem(resp, 409, "conflict")
    assert body["detail"] == "Stored field 'config.speed' is invalid"
    assert len(list(core.effects)) == known
    # Sending the setting replaces the stale one.
    await _put(v2_client, {"type": "rainbow", "config": {"speed": 2.0}})


async def test_a_streamed_to_refusal_creates_no_effect(
    v2_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    core = core_of(v2_client)
    core.virtuals.set_segments(
        VirtualIdStr("dj bird"),
        [Segment("strip", 0, 49, False), Segment("matrix", 0, 63, False)],
    )
    await _put(v2_client, {"type": "rainbow"})
    known = len(list(core.effects))
    create = MagicMock(wraps=core.effects.create)
    monkeypatch.setattr(core.effects, "create", create)
    resp = await v2_client.put(
        f"{V}/matrix/effect", json={"type": "singleColor", "fallback_s": 5}
    )
    await expect_problem(resp, 409, "conflict")
    create.assert_not_called()
    assert len(list(core.effects)) == known


async def test_patch_changes_the_running_effect(v2_client: Client) -> None:
    started = await _put(v2_client, {"type": "rainbow"})
    resp = await v2_client.patch(EFFECT, json={"config": {"speed": 3.0}})
    assert resp.status == 200
    body = await resp.json()
    assert body["config"] == {**started["config"], "speed": 3.0}


@pytest.mark.parametrize(
    ("config", "field"),
    [
        ({"speed": None}, "speed"),
        ({"color": "#ff0000"}, "color"),  # a singleColor setting, not rainbow's
    ],
)
async def test_patch_checks_against_the_running_type(
    v2_client: Client, config: dict[str, object], field: str
) -> None:
    """PATCH applies to the current type."""
    await _put(v2_client, {"type": "rainbow"})
    core = core_of(v2_client)
    effect = core.virtuals.get_or_raise(VirtualIdStr("dj bird")).active_effect
    assert effect is not None
    stored, saved = effect.config, core.config.model_dump()
    core.config_store.request_save.reset_mock()
    resp = await v2_client.patch(EFFECT, json={"config": config})
    body = await expect_problem(resp, 422, "validation")
    assert body["errors"][0]["loc"] == ["body", "config", field]
    assert effect.config == stored
    assert core.config.model_dump() == saved
    core.config_store.request_save.assert_not_called()


async def test_a_bad_stored_setting_is_a_409_until_fixed(v2_client: Client) -> None:
    await _put(v2_client, {"type": "rainbow"})
    core = core_of(v2_client)
    effect = core.virtuals.get_or_raise(VirtualIdStr("dj bird")).active_effect
    assert effect is not None
    effect._config = effect.config.model_copy(update={"speed": 1e9})
    stored, saved = effect.config, core.config.model_dump()
    core.config_store.request_save.reset_mock()
    resp = await v2_client.patch(EFFECT, json={"config": {"brightness": 0.5}})
    body = await expect_problem(resp, 409, "conflict")
    assert "Stored field 'config.speed' is invalid" in str(body["detail"])
    assert effect.config == stored
    assert core.config.model_dump() == saved
    core.config_store.request_save.assert_not_called()
    resp = await v2_client.patch(EFFECT, json={"config": {"speed": 2.0}})
    assert resp.status == 200


async def test_patch_on_an_effect_swapped_after_the_check_is_a_conflict(
    v2_client: Client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A fallback timer can swap the effect between the check and the change:
    the patch, checked against rainbow, must not reach singleColor."""
    await _put(v2_client, {"type": "rainbow"})
    core = core_of(v2_client)
    check = virtual_effect.checked_config

    def swap_then_check(
        variant: type[BaseModel],
        config: Mapping[str, object],
        sent: Mapping[str, object],
    ) -> dict[str, object]:
        core.virtuals.set_effect(VirtualIdStr("dj bird"), "singleColor", {})
        return check(variant, config, sent)

    monkeypatch.setattr(virtual_effect, "checked_config", swap_then_check)
    resp = await v2_client.patch(EFFECT, json={"config": {"speed": 3.0}})
    body = await expect_problem(resp, 409, "conflict")
    assert body["detail"] == "Virtual dj bird runs singleColor, not rainbow"


async def test_patch_without_an_effect_is_a_conflict(v2_client: Client) -> None:
    resp = await v2_client.patch(EFFECT, json={"config": {"speed": 3.0}})
    body = await expect_problem(resp, 409, "conflict")
    assert body["detail"] == "Virtual dj bird has no active effect"


async def test_put_changes_the_type(v2_client: Client) -> None:
    await _put(v2_client, {"type": "rainbow"})
    body = await _put(v2_client, {"type": "singleColor", "config": {"color": "blue"}})
    assert body["type"] == "singleColor"
    assert body["config"]["color"] == "#0000ff"


async def test_an_unregistered_stored_effect_is_an_unknown_plugin(
    v2_client: Client,
) -> None:
    unknown = {"type": "gone", "config": {"x": 1}, "available": False}
    listed = await (await v2_client.get(V)).json()
    assert [v["effect"] for v in listed if v["id"] == "old"] == [unknown]
    assert await (await v2_client.get(f"{V}/old/effect")).json() == unknown
    history = await (await v2_client.get(f"{V}/old/effects")).json()
    assert history == [unknown]
    resp = await v2_client.put(f"{V}/old/effect", json={"type": "gone"})
    body = await expect_problem(resp, 422, "validation")
    assert body["detail"] == "Unknown effect type: gone"
    assert body["errors"][0]["loc"] == ["body", "type"]


async def test_randomize_and_reset(v2_client: Client) -> None:
    await _put(
        v2_client, {"type": "rainbow", "config": {"brightness": 0.3, "speed": 3.0}}
    )
    resp = await v2_client.post(f"{EFFECT}/randomize")
    assert resp.status == 200
    assert (await resp.json())["config"]["brightness"] == 0.3
    resp = await v2_client.post(f"{EFFECT}/reset")
    assert resp.status == 200
    assert (await resp.json())["config"]["brightness"] == 1.0


async def test_clear_keeps_the_history(v2_client: Client) -> None:
    await _put(v2_client, {"type": "rainbow"})
    assert (await v2_client.delete(EFFECT)).status == 204
    assert await (await v2_client.get(EFFECT)).json() is None
    history = await (await v2_client.get(f"{BIRD}/effects")).json()
    assert [h["type"] for h in history] == ["rainbow"]


async def test_delete_from_the_history(v2_client: Client) -> None:
    await _put(v2_client, {"type": "singleColor"})
    await _put(v2_client, {"type": "rainbow"})
    assert (await v2_client.delete(f"{BIRD}/effects/rainbow")).status == 204
    assert await (await v2_client.get(EFFECT)).json() is None
    history = await (await v2_client.get(f"{BIRD}/effects")).json()
    assert [h["type"] for h in history] == ["singleColor"]
    resp = await v2_client.delete(f"{BIRD}/effects/rainbow")
    body = await expect_problem(resp, 404, "not-found")
    assert body["detail"] == "Effect 'rainbow' not found"


async def test_fallback(v2_client: Client) -> None:
    assert (await v2_client.post(f"{BIRD}/fallback")).status == 204
    await expect_problem(await v2_client.post(f"{V}/nope/fallback"), 404, "not-found")


async def test_safe_mode_refuses_changes_but_serves_reads(v2_client: Client) -> None:
    await _put(v2_client, {"type": "rainbow"})
    core = core_of(v2_client)
    enter_safe_mode(core)
    before = core.config.model_dump()
    for method, path, body in (
        ("PUT", EFFECT, {"type": "singleColor"}),
        ("PATCH", EFFECT, {"config": {"speed": 3.0}}),
        ("DELETE", EFFECT, None),
        ("POST", f"{EFFECT}/randomize", None),
        ("POST", f"{EFFECT}/reset", None),
        ("DELETE", f"{BIRD}/effects/rainbow", None),
    ):
        resp = await v2_client.request(method, path, json=body)
        await expect_problem(resp, 409, "safe-mode")
    assert core.config.model_dump() == before
    assert (await v2_client.get(EFFECT)).status == 200
    assert (await v2_client.get(f"{BIRD}/effects")).status == 200
    assert (await v2_client.post(f"{BIRD}/fallback")).status == 204
