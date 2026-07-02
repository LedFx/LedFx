"""Unit tests for Now Playing metadata normalisation helpers."""

from ledfx.nowplaying.normalise import normalise_title


def test_official_video_suffix_with_trailing_text_is_stripped():
    title = "Stand Back (Official Music Video) [HD Remaster]"
    assert normalise_title(title, artist="Stevie Nicks") == "Stand Back"


def test_official_video_bracket_with_following_text_is_stripped():
    title = "Song [Official Music Video] feat. X"
    assert normalise_title(title, artist="Artist") == "Song"


def test_terminal_official_video_suffix_is_stripped():
    title = "Artist - Song (Official Music Video)"
    assert normalise_title(title, artist="Artist") == "Song"
