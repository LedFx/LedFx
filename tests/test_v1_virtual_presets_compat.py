"""The v1 virtual presets endpoint changes effects only through the Virtuals
manager."""

import inspect
from collections.abc import Iterator
from unittest.mock import MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import TestClient, TestServer

import ledfx.api.virtual_presets as presets_module
from ledfx.api.virtual_presets import VirtualPresetsEndpoint
from ledfx.configuration.fields import VirtualIdStr
from tests.test_utilities.virtuals_core import enter_safe_mode, running_core
from tests.v1_golden.harness import build_app

RESET = {"category": "ledfx_presets", "effect_id": "singleColor", "preset_id": "reset"}


@pytest.fixture
def ledfx(monkeypatch: pytest.MonkeyPatch) -> Iterator[MagicMock]:
    yield from running_core(monkeypatch)


def client(ledfx: MagicMock) -> TestClient[web.Request, web.Application]:
    return TestClient(TestServer(build_app(ledfx, (VirtualPresetsEndpoint,))))


def running(ledfx: MagicMock, virtual_id: str) -> str | None:
    effect = ledfx.virtuals.get_or_raise(VirtualIdStr(virtual_id)).active_effect
    return effect.type if effect else None


async def test_a_refusing_virtual_leaks_no_effect(ledfx: MagicMock) -> None:
    before = len(ledfx.effects.values())
    async with client(ledfx) as http:
        response = await http.put("/api/virtuals/empty/presets", json=RESET)
        assert (await response.json())["status"] == "failed"

    assert len(ledfx.effects.values()) == before
    assert running(ledfx, "empty") is None


async def test_safe_mode_changes_nothing(ledfx: MagicMock) -> None:
    ledfx.virtuals.set_effect("dj bird", "rainbow", None)
    entry = ledfx.virtuals.get_or_raise(VirtualIdStr("dj bird")).entry
    assert entry is not None
    stored = entry.model_copy(deep=True)
    enter_safe_mode(ledfx)
    ledfx.config_store.request_save.reset_mock()
    async with client(ledfx) as http:
        put = await http.put("/api/virtuals/dj%20bird/presets", json=RESET)
        delete = await http.delete("/api/virtuals/dj%20bird/presets")
        for response in (put, delete):
            body = await response.json()
            assert body["status"] == "failed"
            assert "safe mode" in body["payload"]["reason"]

    assert running(ledfx, "dj bird") == "rainbow"
    assert entry == stored
    ledfx.config_store.request_save.assert_not_called()


async def test_apply_and_clear_use_the_manager(
    ledfx: MagicMock, monkeypatch: pytest.MonkeyPatch
) -> None:
    set_effect = MagicMock(wraps=ledfx.virtuals.set_effect)
    clear_effect = MagicMock(wraps=ledfx.virtuals.clear_effect)
    monkeypatch.setattr(ledfx.virtuals, "set_effect", set_effect)
    monkeypatch.setattr(ledfx.virtuals, "clear_effect", clear_effect)

    async with client(ledfx) as http:
        await http.put("/api/virtuals/dj%20bird/presets", json=RESET)
        await http.delete("/api/virtuals/dj%20bird/presets")

    assert [c.args[:2] for c in set_effect.call_args_list] == [
        (VirtualIdStr("dj bird"), "singleColor")
    ]
    assert [c.args for c in clear_effect.call_args_list] == [(VirtualIdStr("dj bird"),)]


def test_source_has_no_direct_effect_calls() -> None:
    source = inspect.getsource(presets_module)
    assert "effects.create(" not in source
    assert "update_effect_config" not in source
    assert source.count(".set_effect(") == source.count("virtuals.set_effect(")
    assert source.count(".clear_effect(") == source.count("virtuals.clear_effect(")
