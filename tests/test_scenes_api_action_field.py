"""Tests for scenes API endpoints with action field support."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from aiohttp import web
from aiohttp.test_utils import AioHTTPTestCase

from ledfx.api.scenes import ScenesEndpoint
from ledfx.api.scenes_id import SceneEndpoint


class MockLedFx:
    """Mock LedFx instance for testing."""

    def __init__(self):
        self.config = {
            "scenes": {},
            "ledfx_presets": {},
            "user_presets": {},
        }
        self.config_dir = "/tmp/test"
        self.virtuals = {}
        self.effects = MagicMock()
        self.scenes = MagicMock()
        self.scenes.is_active = MagicMock(return_value=False)


class TestScenesEndpointPost(AioHTTPTestCase):
    """Test POST /api/scenes endpoint with action field support."""

    async def get_application(self):
        app = web.Application()
        endpoint = ScenesEndpoint(MockLedFx())
        app.router.add_post("/api/scenes", endpoint.post)
        return app

    @patch("ledfx.api.scenes.save_config")
    async def test_create_scene_with_action_fields(self, mock_save):
        """Test creating a scene with action fields."""
        request_data = {
            "name": "Test Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "bars",
                    "config": {"speed": 2},
                },
                "v2": {"action": "stop"},
                "v3": {"action": "forceblack"},
                "v4": {"action": "ignore"},
            },
        }

        resp = await self.client.post(
            "/api/scenes",
            data=json.dumps(request_data),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"
        assert "scene" in data
        assert "id" in data["scene"]

        # Verify all action fields are preserved
        scene_config = data["scene"]["config"]
        assert scene_config["virtuals"]["v1"]["action"] == "activate"
        assert scene_config["virtuals"]["v1"]["type"] == "bars"
        assert scene_config["virtuals"]["v2"]["action"] == "stop"
        assert scene_config["virtuals"]["v3"]["action"] == "forceblack"
        assert scene_config["virtuals"]["v4"]["action"] == "ignore"

    @patch("ledfx.api.scenes.save_config")
    async def test_create_scene_with_preset(self, mock_save):
        """Test creating a scene with preset reference."""
        request_data = {
            "name": "Preset Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "preset": "rainbow-scroll",
                },
            },
        }

        resp = await self.client.post(
            "/api/scenes",
            data=json.dumps(request_data),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"

        scene_config = data["scene"]["config"]
        assert scene_config["virtuals"]["v1"]["action"] == "activate"
        assert scene_config["virtuals"]["v1"]["preset"] == "rainbow-scroll"
        # Should not have type/config when using preset
        assert "type" not in scene_config["virtuals"]["v1"]

    @patch("ledfx.api.scenes.save_config")
    async def test_create_scene_legacy_format(self, mock_save):
        """Test creating a scene with legacy format (no action field)."""
        request_data = {
            "name": "Legacy Scene",
            "virtuals": {
                "v1": {
                    "type": "energy",
                    "config": {"intensity": 5},
                },
                "v2": {},
            },
        }

        resp = await self.client.post(
            "/api/scenes",
            data=json.dumps(request_data),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"

        scene_config = data["scene"]["config"]
        # Legacy format should be preserved
        assert scene_config["virtuals"]["v1"]["type"] == "energy"
        assert scene_config["virtuals"]["v1"]["config"]["intensity"] == 5
        assert "action" not in scene_config["virtuals"]["v1"]

    @patch("ledfx.api.scenes.save_config")
    async def test_upsert_scene_with_id(self, mock_save):
        """Test upserting a scene with explicit ID."""
        request_data = {
            "id": "my-scene",
            "name": "My Scene",
            "virtuals": {
                "v1": {"action": "stop"},
            },
        }

        resp = await self.client.post(
            "/api/scenes",
            data=json.dumps(request_data),
            headers={"Content-Type": "application/json"},
        )

        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"
        assert data["scene"]["id"] == "my-scene"


class TestScenesEndpointGet(AioHTTPTestCase):
    """Test GET /api/scenes endpoint with preset detection."""

    async def get_application(self):
        app = web.Application()
        self.mock_ledfx = MockLedFx()
        endpoint = ScenesEndpoint(self.mock_ledfx)
        app.router.add_get("/api/scenes", endpoint.handler)
        return app

    async def test_get_scenes_with_preset_detection(self):
        """Test that GET /api/scenes includes preset detection."""
        self.mock_ledfx.config["scenes"] = {
            "scene-1": {
                "name": "Scene 1",
                "virtuals": {
                    "v1": {
                        "action": "activate",
                        "type": "bars",
                        "config": {"speed": 2},
                    },
                },
            },
        }

        with patch("ledfx.api.scenes.find_matching_preset") as mock_find:
            mock_find.return_value = ("cool-preset", "ledfx_presets")

            resp = await self.client.get("/api/scenes")

            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "success"
            assert "scenes" in data
            assert "scene-1" in data["scenes"]

            # Check preset was added
            virtual_config = data["scenes"]["scene-1"]["virtuals"]["v1"]
            assert virtual_config["preset"] == "cool-preset"
            assert virtual_config["preset_category"] == "ledfx_presets"

    async def test_get_scenes_includes_active_flag(self):
        """Test that scenes include active flag."""
        self.mock_ledfx.config["scenes"] = {
            "scene-1": {
                "name": "Scene 1",
                "virtuals": {},
            },
        }
        self.mock_ledfx.scenes.is_active.return_value = True

        resp = await self.client.get("/api/scenes")

        assert resp.status == 200
        data = await resp.json()
        assert data["scenes"]["scene-1"]["active"] is True


class TestSceneEndpointDelete(AioHTTPTestCase):
    """Test DELETE /api/scenes/{id} endpoint."""

    async def get_application(self):
        app = web.Application()
        self.mock_ledfx = MockLedFx()
        endpoint = SceneEndpoint(self.mock_ledfx)
        app.router.add_delete("/api/scenes/{scene_id}", endpoint.handler)
        return app

    @patch("ledfx.api.scenes_id.save_config")
    async def test_delete_scene_restful(self, mock_save):
        """Test RESTful DELETE /api/scenes/{id} endpoint."""
        self.mock_ledfx.config["scenes"]["test-scene"] = {
            "name": "Test Scene",
            "virtuals": {},
        }

        resp = await self.client.delete("/api/scenes/test-scene")

        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "success"
        assert "test-scene" in data["payload"]["reason"]

        # Verify scene was deleted
        assert "test-scene" not in self.mock_ledfx.config["scenes"]
        mock_save.assert_called_once()

    async def test_delete_nonexistent_scene(self):
        """Test deleting a scene that doesn't exist."""
        resp = await self.client.delete("/api/scenes/missing-scene")

        assert resp.status == 200
        data = await resp.json()
        assert data["status"] == "failed"
        assert "Scene not found" in data["payload"]["reason"]


