"""Unit tests for the Now Playing Service (Phase 1 + Phase 3 events + Phase 5 artwork + Phase 6 gradient application + Phase 7 configuration)."""

import io
import os
import time
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image
from pydantic import ValidationError

from ledfx.configuration.fields import VirtualIdStr
from ledfx.configuration.plugin import PluginConfig
from ledfx.effects import DummyEffect, Effect
from ledfx.events import Event
from ledfx.nowplaying.models import (
    ArtworkReference,
    NowPlayingState,
    TrackMetadata,
)
from ledfx.nowplaying.service import NowPlayingService
from tests.test_utilities.fake_ledfx import fake_ledfx
from tests.test_utilities.virtuals_core import enter_safe_mode, running_core


class _DummyEvents:
    """Minimal events system stub that records fired events."""

    def __init__(self):
        self.fired = []

    def fire_event(self, event):
        self.fired.append(event)


class _DummyLedFx:
    """Minimal LedFx core stub for testing."""

    def __init__(self, config_dir=None):
        fake = fake_ledfx()
        self.config = fake.config
        self.config_store = fake.config_store
        self.events = _DummyEvents()
        self.config_dir = config_dir


def _make_test_png(width=4, height=4):
    """Create minimal valid PNG bytes for testing."""
    img = Image.new("RGB", (width, height), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def _make_test_jpeg(width=4, height=4):
    """Create minimal valid JPEG bytes for testing."""
    img = Image.new("RGB", (width, height), color=(0, 255, 0))
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


@pytest.fixture
def ledfx(tmp_path):
    return _DummyLedFx(config_dir=str(tmp_path))


@pytest.fixture
def service(ledfx):
    return NowPlayingService(ledfx)


# ------------------------------------------------------------------
# TrackMetadata model tests
# ------------------------------------------------------------------


class TestTrackMetadata:
    def test_track_identity_tuple(self):
        meta = TrackMetadata(
            source_id="test",
            title="Song",
            artist="Artist",
            album="Album",
            track_id="id-1",
        )
        assert meta.track_identity() == ("Song", "Artist", "Album", "id-1")

    def test_track_identity_with_none_fields(self):
        meta = TrackMetadata(source_id="test", title="Song")
        assert meta.track_identity() == ("Song", None, None, None)

    def test_to_dict_roundtrip(self):
        meta = TrackMetadata(
            source_id="sendspin",
            title="Track",
            artist="Artist",
            album="Album",
            track_id="t1",
            artwork_url="https://example.com/art.jpg",
            artwork_hash="abc123",
            updated_at=1000.0,
        )
        d = meta.to_dict()
        assert d["source_id"] == "sendspin"
        assert d["title"] == "Track"
        assert d["artist"] == "Artist"
        assert d["artwork_hash"] == "abc123"


# ------------------------------------------------------------------
# ArtworkReference model tests
# ------------------------------------------------------------------


class TestArtworkReference:
    def test_to_dict(self):
        art = ArtworkReference(
            source_id="sendspin",
            url="https://example.com/art.jpg",
            cache_key="key123",
            content_type="image/jpeg",
            hash="abc",
            width=500,
            height=500,
            gradients={"led_punchy": {"gradient": "linear-gradient(...)"}},
        )
        d = art.to_dict()
        assert d["url"] == "https://example.com/art.jpg"
        assert d["width"] == 500
        assert d["gradients"]["led_punchy"]["gradient"] == "linear-gradient(...)"


# ------------------------------------------------------------------
# NowPlayingState model tests
# ------------------------------------------------------------------


class TestNowPlayingState:
    def test_default_state(self):
        state = NowPlayingState()
        assert state.active_source_id is None
        assert state.metadata is None
        assert state.artwork is None
        assert state.selected_gradient_variant == "led_punchy"
        assert state.current_gradient is None

    def test_to_dict_empty(self):
        state = NowPlayingState()
        d = state.to_dict()
        assert d["active_source_id"] is None
        assert d["metadata"] is None
        assert d["artwork"] is None
        assert d["selected_gradient_variant"] == "led_punchy"

    def test_to_dict_with_data(self):
        state = NowPlayingState(
            active_source_id="sendspin",
            metadata=TrackMetadata(source_id="sendspin", title="Song"),
            selected_gradient_variant="led_max",
        )
        d = state.to_dict()
        assert d["active_source_id"] == "sendspin"
        assert d["metadata"]["title"] == "Song"
        assert d["selected_gradient_variant"] == "led_max"


# ------------------------------------------------------------------
# NowPlayingService tests
# ------------------------------------------------------------------


class TestNowPlayingServiceSetMetadata:
    def test_first_metadata_sets_active_source(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song 1")
        service.set_metadata("sendspin", meta)

        state = service.get_current()
        assert state.active_source_id == "sendspin"
        assert state.metadata.title == "Song 1"

    def test_first_metadata_returns_track_changed(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song 1")
        result = service.set_metadata("sendspin", meta)
        assert result is True

    def test_same_metadata_returns_no_change(self, service):
        meta = TrackMetadata(
            source_id="sendspin",
            title="Song",
            artist="Artist",
            album="Album",
            track_id="t1",
        )
        service.set_metadata("sendspin", meta)

        # Same track identity — re-sending same metadata is not a track change
        meta2 = TrackMetadata(
            source_id="sendspin",
            title="Song",
            artist="Artist",
            album="Album",
            track_id="t1",
        )
        result = service.set_metadata("sendspin", meta2)
        assert result is False

    def test_different_track_returns_change(self, service):
        meta1 = TrackMetadata(source_id="sendspin", title="Song 1", artist="A")
        service.set_metadata("sendspin", meta1)

        meta2 = TrackMetadata(source_id="sendspin", title="Song 2", artist="A")
        result = service.set_metadata("sendspin", meta2)
        assert result is True

    def test_inactive_source_ignored(self, service):
        # Set active source to sendspin
        meta1 = TrackMetadata(source_id="sendspin", title="Song 1")
        service.set_metadata("sendspin", meta1)

        # Try to update from a different source
        meta2 = TrackMetadata(source_id="spotify", title="Other Song")
        result = service.set_metadata("spotify", meta2)

        assert result is False
        assert service.get_current().metadata.title == "Song 1"

    def test_metadata_updated_at_is_set(self, service):
        before = time.time()
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)
        after = time.time()

        assert meta.updated_at >= before
        assert meta.updated_at <= after


class TestNowPlayingServiceSetArtworkUrl:
    def test_artwork_url_stored(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        png_data = _make_test_png()
        with patch.object(
            service, "_download_image", return_value=(png_data, "image/png")
        ):
            result = service.set_artwork_url(
                "sendspin",
                "https://example.com/art.png",
                content_type="image/png",
                artwork_hash="hash1",
            )
        assert result is True

        state = service.get_current()
        assert state.artwork.url == "https://example.com/art.png"
        assert state.artwork.hash == "hash1"
        assert state.artwork.content_type == "image/png"
        assert state.artwork.width == 4
        assert state.artwork.height == 4

    def test_same_artwork_url_no_change(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        png_data = _make_test_png()
        with patch.object(
            service, "_download_image", return_value=(png_data, "image/png")
        ):
            service.set_artwork_url(
                "sendspin", "https://example.com/art.png", artwork_hash="h1"
            )
            result = service.set_artwork_url(
                "sendspin", "https://example.com/art.png", artwork_hash="h1"
            )
        assert result is False

    def test_different_artwork_url_is_change(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        png_data = _make_test_png()
        with patch.object(
            service, "_download_image", return_value=(png_data, "image/png")
        ):
            service.set_artwork_url(
                "sendspin", "https://example.com/art1.png", artwork_hash="h1"
            )
            result = service.set_artwork_url(
                "sendspin", "https://example.com/art2.png", artwork_hash="h2"
            )
        assert result is True

    def test_inactive_source_rejected(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        result = service.set_artwork_url("spotify", "https://example.com/art.png")
        assert result is False
        assert service.get_current().artwork is None

    def test_download_failure_returns_false(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        with patch.object(service, "_download_image", return_value=(None, None)):
            result = service.set_artwork_url("sendspin", "https://example.com/art.png")
        assert result is False
        assert service.get_current().artwork is None


class TestNowPlayingServiceSetArtworkBytes:
    def test_artwork_bytes_stored(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        data = _make_test_png()
        result = service.set_artwork_bytes("sendspin", data, "image/png")
        assert result is True

        state = service.get_current()
        assert state.artwork.cache_key is not None
        assert "now_playing" in state.artwork.cache_key
        assert state.artwork.content_type == "image/png"
        assert state.artwork.hash is not None
        assert state.artwork.width == 4
        assert state.artwork.height == 4

    def test_same_bytes_no_change(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        data = _make_test_png()
        service.set_artwork_bytes("sendspin", data, "image/png")
        result = service.set_artwork_bytes("sendspin", data, "image/png")
        assert result is False

    def test_explicit_hash_used(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        data = _make_test_png()
        service.set_artwork_bytes(
            "sendspin", data, "image/png", artwork_hash="custom_hash"
        )

        state = service.get_current()
        assert state.artwork.hash == "custom_hash"

    def test_artwork_file_written_to_disk(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        data = _make_test_png()
        service.set_artwork_bytes("sendspin", data, "image/png")

        artwork_path = os.path.join(
            ledfx.config_dir, "assets", "now_playing", "now_playing.png"
        )
        assert os.path.exists(artwork_path)
        with open(artwork_path, "rb") as f:
            assert f.read() == data

    def test_artwork_file_overwritten_on_change(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        # First: PNG
        png_data = _make_test_png()
        service.set_artwork_bytes("sendspin", png_data, "image/png")
        png_path = os.path.join(
            ledfx.config_dir, "assets", "now_playing", "now_playing.png"
        )
        assert os.path.exists(png_path)

        # Second: JPEG (different extension) — service tracks new path
        jpeg_data = _make_test_jpeg()
        service.set_artwork_bytes("sendspin", jpeg_data, "image/jpeg")
        jpg_path = os.path.join(
            ledfx.config_dir, "assets", "now_playing", "now_playing.jpg"
        )
        assert os.path.exists(jpg_path)
        # Service state points to the new JPEG
        state = service.get_current()
        assert state.artwork.cache_key == jpg_path


class TestNowPlayingServiceClear:
    def test_clear_active_source_resets_state(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        service.clear("sendspin")

        state = service.get_current()
        assert state.active_source_id is None
        assert state.metadata is None
        assert state.artwork is None

    def test_clear_inactive_source_no_effect(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        service.clear("spotify")

        state = service.get_current()
        assert state.metadata.title == "Song"


class TestNowPlayingServiceGetCurrent:
    def test_initial_state_is_empty(self, service):
        state = service.get_current()
        assert state.active_source_id is None
        assert state.metadata is None
        assert state.artwork is None
        assert state.selected_gradient_variant == "led_punchy"

    def test_get_current_returns_live_state(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Live Song")
        service.set_metadata("sendspin", meta)

        state = service.get_current()
        assert state.metadata.title == "Live Song"


# ------------------------------------------------------------------
# Event emission tests (Phase 3)
# ------------------------------------------------------------------


class TestNowPlayingServiceEvents:
    """Verify correct events are fired by the service."""

    def test_metadata_changed_event_fired(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song", artist="Artist")
        service.set_metadata("sendspin", meta)

        events = ledfx.events.fired
        metadata_events = [
            e for e in events if e.event_type == Event.NOW_PLAYING_METADATA_CHANGED
        ]
        assert len(metadata_events) == 1
        assert metadata_events[0].source_id == "sendspin"
        assert metadata_events[0].metadata["title"] == "Song"

    def test_track_changed_event_on_new_track(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song 1", artist="A")
        service.set_metadata("sendspin", meta)

        events = ledfx.events.fired
        track_events = [
            e for e in events if e.event_type == Event.NOW_PLAYING_TRACK_CHANGED
        ]
        assert len(track_events) == 1
        assert track_events[0].title == "Song 1"
        assert track_events[0].artist == "A"

    def test_no_track_changed_event_on_same_track(self, service, ledfx):
        meta = TrackMetadata(
            source_id="sendspin", title="Song", artist="A", track_id="t1"
        )
        service.set_metadata("sendspin", meta)
        ledfx.events.fired.clear()

        # Re-send the same metadata — no track change expected
        service.set_metadata("sendspin", meta)

        track_events = [
            e
            for e in ledfx.events.fired
            if e.event_type == Event.NOW_PLAYING_TRACK_CHANGED
        ]
        assert len(track_events) == 0

    def test_track_changed_event_on_different_track(self, service, ledfx):
        meta1 = TrackMetadata(source_id="sendspin", title="Song 1", artist="A")
        service.set_metadata("sendspin", meta1)
        ledfx.events.fired.clear()

        meta2 = TrackMetadata(source_id="sendspin", title="Song 2", artist="B")
        service.set_metadata("sendspin", meta2)

        track_events = [
            e
            for e in ledfx.events.fired
            if e.event_type == Event.NOW_PLAYING_TRACK_CHANGED
        ]
        assert len(track_events) == 1
        assert track_events[0].title == "Song 2"
        assert track_events[0].artist == "B"

    def test_artwork_changed_event_on_url(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)
        ledfx.events.fired.clear()

        png_data = _make_test_png()
        with patch.object(
            service, "_download_image", return_value=(png_data, "image/png")
        ):
            service.set_artwork_url(
                "sendspin", "https://example.com/art.png", artwork_hash="h1"
            )

        artwork_events = [
            e
            for e in ledfx.events.fired
            if e.event_type == Event.NOW_PLAYING_ARTWORK_CHANGED
        ]
        assert len(artwork_events) == 1
        assert artwork_events[0].source_id == "sendspin"
        assert artwork_events[0].artwork["url"] == "https://example.com/art.png"

    def test_artwork_changed_event_on_bytes(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)
        ledfx.events.fired.clear()

        data = _make_test_png()
        service.set_artwork_bytes("sendspin", data, "image/png")

        artwork_events = [
            e
            for e in ledfx.events.fired
            if e.event_type == Event.NOW_PLAYING_ARTWORK_CHANGED
        ]
        assert len(artwork_events) == 1
        assert artwork_events[0].artwork["content_type"] == "image/png"

    def test_no_artwork_event_when_unchanged(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        png_data = _make_test_png()
        with patch.object(
            service, "_download_image", return_value=(png_data, "image/png")
        ):
            service.set_artwork_url(
                "sendspin", "https://example.com/art.png", artwork_hash="h1"
            )
            ledfx.events.fired.clear()

            # Same artwork again
            service.set_artwork_url(
                "sendspin", "https://example.com/art.png", artwork_hash="h1"
            )

        artwork_events = [
            e
            for e in ledfx.events.fired
            if e.event_type == Event.NOW_PLAYING_ARTWORK_CHANGED
        ]
        assert len(artwork_events) == 0

    def test_cleared_event_on_active_source(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)
        ledfx.events.fired.clear()

        service.clear("sendspin")

        cleared_events = [
            e for e in ledfx.events.fired if e.event_type == Event.NOW_PLAYING_CLEARED
        ]
        assert len(cleared_events) == 1
        assert cleared_events[0].source_id == "sendspin"

    def test_no_cleared_event_on_inactive_source(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)
        ledfx.events.fired.clear()

        service.clear("spotify")

        cleared_events = [
            e for e in ledfx.events.fired if e.event_type == Event.NOW_PLAYING_CLEARED
        ]
        assert len(cleared_events) == 0

    def test_no_events_from_inactive_source(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)
        ledfx.events.fired.clear()

        # Try from inactive source
        meta2 = TrackMetadata(source_id="spotify", title="Other")
        service.set_metadata("spotify", meta2)

        assert len(ledfx.events.fired) == 0


# ------------------------------------------------------------------
# Gradient application tests (Phase 6)
# ------------------------------------------------------------------


GRADIENT = "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
BIRD = VirtualIdStr("dj bird")
MATRIX = VirtualIdStr("matrix")
EMPTY = VirtualIdStr("empty")  # no segments: refuses every effect


@pytest.fixture
def ledfx_with_virtuals(tmp_path, monkeypatch):
    """A core running the real Virtuals and Effects managers."""
    for core in running_core(monkeypatch):
        core.events.fired = list[object]()
        core.events.fire_event.side_effect = core.events.fired.append
        core.config_dir = str(tmp_path)
        core.audio = MagicMock(_audio_stream_active=True)
        yield core


@pytest.fixture
def service_v(ledfx_with_virtuals):
    svc = NowPlayingService(ledfx_with_virtuals)
    svc.set_metadata("sendspin", TrackMetadata(source_id="sendspin", title="T"))
    return svc


def _start(core: MagicMock, virtual_id: str, type_id: str) -> Effect:
    core.virtuals.set_effect(virtual_id, type_id, PluginConfig.model_validate({}))
    return core.virtuals.get_or_raise(virtual_id).active_effect


def _running(core: MagicMock, virtual_id: str) -> str:
    effect = core.virtuals.get_or_raise(virtual_id).active_effect
    return "" if effect is None or isinstance(effect, DummyEffect) else effect.type


def _png_with_gradient(service: NowPlayingService, data: bytes | None = None) -> None:
    with patch(
        "ledfx.nowplaying.service.extract_gradient_metadata",
        return_value={"led_punchy": {"gradient": GRADIENT}},
    ):
        service.set_artwork_bytes("sendspin", data or _make_test_png(), "image/png")


class TestGradientApplicationConfig:
    """Tests for gradient config properties."""

    def test_default_gradient_enabled(self, service):
        assert service.gradient_enabled is False

    def test_set_gradient_enabled(self, service):
        service.gradient_enabled = False
        assert service.gradient_enabled is False

    def test_default_gradient_virtual_ids_empty(self, service):
        assert service.gradient_virtual_ids == []

    def test_set_gradient_virtual_ids(self, service):
        service.gradient_virtual_ids = ["v1", "v2"]
        assert service.gradient_virtual_ids == ["v1", "v2"]

    def test_gradient_virtual_ids_returns_copy(self, service):
        service.gradient_virtual_ids = ["v1"]
        ids = service.gradient_virtual_ids
        ids.append("v2")
        assert service.gradient_virtual_ids == ["v1"]


class TestApplyGradientToVirtuals:
    """Tests for apply_gradient_to_virtuals(), which goes through the manager."""

    def test_no_gradient_returns_zero(self, service_v):
        assert service_v.apply_gradient_to_virtuals() == 0

    def test_applies_gradient_to_single_effect(self, service_v, ledfx_with_virtuals):
        eff = _start(ledfx_with_virtuals, BIRD, "gradient")
        before = eff.config.as_dict()["gradient"]
        service_v._state.current_gradient = GRADIENT

        assert service_v.apply_gradient_to_virtuals() == 1
        assert eff.config.as_dict()["gradient"] != before

    def test_applies_to_multiple_virtuals(self, service_v, ledfx_with_virtuals):
        _start(ledfx_with_virtuals, BIRD, "gradient")
        _start(ledfx_with_virtuals, MATRIX, "gradient")
        service_v._state.current_gradient = GRADIENT

        assert service_v.apply_gradient_to_virtuals() == 2

    def test_skips_virtual_without_effect(self, service_v, ledfx_with_virtuals):
        service_v._state.current_gradient = GRADIENT
        assert service_v.apply_gradient_to_virtuals() == 0

    def test_filters_by_virtual_ids(self, service_v, ledfx_with_virtuals):
        bird = _start(ledfx_with_virtuals, BIRD, "gradient")
        matrix = _start(ledfx_with_virtuals, MATRIX, "gradient")
        before = matrix.config.as_dict()["gradient"]
        service_v.gradient_virtual_ids = [BIRD]
        service_v._state.current_gradient = GRADIENT

        assert service_v.apply_gradient_to_virtuals() == 1
        assert bird.config.as_dict()["gradient"] != before
        assert matrix.config.as_dict()["gradient"] == before

    def test_empty_virtual_ids_means_all(self, service_v, ledfx_with_virtuals):
        _start(ledfx_with_virtuals, BIRD, "gradient")
        _start(ledfx_with_virtuals, MATRIX, "gradient")
        service_v.gradient_virtual_ids = []
        service_v._state.current_gradient = GRADIENT

        assert service_v.apply_gradient_to_virtuals() == 2

    def test_unknown_configured_ids_are_dropped(self, service_v, ledfx_with_virtuals):
        matrix = _start(ledfx_with_virtuals, MATRIX, "gradient")
        before = matrix.config.as_dict()["gradient"]
        service_v.gradient_virtual_ids = ["ghost"]
        service_v._state.current_gradient = GRADIENT

        assert service_v.apply_gradient_to_virtuals() == 0
        assert matrix.config.as_dict()["gradient"] == before

    def test_unknown_ids_do_not_stop_the_known_ones(
        self, service_v, ledfx_with_virtuals
    ):
        _start(ledfx_with_virtuals, BIRD, "gradient")
        service_v.gradient_virtual_ids = ["ghost", BIRD]
        service_v._state.current_gradient = GRADIENT

        assert service_v.apply_gradient_to_virtuals() == 1

    def test_saves_config_after_updates(self, service_v, ledfx_with_virtuals):
        _start(ledfx_with_virtuals, BIRD, "gradient")
        ledfx_with_virtuals.config_store.request_save.reset_mock()
        service_v._state.current_gradient = GRADIENT

        service_v.apply_gradient_to_virtuals()
        ledfx_with_virtuals.config_store.request_save.assert_called()

    def test_no_config_save_when_nothing_updated(self, service_v, ledfx_with_virtuals):
        ledfx_with_virtuals.config_store.request_save.reset_mock()
        service_v._state.current_gradient = GRADIENT

        service_v.apply_gradient_to_virtuals()
        ledfx_with_virtuals.config_store.request_save.assert_not_called()

    def test_safe_mode_changes_and_saves_nothing(self, service_v, ledfx_with_virtuals):
        eff = _start(ledfx_with_virtuals, BIRD, "gradient")
        before = eff.config.as_dict()["gradient"]
        enter_safe_mode(ledfx_with_virtuals)
        ledfx_with_virtuals.config_store.request_save.reset_mock()
        service_v._state.current_gradient = GRADIENT

        assert service_v.apply_gradient_to_virtuals() == 0
        assert eff.config.as_dict()["gradient"] == before
        ledfx_with_virtuals.config_store.request_save.assert_not_called()

    def test_a_bad_gradient_is_logged_not_raised(
        self, service_v, ledfx_with_virtuals, caplog
    ):
        _start(ledfx_with_virtuals, BIRD, "gradient")
        service_v._state.current_gradient = "nope("

        assert service_v.apply_gradient_to_virtuals() == 0
        assert "Failed to apply Now Playing gradient" in caplog.text

    def test_a_raising_effect_is_logged_not_raised(
        self, service_v, ledfx_with_virtuals, monkeypatch, caplog
    ):
        eff = _start(ledfx_with_virtuals, BIRD, "gradient")

        def bug(config: object) -> None:
            raise TypeError("bug")

        monkeypatch.setattr(eff, "update_config", bug)
        service_v._state.current_gradient = GRADIENT

        assert service_v.apply_gradient_to_virtuals() == 0
        assert "Failed to apply Now Playing gradient" in caplog.text


class TestGradientAutoApplication:
    """Tests verifying gradient is auto-applied when artwork changes."""

    def test_gradient_applied_on_artwork_bytes(self, service_v, ledfx_with_virtuals):
        eff = _start(ledfx_with_virtuals, BIRD, "gradient")
        before = eff.config.as_dict()["gradient"]
        service_v.gradient_enabled = True

        _png_with_gradient(service_v)

        assert eff.config.as_dict()["gradient"] != before

    def test_gradient_not_applied_when_disabled(self, service_v, ledfx_with_virtuals):
        eff = _start(ledfx_with_virtuals, BIRD, "gradient")
        before = eff.config.as_dict()["gradient"]
        service_v.gradient_enabled = False

        _png_with_gradient(service_v)

        assert eff.config.as_dict()["gradient"] == before

    def test_gradient_event_still_fires_when_disabled(
        self, service_v, ledfx_with_virtuals
    ):
        """Gradient changed event fires even when application is disabled."""
        service_v.gradient_enabled = False
        ledfx_with_virtuals.events.fired.clear()

        _png_with_gradient(service_v)

        gradient_events = [
            e
            for e in ledfx_with_virtuals.events.fired
            if e.event_type == Event.NOW_PLAYING_GRADIENT_CHANGED
        ]
        assert len(gradient_events) == 1


# ------------------------------------------------------------------
# Phase 7: Configuration persistence tests
# ------------------------------------------------------------------


class TestNowPlayingConfigSchema:
    """Tests for NowPlayingConfig validation."""

    def test_default_config_is_valid(self):
        from ledfx.configuration.models import NowPlayingConfig

        result = NowPlayingConfig.model_validate({}).model_dump()
        assert result["gradient"]["enabled"] is False
        assert result["gradient"]["variant"] == "led_punchy"
        assert result["gradient"]["virtual_ids"] == []
        assert result["track_text"]["enabled"] is True
        assert result["track_text"]["duration"] == 60
        assert result["track_text"]["virtual_ids"] == []
        assert result["track_text"]["preset"] == ""
        assert result["album_art"]["enabled"] is True
        assert result["album_art"]["duration"] == 10
        assert result["album_art"]["virtual_ids"] == []

    def test_invalid_variant_rejected(self):
        from ledfx.configuration.models import NowPlayingConfig

        with pytest.raises(ValidationError):
            NowPlayingConfig.model_validate(
                {"gradient": {"variant": "not_a_variant"}}
            ).model_dump()

    def test_invalid_enabled_rejected(self):
        from ledfx.configuration.models import NowPlayingConfig

        with pytest.raises(ValidationError):
            NowPlayingConfig.model_validate(
                {"track_text": {"enabled": "not_a_bool"}}
            ).model_dump()

    def test_duration_out_of_range(self):
        from ledfx.configuration.models import NowPlayingConfig

        with pytest.raises(ValidationError):
            NowPlayingConfig.model_validate(
                {"track_text": {"duration": -1}}
            ).model_dump()

        with pytest.raises(ValidationError):
            NowPlayingConfig.model_validate(
                {"album_art": {"duration": 999}}
            ).model_dump()

    def test_all_variants_accepted(self):
        from ledfx.configuration.models import NowPlayingConfig

        for v in ("led_safe", "led_punchy", "led_max"):
            result = NowPlayingConfig.model_validate(
                {"gradient": {"variant": v}}
            ).model_dump()
            assert result["gradient"]["variant"] == v

    def test_enabled_flag_accepted(self):
        from ledfx.configuration.models import NowPlayingConfig

        for v in (True, False):
            result = NowPlayingConfig.model_validate(
                {"track_text": {"enabled": v}}
            ).model_dump()
            assert result["track_text"]["enabled"] is v


class TestServiceConfigFromInit:
    """Tests that NowPlayingService loads config on init."""

    def test_default_config_loaded(self, service):
        cfg = service.config
        assert cfg["gradient"]["enabled"] is False
        assert cfg["gradient"]["variant"] == "led_punchy"
        assert cfg["gradient"]["virtual_ids"] == []
        assert cfg["track_text"]["enabled"] is True
        assert cfg["album_art"]["enabled"] is True

    def test_persisted_config_loaded(self, tmp_path):
        ldfx = _DummyLedFx(config_dir=str(tmp_path))
        ldfx.config = fake_ledfx(
            {
                "now_playing": {
                    "gradient": {
                        "enabled": False,
                        "variant": "led_max",
                        "virtual_ids": ["v1", "v2"],
                    },
                    "track_text": {
                        "enabled": False,
                        "duration": 5,
                        "virtual_ids": ["matrix1"],
                        "preset": "scroll_text",
                    },
                }
            }
        ).config
        svc = NowPlayingService(ldfx)

        assert svc.gradient_enabled is False
        assert svc.gradient_virtual_ids == ["v1", "v2"]
        assert svc.config["gradient"]["variant"] == "led_max"
        assert svc.config["track_text"]["enabled"] is False
        assert svc.config["track_text"]["duration"] == 5
        assert svc.config["track_text"]["virtual_ids"] == ["matrix1"]
        # album_art should be defaults since not specified
        assert svc.config["album_art"]["enabled"] is True

    def test_variant_applied_to_state(self, tmp_path):
        ldfx = _DummyLedFx(config_dir=str(tmp_path))
        ldfx.config = fake_ledfx(
            {
                "now_playing": {
                    "gradient": {"variant": "led_safe"},
                }
            }
        ).config
        svc = NowPlayingService(ldfx)
        assert svc.get_current().selected_gradient_variant == "led_safe"


class TestUpdateConfig:
    """Tests for update_config() method."""

    def test_partial_update_gradient(self, service, ledfx):
        result = service.update_config({"gradient": {"enabled": False}})
        assert result["gradient"]["enabled"] is False
        # Other gradient fields retain defaults
        assert result["gradient"]["variant"] == "led_punchy"
        assert result["gradient"]["virtual_ids"] == []
        assert service.gradient_enabled is False

    def test_partial_update_track_text(self, service, ledfx):
        result = service.update_config(
            {"track_text": {"enabled": False, "duration": 12}}
        )
        assert result["track_text"]["enabled"] is False
        assert result["track_text"]["duration"] == 12
        assert result["track_text"]["preset"] == ""

    def test_partial_update_album_art(self, service, ledfx):
        result = service.update_config(
            {"album_art": {"enabled": False, "virtual_ids": ["m1"]}}
        )
        assert result["album_art"]["enabled"] is False
        assert result["album_art"]["virtual_ids"] == ["m1"]

    def test_full_update(self, service, ledfx):
        new_cfg = {
            "gradient": {
                "enabled": False,
                "variant": "led_max",
                "virtual_ids": ["v1"],
            },
            "track_text": {
                "enabled": False,
                "duration": 6,
                "virtual_ids": ["m1"],
                "preset": "marquee",
            },
            "album_art": {
                "enabled": True,
                "duration": 15,
                "virtual_ids": ["m2"],
            },
        }
        result = service.update_config(new_cfg)

        assert result == new_cfg
        assert service.gradient_enabled is False
        assert service.gradient_virtual_ids == ["v1"]

    def test_invalid_config_raises(self, service):
        with pytest.raises(ValidationError):
            service.update_config({"gradient": {"variant": "bad"}})

    def test_config_persisted_to_disk(self, service, ledfx):
        service.update_config({"gradient": {"enabled": False}})
        ledfx.config_store.request_save.assert_called()

        assert ledfx.config.now_playing.gradient.enabled is False

    def test_variant_change_re_resolves_gradient(self, service, ledfx):
        """Changing variant re-resolves gradient from cached artwork."""
        from ledfx.nowplaying.models import ArtworkReference

        service._state.active_source_id = "test"
        service._state.artwork = ArtworkReference(
            source_id="test",
            gradients={
                "led_punchy": {
                    "gradient": "linear-gradient(90deg, rgb(255,0,0) 0%, rgb(0,0,255) 100%)"
                },
                "led_max": {
                    "gradient": "linear-gradient(90deg, rgb(0,255,0) 0%, rgb(255,0,255) 100%)"
                },
            },
        )
        # Start with led_punchy (default)
        service._update_current_gradient()
        assert "255,0,0" in service.get_current().current_gradient

        service.update_config({"gradient": {"variant": "led_max"}})

        assert "0,255,0" in service.get_current().current_gradient

    def test_variant_change_no_re_resolve_when_unchanged(self, service, ledfx):
        """No re-resolve when variant doesn't change."""
        with patch.object(service, "_update_current_gradient") as mock_update:
            service.update_config({"gradient": {"variant": "led_punchy"}})
            mock_update.assert_not_called()

    def test_update_preserves_unrelated_sections(self, service, ledfx):
        """Updating gradient section preserves track_text and album_art."""
        service.update_config({"track_text": {"enabled": False, "duration": 5}})
        service.update_config({"gradient": {"enabled": False}})

        cfg = service.config
        assert cfg["gradient"]["enabled"] is False
        assert cfg["track_text"]["enabled"] is False
        assert cfg["track_text"]["duration"] == 5


# ------------------------------------------------------------------
# Phase 9: Album artwork temporary display tests
# ------------------------------------------------------------------


def _enable(
    svc: NowPlayingService, section: str, ids: list[str], duration: float = 0
) -> None:
    svc._config[section]["enabled"] = True
    svc._config[section]["virtual_ids"] = list(ids)
    svc._config[section]["duration"] = duration


def _set_artwork_on_service(svc, cache_key="/tmp/now_playing.jpg"):
    """Directly set an ArtworkReference with a cache_key on the service."""
    svc._state.artwork = ArtworkReference(
        source_id="sendspin",
        cache_key=cache_key,
        content_type="image/jpeg",
    )


@pytest.fixture
def set_effect_spy(ledfx_with_virtuals, monkeypatch):
    """The manager's set_effect, recording its calls."""
    spy = MagicMock(wraps=ledfx_with_virtuals.virtuals.set_effect)
    monkeypatch.setattr(ledfx_with_virtuals.virtuals, "set_effect", spy)
    return spy


class TestApplyAlbumArtToVirtuals:
    """Tests for NowPlayingService._apply_album_art_to_virtuals()."""

    def test_disabled_returns_zero(self, service_v, ledfx_with_virtuals):
        _enable(service_v, "album_art", [BIRD])
        service_v._config["album_art"]["enabled"] = False
        _set_artwork_on_service(service_v)

        assert service_v._apply_album_art_to_virtuals() == 0
        assert _running(ledfx_with_virtuals, BIRD) == ""

    def test_empty_virtual_ids_returns_zero(self, service_v, ledfx_with_virtuals):
        _set_artwork_on_service(service_v)
        service_v._config["album_art"]["enabled"] = True

        assert service_v._apply_album_art_to_virtuals() == 0
        assert _running(ledfx_with_virtuals, BIRD) == ""

    def test_no_artwork_returns_zero(self, service_v):
        _enable(service_v, "album_art", [BIRD])
        service_v._state.artwork = None

        assert service_v._apply_album_art_to_virtuals() == 0

    def test_no_cache_key_returns_zero(self, service_v):
        _enable(service_v, "album_art", [BIRD])
        service_v._state.artwork = ArtworkReference(
            source_id="sendspin", cache_key=None
        )

        assert service_v._apply_album_art_to_virtuals() == 0

    def test_temporary_mode_uses_fallback(self, service_v, set_effect_spy):
        _enable(service_v, "album_art", [BIRD], duration=8)
        _set_artwork_on_service(service_v, "/tmp/art.jpg")

        assert service_v._apply_album_art_to_virtuals() == 1
        set_effect_spy.assert_called_once()
        assert set_effect_spy.call_args.kwargs["fallback"] == 8.0

    def test_permanent_mode_no_fallback(self, service_v, set_effect_spy):
        _enable(service_v, "album_art", [BIRD], duration=0)
        _set_artwork_on_service(service_v, "/tmp/art.jpg")

        assert service_v._apply_album_art_to_virtuals() == 1
        assert set_effect_spy.call_args.kwargs["fallback"] is None

    def test_goes_through_the_manager(self, service_v, set_effect_spy):
        """A service that starts effects on the Virtual directly (skipping the
        manager's checks) never reaches the manager's set_effect."""
        _enable(service_v, "album_art", [BIRD, MATRIX])
        _set_artwork_on_service(service_v)

        service_v._apply_album_art_to_virtuals()

        assert [c.args[0] for c in set_effect_spy.call_args_list] == [BIRD, MATRIX]

    def test_image_source_config_uses_cache_key(self, service_v, ledfx_with_virtuals):
        cache_key = "/config/assets/now_playing/now_playing.jpg"
        _enable(service_v, "album_art", [BIRD])
        _set_artwork_on_service(service_v, cache_key)

        service_v._apply_album_art_to_virtuals()

        effect = ledfx_with_virtuals.virtuals.get_or_raise(BIRD).active_effect
        assert effect.type == "imagespin"
        assert effect.config.as_dict()["image_source"] == cache_key

    def test_multiple_virtuals_updated(self, service_v, ledfx_with_virtuals):
        _enable(service_v, "album_art", [BIRD, MATRIX])
        _set_artwork_on_service(service_v)

        assert service_v._apply_album_art_to_virtuals() == 2
        assert _running(ledfx_with_virtuals, MATRIX) == "imagespin"

    def test_missing_virtual_skipped(self, service_v, ledfx_with_virtuals):
        _enable(service_v, "album_art", [BIRD, "missing"])
        _set_artwork_on_service(service_v)

        assert service_v._apply_album_art_to_virtuals() == 1

    def test_a_refusing_virtual_leaks_no_effect(self, service_v, ledfx_with_virtuals):
        """EMPTY has no segments: the manager refuses before it creates."""
        _enable(service_v, "album_art", [EMPTY, BIRD])
        _set_artwork_on_service(service_v)
        before = len(ledfx_with_virtuals.effects.values())

        assert service_v._apply_album_art_to_virtuals() == 1
        assert len(ledfx_with_virtuals.effects.values()) == before + 1

    def test_safe_mode_changes_and_saves_nothing(self, service_v, ledfx_with_virtuals):
        _enable(service_v, "album_art", [BIRD])
        _set_artwork_on_service(service_v)
        enter_safe_mode(ledfx_with_virtuals)
        ledfx_with_virtuals.config_store.request_save.reset_mock()

        assert service_v._apply_album_art_to_virtuals() == 0
        assert _running(ledfx_with_virtuals, BIRD) == ""
        ledfx_with_virtuals.config_store.request_save.assert_not_called()

    def test_an_unexpected_error_skips_only_that_virtual(
        self, service_v, ledfx_with_virtuals, monkeypatch, caplog
    ):
        _enable(service_v, "album_art", [BIRD, MATRIX])
        _set_artwork_on_service(service_v)
        real = ledfx_with_virtuals.virtuals.set_effect

        def flaky(virtual_id: str, *args: object, **kwargs: object) -> object:
            if virtual_id == BIRD:
                raise KeyError("bug")
            return real(virtual_id, *args, **kwargs)

        monkeypatch.setattr(ledfx_with_virtuals.virtuals, "set_effect", flaky)

        assert service_v._apply_album_art_to_virtuals() == 1
        assert "failed to set effect" in caplog.text


class TestApplyTrackTextToVirtuals:
    """Tests for NowPlayingService._apply_track_text_to_virtuals()."""

    def test_starts_texter_through_the_manager(
        self, service_v, ledfx_with_virtuals, set_effect_spy
    ):
        _enable(service_v, "track_text", [BIRD], duration=5)

        assert service_v._apply_track_text_to_virtuals() == 1
        effect = ledfx_with_virtuals.virtuals.get_or_raise(BIRD).active_effect
        assert effect.type == "texter2d"
        assert "T" in effect.config.as_dict()["text"]
        assert set_effect_spy.call_args.kwargs["fallback"] == 5.0

    def test_permanent_mode_no_fallback(self, service_v, set_effect_spy):
        _enable(service_v, "track_text", [BIRD], duration=0)

        service_v._apply_track_text_to_virtuals()

        assert set_effect_spy.call_args.kwargs["fallback"] is None

    def test_a_refusing_virtual_leaks_no_effect(self, service_v, ledfx_with_virtuals):
        _enable(service_v, "track_text", [EMPTY])
        before = len(ledfx_with_virtuals.effects.values())

        assert service_v._apply_track_text_to_virtuals() == 0
        assert len(ledfx_with_virtuals.effects.values()) == before

    def test_safe_mode_changes_and_saves_nothing(self, service_v, ledfx_with_virtuals):
        _enable(service_v, "track_text", [BIRD])
        enter_safe_mode(ledfx_with_virtuals)
        ledfx_with_virtuals.config_store.request_save.reset_mock()

        assert service_v._apply_track_text_to_virtuals() == 0
        assert _running(ledfx_with_virtuals, BIRD) == ""
        ledfx_with_virtuals.config_store.request_save.assert_not_called()


@pytest.mark.parametrize("duration", [0, 5])
@pytest.mark.parametrize("section", ["track_text", "album_art"])
def test_a_track_effect_is_not_stored(
    service_v: NowPlayingService,
    ledfx_with_virtuals: MagicMock,
    section: str,
    duration: float,
) -> None:
    """Track effects are temporary: none is stored or saved, so a restart
    brings back the virtual's own effect, not the last song's."""
    _start(ledfx_with_virtuals, BIRD, "rainbow")
    entry = ledfx_with_virtuals.virtuals.get_or_raise(BIRD).entry
    assert entry is not None
    before = entry.model_dump()
    ledfx_with_virtuals.config_store.request_save.reset_mock()
    _enable(service_v, section, [BIRD], duration)
    _set_artwork_on_service(service_v)
    apply = (
        service_v._apply_track_text_to_virtuals
        if section == "track_text"
        else service_v._apply_album_art_to_virtuals
    )

    assert apply() == 1
    assert _running(ledfx_with_virtuals, BIRD) in ("texter2d", "imagespin")
    assert entry.model_dump() == before
    ledfx_with_virtuals.config_store.request_save.assert_not_called()


class TestAlbumArtAutoApplication:
    """Tests that _apply_album_art_to_virtuals is triggered by artwork changes."""

    def _set_bytes(self, svc):
        with patch(
            "ledfx.nowplaying.service.extract_gradient_metadata", return_value={}
        ):
            svc.set_artwork_bytes("sendspin", _make_test_png(), "image/png")

    def test_called_on_set_artwork_bytes(self, service_v, ledfx_with_virtuals):
        _enable(service_v, "album_art", [BIRD])

        self._set_bytes(service_v)

        assert _running(ledfx_with_virtuals, BIRD) == "imagespin"

    def test_called_on_set_artwork_url(self, service_v, ledfx_with_virtuals):
        _enable(service_v, "album_art", [BIRD])

        with (
            patch.object(
                service_v,
                "_download_image",
                return_value=(_make_test_png(), "image/png"),
            ),
            patch(
                "ledfx.nowplaying.service.extract_gradient_metadata",
                return_value={},
            ),
        ):
            service_v.set_artwork_url("sendspin", "https://example.com/art.png")

        assert _running(ledfx_with_virtuals, BIRD) == "imagespin"

    def test_not_called_when_disabled(self, service_v, ledfx_with_virtuals):
        _enable(service_v, "album_art", [BIRD])
        service_v._config["album_art"]["enabled"] = False

        self._set_bytes(service_v)

        assert _running(ledfx_with_virtuals, BIRD) == ""

    def test_not_called_when_virtual_ids_empty(self, service_v, ledfx_with_virtuals):
        service_v._config["album_art"]["enabled"] = True

        self._set_bytes(service_v)

        assert _running(ledfx_with_virtuals, BIRD) == ""


class TestAlbumArtDurationSchema:
    """Tests that the duration=0 schema change works correctly."""

    def test_duration_zero_accepted_for_album_art(self):
        from ledfx.configuration.models import NowPlayingConfig

        result = NowPlayingConfig.model_validate(
            {"album_art": {"duration": 0}}
        ).model_dump()
        assert result["album_art"]["duration"] == 0

    def test_duration_negative_still_invalid_for_track_text(self):
        from ledfx.configuration.models import NowPlayingConfig

        with pytest.raises(ValidationError):
            NowPlayingConfig.model_validate(
                {"track_text": {"duration": -1}}
            ).model_dump()

    def test_album_art_duration_max_still_enforced(self):
        from ledfx.configuration.models import NowPlayingConfig

        with pytest.raises(ValidationError):
            NowPlayingConfig.model_validate(
                {"album_art": {"duration": 61}}
            ).model_dump()
