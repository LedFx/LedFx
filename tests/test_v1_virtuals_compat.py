"""v1 virtuals handlers over the Virtuals manager: the v1 compatibility
behaviour that rides on it. Deleted with v1; the manager's own tests live in
test_virtuals_manager.py and import nothing from v1."""

import asyncio
from collections.abc import Iterator, Mapping
from unittest.mock import MagicMock

import pytest
from aiohttp.test_utils import TestClient, TestServer

from ledfx.api.effects import EffectsEndpoint
from ledfx.api.v1_compat import v1_color
from ledfx.api.virtual import VirtualEndpoint
from ledfx.api.virtual_effects import EffectsEndpoint as VirtualEffectsEndpoint
from ledfx.api.virtual_effects_delete import EffectsEndpoint as EffectDeleteEndpoint
from ledfx.api.virtuals import VirtualsEndpoint
from ledfx.api.virtuals_tools import VirtualsToolsEndpoint
from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.models import Highlight
from ledfx.configuration.plugin import PluginConfig
from ledfx.effects.oneshots.oneshot import Flash
from ledfx.errors import NotFound
from ledfx.virtuals import VirtualChanges
from tests.test_utilities.virtuals_core import add_virtual, running_core
from tests.v1_golden.harness import build_app

BIRD = VirtualIdStr("dj bird")
MIRROR = VirtualIdStr("mirror")


def cfg(values: Mapping[str, object]) -> PluginConfig:
    return PluginConfig.model_validate(values)


def _entry_ids(ledfx: MagicMock) -> list[str]:
    return [entry.id for entry in ledfx.config.virtuals]


def _flashes(ledfx: MagicMock, virtual_id: str) -> list[Flash]:
    virtual = ledfx.virtuals.get_or_raise(VirtualIdStr(virtual_id))
    return [o for o in virtual.oneshots if isinstance(o, Flash) and o.active]


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


async def test_concurrent_v1_update_and_delete_leave_no_orphan(
    ledfx: MagicMock,
) -> None:
    """An update racing a delete through the v1 handlers
    ends with the virtual gone from both the manager and the config."""
    app = build_app(ledfx, (VirtualsEndpoint, VirtualEndpoint))
    async with TestClient(TestServer(app)) as client:
        for n in range(20):
            virtual_id = f"race-{n}"
            add_virtual(ledfx, virtual_id, virtual_id, [["strip", 0, 9, False]])
            update, delete = await asyncio.gather(
                client.post(
                    "/api/virtuals",
                    json={"id": virtual_id, "config": {"max_brightness": 0.5}},
                ),
                client.delete(f"/api/virtuals/{virtual_id}"),
            )
            assert update.status == 200
            assert delete.status == 200
            assert ledfx.virtuals.get(virtual_id) is None
            assert virtual_id not in _entry_ids(ledfx)


# ---- the running effect ----------------------------------------------------


@pytest.mark.parametrize(("sent", "peak"), [(5, 255), (-3, 0), (0.5, 127.5)])
async def test_v1_oneshot_clamps_brightness(
    ledfx: MagicMock, sent: float, peak: float
) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    async with TestClient(TestServer(build_app(ledfx, (VirtualsToolsEndpoint,)))) as c:
        response = await c.post(
            "/api/virtuals_tools/dj%20bird",
            json={"tool": "oneshot", "color": "white", "brightness": sent},
        )
        assert response.status == 200, await response.text()
    [flash] = _flashes(ledfx, "dj bird")
    assert max(flash._color) == peak


async def test_v1_delete_swallows_only_an_unknown_effect(ledfx: MagicMock) -> None:
    """The virtual vanishing after the handler's check is not a success."""

    def gone(virtual_id: object, type_id: str) -> None:
        raise NotFound("Virtual", "dj bird")

    ledfx.virtuals.delete_effect_history = gone
    async with TestClient(TestServer(build_app(ledfx, (EffectDeleteEndpoint,)))) as c:
        response = await c.post(
            "/api/virtuals/dj%20bird/effects/delete", json={"type": "rainbow"}
        )
        assert '"status": "success"' not in await response.text()


def test_v1_color_turns_lists_into_hex() -> None:
    assert v1_color([255, 0, 16]) == "#ff0010"
    assert v1_color((1, 2, 3)) == "#010203"
    assert v1_color("red") == "#ff0000"
    for bad in ([1, 2], 7, None, dict[str, object]()):
        with pytest.raises(ValueError, match="Invalid color"):
            v1_color(bad)


