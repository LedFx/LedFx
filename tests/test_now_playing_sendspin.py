"""Unit tests for the Sendspin Now Playing provider."""

import io
from dataclasses import dataclass, field
from unittest.mock import patch

import pytest
from PIL import Image

from ledfx.nowplaying.providers.sendspin import (
    SOURCE_ID,
    SendspinNowPlayingProvider,
)

# ------------------------------------------------------------------
# Stubs mimicking aiosendspin models
# ------------------------------------------------------------------


class _UndefinedField:
    """Stub for aiosendspin's UndefinedField sentinel."""

    pass


_UNDEFINED = _UndefinedField()


@dataclass
class _Progress:
    track_progress: int = 0
    track_duration: int = 0
    playback_speed: int = 1000


@dataclass
class _SessionUpdateMetadata:
    timestamp: int = 0
    title: object = field(default_factory=lambda: _UNDEFINED)
    artist: object = field(default_factory=lambda: _UNDEFINED)
    album_artist: object = field(default_factory=lambda: _UNDEFINED)
    album: object = field(default_factory=lambda: _UNDEFINED)
    artwork_url: object = field(default_factory=lambda: _UNDEFINED)
    year: object = field(default_factory=lambda: _UNDEFINED)
    track: object = field(default_factory=lambda: _UNDEFINED)
    progress: object = field(default_factory=lambda: _UNDEFINED)
    repeat: object = field(default_factory=lambda: _UNDEFINED)
    shuffle: object = field(default_factory=lambda: _UNDEFINED)


@dataclass
class _ServerStatePayload:
    metadata: object = None
    controller: object = None


# ------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------


class _DummyEvents:
    def __init__(self):
        self.fired = []

    def fire_event(self, event):
        self.fired.append(event)


class _DummyLedFx:
    def __init__(self):
        self.config = {}
        self.events = _DummyEvents()

        from ledfx.nowplaying.service import NowPlayingService

        self.now_playing = NowPlayingService(self)


@pytest.fixture
def ledfx():
    return _DummyLedFx()


@pytest.fixture
def provider(ledfx):
    return SendspinNowPlayingProvider(ledfx)


# ------------------------------------------------------------------
# Monkey-patch aiosendspin types for isinstance checks
# ------------------------------------------------------------------


@pytest.fixture(autouse=True)
def _patch_aiosendspin_types(monkeypatch):
    """Patch the aiosendspin imports used inside the provider."""
    # The provider does lazy imports inside on_metadata; patch them
    # at the module level via monkeypatch on the import mechanism
    import sys
    from types import ModuleType

    # Create fake modules
    metadata_mod = ModuleType("aiosendspin.models.metadata")
    metadata_mod.SessionUpdateMetadata = _SessionUpdateMetadata

    types_mod = ModuleType("aiosendspin.models.types")
    types_mod.UndefinedField = _UndefinedField

    monkeypatch.setitem(
        sys.modules, "aiosendspin.models.metadata", metadata_mod
    )
    monkeypatch.setitem(sys.modules, "aiosendspin.models.types", types_mod)


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


