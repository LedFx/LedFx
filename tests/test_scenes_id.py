import json

import pytest

from ledfx.api.scenes_id import SceneEndpoint


class _DummyScenes:
    def is_active(self, scene_id):
        return scene_id == "active-scene"


class _DummyEffectClass:
    @staticmethod
    def get_combined_default_schema():
        return {}


class _DummyEffects:
    def get_class(self, _effect_id):
        return _DummyEffectClass


class _DummyLedFx:
    def __init__(
        self, scenes_config, presets_config=None, user_presets_config=None
    ):
        self.config = {
            "scenes": scenes_config,
            "ledfx_presets": presets_config or {},
            "user_presets": user_presets_config or {},
        }
        self.scenes = _DummyScenes()
        self.effects = _DummyEffects()


@pytest.mark.asyncio
async def test_get_scene_returns_scene_with_id_and_config():
    scene_id = "test-scene"
    scene_config = {
        "name": "Test Scene",
        "virtuals": {
            "v1": {"type": "bars", "config": {"speed": 2}},
        },
    }
    ledfx = _DummyLedFx({scene_id: scene_config})
    endpoint = SceneEndpoint(ledfx)

    response = await endpoint.get(scene_id)
    assert response.status == 200

    data = json.loads(response.body.decode())
    assert data["status"] == "success"
    assert data["scene"]["id"] == scene_id
    assert data["scene"]["config"]["name"] == "Test Scene"
    assert data["scene"]["config"]["active"] is False


@pytest.mark.asyncio
async def test_get_scene_returns_active_flag_true_for_active_scene():
    scene_id = "active-scene"
    scene_config = {
        "name": "Active Scene",
        "virtuals": {},
    }
    ledfx = _DummyLedFx({scene_id: scene_config})
    endpoint = SceneEndpoint(ledfx)

    response = await endpoint.get(scene_id)
    data = json.loads(response.body.decode())

    assert data["scene"]["config"]["active"] is True


@pytest.mark.asyncio
async def test_get_scene_returns_error_for_nonexistent_scene():
    ledfx = _DummyLedFx({})
    endpoint = SceneEndpoint(ledfx)

    response = await endpoint.get("nonexistent")
    assert response.status == 200
    data = json.loads(response.body.decode())
    assert data["status"] == "failed"


@pytest.mark.asyncio
async def test_get_scene_handles_empty_virtual_effect():
    scene_id = "empty-virtual-scene"
    scene_config = {
        "name": "Empty Virtual Scene",
        "virtuals": {
            "v1": {},
        },
    }
    ledfx = _DummyLedFx({scene_id: scene_config})
    endpoint = SceneEndpoint(ledfx)

    response = await endpoint.get(scene_id)
    data = json.loads(response.body.decode())

    virtuals = data["scene"]["config"]["virtuals"]
    assert "preset" not in virtuals["v1"]
    assert "preset_category" not in virtuals["v1"]


@pytest.mark.asyncio
async def test_get_scene_handles_scene_with_no_virtuals():
    scene_id = "no-virtuals-scene"
    scene_config = {
        "name": "No Virtuals Scene",
    }
    ledfx = _DummyLedFx({scene_id: scene_config})
    endpoint = SceneEndpoint(ledfx)

    response = await endpoint.get(scene_id)
    data = json.loads(response.body.decode())

    assert data["status"] == "success"
    assert "virtuals" not in data["scene"]["config"]


@pytest.mark.asyncio
async def test_get_scene_sanitizes_scene_id():
    scene_config = {
        "name": "Test Scene",
        "virtuals": {},
    }
    ledfx = _DummyLedFx({"test-scene": scene_config})
    endpoint = SceneEndpoint(ledfx)

    # generate_id should convert "Test Scene" to "test-scene"
    response = await endpoint.get("Test Scene")
    data = json.loads(response.body.decode())

    assert data["scene"]["id"] == "test-scene"