async def test_v1_apply_global_accepts_a_colour_list(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    app = build_app(ledfx, (EffectsEndpoint,))
    async with TestClient(TestServer(app)) as client:
        response = await client.put(
            "/api/effects",
            json={"action": "apply_global", "background_color": [255, 0, 0]},
        )
        assert "Applied global configuration to 1" in await response.text()
    effect = ledfx.virtuals.get_or_raise(BIRD).active_effect
    assert effect.config.background_color == "#ff0000"


async def test_v1_apply_global_reports_a_refusing_effect_as_skipped(
    ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    effect = ledfx.virtuals.get_or_raise(BIRD).active_effect
    assert effect is not None

    def refuse(config: object) -> None:
        raise ValueError("refused")

    monkeypatch.setattr(effect, "update_config", refuse)
    app = build_app(ledfx, (EffectsEndpoint,))
    async with TestClient(TestServer(app)) as client:
        response = await client.put(
            "/api/effects", json={"action": "apply_global", "brightness": 0.5}
        )
        assert "to 0 effects (skipped 1)" in await response.text()


async def test_v1_put_colour_with_a_fallback_arms_the_fallback(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_effect(BIRD, "singleColor", cfg({}))
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    app = build_app(ledfx, (VirtualEffectsEndpoint,))
    async with TestClient(TestServer(app)) as client:
        path = f"/api/virtuals/{BIRD}/effects"
        # In place: nothing restarts, so the fallback is dropped.
        response = await client.put(path, json={"config": {"speed": 4}, "fallback": 30})
        assert (await response.json())["status"] == "success"
        assert not virtual.fallback_active
        # A colour change restarts the effect as a fallback.
        response = await client.put(
            path, json={"config": {"color": "#00ff00"}, "fallback": 30}
        )
        assert (await response.json())["status"] == "success"
    try:
        assert virtual.fallback_active
        assert virtual.fallback_effect_type == "singleColor"
    finally:
        virtual.fallback_clear()


async def test_v1_refused_activations_leave_the_registry_alone(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    ledfx.virtuals.clear_effect(BIRD)
    ledfx.virtuals.patch(BIRD, VirtualChanges(segments=[], active=False))
    before = set(ledfx.effects)
    app = build_app(ledfx, (VirtualEndpoint,))
    async with TestClient(TestServer(app)) as client:
        for _ in range(5):
            response = await client.put(f"/api/virtuals/{BIRD}", json={"active": True})
            assert response.status == 200  # v1 reports failures in the body
            assert (await response.json())["status"] == "failed"
    assert set(ledfx.effects) == before


async def test_v1_highlight_off_outside_calibration_is_refused(
    ledfx: MagicMock,
) -> None:
    app = build_app(ledfx, (VirtualsToolsEndpoint,))
    async with TestClient(TestServer(app)) as client:
        response = await client.put(
            "/api/virtuals_tools/dj%20bird", json={"tool": "highlight", "state": False}
        )
        text = await response.text()
    assert "Cannot set highlight when dj bird is not in calibration mode" in text


async def test_v1_highlight_with_a_bad_range_lights_nothing(
    ledfx: MagicMock,
) -> None:
    virtual = ledfx.virtuals.get_or_raise(BIRD)
    ledfx.virtuals.set_calibration(BIRD, True)
    ledfx.virtuals.set_highlight(BIRD, Highlight("strip", 0, 9))
    app = build_app(ledfx, (VirtualsToolsEndpoint,))
    async with TestClient(TestServer(app)) as client:
        bodies: list[dict[str, int]] = [
            {"start": 10, "stop": 5},
            {"start": -5, "stop": -2},
            {},
        ]
        for body in bodies:
            response = await client.put(
                "/api/virtuals_tools/dj%20bird",
                json={"tool": "highlight", "device": "strip", **body},
            )
            assert (await response.json())["status"] == "success"
            assert not virtual._hl_state  # the earlier highlight is cleared
            ledfx.virtuals.set_highlight(BIRD, Highlight("strip", 0, 9))


async def test_v1_highlight_without_a_string_device_is_refused(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_calibration(BIRD, True)
    app = build_app(ledfx, (VirtualsToolsEndpoint,))
    async with TestClient(TestServer(app)) as client:
        bodies: list[dict[str, int]] = [{}, {"device": 7}]
        for body in bodies:
            response = await client.put(
                "/api/virtuals_tools/dj%20bird",
                json={"tool": "highlight", "start": 0, "stop": 1, **body},
            )
            assert "Device" in await response.text()
            assert "not found" in await response.text()


async def test_v1_copy_skips_unknown_targets_and_lumps_refusals(
    ledfx: MagicMock,
) -> None:
    ledfx.virtuals.set_effect(BIRD, "rainbow", cfg({}))
    app = build_app(ledfx, (VirtualsToolsEndpoint,))
    async with TestClient(TestServer(app)) as client:

        async def copy(*target: str) -> str:
            response = await client.put(
                "/api/virtuals_tools/dj%20bird", json={"tool": "copy", "target": target}
            )
            return (await response.json())["status"]

        assert await copy("ghost", "empty") == "failed"
        assert ledfx.virtuals.get_or_raise(MIRROR).active_effect is None
        assert await copy("ghost", "mirror") == "success"
    assert ledfx.virtuals.get_or_raise(MIRROR).active_effect is not None


async def test_v1_create_repairs_what_add_refuses(ledfx: MagicMock) -> None:
    """v1 create zeroes a rotate on one row and fixes a reversed frequency
    range, as its update does; add itself refuses both."""
    config = {
        "name": "R",
        "rows": 1,
        "rotate": 2,
        "frequency_min": 900,
        "frequency_max": 100,
    }
    async with TestClient(TestServer(build_app(ledfx, (VirtualsEndpoint,)))) as c:
        response = await c.post("/api/virtuals", json={"config": config})
        assert response.status == 200, await response.text()
    stored = ledfx.virtuals.get_or_raise(VirtualIdStr("r")).config
    assert stored.rotate == 0
    assert (stored.frequency_min, stored.frequency_max) == (100, 900)
