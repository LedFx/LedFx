"""Unit tests for MusicBrainz release scoring heuristics."""

import pytest

from ledfx.nowplaying.album_art.musicbrainz import (
    MusicBrainzArtProvider,
    _contains_bad_variant,
    _release_score,
)


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
    bad_release = _release(
        "Seven Nation Army", "London Philharmonic Orchestra"
    )

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


def test_bad_variant_matching_uses_word_boundaries():
    assert _contains_bad_variant("Live at Wembley") is True
    assert _contains_bad_variant("Olive Branch") is False


def test_build_queries_escapes_embedded_quotes():
    provider = MusicBrainzArtProvider()
    queries = provider._build_queries(
        artist='AC/DC "Live"',
        title='He said "Hi"',
        album='Best of "Era"',
    )

    assert (
        'recording:"He said \\"Hi\\""'
        ' AND artistname:"AC/DC \\"Live\\""'
        ' AND release:"Best of \\"Era\\""'
    ) in queries


@pytest.mark.asyncio
async def test_release_dedup_keeps_best_scoring_candidate():
    provider = MusicBrainzArtProvider()

    async def fake_search(_query):
        return [
            {
                "id": "r1",
                "score": 1,
                "title": "Song",
                "artist-credit": [{"name": "Artist"}],
                "releases": [
                    {
                        "id": "rel1",
                        "title": "Song",
                        "artist-credit": [{"name": "Wrong"}],
                        "release-group": {
                            "primary-type": "single",
                            "secondary-types": [],
                        },
                        "status": "Official",
                    }
                ],
            },
            {
                "id": "r2",
                "score": 100,
                "title": "Song",
                "artist-credit": [{"name": "Artist"}],
                "releases": [
                    {
                        "id": "rel1",
                        "title": "Song",
                        "artist-credit": [{"name": "Artist"}],
                        "release-group": {
                            "primary-type": "single",
                            "secondary-types": [],
                        },
                        "status": "Official",
                    }
                ],
            },
        ]

    provider._build_queries = lambda *_args: ["q"]
    provider._search_recordings = fake_search

    candidates = await provider._search_release_candidates(
        artist="Artist",
        title="Song",
        album=None,
    )

    assert len(candidates) == 1
    assert candidates[0].recording_id == "r2"
    assert "release_artist_exact" in candidates[0].reason