class TestSendspinProviderMetadata:
    def test_basic_metadata_forwarded(self, provider, ledfx):
        payload = _ServerStatePayload(
            metadata=_SessionUpdateMetadata(
                timestamp=1000,
                title="Song Title",
                artist="Artist Name",
                album="Album Name",
            )
        )
        provider.on_metadata(payload)

        state = ledfx.now_playing.get_current()
        assert state.active_source_id == SOURCE_ID
        assert state.metadata.title == "Song Title"
        assert state.metadata.artist == "Artist Name"
        assert state.metadata.album == "Album Name"

    def test_undefined_fields_retain_previous_value(self, provider, ledfx):
        # First message sets all fields
        payload1 = _ServerStatePayload(
            metadata=_SessionUpdateMetadata(
                timestamp=1000,
                title="Song",
                artist="Artist",
                album="Album",
            )
        )
        provider.on_metadata(payload1)

        # Second message only sends title (artist, album are UndefinedField)
        payload2 = _ServerStatePayload(
            metadata=_SessionUpdateMetadata(
                timestamp=2000,
                title="Song",
                # artist, album left as UndefinedField → retain previous
            )
        )
        provider.on_metadata(payload2)

        state = ledfx.now_playing.get_current()
        assert state.metadata.title == "Song"
        assert state.metadata.artist == "Artist"
        assert state.metadata.album == "Album"

    def test_undefined_fields_start_as_none(self, provider, ledfx):
        # First message only has title — other fields never sent
        payload = _ServerStatePayload(
            metadata=_SessionUpdateMetadata(
                timestamp=1000,
                title="Song",
                # artist, album left as UndefinedField
            )
        )
        provider.on_metadata(payload)

        state = ledfx.now_playing.get_current()
        assert state.metadata.title == "Song"
        assert state.metadata.artist is None
        assert state.metadata.album is None

    def test_incremental_accumulation_across_messages(self, provider, ledfx):
        """Multiple partial updates build up full state incrementally."""
        # Message 1: only title
        provider.on_metadata(
            _ServerStatePayload(
                metadata=_SessionUpdateMetadata(timestamp=1000, title="Song")
            )
        )
        state = ledfx.now_playing.get_current()
        assert state.metadata.title == "Song"
        assert state.metadata.artist is None
        assert state.metadata.album is None

        # Message 2: only artist
        provider.on_metadata(
            _ServerStatePayload(
                metadata=_SessionUpdateMetadata(
                    timestamp=2000, artist="Artist"
                )
            )
        )
        state = ledfx.now_playing.get_current()
        assert state.metadata.title == "Song"
        assert state.metadata.artist == "Artist"
        assert state.metadata.album is None

        # Message 3: only album
        provider.on_metadata(
            _ServerStatePayload(
                metadata=_SessionUpdateMetadata(timestamp=3000, album="Album")
            )
        )
        state = ledfx.now_playing.get_current()
        assert state.metadata.title == "Song"
        assert state.metadata.artist == "Artist"
        assert state.metadata.album == "Album"

    def test_explicit_none_clears_field(self, provider, ledfx):
        """Explicit None clears a previously set field."""
        # Set all fields
        provider.on_metadata(
            _ServerStatePayload(
                metadata=_SessionUpdateMetadata(
                    timestamp=1000,
                    title="Song",
                    artist="Artist",
                    album="Album",
                )
            )
        )
        # Explicitly clear artist
        provider.on_metadata(
            _ServerStatePayload(
                metadata=_SessionUpdateMetadata(timestamp=2000, artist=None)
            )
        )
        state = ledfx.now_playing.get_current()
        assert state.metadata.title == "Song"
        assert state.metadata.artist is None
        assert state.metadata.album == "Album"

    def test_progress_converted_to_seconds(self, provider, ledfx):
        payload = _ServerStatePayload(
            metadata=_SessionUpdateMetadata(
                timestamp=1000,
                title="Song",
                progress=_Progress(
                    track_progress=45000,  # 45 seconds in ms
                    track_duration=180000,  # 3 minutes in ms
                    playback_speed=1000,
                ),
            )
        )
        provider.on_metadata(payload)

        state = ledfx.now_playing.get_current()
        assert state.metadata.position == 45.0
        assert state.metadata.duration == 180.0

    def test_zero_duration_treated_as_none(self, provider, ledfx):
        payload = _ServerStatePayload(
            metadata=_SessionUpdateMetadata(
                timestamp=1000,
                title="Live Stream",
                progress=_Progress(
                    track_progress=10000,
                    track_duration=0,  # unknown/live
                    playback_speed=1000,
                ),
            )
        )
        provider.on_metadata(payload)

        state = ledfx.now_playing.get_current()
        assert state.metadata.position == 10.0
        assert state.metadata.duration is None

    def test_none_metadata_ignored(self, provider, ledfx):
        payload = _ServerStatePayload(metadata=None)
        provider.on_metadata(payload)

        state = ledfx.now_playing.get_current()
        assert state.metadata is None

    def test_artwork_url_forwarded(self, provider, ledfx):
        # Create a valid test PNG for download mock
        buf = io.BytesIO()
        Image.new("RGB", (4, 4), color="red").save(buf, format="PNG")
        test_png = buf.getvalue()

        with patch.object(
            ledfx.now_playing,
            "_download_image",
            return_value=(test_png, "image/png"),
        ):
            payload = _ServerStatePayload(
                metadata=_SessionUpdateMetadata(
                    timestamp=1000,
                    title="Song",
                    artwork_url="https://example.com/art.jpg",
                )
            )
            provider.on_metadata(payload)

        state = ledfx.now_playing.get_current()
        assert state.artwork is not None
        assert state.artwork.url == "https://example.com/art.jpg"

    def test_same_artwork_url_not_re_sent(self, provider, ledfx):
        buf = io.BytesIO()
        Image.new("RGB", (4, 4), color="red").save(buf, format="PNG")
        test_png = buf.getvalue()

        with patch.object(
            ledfx.now_playing,
            "_download_image",
            return_value=(test_png, "image/png"),
        ):
            payload = _ServerStatePayload(
                metadata=_SessionUpdateMetadata(
                    timestamp=1000,
                    title="Song",
                    artwork_url="https://example.com/art.jpg",
                )
            )
            provider.on_metadata(payload)
            ledfx.events.fired.clear()

            # Same metadata again
            provider.on_metadata(payload)

        from ledfx.events import Event

        artwork_events = [
            e
            for e in ledfx.events.fired
            if e.event_type == Event.NOW_PLAYING_ARTWORK_CHANGED
        ]
        assert len(artwork_events) == 0

    def test_different_artwork_url_sent(self, provider, ledfx):
        buf = io.BytesIO()
        Image.new("RGB", (4, 4), color="red").save(buf, format="PNG")
        test_png = buf.getvalue()

        with patch.object(
            ledfx.now_playing,
            "_download_image",
            return_value=(test_png, "image/png"),
        ):
            payload1 = _ServerStatePayload(
                metadata=_SessionUpdateMetadata(
                    timestamp=1000,
                    title="Song",
                    artwork_url="https://example.com/art1.jpg",
                )
            )
            provider.on_metadata(payload1)
            ledfx.events.fired.clear()

            payload2 = _ServerStatePayload(
                metadata=_SessionUpdateMetadata(
                    timestamp=2000,
                    title="Song",
                    artwork_url="https://example.com/art2.jpg",
                )
            )
            provider.on_metadata(payload2)

        state = ledfx.now_playing.get_current()
        assert state.artwork.url == "https://example.com/art2.jpg"


class TestSendspinProviderClear:
    def test_clear_resets_state(self, provider, ledfx):
        payload = _ServerStatePayload(
            metadata=_SessionUpdateMetadata(
                timestamp=1000,
                title="Song",
                artist="Artist",
            )
        )
        provider.on_metadata(payload)
        provider.clear()

        state = ledfx.now_playing.get_current()
        assert state.metadata is None
        assert state.active_source_id is None

    def test_clear_resets_artwork_tracking(self, provider, ledfx):
        payload = _ServerStatePayload(
            metadata=_SessionUpdateMetadata(
                timestamp=1000,
                title="Song",
                artwork_url="https://example.com/art.jpg",
            )
        )
        provider.on_metadata(payload)
        provider.clear()

        assert provider._last_artwork_url is None


class TestSendspinProviderNoLedfx:
    def test_no_now_playing_graceful(self):
        """Provider should not crash if ledfx has no now_playing attribute."""

        class _BareLedfx:
            pass

        provider = SendspinNowPlayingProvider(_BareLedfx())
        payload = _ServerStatePayload(
            metadata=_SessionUpdateMetadata(
                timestamp=1000,
                title="Song",
            )
        )
        # Should not raise
        provider.on_metadata(payload)
        provider.clear()
