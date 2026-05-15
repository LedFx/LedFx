"""Unit tests for the Now Playing Service (Phase 1 + Phase 3 events + Phase 5 artwork)."""

import io
import os
import time
from unittest.mock import patch

import pytest
from PIL import Image

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

        # Second: JPEG (different extension)
        jpeg_data = _make_test_jpeg()
        service.set_artwork_bytes("sendspin", jpeg_data, "image/jpeg")
        jpg_path = os.path.join(
            ledfx.config_dir, "assets", "now_playing", "now_playing.jpg"
        )
        assert os.path.exists(jpg_path)
        # Old PNG file should have been removed
        assert not os.path.exists(png_path)


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
