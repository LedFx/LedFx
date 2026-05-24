"""Unit tests for the SMTC (Windows System Media Transport Controls) Now Playing provider."""

import sys
from types import ModuleType
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ledfx.nowplaying.providers.smtc import (
    SOURCE_ID,
    SMTCNowPlayingProvider,
)
from ledfx.nowplaying.service import NowPlayingService


# ------------------------------------------------------------------
# WinRT stub helpers
# ------------------------------------------------------------------


class _FakeToken:
    pass


class _FakeProps:
    def __init__(self, title="", artist="", album=""):
        self.title = title
        self.artist = artist
        self.album_title = album


class _FakeSession:
    def __init__(self, props=None, fail_props=False):
        self._props = props
        self._fail_props = fail_props

    async def try_get_media_properties_async(self):
        if self._fail_props:
            raise RuntimeError("props failed")
        return self._props

    def add_media_properties_changed(self, cb):
        return _FakeToken()

    def remove_media_properties_changed(self, tok):
        pass


class _FakeManager:
    def __init__(self, session=None):
        self._session = session

    def get_current_session(self):
        return self._session

    def add_current_session_changed(self, cb):
        return _FakeToken()

    def remove_current_session_changed(self, tok):
        pass


def _inject_winrt_modules(monkeypatch, manager=None, fail_request=False):
    """Inject fake winrt.windows.media.control into sys.modules."""
    control_mod = ModuleType("winrt.windows.media.control")

    media_manager_cls = MagicMock()
    if fail_request:
        media_manager_cls.request_async = AsyncMock(
            side_effect=RuntimeError("request failed")
        )
    else:
        media_manager_cls.request_async = AsyncMock(
            return_value=manager or _FakeManager()
        )
    control_mod.GlobalSystemMediaTransportControlsSessionManager = (
        media_manager_cls
    )

    for key in ("winrt", "winrt.windows", "winrt.windows.media"):
        if key not in sys.modules:
            monkeypatch.setitem(sys.modules, key, ModuleType(key))
    monkeypatch.setitem(
        sys.modules, "winrt.windows.media.control", control_mod
    )
    return control_mod


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
        self.now_playing = NowPlayingService(self)


@pytest.fixture
def ledfx():
    return _DummyLedFx()


@pytest.fixture
def provider(ledfx):
    return SMTCNowPlayingProvider(ledfx)


# ------------------------------------------------------------------
# Lifecycle tests
# ------------------------------------------------------------------


class TestSMTCProviderLifecycle:
    def test_init_state(self, ledfx):
        p = SMTCNowPlayingProvider(ledfx)
        assert p._manager is None
        assert p._manager_token is None
        assert p._session is None
        assert p._session_tokens == []
        assert p._init_task is None
        assert p._last_title is None
        assert p._last_artist is None
        assert p._last_album is None

    def test_start_non_windows_noop(self, provider):
        with patch.object(sys, "platform", "linux"):
            provider.start()
        assert provider._init_task is None

    async def test_start_on_windows_creates_task(self, provider, monkeypatch):
        _inject_winrt_modules(monkeypatch)
        with patch.object(sys, "platform", "win32"):
            provider.start()
        assert provider._init_task is not None
        provider._init_task.cancel()

    async def test_start_idempotent_while_running(self, provider, monkeypatch):
        _inject_winrt_modules(monkeypatch)
        with patch.object(sys, "platform", "win32"):
            provider.start()
            first_task = provider._init_task
            provider.start()  # second call should be a no-op
        assert provider._init_task is first_task
        first_task.cancel()

    async def test_stop_cancels_init_task(self, provider, monkeypatch):
        _inject_winrt_modules(monkeypatch)
        with patch.object(sys, "platform", "win32"):
            provider.start()
        assert provider._init_task is not None
        provider.stop()
        assert provider._init_task is None

    def test_stop_clears_state(self, provider):
        provider._last_title = "Song"
        provider._last_artist = "Artist"
        provider.stop()
        assert provider._last_title is None
        assert provider._last_artist is None

    def test_stop_when_never_started(self, provider):
        """stop() should not raise even if start() was never called."""
        provider.stop()  # should not raise


