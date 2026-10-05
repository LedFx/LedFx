"""Tests for startup_playlist_id configuration and activation logic."""

import logging
from unittest.mock import AsyncMock, MagicMock

import pytest

from ledfx.api.utils import PERMITTED_KEYS
from ledfx.configuration.models import RESTART_FIELDS, LedFxConfig
from ledfx.core import LedFxCore
from ledfx.errors import SafeMode
from tests.test_utilities.fake_ledfx import fake_ledfx


class TestStartupPlaylistConfig:
    """Test that startup_playlist_id is properly defined in config schema."""

    def test_default_value_is_empty_string(self):
        assert LedFxConfig().startup_playlist_id == ""

    def test_accepts_string_value(self):
        config = LedFxConfig(startup_playlist_id="my-playlist")
        assert config.startup_playlist_id == "my-playlist"

    def test_not_a_restart_field(self):
        assert "startup_playlist_id" not in RESTART_FIELDS

    def test_present_in_api_permitted_keys(self):
        assert "startup_playlist_id" in PERMITTED_KEYS["core"]


class TestStartupPlaylistActivation:
    """Test startup playlist activation logic via LedFxCore._handle_startup_playlist."""

    @pytest.fixture
    def core(self):
        """Create a minimal LedFxCore-like object with _handle_startup_playlist."""
        core = MagicMock(spec=LedFxCore)
        core.config = fake_ledfx(
            {
                "startup_scene_id": "",
                "startup_playlist_id": "test-playlist",
                "playlists": {
                    "test-playlist": {
                        "id": "test-playlist",
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
        ).config
        core.config_dir = ""
        core.events = MagicMock()
        # Bind the real helper so the production logic is exercised
        core._handle_startup_playlist = LedFxCore._handle_startup_playlist.__get__(
            core, LedFxCore
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
        core.config.startup_playlist_id = ""
        core.playlists = MagicMock()
        core.playlists.start = AsyncMock(return_value=True)

        await core._handle_startup_playlist()

        core.playlists.start.assert_not_called()

    @pytest.mark.asyncio
    async def test_startup_playlist_warns_when_not_found(self, core):
        core.config.startup_playlist_id = "nonexistent"
        core.playlists = MagicMock()
        core.playlists.start = AsyncMock(return_value=False)

        await core._handle_startup_playlist()

        core.playlists.start.assert_called_once_with("nonexistent")


class TestStartupScene:
    """The startup scene is skipped quietly in safe mode."""

    def test_safe_mode_skips_the_scene_at_debug(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        core = MagicMock()
        core.config.startup_scene_id = "party"
        core.scenes.activate.side_effect = SafeMode("read-only")
        with caplog.at_level(logging.DEBUG, logger="ledfx.core"):
            LedFxCore._activate_startup_scene(core)

        core.scenes.activate.assert_called_once_with("party")
        assert [r.levelno for r in caplog.records if "startup" in r.getMessage()] == [
            logging.DEBUG
        ]
