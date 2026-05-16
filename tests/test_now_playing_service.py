"""Unit tests for the Now Playing Service (Phase 1 + Phase 3 events + Phase 5 artwork + Phase 6 gradient application)."""

import io
import os
import time
from unittest.mock import MagicMock, patch

import pytest
import voluptuous as vol
from PIL import Image

from ledfx.effects import DummyEffect
from ledfx.events import Event
from ledfx.nowplaying.models import (
    ArtworkReference,
    NowPlayingState,
    TrackMetadata,
)
from ledfx.nowplaying.service import NowPlayingService


class _DummyEvents:
    """Minimal events system stub that records fired events."""

    def __init__(self):
        self.fired = []

    def fire_event(self, event):
        self.fired.append(event)


class _DummyLedFx:
    """Minimal LedFx core stub for testing."""

    def __init__(self, config_dir=None):
        self.config = {}
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
            duration=180.0,
            position=42.0,
            track_id="t1",
            artwork_url="https://example.com/art.jpg",
            artwork_hash="abc123",
            updated_at=1000.0,
        )
        d = meta.to_dict()
        assert d["source_id"] == "sendspin"
        assert d["title"] == "Track"
        assert d["artist"] == "Artist"
        assert d["duration"] == 180.0
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
        assert (
            d["gradients"]["led_punchy"]["gradient"] == "linear-gradient(...)"
        )


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

        # Same track identity
        meta2 = TrackMetadata(
            source_id="sendspin",
            title="Song",
            artist="Artist",
            album="Album",
            track_id="t1",
            position=30.0,  # position changed but track is the same
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

        result = service.set_artwork_url(
            "spotify", "https://example.com/art.png"
        )
        assert result is False
        assert service.get_current().artwork is None

    def test_download_failure_returns_false(self, service):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)

        with patch.object(
            service, "_download_image", return_value=(None, None)
        ):
            result = service.set_artwork_url(
                "sendspin", "https://example.com/art.png"
            )
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
        meta = TrackMetadata(
            source_id="sendspin", title="Song", artist="Artist"
        )
        service.set_metadata("sendspin", meta)

        events = ledfx.events.fired
        metadata_events = [
            e
            for e in events
            if e.event_type == Event.NOW_PLAYING_METADATA_CHANGED
        ]
        assert len(metadata_events) == 1
        assert metadata_events[0].source_id == "sendspin"
        assert metadata_events[0].metadata["title"] == "Song"

    def test_track_changed_event_on_new_track(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song 1", artist="A")
        service.set_metadata("sendspin", meta)

        events = ledfx.events.fired
        track_events = [
            e
            for e in events
            if e.event_type == Event.NOW_PLAYING_TRACK_CHANGED
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

        # Same track identity, only position changed
        meta2 = TrackMetadata(
            source_id="sendspin",
            title="Song",
            artist="A",
            track_id="t1",
            position=60.0,
        )
        service.set_metadata("sendspin", meta2)

        track_events = [
            e
            for e in ledfx.events.fired
            if e.event_type == Event.NOW_PLAYING_TRACK_CHANGED
        ]
        assert len(track_events) == 0

    def test_metadata_event_still_fires_on_position_update(
        self, service, ledfx
    ):
        meta = TrackMetadata(
            source_id="sendspin", title="Song", artist="A", track_id="t1"
        )
        service.set_metadata("sendspin", meta)
        ledfx.events.fired.clear()

        meta2 = TrackMetadata(
            source_id="sendspin",
            title="Song",
            artist="A",
            track_id="t1",
            position=30.0,
        )
        service.set_metadata("sendspin", meta2)

        metadata_events = [
            e
            for e in ledfx.events.fired
            if e.event_type == Event.NOW_PLAYING_METADATA_CHANGED
        ]
        assert len(metadata_events) == 1

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
        assert (
            artwork_events[0].artwork["url"] == "https://example.com/art.png"
        )

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
            e
            for e in ledfx.events.fired
            if e.event_type == Event.NOW_PLAYING_CLEARED
        ]
        assert len(cleared_events) == 1
        assert cleared_events[0].source_id == "sendspin"

    def test_no_cleared_event_on_inactive_source(self, service, ledfx):
        meta = TrackMetadata(source_id="sendspin", title="Song")
        service.set_metadata("sendspin", meta)
        ledfx.events.fired.clear()

        service.clear("spotify")

        cleared_events = [
            e
            for e in ledfx.events.fired
            if e.event_type == Event.NOW_PLAYING_CLEARED
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


def _make_mock_schema(*keys):
    """Create a voluptuous schema containing the given optional string keys."""
    schema_dict = {}
    for k in keys:
        schema_dict[vol.Optional(k, default="")] = str
    return vol.Schema(schema_dict)


def _make_mock_effect(schema_keys, hidden_keys=None, config=None):
    """Create a mock effect that mimics the Effect interface for apply_global."""
    eff = MagicMock()
    eff.HIDDEN_KEYS = hidden_keys or []
    eff._config = config or {}

    mock_schema = _make_mock_schema(*schema_keys)
    type(eff).schema = classmethod(lambda cls: mock_schema)
    return eff


def _make_mock_virtual(vid, effect=None):
    """Create a mock virtual with an id and optional active_effect."""
    virtual = MagicMock()
    virtual.id = vid
    virtual.active_effect = effect
    return virtual


class _MockGradients:
    """Minimal gradients collection stub."""

    def get_all(self):
        return {}, {}

    def __getitem__(self, key):
        raise KeyError(key)


class _DummyLedFxWithVirtuals(_DummyLedFx):
    """Extended stub that provides virtuals and gradients for Phase 6 tests."""

    def __init__(self, config_dir=None):
        super().__init__(config_dir)
        self._virtuals = {}
        self.gradients = _MockGradients()

    @property
    def virtuals(self):
        return self._virtuals


@pytest.fixture
def ledfx_with_virtuals(tmp_path):
    return _DummyLedFxWithVirtuals(config_dir=str(tmp_path))


@pytest.fixture
def service_v(ledfx_with_virtuals):
    return NowPlayingService(ledfx_with_virtuals)


class TestGradientApplicationConfig:
    """Tests for gradient config properties."""

    def test_default_gradient_enabled(self, service):
        assert service.gradient_enabled is True

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
    """Tests for apply_gradient_to_virtuals()."""

    def test_no_gradient_returns_zero(self, service_v):
        # No artwork set, no current_gradient
        assert service_v.apply_gradient_to_virtuals() == 0

    def test_no_virtuals_attribute_returns_zero(self, service):
        """Service without virtuals on ledfx returns 0."""
        # _DummyLedFx has no virtuals attribute
        service._state.current_gradient = (
            "linear-gradient(90deg, #ff0000, #0000ff)"
        )
        assert service.apply_gradient_to_virtuals() == 0

    def test_applies_gradient_to_single_effect(
        self, service_v, ledfx_with_virtuals
    ):
        # Set up a virtual with an effect that accepts 'gradient'
        eff = _make_mock_effect(["gradient", "color", "color_high"])
        v1 = _make_mock_virtual("v1", eff)
        ledfx_with_virtuals._virtuals["v1"] = v1

        # Set a valid gradient
        service_v._state.current_gradient = (
            "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
        )

        result = service_v.apply_gradient_to_virtuals()
        assert result == 1
        eff.update_config.assert_called_once()

        # Verify the config contains 'gradient' key
        call_args = eff.update_config.call_args[0][0]
        assert "gradient" in call_args

    def test_applies_to_multiple_virtuals(
        self, service_v, ledfx_with_virtuals
    ):
        eff1 = _make_mock_effect(["gradient", "color"])
        eff2 = _make_mock_effect(["gradient", "color_high"])
        v1 = _make_mock_virtual("v1", eff1)
        v2 = _make_mock_virtual("v2", eff2)
        ledfx_with_virtuals._virtuals["v1"] = v1
        ledfx_with_virtuals._virtuals["v2"] = v2

        service_v._state.current_gradient = (
            "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
        )

        result = service_v.apply_gradient_to_virtuals()
        assert result == 2

    def test_skips_dummy_effect(self, service_v, ledfx_with_virtuals):
        eff = DummyEffect(10)
        v1 = _make_mock_virtual("v1", eff)
        ledfx_with_virtuals._virtuals["v1"] = v1

        service_v._state.current_gradient = (
            "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
        )

        result = service_v.apply_gradient_to_virtuals()
        assert result == 0

    def test_skips_virtual_without_effect(
        self, service_v, ledfx_with_virtuals
    ):
        v1 = _make_mock_virtual("v1", None)
        ledfx_with_virtuals._virtuals["v1"] = v1

        service_v._state.current_gradient = (
            "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
        )

        result = service_v.apply_gradient_to_virtuals()
        assert result == 0

    def test_filters_by_virtual_ids(self, service_v, ledfx_with_virtuals):
        eff1 = _make_mock_effect(["gradient"])
        eff2 = _make_mock_effect(["gradient"])
        v1 = _make_mock_virtual("v1", eff1)
        v2 = _make_mock_virtual("v2", eff2)
        ledfx_with_virtuals._virtuals["v1"] = v1
        ledfx_with_virtuals._virtuals["v2"] = v2

        service_v.gradient_virtual_ids = ["v1"]
        service_v._state.current_gradient = (
            "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
        )

        result = service_v.apply_gradient_to_virtuals()
        assert result == 1
        eff1.update_config.assert_called_once()
        eff2.update_config.assert_not_called()

    def test_empty_virtual_ids_means_all(self, service_v, ledfx_with_virtuals):
        eff1 = _make_mock_effect(["gradient"])
        eff2 = _make_mock_effect(["gradient"])
        v1 = _make_mock_virtual("v1", eff1)
        v2 = _make_mock_virtual("v2", eff2)
        ledfx_with_virtuals._virtuals["v1"] = v1
        ledfx_with_virtuals._virtuals["v2"] = v2

        service_v.gradient_virtual_ids = []
        service_v._state.current_gradient = (
            "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
        )

        result = service_v.apply_gradient_to_virtuals()
        assert result == 2

    def test_hidden_keys_skipped(self, service_v, ledfx_with_virtuals):
        eff = _make_mock_effect(
            ["gradient", "color"], hidden_keys=["gradient"]
        )
        v1 = _make_mock_virtual("v1", eff)
        ledfx_with_virtuals._virtuals["v1"] = v1

        service_v._state.current_gradient = (
            "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
        )

        result = service_v.apply_gradient_to_virtuals()
        # Effect should still update if color key is in schema
        call_args = eff.update_config.call_args[0][0]
        assert "gradient" not in call_args
        assert "color" in call_args

    def test_effect_without_gradient_in_schema_gets_colors_only(
        self, service_v, ledfx_with_virtuals
    ):
        # Effect only has color keys, no gradient key
        eff = _make_mock_effect(["color", "color_high"])
        v1 = _make_mock_virtual("v1", eff)
        ledfx_with_virtuals._virtuals["v1"] = v1

        service_v._state.current_gradient = (
            "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
        )

        result = service_v.apply_gradient_to_virtuals()
        assert result == 1
        call_args = eff.update_config.call_args[0][0]
        assert "gradient" not in call_args
        assert "color" in call_args

    def test_saves_config_after_updates(self, service_v, ledfx_with_virtuals):
        eff = _make_mock_effect(["gradient"])
        v1 = _make_mock_virtual("v1", eff)
        ledfx_with_virtuals._virtuals["v1"] = v1

        service_v._state.current_gradient = (
            "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
        )

        with patch("ledfx.nowplaying.service.save_config") as mock_save:
            service_v.apply_gradient_to_virtuals()
            mock_save.assert_called_once()

    def test_no_config_save_when_nothing_updated(
        self, service_v, ledfx_with_virtuals
    ):
        # No virtuals, no updates
        service_v._state.current_gradient = (
            "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
        )

        with patch("ledfx.nowplaying.service.save_config") as mock_save:
            service_v.apply_gradient_to_virtuals()
            mock_save.assert_not_called()


class TestGradientAutoApplication:
    """Tests verifying gradient is auto-applied when artwork changes."""

    def test_gradient_applied_on_artwork_bytes(
        self, service_v, ledfx_with_virtuals
    ):
        eff = _make_mock_effect(["gradient", "color"])
        v1 = _make_mock_virtual("v1", eff)
        ledfx_with_virtuals._virtuals["v1"] = v1

        meta = TrackMetadata(source_id="sendspin", title="Song")
        service_v.set_metadata("sendspin", meta)

        data = _make_test_png()
        # Mock gradient extraction to return a valid gradient
        with patch(
            "ledfx.nowplaying.service.extract_gradient_metadata",
            return_value={
                "led_punchy": {
                    "gradient": "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
                }
            },
        ):
            with patch("ledfx.nowplaying.service.save_config"):
                service_v.set_artwork_bytes("sendspin", data, "image/png")

        # Effect should have been updated
        eff.update_config.assert_called_once()
        call_args = eff.update_config.call_args[0][0]
        assert "gradient" in call_args

    def test_gradient_not_applied_when_disabled(
        self, service_v, ledfx_with_virtuals
    ):
        eff = _make_mock_effect(["gradient", "color"])
        v1 = _make_mock_virtual("v1", eff)
        ledfx_with_virtuals._virtuals["v1"] = v1

        service_v.gradient_enabled = False

        meta = TrackMetadata(source_id="sendspin", title="Song")
        service_v.set_metadata("sendspin", meta)

        data = _make_test_png()
        with patch(
            "ledfx.nowplaying.service.extract_gradient_metadata",
            return_value={
                "led_punchy": {
                    "gradient": "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
                }
            },
        ):
            service_v.set_artwork_bytes("sendspin", data, "image/png")

        # Effect should NOT have been updated
        eff.update_config.assert_not_called()

    def test_gradient_event_still_fires_when_disabled(
        self, service_v, ledfx_with_virtuals
    ):
        """Gradient changed event fires even when application is disabled."""
        service_v.gradient_enabled = False

        meta = TrackMetadata(source_id="sendspin", title="Song")
        service_v.set_metadata("sendspin", meta)
        ledfx_with_virtuals.events.fired.clear()

        data = _make_test_png()
        with patch(
            "ledfx.nowplaying.service.extract_gradient_metadata",
            return_value={
                "led_punchy": {
                    "gradient": "linear-gradient(90deg, rgb(255, 0, 0) 0%, rgb(0, 0, 255) 100%)"
                }
            },
        ):
            service_v.set_artwork_bytes("sendspin", data, "image/png")

        gradient_events = [
            e
            for e in ledfx_with_virtuals.events.fired
            if e.event_type == Event.NOW_PLAYING_GRADIENT_CHANGED
        ]
        assert len(gradient_events) == 1
