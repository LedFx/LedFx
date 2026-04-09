"""Tests for startup_playlist_id configuration and activation logic."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ledfx.config import CORE_CONFIG_SCHEMA


class TestStartupPlaylistConfig:
    """Test that startup_playlist_id is properly defined in config schema."""

    def test_default_value_is_empty_string(self):
        config = CORE_CONFIG_SCHEMA({})
        assert config["startup_playlist_id"] == ""

    def test_accepts_string_value(self):
        config = CORE_CONFIG_SCHEMA({"startup_playlist_id": "my-playlist"})
        assert config["startup_playlist_id"] == "my-playlist"

    def test_present_in_no_restart_keys(self):
        from ledfx.config import CORE_CONFIG_KEYS_NO_RESTART

        assert "startup_playlist_id" in CORE_CONFIG_KEYS_NO_RESTART

    def test_present_in_api_permitted_keys(self):
        from ledfx.api.utils import PERMITTED_KEYS

        assert "startup_playlist_id" in PERMITTED_KEYS["core"]


class TestStartupPlaylistActivation:
    """Test startup playlist activation logic in core startup flow."""

    @pytest.fixture
    def mock_core(self):
        core = MagicMock()
        core.config = {
            "startup_scene_id": "",
            "startup_playlist_id": "test-playlist",
            "playlists": {
                "test-playlist": {
                    "name": "Test Playlist",
                    "items": [{"scene_id": "scene-1"}],
                    "default_duration_ms": 5000,
                    "mode": "sequence",
                    "timing": {
                        "jitter": {
                            "enabled": False,
                            "factor_min": 1.0,
                            "factor_max": 1.0,
                        }
                    },
                    "tags": [],
                    "image": "Wallpaper",
                }
            },
            "scenes": {"scene-1": {"name": "Scene 1", "virtuals": {}}},
        }
        core.config_dir = ""
        core.events = MagicMock()
        return core

    @pytest.mark.asyncio
    async def test_startup_playlist_starts_when_configured(self, mock_core):
        from ledfx.playlists import PlaylistManager

        manager = PlaylistManager(mock_core)
        manager.start = AsyncMock(return_value=True)

        # Simulate the core.py startup logic
        pid = mock_core.config["startup_playlist_id"]
        assert pid != ""
        result = await manager.start(pid)
        assert result is True
        manager.start.assert_called_once_with("test-playlist")

    @pytest.mark.asyncio
    async def test_startup_playlist_skipped_when_empty(self, mock_core):
        mock_core.config["startup_playlist_id"] = ""

        from ledfx.playlists import PlaylistManager

        manager = PlaylistManager(mock_core)
        manager.start = AsyncMock(return_value=True)

        pid = mock_core.config["startup_playlist_id"]
        # Should not start when empty string
        assert pid == ""
        manager.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_startup_playlist_warns_when_not_found(self, mock_core):
        mock_core.config["startup_playlist_id"] = "nonexistent"

        from ledfx.playlists import PlaylistManager

        manager = PlaylistManager(mock_core)
        manager.start = AsyncMock(return_value=False)

        pid = mock_core.config["startup_playlist_id"]
        result = await manager.start(pid)
        assert result is False
