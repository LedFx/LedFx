"""Unit tests for the Now Playing Service (Phase 1 + Phase 3 events + Phase 5 artwork + Phase 6 gradient application + Phase 7 configuration)."""

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


# ------------------------------------------------------------------
# Phase 7: Configuration persistence tests
# ------------------------------------------------------------------


class TestNowPlayingConfigSchema:
    """Tests for NOW_PLAYING_CONFIG_SCHEMA validation."""

    def test_default_config_is_valid(self):
        from ledfx.nowplaying.service import NOW_PLAYING_CONFIG_SCHEMA

        result = NOW_PLAYING_CONFIG_SCHEMA({})
        assert result["gradient"]["enabled"] is True
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
        from ledfx.nowplaying.service import NOW_PLAYING_CONFIG_SCHEMA

        with pytest.raises(vol.Invalid):
            NOW_PLAYING_CONFIG_SCHEMA(
                {"gradient": {"variant": "not_a_variant"}}
            )

    def test_invalid_enabled_rejected(self):
        from ledfx.nowplaying.service import NOW_PLAYING_CONFIG_SCHEMA

        with pytest.raises(vol.Invalid):
            NOW_PLAYING_CONFIG_SCHEMA(
                {"track_text": {"enabled": "not_a_bool"}}
            )

    def test_duration_out_of_range(self):
        from ledfx.nowplaying.service import NOW_PLAYING_CONFIG_SCHEMA

        with pytest.raises(vol.Invalid):
            NOW_PLAYING_CONFIG_SCHEMA({"track_text": {"duration": -1}})

        with pytest.raises(vol.Invalid):
            NOW_PLAYING_CONFIG_SCHEMA({"album_art": {"duration": 999}})

    def test_all_variants_accepted(self):
        from ledfx.nowplaying.service import NOW_PLAYING_CONFIG_SCHEMA

        for v in ("led_safe", "led_punchy", "led_max"):
            result = NOW_PLAYING_CONFIG_SCHEMA({"gradient": {"variant": v}})
            assert result["gradient"]["variant"] == v

    def test_enabled_flag_accepted(self):
        from ledfx.nowplaying.service import NOW_PLAYING_CONFIG_SCHEMA

        for v in (True, False):
            result = NOW_PLAYING_CONFIG_SCHEMA({"track_text": {"enabled": v}})
            assert result["track_text"]["enabled"] is v