# ------------------------------------------------------------------
# Initialization tests
# ------------------------------------------------------------------


class TestSMTCInitialize:
    async def test_import_error_silently_returns(self, provider, monkeypatch):
        """If winrt is not available, _initialize() silently returns."""
        # Setting an entry to None in sys.modules forces ImportError
        # even when the real package is installed.
        with patch.dict(sys.modules, {
            "winrt": None,
            "winrt.windows": None,
            "winrt.windows.media": None,
            "winrt.windows.media.control": None,
        }):
            await provider._initialize()
        assert provider._manager is None

    async def test_request_async_failure(self, provider, monkeypatch):
        """If request_async raises, manager stays None."""
        _inject_winrt_modules(monkeypatch, fail_request=True)
        await provider._initialize()
        assert provider._manager is None

    async def test_subscribes_to_session_changed(self, provider, monkeypatch):
        """After successful init, manager and token are stored."""
        manager = _FakeManager(session=None)
        _inject_winrt_modules(monkeypatch, manager=manager)
        await provider._initialize()
        assert provider._manager is manager
        assert provider._manager_token is not None

    async def test_attaches_to_existing_session(self, provider, monkeypatch, ledfx):
        """If a session is already active, initial metadata is fetched."""
        props = _FakeProps(title="Song", artist="Artist", album="Album")
        session = _FakeSession(props=props)
        manager = _FakeManager(session=session)
        _inject_winrt_modules(monkeypatch, manager=manager)

        await provider._initialize()

        state = ledfx.now_playing.get_current()
        assert state.metadata is not None
        assert state.metadata.title == "Song"
        assert state.metadata.artist == "Artist"

    async def test_no_active_session_at_startup(self, provider, monkeypatch, ledfx):
        """If no session is active at startup, state stays empty."""
        manager = _FakeManager(session=None)
        _inject_winrt_modules(monkeypatch, manager=manager)

        await provider._initialize()

        state = ledfx.now_playing.get_current()
        assert state.metadata is None


# ------------------------------------------------------------------
# Session attachment tests
# ------------------------------------------------------------------


class TestAttachToSession:
    async def test_none_session_no_clear_when_empty(self, provider):
        """Attaching None when no previous content does not clear."""
        cleared = []
        provider._ledfx.now_playing.clear = lambda sid: cleared.append(sid)
        await provider._attach_to_session(None)
        assert cleared == []

    async def test_none_session_clears_when_had_content(self, provider):
        """Attaching None when we had previous content triggers a clear."""
        provider._last_title = "Old Song"
        cleared = []
        provider._ledfx.now_playing.clear = lambda sid: cleared.append(sid)

        await provider._attach_to_session(None)

        assert SOURCE_ID in cleared

    async def test_attach_new_session_subscribes_events(self, provider):
        """Attaching a session subscribes to media_properties_changed."""
        props = _FakeProps(title="T", artist="A", album="B")
        session = _FakeSession(props=props)
        await provider._attach_to_session(session)
        assert len(provider._session_tokens) == 1

    async def test_attach_replaces_previous_session(self, provider):
        """Attaching a new session detaches the previous one first."""
        props1 = _FakeProps(title="Song1")
        session1 = _FakeSession(props=props1)
        await provider._attach_to_session(session1)

        props2 = _FakeProps(title="Song2")
        session2 = _FakeSession(props=props2)
        await provider._attach_to_session(session2)

        assert provider._session is session2
        state = provider._ledfx.now_playing.get_current()
        assert state.metadata.title == "Song2"

    def test_detach_clears_tokens_and_session(self, provider):
        provider._session = MagicMock()
        provider._session_tokens = [(MagicMock(), _FakeToken())]
        provider._detach_session_events()
        assert provider._session_tokens == []
        assert provider._session is None


# ------------------------------------------------------------------
# Metadata fetch tests
# ------------------------------------------------------------------