class TestSceneEndpointGet(AioHTTPTestCase):
    """Test GET /api/scenes/{id} endpoint."""

    async def get_application(self):
        app = web.Application()
        self.mock_ledfx = MockLedFx()
        endpoint = SceneEndpoint(self.mock_ledfx)
        app.router.add_get("/api/scenes/{scene_id}", endpoint.handler)
        return app

    async def test_get_scene_with_preset_detection(self):
        """Test GET single scene includes preset detection."""
        self.mock_ledfx.config["scenes"]["my-scene"] = {
            "name": "My Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "scroll",
                    "config": {"speed": 3},
                },
            },
        }
        self.mock_ledfx.scenes.is_active.return_value = False

        with patch("ledfx.api.scenes_id.find_matching_preset") as mock_find:
            mock_find.return_value = ("rainbow-preset", "user_presets")

            resp = await self.client.get("/api/scenes/my-scene")

            assert resp.status == 200
            data = await resp.json()
            assert data["status"] == "success"
            assert data["scene"]["id"] == "my-scene"

            virtual_config = data["scene"]["config"]["virtuals"]["v1"]
            assert virtual_config["preset"] == "rainbow-preset"
            assert virtual_config["preset_category"] == "user_presets"


# Integration-style tests
@pytest.mark.asyncio
async def test_scene_action_field_preservation():
    """Test that action fields are preserved through create/retrieve cycle."""
    mock_ledfx = MockLedFx()
    scenes_endpoint = ScenesEndpoint(mock_ledfx)

    # Create a mock request with action fields
    request_data = {
        "name": "Action Test",
        "virtuals": {
            "v1": {"action": "activate", "preset": "rainbow"},
            "v2": {"action": "stop"},
            "v3": {"action": "forceblack"},
            "v4": {"action": "ignore"},
        },
    }

    mock_request = AsyncMock()
    mock_request.json = AsyncMock(return_value=request_data)

    with patch("ledfx.api.scenes.save_config"):
        response = await scenes_endpoint.post(mock_request)
        data = json.loads(response.body.decode())

        virtuals = data["scene"]["config"]["virtuals"]

        # Verify all action types are preserved
        assert virtuals["v1"]["action"] == "activate"
        assert virtuals["v1"]["preset"] == "rainbow"
        assert virtuals["v2"]["action"] == "stop"
        assert virtuals["v3"]["action"] == "forceblack"
        assert virtuals["v4"]["action"] == "ignore"