class TestServiceConfigFromInit:
    """Tests that NowPlayingService loads config on init."""

    def test_default_config_loaded(self, service):
        cfg = service.config
        assert cfg["gradient"]["enabled"] is True
        assert cfg["gradient"]["variant"] == "led_punchy"
        assert cfg["gradient"]["virtual_ids"] == []
        assert cfg["track_text"]["enabled"] is True
        assert cfg["album_art"]["enabled"] is True

    def test_persisted_config_loaded(self, tmp_path):
        ldfx = _DummyLedFx(config_dir=str(tmp_path))
        ldfx.config = {
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
        ldfx.config = {
            "now_playing": {
                "gradient": {"variant": "led_safe"},
            }
        }
        svc = NowPlayingService(ldfx)
        assert svc.get_current().selected_gradient_variant == "led_safe"


class TestUpdateConfig:
    """Tests for update_config() method."""

    def test_partial_update_gradient(self, service, ledfx):
        with patch("ledfx.nowplaying.service.save_config"):
            result = service.update_config({"gradient": {"enabled": False}})
        assert result["gradient"]["enabled"] is False
        # Other gradient fields retain defaults
        assert result["gradient"]["variant"] == "led_punchy"
        assert result["gradient"]["virtual_ids"] == []
        assert service.gradient_enabled is False

    def test_partial_update_track_text(self, service, ledfx):
        with patch("ledfx.nowplaying.service.save_config"):
            result = service.update_config(
                {"track_text": {"enabled": False, "duration": 12}}
            )
        assert result["track_text"]["enabled"] is False
        assert result["track_text"]["duration"] == 12
        assert result["track_text"]["preset"] == ""

    def test_partial_update_album_art(self, service, ledfx):
        with patch("ledfx.nowplaying.service.save_config"):
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
        with patch("ledfx.nowplaying.service.save_config"):
            result = service.update_config(new_cfg)

        assert result == new_cfg
        assert service.gradient_enabled is False
        assert service.gradient_virtual_ids == ["v1"]

    def test_invalid_config_raises(self, service):
        with pytest.raises(vol.Invalid):
            service.update_config({"gradient": {"variant": "bad"}})

    def test_config_persisted_to_disk(self, service, ledfx):
        with patch("ledfx.nowplaying.service.save_config") as mock_save:
            service.update_config({"gradient": {"enabled": False}})
            mock_save.assert_called_once()

        assert ledfx.config["now_playing"]["gradient"]["enabled"] is False

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

        with patch("ledfx.nowplaying.service.save_config"):
            service.update_config({"gradient": {"variant": "led_max"}})

        assert "0,255,0" in service.get_current().current_gradient

    def test_variant_change_no_re_resolve_when_unchanged(self, service, ledfx):
        """No re-resolve when variant doesn't change."""
        with patch.object(service, "_update_current_gradient") as mock_update:
            with patch("ledfx.nowplaying.service.save_config"):
                service.update_config({"gradient": {"variant": "led_punchy"}})
            mock_update.assert_not_called()

    def test_update_preserves_unrelated_sections(self, service, ledfx):
        """Updating gradient section preserves track_text and album_art."""
        with patch("ledfx.nowplaying.service.save_config"):
            service.update_config(
                {"track_text": {"enabled": False, "duration": 5}}
            )
            service.update_config({"gradient": {"enabled": False}})

        cfg = service.config
        assert cfg["gradient"]["enabled"] is False
        assert cfg["track_text"]["enabled"] is False
        assert cfg["track_text"]["duration"] == 5


# ------------------------------------------------------------------
# Phase 9: Album artwork temporary display tests
# ------------------------------------------------------------------


def _make_mock_virtual_with_set_effect(vid):
    """Create a mock virtual with a trackable set_effect method."""
    virtual = MagicMock()
    virtual.id = vid
    return virtual


class _DummyEffectsRegistry:
    """Minimal effects registry that returns a mock effect from create()."""

    def __init__(self):
        self.created = []

    def create(self, ledfx, type, config):
        effect = MagicMock()
        effect.type = type
        effect.config = config
        self.created.append(effect)
        return effect


class _DummyLedFxWithAlbumArt(_DummyLedFxWithVirtuals):
    """Stub with both virtuals and effects, for album art tests."""

    def __init__(self, config_dir=None):
        super().__init__(config_dir)
        self.effects = _DummyEffectsRegistry()
        self.audio = MagicMock()
        self.audio._audio_stream_active = True


@pytest.fixture
def ledfx_album_art(tmp_path):
    return _DummyLedFxWithAlbumArt(config_dir=str(tmp_path))


@pytest.fixture
def service_aa(ledfx_album_art):
    svc = NowPlayingService(ledfx_album_art)
    # activate source so set_artwork_* calls are accepted
    from ledfx.nowplaying.models import TrackMetadata

    svc.set_metadata(
        "sendspin", TrackMetadata(source_id="sendspin", title="T")
    )
    return svc


def _set_artwork_on_service(svc, cache_key="/tmp/now_playing.jpg"):
    """Directly set an ArtworkReference with a cache_key on the service."""
    svc._state.artwork = ArtworkReference(
        source_id="sendspin",
        cache_key=cache_key,
        content_type="image/jpeg",
    )


class TestApplyAlbumArtToVirtuals:
    """Tests for NowPlayingService._apply_album_art_to_virtuals()."""

    def test_disabled_returns_zero(self, service_aa, ledfx_album_art):
        service_aa._config["album_art"]["enabled"] = False
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        _set_artwork_on_service(service_aa)
        v1 = _make_mock_virtual_with_set_effect("v1")
        ledfx_album_art._virtuals["v1"] = v1

        assert service_aa._apply_album_art_to_virtuals() == 0
        v1.set_effect.assert_not_called()

    def test_empty_virtual_ids_returns_zero(self, service_aa, ledfx_album_art):
        # album_art.virtual_ids defaults to []
        _set_artwork_on_service(service_aa)
        v1 = _make_mock_virtual_with_set_effect("v1")
        ledfx_album_art._virtuals["v1"] = v1

        assert service_aa._apply_album_art_to_virtuals() == 0
        v1.set_effect.assert_not_called()

    def test_no_artwork_returns_zero(self, service_aa, ledfx_album_art):
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        # artwork is None
        service_aa._state.artwork = None

        assert service_aa._apply_album_art_to_virtuals() == 0

    def test_no_cache_key_returns_zero(self, service_aa, ledfx_album_art):
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        service_aa._state.artwork = ArtworkReference(
            source_id="sendspin", cache_key=None
        )

        assert service_aa._apply_album_art_to_virtuals() == 0

    def test_no_virtuals_attr_returns_zero(self, service, ledfx):
        """_DummyLedFx has no virtuals attribute — should return 0."""
        service._config["album_art"]["enabled"] = True
        service._config["album_art"]["virtual_ids"] = ["v1"]
        _set_artwork_on_service(service)

        assert service._apply_album_art_to_virtuals() == 0

    def test_no_effects_attr_returns_zero(
        self, service_v, ledfx_with_virtuals
    ):
        """ledfx with virtuals but no effects registry returns 0."""
        service_v._config["album_art"]["enabled"] = True
        service_v._config["album_art"]["virtual_ids"] = ["v1"]
        _set_artwork_on_service(service_v)
        ledfx_with_virtuals._virtuals["v1"] = (
            _make_mock_virtual_with_set_effect("v1")
        )
        # _DummyLedFxWithVirtuals has no effects attribute
        assert service_v._apply_album_art_to_virtuals() == 0

    def test_temporary_mode_uses_fallback(self, service_aa, ledfx_album_art):
        """duration > 0 → set_effect(effect, fallback=duration)."""
        service_aa._config["album_art"]["enabled"] = True
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        service_aa._config["album_art"]["duration"] = 8
        _set_artwork_on_service(service_aa, "/tmp/art.jpg")
        v1 = _make_mock_virtual_with_set_effect("v1")
        ledfx_album_art._virtuals["v1"] = v1

        result = service_aa._apply_album_art_to_virtuals()

        assert result == 1
        v1.set_effect.assert_called_once()
        call_args, call_kwargs = v1.set_effect.call_args
        assert call_kwargs.get("fallback") == 8.0 or (
            len(call_args) > 1 and call_args[1] == 8.0
        )

    def test_permanent_mode_no_fallback(self, service_aa, ledfx_album_art):
        """duration == 0 → set_effect(effect) with no fallback argument."""
        service_aa._config["album_art"]["enabled"] = True
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        service_aa._config["album_art"]["duration"] = 0
        _set_artwork_on_service(service_aa, "/tmp/art.jpg")
        v1 = _make_mock_virtual_with_set_effect("v1")
        ledfx_album_art._virtuals["v1"] = v1

        result = service_aa._apply_album_art_to_virtuals()

        assert result == 1
        v1.set_effect.assert_called_once()
        call_args, call_kwargs = v1.set_effect.call_args
        # No fallback keyword
        assert "fallback" not in call_kwargs
        # Only the effect positional arg
        assert len(call_args) == 1

    def test_image_source_config_uses_cache_key(
        self, service_aa, ledfx_album_art
    ):
        """Effect is created with image_source set to artwork.cache_key."""
        service_aa._config["album_art"]["enabled"] = True
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        cache_key = "/config/assets/now_playing/now_playing.jpg"
        _set_artwork_on_service(service_aa, cache_key)
        v1 = _make_mock_virtual_with_set_effect("v1")
        ledfx_album_art._virtuals["v1"] = v1

        service_aa._apply_album_art_to_virtuals()

        assert len(ledfx_album_art.effects.created) == 1
        created = ledfx_album_art.effects.created[0]
        assert created.config["image_source"] == cache_key

    def test_created_effect_type_is_image(self, service_aa, ledfx_album_art):
        service_aa._config["album_art"]["enabled"] = True
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        _set_artwork_on_service(service_aa)
        ledfx_album_art._virtuals["v1"] = _make_mock_virtual_with_set_effect(
            "v1"
        )

        service_aa._apply_album_art_to_virtuals()

        assert ledfx_album_art.effects.created[0].type == "imagespin"

    def test_multiple_virtuals_updated(self, service_aa, ledfx_album_art):
        service_aa._config["album_art"]["enabled"] = True
        service_aa._config["album_art"]["virtual_ids"] = ["v1", "v2"]
        _set_artwork_on_service(service_aa)
        v1 = _make_mock_virtual_with_set_effect("v1")
        v2 = _make_mock_virtual_with_set_effect("v2")
        ledfx_album_art._virtuals["v1"] = v1
        ledfx_album_art._virtuals["v2"] = v2

        result = service_aa._apply_album_art_to_virtuals()

        assert result == 2
        v1.set_effect.assert_called_once()
        v2.set_effect.assert_called_once()

    def test_missing_virtual_skipped(self, service_aa, ledfx_album_art):
        service_aa._config["album_art"]["enabled"] = True
        service_aa._config["album_art"]["virtual_ids"] = ["v1", "missing"]
        _set_artwork_on_service(service_aa)
        v1 = _make_mock_virtual_with_set_effect("v1")
        ledfx_album_art._virtuals["v1"] = v1
        # "missing" is not in virtuals dict

        result = service_aa._apply_album_art_to_virtuals()

        assert result == 1
        v1.set_effect.assert_called_once()

    def test_effect_creation_error_skips_virtual(
        self, service_aa, ledfx_album_art
    ):
        service_aa._config["album_art"]["enabled"] = True
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        _set_artwork_on_service(service_aa)
        ledfx_album_art._virtuals["v1"] = _make_mock_virtual_with_set_effect(
            "v1"
        )

        ledfx_album_art.effects.create = MagicMock(
            side_effect=Exception("creation failure")
        )

        result = service_aa._apply_album_art_to_virtuals()

        assert result == 0  # graceful skip

    def test_set_effect_error_skips_virtual(self, service_aa, ledfx_album_art):
        service_aa._config["album_art"]["enabled"] = True
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        _set_artwork_on_service(service_aa)
        v1 = _make_mock_virtual_with_set_effect("v1")
        v1.set_effect.side_effect = Exception("set_effect failure")
        ledfx_album_art._virtuals["v1"] = v1

        result = service_aa._apply_album_art_to_virtuals()

        assert result == 0  # graceful skip


class TestAlbumArtAutoApplication:
    """Tests that _apply_album_art_to_virtuals is triggered by artwork changes."""

    def test_called_on_set_artwork_bytes(self, service_aa, ledfx_album_art):
        service_aa._config["album_art"]["enabled"] = True
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        v1 = _make_mock_virtual_with_set_effect("v1")
        ledfx_album_art._virtuals["v1"] = v1

        data = _make_test_png()
        with patch(
            "ledfx.nowplaying.service.extract_gradient_metadata",
            return_value={},
        ):
            with patch("ledfx.nowplaying.service.save_config"):
                service_aa.set_artwork_bytes("sendspin", data, "image/png")

        v1.set_effect.assert_called_once()

    def test_called_on_set_artwork_url(self, service_aa, ledfx_album_art):
        service_aa._config["album_art"]["enabled"] = True
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        v1 = _make_mock_virtual_with_set_effect("v1")
        ledfx_album_art._virtuals["v1"] = v1

        png_data = _make_test_png()
        with patch.object(
            service_aa, "_download_image", return_value=(png_data, "image/png")
        ):
            with patch(
                "ledfx.nowplaying.service.extract_gradient_metadata",
                return_value={},
            ):
                with patch("ledfx.nowplaying.service.save_config"):
                    service_aa.set_artwork_url(
                        "sendspin", "https://example.com/art.png"
                    )

        v1.set_effect.assert_called_once()

    def test_not_called_when_disabled(self, service_aa, ledfx_album_art):
        service_aa._config["album_art"]["enabled"] = False
        service_aa._config["album_art"]["virtual_ids"] = ["v1"]
        v1 = _make_mock_virtual_with_set_effect("v1")
        ledfx_album_art._virtuals["v1"] = v1

        data = _make_test_png()
        with patch(
            "ledfx.nowplaying.service.extract_gradient_metadata",
            return_value={},
        ):
            with patch("ledfx.nowplaying.service.save_config"):
                service_aa.set_artwork_bytes("sendspin", data, "image/png")

        v1.set_effect.assert_not_called()

    def test_not_called_when_virtual_ids_empty(
        self, service_aa, ledfx_album_art
    ):
        service_aa._config["album_art"]["enabled"] = True
        # virtual_ids is [] by default
        v1 = _make_mock_virtual_with_set_effect("v1")
        ledfx_album_art._virtuals["v1"] = v1

        data = _make_test_png()
        with patch(
            "ledfx.nowplaying.service.extract_gradient_metadata",
            return_value={},
        ):
            with patch("ledfx.nowplaying.service.save_config"):
                service_aa.set_artwork_bytes("sendspin", data, "image/png")

        v1.set_effect.assert_not_called()


class TestAlbumArtDurationSchema:
    """Tests that the duration=0 schema change works correctly."""

    def test_duration_zero_accepted_for_album_art(self):
        from ledfx.nowplaying.service import NOW_PLAYING_CONFIG_SCHEMA

        result = NOW_PLAYING_CONFIG_SCHEMA({"album_art": {"duration": 0}})
        assert result["album_art"]["duration"] == 0

    def test_duration_negative_still_invalid_for_track_text(self):
        from ledfx.nowplaying.service import NOW_PLAYING_CONFIG_SCHEMA

        with pytest.raises(vol.Invalid):
            NOW_PLAYING_CONFIG_SCHEMA({"track_text": {"duration": -1}})

    def test_album_art_duration_max_still_enforced(self):
        from ledfx.nowplaying.service import NOW_PLAYING_CONFIG_SCHEMA

        with pytest.raises(vol.Invalid):
            NOW_PLAYING_CONFIG_SCHEMA({"album_art": {"duration": 61}})
