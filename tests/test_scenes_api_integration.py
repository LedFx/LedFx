"""Integration tests for scenes API with action field support."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ledfx.api.scenes import ScenesEndpoint
from ledfx.api.scenes_id import SceneEndpoint


class MockLedFx:
    """Mock LedFx instance for testing."""

    def __init__(self):
        self.config = {
            "scenes": {},
            "ledfx_presets": {
                "scroll": {
                    "rainbow-scroll": {
                        "name": "Rainbow Scroll",
                        "config": {"speed": 2, "gradient": "rainbow"},
                    }
                }
            },
            "user_presets": {},
        }
        self.config_dir = "/tmp/test"
        self.virtuals = {}
        self.effects = MagicMock()
        self.scenes = MagicMock()
        self.scenes.is_active = MagicMock(return_value=False)


@pytest.mark.asyncio
async def test_post_scene_preserves_action_fields():
    """Test that POST /api/scenes preserves action fields."""
    mock_ledfx = MockLedFx()
    endpoint = ScenesEndpoint(mock_ledfx)

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
            "v5": {
                "action": "activate",
                "type": "scroll",
                "preset": "rainbow-scroll",
            },
        },
    }

    mock_request = AsyncMock()
    mock_request.json = AsyncMock(return_value=request_data)

    with patch("ledfx.api.scenes.save_config"):
        response = await endpoint.post(mock_request)
        data = json.loads(response.body.decode())

        assert data["status"] == "success"
        scene_config = data["scene"]["config"]

        # Verify all action fields are preserved
        assert scene_config["virtuals"]["v1"]["action"] == "activate"
        assert scene_config["virtuals"]["v1"]["type"] == "bars"
        assert scene_config["virtuals"]["v2"]["action"] == "stop"
        assert scene_config["virtuals"]["v3"]["action"] == "forceblack"
        assert scene_config["virtuals"]["v4"]["action"] == "ignore"
        assert scene_config["virtuals"]["v5"]["action"] == "activate"
        assert scene_config["virtuals"]["v5"]["type"] == "scroll"
        assert scene_config["virtuals"]["v5"]["preset"] == "rainbow-scroll"


@pytest.mark.asyncio
async def test_post_scene_preserves_legacy_format():
    """Test that POST /api/scenes preserves legacy format."""
    mock_ledfx = MockLedFx()
    endpoint = ScenesEndpoint(mock_ledfx)

    request_data = {
        "name": "Legacy Scene",
        "virtuals": {
            "v1": {"type": "energy", "config": {"intensity": 5}},
            "v2": {},
        },
    }

    mock_request = AsyncMock()
    mock_request.json = AsyncMock(return_value=request_data)

    with patch("ledfx.api.scenes.save_config"):
        response = await endpoint.post(mock_request)
        data = json.loads(response.body.decode())

        assert data["status"] == "success"
        scene_config = data["scene"]["config"]

        # Legacy format should be preserved (no action field added)
        assert scene_config["virtuals"]["v1"]["type"] == "energy"
        assert "action" not in scene_config["virtuals"]["v1"]
        assert scene_config["virtuals"]["v2"] == {}


@pytest.mark.asyncio
async def test_post_scene_mixed_legacy_and_new():
    """Test that POST can handle mixed legacy and new format in same scene."""
    mock_ledfx = MockLedFx()
    endpoint = ScenesEndpoint(mock_ledfx)

    request_data = {
        "name": "Mixed Scene",
        "virtuals": {
            "v1": {"type": "bars", "config": {"speed": 1}},  # Legacy
            "v2": {"action": "stop"},  # New
            "v3": {},  # Legacy empty
            "v4": {
                "action": "activate",
                "type": "scroll",
                "preset": "rainbow-scroll",
            },  # New
        },
    }

    mock_request = AsyncMock()
    mock_request.json = AsyncMock(return_value=request_data)

    with patch("ledfx.api.scenes.save_config"):
        response = await endpoint.post(mock_request)
        data = json.loads(response.body.decode())

        assert data["status"] == "success"
        scene_config = data["scene"]["config"]

        # Legacy entries preserved
        assert scene_config["virtuals"]["v1"]["type"] == "bars"
        assert "action" not in scene_config["virtuals"]["v1"]
        assert scene_config["virtuals"]["v3"] == {}

        # New format preserved
        assert scene_config["virtuals"]["v2"]["action"] == "stop"
        assert scene_config["virtuals"]["v4"]["action"] == "activate"
        assert scene_config["virtuals"]["v4"]["preset"] == "rainbow-scroll"


@pytest.mark.asyncio
async def test_get_scenes_includes_preset_detection():
    """Test that GET /api/scenes includes preset detection."""
    mock_ledfx = MockLedFx()
    mock_ledfx.config["scenes"] = {
        "scene-1": {
            "name": "Scene 1",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "scroll",
                    "config": {"speed": 2, "gradient": "rainbow"},
                },
            },
        },
    }

    endpoint = ScenesEndpoint(mock_ledfx)

    response = await endpoint.get()
    data = json.loads(response.body.decode())

    assert data["status"] == "success"
    assert "scenes" in data
    assert "scene-1" in data["scenes"]

    # Check preset was detected and added
    virtual_config = data["scenes"]["scene-1"]["virtuals"]["v1"]
    assert virtual_config["preset"] == "rainbow-scroll"
    assert virtual_config["preset_category"] == "ledfx_presets"


@pytest.mark.asyncio
async def test_get_scene_by_id_includes_preset_detection():
    """Test that GET /api/scenes/{id} includes preset detection."""
    mock_ledfx = MockLedFx()
    mock_ledfx.config["scenes"] = {
        "my-scene": {
            "name": "My Scene",
            "virtuals": {
                "v1": {
                    "action": "activate",
                    "type": "scroll",
                    "config": {"speed": 2, "gradient": "rainbow"},
                },
            },
        },
    }

    endpoint = SceneEndpoint(mock_ledfx)

    response = await endpoint.get("my-scene")
    data = json.loads(response.body.decode())

    assert data["status"] == "success"
    assert data["scene"]["id"] == "my-scene"

    virtual_config = data["scene"]["config"]["virtuals"]["v1"]
    assert virtual_config["preset"] == "rainbow-scroll"
    assert virtual_config["preset_category"] == "ledfx_presets"


@pytest.mark.asyncio
async def test_delete_scene_by_id_restful():
    """Test that DELETE /api/scenes/{id} works."""
    mock_ledfx = MockLedFx()
    mock_ledfx.config["scenes"]["test-scene"] = {
        "name": "Test Scene",
        "virtuals": {},
    }

    endpoint = SceneEndpoint(mock_ledfx)

    with patch("ledfx.api.scenes_id.save_config") as mock_save:
        response = await endpoint.delete("test-scene")
        data = json.loads(response.body.decode())

        assert data["status"] == "success"
        assert "test-scene" in data["payload"]["reason"]

        # Verify scene was deleted
        assert "test-scene" not in mock_ledfx.config["scenes"]
        mock_save.assert_called_once()


@pytest.mark.asyncio
async def test_delete_nonexistent_scene_returns_error():
    """Test that deleting a nonexistent scene returns an error."""
    mock_ledfx = MockLedFx()
    endpoint = SceneEndpoint(mock_ledfx)

    response = await endpoint.delete("missing-scene")
    data = json.loads(response.body.decode())

    assert data["status"] == "failed"
    assert "Scene not found" in data["payload"]["reason"]


@pytest.mark.asyncio
async def test_post_scene_with_upsert():
    """Test that POST with explicit id performs upsert."""
    mock_ledfx = MockLedFx()
    endpoint = ScenesEndpoint(mock_ledfx)

    # Create initial scene
    request_data = {
        "name": "Original Scene",
        "virtuals": {"v1": {"action": "stop"}},
    }

    mock_request = AsyncMock()
    mock_request.json = AsyncMock(return_value=request_data)

    with patch("ledfx.api.scenes.save_config"):
        response = await endpoint.post(mock_request)
        data = json.loads(response.body.decode())

        assert data["status"] == "success"
        scene_id = data["scene"]["id"]
        assert data["scene"]["config"]["name"] == "Original Scene"

        # Now upsert with same id and new name
        request_data_2 = {
            "id": scene_id,
            "name": "Updated Scene",
            "virtuals": {"v1": {"action": "forceblack"}},
        }

        mock_request.json = AsyncMock(return_value=request_data_2)
        response = await endpoint.post(mock_request)
        data = json.loads(response.body.decode())

        assert data["status"] == "success"
        assert data["scene"]["id"] == scene_id
        assert data["scene"]["config"]["name"] == "Updated Scene"
        assert (
            data["scene"]["config"]["virtuals"]["v1"]["action"] == "forceblack"
        )

        # Test upsert without name (name should remain unchanged)
        request_data_3 = {
            "id": scene_id,
            "virtuals": {"v1": {"action": "ignore"}},
        }

        mock_request.json = AsyncMock(return_value=request_data_3)
        response = await endpoint.post(mock_request)
        data = json.loads(response.body.decode())

        assert data["status"] == "success"
        assert data["scene"]["id"] == scene_id
        assert (
            data["scene"]["config"]["name"] == "Updated Scene"
        )  # Name preserved from previous update
        assert data["scene"]["config"]["virtuals"]["v1"]["action"] == "ignore"


@pytest.mark.asyncio
async def test_get_scenes_handles_virtuals_without_type_or_config():
    """Test that GET handles virtuals with only action field."""
    mock_ledfx = MockLedFx()
    mock_ledfx.config["scenes"] = {
        "scene-1": {
            "name": "Scene 1",
            "virtuals": {
                "v1": {"action": "stop"},
                "v2": {"action": "ignore"},
                "v3": {},  # Legacy empty
            },
        },
    }

    endpoint = ScenesEndpoint(mock_ledfx)

    response = await endpoint.get()
    data = json.loads(response.body.decode())

    assert data["status"] == "success"

    # Should not crash, and should not add preset fields for action-only virtuals
    virtuals = data["scenes"]["scene-1"]["virtuals"]
    assert "preset" not in virtuals["v1"]
    assert "preset" not in virtuals["v2"]
    assert "preset" not in virtuals["v3"]


@pytest.mark.asyncio
async def test_post_scene_warns_preset_without_type():
    """Test that POST /api/scenes logs warning when preset is provided without type."""
    mock_ledfx = MockLedFx()
    endpoint = ScenesEndpoint(mock_ledfx)

    request_data = {
        "name": "Invalid Preset Scene",
        "virtuals": {
            "v1": {
                "action": "activate",
                "preset": "rainbow-scroll",  # Missing required 'type' field
            },
        },
    }

    mock_request = MagicMock()
    mock_request.json = AsyncMock(return_value=request_data)

    with patch("ledfx.api.scenes.save_config"):
        with patch("ledfx.api.scenes._LOGGER") as mock_logger:
            response = await endpoint.post(mock_request)
            data = json.loads(response.body.decode())

            assert data["status"] == "success"
            # Should have logged a warning about missing type
            mock_logger.warning.assert_called_once()
            warning_msg = mock_logger.warning.call_args[0][0]
            assert "preset" in warning_msg.lower()
            assert "type" in warning_msg.lower()
            assert "v1" in warning_msg
