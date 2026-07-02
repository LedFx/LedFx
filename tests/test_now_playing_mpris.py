"""Unit tests for the Linux MPRIS Now Playing provider."""

import sys
import pytest
from unittest.mock import AsyncMock, MagicMock, patch

dbus_fast = pytest.importorskip("dbus_fast")
MessageType = dbus_fast.MessageType

from ledfx.nowplaying.providers.mpris import (
    SOURCE_ID,
    MPRISNowPlayingProvider,
)


class _Variant:
    def __init__(self, value):
        self.value = value


class _Reply:
    def __init__(self, body=None, message_type=MessageType.METHOD_RETURN):
        self.body = body if body is not None else []
        self.message_type = message_type


class _DummyNowPlaying:
    def __init__(self):
        self.last_metadata = None
        self.cleared_sources = []
        self.artwork_url_calls = []
        self.artwork_bytes_calls = []
        self.clear_artwork_calls = []

    def set_metadata(self, source_id, metadata):
        self.last_metadata = (source_id, metadata)
        return True

    def clear(self, source_id):
        self.cleared_sources.append(source_id)

    def set_artwork_url(self, source_id, url):
        self.artwork_url_calls.append((source_id, url))
        return True

    def set_artwork_bytes(self, source_id, data, content_type):
        self.artwork_bytes_calls.append((source_id, data, content_type))
        return True

    def clear_artwork(self, source_id):
        self.clear_artwork_calls.append(source_id)


class _DummyLedFx:
    def __init__(self):
        self.now_playing = _DummyNowPlaying()


def _provider():
    return MPRISNowPlayingProvider(_DummyLedFx())


class TestMPRISLifecycle:
    def test_start_non_linux_noop(self):
        p = _provider()
        with patch.object(sys, "platform", "darwin"):
            p.start()
        assert p._init_task is None

    def test_clear_resets_provider_state(self):
        p = _provider()
        p._active_player_name = "org.mpris.MediaPlayer2.spotify"
        p._active_player_owner = ":1.123"
        p._known_players = {"org.mpris.MediaPlayer2.spotify"}

        p.clear()

        assert p._active_player_name is None
        assert p._active_player_owner is None
        assert p._known_players == set()
        assert p._ledfx.now_playing.cleared_sources == [SOURCE_ID]


class TestMPRISSelection:
    async def test_select_best_player_prefers_playing(self):
        p = _provider()
        p._list_mpris_players = AsyncMock(
            return_value=[
                "org.mpris.MediaPlayer2.firefox",
                "org.mpris.MediaPlayer2.spotify",
            ]
        )

        async def _status(name):
            return "Playing" if name.endswith("spotify") else "Paused"

        p._get_playback_status = _status
        p._get_name_owner = AsyncMock(return_value=":1.55")
        p._schedule_push_metadata = MagicMock()

        await p._select_best_player()

        assert p._active_player_name == "org.mpris.MediaPlayer2.spotify"
        assert p._active_player_owner == ":1.55"
        assert p._schedule_push_metadata.called

    async def test_select_best_player_clears_when_none(self):
        p = _provider()
        p._active_player_name = "org.mpris.MediaPlayer2.spotify"
        p._list_mpris_players = AsyncMock(return_value=[])

        await p._select_best_player()

        assert p._active_player_name is None
        assert p._ledfx.now_playing.cleared_sources == [SOURCE_ID]


class TestMPRISMetadata:
    async def test_push_metadata_forwards_track(self):
        p = _provider()
        p._active_player_name = "org.mpris.MediaPlayer2.spotify"

        props = {
            "PlaybackStatus": _Variant("Playing"),
            "Metadata": _Variant(
                {
                    "xesam:title": _Variant("Song"),
                    "xesam:artist": _Variant(["Artist"]),
                    "xesam:album": _Variant("Album"),
                    "mpris:trackid": _Variant("/org/mpris/track/1"),
                    "mpris:artUrl": _Variant("https://example.com/art.jpg"),
                }
            ),
        }
        p._call_method = AsyncMock(return_value=_Reply(body=[props]))

        await p._push_metadata()

        source_id, metadata = p._ledfx.now_playing.last_metadata
        assert source_id == SOURCE_ID
        assert metadata.title == "Song"
        assert metadata.artist == "Artist"
        assert metadata.album == "Album"
        assert metadata.track_id == "/org/mpris/track/1"
        assert metadata.artwork_url is None
        assert p._ledfx.now_playing.artwork_url_calls == []
        assert p._ledfx.now_playing.artwork_bytes_calls == []

    async def test_push_metadata_stopped_with_no_content_clears(self):
        p = _provider()
        p._active_player_name = "org.mpris.MediaPlayer2.spotify"

        props = {
            "PlaybackStatus": _Variant("Stopped"),
            "Metadata": _Variant({}),
        }
        p._call_method = AsyncMock(return_value=_Reply(body=[props]))

        await p._push_metadata()

        assert p._ledfx.now_playing.cleared_sources == [SOURCE_ID]


class TestMPRISArtworkRouting:
    async def test_provider_does_not_set_artwork_directly(self):
        p = _provider()
        p._active_player_name = "org.mpris.MediaPlayer2.spotify"

        props = {
            "PlaybackStatus": _Variant("Playing"),
            "Metadata": _Variant(
                {
                    "xesam:title": _Variant("Song"),
                    "xesam:artist": _Variant(["Artist"]),
                    "xesam:album": _Variant("Album"),
                    "mpris:artUrl": _Variant("file:///tmp/cover.png"),
                }
            ),
        }
        p._call_method = AsyncMock(return_value=_Reply(body=[props]))

        await p._push_metadata()

        np = p._ledfx.now_playing
        assert np.artwork_url_calls == []
        assert np.artwork_bytes_calls == []
        assert np.clear_artwork_calls == []
