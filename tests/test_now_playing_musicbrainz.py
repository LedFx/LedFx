"""Unit tests for MusicBrainz release scoring heuristics."""

from ledfx.nowplaying.album_art.musicbrainz import _release_score


def _release(title: str, artist: str, primary_type: str = "single") -> dict:
    return {
        "title": title,
        "artist-credit": [{"name": artist}],
        "release-group": {
            "primary-type": primary_type,
            "secondary-types": [],
        },
        "status": "Official",
        "date": "2003-01-01",
    }


def test_release_artist_exact_match_scores_much_higher_than_mismatch():
    base_score = 100.0
    base_reasons = ["seed"]

    good_release = _release("Seven Nation Army", "The White Stripes")
    bad_release = _release("Seven Nation Army", "London Philharmonic Orchestra")

    good_score, _ = _release_score(
        good_release,
        base_score,
        base_reasons,
        artist="The White Stripes",
        title="Seven Nation Army",
        album=None,
    )
    bad_score, _ = _release_score(
        bad_release,
        base_score,
        base_reasons,
        artist="The White Stripes",
        title="Seven Nation Army",
        album=None,
    )

    assert good_score > bad_score + 80


def test_various_artists_release_gets_strong_penalty():
    base_score = 100.0
    base_reasons = ["seed"]

    canonical = _release("Seven Nation Army", "The White Stripes")
    various = _release("Seven Nation Army", "Various Artists")

    canonical_score, _ = _release_score(
        canonical,
        base_score,
        base_reasons,
        artist="The White Stripes",
        title="Seven Nation Army",
        album=None,
    )
    various_score, _ = _release_score(
        various,
        base_score,
        base_reasons,
        artist="The White Stripes",
        title="Seven Nation Army",
        album=None,
    )

    assert canonical_score > various_score + 60


def test_release_score_reason_includes_artist_mismatch_marker():
    release = _release("Seven Nation Army", "Totally Different Orchestra")
    _score, reason = _release_score(
        release,
        base_score=100.0,
        base_reasons=["seed"],
        artist="The White Stripes",
        title="Seven Nation Army",
        album=None,
    )

    assert "release_artist_mismatch" in reason
