"""Tests for startup_playlist_id configuration and activation logic."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ledfx.api.utils import PERMITTED_KEYS
from ledfx.config import CORE_CONFIG_KEYS_NO_RESTART, CORE_CONFIG_SCHEMA
from ledfx.core import LedFxCore


class TestStartupPlaylistConfig:
    """Test that startup_playlist_id is properly defined in config schema."""

    def test_default_value_is_empty_string(self):
        config = CORE_CONFIG_SCHEMA({})
        assert config["startup_playlist_id"] == ""

    def test_accepts_string_value(self):
        config = CORE_CONFIG_SCHEMA({"startup_playlist_id": "my-playlist"})
        assert config["startup_playlist_id"] == "my-playlist"

    def test_present_in_no_restart_keys(self):
        assert "startup_playlist_id" in CORE_CONFIG_KEYS_NO_RESTART

    def test_present_in_api_permitted_keys(self):
        assert "startup_playlist_id" in PERMITTED_KEYS["core"]


class TestStartupPlaylistActivation:
    """Test startup playlist activation logic via LedFxCore._handle_startup_playlist."""

    @pytest.fixture
    def core(self):
        """Create a minimal LedFxCore-like object with _handle_startup_playlist."""
        core = MagicMock(spec=LedFxCore)
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
        # Bind the real helper so the production logic is exercised
        core._handle_startup_playlist = (
            LedFxCore._handle_startup_playlist.__get__(core, LedFxCore)
        )
        return core

    @pytest.mark.asyncio
    async def test_startup_playlist_starts_when_configured(self, core):
        core.playlists = MagicMock()
        core.playlists.start = AsyncMock(return_value=True)

        await core._handle_startup_playlist()

        core.playlists.start.assert_called_once_with("test-playlist")

    @pytest.mark.asyncio
    async def test_startup_playlist_skipped_when_empty(self, core):
        core.config["startup_playlist_id"] = ""
        core.playlists = MagicMock()
        core.playlists.start = AsyncMock(return_value=True)

        await core._handle_startup_playlist()

        core.playlists.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_startup_playlist_warns_when_not_found(self, core):
        core.config["startup_playlist_id"] = "nonexistent"
        core.playlists = MagicMock()
        core.playlists.start = AsyncMock(return_value=False)

        await core._handle_startup_playlist()

        core.playlists.start.assert_called_once_with("nonexistent")

    @pytest.mark.asyncio
    async def test_creates_playlist_manager_if_missing(self, core):
        # Remove playlists attribute so hasattr check triggers
        del core.playlists

        with patch(
            "ledfx.core.PlaylistManager", autospec=True
        ) as MockPM:
            mock_manager = MockPM.return_value
            mock_manager.start = AsyncMock(return_value=True)

            await core._handle_startup_playlist()

            MockPM.assert_called_once_with(core)
            mock_manager.start.assert_called_once_with("test-playlist")