class TestFetchAndPushMetadata:
    async def test_no_session_returns_early(self, provider):
        """With no session, _fetch_and_push_metadata() is a no-op."""
        provider._session = None
        await provider._fetch_and_push_metadata()
        state = provider._ledfx.now_playing.get_current()
        assert state.metadata is None

    async def test_props_failure_returns_early(self, provider):
        """If try_get_media_properties_async raises, we swallow it."""
        provider._session = _FakeSession(fail_props=True)
        await provider._fetch_and_push_metadata()
        assert provider._ledfx.now_playing.get_current().metadata is None

    async def test_none_props_triggers_maybe_clear(self, provider):
        """If props is None, previously cached content is cleared."""
        provider._session = _FakeSession(props=None)
        provider._last_title = "Old"
        cleared = []
        provider._ledfx.now_playing.clear = lambda sid: cleared.append(sid)

        await provider._fetch_and_push_metadata()

        assert SOURCE_ID in cleared

    async def test_basic_metadata_forwarded(self, provider, ledfx):
        """Full title/artist/album are forwarded to NowPlayingService."""
        props = _FakeProps(title="My Song", artist="My Artist", album="My Album")
        provider._session = _FakeSession(props=props)

        await provider._fetch_and_push_metadata()

        state = ledfx.now_playing.get_current()
        assert state.active_source_id == SOURCE_ID
        assert state.metadata.title == "My Song"
        assert state.metadata.artist == "My Artist"
        assert state.metadata.album == "My Album"

    async def test_empty_string_fields_become_none(self, provider, ledfx):
        """Empty string title/artist/album are coerced to None."""
        props = _FakeProps(title="", artist="", album="")
        provider._session = _FakeSession(props=props)

        await provider._fetch_and_push_metadata()

        state = ledfx.now_playing.get_current()
        assert state.metadata.title is None
        assert state.metadata.artist is None
        assert state.metadata.album is None

    async def test_no_now_playing_attr_returns_early(self, provider):
        """If now_playing is not on ledfx yet, no error is raised."""
        del provider._ledfx.now_playing
        props = _FakeProps(title="Song")
        provider._session = _FakeSession(props=props)
        # Should not raise
        await provider._fetch_and_push_metadata()

    async def test_cache_updated_after_fetch(self, provider):
        """_last_title/artist/album are updated after a successful fetch."""
        props = _FakeProps(title="T", artist="A", album="B")
        provider._session = _FakeSession(props=props)

        await provider._fetch_and_push_metadata()

        assert provider._last_title == "T"
        assert provider._last_artist == "A"
        assert provider._last_album == "B"


# ------------------------------------------------------------------
# State helper tests
# ------------------------------------------------------------------


class TestStateMethods:
    def test_maybe_clear_noop_when_no_content(self, provider):
        """_maybe_clear() does nothing when all cached values are None."""
        cleared = []
        provider._ledfx.now_playing.clear = lambda sid: cleared.append(sid)
        provider._maybe_clear()
        assert cleared == []

    def test_maybe_clear_fires_when_title_set(self, provider):
        provider._last_title = "Song"
        cleared = []
        provider._ledfx.now_playing.clear = lambda sid: cleared.append(sid)
        provider._maybe_clear()
        assert SOURCE_ID in cleared

    def test_maybe_clear_fires_when_artist_set(self, provider):
        provider._last_artist = "Artist"
        cleared = []
        provider._ledfx.now_playing.clear = lambda sid: cleared.append(sid)
        provider._maybe_clear()
        assert SOURCE_ID in cleared

    def test_maybe_clear_fires_when_album_set(self, provider):
        provider._last_album = "Album"
        cleared = []
        provider._ledfx.now_playing.clear = lambda sid: cleared.append(sid)
        provider._maybe_clear()
        assert SOURCE_ID in cleared

    def test_clear_resets_cache(self, provider):
        provider._last_title = "T"
        provider._last_artist = "A"
        provider._last_album = "B"
        provider.clear()
        assert provider._last_title is None
        assert provider._last_artist is None
        assert provider._last_album is None

    def test_clear_calls_now_playing_clear(self, provider):
        cleared = []
        provider._ledfx.now_playing.clear = lambda sid: cleared.append(sid)
        provider.clear()
        assert SOURCE_ID in cleared

    def test_clear_no_now_playing(self, provider):
        """clear() does not raise if now_playing is absent."""
        del provider._ledfx.now_playing
        provider.clear()  # should not raise
