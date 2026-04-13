"""Tests for the now-playing subsystem: models, manager, events, dedupe."""

from __future__ import annotations

import asyncio
import io
import time
from collections import OrderedDict
from unittest.mock import AsyncMock, MagicMock, patch

import numpy as np
import PIL.Image as Image
import pytest

from ledfx.events import (
    Event,
    NowPlayingArtUpdatedEvent,
    NowPlayingPaletteUpdatedEvent,
    NowPlayingUpdatedEvent,
)
from ledfx.nowplaying.manager import NowPlayingManager
from ledfx.nowplaying.models import NowPlayingState, NowPlayingTrack


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _DummyEvents:
    def __init__(self):
        self.fired = []

    def fire_event(self, event):
        self.fired.append(event)

    def add_listener(self, callback, event_type, event_filter=None):
        def remove():
            pass

        return remove


class _DummyVirtual:
    def __init__(self, vid, effect=None):
        self.id = vid
        self.active_effect = effect


class _DummyGradientEffect:
    """Simulates a GradientEffect with update_config."""

    def __init__(self, etype="bars"):
        self.type = etype
        self._config = {"gradient": "linear-gradient(90deg, rgb(255,0,0) 0%, rgb(0,0,255) 100%)"}
        self._updated = False

    def update_config(self, config):
        self._config.update(config)
        self._updated = True


class _DummyNonGradientEffect:
    """Simulates an effect without gradient support."""

    def __init__(self, etype="strobe"):
        self.type = etype
        self._config = {"speed": 1.0}


class _DummyLedFx:
    def __init__(self, config=None, virtuals=None):
        self.config = config or {"now_playing": {"enabled": False}}
        self.events = _DummyEvents()
        self.loop = asyncio.new_event_loop()
        self._virtuals = virtuals or {}

    @property
    def virtuals(self):
        return self

    def values(self):
        return self._virtuals.values()

    def get(self, vid):
        return self._virtuals.get(vid)


def _make_test_image(width=64, height=64) -> bytes:
    """Create a simple test image as bytes."""
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    arr[:, :width // 3, 0] = 255  # Red
    arr[:, width // 3 : 2 * width // 3, 1] = 255  # Green
    arr[:, 2 * width // 3 :, 2] = 255  # Blue
    img = Image.fromarray(arr)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


# ---------------------------------------------------------------------------
# NowPlayingTrack tests
# ---------------------------------------------------------------------------


class TestNowPlayingTrack:
    def test_signature_stable(self):
        track = NowPlayingTrack(
            provider="test",
            title="Song",
            artist="Artist",
            album="Album",
            player_name="Spotify",
        )
        sig1 = track.signature()
        sig2 = track.signature()
        assert sig1 == sig2

    def test_signature_changes_on_title_change(self):
        t1 = NowPlayingTrack(provider="test", title="Song A", artist="Art")
        t2 = NowPlayingTrack(provider="test", title="Song B", artist="Art")
        assert t1.signature() != t2.signature()

    def test_signature_same_for_same_track(self):
        t1 = NowPlayingTrack(
            provider="test", title="X", artist="Y", album="Z"
        )
        t2 = NowPlayingTrack(
            provider="test", title="X", artist="Y", album="Z"
        )
        assert t1.signature() == t2.signature()

    def test_art_signature_changes_with_url(self):
        t1 = NowPlayingTrack(provider="test", art_url="http://a.com/1.jpg")
        t2 = NowPlayingTrack(provider="test", art_url="http://a.com/2.jpg")
        assert t1.art_signature() != t2.art_signature()

    def test_art_signature_none_is_stable(self):
        t1 = NowPlayingTrack(provider="test", art_url=None)
        t2 = NowPlayingTrack(provider="test", art_url=None)
        assert t1.art_signature() == t2.art_signature()

    def test_to_dict(self):
        track = NowPlayingTrack(
            provider="test",
            title="Song",
            artist="Artist",
            is_playing=True,
        )
        d = track.to_dict()
        assert d["provider"] == "test"
        assert d["title"] == "Song"
        assert d["is_playing"] is True
        assert "raw" not in d


# ---------------------------------------------------------------------------
# NowPlayingState tests
# ---------------------------------------------------------------------------


class TestNowPlayingState:
    def test_default_state(self):
        state = NowPlayingState()
        assert state.enabled is False
        assert state.status == "disabled"
        assert state.active_track is None

    def test_to_dict(self):
        state = NowPlayingState(enabled=True, status="running")
        d = state.to_dict()
        assert d["enabled"] is True
        assert d["status"] == "running"
        assert d["active_track"] is None

    def test_to_dict_with_track(self):
        track = NowPlayingTrack(provider="test", title="Hello")
        state = NowPlayingState(
            enabled=True, status="running", active_track=track
        )
        d = state.to_dict()
        assert d["active_track"]["title"] == "Hello"


# ---------------------------------------------------------------------------
# NowPlayingManager tests
# ---------------------------------------------------------------------------


class TestNowPlayingManagerDisabled:
    @pytest.mark.asyncio
    async def test_start_disabled(self):
        ledfx = _DummyLedFx(config={"now_playing": {"enabled": False}})
        mgr = NowPlayingManager(ledfx)
        await mgr.start()
        assert mgr.state.status == "disabled"
        assert mgr.state.enabled is False

    @pytest.mark.asyncio
    async def test_start_missing_config(self):
        ledfx = _DummyLedFx(config={})
        mgr = NowPlayingManager(ledfx)
        await mgr.start()
        assert mgr.state.status == "disabled"


class TestNowPlayingManagerDedupe:
    @pytest.mark.asyncio
    async def test_duplicate_track_ignored(self):
        ledfx = _DummyLedFx(
            config={"now_playing": {"enabled": True, "provider": "platform_media"}}
        )
        mgr = NowPlayingManager(ledfx)

        track = NowPlayingTrack(
            provider="test", title="Song", artist="Artist"
        )

        # First call should trigger event
        await mgr._on_track_update(track)
        assert len(ledfx.events.fired) == 1
        assert isinstance(ledfx.events.fired[0], NowPlayingUpdatedEvent)

        # Second identical call should be ignored
        await mgr._on_track_update(track)
        assert len(ledfx.events.fired) == 1

    @pytest.mark.asyncio
    async def test_different_track_triggers_event(self):
        ledfx = _DummyLedFx(
            config={"now_playing": {"enabled": True, "provider": "platform_media"}}
        )
        mgr = NowPlayingManager(ledfx)

        t1 = NowPlayingTrack(provider="test", title="Song A", artist="Art")
        t2 = NowPlayingTrack(provider="test", title="Song B", artist="Art")

        await mgr._on_track_update(t1)
        await mgr._on_track_update(t2)
        assert len(ledfx.events.fired) == 2

    @pytest.mark.asyncio
    async def test_playing_state_change_triggers_update(self):
        ledfx = _DummyLedFx(
            config={"now_playing": {"enabled": True, "provider": "platform_media"}}
        )
        mgr = NowPlayingManager(ledfx)

        t1 = NowPlayingTrack(
            provider="test", title="Song", artist="Art", is_playing=True
        )
        t2 = NowPlayingTrack(
            provider="test", title="Song", artist="Art", is_playing=False
        )

        await mgr._on_track_update(t1)
        # Playing state changed but signature is same - should still update state
        await mgr._on_track_update(t2)
        assert mgr.state.active_track.is_playing is False


class TestNowPlayingManagerArtCache:
    @pytest.mark.asyncio
    async def test_art_cache_bounded(self):
        ledfx = _DummyLedFx(
            config={
                "now_playing": {
                    "enabled": True,
                    "art_cache": True,
                    "art_cache_max_items": 3,
                }
            }
        )
        mgr = NowPlayingManager(ledfx)

        # Manually fill cache beyond limit
        for i in range(5):
            mgr._art_cache[f"key_{i}"] = b"data"
            if len(mgr._art_cache) > 3:
                mgr._art_cache.popitem(last=False)

        assert len(mgr._art_cache) == 3
        assert "key_0" not in mgr._art_cache
        assert "key_4" in mgr._art_cache


class TestNowPlayingManagerGradientApply:
    def test_apply_gradient_to_gradient_effects(self):
        gradient_effect = _DummyGradientEffect("bars")
        non_gradient_effect = _DummyNonGradientEffect("strobe")

        virtuals = {
            "v1": _DummyVirtual("v1", gradient_effect),
            "v2": _DummyVirtual("v2", non_gradient_effect),
        }
        ledfx = _DummyLedFx(
            config={"now_playing": {"enabled": True}},
            virtuals=virtuals,
        )
        mgr = NowPlayingManager(ledfx)

        test_gradient = "linear-gradient(90deg, rgb(255,0,0) 0%, rgb(0,255,0) 100%)"

        with patch(
            "ledfx.effects.gradient.GradientEffect",
            new=type(gradient_effect),
        ):
            affected, skipped = mgr._apply_gradient_to_effects(test_gradient)

        assert len(affected) == 1
        assert "v1:bars" in affected[0]
        assert gradient_effect._config["gradient"] == test_gradient

    def test_apply_gradient_skips_dummy_effects(self):
        from ledfx.effects import DummyEffect

        dummy = DummyEffect(10)
        virtuals = {"v1": _DummyVirtual("v1", dummy)}
        ledfx = _DummyLedFx(
            config={"now_playing": {"enabled": True}},
            virtuals=virtuals,
        )
        mgr = NowPlayingManager(ledfx)

        affected, skipped = mgr._apply_gradient_to_effects("test_gradient")
        assert len(affected) == 0
        assert len(skipped) == 0

    def test_apply_gradient_skips_none_effects(self):
        virtuals = {"v1": _DummyVirtual("v1", None)}
        ledfx = _DummyLedFx(
            config={"now_playing": {"enabled": True}},
            virtuals=virtuals,
        )
        mgr = NowPlayingManager(ledfx)

        affected, skipped = mgr._apply_gradient_to_effects("test_gradient")
        assert len(affected) == 0
        assert len(skipped) == 0


class TestNowPlayingManagerPalette:
    @pytest.mark.asyncio
    async def test_palette_extraction_from_art(self):
        """Test that palette extraction works with real image data."""
        ledfx = _DummyLedFx(
            config={
                "now_playing": {
                    "enabled": True,
                    "generate_palette_from_album_art": True,
                    "apply_palette_to_running_effects": False,
                    "gradient_variant": "led_punchy",
                }
            }
        )
        mgr = NowPlayingManager(ledfx)

        art_bytes = _make_test_image()
        track = NowPlayingTrack(provider="test", title="Song", artist="Art")
        sig = track.signature()

        await mgr._generate_and_apply_palette(
            art_bytes, track, sig, ledfx.config["now_playing"], time.time()
        )

        # Should have emitted palette event
        palette_events = [
            e
            for e in ledfx.events.fired
            if isinstance(e, NowPlayingPaletteUpdatedEvent)
        ]
        assert len(palette_events) == 1
        assert palette_events[0].gradient is not None
        assert "linear-gradient" in palette_events[0].gradient
        assert mgr.state.active_gradient is not None


# ---------------------------------------------------------------------------
# Event class tests
# ---------------------------------------------------------------------------


class TestNowPlayingEvents:
    def test_now_playing_updated_event(self):
        event = NowPlayingUpdatedEvent(
            provider="test",
            title="Song",
            artist="Artist",
            album="Album",
            art_url=None,
            is_playing=True,
            duration=180.0,
            position=42.0,
            player_name="Spotify",
            track_signature="abc123",
            timestamp=1000.0,
        )
        assert event.event_type == Event.NOW_PLAYING_UPDATED
        assert event.title == "Song"
        d = event.to_dict()
        assert d["title"] == "Song"
        assert d["provider"] == "test"

    def test_now_playing_art_updated_event(self):
        event = NowPlayingArtUpdatedEvent(
            provider="test",
            track_signature="abc123",
            art_url="http://example.com/art.jpg",
            art_cache_key="key123",
            timestamp=1000.0,
        )
        assert event.event_type == Event.NOW_PLAYING_ART_UPDATED
        assert event.art_url == "http://example.com/art.jpg"

    def test_now_playing_palette_updated_event(self):
        event = NowPlayingPaletteUpdatedEvent(
            provider="test",
            track_signature="abc123",
            gradient="linear-gradient(90deg, rgb(255,0,0) 0%, rgb(0,0,255) 100%)",
            palette_applied=True,
            affected_effects=["v1:bars"],
            skipped_effects=["v2:strobe"],
            timestamp=1000.0,
        )
        assert event.event_type == Event.NOW_PLAYING_PALETTE_UPDATED
        assert event.palette_applied is True
        assert len(event.affected_effects) == 1


# ---------------------------------------------------------------------------
# Provider contract tests
# ---------------------------------------------------------------------------


class TestProviderContract:
    def test_provider_has_correct_interface(self):
        """Verify the platform provider satisfies the protocol."""
        from ledfx.nowplaying.providers.platform_media_provider import (
            PlatformMediaProvider,
        )

        provider = PlatformMediaProvider(poll_interval=1.0)
        assert hasattr(provider, "start")
        assert hasattr(provider, "stop")
        assert callable(provider.start)
        assert callable(provider.stop)
